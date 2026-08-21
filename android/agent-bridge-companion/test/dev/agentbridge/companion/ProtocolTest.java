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
        String projectionResponse = "OK " + payload + " " + responseMac;
        ProjectionProtocol.VerifiedFrame verifiedFrame = ProjectionProtocol.verifyFrameResponse(
                token, projectionSession, now, nonce, projectionResponse);
        check(verifiedFrame.rawJson.contains(ProjectionProtocol.SCHEMA));
        check(verifiedFrame.rawJson.equals(new String(
                verifiedFrame.rawJsonUtf8(), Charset.forName("UTF-8"))));
        check(verifiedFrame.frameSha256.equals(
                "9cca83a4561232783196fc8a3f5361ef7bd1d41fdfe04700e49b662dae527adb"));
        check(ProjectionProtocol.verifyResponse(token, projectionSession, now, nonce,
                projectionResponse).equals(verifiedFrame.rawJson));
        boolean rejected = false;
        try { ProjectionProtocol.verifyResponse(token, projectionSession, now, nonce,
                "OK " + payload + " " + repeat("00", 32)); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected);
        String invalidUtf8Payload = "wyg";
        String invalidUtf8Mac = hmac(token, "ABP1R\n" + projectionSession + "\n" + now
                + "\n" + nonce + "\n" + invalidUtf8Payload);
        rejected = false;
        try { ProjectionProtocol.verifyFrameResponse(token, projectionSession, now, nonce,
                "OK " + invalidUtf8Payload + " " + invalidUtf8Mac); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected);
        long revision = 7L;
        String renderRequest = ProjectionProtocol.renderReportRequest(token, projectionSession,
                now, nonce, revision, verifiedFrame.frameSha256);
        check(renderRequest.equals("ABR1 projection-1 1700000000 "
                + "0123456789abcdef0123456789abcdef 7 "
                + "9cca83a4561232783196fc8a3f5361ef7bd1d41fdfe04700e49b662dae527adb "
                + "b81cd8e26188dfeaff025cb2d840e657d2308eeaf234f5a693394922c93e9545"));
        String renderAck = "RENDERED 7 " + verifiedFrame.frameSha256 + " "
                + "3d49253c3b4ca929eaafc2b567ba065081ae87917a0f431fd136f6a89b57b8c6";
        ProjectionProtocol.verifyRenderReportAck(token, projectionSession, now, nonce,
                revision, verifiedFrame.frameSha256, renderAck);
        rejected = false;
        try { ProjectionProtocol.verifyRenderReportAck(token, projectionSession, now, nonce,
                revision, verifiedFrame.frameSha256, renderAck.replace("RENDERED 7", "RENDERED 07")); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected);
        rejected = false;
        try { ProjectionProtocol.verifyRenderReportAck(token, projectionSession, now, nonce,
                revision, repeat("00", 32), renderAck); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected);
        rejected = false;
        try { ProjectionProtocol.verifyRenderReportAck(token, projectionSession, now, nonce,
                revision, verifiedFrame.frameSha256,
                "RENDERED 7 " + verifiedFrame.frameSha256 + " " + repeat("00", 32)); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected);
        rejected = false;
        try { ProjectionProtocol.renderReportRequest(token, projectionSession, now, nonce,
                0L, verifiedFrame.frameSha256); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected);
        ProjectionProtocol.validateSession(now, now + 600L);
        String text = "手机主动提交给 AB";
        String digest = TextObservationProtocol.payloadDigest(text);
        String submissionId = "abcdef0123456789abcdef0123456789";
        TextObservationProtocol.validateSubmissionId(submissionId);
        String textPayloadJson = "{\"schema\":\"" + TextObservationProtocol.SCHEMA
                + "\",\"submission_id\":\"" + submissionId + "\",\"text\":\"" + text
                + "\",\"payload_sha256\":\"" + digest + "\"}";
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
        rejected = false;
        try { TextObservationProtocol.validateSubmissionId("not-hex"); }
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
        String canonicalReceipt=RecoveryAuthorizationProtocol.canonicalReceipt(
                "ab-episode-"+repeat("1",32),repeat("2",64),repeat("3",64),repeat("4",64),repeat("5",64),
                now,now+120,"android-keystore:companion-v0",repeat("6",32));
        check(canonicalReceipt.equals("{\"expires_at_unix_seconds\":1700000120,\"issued_at_unix_seconds\":1700000000,"
                +"\"issuer\":\"android-keystore:companion-v0\",\"nonce\":\""+repeat("6",32)
                +"\",\"operation_id\":\"ab-episode-"+repeat("1",32)+"\",\"record_sha256\":\""+repeat("2",64)
                +"\",\"request_sha256\":\""+repeat("3",64)+"\",\"schema\":\""
                +RecoveryAuthorizationProtocol.RECEIPT_SCHEMA+"\",\"session_sha256\":\""+repeat("5",64)
                +"\",\"workspace_sha256\":\""+repeat("4",64)+"\"}"));
        check(RecoveryAuthorizationProtocol.receiptToken(canonicalReceipt,new byte[64]).split("\\.").length==2);
        rejected=false; try { RecoveryAuthorizationProtocol.canonicalReceipt("bad",repeat("2",64),repeat("3",64),
                repeat("4",64),repeat("5",64),now,now+120,"android-keystore:companion-v0",repeat("6",32)); }
        catch(IllegalArgumentException expected){ rejected=true; } check(rejected);
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
