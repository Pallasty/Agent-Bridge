package dev.agentbridge.companion;

import java.nio.charset.Charset;
import java.security.GeneralSecurityException;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public final class ConsentReceiptProtocol {
    private static final Charset UTF_8 = Charset.forName("UTF-8");
    private ConsentReceiptProtocol() {}

    public static String deriveReceiptKey(String masterToken) {
        if (!Hex.isLower(masterToken, 64)) throw new IllegalArgumentException("invalid master token");
        return hmac(Hex.decode(masterToken), "agent_bridge.mobile_consent_receipt.key.v0");
    }

    public static String sign(String key, String requestId, String deviceId, String sessionId,
                              String purpose, String challenge, long sequence, long issuedAt,
                              long expiresAt, String consentDigest, long durationMs,
                              long sampleRateHz, long maximumSamples) {
        if (!Hex.isLower(key, 64) || !Hex.isLower(challenge, 64) || !Hex.isLower(consentDigest, 64)
                || sequence <= 0 || expiresAt <= issuedAt || expiresAt - issuedAt > 10000L) {
            throw new IllegalArgumentException("invalid consent receipt fields");
        }
        String message = "ABCR1\n" + requestId + "\n" + deviceId + "\n" + sessionId + "\n"
                + purpose + "\n" + challenge + "\n" + sequence + "\n" + issuedAt + "\n"
                + expiresAt + "\n" + consentDigest + "\n" + durationMs + "\n" + sampleRateHz
                + "\n" + maximumSamples;
        return hmac(Hex.decode(key), message);
    }

    private static String hmac(byte[] key, String message) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return Hex.encode(mac.doFinal(message.getBytes(UTF_8)));
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException("HmacSHA256 unavailable", error);
        }
    }
}
