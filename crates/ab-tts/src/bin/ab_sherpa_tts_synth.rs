//! CLI bridge for an offline Sherpa-ONNX Chinese VITS model.
//!
//! Required environment: `AB_TTS_SHERPA_MODEL_DIR` and
//! `AB_TTS_SHERPA_VOICE_MAP` (for example `male_standard=7,female_standard=18`).

use ab_tts::sherpa::{SherpaVitsBackend, SherpaVitsConfig};
use std::path::PathBuf;
use std::process::exit;

fn fail(message: impl AsRef<str>) -> ! {
    let message = message.as_ref().replace('"', "\\\"");
    println!("{{\"ok\":false,\"error\":\"{message}\"}}");
    exit(1);
}

fn main() {
    let mut text = None;
    let mut out = None;
    let mut voice = "narrator_calm".to_owned();
    let mut speed = 1.0_f32;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--text" => text = args.next(),
            "--out" => out = args.next(),
            "--voice" => voice = args.next().unwrap_or(voice),
            "--speed" => speed = args.next().and_then(|v| v.parse().ok()).unwrap_or(speed),
            other => fail(format!("unknown argument {other:?}")),
        }
    }
    let text = text.unwrap_or_else(|| fail("missing --text"));
    let out = out.unwrap_or_else(|| fail("missing --out"));
    let model_dir = std::env::var("AB_TTS_SHERPA_MODEL_DIR")
        .unwrap_or_else(|_| fail("AB_TTS_SHERPA_MODEL_DIR is required"));
    let voice_map = std::env::var("AB_TTS_SHERPA_VOICE_MAP").unwrap_or_else(|_| {
        fail("AB_TTS_SHERPA_VOICE_MAP is required; use explicit name=sid entries")
    });
    let voices =
        SherpaVitsConfig::parse_voice_map(&voice_map).unwrap_or_else(|e| fail(e.to_string()));
    let backend = SherpaVitsBackend::from_config(SherpaVitsConfig {
        model_dir: PathBuf::from(model_dir),
        voice_map: voices,
        num_threads: 4,
        noise_scale: 0.667,
        noise_scale_w: 0.8,
        silence_scale: 0.2,
    })
    .unwrap_or_else(|e| fail(e.to_string()));
    let audio = backend
        .synthesize_with_speed(&text, &voice, speed)
        .unwrap_or_else(|e| fail(e.to_string()));
    audio
        .write_wav(&out)
        .unwrap_or_else(|e| fail(format!("write wav: {e}")));
    println!("{{\"ok\":true,\"backend\":\"sherpa-vits\",\"voice\":\"{}\",\"out\":\"{}\",\"samples\":{},\"sample_rate\":{},\"speakers\":{}}}", voice, out, audio.samples.len(), audio.sample_rate, backend.model_num_speakers().unwrap_or(-1));
}
