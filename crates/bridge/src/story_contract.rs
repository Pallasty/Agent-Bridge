//! Pure, non-actuating contracts shared by the native `/story` path.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use thiserror::Error;

const SUPPORTED_SOURCE_SUFFIXES: [&str; 3] = [".txt", ".md", ".markdown"];

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum StoryStart {
    FromStart,
    Chapter { chapter: u32 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StoryRequest {
    pub source_path: String,
    pub start: StoryStart,
    pub dry_run: bool,
}

impl StoryRequest {
    pub fn validate(&self) -> Result<(), StoryContractError> {
        if self.source_path.trim().is_empty() {
            return Err(StoryContractError::InvalidRequest("source_path_empty"));
        }

        let lowercase_path = self.source_path.to_lowercase();
        if !SUPPORTED_SOURCE_SUFFIXES
            .iter()
            .any(|suffix| lowercase_path.ends_with(suffix))
        {
            return Err(StoryContractError::InvalidRequest(
                "story_source_suffix_unsupported",
            ));
        }
        if !self.dry_run {
            return Err(StoryContractError::InvalidRequest(
                "story_rust_contract_core_requires_dry_run",
            ));
        }
        if matches!(self.start, StoryStart::Chapter { chapter: 0 }) {
            return Err(StoryContractError::InvalidRequest(
                "story_chapter_must_be_positive_integer",
            ));
        }

        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SegmentCacheKeyInput {
    pub source_sha256: String,
    pub voice_plan_sha256: String,
    pub event_id: String,
    pub text: String,
    pub qwen_speaker: String,
    pub style_instruction: String,
    pub voice_profile_version: u32,
    pub model_inference_sha256: String,
}

impl SegmentCacheKeyInput {
    fn validate(&self) -> Result<(), StoryContractError> {
        for (field, value) in [
            ("source_sha256", self.source_sha256.as_str()),
            ("voice_plan_sha256", self.voice_plan_sha256.as_str()),
            (
                "model_inference_sha256",
                self.model_inference_sha256.as_str(),
            ),
        ] {
            if !is_lowercase_sha256(value) {
                return Err(StoryContractError::InvalidCacheKey(field));
            }
        }
        for (field, value) in [
            ("event_id", self.event_id.as_str()),
            ("text", self.text.as_str()),
            ("qwen_speaker", self.qwen_speaker.as_str()),
            ("style_instruction", self.style_instruction.as_str()),
        ] {
            if value.trim().is_empty() {
                return Err(StoryContractError::InvalidCacheKey(field));
            }
        }
        if self.voice_profile_version == 0 {
            return Err(StoryContractError::InvalidCacheKey("voice_profile_version"));
        }
        Ok(())
    }
}

#[derive(Debug, Error)]
pub enum StoryContractError {
    #[error("invalid story request: {0}")]
    InvalidRequest(&'static str),
    #[error("invalid segment cache key field: {0}")]
    InvalidCacheKey(&'static str),
    #[error("cannot serialize canonical JSON: {0}")]
    Json(#[from] serde_json::Error),
}

/// Serialize JSON with recursively sorted object keys, compact separators, and UTF-8 text.
pub fn canonical_json(value: &Value) -> Result<String, StoryContractError> {
    Ok(serde_json::to_string(&canonicalize(value))?)
}

/// Hash the exact UTF-8 bytes returned by [`canonical_json`].
pub fn sha256_canonical_json(value: &Value) -> Result<String, StoryContractError> {
    let canonical = canonical_json(value)?;
    Ok(hex_sha256(canonical.as_bytes()))
}

/// Produce the S5ZF-compatible segment cache key without reading files or actuating audio.
pub fn segment_cache_key(input: &SegmentCacheKeyInput) -> Result<String, StoryContractError> {
    input.validate()?;
    sha256_canonical_json(&serde_json::to_value(input)?)
}

fn canonicalize(value: &Value) -> Value {
    match value {
        Value::Object(object) => {
            let sorted = object
                .iter()
                .map(|(key, value)| (key.clone(), canonicalize(value)))
                .collect::<BTreeMap<_, _>>();
            Value::Object(sorted.into_iter().collect::<Map<_, _>>())
        }
        Value::Array(values) => Value::Array(values.iter().map(canonicalize).collect()),
        _ => value.clone(),
    }
}

fn is_lowercase_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn hex_sha256(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}
