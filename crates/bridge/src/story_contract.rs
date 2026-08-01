//! Pure, non-actuating contracts shared by the native `/story` path.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, HashSet},
    fs::{self, File},
    io::Read,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
};
use thiserror::Error;
use tokio::sync::Notify;

const SUPPORTED_SOURCE_SUFFIXES: [&str; 3] = [".txt", ".md", ".markdown"];
pub const MAX_STORY_SOURCE_BYTES: u64 = 16 * 1024 * 1024;
const READ_CHUNK_BYTES: usize = 64 * 1024;

#[derive(Debug, Clone)]
pub struct StorySourcePolicy {
    pub allowed_root: PathBuf,
    pub max_bytes: u64,
}

#[derive(Debug, Clone)]
pub struct EvidenceFileSpec {
    pub path: PathBuf,
    pub sha256: String,
}

#[derive(Debug, Clone)]
pub struct StoryEvidenceBundleConfig {
    pub voice_plan: EvidenceFileSpec,
    pub mapping: EvidenceFileSpec,
    pub role_acceptance: EvidenceFileSpec,
    pub continuity_acceptance: EvidenceFileSpec,
    pub allowed_root: PathBuf,
    pub max_file_bytes: u64,
}

#[derive(Debug, Clone)]
pub struct StoryEvidenceBundle {
    pub voice_plan: Value,
    pub mapping: Value,
    pub role_acceptance: Value,
    pub continuity_acceptance: Value,
}

#[derive(Debug, Default)]
pub struct StoryPreflightCancellation {
    cancelled: AtomicBool,
    notify: Notify,
}

impl StoryPreflightCancellation {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn cancel(&self) {
        self.cancelled.store(true, Ordering::Release);
        self.notify.notify_one();
    }

    fn check(&self) -> Result<(), StoryContractError> {
        if self.cancelled.load(Ordering::Acquire) {
            Err(StoryContractError::Cancelled)
        } else {
            Ok(())
        }
    }

    async fn cancelled(&self) {
        loop {
            if self.cancelled.load(Ordering::Acquire) {
                return;
            }
            self.notify.notified().await;
        }
    }
}

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

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StorySource {
    pub source_id: String,
    pub kind: String,
    pub format: String,
    pub uri: String,
    pub sha256: String,
    pub version: String,
    pub encoding: String,
    pub byte_length: usize,
    pub char_length: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceSpan {
    pub source_id: String,
    pub line_start: usize,
    pub line_end: usize,
    pub char_start: usize,
    pub char_end: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StoryChapter {
    pub chapter_id: String,
    pub ordinal: u32,
    pub title: String,
    pub selected: bool,
    pub source_span: SourceSpan,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StorySelection {
    pub first_chapter: u32,
    pub selected_chapter_ids: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StorySourceIngest {
    pub source: StorySource,
    pub selection: StorySelection,
    pub chapters: Vec<StoryChapter>,
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
    #[error("story source error: {0}")]
    InvalidSource(String),
    #[error("story voice plan error: {0}")]
    InvalidVoicePlan(String),
    #[error("story preflight error: {0}")]
    InvalidPreflight(String),
    #[error("cannot read story source {path}: {source}")]
    SourceIo {
        path: String,
        #[source]
        source: std::io::Error,
    },
    #[error("cannot serialize canonical JSON: {0}")]
    Json(#[from] serde_json::Error),
    #[error("story preflight cancelled")]
    Cancelled,
    #[error("story preflight worker failed: {0}")]
    Worker(String),
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

/// Read and index a UTF-8 TXT/Markdown source without producing a full story plan.
pub fn ingest_story_source(
    path: &Path,
    start: &StoryStart,
) -> Result<StorySourceIngest, StoryContractError> {
    let source_bytes = fs::read(path).map_err(|source| StoryContractError::SourceIo {
        path: path.display().to_string(),
        source,
    })?;
    build_story_source_ingest(path, start, source_bytes)
}

/// Read a story only after canonical-root and byte-ceiling admission.
pub fn ingest_story_source_with_policy(
    path: &Path,
    start: &StoryStart,
    policy: &StorySourcePolicy,
    cancellation: &StoryPreflightCancellation,
) -> Result<StorySourceIngest, StoryContractError> {
    let source_bytes = read_admitted_file(
        path,
        &policy.allowed_root,
        policy.max_bytes.min(MAX_STORY_SOURCE_BYTES),
        cancellation,
        "story_source",
    )?;
    build_story_source_ingest(path, start, source_bytes)
}

fn build_story_source_ingest(
    path: &Path,
    start: &StoryStart,
    source_bytes: Vec<u8>,
) -> Result<StorySourceIngest, StoryContractError> {
    let suffix = path
        .extension()
        .and_then(|value| value.to_str())
        .map(|value| format!(".{}", value.to_lowercase()))
        .unwrap_or_default();
    if !SUPPORTED_SOURCE_SUFFIXES.contains(&suffix.as_str()) {
        return Err(StoryContractError::InvalidSource(format!(
            "unsupported_story_source:{}",
            if suffix.is_empty() { "<none>" } else { &suffix }
        )));
    }

    let text = std::str::from_utf8(&source_bytes)
        .map_err(|_| StoryContractError::InvalidSource("story_source_must_be_utf8".into()))?;
    let source_sha256 = hex_sha256(&source_bytes);
    let source_id = deterministic_id(
        "source",
        &serde_json::json!({"sha256": &source_sha256, "version": "source-v1"}),
    )?;
    let mut chapters = index_chapters(text, &source_id)?;
    let first_chapter = match start {
        StoryStart::FromStart => chapters[0].ordinal,
        StoryStart::Chapter { chapter } if chapters.iter().any(|row| row.ordinal == *chapter) => {
            *chapter
        }
        StoryStart::Chapter { chapter } => {
            return Err(StoryContractError::InvalidSource(format!(
                "story_chapter_not_found:{chapter}"
            )));
        }
    };
    for chapter in &mut chapters {
        chapter.selected = chapter.ordinal >= first_chapter;
    }
    let selected_chapter_ids = chapters
        .iter()
        .filter(|chapter| chapter.selected)
        .map(|chapter| chapter.chapter_id.clone())
        .collect();
    let absolute_path = path
        .canonicalize()
        .map_err(|source| StoryContractError::SourceIo {
            path: path.display().to_string(),
            source,
        })?;

    Ok(StorySourceIngest {
        source: StorySource {
            source_id,
            kind: "novel".into(),
            format: suffix.trim_start_matches('.').into(),
            uri: absolute_path.display().to_string(),
            sha256: source_sha256,
            version: "source-v1".into(),
            encoding: "utf-8".into(),
            byte_length: source_bytes.len(),
            char_length: text.chars().count(),
        },
        selection: StorySelection {
            first_chapter,
            selected_chapter_ids,
        },
        chapters,
    })
}

fn read_admitted_file(
    path: &Path,
    allowed_root: &Path,
    max_bytes: u64,
    cancellation: &StoryPreflightCancellation,
    label: &str,
) -> Result<Vec<u8>, StoryContractError> {
    cancellation.check()?;
    if max_bytes == 0 {
        return Err(StoryContractError::InvalidSource(format!(
            "{label}_byte_limit_invalid"
        )));
    }
    let canonical_root =
        allowed_root
            .canonicalize()
            .map_err(|source| StoryContractError::SourceIo {
                path: allowed_root.display().to_string(),
                source,
            })?;
    let canonical_path = path
        .canonicalize()
        .map_err(|source| StoryContractError::SourceIo {
            path: path.display().to_string(),
            source,
        })?;
    if !canonical_path.starts_with(&canonical_root) {
        return Err(StoryContractError::InvalidSource(format!(
            "{label}_outside_allowed_root"
        )));
    }
    let metadata = canonical_path
        .metadata()
        .map_err(|source| StoryContractError::SourceIo {
            path: canonical_path.display().to_string(),
            source,
        })?;
    if !metadata.is_file() {
        return Err(StoryContractError::InvalidSource(format!(
            "{label}_not_regular_file"
        )));
    }
    if metadata.len() > max_bytes {
        return Err(StoryContractError::InvalidSource(format!(
            "{label}_byte_limit_exceeded"
        )));
    }

    let mut file = File::open(&canonical_path).map_err(|source| StoryContractError::SourceIo {
        path: canonical_path.display().to_string(),
        source,
    })?;
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    let mut chunk = [0_u8; READ_CHUNK_BYTES];
    loop {
        cancellation.check()?;
        let read = file
            .read(&mut chunk)
            .map_err(|source| StoryContractError::SourceIo {
                path: canonical_path.display().to_string(),
                source,
            })?;
        if read == 0 {
            break;
        }
        if bytes.len().saturating_add(read) > max_bytes as usize {
            return Err(StoryContractError::InvalidSource(format!(
                "{label}_byte_limit_exceeded"
            )));
        }
        bytes.extend_from_slice(&chunk[..read]);
    }
    cancellation.check()?;
    Ok(bytes)
}

pub fn resolve_story_evidence(
    config: &StoryEvidenceBundleConfig,
    cancellation: &StoryPreflightCancellation,
) -> Result<StoryEvidenceBundle, StoryContractError> {
    let resolve = |spec: &EvidenceFileSpec, label: &str| -> Result<Value, StoryContractError> {
        if !is_lowercase_sha256(&spec.sha256) {
            return preflight_error(&format!("{label} configured SHA-256 invalid"));
        }
        let bytes = read_admitted_file(
            &spec.path,
            &config.allowed_root,
            config.max_file_bytes.min(MAX_STORY_SOURCE_BYTES),
            cancellation,
            label,
        )?;
        if hex_sha256(&bytes) != spec.sha256 {
            return preflight_error(&format!("{label} configured SHA-256 mismatch"));
        }
        Ok(serde_json::from_slice(&bytes)?)
    };
    Ok(StoryEvidenceBundle {
        voice_plan: resolve(&config.voice_plan, "voice_plan")?,
        mapping: resolve(&config.mapping, "mapping")?,
        role_acceptance: resolve(&config.role_acceptance, "role_acceptance")?,
        continuity_acceptance: resolve(&config.continuity_acceptance, "continuity_acceptance")?,
    })
}

/// Build the deterministic S5ZL voice-plan projection without model or audio access.
pub fn build_chapter_voice_plan(
    plan: &Value,
    mapping: &Value,
    role_acceptance: &Value,
    pacing_acceptance: &Value,
) -> Result<Value, StoryContractError> {
    if plan["status"] != "story_plan_reviewable" {
        return voice_plan_error("story plan not reviewable");
    }
    if plan["source"]["sha256"] != mapping["source_sha256"] {
        return voice_plan_error("source SHA-256 mismatch");
    }
    if mapping["mapping_sha256"] != role_acceptance["mapping_sha256"] {
        return voice_plan_error("mapping SHA-256 mismatch");
    }
    for claim in [
        "owner_accepted_both",
        "voices_distinguishable",
        "chapter_render_ready",
    ] {
        if role_acceptance["claims"][claim] != true {
            return voice_plan_error("role voices not accepted");
        }
    }
    if pacing_acceptance["claims"]["owner_pacing_accepted"] != true {
        return voice_plan_error("pacing policy not accepted");
    }
    let policy = pacing_acceptance["policy"]
        .as_object()
        .ok_or_else(|| StoryContractError::InvalidVoicePlan("pause policy invalid".into()))?;
    let expected_policy_keys = [
        "same_paragraph",
        "speaker_turn",
        "paragraph_break",
        "scene_break",
        "selection_authority",
        "freeform_model_guessing",
    ];
    if policy.len() != expected_policy_keys.len()
        || expected_policy_keys
            .iter()
            .any(|key| !policy.contains_key(*key))
        || policy["selection_authority"] != "explicit_structural_label"
        || policy["freeform_model_guessing"] != false
    {
        return voice_plan_error("pause policy invalid");
    }
    let mut pause_policy = Map::new();
    for transition in [
        "same_paragraph",
        "speaker_turn",
        "paragraph_break",
        "scene_break",
    ] {
        let seconds = policy[transition]
            .as_f64()
            .filter(|value| (0.0..=3.0).contains(value))
            .ok_or_else(|| StoryContractError::InvalidVoicePlan("pause policy invalid".into()))?;
        pause_policy.insert(transition.into(), Value::from(seconds));
    }

    let roles = mapping["roles"]
        .as_array()
        .ok_or_else(|| StoryContractError::InvalidVoicePlan("voice mapping invalid".into()))?;
    let role_by_speaker = roles
        .iter()
        .filter_map(|role| role["speaker_id"].as_str().map(|id| (id, role)))
        .collect::<BTreeMap<_, _>>();
    let narrator_ids = roles
        .iter()
        .filter(|role| role["role_kind"] == "narrator")
        .filter_map(|role| role["speaker_id"].as_str())
        .collect::<Vec<_>>();
    if narrator_ids.len() != 1 {
        return voice_plan_error("unique narrator voice mapping required");
    }

    let mut timeline = plan["voice_scene"]["timeline"]
        .as_array()
        .cloned()
        .ok_or_else(|| StoryContractError::InvalidVoicePlan("chapter timeline empty".into()))?;
    if timeline.is_empty() {
        return voice_plan_error("chapter timeline empty");
    }
    timeline.sort_by_key(|event| event["sequence"].as_u64().unwrap_or(u64::MAX));
    let mut expanded = Vec::new();
    let mut review_queue = Vec::new();
    for event in timeline {
        match split_attributed_dialogue(&event, narrator_ids[0])? {
            (units, None) => expanded.extend(units),
            (units, Some(reason)) => {
                review_queue.push(serde_json::json!({
                    "event_id": event["event_id"],
                    "reason": reason,
                }));
                expanded.extend(units);
            }
        }
    }

    let mut segments = Vec::new();
    for (index, event) in expanded.iter().enumerate() {
        let speaker_id = required_str(&event["utterance"]["speaker_id"], "speaker_id")?;
        let role = role_by_speaker.get(speaker_id).ok_or_else(|| {
            StoryContractError::InvalidVoicePlan(format!("voice mapping missing:{speaker_id}"))
        })?;
        let text = required_str(&event["utterance"]["text"], "utterance text")?;
        let source_span = if event.get("source_span").is_some() {
            event["source_span"].clone()
        } else {
            source_span(event, 0, text.chars().count(), text, "none")?
        };
        let mut row = serde_json::json!({
            "segment_index": index,
            "event_id": event["event_id"],
            "source_event_id": event.get("source_event_id").unwrap_or(&event["event_id"]),
            "sequence": index + 1,
            "source_line": source_line(event)?,
            "source_span": source_span,
            "speaker_id": speaker_id,
            "display_name": role["display_name"],
            "qwen_speaker": role["qwen_speaker"],
            "style_instruction": role["style_instruction"],
            "voice_profile_version": role["voice_profile_version"],
            "text": text,
        });
        if let Some(following) = expanded.get(index + 1) {
            let transition = transition_after(plan, event, following)?;
            row["pause_after_seconds"] = pause_policy[transition].clone();
            row["transition_after"] = Value::String(transition.into());
        }
        segments.push(row);
    }

    let chapter_render_ready = review_queue.is_empty();
    let bound = serde_json::json!({
        "source_sha256": plan["source"]["sha256"],
        "mapping_sha256": mapping["mapping_sha256"],
        "pause_policy": pause_policy,
        "segments": segments,
        "review_queue": review_queue,
        "chapter_render_ready": chapter_render_ready,
    });
    let plan_sha256 = sha256_canonical_json(&bound)?;
    Ok(serde_json::json!({
        "schema": "agent_bridge.story_chapter_voice_plan.v1",
        "status": "chapter_voice_plan_reviewable",
        "source_sha256": bound["source_sha256"],
        "mapping_sha256": bound["mapping_sha256"],
        "pause_policy": bound["pause_policy"],
        "segments": bound["segments"],
        "review_queue": bound["review_queue"],
        "chapter_render_ready": chapter_render_ready,
        "plan_sha256": plan_sha256,
        "runtime_effects": {
            "loaded_model": false,
            "rendered_audio": false,
            "played_audio": false,
            "registered_story_command": false,
        },
        "next_gate": if chapter_render_ready {"bounded_first_chapter_qwen_render"} else {"source_grounded_utterance_segmentation"},
    }))
}

/// Compose the accepted story evidence into S5ZF-compatible, non-actuating requests.
pub fn build_story_command_preflight(
    raw_command: &str,
    request: &StoryRequest,
    voice_plan: &Value,
    mapping: &Value,
    role_acceptance: &Value,
    continuity_acceptance: &Value,
) -> Result<Value, StoryContractError> {
    request.validate()?;
    for forbidden in [
        "--play",
        "--emit-voice",
        "--record",
        "--download-model",
        "--write-memory",
    ] {
        if raw_command
            .split_whitespace()
            .any(|token| token == forbidden)
        {
            return preflight_error(&format!("runtime_option_forbidden:{forbidden}"));
        }
    }
    let source_ingest = ingest_story_source(Path::new(&request.source_path), &request.start)?;
    compose_story_command_preflight(
        raw_command,
        request,
        source_ingest,
        voice_plan,
        mapping,
        role_acceptance,
        continuity_acceptance,
    )
}

fn compose_story_command_preflight(
    raw_command: &str,
    request: &StoryRequest,
    source_ingest: StorySourceIngest,
    voice_plan: &Value,
    mapping: &Value,
    role_acceptance: &Value,
    continuity_acceptance: &Value,
) -> Result<Value, StoryContractError> {
    validate_preflight_evidence(
        &source_ingest.source.sha256,
        voice_plan,
        mapping,
        role_acceptance,
        continuity_acceptance,
    )?;
    let chapter_number = match &request.start {
        StoryStart::FromStart => source_ingest.chapters[0].ordinal,
        StoryStart::Chapter { chapter } => *chapter,
    };
    let selected = bounded_chapter_requests(voice_plan, chapter_number)?;

    let roles = mapping["roles"]
        .as_array()
        .ok_or_else(|| StoryContractError::InvalidPreflight("voice mapping invalid".into()))?;
    let mut roles_by_voice = BTreeMap::new();
    for role in roles {
        let voice = required_preflight_str(&role["qwen_speaker"], "qwen_speaker")?;
        if roles_by_voice.insert(voice, role).is_some() {
            return preflight_error("Qwen speaker mapping must be unique");
        }
    }
    let accepted_candidates = role_acceptance["candidates"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|candidate| candidate["qwen_speaker"].as_str())
        .collect::<HashSet<_>>();
    let model_hash = required_preflight_str(
        &continuity_acceptance["model"]["inference_sha256"],
        "model inference SHA-256",
    )?;
    if model_hash.len() != 64 {
        return preflight_error("model inference SHA-256 missing");
    }

    let mut render_requests = Vec::new();
    for request_value in selected["requests"].as_array().into_iter().flatten() {
        let event_id = required_preflight_str(&request_value["event_id"], "event_id")?;
        let voice = required_preflight_str(&request_value["qwen_speaker"], "qwen_speaker")?;
        let role = roles_by_voice.get(voice).ok_or_else(|| {
            StoryContractError::InvalidPreflight(format!("voice role unresolved:{event_id}"))
        })?;
        if role["audition_status"] != "owner_accepted" && !accepted_candidates.contains(voice) {
            return preflight_error(&format!("voice role not accepted:{event_id}"));
        }
        let version = role["voice_profile_version"].as_u64().ok_or_else(|| {
            StoryContractError::InvalidPreflight("voice profile version invalid".into())
        })? as u32;
        let cache_key = segment_cache_key(&SegmentCacheKeyInput {
            source_sha256: source_ingest.source.sha256.clone(),
            voice_plan_sha256: required_preflight_str(
                &voice_plan["plan_sha256"],
                "voice plan SHA-256",
            )?
            .into(),
            event_id: event_id.into(),
            text: required_preflight_str(&request_value["text"], "text")?.into(),
            qwen_speaker: voice.into(),
            style_instruction: required_preflight_str(
                &request_value["style_instruction"],
                "style instruction",
            )?
            .into(),
            voice_profile_version: version,
            model_inference_sha256: model_hash.into(),
        })?;
        let mut rendered = request_value.clone();
        rendered["voice_profile_version"] = Value::from(version);
        rendered["cache_key"] = Value::String(cache_key);
        render_requests.push(rendered);
    }

    let bound = serde_json::json!({
        "source_sha256": source_ingest.source.sha256,
        "mapping_sha256": mapping["mapping_sha256"],
        "voice_plan_sha256": voice_plan["plan_sha256"],
        "model_inference_sha256": model_hash,
        "chapter_number": chapter_number,
        "render_requests": render_requests,
        "assembly_gap_seconds": selected["assembly_gap_seconds"],
        "preceding_scene_gap_seconds": selected["preceding_scene_gap_seconds"],
    });
    let preflight_sha256 = sha256_canonical_json(&bound)?;
    Ok(serde_json::json!({
        "schema": "agent_bridge.story_command_integration_preflight.v1",
        "status": "story_command_integration_preflight_reviewable",
        "command": {
            "raw": raw_command,
            "source_path": source_ingest.source.uri,
            "start": serde_json::to_value(&request.start)?,
            "chapter_number": chapter_number,
            "dry_run": true,
        },
        "provenance": {
            "source_sha256": bound["source_sha256"],
            "mapping_sha256": bound["mapping_sha256"],
            "voice_plan_sha256": bound["voice_plan_sha256"],
            "model_inference_sha256": model_hash,
            "continuity_receipt_status": continuity_acceptance["status"],
        },
        "selection": {
            "selected_segments": bound["render_requests"].as_array().map_or(0, Vec::len),
            "excluded_earlier_segments": selected["excluded_earlier_segments"],
            "excluded_later_segments": selected["excluded_later_segments"],
            "assembly_gap_seconds": selected["assembly_gap_seconds"],
            "preceding_scene_gap_seconds": selected["preceding_scene_gap_seconds"],
        },
        "render_requests": bound["render_requests"],
        "preflight_sha256": preflight_sha256,
        "execution_authorized": false,
        "runtime_effects": {
            "registered_story_command": false,
            "loaded_model": false,
            "executed_onnx": false,
            "rendered_audio": false,
            "played_audio": false,
            "wrote_memory": false,
            "wrote_cache": false,
        },
        "next_gate": "story_command_static_registration_contract",
    }))
}

/// Run the hardened pure preflight on owned blocking work with cooperative cancellation.
pub async fn run_story_preflight_hardened(
    raw_command: &str,
    request: StoryRequest,
    source_policy: StorySourcePolicy,
    evidence_config: StoryEvidenceBundleConfig,
    cancellation: Arc<StoryPreflightCancellation>,
) -> Result<Value, StoryContractError> {
    cancellation.check()?;
    let raw_command = raw_command.to_owned();
    let worker_cancellation = Arc::clone(&cancellation);
    let mut worker = tokio::task::spawn_blocking(move || {
        request.validate()?;
        for forbidden in [
            "--play",
            "--emit-voice",
            "--record",
            "--download-model",
            "--write-memory",
        ] {
            if raw_command
                .split_whitespace()
                .any(|token| token == forbidden)
            {
                return preflight_error(&format!("runtime_option_forbidden:{forbidden}"));
            }
        }
        let evidence = resolve_story_evidence(&evidence_config, &worker_cancellation)?;
        let source_ingest = ingest_story_source_with_policy(
            Path::new(&request.source_path),
            &request.start,
            &source_policy,
            &worker_cancellation,
        )?;
        worker_cancellation.check()?;
        compose_story_command_preflight(
            &raw_command,
            &request,
            source_ingest,
            &evidence.voice_plan,
            &evidence.mapping,
            &evidence.role_acceptance,
            &evidence.continuity_acceptance,
        )
    });

    tokio::select! {
        biased;
        _ = cancellation.cancelled() => {
            cancellation.cancel();
            let _ = worker.await;
            Err(StoryContractError::Cancelled)
        }
        result = &mut worker => {
            result.map_err(|error| StoryContractError::Worker(error.to_string()))?
        }
    }
}

fn validate_preflight_evidence(
    source_sha256: &str,
    voice_plan: &Value,
    mapping: &Value,
    role_acceptance: &Value,
    continuity_acceptance: &Value,
) -> Result<(), StoryContractError> {
    if voice_plan["source_sha256"] != source_sha256 {
        return preflight_error("story source SHA-256 mismatch");
    }
    if mapping["source_sha256"] != source_sha256 {
        return preflight_error("voice mapping source SHA-256 mismatch");
    }
    if voice_plan["mapping_sha256"] != mapping["mapping_sha256"] {
        return preflight_error("voice plan mapping SHA-256 mismatch");
    }
    if role_acceptance["mapping_sha256"] != mapping["mapping_sha256"] {
        return preflight_error("role acceptance mapping SHA-256 mismatch");
    }
    for claim in [
        "owner_accepted_both",
        "voices_distinguishable",
        "chapter_render_ready",
    ] {
        if role_acceptance["claims"][claim] != true {
            return preflight_error("role voices not accepted");
        }
    }
    let plan_bound = serde_json::json!({
        "source_sha256": voice_plan["source_sha256"],
        "mapping_sha256": voice_plan["mapping_sha256"],
        "pause_policy": voice_plan["pause_policy"],
        "segments": voice_plan["segments"],
        "review_queue": voice_plan["review_queue"],
        "chapter_render_ready": voice_plan["chapter_render_ready"],
    });
    if sha256_canonical_json(&plan_bound)? != voice_plan["plan_sha256"] {
        return preflight_error("chapter voice plan digest invalid");
    }
    if continuity_acceptance["status"] != "owner_accepted"
        || continuity_acceptance["voice_plan_sha256"] != voice_plan["plan_sha256"]
        || continuity_acceptance["claims"]["owner_accepted"] != true
        || continuity_acceptance["claims"]["cross_chapter_continuity_admitted"] != true
    {
        return preflight_error("cross-chapter continuity not accepted");
    }
    Ok(())
}

fn bounded_chapter_requests(
    voice_plan: &Value,
    chapter_number: u32,
) -> Result<Value, StoryContractError> {
    if voice_plan["status"] != "chapter_voice_plan_reviewable"
        || voice_plan["chapter_render_ready"] != true
    {
        return preflight_error("chapter voice plan not render ready");
    }
    let all_segments = voice_plan["segments"]
        .as_array()
        .ok_or_else(|| StoryContractError::InvalidPreflight("chapter voice plan empty".into()))?;
    if all_segments.is_empty() {
        return preflight_error("chapter voice plan empty");
    }
    let mut chapters = Vec::<Vec<&Value>>::new();
    let mut scene_gaps = vec![Value::Null];
    let mut current = Vec::new();
    for segment in all_segments {
        current.push(segment);
        if segment["transition_after"] == "scene_break" {
            chapters.push(std::mem::take(&mut current));
            scene_gaps.push(segment["pause_after_seconds"].clone());
        }
    }
    if !current.is_empty() {
        chapters.push(current);
    }
    let selected_index = chapter_number
        .checked_sub(1)
        .map(|value| value as usize)
        .filter(|index| *index < chapters.len())
        .ok_or_else(|| {
            StoryContractError::InvalidPreflight("chapter number out of range".into())
        })?;
    let selected = &chapters[selected_index];
    let earlier_count = chapters[..selected_index]
        .iter()
        .map(Vec::len)
        .sum::<usize>();
    let later_count = chapters[selected_index + 1..]
        .iter()
        .map(Vec::len)
        .sum::<usize>();
    let requests = selected
        .iter()
        .enumerate()
        .map(|(index, segment)| {
            serde_json::json!({
                "segment_index": index,
                "event_id": segment["event_id"],
                "voice_plan_sha256": voice_plan["plan_sha256"],
                "text": segment["text"],
                "qwen_speaker": segment["qwen_speaker"],
                "style_instruction": segment["style_instruction"],
                "language": "Chinese",
                "frame_cap": 100,
            })
        })
        .collect::<Vec<_>>();
    let assembly_gaps = selected
        .iter()
        .take(selected.len().saturating_sub(1))
        .map(|segment| segment["pause_after_seconds"].clone())
        .collect::<Vec<_>>();
    Ok(serde_json::json!({
        "requests": requests,
        "assembly_gap_seconds": assembly_gaps,
        "preceding_scene_gap_seconds": scene_gaps[selected_index],
        "excluded_earlier_segments": earlier_count,
        "excluded_later_segments": later_count,
    }))
}

fn required_preflight_str<'a>(
    value: &'a Value,
    field: &str,
) -> Result<&'a str, StoryContractError> {
    value
        .as_str()
        .ok_or_else(|| StoryContractError::InvalidPreflight(format!("{field} missing")))
}

fn preflight_error<T>(message: &str) -> Result<T, StoryContractError> {
    Err(StoryContractError::InvalidPreflight(message.into()))
}

fn split_attributed_dialogue(
    event: &Value,
    narrator_speaker_id: &str,
) -> Result<(Vec<Value>, Option<&'static str>), StoryContractError> {
    let text = required_str(&event["utterance"]["text"], "utterance text")?;
    let attributed = ["说", "说道", "问", "答道", "回答", "喊道", "低声说"]
        .iter()
        .any(|verb| {
            text.contains(&format!("{verb}：“"))
                || text.contains(&format!("{verb}:\""))
                || text.contains(&format!("{verb}:\""))
                || text.contains(&format!("{verb}\""))
        });
    if !attributed {
        return Ok((vec![event.clone()], None));
    }
    let characters = text.chars().collect::<Vec<_>>();
    let mut matches = Vec::new();
    for (opening, closing) in [('“', '”'), ('"', '"')] {
        let positions = characters
            .iter()
            .enumerate()
            .filter_map(|(index, character)| (*character == opening).then_some(index))
            .collect::<Vec<_>>();
        let closing_positions = characters
            .iter()
            .enumerate()
            .filter_map(|(index, character)| (*character == closing).then_some(index))
            .collect::<Vec<_>>();
        let valid_count = if opening == closing {
            positions.len() == 2
        } else {
            positions.len() == 1 && closing_positions.len() == 1
        };
        let opening_index = positions.first().copied().unwrap_or(0);
        let closing_index = closing_positions.last().copied().unwrap_or(0);
        if valid_count
            && opening_index > 0
            && closing_index == characters.len() - 1
            && closing_index > opening_index + 1
        {
            matches.push((opening_index, closing_index));
        }
    }
    if matches.len() != 1 {
        return Ok((
            vec![event.clone()],
            Some("attributed_dialogue_split_ambiguous"),
        ));
    }
    let (opening_index, closing_index) = matches[0];
    let prefix = characters[..opening_index].iter().collect::<String>();
    let dialogue = characters[opening_index + 1..closing_index]
        .iter()
        .collect::<String>();
    if prefix.trim().is_empty() || dialogue.trim().is_empty() {
        return Ok((
            vec![event.clone()],
            Some("attributed_dialogue_split_ambiguous"),
        ));
    }
    let (spoken_prefix, normalization) = if prefix.ends_with(['：', ':']) {
        let mut characters = prefix.chars().collect::<Vec<_>>();
        characters.pop();
        (
            format!("{}。", characters.iter().collect::<String>()),
            "terminal_colon_to_full_stop",
        )
    } else {
        (prefix.clone(), "none")
    };
    let mut narration = event.clone();
    narration["event_id"] = Value::String(format!(
        "{}.narration",
        event["event_id"].as_str().unwrap_or_default()
    ));
    narration["source_event_id"] = event["event_id"].clone();
    narration["source_span"] = source_span(event, 0, opening_index, &prefix, normalization)?;
    narration["utterance"]["speaker_id"] = Value::String(narrator_speaker_id.into());
    narration["utterance"]["text"] = Value::String(spoken_prefix);

    let mut spoken = event.clone();
    spoken["event_id"] = Value::String(format!(
        "{}.dialogue",
        event["event_id"].as_str().unwrap_or_default()
    ));
    spoken["source_event_id"] = event["event_id"].clone();
    spoken["source_span"] =
        source_span(event, opening_index + 1, closing_index, &dialogue, "none")?;
    spoken["utterance"]["text"] = Value::String(dialogue);
    Ok((vec![narration, spoken], None))
}

fn source_line(event: &Value) -> Result<u64, StoryContractError> {
    let locator = required_str(&event["source_ref"]["locator"], "event source locator")?;
    locator
        .split(';')
        .find_map(|part| part.strip_prefix("line=")?.parse().ok())
        .ok_or_else(|| StoryContractError::InvalidVoicePlan("event source line missing".into()))
}

fn source_chars(event: &Value) -> Result<(usize, usize), StoryContractError> {
    let locator = required_str(&event["source_ref"]["locator"], "event source locator")?;
    let range = locator
        .split(';')
        .find_map(|part| part.strip_prefix("chars="))
        .ok_or_else(|| StoryContractError::InvalidVoicePlan("event source chars missing".into()))?;
    let (start, end) = range
        .split_once(':')
        .ok_or_else(|| StoryContractError::InvalidVoicePlan("event source chars invalid".into()))?;
    let start = start
        .parse::<usize>()
        .map_err(|_| StoryContractError::InvalidVoicePlan("event source chars invalid".into()))?;
    let end = end
        .parse::<usize>()
        .map_err(|_| StoryContractError::InvalidVoicePlan("event source chars invalid".into()))?;
    if end <= start {
        return voice_plan_error("event source chars invalid");
    }
    Ok((start, end))
}

fn source_span(
    event: &Value,
    local_start: usize,
    local_end: usize,
    source_text: &str,
    normalization: &str,
) -> Result<Value, StoryContractError> {
    let (char_start, char_end) = source_chars(event)?;
    if local_end <= local_start || char_start + local_end > char_end {
        return voice_plan_error("derived source span invalid");
    }
    Ok(serde_json::json!({
        "line": source_line(event)?,
        "char_start": char_start + local_start,
        "char_end": char_start + local_end,
        "source_text": source_text,
        "normalization": normalization,
    }))
}

fn selected_chapter_id<'a>(plan: &'a Value, line: u64) -> Result<&'a str, StoryContractError> {
    let matches = plan["chapters"]
        .as_array()
        .into_iter()
        .flatten()
        .filter(|chapter| {
            chapter["selected"] == true
                && chapter["source_span"]["line_start"]
                    .as_u64()
                    .is_some_and(|start| start <= line)
                && chapter["source_span"]["line_end"]
                    .as_u64()
                    .is_some_and(|end| line <= end)
        })
        .filter_map(|chapter| chapter["chapter_id"].as_str())
        .collect::<Vec<_>>();
    if matches.len() != 1 {
        return voice_plan_error("selected chapter unresolved");
    }
    Ok(matches[0])
}

fn transition_after(
    plan: &Value,
    current: &Value,
    following: &Value,
) -> Result<&'static str, StoryContractError> {
    let current_line = source_line(current)?;
    let next_line = source_line(following)?;
    if next_line < current_line {
        return voice_plan_error("timeline source lines must be strictly increasing");
    }
    if selected_chapter_id(plan, current_line)? != selected_chapter_id(plan, next_line)? {
        Ok("scene_break")
    } else if next_line - current_line > 1 {
        Ok("paragraph_break")
    } else if current["utterance"]["speaker_id"] != following["utterance"]["speaker_id"] {
        Ok("speaker_turn")
    } else {
        Ok("same_paragraph")
    }
}

fn required_str<'a>(value: &'a Value, field: &str) -> Result<&'a str, StoryContractError> {
    value
        .as_str()
        .ok_or_else(|| StoryContractError::InvalidVoicePlan(format!("{field} invalid")))
}

fn voice_plan_error<T>(message: &str) -> Result<T, StoryContractError> {
    Err(StoryContractError::InvalidVoicePlan(message.into()))
}

#[derive(Debug)]
struct LineRecord<'a> {
    number: usize,
    text: &'a str,
    char_start: usize,
    char_end: usize,
}

fn line_records(text: &str) -> Vec<LineRecord<'_>> {
    let mut records = Vec::new();
    let mut byte_start = 0;
    let mut char_start = 0;
    for line_with_end in text.split_inclusive('\n') {
        let line = line_with_end.trim_end_matches(['\r', '\n']);
        let char_end = char_start + line_with_end.chars().count();
        records.push(LineRecord {
            number: records.len() + 1,
            text: &text[byte_start..byte_start + line.len()],
            char_start,
            char_end,
        });
        byte_start += line_with_end.len();
        char_start = char_end;
    }
    if !text.is_empty() && !text.ends_with('\n') && records.is_empty() {
        records.push(LineRecord {
            number: 1,
            text,
            char_start: 0,
            char_end: text.chars().count(),
        });
    }
    records
}

fn index_chapters(text: &str, source_id: &str) -> Result<Vec<StoryChapter>, StoryContractError> {
    let records = line_records(text);
    if records.is_empty() {
        return Err(StoryContractError::InvalidSource(
            "story_source_empty".into(),
        ));
    }
    let mut starts = records
        .iter()
        .enumerate()
        .filter_map(|(index, record)| chapter_heading(record.text).map(|row| (index, row)))
        .collect::<Vec<_>>();
    if starts.is_empty() {
        starts.push((0, ("全文".into(), Some(1))));
    } else if starts[0].0 > 0
        && records[..starts[0].0]
            .iter()
            .any(|record| !record.text.trim().is_empty())
    {
        starts.insert(0, (0, ("前言".into(), Some(0))));
    }

    let mut chapters = Vec::new();
    let mut used_ordinals = HashSet::new();
    let mut next_ordinal = 1;
    for (chapter_index, (record_start, (title, parsed_ordinal))) in starts.iter().enumerate() {
        let record_end = starts
            .get(chapter_index + 1)
            .map(|row| row.0)
            .unwrap_or(records.len());
        let mut ordinal = parsed_ordinal.unwrap_or(next_ordinal);
        if parsed_ordinal.is_none() || used_ordinals.contains(&ordinal) {
            while used_ordinals.contains(&next_ordinal) {
                next_ordinal += 1;
            }
            ordinal = next_ordinal;
        }
        used_ordinals.insert(ordinal);
        next_ordinal = next_ordinal.max(ordinal + 1);
        let first = &records[*record_start];
        let last = &records[record_end - 1];
        let chapter_id = deterministic_id(
            "chapter",
            &serde_json::json!({
                "source_id": source_id,
                "ordinal": ordinal,
                "title": title,
            }),
        )?;
        chapters.push(StoryChapter {
            chapter_id,
            ordinal,
            title: title.clone(),
            selected: false,
            source_span: SourceSpan {
                source_id: source_id.into(),
                line_start: first.number,
                line_end: last.number,
                char_start: first.char_start,
                char_end: last.char_end,
            },
        });
    }
    Ok(chapters)
}

fn chapter_heading(line: &str) -> Option<(String, Option<u32>)> {
    let trimmed = line.trim_start();
    let without_hashes = strip_optional_hash_prefix(trimmed);
    if let Some(rest) = without_hashes.strip_prefix('第') {
        let numeral_len = rest
            .chars()
            .take_while(|character| is_chapter_numeral(*character))
            .map(char::len_utf8)
            .sum::<usize>();
        let (numeral, after_numeral) = rest.split_at(numeral_len);
        if !numeral.is_empty()
            && after_numeral
                .chars()
                .next()
                .is_some_and(|marker| matches!(marker, '章' | '节' | '回' | '卷'))
        {
            return Some((without_hashes.trim().into(), chinese_number(numeral)));
        }
    }
    markdown_heading(trimmed).map(|title| (title, None))
}

fn strip_optional_hash_prefix(line: &str) -> &str {
    let count = line
        .chars()
        .take_while(|character| *character == '#')
        .count();
    if (1..=6).contains(&count) {
        line[count..].trim_start()
    } else {
        line
    }
}

fn markdown_heading(line: &str) -> Option<String> {
    let count = line
        .chars()
        .take_while(|character| *character == '#')
        .count();
    if !(1..=6).contains(&count) {
        return None;
    }
    let rest = &line[count..];
    if rest.chars().next().is_some_and(char::is_whitespace) {
        Some(rest.trim().into())
    } else {
        None
    }
}

fn is_chapter_numeral(character: char) -> bool {
    character.is_ascii_digit()
        || matches!(
            character,
            '零' | '〇'
                | '一'
                | '二'
                | '三'
                | '四'
                | '五'
                | '六'
                | '七'
                | '八'
                | '九'
                | '十'
                | '百'
                | '千'
        )
}

fn chinese_number(value: &str) -> Option<u32> {
    if value.chars().all(|character| character.is_ascii_digit()) {
        return value.parse().ok();
    }
    let mut total = 0;
    let mut current = 0;
    for character in value.chars() {
        current = match character {
            '零' | '〇' => 0,
            '一' => 1,
            '二' => 2,
            '三' => 3,
            '四' => 4,
            '五' => 5,
            '六' => 6,
            '七' => 7,
            '八' => 8,
            '九' => 9,
            _ => {
                let unit = match character {
                    '十' => 10,
                    '百' => 100,
                    '千' => 1000,
                    _ => return None,
                };
                total += current.max(1) * unit;
                0
            }
        };
    }
    Some(total + current)
}

fn deterministic_id(prefix: &str, value: &Value) -> Result<String, StoryContractError> {
    let digest = sha256_canonical_json(value)?;
    Ok(format!("{prefix}_{}", &digest[..20]))
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
