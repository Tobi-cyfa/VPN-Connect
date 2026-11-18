"""Connections, events and the VPN log, kept in the user's home directory.

~/.config/vpn-connect/connections.json   (0600: holds the pre-shared keys from the .scx files)
~/.local/state/vpn-connect/events.json
~/.local/state/vpn-connect/vpn.log

The password is never saved.

Author: zero.cyfa
"""

import json
import os
import tempfile
import time
import uuid

MAX_EVENTS = 200
MAX_LOG_BYTES = 1024 * 1024


def _dir(env, fallback, *parts):
    base = os.environ.get(env) or os.path.join(os.path.expanduser("~"), *fallback)
    path = os.path.join(base, *parts)
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def config_dir():
    return _dir("XDG_CONFIG_HOME", (".config",), "vpn-connect")


def state_dir():
    return _dir("XDG_STATE_HOME", (".local", "state"), "vpn-connect")


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    """Write atomically with mode 0600."""
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class Connections:
    FIELDS = ("name", "gateway", "psk", "networks", "ike_proposal", "esp_proposal",
              "dpd", "ike_rekey", "child_rekey")

    def __init__(self):
        self.path = os.path.join(config_dir(), "connections.json")
        data = _load(self.path, {})
        self.items = [c for c in data.get("connections", []) if isinstance(c, dict) and c.get("id")]
        self.selected = data.get("selected")

    def save(self):
        _save(self.path, {"connections": self.items, "selected": self.selected})

    def get(self, cid):
        return next((c for c in self.items if c["id"] == cid), None)

    def add_or_update(self, scx, file_name):
        """Same gateway or same name updates the existing connection. Returns (entry, created)."""
        entry = next((c for c in self.items if c.get("gateway") == scx["gateway"]), None) \
            or next((c for c in self.items if c.get("name") == scx["name"]), None)
        created = entry is None
        if created:
            entry = {"id": str(uuid.uuid4()), "username": "", "last_connected": None}
            self.items.append(entry)
        for k in self.FIELDS:
            entry[k] = scx.get(k)
        entry["file_name"] = file_name
        self.selected = entry["id"]
        self.save()
        return entry, created

    def remove(self, cid):
        self.items = [c for c in self.items if c["id"] != cid]
        if self.selected == cid:
            self.selected = self.items[0]["id"] if self.items else None
        self.save()


class Events:
    def __init__(self):
        self.path = os.path.join(state_dir(), "events.json")
        self.items = [e for e in _load(self.path, []) if isinstance(e, dict)]

    def add(self, text):
        self.items.insert(0, {"time": time.time(), "text": text})
        del self.items[MAX_EVENTS:]
        _save(self.path, self.items)

    def clear(self):
        self.items = []
        _save(self.path, self.items)


class VpnLog:
    def __init__(self):
        self.path = os.path.join(state_dir(), "vpn.log")

    def start(self):
        """Each connect starts a fresh log, like the Android app."""
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.close(fd)

    def append(self, line):
        try:
            if os.path.getsize(self.path) > MAX_LOG_BYTES:
                return
        except OSError:
            pass
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + line.rstrip("\n") + "\n")

    def read(self):
        try:
            with open(self.path, encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""
