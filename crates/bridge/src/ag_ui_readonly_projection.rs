//! Pure, content-minimizing AG-UI 0.0.57 event projection.
//!
//! The projector accepts only caller-supplied JSON and returns in-memory JSON.
//! It deliberately owns no transport, store, process, browser, mobile, lease,
//! policy, or MCP registration handle. AG-UI lifecycle events are observations;
//! none of them can establish a verified external effect.

use std::collections::BTreeMap;

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use thiserror::Error;

pub const REQUEST_SCHEMA: &str = "agent_bridge.ag_ui_readonly_projection_request.v0";
pub const PROJECTION_SCHEMA: &str = "agent_bridge.ag_ui_readonly_projection.v0";
pub const PROTOCOL_NAME: &str = "ag-ui";
pub const CORE_VERSION: &str = "0.0.57";
pub const MAX_EVENTS: usize = 500;
pub const MAX_REQUEST_BYTES: usize = 1024 * 1024;
pub const MAX_IDENTIFIER_BYTES: usize = 256;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum AgUiProjectionError {
    #[error("request serialization failed")]
    RequestSerialization,
    #[error("request exceeds the {max} byte budget ({actual} bytes)")]
    RequestTooLarge { actual: usize, max: usize },
    #[error("request field '{field}' is missing or has the wrong type")]
    InvalidRequestField { field: &'static str },
    #[error("request schema is unsupported")]
    UnsupportedRequestSchema,
    #[error("AG-UI protocol name or core version is unsupported")]
    UnsupportedProtocol,
    #[error("events must contain between 1 and {max} entries (got {actual})")]
    InvalidEventCount { actual: usize, max: usize },
    #[error("event {event_index} field '{field}' is missing or has the wrong type")]
    InvalidEventField {
        event_index: usize,
        field: &'static str,
    },
    #[error(
        "event {event_index} identifier '{field}' exceeds the {max} byte budget ({actual} bytes)"
    )]
    IdentifierTooLong {
        event_index: usize,
        field: &'static str,
        actual: usize,
        max: usize,
    },
    #[error("source identifier '{field}' exceeds the {max} byte budget ({actual} bytes)")]
    SourceIdentifierTooLong {
        field: &'static str,
        actual: usize,
        max: usize,
    },
    #[error("projection canonicalization failed")]
    Canonicalization,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RunStatus {
    Open,
    Finished,
    Interrupted,
    Error,
}

impl RunStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Open => "open",
            Self::Finished => "finished",
            Self::Interrupted => "interrupted",
            Self::Error => "error",
        }
    }

    fn is_terminal(self) -> bool {
        self != Self::Open
    }

    fn verdict_status(self) -> &'static str {
        match self {
            Self::Interrupted | Self::Error => "not_verified",
            Self::Open | Self::Finished => "unknown",
        }
    }
}

#[derive(Debug, Clone)]
struct RunProjection {
    run_id_hash: String,
    thread_id_hash: String,
    parent_run_id_hash: Option<String>,
    error_code_hash: Option<String>,
    status: RunStatus,
}

impl RunProjection {
    fn to_json(&self) -> Value {
        json!({
            "run_id_hash": self.run_id_hash,
            "thread_id_hash": self.thread_id_hash,
            "parent_run_id_hash": self.parent_run_id_hash,
            "error_code_hash": self.error_code_hash,
            "status": self.status.as_str(),
            "verdict": {
                "status": self.status.verdict_status(),
                "method": "ag_ui_event_projection_no_external_effect_readback",
                "evidence": Value::Null,
            }
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ToolCallStatus {
    Started,
    ArgsObserved,
    RequestClosed,
    ResultObserved,
}

impl ToolCallStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Started => "started",
            Self::ArgsObserved => "args_observed",
            Self::RequestClosed => "request_closed",
            Self::ResultObserved => "result_observed",
        }
    }

    fn is_open(self) -> bool {
        self != Self::ResultObserved
    }
}

#[derive(Debug, Clone)]
struct ToolCallProjection {
    tool_call_id_hash: String,
    tool_name_hash: String,
    run_id_hash: String,
    status: ToolCallStatus,
    args_chunks: usize,
    args_bytes: usize,
    result_size_bucket: Option<&'static str>,
}

impl ToolCallProjection {
    fn to_json(&self) -> Value {
        json!({
            "tool_call_id_hash": self.tool_call_id_hash,
            "tool_name_hash": self.tool_name_hash,
            "run_id_hash": self.run_id_hash,
            "status": self.status.as_str(),
            "args_chunks": self.args_chunks,
            "args_bytes": self.args_bytes,
            "result_size_bucket": self.result_size_bucket,
            "verdict": {
                "status": "unknown",
                "method": "ag_ui_event_projection_no_effect_readback",
                "evidence": Value::Null,
            }
        })
    }
}

#[derive(Debug, Clone)]
struct Violation {
    index: usize,
    code: &'static str,
}

impl Violation {
    fn to_json(&self) -> Value {
        json!({"event_index": self.index, "code": self.code})
    }
}

#[derive(Debug, Default)]
struct Counters {
    omitted_content_events: usize,
    unknown_event_types: usize,
    content_bytes_omitted: usize,
    tool_args_chunks: usize,
    tool_args_bytes: usize,
    tool_chunk_events: usize,
    tool_chunk_bytes: usize,
    message_snapshots: usize,
    messages_observed: usize,
    state_snapshot_keys: usize,
    state_snapshot_bytes: usize,
    state_delta_operations: usize,
    state_delta_bytes: usize,
    activity_events: usize,
    activity_payload_bytes: usize,
    extension_events: usize,
    extension_payload_bytes: usize,
    error_message_bytes: usize,
    run_payload_bytes: usize,
}

/// Project one bounded AG-UI 0.0.57 batch without performing I/O or mutation.
pub fn project_ag_ui_readonly(input: &Value) -> Result<Value, AgUiProjectionError> {
    validate_request_budget(input)?;
    let request = input
        .as_object()
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "request" })?;

    let schema = request
        .get("schema")
        .and_then(Value::as_str)
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "schema" })?;
    if schema != REQUEST_SCHEMA {
        return Err(AgUiProjectionError::UnsupportedRequestSchema);
    }

    let protocol = request
        .get("protocol")
        .and_then(Value::as_object)
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "protocol" })?;
    let protocol_name = protocol.get("name").and_then(Value::as_str).ok_or(
        AgUiProjectionError::InvalidRequestField {
            field: "protocol.name",
        },
    )?;
    let core_version = protocol.get("core_version").and_then(Value::as_str).ok_or(
        AgUiProjectionError::InvalidRequestField {
            field: "protocol.core_version",
        },
    )?;
    if protocol_name != PROTOCOL_NAME || core_version != CORE_VERSION {
        return Err(AgUiProjectionError::UnsupportedProtocol);
    }

    let source = request
        .get("source")
        .and_then(Value::as_object)
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "source" })?;
    validate_source_identifier(source, "adapter_id")?;
    validate_source_identifier(source, "agent_id_hash")?;

    let events = request
        .get("events")
        .and_then(Value::as_array)
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "events" })?;
    if events.is_empty() || events.len() > MAX_EVENTS {
        return Err(AgUiProjectionError::InvalidEventCount {
            actual: events.len(),
            max: MAX_EVENTS,
        });
    }

    let mut counters = Counters::default();
    let mut runs = BTreeMap::<String, RunProjection>::new();
    let mut tool_calls = BTreeMap::<String, ToolCallProjection>::new();
    let mut projected_events = Vec::<Value>::new();
    let mut violations = Vec::<Violation>::new();
    let mut current_run_hash: Option<String> = None;

    for (index, event_value) in events.iter().enumerate() {
        let event = event_value
            .as_object()
            .ok_or(AgUiProjectionError::InvalidEventField {
                event_index: index,
                field: "event",
            })?;
        let event_type = required_string(event, index, "type")?;
        let mut omitted_event = event.contains_key("rawEvent");
        let mut omitted_bytes = event.get("rawEvent").map(serialized_len).unwrap_or(0);

        if event_type != "RUN_STARTED"
            && current_run_hash
                .as_ref()
                .and_then(|hash| runs.get(hash))
                .is_some_and(|run| run.status.is_terminal())
        {
            violations.push(Violation {
                index,
                code: "event_after_terminal_run",
            });
        }

        match event_type {
            "RUN_STARTED" => {
                let thread_id = required_identifier(event, index, "threadId")?;
                let run_id = required_identifier(event, index, "runId")?;
                let parent_run_id = optional_identifier(event, index, "parentRunId")?;
                if let Some(payload) = event.get("input") {
                    omitted_event = true;
                    omitted_bytes += serialized_len(payload);
                    counters.run_payload_bytes += serialized_len(payload);
                }

                if current_run_hash
                    .as_ref()
                    .and_then(|hash| runs.get(hash))
                    .is_some_and(|run| !run.status.is_terminal())
                {
                    violations.push(Violation {
                        index,
                        code: "run_started_before_prior_terminal",
                    });
                }

                let run_hash = domain_hash("run", run_id);
                let thread_hash = domain_hash("thread", thread_id);
                let parent_hash = parent_run_id.map(|value| domain_hash("run", value));
                if let Some(existing) = runs.get(&run_hash) {
                    violations.push(Violation {
                        index,
                        code: "duplicate_run_start",
                    });
                    if existing.thread_id_hash != thread_hash {
                        violations.push(Violation {
                            index,
                            code: "conflicting_thread_id",
                        });
                    }
                } else {
                    runs.insert(
                        run_hash.clone(),
                        RunProjection {
                            run_id_hash: run_hash.clone(),
                            thread_id_hash: thread_hash,
                            parent_run_id_hash: parent_hash,
                            error_code_hash: None,
                            status: RunStatus::Open,
                        },
                    );
                }
                current_run_hash = Some(run_hash.clone());
                projected_events.push(ssb_event(
                    index,
                    "run_opened",
                    &run_hash,
                    "agent_run",
                    "lifecycle",
                    "low",
                    false,
                    "unknown",
                    "ag_ui_run_started_observation",
                ));
            }
            "RUN_FINISHED" => {
                let thread_id = required_identifier(event, index, "threadId")?;
                let run_id = required_identifier(event, index, "runId")?;
                let run_hash = domain_hash("run", run_id);
                let thread_hash = domain_hash("thread", thread_id);
                let interrupted =
                    validate_run_outcome(event, index, &mut omitted_event, &mut omitted_bytes)?;
                if let Some(result) = event.get("result") {
                    omitted_event = true;
                    let bytes = serialized_len(result);
                    omitted_bytes += bytes;
                    counters.run_payload_bytes += bytes;
                }

                if current_run_hash.as_deref() != Some(run_hash.as_str()) {
                    violations.push(Violation {
                        index,
                        code: "conflicting_run_id",
                    });
                }
                mark_terminal_open_tools(&run_hash, index, &tool_calls, &mut violations);
                let status = if interrupted {
                    RunStatus::Interrupted
                } else {
                    RunStatus::Finished
                };
                if let Some(run) = runs.get_mut(&run_hash) {
                    if run.thread_id_hash != thread_hash {
                        violations.push(Violation {
                            index,
                            code: "conflicting_thread_id",
                        });
                    }
                    if run.status.is_terminal() {
                        violations.push(Violation {
                            index,
                            code: "duplicate_run_terminal",
                        });
                    }
                    run.status = status;
                } else {
                    violations.push(Violation {
                        index,
                        code: "run_terminal_before_start",
                    });
                }
                current_run_hash = Some(run_hash.clone());
                projected_events.push(ssb_event(
                    index,
                    "run_closed",
                    &run_hash,
                    "agent_run",
                    "lifecycle",
                    "low",
                    false,
                    status.verdict_status(),
                    if interrupted {
                        "ag_ui_run_interrupted_observation"
                    } else {
                        "ag_ui_run_finished_no_external_effect_readback"
                    },
                ));
            }
            "RUN_ERROR" => {
                let message = required_string(event, index, "message")?;
                omitted_event = true;
                omitted_bytes += message.len();
                counters.error_message_bytes += message.len();
                let code = optional_identifier(event, index, "code")?;
                if let Some(run_hash) = current_run_hash.clone() {
                    mark_terminal_open_tools(&run_hash, index, &tool_calls, &mut violations);
                    if let Some(run) = runs.get_mut(&run_hash) {
                        if run.status.is_terminal() {
                            violations.push(Violation {
                                index,
                                code: "duplicate_run_terminal",
                            });
                        }
                        run.status = RunStatus::Error;
                        run.error_code_hash = code.map(|value| domain_hash("error-code", value));
                    }
                    projected_events.push(ssb_event(
                        index,
                        "run_failed",
                        &run_hash,
                        "agent_run",
                        "lifecycle",
                        "low",
                        false,
                        "not_verified",
                        "ag_ui_run_error_observation",
                    ));
                } else {
                    violations.push(Violation {
                        index,
                        code: "run_error_before_start",
                    });
                }
            }
            "STEP_STARTED" | "STEP_FINISHED" => {
                let step_name = required_identifier(event, index, "stepName")?;
                require_active_run(index, &current_run_hash, &mut violations);
                let step_hash = domain_hash("step", step_name);
                projected_events.push(ssb_event(
                    index,
                    if event_type == "STEP_STARTED" {
                        "step_opened"
                    } else {
                        "step_closed"
                    },
                    &step_hash,
                    "agent_step",
                    "lifecycle",
                    "low",
                    false,
                    "unknown",
                    "ag_ui_step_lifecycle_observation",
                ));
            }
            "TOOL_CALL_START" => {
                let tool_call_id = required_identifier(event, index, "toolCallId")?;
                let tool_name = required_identifier(event, index, "toolCallName")?;
                optional_identifier(event, index, "parentMessageId")?;
                if let Some(run_hash) = active_run(index, &current_run_hash, &mut violations) {
                    let call_hash = domain_hash("tool-call", tool_call_id);
                    let tool_name_hash = domain_hash("tool-name", tool_name);
                    if let Some(existing) = tool_calls.get(&call_hash) {
                        violations.push(Violation {
                            index,
                            code: if existing.run_id_hash == run_hash {
                                "duplicate_tool_call_start"
                            } else {
                                "cross_run_tool_call_id_reuse"
                            },
                        });
                    } else {
                        tool_calls.insert(
                            call_hash.clone(),
                            ToolCallProjection {
                                tool_call_id_hash: call_hash.clone(),
                                tool_name_hash,
                                run_id_hash: run_hash,
                                status: ToolCallStatus::Started,
                                args_chunks: 0,
                                args_bytes: 0,
                                result_size_bucket: None,
                            },
                        );
                    }
                    projected_events.push(ssb_event(
                        index,
                        "intent_opened",
                        &call_hash,
                        "agent_tool_call",
                        "tool_call",
                        "medium",
                        true,
                        "unknown",
                        "ag_ui_tool_intent_no_execution_authority",
                    ));
                }
            }
            "TOOL_CALL_ARGS" => {
                let tool_call_id = required_identifier(event, index, "toolCallId")?;
                let delta = required_string(event, index, "delta")?;
                omitted_event = true;
                omitted_bytes += delta.len();
                counters.tool_args_chunks += 1;
                counters.tool_args_bytes += delta.len();
                if let Some(run_hash) = active_run(index, &current_run_hash, &mut violations) {
                    let call_hash = domain_hash("tool-call", tool_call_id);
                    match tool_calls.get_mut(&call_hash) {
                        None => violations.push(Violation {
                            index,
                            code: "tool_args_before_start",
                        }),
                        Some(call) if call.run_id_hash != run_hash => violations.push(Violation {
                            index,
                            code: "cross_run_tool_call_id_reuse",
                        }),
                        Some(call)
                            if matches!(
                                call.status,
                                ToolCallStatus::RequestClosed | ToolCallStatus::ResultObserved
                            ) =>
                        {
                            violations.push(Violation {
                                index,
                                code: "tool_args_after_end",
                            })
                        }
                        Some(call) => {
                            call.status = ToolCallStatus::ArgsObserved;
                            call.args_chunks += 1;
                            call.args_bytes += delta.len();
                        }
                    }
                }
            }
            "TOOL_CALL_END" => {
                let tool_call_id = required_identifier(event, index, "toolCallId")?;
                if let Some(run_hash) = active_run(index, &current_run_hash, &mut violations) {
                    let call_hash = domain_hash("tool-call", tool_call_id);
                    match tool_calls.get_mut(&call_hash) {
                        None => violations.push(Violation {
                            index,
                            code: "tool_end_before_start",
                        }),
                        Some(call) if call.run_id_hash != run_hash => violations.push(Violation {
                            index,
                            code: "cross_run_tool_call_id_reuse",
                        }),
                        Some(call)
                            if matches!(
                                call.status,
                                ToolCallStatus::RequestClosed | ToolCallStatus::ResultObserved
                            ) =>
                        {
                            violations.push(Violation {
                                index,
                                code: "duplicate_tool_call_end",
                            })
                        }
                        Some(call) => call.status = ToolCallStatus::RequestClosed,
                    }
                    projected_events.push(ssb_event(
                        index,
                        "request_closed",
                        &call_hash,
                        "agent_tool_call",
                        "tool_call",
                        "medium",
                        true,
                        "unknown",
                        "ag_ui_tool_call_end_no_dispatch_or_effect_proof",
                    ));
                }
            }
            "TOOL_CALL_RESULT" => {
                required_identifier(event, index, "messageId")?;
                let tool_call_id = required_identifier(event, index, "toolCallId")?;
                let content = required_string(event, index, "content")?;
                omitted_event = true;
                omitted_bytes += content.len();
                if let Some(run_hash) = active_run(index, &current_run_hash, &mut violations) {
                    let call_hash = domain_hash("tool-call", tool_call_id);
                    match tool_calls.get_mut(&call_hash) {
                        None => violations.push(Violation {
                            index,
                            code: "tool_result_before_start",
                        }),
                        Some(call) if call.run_id_hash != run_hash => violations.push(Violation {
                            index,
                            code: "cross_run_tool_call_id_reuse",
                        }),
                        Some(call) if call.status == ToolCallStatus::ResultObserved => violations
                            .push(Violation {
                                index,
                                code: "duplicate_tool_call_result",
                            }),
                        Some(call) => {
                            if call.status != ToolCallStatus::RequestClosed {
                                violations.push(Violation {
                                    index,
                                    code: "tool_result_before_end",
                                });
                            }
                            call.status = ToolCallStatus::ResultObserved;
                            call.result_size_bucket = Some(size_bucket(content.len()));
                        }
                    }
                    projected_events.push(ssb_event(
                        index,
                        "result_observed",
                        &call_hash,
                        "agent_tool_call",
                        "tool_call",
                        "medium",
                        true,
                        "unknown",
                        "ag_ui_tool_result_content_has_no_normative_effect_readback",
                    ));
                }
            }
            "TOOL_CALL_CHUNK" => {
                optional_identifier(event, index, "toolCallId")?;
                optional_identifier(event, index, "toolCallName")?;
                optional_identifier(event, index, "parentMessageId")?;
                let delta = optional_string(event, index, "delta")?;
                omitted_event = true;
                let bytes = delta.map(str::len).unwrap_or(0);
                omitted_bytes += bytes;
                counters.tool_chunk_events += 1;
                counters.tool_chunk_bytes += bytes;
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "STATE_SNAPSHOT" => {
                let snapshot = event
                    .get("snapshot")
                    .filter(|value| value.is_object())
                    .ok_or(AgUiProjectionError::InvalidEventField {
                        event_index: index,
                        field: "snapshot",
                    })?;
                let bytes = serialized_len(snapshot);
                omitted_event = true;
                omitted_bytes += bytes;
                counters.state_snapshot_keys += snapshot.as_object().map_or(0, |value| value.len());
                counters.state_snapshot_bytes += bytes;
                if let Some(run_hash) = active_run(index, &current_run_hash, &mut violations) {
                    projected_events.push(ssb_event(
                        index,
                        "state_observed",
                        &run_hash,
                        "agent_state",
                        "observation",
                        "low",
                        false,
                        "unknown",
                        "ag_ui_state_snapshot_content_omitted",
                    ));
                }
            }
            "STATE_DELTA" => {
                let delta = event.get("delta").and_then(Value::as_array).ok_or(
                    AgUiProjectionError::InvalidEventField {
                        event_index: index,
                        field: "delta",
                    },
                )?;
                let bytes = serialized_len(event.get("delta").expect("validated delta"));
                omitted_event = true;
                omitted_bytes += bytes;
                counters.state_delta_operations += delta.len();
                counters.state_delta_bytes += bytes;
                if let Some(run_hash) = active_run(index, &current_run_hash, &mut violations) {
                    projected_events.push(ssb_event(
                        index,
                        "state_observed",
                        &run_hash,
                        "agent_state",
                        "observation",
                        "low",
                        false,
                        "unknown",
                        "ag_ui_state_delta_paths_and_values_omitted",
                    ));
                }
            }
            "MESSAGES_SNAPSHOT" => {
                let messages = event.get("messages").and_then(Value::as_array).ok_or(
                    AgUiProjectionError::InvalidEventField {
                        event_index: index,
                        field: "messages",
                    },
                )?;
                omitted_event = true;
                omitted_bytes += serialized_len(event.get("messages").expect("validated messages"));
                counters.message_snapshots += 1;
                counters.messages_observed += messages.len();
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "ACTIVITY_SNAPSHOT" | "ACTIVITY_DELTA" => {
                let message_id = required_identifier(event, index, "messageId")?;
                required_identifier(event, index, "activityType")?;
                let payload_field = if event_type == "ACTIVITY_SNAPSHOT" {
                    "content"
                } else {
                    "patch"
                };
                let payload =
                    event
                        .get(payload_field)
                        .ok_or(AgUiProjectionError::InvalidEventField {
                            event_index: index,
                            field: payload_field,
                        })?;
                if (event_type == "ACTIVITY_SNAPSHOT" && !payload.is_object())
                    || (event_type == "ACTIVITY_DELTA" && !payload.is_array())
                {
                    return Err(AgUiProjectionError::InvalidEventField {
                        event_index: index,
                        field: payload_field,
                    });
                }
                let bytes = serialized_len(payload);
                omitted_event = true;
                omitted_bytes += bytes;
                counters.activity_events += 1;
                counters.activity_payload_bytes += bytes;
                if active_run(index, &current_run_hash, &mut violations).is_some() {
                    let message_hash = domain_hash("message", message_id);
                    projected_events.push(ssb_event(
                        index,
                        "activity_observed",
                        &message_hash,
                        "agent_activity",
                        "observation",
                        "low",
                        false,
                        "unknown",
                        "ag_ui_activity_body_omitted",
                    ));
                }
            }
            "RAW" => {
                optional_identifier(event, index, "source")?;
                let payload = event
                    .get("event")
                    .ok_or(AgUiProjectionError::InvalidEventField {
                        event_index: index,
                        field: "event",
                    })?;
                let bytes = serialized_len(payload);
                omitted_event = true;
                omitted_bytes += bytes;
                counters.extension_events += 1;
                counters.extension_payload_bytes += bytes;
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "CUSTOM" => {
                required_identifier(event, index, "name")?;
                let payload = event
                    .get("value")
                    .ok_or(AgUiProjectionError::InvalidEventField {
                        event_index: index,
                        field: "value",
                    })?;
                let bytes = serialized_len(payload);
                omitted_event = true;
                omitted_bytes += bytes;
                counters.extension_events += 1;
                counters.extension_payload_bytes += bytes;
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "TEXT_MESSAGE_START" => {
                required_identifier(event, index, "messageId")?;
                optional_identifier(event, index, "name")?;
                omitted_event = true;
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "TEXT_MESSAGE_CONTENT" => {
                required_identifier(event, index, "messageId")?;
                let delta = required_string(event, index, "delta")?;
                omitted_event = true;
                omitted_bytes += delta.len();
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "TEXT_MESSAGE_END" => {
                required_identifier(event, index, "messageId")?;
                omitted_event = true;
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "TEXT_MESSAGE_CHUNK" => {
                optional_identifier(event, index, "messageId")?;
                optional_identifier(event, index, "name")?;
                let delta = optional_string(event, index, "delta")?;
                omitted_event = true;
                omitted_bytes += delta.map(str::len).unwrap_or(0);
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "THINKING_START" => {
                let title = optional_string(event, index, "title")?;
                omitted_event = true;
                omitted_bytes += title.map(str::len).unwrap_or(0);
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "THINKING_END" | "THINKING_TEXT_MESSAGE_START" | "THINKING_TEXT_MESSAGE_END" => {
                omitted_event = true;
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "THINKING_TEXT_MESSAGE_CONTENT" => {
                let delta = required_string(event, index, "delta")?;
                omitted_event = true;
                omitted_bytes += delta.len();
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "REASONING_START"
            | "REASONING_MESSAGE_START"
            | "REASONING_MESSAGE_END"
            | "REASONING_END" => {
                required_identifier(event, index, "messageId")?;
                omitted_event = true;
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "REASONING_MESSAGE_CONTENT" => {
                required_identifier(event, index, "messageId")?;
                let delta = required_string(event, index, "delta")?;
                omitted_event = true;
                omitted_bytes += delta.len();
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "REASONING_MESSAGE_CHUNK" => {
                optional_identifier(event, index, "messageId")?;
                let delta = optional_string(event, index, "delta")?;
                omitted_event = true;
                omitted_bytes += delta.map(str::len).unwrap_or(0);
                require_active_run(index, &current_run_hash, &mut violations);
            }
            "REASONING_ENCRYPTED_VALUE" => {
                required_identifier(event, index, "entityId")?;
                let encrypted = required_string(event, index, "encryptedValue")?;
                omitted_event = true;
                omitted_bytes += encrypted.len();
                require_active_run(index, &current_run_hash, &mut violations);
            }
            _ => {
                counters.unknown_event_types += 1;
                omitted_event = true;
                omitted_bytes = serialized_len(event_value);
            }
        }

        if omitted_event {
            counters.omitted_content_events += 1;
            counters.content_bytes_omitted += omitted_bytes;
        }
    }

    for call in tool_calls.values() {
        if call.status.is_open() {
            violations.push(Violation {
                index: events.len(),
                code: "open_tool_call_at_batch_end",
            });
        }
    }

    let stream_complete = counters.unknown_event_types == 0
        && violations.is_empty()
        && !runs.is_empty()
        && runs.values().all(|run| run.status.is_terminal())
        && tool_calls.values().all(|call| !call.status.is_open());

    let run_values = runs
        .values()
        .map(RunProjection::to_json)
        .collect::<Vec<_>>();
    let tool_values = tool_calls
        .values()
        .map(ToolCallProjection::to_json)
        .collect::<Vec<_>>();
    let violation_values = violations
        .iter()
        .map(Violation::to_json)
        .collect::<Vec<_>>();

    Ok(json!({
        "schema": PROJECTION_SCHEMA,
        "read_only": true,
        "executes_actions": false,
        "writes_store": false,
        "changes_policy": false,
        "protocol": {
            "name": PROTOCOL_NAME,
            "core_version": CORE_VERSION,
        },
        "counts": {
            "input_events": events.len(),
            "projected_events": projected_events.len(),
            "omitted_content_events": counters.omitted_content_events,
            "unknown_event_types": counters.unknown_event_types,
            "violations": violations.len(),
        },
        "observations": {
            "content_bytes_omitted": counters.content_bytes_omitted,
            "tool_args_chunks": counters.tool_args_chunks,
            "tool_args_bytes": counters.tool_args_bytes,
            "tool_chunk_events": counters.tool_chunk_events,
            "tool_chunk_bytes": counters.tool_chunk_bytes,
            "message_snapshots": counters.message_snapshots,
            "messages_observed": counters.messages_observed,
            "state_snapshot_keys": counters.state_snapshot_keys,
            "state_snapshot_bytes": counters.state_snapshot_bytes,
            "state_delta_operations": counters.state_delta_operations,
            "state_delta_bytes": counters.state_delta_bytes,
            "activity_events": counters.activity_events,
            "activity_payload_bytes": counters.activity_payload_bytes,
            "extension_events": counters.extension_events,
            "extension_payload_bytes": counters.extension_payload_bytes,
            "error_message_bytes": counters.error_message_bytes,
            "run_payload_bytes": counters.run_payload_bytes,
        },
        "runs": run_values,
        "tool_calls": tool_values,
        "projected_events": projected_events,
        "violations": violation_values,
        "claims": {
            "all_actions_traceable": false,
            "external_effects_verified": false,
            "stream_complete": stream_complete,
        }
    }))
}

/// Return an RFC 8785/JCS-style canonical JSON encoding for deterministic receipts.
pub fn project_ag_ui_readonly_canonical(input: &Value) -> Result<Vec<u8>, AgUiProjectionError> {
    let projection = project_ag_ui_readonly(input)?;
    serde_json_canonicalizer::to_vec(&projection).map_err(|_| AgUiProjectionError::Canonicalization)
}

fn validate_request_budget(input: &Value) -> Result<(), AgUiProjectionError> {
    let actual = serde_json::to_vec(input)
        .map_err(|_| AgUiProjectionError::RequestSerialization)?
        .len();
    if actual > MAX_REQUEST_BYTES {
        return Err(AgUiProjectionError::RequestTooLarge {
            actual,
            max: MAX_REQUEST_BYTES,
        });
    }
    Ok(())
}

fn validate_source_identifier(
    source: &serde_json::Map<String, Value>,
    field: &'static str,
) -> Result<(), AgUiProjectionError> {
    let value = source
        .get(field)
        .and_then(Value::as_str)
        .ok_or(AgUiProjectionError::InvalidRequestField { field })?;
    if value.len() > MAX_IDENTIFIER_BYTES {
        return Err(AgUiProjectionError::SourceIdentifierTooLong {
            field,
            actual: value.len(),
            max: MAX_IDENTIFIER_BYTES,
        });
    }
    Ok(())
}

fn required_string<'a>(
    event: &'a serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
) -> Result<&'a str, AgUiProjectionError> {
    event
        .get(field)
        .and_then(Value::as_str)
        .ok_or(AgUiProjectionError::InvalidEventField { event_index, field })
}

fn optional_string<'a>(
    event: &'a serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
) -> Result<Option<&'a str>, AgUiProjectionError> {
    match event.get(field) {
        None => Ok(None),
        Some(value) => value
            .as_str()
            .map(Some)
            .ok_or(AgUiProjectionError::InvalidEventField { event_index, field }),
    }
}

fn required_identifier<'a>(
    event: &'a serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
) -> Result<&'a str, AgUiProjectionError> {
    let value = required_string(event, event_index, field)?;
    validate_identifier(value, event_index, field)?;
    Ok(value)
}

fn optional_identifier<'a>(
    event: &'a serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
) -> Result<Option<&'a str>, AgUiProjectionError> {
    let value = optional_string(event, event_index, field)?;
    if let Some(value) = value {
        validate_identifier(value, event_index, field)?;
    }
    Ok(value)
}

fn validate_identifier(
    value: &str,
    event_index: usize,
    field: &'static str,
) -> Result<(), AgUiProjectionError> {
    if value.len() > MAX_IDENTIFIER_BYTES {
        return Err(AgUiProjectionError::IdentifierTooLong {
            event_index,
            field,
            actual: value.len(),
            max: MAX_IDENTIFIER_BYTES,
        });
    }
    Ok(())
}

fn validate_run_outcome(
    event: &serde_json::Map<String, Value>,
    event_index: usize,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<bool, AgUiProjectionError> {
    let Some(outcome) = event.get("outcome") else {
        return Ok(false);
    };
    if outcome.is_null() {
        return Ok(false);
    }
    let object = outcome
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "outcome",
        })?;
    let outcome_type = object.get("type").and_then(Value::as_str).ok_or(
        AgUiProjectionError::InvalidEventField {
            event_index,
            field: "outcome.type",
        },
    )?;
    match outcome_type {
        "success" => Ok(false),
        "interrupt" => {
            let interrupts_value =
                object
                    .get("interrupts")
                    .ok_or(AgUiProjectionError::InvalidEventField {
                        event_index,
                        field: "outcome.interrupts",
                    })?;
            interrupts_value
                .as_array()
                .filter(|values| !values.is_empty())
                .ok_or(AgUiProjectionError::InvalidEventField {
                    event_index,
                    field: "outcome.interrupts",
                })?;
            *omitted_event = true;
            *omitted_bytes += serialized_len(interrupts_value);
            Ok(true)
        }
        _ => Err(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "outcome.type",
        }),
    }
}

fn require_active_run(
    index: usize,
    current_run_hash: &Option<String>,
    violations: &mut Vec<Violation>,
) {
    if current_run_hash.is_none() {
        violations.push(Violation {
            index,
            code: "event_without_active_run",
        });
    }
}

fn active_run(
    index: usize,
    current_run_hash: &Option<String>,
    violations: &mut Vec<Violation>,
) -> Option<String> {
    if current_run_hash.is_none() {
        violations.push(Violation {
            index,
            code: "event_without_active_run",
        });
    }
    current_run_hash.clone()
}

fn mark_terminal_open_tools(
    run_hash: &str,
    index: usize,
    tool_calls: &BTreeMap<String, ToolCallProjection>,
    violations: &mut Vec<Violation>,
) {
    for call in tool_calls.values() {
        if call.run_id_hash == run_hash && call.status.is_open() {
            violations.push(Violation {
                index,
                code: "run_terminal_with_open_tool_call",
            });
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn ssb_event(
    index: usize,
    action: &'static str,
    target: &str,
    object_type: &'static str,
    action_type: &'static str,
    risk_level: &'static str,
    requires_gate: bool,
    verdict_status: &'static str,
    verdict_method: &'static str,
) -> Value {
    json!({
        "event_index": index,
        "source": "ag_ui_readonly",
        "action": action,
        "target": target,
        "object": {
            "object_type": object_type,
            "source_adapter": "ag_ui_readonly",
            "label": Value::Null,
            "object_id": target,
        },
        "affordance": {
            "action_type": action_type,
            "risk_level": risk_level,
            "requires_gate": requires_gate,
            "expected_effect": Value::Null,
        },
        "verdict": {
            "status": verdict_status,
            "method": verdict_method,
            "evidence": Value::Null,
        }
    })
}

fn domain_hash(domain: &str, value: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(b"ag-ui/v0/");
    hasher.update(domain.as_bytes());
    hasher.update([0]);
    hasher.update(value.as_bytes());
    format!("sha256:{:x}", hasher.finalize())
}

fn size_bucket(bytes: usize) -> &'static str {
    match bytes {
        0 => "empty",
        1..=64 => "1_64",
        65..=1024 => "65_1024",
        1025..=16384 => "1025_16384",
        _ => "over_16384",
    }
}

fn serialized_len(value: &Value) -> usize {
    serde_json::to_vec(value).map_or(0, |bytes| bytes.len())
}

#[cfg(test)]
mod tests {
    use super::*;

    const COMPLETE_TEXT: &str =
        include_str!("../tests/fixtures/ag_ui_readonly_projection/complete_text_run.json");
    const COMPLETE_TOOL: &str =
        include_str!("../tests/fixtures/ag_ui_readonly_projection/complete_tool_run.json");
    const RUN_ERROR: &str =
        include_str!("../tests/fixtures/ag_ui_readonly_projection/run_error.json");
    const INTERRUPTED: &str =
        include_str!("../tests/fixtures/ag_ui_readonly_projection/interrupted_run.json");
    const TRUNCATED: &str =
        include_str!("../tests/fixtures/ag_ui_readonly_projection/truncated_stream.json");
    const ADVERSARIAL: &str =
        include_str!("../tests/fixtures/ag_ui_readonly_projection/reordered_cross_run.json");
    const LEAK_CANARIES: &str =
        include_str!("../tests/fixtures/ag_ui_readonly_projection/content_leak_canaries.json");

    fn fixture(source: &str) -> Value {
        serde_json::from_str(source).expect("valid fixture")
    }

    fn verdict_statuses(value: &Value, output: &mut Vec<String>) {
        match value {
            Value::Array(values) => {
                for value in values {
                    verdict_statuses(value, output);
                }
            }
            Value::Object(object) => {
                if let Some(status) = object
                    .get("verdict")
                    .and_then(Value::as_object)
                    .and_then(|verdict| verdict.get("status"))
                    .and_then(Value::as_str)
                {
                    output.push(status.to_string());
                }
                for value in object.values() {
                    verdict_statuses(value, output);
                }
            }
            _ => {}
        }
    }

    #[test]
    fn complete_text_run_is_content_minimized_and_complete() {
        let output = project_ag_ui_readonly(&fixture(COMPLETE_TEXT)).expect("projection");
        assert_eq!(output["claims"]["stream_complete"], true);
        assert_eq!(output["claims"]["all_actions_traceable"], false);
        assert_eq!(output["counts"]["omitted_content_events"], 3);
        assert!(output["violations"].as_array().expect("array").is_empty());
    }

    #[test]
    fn tool_end_and_success_looking_result_never_become_verified() {
        let output = project_ag_ui_readonly(&fixture(COMPLETE_TOOL)).expect("projection");
        let mut statuses = Vec::new();
        verdict_statuses(&output, &mut statuses);
        assert!(!statuses.is_empty());
        assert!(statuses.iter().all(|status| status != "verified"));

        let events = output["projected_events"].as_array().expect("events");
        for action in ["request_closed", "result_observed"] {
            let event = events
                .iter()
                .find(|event| event["action"] == action)
                .expect("projected tool event");
            assert_eq!(event["verdict"]["status"], "unknown");
        }
        assert_eq!(output["claims"]["external_effects_verified"], false);
    }

    #[test]
    fn run_error_and_interrupt_are_not_verified() {
        for source in [RUN_ERROR, INTERRUPTED] {
            let output = project_ag_ui_readonly(&fixture(source)).expect("projection");
            assert_eq!(output["runs"][0]["verdict"]["status"], "not_verified");
            assert_eq!(output["claims"]["external_effects_verified"], false);
        }
    }

    #[test]
    fn raw_content_canaries_never_appear_in_serialized_output() {
        let output = project_ag_ui_readonly(&fixture(LEAK_CANARIES)).expect("projection");
        let serialized = String::from_utf8(
            serde_json_canonicalizer::to_vec(&output).expect("canonical projection"),
        )
        .expect("utf8");
        for canary in [
            "sk-live-AGUI-CANARY",
            "https://internal.example.test/private?q=canary",
            "/Users/alice/.ssh/id_ed25519",
            "SYSTEM_PROMPT_CANARY_DO_NOT_LEAK",
            "COOKIE=session-secret-canary",
            "raw-event-secret-canary",
            "tool_result_success_canary",
            "reasoning-secret-canary",
            "encrypted-reasoning-canary",
            "messages-snapshot-canary",
            "snapshot-secret-canary",
            "delta-secret-canary",
            "activity-secret-canary",
            "custom-secret-canary",
            "raw-extension-canary",
        ] {
            assert!(!serialized.contains(canary), "leaked canary: {canary}");
        }
    }

    #[test]
    fn reordered_and_cross_run_tool_events_are_violations() {
        let output = project_ag_ui_readonly(&fixture(ADVERSARIAL)).expect("projection");
        let codes = output["violations"]
            .as_array()
            .expect("violations")
            .iter()
            .filter_map(|value| value["code"].as_str())
            .collect::<Vec<_>>();
        assert!(codes.contains(&"tool_args_before_start"));
        assert!(codes.contains(&"tool_end_before_start"));
        assert!(codes.contains(&"tool_result_before_start"));
        assert!(codes.contains(&"duplicate_tool_call_start"));
        assert!(codes.contains(&"tool_result_before_end"));
        assert!(codes.contains(&"cross_run_tool_call_id_reuse"));
        assert!(codes.contains(&"run_terminal_with_open_tool_call"));
        assert!(codes.contains(&"open_tool_call_at_batch_end"));
        assert!(codes.contains(&"event_after_terminal_run"));
        assert!(codes.contains(&"conflicting_thread_id"));
        assert!(codes.contains(&"conflicting_run_id"));
        assert_eq!(output["claims"]["stream_complete"], false);
    }

    #[test]
    fn truncated_stream_never_claims_completeness_or_traceability() {
        let output = project_ag_ui_readonly(&fixture(TRUNCATED)).expect("projection");
        assert_eq!(output["claims"]["stream_complete"], false);
        assert_eq!(output["claims"]["all_actions_traceable"], false);
    }

    #[test]
    fn unknown_event_type_is_counted_and_omitted() {
        let mut input = fixture(COMPLETE_TEXT);
        input["events"].as_array_mut().expect("events").insert(
            1,
            json!({"type": "FUTURE_PRIVATE_EVENT", "secret": "omit-me"}),
        );
        let output = project_ag_ui_readonly(&input).expect("projection");
        assert_eq!(output["counts"]["unknown_event_types"], 1);
        assert_eq!(output["claims"]["stream_complete"], false);
        assert!(!serde_json::to_string(&output)
            .expect("json")
            .contains("omit-me"));
    }

    #[test]
    fn budgets_and_protocol_version_fail_closed() {
        let mut wrong_version = fixture(COMPLETE_TEXT);
        wrong_version["protocol"]["core_version"] = json!("0.0.58");
        assert_eq!(
            project_ag_ui_readonly(&wrong_version),
            Err(AgUiProjectionError::UnsupportedProtocol)
        );

        let mut long_identifier = fixture(COMPLETE_TEXT);
        long_identifier["events"][0]["runId"] = json!("x".repeat(MAX_IDENTIFIER_BYTES + 1));
        assert!(matches!(
            project_ag_ui_readonly(&long_identifier),
            Err(AgUiProjectionError::IdentifierTooLong { .. })
        ));

        let mut too_many = fixture(COMPLETE_TEXT);
        too_many["events"] = Value::Array(
            (0..=MAX_EVENTS)
                .map(|_| json!({"type": "FUTURE_EVENT"}))
                .collect(),
        );
        assert_eq!(
            project_ag_ui_readonly(&too_many),
            Err(AgUiProjectionError::InvalidEventCount {
                actual: MAX_EVENTS + 1,
                max: MAX_EVENTS,
            })
        );

        let mut oversized = fixture(COMPLETE_TEXT);
        oversized["ignored"] = json!("x".repeat(MAX_REQUEST_BYTES));
        assert!(matches!(
            project_ag_ui_readonly(&oversized),
            Err(AgUiProjectionError::RequestTooLarge { .. })
        ));
    }

    #[test]
    fn canonical_projection_is_byte_deterministic() {
        let input = fixture(COMPLETE_TOOL);
        let first = project_ag_ui_readonly_canonical(&input).expect("first");
        let second = project_ag_ui_readonly_canonical(&input).expect("second");
        assert_eq!(first, second);
    }

    #[test]
    fn output_contract_is_explicitly_read_only_and_non_effectful() {
        let output = project_ag_ui_readonly(&fixture(COMPLETE_TOOL)).expect("projection");
        assert_eq!(output["read_only"], true);
        assert_eq!(output["executes_actions"], false);
        assert_eq!(output["writes_store"], false);
        assert_eq!(output["changes_policy"], false);
        assert_eq!(output["claims"]["external_effects_verified"], false);
    }
}
