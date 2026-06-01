//! # ab-tts — pluggable offline Rust TTS for the audio-embodiment lane
//!
//! Houses the text-to-speech backends behind `present_voice` (output-expression
//! lane, audio domain). Two backends, one trait:
//!
//! - **Kokoro-82M** (StyleTTS2, Apache-2.0, 24 kHz) — `misaki-rs` g2p + `ort` ONNX.
//! - **Piper** (VITS, MIT, 22.05 kHz) — `espeak-ng` phonemes + `ort` ONNX.
//!
//! Design decisions (forum #92):
//! - **Inference via `ort`** (ONNX Runtime) — the compute-dense forward pass is
//!   *run*, not rewritten.
//! - **Grapheme→phoneme in pure Rust** (`misaki-rs` / `espeak-ng`) — no Python
//!   (misaki) or C (espeak-ng) system dependency; the lane owns the tokenizer.
//! - **Feature-gated**: the heavy `ort` native dependency is pulled ONLY when a
//!   backend feature (`kokoro` / `piper`) is enabled, so the core workspace and
//!   the default `agent-bridge` binary never carry the ONNX Runtime.
//!
//! The synthesized [`AudioBuf`] is played to a PipeWire sink and the lane's
//! bus-readback falsifier (see `scripts/audio_embody.py`) verifies, in *speech
//! mode* (energy + duration; later an STT round-trip), that the audio reached the
//! output bus — honest about the unverifiable last mile (physical transducer).

use std::fmt;

/// Mono audio: f32 samples in `[-1.0, 1.0]` plus the sample rate the backend
/// produced them at (Kokoro 24 kHz, Piper 22.05 kHz). Kept backend-agnostic so
/// the caller (and the bus-readback falsifier) never depends on which engine ran.
#[derive(Debug, Clone)]
pub struct AudioBuf {
    pub samples: Vec<f32>,
    pub sample_rate: u32,
}

impl AudioBuf {
    pub fn new(samples: Vec<f32>, sample_rate: u32) -> Self {
        Self { samples, sample_rate }
    }

    /// Wall-clock duration of the buffer — the value the speech-mode falsifier
    /// expects the captured bus signal to span.
    pub fn duration_secs(&self) -> f32 {
        if self.sample_rate == 0 {
            return 0.0;
        }
        self.samples.len() as f32 / self.sample_rate as f32
    }

    /// RMS amplitude — a cheap "is there real signal here" probe (0.0 = silent),
    /// used both as a sanity check on synthesis and as the speech-mode falsifier's
    /// energy floor.
    pub fn rms(&self) -> f32 {
        if self.samples.is_empty() {
            return 0.0;
        }
        let sum_sq: f64 = self.samples.iter().map(|&x| (x as f64) * (x as f64)).sum();
        (sum_sq / self.samples.len() as f64).sqrt() as f32
    }

    /// Clamp + scale to signed 16-bit PCM for WAV encode / PipeWire playback.
    pub fn to_i16(&self) -> Vec<i16> {
        self.samples
            .iter()
            .map(|&x| (x.clamp(-1.0, 1.0) * 32767.0) as i16)
            .collect()
    }
}

/// Why a synthesis attempt could not produce audio — surfaced honestly rather
/// than faked (mirrors the lane's never-claim-what-wasn't-done discipline).
#[derive(Debug)]
pub enum TtsError {
    /// Grapheme→phoneme conversion failed (g2p / tokenizer).
    Phonemize(String),
    /// The ONNX model could not be loaded (missing/corrupt asset).
    Model(String),
    /// The inference run itself failed.
    Inference(String),
    /// The requested voice is not available in the backend's voice pack.
    Voice(String),
    /// I/O (model/voice asset read, capture write, etc.).
    Io(String),
}

impl fmt::Display for TtsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TtsError::Phonemize(m) => write!(f, "phonemize: {m}"),
            TtsError::Model(m) => write!(f, "model: {m}"),
            TtsError::Inference(m) => write!(f, "inference: {m}"),
            TtsError::Voice(m) => write!(f, "voice: {m}"),
            TtsError::Io(m) => write!(f, "io: {m}"),
        }
    }
}

impl std::error::Error for TtsError {}

/// Text → phoneme string, in pure Rust. The phonemizer owns text→phoneme; each
/// backend owns the phoneme→token-id table (Kokoro's is a fixed ~178-symbol vocab;
/// Piper's is a per-voice map in the model's `.onnx.json`), so this surface returns
/// the IPA phoneme string and id-mapping lives backend-side. Kept a trait so
/// `misaki-rs` (Kokoro, MIT) and `espeak-ng` (Piper, GPL-3.0 — opt-in) plug in
/// behind the same surface and are unit-testable.
pub trait Phonemizer: Send + Sync {
    /// Convert text to an IPA phoneme string (with stress marks), e.g.
    /// `"hɛlˈəʊ wˈɜːld"`. Errors honestly on empty/failed g2p.
    fn phonemize(&self, text: &str) -> Result<String, TtsError>;
}

/// A synthesizer backend: text + voice → audio. Offline, no network at call time.
pub trait TtsBackend: Send + Sync {
    /// Stable id recorded in the outcome sidecar (`"kokoro"` | `"piper"`).
    fn id(&self) -> &'static str;
    /// Native output sample rate.
    fn sample_rate(&self) -> u32;
    /// Voice names this backend can render.
    fn voices(&self) -> Vec<String>;
    /// Synthesize `text` in `voice`. Errors are honest (see [`TtsError`]).
    fn synthesize(&self, text: &str, voice: &str) -> Result<AudioBuf, TtsError>;
}

#[cfg(feature = "kokoro")]
pub mod kokoro;
#[cfg(feature = "piper")]
pub mod piper;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn audiobuf_duration_and_silence() {
        let one_sec = AudioBuf::new(vec![0.0; 24_000], 24_000);
        assert!((one_sec.duration_secs() - 1.0).abs() < 1e-6);
        assert_eq!(one_sec.rms(), 0.0, "all-zero buffer is silent");
        // zero sample rate must not divide-by-zero
        assert_eq!(AudioBuf::new(vec![0.1; 10], 0).duration_secs(), 0.0);
        assert_eq!(AudioBuf::new(vec![], 24_000).rms(), 0.0);
    }

    #[test]
    fn audiobuf_rms_and_i16_clamp() {
        let buf = AudioBuf::new(vec![1.0, -1.0, 1.0, -1.0], 48_000);
        assert!((buf.rms() - 1.0).abs() < 1e-6, "full-scale square has rms 1.0");
        // out-of-range samples clamp, not wrap
        let clipped = AudioBuf::new(vec![2.0, -2.0], 48_000).to_i16();
        assert_eq!(clipped, vec![32767i16, -32767i16]);
    }
}
