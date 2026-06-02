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
import argparse, array, json, math, os, re, subprocess, sys, tempfile, time, wave

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


# Speech-mode thresholds. A single-frequency Goertzel peak is the WRONG
# discriminator for broadband speech (no isolated tone), so speech is verified by
# ENERGY-ENVELOPE CROSS-CORRELATION: the bus capture must carry a signal whose
# loudness-over-time SHAPE matches the WAV we played (concurrent background audio
# decorrelates, so this stays robust on a busy bus — the speech analog of the
# tone path's spectral-peak test), AND the voiced span must cover a real fraction
# of the played duration. Passed as args so the truth table is pinned in tests.
SPEECH_RMS_FLOOR = 5.0     # below this the bus is silent (no audio at all)
ENV_CORR_MIN = 0.45        # min normalized envelope correlation (shape match)
SPEECH_DUR_FRAC = 0.40     # voiced span must be >= this fraction of played duration


def classify_speech_embody(capture_rms, env_corr, voiced_secs, expected_secs, frames,
                           rms_floor=SPEECH_RMS_FLOOR, env_corr_min=ENV_CORR_MIN,
                           dur_frac=SPEECH_DUR_FRAC):
    """Pure: given bus-readback metrics for SPEECH, decide the embodiment outcome.

    `env_corr` = peak normalized cross-correlation between the played WAV's energy
    envelope and the captured bus envelope; `voiced_secs` = total span of the
    capture above the voiced floor; `expected_secs` = the played WAV's duration.

    emitted iff the bus carried audio (rms>=floor) whose envelope shape matches
    what we played (env_corr>=min) over a real fraction of its duration.
    Returns one of: emitted | silent | mismatch | no_capture.
    """
    if frames <= 0:
        return "no_capture"
    if capture_rms < rms_floor:
        return "silent"            # nothing on the bus at all
    enough_span = expected_secs <= 0 or voiced_secs >= dur_frac * expected_secs
    if env_corr >= env_corr_min and enough_span:
        return "emitted"           # envelope shape matches what we played -> on the bus
    return "mismatch"              # bus has audio, but not the speech we played


# --- intelligibility (STT round-trip) -------------------------------------------
# The envelope correlation (above) proves the bus carried OUR signal's shape; this
# proves the WORDS survived — transcribe the bus capture and check the requested
# words come back. A STRONGER, layered falsifier (not a replacement): the envelope
# status still gates the outcome; intelligibility is recorded as extra evidence.
# Honest boundary unchanged: this verifies intelligibility AT THE BUS, not at the
# physical transducer (a human ear is still the only judge of the last mile).

INTELLIGIBLE_MIN = 0.6   # fraction of requested words that must come back from the bus

_WORD_RE = re.compile(r"[a-z0-9']+")


def _norm_words(text):
    return _WORD_RE.findall((text or "").lower())


def word_overlap(reference, hypothesis):
    """Recall of reference words present in the hypothesis — order-, case- and
    punctuation-insensitive. Returns (ratio, n_reference_words). 1.0 = every
    requested word was transcribed off the bus."""
    ref = _norm_words(reference)
    if not ref:
        return 0.0, 0
    hyp = set(_norm_words(hypothesis))
    hit = sum(1 for w in ref if w in hyp)
    return hit / len(ref), len(ref)


def classify_intelligibility(overlap_ratio, n_ref_words, threshold=INTELLIGIBLE_MIN):
    """Pure: did STT recover enough of the requested words from the bus capture?
    Returns intelligible | garbled | no_words."""
    if n_ref_words <= 0:
        return "no_words"
    return "intelligible" if overlap_ratio >= threshold else "garbled"


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


# --- speech-mode analysis (energy envelope, pure over samples) ------------------

def energy_envelope(samples, sr, frame_ms=50):
    """Per-frame RMS loudness over time (frames of `frame_ms`). Time-domain, so a
    24 kHz played WAV and a 48 kHz bus capture yield directly comparable envelopes."""
    n = max(1, int(sr * frame_ms / 1000))
    env = []
    for i in range(0, len(samples), n):
        frame = samples[i:i + n]
        if frame:
            env.append(math.sqrt(sum(x * x for x in frame) / len(frame)))
    return env


def _zscore(xs):
    n = len(xs)
    if n == 0:
        return []
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / n
    sd = math.sqrt(var)
    if sd < 1e-9:
        return [0.0] * n            # flat envelope carries no shape to correlate
    return [(x - mean) / sd for x in xs]


def envelope_xcorr(played_env, captured_env):
    """Peak normalized cross-correlation of two energy envelopes over all lags
    where `played` fits inside `captured`. Returns a value in [-1, 1]: ~1 means the
    bus capture contains a loudness-over-time shape matching what we played.
    Amplitude-invariant (z-scored), so it measures SHAPE, not level."""
    p = _zscore(played_env)
    if not p:
        return 0.0
    if len(captured_env) < len(p):
        # capture shorter than playback: compare the overlap head-to-head
        c = _zscore(captured_env)
        m = min(len(p), len(c))
        if m == 0:
            return 0.0
        return sum(p[i] * c[i] for i in range(m)) / m
    best = -1.0
    max_lag = len(captured_env) - len(p)
    for lag in range(0, max_lag + 1):
        window = _zscore(captured_env[lag:lag + len(p)])
        if not window:
            continue
        corr = sum(p[i] * window[i] for i in range(len(p))) / len(p)
        if corr > best:
            best = corr
    return best


def voiced_seconds(samples, sr, frame_ms=50, floor=SPEECH_RMS_FLOOR):
    """Total time (s) the signal spends above the voiced floor — the span of real
    energy on the bus, guarding against a brief blip that happens to correlate."""
    env = energy_envelope(samples, sr, frame_ms)
    voiced_frames = sum(1 for e in env if e >= floor)
    return voiced_frames * (frame_ms / 1000.0)


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


def resolve_synth_bin(arg):
    """Locate the ab-tts-synth CLI: explicit arg → env → None (caller errors)."""
    cand = arg or os.environ.get("AB_TTS_SYNTH_BIN", "").strip()
    return cand or None


def synth_speech(text, voice, speed, synth_bin):
    """Invoke ab-tts-synth (Rust/Kokoro) to render `text` → WAV. Returns
    (wav_path, info_dict) or (None, error_dict)."""
    if not synth_bin or not os.path.exists(synth_bin):
        return None, {"detail": f"ab-tts-synth not found ({synth_bin!r}); set --synth-bin or AB_TTS_SYNTH_BIN"}
    wav = os.path.join(tempfile.gettempdir(), "ab_voice_speech.wav")
    proc = subprocess.run(
        [synth_bin, "--text", text, "--voice", voice, "--speed", str(speed), "--out", wav],
        capture_output=True, text=True)
    try:
        info = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except Exception:  # noqa
        info = {}
    if proc.returncode != 0 or not info.get("ok") or not os.path.exists(wav):
        return None, {"detail": f"synth failed rc={proc.returncode}: {info.get('error') or proc.stderr[:300]}"}
    return wav, info


def resolve_stt(stt_bin_arg, model_arg):
    """Locate whisper.cpp CLI + ggml model: explicit args → env → None."""
    b = stt_bin_arg or os.environ.get("AB_TTS_STT_BIN", "").strip()
    m = model_arg or os.environ.get("AB_TTS_STT_MODEL", "").strip()
    return (b or None), (m or None)


def transcribe(wav_path, stt_bin, model):
    """whisper.cpp transcription of `wav_path` → (text, None) or (None, error).
    Resamples to 16 kHz mono first (whisper.cpp's required input rate)."""
    if not stt_bin or not os.path.exists(stt_bin):
        return None, f"stt bin not found ({stt_bin!r}); set --stt-bin or AB_TTS_STT_BIN"
    if not model or not os.path.exists(model):
        return None, f"stt model not found ({model!r}); set --stt-model or AB_TTS_STT_MODEL"
    wav16 = os.path.join(tempfile.gettempdir(), "ab_voice_capture_16k.wav")
    _sh(f"ffmpeg -y -i {wav_path} -ac 1 -ar 16000 {wav16} 2>&1")
    if not os.path.exists(wav16):
        return None, "resample to 16k failed"
    p = subprocess.run([stt_bin, "-m", model, "-f", wav16, "-l", "en", "-nt", "-np"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        return None, f"whisper rc={p.returncode}: {p.stderr[:200]}"
    return p.stdout.strip(), None


def run_speech(text, voice, speed, sink_arg, capture_channel, synth_bin,
               check_intelligibility=False, stt_bin=None, stt_model=None):
    """Speech-mode embodiment: synthesize `text` → play to the sink while capturing
    the bus → verify by energy-envelope correlation + voiced span (NOT a tone peak).
    Optionally also transcribe the bus capture (whisper.cpp) and check the requested
    words came back — a stronger, layered intelligibility falsifier."""
    sink, src, verified_to, not_verified = resolve_targets(sink_arg, capture_channel)
    out = {
        "mode": "speech", "text": text, "voice": voice, "speed": speed, "sink": sink,
        "capture_channel": capture_channel, "capture_source": src,
        "verified_to": verified_to, "not_verified": not_verified,
    }

    wav, info = synth_speech(text, voice, speed, synth_bin)
    if wav is None:
        out.update(status="error", verify_status="error", **info)
        return out
    played = _read_wav_mono_s16(wav)
    if played is None or not len(played["samples"]):
        out.update(status="error", verify_status="error", detail="synthesized WAV unreadable/empty")
        return out
    played_sr = played["sr"] or 24000
    played_dur = played["frames"] / played_sr
    out["played_dur_s"] = round(played_dur, 3)

    cap_path = os.path.join(tempfile.gettempdir(), "ab_voice_capture.wav")
    secs = played_dur + 1.2  # lead-in (0.4) + tail margin
    try:
        cap = capture_async(src, secs, cap_path)
        time.sleep(0.4)  # let capture spin up before playback
        _sh(f"paplay --device={sink} {wav}")  # blocks ~played_dur, to the target sink
        cap.wait()
    except Exception as e:  # noqa
        out.update(status="error", verify_status="error", detail=f"orchestration: {e}")
        return out

    parsed = _read_wav_mono_s16(cap_path)
    if parsed is None:
        out.update(status="no_capture", verify_status="no_capture", detail="no capture file")
        return out
    cap_samples, cap_sr = parsed["samples"], parsed["sr"] or 48000
    capture_rms = round(rms_of(cap_samples), 2)
    played_env = energy_envelope(played["samples"], played_sr)
    captured_env = energy_envelope(cap_samples, cap_sr)
    env_corr = round(envelope_xcorr(played_env, captured_env), 3)
    voiced = round(voiced_seconds(cap_samples, cap_sr), 2)
    status = classify_speech_embody(capture_rms, env_corr, voiced, played_dur, parsed["frames"])
    out.update(
        status=status, verify_status=verify_status_for(status),
        capture_rms=capture_rms, env_corr=env_corr, voiced_secs=voiced,
        frames=parsed["frames"], sr=cap_sr,
        detail=f"env_corr={env_corr} voiced_secs={voiced}/{round(played_dur,2)} capture_rms={capture_rms} frames={parsed['frames']}",
    )

    # Layered intelligibility falsifier (STT round-trip): transcribe the BUS
    # CAPTURE (not the synth) and check the requested words survived the emit→bus
    # path. Recorded as extra evidence; does NOT override the envelope-based status.
    if check_intelligibility:
        sb, sm = resolve_stt(stt_bin, stt_model)
        transcript, stt_err = transcribe(cap_path, sb, sm)
        if transcript is not None:
            ratio, nref = word_overlap(text, transcript)
            out["stt_transcript"] = transcript
            out["word_overlap"] = round(ratio, 3)
            out["intelligibility"] = classify_intelligibility(ratio, nref)
            out["detail"] += f" | stt: '{transcript[:80]}' overlap={round(ratio,3)} -> {out['intelligibility']}"
        else:
            out["intelligibility"] = "unavailable"
            out["stt_detail"] = stt_err
    return out


def main():
    ap = argparse.ArgumentParser(description="present_voice audio-embodiment falsifier")
    ap.add_argument("--mode", choices=["tone", "speech"], default="tone",
                    help="tone = fixed-freq Goertzel peak (default); speech = TTS envelope-correlation falsifier")
    ap.add_argument("--freq", type=float, default=440.0)
    ap.add_argument("--duration-ms", type=int, default=1500)
    ap.add_argument("--amplitude", type=float, default=0.25)
    ap.add_argument("--sink", default=None)
    ap.add_argument("--capture-channel", choices=["sink_monitor", "mic"], default="sink_monitor")
    ap.add_argument("--no-emit", action="store_true", help="capture-only (silence/external check)")
    # speech-mode args
    ap.add_argument("--text", default=None, help="speech mode: text to synthesize + speak")
    ap.add_argument("--voice", default="af_sarah", help="speech mode: TTS voice name")
    ap.add_argument("--speed", type=float, default=1.0, help="speech mode: speech speed (0.5-2.0)")
    ap.add_argument("--synth-bin", default=None, help="speech mode: path to ab-tts-synth (or env AB_TTS_SYNTH_BIN)")
    ap.add_argument("--check-intelligibility", action="store_true",
                    help="speech mode: also transcribe the bus capture (whisper.cpp) and check words came back")
    ap.add_argument("--stt-bin", default=None, help="whisper.cpp CLI path (or env AB_TTS_STT_BIN)")
    ap.add_argument("--stt-model", default=None, help="whisper ggml model path (or env AB_TTS_STT_MODEL)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.mode == "speech":
        if not a.text or not a.text.strip():
            res = {"mode": "speech", "status": "error", "verify_status": "error",
                   "detail": "speech mode requires --text"}
        else:
            res = run_speech(a.text, a.voice, max(0.5, min(a.speed, 2.0)), a.sink,
                             a.capture_channel, resolve_synth_bin(a.synth_bin),
                             check_intelligibility=a.check_intelligibility,
                             stt_bin=a.stt_bin, stt_model=a.stt_model)
        if a.json:
            print(json.dumps(res))
        else:
            for k, v in res.items():
                print(f"{k}: {v}")
        return
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
