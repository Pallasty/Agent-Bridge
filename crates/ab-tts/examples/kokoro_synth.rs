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
use std::io::Write;

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
    if let Err(e) = write_wav(&out, &audio.to_i16(), audio.sample_rate) {
        eprintln!("write wav {out}: {e}");
        std::process::exit(4);
    }
    println!("wrote {out}");
}

/// Minimal canonical 16-bit mono PCM WAV — hand-rolled to keep the dogfood free
/// of any encoder-dependency ambiguity.
fn write_wav(path: &str, samples: &[i16], sr: u32) -> std::io::Result<()> {
    let mut f = std::fs::File::create(path)?;
    let data_len = (samples.len() * 2) as u32;
    f.write_all(b"RIFF")?;
    f.write_all(&(36 + data_len).to_le_bytes())?;
    f.write_all(b"WAVE")?;
    f.write_all(b"fmt ")?;
    f.write_all(&16u32.to_le_bytes())?; // PCM fmt chunk size
    f.write_all(&1u16.to_le_bytes())?; // audio format = PCM
    f.write_all(&1u16.to_le_bytes())?; // channels = mono
    f.write_all(&sr.to_le_bytes())?;
    f.write_all(&(sr * 2).to_le_bytes())?; // byte rate
    f.write_all(&2u16.to_le_bytes())?; // block align
    f.write_all(&16u16.to_le_bytes())?; // bits/sample
    f.write_all(b"data")?;
    f.write_all(&data_len.to_le_bytes())?;
    for &s in samples {
        f.write_all(&s.to_le_bytes())?;
    }
    Ok(())
}
