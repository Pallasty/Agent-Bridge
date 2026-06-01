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
