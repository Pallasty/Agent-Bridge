use std::collections::{BTreeMap, BTreeSet};

use serde_json::{json, Value};

pub const LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_fixture.v0";
pub const LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_validation.v0";
pub const LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_readback.v0";
pub const LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_validation_envelope.v0";
pub const LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_evidence_packet.v0";
pub const LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_consumption_preflight.v0";

const EXPECTED_EVENT_TYPES: [&str; 8] = [
    "human.select",
    "ai.patch_proposed",
    "runtime.patch_result",
    "presentation.state_changed",
    "runtime.verification_result",
    "human.reject",
    "feedback.explicit_text",
    "ai.patch_proposed",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InteractionFeedbackValidationReport {
    pub valid: bool,
    pub failure_reasons: Vec<String>,
    pub readback: Value,
}

impl InteractionFeedbackValidationReport {
    pub fn to_value(&self) -> Value {
        json!({
            "schema": LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA,
            "valid": self.valid,
            "failure_reasons": self.failure_reasons,
            "readback": self.readback,
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false
        })
    }
}

pub fn validate_interaction_feedback_fixture(
    fixture: &Value,
) -> InteractionFeedbackValidationReport {
    let mut failure_reasons = Vec::new();
    let readback = build_interaction_feedback_readback(fixture);

    if fixture.get("schema").and_then(Value::as_str)
        != Some(LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA)
    {
        failure_reasons.push("schema_mismatch".to_string());
    }

    if fixture
        .get("requires_screenshot_for_primary_readback")
        .and_then(Value::as_bool)
        != Some(false)
    {
        failure_reasons.push("primary_readback_requires_screenshot".to_string());
    }

    validate_event_loop(fixture, &mut failure_reasons);
    validate_verification_honesty(fixture, &mut failure_reasons);
    validate_feedback_and_revision(fixture, &readback, &mut failure_reasons);

    InteractionFeedbackValidationReport {
        valid: failure_reasons.is_empty(),
        failure_reasons,
        readback,
    }
}

pub fn build_interaction_feedback_validation_envelope(fixture: &Value) -> Value {
    let report = validate_interaction_feedback_fixture(fixture);
    let report_value = report.to_value();

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA,
        "fixture_schema": fixture.get("schema").cloned().unwrap_or(Value::Null),
        "expected_fixture_schema": LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA,
        "validation_schema": LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA,
        "readback_schema": LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA,
        "readback_mode": "interaction_feedback_detailed",
        "requires_screenshot_for_primary_readback": false,
        "valid": report.valid,
        "failure_reasons": report.failure_reasons,
        "guardrails": {
            "read_only": true,
            "mutation_surface": "none",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "primary_readback_requires_screenshot": false,
            "feedback_changes_world_verdict_allowed": false
        },
        "report": report_value,
        "readback": report.readback,
        "next_agent_action_contract": {
            "preserve_failed_world_verdict": true,
            "treat_human_feedback_as_revision_input": true,
            "require_revision_sources_from_readback": true,
            "forbid_ingestion_or_state_write": true
        }
    })
}

pub fn render_interaction_feedback_validation_envelope(envelope: &Value) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Validation".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &envelope["schema"]);
    push_markdown_kv(&mut lines, "fixture_schema", &envelope["fixture_schema"]);
    push_markdown_kv(
        &mut lines,
        "validation_schema",
        &envelope["validation_schema"],
    );
    push_markdown_kv(&mut lines, "readback_schema", &envelope["readback_schema"]);
    push_markdown_kv(&mut lines, "readback_mode", &envelope["readback_mode"]);
    push_markdown_kv(&mut lines, "valid", &envelope["valid"]);
    push_markdown_kv(&mut lines, "failure_reasons", &envelope["failure_reasons"]);
    push_markdown_kv(
        &mut lines,
        "requires_screenshot_for_primary_readback",
        &envelope["requires_screenshot_for_primary_readback"],
    );

    lines.push(String::new());
    lines.push("## Guardrails".to_string());
    lines.push(String::new());
    for key in [
        "read_only",
        "mutation_surface",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "primary_readback_requires_screenshot",
        "feedback_changes_world_verdict_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &envelope["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Readback".to_string());
    lines.push(String::new());
    for key in [
        "selected_entities",
        "latest_visible_change",
        "latest_verification_verdict",
        "latest_verification_reason",
        "failed_clause_ids",
        "latest_human_decision",
        "latest_feedback_issue",
        "next_revision_patch_id",
        "revision_should_cite",
    ] {
        push_markdown_kv(&mut lines, key, &envelope["readback"][key]);
    }

    lines.push(String::new());
    lines.push("## Next Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "preserve_failed_world_verdict",
        "treat_human_feedback_as_revision_input",
        "require_revision_sources_from_readback",
        "forbid_ingestion_or_state_write",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &envelope["next_agent_action_contract"][key],
        );
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_evidence_packet(fixture: &Value) -> Value {
    let envelope = build_interaction_feedback_validation_envelope(fixture);
    let markdown = render_interaction_feedback_validation_envelope(&envelope);

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA,
        "fixture_id": fixture.get("fixture_id").cloned().unwrap_or(Value::Null),
        "fixture_schema": fixture.get("schema").cloned().unwrap_or(Value::Null),
        "envelope_schema": envelope.get("schema").cloned().unwrap_or(Value::Null),
        "validation_schema": envelope.get("validation_schema").cloned().unwrap_or(Value::Null),
        "readback_schema": envelope.get("readback_schema").cloned().unwrap_or(Value::Null),
        "readback_mode": envelope.get("readback_mode").cloned().unwrap_or(Value::Null),
        "valid": envelope.get("valid").cloned().unwrap_or(Value::Null),
        "failure_reasons": envelope.get("failure_reasons").cloned().unwrap_or(Value::Null),
        "guardrails": envelope.get("guardrails").cloned().unwrap_or(Value::Null),
        "readback": envelope.get("readback").cloned().unwrap_or(Value::Null),
        "markdown": markdown,
        "envelope": envelope,
        "note": "local evidence only: pure fixture render, no MCP call, no store access, no memory write"
    })
}

pub fn build_interaction_feedback_packet_consumption_preflight(input: &Value) -> Value {
    let (input_kind, packet, extraction_failure) = extract_consumption_packet(input);
    let guardrails = consumption_preflight_guardrails();

    let mut gates = Vec::new();
    let explicit_input = packet.is_some();
    gates.push(consumption_gate(
        "C1",
        "explicit_input_only",
        explicit_input,
        if explicit_input {
            "explicit fixture or evidence packet supplied"
        } else {
            "missing explicit fixture or evidence packet"
        },
    ));

    if let Some(packet) = packet {
        let packet_guardrails = &packet["guardrails"];
        let guardrails_preserved = packet_guardrails["read_only"] == true
            && packet_guardrails["writes_state"] == false
            && packet_guardrails["store_access_required"] == false
            && packet_guardrails["mcp_tool_registered"] == false
            && packet_guardrails["feedback_changes_world_verdict_allowed"] == false;
        gates.push(consumption_gate(
            "C2",
            "guardrails_preserved",
            guardrails_preserved,
            "packet guardrails must stay read-only, no-store, no-MCP, no-verdict-laundering",
        ));

        let failed_verdict_preserved =
            packet["readback"]["latest_verification_verdict"] == "not_verified";
        gates.push(consumption_gate(
            "C3",
            "no_verification_laundering",
            failed_verdict_preserved,
            "human feedback must not upgrade latest_verification_verdict",
        ));

        let revision_sources = packet["readback"]["revision_should_cite"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        let cites_failed_verification = revision_sources
            .iter()
            .any(|source| source == "verify_patch_arrival_bath_move_001");
        let cites_feedback = revision_sources
            .iter()
            .any(|source| source == "fb_arrival_crowded_001");
        gates.push(consumption_gate(
            "C4",
            "agent_can_choose_next_revision_source",
            cites_failed_verification && cites_feedback,
            "revision_should_cite must include failed verification and feedback ids",
        ));

        let markdown = packet["markdown"].as_str().unwrap_or("");
        let human_auditable = markdown.contains("effect_walkway_clearance_001")
            && markdown.contains("visual_density_too_high")
            && markdown.contains("verify_patch_arrival_bath_move_001")
            && markdown.contains("fb_arrival_crowded_001");
        gates.push(consumption_gate(
            "C5",
            "human_can_audit_same_result",
            human_auditable,
            "rendered markdown must expose failed clause, feedback issue, and revision sources",
        ));

        let failure_reasons = consumption_failure_reasons(&gates);
        let blockers = consumption_blockers(&failure_reasons);
        let accepted = failure_reasons.is_empty();
        let reason = if accepted {
            "explicit_input_consumption_preflight_passed".to_string()
        } else {
            failure_reasons
                .first()
                .cloned()
                .unwrap_or_else(|| "consumption_preflight_failed".to_string())
        };

        json!({
            "schema": LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA,
            "input_kind": input_kind,
            "source_kind": normalized_consumption_source_kind(input_kind),
            "accepted": accepted,
            "preflight_verdict": if accepted { "accepted" } else { "blocked" },
            "status": if accepted { "accepted" } else { "blocked" },
            "world_verdict": packet["readback"]["latest_verification_verdict"].clone(),
            "world_result_verdict": packet["readback"]["latest_verification_verdict"].clone(),
            "reason": reason,
            "failure_reasons": failure_reasons,
            "blockers": blockers,
            "guardrails": guardrails,
            "input_contract": consumption_input_contract(),
            "acceptance_matrix": gates,
            "packet_schema": packet.get("schema").cloned().unwrap_or(Value::Null),
            "fixture_id": packet.get("fixture_id").cloned().unwrap_or(Value::Null),
            "readback": packet.get("readback").cloned().unwrap_or(Value::Null),
            "packet": packet,
            "implicit_live_runtime_lookup_attempted": false,
            "note": "pure consumption preflight: explicit input only, no MCP call, no store access, no memory write"
        })
    } else {
        gates.push(consumption_gate(
            "C2",
            "guardrails_preserved",
            false,
            "no packet supplied to inspect guardrails",
        ));
        gates.push(consumption_gate(
            "C3",
            "no_verification_laundering",
            false,
            "no packet supplied to inspect verification verdict",
        ));
        gates.push(consumption_gate(
            "C4",
            "agent_can_choose_next_revision_source",
            false,
            "no packet supplied to inspect revision sources",
        ));
        gates.push(consumption_gate(
            "C5",
            "human_can_audit_same_result",
            false,
            "no packet supplied to inspect rendered markdown",
        ));

        let mut failure_reasons = consumption_failure_reasons(&gates);
        if let Some(reason) = extraction_failure {
            failure_reasons.push(reason);
        }
        let blockers = consumption_blockers(&failure_reasons);
        let reason = failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "missing_explicit_fixture_or_packet".to_string());

        json!({
            "schema": LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA,
            "input_kind": input_kind,
            "source_kind": "none",
            "accepted": false,
            "preflight_verdict": "blocked",
            "status": "blocked",
            "world_verdict": "not_verified",
            "world_result_verdict": "not_verified",
            "reason": reason,
            "failure_reasons": failure_reasons,
            "blockers": blockers,
            "guardrails": guardrails,
            "input_contract": consumption_input_contract(),
            "acceptance_matrix": gates,
            "packet_schema": Value::Null,
            "fixture_id": Value::Null,
            "readback": Value::Null,
            "packet": Value::Null,
            "implicit_live_runtime_lookup_attempted": false,
            "note": "pure consumption preflight: explicit input only, no MCP call, no store access, no memory write"
        })
    }
}

pub fn build_interaction_feedback_readback(fixture: &Value) -> Value {
    let selected_entities =
        fixture["interaction_state_after"]["active_view"]["selected_entities"].clone();
    let latest_visible_change = fixture["presentation_page"]["presentations"]
        .as_array()
        .and_then(|items| items.last())
        .and_then(|item| item.get("patch_id"))
        .cloned()
        .unwrap_or(Value::Null);
    let latest_verification = fixture["verification_page"]["verifications"]
        .as_array()
        .and_then(|items| items.last());
    let failed_clause_ids = latest_verification
        .and_then(|item| item.get("failed_clause_ids"))
        .cloned()
        .unwrap_or(Value::Null);
    let latest_verification_verdict = latest_verification
        .and_then(|item| item.get("verdict"))
        .cloned()
        .unwrap_or(Value::Null);
    let latest_verification_reason = latest_verification
        .and_then(|item| item.get("reason"))
        .cloned()
        .unwrap_or(Value::Null);
    let latest_human_decision = event_by_type(fixture, "human.reject")
        .and_then(|event| event["payload"].get("decision"))
        .cloned()
        .unwrap_or(Value::Null);
    let latest_feedback_issue = fixture["feedback"]
        .as_array()
        .and_then(|items| items.last())
        .and_then(|item| item["normalized"].get("issue"))
        .cloned()
        .unwrap_or(Value::Null);
    let revision_event = events(fixture).and_then(|events| {
        events
            .iter()
            .rev()
            .find(|event| event["event_type"] == "ai.patch_proposed")
    });
    let next_revision_patch_id = revision_event
        .and_then(|event| event["refs"].get("patch_id"))
        .cloned()
        .unwrap_or(Value::Null);
    let revision_should_cite = revision_event
        .and_then(|event| event["payload"]["patch"].get("revision_sources"))
        .cloned()
        .unwrap_or(Value::Null);

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA,
        "selected_entities": selected_entities,
        "latest_visible_change": latest_visible_change,
        "latest_verification_verdict": latest_verification_verdict,
        "latest_verification_reason": latest_verification_reason,
        "failed_clause_ids": failed_clause_ids,
        "latest_human_decision": latest_human_decision,
        "latest_feedback_issue": latest_feedback_issue,
        "next_revision_patch_id": next_revision_patch_id,
        "revision_should_cite": revision_should_cite,
        "requires_screenshot_for_primary_readback": false
    })
}

fn validate_event_loop(fixture: &Value, failure_reasons: &mut Vec<String>) {
    let Some(events) = events(fixture) else {
        failure_reasons.push("events_missing_or_invalid".to_string());
        return;
    };

    let event_types: Vec<&str> = events
        .iter()
        .map(|event| event["event_type"].as_str().unwrap_or(""))
        .collect();
    if event_types != EXPECTED_EVENT_TYPES {
        failure_reasons.push("event_sequence_mismatch".to_string());
    }

    let mut positions = BTreeMap::new();
    for (idx, event) in events.iter().enumerate() {
        let Some(event_id) = event["event_id"].as_str().filter(|id| !id.is_empty()) else {
            failure_reasons.push(format!("event_id_missing_at_index:{idx}"));
            continue;
        };
        if positions.insert(event_id, idx).is_some() {
            failure_reasons.push(format!("duplicate_event_id:{event_id}"));
        }
    }

    for (idx, event) in events.iter().enumerate() {
        let Some(cause_event_id) = event["refs"]["cause_event_id"].as_str() else {
            continue;
        };
        match positions.get(cause_event_id) {
            Some(cause_idx) if *cause_idx < idx => {}
            Some(_) => {
                failure_reasons.push(format!("cause_event_not_before_child:{cause_event_id}"))
            }
            None => failure_reasons.push(format!("cause_event_missing:{cause_event_id}")),
        }
    }
}

fn validate_verification_honesty(fixture: &Value, failure_reasons: &mut Vec<String>) {
    let Some(verification) = event_by_id(fixture, "evt_verify_patch_001") else {
        failure_reasons.push("verification_event_missing".to_string());
        return;
    };

    if verification["verification"]["verdict"] != "not_verified" {
        failure_reasons.push("verification_verdict_not_preserved".to_string());
    }
    if verification["verification"]["reason"] != "expected_effect_clause_failed" {
        failure_reasons.push("verification_reason_not_preserved".to_string());
    }
    if verification["verification"]["evidence"]["failed_clause_ids"]
        != json!(["effect_walkway_clearance_001"])
    {
        failure_reasons.push("failed_clause_ids_mismatch".to_string());
    }

    let Some(reject) = event_by_id(fixture, "evt_human_reject_001") else {
        failure_reasons.push("human_reject_event_missing".to_string());
        return;
    };
    if reject["payload"]["decision"] != "reject" {
        failure_reasons.push("human_reject_decision_missing".to_string());
    }
    if reject["payload"]["does_not_change_verification"] != true {
        failure_reasons.push("human_review_may_change_verification".to_string());
    }
    if reject["refs"]["cause_event_id"] != "evt_verify_patch_001" {
        failure_reasons.push("human_reject_not_anchored_to_verification".to_string());
    }
    if fixture["verification_page"]["verifications"][0]["verdict"] != "not_verified" {
        failure_reasons.push("verification_page_laundered_verdict".to_string());
    }
}

fn validate_feedback_and_revision(
    fixture: &Value,
    readback: &Value,
    failure_reasons: &mut Vec<String>,
) {
    let Some(feedback_event) = event_by_id(fixture, "evt_feedback_text_001") else {
        failure_reasons.push("feedback_event_missing".to_string());
        return;
    };
    let Some(feedback_record) = fixture["feedback"]
        .as_array()
        .and_then(|items| items.first())
    else {
        failure_reasons.push("feedback_record_missing".to_string());
        return;
    };

    if feedback_event["payload"]["raw"]["text"] != feedback_record["raw"]["text"] {
        failure_reasons.push("raw_feedback_not_preserved".to_string());
    }
    if feedback_record["verification_relation"]["changes_world_verdict"] != false {
        failure_reasons.push("feedback_changes_world_verdict".to_string());
    }
    if feedback_record["verification_relation"]["related_verification_event_id"]
        != "evt_verify_patch_001"
    {
        failure_reasons.push("feedback_not_anchored_to_verification".to_string());
    }

    let Some(revision_event) = event_by_id(fixture, "evt_ai_patch_proposed_002") else {
        failure_reasons.push("revision_patch_event_missing".to_string());
        return;
    };
    let revision_sources: BTreeSet<&str> = revision_event["payload"]["patch"]["revision_sources"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .collect();
    if !revision_sources.contains("verify_patch_arrival_bath_move_001") {
        failure_reasons.push("revision_missing_failed_verification_source".to_string());
    }
    if !revision_sources.contains("fb_arrival_crowded_001") {
        failure_reasons.push("revision_missing_feedback_source".to_string());
    }

    let expected = fixture
        .get("expected_agent_readback")
        .cloned()
        .unwrap_or(Value::Null);
    if strip_readback_schema(readback) != expected {
        failure_reasons.push("readback_report_mismatch".to_string());
    }
}

fn strip_readback_schema(readback: &Value) -> Value {
    let mut stripped = readback.clone();
    if let Some(map) = stripped.as_object_mut() {
        map.remove("schema");
        map.remove("requires_screenshot_for_primary_readback");
    }
    stripped
}

fn extract_consumption_packet(input: &Value) -> (&'static str, Option<Value>, Option<String>) {
    match input.get("schema").and_then(Value::as_str) {
        Some(LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA) => {
            return ("evidence_packet", Some(input.clone()), None)
        }
        Some(LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA) => {
            return (
                "fixture",
                Some(build_interaction_feedback_evidence_packet(input)),
                None,
            )
        }
        _ => {}
    }

    if let Some(packet) = input.get("packet") {
        if packet.get("schema").and_then(Value::as_str)
            == Some(LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA)
        {
            return ("packet_wrapper", Some(packet.clone()), None);
        }
    }

    if let Some(fixture) = input.get("fixture") {
        if fixture.get("schema").and_then(Value::as_str)
            == Some(LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA)
        {
            return (
                "fixture_wrapper",
                Some(build_interaction_feedback_evidence_packet(fixture)),
                None,
            );
        }
    }

    let failure = match input.get("schema").and_then(Value::as_str) {
        Some(schema) => format!("unsupported_input_schema:{schema}"),
        None => "missing_explicit_fixture_or_packet".to_string(),
    };
    ("missing_or_invalid", None, Some(failure))
}

fn consumption_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "live_runtime_lookup_allowed": false,
        "implicit_live_runtime_lookup_allowed": false,
        "default_profile_exposure_allowed": false,
        "outcome_ingestion_allowed": false,
        "feedback_changes_world_verdict_allowed": false
    })
}

fn consumption_input_contract() -> Value {
    json!({
        "explicit_input_required": true,
        "accepted_inputs": ["packet", "fixture"],
        "implicit_live_runtime_lookup_allowed": false
    })
}

fn normalized_consumption_source_kind(input_kind: &str) -> &'static str {
    match input_kind {
        "evidence_packet" | "packet_wrapper" => "packet",
        "fixture" | "fixture_wrapper" => "fixture",
        _ => "none",
    }
}

fn consumption_gate(gate: &str, name: &str, passed: bool, evidence: &str) -> Value {
    json!({
        "gate": gate,
        "id": gate,
        "name": name,
        "passed": passed,
        "evidence": evidence
    })
}

fn consumption_failure_reasons(gates: &[Value]) -> Vec<String> {
    gates
        .iter()
        .filter(|gate| gate["passed"] != true)
        .map(|gate| {
            format!(
                "{}:{}",
                gate["gate"].as_str().unwrap_or("unknown"),
                gate["name"].as_str().unwrap_or("unknown")
            )
        })
        .collect()
}

fn consumption_blockers(failure_reasons: &[String]) -> Vec<String> {
    let mut blockers = failure_reasons.to_vec();
    for reason in failure_reasons {
        if reason == "missing_explicit_fixture_or_packet" {
            push_unique_blocker(&mut blockers, "explicit_packet_or_fixture_required");
        }
        if reason.starts_with("C1:") {
            push_unique_blocker(&mut blockers, "explicit_packet_or_fixture_required");
        }
        if reason.starts_with("C2:") {
            push_unique_blocker(&mut blockers, "guardrails_not_preserved");
        }
        if reason.starts_with("C3:") {
            push_unique_blocker(&mut blockers, "verification_laundering_guard_failed");
        }
        if reason.starts_with("C4:") {
            push_unique_blocker(&mut blockers, "revision_sources_not_recoverable");
        }
        if reason.starts_with("C5:") {
            push_unique_blocker(&mut blockers, "human_audit_fields_not_visible");
        }
    }
    blockers
}

fn push_unique_blocker(blockers: &mut Vec<String>, blocker: &str) {
    if !blockers.iter().any(|existing| existing == blocker) {
        blockers.push(blocker.to_string());
    }
}

fn events(fixture: &Value) -> Option<&Vec<Value>> {
    fixture["events"].as_array()
}

fn event_by_type<'a>(fixture: &'a Value, event_type: &str) -> Option<&'a Value> {
    events(fixture)?
        .iter()
        .find(|event| event["event_type"] == event_type)
}

fn event_by_id<'a>(fixture: &'a Value, event_id: &str) -> Option<&'a Value> {
    events(fixture)?
        .iter()
        .find(|event| event["event_id"] == event_id)
}

fn push_markdown_kv(lines: &mut Vec<String>, key: &str, value: &Value) {
    lines.push(format!("- {key}: `{}`", markdown_value(value)));
}

fn markdown_value(value: &Value) -> String {
    match value {
        Value::Array(items) if items.is_empty() => "none".to_string(),
        Value::Array(items) => items
            .iter()
            .map(markdown_value)
            .collect::<Vec<_>>()
            .join(", "),
        Value::Bool(value) => value.to_string(),
        Value::Null => "null".to_string(),
        Value::Number(value) => value.to_string(),
        Value::String(value) => value.clone(),
        Value::Object(_) => value.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn malformed_fixture_reports_structured_failures_without_panicking() {
        let report = validate_interaction_feedback_fixture(&json!({
            "schema": "wrong",
            "requires_screenshot_for_primary_readback": true,
            "events": []
        }));

        assert!(!report.valid);
        assert!(report
            .failure_reasons
            .contains(&"schema_mismatch".to_string()));
        assert!(report
            .failure_reasons
            .contains(&"primary_readback_requires_screenshot".to_string()));
        assert!(report
            .failure_reasons
            .contains(&"event_sequence_mismatch".to_string()));
        assert_eq!(report.to_value()["writes_state"], false);
        assert_eq!(report.to_value()["store_access_required"], false);
        assert_eq!(report.to_value()["mcp_tool_registered"], false);
    }
}
