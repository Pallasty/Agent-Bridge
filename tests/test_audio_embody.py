#!/usr/bin/env python3
"""Truth table for the PURE audio-embodiment decision (spectral-peak discriminator)
+ Goertzel sanity. Runs under pytest, or standalone:
    python3 tests/test_audio_embody.py
"""
import array
import math
import os
import sys

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
