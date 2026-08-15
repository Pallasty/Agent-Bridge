package dev.agentbridge.companion;

import java.util.ArrayList;

final class VoiceDraftPolicy {
    static String firstTranscript(ArrayList<String> candidates) {
        if (candidates == null) return "";
        for (String candidate : candidates) {
            if (candidate != null && !candidate.trim().isEmpty()) return candidate.trim();
        }
        return "";
    }

    static String mergeDraft(String existing, String transcript) {
        String current = existing == null ? "" : existing;
        String addition = transcript == null ? "" : transcript.trim();
        if (addition.isEmpty()) return current;
        if (current.trim().isEmpty()) return addition;
        return current + (current.endsWith("\n") ? "" : "\n") + addition;
    }

    private VoiceDraftPolicy() {}
}
