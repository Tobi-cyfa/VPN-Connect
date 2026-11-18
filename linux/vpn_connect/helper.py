"""Privileged part of VPN Connect, started by the app through pkexec (one session per connect).

Protocol (one JSON object per line):
  stdin  first line : {"profile": {...}, "username": "...", "password": "..."}
  stdin  later      : {"action": "disconnect"}      (EOF means the same)
  stdout            : {"type": "log", "line": "..."}
                      {"type": "state", "state": "connecting|connected|disconnected",
                       "error": "auth|peer_auth|lookup|unreachable|generic"?, ...}
                      {"type": "stats", "bytes_in": n, "bytes_out": n, "tunnels": n, "vips": [...]}

Everything loaded into charon (connection, pre-shared key, XAuth password) is removed again
when the session ends, however it ends. Nothing is written to disk.

Author: zero.cyfa
"""

import json
import os
import re
import select
import subprocess
import sys
import threading
import time

from . import VERSION
from .vici import Session, ViciError

CONN = "vpn-connect"
PSK_ID = "vpn-connect-psk"
XAUTH_ID = "vpn-connect-xauth"
DEFAULT_IKE = "aes256-sha256-modp2048"
DEFAULT_ESP = "aes256-sha512-modp2048"
DAEMON_UNITS = ("strongswan.service", "strongswan-swanctl.service", "strongswan-starter.service")
POLL_SECONDS = 2
LOST_AFTER_POLLS = 5

_out_lock = threading.Lock()


def emit(**obj):
    with _out_lock:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()


def log(line):
    emit(type="log", line=line)


# -- configuration --------------------------------------------------------------

_PROPOSAL = re.compile(r"^[a-z0-9_]+(-[a-z0-9_]+)*$")
_NAME_OK = re.compile(r"^[^\x00-\x1f]{1,255}$")


def _proposal(value, default):
    value = (value or "").strip().lower()
    return value if _PROPOSAL.match(value) else default


def _int(value, default, low, high):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return v if low <= v <= high else default


def build_config(profile, username):
    """The load-conn message for a profile (validated: it comes from an unprivileged user)."""
    gateway = str(profile.get("gateway") or "").strip()
    if not gateway or not _NAME_OK.match(gateway) or " " in gateway:
        raise ValueError("invalid gateway")
    if not username or not _NAME_OK.match(username):
        raise ValueError("invalid user name")

    import ipaddress
    networks = []
    for item in profile.get("networks") or []:
        try:
            net = ipaddress.ip_network(str(item).strip(), strict=False)
        except ValueError:
            continue
        if net.version == 4 and str(net) not in networks:  # IPv4 only, as on Android
            networks.append(str(net))
    if not networks:
        networks = ["0.0.0.0/0"]

    ike_rekey = _int(profile.get("ike_rekey"), 10710, 300, 86400 * 7)
    child_rekey = _int(profile.get("child_rekey"), 4590, 120, 86400 * 7)
    esp = _proposal(profile.get("esp_proposal"), DEFAULT_ESP)

    children = {}
    for i, net in enumerate(networks, 1):
        children["net-%d" % i] = {
            "mode": "tunnel",
            "local_ts": ["dynamic"],
            "remote_ts": [net],
            "esp_proposals": [esp],
            "rekey_time": "%ds" % child_rekey,
            "life_time": "%ds" % (child_rekey + child_rekey // 10),
            "dpd_action": "restart",
            "start_action": "none",
            "close_action": "none",
        }

    conn = {
        "version": "1",
        "aggressive": "no",
        "remote_addrs": [gateway],
        "vips": ["0.0.0.0"],
        "encap": "yes",
        "fragmentation": "yes",
        "unique": "replace",
        "keyingtries": "1",
        "dpd_delay": "%ds" % _int(profile.get("dpd"), 30, 5, 3600),
        "rekey_time": "%ds" % ike_rekey,
        "proposals": [_proposal(profile.get("ike_proposal"), DEFAULT_IKE)],
        # round 1: pre-shared key, round 2: XAuth with user name and password
        "local-1": {"auth": "psk"},
        "local-2": {"auth": "xauth", "xauth_id": username},
        "remote-1": {"auth": "psk"},
        "children": children,
    }
    return {CONN: conn}, list(children)


# -- error classification -------------------------------------------------------

_ERRORS = (
    ("auth", re.compile(r"xauth.*(fail|reject)|(fail|reject).*xauth|XAuth authentication .* failed", re.I)),
    ("peer_auth", re.compile(r"INVALID_HASH_INFORMATION|AUTHENTICATION_FAILED|PAYLOAD_MALFORMED|"
                             r"pre-shared key mismatch|decryption failed|no shared key found", re.I)),
    ("lookup", re.compile(r"unable to resolve|resolving .* failed|host name lookup failed", re.I)),
    ("unreachable", re.compile(r"giving up after \d+ retransmits|no route to host|unreachable", re.I)),
)


def classify(lines):
    for code, pattern in _ERRORS:
        if any(pattern.search(l) for l in lines):
            return code
    return "generic"


_DNS = re.compile(r"installing DNS server (\S+)")


# -- daemon ---------------------------------------------------------------------

def open_vici():
    """Connect to charon, starting the strongSwan service if it is not running."""
    try:
        return Session(timeout=60)
    except ViciError:
        pass
    log("Starting the strongSwan service")
    for unit in DAEMON_UNITS:
        r = subprocess.run(["systemctl", "start", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            break
    last = None
    for _ in range(20):
        try:
            return Session(timeout=60)
        except ViciError as e:
            last = e
            time.sleep(0.5)
    raise last


def cleanup(v):
    for cmd, msg in (("terminate", {"ike": CONN, "force": "yes", "timeout": "-1"}),
                     ("unload-conn", {"name": CONN}),
                     ("unload-shared", {"id": PSK_ID}),
                     ("unload-shared", {"id": XAUTH_ID})):
        try:
            v.request(cmd, msg)
        except (ViciError, OSError):
            pass


# -- session ----------------------------------------------------------------------

class Connector(threading.Thread):
    """Initiates the tunnels on its own VICI connection so the main thread can cancel."""

    def __init__(self, children):
        super().__init__(daemon=True)
        self.children = children
        self.lines = []
        self.dns = []
        self.result = None  # (ok, installed_count)
        self.done = threading.Event()

    def _on_log(self, event):
        line = event.get("msg", "")
        if not line:
            return
        self.lines.append(line)
        m = _DNS.search(line)
        if m and m.group(1) not in self.dns:
            self.dns.append(m.group(1))
        log(line)

    def run(self):
        ok = False
        installed = 0
        try:
            with Session(timeout=None) as v:
                for i, child in enumerate(self.children):
                    reply = v.request("initiate", {
                        "child": child, "ike": CONN, "timeout": "45000" if i == 0 else "20000",
                        "init-limits": "no", "loglevel": "1",
                    }, stream_event="control-log", on_event=self._on_log)
                    if reply.get("success") == "yes":
                        installed += 1
                    elif i == 0:
                        if reply.get("errmsg"):
                            self.lines.append(reply["errmsg"])
                            log(reply["errmsg"])
                        break
                    else:
                        log("The gateway refused tunnel %s; skipped" % child)
                ok = installed > 0
        except (ViciError, OSError) as e:
            self.lines.append(str(e))
            log(str(e))
        self.result = (ok, installed)
        self.done.set()


class StdinLines:
    """Line reader on fd 0 without Python's read-ahead buffer, so select() never misses a line."""

    def __init__(self):
        self.buf = b""
        self.eof = False

    def _pop(self):
        if b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            return line.decode("utf-8", "replace")
        return None

    def readline(self, timeout=None):
        """A line, "" on timeout, or None at end of input."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            line = self._pop()
            if line is not None:
                return line
            if self.eof:
                return None
            wait = None if deadline is None else max(0.0, deadline - time.monotonic())
            r, _, _ = select.select([0], [], [], wait)
            if not r:
                return ""
            chunk = os.read(0, 65536)
            if not chunk:
                self.eof = True
                if self.buf:
                    line, self.buf = self.buf.decode("utf-8", "replace"), b""
                    return line
                return None
            self.buf += chunk


STDIN = StdinLines()


def read_command(timeout):
    """Next command from stdin: a dict, None on timeout, or {"action": "disconnect"} at EOF."""
    line = STDIN.readline(timeout)
    if line is None:
        return {"action": "disconnect", "eof": True}
    try:
        cmd = json.loads(line) if line.strip() else None
    except ValueError:
        return None
    return cmd if isinstance(cmd, dict) else None


def summarize(sa):
    stats = {"bytes_in": 0, "bytes_out": 0, "tunnels": 0, "vips": sa.get("local-vips") or []}
    for child in (sa.get("child-sas") or {}).values():
        if child.get("state") == "INSTALLED":
            stats["tunnels"] += 1
        for key, field in (("bytes_in", "bytes-in"), ("bytes_out", "bytes-out")):
            try:
                stats[key] += int(child.get(field, 0))
            except ValueError:
                pass
    return stats


def run_session(request):
    profile = request.get("profile") or {}
    username = str(request.get("username") or "").strip()
    password = str(request.get("password") or "")
    psk = str(profile.get("psk") or "")
    if not password or not psk:
        raise ValueError("user name, password and pre-shared key are required")
    config, children = build_config(profile, username)

    emit(type="state", state="connecting")
    log("VPN Connect %s for Linux, gateway %s" % (VERSION, profile.get("gateway")))
    v = open_vici()
    try:
        version = v.request("version")
        log("strongSwan %s (%s)" % (version.get("version", "?"), version.get("daemon", "charon")))
        cleanup(v)  # leftovers of a session that did not end cleanly
        v.checked("load-shared", {"id": PSK_ID, "type": "IKE", "data": psk, "owners": []})
        v.checked("load-shared", {"id": XAUTH_ID, "type": "XAUTH", "data": password, "owners": [username]})
        password = None
        v.checked("load-conn", config)
        log("Connecting %d tunnel(s): %s" % (len(children),
            ", ".join(config[CONN]["children"][c]["remote_ts"][0] for c in children)))

        connector = Connector(children)
        connector.start()
        while not connector.done.is_set():
            cmd = read_command(0.25)
            if cmd and cmd.get("action") == "disconnect":
                log("Cancelled")
                cleanup(v)
                connector.done.wait(10)
                return {"cancelled": True}
        ok, installed = connector.result
        if not ok:
            return {"error": classify(connector.lines)}

        sa = v.list_sas(CONN).get(CONN, {})
        stats = summarize(sa)
        emit(type="state", state="connected", vips=stats["vips"], dns=connector.dns,
             tunnels=installed, networks=len(children))

        missing = 0
        while True:
            cmd = read_command(POLL_SECONDS)
            if cmd and cmd.get("action") == "disconnect":
                emit(type="state", state="disconnecting")
                return {}
            sa = v.list_sas(CONN).get(CONN)
            if sa and sa.get("state") == "ESTABLISHED":
                missing = 0
                emit(type="stats", **summarize(sa))
            else:
                missing += 1  # IKEv1 reauthentication briefly replaces the IKE_SA
                if missing >= LOST_AFTER_POLLS:
                    log("The VPN connection was lost")
                    return {"error": "unreachable", "lost": True}
    finally:
        cleanup(v)
        v.close()


def main():
    if os.geteuid() != 0:
        print("vpn-connect-helper must run as root (the app starts it through pkexec)", file=sys.stderr)
        return 2
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    line = STDIN.readline(120) or ""
    try:
        request = json.loads(line)
        if not isinstance(request, dict):
            raise ValueError("bad request")
        final = run_session(request)
    except (ValueError, ViciError, OSError) as e:
        log(str(e))
        emit(type="state", state="disconnected", error="generic", message=str(e))
        return 1
    emit(type="state", state="disconnected", **final)
    return 1 if final.get("error") else 0


def selftest():
    """Load and unload a sample connection in charon (used by the package CI)."""
    profile = {"gateway": "192.0.2.1", "psk": "selftest", "networks": ["10.0.0.0/8", "172.16.0.0/12"]}
    config, _ = build_config(profile, "selftest")
    v = open_vici()
    try:
        print("strongSwan", v.request("version").get("version"))
        v.checked("load-shared", {"id": PSK_ID, "type": "IKE", "data": "selftest", "owners": []})
        v.checked("load-shared", {"id": XAUTH_ID, "type": "XAUTH", "data": "selftest", "owners": ["selftest"]})
        v.checked("load-conn", config)
        conns = {}
        v.request("list-conns", {"ike": CONN}, stream_event="list-conn", on_event=conns.update)
        conn = conns.get(CONN) or {}
        assert conn.get("version") == "IKEv1", conn
        assert sorted(conn.get("children", {})) == ["net-1", "net-2"], conn
        print("loaded:", json.dumps(conn, sort_keys=True))
    finally:
        cleanup(v)
        v.close()
    print("selftest ok")
    return 0
