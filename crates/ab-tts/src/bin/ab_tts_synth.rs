//! `ab-tts-synth` — production text→WAV CLI for the audio-embodiment lane.
//!
//! Invoked by `scripts/audio_embody.py` (present_voice speech mode): synthesize
//! `--text` with the selected backend and write a mono WAV to `--out`, then print a
//! one-line JSON status to stdout for the caller to parse. Kept a separate binary
//! (gated on the `kokoro` feature; `piper` adds the second engine) so the heavy
//! `ort`/ONNX-Runtime link lives here and never in the `agent-bridge` daemon.
//!
//! ```text
//! ab-tts-synth --text "Hello." --out /tmp/x.wav [--backend kokoro|piper] [--voice af_sarah] [--speed 1.0] [--british]
//! ```
//! - `kokoro` (default, 24 kHz): env `AB_TTS_KOKORO_MODEL` / `AB_TTS_KOKORO_VOICES`.
//! - `piper` (22.05 kHz, opt-in `piper` feature): env `AB_TTS_PIPER_MODEL` /
//!   `AB_TTS_PIPER_PHONEMIZE` (single-voice model — `--voice`/`--speed` ignored).
//! On failure: a JSON `{"ok":false,"error":…}` on stdout + non-zero exit. A
//! `--backend piper` request errors honestly if the bin was not built with `piper`.

use ab_tts::kokoro::KokoroBackend;
use ab_tts::AudioBuf;
use std::process::exit;

fn fail(msg: String) -> ! {
    // machine-readable on stdout (caller parses stdout), human hint on stderr
    println!("{{\"ok\":false,\"error\":{}}}", json_str(&msg));
    eprintln!("ab-tts-synth: {msg}");
    exit(1);
}

/// Minimal JSON string escaper (no serde dependency in this crate).
fn json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn main() {
    let mut text: Option<String> = None;
    let mut voice = "af_sarah".to_string();
    let mut out: Option<String> = None;
    let mut speed = 1.0f32;
    let mut british = false;
    let mut backend = "kokoro".to_string();

    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--text" => text = args.next(),
            "--backend" => backend = args.next().unwrap_or(backend),
            "--voice" => voice = args.next().unwrap_or(voice),
            "--out" => out = args.next(),
            "--speed" => {
                speed = args
                    .next()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(speed)
                    .clamp(0.5, 2.0)
            }
            "--british" => british = true,
            other => {
                // first bare arg is treated as the text, for ergonomics
                if text.is_none() && !other.starts_with("--") {
                    text = Some(other.to_string());
                } else {
                    fail(format!("unknown argument {other:?}"));
                }
            }
        }
    }

    let text = text.unwrap_or_else(|| fail("missing --text".into()));
    let out = out.unwrap_or_else(|| fail("missing --out".into()));
    if text.trim().is_empty() {
        fail("empty --text".into());
    }

    let (audio, eff_voice): (AudioBuf, String) = match backend.as_str() {
        "kokoro" => {
            let b = match KokoroBackend::from_cache(british) {
                Ok(b) => b,
                Err(e) => fail(format!("load kokoro backend: {e}")),
            };
            match b.synthesize_at(&text, &voice, speed) {
                Ok(a) => (a, voice.clone()),
                Err(e) => fail(format!("kokoro synthesize: {e}")),
            }
        }
        "piper" => synth_piper(&text),
        other => fail(format!("unknown --backend {other:?} (expected kokoro|piper)")),
    };
    if let Err(e) = audio.write_wav(&out) {
        fail(format!("write wav {out}: {e}"));
    }

    // one-line JSON status for the caller (audio_embody.py)
    println!(
        "{{\"ok\":true,\"backend\":{},\"voice\":{},\"out\":{},\"samples\":{},\"sample_rate\":{},\"dur_s\":{:.4},\"rms\":{:.4}}}",
        json_str(&backend),
        json_str(&eff_voice),
        json_str(&out),
        audio.samples.len(),
        audio.sample_rate,
        audio.duration_secs(),
        audio.rms()
    );
}

/// Synthesize via the Piper backend (single-voice model; `--voice`/`--speed` do
/// not apply). cfg-gated: when the bin is built without `piper`, the request fails
/// honestly rather than silently falling back to another engine.
#[cfg(feature = "piper")]
fn synth_piper(text: &str) -> (AudioBuf, String) {
    use ab_tts::piper::PiperBackend;
    use ab_tts::TtsBackend;
    let b = match PiperBackend::from_cache() {
        Ok(b) => b,
        Err(e) => fail(format!("load piper backend: {e}")),
    };
    let voice = b.voices().first().cloned().unwrap_or_default();
    match b.synthesize(text, &voice) {
        Ok(a) => (a, voice),
        Err(e) => fail(format!("piper synthesize: {e}")),
    }
}

#[cfg(not(feature = "piper"))]
fn synth_piper(_text: &str) -> (AudioBuf, String) {
    fail("--backend piper requested but this ab-tts-synth was not built with the `piper` feature".into())
}
