package com.vpnconnect.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.strongswan.android.R;
import org.strongswan.android.logic.CharonVpnService;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

/**
 * "Open VPN log": shows strongSwan's log with Copy and Share, for sending to ICT support.
 *
 * @author zero.cyfa
 */
public class LogActivity extends Activity {
    private static final int MAX_CHARS = 400_000;

    private ScrollView scroll;
    private String logText = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.vc_log);

        TextView body = findViewById(R.id.vc_log_body);
        scroll = findViewById(R.id.vc_log_scroll);
        findViewById(R.id.vc_log_back).setOnClickListener(v -> finish());
        findViewById(R.id.vc_log_copy).setOnClickListener(v -> copy());
        findViewById(R.id.vc_log_share).setOnClickListener(v -> share());
        applyTopInset(findViewById(R.id.vc_log_bar));

        logText = readLog();
        body.setText(logText);
        scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
    }

    private String readLog() {
        File file = new File(getFilesDir(), CharonVpnService.LOG_FILE);
        if (!file.exists() || file.length() == 0) {
            return getString(R.string.vc_log_empty);
        }
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line).append('\n');
                if (sb.length() > MAX_CHARS) {
                    sb.delete(0, sb.length() - MAX_CHARS);
                }
            }
        } catch (IOException e) {
            return getString(R.string.vc_log_empty);
        }
        return sb.toString();
    }

    private void copy() {
        ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        if (clipboard != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText(getString(R.string.vc_log_title), logText));
            Toast.makeText(this, R.string.vc_copied, Toast.LENGTH_SHORT).show();
        }
    }

    private void share() {
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_SUBJECT, getString(R.string.vc_log_title));
        send.putExtra(Intent.EXTRA_TEXT, logText);
        startActivity(Intent.createChooser(send, getString(R.string.vc_share)));
    }

    @SuppressWarnings("deprecation")
    private void applyTopInset(final View bar) {
        final int basePad = bar.getPaddingTop();
        bar.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(view.getPaddingLeft(), basePad + insets.getSystemWindowInsetTop(),
                    view.getPaddingRight(), view.getPaddingBottom());
            return insets;
        });
    }
}
