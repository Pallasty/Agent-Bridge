//! ChatGPT collaboration control-plane tools.
//!
//! These tools can stage and inspect private operator requests. They cannot
//! approve, execute, or write canonical project, memory, forum, or runtime
//! state.

use super::*;
use crate::operator_request::{OperatorCapability, OperatorRequestInput, OperatorRequestStore};

pub(super) struct OperatorRequestStageTool {
    store: OperatorRequestStore,
    channel_id: String,
    allowed_capabilities: BTreeSet<OperatorCapability>,
}

impl OperatorRequestStageTool {
    pub(super) fn new(
        store: OperatorRequestStore,
        channel_id: String,
        allowed_capabilities: BTreeSet<OperatorCapability>,
    ) -> Self {
        Self {
            store,
            channel_id,
            allowed_capabilities,
        }
    }
}

#[async_trait]
impl McpTool for OperatorRequestStageTool {
    fn name(&self) -> &'static str {
        "operator_request_stage"
    }

    fn title(&self) -> String {
        "Stage an Agent-Bridge operator request".into()
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations {
            read_only_hint: false,
            destructive_hint: false,
            open_world_hint: false,
            idempotent_hint: Some(false),
        })
    }

    fn output_schema(&self) -> Option<Value> {
        Some(operator_request_view_schema())
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Stage one API-single-write, TTL-bounded request for local operator review. This writes only a private request record. It never approves or executes the request and never writes canonical memory, forum, project, external-service, or runtime state. A non-read-only contract must include accepted parent evidence for the exact authority boundary; P1 records that reference but does not authenticate its claimant."
                .into(),
            input_schema: json!({
                "type": "object",
                "additionalProperties": false,
                "required": [
                    "requested_capability",
                    "target",
                    "summary",
                    "contract"
                ],
                "properties": {
                    "requested_capability": {
                        "type": "string",
                        "enum": [
                            "work_memory_write",
                            "forum_post",
                            "project_write",
                            "external_write",
                            "runtime_enablement"
                        ]
                    },
                    "target": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 1024,
                        "description": "Exact project path, forum thread, external service, or runtime target under review."
                    },
                    "summary": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 2000,
                        "description": "Bounded action requested from a future, separately gated executor."
                    },
                    "ttl_secs": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 3600,
                        "default": 600
                    },
                    "contract": agent_task_contract_input_schema()
                }
            }),
        }
    }

    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        let input = match serde_json::from_value::<OperatorRequestInput>(args) {
            Ok(input) => input,
            Err(error) => {
                return Ok(ToolResult::error(format!(
                    "invalid operator request: {error}"
                )))
            }
        };
        let result = self.store.stage(
            input,
            &self.channel_id,
            ctx.session_id.as_ref().map(|id| id.as_str()),
            "chatgpt",
            "chatgpt-collab",
            &self.allowed_capabilities,
        );
        match result {
            Ok(view) => Ok(ToolResult::structured_json(&json!(view))),
            Err(error) => Ok(ToolResult::error(format!(
                "operator request was not staged: {error}"
            ))),
        }
    }
}

pub(super) struct OperatorRequestGetTool {
    store: OperatorRequestStore,
    channel_id: String,
}

impl OperatorRequestGetTool {
    pub(super) fn new(store: OperatorRequestStore, channel_id: String) -> Self {
        Self { store, channel_id }
    }
}

#[derive(serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct OperatorRequestGetArgs {
    request_id: String,
}

#[async_trait]
impl McpTool for OperatorRequestGetTool {
    fn name(&self) -> &'static str {
        "operator_request_get"
    }

    fn title(&self) -> String {
        "Inspect an Agent-Bridge operator request".into()
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    fn output_schema(&self) -> Option<Value> {
        Some(operator_request_view_schema())
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read one staged operator request from this collaboration channel. Approval is local-only, and an approved record still reports execution_allowed=false until a separate executor gate exists."
                .into(),
            input_schema: json!({
                "type": "object",
                "additionalProperties": false,
                "required": ["request_id"],
                "properties": {
                    "request_id": {
                        "type": "string",
                        "format": "uuid"
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let args = match serde_json::from_value::<OperatorRequestGetArgs>(args) {
            Ok(args) => args,
            Err(error) => {
                return Ok(ToolResult::error(format!(
                    "invalid operator request lookup: {error}"
                )))
            }
        };
        let view = match self.store.get(&args.request_id) {
            Ok(view) => view,
            Err(_) => return Ok(ToolResult::error("operator request is unavailable")),
        };
        if view.request.channel_id != self.channel_id {
            return Ok(ToolResult::error("operator request is unavailable"));
        }
        Ok(ToolResult::structured_json(&json!(view)))
    }
}

fn agent_task_contract_input_schema() -> Value {
    json!({
        "type": "object",
        "additionalProperties": false,
        "required": [
            "schema_version",
            "contract_id",
            "revision",
            "objective",
            "this_attempt_only",
            "acceptance_criteria",
            "authority_boundary",
            "attempt_no",
            "attempt_budget"
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "const": "agent_bridge.agent_task_contract.v0"
            },
            "contract_id": { "type": "string", "minLength": 1 },
            "revision": { "type": "integer", "minimum": 1 },
            "objective": { "type": "string", "minLength": 1 },
            "parent_evidence_refs": {
                "type": "array",
                "default": [],
                "items": {
                    "type": "object",
                    "additionalProperties": false,
                    "required": ["reference", "verdict", "authority_boundary"],
                    "properties": {
                        "reference": { "type": "string", "minLength": 1 },
                        "verdict": {
                            "type": "string",
                            "enum": ["accepted", "accepted_with_deviation", "rejected"]
                        },
                        "authority_boundary": {
                            "type": "string",
                            "enum": ["read_only", "project_write", "external_write", "runtime_enablement"]
                        }
                    }
                }
            },
            "this_attempt_only": {
                "type": "array",
                "items": { "type": "string", "minLength": 1 },
                "minItems": 1
            },
            "reserved_actions": {
                "type": "array",
                "items": { "type": "string" },
                "default": []
            },
            "continuity_locks": {
                "type": "object",
                "additionalProperties": { "type": "string" },
                "default": {}
            },
            "allowed_changes": {
                "type": "array",
                "items": { "type": "string" },
                "default": []
            },
            "acceptance_criteria": {
                "type": "array",
                "items": { "type": "string", "minLength": 1 },
                "minItems": 1
            },
            "authority_boundary": {
                "type": "string",
                "enum": ["read_only", "project_write", "external_write", "runtime_enablement"]
            },
            "attempt_no": { "type": "integer", "minimum": 1 },
            "attempt_budget": { "type": "integer", "minimum": 1 },
            "changed_variable": { "type": ["string", "null"] },
            "planned_state": {
                "type": "object",
                "additionalProperties": { "type": "string" },
                "default": {}
            },
            "observed_state": {
                "type": "object",
                "additionalProperties": { "type": "string" },
                "default": {}
            }
        }
    })
}

fn operator_request_view_schema() -> Value {
    json!({
        "type": "object",
        "additionalProperties": false,
        "required": ["status", "request", "decision", "execution_allowed", "next_step"],
        "properties": {
            "status": {
                "type": "string",
                "enum": ["pending", "expired", "approved_for_executor_review", "rejected"]
            },
            "request": { "type": "object", "additionalProperties": true },
            "decision": { "type": ["object", "null"] },
            "execution_allowed": { "type": "boolean", "const": false },
            "next_step": { "type": "string" }
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request_args() -> Value {
        json!({
            "requested_capability": "project_write",
            "target": "/tmp/project",
            "summary": "Prepare a reversible patch",
            "ttl_secs": 600,
            "contract": {
                "schema_version": "agent_bridge.agent_task_contract.v0",
                "contract_id": "chatgpt-collab-mcp-test",
                "revision": 1,
                "objective": "Stage a bounded project request",
                "parent_evidence_refs": [{
                    "reference": "owner-reviewed-boundary",
                    "verdict": "accepted",
                    "authority_boundary": "project_write"
                }],
                "this_attempt_only": ["stage request evidence"],
                "reserved_actions": ["execute request"],
                "allowed_changes": ["private operator queue"],
                "acceptance_criteria": ["execution_allowed remains false"],
                "authority_boundary": "project_write",
                "attempt_no": 1,
                "attempt_budget": 1,
                "changed_variable": "request queue"
            }
        })
    }

    #[tokio::test]
    async fn stage_and_get_are_channel_scoped_and_non_executing() {
        let temp = tempfile::tempdir().unwrap();
        let store = OperatorRequestStore::new(temp.path().join("queue"));
        let stage = OperatorRequestStageTool::new(
            store.clone(),
            "chatgpt-desktop".to_string(),
            BTreeSet::from([OperatorCapability::ProjectWrite]),
        );
        let mut ctx = ToolContext::default();
        ctx.session_id = Some(SessionId::from_raw("conversation-1"));
        let staged = stage.execute(request_args(), &ctx).await.unwrap();
        assert!(!staged.is_error);
        let payload = staged.structured_content.unwrap();
        assert_eq!(payload["status"], "pending");
        assert_eq!(payload["execution_allowed"], false);
        let request_id = payload["request"]["request_id"].as_str().unwrap();

        let get = OperatorRequestGetTool::new(store.clone(), "chatgpt-desktop".to_string());
        let fetched = get
            .execute(json!({ "request_id": request_id }), &ToolContext::default())
            .await
            .unwrap();
        assert!(!fetched.is_error);
        assert_eq!(
            fetched.structured_content.unwrap()["execution_allowed"],
            false
        );

        let other_channel = OperatorRequestGetTool::new(store, "other-channel".to_string());
        let denied = other_channel
            .execute(json!({ "request_id": request_id }), &ToolContext::default())
            .await
            .unwrap();
        assert!(denied.is_error);
        assert!(denied.structured_content.is_none());
    }
}
