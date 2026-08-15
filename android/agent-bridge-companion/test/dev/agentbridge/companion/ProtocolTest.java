package dev.agentbridge.companion;

import java.nio.charset.Charset;
import java.util.ArrayList;
import java.util.Base64;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public final class ProtocolTest {
    public static void main(String[] args) throws Exception {
        String token = repeat("11", 32);
        String nonce = "0123456789abcdef0123456789abcdef";
        long now = 1700000000L;
        String mac = hmac(token, "ABH1\n" + now + "\n" + nonce);
        LanHealthProtocol protocol = new LanHealthProtocol(token);
        check(protocol.verify("ABH1 " + now + " " + nonce + " " + mac, now) == LanHealthProtocol.Result.OK);
        check(protocol.verify("ABH1 " + now + " " + nonce + " " + mac, now) == LanHealthProtocol.Result.REPLAY);
        check(ImuCaptureContract.validate("request-1", repeat("22", 32), 500, 20).maximumSamples == 10);
        ImuSampleSummary summary = new ImuSampleSummary(1);
        summary.addAccelerometer(7, 1f, 2f, 3f);
        summary.addAccelerometer(8, 9f, 9f, 9f);
        check(summary.accelerometerSamples() == 1 && summary.payloadByteLength() == 21);
        String projectionSession = "projection-1";
        String projectionRequest = ProjectionProtocol.request(token, projectionSession, now, nonce);
        check(projectionRequest.equals("ABP1 " + projectionSession + " " + now + " " + nonce + " "
                + hmac(token, "ABP1\n" + projectionSession + "\n" + now + "\n" + nonce)));
        String payload = Base64.getEncoder().withoutPadding().encodeToString(
                "{\"schema\":\"agent_bridge.mobile_projection.frame.v1\"}".getBytes(Charset.forName("UTF-8")));
        String responseMac = hmac(token, "ABP1R\n" + projectionSession + "\n" + now + "\n" + nonce + "\n" + payload);
        String decoded = ProjectionProtocol.verifyResponse(token, projectionSession, now, nonce,
                "OK " + payload + " " + responseMac);
        check(decoded.contains(ProjectionProtocol.SCHEMA));
        boolean rejected = false;
        try { ProjectionProtocol.verifyResponse(token, projectionSession, now, nonce,
                "OK " + payload + " " + repeat("00", 32)); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected);
        ProjectionProtocol.validateSession(now, now + 600L);
        String text = "手机主动提交给 AB";
        String digest = TextObservationProtocol.payloadDigest(text);
        String textPayloadJson = "{\"schema\":\"" + TextObservationProtocol.SCHEMA
                + "\",\"text\":\"" + text + "\",\"payload_sha256\":\"" + digest + "\"}";
        String textPayload = Base64.getEncoder().withoutPadding().encodeToString(
                textPayloadJson.getBytes(Charset.forName("UTF-8")));
        String textRequest = TextObservationProtocol.request(
                token, projectionSession, now, nonce, textPayloadJson);
        check(textRequest.equals("ABT1 " + projectionSession + " " + now + " " + nonce
                + " " + textPayload + " "
                + hmac(token, "ABT1\n" + projectionSession + "\n" + now + "\n" + nonce
                        + "\n" + textPayload)));
        String ackMac = hmac(token, "ABT1R\n" + projectionSession + "\n" + now + "\n"
                + nonce + "\n" + digest);
        TextObservationProtocol.verifyAck(token, projectionSession, now, nonce, digest,
                "ACCEPTED " + digest + " " + ackMac);
        rejected = false;
        try { TextObservationProtocol.payloadDigest(repeat("x", 1001)); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected);
        ArrayList<String> transcripts = new ArrayList<String>();
        transcripts.add("  voice draft  ");
        check(VoiceDraftPolicy.firstTranscript(transcripts).equals("voice draft"));
        check(VoiceDraftPolicy.firstTranscript(null).isEmpty());
        check(VoiceDraftPolicy.mergeDraft("", "voice draft").equals("voice draft"));
        check(VoiceDraftPolicy.mergeDraft("typed draft", "voice draft")
                .equals("typed draft\nvoice draft"));
        check(VoiceDraftPolicy.mergeDraft("typed draft", "  ").equals("typed draft"));
        System.out.println("android companion protocol tests: PASS");
    }

    private static String hmac(String key, String message) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(Hex.decode(key), "HmacSHA256"));
        return Hex.encode(mac.doFinal(message.getBytes(Charset.forName("UTF-8"))));
    }

    private static String repeat(String value, int count) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < count; i++) out.append(value);
        return out.toString();
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError();
    }
}
