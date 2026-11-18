"""Unit tests that need neither GTK nor strongSwan. Run: python3 -m unittest discover -s tests"""

import json
import os
import socket
import struct
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vpn_connect import helper, scx, vici  # noqa: E402

SAMPLE = {
    "gateway": "vpn.example.org",
    "display_name": "Head office",
    "remote_auth": {"psk": {"secret": "s3cret"}},
    "proposals": ["aes256-sha256-modp2048"],
    "dpd_delay": "30 ",
    "rekey_time": 10710,
    "child": {"proposals": ["aes256-sha512-modp2048"], "remote_ts": ["10.1.0.0/16", " 192.168.5.0/24", "junk"],
              "rekey_time": "4590"},
}


class ScxTest(unittest.TestCase):
    def test_parse(self):
        p = scx.parse("﻿" + json.dumps(SAMPLE))
        self.assertEqual(p["name"], "Head office")
        self.assertEqual(p["gateway"], "vpn.example.org")
        self.assertEqual(p["psk"], "s3cret")
        self.assertEqual(p["networks"], ["10.1.0.0/16", "192.168.5.0/24"])
        self.assertEqual(p["dpd"], 30)
        self.assertEqual(p["child_rekey"], 4590)
        self.assertEqual(p["esp_proposal"], "aes256-sha512-modp2048")

    def test_name_falls_back(self):
        d = dict(SAMPLE)
        del d["display_name"]
        self.assertEqual(scx.parse(json.dumps(d))["name"], "vpn.example.org")
        d["name"] = "Named"
        self.assertEqual(scx.parse(json.dumps(d))["name"], "Named")

    def test_rejects(self):
        for broken in ("not json", "[]", json.dumps({"gateway": "x"}),
                       json.dumps({"remote_auth": {"psk": {"secret": "a"}}})):
            with self.assertRaises(scx.ScxError):
                scx.parse(broken)


class HelperConfigTest(unittest.TestCase):
    def test_config(self):
        cfg, children = helper.build_config(scx.parse(json.dumps(SAMPLE)), "alice")
        c = cfg["vpn-connect"]
        self.assertEqual(c["version"], "1")
        self.assertEqual(c["remote_addrs"], ["vpn.example.org"])
        self.assertEqual(c["local-2"], {"auth": "xauth", "xauth_id": "alice"})
        self.assertEqual(children, ["net-1", "net-2"])
        self.assertEqual(c["children"]["net-2"]["remote_ts"], ["192.168.5.0/24"])
        self.assertEqual(c["dpd_delay"], "30s")
        self.assertNotIn("s3cret", json.dumps(cfg))  # the key goes in load-shared, not the connection

    def test_defaults_and_validation(self):
        cfg, children = helper.build_config({"gateway": "1.2.3.4", "ike_proposal": "bad;rm -rf"}, "bob")
        self.assertEqual(cfg["vpn-connect"]["proposals"], [helper.DEFAULT_IKE])
        self.assertEqual(cfg["vpn-connect"]["children"]["net-1"]["remote_ts"], ["0.0.0.0/0"])
        with self.assertRaises(ValueError):
            helper.build_config({"gateway": "a b"}, "bob")
        with self.assertRaises(ValueError):
            helper.build_config({"gateway": "1.2.3.4"}, "")

    def test_classify(self):
        self.assertEqual(helper.classify(["received INVALID_HASH_INFORMATION error notify"]), "peer_auth")
        self.assertEqual(helper.classify(["XAuth authentication of 'bob' (myself) failed"]), "auth")
        self.assertEqual(helper.classify(["giving up after 5 retransmits"]), "unreachable")
        self.assertEqual(helper.classify(["something else"]), "generic")


class ViciCodecTest(unittest.TestCase):
    def test_roundtrip(self):
        msg = {"a": "1", "list": ["x", "y"], "sec": {"inner": "v", "deeper": {"l": ["z"]}}, "b": True}
        out = vici.decode(vici.encode(msg))
        self.assertEqual(out, {"a": "1", "list": ["x", "y"], "sec": {"inner": "v", "deeper": {"l": ["z"]}},
                               "b": "yes"})

    def test_truncated(self):
        with self.assertRaises(vici.ViciError):
            vici.decode(vici.encode({"key": "value"})[:-2])


class FakeCharon(threading.Thread):
    """Answers one streamed list-sas request the way charon does."""

    def __init__(self, path):
        super().__init__(daemon=True)
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(path)
        self.srv.listen(1)

    def run(self):
        conn, _ = self.srv.accept()

        def recv():
            (n,) = struct.unpack("!I", conn.recv(4))
            data = b""
            while len(data) < n:
                data += conn.recv(n - len(data))
            return data

        def send(payload):
            conn.sendall(struct.pack("!I", len(payload)) + payload)

        assert recv()[0] == vici.EVENT_REGISTER
        send(bytes([vici.EVENT_CONFIRM]))
        req = recv()
        assert req[0] == vici.CMD_REQUEST and req[2:2 + req[1]] == b"list-sas"
        sa = {"vpn-connect": {"state": "ESTABLISHED", "local-vips": ["10.9.0.7"],
                              "child-sas": {"net-1-1": {"state": "INSTALLED", "bytes-in": "100", "bytes-out": "50"}}}}
        send(bytes([vici.EVENT]) + vici._name("list-sa") + vici.encode(sa))
        send(bytes([vici.CMD_RESPONSE]))
        assert recv()[0] == vici.EVENT_UNREGISTER
        send(bytes([vici.EVENT_CONFIRM]))
        conn.close()
        self.srv.close()


@unittest.skipUnless(hasattr(socket, "AF_UNIX") and os.name == "posix", "needs Unix sockets")
class ViciSessionTest(unittest.TestCase):
    def test_list_sas(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "charon.vici")
            server = FakeCharon(path)
            server.start()
            with vici.Session(path, timeout=5) as v:
                sas = v.list_sas("vpn-connect")
            server.join(5)
        stats = helper.summarize(sas["vpn-connect"])
        self.assertEqual(stats, {"bytes_in": 100, "bytes_out": 50, "tunnels": 1, "vips": ["10.9.0.7"]})


if __name__ == "__main__":
    unittest.main()
