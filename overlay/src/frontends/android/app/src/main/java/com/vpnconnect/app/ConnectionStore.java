package com.vpnconnect.app;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Keeps the connection list (names, gateways, networks, profile links). No secrets are stored here.
 *
 * @author zero.cyfa
 */
final class ConnectionStore {
    private static final String PREFS = "vc_connections";
    private static final String KEY = "list";
    private static final String KEY_SELECTED = "selected";

    private static ConnectionStore instance;

    private final SharedPreferences prefs;
    private final List<VpnEntry> items = new ArrayList<>();

    static synchronized ConnectionStore get(Context context) {
        if (instance == null) {
            instance = new ConnectionStore(context.getApplicationContext());
        }
        return instance;
    }

    private ConnectionStore(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        load();
    }

    List<VpnEntry> all() {
        return items;
    }

    VpnEntry findById(String id) {
        if (id == null) {
            return null;
        }
        for (VpnEntry e : items) {
            if (e.id.equals(id)) {
                return e;
            }
        }
        return null;
    }

    VpnEntry findByProfile(String profileUuid) {
        if (profileUuid == null) {
            return null;
        }
        for (VpnEntry e : items) {
            if (profileUuid.equals(e.profileUuid)) {
                return e;
            }
        }
        return null;
    }

    VpnEntry findByGateway(String gateway) {
        for (VpnEntry e : items) {
            if (e.gateway != null && e.gateway.equalsIgnoreCase(gateway)) {
                return e;
            }
        }
        return null;
    }

    VpnEntry findByName(String name) {
        for (VpnEntry e : items) {
            if (e.name != null && e.name.equalsIgnoreCase(name)) {
                return e;
            }
        }
        return null;
    }

    /** The entry shown in the header; falls back to the first one. */
    VpnEntry selected() {
        VpnEntry e = findById(prefs.getString(KEY_SELECTED, null));
        if (e == null && !items.isEmpty()) {
            e = items.get(0);
            select(e);
        }
        return e;
    }

    void select(VpnEntry entry) {
        prefs.edit().putString(KEY_SELECTED, entry.id).apply();
    }

    void add(VpnEntry entry) {
        items.add(entry);
        save();
    }

    void remove(VpnEntry entry) {
        items.remove(entry);
        save();
    }

    void save() {
        JSONArray arr = new JSONArray();
        try {
            for (VpnEntry e : items) {
                JSONObject o = new JSONObject();
                o.put("id", e.id);
                o.put("name", e.name);
                o.put("gateway", e.gateway);
                o.put("networks", new JSONArray(e.networks));
                if (e.profileUuid != null) {
                    o.put("profile", e.profileUuid);
                }
                if (e.fileName != null) {
                    o.put("file", e.fileName);
                }
                o.put("last", e.lastConnectedMs);
                arr.put(o);
            }
        } catch (JSONException ex) {
            return;
        }
        prefs.edit().putString(KEY, arr.toString()).apply();
    }

    private void load() {
        items.clear();
        try {
            JSONArray arr = new JSONArray(prefs.getString(KEY, "[]"));
            for (int i = 0; i < arr.length(); i++) {
                JSONObject o = arr.getJSONObject(i);
                VpnEntry e = new VpnEntry(o.getString("id"), o.optString("name"), o.optString("gateway"));
                JSONArray nets = o.optJSONArray("networks");
                if (nets != null) {
                    for (int n = 0; n < nets.length(); n++) {
                        e.networks.add(nets.optString(n));
                    }
                }
                e.profileUuid = o.has("profile") ? o.optString("profile") : null;
                e.fileName = o.has("file") ? o.optString("file") : null;
                e.lastConnectedMs = o.optLong("last", 0);
                items.add(e);
            }
        } catch (JSONException ex) {
            items.clear();
        }
    }
}
