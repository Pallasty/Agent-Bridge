//! Dogfood: synthesize a sentence with the Piper backend → write a WAV, and report
//! duration / RMS / real-time-factor. End-to-end proof that the `piper_phonemize`
//! CLI → phoneme ids → `ort` VITS forward path produces real 22.05 kHz audio.
//!
//! Needs the piper voice + the piper_phonemize dist (not vendored). Point env at
//! them, e.g.:
//! ```text
//! AB_TTS_PIPER_MODEL=/tmp/tts-eval/voices/en_US-lessac-medium.onnx \
//! AB_TTS_PIPER_PHONEMIZE=/tmp/tts-eval/piper/piper_phonemize \
//! cargo run -p ab-tts --features piper --example piper_synth -- "Some text."
//! ```
//! Optional: `AB_TTS_PIPER_LIBDIR` / `AB_TTS_PIPER_ESPEAK_DATA` (default: derived
//! from the phonemize bin dir), `AB_TTS_PIPER_LANG` (default `en-us`),
//! `AB_TTS_OUT` (default `/tmp/ab-piper-rust.wav`).

use ab_tts::piper::PiperBackend;
use ab_tts::TtsBackend;

fn main() {
    let text = std::env::args().nth(1).unwrap_or_else(|| {
        "Hello. This is Piper, speaking from agent bridge, synthesized in Rust.".to_string()
    });

    let backend = match PiperBackend::from_cache() {
        Ok(b) => b,
        Err(e) => {
            eprintln!("load failed:\n{e}");
            std::process::exit(2);
        }
    };
    let voice = backend.voices().first().cloned().unwrap_or_default();
    eprintln!(
        "backend={} sample_rate={} voice={voice}",
        backend.id(),
        backend.sample_rate()
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

    let out = std::env::var("AB_TTS_OUT").unwrap_or_else(|_| "/tmp/ab-piper-rust.wav".to_string());
    if let Err(e) = audio.write_wav(&out) {
        eprintln!("write wav {out}: {e}");
        std::process::exit(4);
    }
    println!("wrote {out}");
}
