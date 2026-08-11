package dev.agentbridge.companion;

import android.app.Activity;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.SystemClock;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.security.SecureRandom;
import java.util.Locale;
import org.json.JSONObject;

public final class ProjectionActivity extends Activity {
    private static final String HOST = "projection_host";
    private static final String PORT = "projection_port";
    private static final String TOKEN = "projection_token";
    private static final String SESSION_ID = "projection_session_id";
    private static final String EXPIRES_AT = "projection_expires_at_unix_seconds";
    private final Handler handler = new Handler();
    private final SecureRandom random = new SecureRandom();
    private volatile boolean connected;
    private String host, token, sessionId;
    private int port;
    private long expiresAt;
    private TextView heading, body, state;
    private Button primary;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        host = getIntent().getStringExtra(HOST);
        token = getIntent().getStringExtra(TOKEN);
        sessionId = getIntent().getStringExtra(SESSION_ID);
        port = getIntent().getIntExtra(PORT, 0);
        expiresAt = getIntent().getLongExtra(EXPIRES_AT, 0L);
        showConsent();
    }

    private void showConsent() {
        LinearLayout panel = panel();
        TextView title = text("Allow temporary projection?", 24, Typeface.BOLD);
        panel.addView(title);
        panel.addView(text("Source: " + safe(host) + ":" + port + "\nSession: " + safe(sessionId)
                + "\nEnds automatically: " + expiresAt
                + "\n\nThis displays title and text only. It grants no attention, memory, sensor, or control authority.", 17, Typeface.NORMAL));
        state = text("Not connected", 15, Typeface.ITALIC); panel.addView(state);
        primary = button("Allow and connect"); panel.addView(primary);
        Button cancel = button("Cancel"); panel.addView(cancel);
        primary.setOnClickListener(new View.OnClickListener() { public void onClick(View view) { beginProjection(); } });
        cancel.setOnClickListener(new View.OnClickListener() { public void onClick(View view) { finish(); } });
        setContentView(scroll(panel));
    }

    private void beginProjection() {
        try {
            long now = System.currentTimeMillis() / 1000L;
            ProjectionProtocol.validateSession(now, expiresAt);
            InetAddress address = InetAddress.getByName(host);
            if ((!address.isSiteLocalAddress() && !address.isLinkLocalAddress())
                    || port < 1 || port > 65535) throw new IllegalArgumentException("invalid projection endpoint");
            ProjectionProtocol.request(token, sessionId, now, "00000000000000000000000000000000");
        } catch (Exception error) { state.setText("Cannot connect: invalid or expired session"); return; }
        connected = true;
        LinearLayout panel = panel();
        heading = text("Connecting…", 24, Typeface.BOLD); panel.addView(heading);
        body = text("", 18, Typeface.NORMAL); panel.addView(body);
        state = text("Temporary read-only projection", 14, Typeface.ITALIC); panel.addView(state);
        primary = button("Disconnect"); panel.addView(primary);
        primary.setOnClickListener(new View.OnClickListener() { public void onClick(View view) { disconnect("Disconnected by you"); } });
        setContentView(scroll(panel));
        poll();
    }

    private void poll() {
        if (!connected) return;
        if (System.currentTimeMillis() / 1000L >= expiresAt) { disconnect("Session expired"); return; }
        new Thread(new Runnable() { public void run() {
            try {
                final String json = fetchFrame();
                handler.post(new Runnable() { public void run() { showFrame(json); } });
            } catch (final Exception error) {
                handler.post(new Runnable() { public void run() { if (connected) state.setText("Waiting for host…"); } });
            } finally {
                handler.postDelayed(new Runnable() { public void run() { poll(); } }, 2000L);
            }
        }, "AgentBridgeProjectionPull").start();
    }

    private String fetchFrame() throws Exception {
        long now = System.currentTimeMillis() / 1000L;
        byte[] nonceBytes = new byte[16]; random.nextBytes(nonceBytes);
        String nonce = Hex.encode(nonceBytes);
        String request = ProjectionProtocol.request(token, sessionId, now, nonce);
        Socket socket = new Socket();
        try {
            socket.connect(new InetSocketAddress(host, port), 2000); socket.setSoTimeout(2000);
            BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), "UTF-8"));
            writer.write(request); writer.write("\n"); writer.flush();
            String response = new BufferedReader(new InputStreamReader(socket.getInputStream(), "UTF-8")).readLine();
            if (response == null) throw new IllegalArgumentException("empty projection response");
            return ProjectionProtocol.verifyResponse(token, sessionId, now, nonce, response);
        } finally { socket.close(); }
    }

    private void showFrame(String json) {
        if (!connected) return;
        try {
            JSONObject frame = new JSONObject(json);
            if (!ProjectionProtocol.SCHEMA.equals(frame.getString("schema"))
                    || !sessionId.equals(frame.getString("session_id"))
                    || frame.getLong("expires_at_unix_seconds") != expiresAt
                    || frame.getBoolean("attention_authority")
                    || frame.getBoolean("memory_authority")
                    || frame.getBoolean("actuation_authority")) throw new IllegalArgumentException("invalid frame boundary");
            heading.setText(frame.getString("title")); body.setText(frame.getString("body"));
            state.setText(String.format(Locale.US, "Read-only · revision %d · disconnect anytime", frame.getLong("revision")));
        } catch (Exception error) { state.setText("Rejected invalid projection frame"); }
    }

    private void disconnect(String message) { connected = false; handler.removeCallbacksAndMessages(null); state.setText(message); primary.setEnabled(false); }
    @Override protected void onDestroy() { connected = false; handler.removeCallbacksAndMessages(null); token = null; super.onDestroy(); }
    @Override public void onBackPressed() { disconnect("Disconnected by you"); super.onBackPressed(); }

    private LinearLayout panel() { LinearLayout p = new LinearLayout(this); p.setOrientation(LinearLayout.VERTICAL); p.setPadding(32, 32, 32, 32); return p; }
    private TextView text(String value, int size, int style) { TextView v = new TextView(this); v.setText(value); v.setTextSize(size); v.setTypeface(Typeface.DEFAULT, style); v.setPadding(0, 12, 0, 12); return v; }
    private Button button(String value) { Button b = new Button(this); b.setText(value); return b; }
    private ScrollView scroll(LinearLayout panel) { ScrollView s = new ScrollView(this); s.addView(panel); return s; }
    private static String safe(String value) { return value == null ? "(missing)" : value; }
}
