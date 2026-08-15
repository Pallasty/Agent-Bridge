package dev.agentbridge.companion;

import java.nio.charset.Charset;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

final class TextObservationProtocol {
    static final String SCHEMA = "agent_bridge.mobile_text_observation.v1";
    static final String RETENTION = "ephemeral_session_only";
    static final int MAX_TEXT_CHARS = 1000;
    static final int MAX_PAYLOAD_BYTES = 4096;
    private static final Charset UTF_8 = Charset.forName("UTF-8");

    static String payloadDigest(String text) {
        if (text == null || text.trim().isEmpty() || text.length() > MAX_TEXT_CHARS)
            throw new IllegalArgumentException("text must contain 1..1000 characters");
        try { return Hex.encode(MessageDigest.getInstance("SHA-256").digest(text.getBytes(UTF_8))); }
        catch (GeneralSecurityException error) { throw new IllegalStateException(error); }
    }

    static void validateSubmissionId(String submissionId) {
        if (!isLowerHex(submissionId, 32))
            throw new IllegalArgumentException("invalid submission id");
    }

    static String request(String tokenHex, String sessionId, long unixSeconds, String nonce,
            String payloadJson) {
        validate(tokenHex, sessionId, nonce);
        byte[] payloadBytes = payloadJson.getBytes(UTF_8);
        if (payloadBytes.length > MAX_PAYLOAD_BYTES)
            throw new IllegalArgumentException("text observation payload too large");
        String payload = encodeBase64NoPad(payloadBytes);
        String canonical = "ABT1\n" + sessionId + "\n" + unixSeconds + "\n" + nonce
                + "\n" + payload;
        return "ABT1 " + sessionId + " " + unixSeconds + " " + nonce + " " + payload
                + " " + Hex.encode(hmac(Hex.decode(tokenHex), canonical));
    }

    static void verifyAck(String tokenHex, String sessionId, long unixSeconds, String nonce,
            String expectedDigest, String response) {
        validate(tokenHex, sessionId, nonce);
        String[] fields = response.trim().split(" ", -1);
        if (fields.length != 3 || !"ACCEPTED".equals(fields[0])
                || !expectedDigest.equals(fields[1]) || !isLowerHex(fields[2], 64))
            throw new IllegalArgumentException("invalid text observation acknowledgement");
        String canonical = "ABT1R\n" + sessionId + "\n" + unixSeconds + "\n" + nonce
                + "\n" + expectedDigest;
        byte[] expected = hmac(Hex.decode(tokenHex), canonical);
        if (!MessageDigest.isEqual(expected, Hex.decode(fields[2])))
            throw new IllegalArgumentException("invalid text observation acknowledgement MAC");
    }

    private static void validate(String tokenHex, String sessionId, String nonce) {
        if (!isLowerHex(tokenHex, 64)) throw new IllegalArgumentException("invalid token");
        if (sessionId == null || !sessionId.matches("[A-Za-z0-9_.-]{1,64}"))
            throw new IllegalArgumentException("invalid session id");
        if (!isLowerHex(nonce, 32)) throw new IllegalArgumentException("invalid nonce");
    }

    private static boolean isLowerHex(String value, int length) {
        return value != null && value.length() == length && value.matches("[0-9a-f]+$");
    }

    private static byte[] hmac(byte[] key, String value) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return mac.doFinal(value.getBytes(UTF_8));
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException("HmacSHA256 unavailable", error);
        }
    }

    private static String encodeBase64NoPad(byte[] bytes) {
        final char[] alphabet =
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".toCharArray();
        StringBuilder out = new StringBuilder((bytes.length * 4 + 2) / 3);
        for (int i = 0; i < bytes.length; i += 3) {
            int value = (bytes[i] & 0xff) << 16;
            int remaining = Math.min(3, bytes.length - i);
            if (remaining > 1) value |= (bytes[i + 1] & 0xff) << 8;
            if (remaining > 2) value |= bytes[i + 2] & 0xff;
            out.append(alphabet[(value >>> 18) & 63]);
            out.append(alphabet[(value >>> 12) & 63]);
            if (remaining > 1) out.append(alphabet[(value >>> 6) & 63]);
            if (remaining > 2) out.append(alphabet[value & 63]);
        }
        return out.toString();
    }

    private TextObservationProtocol() {}
}
