package com.vpnconnect.app;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * The parts of a Sophos Connect IPsec profile (.scx, plain JSON) that this app needs.
 *
 * @author zero.cyfa
 */
final class ScxFile {
    String name;
    String gateway;
    /** IKE pre-shared key. Needed for the tunnel; stored only in the app's private database. */
    String psk;
    final List<String> networks = new ArrayList<>();
    String ikeProposal;
    String espProposal;
    int dpdDelay = 30;
    int ikeRekey = 10710;
    int childRekey = 4590;

    static final class ScxException extends Exception {
        ScxException(String message) {
            super(message);
        }
    }

    static ScxFile parse(String text) throws ScxException {
        try {
            JSONObject root = new JSONObject(text);
            ScxFile f = new ScxFile();

            f.gateway = root.optString("gateway", "").trim();
            f.name = root.optString("display_name", "").trim();
            if (f.name.isEmpty()) {
                f.name = root.optString("name", "").trim();
            }
            if (f.gateway.isEmpty()) {
                throw new ScxException("no gateway");
            }
            if (f.name.isEmpty()) {
                f.name = f.gateway;
            }

            JSONObject remoteAuth = root.optJSONObject("remote_auth");
            JSONObject psk = remoteAuth == null ? null : remoteAuth.optJSONObject("psk");
            f.psk = psk == null ? "" : psk.optString("secret", "");
            if (f.psk.isEmpty()) {
                throw new ScxException("no pre-shared key");
            }

            f.ikeProposal = firstString(root.optJSONArray("proposals"));
            JSONObject child = root.optJSONObject("child");
            if (child != null) {
                f.espProposal = firstString(child.optJSONArray("proposals"));
                JSONArray ts = child.optJSONArray("remote_ts");
                if (ts != null) {
                    for (int i = 0; i < ts.length(); i++) {
                        String net = ts.optString(i, "").trim();
                        if (!net.isEmpty()) {
                            f.networks.add(net);
                        }
                    }
                }
                f.childRekey = seconds(child.opt("rekey_time"), f.childRekey);
            }
            f.dpdDelay = seconds(root.opt("dpd_delay"), f.dpdDelay);
            f.ikeRekey = seconds(root.opt("rekey_time"), f.ikeRekey);
            return f;
        } catch (JSONException e) {
            throw new ScxException(e.getMessage());
        }
    }

    private static String firstString(JSONArray array) {
        if (array == null || array.length() == 0) {
            return null;
        }
        String s = array.optString(0, "").trim();
        return s.isEmpty() ? null : s;
    }

    /** Numbers in the file are sometimes strings with trailing spaces ("30 "). */
    private static int seconds(Object value, int fallback) {
        if (value == null) {
            return fallback;
        }
        try {
            int v = Integer.parseInt(String.valueOf(value).trim());
            return v > 0 ? v : fallback;
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    /** JSON with the IKEv1 options stored next to the profile. */
    String optionsJson() throws JSONException {
        return new JSONObject()
                .put("psk", psk)
                .put("dpd", dpdDelay)
                .put("ike_rekey", ikeRekey)
                .put("child_rekey", childRekey)
                .toString();
    }
}
