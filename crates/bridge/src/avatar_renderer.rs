use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

pub const LCC_AURA_IO_SCHEMA_VERSION: &str = "lcc.aura_io.v1";
pub const LCC_AURA_RENDERER_INPUT_KIND: &str = "tfe_uniform_f32x256";
pub const LCC_AURA_UNIFORM_CONTRACT_VERSION: u64 = 1;
pub const LCC_AURA_UNIFORM_LEN: u64 = 256;
pub const LCC_AURA_UNIFORM_BYTES: u64 = 1024;
pub const LCC_AURA_UNIFORM_ENCODING: &str = "little_endian_f32";
pub const LCC_AURA_VISIBLE_SIGNAL_SOURCE: &str = "curated_digest_only";
pub const LCC_AURA_SHADOW_SIGNAL_POLICY: &str = "shadow_only_until_falsified";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RendererSource {
    ProjectedAvatar,
    ScopedRawPet,
    IdleFallback,
}

impl RendererSource {
    fn as_str(&self) -> &'static str {
        match self {
            Self::ProjectedAvatar => "projected_avatar",
            Self::ScopedRawPet => "scoped_raw_pet",
            Self::IdleFallback => "idle_fallback",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RendererScope {
    pub project: String,
    pub cwd: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct RendererStateSelection {
    pub source: RendererSource,
    pub state: Value,
    pub fallback_reason: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RendererPlan {
    pub track: String,
    pub renderer_token: String,
    pub asset_route: Option<String>,
    pub fallback_reason: Option<String>,
}

fn non_empty_str<'a>(value: &'a Value, key: &str) -> Option<&'a str> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
}

fn object_field<'a>(value: &'a Value, key: &str) -> Result<&'a Value> {
    let field = value
        .get(key)
        .with_context(|| format!("{key} is required"))?;
    if !field.is_object() {
        bail!("{key} must be an object");
    }
    Ok(field)
}

fn required_str<'a>(value: &'a Value, key: &str) -> Result<&'a str> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .with_context(|| format!("{key} must be a non-empty string"))
}

fn required_u64(value: &Value, key: &str) -> Result<u64> {
    value
        .get(key)
        .and_then(Value::as_u64)
        .with_context(|| format!("{key} must be an unsigned integer"))
}

fn expect_str(value: &Value, key: &str, expected: &str) -> Result<()> {
    let actual = required_str(value, key)?;
    if actual != expected {
        bail!("{key} must be {expected}, got {actual}");
    }
    Ok(())
}

fn expect_u64(value: &Value, key: &str, expected: u64) -> Result<()> {
    let actual = required_u64(value, key)?;
    if actual != expected {
        bail!("{key} must be {expected}, got {actual}");
    }
    Ok(())
}

fn strip_sha256_prefix(value: &str) -> &str {
    value.strip_prefix("sha256:").unwrap_or(value)
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn resolve_manifest_path(path: &str, base_dir: Option<&Path>) -> PathBuf {
    let path = PathBuf::from(path);
    if path.is_relative() {
        if let Some(base) = base_dir {
            return base.join(path);
        }
    }
    path
}

fn shadow_visible_key(value: &Value) -> Option<String> {
    let obj = value.as_object()?;
    obj.keys().find_map(|key| {
        let lowered = key.to_ascii_lowercase();
        let is_shadow = lowered.contains("biocortex")
            || lowered.contains("cortex")
            || lowered.contains("dream")
            || matches!(
                lowered.as_str(),
                "affect" | "affect_state" | "emotion" | "emotion_state"
            );
        is_shadow.then(|| key.to_string())
    })
}

fn validate_aura_io_manifest_inner(
    manifest: &Value,
    check_files: bool,
    base_dir: Option<&Path>,
) -> Result<Value> {
    if !manifest.is_object() {
        bail!("aura_io manifest root must be an object");
    }
    expect_str(manifest, "schema_version", LCC_AURA_IO_SCHEMA_VERSION)?;

    let renderer_input = object_field(manifest, "renderer_input")?;
    expect_str(renderer_input, "kind", LCC_AURA_RENDERER_INPUT_KIND)?;
    expect_u64(
        renderer_input,
        "contract_version",
        LCC_AURA_UNIFORM_CONTRACT_VERSION,
    )?;
    expect_u64(renderer_input, "uniform_len", LCC_AURA_UNIFORM_LEN)?;
    expect_u64(renderer_input, "bin_bytes", LCC_AURA_UNIFORM_BYTES)?;
    expect_str(renderer_input, "encoding", LCC_AURA_UNIFORM_ENCODING)?;

    let source_digest = object_field(manifest, "source_digest")?;
    expect_str(
        manifest,
        "visible_signal_source",
        LCC_AURA_VISIBLE_SIGNAL_SOURCE,
    )?;
    expect_str(
        manifest,
        "shadow_signal_policy",
        LCC_AURA_SHADOW_SIGNAL_POLICY,
    )?;

    let source_state = object_field(manifest, "source_state")?;
    if let Some(key) = shadow_visible_key(source_state) {
        bail!("source_state contains shadow-only visible key: {key}");
    }

    let uniform_path_text = required_str(renderer_input, "path")?;
    let digest_path_text = required_str(source_digest, "json_path")?;
    let uniform_sha = required_str(renderer_input, "sha256")?;
    let digest_sha = required_str(source_digest, "json_sha256")?;
    let item_count = required_u64(source_digest, "item_count")?;

    let mut uniform_file_match = Value::Null;
    let mut digest_file_match = Value::Null;
    if check_files {
        let uniform_path = resolve_manifest_path(uniform_path_text, base_dir);
        let digest_path = resolve_manifest_path(digest_path_text, base_dir);
        let uniform_bytes = fs::read(&uniform_path)
            .with_context(|| format!("read uniform {}", uniform_path.display()))?;
        if uniform_bytes.len() != LCC_AURA_UNIFORM_BYTES as usize {
            bail!(
                "uniform file must be {} bytes, got {}",
                LCC_AURA_UNIFORM_BYTES,
                uniform_bytes.len()
            );
        }
        let digest_bytes = fs::read(&digest_path)
            .with_context(|| format!("read digest {}", digest_path.display()))?;
        let uniform_ok = sha256_hex(&uniform_bytes) == strip_sha256_prefix(uniform_sha);
        let digest_ok = sha256_hex(&digest_bytes) == strip_sha256_prefix(digest_sha);
        if !uniform_ok {
            bail!("uniform file sha256 does not match aura_io");
        }
        if !digest_ok {
            bail!("digest file sha256 does not match aura_io");
        }
        uniform_file_match = Value::Bool(true);
        digest_file_match = Value::Bool(true);
    }

    Ok(json!({
        "surface": "lcc_aura_io_intake",
        "schema": 1,
        "ok": true,
        "schema_version": LCC_AURA_IO_SCHEMA_VERSION,
        "renderer_input_kind": LCC_AURA_RENDERER_INPUT_KIND,
        "uniform_contract_version": LCC_AURA_UNIFORM_CONTRACT_VERSION,
        "uniform_len": LCC_AURA_UNIFORM_LEN,
        "bin_bytes": LCC_AURA_UNIFORM_BYTES,
        "uniform_path": uniform_path_text,
        "digest_path": digest_path_text,
        "digest_item_count": item_count,
        "visible_signal_source": LCC_AURA_VISIBLE_SIGNAL_SOURCE,
        "shadow_signal_policy": LCC_AURA_SHADOW_SIGNAL_POLICY,
        "uniform_file_sha256_matches": uniform_file_match,
        "digest_file_sha256_matches": digest_file_match,
        "safety": {
            "read_only": true,
            "writes_files": false,
            "mutates_renderer": false,
            "emits_audio": false,
            "controls_desktop": false,
            "shadow_visible_state": false,
        }
    }))
}

pub fn validate_aura_io_manifest(manifest: &Value, check_files: bool) -> Result<Value> {
    validate_aura_io_manifest_inner(manifest, check_files, None)
}

pub fn validate_aura_io_sidecar_path(path: &Path, check_files: bool) -> Result<Value> {
    let bytes =
        fs::read(path).with_context(|| format!("read aura_io sidecar {}", path.display()))?;
    let manifest: Value = serde_json::from_slice(&bytes)
        .with_context(|| format!("parse aura_io sidecar {}", path.display()))?;
    let mut report = validate_aura_io_manifest_inner(&manifest, check_files, path.parent())?;
    if let Some(obj) = report.as_object_mut() {
        obj.insert(
            "sidecar_path".to_string(),
            Value::String(path.display().to_string()),
        );
    }
    Ok(report)
}

fn raw_pet_matches_scope(scope: &RendererScope, raw_pet: &Value) -> bool {
    if non_empty_str(raw_pet, "project") != Some(scope.project.as_str()) {
        return false;
    }

    match (&scope.cwd, non_empty_str(raw_pet, "cwd")) {
        (Some(expected), Some(actual)) => actual == expected,
        (Some(_), None) => false,
        (None, _) => true,
    }
}

fn idle_state(scope: &RendererScope) -> Value {
    json!({
        "agent_avatar_protocol": 1,
        "project": scope.project,
        "cwd": scope.cwd,
        "mode": "idle",
        "activity_state": "idle"
    })
}

pub fn select_renderer_state(
    scope: &RendererScope,
    projected_avatar: Option<&Value>,
    raw_pet: Option<&Value>,
) -> RendererStateSelection {
    if let Some(state) = projected_avatar.filter(|value| value.is_object()) {
        return RendererStateSelection {
            source: RendererSource::ProjectedAvatar,
            state: state.clone(),
            fallback_reason: None,
        };
    }

    if let Some(state) = raw_pet.filter(|value| value.is_object()) {
        if raw_pet_matches_scope(scope, state) {
            return RendererStateSelection {
                source: RendererSource::ScopedRawPet,
                state: state.clone(),
                fallback_reason: None,
            };
        }

        return RendererStateSelection {
            source: RendererSource::IdleFallback,
            state: idle_state(scope),
            fallback_reason: Some("raw_pet_scope_mismatch".to_string()),
        };
    }

    RendererStateSelection {
        source: RendererSource::IdleFallback,
        state: idle_state(scope),
        fallback_reason: Some("no_state_available".to_string()),
    }
}

pub fn renderer_plan_from_state(state: &Value) -> RendererPlan {
    let mode = non_empty_str(state, "mode").unwrap_or("idle");
    let (track, renderer_token, asset_route, fallback_reason) = match mode {
        "idle" => (
            "idle_breathe",
            "xiao_shu::idle_breathe::low",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1"),
            None,
        ),
        "orienting" => ("focused_review", "xiao_shu::focused_review::low", None, None),
        "reviewing" => (
            "look_sideways",
            "xiao_shu::look_sideways::medium",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-look-sideways-v2"),
            None,
        ),
        "working" => (
            "sorting_glow",
            "xiao_shu::sorting_glow::medium",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v3"),
            None,
        ),
        "waiting_for_user" => ("waiting_for_user", "xiao_shu::waiting_for_user::low", None, None),
        "failed" => ("mismatch", "xiao_shu::mismatch::medium", None, None),
        "verified" => (
            "completion_nod",
            "xiao_shu::completion_nod::low",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-completion-nod-v1"),
            None,
        ),
        "handoff" => (
            "idle_breathe",
            "xiao_shu::idle_breathe::low",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1"),
            None,
        ),
        _ => (
            "idle_breathe",
            "xiao_shu::idle_breathe::low",
            Some("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1"),
            Some("unknown_mode"),
        ),
    };

    RendererPlan {
        track: track.to_string(),
        renderer_token: renderer_token.to_string(),
        asset_route: asset_route.map(ToString::to_string),
        fallback_reason: fallback_reason.map(ToString::to_string),
    }
}

pub fn renderer_payload_from_sources(
    scope: &RendererScope,
    projected_avatar: Option<&Value>,
    raw_pet: Option<&Value>,
) -> Value {
    let selection = select_renderer_state(scope, projected_avatar, raw_pet);
    let plan = renderer_plan_from_state(&selection.state);

    json!({
        "surface": "linux_codex_avatar_renderer_state",
        "schema": 1,
        "read_only": true,
        "project": scope.project,
        "cwd": scope.cwd,
        "selection": {
            "source": selection.source.as_str(),
            "fallback_reason": selection.fallback_reason,
        },
        "state": selection.state,
        "plan": {
            "track": plan.track,
            "renderer_token": plan.renderer_token,
            "asset_route": plan.asset_route,
            "fallback_reason": plan.fallback_reason,
        },
        "safety": {
            "sidecar_only": true,
            "writes_files": false,
            "mutates_renderer": false,
            "codex_pet_package_mutation": false,
            "emits_audio": false,
            "emits_notification": false,
            "controls_desktop": false,
        }
    })
}
