package dev.agentbridge.companion;

import java.nio.charset.Charset;
import java.security.MessageDigest;
import java.util.Base64;

public final class RecoveryAuthorizationProtocol {
    public static final String RECEIPT_SCHEMA = "agent_bridge.app_control.recovery_authorization_receipt.v0";
    public static final String REQUEST_SCHEMA = "agent_bridge.app_control.recovery_authorization_broker_request.v0";
    private static final Charset UTF_8 = Charset.forName("UTF-8");
    private RecoveryAuthorizationProtocol() {}

    public static String canonicalReceipt(String operationId, String recordSha256,
            String requestSha256, String workspaceSha256, String sessionSha256,
            long issuedAt, long expiresAt, String issuer, String nonce) {
        if (!operationId.matches("ab-episode-[0-9a-f]{32}")
                || !lowerHex64(recordSha256) || !lowerHex64(requestSha256)
                || !lowerHex64(workspaceSha256) || !lowerHex64(sessionSha256)
                || issuedAt <= 0 || expiresAt <= issuedAt || expiresAt - issuedAt > 300
                || issuer == null || !issuer.matches("android-keystore:[A-Za-z0-9._-]{1,64}")
                || nonce == null || !nonce.matches("[0-9a-f]{32,64}")) {
            throw new IllegalArgumentException("invalid recovery authorization receipt");
        }
        return "{\"expires_at_unix_seconds\":" + expiresAt
                + ",\"issued_at_unix_seconds\":" + issuedAt
                + ",\"issuer\":\"" + issuer + "\""
                + ",\"nonce\":\"" + nonce + "\""
                + ",\"operation_id\":\"" + operationId + "\""
                + ",\"record_sha256\":\"" + recordSha256 + "\""
                + ",\"request_sha256\":\"" + requestSha256 + "\""
                + ",\"schema\":\"" + RECEIPT_SCHEMA + "\""
                + ",\"session_sha256\":\"" + sessionSha256 + "\""
                + ",\"workspace_sha256\":\"" + workspaceSha256 + "\"}";
    }

    public static String receiptToken(String canonical, byte[] signature) {
        if (signature == null || signature.length != 64) throw new IllegalArgumentException("invalid Ed25519 signature");
        return Base64.getUrlEncoder().withoutPadding().encodeToString(canonical.getBytes(UTF_8))
                + "." + Base64.getUrlEncoder().withoutPadding().encodeToString(signature);
    }

    public static String publicKeyRawBase64(byte[] subjectPublicKeyInfo) {
        if (subjectPublicKeyInfo == null || subjectPublicKeyInfo.length != 44)
            throw new IllegalArgumentException("invalid Ed25519 SubjectPublicKeyInfo");
        byte[] prefix = new byte[] {0x30,0x2a,0x30,0x05,0x06,0x03,0x2b,0x65,0x70,0x03,0x21,0x00};
        for (int i=0;i<prefix.length;i++) if (subjectPublicKeyInfo[i] != prefix[i])
            throw new IllegalArgumentException("unexpected Ed25519 public key encoding");
        byte[] raw = new byte[32]; System.arraycopy(subjectPublicKeyInfo, 12, raw, 0, 32);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(raw);
    }

    public static String digest(String value) {
        try { return Hex.encode(MessageDigest.getInstance("SHA-256").digest(value.getBytes(UTF_8))); }
        catch (Exception error) { throw new IllegalStateException(error); }
    }
    private static boolean lowerHex64(String value) { return value != null && value.matches("[0-9a-f]{64}"); }
}
