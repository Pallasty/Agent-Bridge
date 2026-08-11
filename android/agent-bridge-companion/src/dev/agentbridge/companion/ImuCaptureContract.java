package dev.agentbridge.companion;

public final class ImuCaptureContract {
    public static final long MIN_DURATION_MS = 100L;
    public static final long MAX_DURATION_MS = 1000L;
    public static final long MIN_SAMPLE_RATE_HZ = 1L;
    public static final long MAX_SAMPLE_RATE_HZ = 50L;

    private ImuCaptureContract() {}

    public static Request validate(String requestId, String challenge, long durationMs, long sampleRateHz) {
        if (!isRequestId(requestId) || !Hex.isLower(challenge, 64)
                || durationMs < MIN_DURATION_MS || durationMs > MAX_DURATION_MS
                || sampleRateHz < MIN_SAMPLE_RATE_HZ || sampleRateHz > MAX_SAMPLE_RATE_HZ) {
            throw new IllegalArgumentException("invalid IMU capture request");
        }
        long maximumSamples = (durationMs * sampleRateHz + 999L) / 1000L;
        int samplingPeriodUs = (int) (1_000_000L / sampleRateHz);
        return new Request(requestId, challenge, durationMs, sampleRateHz, maximumSamples, samplingPeriodUs);
    }

    private static boolean isRequestId(String value) {
        if (value == null || value.length() < 1 || value.length() > 64) return false;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
                    || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.')) return false;
        }
        return true;
    }

    public static final class Request {
        public final String requestId;
        public final String challenge;
        public final long durationMs;
        public final long sampleRateHz;
        public final long maximumSamples;
        public final int samplingPeriodUs;

        private Request(String requestId, String challenge, long durationMs, long sampleRateHz,
                        long maximumSamples, int samplingPeriodUs) {
            this.requestId = requestId;
            this.challenge = challenge;
            this.durationMs = durationMs;
            this.sampleRateHz = sampleRateHz;
            this.maximumSamples = maximumSamples;
            this.samplingPeriodUs = samplingPeriodUs;
        }
    }
}
