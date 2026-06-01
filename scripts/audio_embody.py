#!/usr/bin/env python3
"""Audio-domain embodiment falsifier for the output-expression lane (present_voice).

Emit a KNOWN signal (a defined-frequency tone) to an output sink, then read it
back off the SYSTEM BUS (the PipeWire sink `.monitor` loopback) and prove the
requested signal actually reached the bus — via RMS + a single-bin Goertzel at
the target frequency. The decision (`classify_audio_embody`) is PURE so the
truth table is a unit test, not a live assertion (mirrors present.rs
classify_render / classify_embody).

HONEST BOUNDARY (the unverifiable last mile): the `sink_monitor` channel verifies
the signal reached the OUTPUT BUS, NOT the physical transducer (headphone/speaker
driver) — only a human (or, for speakers, the `mic` channel) can confirm that.

Pluggable capture channel:
  - sink_monitor (default): the `.monitor` of the sink we emit to (bus loopback).
  - mic: the default input source (Phase 2; for speakers, captures the acoustic
    output a mic hears — does not capture headphone-private audio).

This is the Python half (analysis + decision) wrapped by the thin Rust MCP tool
`present_voice`, matching the desktop_verify / vision_grounding_ocr pattern.
"""
import argparse, array, json, math, os, subprocess, sys, tempfile, time, wave

# --- pure decision (unit-tested; no audio needed) -------------------------------

# Tunable thresholds. The discriminator is a SPECTRAL PEAK at the target bin, NOT
# a fraction of total RMS: a pure tone concentrates all its energy in the F bin,
# so it stands sharply above the LOCAL spectral floor (nearby off-target bins),
# whereas broadband background audio (music) is ~flat across F and its neighbors.
# This makes the falsifier robust to a busy bus (proven necessary by live dogfood:
# a silence sample read RMS~10000 from concurrent audio, swamping a total-energy
# ratio). Passed as args so the truth table is pinned in tests with synthetic
# (peak, floor) values.
RMS_FLOOR = 5.0        # below this the bus is silent (no audio at all)
GOERTZEL_MIN = 5.0     # absolute floor: target bin must carry at least this energy
PEAK_RATIO = 2.5       # target bin must exceed this multiple of the local spectral floor


def classify_audio_embody(rms_val, goertzel_f, goertzel_floor, frames,
                          rms_floor=RMS_FLOOR, goertzel_min=GOERTZEL_MIN,
                          peak_ratio=PEAK_RATIO):
    """Pure: given bus-readback metrics, decide the audio embodiment outcome.

    `goertzel_f` = energy at the target frequency; `goertzel_floor` = the local
    spectral floor (median of nearby off-target bins). Our pure tone is detected
    iff F is a sharp PEAK above that floor — robust to concurrent background audio.

    Returns one of: emitted | silent | mismatch | no_capture.
    (error / skipped are produced by the orchestration, not this fn.)
    """
    if frames <= 0:
        return "no_capture"
    if rms_val < rms_floor:
        return "silent"            # nothing on the bus at all
    if goertzel_f >= goertzel_min and goertzel_f >= peak_ratio * goertzel_floor:
        return "emitted"           # target frequency is a sharp peak -> our tone reached the bus
    return "mismatch"              # bus has audio, but our tone is not a distinct peak


def verify_status_for(status):
    """Map the audio status onto the lane's gate-facing verify_status vocabulary.
    Only `emitted` -> rendered_ok passes outcome_gate; the rest reject honestly
    with their own reason (mirrors EmbodyStatus::implied_verify_status)."""
    return {
        "emitted": "rendered_ok",
        "silent": "silent",
        "mismatch": "mismatch",
        "no_capture": "no_capture",
        "error": "error",
        "skipped": "skipped",
    }.get(status, "error")


# --- audio analysis (pure over samples) -----------------------------------------

def _read_wav_mono_s16(path):
    if not os.path.exists(path):
        return None
    w = wave.open(path, "rb")
    n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(n)
    w.close()
    if sw != 2 or n == 0:
        return {"frames": n, "sr": sr, "samples": array.array("h")}
    a = array.array("h")
    a.frombytes(raw)
    if ch > 1:
        a = a[0::ch]
    return {"frames": len(a), "sr": sr, "samples": a}


def rms_of(samples):
    if not len(samples):
        return 0.0
    return math.sqrt(sum(x * x for x in samples) / len(samples))


def goertzel(samples, sr, freq):
    """Single-bin DFT magnitude (per-sample normalized) at `freq`."""
    N = len(samples)
    if N == 0:
        return 0.0
    k = int(0.5 + N * freq / sr)
    w0 = 2 * math.pi * k / N
    coeff = 2 * math.cos(w0)
    s1 = s2 = 0.0
    for x in samples:
        s = x + coeff * s1 - s2
        s2 = s1
        s1 = s
    power = s2 * s2 + s1 * s1 - coeff * s1 * s2
    return math.sqrt(abs(power)) / N


# Off-target reference offsets (fractions of the target freq) used to estimate the
# LOCAL spectral floor. Chosen close-ish but not harmonically related to the target
# so a pure tone never leaks into them, while broadband background sits at ~the same
# level as it does at the target bin.
_FLOOR_OFFSETS = (0.77, 0.91, 1.09, 1.31)


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def spectral_floor(samples, sr, freq):
    """Median Goertzel magnitude at nearby off-target bins — the local background
    level our pure tone must peak above. Median (not max) so one loud neighbor
    doesn't mask a real tone."""
    return _median([goertzel(samples, sr, freq * f) for f in _FLOOR_OFFSETS])


# --- orchestration (emit + capture) ---------------------------------------------

def _sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def resolve_targets(sink_arg, capture_channel):
    sink = sink_arg or _sh("pactl get-default-sink").stdout.strip()
    if capture_channel == "mic":
        src = _sh("pactl get-default-source").stdout.strip()
        verified_to = "acoustic capture (mic input)"
        not_verified = "headphone-private audio (mic cannot hear in-ear output)"
    else:  # sink_monitor
        src = sink + ".monitor"
        verified_to = "output bus (PipeWire sink monitor / loopback)"
        not_verified = "physical transducer (headphone/speaker driver output)"
    return sink, src, verified_to, not_verified


def gen_tone(freq, dur_ms, amp):
    path = os.path.join(tempfile.gettempdir(), f"ab_voice_tone_{int(freq)}_{dur_ms}.wav")
    dur_s = dur_ms / 1000.0
    r = _sh(f"ffmpeg -y -f lavfi -i sine=frequency={freq}:duration={dur_s} "
            f"-af volume={amp} -ac 1 -ar 48000 {path} 2>&1")
    return path if os.path.exists(path) else None


def capture_async(source, secs, path):
    return subprocess.Popen(
        f"ffmpeg -y -f pulse -i {source} -t {secs} -ac 1 -ar 48000 -sample_fmt s16 {path}",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run(freq, dur_ms, amp, sink_arg, capture_channel, emit):
    sink, src, verified_to, not_verified = resolve_targets(sink_arg, capture_channel)
    out = {
        "freq": freq, "duration_ms": dur_ms, "sink": sink,
        "capture_channel": capture_channel, "capture_source": src,
        "verified_to": verified_to, "not_verified": not_verified,
    }
    cap_path = os.path.join(tempfile.gettempdir(), "ab_voice_capture.wav")
    secs = dur_ms / 1000.0 + 1.0
    try:
        cap = capture_async(src, secs, cap_path)
        if emit:
            time.sleep(0.4)  # let capture spin up before emitting
            tone = gen_tone(freq, dur_ms, amp)
            if not tone:
                cap.wait()
                out.update(status="error", verify_status="error", detail="tone generation failed")
                return out
            _sh(f"paplay --device={sink} {tone}")  # blocks ~dur_ms, to the target sink
        cap.wait()
    except Exception as e:  # noqa
        out.update(status="error", verify_status="error", detail=f"orchestration: {e}")
        return out

    parsed = _read_wav_mono_s16(cap_path)
    if parsed is None:
        out.update(status="no_capture", verify_status="no_capture", detail="no capture file")
        return out
    samples, sr = parsed["samples"], parsed["sr"] or 48000
    rv = round(rms_of(samples), 2)
    gv = round(goertzel(samples, sr, freq), 2)
    floor = round(spectral_floor(samples, sr, freq), 2)
    status = classify_audio_embody(rv, gv, floor, parsed["frames"])
    ratio = round(gv / floor, 2) if floor > 0 else None
    out.update(
        status=status, verify_status=verify_status_for(status),
        rms=rv, goertzel=gv, goertzel_floor=floor, peak_ratio=ratio,
        frames=parsed["frames"], sr=sr,
        detail=f"rms={rv} goertzel@{int(freq)}={gv} floor={floor} peak_ratio={ratio} frames={parsed['frames']}",
    )
    return out


def main():
    ap = argparse.ArgumentParser(description="present_voice audio-embodiment falsifier")
    ap.add_argument("--freq", type=float, default=440.0)
    ap.add_argument("--duration-ms", type=int, default=1500)
    ap.add_argument("--amplitude", type=float, default=0.25)
    ap.add_argument("--sink", default=None)
    ap.add_argument("--capture-channel", choices=["sink_monitor", "mic"], default="sink_monitor")
    ap.add_argument("--no-emit", action="store_true", help="capture-only (silence/external check)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    dur = max(100, min(a.duration_ms, 8000))
    amp = max(0.0, min(a.amplitude, 1.0))
    res = run(a.freq, dur, amp, a.sink, a.capture_channel, emit=not a.no_emit)
    if a.json:
        print(json.dumps(res))
    else:
        for k, v in res.items():
            print(f"{k}: {v}")
    # exit 0 always: status is data, not process success (mirrors read-only verify tools)


if __name__ == "__main__":
    main()
