//! Pure, content-minimizing AG-UI 0.0.57 event projection.
//!
//! The projector accepts only caller-supplied JSON and returns in-memory JSON.
//! It deliberately owns no transport, store, process, browser, mobile, lease,
//! policy, or MCP registration handle. AG-UI lifecycle events are observations;
//! none of them can establish a verified external effect.

use std::collections::{BTreeMap, BTreeSet};

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
    #[error("request object '{object}' contains an unexpected field")]
    UnexpectedRequestField { object: &'static str },
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

#[derive(Debug, Clone, Copy)]
struct RunInputIdentifiers<'a> {
    thread_id: &'a str,
    run_id: &'a str,
    parent_run_id: Option<&'a str>,
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

#[derive(Debug, Default)]
struct ProjectionState {
    counters: Counters,
    runs: BTreeMap<String, RunProjection>,
    tool_calls: BTreeMap<String, ToolCallProjection>,
    open_steps: BTreeSet<(String, String)>,
    projected_events: Vec<Value>,
    violations: Vec<Violation>,
    current_run_hash: Option<String>,
}

struct ProjectionContext<'a> {
    counters: &'a mut Counters,
    runs: &'a mut BTreeMap<String, RunProjection>,
    tool_calls: &'a mut BTreeMap<String, ToolCallProjection>,
    open_steps: &'a mut BTreeSet<(String, String)>,
    projected_events: &'a mut Vec<Value>,
    violations: &'a mut Vec<Violation>,
    current_run_hash: &'a mut Option<String>,
}

impl Counters {
    fn observations_json(&self) -> Value {
        json!({
            "content_bytes_omitted": self.content_bytes_omitted,
            "tool_args_chunks": self.tool_args_chunks,
            "tool_args_bytes": self.tool_args_bytes,
            "tool_chunk_events": self.tool_chunk_events,
            "tool_chunk_bytes": self.tool_chunk_bytes,
            "message_snapshots": self.message_snapshots,
            "messages_observed": self.messages_observed,
            "state_snapshot_keys": self.state_snapshot_keys,
            "state_snapshot_bytes": self.state_snapshot_bytes,
            "state_delta_operations": self.state_delta_operations,
            "state_delta_bytes": self.state_delta_bytes,
            "activity_events": self.activity_events,
            "activity_payload_bytes": self.activity_payload_bytes,
            "extension_events": self.extension_events,
            "extension_payload_bytes": self.extension_payload_bytes,
            "error_message_bytes": self.error_message_bytes,
            "run_payload_bytes": self.run_payload_bytes,
        })
    }
}

impl ProjectionState {
    fn context(&mut self) -> ProjectionContext<'_> {
        ProjectionContext {
            counters: &mut self.counters,
            runs: &mut self.runs,
            tool_calls: &mut self.tool_calls,
            open_steps: &mut self.open_steps,
            projected_events: &mut self.projected_events,
            violations: &mut self.violations,
            current_run_hash: &mut self.current_run_hash,
        }
    }

    fn finish(&mut self, event_count: usize) {
        for call in self.tool_calls.values() {
            if call.status.is_open() {
                self.violations.push(Violation {
                    index: event_count,
                    code: "open_tool_call_at_batch_end",
                });
            }
        }
        for _ in &self.open_steps {
            self.violations.push(Violation {
                index: event_count,
                code: "open_step_at_batch_end",
            });
        }
    }

    fn stream_complete(&self) -> bool {
        self.counters.unknown_event_types == 0
            && self.violations.is_empty()
            && !self.runs.is_empty()
            && self.runs.values().all(|run| run.status.is_terminal())
            && self.tool_calls.values().all(|call| !call.status.is_open())
            && self.open_steps.is_empty()
    }

    fn into_json(self, input_events: usize) -> Value {
        let stream_complete = self.stream_complete();
        let runs = self
            .runs
            .values()
            .map(RunProjection::to_json)
            .collect::<Vec<_>>();
        let tool_calls = self
            .tool_calls
            .values()
            .map(ToolCallProjection::to_json)
            .collect::<Vec<_>>();
        let violations = self
            .violations
            .iter()
            .map(Violation::to_json)
            .collect::<Vec<_>>();
        json!({
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
                "input_events": input_events,
                "projected_events": self.projected_events.len(),
                "omitted_content_events": self.counters.omitted_content_events,
                "unknown_event_types": self.counters.unknown_event_types,
                "violations": self.violations.len(),
            },
            "observations": self.counters.observations_json(),
            "runs": runs,
            "tool_calls": tool_calls,
            "projected_events": self.projected_events,
            "violations": violations,
            "claims": {
                "all_actions_traceable": false,
                "external_effects_verified": false,
                "stream_complete": stream_complete,
            }
        })
    }
}

fn validate_projection_request(input: &Value) -> Result<&[Value], AgUiProjectionError> {
    validate_request_budget(input)?;
    let request = input
        .as_object()
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "request" })?;
    validate_closed_request_object(
        request,
        &["schema", "protocol", "source", "events"],
        "request",
    )?;
    let schema = request
        .get("schema")
        .and_then(Value::as_str)
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "schema" })?;
    if schema != REQUEST_SCHEMA {
        return Err(AgUiProjectionError::UnsupportedRequestSchema);
    }

    validate_protocol(request)?;
    let source = request
        .get("source")
        .and_then(Value::as_object)
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "source" })?;
    validate_closed_request_object(source, &["adapter_id", "agent_id_hash"], "source")?;
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
    Ok(events)
}

fn validate_protocol(request: &serde_json::Map<String, Value>) -> Result<(), AgUiProjectionError> {
    let protocol = request
        .get("protocol")
        .and_then(Value::as_object)
        .ok_or(AgUiProjectionError::InvalidRequestField { field: "protocol" })?;
    validate_closed_request_object(protocol, &["name", "core_version"], "protocol")?;
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
    Ok(())
}

fn validate_closed_request_object(
    object: &serde_json::Map<String, Value>,
    allowed_fields: &[&str],
    object_name: &'static str,
) -> Result<(), AgUiProjectionError> {
    if object
        .keys()
        .any(|field| !allowed_fields.contains(&field.as_str()))
    {
        return Err(AgUiProjectionError::UnexpectedRequestField {
            object: object_name,
        });
    }
    Ok(())
}

/// Project one bounded AG-UI 0.0.57 batch without performing I/O or mutation.
///
/// # Errors
///
/// Returns [`AgUiProjectionError`] when the request exceeds its budget, does
/// not match the pinned projection envelope, or contains a malformed known
/// AG-UI 0.0.57 event.
pub fn project_ag_ui_readonly(input: &Value) -> Result<Value, AgUiProjectionError> {
    let events = validate_projection_request(input)?;
    let mut state = ProjectionState::default();
    process_events(events, &mut state)?;
    state.finish(events.len());
    Ok(state.into_json(events.len()))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum EventFamily {
    Run,
    Step,
    Tool,
    Observation,
    Content,
    Unknown,
}

impl EventFamily {
    fn classify(event_type: &str) -> Self {
        match event_type {
            "RUN_STARTED" | "RUN_FINISHED" | "RUN_ERROR" => Self::Run,
            "STEP_STARTED" | "STEP_FINISHED" => Self::Step,
            "TOOL_CALL_START" | "TOOL_CALL_ARGS" | "TOOL_CALL_END" | "TOOL_CALL_RESULT"
            | "TOOL_CALL_CHUNK" => Self::Tool,
            "STATE_SNAPSHOT" | "STATE_DELTA" | "MESSAGES_SNAPSHOT" | "ACTIVITY_SNAPSHOT"
            | "ACTIVITY_DELTA" | "RAW" | "CUSTOM" => Self::Observation,
            "TEXT_MESSAGE_START"
            | "TEXT_MESSAGE_CONTENT"
            | "TEXT_MESSAGE_END"
            | "TEXT_MESSAGE_CHUNK"
            | "THINKING_START"
            | "THINKING_END"
            | "THINKING_TEXT_MESSAGE_START"
            | "THINKING_TEXT_MESSAGE_CONTENT"
            | "THINKING_TEXT_MESSAGE_END"
            | "REASONING_START"
            | "REASONING_MESSAGE_START"
            | "REASONING_MESSAGE_CONTENT"
            | "REASONING_MESSAGE_END"
            | "REASONING_MESSAGE_CHUNK"
            | "REASONING_ENCRYPTED_VALUE"
            | "REASONING_END" => Self::Content,
            _ => Self::Unknown,
        }
    }
}

fn process_events(
    events: &[Value],
    state: &mut ProjectionState,
) -> Result<(), AgUiProjectionError> {
    for (index, event_value) in events.iter().enumerate() {
        process_event(event_value, index, state)?;
    }
    Ok(())
}

fn process_event(
    event_value: &Value,
    index: usize,
    state: &mut ProjectionState,
) -> Result<(), AgUiProjectionError> {
    let event = event_value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index: index,
            field: "event",
        })?;
    let event_type = required_string(event, index, "type")?;
    validate_base_event_fields(event, index)?;
    let mut omitted_event = event.contains_key("rawEvent");
    let mut omitted_bytes = event.get("rawEvent").map(serialized_len).unwrap_or(0);
    note_event_after_terminal(event_type, index, state);

    match EventFamily::classify(event_type) {
        EventFamily::Run => handle_run_event(
            event_type,
            event,
            index,
            state.context(),
            &mut omitted_event,
            &mut omitted_bytes,
        )?,
        EventFamily::Step => handle_step_event(event_type, event, index, state.context())?,
        EventFamily::Tool => handle_tool_event(
            event_type,
            event,
            index,
            state.context(),
            &mut omitted_event,
            &mut omitted_bytes,
        )?,
        EventFamily::Observation => handle_observation_event(
            event_type,
            event,
            index,
            state.context(),
            &mut omitted_event,
            &mut omitted_bytes,
        )?,
        EventFamily::Content => handle_content_event(
            event_type,
            event,
            index,
            state.context(),
            &mut omitted_event,
            &mut omitted_bytes,
        )?,
        EventFamily::Unknown => {
            state.counters.unknown_event_types += 1;
            omitted_event = true;
            omitted_bytes = serialized_len(event_value);
        }
    }

    if omitted_event {
        state.counters.omitted_content_events += 1;
        state.counters.content_bytes_omitted += omitted_bytes;
    }
    Ok(())
}

fn note_event_after_terminal(event_type: &str, index: usize, state: &mut ProjectionState) {
    if event_type != "RUN_STARTED"
        && state
            .current_run_hash
            .as_ref()
            .and_then(|hash| state.runs.get(hash))
            .is_some_and(|run| run.status.is_terminal())
    {
        state.violations.push(Violation {
            index,
            code: "event_after_terminal_run",
        });
    }
}

fn handle_content_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    if event_type.starts_with("TEXT_MESSAGE_") {
        handle_text_event(
            event_type,
            event,
            index,
            context,
            omitted_event,
            omitted_bytes,
        )
    } else if event_type.starts_with("THINKING_") {
        handle_thinking_event(
            event_type,
            event,
            index,
            context,
            omitted_event,
            omitted_bytes,
        )
    } else {
        handle_reasoning_event(
            event_type,
            event,
            index,
            context,
            omitted_event,
            omitted_bytes,
        )
    }
}

fn handle_text_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        runs,
        violations,
        current_run_hash,
        ..
    } = context;
    match event_type {
        "TEXT_MESSAGE_START" => {
            required_identifier(event, index, "messageId")?;
            optional_identifier(event, index, "name")?;
            optional_enum(
                event,
                index,
                "role",
                &["developer", "system", "assistant", "user"],
            )?;
        }
        "TEXT_MESSAGE_CONTENT" => {
            required_identifier(event, index, "messageId")?;
            *omitted_bytes += required_string(event, index, "delta")?.len();
        }
        "TEXT_MESSAGE_END" => {
            required_identifier(event, index, "messageId")?;
        }
        "TEXT_MESSAGE_CHUNK" => {
            optional_identifier(event, index, "messageId")?;
            optional_identifier(event, index, "name")?;
            optional_enum(
                event,
                index,
                "role",
                &["developer", "system", "assistant", "user"],
            )?;
            *omitted_bytes += optional_string(event, index, "delta")?
                .map(str::len)
                .unwrap_or(0);
        }
        _ => unreachable!("text handler called with non-text event"),
    }
    *omitted_event = true;
    require_active_run(index, current_run_hash, runs, violations);
    Ok(())
}

fn handle_thinking_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        runs,
        violations,
        current_run_hash,
        ..
    } = context;
    match event_type {
        "THINKING_START" => {
            *omitted_bytes += optional_string(event, index, "title")?
                .map(str::len)
                .unwrap_or(0);
        }
        "THINKING_TEXT_MESSAGE_CONTENT" => {
            *omitted_bytes += required_string(event, index, "delta")?.len();
        }
        "THINKING_END" | "THINKING_TEXT_MESSAGE_START" | "THINKING_TEXT_MESSAGE_END" => {}
        _ => unreachable!("thinking handler called with non-thinking event"),
    }
    *omitted_event = true;
    require_active_run(index, current_run_hash, runs, violations);
    Ok(())
}

fn handle_reasoning_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        runs,
        violations,
        current_run_hash,
        ..
    } = context;
    match event_type {
        "REASONING_START"
        | "REASONING_MESSAGE_START"
        | "REASONING_MESSAGE_END"
        | "REASONING_END" => {
            required_identifier(event, index, "messageId")?;
            if event_type == "REASONING_MESSAGE_START" {
                required_literal(event, index, "role", "reasoning")?;
            }
        }
        "REASONING_MESSAGE_CONTENT" => {
            required_identifier(event, index, "messageId")?;
            *omitted_bytes += required_string(event, index, "delta")?.len();
        }
        "REASONING_MESSAGE_CHUNK" => {
            optional_identifier(event, index, "messageId")?;
            *omitted_bytes += optional_string(event, index, "delta")?
                .map(str::len)
                .unwrap_or(0);
        }
        "REASONING_ENCRYPTED_VALUE" => {
            required_enum(event, index, "subtype", &["tool-call", "message"])?;
            required_identifier(event, index, "entityId")?;
            *omitted_bytes += required_string(event, index, "encryptedValue")?.len();
        }
        _ => unreachable!("reasoning handler called with non-reasoning event"),
    }
    *omitted_event = true;
    require_active_run(index, current_run_hash, runs, violations);
    Ok(())
}

fn handle_observation_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    match event_type {
        "STATE_SNAPSHOT" => {
            handle_state_snapshot(event, index, context, omitted_event, omitted_bytes)
        }
        "STATE_DELTA" => handle_state_delta(event, index, context, omitted_event, omitted_bytes),
        "MESSAGES_SNAPSHOT" => {
            handle_messages_snapshot(event, index, context, omitted_event, omitted_bytes)
        }
        "ACTIVITY_SNAPSHOT" | "ACTIVITY_DELTA" => handle_activity_event(
            event_type,
            event,
            index,
            context,
            omitted_event,
            omitted_bytes,
        ),
        "RAW" | "CUSTOM" => handle_extension_event(
            event_type,
            event,
            index,
            context,
            omitted_event,
            omitted_bytes,
        ),
        _ => unreachable!("observation handler called with unrelated event"),
    }
}

fn handle_state_snapshot(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        projected_events,
        violations,
        current_run_hash,
        ..
    } = context;
    let snapshot = event
        .get("snapshot")
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index: index,
            field: "snapshot",
        })?;
    let bytes = serialized_len(snapshot);
    *omitted_event = true;
    *omitted_bytes += bytes;
    counters.state_snapshot_keys += snapshot.as_object().map_or(0, |value| value.len());
    counters.state_snapshot_bytes += bytes;
    if let Some(run_hash) = active_run(index, current_run_hash, runs, violations) {
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
    Ok(())
}

fn handle_state_delta(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        projected_events,
        violations,
        current_run_hash,
        ..
    } = context;
    let delta_value = event
        .get("delta")
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index: index,
            field: "delta",
        })?;
    let delta = delta_value
        .as_array()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index: index,
            field: "delta",
        })?;
    let bytes = serialized_len(delta_value);
    *omitted_event = true;
    *omitted_bytes += bytes;
    counters.state_delta_operations += delta.len();
    counters.state_delta_bytes += bytes;
    if let Some(run_hash) = active_run(index, current_run_hash, runs, violations) {
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
    Ok(())
}

fn handle_messages_snapshot(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        violations,
        current_run_hash,
        ..
    } = context;
    let messages_value = event
        .get("messages")
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index: index,
            field: "messages",
        })?;
    let messages = messages_value
        .as_array()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index: index,
            field: "messages",
        })?;
    validate_messages(messages, index)?;
    *omitted_event = true;
    *omitted_bytes += serialized_len(messages_value);
    counters.message_snapshots += 1;
    counters.messages_observed += messages.len();
    require_active_run(index, current_run_hash, runs, violations);
    Ok(())
}

fn handle_activity_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        projected_events,
        violations,
        current_run_hash,
        ..
    } = context;
    let message_id = required_identifier(event, index, "messageId")?;
    required_identifier(event, index, "activityType")?;
    let payload_field = if event_type == "ACTIVITY_SNAPSHOT" {
        "content"
    } else {
        "patch"
    };
    let payload = event
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
    if event_type == "ACTIVITY_SNAPSHOT" {
        optional_bool(event, index, "replace")?;
    }
    let bytes = serialized_len(payload);
    *omitted_event = true;
    *omitted_bytes += bytes;
    counters.activity_events += 1;
    counters.activity_payload_bytes += bytes;
    if active_run(index, current_run_hash, runs, violations).is_some() {
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
    Ok(())
}

fn handle_extension_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        violations,
        current_run_hash,
        ..
    } = context;
    let payload = if event_type == "RAW" {
        optional_identifier(event, index, "source")?;
        event
            .get("event")
            .ok_or(AgUiProjectionError::InvalidEventField {
                event_index: index,
                field: "event",
            })?
    } else {
        required_identifier(event, index, "name")?;
        event
            .get("value")
            .ok_or(AgUiProjectionError::InvalidEventField {
                event_index: index,
                field: "value",
            })?
    };
    let bytes = serialized_len(payload);
    *omitted_event = true;
    *omitted_bytes += bytes;
    counters.extension_events += 1;
    counters.extension_payload_bytes += bytes;
    require_active_run(index, current_run_hash, runs, violations);
    Ok(())
}

fn handle_tool_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    match event_type {
        "TOOL_CALL_START" => handle_tool_start(event, index, context),
        "TOOL_CALL_ARGS" => handle_tool_args(event, index, context, omitted_event, omitted_bytes),
        "TOOL_CALL_END" => handle_tool_end(event, index, context),
        "TOOL_CALL_RESULT" => {
            handle_tool_result(event, index, context, omitted_event, omitted_bytes)
        }
        "TOOL_CALL_CHUNK" => handle_tool_chunk(event, index, context, omitted_event, omitted_bytes),
        _ => unreachable!("tool handler called with non-tool event"),
    }
}

fn handle_tool_start(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        runs,
        tool_calls,
        projected_events,
        violations,
        current_run_hash,
        ..
    } = context;
    let tool_call_id = required_identifier(event, index, "toolCallId")?;
    let tool_name = required_identifier(event, index, "toolCallName")?;
    optional_identifier(event, index, "parentMessageId")?;
    if let Some(run_hash) = active_run(index, current_run_hash, runs, violations) {
        let call_hash = domain_hash("tool-call", tool_call_id);
        let tool_name_hash = domain_hash("tool-name", tool_name);
        let mut inserted = false;
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
            inserted = true;
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
        if inserted {
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
    Ok(())
}

fn handle_tool_args(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        tool_calls,
        violations,
        current_run_hash,
        ..
    } = context;
    let tool_call_id = required_identifier(event, index, "toolCallId")?;
    let delta = required_string(event, index, "delta")?;
    *omitted_event = true;
    *omitted_bytes += delta.len();
    counters.tool_args_chunks += 1;
    counters.tool_args_bytes += delta.len();
    if let Some(run_hash) = active_run(index, current_run_hash, runs, violations) {
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
                });
            }
            Some(call) => {
                call.status = ToolCallStatus::ArgsObserved;
                call.args_chunks += 1;
                call.args_bytes += delta.len();
            }
        }
    }
    Ok(())
}

fn handle_tool_end(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        runs,
        tool_calls,
        projected_events,
        violations,
        current_run_hash,
        ..
    } = context;
    let tool_call_id = required_identifier(event, index, "toolCallId")?;
    if let Some(run_hash) = active_run(index, current_run_hash, runs, violations) {
        let call_hash = domain_hash("tool-call", tool_call_id);
        let mut transitioned = false;
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
                });
            }
            Some(call) => {
                call.status = ToolCallStatus::RequestClosed;
                transitioned = true;
            }
        }
        if transitioned {
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
    Ok(())
}

fn handle_tool_result(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        runs,
        tool_calls,
        projected_events,
        violations,
        current_run_hash,
        ..
    } = context;
    required_identifier(event, index, "messageId")?;
    let tool_call_id = required_identifier(event, index, "toolCallId")?;
    let content = required_string(event, index, "content")?;
    optional_literal(event, index, "role", "tool")?;
    *omitted_event = true;
    *omitted_bytes += content.len();
    if let Some(run_hash) = active_run(index, current_run_hash, runs, violations) {
        let call_hash = domain_hash("tool-call", tool_call_id);
        let mut transitioned = false;
        match tool_calls.get_mut(&call_hash) {
            None => violations.push(Violation {
                index,
                code: "tool_result_before_start",
            }),
            Some(call) if call.run_id_hash != run_hash => violations.push(Violation {
                index,
                code: "cross_run_tool_call_id_reuse",
            }),
            Some(call) if call.status == ToolCallStatus::ResultObserved => {
                violations.push(Violation {
                    index,
                    code: "duplicate_tool_call_result",
                });
            }
            Some(call) if call.status == ToolCallStatus::RequestClosed => {
                call.status = ToolCallStatus::ResultObserved;
                call.result_size_bucket = Some(size_bucket(content.len()));
                transitioned = true;
            }
            Some(_) => violations.push(Violation {
                index,
                code: "tool_result_before_end",
            }),
        }
        if transitioned {
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
    Ok(())
}

fn handle_tool_chunk(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        violations,
        current_run_hash,
        ..
    } = context;
    optional_identifier(event, index, "toolCallId")?;
    optional_identifier(event, index, "toolCallName")?;
    optional_identifier(event, index, "parentMessageId")?;
    let delta = optional_string(event, index, "delta")?;
    *omitted_event = true;
    let bytes = delta.map(str::len).unwrap_or(0);
    *omitted_bytes += bytes;
    counters.tool_chunk_events += 1;
    counters.tool_chunk_bytes += bytes;
    require_active_run(index, current_run_hash, runs, violations);
    Ok(())
}

fn handle_step_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        runs,
        open_steps,
        projected_events,
        violations,
        current_run_hash,
        ..
    } = context;
    let step_name = required_identifier(event, index, "stepName")?;
    let step_hash = domain_hash("step", step_name);
    if let Some(run_hash) = active_run(index, current_run_hash, runs, violations) {
        let key = (run_hash, step_hash.clone());
        let transitioned = if event_type == "STEP_STARTED" {
            if open_steps.insert(key) {
                true
            } else {
                violations.push(Violation {
                    index,
                    code: "duplicate_step_start",
                });
                false
            }
        } else if open_steps.remove(&key) {
            true
        } else {
            violations.push(Violation {
                index,
                code: "step_finish_before_start",
            });
            false
        };
        if transitioned {
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
    }
    Ok(())
}

fn handle_run_event(
    event_type: &str,
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    match event_type {
        "RUN_STARTED" => handle_run_started(event, index, context, omitted_event, omitted_bytes),
        "RUN_FINISHED" => handle_run_finished(event, index, context, omitted_event, omitted_bytes),
        "RUN_ERROR" => handle_run_error(event, index, context, omitted_event, omitted_bytes),
        _ => unreachable!("run handler called with non-run event"),
    }
}

fn handle_run_started(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        projected_events,
        violations,
        current_run_hash,
        ..
    } = context;
    let thread_id = required_identifier(event, index, "threadId")?;
    let run_id = required_identifier(event, index, "runId")?;
    let parent_run_id = optional_identifier(event, index, "parentRunId")?;
    if let Some(payload) = event.get("input") {
        let input_identifiers = validate_run_input(payload, index)?;
        if input_identifiers.thread_id != thread_id {
            violations.push(Violation {
                index,
                code: "run_input_thread_id_mismatch",
            });
        }
        if input_identifiers.run_id != run_id {
            violations.push(Violation {
                index,
                code: "run_input_run_id_mismatch",
            });
        }
        if input_identifiers.parent_run_id != parent_run_id {
            violations.push(Violation {
                index,
                code: "run_input_parent_run_id_mismatch",
            });
        }
        *omitted_event = true;
        let bytes = serialized_len(payload);
        *omitted_bytes += bytes;
        counters.run_payload_bytes += bytes;
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
    let mut inserted = false;
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
        inserted = true;
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
    *current_run_hash = Some(run_hash.clone());
    if inserted {
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
    Ok(())
}

fn handle_run_finished(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        tool_calls,
        open_steps,
        projected_events,
        violations,
        current_run_hash,
    } = context;
    let thread_id = required_identifier(event, index, "threadId")?;
    let run_id = required_identifier(event, index, "runId")?;
    let run_hash = domain_hash("run", run_id);
    let thread_hash = domain_hash("thread", thread_id);
    let interrupted = validate_run_outcome(event, index, omitted_event, omitted_bytes)?;
    if let Some(result) = event.get("result") {
        *omitted_event = true;
        let bytes = serialized_len(result);
        *omitted_bytes += bytes;
        counters.run_payload_bytes += bytes;
    }

    if current_run_hash.as_deref() != Some(run_hash.as_str()) {
        violations.push(Violation {
            index,
            code: "conflicting_run_id",
        });
    }
    let status = if interrupted {
        RunStatus::Interrupted
    } else {
        RunStatus::Finished
    };
    let mut transitioned = false;
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
        } else if run.thread_id_hash == thread_hash
            && current_run_hash.as_deref() == Some(run_hash.as_str())
        {
            run.status = status;
            transitioned = true;
        }
    } else {
        violations.push(Violation {
            index,
            code: "run_terminal_before_start",
        });
    }
    *current_run_hash = Some(run_hash.clone());
    if transitioned {
        mark_terminal_open_tools(&run_hash, index, tool_calls, violations);
        mark_terminal_open_steps(&run_hash, index, open_steps, violations);
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
    Ok(())
}

fn handle_run_error(
    event: &serde_json::Map<String, Value>,
    index: usize,
    context: ProjectionContext<'_>,
    omitted_event: &mut bool,
    omitted_bytes: &mut usize,
) -> Result<(), AgUiProjectionError> {
    let ProjectionContext {
        counters,
        runs,
        tool_calls,
        open_steps,
        projected_events,
        violations,
        current_run_hash,
    } = context;
    let message = required_string(event, index, "message")?;
    *omitted_event = true;
    *omitted_bytes += message.len();
    counters.error_message_bytes += message.len();
    let code = optional_identifier(event, index, "code")?;
    if let Some(run_hash) = current_run_hash.clone() {
        if let Some(run) = runs.get_mut(&run_hash) {
            if run.status.is_terminal() {
                violations.push(Violation {
                    index,
                    code: "duplicate_run_terminal",
                });
            } else {
                run.status = RunStatus::Error;
                run.error_code_hash = code.map(|value| domain_hash("error-code", value));
                mark_terminal_open_tools(&run_hash, index, tool_calls, violations);
                mark_terminal_open_steps(&run_hash, index, open_steps, violations);
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
            }
        }
    } else {
        violations.push(Violation {
            index,
            code: "run_error_before_start",
        });
    }
    Ok(())
}

/// Return an RFC 8785/JCS-style canonical JSON encoding for deterministic receipts.
///
/// # Errors
///
/// Returns [`AgUiProjectionError`] when projection validation or canonical JSON
/// encoding fails.
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

fn validate_base_event_fields(
    event: &serde_json::Map<String, Value>,
    event_index: usize,
) -> Result<(), AgUiProjectionError> {
    if event
        .get("timestamp")
        .is_some_and(|value| !value.is_number())
    {
        return Err(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "timestamp",
        });
    }
    Ok(())
}

fn required_enum<'a>(
    event: &'a serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
    allowed: &[&str],
) -> Result<&'a str, AgUiProjectionError> {
    let value = required_string(event, event_index, field)?;
    if allowed.contains(&value) {
        Ok(value)
    } else {
        Err(AgUiProjectionError::InvalidEventField { event_index, field })
    }
}

fn optional_enum(
    event: &serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
    allowed: &[&str],
) -> Result<(), AgUiProjectionError> {
    if let Some(value) = optional_string(event, event_index, field)? {
        if !allowed.contains(&value) {
            return Err(AgUiProjectionError::InvalidEventField { event_index, field });
        }
    }
    Ok(())
}

fn required_literal(
    event: &serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
    expected: &str,
) -> Result<(), AgUiProjectionError> {
    if required_string(event, event_index, field)? != expected {
        return Err(AgUiProjectionError::InvalidEventField { event_index, field });
    }
    Ok(())
}

fn optional_literal(
    event: &serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
    expected: &str,
) -> Result<(), AgUiProjectionError> {
    if optional_string(event, event_index, field)?.is_some_and(|value| value != expected) {
        return Err(AgUiProjectionError::InvalidEventField { event_index, field });
    }
    Ok(())
}

fn optional_bool(
    event: &serde_json::Map<String, Value>,
    event_index: usize,
    field: &'static str,
) -> Result<(), AgUiProjectionError> {
    if event.get(field).is_some_and(|value| !value.is_boolean()) {
        return Err(AgUiProjectionError::InvalidEventField { event_index, field });
    }
    Ok(())
}

fn nested_required_string<'a>(
    object: &'a serde_json::Map<String, Value>,
    event_index: usize,
    key: &str,
    field: &'static str,
) -> Result<&'a str, AgUiProjectionError> {
    object
        .get(key)
        .and_then(Value::as_str)
        .ok_or(AgUiProjectionError::InvalidEventField { event_index, field })
}

fn nested_optional_string<'a>(
    object: &'a serde_json::Map<String, Value>,
    event_index: usize,
    key: &str,
    field: &'static str,
) -> Result<Option<&'a str>, AgUiProjectionError> {
    match object.get(key) {
        None => Ok(None),
        Some(value) => value
            .as_str()
            .map(Some)
            .ok_or(AgUiProjectionError::InvalidEventField { event_index, field }),
    }
}

fn nested_required_identifier<'a>(
    object: &'a serde_json::Map<String, Value>,
    event_index: usize,
    key: &str,
    field: &'static str,
) -> Result<&'a str, AgUiProjectionError> {
    let value = nested_required_string(object, event_index, key, field)?;
    validate_identifier(value, event_index, field)?;
    Ok(value)
}

fn nested_optional_identifier<'a>(
    object: &'a serde_json::Map<String, Value>,
    event_index: usize,
    key: &str,
    field: &'static str,
) -> Result<Option<&'a str>, AgUiProjectionError> {
    let value = nested_optional_string(object, event_index, key, field)?;
    if let Some(value) = value {
        validate_identifier(value, event_index, field)?;
    }
    Ok(value)
}

fn nested_required_array<'a>(
    object: &'a serde_json::Map<String, Value>,
    event_index: usize,
    key: &str,
    field: &'static str,
) -> Result<&'a Vec<Value>, AgUiProjectionError> {
    object
        .get(key)
        .and_then(Value::as_array)
        .ok_or(AgUiProjectionError::InvalidEventField { event_index, field })
}

fn validate_run_input(
    value: &Value,
    event_index: usize,
) -> Result<RunInputIdentifiers<'_>, AgUiProjectionError> {
    let object = value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "input",
        })?;
    let thread_id = nested_required_identifier(object, event_index, "threadId", "input.threadId")?;
    let run_id = nested_required_identifier(object, event_index, "runId", "input.runId")?;
    let parent_run_id =
        nested_optional_identifier(object, event_index, "parentRunId", "input.parentRunId")?;

    let messages = nested_required_array(object, event_index, "messages", "input.messages")?;
    validate_messages(messages, event_index)?;

    for tool in nested_required_array(object, event_index, "tools", "input.tools")? {
        validate_input_tool(tool, event_index)?;
    }
    for context in nested_required_array(object, event_index, "context", "input.context")? {
        validate_input_context(context, event_index)?;
    }
    if let Some(resume) = object.get("resume") {
        let entries = resume
            .as_array()
            .ok_or(AgUiProjectionError::InvalidEventField {
                event_index,
                field: "input.resume",
            })?;
        for entry in entries {
            validate_resume_entry(entry, event_index)?;
        }
    }
    Ok(RunInputIdentifiers {
        thread_id,
        run_id,
        parent_run_id,
    })
}

fn validate_input_tool(value: &Value, event_index: usize) -> Result<(), AgUiProjectionError> {
    let object = value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "input.tools[]",
        })?;
    nested_required_identifier(object, event_index, "name", "input.tools[].name")?;
    nested_required_string(
        object,
        event_index,
        "description",
        "input.tools[].description",
    )?;
    if object
        .get("metadata")
        .is_some_and(|value| !value.is_object())
    {
        return Err(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "input.tools[].metadata",
        });
    }
    Ok(())
}

fn validate_input_context(value: &Value, event_index: usize) -> Result<(), AgUiProjectionError> {
    let object = value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "input.context[]",
        })?;
    nested_required_string(
        object,
        event_index,
        "description",
        "input.context[].description",
    )?;
    nested_required_string(object, event_index, "value", "input.context[].value")?;
    Ok(())
}

fn validate_resume_entry(value: &Value, event_index: usize) -> Result<(), AgUiProjectionError> {
    let object = value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "input.resume[]",
        })?;
    nested_required_identifier(
        object,
        event_index,
        "interruptId",
        "input.resume[].interruptId",
    )?;
    let status = nested_required_string(object, event_index, "status", "input.resume[].status")?;
    if !matches!(status, "resolved" | "cancelled") {
        return Err(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "input.resume[].status",
        });
    }
    Ok(())
}

fn validate_messages(messages: &[Value], event_index: usize) -> Result<(), AgUiProjectionError> {
    for message in messages {
        validate_message(message, event_index)?;
    }
    Ok(())
}

fn validate_message(value: &Value, event_index: usize) -> Result<(), AgUiProjectionError> {
    let object = value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[]",
        })?;
    nested_required_identifier(object, event_index, "id", "messages[].id")?;
    let role = nested_required_string(object, event_index, "role", "messages[].role")?;
    match role {
        "developer" | "system" => {
            nested_required_string(object, event_index, "content", "messages[].content")?;
            validate_base_message_optionals(object, event_index)?;
        }
        "assistant" => {
            nested_optional_string(object, event_index, "content", "messages[].content")?;
            if let Some(tool_calls) = object.get("toolCalls") {
                let tool_calls =
                    tool_calls
                        .as_array()
                        .ok_or(AgUiProjectionError::InvalidEventField {
                            event_index,
                            field: "messages[].toolCalls",
                        })?;
                for tool_call in tool_calls {
                    validate_message_tool_call(tool_call, event_index)?;
                }
            }
            validate_base_message_optionals(object, event_index)?;
        }
        "user" => {
            validate_user_message_content(object, event_index)?;
            validate_base_message_optionals(object, event_index)?;
        }
        "tool" => {
            nested_required_string(object, event_index, "content", "messages[].content")?;
            nested_required_identifier(object, event_index, "toolCallId", "messages[].toolCallId")?;
            nested_optional_string(object, event_index, "error", "messages[].error")?;
            nested_optional_string(
                object,
                event_index,
                "encryptedValue",
                "messages[].encryptedValue",
            )?;
        }
        "activity" => {
            nested_required_identifier(
                object,
                event_index,
                "activityType",
                "messages[].activityType",
            )?;
            if object.get("content").is_none_or(|value| !value.is_object()) {
                return Err(AgUiProjectionError::InvalidEventField {
                    event_index,
                    field: "messages[].content",
                });
            }
        }
        "reasoning" => {
            nested_required_string(object, event_index, "content", "messages[].content")?;
            nested_optional_string(
                object,
                event_index,
                "encryptedValue",
                "messages[].encryptedValue",
            )?;
        }
        _ => {
            return Err(AgUiProjectionError::InvalidEventField {
                event_index,
                field: "messages[].role",
            });
        }
    }
    Ok(())
}

fn validate_base_message_optionals(
    object: &serde_json::Map<String, Value>,
    event_index: usize,
) -> Result<(), AgUiProjectionError> {
    nested_optional_identifier(object, event_index, "name", "messages[].name")?;
    nested_optional_string(
        object,
        event_index,
        "encryptedValue",
        "messages[].encryptedValue",
    )?;
    Ok(())
}

fn validate_message_tool_call(
    value: &Value,
    event_index: usize,
) -> Result<(), AgUiProjectionError> {
    let object = value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].toolCalls[]",
        })?;
    nested_required_identifier(object, event_index, "id", "messages[].toolCalls[].id")?;
    if nested_required_string(object, event_index, "type", "messages[].toolCalls[].type")?
        != "function"
    {
        return Err(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].toolCalls[].type",
        });
    }
    let function = object.get("function").and_then(Value::as_object).ok_or(
        AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].toolCalls[].function",
        },
    )?;
    nested_required_identifier(
        function,
        event_index,
        "name",
        "messages[].toolCalls[].function.name",
    )?;
    nested_required_string(
        function,
        event_index,
        "arguments",
        "messages[].toolCalls[].function.arguments",
    )?;
    nested_optional_string(
        object,
        event_index,
        "encryptedValue",
        "messages[].toolCalls[].encryptedValue",
    )?;
    Ok(())
}

fn validate_user_message_content(
    object: &serde_json::Map<String, Value>,
    event_index: usize,
) -> Result<(), AgUiProjectionError> {
    let content = object
        .get("content")
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].content",
        })?;
    if content.is_string() {
        return Ok(());
    }
    let parts = content
        .as_array()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].content",
        })?;
    for part in parts {
        validate_input_content(part, event_index)?;
    }
    Ok(())
}

fn validate_input_content(value: &Value, event_index: usize) -> Result<(), AgUiProjectionError> {
    let object = value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].content[]",
        })?;
    let content_type =
        nested_required_string(object, event_index, "type", "messages[].content[].type")?;
    match content_type {
        "text" => {
            nested_required_string(object, event_index, "text", "messages[].content[].text")?;
        }
        "image" | "audio" | "video" | "document" => {
            validate_input_source(object, event_index)?;
        }
        "binary" => validate_legacy_binary_input(object, event_index)?,
        _ => {
            return Err(AgUiProjectionError::InvalidEventField {
                event_index,
                field: "messages[].content[].type",
            });
        }
    }
    Ok(())
}

fn validate_input_source(
    object: &serde_json::Map<String, Value>,
    event_index: usize,
) -> Result<(), AgUiProjectionError> {
    let source = object.get("source").and_then(Value::as_object).ok_or(
        AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].content[].source",
        },
    )?;
    let source_type = nested_required_string(
        source,
        event_index,
        "type",
        "messages[].content[].source.type",
    )?;
    if !matches!(source_type, "data" | "url") {
        return Err(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].content[].source.type",
        });
    }
    nested_required_string(
        source,
        event_index,
        "value",
        "messages[].content[].source.value",
    )?;
    if source_type == "data" {
        nested_required_string(
            source,
            event_index,
            "mimeType",
            "messages[].content[].source.mimeType",
        )?;
    } else {
        nested_optional_string(
            source,
            event_index,
            "mimeType",
            "messages[].content[].source.mimeType",
        )?;
    }
    Ok(())
}

fn validate_legacy_binary_input(
    object: &serde_json::Map<String, Value>,
    event_index: usize,
) -> Result<(), AgUiProjectionError> {
    nested_required_string(
        object,
        event_index,
        "mimeType",
        "messages[].content[].mimeType",
    )?;
    let id = nested_optional_identifier(object, event_index, "id", "messages[].content[].id")?;
    let url = nested_optional_string(object, event_index, "url", "messages[].content[].url")?;
    let data = nested_optional_string(object, event_index, "data", "messages[].content[].data")?;
    nested_optional_string(
        object,
        event_index,
        "filename",
        "messages[].content[].filename",
    )?;
    if [id, url, data]
        .into_iter()
        .all(|value| value.is_none_or(str::is_empty))
    {
        return Err(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "messages[].content[].binary_payload",
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
        "success" => {
            if object.len() != 1 {
                return Err(AgUiProjectionError::InvalidEventField {
                    event_index,
                    field: "outcome",
                });
            }
            Ok(false)
        }
        "interrupt" => {
            if object.len() != 2 {
                return Err(AgUiProjectionError::InvalidEventField {
                    event_index,
                    field: "outcome",
                });
            }
            let interrupts_value =
                object
                    .get("interrupts")
                    .ok_or(AgUiProjectionError::InvalidEventField {
                        event_index,
                        field: "outcome.interrupts",
                    })?;
            let interrupts = interrupts_value
                .as_array()
                .filter(|values| !values.is_empty())
                .ok_or(AgUiProjectionError::InvalidEventField {
                    event_index,
                    field: "outcome.interrupts",
                })?;
            for interrupt in interrupts {
                validate_interrupt(interrupt, event_index)?;
            }
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

fn validate_interrupt(value: &Value, event_index: usize) -> Result<(), AgUiProjectionError> {
    let object = value
        .as_object()
        .ok_or(AgUiProjectionError::InvalidEventField {
            event_index,
            field: "outcome.interrupts[]",
        })?;
    nested_required_identifier(object, event_index, "id", "outcome.interrupts[].id")?;
    nested_required_string(object, event_index, "reason", "outcome.interrupts[].reason")?;
    nested_optional_string(
        object,
        event_index,
        "message",
        "outcome.interrupts[].message",
    )?;
    nested_optional_identifier(
        object,
        event_index,
        "toolCallId",
        "outcome.interrupts[].toolCallId",
    )?;
    nested_optional_string(
        object,
        event_index,
        "expiresAt",
        "outcome.interrupts[].expiresAt",
    )?;
    for (key, field) in [
        ("responseSchema", "outcome.interrupts[].responseSchema"),
        ("metadata", "outcome.interrupts[].metadata"),
    ] {
        if object.get(key).is_some_and(|value| !value.is_object()) {
            return Err(AgUiProjectionError::InvalidEventField { event_index, field });
        }
    }
    Ok(())
}

fn require_active_run(
    index: usize,
    current_run_hash: &Option<String>,
    runs: &BTreeMap<String, RunProjection>,
    violations: &mut Vec<Violation>,
) {
    if current_run_hash
        .as_ref()
        .and_then(|hash| runs.get(hash))
        .is_none_or(|run| run.status.is_terminal())
    {
        violations.push(Violation {
            index,
            code: "event_without_active_run",
        });
    }
}

fn active_run(
    index: usize,
    current_run_hash: &Option<String>,
    runs: &BTreeMap<String, RunProjection>,
    violations: &mut Vec<Violation>,
) -> Option<String> {
    match current_run_hash.as_ref().and_then(|hash| runs.get(hash)) {
        Some(run) if !run.status.is_terminal() => current_run_hash.clone(),
        _ => {
            violations.push(Violation {
                index,
                code: "event_without_active_run",
            });
            None
        }
    }
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

fn mark_terminal_open_steps(
    run_hash: &str,
    index: usize,
    open_steps: &BTreeSet<(String, String)>,
    violations: &mut Vec<Violation>,
) {
    for (step_run_hash, _) in open_steps {
        if step_run_hash == run_hash {
            violations.push(Violation {
                index,
                code: "run_terminal_with_open_step",
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

    fn request_with_events(events: Vec<Value>) -> Value {
        json!({
            "schema": REQUEST_SCHEMA,
            "protocol": {"name": PROTOCOL_NAME, "core_version": CORE_VERSION},
            "source": {"adapter_id": "property-corpus", "agent_id_hash": "agent"},
            "events": events,
        })
    }

    fn run_started() -> Value {
        json!({"type": "RUN_STARTED", "threadId": "thread", "runId": "run"})
    }

    fn run_finished() -> Value {
        json!({"type": "RUN_FINISHED", "threadId": "thread", "runId": "run"})
    }

    fn run_input(thread_id: &str, run_id: &str, parent_run_id: Option<&str>) -> Value {
        let mut input = json!({
            "threadId": thread_id,
            "runId": run_id,
            "messages": [],
            "tools": [],
            "context": [],
        });
        if let Some(parent_run_id) = parent_run_id {
            input
                .as_object_mut()
                .expect("run input object")
                .insert("parentRunId".to_string(), json!(parent_run_id));
        }
        input
    }

    fn request_for_known_event(event_type: &str, event: Value) -> Value {
        let events = match event_type {
            "RUN_STARTED" => vec![event, run_finished()],
            "RUN_FINISHED" | "RUN_ERROR" => vec![run_started(), event],
            _ => vec![run_started(), event, run_finished()],
        };
        request_with_events(events)
    }

    fn violation_codes(output: &Value) -> Vec<&str> {
        output["violations"]
            .as_array()
            .expect("violations")
            .iter()
            .filter_map(|value| value["code"].as_str())
            .collect()
    }

    fn string_values(value: &Value, output: &mut Vec<String>) {
        match value {
            Value::Array(values) => {
                for value in values {
                    string_values(value, output);
                }
            }
            Value::Object(object) => {
                for value in object.values() {
                    string_values(value, output);
                }
            }
            Value::String(value) => output.push(value.clone()),
            _ => {}
        }
    }

    struct KnownEventCase {
        event: Value,
        missing_field: &'static str,
        wrong_type_field: &'static str,
    }

    fn known_event_cases() -> Vec<KnownEventCase> {
        vec![
            KnownEventCase {
                event: run_started(),
                missing_field: "threadId",
                wrong_type_field: "threadId",
            },
            KnownEventCase {
                event: run_finished(),
                missing_field: "threadId",
                wrong_type_field: "threadId",
            },
            KnownEventCase {
                event: json!({"type": "RUN_ERROR", "message": "private"}),
                missing_field: "message",
                wrong_type_field: "message",
            },
            KnownEventCase {
                event: json!({"type": "STEP_STARTED", "stepName": "step"}),
                missing_field: "stepName",
                wrong_type_field: "stepName",
            },
            KnownEventCase {
                event: json!({"type": "STEP_FINISHED", "stepName": "step"}),
                missing_field: "stepName",
                wrong_type_field: "stepName",
            },
            KnownEventCase {
                event: json!({
                    "type": "TOOL_CALL_START",
                    "toolCallId": "call",
                    "toolCallName": "tool"
                }),
                missing_field: "toolCallId",
                wrong_type_field: "toolCallId",
            },
            KnownEventCase {
                event: json!({"type": "TOOL_CALL_ARGS", "toolCallId": "call", "delta": "private"}),
                missing_field: "delta",
                wrong_type_field: "delta",
            },
            KnownEventCase {
                event: json!({"type": "TOOL_CALL_END", "toolCallId": "call"}),
                missing_field: "toolCallId",
                wrong_type_field: "toolCallId",
            },
            KnownEventCase {
                event: json!({
                    "type": "TOOL_CALL_RESULT",
                    "messageId": "message",
                    "toolCallId": "call",
                    "content": "private"
                }),
                missing_field: "content",
                wrong_type_field: "content",
            },
            KnownEventCase {
                event: json!({"type": "TOOL_CALL_CHUNK", "delta": "private"}),
                missing_field: "type",
                wrong_type_field: "delta",
            },
            KnownEventCase {
                event: json!({"type": "STATE_SNAPSHOT", "snapshot": {"private": true}, "timestamp": 1}),
                missing_field: "snapshot",
                wrong_type_field: "timestamp",
            },
            KnownEventCase {
                event: json!({"type": "STATE_DELTA", "delta": []}),
                missing_field: "delta",
                wrong_type_field: "delta",
            },
            KnownEventCase {
                event: json!({"type": "MESSAGES_SNAPSHOT", "messages": []}),
                missing_field: "messages",
                wrong_type_field: "messages",
            },
            KnownEventCase {
                event: json!({
                    "type": "ACTIVITY_SNAPSHOT",
                    "messageId": "message",
                    "activityType": "progress",
                    "content": {}
                }),
                missing_field: "content",
                wrong_type_field: "content",
            },
            KnownEventCase {
                event: json!({
                    "type": "ACTIVITY_DELTA",
                    "messageId": "message",
                    "activityType": "progress",
                    "patch": []
                }),
                missing_field: "patch",
                wrong_type_field: "patch",
            },
            KnownEventCase {
                event: json!({"type": "RAW", "source": "extension", "event": {"private": true}}),
                missing_field: "event",
                wrong_type_field: "source",
            },
            KnownEventCase {
                event: json!({"type": "CUSTOM", "name": "extension", "value": {"private": true}}),
                missing_field: "value",
                wrong_type_field: "name",
            },
            KnownEventCase {
                event: json!({"type": "TEXT_MESSAGE_START", "messageId": "message"}),
                missing_field: "messageId",
                wrong_type_field: "messageId",
            },
            KnownEventCase {
                event: json!({
                    "type": "TEXT_MESSAGE_CONTENT",
                    "messageId": "message",
                    "delta": "private"
                }),
                missing_field: "delta",
                wrong_type_field: "delta",
            },
            KnownEventCase {
                event: json!({"type": "TEXT_MESSAGE_END", "messageId": "message"}),
                missing_field: "messageId",
                wrong_type_field: "messageId",
            },
            KnownEventCase {
                event: json!({"type": "TEXT_MESSAGE_CHUNK", "delta": "private"}),
                missing_field: "type",
                wrong_type_field: "delta",
            },
            KnownEventCase {
                event: json!({"type": "THINKING_START", "title": "private"}),
                missing_field: "type",
                wrong_type_field: "title",
            },
            KnownEventCase {
                event: json!({"type": "THINKING_END"}),
                missing_field: "type",
                wrong_type_field: "type",
            },
            KnownEventCase {
                event: json!({"type": "THINKING_TEXT_MESSAGE_START"}),
                missing_field: "type",
                wrong_type_field: "type",
            },
            KnownEventCase {
                event: json!({"type": "THINKING_TEXT_MESSAGE_CONTENT", "delta": "private"}),
                missing_field: "delta",
                wrong_type_field: "delta",
            },
            KnownEventCase {
                event: json!({"type": "THINKING_TEXT_MESSAGE_END"}),
                missing_field: "type",
                wrong_type_field: "type",
            },
            KnownEventCase {
                event: json!({"type": "REASONING_START", "messageId": "message"}),
                missing_field: "messageId",
                wrong_type_field: "messageId",
            },
            KnownEventCase {
                event: json!({
                    "type": "REASONING_MESSAGE_START",
                    "messageId": "message",
                    "role": "reasoning"
                }),
                missing_field: "role",
                wrong_type_field: "role",
            },
            KnownEventCase {
                event: json!({
                    "type": "REASONING_MESSAGE_CONTENT",
                    "messageId": "message",
                    "delta": "private"
                }),
                missing_field: "delta",
                wrong_type_field: "delta",
            },
            KnownEventCase {
                event: json!({"type": "REASONING_MESSAGE_END", "messageId": "message"}),
                missing_field: "messageId",
                wrong_type_field: "messageId",
            },
            KnownEventCase {
                event: json!({"type": "REASONING_MESSAGE_CHUNK", "delta": "private"}),
                missing_field: "type",
                wrong_type_field: "delta",
            },
            KnownEventCase {
                event: json!({
                    "type": "REASONING_ENCRYPTED_VALUE",
                    "subtype": "message",
                    "entityId": "message",
                    "encryptedValue": "private"
                }),
                missing_field: "encryptedValue",
                wrong_type_field: "encryptedValue",
            },
            KnownEventCase {
                event: json!({"type": "REASONING_END", "messageId": "message"}),
                missing_field: "messageId",
                wrong_type_field: "messageId",
            },
        ]
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
    fn valid_non_object_state_snapshots_are_accepted() {
        for snapshot in [
            Value::Null,
            json!(["private", "state"]),
            json!("private-state"),
            json!(42),
            json!(true),
        ] {
            let mut input = fixture(COMPLETE_TEXT);
            input["events"]
                .as_array_mut()
                .expect("events")
                .insert(1, json!({"type": "STATE_SNAPSHOT", "snapshot": snapshot}));
            let output = project_ag_ui_readonly(&input).expect("valid state snapshot");
            assert_eq!(output["claims"]["stream_complete"], true);
            assert_eq!(output["observations"]["state_snapshot_keys"], 0);
        }
    }

    #[test]
    fn malformed_known_event_fields_fail_closed() {
        for malformed in [
            json!({"type": "TEXT_MESSAGE_START", "messageId": "m", "role": "tool"}),
            json!({"type": "REASONING_MESSAGE_START", "messageId": "r"}),
            json!({
                "type": "REASONING_ENCRYPTED_VALUE",
                "subtype": "unknown",
                "entityId": "r",
                "encryptedValue": "private"
            }),
            json!({"type": "TEXT_MESSAGE_END", "messageId": "m", "timestamp": "now"}),
        ] {
            let mut input = fixture(COMPLETE_TEXT);
            input["events"]
                .as_array_mut()
                .expect("events")
                .insert(1, malformed);
            assert!(matches!(
                project_ag_ui_readonly(&input),
                Err(AgUiProjectionError::InvalidEventField { .. })
            ));
        }

        let mut malformed_snapshot = fixture(COMPLETE_TEXT);
        malformed_snapshot["events"]
            .as_array_mut()
            .expect("events")
            .insert(
                1,
                json!({"type": "MESSAGES_SNAPSHOT", "messages": [{"role": "user"}]}),
            );
        assert!(matches!(
            project_ag_ui_readonly(&malformed_snapshot),
            Err(AgUiProjectionError::InvalidEventField { .. })
        ));

        let mut malformed_input = fixture(COMPLETE_TEXT);
        malformed_input["events"][0]["input"] = json!({
            "messages": [],
            "tools": [],
            "context": []
        });
        assert!(matches!(
            project_ag_ui_readonly(&malformed_input),
            Err(AgUiProjectionError::InvalidEventField { .. })
        ));
    }

    #[test]
    fn all_known_event_types_validate_required_field_shape() {
        let cases = known_event_cases();
        assert_eq!(cases.len(), 33, "AG-UI 0.0.57 known event corpus drifted");

        for case in cases {
            let event_type = case.event["type"].as_str().expect("event type").to_string();
            project_ag_ui_readonly(&request_for_known_event(&event_type, case.event.clone()))
                .unwrap_or_else(|error| panic!("valid {event_type} rejected: {error}"));

            let mut missing = case.event.clone();
            missing
                .as_object_mut()
                .expect("event object")
                .remove(case.missing_field);
            assert!(
                matches!(
                    project_ag_ui_readonly(&request_for_known_event(&event_type, missing)),
                    Err(AgUiProjectionError::InvalidEventField { .. })
                ),
                "{event_type} accepted missing field {}",
                case.missing_field
            );

            let mut wrong_type = case.event;
            let wrong_value = if case.wrong_type_field == "timestamp" {
                json!("not-a-number")
            } else {
                json!(17)
            };
            wrong_type
                .as_object_mut()
                .expect("event object")
                .insert(case.wrong_type_field.to_string(), wrong_value);
            assert!(
                matches!(
                    project_ag_ui_readonly(&request_for_known_event(&event_type, wrong_type)),
                    Err(AgUiProjectionError::InvalidEventField { .. })
                ),
                "{event_type} accepted wrong type for {}",
                case.wrong_type_field
            );
        }
    }

    #[test]
    fn matching_run_input_identifiers_preserve_complete_outer_run() {
        let mut started = run_started();
        started["parentRunId"] = json!("parent");
        started["input"] = run_input("thread", "run", Some("parent"));
        let output = project_ag_ui_readonly(&request_with_events(vec![started, run_finished()]))
            .expect("matching identifiers");

        assert!(violation_codes(&output).is_empty());
        assert_eq!(output["claims"]["stream_complete"], true);
        assert_eq!(output["runs"][0]["run_id_hash"], domain_hash("run", "run"));
        assert_eq!(
            output["runs"][0]["thread_id_hash"],
            domain_hash("thread", "thread")
        );
        assert_eq!(
            output["runs"][0]["parent_run_id_hash"],
            domain_hash("run", "parent")
        );
    }

    #[test]
    fn mismatched_run_input_identifiers_are_typed_and_outer_authoritative() {
        let canaries = [
            (
                "nested-thread-canary",
                "run",
                Some("parent"),
                "run_input_thread_id_mismatch",
            ),
            (
                "thread",
                "nested-run-canary",
                Some("parent"),
                "run_input_run_id_mismatch",
            ),
            (
                "thread",
                "run",
                Some("nested-parent-canary"),
                "run_input_parent_run_id_mismatch",
            ),
        ];

        for (input_thread, input_run, input_parent, expected_code) in canaries {
            let mut started = run_started();
            started["parentRunId"] = json!("parent");
            started["input"] = run_input(input_thread, input_run, input_parent);
            let output =
                project_ag_ui_readonly(&request_with_events(vec![started, run_finished()]))
                    .expect("structurally valid mismatch");
            let serialized = serde_json::to_string(&output).expect("serialized projection");

            assert_eq!(violation_codes(&output), vec![expected_code]);
            assert_eq!(output["claims"]["stream_complete"], false);
            assert_eq!(output["runs"][0]["run_id_hash"], domain_hash("run", "run"));
            assert_eq!(
                output["runs"][0]["thread_id_hash"],
                domain_hash("thread", "thread")
            );
            assert_eq!(
                output["runs"][0]["parent_run_id_hash"],
                domain_hash("run", "parent")
            );
            for canary in [input_thread, input_run, input_parent.expect("parent")] {
                if canary.contains("canary") {
                    assert!(!serialized.contains(canary), "leaked nested identifier");
                }
            }
        }
    }

    #[test]
    fn parent_run_input_presence_mismatch_fails_closed_both_ways() {
        for (outer_parent, input_parent) in [(Some("parent"), None), (None, Some("parent"))] {
            let mut started = run_started();
            if let Some(outer_parent) = outer_parent {
                started["parentRunId"] = json!(outer_parent);
            }
            started["input"] = run_input("thread", "run", input_parent);
            let output =
                project_ag_ui_readonly(&request_with_events(vec![started, run_finished()]))
                    .expect("structurally valid presence mismatch");

            assert_eq!(
                violation_codes(&output),
                vec!["run_input_parent_run_id_mismatch"]
            );
            assert_eq!(output["claims"]["stream_complete"], false);
            assert_eq!(
                output["runs"][0]["parent_run_id_hash"].is_null(),
                outer_parent.is_none()
            );
        }
    }

    #[test]
    fn independent_model_oracle_covers_run_step_and_tool_state() {
        struct OracleCase {
            events: Vec<Value>,
            actions: Vec<&'static str>,
            run_status: &'static str,
            tool_status: Option<&'static str>,
            violation_codes: Vec<&'static str>,
            stream_complete: bool,
        }

        let cases = vec![
            OracleCase {
                events: vec![
                    run_started(),
                    json!({"type": "STEP_STARTED", "stepName": "step"}),
                    json!({"type": "STEP_FINISHED", "stepName": "step"}),
                    json!({
                        "type": "TOOL_CALL_START",
                        "toolCallId": "call",
                        "toolCallName": "tool"
                    }),
                    json!({"type": "TOOL_CALL_ARGS", "toolCallId": "call", "delta": "private"}),
                    json!({"type": "TOOL_CALL_END", "toolCallId": "call"}),
                    json!({
                        "type": "TOOL_CALL_RESULT",
                        "messageId": "message",
                        "toolCallId": "call",
                        "content": "private"
                    }),
                    run_finished(),
                ],
                actions: vec![
                    "run_opened",
                    "step_opened",
                    "step_closed",
                    "intent_opened",
                    "request_closed",
                    "result_observed",
                    "run_closed",
                ],
                run_status: "finished",
                tool_status: Some("result_observed"),
                violation_codes: vec![],
                stream_complete: true,
            },
            OracleCase {
                events: vec![
                    run_started(),
                    json!({"type": "STEP_STARTED", "stepName": "step"}),
                    json!({
                        "type": "TOOL_CALL_START",
                        "toolCallId": "call",
                        "toolCallName": "tool"
                    }),
                    run_finished(),
                ],
                actions: vec!["run_opened", "step_opened", "intent_opened", "run_closed"],
                run_status: "finished",
                tool_status: Some("started"),
                violation_codes: vec![
                    "run_terminal_with_open_tool_call",
                    "run_terminal_with_open_step",
                    "open_tool_call_at_batch_end",
                    "open_step_at_batch_end",
                ],
                stream_complete: false,
            },
            OracleCase {
                events: vec![
                    run_started(),
                    json!({"type": "STEP_FINISHED", "stepName": "step"}),
                    json!({"type": "TOOL_CALL_ARGS", "toolCallId": "call", "delta": "private"}),
                    run_finished(),
                ],
                actions: vec!["run_opened", "run_closed"],
                run_status: "finished",
                tool_status: None,
                violation_codes: vec!["step_finish_before_start", "tool_args_before_start"],
                stream_complete: false,
            },
        ];

        for case in cases {
            let output =
                project_ag_ui_readonly(&request_with_events(case.events)).expect("oracle case");
            let actions = output["projected_events"]
                .as_array()
                .expect("projected events")
                .iter()
                .map(|event| event["action"].as_str().expect("action"))
                .collect::<Vec<_>>();

            assert_eq!(actions, case.actions);
            assert_eq!(output["runs"][0]["status"], case.run_status);
            assert_eq!(
                output["tool_calls"]
                    .as_array()
                    .expect("tool calls")
                    .first()
                    .map(|call| call["status"].as_str().expect("tool status")),
                case.tool_status
            );
            assert_eq!(violation_codes(&output), case.violation_codes);
            assert_eq!(output["claims"]["stream_complete"], case.stream_complete);
        }
    }

    #[test]
    fn invalid_tool_transitions_do_not_emit_normal_semantic_events() {
        let output = project_ag_ui_readonly(&fixture(ADVERSARIAL)).expect("projection");
        let actions = output["projected_events"]
            .as_array()
            .expect("events")
            .iter()
            .filter_map(|event| event["action"].as_str())
            .collect::<Vec<_>>();
        assert!(!actions.contains(&"request_closed"));
        assert!(!actions.contains(&"result_observed"));
        assert_eq!(output["claims"]["stream_complete"], false);
    }

    #[test]
    fn exhaustive_tool_transition_sequences_remain_fail_closed() {
        const ACTION_ORDER: [&str; 3] = ["intent_opened", "request_closed", "result_observed"];
        for sequence_len in 0..=5_u32 {
            for mut sequence_code in 0..4_usize.pow(sequence_len) {
                let mut events = vec![json!({
                    "type": "RUN_STARTED",
                    "threadId": "thread",
                    "runId": "run"
                })];
                for _ in 0..sequence_len {
                    let event = match sequence_code % 4 {
                        0 => json!({
                            "type": "TOOL_CALL_START",
                            "toolCallId": "call",
                            "toolCallName": "tool"
                        }),
                        1 => json!({
                            "type": "TOOL_CALL_ARGS",
                            "toolCallId": "call",
                            "delta": "sequence-canary-args"
                        }),
                        2 => json!({"type": "TOOL_CALL_END", "toolCallId": "call"}),
                        _ => json!({
                            "type": "TOOL_CALL_RESULT",
                            "messageId": "message",
                            "toolCallId": "call",
                            "content": "sequence-canary-result",
                            "role": "tool"
                        }),
                    };
                    events.push(event);
                    sequence_code /= 4;
                }
                events.push(json!({
                    "type": "RUN_FINISHED",
                    "threadId": "thread",
                    "runId": "run"
                }));

                let input = request_with_events(events);
                let output = project_ag_ui_readonly(&input).expect("valid transition corpus case");
                let actions = output["projected_events"]
                    .as_array()
                    .expect("projected events")
                    .iter()
                    .filter(|event| event["object"]["object_type"] == "agent_tool_call")
                    .filter_map(|event| event["action"].as_str())
                    .collect::<Vec<_>>();
                assert!(actions.len() <= ACTION_ORDER.len());
                assert_eq!(actions, ACTION_ORDER[..actions.len()]);
                assert_eq!(output["claims"]["external_effects_verified"], false);

                let mut statuses = Vec::new();
                verdict_statuses(&output, &mut statuses);
                assert!(statuses.iter().all(|status| status != "verified"));
                let serialized = serde_json::to_string(&output).expect("serialized projection");
                assert!(!serialized.contains("sequence-canary"));
            }
        }
    }

    #[test]
    fn deterministic_mixed_sequence_corpus_preserves_projection_invariants() {
        for seed in 0..128_u64 {
            let mut generator = seed;
            let mut events = vec![json!({
                "type": "RUN_STARTED",
                "threadId": "thread",
                "runId": "run"
            })];
            for _ in 0..12 {
                generator = generator
                    .wrapping_mul(6_364_136_223_846_793_005)
                    .wrapping_add(1);
                let event = match generator % 12 {
                    0 => json!({"type": "STEP_STARTED", "stepName": "step"}),
                    1 => json!({"type": "STEP_FINISHED", "stepName": "step"}),
                    2 => json!({
                        "type": "TOOL_CALL_START",
                        "toolCallId": "call",
                        "toolCallName": "tool"
                    }),
                    3 => json!({
                        "type": "TOOL_CALL_ARGS",
                        "toolCallId": "call",
                        "delta": "mixed-sequence-canary"
                    }),
                    4 => json!({"type": "TOOL_CALL_END", "toolCallId": "call"}),
                    5 => json!({
                        "type": "TOOL_CALL_RESULT",
                        "messageId": "message",
                        "toolCallId": "call",
                        "content": "mixed-sequence-canary",
                        "role": "tool"
                    }),
                    6 => json!({
                        "type": "STATE_SNAPSHOT",
                        "snapshot": {"private": "mixed-sequence-canary"}
                    }),
                    7 => json!({
                        "type": "STATE_DELTA",
                        "delta": [{"op": "replace", "path": "/private", "value": "mixed-sequence-canary"}]
                    }),
                    8 => json!({
                        "type": "ACTIVITY_SNAPSHOT",
                        "messageId": "message",
                        "activityType": "progress",
                        "content": {"private": "mixed-sequence-canary"}
                    }),
                    9 => json!({
                        "type": "TEXT_MESSAGE_CONTENT",
                        "messageId": "message",
                        "delta": "mixed-sequence-canary"
                    }),
                    10 => json!({
                        "type": "CUSTOM",
                        "name": "extension",
                        "value": {"private": "mixed-sequence-canary"}
                    }),
                    _ => json!({
                        "type": "FUTURE_PRIVATE_EVENT",
                        "private": "mixed-sequence-canary"
                    }),
                };
                events.push(event);
            }
            events.push(json!({
                "type": "RUN_FINISHED",
                "threadId": "thread",
                "runId": "run"
            }));

            let input = request_with_events(events);
            let first = project_ag_ui_readonly(&input).expect("first projection");
            let second = project_ag_ui_readonly(&input).expect("second projection");
            assert_eq!(first, second);
            assert_eq!(first["claims"]["external_effects_verified"], false);
            assert_eq!(
                first["counts"]["projected_events"].as_u64(),
                Some(
                    first["projected_events"]
                        .as_array()
                        .expect("projected events")
                        .len() as u64
                )
            );
            assert!(first["projected_events"]
                .as_array()
                .expect("projected events")
                .windows(2)
                .all(|pair| pair[0]["event_index"].as_u64() <= pair[1]["event_index"].as_u64()));
            let mut statuses = Vec::new();
            verdict_statuses(&first, &mut statuses);
            assert!(statuses.iter().all(|status| status != "verified"));
            assert!(!serde_json::to_string(&first)
                .expect("serialized projection")
                .contains("mixed-sequence-canary"));
        }
    }

    #[test]
    fn step_ordering_is_fail_closed() {
        let mut input = fixture(COMPLETE_TEXT);
        input["events"].as_array_mut().expect("events").insert(
            1,
            json!({"type": "STEP_FINISHED", "stepName": "not-started"}),
        );
        let output = project_ag_ui_readonly(&input).expect("projection");
        assert!(output["violations"]
            .as_array()
            .expect("violations")
            .iter()
            .any(|violation| violation["code"] == "step_finish_before_start"));
        assert!(!output["projected_events"]
            .as_array()
            .expect("events")
            .iter()
            .any(|event| event["action"] == "step_closed"));
        assert_eq!(output["claims"]["stream_complete"], false);
    }

    #[test]
    fn request_protocol_and_source_objects_reject_unexpected_fields_without_echoing_them() {
        let cases = [
            (
                "request",
                "endpoint_url_canary",
                "https://internal.example.test/ag-ui?token=request-secret",
            ),
            ("protocol", "authorization_canary", "Bearer protocol-secret"),
            (
                "source",
                "workspace_path_canary",
                "/Users/private/source-secret",
            ),
        ];

        for (object_name, unexpected_field, rejected_value) in cases {
            let mut input = request_with_events(vec![run_started(), run_finished()]);
            let object = match object_name {
                "request" => input.as_object_mut().expect("request object"),
                "protocol" | "source" => input[object_name]
                    .as_object_mut()
                    .expect("nested request object"),
                _ => unreachable!("fixed test case"),
            };
            object.insert(unexpected_field.to_string(), json!(rejected_value));

            let error = project_ag_ui_readonly(&input).expect_err("closed request envelope");
            assert_eq!(
                error,
                AgUiProjectionError::UnexpectedRequestField {
                    object: object_name
                }
            );
            let display = error.to_string();
            assert!(!display.contains(unexpected_field));
            assert!(!display.contains(rejected_value));
        }
    }

    #[test]
    fn event_objects_remain_governed_by_the_pinned_protocol_validator() {
        let input = request_with_events(vec![
            json!({
                "type": "RUN_STARTED",
                "threadId": "thread",
                "runId": "run",
                "futureProtocolField": "not-an-envelope-field"
            }),
            run_finished(),
        ]);
        assert!(project_ag_ui_readonly(&input).is_ok());
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
    fn exact_identifier_event_and_request_boundaries_use_bytes() {
        for run_id in ["x".repeat(MAX_IDENTIFIER_BYTES), "界".repeat(85)] {
            assert!(run_id.len() <= MAX_IDENTIFIER_BYTES);
            let input = request_with_events(vec![
                json!({"type": "RUN_STARTED", "threadId": "thread", "runId": run_id.clone()}),
                json!({"type": "RUN_FINISHED", "threadId": "thread", "runId": run_id}),
            ]);
            assert!(project_ag_ui_readonly(&input).is_ok());
        }

        for run_id in ["x".repeat(MAX_IDENTIFIER_BYTES + 1), "界".repeat(86)] {
            let actual_bytes = run_id.len();
            assert!(actual_bytes > MAX_IDENTIFIER_BYTES);
            let input = request_with_events(vec![json!({
                "type": "RUN_STARTED",
                "threadId": "thread",
                "runId": run_id
            })]);
            assert!(matches!(
                project_ag_ui_readonly(&input),
                Err(AgUiProjectionError::IdentifierTooLong {
                    actual,
                    max: MAX_IDENTIFIER_BYTES,
                    ..
                }) if actual == actual_bytes
            ));
        }

        let exact_events = request_with_events(
            (0..MAX_EVENTS)
                .map(|_| json!({"type": "FUTURE_EVENT"}))
                .collect(),
        );
        assert!(project_ag_ui_readonly(&exact_events).is_ok());

        let over_events = request_with_events(
            (0..=MAX_EVENTS)
                .map(|_| json!({"type": "FUTURE_EVENT"}))
                .collect(),
        );
        assert_eq!(
            project_ag_ui_readonly(&over_events),
            Err(AgUiProjectionError::InvalidEventCount {
                actual: MAX_EVENTS + 1,
                max: MAX_EVENTS,
            })
        );

        let mut exact_request = request_with_events(vec![
            run_started(),
            json!({"type": "CUSTOM", "name": "boundary", "value": ""}),
            run_finished(),
        ]);
        let envelope_bytes = serialized_len(&exact_request);
        exact_request["events"][1]["value"] = json!("x".repeat(MAX_REQUEST_BYTES - envelope_bytes));
        assert_eq!(serialized_len(&exact_request), MAX_REQUEST_BYTES);
        assert!(project_ag_ui_readonly(&exact_request).is_ok());

        let over_budget_padding = format!(
            "{}x",
            exact_request["events"][1]["value"]
                .as_str()
                .expect("padding")
        );
        exact_request["events"][1]["value"] = json!(over_budget_padding);
        assert_eq!(serialized_len(&exact_request), MAX_REQUEST_BYTES + 1);
        assert_eq!(
            project_ag_ui_readonly(&exact_request),
            Err(AgUiProjectionError::RequestTooLarge {
                actual: MAX_REQUEST_BYTES + 1,
                max: MAX_REQUEST_BYTES,
            })
        );

        let mut multibyte_request = request_with_events(vec![
            run_started(),
            json!({"type": "CUSTOM", "name": "boundary", "value": ""}),
            run_finished(),
        ]);
        let multibyte_padding = "界".repeat(MAX_REQUEST_BYTES / 3);
        assert!(multibyte_padding.chars().count() < MAX_REQUEST_BYTES);
        multibyte_request["events"][1]["value"] = json!(multibyte_padding);
        let actual_bytes = serialized_len(&multibyte_request);
        assert!(actual_bytes > MAX_REQUEST_BYTES);
        assert_eq!(
            project_ag_ui_readonly(&multibyte_request),
            Err(AgUiProjectionError::RequestTooLarge {
                actual: actual_bytes,
                max: MAX_REQUEST_BYTES,
            })
        );
    }

    #[test]
    fn reordered_input_keys_have_the_same_canonical_projection() {
        let left: Value = serde_json::from_str(
            r#"{
                "schema":"agent_bridge.ag_ui_readonly_projection_request.v0",
                "protocol":{"name":"ag-ui","core_version":"0.0.57"},
                "source":{"adapter_id":"adapter","agent_id_hash":"agent"},
                "events":[
                    {"type":"RUN_STARTED","threadId":"thread","runId":"run"},
                    {"type":"RUN_FINISHED","threadId":"thread","runId":"run"}
                ]
            }"#,
        )
        .expect("left request");
        let right: Value = serde_json::from_str(
            r#"{
                "events":[
                    {"runId":"run","threadId":"thread","type":"RUN_STARTED"},
                    {"runId":"run","type":"RUN_FINISHED","threadId":"thread"}
                ],
                "source":{"agent_id_hash":"agent","adapter_id":"adapter"},
                "protocol":{"core_version":"0.0.57","name":"ag-ui"},
                "schema":"agent_bridge.ag_ui_readonly_projection_request.v0"
            }"#,
        )
        .expect("right request");

        assert_eq!(
            project_ag_ui_readonly_canonical(&left).expect("left projection"),
            project_ag_ui_readonly_canonical(&right).expect("right projection")
        );
    }

    #[test]
    fn exact_verified_string_never_becomes_an_output_value() {
        let output = project_ag_ui_readonly(&request_with_events(vec![
            run_started(),
            json!({"type": "CUSTOM", "name": "verified", "value": "verified"}),
            json!({"type": "RAW", "source": "verified", "event": {"status": "verified"}}),
            run_finished(),
        ]))
        .expect("projection");
        let mut values = Vec::new();
        string_values(&output, &mut values);
        assert!(values.iter().all(|value| value != "verified"));

        let marker = "verified".repeat(MAX_IDENTIFIER_BYTES);
        let error = project_ag_ui_readonly(&request_with_events(vec![json!({
            "type": "RUN_STARTED",
            "threadId": "thread",
            "runId": marker
        })]))
        .expect_err("overlong identifier");
        assert!(!error.to_string().contains("verified"));
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
