package com.vpnconnect.app;

import android.content.Context;

import org.strongswan.android.data.VpnProfile;
import org.strongswan.android.data.VpnProfileSource;

import java.util.UUID;

/**
 * Small helpers around strongSwan's profile database.
 *
 * @author zero.cyfa
 */
final class Profiles {
    private Profiles() {}

    private static VpnProfileSource open(Context ctx) {
        VpnProfileSource source = new VpnProfileSource(ctx.getApplicationContext());
        source.open();
        return source;
    }

    static VpnProfile find(Context ctx, String uuid) {
        if (uuid == null) {
            return null;
        }
        VpnProfileSource source = open(ctx);
        try {
            return source.getVpnProfile(UUID.fromString(uuid));
        } catch (IllegalArgumentException e) {
            return null;
        } finally {
            source.close();
        }
    }

    /** @return the stored profile, or null if it could not be saved */
    static VpnProfile insert(Context ctx, VpnProfile profile) {
        VpnProfileSource source = open(ctx);
        try {
            return source.insertProfile(profile);
        } finally {
            source.close();
        }
    }

    /**
     * strongSwan routes update/delete through profile.getDataSource(), i.e. the source that
     * loaded the profile. Profiles loaded via find() carry a source that is already closed
     * (null database), so re-bind the profile to the source opened for this operation.
     * @return false if the profile no longer exists in the database
     */
    private static boolean bind(VpnProfileSource source, VpnProfile profile) {
        VpnProfile live = profile.getUUID() == null ? null : source.getVpnProfile(profile.getUUID());
        if (live == null || live.getDataSource() == null) {
            return false;
        }
        profile.setDataSource(live.getDataSource());
        return true;
    }

    static boolean update(Context ctx, VpnProfile profile) {
        VpnProfileSource source = open(ctx);
        try {
            return bind(source, profile) && source.updateVpnProfile(profile);
        } finally {
            source.close();
        }
    }

    static String username(Context ctx, String uuid) {
        VpnProfile p = find(ctx, uuid);
        return p == null || p.getUsername() == null ? "" : p.getUsername();
    }

    static boolean saveUsername(Context ctx, String uuid, String username) {
        VpnProfile p = find(ctx, uuid);
        if (p == null) {
            return false;
        }
        p.setUsername(username);
        return update(ctx, p);
    }

    static void delete(Context ctx, String uuid) {
        VpnProfile p = find(ctx, uuid);
        if (p == null) {
            return;
        }
        VpnProfileSource source = open(ctx);
        try {
            if (bind(source, p)) {
                source.deleteVpnProfile(p);
            }
        } finally {
            source.close();
        }
    }
}
