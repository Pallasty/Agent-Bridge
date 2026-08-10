use ab_mcp::{McpTool, ToolAnnotations, ToolContext, ToolResult, ToolSchema};
use ab_world_core::{AttentionDecision, AuthorityDecision, ProjectionRequest};
use async_trait::async_trait;
use serde_json::{json, Value};

use crate::embodiment_runtime::EmbodimentRuntimeGate;

pub(super) const EMBODIMENT_P4_MCP_ENABLE_ENV: &str = "AGENT_BRIDGE_EMBODIMENT_P4_MCP";
pub(super) const EMBODIMENT_P4_ALLOWED_OPERATIONS_ENV: &str =
    "AGENT_BRIDGE_EMBODIMENT_P4_ALLOWED_OPERATIONS";

pub(super) fn parse_projection_preview_config(
    enabled: Option<&str>,
    allowed_operations: Option<&str>,
) -> Result<Option<Vec<String>>, String> {
    if enabled.map(str::trim) != Some("1") {
        return Ok(None);
    }
    let operations: Vec<String> = allowed_operations
        .unwrap_or_default()
        .split(',')
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(str::to_string)
        .collect();
    if operations.is_empty() {
        return Err(format!(
            "{EMBODIMENT_P4_ALLOWED_OPERATIONS_ENV} must contain at least one operation"
        ));
    }
    if operations.len() > 32
        || operations.iter().any(|operation| {
            operation.len() > 64
                || !operation
                    .chars()
                    .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.'))
        })
    {
        return Err(format!(
            "{EMBODIMENT_P4_ALLOWED_OPERATIONS_ENV} contains an invalid operation"
        ));
    }
    Ok(Some(operations))
}

pub(super) fn configured_projection_preview_operations() -> Result<Option<Vec<String>>, String> {
    parse_projection_preview_config(
        std::env::var(EMBODIMENT_P4_MCP_ENABLE_ENV).ok().as_deref(),
        std::env::var(EMBODIMENT_P4_ALLOWED_OPERATIONS_ENV)
            .ok()
            .as_deref(),
    )
}

pub(super) struct EmbodimentProjectionPreviewTool {
    gate: EmbodimentRuntimeGate,
}

impl EmbodimentProjectionPreviewTool {
    pub(super) fn new(allowed_operations: Vec<String>) -> Self {
        Self {
            gate: EmbodimentRuntimeGate::enabled(allowed_operations),
        }
    }
}

fn parse_required<T: serde::de::DeserializeOwned>(args: &Value, field: &str) -> Result<T, String> {
    let value = args
        .get(field)
        .cloned()
        .ok_or_else(|| format!("missing '{field}'"))?;
    serde_json::from_value(value).map_err(|error| format!("invalid '{field}': {error}"))
}

#[async_trait]
impl McpTool for EmbodimentProjectionPreviewTool {
    fn name(&self) -> &'static str {
        "embodiment_projection_preview"
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Compile an owner-confirmed embodiment ProjectionPlan as a dry run. The tool never executes, acquires a lease, records an effect, or writes durable state. It is build-, env-, allowlist-, and profile-gated.".into(),
            input_schema: json!({
                "type": "object",
                "additionalProperties": false,
                "required": ["attention", "authority", "request"],
                "properties": {
                    "attention": {
                        "type": "object",
                        "description": "AttentionDecision v0 produced by shadow attention."
                    },
                    "authority": {
                        "type": "object",
                        "description": "Approved AuthorityDecision v0 with owner_confirmation=true."
                    },
                    "request": {
                        "type": "object",
                        "description": "ProjectionRequest containing intent, allowlisted operation, arguments, precondition, and reversibility."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> ab_core::Result<ToolResult> {
        let attention: AttentionDecision = match parse_required(&args, "attention") {
            Ok(value) => value,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let authority: AuthorityDecision = match parse_required(&args, "authority") {
            Ok(value) => value,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let request: ProjectionRequest = match parse_required(&args, "request") {
            Ok(value) => value,
            Err(error) => return Ok(ToolResult::error(error)),
        };

        match self.gate.prepare_plan(&attention, &authority, request) {
            Ok(plan) => Ok(ToolResult::json_text(&json!({
                "schema": "agent_bridge.embodiment_projection_preview.v0",
                "dry_run": true,
                "executed": false,
                "lease_acquired": false,
                "effect_receipt_created": false,
                "requires_separate_execution_surface": true,
                "plan": plan,
            }))),
            Err(error) => Ok(ToolResult::error(format!(
                "embodiment projection preview rejected: {error:?}"
            ))),
        }
    }
}
