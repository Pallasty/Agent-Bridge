//! Dogfood: synthesize a sentence with the Kokoro backend → write a WAV, and
//! report duration / RMS / real-time-factor. This is the end-to-end proof that
//! the misaki g2p → fixed vocab → `ort` ONNX forward path produces real audio.
//!
//! Needs the model + voice pack (not vendored). Point env at them, e.g.:
//! ```text
//! AB_TTS_KOKORO_MODEL=/tmp/tts-eval/kokoro-v1.0.onnx \
//! AB_TTS_KOKORO_VOICES=/tmp/tts-eval/voices-v1.0.bin \
//! cargo run -p ab-tts --features kokoro --example kokoro_synth -- "Some text."
//! ```
//! Optional: `AB_TTS_VOICE` (default `af_sarah`), `AB_TTS_OUT` (default
//! `/tmp/ab-kokoro-rust.wav`).

use ab_tts::kokoro::KokoroBackend;
use ab_tts::TtsBackend;

fn main() {
    let text = std::env::args().nth(1).unwrap_or_else(|| {
        "Hello. This is Kokoro, speaking from agent bridge, synthesized in Rust.".to_string()
    });
    let voice = std::env::var("AB_TTS_VOICE").unwrap_or_else(|_| "af_sarah".to_string());

    let backend = match KokoroBackend::from_cache(false) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("load failed:\n{e}");
            std::process::exit(2);
        }
    };
    eprintln!(
        "backend={} sample_rate={} voices={}",
        backend.id(),
        backend.sample_rate(),
        backend.voices().len()
    );

    let t0 = std::time::Instant::now();
    let audio = match backend.synthesize(&text, &voice) {
        Ok(a) => a,
        Err(e) => {
            eprintln!("synth failed: {e}");
            std::process::exit(3);
        }
    };
    let wall = t0.elapsed().as_secs_f32();
    let dur = audio.duration_secs();
    println!(
        "synth ok: voice={voice} text_chars={} samples={} dur={dur:.2}s rms={:.4} wall={wall:.2}s rtf={:.2}",
        text.len(),
        audio.samples.len(),
        audio.rms(),
        wall / dur.max(1e-6)
    );

    let out = std::env::var("AB_TTS_OUT").unwrap_or_else(|_| "/tmp/ab-kokoro-rust.wav".to_string());
    if let Err(e) = audio.write_wav(&out) {
        eprintln!("write wav {out}: {e}");
        std::process::exit(4);
    }
    println!("wrote {out}");
}
