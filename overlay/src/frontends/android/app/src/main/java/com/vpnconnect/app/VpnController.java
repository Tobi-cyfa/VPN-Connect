package com.vpnconnect.app;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import org.strongswan.android.data.VpnProfile;
import org.strongswan.android.data.VpnProfileDataSource;
import org.strongswan.android.logic.VpnStateService;
import org.strongswan.android.logic.VpnStateService.ErrorState;
import org.strongswan.android.logic.VpnStateService.State;

/**
 * Connects the screen to strongSwan's VpnStateService: state updates, connect and disconnect.
 *
 * @author zero.cyfa
 */
final class VpnController implements ServiceConnection {
    interface Listener {
        void onVpnChanged();
    }

    private final Context app;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private Listener listener;
    private VpnStateService service;
    private boolean bound;

    private final VpnStateService.VpnStateListener stateListener = new VpnStateService.VpnStateListener() {
        @Override
        public void stateChanged() {
            ui.post(new Runnable() {
                @Override
                public void run() {
                    notifyListener();
                }
            });
        }
    };

    VpnController(Context context) {
        this.app = context.getApplicationContext();
    }

    void bind(Listener l) {
        listener = l;
        if (!bound) {
            bound = app.bindService(new Intent(app, VpnStateService.class), this, Context.BIND_AUTO_CREATE);
        }
    }

    void unbind() {
        listener = null;
        if (service != null) {
            service.unregisterListener(stateListener);
            service = null;
        }
        if (bound) {
            app.unbindService(this);
            bound = false;
        }
    }

    @Override
    public void onServiceConnected(ComponentName name, IBinder binder) {
        service = ((VpnStateService.LocalBinder) binder).getService();
        service.registerListener(stateListener);
        notifyListener();
    }

    @Override
    public void onServiceDisconnected(ComponentName name) {
        service = null;
    }

    private void notifyListener() {
        if (listener != null) {
            listener.onVpnChanged();
        }
    }

    State state() {
        return service == null ? State.DISABLED : service.getState();
    }

    ErrorState error() {
        return service == null ? ErrorState.NO_ERROR : service.getErrorState();
    }

    /** UUID of the profile the service is working with, or null. */
    String profileUuid() {
        VpnProfile p = service == null ? null : service.getProfile();
        return p == null ? null : p.getUUID().toString();
    }

    /**
     * Starts the tunnel. The password is handed over in memory only. The caller must already hold
     * Android's VPN permission.
     */
    boolean connect(String profileUuid, String password) {
        if (service == null) {
            return false;
        }
        Bundle info = new Bundle();
        info.putString(VpnProfileDataSource.KEY_UUID, profileUuid);
        info.putString(VpnProfileDataSource.KEY_PASSWORD, password);
        service.connect(info, true);
        return true;
    }

    void disconnect() {
        if (service != null) {
            service.disconnect();
        }
    }
}
