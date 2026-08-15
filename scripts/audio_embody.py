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
import argparse, array, fcntl, hashlib, json, math, os, re, socket, subprocess, sys, tempfile, time, unicodedata, wave

# Platform routing: macOS has NO PipeWire sink `.monitor` loopback, so present_voice
# verifies the SYNTHESIZED FILE (via STT) instead of a bus readback — a different,
# honestly-narrower channel (verified_to = synth file, NOT the output bus). The Linux
# bus path is unchanged; only `darwin` (or an explicit `synth_file` channel) reroutes.
# See run_speech_synth_file / classify_synth_file_embody. (RFC #2275, thread 92.)
_IS_MACOS = sys.platform == "darwin"

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


def emit_claim_fields(play_ok):
    """Pure honesty invariant of the FAST-EMIT tier (`--mode emit`).

    Emit mode plays synthesized speech WITHOUT reading the bus back, so it makes
    NO verification claim: `verify_status` is NEVER the gate-passing `rendered_ok`
    and `verified_to` is ALWAYS None. This is the low-truth-claim companion-chatter
    path; the verified tier is `--mode speech` (bus envelope/STT falsifier).
    Returns (status, verify_status, verified_to).
    """
    if play_ok:
        return "played_unverified", "unverified", None
    return "error", "error", None


def honest_attestation(status, channel_verified_to, channel_not_verified):
    """Pure: what a run may CLAIM it verified, given its outcome. The channel target
    (e.g. the output bus) counts as `verified_to` ONLY when that channel actually
    confirmed the signal (status=='emitted'); on every other status the run proved
    nothing there, so the channel target moves into `not_verified` and verified_to is
    None. Prevents a failed/mismatched run from reporting a verified_to it never
    earned (adversarial findings INV-RECEIPT-NOFAB / INV-CONTRACT).
    Returns (verified_to, not_verified)."""
    if status == "emitted":
        return channel_verified_to, channel_not_verified
    return None, f"{channel_verified_to} — NOT confirmed on this run; plus {channel_not_verified}"


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

# synth_file channel (macOS / no-loopback) gates — TIGHTER than the noisy-bus floor.
# The readback is the CLEAN synthesized file (no concurrent-audio masking), so synth+STT
# should recover ~all words; the 0.6 bus floor over-claims here, and set-recall
# word_overlap INFLATES on REPEATED reference words. A DURATION guard (actual synth_dur
# vs expected = word_count/wpm) is the truncation falsifier the word gate alone misses.
# (review #2300 MED-1, thread 92; defaults conservative pending macOS live calibration.)
SYNTH_FILE_INTEL_MIN = 0.8   # word-recall floor for the clean synth-file channel
SYNTH_FILE_DUR_FRAC = 0.5    # synth_dur must be >= this * expected(word_count/wpm) or it's truncated
SYNTH_FILE_DEGRADED_FLOOR = 0.5  # 5+ words: a FULL-LENGTH clip with recall in [this, INTEL_MIN)
                                 # is treated as STT DEGRADATION -> no_capture (honest "couldn't
                                 # verify"), NOT a content fault -> mismatch. Below it recall has
                                 # collapsed -> mismatch. (review #2300 follow-up / #2335 design Q;
                                 # the long-line twin of MED-2 degraded!=fault; pending mac calibration.)

_WORD_RE = re.compile(r"[a-z0-9']+|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _norm_words(text):
    return _WORD_RE.findall((text or "").lower())


def _contains_cjk(text):
    return bool(_CJK_RE.search(text or ""))


def _expected_speech_duration(text, wpm):
    """Estimate speech duration without treating a whole CJK clause as one word.

    Preserve the historical English words/wpm calculation exactly. CJK characters
    are counted separately at a conservative 1.45 characters per Latin word.
    This estimate is only a truncation falsifier; it never proves intelligibility.
    """
    if wpm <= 0:
        return 0.0
    latin_words = re.findall(r"[a-z0-9']+", (text or "").lower())
    cjk_chars = _CJK_RE.findall(text or "")
    return (len(latin_words) / wpm * 60.0
            + len(cjk_chars) / (wpm * 1.45) * 60.0)


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


def classify_synth_file_embody(frames, rms_val, overlap_ratio, n_ref_words, stt_available,
                               synth_dur_s=0.0, expected_dur_s=0.0,
                               rms_floor=SPEECH_RMS_FLOOR, intel_min=SYNTH_FILE_INTEL_MIN,
                               dur_frac=SYNTH_FILE_DUR_FRAC,
                               degraded_floor=SYNTH_FILE_DEGRADED_FLOOR):
    """Pure: the `synth_file` channel (macOS / any host without a bus `.monitor`).

    The readback object is the SYNTHESIZED wav ITSELF, so an envelope-vs-itself
    correlation is ~1.0 by construction and proves nothing — therefore the GATE is two
    falsifiers on the synth: (1) the STT word_overlap (did the requested WORDS survive?)
    against the CLEAN-channel floor SYNTH_FILE_INTEL_MIN, and (2) a DURATION guard
    (synth_dur vs expected = word_count/wpm) — set-recall word_overlap INFLATES on
    repeated reference words, so a truncated-but-loud clip can pass the word gate while
    most spoken words were dropped; a clip far shorter than the text implies is truncated
    regardless. (This hardens the macOS-truncation defense — review #2300 MED-1.) Mapping:
      frames<=0                       -> no_capture  (nothing synthesized)
      rms<floor                       -> silent      (synth produced a silent file)
      STT unavailable / no ref words  -> no_capture  (cannot verify words -> NEVER claim
                                        emitted; degraded capability, honest — never
                                        `mismatch`, which would falsely assert words wrong)
      synth_dur < frac*expected       -> mismatch    (TRUNCATED — too short for the text)
      words survived (length-aware)   -> emitted     (5+ words: >=intel_min; 3-4 words:
                                        tolerate one STT miss; 1-2 words: all words back —
                                        whisper-tiny is NOISY on short clips and the
                                        duration guard already caught truncation)
      1-2 words, not all recovered    -> no_capture  (STT too unreliable to assert anything)
      5+ words, full-length,           -> no_capture  (STT DEGRADED on a long line, NOT a content
        recall in [degraded_floor,                     fault — the long-line twin of the MED-2
        intel_min)                                     degraded!=fault rule; degrade honestly
                                                       instead of falsely asserting words wrong)
      else (recall collapsed below     -> mismatch    (full-length but words did not survive, or
        degraded_floor, or 3-4 words                   3-4 words missed >1, or timing unknown so
        missed >1, or timing unknown)                  truncation cannot be ruled out)
    expected_dur_s<=0 disables the duration guard (unknown timing). Returns: emitted |
    silent | mismatch | no_capture — the same vocabulary the bus channels use, so
    verify_status_for / honest_attestation handle it unchanged."""
    if frames <= 0:
        return "no_capture"
    if rms_val < rms_floor:
        return "silent"
    if not stt_available or n_ref_words <= 0:
        return "no_capture"
    if expected_dur_s > 0 and synth_dur_s < dur_frac * expected_dur_s:
        return "mismatch"            # TRUNCATED: clip too short for the requested text
    # length-aware word gate. whisper-tiny is NOISY on SHORT clips (the companion voice
    # templates are 1-3 words), so a flat high floor would falsely reject good short
    # utterances. The DURATION guard above already catches truncation independent of STT,
    # so the word gate can tolerate STT noise on short clips without letting truncation in:
    hits = round(overlap_ratio * n_ref_words)
    if n_ref_words <= 2:
        # 1-2 words: STT too unreliable to assert garbling. all words back -> emitted;
        # else CANNOT verify -> no_capture (honest — never a false 'mismatch'/garbled claim).
        return "emitted" if hits >= n_ref_words else "no_capture"
    if n_ref_words <= 4:
        # 3-4 words: tolerate ONE STT miss (>= n-1 words back) -> emitted; else mismatch.
        return "emitted" if hits >= n_ref_words - 1 else "mismatch"
    # 5+ words: STT noise averages out -> require the clean-channel recall floor.
    if overlap_ratio >= intel_min:
        return "emitted"
    # Below the floor. The duration guard above already rejected truncation WHEN TIMING IS
    # KNOWN, so low recall on a confirmed full-length long line is far more likely STT
    # DEGRADATION (tiny-whisper accumulates errors across many words) than a synth content
    # fault. Asserting `mismatch` ("words came out wrong") there is the long-line twin of the
    # MED-2 degraded!=fault error. Degrade to `no_capture` (honest "couldn't verify") only when
    # (a) timing CONFIRMS a full-length render AND (b) recall is merely degraded, not collapsed.
    # Otherwise `mismatch`: recall collapsed below degraded_floor (too low even for STT noise),
    # or timing is unknown (cannot rule out truncation). (#2300 follow-up / #2335 design Q.)
    duration_confirmed = expected_dur_s > 0 and synth_dur_s >= dur_frac * expected_dur_s
    if duration_confirmed and overlap_ratio >= degraded_floor:
        return "no_capture"
    return "mismatch"


# --- voice-policy v0 decision (LCC-V1, the companion voice adapter) --------------
# Contract: forum #98 #2207 (voice_policy v0) + #2215 (wiring/receipt). The
# companion is silent by default and only speaks on a few gated lifecycle modes;
# a `verified` line is a TRUTH-CLAIM and must point at real verification evidence
# (never inferred from a mode flip alone); milestone (verified) lines route to the
# VERIFIED tier (`--mode speech`, bus-falsified) while ambient/status lines route
# to the FAST tier (`--mode emit`, unverified). This is a PURE decision so the
# whole policy is a truth table, not a live assertion.

VOICE_ALLOWED_MODES = ("failed", "verified", "waiting_for_user", "handoff")
VOICE_COOLDOWN_SECS = 300          # default per #2207; same (agent,mode,evidence) not repeated
VOICE_LINE_MAX_CHARS = 240         # v0 noise budget — companion lines stay short
VOICE_VERIFIED_TIER_MODES = ("verified",)   # modes that route to the bus-VERIFIED tier
# v0 text source is a template ENUM, not arbitrary LLM text (#2207). A raw
# `voice_line` is still accepted but length/mode/evidence/cooldown gated.
VOICE_LINE_TEMPLATES = {
    "verified.generic": "Verified.",
    "failed.generic": "A check failed.",
    "waiting_for_user.generic": "Waiting for you.",
    "handoff.generic": "Handing off.",
}


# Codepoint categories that carry NO standalone visible glyph, so an id made only
# of them is not real proof: format (zero-width U+200B/200C/200D/2060/FEFF…),
# control, the three space separators, unassigned, the no-base mark categories
# (Mn nonspacing / Me enclosing — bare combining accents, variation selectors), and
# surrogates (Cs — also unencodable). A real id needs >=1 char OUTSIDE this set.
_INVISIBLE_CATEGORIES = ("Cf", "Cc", "Zs", "Zl", "Zp", "Cn", "Mn", "Me", "Cs")
# Default_Ignorable_Code_Points that fall in an otherwise-VISIBLE general category
# (so the category test alone misses them) yet render as nothing: the Hangul fillers
# (category Lo). U+3164 is the canonical web "invisible character". Every OTHER
# Default_Ignorable codepoint already lives in a rejected category above.
_INVISIBLE_CODEPOINTS = frozenset("\u115f\u1160\u3164\uffa0")  # Hangul fillers (Lo, Default_Ignorable)


def _is_visible(ch):
    """A char carries a real visible glyph iff its category is not in the no-glyph
    set AND it is not a known zero-glyph Default_Ignorable codepoint."""
    return unicodedata.category(ch) not in _INVISIBLE_CATEGORIES and ch not in _INVISIBLE_CODEPOINTS


def _meaningful_id(e):
    """Return the stripped string id iff it carries >=1 real VISIBLE character, else
    None. Rejecting non-strings is load-bearing (str(None)=='None' would be phantom
    evidence); rejecting all-invisible strings is too — str.strip() removes only
    Unicode WHITESPACE, so zero-width format chars (U+200B…), bare combining marks,
    and zero-glyph Hangul fillers (U+3164…) would otherwise pose as evidence and let
    a 'verified' line speak with no proof (adversarial INV-GROUND, rounds 2-4)."""
    if not isinstance(e, str):
        return None
    s = e.strip()
    if not s or not any(_is_visible(ch) for ch in s):
        return None
    return s


def _clean_evidence(evidence_ids):
    """Keep only real, non-empty, VISIBLE string evidence ids (see _meaningful_id)."""
    return [m for m in (_meaningful_id(e) for e in (evidence_ids or [])) if m]


def voice_evidence_hash(evidence_ids):
    """Stable, order-insensitive short hash of the (cleaned) evidence id set. Empty →
    the fixed token 'none' (so ambient lines dedup by (agent, mode) alone)."""
    ids = sorted(set(_clean_evidence(evidence_ids)))
    if not ids:
        return "none"
    # errors='replace': a stray surrogate in an id must not crash the hash (DoS).
    return hashlib.sha256("|".join(ids).encode("utf-8", "replace")).hexdigest()[:12]


def _esc_key_field(s):
    """Backslash-escape the dedup-key delimiter so an agent_id/mode containing '|'
    cannot collide two distinct (agent,mode,evidence) tuples into one key
    (adversarial finding INV-COOLDOWN)."""
    return str(s).replace("\\", "\\\\").replace("|", "\\|")


def voice_dedup_key(agent_id, mode, evidence_ids):
    """The cooldown/dedup key per #2207: (agent_id, mode, evidence_hash), with the
    free-text fields escaped so the join is injective. Returned to the caller so its
    cooldown map can key on the same evidence."""
    return f"{_esc_key_field(agent_id or '?')}|{_esc_key_field(mode)}|{voice_evidence_hash(evidence_ids)}"


def text_hash(text):
    """Short content hash for the receipt (we record WHAT was said without storing
    the full line in every downstream record)."""
    return hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()[:16]


def decide_voice(mode, evidence_ids=None, voice_line_id=None, voice_line=None,
                 agent_id=None, allowed_modes=VOICE_ALLOWED_MODES,
                 last_spoken_ts=None, now=None, cooldown_secs=VOICE_COOLDOWN_SECS,
                 line_max_chars=VOICE_LINE_MAX_CHARS, templates=VOICE_LINE_TEMPLATES):
    """Pure voice-policy v0 decision. Returns a dict with:
      speak (bool), tier (silent|emit|speech), reason, text, voice_line_id,
      dedup_key, evidence_ids.

    Rules (in order):
      1. default_silent: mode not in allowed_modes -> silent/mode_not_allowed.
      2. verified requires evidence: mode=='verified' with no evidence_ids ->
         silent/verified_requires_evidence (never speak a 'verified' claim that is
         only a mode flip).
      3. text source v0: a known voice_line_id (template) is preferred; a raw
         voice_line is accepted only if non-empty and <= line_max_chars; an unknown
         line id, an over-long line, or no text at all -> silent with that reason.
      4. cooldown: if last_spoken_ts and now are given and now-last_spoken_ts <
         cooldown_secs -> silent/cooldown (same (agent,mode,evidence) not repeated).
      5. tier routing: verified -> speech (bus-verified emission, evidence already
         required in rule 2); every other allowed mode -> emit (fast/unverified).
    The dedup_key is always computed and returned, even on silence, so the caller's
    cooldown map can record it on a real utterance.
    """
    evidence_ids = _clean_evidence(evidence_ids)
    dedup_key = voice_dedup_key(agent_id, mode, evidence_ids)
    base = {"speak": False, "tier": "silent", "mode": mode, "text": None,
            "voice_line_id": voice_line_id, "dedup_key": dedup_key,
            "evidence_ids": evidence_ids}

    if mode not in allowed_modes:
        return {**base, "reason": "mode_not_allowed"}
    if mode == "verified" and not evidence_ids:
        return {**base, "reason": "verified_requires_evidence"}

    # text resolution (v0: template enum preferred, raw line validated)
    if voice_line_id:
        text = templates.get(voice_line_id)
        if text is None:
            return {**base, "reason": "unknown_line_id"}
    elif isinstance(voice_line, str) and voice_line.strip():
        text = voice_line.strip()
        if len(text) > line_max_chars:
            return {**base, "reason": "line_too_long", "text": None}
    else:
        return {**base, "reason": "no_text"}

    if last_spoken_ts is not None and now is not None and (now - last_spoken_ts) < cooldown_secs:
        return {**base, "reason": "cooldown", "text": text}

    tier = "speech" if mode in VOICE_VERIFIED_TIER_MODES else "emit"
    return {"speak": True, "tier": tier, "reason": "speak", "mode": mode,
            "text": text, "voice_line_id": voice_line_id,
            "dedup_key": dedup_key, "evidence_ids": evidence_ids}


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
        # mic = the ACOUSTIC rung, one step beyond the software bus: a microphone
        # hearing the signal proves the sound left a speaker INTO THE AIR. It still
        # does NOT prove the specific listener heard it (a mic at one position is not
        # their eardrum), and a room mic cannot hear private in-ear/headphone output
        # at all — empirically that yields `mismatch`, which is the honest result
        # (the boundary refuses to claim acoustic verification of in-ear audio).
        verified_to = "acoustic output (a microphone heard the signal in the air)"
        not_verified = ("the specific listener's eardrum (a mic position is not their ear); "
                        "and private in-ear/headphone output a room mic cannot hear")
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
    sink, src, channel_verified_to, channel_not_verified = resolve_targets(sink_arg, capture_channel)
    out = {
        "freq": freq, "duration_ms": dur_ms, "sink": sink,
        "capture_channel": capture_channel, "capture_source": src,
        # claim nothing until the channel confirms it; not_verified already names the
        # channel so EARLY-RETURN failures stay honest (see honest_attestation):
        "verified_to": None,
        "not_verified": honest_attestation(None, channel_verified_to, channel_not_verified)[1],
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
    vt, nvt = honest_attestation(status, channel_verified_to, channel_not_verified)
    out.update(
        status=status, verify_status=verify_status_for(status),
        verified_to=vt, not_verified=nvt,
        rms=rv, goertzel=gv, goertzel_floor=floor, peak_ratio=ratio,
        frames=parsed["frames"], sr=sr,
        detail=f"rms={rv} goertzel@{int(freq)}={gv} floor={floor} peak_ratio={ratio} frames={parsed['frames']}",
    )
    return out


def resolve_synth_bin(arg):
    """Locate the selected TTS CLI: explicit arg → env → None (caller errors)."""
    cand = arg or os.environ.get("AB_TTS_SYNTH_BIN", "").strip()
    return cand or None


def synth_speech(text, voice, speed, synth_bin, backend="kokoro"):
    """Invoke ab-tts-synth (Rust) to render `text` → WAV with the chosen `backend`
    (kokoro | piper) or ab-sherpa-tts-synth (sherpa). Returns (wav_path, info_dict)
    or (None, error_dict). The synth bin reports its own sample_rate in `info`, so
    the falsifier stays backend-agnostic."""
    if not synth_bin or not os.path.exists(synth_bin):
        return None, {"detail": f"TTS synth binary not found ({synth_bin!r}); set --synth-bin or AB_TTS_SYNTH_BIN"}
    fd, wav = tempfile.mkstemp(prefix="ab_voice_speech_", suffix=".wav")
    os.close(fd)
    os.unlink(wav)
    if backend == "sherpa":
        cmd = [synth_bin, "--text", text, "--voice", voice, "--speed", str(speed), "--out", wav]
    else:
        cmd = [synth_bin, "--backend", backend, "--text", text, "--voice", voice,
               "--speed", str(speed), "--out", wav]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        info = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except Exception:  # noqa
        info = {}
    if proc.returncode != 0 or not info.get("ok") or not os.path.exists(wav):
        if os.path.exists(wav):
            os.unlink(wav)
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


# --- macOS native path (`say` synth + STT-on-synth-file falsifier) ----------------
# macOS has no PipeWire bus loopback, so the verified channel is the synthesized file
# itself (intelligibility via STT), NOT the output bus. See run_speech_synth_file.

# CRITICAL: the bare `say` default voice resolves to a super-compact alias that
# SILENTLY TRUNCATES input — a duration/file check passes on the broken clip; only the
# STT gate catches it (verified live on this host). So ALWAYS pass an explicit,
# full-quality voice. Kokoro-style names (af_*/bf_*) don't exist on macOS -> fall back.
_MACOS_DEFAULT_VOICE = "Samantha"
_MACOS_PLAYBACK_LOCK_NAME = "agent-bridge-present-voice.lock"


def _new_say_wav_path():
    """Reserve a per-request WAV name without retaining an open descriptor.

    A single fixed `ab_voice_say.wav` path allowed a later synthesis to replace a
    file still being consumed by afplay, which manifests as an audible prefix
    followed by truncation. Each request therefore owns its source file.
    """
    fd, path = tempfile.mkstemp(prefix="ab_voice_say_", suffix=".wav")
    os.close(fd)
    os.unlink(path)
    return path


def play_say_serialized(wav_path):
    """Best-effort macOS playback with a bounded, cross-process endpoint lock.

    This serializes only physical playback, not synthesis or STT. A lock timeout
    is an honest no-play result rather than permitting overlapping afplay calls.
    The returned timing describes process completion, not speaker audibility.
    """
    if not os.path.exists("/usr/bin/afplay"):
        return {"play_ok": False, "playback_error": "afplay not found"}
    lock_path = os.path.join(tempfile.gettempdir(), _MACOS_PLAYBACK_LOCK_NAME)
    try:
        timeout_s = float(os.environ.get("AB_TTS_PLAYBACK_LOCK_TIMEOUT_SECS", "30"))
    except ValueError:
        timeout_s = 30.0
    timeout_s = max(1.0, min(timeout_s, 120.0))
    started_wait = time.monotonic()
    lock_file = open(lock_path, "a+")
    try:
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() - started_wait >= timeout_s:
                    return {
                        "play_ok": False,
                        "playback_error": f"playback lock timed out after {timeout_s:g}s",
                        "playback_lock_wait_ms": round((time.monotonic() - started_wait) * 1000),
                        "playback_serialized": True,
                    }
                time.sleep(0.05)
        lock_wait_ms = round((time.monotonic() - started_wait) * 1000)
        started_ms = round(time.time() * 1000)
        started_play = time.monotonic()
        play = subprocess.run(["/usr/bin/afplay", wav_path], capture_output=True, text=True)
        elapsed_ms = round((time.monotonic() - started_play) * 1000)
        return {
            "play_ok": play.returncode == 0,
            "playback_lock_wait_ms": lock_wait_ms,
            "playback_started_at_unix_ms": started_ms,
            "playback_elapsed_ms": elapsed_ms,
            "playback_serialized": True,
            "playback_error": (play.stderr or "")[:200] if play.returncode else None,
        }
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()


def synth_say(text, voice, speed):
    """macOS `say` -> 16 kHz mono LEI16 WAV (whisper-native rate). Returns (wav, info)
    or (None, err). Bare `say -o x.wav` FAILS ('fmt?') without --data-format; LEI16@16000
    is the verified working spec. NEVER relies on the truncating default voice."""
    say_bin = "/usr/bin/say"
    if not os.path.exists(say_bin):
        return None, {"detail": "macOS `say` not found at /usr/bin/say"}
    v = (voice if (voice and not voice.startswith(("af_", "bf_", "am_", "bm_")))
         else _MACOS_DEFAULT_VOICE)
    # speed (0.5-2.0) -> words/min around the ~175 baseline; floored to stay intelligible.
    wpm = int(max(90, min(2.0, max(0.5, speed)) * 175))
    wav = _new_say_wav_path()
    p = subprocess.run([say_bin, "-v", v, "-r", str(wpm), "-o", wav,
                        "--data-format=LEI16@16000", text],
                       capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(wav):
        return None, {"detail": f"say rc={p.returncode}: {(p.stderr or '')[:200]}"}
    return wav, {"ok": True, "backend": "say", "voice": v, "sample_rate": 16000, "wpm": wpm}


def _qwen_worker_request(socket_path, request, timeout_s):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout_s)
    try:
        client.connect(socket_path)
        client.sendall((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
        raw = bytearray()
        while len(raw) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                break
            raw.extend(chunk)
            if b"\n" in chunk:
                break
        if not raw:
            raise RuntimeError("Qwen3 worker returned no receipt")
        return json.loads(raw.split(b"\n", 1)[0].decode("utf-8"))
    finally:
        client.close()


def synth_qwen3(text, voice, speed, instruct=None, qwen_python=None, qwen_model=None,
                qwen_worker=None):
    """Run Qwen3-TTS only through an explicit isolated Python runtime.

    No implicit package lookup or native-``say`` fallback is allowed: an unavailable
    Qwen environment is an honest synthesis error.  The model itself is loaded by
    the child adapter, keeping PyTorch out of the AB MCP process.
    """
    fd, wav = tempfile.mkstemp(prefix="ab_voice_qwen3_", suffix=".wav")
    os.close(fd)
    os.unlink(wav)
    try:
        timeout_s = float(os.environ.get("AB_QWEN3_TTS_TIMEOUT_SECS", "180"))
    except ValueError:
        timeout_s = 180.0
    timeout_s = max(30.0, min(timeout_s, 600.0))
    qwen_worker = qwen_worker or os.environ.get("AB_QWEN3_TTS_WORKER_SOCKET", "").strip()
    if qwen_worker:
        try:
            info = _qwen_worker_request(qwen_worker, {"op": "synthesize", "text": text,
                "output": wav, "speaker": voice, "instruct": instruct or ""}, timeout_s)
        except (OSError, ValueError, RuntimeError, socket.timeout) as exc:
            return None, {"detail": f"Qwen3 worker unavailable: {str(exc)[:300]}"}
        if not info.get("ok") or not os.path.exists(wav):
            return None, {"detail": info.get("detail", "Qwen3 worker did not write WAV")}
    else:
        qwen_python = qwen_python or os.environ.get("AB_QWEN3_TTS_PYTHON", "").strip()
        if not qwen_python or not os.path.exists(qwen_python):
            return None, {"detail": "Qwen3-TTS runtime not configured; set AB_QWEN3_TTS_PYTHON or AB_QWEN3_TTS_WORKER_SOCKET"}
        adapter = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen3_tts_synth.py")
        if not os.path.exists(adapter):
            return None, {"detail": f"Qwen3-TTS adapter not found: {adapter}"}
        cmd = [qwen_python, adapter, "--text", text, "--output", wav, "--speaker", voice]
        if instruct: cmd.extend(["--instruct", instruct])
        if qwen_model: cmd.extend(["--model", qwen_model])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return None, {"detail": f"Qwen3-TTS timed out after {timeout_s:g}s"}
        try: info = json.loads((proc.stdout or "").strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError): info = {"detail": f"Qwen3-TTS produced no JSON receipt: {(proc.stderr or '')[:200]}"}
        if proc.returncode != 0 or not info.get("ok") or not os.path.exists(wav):
            return None, {"detail": info.get("detail", f"Qwen3-TTS rc={proc.returncode}")}
    # A timing estimate is only a truncation falsifier. It is not a claim that Qwen
    # emitted at an exact rate, and stays aligned with the existing macOS gate.
    info["wpm"] = int(max(90, min(2.0, max(0.5, speed)) * 175))
    return wav, info


def synth_omnivoice(text, voice, speed, instruct=None, omnivoice_python=None,
                    omnivoice_manifest=None):
    """Run the default-off OmniVoice ONNX candidate through its pinned adapter."""
    enabled = os.environ.get("AB_OMNIVOICE_TTS_ENABLED", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return None, {"detail": "OmniVoice backend is disabled; set AB_OMNIVOICE_TTS_ENABLED=1"}
    if voice and voice.lower() not in {"auto", "default", "omnivoice"}:
        return None, {"detail": "OmniVoice pilot does not support named speakers; use --voice auto"}
    if instruct:
        return None, {"detail": "OmniVoice pilot does not support style instructions"}
    omnivoice_python = (omnivoice_python or
                        os.environ.get("AB_OMNIVOICE_TTS_PYTHON", "").strip())
    if not omnivoice_python or not os.path.exists(omnivoice_python):
        return None, {"detail": "OmniVoice runtime not configured; set AB_OMNIVOICE_TTS_PYTHON"}
    adapter = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "omnivoice_tts_synth.py")
    fd, wav = tempfile.mkstemp(prefix="ab_voice_omnivoice_", suffix=".wav")
    os.close(fd)
    os.unlink(wav)
    cmd = [omnivoice_python, adapter, "--text", text, "--output", wav]
    if omnivoice_manifest:
        cmd.extend(["--manifest", omnivoice_manifest])
    try:
        timeout_s = float(os.environ.get("AB_OMNIVOICE_TTS_TIMEOUT_SECS", "300"))
    except ValueError:
        timeout_s = 300.0
    timeout_s = max(30.0, min(timeout_s, 900.0))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return None, {"detail": f"OmniVoice timed out after {timeout_s:g}s"}
    try:
        info = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        info = {"detail": f"OmniVoice produced no JSON receipt: {(proc.stderr or '')[:200]}"}
    if proc.returncode != 0 or not info.get("ok") or not os.path.exists(wav):
        if os.path.exists(wav):
            os.unlink(wav)
        return None, {"detail": info.get("detail", f"OmniVoice rc={proc.returncode}")}
    info["wpm"] = int(max(90, min(2.0, max(0.5, speed)) * 175))
    return wav, info


def synth_tts_canary(text, voice, speed, instruct=None, subject=None, request_id=None,
                     policy_path=None, qwen_python=None, qwen_model=None,
                     qwen_worker=None, omnivoice_python=None, omnivoice_manifest=None):
    """Select Qwen/OmniVoice through the review-bound, default-off canary gate."""
    from tts_canary_router import decide

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    policy_path = policy_path or os.environ.get("AB_TTS_CANARY_POLICY", "").strip()
    if not policy_path:
        policy_path = os.path.join(root, "config", "omnivoice-canary.json")
    try:
        with open(policy_path, encoding="utf-8") as handle:
            policy = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return None, {"detail": f"TTS canary policy unavailable: {str(exc)[:300]}"}
    runtime_enabled = os.environ.get("AB_TTS_CANARY_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on"
    }
    language = "Chinese" if _contains_cjk(text) else "English"
    decision = decide(policy, root=os.path.abspath(root),
                      runtime_enabled=runtime_enabled, subject=subject or "",
                      request_id=request_id or "", language=language, speaker=voice,
                      instruction=instruct, reference_clone=False)
    if decision["selected_backend"] == policy["candidate_backend"]:
        wav, info = synth_omnivoice(text, "auto", speed, None,
                                    omnivoice_python, omnivoice_manifest)
        executed_backend = policy["candidate_backend"]
        fallback_used = False
        candidate_error = None
        if wav is None and policy.get("fallback_to_control_on_candidate_error") is True:
            candidate_error = info.get("detail", "OmniVoice candidate failed")
            control_voice = policy.get("control_speaker", "Serena")
            wav, info = synth_qwen3(text, control_voice, speed, instruct,
                                    qwen_python, qwen_model, qwen_worker)
            executed_backend = policy["control_backend"]
            fallback_used = True
    else:
        control_voice = (policy.get("control_speaker", "Serena")
                         if not voice or voice.lower() in {"auto", "default", "omnivoice"}
                         else voice)
        wav, info = synth_qwen3(text, control_voice, speed, instruct,
                                qwen_python, qwen_model, qwen_worker)
        executed_backend = policy["control_backend"]
        fallback_used = False
        candidate_error = None
    info = dict(info)
    info.update({"canary_selected_backend": executed_backend,
                 "canary_assigned_backend": decision["selected_backend"],
                 "canary_executed_backend": executed_backend,
                 "canary_candidate_selected": decision["candidate_selected"],
                 "canary_fallback_used": fallback_used,
                 "canary_candidate_error": candidate_error,
                 "canary_bucket": decision["bucket"],
                 "canary_reasons": decision["reasons"],
                 "canary_review_decision_sha256": decision["review_decision_sha256"]})
    return wav, info


def synth_qwen3_rust(text, voice, speed, instruct=None, binary=None,
                     model_dir=None, model_profile=None):
    """Run the pure-Rust Qwen3-TTS pilot through its fail-closed integrity gate.

    The backend is deliberately unavailable unless the operator explicitly opts
    in and supplies both the local CLI and model directory. It never downloads a
    model, searches PATH, or falls back to Python/native speech.
    """
    enabled = os.environ.get("AB_QWEN3_TTS_RUST_ENABLED", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return None, {
            "detail": "Qwen3 Rust backend is disabled; set AB_QWEN3_TTS_RUST_ENABLED=1"
        }
    binary = binary or os.environ.get("AB_QWEN3_TTS_RUST_BIN", "").strip()
    model_dir = model_dir or os.environ.get("AB_QWEN3_TTS_RUST_MODEL_DIR", "").strip()
    model_profile = model_profile or os.environ.get("AB_QWEN3_TTS_RUST_PROFILE", "").strip()
    if not binary:
        return None, {"detail": "Qwen3 Rust binary not configured; set AB_QWEN3_TTS_RUST_BIN"}
    if not model_dir:
        return None, {"detail": "Qwen3 Rust model directory not configured; set AB_QWEN3_TTS_RUST_MODEL_DIR"}
    if not model_profile:
        return None, {"detail": "Qwen3 Rust model profile not configured; set AB_QWEN3_TTS_RUST_PROFILE"}
    gate = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qwen3_tts_rust_gate.py")
    if not os.path.exists(gate):
        return None, {"detail": f"Qwen3 Rust integrity gate not found: {gate}"}

    fd, wav = tempfile.mkstemp(prefix="ab_voice_qwen3_rust_", suffix=".wav")
    os.close(fd)
    os.unlink(wav)
    cmd = [sys.executable, gate, "--binary", binary, "--model-dir", model_dir,
           "--model-profile", model_profile, "--output", wav, "--text", text,
           "--speaker", voice]
    if instruct:
        cmd.extend(["--instruct", instruct])
    try:
        timeout_s = float(os.environ.get("AB_QWEN3_TTS_RUST_TIMEOUT_SECS", "900"))
    except ValueError:
        timeout_s = 900.0
    timeout_s = max(30.0, min(timeout_s, 1200.0))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return None, {"detail": f"Qwen3 Rust gate timed out after {timeout_s:g}s"}
    try:
        receipt = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        receipt = {"reason": "malformed_gate_receipt",
                   "detail": f"Qwen3 Rust gate produced no JSON receipt: {(proc.stderr or '')[:200]}"}
    if proc.returncode != 0 or not receipt.get("verified") or not os.path.exists(wav):
        if os.path.exists(wav):
            try:
                os.unlink(wav)
            except OSError:
                pass
        reason = receipt.get("reason") or f"gate_rc_{proc.returncode}"
        return None, {"detail": receipt.get("detail", f"Qwen3 Rust gate failed: {reason}"),
                      "reason": reason}

    binary_evidence = receipt.get("binary_evidence") or {}
    return wav, {
        "ok": True, "backend": "qwen3-rust", "runtime": "rust", "model": model_dir,
        "model_profile": receipt.get("model_profile"), "model_revision": receipt.get("model_revision"),
        "voice": voice, "device": "metal", "dtype": "f16",
        "instruct_applied": bool(instruct), "integrity_verified": True, "binary": binary,
        "binary_sha256": binary_evidence.get("sha256"),
        "wpm": int(max(90, min(2.0, max(0.5, speed)) * 175)),
    }


def transcribe_synth_file(wav_path, model=None, language="en"):
    """OpenAI-whisper (Python CLI, NOT whisper.cpp) transcription of a synth WAV ->
    (text, None) or (None, err). The macOS STT path: AB_TTS_STT_BIN points at a
    whisper.cpp CLI with different flags, so the synth_file channel uses the `whisper`
    CLI directly. bin: env AB_TTS_WHISPER_BIN -> stock brew paths. model: env
    AB_TTS_WHISPER_MODEL or 'tiny' (fast, CPU; tiny was empirically sufficient)."""
    whisper_bin = os.environ.get("AB_TTS_WHISPER_BIN", "").strip()
    if not whisper_bin or not os.path.exists(whisper_bin):
        whisper_bin = next((c for c in ("/opt/homebrew/bin/whisper", "/usr/local/bin/whisper")
                            if os.path.exists(c)), None)
    if not whisper_bin:
        return None, "whisper CLI not found (brew install openai-whisper, or set AB_TTS_WHISPER_BIN)"
    model = model or os.environ.get("AB_TTS_WHISPER_MODEL", "").strip() or "tiny"
    outdir = tempfile.mkdtemp(prefix="ab_whisper_")
    try:
        timeout_s = float(os.environ.get("AB_TTS_WHISPER_TIMEOUT_SECS", "45"))
    except ValueError:
        timeout_s = 45.0
    timeout_s = max(5.0, min(timeout_s, 300.0))
    try:
        cmd = [whisper_bin, wav_path, "--model", model, "--language", language,
               "--output_format", "txt", "--output_dir", outdir,
               "--fp16", "False", "--verbose", "False"]
        # macOS Tingting speaks Mandarin, but Whisper often emits semantically
        # identical Traditional Chinese. The exact-character recall gate then
        # misclassifies a healthy synth as garbled. Prompt the decoder toward
        # Simplified Chinese so the transcript and requested text share the same
        # writing system; this does not supply the requested sentence itself.
        if language == "zh":
            cmd.extend(["--initial_prompt", "以下是普通话的简体中文句子。"])
        p = subprocess.run(cmd,
                           capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return None, f"whisper timed out after {timeout_s:g}s"
    if p.returncode != 0:
        return None, f"whisper rc={p.returncode}: {(p.stderr or '')[:200]}"
    txt_path = os.path.join(outdir, os.path.splitext(os.path.basename(wav_path))[0] + ".txt")
    if not os.path.exists(txt_path):
        return None, "whisper produced no transcript file"
    try:
        return open(txt_path, encoding="utf-8").read().strip(), None
    except OSError as e:  # noqa
        return None, f"read transcript failed: {e}"


def run_speech(text, voice, speed, sink_arg, capture_channel, synth_bin,
               check_intelligibility=False, stt_bin=None, stt_model=None, synth_backend="kokoro"):
    """Speech-mode embodiment: synthesize `text` (via `synth_backend` = kokoro|piper)
    → play to the sink while capturing the bus → verify by energy-envelope correlation
    + voiced span (NOT a tone peak). Optionally also transcribe the bus capture
    (whisper.cpp) and check the requested words came back — a stronger, layered
    intelligibility falsifier. The falsifier is backend-agnostic (it correlates the
    captured bus against whatever WAV the chosen engine produced)."""
    sink, src, channel_verified_to, channel_not_verified = resolve_targets(sink_arg, capture_channel)
    out = {
        "mode": "speech", "text": text, "voice": voice, "speed": speed, "sink": sink,
        "synth_backend": synth_backend,
        "capture_channel": capture_channel, "capture_source": src,
        # claim nothing until the bus confirms it; not_verified already names the bus
        # so EARLY-RETURN failures stay honest (see honest_attestation):
        "verified_to": None,
        "not_verified": honest_attestation(None, channel_verified_to, channel_not_verified)[1],
    }

    wav, info = synth_speech(text, voice, speed, synth_bin, backend=synth_backend)
    if wav is None:
        out.update(status="error", verify_status="error", detail=info.get("detail", "synth failed"))
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
    vt, nvt = honest_attestation(status, channel_verified_to, channel_not_verified)
    out.update(
        status=status, verify_status=verify_status_for(status),
        verified_to=vt, not_verified=nvt,
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


def run_speech_synth_file(text, voice, speed, synth_backend="say", qwen_instruct=None,
                          qwen_python=None, qwen_model=None, qwen_worker=None,
                          qwen_rust_bin=None, qwen_rust_model_dir=None,
                          qwen_rust_profile=None, omnivoice_python=None,
                          omnivoice_manifest=None, canary_subject=None,
                          canary_request_id=None, canary_policy=None, stt_model=None):
    """macOS speech embodiment: selected synth -> STT-on-the-synth-file falsifier. No bus
    `.monitor` loopback exists on macOS, so this channel honestly verifies the
    SYNTHESIZED FILE is intelligible, NOT that it played. The STT word_overlap is THE
    gate (envelope-vs-itself is meaningless on a source-only readback). `afplay` is
    best-effort audible playback and NEVER lifts verify_status (exit 0 != audible sound
    — the macOS twin of the 'recompute-error must not self-fulfill' / 'timeout is never
    approval' trap). Every early-return routes through honest_attestation so a failed
    run never inherits a verified_to it did not earn."""
    channel_verified_to = "synthesized audio file (STT-intelligible speech rendered to disk)"
    channel_not_verified = ("output bus AND physical transducer — this run read the synth "
                            "file, not any playback (no loopback / sink .monitor on macOS)")
    out = {
        "mode": "speech", "text": text, "voice": voice, "speed": speed,
        "synth_backend": synth_backend, "capture_channel": "synth_file",
        "verify_method": "synth_file_stt",
        # claim nothing until the channel confirms it; not_verified already names the
        # channel so EARLY-RETURN failures stay honest (see honest_attestation):
        "verified_to": None,
        "not_verified": honest_attestation(None, channel_verified_to, channel_not_verified)[1],
    }
    if synth_backend == "qwen3":
        wav, info = synth_qwen3(text, voice, speed, qwen_instruct, qwen_python, qwen_model, qwen_worker)
    elif synth_backend == "qwen3-rust":
        wav, info = synth_qwen3_rust(text, voice, speed, qwen_instruct,
                                     qwen_rust_bin, qwen_rust_model_dir,
                                     qwen_rust_profile)
    elif synth_backend == "omnivoice":
        wav, info = synth_omnivoice(text, voice, speed, qwen_instruct,
                                    omnivoice_python, omnivoice_manifest)
    elif synth_backend == "canary":
        wav, info = synth_tts_canary(
            text, voice, speed, qwen_instruct, canary_subject, canary_request_id,
            canary_policy, qwen_python, qwen_model, qwen_worker,
            omnivoice_python, omnivoice_manifest)
    else:
        wav, info = synth_say(text, voice, speed)
    if wav is None:
        out.update(status="error", verify_status="error", detail=info.get("detail", f"{synth_backend} synth failed"))
        return out
    out["voice"] = info.get("voice", voice)
    executed_backend = info.get("canary_executed_backend")
    if synth_backend in {"qwen3", "qwen3-rust"} or (
            synth_backend == "canary" and executed_backend == "qwen3"):
        for field in ("model", "device", "dtype", "instruct_applied", "runtime",
                      "model_profile", "model_revision", "integrity_verified",
                      "binary", "binary_sha256"):
            if field in info:
                out[f"qwen_{field}"] = info[field]
    if synth_backend == "omnivoice" or (
            synth_backend == "canary" and executed_backend == "omnivoice"):
        for field in ("manifest", "manifest_status", "hashes_verified", "steps",
                      "language", "runtime", "rtf"):
            if field in info:
                out[f"omnivoice_{field}"] = info[field]
    if synth_backend == "canary":
        for field in ("canary_selected_backend", "canary_candidate_selected",
                      "canary_assigned_backend", "canary_executed_backend",
                      "canary_fallback_used", "canary_candidate_error",
                      "canary_bucket", "canary_reasons",
                      "canary_review_decision_sha256"):
            if field in info:
                out[field] = info[field]
    parsed = _read_wav_mono_s16(wav)
    if parsed is None or not len(parsed["samples"]):
        out.update(status="error", verify_status="error", detail="synthesized WAV unreadable/empty")
        return out
    samples, sr = parsed["samples"], parsed["sr"] or 16000
    rms_val = round(rms_of(samples), 2)
    synth_dur = round(parsed["frames"] / sr, 3)
    out["synth_dur_s"] = synth_dur

    # STT gate (THE falsifier for the synth_file channel): transcribe the synth WAV and
    # check the requested words survived synthesis. STT unavailable -> no_capture (never
    # claim emitted without the word gate; degraded capability, not a content fault).
    stt_language = "zh" if _contains_cjk(text) else "en"
    transcript, stt_err = transcribe_synth_file(wav, model=stt_model, language=stt_language)
    out["stt_language"] = stt_language
    # An empty/whitespace transcript from a WORKING whisper (exit 0, no words) is NOT a
    # content fault — whisper declined to transcribe (silence / non-speech / undecodable).
    # Fold it into the honest no_capture path (NOT mismatch, which would falsely assert the
    # words came out wrong) — symmetric with the (None, err) STT-unavailable case. (#2300 MED-2.)
    if transcript is not None and not transcript.strip():
        stt_err = "whisper returned an empty transcript (no words recovered — STT could not verify)"
        transcript = None
    stt_available = transcript is not None
    ratio, nref = word_overlap(text, transcript or "")
    # expected duration from words/wpm feeds the truncation guard (see classify_synth_file_embody).
    wpm = info.get("wpm", 0) or 0
    expected_dur = _expected_speech_duration(text, wpm)
    out["expected_dur_s"] = round(expected_dur, 3)
    status = classify_synth_file_embody(parsed["frames"], rms_val, ratio, nref, stt_available,
                                        synth_dur_s=synth_dur, expected_dur_s=expected_dur)
    vt, nvt = honest_attestation(status, channel_verified_to, channel_not_verified)
    out.update(status=status, verify_status=verify_status_for(status),
               verified_to=vt, not_verified=nvt,
               synth_rms=rms_val, frames=parsed["frames"], sr=sr)
    if stt_available:
        out["stt_transcript"] = transcript
        out["word_overlap"] = round(ratio, 3)
        out["intelligibility"] = classify_intelligibility(ratio, nref, threshold=SYNTH_FILE_INTEL_MIN)
        truncated = expected_dur > 0 and synth_dur < SYNTH_FILE_DUR_FRAC * expected_dur
        dur_note = (f"; TRUNCATED (synth {synth_dur}s < {SYNTH_FILE_DUR_FRAC}x expected {round(expected_dur, 2)}s)"
                    if truncated else "")
        out["detail"] = (f"{synth_backend} synth {synth_dur}s; stt '{transcript[:80]}' "
                         f"overlap={round(ratio, 3)} -> {out['intelligibility']}{dur_note}")
    else:
        out["intelligibility"] = "unavailable"
        out["stt_detail"] = stt_err
        out["detail"] = f"{synth_backend} synth {synth_dur}s rms={rms_val}; STT unavailable -> words unverified ({stt_err})"

    # Best-effort physical playback is serialized across local processes so one
    # request cannot cut off another. Completion timing proves only afplay's
    # process lifetime; human confirmation remains the last-mile evidence.
    playback = play_say_serialized(wav)
    out.update(playback)
    out["play_note"] = (
        "afplay is serialized and timed; play_ok still does NOT prove speaker audibility "
        "or full-utterance delivery"
    )
    return out


def run_emit(text, voice, speed, sink_arg, synth_bin):
    """FAST-EMIT tier: synthesize `text` and play it to the sink WITHOUT reading the
    bus back. The low-truth-claim companion-chatter path (status lines), distinct
    from `--mode speech` which verifies on the bus. It makes NO verification claim
    (see `emit_claim_fields`): it played the audio but did NOT confirm it reached
    the bus, so the honest boundary is WIDER than speech mode — both the output bus
    AND the physical transducer are unverified. Fast because it skips capture +
    envelope/STT analysis entirely (no `.monitor` readback)."""
    sink = sink_arg or _sh("pactl get-default-sink").stdout.strip()
    out = {
        "mode": "emit", "text": text, "voice": voice, "speed": speed, "sink": sink,
        # emit never reads back → it asserts nothing about the bus:
        "verified_to": None,
        "not_verified": "output bus AND physical transducer "
                        "(emit mode plays without bus readback — use --mode speech to verify)",
    }
    wav, info = synth_speech(text, voice, speed, synth_bin)
    if wav is None:
        status, verify_status, _ = emit_claim_fields(False)
        out.update(status=status, verify_status=verify_status, detail=info.get("detail", "synth failed"))
        return out
    played = _read_wav_mono_s16(wav)
    played_dur = (played["frames"] / (played["sr"] or 24000)) if played else 0.0
    out["played_dur_s"] = round(played_dur, 3)
    try:
        play = _sh(f"paplay --device={sink} {wav}")  # blocks ~played_dur (no capture)
        play_ok = play.returncode == 0
    except Exception as e:  # noqa
        status, verify_status, _ = emit_claim_fields(False)
        out.update(status=status, verify_status=verify_status, detail=f"playback: {e}")
        return out
    status, verify_status, _ = emit_claim_fields(play_ok)
    out.update(
        status=status, verify_status=verify_status, play_ok=play_ok,
        detail=f"played {round(played_dur, 2)}s to {sink} (emit: no bus readback, unverified)",
    )
    return out


def run_render(text, voice, speed, synth_bin, synth_backend, output_file):
    """Synthesize a durable WAV without emitting it to an audio sink."""
    out = {"mode": "render", "text": text, "voice": voice, "speed": speed,
           "synth_backend": synth_backend, "verified_to": None,
           "not_verified": "output bus and physical transducer (render mode never plays audio)"}
    wav, info = synth_speech(text, voice, speed, synth_bin, backend=synth_backend)
    if wav is None:
        out.update(status="error", verify_status="error", detail=info.get("detail", "synth failed"))
        return out
    target = os.path.abspath(output_file)
    try:
        target_dir = os.path.dirname(target)
        os.makedirs(target_dir, exist_ok=True)
        fd, staged = tempfile.mkstemp(prefix=".ab_voice_render_", suffix=".wav", dir=target_dir)
        os.close(fd)
        with open(wav, "rb") as src, open(staged, "wb") as dst:
            while block := src.read(1024 * 1024):
                dst.write(block)
        os.unlink(wav)
        os.replace(staged, target)
        with open(target, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        out.update(status="rendered", verify_status="synthesized", audio_file=target,
                   audio_sha256=digest, audio_bytes=os.path.getsize(target),
                   detail="rendered click-to-play audio; no playback requested")
    except Exception as e:  # noqa
        if os.path.exists(wav):
            os.unlink(wav)
        out.update(status="error", verify_status="error", detail=f"persist rendered audio: {e}")
    return out


# --- voice adapter orchestration (LCC-V1: decide -> route -> receipt) ------------

# Fields the chosen tier (emit | speech) produces that we copy verbatim into the
# voice receipt, so the receipt carries exactly what that tier actually PROVED —
# never more. emit contributes played_unverified + a null verified_to; speech
# contributes the bus falsifier (env_corr/STT) + verified_to=output bus.
_VOICE_TIER_PASSTHROUGH = (
    "status", "verify_status", "verified_to", "not_verified", "play_ok",
    "played_dur_s", "sink", "env_corr", "voiced_secs", "capture_rms",
    "intelligibility", "word_overlap", "stt_transcript",
)


def run_voice(mode, voice, sink_arg, synth_bin, evidence_ids=None,
              voice_line_id=None, voice_line=None, agent_id=None,
              allowed_modes=VOICE_ALLOWED_MODES, last_spoken_ts=None, now=None,
              cooldown_secs=VOICE_COOLDOWN_SECS, speed=1.0,
              stt_bin=None, stt_model=None):
    """LCC-V1 companion voice adapter. Applies the PURE voice-policy v0 decision
    (`decide_voice`), then — only if it says speak — routes to the FAST tier
    (`run_emit`) or the VERIFIED tier (`run_speech`) and folds the tier's own
    honest proof into a voice receipt (#2215 shape).

    Honest by construction: the receipt's `verify_status`/`verified_to` are
    whatever the chosen tier actually established at the bus, NOT what the policy
    *wanted*. So a `verified` line whose bus readback fails is recorded as a
    mismatch, never as rendered_ok — the evidence requirement (policy) and the bus
    verification (tier) are two independent gates that must BOTH hold for a true
    verified claim.
    """
    d = decide_voice(mode, evidence_ids=evidence_ids, voice_line_id=voice_line_id,
                     voice_line=voice_line, agent_id=agent_id, allowed_modes=allowed_modes,
                     last_spoken_ts=last_spoken_ts, now=now, cooldown_secs=cooldown_secs)
    receipt = {
        "mode": "voice", "lifecycle_mode": mode, "decision": d["reason"],
        "tier": d["tier"], "dedup_key": d["dedup_key"], "evidence_ids": d["evidence_ids"],
        "voice_line_id": voice_line_id, "voice": voice,
    }
    if not d["speak"]:
        # silent is a first-class, honest outcome — it never claims verification.
        receipt.update(status="silent", verify_status="skipped",
                       verified_to=None, not_verified=None, play_ok=False,
                       text_hash=None, detail=f"voice-policy: {d['reason']}")
        return receipt

    text = d["text"]
    receipt["text_hash"] = text_hash(text)
    if d["tier"] == "speech":
        want_stt = bool(stt_bin or os.environ.get("AB_TTS_STT_BIN", "").strip())
        em = run_speech(text, voice, speed, sink_arg, "sink_monitor", synth_bin,
                        check_intelligibility=want_stt, stt_bin=stt_bin, stt_model=stt_model)
    else:
        em = run_emit(text, voice, speed, sink_arg, synth_bin)
    for k in _VOICE_TIER_PASSTHROUGH:
        if k in em:
            receipt[k] = em[k]
    receipt["detail"] = f"tier={d['tier']} -> {em.get('detail', '')}"
    return receipt


def main():
    ap = argparse.ArgumentParser(description="present_voice audio-embodiment falsifier")
    ap.add_argument("--mode", choices=["tone", "speech", "emit", "render", "voice"], default="tone",
                    help="tone = fixed-freq Goertzel peak (default); speech = TTS envelope-correlation "
                         "falsifier (verified); emit = TTS synth+play, NO bus readback (fast, unverified); "
                         "voice = LCC-V1 companion voice adapter (voice-policy v0 gate -> emit/speech tier)")
    # voice-adapter args (LCC-V1)
    ap.add_argument("--lifecycle-mode", default=None,
                    help="voice mode: companion lifecycle mode (failed|verified|waiting_for_user|handoff|...)")
    ap.add_argument("--voice-line-id", default=None, help="voice mode: template line id (e.g. verified.generic)")
    ap.add_argument("--voice-line", default=None, help="voice mode: raw line text (length/policy gated)")
    ap.add_argument("--evidence-id", action="append", default=None,
                    help="voice mode: verification_outcome_id / evidence_event_id (repeatable); required for verified")
    ap.add_argument("--agent-id", default=None, help="voice mode: agent id for the (agent,mode,evidence) dedup key")
    ap.add_argument("--allowed-modes", default=None, help="voice mode: comma list overriding the default 4 gates")
    ap.add_argument("--last-spoken-ts", type=float, default=None, help="voice mode: ts of the last utterance for this dedup key")
    ap.add_argument("--now", type=float, default=None, help="voice mode: current ts (cooldown eval); default time.time()")
    ap.add_argument("--cooldown-secs", type=float, default=VOICE_COOLDOWN_SECS, help="voice mode: cooldown window")
    ap.add_argument("--freq", type=float, default=440.0)
    ap.add_argument("--duration-ms", type=int, default=1500)
    ap.add_argument("--amplitude", type=float, default=0.25)
    ap.add_argument("--sink", default=None)
    ap.add_argument("--capture-channel", choices=["sink_monitor", "mic", "synth_file"], default="sink_monitor",
                    help="sink_monitor/mic = PipeWire bus (Linux); synth_file = verify the synth WAV via STT "
                         "(macOS / no-loopback; auto-selected on darwin)")
    ap.add_argument("--no-emit", action="store_true", help="capture-only (silence/external check)")
    # speech-mode args
    ap.add_argument("--text", default=None, help="speech mode: text to synthesize + speak")
    ap.add_argument("--voice", default="af_sarah", help="speech mode: TTS voice name")
    ap.add_argument("--speed", type=float, default=1.0, help="speech mode: speech speed (0.5-2.0)")
    ap.add_argument("--synth-bin", default=None, help="speech mode: path to ab-tts-synth (or env AB_TTS_SYNTH_BIN)")
    ap.add_argument("--output-file", default=None, help="render mode: durable WAV output path")
    ap.add_argument("--synth-backend", choices=["kokoro", "piper", "sherpa", "say", "qwen3", "qwen3-rust", "omnivoice", "canary"], default="kokoro",
                    help="speech mode: TTS engine (kokoro 24kHz | piper 22.05kHz | sherpa = Chinese multi-speaker VITS | say = macOS native | "
                         "qwen3 = explicit Python CustomVoice | qwen3-rust = default-off local Rust gate | omnivoice = default-off ONNX pilot | canary = review-bound Qwen/OmniVoice selector; macOS uses synth_file STT verification)")
    ap.add_argument("--qwen-instruct", default=None, help="Qwen3 CustomVoice natural-language style instruction")
    ap.add_argument("--qwen-python", default=None, help="explicit isolated Python that has qwen-tts installed")
    ap.add_argument("--qwen-model", default=None, help="Qwen3 model id or local directory; defaults to 1.7B CustomVoice")
    ap.add_argument("--qwen-worker", default=None, help="explicit owner-only Unix socket for the persistent Qwen worker")
    ap.add_argument("--qwen-rust-bin", default=None, help="qwen3-rust: explicit local qwen-tts executable")
    ap.add_argument("--qwen-rust-model-dir", default=None, help="qwen3-rust: explicit complete local model directory")
    ap.add_argument("--qwen-rust-profile", default=None, help="qwen3-rust: pinned integrity profile, e.g. 1.7b-customvoice")
    ap.add_argument("--omnivoice-python", default=None, help="omnivoice: explicit isolated Python with ONNX dependencies")
    ap.add_argument("--omnivoice-manifest", default=None, help="omnivoice: pinned composition manifest")
    ap.add_argument("--canary-subject", default=None, help="canary: allowlisted subject identifier")
    ap.add_argument("--canary-request-id", default=None, help="canary: stable per-request identifier used for bucketing")
    ap.add_argument("--canary-policy", default=None, help="canary: explicit policy path; defaults to checked-in disabled policy")
    ap.add_argument("--check-intelligibility", action="store_true",
                    help="speech mode: also transcribe the bus capture (whisper.cpp) and check words came back")
    ap.add_argument("--stt-bin", default=None, help="whisper.cpp CLI path (or env AB_TTS_STT_BIN)")
    ap.add_argument("--stt-model", default=None, help="whisper ggml model path (or env AB_TTS_STT_MODEL)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.mode == "voice":
        lm = (a.lifecycle_mode or "").strip()
        if not lm:
            res = {"mode": "voice", "status": "error", "verify_status": "error",
                   "detail": "voice mode requires --lifecycle-mode"}
        else:
            allowed = (tuple(m.strip() for m in a.allowed_modes.split(",") if m.strip())
                       if a.allowed_modes else VOICE_ALLOWED_MODES)
            now = a.now if a.now is not None else (time.time() if a.last_spoken_ts is not None else None)
            res = run_voice(lm, a.voice, a.sink, resolve_synth_bin(a.synth_bin),
                            evidence_ids=a.evidence_id, voice_line_id=a.voice_line_id,
                            voice_line=a.voice_line, agent_id=a.agent_id, allowed_modes=allowed,
                            last_spoken_ts=a.last_spoken_ts, now=now,
                            cooldown_secs=a.cooldown_secs, speed=max(0.5, min(a.speed, 2.0)),
                            stt_bin=a.stt_bin, stt_model=a.stt_model)
        if a.json:
            print(json.dumps(res))
        else:
            for k, v in res.items():
                print(f"{k}: {v}")
        return
    if a.mode == "emit":
        if not a.text or not a.text.strip():
            res = {"mode": "emit", "status": "error", "verify_status": "error",
                   "detail": "emit mode requires --text"}
        else:
            res = run_emit(a.text, a.voice, max(0.5, min(a.speed, 2.0)), a.sink,
                           resolve_synth_bin(a.synth_bin))
        if a.json:
            print(json.dumps(res))
        else:
            for k, v in res.items():
                print(f"{k}: {v}")
        return
    if a.mode == "render":
        if not a.text or not a.text.strip():
            res = {"mode": "render", "status": "error", "verify_status": "error", "detail": "render mode requires --text"}
        elif not a.output_file:
            res = {"mode": "render", "status": "error", "verify_status": "error", "detail": "render mode requires --output-file"}
        else:
            res = run_render(a.text, a.voice, max(0.5, min(a.speed, 2.0)), resolve_synth_bin(a.synth_bin), a.synth_backend, a.output_file)
        if a.json:
            print(json.dumps(res))
        else:
            for k, v in res.items():
                print(f"{k}: {v}")
        return
    if a.mode == "speech":
        if not a.text or not a.text.strip():
            res = {"mode": "speech", "status": "error", "verify_status": "error",
                   "detail": "speech mode requires --text"}
        elif _IS_MACOS or a.capture_channel == "synth_file":
            # macOS / no-loopback: present_voice verifies the synthesized FILE via STT
            # (there is no PipeWire sink `.monitor` bus to read back). See
            # run_speech_synth_file. SCOPED to the present_voice speech path only — the
            # LCC voice adapter (`--mode voice` -> run_voice) is deliberately unchanged.
            res = run_speech_synth_file(a.text, a.voice, max(0.5, min(a.speed, 2.0)),
                                        synth_backend=a.synth_backend, qwen_instruct=a.qwen_instruct,
                                        qwen_python=a.qwen_python, qwen_model=a.qwen_model,
                                        qwen_worker=a.qwen_worker,
                                        qwen_rust_bin=a.qwen_rust_bin,
                                        qwen_rust_model_dir=a.qwen_rust_model_dir,
                                        qwen_rust_profile=a.qwen_rust_profile,
                                        omnivoice_python=a.omnivoice_python,
                                        omnivoice_manifest=a.omnivoice_manifest,
                                        canary_subject=a.canary_subject,
                                        canary_request_id=a.canary_request_id,
                                        canary_policy=a.canary_policy,
                                        stt_model=a.stt_model)
        else:
            res = run_speech(a.text, a.voice, max(0.5, min(a.speed, 2.0)), a.sink,
                             a.capture_channel, resolve_synth_bin(a.synth_bin),
                             check_intelligibility=a.check_intelligibility,
                             stt_bin=a.stt_bin, stt_model=a.stt_model,
                             synth_backend=a.synth_backend)
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
