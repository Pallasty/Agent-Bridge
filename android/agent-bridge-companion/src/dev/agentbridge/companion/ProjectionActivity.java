package dev.agentbridge.companion;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.SystemClock;
import android.speech.RecognizerIntent;
import android.view.View;
import android.view.ViewTreeObserver;
import android.widget.Button;
import android.widget.EditText;
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
import java.util.ArrayList;
import java.util.Locale;
import org.json.JSONObject;
import org.json.JSONArray;

public final class ProjectionActivity extends Activity {
    private static final int DICTATE_DRAFT_REQUEST = 2401;
    private static final String HOST = "projection_host";
    private static final String PORT = "projection_port";
    private static final String TOKEN = "projection_token";
    private static final String SESSION_ID = "projection_session_id";
    private static final String EXPIRES_AT = "projection_expires_at_unix_seconds";
    private static final String AUTO_CONNECT = "projection_auto_connect";
    private final Handler handler = new Handler();
    private final SecureRandom random = new SecureRandom();
    private volatile boolean connected;
    private String host, token, sessionId;
    private int port;
    private long expiresAt;
    private TextView heading, body, statusCard, actionsHeading, actionsBody, state;
    private Button primary;
    private EditText textInput;
    private TextView textSubmitState;
    private Button textSubmitButton;
    private long connectionGeneration;
    private long lastAppliedRevision = -1L;
    private String lastAppliedFrameSha256;
    private long lastAcknowledgedRevision = -1L;
    private String lastAcknowledgedFrameSha256;
    private RenderTicket pendingDraw;
    private RenderTicket acknowledgementInFlight;
    private View pendingDrawView;
    private ViewTreeObserver.OnDrawListener pendingDrawListener;
    private volatile Socket renderReportSocket;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R)
            getWindow().setDecorFitsSystemWindows(true);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.M) {
            int systemUi = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O)
                systemUi |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            getWindow().getDecorView().setSystemUiVisibility(systemUi);
        }
        host = getIntent().getStringExtra(HOST);
        token = getIntent().getStringExtra(TOKEN);
        sessionId = getIntent().getStringExtra(SESSION_ID);
        port = getIntent().getIntExtra(PORT, 0);
        expiresAt = getIntent().getLongExtra(EXPIRES_AT, 0L);
        showConsent();
        if (getIntent().getBooleanExtra(AUTO_CONNECT, false)) {
            // Test-only host opt-in: ADB pairing still scopes delivery to this
            // device, while beginProjection retains endpoint/session validation
            // and the authenticated, expiring pull protocol.
            handler.post(new Runnable() { public void run() { beginProjection(); } });
        }
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
        final ScrollView consentScroll = scroll(panel);
        setContentView(consentScroll);
        consentScroll.post(new Runnable() {
            public void run() { consentScroll.scrollTo(0, 0); }
        });
    }

    private void beginProjection() {
        if (connected) return;
        try {
            long now = System.currentTimeMillis() / 1000L;
            ProjectionProtocol.validateSession(now, expiresAt);
            InetAddress address = InetAddress.getByName(host);
            if ((!address.isSiteLocalAddress() && !address.isLinkLocalAddress())
                    || port < 1 || port > 65535) throw new IllegalArgumentException("invalid projection endpoint");
            ProjectionProtocol.request(token, sessionId, now, "00000000000000000000000000000000");
        } catch (Exception error) { state.setText("Cannot connect: invalid or expired session"); return; }
        connected = true;
        connectionGeneration++;
        lastAppliedRevision = -1L;
        lastAppliedFrameSha256 = null;
        lastAcknowledgedRevision = -1L;
        lastAcknowledgedFrameSha256 = null;
        pendingDraw = null;
        acknowledgementInFlight = null;
        LinearLayout panel = panel();
        heading = text("Connecting…", 24, Typeface.BOLD); panel.addView(heading);
        statusCard = text("", 18, Typeface.BOLD); statusCard.setVisibility(View.GONE); panel.addView(statusCard);
        body = text("", 18, Typeface.NORMAL); panel.addView(body);
        actionsHeading = text("Next actions", 17, Typeface.BOLD); actionsHeading.setVisibility(View.GONE); panel.addView(actionsHeading);
        actionsBody = text("", 18, Typeface.NORMAL); actionsBody.setVisibility(View.GONE); panel.addView(actionsBody);
        state = text("Temporary read-only projection", 14, Typeface.ITALIC); panel.addView(state);
        panel.addView(text("Send text to Agent-Bridge", 18, Typeface.BOLD));
        panel.addView(text("Submitted text is authenticated, retained only in this temporary session, and grants no attention, memory, or control authority.", 14, Typeface.NORMAL));
        textInput = new EditText(this);
        textInput.setHint("Type a message (maximum 1000 characters)");
        textInput.setMaxLines(6);
        panel.addView(textInput);
        panel.addView(text("Dictation opens Android's visible system speech recognizer. Agent-Bridge receives no audio. Review and edit the draft before submitting.", 14, Typeface.NORMAL));
        Button dictate = button("Dictate draft"); panel.addView(dictate);
        textSubmitButton = button("Submit text"); panel.addView(textSubmitButton);
        textSubmitState = text("Nothing submitted", 14, Typeface.ITALIC); panel.addView(textSubmitState);
        dictate.setOnClickListener(new View.OnClickListener() {
            public void onClick(View view) { beginDictation(); }
        });
        textSubmitButton.setOnClickListener(new View.OnClickListener() {
            public void onClick(View view) { submitTextObservation(); }
        });
        primary = button("Disconnect"); panel.addView(primary);
        primary.setOnClickListener(new View.OnClickListener() { public void onClick(View view) { disconnect("Disconnected by you"); } });
        setContentView(scroll(panel));
        poll();
    }

    private void beginDictation() {
        if (!connected || textInput == null) return;
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag());
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Dictate a draft to review before submitting");
        try {
            textSubmitState.setText("Opening Android system dictation…");
            startActivityForResult(intent, DICTATE_DRAFT_REQUEST);
        } catch (ActivityNotFoundException error) {
            textSubmitState.setText("System dictation is unavailable; type your draft instead");
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != DICTATE_DRAFT_REQUEST || !connected || textInput == null) return;
        if (resultCode != RESULT_OK || data == null) {
            textSubmitState.setText("Dictation cancelled; existing draft preserved");
            return;
        }
        ArrayList<String> candidates =
                data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
        String transcript = VoiceDraftPolicy.firstTranscript(candidates);
        if (transcript.isEmpty()) {
            textSubmitState.setText("No dictation result; existing draft preserved");
            return;
        }
        String draft = VoiceDraftPolicy.mergeDraft(textInput.getText().toString(), transcript);
        textInput.setText(draft);
        textInput.setSelection(draft.length());
        textSubmitState.setText("Draft updated locally; review it, then tap Submit text");
    }

    private void submitTextObservation() {
        if (!connected) return;
        final String submitted = textInput.getText().toString();
        try { TextObservationProtocol.payloadDigest(submitted); }
        catch (IllegalArgumentException error) {
            textSubmitState.setText("Enter 1–1000 characters before submitting");
            return;
        }
        byte[] submissionIdBytes = new byte[16]; random.nextBytes(submissionIdBytes);
        final String submissionId = Hex.encode(submissionIdBytes);
        TextObservationProtocol.validateSubmissionId(submissionId);
        textSubmitButton.setEnabled(false);
        textSubmitState.setText("Submitting…");
        new Thread(new Runnable() { public void run() {
            try {
                final String digest = TextObservationProtocol.payloadDigest(submitted);
                JSONObject payload = new JSONObject();
                payload.put("schema", TextObservationProtocol.SCHEMA);
                payload.put("session_id", sessionId);
                payload.put("submission_id", submissionId);
                payload.put("locale", Locale.getDefault().toLanguageTag());
                payload.put("text", submitted);
                payload.put("payload_sha256", digest);
                payload.put("retention_policy", TextObservationProtocol.RETENTION);
                payload.put("foreground_user_submit", true);
                payload.put("attention_authority", false);
                payload.put("memory_authority", false);
                payload.put("actuation_authority", false);
                Exception lastError = null;
                for (int attempt = 0; attempt < 2; attempt++) {
                    final long now = System.currentTimeMillis() / 1000L;
                    payload.put("captured_at_unix_seconds", now);
                    byte[] nonceBytes = new byte[16]; random.nextBytes(nonceBytes);
                    final String nonce = Hex.encode(nonceBytes);
                    String request = TextObservationProtocol.request(
                            token, sessionId, now, nonce, payload.toString());
                    Socket socket = new Socket();
                    try {
                        socket.connect(new InetSocketAddress(host, port), 2000);
                        socket.setSoTimeout(2000);
                        BufferedWriter writer = new BufferedWriter(
                                new OutputStreamWriter(socket.getOutputStream(), "UTF-8"));
                        writer.write(request); writer.write("\n"); writer.flush();
                        String response = new BufferedReader(
                                new InputStreamReader(socket.getInputStream(), "UTF-8")).readLine();
                        if (response == null)
                            throw new IllegalArgumentException("empty acknowledgement");
                        TextObservationProtocol.verifyAck(
                                token, sessionId, now, nonce, digest, response);
                        lastError = null;
                        break;
                    } catch (Exception error) {
                        lastError = error;
                    } finally { socket.close(); }
                }
                if (lastError != null) throw lastError;
                handler.post(new Runnable() { public void run() {
                    textInput.setText("");
                    textSubmitButton.setEnabled(true);
                    textSubmitState.setText("Accepted by this temporary Agent-Bridge session");
                } });
            } catch (final Exception error) {
                handler.post(new Runnable() { public void run() {
                    textSubmitButton.setEnabled(true);
                    textSubmitState.setText("Not accepted; text remains on this device");
                } });
            }
        } }, "AgentBridgeTextSubmit").start();
    }

    private void poll() {
        if (!connected) return;
        if (System.currentTimeMillis() / 1000L >= expiresAt) { disconnect("Session expired"); return; }
        new Thread(new Runnable() { public void run() {
            try {
                final ProjectionProtocol.VerifiedFrame frame = fetchFrame();
                handler.post(new Runnable() { public void run() { showFrame(frame); } });
            } catch (final Exception error) {
                handler.post(new Runnable() { public void run() {
                    if (connected && lastAppliedRevision < 0L) state.setText("Waiting for host…");
                } });
            } finally {
                handler.post(new Runnable() { public void run() {
                    if (connected) handler.postDelayed(new Runnable() {
                        public void run() { poll(); }
                    }, 2000L);
                } });
            }
        } }, "AgentBridgeProjectionPull").start();
    }

    private ProjectionProtocol.VerifiedFrame fetchFrame() throws Exception {
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
            return ProjectionProtocol.verifyFrameResponse(token, sessionId, now, nonce, response);
        } finally { socket.close(); }
    }

    private void showFrame(ProjectionProtocol.VerifiedFrame verifiedFrame) {
        if (!connected) return;
        try {
            JSONObject frame = new JSONObject(verifiedFrame.rawJson);
            long frameExpiresAt = frame.getLong("expires_at_unix_seconds");
            long revision = frame.getLong("revision");
            ProjectionProtocol.validateSession(System.currentTimeMillis() / 1000L, frameExpiresAt);
            if (!ProjectionProtocol.SCHEMA.equals(frame.getString("schema"))
                    || !sessionId.equals(frame.getString("session_id"))
                    || frameExpiresAt != expiresAt
                    || revision <= 0L
                    || frame.getBoolean("attention_authority")
                    || frame.getBoolean("memory_authority")
                    || frame.getBoolean("actuation_authority")) throw new IllegalArgumentException("invalid frame boundary");
            if (lastAppliedRevision > revision
                    || (lastAppliedRevision == revision
                    && lastAppliedFrameSha256 != null
                    && !lastAppliedFrameSha256.equals(verifiedFrame.frameSha256)))
                throw new IllegalArgumentException("projection revision identity mismatch");

            boolean alreadyApplied = lastAppliedRevision == revision
                    && verifiedFrame.frameSha256.equals(lastAppliedFrameSha256);
            if (!alreadyApplied) {
                heading.setText(frame.getString("title")); body.setText(frame.getString("body"));
                String statusValue = frame.optString("status", "").trim();
                statusCard.setText(statusValue.isEmpty() ? "" : "STATUS  ·  " + statusValue);
                statusCard.setVisibility(statusValue.isEmpty() ? View.GONE : View.VISIBLE);
                JSONArray actions = frame.optJSONArray("actions");
                StringBuilder actionText = new StringBuilder();
                if (actions != null) for (int i = 0; i < actions.length() && i < 6; i++) {
                    String action = actions.optString(i, "").trim();
                    if (!action.isEmpty()) actionText.append(actionText.length() == 0 ? "" : "\n\n")
                            .append(i + 1).append(". ").append(action);
                }
                boolean hasActions = actionText.length() > 0;
                actionsHeading.setVisibility(hasActions ? View.VISIBLE : View.GONE);
                actionsBody.setText(actionText.toString());
                actionsBody.setVisibility(hasActions ? View.VISIBLE : View.GONE);
                state.setText(String.format(Locale.US,
                        "Read-only · revision %d · disconnect anytime", revision));
                lastAppliedRevision = revision;
                lastAppliedFrameSha256 = verifiedFrame.frameSha256;
            }

            if (lastAcknowledgedRevision == revision
                    && verifiedFrame.frameSha256.equals(lastAcknowledgedFrameSha256)) return;
            RenderTicket ticket = new RenderTicket(
                    connectionGeneration, revision, verifiedFrame.frameSha256);
            if (ticket.sameFrame(pendingDraw) || ticket.sameFrame(acknowledgementInFlight)) return;
            if (acknowledgementInFlight != null) return;
            scheduleRenderReportAfterDraw(ticket);
        } catch (Exception error) {
            cancelPendingDraw();
            state.setText("Rejected invalid projection frame");
        }
    }

    private void scheduleRenderReportAfterDraw(final RenderTicket ticket) {
        cancelPendingDraw();
        if (!isActive(ticket)) return;
        final View decor = getWindow().getDecorView();
        final ViewTreeObserver.OnDrawListener listener = new ViewTreeObserver.OnDrawListener() {
            private boolean observed;
            public void onDraw() {
                if (observed) return;
                observed = true;
                final ViewTreeObserver.OnDrawListener self = this;
                decor.post(new Runnable() { public void run() {
                    removeDrawListener(decor, self);
                    if (pendingDraw != ticket) return;
                    pendingDraw = null;
                    pendingDrawView = null;
                    pendingDrawListener = null;
                    if (!isActive(ticket) || acknowledgementInFlight != null) return;
                    acknowledgementInFlight = ticket;
                    sendRenderReport(ticket);
                } });
            }
        };
        pendingDraw = ticket;
        pendingDrawView = decor;
        pendingDrawListener = listener;
        decor.getViewTreeObserver().addOnDrawListener(listener);
        decor.invalidate();
    }

    private void sendRenderReport(final RenderTicket ticket) {
        new Thread(new Runnable() { public void run() {
            Socket socket = new Socket();
            renderReportSocket = socket;
            try {
                if (!isActive(ticket)) return;
                final long now = System.currentTimeMillis() / 1000L;
                byte[] nonceBytes = new byte[16]; random.nextBytes(nonceBytes);
                final String nonce = Hex.encode(nonceBytes);
                final String request = ProjectionProtocol.renderReportRequest(
                        token, sessionId, now, nonce, ticket.revision, ticket.frameSha256);
                socket.connect(new InetSocketAddress(host, port), 2000);
                socket.setSoTimeout(2000);
                if (!isActive(ticket)) return;
                BufferedWriter writer = new BufferedWriter(
                        new OutputStreamWriter(socket.getOutputStream(), "UTF-8"));
                writer.write(request); writer.write("\n"); writer.flush();
                String response = new BufferedReader(
                        new InputStreamReader(socket.getInputStream(), "UTF-8")).readLine();
                ProjectionProtocol.verifyRenderReportAck(token, sessionId, now, nonce,
                        ticket.revision, ticket.frameSha256, response);
                handler.post(new Runnable() { public void run() {
                    if (acknowledgementInFlight == ticket) acknowledgementInFlight = null;
                    if (!isActive(ticket)) return;
                    lastAcknowledgedRevision = ticket.revision;
                    lastAcknowledgedFrameSha256 = ticket.frameSha256;
                } });
            } catch (Exception error) {
                handler.post(new Runnable() { public void run() {
                    if (acknowledgementInFlight == ticket) acknowledgementInFlight = null;
                } });
            } finally {
                try { socket.close(); } catch (Exception ignored) {}
                if (renderReportSocket == socket) renderReportSocket = null;
            }
        } }, "AgentBridgeProjectionRenderedReport").start();
    }

    private boolean isActive(RenderTicket ticket) {
        return connected && ticket != null && ticket.generation == connectionGeneration
                && System.currentTimeMillis() / 1000L < expiresAt;
    }

    private void cancelPendingDraw() {
        if (pendingDrawView != null && pendingDrawListener != null)
            removeDrawListener(pendingDrawView, pendingDrawListener);
        pendingDraw = null;
        pendingDrawView = null;
        pendingDrawListener = null;
    }

    private static void removeDrawListener(View view, ViewTreeObserver.OnDrawListener listener) {
        ViewTreeObserver observer = view.getViewTreeObserver();
        if (observer.isAlive()) observer.removeOnDrawListener(listener);
    }

    private void closeRenderReportSocket() {
        Socket socket = renderReportSocket;
        renderReportSocket = null;
        if (socket != null) try { socket.close(); } catch (Exception ignored) {}
    }

    private static final class RenderTicket {
        final long generation;
        final long revision;
        final String frameSha256;

        RenderTicket(long generation, long revision, String frameSha256) {
            this.generation = generation;
            this.revision = revision;
            this.frameSha256 = frameSha256;
        }

        boolean sameFrame(RenderTicket other) {
            return other != null && revision == other.revision
                    && frameSha256.equals(other.frameSha256);
        }
    }

    private void disconnect(String message) {
        connected = false;
        connectionGeneration++;
        cancelPendingDraw();
        acknowledgementInFlight = null;
        closeRenderReportSocket();
        handler.removeCallbacksAndMessages(null);
        state.setText(message);
        primary.setEnabled(false);
    }
    @Override protected void onDestroy() {
        connected = false;
        connectionGeneration++;
        cancelPendingDraw();
        acknowledgementInFlight = null;
        closeRenderReportSocket();
        handler.removeCallbacksAndMessages(null);
        token = null;
        super.onDestroy();
    }
    @Override public void onBackPressed() { disconnect("Disconnected by you"); super.onBackPressed(); }

    private LinearLayout panel() { LinearLayout p = new LinearLayout(this); p.setOrientation(LinearLayout.VERTICAL); p.setPadding(32, 32, 32, 32); return p; }
    private TextView text(String value, int size, int style) { TextView v = new TextView(this); v.setText(value); v.setTextSize(size); v.setTypeface(Typeface.DEFAULT, style); v.setPadding(0, 12, 0, 12); return v; }
    private Button button(String value) { Button b = new Button(this); b.setText(value); return b; }
    private ScrollView scroll(LinearLayout panel) { ScrollView s = new ScrollView(this); s.addView(panel); return s; }
    private static String safe(String value) { return value == null ? "(missing)" : value; }
}
