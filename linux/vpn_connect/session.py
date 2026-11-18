"""Runs the privileged helper through pkexec and turns its output into callbacks.

Author: zero.cyfa
"""

import json
import os
import shutil
import subprocess
import threading

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
# installed next to the package: <prefix>/lib/vpn-connect/vpn-connect-helper
HELPER = os.path.join(os.path.dirname(PKG_DIR), "vpn-connect-helper")

# pkexec exit codes when the admin prompt is dismissed or refused
PKEXEC_DISMISSED = (126, 127)


class HelperSession:
    """One VPN session. on_message(dict) is called from a reader thread for every helper line;
    on_exit(returncode) once the helper has ended."""

    def __init__(self, on_message, on_exit):
        self.on_message = on_message
        self.on_exit = on_exit
        self.proc = None
        self._lock = threading.Lock()

    @staticmethod
    def available():
        """None if the helper can be started, otherwise a reason for the user."""
        if not shutil.which("pkexec"):
            return "pkexec (polkit) is not installed."
        if not os.path.exists(HELPER):
            return "The VPN helper is missing (%s). Reinstall VPN Connect." % HELPER
        return None

    def start(self, profile, username, password):
        request = {"profile": {k: profile.get(k) for k in (
            "gateway", "psk", "networks", "ike_proposal", "esp_proposal", "dpd", "ike_rekey", "child_rekey")},
            "username": username, "password": password}
        self.proc = subprocess.Popen(
            ["pkexec", HELPER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, close_fds=True)
        self._write(request)
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()

    def _write(self, obj):
        with self._lock:
            if self.proc and self.proc.stdin and not self.proc.stdin.closed:
                try:
                    self.proc.stdin.write(json.dumps(obj) + "\n")
                    self.proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass

    def disconnect(self):
        self._write({"action": "disconnect"})

    def close(self):
        """Ends the session: closing stdin makes the helper disconnect and clean up."""
        with self._lock:
            if self.proc and self.proc.stdin and not self.proc.stdin.closed:
                try:
                    self.proc.stdin.close()
                except OSError:
                    pass

    def wait(self, timeout=None):
        if self.proc:
            try:
                self.proc.wait(timeout)
            except subprocess.TimeoutExpired:
                pass

    def _read(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                msg = {"type": "log", "line": line}
            if isinstance(msg, dict):
                self.on_message(msg)
        self.proc.wait()
        self.on_exit(self.proc.returncode)

    def _read_err(self):
        for line in self.proc.stderr:
            line = line.rstrip()
            if line:
                self.on_message({"type": "log", "line": line})
