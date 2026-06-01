//! Kokoro-82M backend (StyleTTS2, Apache-2.0 model, 24 kHz output).
//!
//! **MIT-clean path:** grapheme→phoneme via `misaki-rs` (MIT) — Kokoro's own g2p
//! with embedded lexicons + POS-tagger weights (no runtime data files, no espeak,
//! no GPL). This is why Kokoro is the license-clean primary: the entire
//! text→phoneme→audio path stays MIT/Apache (misaki-rs MIT + ort MIT/Apache +
//! Kokoro model Apache-2.0).
//!
//! P1 (this): the phonemizer. P2: the `ort` ONNX inference (phoneme→id vocab,
//! voice-pack embedding, forward pass → [`crate::AudioBuf`]).

use crate::{Phonemizer, TtsError};
use misaki_rs::{Language, G2P};

/// Kokoro grapheme→phoneme via `misaki-rs` (MIT, `default-features=false` → no
/// espeak/GPL/C). US English by default; set `british=true` for the `b*` voices.
/// Self-contained — embedded lexicon + POS tagger, no runtime data files.
/// Out-of-vocabulary words map to misaki's `❓` placeholder (no espeak fallback).
pub struct MisakiPhonemizer {
    g2p: G2P,
}

impl MisakiPhonemizer {
    /// `british=false` → US English (Kokoro `a*` voices); `true` → British (`b*`).
    pub fn new(british: bool) -> Self {
        let lang = if british {
            Language::EnglishGB
        } else {
            Language::EnglishUS
        };
        Self { g2p: G2P::new(lang) }
    }
}

impl Default for MisakiPhonemizer {
    fn default() -> Self {
        Self::new(false)
    }
}

impl Phonemizer for MisakiPhonemizer {
    fn phonemize(&self, text: &str) -> Result<String, TtsError> {
        if text.trim().is_empty() {
            return Err(TtsError::Phonemize("empty input text".into()));
        }
        let (phonemes, _tokens) = self
            .g2p
            .g2p(text)
            .map_err(|e| TtsError::Phonemize(format!("misaki g2p: {e}")))?;
        if phonemes.trim().is_empty() {
            return Err(TtsError::Phonemize(format!(
                "misaki produced no phonemes for {text:?}"
            )));
        }
        Ok(phonemes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn misaki_phonemizes_english() {
        let p = MisakiPhonemizer::new(false);
        let ph = p.phonemize("hello world").expect("phonemes");
        assert!(!ph.trim().is_empty(), "expected non-empty phonemes");
        // both "hello" and "world" carry an /l/; cheap, non-brittle presence check
        assert!(ph.contains('l'), "expected an l phoneme, got: {ph:?}");
    }

    #[test]
    fn empty_input_is_honest_error() {
        let p = MisakiPhonemizer::new(false);
        assert!(p.phonemize("").is_err());
        assert!(p.phonemize("   ").is_err());
    }
}
