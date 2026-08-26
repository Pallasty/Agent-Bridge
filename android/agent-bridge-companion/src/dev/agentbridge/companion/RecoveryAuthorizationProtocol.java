package dev.agentbridge.companion;

import java.nio.charset.Charset;
import java.math.BigInteger;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PublicKey;
import java.security.interfaces.ECPublicKey;
import java.security.spec.ECFieldFp;
import java.security.spec.ECParameterSpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;

public final class RecoveryAuthorizationProtocol {
    public static final String RECEIPT_SCHEMA = "agent_bridge.app_control.recovery_authorization_receipt.v0";
    public static final String REQUEST_SCHEMA = "agent_bridge.app_control.recovery_authorization_broker_request.v0";
    public static final String AUTH_PROFILE_BIOMETRIC_STRONG = "biometric_strong";
    public static final String AUTH_PROFILE_DEVICE_CREDENTIAL = "device_credential";
    private static final Charset UTF_8 = Charset.forName("UTF-8");
    private static final BigInteger P256_P = hex("ffffffff00000001000000000000000000000000ffffffffffffffffffffffff");
    private static final BigInteger P256_A = hex("ffffffff00000001000000000000000000000000fffffffffffffffffffffffc");
    private static final BigInteger P256_B = hex("5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b");
    private static final BigInteger P256_GX = hex("6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296");
    private static final BigInteger P256_GY = hex("4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5");
    private static final BigInteger P256_N = hex("ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551");
    private RecoveryAuthorizationProtocol() {}

    public static String requireAuthenticationProfile(String profile) {
        if (!AUTH_PROFILE_BIOMETRIC_STRONG.equals(profile)
                && !AUTH_PROFILE_DEVICE_CREDENTIAL.equals(profile)) {
            throw new IllegalArgumentException("explicit recovery authentication profile required");
        }
        return profile;
    }

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
        if (signature == null || signature.length < 64 || signature.length > 80) throw new IllegalArgumentException("invalid signature");
        return Base64.getUrlEncoder().withoutPadding().encodeToString(canonical.getBytes(UTF_8))
                + "." + Base64.getUrlEncoder().withoutPadding().encodeToString(signature);
    }

    public static String publicKeyBase64(byte[] subjectPublicKeyInfo) {
        if (subjectPublicKeyInfo == null || subjectPublicKeyInfo.length < 80 || subjectPublicKeyInfo.length > 120)
            throw new IllegalArgumentException("invalid P-256 SubjectPublicKeyInfo");
        try {
            PublicKey key = KeyFactory.getInstance("EC").generatePublic(new X509EncodedKeySpec(subjectPublicKeyInfo));
            if (!(key instanceof ECPublicKey) || !isP256(((ECPublicKey) key).getParams()))
                throw new IllegalArgumentException("invalid P-256 SubjectPublicKeyInfo");
            return Base64.getUrlEncoder().withoutPadding().encodeToString(subjectPublicKeyInfo);
        } catch (IllegalArgumentException error) {
            throw error;
        } catch (Exception error) {
            throw new IllegalArgumentException("invalid P-256 SubjectPublicKeyInfo", error);
        }
    }

    public static String digest(String value) {
        try { return Hex.encode(MessageDigest.getInstance("SHA-256").digest(value.getBytes(UTF_8))); }
        catch (Exception error) { throw new IllegalStateException(error); }
    }
    private static boolean isP256(ECParameterSpec params) {
        return params != null && params.getCurve().getField() instanceof ECFieldFp
                && ((ECFieldFp) params.getCurve().getField()).getP().equals(P256_P)
                && params.getCurve().getA().equals(P256_A) && params.getCurve().getB().equals(P256_B)
                && params.getGenerator().getAffineX().equals(P256_GX)
                && params.getGenerator().getAffineY().equals(P256_GY)
                && params.getOrder().equals(P256_N) && params.getCofactor() == 1;
    }
    private static BigInteger hex(String value) { return new BigInteger(value, 16); }
    private static boolean lowerHex64(String value) { return value != null && value.matches("[0-9a-f]{64}"); }
}
