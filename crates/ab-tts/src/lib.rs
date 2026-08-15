//! # ab-tts — pluggable offline Rust TTS for the audio-embodiment lane
//!
//! Houses the text-to-speech backends behind `present_voice` (output-expression
//! lane, audio domain). Two backends, one trait:
//!
//! - **Kokoro-82M** (StyleTTS2, Apache-2.0, 24 kHz) — `misaki-rs` g2p + `ort` ONNX.
//! - **Piper** (VITS, 22.05 kHz) — the `piper_phonemize` CLI (espeak-ng, GPL-3.0)
//!   + `ort` ONNX.
//! - **Sherpa VITS** (offline Chinese multi-speaker) — `sherpa-onnx`'s Rust API
//!   owns the model-specific Chinese frontend and ONNX execution.
//!
//! Design decisions (forum #92):
//! - **Inference via `ort`** (ONNX Runtime) — the compute-dense forward pass is
//!   *run*, not rewritten.
//! - **Grapheme→phoneme without linked C / `bindgen`**: Kokoro uses `misaki-rs`
//!   (pure Rust, MIT, GPL-free); Piper shells to the bundled `piper_phonemize` CLI
//!   (which links espeak-ng, GPL-3.0) the same way the lane shells to `whisper-cli`
//!   / `ffmpeg` — the GPL/C code stays in a subprocess, off the crate's link line.
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
        Self {
            samples,
            sample_rate,
        }
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

    /// Write this buffer as a canonical 16-bit mono PCM WAV — the format the
    /// audio-embodiment falsifier plays to the sink and reads back off the bus.
    /// Hand-rolled (no encoder dependency) so WAV output is always available,
    /// independent of which backend feature is enabled.
    pub fn write_wav(&self, path: impl AsRef<std::path::Path>) -> std::io::Result<()> {
        use std::io::Write as _;
        let samples = self.to_i16();
        let data_len = (samples.len() * 2) as u32;
        let mut f = std::io::BufWriter::new(std::fs::File::create(path)?);
        f.write_all(b"RIFF")?;
        f.write_all(&(36 + data_len).to_le_bytes())?;
        f.write_all(b"WAVE")?;
        f.write_all(b"fmt ")?;
        f.write_all(&16u32.to_le_bytes())?; // PCM fmt chunk size
        f.write_all(&1u16.to_le_bytes())?; // audio format = PCM
        f.write_all(&1u16.to_le_bytes())?; // channels = mono
        f.write_all(&self.sample_rate.to_le_bytes())?;
        f.write_all(&(self.sample_rate * 2).to_le_bytes())?; // byte rate (mono, 2 bytes/sample)
        f.write_all(&2u16.to_le_bytes())?; // block align
        f.write_all(&16u16.to_le_bytes())?; // bits/sample
        f.write_all(b"data")?;
        f.write_all(&data_len.to_le_bytes())?;
        for s in samples {
            f.write_all(&s.to_le_bytes())?;
        }
        f.flush()
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
#[cfg(feature = "sherpa")]
pub mod sherpa;

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
        assert!(
            (buf.rms() - 1.0).abs() < 1e-6,
            "full-scale square has rms 1.0"
        );
        // out-of-range samples clamp, not wrap
        let clipped = AudioBuf::new(vec![2.0, -2.0], 48_000).to_i16();
        assert_eq!(clipped, vec![32767i16, -32767i16]);
    }

    #[test]
    fn audiobuf_write_wav_has_canonical_header() {
        let buf = AudioBuf::new(vec![0.0, 0.5, -0.5, 1.0], 24_000);
        let path = std::env::temp_dir().join("ab_tts_write_wav_test.wav");
        buf.write_wav(&path).expect("write wav");
        let bytes = std::fs::read(&path).expect("read back");
        let _ = std::fs::remove_file(&path);
        // RIFF/WAVE magic, fmt fields, and data chunk for 4 mono s16 samples (8 bytes)
        assert_eq!(&bytes[0..4], b"RIFF");
        assert_eq!(&bytes[8..12], b"WAVE");
        assert_eq!(&bytes[12..16], b"fmt ");
        assert_eq!(u16::from_le_bytes([bytes[22], bytes[23]]), 1, "mono");
        assert_eq!(
            u32::from_le_bytes([bytes[24], bytes[25], bytes[26], bytes[27]]),
            24_000,
            "sample rate"
        );
        assert_eq!(
            u16::from_le_bytes([bytes[34], bytes[35]]),
            16,
            "bits/sample"
        );
        assert_eq!(&bytes[36..40], b"data");
        assert_eq!(
            u32::from_le_bytes([bytes[40], bytes[41], bytes[42], bytes[43]]),
            8,
            "4 samples * 2 bytes"
        );
        assert_eq!(bytes.len(), 44 + 8, "header + data");
    }
}
