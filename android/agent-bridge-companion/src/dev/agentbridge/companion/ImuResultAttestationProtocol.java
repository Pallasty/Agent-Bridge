package dev.agentbridge.companion;

import java.nio.charset.Charset;
import java.security.GeneralSecurityException;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public final class ImuResultAttestationProtocol {
    private static final Charset UTF_8 = Charset.forName("UTF-8");
    private ImuResultAttestationProtocol() {}

    public static String deriveResultKey(String masterToken) {
        if (!Hex.isLower(masterToken, 64)) throw new IllegalArgumentException("invalid master token");
        return hmac(Hex.decode(masterToken), "agent_bridge.mobile_imu_result.key.v0");
    }

    public static String sign(String key, String requestId, String deviceId, String sessionId,
                              String challenge, long sequence, long issuedAt,
                              long accelerometerSamples, long gyroscopeSamples,
                              String payloadEncoding, long payloadByteLength, String payloadSha256,
                              boolean attentionAuthority, boolean memoryAuthority,
                              boolean actuationAuthority) {
        if (!Hex.isLower(key, 64) || requestId == null || requestId.length() == 0
                || deviceId == null || deviceId.length() == 0
                || sessionId == null || sessionId.length() == 0
                || !Hex.isLower(challenge, 64) || sequence <= 0 || issuedAt <= 0
                || accelerometerSamples <= 0 || gyroscopeSamples < 0
                || !"ab_imu_binary_v0".equals(payloadEncoding) || payloadByteLength <= 0
                || !Hex.isLower(payloadSha256, 64)
                || attentionAuthority || memoryAuthority || actuationAuthority) {
            throw new IllegalArgumentException("invalid IMU result attestation fields");
        }
        String message = "ABIR1\n" + requestId + "\n" + deviceId + "\n" + sessionId + "\n"
                + challenge + "\n" + sequence + "\n" + issuedAt + "\n" + accelerometerSamples
                + "\n" + gyroscopeSamples + "\n" + payloadEncoding + "\n" + payloadByteLength
                + "\n" + payloadSha256 + "\n" + attentionAuthority + "\n" + memoryAuthority
                + "\n" + actuationAuthority;
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
