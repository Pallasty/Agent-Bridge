#!/usr/bin/env python3
"""Truth table for the PURE audio-embodiment decision (spectral-peak discriminator)
+ Goertzel sanity. Runs under pytest, or standalone:
    python3 tests/test_audio_embody.py
"""
import array
import math
import os
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import audio_embody as ae  # noqa: E402


# --- classify_audio_embody truth table (rms, goertzel_f, goertzel_floor, frames) -

def test_emitted_when_target_is_a_peak_quiet_bus():
    # quiet-bus TRUE shape (first proof: rms~586, F~335, floor~0).
    assert ae.classify_audio_embody(586.0, 335.0, 1.0, 144000) == "emitted"


def test_emitted_on_BUSY_bus_when_target_peaks_above_floor():
    # REGRESSION (live dogfood): concurrent audio made the bus loud (rms~10800)
    # but our tone still PEAKS at F (293) well above the local floor (~97):
    # 293 >= 2.5*97=242.5 -> emitted. The old total-energy-ratio test failed here.
    assert ae.classify_audio_embody(10800.0, 293.0, 97.0, 109548) == "emitted"


def test_silent_when_bus_below_floor():
    assert ae.classify_audio_embody(0.0, 0.0, 0.0, 144000) == "silent"
    assert ae.classify_audio_embody(3.0, 2.0, 1.0, 144000) == "silent"  # under rms floor


def test_mismatch_busy_bus_no_peak_at_target():
    # REGRESSION (live dogfood FALSE): loud background, F not a peak (F ~= floor).
    assert ae.classify_audio_embody(10387.0, 97.0, 97.0, 105892) == "mismatch"
    # audio present but target bin tiny and below absolute min
    assert ae.classify_audio_embody(500.0, 3.0, 50.0, 144000) == "mismatch"


def test_no_capture_when_no_frames():
    assert ae.classify_audio_embody(0.0, 0.0, 0.0, 0) == "no_capture"
    assert ae.classify_audio_embody(999.0, 999.0, 1.0, 0) == "no_capture"


def test_peak_ratio_boundary():
    # just under the peak ratio -> mismatch; at/above -> emitted.
    floor = 100.0
    assert ae.classify_audio_embody(5000.0, 2.49 * floor, floor, 100) == "mismatch"
    assert ae.classify_audio_embody(5000.0, 2.5 * floor, floor, 100) == "emitted"


# --- verify_status mapping (gate-facing) ----------------------------------------

def test_only_emitted_maps_to_rendered_ok():
    assert ae.verify_status_for("emitted") == "rendered_ok"
    for s in ("silent", "mismatch", "no_capture", "error", "skipped"):
        assert ae.verify_status_for(s) != "rendered_ok", s
        assert ae.verify_status_for(s) == s  # honest reason carried verbatim


# --- Goertzel / spectral floor discriminate a real synthesized tone --------------

def _sine(freq, sr, n, amp=10000):
    return array.array("h", [int(amp * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)])


def test_goertzel_peaks_at_tone_and_floor_is_low():
    sr, n = 48000, 48000
    sig = _sine(440.0, sr, n)
    at_440 = ae.goertzel(sig, sr, 440.0)
    floor = ae.spectral_floor(sig, sr, 440.0)
    assert at_440 > 100.0, at_440                     # strong at the real tone
    assert floor < at_440 * 0.05, (floor, at_440)     # near-zero at off-target bins
    silent = array.array("h", [0] * n)
    assert ae.rms_of(silent) == 0.0
    assert ae.goertzel(silent, sr, 440.0) < 1.0


def test_full_chain_on_synthesized_samples():
    sr, n = 48000, 48000
    tone = _sine(440.0, sr, n)
    g = ae.goertzel(tone, sr, 440.0)
    fl = ae.spectral_floor(tone, sr, 440.0)
    assert ae.classify_audio_embody(ae.rms_of(tone), g, fl, n) == "emitted"
    sil = array.array("h", [0] * n)
    assert ae.classify_audio_embody(ae.rms_of(sil), ae.goertzel(sil, sr, 440.0),
                                    ae.spectral_floor(sil, sr, 440.0), n) == "silent"


# --- SPEECH mode: classify_speech_embody truth table ----------------------------
# (capture_rms, env_corr, voiced_secs, expected_secs, frames)

def test_speech_emitted_when_envelope_matches_and_voiced():
    # live P4 dogfood TRUE: played 7.2s, bus envelope correlated 0.992, voiced 5.9s.
    assert ae.classify_speech_embody(2541.72, 0.992, 5.9, 7.2, 404508) == "emitted"


def test_speech_silent_when_below_floor():
    # live P4 dogfood FALSE (no playback): silent bus -> silent, NOT emitted.
    assert ae.classify_speech_embody(0.0, 0.0, 0.0, 3.4, 169955) == "silent"
    assert ae.classify_speech_embody(3.0, 0.99, 2.0, 3.0, 144000) == "silent"  # under rms floor


def test_speech_mismatch_when_envelope_decorrelated():
    # busy bus (loud) but playing something else -> envelope shape doesn't match.
    assert ae.classify_speech_embody(8000.0, 0.12, 5.0, 7.0, 300000) == "mismatch"


def test_speech_mismatch_when_voiced_span_too_short():
    # envelope correlates on a brief blip, but voiced span is a tiny fraction of
    # the played duration -> reject (a click that happens to correlate isn't speech).
    assert ae.classify_speech_embody(5000.0, 0.9, 0.2, 7.0, 300000) == "mismatch"


def test_speech_no_capture_when_no_frames():
    assert ae.classify_speech_embody(0.0, 0.0, 0.0, 7.0, 0) == "no_capture"
    assert ae.classify_speech_embody(9999.0, 0.99, 7.0, 7.0, 0) == "no_capture"


def test_speech_env_corr_boundary():
    # at the correlation min (with enough voiced span) -> emitted; just under -> mismatch.
    exp, voiced = 4.0, 3.0
    assert ae.classify_speech_embody(5000.0, ae.ENV_CORR_MIN, voiced, exp, 100000) == "emitted"
    assert ae.classify_speech_embody(5000.0, ae.ENV_CORR_MIN - 0.01, voiced, exp, 100000) == "mismatch"


def test_speech_only_emitted_maps_to_rendered_ok():
    assert ae.verify_status_for("emitted") == "rendered_ok"
    for s in ("silent", "mismatch", "no_capture"):
        assert ae.verify_status_for(s) == s


# --- envelope cross-correlation discriminates shape (the speech falsifier core) --

def test_envelope_xcorr_finds_matching_shape_at_lag():
    played = [0.0, 0.0, 8.0, 16.0, 8.0, 0.0, 0.0, 0.0]
    # same shape embedded at lag 3 in a longer (constant-padded) captured envelope.
    captured = [3.0, 3.0, 3.0] + played + [3.0, 3.0]
    assert ae.envelope_xcorr(played, captured) > 0.9


def test_envelope_xcorr_low_for_unrelated_shape():
    played = [0.0, 0.0, 8.0, 16.0, 8.0, 0.0, 0.0, 0.0]
    unrelated = [0.0, 16.0] * 8          # alternating, nothing like the pulse
    assert ae.envelope_xcorr(played, unrelated) < 0.6


def test_envelope_xcorr_zero_for_flat():
    played = [0.0, 0.0, 8.0, 16.0, 8.0, 0.0, 0.0, 0.0]
    flat = [5.0] * 12                    # flat capture has no shape to correlate
    assert ae.envelope_xcorr(played, flat) == 0.0


def test_voiced_seconds_counts_above_floor():
    sr = 48000
    voiced = array.array("h", [1000] * (sr // 2))   # 0.5s above floor
    silence = array.array("h", [0] * (sr // 2))      # 0.5s silent
    assert abs(ae.voiced_seconds(voiced, sr) - 0.5) < 0.06
    assert ae.voiced_seconds(silence, sr) == 0.0


# --- intelligibility (STT round-trip) truth table -------------------------------

def test_word_overlap_is_recall_order_case_punct_insensitive():
    # live P5 dogfood TRUE: transcript == text (modulo case/punct) -> 1.0
    r, n = ae.word_overlap("Hello, brave world!", "hello brave world")
    assert (round(r, 3), n) == (1.0, 3)
    # missing words lower recall; extra hypothesis words don't help
    r, n = ae.word_overlap("a b c d", "a b zzz qqq")
    assert (round(r, 3), n) == (0.5, 4)
    # no reference words -> (0.0, 0)
    assert ae.word_overlap("", "anything") == (0.0, 0)


def test_classify_intelligibility_threshold():
    assert ae.classify_intelligibility(1.0, 10) == "intelligible"
    assert ae.classify_intelligibility(ae.INTELLIGIBLE_MIN, 10) == "intelligible"     # at threshold
    assert ae.classify_intelligibility(ae.INTELLIGIBLE_MIN - 0.01, 10) == "garbled"   # just under
    assert ae.classify_intelligibility(0.0, 10) == "garbled"                          # FALSE: nothing recovered
    assert ae.classify_intelligibility(0.0, 0) == "no_words"                          # nothing to check


def test_intelligibility_garbled_when_transcript_unrelated():
    # bus carried *some* speech but the words don't match what we asked for.
    ratio, nref = ae.word_overlap("activate the reactor core sequence",
                                  "the weather today is quite nice")
    assert ae.classify_intelligibility(ratio, nref) == "garbled"


# --- fast-emit tier honesty invariant (--mode emit) -----------------------------
# emit synthesizes + plays WITHOUT reading the bus back, so it must never claim a
# verification it didn't earn. These pin that invariant as a truth table.

def test_emit_played_never_claims_bus_verification():
    status, verify_status, verified_to = ae.emit_claim_fields(True)
    assert (status, verify_status, verified_to) == (
        "played_unverified",
        "unverified",
        None,
    )
    assert verify_status != "rendered_ok"
    assert verified_to is None


def test_emit_failed_play_is_honest_error():
    status, verify_status, verified_to = ae.emit_claim_fields(False)
    assert (status, verify_status, verified_to) == ("error", "error", None)
    assert verified_to is None


def test_emit_status_not_gate_passing_via_verify_status_map():
    assert ae.verify_status_for("played_unverified") != "rendered_ok"
    assert ae.verify_status_for("unverified") != "rendered_ok"


# --- honest attestation: verified_to is claimed ONLY on a real bus confirmation ---
# Fixes a latent leak: run()/run_speech() previously set verified_to=output bus
# unconditionally, so a busy/decorrelated bus that classifies as mismatch (or any
# early failure) still falsely reported verified_to=output bus. verify_status was
# honest (never rendered_ok), but the verified_to field was fabricated.

def test_honest_attestation_claims_bus_only_on_emitted():
    bus, trans = "output bus", "physical transducer"
    assert ae.honest_attestation("emitted", bus, trans) == (bus, trans)
    for fail in ("silent", "mismatch", "no_capture", "error", "skipped"):
        vt, nvt = ae.honest_attestation(fail, bus, trans)
        assert vt is None, fail                          # no verified_to claimed on failure
        assert "output bus" in nvt and "NOT confirmed" in nvt, fail   # bus folded into not_verified


# --- LCC-V1 voice-policy v0 decision truth table (decide_voice) ------------------
# Contract: forum #98 #2207/#2215 — silent by default; only 4 allowed modes;
# `verified` is a truth-claim requiring real evidence (never a bare mode flip);
# template/length-gated text; cooldown dedup by (agent,mode,evidence);
# verified -> speech (bus-verified) tier, ambient modes -> emit (fast) tier.

def test_voice_default_silent_outside_allowed_modes():
    d = ae.decide_voice("working", voice_line="busy", agent_id="a")
    assert d["speak"] is False and d["tier"] == "silent" and d["reason"] == "mode_not_allowed"


def test_voice_verified_requires_evidence():
    # load-bearing grounding rule: 'verified' with no evidence -> silent.
    d = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a", evidence_ids=[])
    assert d["speak"] is False and d["reason"] == "verified_requires_evidence"
    # with evidence -> speaks, and routes to the VERIFIED (speech) tier.
    d2 = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a",
                         evidence_ids=["voice_kokoro_123"])
    assert d2["speak"] is True and d2["tier"] == "speech" and d2["text"] == "Verified."


def test_voice_ambient_modes_route_to_emit_tier():
    for m, lid in [("failed", "failed.generic"),
                   ("waiting_for_user", "waiting_for_user.generic"),
                   ("handoff", "handoff.generic")]:
        d = ae.decide_voice(m, voice_line_id=lid, agent_id="a")
        assert d["speak"] is True and d["tier"] == "emit", (m, d)


def test_voice_text_source_template_and_raw_line():
    assert ae.decide_voice("handoff", voice_line_id="handoff.generic", agent_id="a")["text"] == "Handing off."
    d2 = ae.decide_voice("handoff", voice_line_id="handoff.bogus", agent_id="a")
    assert d2["speak"] is False and d2["reason"] == "unknown_line_id"
    d3 = ae.decide_voice("handoff", voice_line="Passing the baton.", agent_id="a")
    assert d3["speak"] is True and d3["text"] == "Passing the baton."
    d4 = ae.decide_voice("handoff", voice_line="x" * 999, agent_id="a")
    assert d4["speak"] is False and d4["reason"] == "line_too_long"
    d5 = ae.decide_voice("handoff", agent_id="a")
    assert d5["speak"] is False and d5["reason"] == "no_text"


def test_voice_cooldown_dedups_same_evidence():
    ev = ["outcome_42"]
    d = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a",
                        evidence_ids=ev, last_spoken_ts=1000.0, now=1100.0, cooldown_secs=300)
    assert d["speak"] is False and d["reason"] == "cooldown"
    d2 = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a",
                         evidence_ids=ev, last_spoken_ts=1000.0, now=1400.0, cooldown_secs=300)
    assert d2["speak"] is True


def test_voice_dedup_key_is_agent_mode_evidence():
    k1 = ae.voice_dedup_key("a", "verified", ["o1", "o2"])
    assert k1 == ae.voice_dedup_key("a", "verified", ["o2", "o1"])   # order-insensitive
    assert ae.voice_dedup_key("a", "verified", ["o3"]) != k1         # diff evidence -> diff key
    assert ae.voice_dedup_key("b", "verified", ["o1", "o2"]) != k1   # diff agent -> diff key
    assert ae.voice_evidence_hash([]) == "none"
    assert ae.voice_dedup_key("a", "handoff", []).endswith("|handoff|none")


def test_voice_receipt_silent_path_never_claims_verification():
    # silent path needs no audio: disallowed mode -> receipt claims no verification.
    r = ae.run_voice("working", "af_sarah", None, None, voice_line="busy", agent_id="a")
    assert r["status"] == "silent" and r["verify_status"] == "skipped"
    assert r["verify_status"] != "rendered_ok" and r["verified_to"] is None
    assert r["tier"] == "silent" and r["decision"] == "mode_not_allowed"
    # verified-without-evidence is silent too — no emission attempted, no claim.
    r2 = ae.run_voice("verified", "af_sarah", None, None, voice_line_id="verified.generic", agent_id="a")
    assert r2["status"] == "silent" and r2["decision"] == "verified_requires_evidence"
    assert r2["verify_status"] != "rendered_ok"


# --- adversarial-found regressions (workflow lcc-v1-voice-adversarial-verify) ----

def test_voice_grounding_rejects_non_string_evidence_placeholders():
    # INV-GROUND (high): str(None)=='None' must NOT count as evidence. A null/0/False
    # placeholder can never let a 'verified' truth-claim speak.
    for bad in ([None], [False], [0], [0.0], [[]], [{}], ["   "], ["\t", "\n"], [""]):
        d = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a", evidence_ids=bad)
        assert d["speak"] is False and d["reason"] == "verified_requires_evidence", bad
    assert ae.voice_evidence_hash([None]) == "none"
    assert ae.voice_evidence_hash([0, False, "  "]) == "none"
    # a real string evidence among placeholders survives, and only the real one.
    d2 = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a",
                         evidence_ids=[None, "real-evt", ""])
    assert d2["speak"] is True and d2["evidence_ids"] == ["real-evt"]


def test_honest_attestation_claims_bus_only_on_emitted():
    # INV-RECEIPT-NOFAB / INV-CONTRACT: verified_to is non-null ONLY on a real bus
    # confirmation; every failure moves the bus into not_verified.
    bus, trans = "output bus", "physical transducer"
    assert ae.honest_attestation("emitted", bus, trans) == (bus, trans)
    for fail in ("silent", "mismatch", "no_capture", "error", "skipped"):
        vt, nvt = ae.honest_attestation(fail, bus, trans)
        assert vt is None, fail
        assert "output bus" in nvt and "NOT confirmed" in nvt, fail


def test_voice_dedup_key_injection_safe():
    # INV-COOLDOWN: a '|' in agent_id/mode cannot collide two distinct tuples.
    assert ae.voice_dedup_key("svc", "x|y", []) != ae.voice_dedup_key("svc|x", "y", [])
    assert ae.voice_dedup_key("a|b", "verified", ["e"]) != ae.voice_dedup_key("a", "b|verified", ["e"])


# --- 2nd-round adversarial regressions (reverify workflow found deeper holes) ----

def test_voice_grounding_rejects_zero_width_evidence():
    # INV-GROUND zero-width bypass: invisible format chars are NOT real evidence —
    # str.strip() leaves them, so they must be rejected by category.
    for zw in ["​", "﻿", "‌", "‍", "⁠", "᠎", "​﻿‍", "  "]:
        d = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a", evidence_ids=[zw])
        assert d["speak"] is False and d["reason"] == "verified_requires_evidence", repr(zw)
    assert ae.voice_evidence_hash(["​", "﻿"]) == "none"
    # an id that carries a real visible token still counts (incidental zero-width ok)
    d2 = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a", evidence_ids=["​evt-9"])
    assert d2["speak"] is True


def test_voice_verified_tier_synth_failure_names_bus_in_not_verified():
    # INV-CONTRACT early-return: a verified line whose synth fails (no synth bin) is
    # routed to the speech tier, fails early, and must STILL name the bus as
    # not_verified (it was never confirmed there) — and never claim verified_to.
    r = ae.run_voice("verified", "af_sarah", None, "/nonexistent/ab-tts-synth",
                     evidence_ids=["evt-1"], voice_line_id="verified.generic", agent_id="a")
    assert r["tier"] == "speech" and r["status"] == "error"
    assert r["verify_status"] != "rendered_ok" and r["verified_to"] is None
    assert "output bus" in (r.get("not_verified") or "")


def test_voice_grounding_rejects_combining_marks_and_surrogates():
    # round-3 INV-GROUND: bare combining marks (Mn), enclosing marks (Me), variation
    # selectors (Mn) and surrogates (Cs) carry no standalone glyph — not real evidence.
    for bad in ["́", "️", "︀", "⃝", "́̂", "\udc80"]:
        d = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a", evidence_ids=[bad])
        assert d["speak"] is False and d["reason"] == "verified_requires_evidence", repr(bad)
    # a surrogate must not crash the hash (DoS guard), even mixed with a real id
    assert ae.voice_evidence_hash(["evt\udc80-1"])   # no UnicodeEncodeError
    assert ae.text_hash("say\udc80")                  # no UnicodeEncodeError
    # a real visible id still speaks
    assert ae.decide_voice("verified", voice_line_id="verified.generic",
                           agent_id="a", evidence_ids=["e1"])["speak"] is True


def test_voice_grounding_rejects_hangul_filler_invisibles():
    # round-4 INV-GROUND: Hangul fillers are category Lo (letters) yet render as
    # nothing (Default_Ignorable); U+3164 is the canonical web "invisible character".
    for filler in ["\u115f", "\u1160", "\u3164", "\uffa0", "\u3164\u3164"]:
        d = ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a", evidence_ids=[filler])
        assert d["speak"] is False and d["reason"] == "verified_requires_evidence", hex(ord(filler[0]))
    assert ae.voice_evidence_hash(["\u3164"]) == "none"
    # a filler mixed with a real visible token still counts
    assert ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a",
                           evidence_ids=["\u3164evt-1"])["speak"] is True
    # a genuine CJK letter id (also category Lo) is NOT rejected — it renders a glyph
    assert ae.decide_voice("verified", voice_line_id="verified.generic", agent_id="a",
                           evidence_ids=["中"])["speak"] is True


# --- mic channel = the ACOUSTIC rung; honest boundary (acoustic != the human ear) -
# Empirically (aio2/AG06 headphones): playing to in-ear output -> the room mic hears
# ambient but NOT the tone -> classify_audio_embody returns `mismatch`, and
# honest_attestation then reports verified_to=None — the boundary refuses to claim
# acoustic verification of private in-ear audio. The strings below pin the contract.

def test_mic_channel_boundary_is_acoustic_not_eardrum():
    _, _, vt, nvt = ae.resolve_targets("test-sink", "mic")
    assert "acoustic" in vt and "air" in vt                     # mic verifies sound in the air
    assert "eardrum" in nvt and ("in-ear" in nvt or "headphone" in nvt)   # NOT the human ear
    # the default sink_monitor channel verifies only the bus, never the transducer.
    sink, src, vt2, nvt2 = ae.resolve_targets("test-sink", "sink_monitor")
    assert "output bus" in vt2 and "transducer" in nvt2 and src.endswith(".monitor")


def test_mic_acoustic_mismatch_claims_nothing():
    # a mic that hears ambient but not the played tone (the headphone case) classifies
    # as mismatch; honest_attestation must then claim no acoustic verified_to.
    bus_vt = "acoustic output (a microphone heard the signal in the air)"
    bus_nvt = "the specific listener's eardrum ..."
    for fail in ("mismatch", "silent", "no_capture"):
        vt, nvt = ae.honest_attestation(fail, bus_vt, bus_nvt)
        assert vt is None and "NOT confirmed" in nvt, fail
    # only a real acoustic 'emitted' (mic actually heard it) claims the acoustic target
    assert ae.honest_attestation("emitted", bus_vt, bus_nvt) == (bus_vt, bus_nvt)


# --- synth_file channel (macOS / no-loopback): classify_synth_file_embody ---------
# The readback object is the synth WAV ITSELF, so env-vs-itself is meaningless and the
# GATE is the STT word_overlap. Same {emitted|silent|mismatch|no_capture} vocabulary.

def test_synth_file_emitted_when_words_recovered():
    # non-silent audio, STT available, overlap >= SYNTH_FILE_INTEL_MIN (0.8 — TIGHTER than the
    # 0.6 noisy-bus floor; the clean synth file should recover ~all words). duration guard
    # disabled (expected_dur_s defaults 0) to isolate the word gate. (#2300 MED-1)
    assert ae.classify_synth_file_embody(64000, 1200.0, 0.9, 10, True) == "emitted"
    assert ae.classify_synth_file_embody(64000, 1200.0, 0.8, 10, True) == "emitted"  # boundary


def test_synth_file_mismatch_is_the_macos_truncation_case():
    # The macOS super-compact default voice TRUNCATION case: a real non-silent clip
    # (a duration/RMS-only check would PASS) whose words did NOT survive synthesis ->
    # low overlap -> mismatch. This is exactly why the gate must read CONTENT, not the
    # envelope: only the STT word_overlap exposes the broken clip.
    assert ae.classify_synth_file_embody(13000, 800.0, 0.1, 10, True) == "mismatch"
    assert ae.classify_synth_file_embody(64000, 1200.0, 0.59, 10, True) == "mismatch"  # just under
    # #2300 MED-1: the 0.6-0.79 mild-truncation band — previously falsely 'emitted' on the
    # 0.6 bus floor — is now 'mismatch' under the tighter clean-channel floor (0.8).
    assert ae.classify_synth_file_embody(64000, 1200.0, 0.6, 10, True) == "mismatch"
    assert ae.classify_synth_file_embody(64000, 1200.0, 0.79, 10, True) == "mismatch"


def test_synth_file_no_capture_when_nothing_synthesized():
    assert ae.classify_synth_file_embody(0, 0.0, 0.9, 10, True) == "no_capture"


def test_synth_file_silent_when_below_rms_floor():
    # frames present but no energy (synth produced a silent file) -> silent, not emitted
    assert ae.classify_synth_file_embody(64000, 1.0, 0.9, 10, True) == "silent"


def test_synth_file_stt_unavailable_is_no_capture_not_mismatch():
    # degraded capability (no whisper) must NOT claim emitted AND must NOT assert the
    # words were wrong (mismatch) — it honestly reports no_capture.
    assert ae.classify_synth_file_embody(64000, 1200.0, 0.0, 10, False) == "no_capture"
    # empty reference (no requested words) also cannot verify -> no_capture
    assert ae.classify_synth_file_embody(64000, 1200.0, 0.0, 0, True) == "no_capture"


def test_synth_file_only_emitted_maps_to_rendered_ok():
    assert ae.verify_status_for("emitted") == "rendered_ok"
    for s in ("silent", "mismatch", "no_capture", "error"):
        assert ae.verify_status_for(s) != "rendered_ok", s


def test_synth_file_honest_attestation_and_channel_label():
    # the synth_file channel proves the FILE is intelligible — never the bus/transducer.
    vt = "synthesized audio file (STT-intelligible speech rendered to disk)"
    nvt = ("output bus AND physical transducer — this run read the synth file, "
           "not any playback (no loopback / sink .monitor on macOS)")
    # only emitted earns the verified_to
    assert ae.honest_attestation("emitted", vt, nvt) == (vt, nvt)
    # every failure folds the channel target into not_verified, verified_to=None
    for fail in ("silent", "mismatch", "no_capture"):
        v, n = ae.honest_attestation(fail, vt, nvt)
        assert v is None and "NOT confirmed" in n, fail
    # CHANNEL-MISLABEL guard: the synth_file not_verified MUST name the OUTPUT BUS (this
    # channel never read it) — else a reader is misled into thinking playback was proven.
    assert "output bus" in nvt and "physical transducer" in nvt


def test_say_backend_never_uses_truncating_default_voice():
    # the say backend must fall back to an explicit, full-quality voice (the bare
    # default resolves to the truncating super-compact alias).
    assert ae._MACOS_DEFAULT_VOICE and not ae._MACOS_DEFAULT_VOICE.startswith(("af_", "bf_"))


def test_say_wav_paths_are_unique_per_request():
    first = ae._new_say_wav_path()
    second = ae._new_say_wav_path()
    try:
        assert first != second
        assert not os.path.exists(first)
        assert not os.path.exists(second)
        assert os.path.basename(first).startswith("ab_voice_say_")
    finally:
        for path in (first, second):
            if os.path.exists(path):
                os.unlink(path)


def test_serialized_say_playback_returns_process_timing(monkeypatch, tmp_path):
    wav = tmp_path / "voice.wav"
    wav.write_bytes(b"fake")
    monkeypatch.setattr(ae.os.path, "exists", lambda path: path == "/usr/bin/afplay")
    monkeypatch.setattr(
        ae.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr=""),
    )
    out = ae.play_say_serialized(str(wav))
    assert out["play_ok"] is True
    assert out["playback_serialized"] is True
    assert out["playback_lock_wait_ms"] >= 0
    assert out["playback_elapsed_ms"] >= 0
    assert isinstance(out["playback_started_at_unix_ms"], int)


def test_cjk_units_participate_in_overlap_and_duration():
    ratio, nref = ae.word_overlap("Agent Bridge 本地语音", "Agent Bridge 本地語音")
    assert nref == 6
    assert ratio == 5 / 6
    # English behavior is unchanged; CJK is no longer collapsed to zero/one word.
    assert round(ae._expected_speech_duration("one two", 120), 3) == 1.0
    assert ae._expected_speech_duration("本地语音", 120) > 1.0


def test_synth_file_selects_zh_stt_for_cjk():
    seen = {}
    saved = _patch(
        synth_say=lambda t, v, s: ("/tmp/ab_fake.wav",
                                   {"ok": True, "backend": "say", "voice": "Tingting",
                                    "sample_rate": 16000, "wpm": 175}),
        _read_wav_mono_s16=lambda p: {"samples": [1000] * 48000, "sr": 16000, "frames": 48000},
        transcribe_synth_file=lambda w, model=None, language="en":
            (seen.setdefault("language", language) and "本地语音", None),
    )
    try:
        out = ae.run_speech_synth_file("本地语音", "Tingting", 1.0)
        assert seen["language"] == "zh"
        assert out["stt_language"] == "zh"
        assert out["verify_method"] == "synth_file_stt"
        assert out["status"] == "emitted", out
    finally:
        _restore(saved)


def test_qwen3_requires_an_explicit_isolated_runtime(monkeypatch):
    monkeypatch.delenv("AB_QWEN3_TTS_PYTHON", raising=False)
    wav, info = ae.synth_qwen3("你好", "Serena", 1.0)
    assert wav is None
    assert "AB_QWEN3_TTS_PYTHON" in info["detail"]


def test_synth_file_qwen3_records_backend_and_expression_provenance():
    saved = _patch(
        synth_qwen3=lambda *args, **kwargs: ("/tmp/ab_fake.wav", {
            "ok": True, "backend": "qwen3", "voice": "Serena", "sample_rate": 24000,
            "wpm": 175, "model": "Qwen/test", "device": "mps", "dtype": "float16",
            "instruct_applied": True,
        }),
        _read_wav_mono_s16=lambda p: {"samples": [1000] * 48000, "sr": 16000, "frames": 48000},
        transcribe_synth_file=lambda w, model=None, language="en": ("本地语音", None),
    )
    try:
        out = ae.run_speech_synth_file("本地语音", "Serena", 1.0, synth_backend="qwen3",
                                       qwen_instruct="温暖、平静")
        assert out["synth_backend"] == "qwen3"
        assert out["qwen_model"] == "Qwen/test"
        assert out["qwen_device"] == "mps"
        assert out["qwen_instruct_applied"] is True
        assert out["status"] == "emitted", out
    finally:
        _restore(saved)


def test_whisper_timeout_is_bounded_and_degrades():
    original_exists = ae.os.path.exists
    original_run = ae.subprocess.run
    original_env = ae.os.environ.get("AB_TTS_WHISPER_TIMEOUT_SECS")
    try:
        ae.os.path.exists = lambda p: True
        ae.subprocess.run = lambda *a, **kw: (_ for _ in ()).throw(
            ae.subprocess.TimeoutExpired(a[0], kw["timeout"]))
        ae.os.environ["AB_TTS_WHISPER_TIMEOUT_SECS"] = "12"
        transcript, err = ae.transcribe_synth_file("/tmp/fake.wav")
        assert transcript is None
        assert err == "whisper timed out after 12s"
    finally:
        ae.os.path.exists = original_exists
        ae.subprocess.run = original_run
        if original_env is None:
            ae.os.environ.pop("AB_TTS_WHISPER_TIMEOUT_SECS", None)
        else:
            ae.os.environ["AB_TTS_WHISPER_TIMEOUT_SECS"] = original_env


def test_zh_whisper_requests_simplified_chinese_without_leaking_reference_text():
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "voice.wav")
        open(wav, "wb").close()
        whisper = os.path.join(td, "whisper")
        open(whisper, "wb").close()
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            outdir = cmd[cmd.index("--output_dir") + 1]
            with open(os.path.join(outdir, "voice.txt"), "w", encoding="utf-8") as f:
                f.write("中文语音闭环测试")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        old_run = ae.subprocess.run
        old_bin = os.environ.get("AB_TTS_WHISPER_BIN")
        try:
            ae.subprocess.run = fake_run
            os.environ["AB_TTS_WHISPER_BIN"] = whisper
            transcript, err = ae.transcribe_synth_file(wav, model="tiny", language="zh")
        finally:
            ae.subprocess.run = old_run
            if old_bin is None:
                os.environ.pop("AB_TTS_WHISPER_BIN", None)
            else:
                os.environ["AB_TTS_WHISPER_BIN"] = old_bin

        assert err is None
        assert transcript == "中文语音闭环测试"
        assert seen["cmd"][-2:] == ["--initial_prompt", "以下是普通话的简体中文句子。"]


# --- #2300 review fixes: duration guard (MED-1) + empty-transcript no_capture (MED-2) -----

def _patch(**stubs):
    """Save + set ae.<name> stubs; returns the saved originals for _restore."""
    saved = {k: getattr(ae, k) for k in stubs}
    for k, v in stubs.items():
        setattr(ae, k, v)
    return saved


def _restore(saved):
    for k, v in saved.items():
        setattr(ae, k, v)


def test_synth_file_duration_guard_catches_repeated_word_inflation():
    # #2300 MED-1: set-recall word_overlap INFLATES on repeated reference words, so a truncated
    # clip can pass the word gate. The DURATION guard (synth_dur < 0.5 * expected) catches it
    # even at overlap 1.0.
    assert ae.classify_synth_file_embody(5000, 900.0, 1.0, 5, True,
                                         synth_dur_s=0.3, expected_dur_s=1.7) == "mismatch"
    # full-length clip with good words -> emitted (guard does NOT false-reject legit synthesis)
    assert ae.classify_synth_file_embody(50000, 900.0, 0.9, 10, True,
                                         synth_dur_s=3.0, expected_dur_s=3.4) == "emitted"
    # expected_dur_s<=0 disables the guard (unknown timing -> word gate alone, back-compat)
    assert ae.classify_synth_file_embody(5000, 900.0, 0.9, 5, True,
                                         synth_dur_s=0.1, expected_dur_s=0.0) == "emitted"


def test_synth_file_caller_empty_transcript_is_no_capture_not_mismatch():
    # #2300 MED-2: a WORKING whisper returning an empty transcript ("", None) must route to
    # no_capture (degraded), NOT mismatch (false "words came out wrong"). Regression at the
    # CALLER level — the bug was in run_speech_synth_file's `transcript is not None` wiring.
    saved = _patch(
        synth_say=lambda t, v, s: ("/tmp/ab_fake.wav",
                                   {"ok": True, "backend": "say", "voice": "Samantha",
                                    "sample_rate": 16000, "wpm": 175}),
        _read_wav_mono_s16=lambda p: {"samples": [1000] * 48000, "sr": 16000, "frames": 48000},
        transcribe_synth_file=lambda w, model=None, language="en": ("", None),  # working whisper, no words
    )
    try:
        out = ae.run_speech_synth_file("hello world this is a real test", "Samantha", 1.0)
        assert out["status"] == "no_capture", out["status"]
        assert out["verify_status"] != "rendered_ok", out["verify_status"]
        assert out["verified_to"] is None
        assert "output bus" in out["not_verified"] and "physical transducer" in out["not_verified"]
    finally:
        _restore(saved)


def test_synth_file_caller_duration_guard_rejects_truncated_clip():
    # #2300 MED-1 at the CALLER: words recovered (overlap 1.0 via repeats) but the clip is far
    # too short for the text -> the wired expected_dur (words/wpm) fires the truncation guard.
    saved = _patch(
        synth_say=lambda t, v, s: ("/tmp/ab_fake.wav",
                                   {"ok": True, "backend": "say", "voice": "Samantha",
                                    "sample_rate": 16000, "wpm": 175}),
        _read_wav_mono_s16=lambda p: {"samples": [1000] * 6400, "sr": 16000, "frames": 6400},  # 0.4s
        transcribe_synth_file=lambda w, model=None, language="en": ("go now here", None),  # all unique words back
    )
    try:
        # 10 words (go x8 + now + here) -> expected ~3.43s; synth 0.4s << 0.5*expected -> truncated
        out = ae.run_speech_synth_file("go go go go go go go go now here", "Samantha", 1.0)
        assert out["word_overlap"] == 1.0, out["word_overlap"]   # word gate WOULD have passed
        assert out["status"] == "mismatch", out["status"]        # but duration guard fires
        assert out["verify_status"] != "rendered_ok", out["verify_status"]
        assert out["verified_to"] is None
        assert "TRUNCATED" in out["detail"], out["detail"]
    finally:
        _restore(saved)


def test_synth_file_caller_full_clip_emitted_with_verified_to():
    # positive control: a full-length, fully-transcribed clip -> emitted + verified_to set.
    # proves the tightened gates do NOT reject legitimate synthesis (no false-low).
    text = "one two three four five six seven eight nine ten"  # 10 words -> expected ~3.43s
    saved = _patch(
        synth_say=lambda t, v, s: ("/tmp/ab_fake.wav",
                                   {"ok": True, "backend": "say", "voice": "Samantha",
                                    "sample_rate": 16000, "wpm": 175}),
        _read_wav_mono_s16=lambda p: {"samples": [1000] * 54880, "sr": 16000, "frames": 54880},  # 3.43s
        transcribe_synth_file=lambda w, model=None, language="en": (text, None),
    )
    try:
        out = ae.run_speech_synth_file(text, "Samantha", 1.0)
        assert out["status"] == "emitted", out["status"]
        assert out["verify_status"] == "rendered_ok", out["verify_status"]
        assert out["verified_to"] == "synthesized audio file (STT-intelligible speech rendered to disk)"
        assert out["word_overlap"] == 1.0, out["word_overlap"]
    finally:
        _restore(saved)


def test_synth_file_word_gate_is_length_aware():
    # #2300 MED-1 refinement (adversarial w795q6xei FALSE-LOW): whisper-tiny is NOISY on
    # SHORT clips (voice templates are 1-3 words), so a flat 0.8 floor would falsely reject a
    # good short line when STT drops one word. The DURATION guard (separate) catches
    # truncation; the word gate is length-aware so short good clips are not false-rejected.
    # All calls leave expected_dur_s=0 (guard disabled) to isolate the word gate.
    # 1-2 words: all back -> emitted; any miss -> no_capture (NOT a false mismatch/garbled).
    assert ae.classify_synth_file_embody(20000, 900.0, 1.0, 2, True) == "emitted"      # both back
    assert ae.classify_synth_file_embody(20000, 900.0, 0.5, 2, True) == "no_capture"   # 1/2 -> can't verify
    assert ae.classify_synth_file_embody(20000, 900.0, 1.0, 1, True) == "emitted"      # the word back
    assert ae.classify_synth_file_embody(20000, 900.0, 0.0, 1, True) == "no_capture"   # missed -> can't verify
    # 3-4 words: tolerate exactly ONE STT miss.
    assert ae.classify_synth_file_embody(30000, 900.0, 0.667, 3, True) == "emitted"    # 2/3
    assert ae.classify_synth_file_embody(30000, 900.0, 0.333, 3, True) == "mismatch"   # 1/3 -> garbled
    assert ae.classify_synth_file_embody(40000, 900.0, 0.75, 4, True) == "emitted"     # 3/4
    assert ae.classify_synth_file_embody(40000, 900.0, 0.5, 4, True) == "mismatch"     # 2/4 -> garbled
    # 5+ words: clean-channel floor (SYNTH_FILE_INTEL_MIN = 0.8). With timing UNKNOWN
    # (expected_dur=0 here) a sub-floor recall stays mismatch (truncation can't be ruled out);
    # the duration-CONFIRMED degrade to no_capture is covered in the next two tests.
    assert ae.classify_synth_file_embody(60000, 900.0, 0.8, 5, True) == "emitted"
    assert ae.classify_synth_file_embody(60000, 900.0, 0.6, 5, True) == "mismatch"  # timing unknown


def test_synth_file_5plus_degraded_is_no_capture_not_mismatch():
    # 5+ words, FULL-LENGTH clip (duration CONFIRMS non-truncation) but recall below
    # INTEL_MIN(0.8): low recall on a long line is STT DEGRADATION (tiny-whisper accumulates
    # errors over many words), NOT a synth content fault. Degrade to no_capture (honest
    # "couldn't verify"), NOT mismatch (false "words came out wrong") — the long-line twin of
    # MED-2. Real aio2 cross-engine datum: 13-word line, synth 4.93s ~= expected 5.25s (FULL),
    # piper+whisper.cpp overlap 0.615 (#2335).
    full = dict(synth_dur_s=4.93, expected_dur_s=5.25)  # timing confirms full-length
    assert ae.classify_synth_file_embody(200000, 900.0, 0.615, 13, True, **full) == "no_capture"
    assert ae.classify_synth_file_embody(200000, 900.0, 0.5, 13, True, **full) == "no_capture"   # at floor
    assert ae.classify_synth_file_embody(200000, 900.0, 0.49, 13, True, **full) == "mismatch"    # collapsed
    assert ae.classify_synth_file_embody(200000, 900.0, 0.8, 13, True, **full) == "emitted"      # at intel_min


def test_synth_file_5plus_degrade_is_gated_on_duration_confirmation():
    # The no_capture degrade fires ONLY when timing confirms full-length. Otherwise mismatch —
    # conservative: never relabel a possibly-truncated clip as a benign no_capture.
    mid = 0.615  # in [degraded_floor, intel_min)
    # timing UNKNOWN (expected_dur=0) -> can't rule out truncation -> mismatch
    assert ae.classify_synth_file_embody(200000, 900.0, mid, 13, True) == "mismatch"
    assert ae.classify_synth_file_embody(200000, 900.0, mid, 13, True,
                                         synth_dur_s=4.93, expected_dur_s=0.0) == "mismatch"
    # TRUNCATED (synth_dur < 0.5*expected) -> duration guard returns mismatch BEFORE the
    # degrade path is reached -> never no_capture:
    assert ae.classify_synth_file_embody(200000, 900.0, mid, 13, True,
                                         synth_dur_s=1.0, expected_dur_s=5.25) == "mismatch"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
