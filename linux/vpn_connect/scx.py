"""The parts of a Sophos Connect IPsec profile (.scx, plain JSON) that VPN Connect needs.

Same rules as ScxFile.java in the Android app.

Author: zero.cyfa
"""

import ipaddress
import json

MAX_BYTES = 512 * 1024


class ScxError(Exception):
    pass


def _first_string(value):
    if isinstance(value, list) and value:
        s = str(value[0]).strip()
        return s or None
    return None


def _seconds(value, fallback):
    """Numbers in the file are sometimes strings with trailing spaces ("30 ")."""
    if value is None:
        return fallback
    try:
        v = int(str(value).strip())
    except ValueError:
        return fallback
    return v if v > 0 else fallback


def _network(text):
    """A remote network as CIDR, or None if it is not an IPv4/IPv6 network."""
    try:
        return str(ipaddress.ip_network(text.strip(), strict=False))
    except ValueError:
        return None


def parse(text):
    """Parse .scx text and return a dict describing the connection."""
    if text.startswith("﻿"):
        text = text[1:]
    try:
        root = json.loads(text)
    except ValueError as e:
        raise ScxError("not JSON: %s" % e)
    if not isinstance(root, dict):
        raise ScxError("not a connection profile")

    gateway = str(root.get("gateway") or "").strip()
    if not gateway:
        raise ScxError("no gateway")
    name = str(root.get("display_name") or "").strip() or str(root.get("name") or "").strip() or gateway

    remote_auth = root.get("remote_auth")
    psk = remote_auth.get("psk") if isinstance(remote_auth, dict) else None
    secret = str(psk.get("secret") or "") if isinstance(psk, dict) else ""
    if not secret:
        raise ScxError("no pre-shared key")

    networks = []
    esp = None
    child_rekey = 4590
    child = root.get("child")
    if isinstance(child, dict):
        esp = _first_string(child.get("proposals"))
        for item in child.get("remote_ts") or []:
            net = _network(str(item))
            if net and net not in networks:
                networks.append(net)
        child_rekey = _seconds(child.get("rekey_time"), child_rekey)

    return {
        "name": name,
        "gateway": gateway,
        "psk": secret,
        "networks": networks,
        "ike_proposal": _first_string(root.get("proposals")),
        "esp_proposal": esp,
        "dpd": _seconds(root.get("dpd_delay"), 30),
        "ike_rekey": _seconds(root.get("rekey_time"), 10710),
        "child_rekey": child_rekey,
    }


def read_file(path):
    with open(path, "rb") as f:
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ScxError("file too large")
    try:
        return parse(data.decode("utf-8"))
    except UnicodeDecodeError:
        raise ScxError("not UTF-8 text")
