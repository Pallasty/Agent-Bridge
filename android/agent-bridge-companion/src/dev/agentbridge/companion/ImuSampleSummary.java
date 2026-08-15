package dev.agentbridge.companion;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

public final class ImuSampleSummary {
    private final long maximumSamples;
    private final MessageDigest digest;
    private long accelerometerSamples;
    private long gyroscopeSamples;
    private double accelerometerSumX;
    private double accelerometerSumY;
    private double accelerometerSumZ;
    private long lastSensorTimestampNs;
    private long payloadByteLength;

    public ImuSampleSummary(long maximumSamples) {
        if (maximumSamples <= 0) throw new IllegalArgumentException("maximumSamples must be positive");
        this.maximumSamples = maximumSamples;
        try { digest = MessageDigest.getInstance("SHA-256"); }
        catch (NoSuchAlgorithmException error) { throw new IllegalStateException("SHA-256 unavailable", error); }
    }

    public synchronized void addAccelerometer(long timestamp, float x, float y, float z) {
        if (accelerometerSamples >= maximumSamples) return;
        accelerometerSamples++;
        accelerometerSumX += x;
        accelerometerSumY += y;
        accelerometerSumZ += z;
        addDigestSample((byte) 1, timestamp, x, y, z);
    }

    public synchronized void addGyroscope(long timestamp, float x, float y, float z) {
        if (gyroscopeSamples >= maximumSamples) return;
        gyroscopeSamples++;
        addDigestSample((byte) 2, timestamp, x, y, z);
    }

    private void addDigestSample(byte kind, long timestamp, float x, float y, float z) {
        ByteBuffer buffer = ByteBuffer.allocate(21).order(ByteOrder.BIG_ENDIAN);
        buffer.put(kind).putLong(timestamp).putFloat(x).putFloat(y).putFloat(z);
        byte[] sample = buffer.array();
        digest.update(sample);
        payloadByteLength += sample.length;
        lastSensorTimestampNs = timestamp;
    }

    public synchronized long accelerometerSamples() { return accelerometerSamples; }
    public synchronized long gyroscopeSamples() { return gyroscopeSamples; }
    public synchronized double accelerometerMeanX() { return accelerometerSamples == 0 ? 0 : accelerometerSumX / accelerometerSamples; }
    public synchronized double accelerometerMeanY() { return accelerometerSamples == 0 ? 0 : accelerometerSumY / accelerometerSamples; }
    public synchronized double accelerometerMeanZ() { return accelerometerSamples == 0 ? 0 : accelerometerSumZ / accelerometerSamples; }
    public synchronized long lastSensorTimestampNs() { return lastSensorTimestampNs; }
    public synchronized long payloadByteLength() { return payloadByteLength; }
    public synchronized String payloadSha256() {
        try { return Hex.encode(((MessageDigest) digest.clone()).digest()); }
        catch (CloneNotSupportedException error) { throw new IllegalStateException("SHA-256 digest cannot be cloned", error); }
    }
}
