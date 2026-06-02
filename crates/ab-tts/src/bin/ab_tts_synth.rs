//! `ab-tts-synth` — production text→WAV CLI for the audio-embodiment lane.
//!
//! Invoked by `scripts/audio_embody.py` (present_voice speech mode): synthesize
//! `--text` with the Kokoro backend and write a 24 kHz mono WAV to `--out`, then
//! print a one-line JSON status to stdout for the caller to parse. Kept a separate
//! binary (gated on the `kokoro` feature) so the heavy `ort`/ONNX-Runtime link
//! lives here and never in the `agent-bridge` daemon.
//!
//! ```text
//! ab-tts-synth --text "Hello." --voice af_sarah --out /tmp/x.wav [--speed 1.0] [--british]
//! ```
//! Model + voice pack are resolved offline from env (`AB_TTS_KOKORO_MODEL`,
//! `AB_TTS_KOKORO_VOICES`) or the cache dir (see `KokoroBackend::from_cache`).
//! On failure: a JSON `{"ok":false,"error":…}` on stdout + non-zero exit.

use ab_tts::kokoro::KokoroBackend;
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

    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--text" => text = args.next(),
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

    let backend = match KokoroBackend::from_cache(british) {
        Ok(b) => b,
        Err(e) => fail(format!("load backend: {e}")),
    };
    let audio = match backend.synthesize_at(&text, &voice, speed) {
        Ok(a) => a,
        Err(e) => fail(format!("synthesize: {e}")),
    };
    if let Err(e) = audio.write_wav(&out) {
        fail(format!("write wav {out}: {e}"));
    }

    // one-line JSON status for the caller (audio_embody.py)
    println!(
        "{{\"ok\":true,\"voice\":{},\"out\":{},\"samples\":{},\"sample_rate\":{},\"dur_s\":{:.4},\"rms\":{:.4}}}",
        json_str(&voice),
        json_str(&out),
        audio.samples.len(),
        audio.sample_rate,
        audio.duration_secs(),
        audio.rms()
    );
}
