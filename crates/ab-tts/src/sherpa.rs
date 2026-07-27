//! Offline Chinese multi-speaker VITS via the official `sherpa-onnx` Rust API.
//!
//! The initial supported asset is `vits-icefall-zh-aishell3`: it ships the ONNX
//! graph, Chinese lexicon/tokens and three rule FSTs as one self-contained model
//! directory. Speaker gender is deliberately *not* inferred from a numeric `sid`.
//! The caller supplies an explicit, auditioned voice-to-sid map.

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::Mutex;

use sherpa_onnx::{
    GenerationConfig, OfflineTts, OfflineTtsConfig, OfflineTtsModelConfig,
    OfflineTtsVitsModelConfig,
};

use crate::{AudioBuf, TtsBackend, TtsError};

const REQUIRED_ASSETS: &[&str] = &[
    "model.onnx",
    "lexicon.txt",
    "tokens.txt",
    "phone.fst",
    "date.fst",
    "number.fst",
];

/// Explicit, audited configuration for a Sherpa Chinese VITS model directory.
#[derive(Clone, Debug)]
pub struct SherpaVitsConfig {
    pub model_dir: PathBuf,
    pub voice_map: BTreeMap<String, i32>,
    pub num_threads: i32,
    pub noise_scale: f32,
    pub noise_scale_w: f32,
    pub silence_scale: f32,
}

impl SherpaVitsConfig {
    /// Parse `name=sid,name=sid`; duplicate names and negative IDs are rejected.
    pub fn parse_voice_map(value: &str) -> Result<BTreeMap<String, i32>, TtsError> {
        let mut voices = BTreeMap::new();
        for item in value.split(',').filter(|item| !item.trim().is_empty()) {
            let (name, sid) = item.split_once('=').ok_or_else(|| {
                TtsError::Voice(format!(
                    "invalid voice map entry {item:?}; expected name=sid"
                ))
            })?;
            let name = name.trim();
            let sid = sid
                .trim()
                .parse::<i32>()
                .map_err(|_| TtsError::Voice(format!("invalid sid in voice map entry {item:?}")))?;
            if name.is_empty() || sid < 0 || voices.insert(name.to_owned(), sid).is_some() {
                return Err(TtsError::Voice(format!(
                    "invalid or duplicate voice map entry {item:?}"
                )));
            }
        }
        if voices.is_empty() {
            return Err(TtsError::Voice(
                "voice map must contain at least one name=sid entry".into(),
            ));
        }
        Ok(voices)
    }

    fn validate_assets(&self) -> Result<(), TtsError> {
        for name in REQUIRED_ASSETS {
            let path = self.model_dir.join(name);
            if !path.is_file() {
                return Err(TtsError::Model(format!(
                    "missing Sherpa VITS asset: {}",
                    path.display()
                )));
            }
        }
        Ok(())
    }
}

/// Thread-serialized Sherpa VITS engine. Generation parameters remain per-call.
pub struct SherpaVitsBackend {
    tts: Mutex<OfflineTts>,
    voices: BTreeMap<String, i32>,
}

impl SherpaVitsBackend {
    pub fn from_config(config: SherpaVitsConfig) -> Result<Self, TtsError> {
        config.validate_assets()?;
        let fsts = ["phone.fst", "date.fst", "number.fst"]
            .iter()
            .map(|name| config.model_dir.join(name).display().to_string())
            .collect::<Vec<_>>()
            .join(",");
        let tts = OfflineTts::create(&OfflineTtsConfig {
            model: OfflineTtsModelConfig {
                vits: OfflineTtsVitsModelConfig {
                    model: Some(config.model_dir.join("model.onnx").display().to_string()),
                    lexicon: Some(config.model_dir.join("lexicon.txt").display().to_string()),
                    tokens: Some(config.model_dir.join("tokens.txt").display().to_string()),
                    noise_scale: config.noise_scale,
                    noise_scale_w: config.noise_scale_w,
                    ..Default::default()
                },
                num_threads: config.num_threads.max(1),
                ..Default::default()
            },
            rule_fsts: Some(fsts),
            silence_scale: config.silence_scale.max(0.0),
            ..Default::default()
        })
        .ok_or_else(|| TtsError::Model("sherpa-onnx rejected VITS configuration".into()))?;
        Ok(Self {
            tts: Mutex::new(tts),
            voices: config.voice_map,
        })
    }

    pub fn synthesize_with_speed(
        &self,
        text: &str,
        voice: &str,
        speed: f32,
    ) -> Result<AudioBuf, TtsError> {
        if text.trim().is_empty() {
            return Err(TtsError::Inference("empty text".into()));
        }
        let sid = *self
            .voices
            .get(voice)
            .ok_or_else(|| TtsError::Voice(format!("unknown Sherpa voice {voice:?}")))?;
        let tts = self
            .tts
            .lock()
            .map_err(|_| TtsError::Inference("Sherpa TTS lock poisoned".into()))?;
        let generated = tts
            .generate_with_config(
                text,
                &GenerationConfig {
                    sid,
                    speed: speed.clamp(0.5, 2.0),
                    ..Default::default()
                },
                None::<fn(&[f32], f32) -> bool>,
            )
            .ok_or_else(|| TtsError::Inference("Sherpa VITS generation failed".into()))?;
        let samples = generated.samples().to_vec();
        if samples.is_empty() {
            return Err(TtsError::Inference(
                "Sherpa VITS returned empty audio".into(),
            ));
        }
        Ok(AudioBuf::new(
            samples,
            generated.sample_rate().max(0) as u32,
        ))
    }

    pub fn model_num_speakers(&self) -> Result<i32, TtsError> {
        self.tts
            .lock()
            .map(|tts| tts.num_speakers())
            .map_err(|_| TtsError::Inference("Sherpa TTS lock poisoned".into()))
    }
}

impl TtsBackend for SherpaVitsBackend {
    fn id(&self) -> &'static str {
        "sherpa-vits"
    }
    fn sample_rate(&self) -> u32 {
        self.tts
            .lock()
            .map(|tts| tts.sample_rate().max(0) as u32)
            .unwrap_or(0)
    }
    fn voices(&self) -> Vec<String> {
        self.voices.keys().cloned().collect()
    }
    fn synthesize(&self, text: &str, voice: &str) -> Result<AudioBuf, TtsError> {
        self.synthesize_with_speed(text, voice, 1.0)
    }
}

#[cfg(test)]
mod tests {
    use super::SherpaVitsConfig;

    #[test]
    fn parses_explicit_voice_map() {
        let map = SherpaVitsConfig::parse_voice_map(
            "male_standard=7,female_standard=18,narrator_calm=42",
        )
        .unwrap();
        assert_eq!(map.get("female_standard"), Some(&18));
    }

    #[test]
    fn rejects_unsafe_voice_map_entries() {
        assert!(SherpaVitsConfig::parse_voice_map("male=-1").is_err());
        assert!(SherpaVitsConfig::parse_voice_map("male=1,male=2").is_err());
    }
}
