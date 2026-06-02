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
