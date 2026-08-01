//! Isolated, not-yet-registered MCP transport for the native story preflight.

use crate::story_contract::{
    run_story_preflight_hardened, EvidenceFileSpec, StoryEvidenceBundleConfig,
    StoryPreflightCancellation, StoryRequest, StorySourcePolicy, MAX_STORY_SOURCE_BYTES,
};
use ab_core::Result;
use ab_mcp::{McpTool, ToolAnnotations, ToolContext, ToolResult, ToolSchema};
use async_trait::async_trait;
use serde::Deserialize;
use serde_json::{json, Value};
use std::{collections::BTreeMap, path::PathBuf, sync::Arc};
use thiserror::Error;

const ENABLE_ENV: &str = "AB_STORY_COMMAND_PREFLIGHT_ENABLE";
const CONFIG_KEYS: [&str; 11] = [
    "AB_STORY_SOURCE_ROOT",
    "AB_STORY_SOURCE_MAX_BYTES",
    "AB_STORY_EVIDENCE_ROOT",
    "AB_STORY_VOICE_PLAN_PATH",
    "AB_STORY_VOICE_PLAN_SHA256",
    "AB_STORY_MAPPING_PATH",
    "AB_STORY_MAPPING_SHA256",
    "AB_STORY_ROLE_ACCEPTANCE_PATH",
    "AB_STORY_ROLE_ACCEPTANCE_SHA256",
    "AB_STORY_CONTINUITY_PATH",
    "AB_STORY_CONTINUITY_SHA256",
];

#[derive(Debug, Error)]
pub enum StoryMcpConfigError {
    #[error("invalid {ENABLE_ENV} value; expected 0 or 1")]
    InvalidActivation,
    #[error("story MCP configuration missing: {0}")]
    Missing(String),
    #[error("invalid AB_STORY_SOURCE_MAX_BYTES; expected 1..={MAX_STORY_SOURCE_BYTES}")]
    InvalidSourceLimit,
    #[error("invalid lowercase SHA-256 in {0}")]
    InvalidSha256(&'static str),
}

#[derive(Debug, Clone)]
pub struct StoryMcpConfig {
    pub source_policy: StorySourcePolicy,
    pub evidence: StoryEvidenceBundleConfig,
}

impl StoryMcpConfig {
    pub fn from_env() -> std::result::Result<Option<Self>, StoryMcpConfigError> {
        let mut values = BTreeMap::new();
        for key in std::iter::once(ENABLE_ENV).chain(CONFIG_KEYS) {
            if let Ok(value) = std::env::var(key) {
                values.insert(key.to_string(), value);
            }
        }
        Self::from_values(&values)
    }

    pub fn from_values(
        values: &BTreeMap<String, String>,
    ) -> std::result::Result<Option<Self>, StoryMcpConfigError> {
        match values.get(ENABLE_ENV).map(|value| value.trim()) {
            None | Some("") | Some("0") => return Ok(None),
            Some("1") => {}
            Some(_) => return Err(StoryMcpConfigError::InvalidActivation),
        }

        let missing = CONFIG_KEYS
            .iter()
            .filter(|key| {
                values
                    .get(**key)
                    .is_none_or(|value| value.trim().is_empty())
            })
            .copied()
            .collect::<Vec<_>>();
        if !missing.is_empty() {
            return Err(StoryMcpConfigError::Missing(missing.join(",")));
        }
        let get = |key: &'static str| values.get(key).expect("checked config key").trim();
        let max_bytes = get("AB_STORY_SOURCE_MAX_BYTES")
            .parse::<u64>()
            .ok()
            .filter(|value| (1..=MAX_STORY_SOURCE_BYTES).contains(value))
            .ok_or(StoryMcpConfigError::InvalidSourceLimit)?;
        let evidence_spec = |path_key: &'static str,
                             hash_key: &'static str|
         -> std::result::Result<EvidenceFileSpec, StoryMcpConfigError> {
            let sha256 = get(hash_key);
            if sha256.len() != 64
                || !sha256
                    .bytes()
                    .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
            {
                return Err(StoryMcpConfigError::InvalidSha256(hash_key));
            }
            Ok(EvidenceFileSpec {
                path: PathBuf::from(get(path_key)),
                sha256: sha256.to_string(),
            })
        };
        let evidence_root = PathBuf::from(get("AB_STORY_EVIDENCE_ROOT"));
        Ok(Some(Self {
            source_policy: StorySourcePolicy {
                allowed_root: PathBuf::from(get("AB_STORY_SOURCE_ROOT")),
                max_bytes,
            },
            evidence: StoryEvidenceBundleConfig {
                voice_plan: evidence_spec(
                    "AB_STORY_VOICE_PLAN_PATH",
                    "AB_STORY_VOICE_PLAN_SHA256",
                )?,
                mapping: evidence_spec("AB_STORY_MAPPING_PATH", "AB_STORY_MAPPING_SHA256")?,
                role_acceptance: evidence_spec(
                    "AB_STORY_ROLE_ACCEPTANCE_PATH",
                    "AB_STORY_ROLE_ACCEPTANCE_SHA256",
                )?,
                continuity_acceptance: evidence_spec(
                    "AB_STORY_CONTINUITY_PATH",
                    "AB_STORY_CONTINUITY_SHA256",
                )?,
                allowed_root: evidence_root,
                max_file_bytes: max_bytes,
            },
        }))
    }
}

/// Cancels the shared native preflight token when MCP abort drops the tool future.
pub struct StoryPreflightCancelOnDrop {
    cancellation: Arc<StoryPreflightCancellation>,
    armed: bool,
}

impl StoryPreflightCancelOnDrop {
    pub fn new(cancellation: Arc<StoryPreflightCancellation>) -> Self {
        Self {
            cancellation,
            armed: true,
        }
    }

    fn disarm(&mut self) {
        self.armed = false;
    }
}

impl Drop for StoryPreflightCancelOnDrop {
    fn drop(&mut self) {
        if self.armed {
            self.cancellation.cancel();
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct StoryToolArgs {
    source_path: String,
    start: crate::story_contract::StoryStart,
    dry_run: bool,
}

pub struct StoryCommandPreflightTool {
    config: StoryMcpConfig,
}

impl StoryCommandPreflightTool {
    pub fn new(config: StoryMcpConfig) -> Self {
        Self { config }
    }

    pub async fn execute_value(&self, args: Value) -> ToolResult {
        let args: StoryToolArgs = match serde_json::from_value(args) {
            Ok(args) => args,
            Err(error) => return ToolResult::error(format!("invalid story arguments: {error}")),
        };
        let request = StoryRequest {
            source_path: args.source_path,
            start: args.start,
            dry_run: args.dry_run,
        };
        let start = match &request.start {
            crate::story_contract::StoryStart::FromStart => "from-start".to_string(),
            crate::story_contract::StoryStart::Chapter { chapter } => {
                format!("chapter {chapter}")
            }
        };
        let quoted_path = serde_json::to_string(&request.source_path)
            .unwrap_or_else(|_| "\"<invalid>\"".to_string());
        let raw_command = format!("/story {quoted_path} {start}");
        let cancellation = Arc::new(StoryPreflightCancellation::new());
        let mut drop_guard = StoryPreflightCancelOnDrop::new(Arc::clone(&cancellation));
        let result = run_story_preflight_hardened(
            &raw_command,
            request,
            self.config.source_policy.clone(),
            self.config.evidence.clone(),
            cancellation,
        )
        .await;
        drop_guard.disarm();
        match result {
            Ok(value) => ToolResult::structured_json(&value),
            Err(error) => ToolResult::error(format!("story preflight rejected: {error}")),
        }
    }
}

#[async_trait]
impl McpTool for StoryCommandPreflightTool {
    fn name(&self) -> &'static str {
        "story_command_preflight"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Validate a bounded, source- and evidence-bound story chapter preflight without rendering or playback.".into(),
            input_schema: json!({
                "type": "object",
                "additionalProperties": false,
                "required": ["source_path", "start", "dry_run"],
                "properties": {
                    "source_path": {"type": "string", "minLength": 1, "pattern": "(?i)\\.(txt|md|markdown)$"},
                    "start": {
                        "oneOf": [
                            {"type": "object", "additionalProperties": false, "required": ["kind"], "properties": {"kind": {"const": "from_start"}}},
                            {"type": "object", "additionalProperties": false, "required": ["kind", "chapter"], "properties": {"kind": {"const": "chapter"}, "chapter": {"type": "integer", "minimum": 1}}}
                        ]
                    },
                    "dry_run": {"const": true}
                }
            }),
        }
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(self.execute_value(args).await)
    }
}
