package com.vpnconnect.app;

import java.util.ArrayList;
import java.util.List;

/**
 * One row in the connection list (what Sophos Connect calls a "connection").
 *
 * @author zero.cyfa
 */
final class VpnEntry {
    final String id;
    String name;
    String gateway;
    final List<String> networks = new ArrayList<>();
    /** UUID of the strongSwan profile that holds the tunnel settings. */
    String profileUuid;
    /** Name of the .scx file it was imported from (e.g. office_vpn.scx), null if unknown. */
    String fileName;
    /** Epoch millis of the last successful connection, 0 if never. */
    long lastConnectedMs;

    VpnEntry(String id, String name, String gateway) {
        this.id = id;
        this.name = name;
        this.gateway = gateway;
    }
}
