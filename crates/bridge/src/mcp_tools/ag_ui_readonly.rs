//! Default-off MCP transport for the pure AG-UI 0.0.57 projection.

use crate::ag_ui_readonly_projection::{
    project_ag_ui_readonly, AgUiProjectionError, CORE_VERSION, MAX_EVENTS, MAX_IDENTIFIER_BYTES,
    PROJECTION_SCHEMA, PROJECTION_SCHEMA_V1, PROTOCOL_NAME, REQUEST_SCHEMA, REQUEST_SCHEMA_V1,
};
use ab_core::Result;
use ab_mcp::{ContentBlock, McpTool, ToolAnnotations, ToolContext, ToolResult, ToolSchema};
use async_trait::async_trait;
use serde_json::{json, Value};

pub(super) const TOOL_NAME: &str = "ag_ui_readonly_project";
const PROJECTION_ERROR_SCHEMA: &str = "agent_bridge.ag_ui_readonly_projection_error.v0";

pub struct AgUiReadonlyProjectTool;

impl AgUiReadonlyProjectTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for AgUiReadonlyProjectTool {
    fn name(&self) -> &'static str {
        TOOL_NAME
    }

    fn title(&self) -> String {
        "Project an AG-UI 0.0.57 batch read-only".into()
    }

    fn annotations(&self) -> Option<ToolAnnotations> {
        Some(ToolAnnotations::read_only())
    }

    fn output_schema(&self) -> Option<Value> {
        Some(json!({
            "oneOf": [
                projection_output_schema(),
                projection_output_schema_v1(),
                projection_error_output_schema()
            ]
        }))
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Project one caller-supplied, bounded AG-UI 0.0.57 batch into a content-minimized read-only observation. Request v0 preserves the strict legacy completeness contract; request v1 separately reports run-structure and tool-result-observation completeness. Neither contract grants action authority or makes an external-effect claim. Default-off: exposed only by codex-ag-ui-readonly or all-dev; other tools in those toolsets retain their own authority.".into(),
            input_schema: projection_input_schema(),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let result = match project_ag_ui_readonly(&args) {
            Ok(projection) => ToolResult::structured_json(&projection),
            Err(error) => projection_error_result(error),
        };
        Ok(result)
    }
}

fn projection_input_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "schema": {"enum": [REQUEST_SCHEMA, REQUEST_SCHEMA_V1]},
            "protocol": {
                "type": "object",
                "properties": {
                    "name": {"const": PROTOCOL_NAME},
                    "core_version": {"const": CORE_VERSION}
                },
                "required": ["name", "core_version"],
                "additionalProperties": false
            },
            "source": {
                "type": "object",
                "properties": {
                    "adapter_id": {
                        "type": "string",
                        "maxLength": MAX_IDENTIFIER_BYTES,
                        "description": "Bounded again by the projector's UTF-8 byte limit."
                    },
                    "agent_id_hash": {
                        "type": "string",
                        "maxLength": MAX_IDENTIFIER_BYTES,
                        "description": "Bounded again by the projector's UTF-8 byte limit."
                    }
                },
                "required": ["adapter_id", "agent_id_hash"],
                "additionalProperties": false
            },
            "events": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_EVENTS,
                "items": {"type": "object"}
            }
        },
        "required": ["schema", "protocol", "source", "events"],
        "additionalProperties": false
    })
}

fn projection_output_schema() -> Value {
    projection_output_schema_for(PROJECTION_SCHEMA, false)
}

fn projection_output_schema_v1() -> Value {
    projection_output_schema_for(PROJECTION_SCHEMA_V1, true)
}

fn projection_output_schema_for(schema: &'static str, split_completeness: bool) -> Value {
    let claims_properties = if split_completeness {
        json!({
            "all_actions_traceable": {"const": false},
            "external_effects_verified": {"const": false},
            "run_stream_complete": {
                "type": "boolean",
                "description": "True only when run, step, and tool-request structure is complete and violation-free; it does not require or imply a tool result."
            },
            "tool_result_observation_complete": {
                "type": "boolean",
                "description": "True only when every projected tool request has a TOOL_CALL_RESULT observation; this is not external-effect verification."
            },
            "stream_complete": {
                "type": "boolean",
                "description": "Conservative aggregate: run_stream_complete and tool_result_observation_complete."
            }
        })
    } else {
        json!({
            "all_actions_traceable": {"const": false},
            "external_effects_verified": {"const": false},
            "stream_complete": {"type": "boolean"}
        })
    };
    let claims_required = if split_completeness {
        json!([
            "all_actions_traceable",
            "external_effects_verified",
            "run_stream_complete",
            "tool_result_observation_complete",
            "stream_complete"
        ])
    } else {
        json!([
            "all_actions_traceable",
            "external_effects_verified",
            "stream_complete"
        ])
    };

    json!({
        "type": "object",
        "properties": {
            "schema": {"const": schema},
            "read_only": {"const": true},
            "executes_actions": {"const": false},
            "writes_store": {"const": false},
            "changes_policy": {"const": false},
            "protocol": {
                "type": "object",
                "properties": {
                    "name": {"const": PROTOCOL_NAME},
                    "core_version": {"const": CORE_VERSION}
                },
                "required": ["name", "core_version"],
                "additionalProperties": false
            },
            "counts": {
                "type": "object",
                "properties": {
                    "input_events": nonnegative_integer_schema(),
                    "projected_events": nonnegative_integer_schema(),
                    "omitted_content_events": nonnegative_integer_schema(),
                    "unknown_event_types": nonnegative_integer_schema(),
                    "violations": nonnegative_integer_schema()
                },
                "required": [
                    "input_events", "projected_events", "omitted_content_events",
                    "unknown_event_types", "violations"
                ],
                "additionalProperties": false
            },
            "observations": observation_output_schema(),
            "runs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "run_id_hash": {"type": "string"},
                        "thread_id_hash": {"type": "string"},
                        "parent_run_id_hash": {"type": ["string", "null"]},
                        "error_code_hash": {"type": ["string", "null"]},
                        "status": {"enum": ["open", "finished", "interrupted", "error"]},
                        "verdict": {
                            "type": "object",
                            "properties": {
                                "status": {"enum": ["unknown", "not_verified"]},
                                "method": {"const": "ag_ui_event_projection_no_external_effect_readback"},
                                "evidence": {"type": "null"}
                            },
                            "required": ["status", "method", "evidence"],
                            "additionalProperties": false
                        }
                    },
                    "required": [
                        "run_id_hash", "thread_id_hash", "parent_run_id_hash",
                        "error_code_hash", "status", "verdict"
                    ],
                    "additionalProperties": false
                }
            },
            "tool_calls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool_call_id_hash": {"type": "string"},
                        "tool_name_hash": {"type": "string"},
                        "run_id_hash": {"type": "string"},
                        "status": {"enum": [
                            "started", "args_observed", "request_closed", "result_observed"
                        ]},
                        "args_chunks": nonnegative_integer_schema(),
                        "args_bytes": nonnegative_integer_schema(),
                        "result_size_bucket": {"type": ["string", "null"]},
                        "verdict": {
                            "type": "object",
                            "properties": {
                                "status": {"const": "unknown"},
                                "method": {"const": "ag_ui_event_projection_no_effect_readback"},
                                "evidence": {"type": "null"}
                            },
                            "required": ["status", "method", "evidence"],
                            "additionalProperties": false
                        }
                    },
                    "required": [
                        "tool_call_id_hash", "tool_name_hash", "run_id_hash", "status",
                        "args_chunks", "args_bytes", "result_size_bucket", "verdict"
                    ],
                    "additionalProperties": false
                }
            },
            "projected_events": {"type": "array", "items": {"type": "object"}},
            "violations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event_index": nonnegative_integer_schema(),
                        "code": {"type": "string"}
                    },
                    "required": ["event_index", "code"],
                    "additionalProperties": false
                }
            },
            "claims": {
                "type": "object",
                "properties": claims_properties,
                "required": claims_required,
                "additionalProperties": false
            }
        },
        "required": [
            "schema", "read_only", "executes_actions", "writes_store", "changes_policy",
            "protocol", "counts", "observations", "runs", "tool_calls", "projected_events",
            "violations", "claims"
        ],
        "additionalProperties": false
    })
}

fn observation_output_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "content_bytes_omitted": nonnegative_integer_schema(),
            "tool_args_chunks": nonnegative_integer_schema(),
            "tool_args_bytes": nonnegative_integer_schema(),
            "tool_chunk_events": nonnegative_integer_schema(),
            "tool_chunk_bytes": nonnegative_integer_schema(),
            "message_snapshots": nonnegative_integer_schema(),
            "messages_observed": nonnegative_integer_schema(),
            "state_snapshot_keys": nonnegative_integer_schema(),
            "state_snapshot_bytes": nonnegative_integer_schema(),
            "state_delta_operations": nonnegative_integer_schema(),
            "state_delta_bytes": nonnegative_integer_schema(),
            "activity_events": nonnegative_integer_schema(),
            "activity_payload_bytes": nonnegative_integer_schema(),
            "extension_events": nonnegative_integer_schema(),
            "extension_payload_bytes": nonnegative_integer_schema(),
            "error_message_bytes": nonnegative_integer_schema(),
            "run_payload_bytes": nonnegative_integer_schema()
        },
        "required": [
            "content_bytes_omitted", "tool_args_chunks", "tool_args_bytes",
            "tool_chunk_events", "tool_chunk_bytes", "message_snapshots",
            "messages_observed", "state_snapshot_keys", "state_snapshot_bytes",
            "state_delta_operations", "state_delta_bytes", "activity_events",
            "activity_payload_bytes", "extension_events", "extension_payload_bytes",
            "error_message_bytes", "run_payload_bytes"
        ],
        "additionalProperties": false
    })
}

fn projection_error_output_schema() -> Value {
    json!({
        "type": "object",
        "properties": {
            "schema": {"const": PROJECTION_ERROR_SCHEMA},
            "read_only": {"const": true},
            "executes_actions": {"const": false},
            "writes_store": {"const": false},
            "changes_policy": {"const": false},
            "code": {
                "enum": [
                    "request_serialization_failed", "request_too_large",
                    "invalid_request_field", "unexpected_request_field",
                    "unsupported_request_schema",
                    "unsupported_protocol", "invalid_event_count", "invalid_event_field",
                    "identifier_too_long", "source_identifier_too_long",
                    "canonicalization_failed"
                ]
            },
            "details": {
                "type": "object",
                "properties": {
                    "event_index": nonnegative_integer_schema(),
                    "field": {"type": "string"},
                    "object": {"enum": ["request", "protocol", "source"]},
                    "actual_bytes": nonnegative_integer_schema(),
                    "max_bytes": nonnegative_integer_schema(),
                    "actual_events": nonnegative_integer_schema(),
                    "max_events": nonnegative_integer_schema()
                },
                "additionalProperties": false
            }
        },
        "required": [
            "schema", "read_only", "executes_actions", "writes_store", "changes_policy",
            "code", "details"
        ],
        "additionalProperties": false
    })
}

fn nonnegative_integer_schema() -> Value {
    json!({"type": "integer", "minimum": 0})
}

fn projection_error_result(error: AgUiProjectionError) -> ToolResult {
    let (code, details) = projection_error_parts(error);
    let structured = json!({
        "schema": PROJECTION_ERROR_SCHEMA,
        "read_only": true,
        "executes_actions": false,
        "writes_store": false,
        "changes_policy": false,
        "code": code,
        "details": details,
    });
    ToolResult {
        content: vec![ContentBlock::text(code)],
        structured_content: Some(structured),
        is_error: true,
        backend_id: None,
    }
}

fn projection_error_parts(error: AgUiProjectionError) -> (&'static str, Value) {
    match error {
        AgUiProjectionError::RequestSerialization => ("request_serialization_failed", json!({})),
        AgUiProjectionError::RequestTooLarge { actual, max } => (
            "request_too_large",
            json!({"actual_bytes": actual, "max_bytes": max}),
        ),
        AgUiProjectionError::InvalidRequestField { field } => {
            ("invalid_request_field", json!({"field": field}))
        }
        AgUiProjectionError::UnexpectedRequestField { object } => {
            ("unexpected_request_field", json!({"object": object}))
        }
        AgUiProjectionError::UnsupportedRequestSchema => ("unsupported_request_schema", json!({})),
        AgUiProjectionError::UnsupportedProtocol => ("unsupported_protocol", json!({})),
        AgUiProjectionError::InvalidEventCount { actual, max } => (
            "invalid_event_count",
            json!({"actual_events": actual, "max_events": max}),
        ),
        AgUiProjectionError::InvalidEventField { event_index, field } => (
            "invalid_event_field",
            json!({"event_index": event_index, "field": field}),
        ),
        AgUiProjectionError::IdentifierTooLong {
            event_index,
            field,
            actual,
            max,
        } => (
            "identifier_too_long",
            json!({
                "event_index": event_index,
                "field": field,
                "actual_bytes": actual,
                "max_bytes": max,
            }),
        ),
        AgUiProjectionError::SourceIdentifierTooLong { field, actual, max } => (
            "source_identifier_too_long",
            json!({"field": field, "actual_bytes": actual, "max_bytes": max}),
        ),
        AgUiProjectionError::Canonicalization => ("canonicalization_failed", json!({})),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use futures::executor::block_on;

    const FIXTURES: &[&str] = &[
        include_str!("../../tests/fixtures/ag_ui_readonly_projection/complete_text_run.json"),
        include_str!("../../tests/fixtures/ag_ui_readonly_projection/complete_tool_run.json"),
        include_str!("../../tests/fixtures/ag_ui_readonly_projection/openbot_tool_request_v1.json"),
        include_str!("../../tests/fixtures/ag_ui_readonly_projection/run_error.json"),
        include_str!("../../tests/fixtures/ag_ui_readonly_projection/interrupted_run.json"),
        include_str!("../../tests/fixtures/ag_ui_readonly_projection/truncated_stream.json"),
        include_str!("../../tests/fixtures/ag_ui_readonly_projection/reordered_cross_run.json"),
        include_str!("../../tests/fixtures/ag_ui_readonly_projection/content_leak_canaries.json"),
    ];

    fn valid_request(events: Vec<Value>) -> Value {
        json!({
            "schema": REQUEST_SCHEMA,
            "protocol": {"name": PROTOCOL_NAME, "core_version": CORE_VERSION},
            "source": {"adapter_id": "wrapper-tests", "agent_id_hash": "agent"},
            "events": events,
        })
    }

    fn execute(args: Value) -> ToolResult {
        block_on(AgUiReadonlyProjectTool::new().execute(args, &ToolContext::default()))
            .expect("wrapper execution")
    }

    fn text(result: &ToolResult) -> &str {
        let Some(ContentBlock::Text { text }) = result.content.first() else {
            panic!("expected one text content block")
        };
        text
    }

    fn contains_exact_string(value: &Value, needle: &str) -> bool {
        match value {
            Value::String(value) => value == needle,
            Value::Array(values) => values
                .iter()
                .any(|value| contains_exact_string(value, needle)),
            Value::Object(values) => values
                .values()
                .any(|value| contains_exact_string(value, needle)),
            Value::Null | Value::Bool(_) | Value::Number(_) => false,
        }
    }

    fn production_source() -> &'static str {
        include_str!("ag_ui_readonly.rs")
            .split("\n#[cfg(test)]")
            .next()
            .expect("production source prefix")
    }

    fn function_body<'a>(source: &'a str, signature: &str) -> &'a str {
        let function_start = source.find(signature).expect("function signature");
        let brace_start = source[function_start..]
            .find('{')
            .map(|offset| function_start + offset)
            .expect("function opening brace");
        let mut depth = 0usize;
        for (offset, byte) in source.as_bytes()[brace_start..].iter().enumerate() {
            match byte {
                b'{' => depth += 1,
                b'}' => {
                    depth -= 1;
                    if depth == 0 {
                        return &source[brace_start + 1..brace_start + offset];
                    }
                }
                _ => {}
            }
        }
        panic!("function closing brace")
    }

    #[test]
    fn descriptor_is_bounded_read_only_and_closed_at_envelope_layers() {
        let tool = AgUiReadonlyProjectTool::new();
        assert_eq!(tool.name(), TOOL_NAME);
        assert_eq!(tool.title(), "Project an AG-UI 0.0.57 batch read-only");
        assert_eq!(tool.annotations(), Some(ToolAnnotations::read_only()));

        let input = tool.schema().input_schema;
        assert_eq!(input["additionalProperties"], false);
        assert_eq!(
            input["properties"]["schema"]["enum"],
            json!([REQUEST_SCHEMA, REQUEST_SCHEMA_V1])
        );
        assert_eq!(
            input["properties"]["protocol"]["additionalProperties"],
            false
        );
        assert_eq!(input["properties"]["source"]["additionalProperties"], false);
        assert_eq!(input["properties"]["events"]["minItems"], 1);
        assert_eq!(input["properties"]["events"]["maxItems"], MAX_EVENTS);
        assert_eq!(
            input["properties"]["source"]["properties"]["adapter_id"]["maxLength"],
            MAX_IDENTIFIER_BYTES
        );

        let output = tool.output_schema().expect("output schema");
        for branch in output["oneOf"].as_array().expect("output variants") {
            assert_eq!(branch["properties"]["read_only"]["const"], true);
            assert_eq!(branch["properties"]["executes_actions"]["const"], false);
            assert_eq!(branch["properties"]["writes_store"]["const"], false);
            assert_eq!(branch["properties"]["changes_policy"]["const"], false);
            assert_eq!(branch["additionalProperties"], false);
        }

        let success_branches = output["oneOf"]
            .as_array()
            .expect("output variants")
            .iter()
            .filter(|branch| {
                matches!(
                    branch["properties"]["schema"]["const"].as_str(),
                    Some(PROJECTION_SCHEMA | PROJECTION_SCHEMA_V1)
                )
            })
            .collect::<Vec<_>>();
        assert_eq!(success_branches.len(), 2);
        let v0 = success_branches
            .iter()
            .find(|branch| branch["properties"]["schema"]["const"] == PROJECTION_SCHEMA)
            .expect("v0 output schema");
        assert!(v0["properties"]["claims"]["properties"]
            .get("run_stream_complete")
            .is_none());
        let v1 = success_branches
            .iter()
            .find(|branch| branch["properties"]["schema"]["const"] == PROJECTION_SCHEMA_V1)
            .expect("v1 output schema");
        assert_eq!(
            v1["properties"]["claims"]["required"],
            json!([
                "all_actions_traceable",
                "external_effects_verified",
                "run_stream_complete",
                "tool_result_observation_complete",
                "stream_complete"
            ])
        );
        assert_eq!(v1["properties"]["claims"]["additionalProperties"], false);
    }

    #[test]
    fn wrapper_matches_the_direct_projector_for_every_fixed_fixture() {
        for source in FIXTURES {
            let args: Value = serde_json::from_str(source).expect("fixture JSON");
            let direct = project_ag_ui_readonly(&args).expect("fixture projection");
            let result = execute(args);
            assert!(!result.is_error);
            assert_eq!(result.structured_content, Some(direct.clone()));
            assert_eq!(
                serde_json::from_str::<Value>(text(&result)).expect("projection text JSON"),
                direct
            );
        }
    }

    #[test]
    fn reachable_failures_are_typed_and_text_contains_only_the_stable_code() {
        let cases = [
            (
                json!({}),
                "invalid_request_field",
                Some(("field", json!("schema"))),
            ),
            (
                json!({
                    "schema": REQUEST_SCHEMA,
                    "protocol": {"name": PROTOCOL_NAME, "core_version": CORE_VERSION},
                    "source": {"adapter_id": "adapter", "agent_id_hash": "agent"},
                    "events": [{"type": "RUN_STARTED", "threadId": "thread", "runId": "run"}],
                    "endpoint_url_canary": "https://internal.example.test/ag-ui?token=request-secret"
                }),
                "unexpected_request_field",
                Some(("object", json!("request"))),
            ),
            (
                json!({
                    "schema": REQUEST_SCHEMA,
                    "protocol": {
                        "name": PROTOCOL_NAME,
                        "core_version": CORE_VERSION,
                        "authorization_canary": "Bearer protocol-secret"
                    },
                    "source": {"adapter_id": "adapter", "agent_id_hash": "agent"},
                    "events": [{"type": "RUN_STARTED", "threadId": "thread", "runId": "run"}]
                }),
                "unexpected_request_field",
                Some(("object", json!("protocol"))),
            ),
            (
                json!({
                    "schema": REQUEST_SCHEMA,
                    "protocol": {"name": PROTOCOL_NAME, "core_version": CORE_VERSION},
                    "source": {
                        "adapter_id": "adapter",
                        "agent_id_hash": "agent",
                        "workspace_path_canary": "/Users/private/source-secret"
                    },
                    "events": [{"type": "RUN_STARTED", "threadId": "thread", "runId": "run"}]
                }),
                "unexpected_request_field",
                Some(("object", json!("source"))),
            ),
            (
                json!({
                    "schema": "wrong",
                    "protocol": {"name": PROTOCOL_NAME, "core_version": CORE_VERSION},
                    "source": {"adapter_id": "adapter", "agent_id_hash": "agent"},
                    "events": [{}]
                }),
                "unsupported_request_schema",
                None,
            ),
            (
                json!({
                    "schema": REQUEST_SCHEMA,
                    "protocol": {"name": PROTOCOL_NAME, "core_version": "0.0.58"},
                    "source": {"adapter_id": "adapter", "agent_id_hash": "agent"},
                    "events": [{}]
                }),
                "unsupported_protocol",
                None,
            ),
            (valid_request(vec![]), "invalid_event_count", None),
            (
                valid_request(vec![json!({
                    "type": "RUN_STARTED",
                    "threadId": {"rejected": "field-shape-canary"},
                    "runId": "run"
                })]),
                "invalid_event_field",
                Some(("field", json!("threadId"))),
            ),
            (
                valid_request(vec![json!({
                    "type": "RUN_STARTED",
                    "threadId": "thread",
                    "runId": "identifier-canary".repeat(20)
                })]),
                "identifier_too_long",
                Some(("field", json!("runId"))),
            ),
            (
                json!({
                    "schema": REQUEST_SCHEMA,
                    "protocol": {"name": PROTOCOL_NAME, "core_version": CORE_VERSION},
                    "source": {
                        "adapter_id": "source-identifier-canary".repeat(20),
                        "agent_id_hash": "agent"
                    },
                    "events": [{"type": "RUN_STARTED", "threadId": "thread", "runId": "run"}]
                }),
                "source_identifier_too_long",
                Some(("field", json!("adapter_id"))),
            ),
            (
                json!({
                    "schema": REQUEST_SCHEMA,
                    "protocol": {"name": PROTOCOL_NAME, "core_version": CORE_VERSION},
                    "source": {"adapter_id": "adapter", "agent_id_hash": "agent"},
                    "events": [{
                        "type": "CUSTOM",
                        "name": "size-canary",
                        "value": "x".repeat(crate::ag_ui_readonly_projection::MAX_REQUEST_BYTES)
                    }]
                }),
                "request_too_large",
                None,
            ),
        ];

        for (args, expected_code, expected_detail) in cases {
            let rejected_input = serde_json::to_string(&args).expect("input JSON");
            let result = execute(args);
            assert!(result.is_error);
            assert_eq!(result.content.len(), 1);
            assert_eq!(text(&result), expected_code);
            let structured = result.structured_content.as_ref().expect("typed error");
            assert_eq!(structured["schema"], PROJECTION_ERROR_SCHEMA);
            assert_eq!(structured["code"], expected_code);
            assert_eq!(structured["read_only"], true);
            assert_eq!(structured["executes_actions"], false);
            assert_eq!(structured["writes_store"], false);
            assert_eq!(structured["changes_policy"], false);
            if let Some((key, value)) = expected_detail {
                assert_eq!(structured["details"][key], value);
            }
            let serialized = serde_json::to_string(&structured).expect("error JSON");
            for canary in [
                "field-shape-canary",
                "identifier-canaryidentifier-canary",
                "source-identifier-canarysource-identifier-canary",
                "size-canary",
                "endpoint_url_canary",
                "https://internal.example.test/ag-ui?token=request-secret",
                "authorization_canary",
                "Bearer protocol-secret",
                "workspace_path_canary",
                "/Users/private/source-secret",
            ] {
                if rejected_input.contains(canary) {
                    assert!(!serialized.contains(canary));
                    assert!(!text(&result).contains(canary));
                }
            }
        }
    }

    #[test]
    fn exact_verified_value_is_absent_from_success_and_error_channels() {
        for source in FIXTURES {
            let args: Value = serde_json::from_str(source).expect("fixture JSON");
            let result = execute(args);
            assert!(!contains_exact_string(
                result.structured_content.as_ref().expect("projection"),
                "verified"
            ));
            assert_ne!(text(&result), "verified");
        }

        let error = execute(json!({"rejected": "verified"}));
        assert!(!contains_exact_string(
            error.structured_content.as_ref().expect("typed error"),
            "verified"
        ));
        assert_ne!(text(&error), "verified");
    }

    #[test]
    fn static_architecture_gate_keeps_the_wrapper_fieldless_and_authority_free() {
        let source = production_source();
        assert!(source.contains("pub struct AgUiReadonlyProjectTool;"));
        assert!(source.contains("pub fn new() -> Self"));
        assert!(!source.contains("use super::*"));
        assert_eq!(source.matches("project_ag_ui_readonly(&args)").count(), 1);

        let execute_body = function_body(source, "async fn execute");
        assert!(execute_body.contains("project_ag_ui_readonly(&args)"));
        assert!(!execute_body.contains(".await"));
        assert!(!execute_body.contains("unsafe"));

        for forbidden in [
            "Hub",
            "StateStore",
            "record_semantic_event",
            "ToolPolicy",
            "TokioCommand",
            "crate::hub",
            "ab_store",
            "crate::security",
            "crate::embodiment",
            "crate::browser",
            "crate::mobile",
            "crate::world_tools",
            "reqwest",
            "std::process",
            "tokio",
            "std::fs",
            "std::net",
            "std::env",
            "std::thread",
            "thread::spawn",
            "spawn_blocking",
            "callback",
        ] {
            assert!(
                !source.contains(forbidden),
                "wrapper production source contains forbidden authority token {forbidden}"
            );
        }

        for required in [
            "ToolAnnotations::read_only()",
            "\"executes_actions\": {\"const\": false}",
            "\"writes_store\": {\"const\": false}",
            "\"changes_policy\": {\"const\": false}",
        ] {
            assert!(
                source.contains(required),
                "missing static contract {required}"
            );
        }
    }

    #[test]
    fn source_registration_matrix_is_explicit_and_default_off() {
        let exposed = |toolset: Option<&str>, profile: Option<&str>| {
            super::super::exposed_tool_names_for(toolset, None, profile)
                .into_iter()
                .any(|name| name == TOOL_NAME)
        };

        assert!(!exposed(None, None), "unset/default must stay closed");
        for profile in ["essential", "compact", "standard", "all"] {
            assert!(
                !exposed(None, Some(profile)),
                "generic profile {profile} must stay closed"
            );
        }
        for toolset in [
            "codex-essential",
            "codex-lean",
            "claude-standard",
            "gemini-lean",
            "chatgpt-read",
            "chatgpt-collab",
            "hook-lifecycle",
        ] {
            assert!(
                !exposed(Some(toolset), None),
                "existing toolset {toolset} must stay closed"
            );
        }

        assert!(
            exposed(Some("codex-ag-ui-readonly"), None),
            "dedicated opt-in toolset must expose the projector"
        );
        assert!(
            exposed(Some("all-dev"), None),
            "explicit broad development toolset must expose the projector"
        );
    }

    #[test]
    fn dedicated_toolset_is_exactly_codex_lean_plus_the_projector() {
        let names = |toolset| {
            super::super::exposed_tool_names_for(Some(toolset), None, None)
                .into_iter()
                .collect::<std::collections::BTreeSet<_>>()
        };
        let lean = names("codex-lean");
        let opted_in = names("codex-ag-ui-readonly");
        let mut expected = lean;
        expected.insert(TOOL_NAME.to_string());
        assert_eq!(opted_in, expected);

        let policy = super::super::ToolPolicy::from_values(
            Some("codex-ag-ui-readonly"),
            None,
            None,
            Some("all"),
        );
        assert_eq!(policy.label(), "codex-ag-ui-readonly");
        assert_eq!(policy.profile().label(), "essential");
        assert_eq!(policy.extras(), vec![TOOL_NAME]);
    }
}
