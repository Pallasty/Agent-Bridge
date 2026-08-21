package dev.agentbridge.companion;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import java.io.FileDescriptor;
import java.io.IOException;
import java.io.PrintWriter;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.charset.Charset;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;

public final class CompanionService extends Service {
    private static final int NOTIFICATION_ID = 17031;
    private static final String NOTIFICATION_CHANNEL_ID = "agent_bridge_companion_runtime";
    private static final int LAN_HEALTH_PORT = 17321;
    private static final long LAN_HEALTH_RETRY_MS = 5000L;
    private static final String PREFERENCES = "agent_bridge_companion";
    private static final String HEALTH_TOKEN_KEY = "health_token";
    private static final String HEALTH_SCHEMA = "agent_bridge.android_companion.health.v1";
    private static final String HEALTH_PREFIX = "AGENT_BRIDGE_COMPANION_HEALTH ";
    private static final String IMU_PREFIX = "AGENT_BRIDGE_COMPANION_IMU ";
    private static final String RECOVERY_AUTH_PREFIX = "AGENT_BRIDGE_COMPANION_RECOVERY_AUTH ";
    private static final String IMU_SCHEMA = "agent_bridge.android_companion.imu_summary.v0";
    private static final String IMU_REQUEST_ID = "imu_request_id";
    private static final String IMU_CHALLENGE = "imu_challenge";
    private static final String IMU_DURATION_MS = "imu_duration_ms";
    private static final String IMU_SAMPLE_RATE_HZ = "imu_sample_rate_hz";
    private static final String IMU_SEQUENCE_KEY = "imu_sequence";
    private static final Charset UTF_8 = Charset.forName("UTF-8");

    private PowerManager.WakeLock partialWakeLock;
    private WifiManager.WifiLock wifiLock;
    private long processStartedElapsedRealtimeMs;
    private String sessionId;
    private Handler lanHealthRetryHandler;
    private LanHealthServer lanHealthServer;
    private volatile String lanHealthState = "unprovisioned";
    private volatile String lanHealthBindAddress = "";
    private Handler imuHandler;
    private SensorManager sensorManager;
    private SensorEventListener imuListener;
    private ImuSampleSummary activeImuSummary;
    private ImuCaptureContract.Request activeImuRequest;
    private boolean activeGyroscopeAvailable;
    private volatile String lastImuJson = "{\"schema\":\"" + IMU_SCHEMA + "\",\"status\":\"idle\"}";
    private final Runnable lanHealthRetry = new Runnable() {
        @Override public void run() { startLanHealth(loadHealthToken()); }
    };

    @Override public void onCreate() {
        super.onCreate();
        processStartedElapsedRealtimeMs = SystemClock.elapsedRealtime();
        sessionId = Build.SERIAL + "-" + processStartedElapsedRealtimeMs;
        lanHealthRetryHandler = new Handler();
        imuHandler = new Handler();
        sensorManager = (SensorManager) getSystemService(Context.SENSOR_SERVICE);
        acquireLocks();
        startForeground(NOTIFICATION_ID, buildNotification());
        startLanHealth(loadHealthToken());
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        acquireLocks();
        if (intent != null && intent.hasExtra(HEALTH_TOKEN_KEY)) {
            String token = intent.getStringExtra(HEALTH_TOKEN_KEY);
            intent.removeExtra(HEALTH_TOKEN_KEY);
            if (isValidHealthToken(token)) {
                getSharedPreferences(PREFERENCES, MODE_PRIVATE).edit().putString(HEALTH_TOKEN_KEY, token).commit();
                startLanHealth(token);
            } else lanHealthState = "invalid_token";
        }
        if (intent != null && intent.hasExtra(IMU_REQUEST_ID)) startImuCapture(intent);
        return START_NOT_STICKY;
    }

    @Override public void onDestroy() {
        if (lanHealthRetryHandler != null) lanHealthRetryHandler.removeCallbacks(lanHealthRetry);
        if (lanHealthServer != null) { lanHealthServer.close(); lanHealthServer = null; }
        stopImuCapture();
        releaseLocks();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    private void acquireLocks() {
        if (partialWakeLock == null) {
            PowerManager power = (PowerManager) getSystemService(Context.POWER_SERVICE);
            partialWakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "AgentBridgeCompanion:Lifecycle");
            partialWakeLock.setReferenceCounted(false);
        }
        if (!partialWakeLock.isHeld()) partialWakeLock.acquire();
        if (wifiLock == null) {
            WifiManager wifi = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            wifiLock = wifi.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "AgentBridgeCompanion:Wifi");
            wifiLock.setReferenceCounted(false);
        }
        if (!wifiLock.isHeld()) wifiLock.acquire();
    }

    private void releaseLocks() {
        if (wifiLock != null && wifiLock.isHeld()) wifiLock.release();
        if (partialWakeLock != null && partialWakeLock.isHeld()) partialWakeLock.release();
    }

    private String loadHealthToken() {
        return getSharedPreferences(PREFERENCES, MODE_PRIVATE).getString(HEALTH_TOKEN_KEY, "");
    }

    private boolean isValidHealthToken(String token) {
        try { new LanHealthProtocol(token); return true; }
        catch (IllegalArgumentException error) { return false; }
    }

    private synchronized void startLanHealth(String token) {
        if (lanHealthRetryHandler != null) lanHealthRetryHandler.removeCallbacks(lanHealthRetry);
        if (lanHealthServer != null) { lanHealthServer.close(); lanHealthServer = null; }
        lanHealthBindAddress = "";
        if (!isValidHealthToken(token)) { lanHealthState = "unprovisioned"; return; }
        try {
            final InetAddress address = getWifiAddress();
            lanHealthServer = new LanHealthServer(address, LAN_HEALTH_PORT, token,
                    new LanHealthServer.HealthSupplier() { public String healthJson() { return CompanionService.this.healthJson(); } });
            lanHealthServer.start();
            lanHealthBindAddress = address.getHostAddress();
            lanHealthState = "listening";
        } catch (IOException error) {
            lanHealthState = "bind_retry_wait";
            lanHealthRetryHandler.postDelayed(lanHealthRetry, LAN_HEALTH_RETRY_MS);
        }
    }

    private InetAddress getWifiAddress() throws UnknownHostException {
        WifiManager wifi = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        int value = wifi.getConnectionInfo().getIpAddress();
        if (value == 0) throw new UnknownHostException("Wi-Fi has no IPv4 address");
        byte[] bytes = new byte[] {(byte) value, (byte) (value >> 8), (byte) (value >> 16), (byte) (value >> 24)};
        InetAddress address = InetAddress.getByAddress(bytes);
        if (address.isAnyLocalAddress() || address.isLoopbackAddress()) throw new UnknownHostException("invalid Wi-Fi bind address");
        return address;
    }

    private Notification buildNotification() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(NOTIFICATION_CHANNEL_ID,
                    "Agent-Bridge explicit runtime", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Visible only while the operator-enabled companion service is running");
            ((NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE)).createNotificationChannel(channel);
        }
        int pendingFlags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) pendingFlags |= PendingIntent.FLAG_IMMUTABLE;
        PendingIntent pending = PendingIntent.getService(this, 0,
                new Intent(this, CompanionService.class), pendingFlags);
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, NOTIFICATION_CHANNEL_ID)
                : new Notification.Builder(this);
        return builder.setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("Agent-Bridge Companion").setContentText("Lifecycle and timing channel active")
                .setContentIntent(pending).setOngoing(true).build();
    }

    @Override protected void dump(FileDescriptor fd, PrintWriter writer, String[] args) {
        writer.println(HEALTH_PREFIX + healthJson());
        writer.println(IMU_PREFIX + lastImuJson);
        writer.println(RECOVERY_AUTH_PREFIX + recoveryAuthorizationJson());
    }

    private String recoveryAuthorizationJson() {
        SharedPreferences preferences=getSharedPreferences(RecoveryAuthorizationActivity.PREFS,MODE_PRIVATE);
        String receipt=preferences.getString(RecoveryAuthorizationActivity.RECEIPT_KEY,"");
        String publicKey=preferences.getString(RecoveryAuthorizationActivity.PUBLIC_KEY,"");
        if (receipt.isEmpty() || publicKey.isEmpty())
            return "{\"schema\":\"agent_bridge.android_companion.recovery_authorization_export.v0\",\"status\":\"empty\",\"private_key_exported\":false}";
        try {
            return new org.json.JSONObject().put("schema","agent_bridge.android_companion.recovery_authorization_export.v0")
                    .put("status","signed").put("receipt",receipt).put("public_key_b64",publicKey)
                    .put("private_key_exported",false).put("action_invoked",false).toString();
        } catch (Exception error) {
            return "{\"schema\":\"agent_bridge.android_companion.recovery_authorization_export.v0\",\"status\":\"error\",\"private_key_exported\":false}";
        }
    }

    private synchronized void startImuCapture(Intent intent) {
        if (activeImuRequest != null) { lastImuJson = imuErrorJson("busy", safeRequestId(intent)); return; }
        final ImuCaptureContract.Request request;
        try {
            request = ImuCaptureContract.validate(intent.getStringExtra(IMU_REQUEST_ID),
                    intent.getStringExtra(IMU_CHALLENGE), intent.getLongExtra(IMU_DURATION_MS, 0),
                    intent.getLongExtra(IMU_SAMPLE_RATE_HZ, 0));
        } catch (IllegalArgumentException error) { lastImuJson = imuErrorJson("invalid_request", safeRequestId(intent)); return; }
        if (!isValidHealthToken(loadHealthToken())) { lastImuJson = imuErrorJson("unprovisioned", request.requestId); return; }
        Sensor accelerometer = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        if (accelerometer == null) { lastImuJson = imuErrorJson("accelerometer_unavailable", request.requestId); return; }
        Sensor gyroscope = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE);
        activeImuRequest = request;
        activeImuSummary = new ImuSampleSummary(request.maximumSamples);
        activeGyroscopeAvailable = gyroscope != null;
        imuListener = new SensorEventListener() {
            public void onSensorChanged(SensorEvent event) {
                if (event.values.length < 3 || activeImuSummary == null) return;
                if (event.sensor.getType() == Sensor.TYPE_ACCELEROMETER)
                    activeImuSummary.addAccelerometer(event.timestamp, event.values[0], event.values[1], event.values[2]);
                else if (event.sensor.getType() == Sensor.TYPE_GYROSCOPE)
                    activeImuSummary.addGyroscope(event.timestamp, event.values[0], event.values[1], event.values[2]);
            }
            public void onAccuracyChanged(Sensor sensor, int accuracy) {}
        };
        boolean registered = sensorManager.registerListener(imuListener, accelerometer, request.samplingPeriodUs);
        if (gyroscope != null) sensorManager.registerListener(imuListener, gyroscope, request.samplingPeriodUs);
        if (!registered) { stopImuCapture(); lastImuJson = imuErrorJson("accelerometer_registration_failed", request.requestId); return; }
        lastImuJson = "{\"schema\":\"" + IMU_SCHEMA + "\",\"status\":\"capturing\",\"request_id\":\"" + request.requestId + "\"}";
        imuHandler.postDelayed(new Runnable() { public void run() { finishImuCapture(); } }, request.durationMs);
    }

    private synchronized void finishImuCapture() {
        if (activeImuRequest == null || activeImuSummary == null) return;
        ImuCaptureContract.Request request = activeImuRequest;
        ImuSampleSummary summary = activeImuSummary;
        boolean gyroscopeAvailable = activeGyroscopeAvailable;
        if (imuListener != null) sensorManager.unregisterListener(imuListener);
        imuListener = null; activeImuRequest = null; activeImuSummary = null;
        long issuedAt = System.currentTimeMillis(), expiresAt = issuedAt + 10000L, sequence = nextImuSequence();
        String consentDigest = sha256Hex("imu\n" + request.requestId + "\n" + request.durationMs + "\n" + request.sampleRateHz + "\n" + request.maximumSamples);
        String receiptMac = ConsentReceiptProtocol.sign(ConsentReceiptProtocol.deriveReceiptKey(loadHealthToken()),
                request.requestId, Build.SERIAL, sessionId, "imu", request.challenge, sequence, issuedAt,
                expiresAt, consentDigest, request.durationMs, request.sampleRateHz, request.maximumSamples);
        String resultMac = ImuResultAttestationProtocol.sign(ImuResultAttestationProtocol.deriveResultKey(loadHealthToken()),
                request.requestId, Build.SERIAL, sessionId, request.challenge, sequence, issuedAt,
                summary.accelerometerSamples(), summary.gyroscopeSamples(), "ab_imu_binary_v0",
                summary.payloadByteLength(), summary.payloadSha256(), false, false, false);
        lastImuJson = String.format(Locale.US,
                "{\"schema\":\"%s\",\"status\":\"complete\",\"request_id\":\"%s\",\"device_id\":\"%s\",\"session_id\":\"%s\",\"duration_ms\":%d,\"sample_rate_hz\":%d,\"maximum_samples\":%d,\"accelerometer_available\":true,\"gyroscope_available\":%s,\"accelerometer_samples\":%d,\"gyroscope_samples\":%d,\"accelerometer_mean_m_s2\":[%.6f,%.6f,%.6f],\"last_sensor_timestamp_ns\":%d,\"payload_encoding\":\"ab_imu_binary_v0\",\"payload_byte_length\":%d,\"payload_sha256\":\"%s\",\"sequence\":%d,\"issued_at_unix_ms\":%d,\"expires_at_unix_ms\":%d,\"consent_digest_sha256\":\"%s\",\"receipt_mac_sha256\":\"%s\",\"result_attestation_schema\":\"agent_bridge.mobile_imu_result_attestation.v0\",\"result_attestation_mac_sha256\":\"%s\",\"attention_authority\":false,\"memory_authority\":false,\"actuation_authority\":false}",
                IMU_SCHEMA, request.requestId, Build.SERIAL, sessionId, request.durationMs,
                request.sampleRateHz, request.maximumSamples, Boolean.toString(gyroscopeAvailable),
                summary.accelerometerSamples(), summary.gyroscopeSamples(), summary.accelerometerMeanX(),
                summary.accelerometerMeanY(), summary.accelerometerMeanZ(), summary.lastSensorTimestampNs(),
                summary.payloadByteLength(), summary.payloadSha256(), sequence, issuedAt, expiresAt,
                consentDigest, receiptMac, resultMac);
    }

    private synchronized void stopImuCapture() {
        if (imuHandler != null) imuHandler.removeCallbacksAndMessages(null);
        if (sensorManager != null && imuListener != null) sensorManager.unregisterListener(imuListener);
        imuListener = null; activeImuRequest = null; activeImuSummary = null;
    }

    private long nextImuSequence() {
        SharedPreferences preferences = getSharedPreferences(PREFERENCES, MODE_PRIVATE);
        long next = preferences.getLong(IMU_SEQUENCE_KEY, 0) + 1;
        preferences.edit().putLong(IMU_SEQUENCE_KEY, next).commit();
        return next;
    }

    private String safeRequestId(Intent intent) {
        String value = intent.getStringExtra(IMU_REQUEST_ID);
        return value != null && value.matches("[A-Za-z0-9_.-]{1,64}") ? value : "";
    }

    private String imuErrorJson(String status, String requestId) {
        return "{\"schema\":\"" + IMU_SCHEMA + "\",\"status\":\"" + status + "\",\"request_id\":\"" + requestId + "\"}";
    }

    private static String sha256Hex(String value) {
        try { return Hex.encode(MessageDigest.getInstance("SHA-256").digest(value.getBytes(UTF_8))); }
        catch (NoSuchAlgorithmException error) { throw new IllegalStateException("SHA-256 unavailable", error); }
    }

    private String healthJson() {
        return "{\"schema\":\"" + HEALTH_SCHEMA + "\",\"package\":\"" + getPackageName()
                + "\",\"device_id\":\"" + Build.SERIAL + "\",\"session_id\":\"" + sessionId
                + "\",\"process_started_elapsed_realtime_ms\":" + processStartedElapsedRealtimeMs
                + ",\"process_uptime_ms\":" + (SystemClock.elapsedRealtime() - processStartedElapsedRealtimeMs)
                + ",\"lan_health_state\":\"" + lanHealthState + "\",\"lan_health_bind_address\":\""
                + lanHealthBindAddress + "\",\"lan_health_port\":" + LAN_HEALTH_PORT
                + ",\"wake_lock_held\":" + (partialWakeLock != null && partialWakeLock.isHeld())
                + ",\"wifi_lock_held\":" + (wifiLock != null && wifiLock.isHeld()) + "}";
    }
}
