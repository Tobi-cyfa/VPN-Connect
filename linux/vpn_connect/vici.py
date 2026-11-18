"""Minimal client for strongSwan's VICI protocol (the socket swanctl talks to).

Wire format: https://docs.strongswan.org/docs/latest/plugins/vici.html

Author: zero.cyfa
"""

import socket
import struct

SOCKET_PATHS = ("/run/strongswan/charon.vici", "/var/run/charon.vici", "/run/charon.vici")

# packet types
CMD_REQUEST, CMD_RESPONSE, CMD_UNKNOWN = 0, 1, 2
EVENT_REGISTER, EVENT_UNREGISTER, EVENT_CONFIRM, EVENT_UNKNOWN, EVENT = 3, 4, 5, 6, 7

# message element types
SECTION_START, SECTION_END, KEY_VALUE, LIST_START, LIST_ITEM, LIST_END = 1, 2, 3, 4, 5, 6

MAX_PACKET = 512 * 1024


class ViciError(Exception):
    pass


def _bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bool):
        return b"yes" if value else b"no"
    return str(value).encode("utf-8")


def _name(name):
    b = _bytes(name)
    if not b or len(b) > 255:
        raise ViciError("invalid name %r" % name)
    return struct.pack("!B", len(b)) + b


def _value(value):
    b = _bytes(value)
    if len(b) > 0xFFFF:
        raise ViciError("value too long")
    return struct.pack("!H", len(b)) + b


def encode(message):
    """Encode a dict (values: str/int/bool, list of those, or nested dict)."""
    out = bytearray()
    for key, value in message.items():
        if isinstance(value, dict):
            out += bytes([SECTION_START]) + _name(key) + encode(value) + bytes([SECTION_END])
        elif isinstance(value, (list, tuple)):
            out += bytes([LIST_START]) + _name(key)
            for item in value:
                out += bytes([LIST_ITEM]) + _value(item)
            out += bytes([LIST_END])
        else:
            out += bytes([KEY_VALUE]) + _name(key) + _value(value)
    return bytes(out)


def decode(data):
    """Decode a message into nested dicts; values become str, lists become lists of str."""
    root = {}
    stack = [root]
    current_list = None
    pos = 0

    def take(n):
        nonlocal pos
        if pos + n > len(data):
            raise ViciError("truncated message")
        chunk = data[pos:pos + n]
        pos += n
        return chunk

    def take_name():
        return take(take(1)[0]).decode("utf-8", "replace")

    def take_value():
        (n,) = struct.unpack("!H", take(2))
        return take(n).decode("utf-8", "replace")

    while pos < len(data):
        kind = take(1)[0]
        if kind == SECTION_START:
            section = {}
            stack[-1][take_name()] = section
            stack.append(section)
        elif kind == SECTION_END:
            if len(stack) == 1:
                raise ViciError("unbalanced section")
            stack.pop()
        elif kind == KEY_VALUE:
            key = take_name()
            stack[-1][key] = take_value()
        elif kind == LIST_START:
            current_list = []
            stack[-1][take_name()] = current_list
        elif kind == LIST_ITEM:
            if current_list is None:
                raise ViciError("list item outside list")
            current_list.append(take_value())
        elif kind == LIST_END:
            current_list = None
        else:
            raise ViciError("unknown element type %d" % kind)
    if len(stack) != 1:
        raise ViciError("unbalanced section")
    return root


class Session:
    """One connection to charon's VICI socket. Not thread-safe: use one per thread."""

    def __init__(self, path=None, timeout=None):
        self.sock = None
        errors = []
        for p in ([path] if path else SOCKET_PATHS):
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            try:
                s.connect(p)
            except OSError as e:
                s.close()
                errors.append("%s: %s" % (p, e))
                continue
            self.sock = s
            break
        if self.sock is None:
            raise ViciError("cannot reach the strongSwan daemon (%s)" % "; ".join(errors))

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- transport --------------------------------------------------------

    def _send(self, payload):
        self.sock.sendall(struct.pack("!I", len(payload)) + payload)

    def _recv_exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ViciError("connection to the strongSwan daemon closed")
            buf += chunk
        return bytes(buf)

    def _recv(self):
        (n,) = struct.unpack("!I", self._recv_exact(4))
        if n == 0 or n > MAX_PACKET:
            raise ViciError("bad packet length %d" % n)
        data = self._recv_exact(n)
        return data[0], data[1:]

    # -- requests -----------------------------------------------------------

    def _register(self, event, register=True):
        self._send(bytes([EVENT_REGISTER if register else EVENT_UNREGISTER]) + _name(event))
        while True:
            kind, _ = self._recv()
            if kind == EVENT_CONFIRM:
                return
            if kind == EVENT_UNKNOWN:
                raise ViciError("unknown event %s" % event)
            if kind != EVENT:  # stray events from an earlier stream are skipped
                raise ViciError("unexpected reply %d to event registration" % kind)

    def request(self, command, message=None, stream_event=None, on_event=None):
        """Send a command. Events named stream_event that arrive before the reply go to on_event."""
        if stream_event:
            self._register(stream_event)
        try:
            self._send(bytes([CMD_REQUEST]) + _name(command) + encode(message or {}))
            while True:
                kind, data = self._recv()
                if kind == CMD_RESPONSE:
                    return decode(data)
                if kind == CMD_UNKNOWN:
                    raise ViciError("command %s not supported by this strongSwan" % command)
                if kind == EVENT:
                    n = data[0]
                    name = data[1:1 + n].decode("utf-8", "replace")
                    if on_event and name == stream_event:
                        on_event(decode(data[1 + n:]))
                    continue
                raise ViciError("unexpected packet type %d" % kind)
        finally:
            if stream_event:
                self._register(stream_event, register=False)

    def checked(self, command, message=None, **kw):
        """request() that raises if the reply says success=no."""
        reply = self.request(command, message, **kw)
        if reply.get("success", "yes") != "yes":
            raise ViciError("%s failed: %s" % (command, reply.get("errmsg") or "unknown error"))
        return reply

    def list_sas(self, ike=None):
        """Return {ike_name: sa_dict} for the current IKE_SAs."""
        sas = {}

        def collect(event):
            sas.update(event)

        self.request("list-sas", {"ike": ike} if ike else {}, stream_event="list-sa", on_event=collect)
        return sas
