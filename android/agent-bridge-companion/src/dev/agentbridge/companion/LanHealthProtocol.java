package dev.agentbridge.companion;

import java.nio.charset.Charset;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public final class LanHealthProtocol {
    private static final Charset UTF_8 = Charset.forName("UTF-8");
    private static final int MAX_REQUEST_BYTES = 1024;
    private static final long MAX_CLOCK_SKEW_SECONDS = 60L;
    private static final long RATE_WINDOW_SECONDS = 60L;
    private static final int MAX_REQUESTS_PER_WINDOW = 12;
    private static final int MAX_NONCES = 128;
    private final byte[] token;
    private final ArrayDeque<Long> attemptTimes = new ArrayDeque<Long>();
    private final LinkedHashMap<String, Long> acceptedNonces = new LinkedHashMap<String, Long>();

    public LanHealthProtocol(String tokenHex) {
        if (!Hex.isLower(tokenHex, 64)) {
            throw new IllegalArgumentException("health token must be 64 lowercase hex characters");
        }
        token = Hex.decode(tokenHex);
    }

    public synchronized Result verify(String request, long nowSeconds) {
        pruneAttempts(nowSeconds);
        if (attemptTimes.size() >= MAX_REQUESTS_PER_WINDOW) return Result.RATE_LIMITED;
        attemptTimes.addLast(nowSeconds);
        if (request == null || request.getBytes(UTF_8).length > MAX_REQUEST_BYTES) return Result.MALFORMED;
        String[] parts = request.split(" ", -1);
        if (parts.length != 4 || !"ABH1".equals(parts[0])
                || !Hex.isLower(parts[2], 32) || !Hex.isLower(parts[3], 64)) return Result.MALFORMED;
        final long issuedAt;
        try { issuedAt = Long.parseLong(parts[1]); }
        catch (NumberFormatException error) { return Result.MALFORMED; }
        if (issuedAt < nowSeconds - MAX_CLOCK_SKEW_SECONDS || issuedAt > nowSeconds + MAX_CLOCK_SKEW_SECONDS) {
            return Result.EXPIRED;
        }
        if (!MessageDigest.isEqual(hmac(canonical(issuedAt, parts[2])), Hex.decode(parts[3]))) return Result.BAD_MAC;
        if (acceptedNonces.containsKey(parts[2])) return Result.REPLAY;
        acceptedNonces.put(parts[2], nowSeconds);
        trimNonces();
        return Result.OK;
    }

    private void pruneAttempts(long now) {
        while (!attemptTimes.isEmpty() && attemptTimes.peekFirst() <= now - RATE_WINDOW_SECONDS) {
            attemptTimes.removeFirst();
        }
    }

    private void trimNonces() {
        while (acceptedNonces.size() > MAX_NONCES) {
            Iterator<Map.Entry<String, Long>> iterator = acceptedNonces.entrySet().iterator();
            iterator.next();
            iterator.remove();
        }
    }

    private byte[] hmac(String message) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(token, "HmacSHA256"));
            return mac.doFinal(message.getBytes(UTF_8));
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException("HmacSHA256 unavailable", error);
        }
    }

    private static String canonical(long issuedAt, String nonce) {
        return "ABH1\n" + issuedAt + "\n" + nonce;
    }

    public enum Result { OK, MALFORMED, EXPIRED, BAD_MAC, REPLAY, RATE_LIMITED }
}
