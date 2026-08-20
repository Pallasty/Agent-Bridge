package dev.agentbridge.companion;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.Charset;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

final class ProjectionProtocol {
    static final String SCHEMA = "agent_bridge.mobile_projection.frame.v1";
    static final long MAX_SESSION_SECONDS = 600L;
    private static final Charset UTF_8 = Charset.forName("UTF-8");

    static String request(String tokenHex, String sessionId, long unixSeconds, String nonce) {
        validate(tokenHex, sessionId, nonce);
        String canonical = "ABP1\n" + sessionId + "\n" + unixSeconds + "\n" + nonce;
        return "ABP1 " + sessionId + " " + unixSeconds + " " + nonce + " "
                + Hex.encode(hmac(Hex.decode(tokenHex), canonical));
    }

    static String verifyResponse(String tokenHex, String sessionId, long unixSeconds,
            String nonce, String response) {
        return verifyFrameResponse(tokenHex, sessionId, unixSeconds, nonce, response).rawJson;
    }

    /**
     * Verifies the legacy ABP1 response while retaining the exact authenticated
     * UTF-8 frame identity needed by the post-render ABR1 report.
     */
    static VerifiedFrame verifyFrameResponse(String tokenHex, String sessionId,
            long unixSeconds, String nonce, String response) {
        validate(tokenHex, sessionId, nonce);
        if (response == null) throw new IllegalArgumentException("empty projection response");
        String[] fields = response.trim().split(" ", -1);
        if (fields.length != 3 || !"OK".equals(fields[0]) || !isLowerHex(fields[2], 64))
            throw new IllegalArgumentException("invalid projection response");
        String canonical = "ABP1R\n" + sessionId + "\n" + unixSeconds + "\n" + nonce
                + "\n" + fields[1];
        byte[] expected = hmac(Hex.decode(tokenHex), canonical);
        if (!constantTimeEquals(expected, Hex.decode(fields[2])))
            throw new IllegalArgumentException("invalid projection response MAC");
        byte[] payload = decodeBase64NoPad(fields[1]);
        if (payload.length > 16384) throw new IllegalArgumentException("projection frame too large");
        return new VerifiedFrame(decodeUtf8Strict(payload), Hex.encode(sha256(payload)), payload);
    }

    static String renderReportRequest(String tokenHex, String sessionId, long unixSeconds,
            String nonce, long revision, String frameSha256) {
        validateRenderReport(tokenHex, sessionId, nonce, revision, frameSha256);
        String canonical = "ABR1\n" + sessionId + "\n" + unixSeconds + "\n" + nonce
                + "\n" + revision + "\n" + frameSha256;
        return "ABR1 " + sessionId + " " + unixSeconds + " " + nonce + " " + revision
                + " " + frameSha256 + " " + Hex.encode(hmac(Hex.decode(tokenHex), canonical));
    }

    static void verifyRenderReportAck(String tokenHex, String sessionId, long unixSeconds,
            String nonce, long revision, String frameSha256, String response) {
        validateRenderReport(tokenHex, sessionId, nonce, revision, frameSha256);
        if (response == null) throw new IllegalArgumentException("empty render acknowledgement");
        String[] fields = response.trim().split(" ", -1);
        if (fields.length != 4 || !"RENDERED".equals(fields[0])
                || !canonicalRevision(fields[1], revision)
                || !isLowerHex(fields[2], 64)
                || !isLowerHex(fields[3], 64)
                || !constantTimeEquals(Hex.decode(frameSha256), Hex.decode(fields[2])))
            throw new IllegalArgumentException("invalid render acknowledgement");
        String canonical = "ABR1R\n" + sessionId + "\n" + unixSeconds + "\n" + nonce
                + "\n" + revision + "\n" + frameSha256;
        if (!constantTimeEquals(hmac(Hex.decode(tokenHex), canonical), Hex.decode(fields[3])))
            throw new IllegalArgumentException("invalid render acknowledgement MAC");
    }

    static void validateSession(long now, long expiresAt) {
        if (expiresAt <= now || expiresAt - now > MAX_SESSION_SECONDS)
            throw new IllegalArgumentException("projection session must expire within 10 minutes");
    }

    private static void validate(String tokenHex, String sessionId, String nonce) {
        if (!isLowerHex(tokenHex, 64)) throw new IllegalArgumentException("invalid projection token");
        if (sessionId == null || !sessionId.matches("[A-Za-z0-9_.-]{1,64}"))
            throw new IllegalArgumentException("invalid projection session id");
        if (!isLowerHex(nonce, 32)) throw new IllegalArgumentException("invalid projection nonce");
    }

    private static void validateRenderReport(String tokenHex, String sessionId, String nonce,
            long revision, String frameSha256) {
        validate(tokenHex, sessionId, nonce);
        if (revision <= 0L) throw new IllegalArgumentException("invalid projection revision");
        if (!isLowerHex(frameSha256, 64))
            throw new IllegalArgumentException("invalid projection frame digest");
    }

    private static boolean canonicalRevision(String value, long expected) {
        if (value == null || !value.matches("0|[1-9][0-9]*")) return false;
        try {
            return Long.parseLong(value) == expected && value.equals(Long.toString(expected));
        } catch (NumberFormatException error) {
            return false;
        }
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

    private static byte[] sha256(byte[] value) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(value);
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException("SHA-256 unavailable", error);
        }
    }

    private static String decodeUtf8Strict(byte[] value) {
        try {
            return UTF_8.newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .decode(ByteBuffer.wrap(value)).toString();
        } catch (CharacterCodingException error) {
            throw new IllegalArgumentException("projection frame is not UTF-8", error);
        }
    }

    private static boolean constantTimeEquals(byte[] left, byte[] right) {
        if (left.length != right.length) return false;
        int difference = 0;
        for (int i = 0; i < left.length; i++) difference |= left[i] ^ right[i];
        return difference == 0;
    }

    private static byte[] decodeBase64NoPad(String value) {
        if (value == null || value.length() % 4 == 1 || !value.matches("[A-Za-z0-9+/]*"))
            throw new IllegalArgumentException("invalid projection payload encoding");
        ByteArrayOutputStream output = new ByteArrayOutputStream(value.length() * 3 / 4);
        int buffer = 0, bits = 0;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            int digit = c >= 'A' && c <= 'Z' ? c - 'A'
                    : c >= 'a' && c <= 'z' ? c - 'a' + 26
                    : c >= '0' && c <= '9' ? c - '0' + 52 : c == '+' ? 62 : 63;
            buffer = (buffer << 6) | digit;
            bits += 6;
            if (bits >= 8) { bits -= 8; output.write((buffer >> bits) & 0xff); }
        }
        if (bits > 0 && (buffer & ((1 << bits) - 1)) != 0)
            throw new IllegalArgumentException("non-canonical projection payload encoding");
        return output.toByteArray();
    }

    static final class VerifiedFrame {
        final String rawJson;
        final String frameSha256;
        private final byte[] rawJsonUtf8;

        private VerifiedFrame(String rawJson, String frameSha256, byte[] rawJsonUtf8) {
            this.rawJson = rawJson;
            this.frameSha256 = frameSha256;
            this.rawJsonUtf8 = rawJsonUtf8.clone();
        }

        byte[] rawJsonUtf8() { return rawJsonUtf8.clone(); }
    }

    private ProjectionProtocol() {}
}
