use std::collections::{BTreeMap, BTreeSet};

use serde_json::{Value, json};

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
pub const LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_consumption_report.v0";
pub const LSWR_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_next_revision_plan.v0";
pub const LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_semantic_patch_draft.v0";
pub const LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_argument_context.v0";
pub const LSWR_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_patch_execution_preflight.v0";
pub const LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_patch_apply_request.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_design_preflight.v0";
pub const LSWR_INTERACTION_FEEDBACK_LIVE_RUNTIME_LOOKUP_DESIGN_PREFLIGHT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_live_runtime_lookup_design_preflight.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_live_lookup_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.live_lookup_snapshot.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA:
    &str = "agent_bridge.lswr.interaction_feedback_runtime_executor_operator_submission_token_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.operator_submission_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_patch_application_gate_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.patch_application_gate_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA:
    &str = "agent_bridge.lswr.interaction_feedback_runtime_executor_patch_executor_invocation_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.patch_executor_invocation_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA:
    &str = "agent_bridge.lswr.interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.patch_runtime_application_evidence.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_post_apply_verification_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_EVIDENCE_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.post_apply_verification_evidence.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_outcome_ingestion_review_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.outcome_ingestion_review_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_ingestion_gate_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_ingestion_execution_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_write_implementation_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_write_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_record_write_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_record_write_execution_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_record_persistence_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_record_store_write_execution_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_record_write_evidence.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.durable_outcome_record_write_evidence_review_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_world_verdict_rewrite_gate.v0";
pub const LSWR_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.world_verdict_rewrite_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_GATE_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_gate.v0";
pub const LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight.v0";
pub const LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_execution_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit.v0";
pub const LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_execution_commit_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_GATE_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate.v0";
pub const LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_apply_decision.v0";
pub const LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_SCHEMA:
    &str =
    "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_writer.v0";
pub const LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_DECISION_SCHEMA: &str =
    "agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_writer_decision.v0";
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

pub fn build_interaction_feedback_consumption_report(input: &Value) -> Value {
    let preflight = if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA)
    {
        input.clone()
    } else {
        build_interaction_feedback_packet_consumption_preflight(input)
    };
    let markdown = render_interaction_feedback_consumption_preflight_report(&preflight);

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_SCHEMA,
        "preflight_schema": preflight.get("schema").cloned().unwrap_or(Value::Null),
        "accepted": preflight.get("accepted").cloned().unwrap_or(Value::Bool(false)),
        "preflight_verdict": preflight.get("preflight_verdict").cloned().unwrap_or(Value::Null),
        "status": preflight.get("status").cloned().unwrap_or(Value::Null),
        "input_kind": preflight.get("input_kind").cloned().unwrap_or(Value::Null),
        "source_kind": preflight.get("source_kind").cloned().unwrap_or(Value::Null),
        "world_verdict": preflight.get("world_verdict").cloned().unwrap_or(Value::Null),
        "world_result_verdict": preflight.get("world_result_verdict").cloned().unwrap_or(Value::Null),
        "reason": preflight.get("reason").cloned().unwrap_or(Value::Null),
        "failure_reasons": preflight.get("failure_reasons").cloned().unwrap_or(Value::Null),
        "blockers": preflight.get("blockers").cloned().unwrap_or(Value::Null),
        "guardrails": preflight.get("guardrails").cloned().unwrap_or(Value::Null),
        "input_contract": preflight.get("input_contract").cloned().unwrap_or(Value::Null),
        "acceptance_matrix": preflight.get("acceptance_matrix").cloned().unwrap_or(Value::Null),
        "packet_schema": preflight.get("packet_schema").cloned().unwrap_or(Value::Null),
        "fixture_id": preflight.get("fixture_id").cloned().unwrap_or(Value::Null),
        "readback": preflight.get("readback").cloned().unwrap_or(Value::Null),
        "markdown": markdown,
        "markdown_source": "preflight",
        "json_canonical": true,
        "preflight": preflight,
        "implicit_live_runtime_lookup_attempted": preflight
            .get("implicit_live_runtime_lookup_attempted")
            .cloned()
            .unwrap_or(Value::Bool(false)),
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure consumption report: renders canonical preflight only, no MCP call, no store access, no memory write"
    })
}

pub fn render_interaction_feedback_consumption_preflight_report(preflight: &Value) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Consumption Report".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "preflight_verdict",
        &preflight["preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "accepted", &preflight["accepted"]);
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "input_kind", &preflight["input_kind"]);
    push_markdown_kv(&mut lines, "source_kind", &preflight["source_kind"]);
    push_markdown_kv(&mut lines, "world_verdict", &preflight["world_verdict"]);
    push_markdown_kv(
        &mut lines,
        "world_result_verdict",
        &preflight["world_result_verdict"],
    );
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);
    push_markdown_kv(&mut lines, "blockers", &preflight["blockers"]);
    push_markdown_kv(
        &mut lines,
        "implicit_live_runtime_lookup_attempted",
        &preflight["implicit_live_runtime_lookup_attempted"],
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
        "queries_live_runtime",
        "live_runtime_lookup_allowed",
        "implicit_live_runtime_lookup_allowed",
        "default_profile_exposure_allowed",
        "outcome_ingestion_allowed",
        "feedback_changes_world_verdict_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Acceptance Matrix".to_string());
    lines.push(String::new());
    if let Some(gates) = preflight["acceptance_matrix"].as_array() {
        for gate in gates {
            let gate_id = gate["gate"].as_str().unwrap_or("unknown");
            let name = gate["name"].as_str().unwrap_or("unknown");
            let status = if gate["passed"] == true {
                "passed"
            } else {
                "failed"
            };
            let evidence = markdown_value(&gate["evidence"]);
            lines.push(format!("- {gate_id} {name}: `{status}` - {evidence}"));
        }
    } else {
        lines.push("- none".to_string());
    }

    lines.push(String::new());
    lines.push("## Readback".to_string());
    lines.push(String::new());
    for key in [
        "latest_verification_verdict",
        "latest_verification_reason",
        "failed_clause_ids",
        "latest_human_decision",
        "latest_feedback_issue",
        "next_revision_patch_id",
        "revision_should_cite",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["readback"][key]);
    }

    lines.push(String::new());
    lines.push("## Canonical Source".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "packet_schema", &preflight["packet_schema"]);
    push_markdown_kv(&mut lines, "fixture_id", &preflight["fixture_id"]);
    lines.push("- json_remains_canonical: `true`".to_string());
    lines.push("- markdown_writes_state: `false`".to_string());
    lines.push(
        "- note: `Markdown renders the preflight object; it does not replace it.`".to_string(),
    );

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_next_revision_plan(input: &Value) -> Value {
    let report = if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_SCHEMA)
    {
        input.clone()
    } else {
        build_interaction_feedback_consumption_report(input)
    };
    let readback = report.get("readback").cloned().unwrap_or(Value::Null);
    let source_accepted = report.get("accepted").and_then(Value::as_bool) == Some(true)
        && report.get("preflight_verdict").and_then(Value::as_str) == Some("accepted");

    let mut failure_reasons = Vec::new();
    if !source_accepted {
        failure_reasons.push("source_report_not_accepted".to_string());
    }
    if readback["latest_verification_verdict"] != "not_verified" {
        failure_reasons.push("world_verdict_must_remain_not_verified".to_string());
    }
    if readback["failed_clause_ids"]
        .as_array()
        .map(Vec::is_empty)
        .unwrap_or(true)
    {
        failure_reasons.push("failed_clause_ids_missing".to_string());
    }
    if readback["revision_should_cite"]
        .as_array()
        .map(Vec::is_empty)
        .unwrap_or(true)
    {
        failure_reasons.push("revision_sources_missing".to_string());
    }
    if readback["next_revision_patch_id"]
        .as_str()
        .filter(|value| !value.is_empty())
        .is_none()
    {
        failure_reasons.push("next_revision_patch_id_missing".to_string());
    }
    if readback["latest_feedback_issue"]
        .as_str()
        .filter(|value| !value.is_empty())
        .is_none()
    {
        failure_reasons.push("feedback_issue_missing".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "explicit_feedback_report_revision_plan_ready".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "next_revision_plan_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_SCHEMA,
        "source_schema": report.get("schema").cloned().unwrap_or(Value::Null),
        "source_fixture_id": report.get("fixture_id").cloned().unwrap_or(Value::Null),
        "source_accepted": source_accepted,
        "source_status": report.get("status").cloned().unwrap_or(Value::Null),
        "source_world_verdict": report.get("world_verdict").cloned().unwrap_or(Value::Null),
        "source_world_result_verdict": report.get("world_result_verdict").cloned().unwrap_or(Value::Null),
        "plan_verdict": if ready { "ready_for_revision" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": failure_reasons,
        "guardrails": next_revision_plan_guardrails(),
        "input_contract": {
            "accepted_inputs": ["consumption_report", "preflight", "packet", "fixture"],
            "explicit_input_required": true,
            "implicit_live_runtime_lookup_allowed": false
        },
        "next_revision": {
            "patch_id": readback.get("next_revision_patch_id").cloned().unwrap_or(Value::Null),
            "selected_entities": readback.get("selected_entities").cloned().unwrap_or(Value::Null),
            "failed_clause_ids": readback.get("failed_clause_ids").cloned().unwrap_or(Value::Null),
            "human_decision": readback.get("latest_human_decision").cloned().unwrap_or(Value::Null),
            "feedback_issue": readback.get("latest_feedback_issue").cloned().unwrap_or(Value::Null),
            "must_cite": readback.get("revision_should_cite").cloned().unwrap_or(Value::Null),
            "preserved_world_verdict": readback.get("latest_verification_verdict").cloned().unwrap_or(Value::Null),
            "recommended_step": if ready {
                "draft_semantic_patch_revision"
            } else {
                "repair_or_supply_accepted_feedback_report"
            },
            "allowed_to_apply": false,
            "allowed_to_ingest": false
        },
        "agent_action_contract": {
            "mode": "plan_next_patch_only",
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_query_live_runtime": true,
            "do_not_rewrite_world_verdict": true,
            "use_revision_sources_as_required_citations": true,
            "treat_human_feedback_as_revision_input": true
        },
        "readback": readback,
        "report": report,
        "implicit_live_runtime_lookup_attempted": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure next-revision plan: derives an AI-readable revision target from an explicit consumption report without applying patches or writing state"
    })
}

pub fn render_interaction_feedback_next_revision_plan(plan: &Value) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Next Revision Plan".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &plan["schema"]);
    push_markdown_kv(&mut lines, "plan_verdict", &plan["plan_verdict"]);
    push_markdown_kv(&mut lines, "status", &plan["status"]);
    push_markdown_kv(&mut lines, "reason", &plan["reason"]);
    push_markdown_kv(&mut lines, "source_schema", &plan["source_schema"]);
    push_markdown_kv(&mut lines, "source_accepted", &plan["source_accepted"]);
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &plan["source_world_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_result_verdict",
        &plan["source_world_result_verdict"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &plan["failure_reasons"]);
    push_markdown_kv(
        &mut lines,
        "implicit_live_runtime_lookup_attempted",
        &plan["implicit_live_runtime_lookup_attempted"],
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
        "queries_live_runtime",
        "outcome_ingestion_allowed",
        "feedback_changes_world_verdict_allowed",
        "applies_patch",
    ] {
        push_markdown_kv(&mut lines, key, &plan["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Next Revision".to_string());
    lines.push(String::new());
    for key in [
        "patch_id",
        "selected_entities",
        "failed_clause_ids",
        "human_decision",
        "feedback_issue",
        "must_cite",
        "preserved_world_verdict",
        "recommended_step",
        "allowed_to_apply",
        "allowed_to_ingest",
    ] {
        push_markdown_kv(&mut lines, key, &plan["next_revision"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_query_live_runtime",
        "do_not_rewrite_world_verdict",
        "use_revision_sources_as_required_citations",
        "treat_human_feedback_as_revision_input",
    ] {
        push_markdown_kv(&mut lines, key, &plan["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_semantic_patch_draft(input: &Value) -> Value {
    let plan = if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_SCHEMA)
    {
        input.clone()
    } else {
        build_interaction_feedback_next_revision_plan(input)
    };
    let next_revision = plan.get("next_revision").cloned().unwrap_or(Value::Null);
    let source_plan_ready =
        plan.get("plan_verdict").and_then(Value::as_str) == Some("ready_for_revision");

    let mut failure_reasons = Vec::new();
    if !source_plan_ready {
        failure_reasons.push("source_plan_not_ready".to_string());
    }
    if plan["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if next_revision["patch_id"]
        .as_str()
        .filter(|value| !value.is_empty())
        .is_none()
    {
        failure_reasons.push("patch_id_missing".to_string());
    }
    if next_revision["selected_entities"]
        .as_array()
        .map(Vec::is_empty)
        .unwrap_or(true)
    {
        failure_reasons.push("target_entities_missing".to_string());
    }
    if next_revision["must_cite"]
        .as_array()
        .map(Vec::is_empty)
        .unwrap_or(true)
    {
        failure_reasons.push("revision_sources_missing".to_string());
    }
    if next_revision["feedback_issue"]
        .as_str()
        .filter(|value| !value.is_empty())
        .is_none()
    {
        failure_reasons.push("feedback_issue_missing".to_string());
    }

    let drafted = failure_reasons.is_empty();
    let reason = if drafted {
        "accepted_plan_semantic_patch_draft_ready".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "semantic_patch_draft_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA,
        "source_schema": plan.get("schema").cloned().unwrap_or(Value::Null),
        "source_plan_verdict": plan.get("plan_verdict").cloned().unwrap_or(Value::Null),
        "source_world_verdict": plan.get("source_world_verdict").cloned().unwrap_or(Value::Null),
        "draft_verdict": if drafted { "drafted" } else { "blocked" },
        "status": if drafted { "drafted" } else { "blocked" },
        "reason": reason,
        "failure_reasons": failure_reasons,
        "guardrails": semantic_patch_draft_guardrails(),
        "input_contract": {
            "accepted_inputs": ["next_revision_plan", "consumption_report", "preflight", "packet", "fixture"],
            "explicit_input_required": true,
            "implicit_live_runtime_lookup_allowed": false
        },
        "semantic_patch_draft": {
            "patch_id": next_revision.get("patch_id").cloned().unwrap_or(Value::Null),
            "op": "semantic_revision",
            "operation_hint": semantic_patch_operation_hint(&next_revision),
            "target_entities": next_revision.get("selected_entities").cloned().unwrap_or(Value::Null),
            "reason": semantic_patch_reason(&next_revision),
            "revision_sources": next_revision.get("must_cite").cloned().unwrap_or(Value::Null),
            "constraints": {
                "failed_clause_ids": next_revision.get("failed_clause_ids").cloned().unwrap_or(Value::Null),
                "feedback_issue": next_revision.get("feedback_issue").cloned().unwrap_or(Value::Null),
                "human_decision": next_revision.get("human_decision").cloned().unwrap_or(Value::Null),
                "preserve_world_verdict": next_revision.get("preserved_world_verdict").cloned().unwrap_or(Value::Null),
                "expected_effect_requirements": semantic_patch_expected_effect_requirements(&next_revision)
            },
            "unresolved_arguments": ["patch.args.cell"],
            "requires_live_world_state_for_arguments": true,
            "live_world_state_queried": false,
            "apply_allowed": false,
            "ingest_allowed": false
        },
        "agent_action_contract": {
            "mode": "draft_semantic_patch_only",
            "resolve_arguments_before_apply": true,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_query_live_runtime": true,
            "do_not_rewrite_world_verdict": true,
            "cite_revision_sources": true
        },
        "source_plan": plan,
        "implicit_live_runtime_lookup_attempted": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure semantic patch draft: converts an accepted next-revision plan into a draft-only patch target without resolving live-world arguments or applying the patch"
    })
}

pub fn render_interaction_feedback_semantic_patch_draft(draft: &Value) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Semantic Patch Draft".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &draft["schema"]);
    push_markdown_kv(&mut lines, "draft_verdict", &draft["draft_verdict"]);
    push_markdown_kv(&mut lines, "status", &draft["status"]);
    push_markdown_kv(&mut lines, "reason", &draft["reason"]);
    push_markdown_kv(&mut lines, "source_schema", &draft["source_schema"]);
    push_markdown_kv(
        &mut lines,
        "source_plan_verdict",
        &draft["source_plan_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &draft["source_world_verdict"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &draft["failure_reasons"]);
    push_markdown_kv(
        &mut lines,
        "implicit_live_runtime_lookup_attempted",
        &draft["implicit_live_runtime_lookup_attempted"],
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
        "queries_live_runtime",
        "applies_patch",
        "outcome_ingestion_allowed",
        "feedback_changes_world_verdict_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &draft["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Semantic Patch Draft".to_string());
    lines.push(String::new());
    for key in [
        "patch_id",
        "op",
        "operation_hint",
        "target_entities",
        "reason",
        "revision_sources",
        "unresolved_arguments",
        "requires_live_world_state_for_arguments",
        "live_world_state_queried",
        "apply_allowed",
        "ingest_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &draft["semantic_patch_draft"][key]);
    }
    push_markdown_kv(
        &mut lines,
        "failed_clause_ids",
        &draft["semantic_patch_draft"]["constraints"]["failed_clause_ids"],
    );
    push_markdown_kv(
        &mut lines,
        "feedback_issue",
        &draft["semantic_patch_draft"]["constraints"]["feedback_issue"],
    );
    push_markdown_kv(
        &mut lines,
        "preserve_world_verdict",
        &draft["semantic_patch_draft"]["constraints"]["preserve_world_verdict"],
    );

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "resolve_arguments_before_apply",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_query_live_runtime",
        "do_not_rewrite_world_verdict",
        "cite_revision_sources",
    ] {
        push_markdown_kv(&mut lines, key, &draft["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_patch_execution_preflight(input: &Value) -> Value {
    let (input_kind, draft, argument_context) = extract_execution_preflight_input(input);
    let source_drafted = draft.get("draft_verdict").and_then(Value::as_str) == Some("drafted");
    let context_status = validate_argument_context(argument_context.as_ref());
    let selected_argument = context_status
        .get("selected_argument")
        .cloned()
        .unwrap_or(Value::Null);

    let mut failure_reasons = Vec::new();
    if !source_drafted {
        failure_reasons.push("source_draft_not_drafted".to_string());
    }
    if draft["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if context_status["accepted"] != true {
        failure_reasons.push(
            context_status["reason"]
                .as_str()
                .unwrap_or("argument_context_not_accepted")
                .to_string(),
        );
    }
    if selected_argument.is_null() {
        failure_reasons.push("patch_args_cell_unresolved".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "explicit_argument_context_execution_preflight_ready".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "execution_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": draft.get("schema").cloned().unwrap_or(Value::Null),
        "source_draft_verdict": draft.get("draft_verdict").cloned().unwrap_or(Value::Null),
        "source_world_verdict": draft.get("source_world_verdict").cloned().unwrap_or(Value::Null),
        "preflight_verdict": if ready { "ready_for_execution_request" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": execution_preflight_guardrails(),
        "input_contract": {
            "accepted_inputs": ["semantic_patch_draft", "wrapper_with_draft_and_argument_context", "fixture"],
            "explicit_argument_context_required": true,
            "implicit_live_runtime_lookup_allowed": false
        },
        "argument_context": argument_context.unwrap_or(Value::Null),
        "argument_context_status": context_status,
        "resolved_patch": {
            "patch_id": draft["semantic_patch_draft"].get("patch_id").cloned().unwrap_or(Value::Null),
            "op": draft["semantic_patch_draft"].get("op").cloned().unwrap_or(Value::Null),
            "operation_hint": draft["semantic_patch_draft"].get("operation_hint").cloned().unwrap_or(Value::Null),
            "target_entities": draft["semantic_patch_draft"].get("target_entities").cloned().unwrap_or(Value::Null),
            "args": if ready {
                json!({"cell": selected_argument.get("value").cloned().unwrap_or(Value::Null)})
            } else {
                Value::Null
            },
            "resolved_arguments": if ready {
                json!({"patch.args.cell": selected_argument.get("value").cloned().unwrap_or(Value::Null)})
            } else {
                Value::Null
            },
            "required_citations": draft["semantic_patch_draft"].get("revision_sources").cloned().unwrap_or(Value::Null),
            "expected_effect_requirements": draft["semantic_patch_draft"]["constraints"].get("expected_effect_requirements").cloned().unwrap_or(Value::Null),
            "ready_for_execution_request": ready,
            "execution_performed": false,
            "apply_allowed_by_this_tool": false,
            "ingest_allowed_by_this_tool": false
        },
        "agent_action_contract": {
            "mode": "execution_gate_preflight_only",
            "may_request_separate_apply_after_preflight": ready,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_query_live_runtime": true,
            "do_not_rewrite_world_verdict": true,
            "preserve_required_citations": true
        },
        "source_draft": draft,
        "implicit_live_runtime_lookup_attempted": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure execution-gate preflight: resolves draft arguments only from explicit argument context and never applies the patch"
    })
}

pub fn render_interaction_feedback_patch_execution_preflight(preflight: &Value) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Patch Execution Preflight".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "preflight_verdict",
        &preflight["preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_draft_verdict",
        &preflight["source_draft_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &preflight["source_world_verdict"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);
    push_markdown_kv(
        &mut lines,
        "implicit_live_runtime_lookup_attempted",
        &preflight["implicit_live_runtime_lookup_attempted"],
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
        "queries_live_runtime",
        "applies_patch",
        "outcome_ingestion_allowed",
        "feedback_changes_world_verdict_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Argument Context".to_string());
    lines.push(String::new());
    for key in [
        "accepted",
        "reason",
        "context_schema",
        "live_runtime_queried_by_preflight",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["argument_context_status"][key]);
    }

    lines.push(String::new());
    lines.push("## Resolved Patch".to_string());
    lines.push(String::new());
    for key in [
        "patch_id",
        "op",
        "operation_hint",
        "target_entities",
        "args",
        "resolved_arguments",
        "required_citations",
        "ready_for_execution_request",
        "execution_performed",
        "apply_allowed_by_this_tool",
        "ingest_allowed_by_this_tool",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["resolved_patch"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_request_separate_apply_after_preflight",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_query_live_runtime",
        "do_not_rewrite_world_verdict",
        "preserve_required_citations",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_patch_apply_request(input: &Value) -> Value {
    let (input_kind, preflight) = extract_apply_request_input(input);
    let schema_ok = preflight.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_SCHEMA);
    let resolved_patch = &preflight["resolved_patch"];
    let guardrails = &preflight["guardrails"];

    let mut failure_reasons = Vec::new();
    if !schema_ok {
        failure_reasons.push("patch_execution_preflight_required".to_string());
    }
    if schema_ok && preflight["preflight_verdict"] != "ready_for_execution_request" {
        failure_reasons.push("source_preflight_not_ready".to_string());
    }
    if schema_ok && preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if schema_ok && resolved_patch["ready_for_execution_request"] != true {
        failure_reasons.push("resolved_patch_not_ready".to_string());
    }
    if schema_ok && resolved_patch["args"].is_null() {
        failure_reasons.push("resolved_patch_args_required".to_string());
    }
    if schema_ok
        && resolved_patch["required_citations"]
            .as_array()
            .map(Vec::is_empty)
            .unwrap_or(true)
    {
        failure_reasons.push("required_citations_missing".to_string());
    }
    if schema_ok && resolved_patch["execution_performed"] != false {
        failure_reasons.push("source_preflight_must_not_execute_patch".to_string());
    }
    if schema_ok && resolved_patch["apply_allowed_by_this_tool"] != false {
        failure_reasons.push("source_preflight_apply_authority_must_remain_false".to_string());
    }
    if schema_ok
        && (guardrails["read_only"] != true
            || guardrails["writes_state"] != false
            || guardrails["queries_live_runtime"] != false
            || guardrails["applies_patch"] != false)
    {
        failure_reasons.push("source_preflight_guardrails_not_read_only".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "external_apply_request_ready".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "apply_request_blocked".to_string())
    };
    let request_id = if ready {
        apply_request_id_for_patch(&resolved_patch["patch_id"])
    } else {
        Value::Null
    };
    let patch = if ready {
        json!({
            "patch_id": resolved_patch.get("patch_id").cloned().unwrap_or(Value::Null),
            "op": resolved_patch.get("op").cloned().unwrap_or(Value::Null),
            "operation_hint": resolved_patch.get("operation_hint").cloned().unwrap_or(Value::Null),
            "target_entities": resolved_patch.get("target_entities").cloned().unwrap_or(Value::Null),
            "args": resolved_patch.get("args").cloned().unwrap_or(Value::Null),
            "required_citations": resolved_patch.get("required_citations").cloned().unwrap_or(Value::Null),
            "expected_effect_requirements": resolved_patch
                .get("expected_effect_requirements")
                .cloned()
                .unwrap_or(Value::Null)
        })
    } else {
        Value::Null
    };
    let target_runtime = if ready {
        json!({
            "runtime_family": "lswr",
            "world_id": preflight["argument_context"].get("world_id").cloned().unwrap_or(Value::Null),
            "branch_id": preflight["argument_context"].get("branch_id").cloned().unwrap_or(Value::Null),
            "executor": "separate_lswr_patch_executor"
        })
    } else {
        Value::Null
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA,
        "input_kind": input_kind,
        "source_schema": preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_preflight_verdict": preflight.get("preflight_verdict").cloned().unwrap_or(Value::Null),
        "source_world_verdict": preflight.get("source_world_verdict").cloned().unwrap_or(Value::Null),
        "apply_request_verdict": if ready { "ready_for_external_executor" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": apply_request_guardrails(),
        "input_contract": {
            "accepted_inputs": ["patch_execution_preflight", "wrapper_with_preflight"],
            "requires_ready_preflight": true,
            "normalizes_draft_or_fixture": false,
            "external_executor_required": true
        },
        "apply_request": {
            "request_id": request_id,
            "target_runtime": target_runtime,
            "patch": patch,
            "preconditions": {
                "source_world_verdict_must_remain": "not_verified",
                "verify_required_citations_before_apply": true,
                "external_executor_must_verify_postcondition": true,
                "do_not_rewrite_feedback_verdict": true
            },
            "ready_for_external_submission": ready,
            "requires_operator_gate": true,
            "requires_external_executor": true,
            "apply_performed": false,
            "submitted_by_this_tool": false,
            "outcome_ingestion_allowed_by_this_tool": false
        },
        "agent_action_contract": {
            "mode": "apply_request_boundary_only",
            "may_submit_to_separate_executor_after_operator_gate": ready,
            "do_not_apply_patch": true,
            "do_not_submit_patch_from_this_tool": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_query_live_runtime": true,
            "do_not_rewrite_world_verdict": true,
            "external_executor_required": true,
            "preserve_required_citations": true,
            "require_post_apply_verification": true
        },
        "source_preflight": if schema_ok { preflight } else { Value::Null },
        "implicit_live_runtime_lookup_attempted": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure apply-request boundary: emits an external executor request envelope but never submits or applies the patch"
    })
}

pub fn render_interaction_feedback_patch_apply_request(request: &Value) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Patch Apply Request Boundary".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &request["schema"]);
    push_markdown_kv(
        &mut lines,
        "apply_request_verdict",
        &request["apply_request_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &request["status"]);
    push_markdown_kv(&mut lines, "reason", &request["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_preflight_verdict",
        &request["source_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &request["source_world_verdict"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &request["failure_reasons"]);
    push_markdown_kv(
        &mut lines,
        "implicit_live_runtime_lookup_attempted",
        &request["implicit_live_runtime_lookup_attempted"],
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
        "queries_live_runtime",
        "submits_apply_request",
        "applies_patch",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &request["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Apply Request".to_string());
    lines.push(String::new());
    for key in [
        "request_id",
        "target_runtime",
        "patch",
        "ready_for_external_submission",
        "requires_operator_gate",
        "requires_external_executor",
        "apply_performed",
        "submitted_by_this_tool",
        "outcome_ingestion_allowed_by_this_tool",
    ] {
        push_markdown_kv(&mut lines, key, &request["apply_request"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_submit_to_separate_executor_after_operator_gate",
        "do_not_apply_patch",
        "do_not_submit_patch_from_this_tool",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_query_live_runtime",
        "do_not_rewrite_world_verdict",
        "external_executor_required",
        "require_post_apply_verification",
    ] {
        push_markdown_kv(&mut lines, key, &request["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_design_preflight(input: &Value) -> Value {
    let (input_kind, apply_request_packet) = extract_runtime_executor_design_preflight_input(input);
    let schema_ok = apply_request_packet.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA);
    let apply_request = &apply_request_packet["apply_request"];
    let guardrails = &apply_request_packet["guardrails"];
    let contract = &apply_request_packet["agent_action_contract"];

    let mut failure_reasons = Vec::new();
    if !schema_ok {
        failure_reasons.push("patch_apply_request_required".to_string());
    }
    if schema_ok && apply_request_packet["apply_request_verdict"] != "ready_for_external_executor" {
        failure_reasons.push("source_apply_request_not_ready".to_string());
    }
    if schema_ok && apply_request_packet["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if schema_ok && apply_request["ready_for_external_submission"] != true {
        failure_reasons.push("external_submission_readiness_missing".to_string());
    }
    if schema_ok && apply_request["requires_operator_gate"] != true {
        failure_reasons.push("operator_gate_required".to_string());
    }
    if schema_ok && apply_request["requires_external_executor"] != true {
        failure_reasons.push("external_executor_required".to_string());
    }
    if schema_ok && apply_request["apply_performed"] != false {
        failure_reasons.push("source_apply_request_must_not_apply_patch".to_string());
    }
    if schema_ok && apply_request["submitted_by_this_tool"] != false {
        failure_reasons.push("source_apply_request_must_not_be_submitted".to_string());
    }
    if schema_ok && apply_request["outcome_ingestion_allowed_by_this_tool"] != false {
        failure_reasons.push("source_apply_request_must_not_ingest_outcome".to_string());
    }
    if schema_ok && apply_request["patch"].is_null() {
        failure_reasons.push("patch_payload_required".to_string());
    }
    if schema_ok && apply_request["patch"]["args"].is_null() {
        failure_reasons.push("patch_args_required".to_string());
    }
    if schema_ok
        && apply_request["patch"]["required_citations"]
            .as_array()
            .map(Vec::is_empty)
            .unwrap_or(true)
    {
        failure_reasons.push("required_citations_missing".to_string());
    }
    if schema_ok
        && (guardrails["read_only"] != true
            || guardrails["writes_state"] != false
            || guardrails["queries_live_runtime"] != false
            || guardrails["submits_apply_request"] != false
            || guardrails["applies_patch"] != false)
    {
        failure_reasons.push("source_apply_request_guardrails_not_read_only".to_string());
    }
    if schema_ok
        && (contract["do_not_apply_patch"] != true
            || contract["do_not_submit_patch_from_this_tool"] != true
            || contract["do_not_query_live_runtime"] != true
            || contract["do_not_ingest_outcome"] != true
            || contract["external_executor_required"] != true)
    {
        failure_reasons.push("source_apply_request_contract_not_protective".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "runtime_executor_design_preflight_ready".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "runtime_executor_design_preflight_blocked".to_string())
    };
    let design_request_id = if ready {
        executor_design_request_id_for_apply_request(&apply_request["request_id"])
    } else {
        Value::Null
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": apply_request_packet.get("schema").cloned().unwrap_or(Value::Null),
        "source_apply_request_verdict": apply_request_packet
            .get("apply_request_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": apply_request_packet
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "design_preflight_verdict": if ready { "ready_for_runtime_executor_design" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_design_preflight_guardrails(),
        "input_contract": {
            "accepted_inputs": ["patch_apply_request", "wrapper_with_apply_request"],
            "requires_ready_apply_request": true,
            "normalizes_preflight_or_fixture": false,
            "runtime_executor_design_only": true
        },
        "executor_design_request": {
            "design_request_id": design_request_id,
            "source_apply_request_id": if ready {
                apply_request.get("request_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "target_runtime": if ready {
                apply_request.get("target_runtime").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "patch": if ready {
                apply_request.get("patch").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "required_design_gates": [
                "live_runtime_lookup_gate",
                "operator_submission_gate",
                "patch_application_gate",
                "post_apply_verification_gate",
                "outcome_ingestion_gate"
            ],
            "ready_for_design_review": ready,
            "ready_for_live_runtime_lookup": false,
            "ready_for_submission": false,
            "ready_for_patch_application": false,
            "execution_performed": false,
            "outcome_ingestion_allowed_by_this_tool": false,
            "requires_separate_runtime_executor_approval": true
        },
        "agent_action_contract": {
            "mode": "runtime_executor_design_preflight_only",
            "may_design_runtime_executor_after_review": ready,
            "do_not_query_live_runtime": true,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "require_operator_gate_before_submission": true,
            "require_post_apply_verification_design": true,
            "require_separate_outcome_ingestion_review": true
        },
        "source_apply_request": if schema_ok { apply_request_packet } else { Value::Null },
        "implicit_live_runtime_lookup_attempted": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure runtime-executor design preflight: validates the apply-request envelope and never contacts, submits to, or mutates a runtime"
    })
}

pub fn render_interaction_feedback_runtime_executor_design_preflight(preflight: &Value) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Runtime Executor Design Preflight".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "design_preflight_verdict",
        &preflight["design_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_apply_request_verdict",
        &preflight["source_apply_request_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &preflight["source_world_verdict"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);
    push_markdown_kv(
        &mut lines,
        "implicit_live_runtime_lookup_attempted",
        &preflight["implicit_live_runtime_lookup_attempted"],
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
        "queries_live_runtime",
        "submits_apply_request",
        "applies_patch",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Executor Design Request".to_string());
    lines.push(String::new());
    for key in [
        "design_request_id",
        "source_apply_request_id",
        "target_runtime",
        "patch",
        "required_design_gates",
        "ready_for_design_review",
        "ready_for_live_runtime_lookup",
        "ready_for_submission",
        "ready_for_patch_application",
        "execution_performed",
        "outcome_ingestion_allowed_by_this_tool",
        "requires_separate_runtime_executor_approval",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["executor_design_request"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_design_runtime_executor_after_review",
        "do_not_query_live_runtime",
        "do_not_submit_apply_request",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "require_operator_gate_before_submission",
        "require_post_apply_verification_design",
        "require_separate_outcome_ingestion_review",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_live_runtime_lookup_design_preflight(input: &Value) -> Value {
    let (input_kind, design_preflight) = extract_live_runtime_lookup_design_preflight_input(input);
    let schema_ok = design_preflight.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA);
    let design_request = &design_preflight["executor_design_request"];
    let guardrails = &design_preflight["guardrails"];
    let contract = &design_preflight["agent_action_contract"];

    let mut failure_reasons = Vec::new();
    if !schema_ok {
        failure_reasons.push("runtime_executor_design_preflight_required".to_string());
    }
    if schema_ok
        && design_preflight["design_preflight_verdict"] != "ready_for_runtime_executor_design"
    {
        failure_reasons.push("source_design_preflight_not_ready".to_string());
    }
    if schema_ok && design_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if schema_ok && design_request["ready_for_design_review"] != true {
        failure_reasons.push("design_review_readiness_missing".to_string());
    }
    if schema_ok && design_request["target_runtime"].is_null() {
        failure_reasons.push("target_runtime_required".to_string());
    }
    if schema_ok && design_request["patch"].is_null() {
        failure_reasons.push("patch_payload_required".to_string());
    }
    if schema_ok && design_request["ready_for_live_runtime_lookup"] != false {
        failure_reasons.push("source_must_not_allow_live_runtime_lookup".to_string());
    }
    if schema_ok && design_request["ready_for_submission"] != false {
        failure_reasons.push("source_must_not_allow_submission".to_string());
    }
    if schema_ok && design_request["ready_for_patch_application"] != false {
        failure_reasons.push("source_must_not_allow_patch_application".to_string());
    }
    if schema_ok && design_request["execution_performed"] != false {
        failure_reasons.push("source_must_not_have_executed".to_string());
    }
    if schema_ok && design_request["outcome_ingestion_allowed_by_this_tool"] != false {
        failure_reasons.push("source_must_not_allow_outcome_ingestion".to_string());
    }
    if schema_ok
        && (guardrails["read_only"] != true
            || guardrails["writes_state"] != false
            || guardrails["queries_live_runtime"] != false
            || guardrails["submits_apply_request"] != false
            || guardrails["applies_patch"] != false)
    {
        failure_reasons.push("source_design_guardrails_not_read_only".to_string());
    }
    if schema_ok
        && (contract["do_not_query_live_runtime"] != true
            || contract["do_not_submit_apply_request"] != true
            || contract["do_not_apply_patch"] != true
            || contract["do_not_ingest_outcome"] != true
            || contract["do_not_write_memory"] != true)
    {
        failure_reasons.push("source_design_contract_not_protective".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "live_runtime_lookup_design_preflight_ready".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "live_runtime_lookup_design_preflight_blocked".to_string())
    };
    let lookup_design_request_id = if ready {
        live_runtime_lookup_design_request_id_for_design_request(
            &design_request["design_request_id"],
        )
    } else {
        Value::Null
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_LIVE_RUNTIME_LOOKUP_DESIGN_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": design_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_design_preflight_verdict": design_preflight
            .get("design_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": design_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "lookup_design_preflight_verdict": if ready { "ready_for_live_runtime_lookup_design" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": live_runtime_lookup_design_preflight_guardrails(),
        "input_contract": {
            "accepted_inputs": ["runtime_executor_design_preflight", "wrapper_with_design_preflight"],
            "requires_ready_runtime_executor_design_preflight": true,
            "normalizes_preflight_or_fixture": false,
            "live_runtime_lookup_design_only": true
        },
        "lookup_design_request": {
            "lookup_design_request_id": lookup_design_request_id,
            "source_design_request_id": if ready {
                design_request.get("design_request_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "target_runtime": if ready {
                design_request.get("target_runtime").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "patch": if ready {
                design_request.get("patch").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "required_lookup_gates": [
                "operator_supplied_host_gate",
                "host_identity_gate",
                "timeout_budget_gate",
                "post_lookup_redaction_gate",
                "no_execution_gate"
            ],
            "host_binding_requirements": {
                "host_endpoint_required_from_operator": true,
                "host_endpoint_provided": false,
                "default_endpoint": Value::Null,
                "network_contact_allowed_by_this_tool": false,
                "socket_open_allowed_by_this_tool": false
            },
            "ready_for_lookup_design_review": ready,
            "ready_for_live_runtime_lookup": false,
            "live_runtime_lookup_performed": false,
            "host_contact_attempted": false,
            "ready_for_submission": false,
            "ready_for_patch_application": false,
            "execution_performed": false,
            "outcome_ingestion_allowed_by_this_tool": false,
            "requires_separate_runtime_lookup_approval": true
        },
        "agent_action_contract": {
            "mode": "live_runtime_lookup_design_preflight_only",
            "may_design_live_runtime_lookup_after_review": ready,
            "do_not_contact_live_runtime": true,
            "do_not_open_socket": true,
            "do_not_query_live_runtime": true,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "require_operator_supplied_host": true,
            "require_timeout_budget_design": true,
            "require_post_lookup_redaction_design": true,
            "require_no_execution_design": true
        },
        "source_runtime_executor_design_preflight": if schema_ok { design_preflight } else { Value::Null },
        "implicit_live_runtime_lookup_attempted": false,
        "live_runtime_contact_attempted": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure live-runtime-lookup design preflight: validates the runtime executor design envelope and never contacts or queries a live runtime"
    })
}

pub fn render_interaction_feedback_live_runtime_lookup_design_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Live Runtime Lookup Design Preflight".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "lookup_design_preflight_verdict",
        &preflight["lookup_design_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_design_preflight_verdict",
        &preflight["source_design_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &preflight["source_world_verdict"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);
    push_markdown_kv(
        &mut lines,
        "implicit_live_runtime_lookup_attempted",
        &preflight["implicit_live_runtime_lookup_attempted"],
    );
    push_markdown_kv(
        &mut lines,
        "live_runtime_contact_attempted",
        &preflight["live_runtime_contact_attempted"],
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
        "queries_live_runtime",
        "contacts_live_runtime",
        "opens_socket",
        "submits_apply_request",
        "applies_patch",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Lookup Design Request".to_string());
    lines.push(String::new());
    for key in [
        "lookup_design_request_id",
        "source_design_request_id",
        "target_runtime",
        "patch",
        "required_lookup_gates",
        "host_binding_requirements",
        "ready_for_lookup_design_review",
        "ready_for_live_runtime_lookup",
        "live_runtime_lookup_performed",
        "host_contact_attempted",
        "ready_for_submission",
        "ready_for_patch_application",
        "execution_performed",
        "outcome_ingestion_allowed_by_this_tool",
        "requires_separate_runtime_lookup_approval",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["lookup_design_request"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_design_live_runtime_lookup_after_review",
        "do_not_contact_live_runtime",
        "do_not_open_socket",
        "do_not_query_live_runtime",
        "do_not_submit_apply_request",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "require_operator_supplied_host",
        "require_timeout_budget_design",
        "require_post_lookup_redaction_design",
        "require_no_execution_design",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_live_lookup_preflight(input: &Value) -> Value {
    let (input_kind, design_preflight, lookup_snapshot) =
        extract_runtime_executor_live_lookup_preflight_input(input);
    let design_schema_ok = design_preflight.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA);
    let snapshot_schema_ok = lookup_snapshot.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA);
    let design_request = &design_preflight["executor_design_request"];
    let target_runtime = &design_request["target_runtime"];
    let patch = &design_request["patch"];
    let design_guardrails = &design_preflight["guardrails"];
    let design_contract = &design_preflight["agent_action_contract"];

    let mut failure_reasons = Vec::new();
    if !design_schema_ok {
        failure_reasons.push("runtime_executor_design_preflight_required".to_string());
    }
    if design_schema_ok
        && design_preflight["design_preflight_verdict"] != "ready_for_runtime_executor_design"
    {
        failure_reasons.push("source_design_preflight_not_ready".to_string());
    }
    if design_schema_ok && design_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if design_schema_ok && design_request["ready_for_design_review"] != true {
        failure_reasons.push("design_review_readiness_missing".to_string());
    }
    if design_schema_ok && design_request["ready_for_live_runtime_lookup"] != false {
        failure_reasons.push("source_design_must_not_grant_live_lookup_authority".to_string());
    }
    if design_schema_ok && design_request["ready_for_submission"] != false {
        failure_reasons.push("source_design_must_not_grant_submission_authority".to_string());
    }
    if design_schema_ok && design_request["ready_for_patch_application"] != false {
        failure_reasons.push("source_design_must_not_grant_application_authority".to_string());
    }
    if design_schema_ok && design_request["execution_performed"] != false {
        failure_reasons.push("source_design_must_not_execute".to_string());
    }
    if design_schema_ok && design_request["outcome_ingestion_allowed_by_this_tool"] != false {
        failure_reasons.push("source_design_must_not_ingest_outcome".to_string());
    }
    if design_schema_ok && design_request["requires_separate_runtime_executor_approval"] != true {
        failure_reasons.push("separate_runtime_executor_approval_required".to_string());
    }
    if design_schema_ok && target_runtime.is_null() {
        failure_reasons.push("target_runtime_required".to_string());
    }
    if design_schema_ok && patch.is_null() {
        failure_reasons.push("patch_payload_required".to_string());
    }
    if design_schema_ok
        && patch["required_citations"]
            .as_array()
            .map(Vec::is_empty)
            .unwrap_or(true)
    {
        failure_reasons.push("required_citations_missing".to_string());
    }
    if design_schema_ok
        && (design_guardrails["read_only"] != true
            || design_guardrails["writes_state"] != false
            || design_guardrails["queries_live_runtime"] != false
            || design_guardrails["submits_apply_request"] != false
            || design_guardrails["applies_patch"] != false)
    {
        failure_reasons.push("source_design_guardrails_not_read_only".to_string());
    }
    if design_schema_ok
        && (design_contract["do_not_query_live_runtime"] != true
            || design_contract["do_not_submit_apply_request"] != true
            || design_contract["do_not_apply_patch"] != true
            || design_contract["do_not_ingest_outcome"] != true
            || design_contract["require_operator_gate_before_submission"] != true)
    {
        failure_reasons.push("source_design_contract_not_protective".to_string());
    }
    if !snapshot_schema_ok {
        failure_reasons.push("explicit_lookup_snapshot_required".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["lookup_read_only"] != true {
        failure_reasons.push("lookup_snapshot_must_be_read_only".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["mutation_performed"] != false {
        failure_reasons.push("lookup_snapshot_must_not_mutate".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["submission_performed"] != false {
        failure_reasons.push("lookup_snapshot_must_not_submit".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["application_performed"] != false {
        failure_reasons.push("lookup_snapshot_must_not_apply".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["verification_performed"] != false {
        failure_reasons.push("lookup_snapshot_must_not_verify".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["outcome_ingestion_allowed"] != false {
        failure_reasons.push("lookup_snapshot_must_not_allow_ingestion".to_string());
    }
    if design_schema_ok
        && snapshot_schema_ok
        && target_runtime["runtime_family"] != lookup_snapshot["runtime_family"]
    {
        failure_reasons.push("runtime_family_mismatch".to_string());
    }
    if design_schema_ok
        && snapshot_schema_ok
        && target_runtime["world_id"] != lookup_snapshot["world_id"]
    {
        failure_reasons.push("world_id_mismatch".to_string());
    }
    if design_schema_ok
        && snapshot_schema_ok
        && target_runtime["branch_id"] != lookup_snapshot["branch_id"]
    {
        failure_reasons.push("branch_id_mismatch".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["runtime_generation"].as_str().is_none() {
        failure_reasons.push("runtime_generation_required".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["target_entities_present"] != true {
        failure_reasons.push("target_entities_not_present".to_string());
    }
    if snapshot_schema_ok && lookup_snapshot["patch_target_still_valid"] != true {
        failure_reasons.push("patch_target_not_valid".to_string());
    }
    if design_schema_ok
        && snapshot_schema_ok
        && !lookup_snapshot_covers_patch_entities(&lookup_snapshot, patch)
    {
        failure_reasons.push("lookup_snapshot_missing_patch_entities".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "live_lookup_preflight_ready_for_operator_submission_review".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "live_lookup_preflight_blocked".to_string())
    };
    let lookup_evidence_id = if ready {
        live_lookup_evidence_id_for_design_request(&design_request["design_request_id"])
    } else {
        Value::Null
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": design_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_design_preflight_verdict": design_preflight
            .get("design_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": design_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "lookup_snapshot_schema": lookup_snapshot.get("schema").cloned().unwrap_or(Value::Null),
        "lookup_preflight_verdict": if ready { "ready_for_operator_submission_review" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_live_lookup_preflight_guardrails(),
        "input_contract": {
            "accepted_inputs": ["runtime_executor_design_preflight_with_lookup_snapshot", "wrapper_with_design_preflight_and_lookup_snapshot"],
            "requires_ready_design_preflight": true,
            "requires_explicit_lookup_snapshot": true,
            "performs_live_lookup": false,
            "normalizes_apply_request_or_fixture": false
        },
        "lookup_evidence": {
            "lookup_evidence_id": lookup_evidence_id,
            "source_design_request_id": if ready {
                design_request.get("design_request_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "source_apply_request_id": if ready {
                design_request.get("source_apply_request_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "runtime_family": if ready {
                lookup_snapshot.get("runtime_family").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "world_id": if ready {
                lookup_snapshot.get("world_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "branch_id": if ready {
                lookup_snapshot.get("branch_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "runtime_generation": if ready {
                lookup_snapshot.get("runtime_generation").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "target_entities_present": ready,
            "patch_target_still_valid": ready,
            "patch_id": if ready {
                patch.get("patch_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "target_entities": if ready {
                patch.get("target_entities").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "required_citations": if ready {
                patch.get("required_citations").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "ready_for_operator_submission_review": ready,
            "ready_for_submission": false,
            "ready_for_patch_application": false,
            "mutation_performed": false,
            "verification_performed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": if ready { "operator_submission_gate_review" } else { "repair_lookup_preflight_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_live_lookup_preflight_only",
            "may_review_operator_submission_after_gate": ready,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_verify_post_apply_result": true,
            "require_operator_gate_before_submission": true,
            "require_patch_application_gate_after_submission": true,
            "require_post_apply_verification_after_application": true,
            "require_separate_outcome_ingestion_review": true
        },
        "source_design_preflight": if design_schema_ok { design_preflight } else { Value::Null },
        "lookup_snapshot": if snapshot_schema_ok { lookup_snapshot } else { Value::Null },
        "implicit_live_runtime_lookup_attempted": false,
        "lookup_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure G1 live-lookup preflight: validates an explicit read-only lookup snapshot and never queries, submits to, or mutates a runtime"
    })
}

pub fn render_interaction_feedback_runtime_executor_live_lookup_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push("# LSWR Interaction Feedback Runtime Executor Live Lookup Preflight".to_string());
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "lookup_preflight_verdict",
        &preflight["lookup_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_design_preflight_verdict",
        &preflight["source_design_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &preflight["source_world_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "lookup_snapshot_schema",
        &preflight["lookup_snapshot_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);
    push_markdown_kv(
        &mut lines,
        "implicit_live_runtime_lookup_attempted",
        &preflight["implicit_live_runtime_lookup_attempted"],
    );
    push_markdown_kv(
        &mut lines,
        "lookup_performed_by_this_tool",
        &preflight["lookup_performed_by_this_tool"],
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
        "queries_live_runtime",
        "requires_explicit_lookup_snapshot",
        "submits_apply_request",
        "applies_patch",
        "verifies_post_apply_result",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Lookup Evidence".to_string());
    lines.push(String::new());
    for key in [
        "lookup_evidence_id",
        "source_design_request_id",
        "source_apply_request_id",
        "runtime_family",
        "world_id",
        "branch_id",
        "runtime_generation",
        "target_entities_present",
        "patch_target_still_valid",
        "patch_id",
        "target_entities",
        "required_citations",
        "ready_for_operator_submission_review",
        "ready_for_submission",
        "ready_for_patch_application",
        "mutation_performed",
        "verification_performed",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["lookup_evidence"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_review_operator_submission_after_gate",
        "do_not_submit_apply_request",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_verify_post_apply_result",
        "require_operator_gate_before_submission",
        "require_patch_application_gate_after_submission",
        "require_post_apply_verification_after_application",
        "require_separate_outcome_ingestion_review",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_operator_submission_token_preflight(
    input: &Value,
) -> Value {
    let (input_kind, lookup_preflight, operator_decision) =
        extract_runtime_executor_operator_submission_token_preflight_input(input);
    let lookup_schema_ok = lookup_preflight.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA);
    let decision_schema_ok = operator_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA);
    let lookup_evidence = &lookup_preflight["lookup_evidence"];
    let lookup_guardrails = &lookup_preflight["guardrails"];
    let lookup_contract = &lookup_preflight["agent_action_contract"];
    let approved_scope = &operator_decision["approved_scope"];

    let mut failure_reasons = Vec::new();
    if !lookup_schema_ok {
        failure_reasons.push("runtime_executor_live_lookup_preflight_required".to_string());
    }
    if lookup_schema_ok
        && lookup_preflight["lookup_preflight_verdict"] != "ready_for_operator_submission_review"
    {
        failure_reasons.push("source_lookup_preflight_not_ready".to_string());
    }
    if lookup_schema_ok && lookup_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if lookup_schema_ok && lookup_evidence["ready_for_operator_submission_review"] != true {
        failure_reasons.push("lookup_evidence_not_ready_for_operator_review".to_string());
    }
    if lookup_schema_ok && lookup_evidence["ready_for_submission"] != false {
        failure_reasons.push("lookup_evidence_must_not_grant_submission_authority".to_string());
    }
    if lookup_schema_ok && lookup_evidence["ready_for_patch_application"] != false {
        failure_reasons.push("lookup_evidence_must_not_grant_application_authority".to_string());
    }
    if lookup_schema_ok && lookup_evidence["mutation_performed"] != false {
        failure_reasons.push("lookup_evidence_must_not_mutate".to_string());
    }
    if lookup_schema_ok && lookup_evidence["verification_performed"] != false {
        failure_reasons.push("lookup_evidence_must_not_verify".to_string());
    }
    if lookup_schema_ok && lookup_evidence["outcome_ingestion_allowed"] != false {
        failure_reasons.push("lookup_evidence_must_not_allow_ingestion".to_string());
    }
    if lookup_schema_ok
        && (lookup_guardrails["read_only"] != true
            || lookup_guardrails["writes_state"] != false
            || lookup_guardrails["submits_apply_request"] != false
            || lookup_guardrails["applies_patch"] != false
            || lookup_guardrails["verifies_post_apply_result"] != false
            || lookup_guardrails["outcome_ingestion_allowed"] != false)
    {
        failure_reasons.push("source_lookup_guardrails_not_read_only".to_string());
    }
    if lookup_schema_ok
        && (lookup_contract["do_not_submit_apply_request"] != true
            || lookup_contract["do_not_apply_patch"] != true
            || lookup_contract["do_not_ingest_outcome"] != true
            || lookup_contract["require_operator_gate_before_submission"] != true
            || lookup_contract["require_patch_application_gate_after_submission"] != true)
    {
        failure_reasons.push("source_lookup_contract_not_protective".to_string());
    }
    if !decision_schema_ok {
        failure_reasons.push("explicit_operator_submission_decision_required".to_string());
    }
    if decision_schema_ok && operator_decision["decision"] != "approved" {
        failure_reasons.push("operator_decision_must_be_approved".to_string());
    }
    if decision_schema_ok
        && operator_decision["requested_authority"] != "operator_submission_token_only"
    {
        failure_reasons.push("operator_decision_authority_scope_not_token_only".to_string());
    }
    if decision_schema_ok && operator_decision["operator_id"].as_str().is_none() {
        failure_reasons.push("operator_id_required".to_string());
    }
    if decision_schema_ok && operator_decision["decision_id"].as_str().is_none() {
        failure_reasons.push("operator_decision_id_required".to_string());
    }
    if decision_schema_ok && operator_decision["expires_at"].as_str().is_none() {
        failure_reasons.push("operator_decision_expiry_required".to_string());
    }
    if decision_schema_ok && operator_decision["approved_at"].as_str().is_none() {
        failure_reasons.push("operator_decision_timestamp_required".to_string());
    }
    if decision_schema_ok && operator_decision["submission_performed"] != false {
        failure_reasons.push("operator_decision_must_not_submit".to_string());
    }
    if decision_schema_ok && operator_decision["apply_request_submitted"] != false {
        failure_reasons.push("operator_decision_must_not_submit_apply_request".to_string());
    }
    if decision_schema_ok && operator_decision["patch_application_allowed"] != false {
        failure_reasons.push("operator_decision_must_not_allow_patch_application".to_string());
    }
    if decision_schema_ok && operator_decision["verification_allowed"] != false {
        failure_reasons.push("operator_decision_must_not_allow_verification".to_string());
    }
    if decision_schema_ok && operator_decision["outcome_ingestion_allowed"] != false {
        failure_reasons.push("operator_decision_must_not_allow_ingestion".to_string());
    }
    if decision_schema_ok && operator_decision["writes_state"] != false {
        failure_reasons.push("operator_decision_must_not_write_state".to_string());
    }
    if lookup_schema_ok
        && decision_schema_ok
        && approved_scope["lookup_evidence_id"] != lookup_evidence["lookup_evidence_id"]
    {
        failure_reasons.push("operator_decision_lookup_evidence_scope_mismatch".to_string());
    }
    if lookup_schema_ok
        && decision_schema_ok
        && approved_scope["world_id"] != lookup_evidence["world_id"]
    {
        failure_reasons.push("operator_decision_world_scope_mismatch".to_string());
    }
    if lookup_schema_ok
        && decision_schema_ok
        && approved_scope["branch_id"] != lookup_evidence["branch_id"]
    {
        failure_reasons.push("operator_decision_branch_scope_mismatch".to_string());
    }
    if lookup_schema_ok
        && decision_schema_ok
        && approved_scope["runtime_generation"] != lookup_evidence["runtime_generation"]
    {
        failure_reasons.push("operator_decision_runtime_generation_scope_mismatch".to_string());
    }
    if lookup_schema_ok
        && decision_schema_ok
        && approved_scope["patch_id"] != lookup_evidence["patch_id"]
    {
        failure_reasons.push("operator_decision_patch_scope_mismatch".to_string());
    }
    if lookup_schema_ok
        && decision_schema_ok
        && approved_scope["source_apply_request_id"] != lookup_evidence["source_apply_request_id"]
    {
        failure_reasons.push("operator_decision_apply_request_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "operator_submission_token_preflight_ready_for_patch_application_gate_review".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "operator_submission_token_preflight_blocked".to_string())
    };
    let token_id = if ready {
        operator_submission_token_id_for_patch(&lookup_evidence["patch_id"])
    } else {
        Value::Null
    };
    let idempotency_key = if ready {
        operator_submission_idempotency_key(
            &lookup_evidence["patch_id"],
            &lookup_evidence["runtime_generation"],
            &operator_decision["decision_id"],
        )
    } else {
        Value::Null
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": lookup_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_lookup_preflight_verdict": lookup_preflight
            .get("lookup_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": lookup_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "operator_decision_schema": operator_decision.get("schema").cloned().unwrap_or(Value::Null),
        "submission_token_preflight_verdict": if ready { "ready_for_patch_application_gate_review" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_operator_submission_token_preflight_guardrails(),
        "input_contract": {
            "accepted_inputs": ["live_lookup_preflight_with_operator_decision", "wrapper_with_lookup_preflight_and_operator_decision"],
            "requires_ready_live_lookup_preflight": true,
            "requires_explicit_operator_decision": true,
            "operator_authority_scope": "operator_submission_token_only",
            "submits_apply_request": false,
            "applies_patch": false
        },
        "operator_submission_token": {
            "token_id": token_id,
            "token_type": if ready { json!("operator_submission_gate_token") } else { Value::Null },
            "operator_decision_id": if ready {
                operator_decision.get("decision_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "operator_id": if ready {
                operator_decision.get("operator_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "approved_at": if ready {
                operator_decision.get("approved_at").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "expires_at": if ready {
                operator_decision.get("expires_at").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "lookup_evidence_id": if ready {
                lookup_evidence.get("lookup_evidence_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "source_design_request_id": if ready {
                lookup_evidence.get("source_design_request_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "source_apply_request_id": if ready {
                lookup_evidence.get("source_apply_request_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "world_id": if ready {
                lookup_evidence.get("world_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "branch_id": if ready {
                lookup_evidence.get("branch_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "runtime_generation": if ready {
                lookup_evidence.get("runtime_generation").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "patch_id": if ready {
                lookup_evidence.get("patch_id").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "target_entities": if ready {
                lookup_evidence.get("target_entities").cloned().unwrap_or(Value::Null)
            } else {
                Value::Null
            },
            "idempotency_key": idempotency_key,
            "replay_guard": {
                "idempotency_key": if ready {
                    operator_submission_idempotency_key(
                        &lookup_evidence["patch_id"],
                        &lookup_evidence["runtime_generation"],
                        &operator_decision["decision_id"],
                    )
                } else {
                    Value::Null
                },
                "runtime_generation_required": ready,
                "single_use_intent": ready,
                "requires_fresh_g1_lookup_evidence": true
            },
            "token_candidate_emitted_by_this_tool": ready,
            "submission_token_persisted": false,
            "ready_for_patch_application_gate_review": ready,
            "ready_for_executor_submission": false,
            "apply_request_submitted": false,
            "patch_application_performed": false,
            "verification_performed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": if ready { "patch_application_gate_review" } else { "repair_operator_submission_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_operator_submission_token_preflight_only",
            "may_review_patch_application_after_gate": ready,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_verify_post_apply_result": true,
            "do_not_persist_submission_token": true,
            "require_patch_application_gate_after_submission_token": true,
            "require_post_apply_verification_after_application": true,
            "require_separate_outcome_ingestion_review": true
        },
        "source_lookup_preflight": if lookup_schema_ok { lookup_preflight } else { Value::Null },
        "operator_decision": if decision_schema_ok { operator_decision } else { Value::Null },
        "submission_performed_by_this_tool": false,
        "apply_request_submitted_by_this_tool": false,
        "patch_application_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure G2 operator-submission token preflight: validates explicit operator approval and emits a scoped token candidate without submitting or mutating"
    })
}

pub fn render_interaction_feedback_runtime_executor_operator_submission_token_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Operator Submission Token Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "submission_token_preflight_verdict",
        &preflight["submission_token_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_lookup_preflight_verdict",
        &preflight["source_lookup_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &preflight["source_world_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "operator_decision_schema",
        &preflight["operator_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Guardrails".to_string());
    lines.push(String::new());
    for key in [
        "read_only",
        "mutation_surface",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "requires_explicit_operator_decision",
        "submits_apply_request",
        "applies_patch",
        "verifies_post_apply_result",
        "outcome_ingestion_allowed",
        "persists_submission_token",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Operator Submission Token".to_string());
    lines.push(String::new());
    for key in [
        "token_id",
        "token_type",
        "operator_decision_id",
        "operator_id",
        "approved_at",
        "expires_at",
        "lookup_evidence_id",
        "source_design_request_id",
        "source_apply_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "target_entities",
        "idempotency_key",
        "token_candidate_emitted_by_this_tool",
        "submission_token_persisted",
        "ready_for_patch_application_gate_review",
        "ready_for_executor_submission",
        "apply_request_submitted",
        "patch_application_performed",
        "verification_performed",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["operator_submission_token"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_review_patch_application_after_gate",
        "do_not_submit_apply_request",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_verify_post_apply_result",
        "do_not_persist_submission_token",
        "require_patch_application_gate_after_submission_token",
        "require_post_apply_verification_after_application",
        "require_separate_outcome_ingestion_review",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_patch_application_gate_preflight(
    input: &Value,
) -> Value {
    let (input_kind, submission_preflight, gate_decision) =
        extract_runtime_executor_patch_application_gate_preflight_input(input);
    let submission_schema_ok = submission_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA,
        );
    let decision_schema_ok = gate_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_DECISION_SCHEMA);
    let token = &submission_preflight["operator_submission_token"];
    let submission_guardrails = &submission_preflight["guardrails"];
    let submission_contract = &submission_preflight["agent_action_contract"];
    let approved_scope = &gate_decision["approved_scope"];

    let mut failure_reasons = Vec::new();
    if !submission_schema_ok {
        failure_reasons
            .push("runtime_executor_operator_submission_token_preflight_required".to_string());
    }
    if submission_schema_ok
        && submission_preflight["submission_token_preflight_verdict"]
            != "ready_for_patch_application_gate_review"
    {
        failure_reasons.push("source_submission_token_preflight_not_ready".to_string());
    }
    if submission_schema_ok && submission_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if submission_schema_ok && token["token_candidate_emitted_by_this_tool"] != true {
        failure_reasons.push("operator_submission_token_candidate_required".to_string());
    }
    if submission_schema_ok && token["submission_token_persisted"] != false {
        failure_reasons.push("operator_submission_token_must_not_be_persisted".to_string());
    }
    if submission_schema_ok && token["ready_for_patch_application_gate_review"] != true {
        failure_reasons.push("operator_submission_token_not_ready_for_patch_gate".to_string());
    }
    if submission_schema_ok && token["ready_for_executor_submission"] != false {
        failure_reasons.push("operator_submission_token_must_not_submit_to_executor".to_string());
    }
    if submission_schema_ok && token["apply_request_submitted"] != false {
        failure_reasons.push("operator_submission_token_must_not_submit_apply_request".to_string());
    }
    if submission_schema_ok && token["patch_application_performed"] != false {
        failure_reasons.push("operator_submission_token_must_not_apply_patch".to_string());
    }
    if submission_schema_ok && token["verification_performed"] != false {
        failure_reasons.push("operator_submission_token_must_not_verify".to_string());
    }
    if submission_schema_ok && token["outcome_ingestion_allowed"] != false {
        failure_reasons.push("operator_submission_token_must_not_allow_ingestion".to_string());
    }
    if submission_schema_ok
        && (submission_guardrails["read_only"] != true
            || submission_guardrails["writes_state"] != false
            || submission_guardrails["submits_apply_request"] != false
            || submission_guardrails["applies_patch"] != false
            || submission_guardrails["verifies_post_apply_result"] != false
            || submission_guardrails["outcome_ingestion_allowed"] != false
            || submission_guardrails["persists_submission_token"] != false)
    {
        failure_reasons.push("source_submission_guardrails_not_read_only".to_string());
    }
    if submission_schema_ok
        && (submission_contract["do_not_submit_apply_request"] != true
            || submission_contract["do_not_apply_patch"] != true
            || submission_contract["do_not_ingest_outcome"] != true
            || submission_contract["do_not_persist_submission_token"] != true
            || submission_contract["require_patch_application_gate_after_submission_token"] != true
            || submission_contract["require_post_apply_verification_after_application"] != true)
    {
        failure_reasons.push("source_submission_contract_not_protective".to_string());
    }
    if !decision_schema_ok {
        failure_reasons.push("explicit_patch_application_gate_decision_required".to_string());
    }
    if decision_schema_ok && gate_decision["decision"] != "approved" {
        failure_reasons.push("patch_application_gate_decision_must_be_approved".to_string());
    }
    if decision_schema_ok
        && gate_decision["requested_authority"] != "patch_application_executor_invocation_gate_only"
    {
        failure_reasons
            .push("patch_application_gate_authority_scope_not_invocation_gate_only".to_string());
    }
    if decision_schema_ok && gate_decision["separate_patch_executor_invocation_allowed"] != true {
        failure_reasons
            .push("patch_application_gate_must_allow_separate_executor_invocation".to_string());
    }
    if decision_schema_ok && gate_decision["operator_id"].as_str().is_none() {
        failure_reasons.push("patch_application_gate_operator_id_required".to_string());
    }
    if decision_schema_ok && gate_decision["decision_id"].as_str().is_none() {
        failure_reasons.push("patch_application_gate_decision_id_required".to_string());
    }
    if decision_schema_ok && gate_decision["expires_at"].as_str().is_none() {
        failure_reasons.push("patch_application_gate_decision_expiry_required".to_string());
    }
    if decision_schema_ok && gate_decision["approved_at"].as_str().is_none() {
        failure_reasons.push("patch_application_gate_decision_timestamp_required".to_string());
    }
    if decision_schema_ok && gate_decision["executor_invocation_performed"] != false {
        failure_reasons.push("patch_application_gate_must_not_invoke_executor".to_string());
    }
    if decision_schema_ok && gate_decision["apply_request_submitted"] != false {
        failure_reasons.push("patch_application_gate_must_not_submit_apply_request".to_string());
    }
    if decision_schema_ok && gate_decision["patch_application_performed"] != false {
        failure_reasons.push("patch_application_gate_must_not_apply_patch".to_string());
    }
    if decision_schema_ok && gate_decision["verification_allowed"] != false {
        failure_reasons.push("patch_application_gate_must_not_allow_verification".to_string());
    }
    if decision_schema_ok && gate_decision["outcome_ingestion_allowed"] != false {
        failure_reasons.push("patch_application_gate_must_not_allow_ingestion".to_string());
    }
    if decision_schema_ok && gate_decision["writes_state"] != false {
        failure_reasons.push("patch_application_gate_must_not_write_state".to_string());
    }
    if submission_schema_ok && decision_schema_ok && approved_scope["token_id"] != token["token_id"]
    {
        failure_reasons.push("patch_application_gate_token_scope_mismatch".to_string());
    }
    if submission_schema_ok
        && decision_schema_ok
        && approved_scope["idempotency_key"] != token["idempotency_key"]
    {
        failure_reasons.push("patch_application_gate_idempotency_scope_mismatch".to_string());
    }
    if submission_schema_ok && decision_schema_ok && approved_scope["world_id"] != token["world_id"]
    {
        failure_reasons.push("patch_application_gate_world_scope_mismatch".to_string());
    }
    if submission_schema_ok
        && decision_schema_ok
        && approved_scope["branch_id"] != token["branch_id"]
    {
        failure_reasons.push("patch_application_gate_branch_scope_mismatch".to_string());
    }
    if submission_schema_ok
        && decision_schema_ok
        && approved_scope["runtime_generation"] != token["runtime_generation"]
    {
        failure_reasons
            .push("patch_application_gate_runtime_generation_scope_mismatch".to_string());
    }
    if submission_schema_ok && decision_schema_ok && approved_scope["patch_id"] != token["patch_id"]
    {
        failure_reasons.push("patch_application_gate_patch_scope_mismatch".to_string());
    }
    if submission_schema_ok
        && decision_schema_ok
        && approved_scope["source_apply_request_id"] != token["source_apply_request_id"]
    {
        failure_reasons.push("patch_application_gate_apply_request_scope_mismatch".to_string());
    }
    if submission_schema_ok
        && decision_schema_ok
        && approved_scope["operator_submission_decision_id"] != token["operator_decision_id"]
    {
        failure_reasons.push("patch_application_gate_operator_decision_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "patch_application_gate_preflight_ready_for_separate_executor_invocation".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "patch_application_gate_preflight_blocked".to_string())
    };
    let gate_id = if ready {
        patch_application_gate_id_for_patch(&token["patch_id"])
    } else {
        Value::Null
    };
    let gate_idempotency_key = if ready {
        patch_application_gate_idempotency_key(
            &token["patch_id"],
            &token["runtime_generation"],
            &token["token_id"],
            &gate_decision["decision_id"],
        )
    } else {
        Value::Null
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": submission_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_submission_token_preflight_verdict": submission_preflight
            .get("submission_token_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": submission_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "patch_application_gate_decision_schema": gate_decision.get("schema").cloned().unwrap_or(Value::Null),
        "patch_application_gate_preflight_verdict": if ready { "ready_for_separate_executor_invocation" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_patch_application_gate_preflight_guardrails(),
        "input_contract": {
            "accepted_inputs": ["operator_submission_token_preflight_with_patch_application_gate_decision", "wrapper_with_submission_preflight_and_patch_application_gate_decision"],
            "requires_ready_operator_submission_token_preflight": true,
            "requires_explicit_patch_application_gate_decision": true,
            "patch_application_authority_scope": "patch_application_executor_invocation_gate_only",
            "invokes_patch_executor": false,
            "submits_apply_request": false,
            "applies_patch": false
        },
        "patch_application_gate": {
            "gate_id": gate_id,
            "gate_type": if ready { json!("patch_application_executor_invocation_gate") } else { Value::Null },
            "gate_decision_id": if ready { gate_decision.get("decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "operator_id": if ready { gate_decision.get("operator_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "approved_at": if ready { gate_decision.get("approved_at").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "expires_at": if ready { gate_decision.get("expires_at").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "operator_submission_token_id": if ready { token.get("token_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "operator_submission_token_idempotency_key": if ready { token.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "operator_submission_decision_id": if ready { token.get("operator_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "lookup_evidence_id": if ready { token.get("lookup_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_apply_request_id": if ready { token.get("source_apply_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { token.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { token.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { token.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { token.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "target_entities": if ready { token.get("target_entities").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": gate_idempotency_key,
            "replay_guard": {
                "idempotency_key": if ready {
                    patch_application_gate_idempotency_key(
                        &token["patch_id"],
                        &token["runtime_generation"],
                        &token["token_id"],
                        &gate_decision["decision_id"],
                    )
                } else {
                    Value::Null
                },
                "requires_fresh_g2_submission_token_preflight": true,
                "runtime_generation_required": ready,
                "single_use_intent": ready
            },
            "ready_for_separate_patch_executor_invocation": ready,
            "separate_patch_executor_invocation_allowed_after_this_gate": ready,
            "executor_invocation_performed_by_this_tool": false,
            "apply_request_submitted": false,
            "patch_application_performed": false,
            "verification_performed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": if ready { "separate_patch_application_executor_invocation" } else { "repair_patch_application_gate_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_patch_application_gate_preflight_only",
            "may_invoke_separate_patch_executor_after_gate": ready,
            "do_not_invoke_patch_executor": true,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_verify_post_apply_result": true,
            "do_not_persist_submission_token": true,
            "require_post_apply_verification_after_application": true,
            "require_separate_outcome_ingestion_review": true
        },
        "source_submission_token_preflight": if submission_schema_ok { submission_preflight } else { Value::Null },
        "patch_application_gate_decision": if decision_schema_ok { gate_decision } else { Value::Null },
        "executor_invocation_performed_by_this_tool": false,
        "apply_request_submitted_by_this_tool": false,
        "patch_application_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure G3 patch-application gate preflight: validates explicit gate approval and emits a readiness decision for a separate executor without invoking, submitting, applying, or mutating"
    })
}

pub fn render_interaction_feedback_runtime_executor_patch_application_gate_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Patch Application Gate Preflight".to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "patch_application_gate_preflight_verdict",
        &preflight["patch_application_gate_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_submission_token_preflight_verdict",
        &preflight["source_submission_token_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "source_world_verdict",
        &preflight["source_world_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "patch_application_gate_decision_schema",
        &preflight["patch_application_gate_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Guardrails".to_string());
    lines.push(String::new());
    for key in [
        "read_only",
        "mutation_surface",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "requires_ready_operator_submission_token_preflight",
        "requires_explicit_patch_application_gate_decision",
        "invokes_patch_executor",
        "submits_apply_request",
        "applies_patch",
        "verifies_post_apply_result",
        "outcome_ingestion_allowed",
        "persists_submission_token",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Patch Application Gate".to_string());
    lines.push(String::new());
    for key in [
        "gate_id",
        "gate_type",
        "gate_decision_id",
        "operator_id",
        "approved_at",
        "expires_at",
        "operator_submission_token_id",
        "operator_submission_token_idempotency_key",
        "operator_submission_decision_id",
        "lookup_evidence_id",
        "source_apply_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "target_entities",
        "idempotency_key",
        "ready_for_separate_patch_executor_invocation",
        "separate_patch_executor_invocation_allowed_after_this_gate",
        "executor_invocation_performed_by_this_tool",
        "apply_request_submitted",
        "patch_application_performed",
        "verification_performed",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["patch_application_gate"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_invoke_separate_patch_executor_after_gate",
        "do_not_invoke_patch_executor",
        "do_not_submit_apply_request",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_verify_post_apply_result",
        "do_not_persist_submission_token",
        "require_post_apply_verification_after_application",
        "require_separate_outcome_ingestion_review",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(
    input: &Value,
) -> Value {
    let (input_kind, gate_preflight, invocation_decision) =
        extract_runtime_executor_patch_executor_invocation_preflight_input(input);
    let gate_schema_ok = gate_preflight.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_SCHEMA);
    let decision_schema_ok = invocation_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_DECISION_SCHEMA);
    let gate = &gate_preflight["patch_application_gate"];
    let gate_guardrails = &gate_preflight["guardrails"];
    let gate_contract = &gate_preflight["agent_action_contract"];
    let approved_scope = &invocation_decision["approved_scope"];

    let mut failure_reasons = Vec::new();
    if !gate_schema_ok {
        failure_reasons
            .push("runtime_executor_patch_application_gate_preflight_required".to_string());
    }
    if gate_schema_ok
        && gate_preflight["patch_application_gate_preflight_verdict"]
            != "ready_for_separate_executor_invocation"
    {
        failure_reasons.push("source_patch_application_gate_preflight_not_ready".to_string());
    }
    if gate_schema_ok && gate_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if gate_schema_ok && gate["ready_for_separate_patch_executor_invocation"] != true {
        failure_reasons.push("source_gate_not_ready_for_patch_executor_invocation".to_string());
    }
    if gate_schema_ok && gate["separate_patch_executor_invocation_allowed_after_this_gate"] != true
    {
        failure_reasons.push("source_gate_does_not_allow_patch_executor_invocation".to_string());
    }
    if gate_schema_ok && gate["executor_invocation_performed_by_this_tool"] != false {
        failure_reasons.push("source_gate_must_not_have_invoked_executor".to_string());
    }
    if gate_schema_ok && gate["apply_request_submitted"] != false {
        failure_reasons.push("source_gate_must_not_submit_apply_request".to_string());
    }
    if gate_schema_ok && gate["patch_application_performed"] != false {
        failure_reasons.push("source_gate_must_not_apply_patch".to_string());
    }
    if gate_schema_ok && gate["verification_performed"] != false {
        failure_reasons.push("source_gate_must_not_verify".to_string());
    }
    if gate_schema_ok && gate["outcome_ingestion_allowed"] != false {
        failure_reasons.push("source_gate_must_not_allow_ingestion".to_string());
    }
    if gate_schema_ok
        && (gate_guardrails["read_only"] != true
            || gate_guardrails["writes_state"] != false
            || gate_guardrails["invokes_patch_executor"] != false
            || gate_guardrails["submits_apply_request"] != false
            || gate_guardrails["applies_patch"] != false
            || gate_guardrails["verifies_post_apply_result"] != false
            || gate_guardrails["outcome_ingestion_allowed"] != false)
    {
        failure_reasons.push("source_gate_guardrails_not_read_only".to_string());
    }
    if gate_schema_ok
        && (gate_contract["may_invoke_separate_patch_executor_after_gate"] != true
            || gate_contract["do_not_invoke_patch_executor"] != true
            || gate_contract["do_not_submit_apply_request"] != true
            || gate_contract["do_not_apply_patch"] != true
            || gate_contract["do_not_ingest_outcome"] != true
            || gate_contract["do_not_write_memory"] != true
            || gate_contract["require_post_apply_verification_after_application"] != true
            || gate_contract["require_separate_outcome_ingestion_review"] != true)
    {
        failure_reasons.push("source_gate_contract_not_protective".to_string());
    }
    if !decision_schema_ok {
        failure_reasons.push("explicit_patch_executor_invocation_decision_required".to_string());
    }
    if decision_schema_ok && invocation_decision["decision"] != "approved" {
        failure_reasons.push("patch_executor_invocation_decision_must_be_approved".to_string());
    }
    if decision_schema_ok
        && invocation_decision["requested_authority"] != "separate_patch_executor_invocation_only"
    {
        failure_reasons
            .push("patch_executor_invocation_authority_scope_not_invocation_only".to_string());
    }
    if decision_schema_ok
        && invocation_decision["separate_patch_executor_invocation_allowed"] != true
    {
        failure_reasons
            .push("patch_executor_invocation_decision_must_allow_invocation".to_string());
    }
    if decision_schema_ok && invocation_decision["operator_id"].as_str().is_none() {
        failure_reasons.push("patch_executor_invocation_operator_id_required".to_string());
    }
    if decision_schema_ok && invocation_decision["decision_id"].as_str().is_none() {
        failure_reasons.push("patch_executor_invocation_decision_id_required".to_string());
    }
    if decision_schema_ok && invocation_decision["expires_at"].as_str().is_none() {
        failure_reasons.push("patch_executor_invocation_decision_expiry_required".to_string());
    }
    if decision_schema_ok && invocation_decision["approved_at"].as_str().is_none() {
        failure_reasons.push("patch_executor_invocation_decision_timestamp_required".to_string());
    }
    if decision_schema_ok && invocation_decision["executor_invocation_performed"] != false {
        failure_reasons
            .push("patch_executor_invocation_decision_must_not_invoke_executor".to_string());
    }
    if decision_schema_ok && invocation_decision["executor_queue_submission_performed"] != false {
        failure_reasons
            .push("patch_executor_invocation_decision_must_not_submit_queue".to_string());
    }
    if decision_schema_ok && invocation_decision["apply_request_submitted"] != false {
        failure_reasons
            .push("patch_executor_invocation_decision_must_not_submit_apply_request".to_string());
    }
    if decision_schema_ok && invocation_decision["patch_application_performed"] != false {
        failure_reasons.push("patch_executor_invocation_decision_must_not_apply_patch".to_string());
    }
    if decision_schema_ok && invocation_decision["verification_allowed"] != false {
        failure_reasons
            .push("patch_executor_invocation_decision_must_not_allow_verification".to_string());
    }
    if decision_schema_ok && invocation_decision["outcome_ingestion_allowed"] != false {
        failure_reasons
            .push("patch_executor_invocation_decision_must_not_allow_ingestion".to_string());
    }
    if decision_schema_ok && invocation_decision["writes_state"] != false {
        failure_reasons.push("patch_executor_invocation_decision_must_not_write_state".to_string());
    }
    if gate_schema_ok && decision_schema_ok && approved_scope["gate_id"] != gate["gate_id"] {
        failure_reasons.push("patch_executor_invocation_gate_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && decision_schema_ok
        && approved_scope["gate_decision_id"] != gate["gate_decision_id"]
    {
        failure_reasons.push("patch_executor_invocation_gate_decision_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && decision_schema_ok
        && approved_scope["gate_idempotency_key"] != gate["idempotency_key"]
    {
        failure_reasons
            .push("patch_executor_invocation_gate_idempotency_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && decision_schema_ok
        && approved_scope["operator_submission_token_id"] != gate["operator_submission_token_id"]
    {
        failure_reasons
            .push("patch_executor_invocation_operator_submission_token_scope_mismatch".to_string());
    }
    if gate_schema_ok && decision_schema_ok && approved_scope["world_id"] != gate["world_id"] {
        failure_reasons.push("patch_executor_invocation_world_scope_mismatch".to_string());
    }
    if gate_schema_ok && decision_schema_ok && approved_scope["branch_id"] != gate["branch_id"] {
        failure_reasons.push("patch_executor_invocation_branch_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && decision_schema_ok
        && approved_scope["runtime_generation"] != gate["runtime_generation"]
    {
        failure_reasons
            .push("patch_executor_invocation_runtime_generation_scope_mismatch".to_string());
    }
    if gate_schema_ok && decision_schema_ok && approved_scope["patch_id"] != gate["patch_id"] {
        failure_reasons.push("patch_executor_invocation_patch_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && decision_schema_ok
        && approved_scope["source_apply_request_id"] != gate["source_apply_request_id"]
    {
        failure_reasons.push("patch_executor_invocation_apply_request_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "patch_executor_invocation_preflight_ready_for_invocation_request".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "patch_executor_invocation_preflight_blocked".to_string())
    };
    let invocation_request_id = if ready {
        patch_executor_invocation_request_id_for_patch(&gate["patch_id"])
    } else {
        Value::Null
    };
    let invocation_idempotency_key = if ready {
        patch_executor_invocation_idempotency_key(
            &gate["patch_id"],
            &gate["runtime_generation"],
            &gate["gate_id"],
            &invocation_decision["decision_id"],
        )
    } else {
        Value::Null
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": gate_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_patch_application_gate_preflight_verdict": gate_preflight
            .get("patch_application_gate_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": gate_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "patch_executor_invocation_decision_schema": invocation_decision.get("schema").cloned().unwrap_or(Value::Null),
        "patch_executor_invocation_preflight_verdict": if ready { "ready_for_separate_patch_executor_invocation_request" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_patch_executor_invocation_preflight_guardrails(),
        "input_contract": {
            "accepted_inputs": ["patch_application_gate_preflight_with_patch_executor_invocation_decision", "wrapper_with_gate_preflight_and_invocation_decision"],
            "requires_ready_patch_application_gate_preflight": true,
            "requires_explicit_patch_executor_invocation_decision": true,
            "patch_executor_invocation_authority_scope": "separate_patch_executor_invocation_only",
            "emits_invocation_request_envelope": ready,
            "invokes_patch_executor": false,
            "submits_executor_queue": false,
            "submits_apply_request": false,
            "applies_patch": false
        },
        "patch_executor_invocation_request": {
            "request_id": invocation_request_id,
            "target_executor": if ready { json!("separate_lswr_patch_executor") } else { Value::Null },
            "request_type": if ready { json!("patch_executor_invocation_request") } else { Value::Null },
            "invocation_decision_id": if ready { invocation_decision.get("decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "operator_id": if ready { invocation_decision.get("operator_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "approved_at": if ready { invocation_decision.get("approved_at").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "expires_at": if ready { invocation_decision.get("expires_at").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_application_gate_id": if ready { gate.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_application_gate_decision_id": if ready { gate.get("gate_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_application_gate_idempotency_key": if ready { gate.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "operator_submission_token_id": if ready { gate.get("operator_submission_token_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "operator_submission_decision_id": if ready { gate.get("operator_submission_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "lookup_evidence_id": if ready { gate.get("lookup_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_apply_request_id": if ready { gate.get("source_apply_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { gate.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { gate.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { gate.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { gate.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "target_entities": if ready { gate.get("target_entities").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": invocation_idempotency_key,
            "replay_guard": {
                "idempotency_key": if ready {
                    patch_executor_invocation_idempotency_key(
                        &gate["patch_id"],
                        &gate["runtime_generation"],
                        &gate["gate_id"],
                        &invocation_decision["decision_id"],
                    )
                } else {
                    Value::Null
                },
                "requires_fresh_g3_patch_application_gate_preflight": true,
                "runtime_generation_required": ready,
                "single_use_intent": ready
            },
            "ready_for_separate_patch_executor_invocation_request": ready,
            "invocation_request_emitted_by_this_tool": ready,
            "executor_invocation_performed_by_this_tool": false,
            "executor_queue_submission_performed": false,
            "apply_request_submitted": false,
            "patch_application_performed": false,
            "verification_performed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": if ready { "separate_patch_executor_runtime_application_evidence" } else { "repair_patch_executor_invocation_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_patch_executor_invocation_preflight_only",
            "may_emit_invocation_request_envelope_after_gate": ready,
            "do_not_invoke_patch_executor": true,
            "do_not_submit_executor_queue": true,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_verify_post_apply_result": true,
            "require_runtime_application_evidence_after_invocation": true,
            "require_post_apply_verification_after_application": true,
            "require_separate_outcome_ingestion_review": true
        },
        "source_patch_application_gate_preflight": if gate_schema_ok { gate_preflight } else { Value::Null },
        "patch_executor_invocation_decision": if decision_schema_ok { invocation_decision } else { Value::Null },
        "invocation_request_emitted_by_this_tool": ready,
        "executor_invocation_performed_by_this_tool": false,
        "executor_queue_submission_performed_by_this_tool": false,
        "apply_request_submitted_by_this_tool": false,
        "patch_application_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure G4 patch-executor invocation preflight: emits a reviewable invocation request envelope without invoking an executor, submitting a queue item, applying, verifying, ingesting, or mutating"
    })
}

pub fn render_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Patch Executor Invocation Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "patch_executor_invocation_preflight_verdict",
        &preflight["patch_executor_invocation_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_patch_application_gate_preflight_verdict",
        &preflight["source_patch_application_gate_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "patch_executor_invocation_decision_schema",
        &preflight["patch_executor_invocation_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Guardrails".to_string());
    lines.push(String::new());
    for key in [
        "read_only",
        "mutation_surface",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "requires_ready_patch_application_gate_preflight",
        "requires_explicit_patch_executor_invocation_decision",
        "invokes_patch_executor",
        "submits_executor_queue",
        "submits_apply_request",
        "applies_patch",
        "verifies_post_apply_result",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["guardrails"][key]);
    }

    lines.push(String::new());
    lines.push("## Patch Executor Invocation Request".to_string());
    lines.push(String::new());
    for key in [
        "request_id",
        "target_executor",
        "request_type",
        "invocation_decision_id",
        "operator_id",
        "approved_at",
        "expires_at",
        "patch_application_gate_id",
        "patch_application_gate_decision_id",
        "patch_application_gate_idempotency_key",
        "operator_submission_token_id",
        "operator_submission_decision_id",
        "lookup_evidence_id",
        "source_apply_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "target_entities",
        "idempotency_key",
        "ready_for_separate_patch_executor_invocation_request",
        "invocation_request_emitted_by_this_tool",
        "executor_invocation_performed_by_this_tool",
        "executor_queue_submission_performed",
        "apply_request_submitted",
        "patch_application_performed",
        "verification_performed",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["patch_executor_invocation_request"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_emit_invocation_request_envelope_after_gate",
        "do_not_invoke_patch_executor",
        "do_not_submit_executor_queue",
        "do_not_submit_apply_request",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_verify_post_apply_result",
        "require_runtime_application_evidence_after_invocation",
        "require_post_apply_verification_after_application",
        "require_separate_outcome_ingestion_review",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
    input: &Value,
) -> Value {
    let (input_kind, invocation_preflight, application_evidence) =
        extract_runtime_executor_patch_runtime_application_evidence_preflight_input(input);
    let invocation_schema_ok = invocation_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA,
        );
    let evidence_schema_ok = application_evidence.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_SCHEMA);
    let request = &invocation_preflight["patch_executor_invocation_request"];
    let invocation_guardrails = &invocation_preflight["guardrails"];
    let invocation_contract = &invocation_preflight["agent_action_contract"];
    let evidence_scope = &application_evidence["source_invocation_request_scope"];

    let mut failure_reasons = Vec::new();
    if !invocation_schema_ok {
        failure_reasons
            .push("runtime_executor_patch_executor_invocation_preflight_required".to_string());
    }
    if invocation_schema_ok
        && invocation_preflight["patch_executor_invocation_preflight_verdict"]
            != "ready_for_separate_patch_executor_invocation_request"
    {
        failure_reasons.push("source_patch_executor_invocation_preflight_not_ready".to_string());
    }
    if invocation_schema_ok && invocation_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if invocation_schema_ok
        && request["ready_for_separate_patch_executor_invocation_request"] != true
    {
        failure_reasons.push("source_invocation_request_not_ready".to_string());
    }
    if invocation_schema_ok && request["invocation_request_emitted_by_this_tool"] != true {
        failure_reasons.push("source_invocation_request_not_emitted".to_string());
    }
    if invocation_schema_ok && request["executor_invocation_performed_by_this_tool"] != false {
        failure_reasons.push("source_invocation_preflight_must_not_invoke_executor".to_string());
    }
    if invocation_schema_ok && request["executor_queue_submission_performed"] != false {
        failure_reasons.push("source_invocation_preflight_must_not_submit_queue".to_string());
    }
    if invocation_schema_ok && request["patch_application_performed"] != false {
        failure_reasons.push("source_invocation_preflight_must_not_apply_patch".to_string());
    }
    if invocation_schema_ok
        && (invocation_guardrails["read_only"] != true
            || invocation_guardrails["writes_state"] != false
            || invocation_guardrails["invokes_patch_executor"] != false
            || invocation_guardrails["submits_executor_queue"] != false
            || invocation_guardrails["submits_apply_request"] != false
            || invocation_guardrails["applies_patch"] != false
            || invocation_guardrails["verifies_post_apply_result"] != false
            || invocation_guardrails["outcome_ingestion_allowed"] != false)
    {
        failure_reasons.push("source_invocation_guardrails_not_read_only".to_string());
    }
    if invocation_schema_ok
        && (invocation_contract["require_runtime_application_evidence_after_invocation"] != true
            || invocation_contract["require_post_apply_verification_after_application"] != true
            || invocation_contract["require_separate_outcome_ingestion_review"] != true
            || invocation_contract["do_not_invoke_patch_executor"] != true
            || invocation_contract["do_not_submit_executor_queue"] != true
            || invocation_contract["do_not_apply_patch"] != true
            || invocation_contract["do_not_ingest_outcome"] != true)
    {
        failure_reasons.push("source_invocation_contract_not_protective".to_string());
    }
    if !evidence_schema_ok {
        failure_reasons.push("explicit_patch_runtime_application_evidence_required".to_string());
    }
    if evidence_schema_ok && application_evidence["evidence_id"].as_str().is_none() {
        failure_reasons.push("patch_runtime_application_evidence_id_required".to_string());
    }
    if evidence_schema_ok && application_evidence["evidence_kind"] != "external_executor_claim" {
        failure_reasons
            .push("patch_runtime_application_evidence_must_be_external_claim".to_string());
    }
    if evidence_schema_ok && application_evidence["target_executor"] != request["target_executor"] {
        failure_reasons
            .push("patch_runtime_application_evidence_executor_scope_mismatch".to_string());
    }
    if invocation_schema_ok
        && evidence_schema_ok
        && evidence_scope["request_id"] != request["request_id"]
    {
        failure_reasons
            .push("patch_runtime_application_evidence_request_scope_mismatch".to_string());
    }
    if invocation_schema_ok
        && evidence_schema_ok
        && evidence_scope["idempotency_key"] != request["idempotency_key"]
    {
        failure_reasons
            .push("patch_runtime_application_evidence_idempotency_scope_mismatch".to_string());
    }
    if invocation_schema_ok
        && evidence_schema_ok
        && evidence_scope["invocation_decision_id"] != request["invocation_decision_id"]
    {
        failure_reasons
            .push("patch_runtime_application_evidence_decision_scope_mismatch".to_string());
    }
    if invocation_schema_ok
        && evidence_schema_ok
        && evidence_scope["world_id"] != request["world_id"]
    {
        failure_reasons.push("patch_runtime_application_evidence_world_scope_mismatch".to_string());
    }
    if invocation_schema_ok
        && evidence_schema_ok
        && evidence_scope["branch_id"] != request["branch_id"]
    {
        failure_reasons
            .push("patch_runtime_application_evidence_branch_scope_mismatch".to_string());
    }
    if invocation_schema_ok
        && evidence_schema_ok
        && evidence_scope["runtime_generation"] != request["runtime_generation"]
    {
        failure_reasons
            .push("patch_runtime_application_evidence_generation_scope_mismatch".to_string());
    }
    if invocation_schema_ok
        && evidence_schema_ok
        && evidence_scope["patch_id"] != request["patch_id"]
    {
        failure_reasons.push("patch_runtime_application_evidence_patch_scope_mismatch".to_string());
    }
    if invocation_schema_ok
        && evidence_schema_ok
        && evidence_scope["source_apply_request_id"] != request["source_apply_request_id"]
    {
        failure_reasons
            .push("patch_runtime_application_evidence_apply_request_scope_mismatch".to_string());
    }
    if evidence_schema_ok && application_evidence["executor_invocation_observed"] != true {
        failure_reasons.push(
            "patch_runtime_application_evidence_must_observe_executor_invocation".to_string(),
        );
    }
    if evidence_schema_ok && application_evidence["patch_application_claimed"] != true {
        failure_reasons
            .push("patch_runtime_application_evidence_must_claim_patch_application".to_string());
    }
    if evidence_schema_ok && application_evidence["runtime_mutation_claimed"] != true {
        failure_reasons
            .push("patch_runtime_application_evidence_must_claim_runtime_mutation".to_string());
    }
    if evidence_schema_ok && application_evidence["post_apply_verification_performed"] != false {
        failure_reasons.push("patch_runtime_application_evidence_must_not_verify".to_string());
    }
    if evidence_schema_ok && application_evidence["outcome_ingestion_allowed"] != false {
        failure_reasons
            .push("patch_runtime_application_evidence_must_not_allow_ingestion".to_string());
    }
    if evidence_schema_ok && application_evidence["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("patch_runtime_application_evidence_must_not_rewrite_verdict".to_string());
    }
    if evidence_schema_ok && application_evidence["evidence_record_persisted"] != false {
        failure_reasons
            .push("patch_runtime_application_evidence_must_not_persist_record".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "patch_runtime_application_evidence_preflight_ready_for_post_apply_verification_review"
            .to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "patch_runtime_application_evidence_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": invocation_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_patch_executor_invocation_preflight_verdict": invocation_preflight
            .get("patch_executor_invocation_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": invocation_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "patch_runtime_application_evidence_schema": application_evidence.get("schema").cloned().unwrap_or(Value::Null),
        "patch_runtime_application_evidence_preflight_verdict": if ready { "ready_for_post_apply_verification_review" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_patch_runtime_application_evidence_preflight_guardrails(),
        "runtime_application_evidence": {
            "evidence_id": if ready { application_evidence.get("evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { evidence_scope.get("request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_idempotency_key": if ready { evidence_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "target_executor": if ready { application_evidence.get("target_executor").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "executor_id": if ready { application_evidence.get("executor_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "executor_invoked_at": if ready { application_evidence.get("executor_invoked_at").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_applied_at": if ready { application_evidence.get("patch_applied_at").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { evidence_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { evidence_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { evidence_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { evidence_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_apply_request_id": if ready { evidence_scope.get("source_apply_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "external_executor_invocation_observed": ready,
            "external_patch_application_claimed": ready,
            "external_runtime_mutation_claimed": ready,
            "application_status": if ready { "applied_claimed_not_verified" } else { "blocked" },
            "post_apply_verification_performed_by_this_tool": false,
            "post_apply_verification_performed_by_evidence": false,
            "outcome_ingestion_allowed": false,
            "world_verdict_rewrite_allowed": false,
            "evidence_record_persisted_by_this_tool": false
        },
        "next_allowed_gate": if ready { "post_apply_verification_preflight" } else { "repair_patch_runtime_application_evidence_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_patch_runtime_application_evidence_preflight_only",
            "may_review_post_apply_verification_after_evidence": ready,
            "do_not_invoke_patch_executor": true,
            "do_not_submit_executor_queue": true,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_verify_post_apply_result": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "require_post_apply_verification_after_application": true,
            "require_separate_outcome_ingestion_review": true
        },
        "source_patch_executor_invocation_preflight": if invocation_schema_ok { invocation_preflight } else { Value::Null },
        "patch_runtime_application_evidence": if evidence_schema_ok { application_evidence } else { Value::Null },
        "executor_invocation_performed_by_this_tool": false,
        "executor_queue_submission_performed_by_this_tool": false,
        "apply_request_submitted_by_this_tool": false,
        "patch_application_performed_by_this_tool": false,
        "post_apply_verification_performed_by_this_tool": false,
        "outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure runtime application evidence preflight: validates an external executor application claim without invoking, submitting, applying, verifying, ingesting, or mutating by this tool"
    })
}

pub fn render_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Patch Runtime Application Evidence Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "patch_runtime_application_evidence_preflight_verdict",
        &preflight["patch_runtime_application_evidence_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_patch_executor_invocation_preflight_verdict",
        &preflight["source_patch_executor_invocation_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "patch_runtime_application_evidence_schema",
        &preflight["patch_runtime_application_evidence_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Runtime Application Evidence".to_string());
    lines.push(String::new());
    for key in [
        "evidence_id",
        "source_invocation_request_id",
        "target_executor",
        "executor_id",
        "executor_invoked_at",
        "patch_applied_at",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "source_apply_request_id",
        "external_executor_invocation_observed",
        "external_patch_application_claimed",
        "external_runtime_mutation_claimed",
        "application_status",
        "post_apply_verification_performed_by_this_tool",
        "post_apply_verification_performed_by_evidence",
        "outcome_ingestion_allowed",
        "world_verdict_rewrite_allowed",
        "evidence_record_persisted_by_this_tool",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["runtime_application_evidence"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_review_post_apply_verification_after_evidence",
        "do_not_invoke_patch_executor",
        "do_not_submit_executor_queue",
        "do_not_apply_patch",
        "do_not_verify_post_apply_result",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "require_post_apply_verification_after_application",
        "require_separate_outcome_ingestion_review",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_post_apply_verification_preflight(
    input: &Value,
) -> Value {
    let (input_kind, application_preflight, verification_evidence) =
        extract_runtime_executor_post_apply_verification_preflight_input(input);
    let application_schema_ok = application_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA,
        );
    let evidence_schema_ok = verification_evidence.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_EVIDENCE_SCHEMA);
    let application = &application_preflight["runtime_application_evidence"];
    let application_guardrails = &application_preflight["guardrails"];
    let application_contract = &application_preflight["agent_action_contract"];
    let evidence_scope = &verification_evidence["source_runtime_application_evidence_scope"];

    let mut failure_reasons = Vec::new();
    if !application_schema_ok {
        failure_reasons.push(
            "runtime_executor_patch_runtime_application_evidence_preflight_required".to_string(),
        );
    }
    if application_schema_ok
        && application_preflight["patch_runtime_application_evidence_preflight_verdict"]
            != "ready_for_post_apply_verification_review"
    {
        failure_reasons.push("source_runtime_application_evidence_preflight_not_ready".to_string());
    }
    if application_schema_ok && application_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if application_schema_ok && application["external_patch_application_claimed"] != true {
        failure_reasons
            .push("source_runtime_application_evidence_missing_application_claim".to_string());
    }
    if application_schema_ok
        && application["post_apply_verification_performed_by_this_tool"] != false
    {
        failure_reasons
            .push("source_runtime_application_evidence_must_not_have_verified".to_string());
    }
    if application_schema_ok && application["outcome_ingestion_allowed"] != false {
        failure_reasons
            .push("source_runtime_application_evidence_must_not_allow_ingestion".to_string());
    }
    if application_schema_ok && application["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("source_runtime_application_evidence_must_not_rewrite_verdict".to_string());
    }
    if application_schema_ok
        && (application_guardrails["read_only"] != true
            || application_guardrails["writes_state"] != false
            || application_guardrails["verifies_post_apply_result"] != false
            || application_guardrails["outcome_ingestion_allowed"] != false
            || application_guardrails["persists_evidence_record"] != false)
    {
        failure_reasons.push("source_runtime_application_guardrails_not_read_only".to_string());
    }
    if application_schema_ok
        && (application_contract["may_review_post_apply_verification_after_evidence"] != true
            || application_contract["require_post_apply_verification_after_application"] != true
            || application_contract["require_separate_outcome_ingestion_review"] != true
            || application_contract["do_not_verify_post_apply_result"] != true
            || application_contract["do_not_ingest_outcome"] != true
            || application_contract["do_not_rewrite_world_verdict"] != true)
    {
        failure_reasons.push("source_runtime_application_contract_not_protective".to_string());
    }
    if !evidence_schema_ok {
        failure_reasons.push("explicit_post_apply_verification_evidence_required".to_string());
    }
    if evidence_schema_ok && verification_evidence["verification_id"].as_str().is_none() {
        failure_reasons.push("post_apply_verification_id_required".to_string());
    }
    if evidence_schema_ok && verification_evidence["evidence_kind"] != "post_apply_verification" {
        failure_reasons.push("post_apply_verification_evidence_kind_required".to_string());
    }
    if evidence_schema_ok
        && !matches!(
            verification_evidence["verification_verdict"].as_str(),
            Some("verified" | "not_verified")
        )
    {
        failure_reasons.push("post_apply_verification_verdict_invalid".to_string());
    }
    if evidence_schema_ok && verification_evidence["expected_effect_checked"] != true {
        failure_reasons.push("post_apply_verification_must_check_expected_effect".to_string());
    }
    if evidence_schema_ok && verification_evidence["presentation_readback_checked"] != true {
        failure_reasons
            .push("post_apply_verification_must_check_presentation_readback".to_string());
    }
    if evidence_schema_ok
        && verification_evidence["verification_verdict"] == "verified"
        && verification_evidence["expected_effect_passed"] != true
    {
        failure_reasons
            .push("verified_post_apply_result_requires_expected_effect_passed".to_string());
    }
    if evidence_schema_ok
        && verification_evidence["verification_verdict"] == "verified"
        && verification_evidence["presentation_readback_consistent"] != true
    {
        failure_reasons.push(
            "verified_post_apply_result_requires_presentation_readback_consistent".to_string(),
        );
    }
    if evidence_schema_ok && verification_evidence["outcome_ingestion_allowed"] != false {
        failure_reasons.push("post_apply_verification_must_not_allow_ingestion".to_string());
    }
    if evidence_schema_ok && verification_evidence["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push("post_apply_verification_must_not_rewrite_verdict".to_string());
    }
    if evidence_schema_ok && verification_evidence["verification_record_persisted"] != false {
        failure_reasons.push("post_apply_verification_must_not_persist_record".to_string());
    }
    if application_schema_ok
        && evidence_schema_ok
        && evidence_scope["runtime_application_evidence_id"] != application["evidence_id"]
    {
        failure_reasons
            .push("post_apply_verification_application_evidence_scope_mismatch".to_string());
    }
    if application_schema_ok
        && evidence_schema_ok
        && evidence_scope["source_invocation_request_id"]
            != application["source_invocation_request_id"]
    {
        failure_reasons
            .push("post_apply_verification_invocation_request_scope_mismatch".to_string());
    }
    if application_schema_ok
        && evidence_schema_ok
        && evidence_scope["world_id"] != application["world_id"]
    {
        failure_reasons.push("post_apply_verification_world_scope_mismatch".to_string());
    }
    if application_schema_ok
        && evidence_schema_ok
        && evidence_scope["branch_id"] != application["branch_id"]
    {
        failure_reasons.push("post_apply_verification_branch_scope_mismatch".to_string());
    }
    if application_schema_ok
        && evidence_schema_ok
        && evidence_scope["runtime_generation"] != application["runtime_generation"]
    {
        failure_reasons.push("post_apply_verification_generation_scope_mismatch".to_string());
    }
    if application_schema_ok
        && evidence_schema_ok
        && evidence_scope["patch_id"] != application["patch_id"]
    {
        failure_reasons.push("post_apply_verification_patch_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let verification_verdict = if ready {
        verification_evidence
            .get("verification_verdict")
            .cloned()
            .unwrap_or(Value::Null)
    } else {
        Value::Null
    };
    let reason = if ready {
        "post_apply_verification_preflight_ready_for_outcome_ingestion_review".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "post_apply_verification_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": application_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_runtime_application_evidence_preflight_verdict": application_preflight
            .get("patch_runtime_application_evidence_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": application_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "post_apply_verification_evidence_schema": verification_evidence.get("schema").cloned().unwrap_or(Value::Null),
        "post_apply_verification_preflight_verdict": if ready { "ready_for_outcome_ingestion_review" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_post_apply_verification_preflight_guardrails(),
        "post_apply_verification": {
            "verification_id": if ready { verification_evidence.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { evidence_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { evidence_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { evidence_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { evidence_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { evidence_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { evidence_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_verdict": verification_verdict,
            "verification_reason": if ready { verification_evidence.get("verification_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "expected_effect_checked": ready,
            "expected_effect_passed": if ready { verification_evidence.get("expected_effect_passed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "presentation_readback_checked": ready,
            "presentation_readback_consistent": if ready { verification_evidence.get("presentation_readback_consistent").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "failed_clause_ids": if ready { verification_evidence.get("failed_clause_ids").cloned().unwrap_or(json!([])) } else { Value::Null },
            "ready_for_outcome_ingestion_review": ready,
            "post_apply_verification_performed_by_this_tool": false,
            "outcome_ingestion_allowed": false,
            "world_verdict_rewrite_allowed": false,
            "verification_record_persisted_by_this_tool": false
        },
        "next_allowed_gate": if ready { "outcome_ingestion_review" } else { "repair_post_apply_verification_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_post_apply_verification_preflight_only",
            "may_review_outcome_ingestion_after_verification": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_verification_record": true,
            "require_separate_outcome_ingestion_review": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_runtime_application_evidence_preflight": if application_schema_ok { application_preflight } else { Value::Null },
        "post_apply_verification_evidence": if evidence_schema_ok { verification_evidence } else { Value::Null },
        "post_apply_verification_performed_by_this_tool": false,
        "outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure post-apply verification preflight: validates explicit verification evidence without ingesting outcomes, writing state, or rewriting world verdict"
    })
}

pub fn render_interaction_feedback_runtime_executor_post_apply_verification_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Post-Apply Verification Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "post_apply_verification_preflight_verdict",
        &preflight["post_apply_verification_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_runtime_application_evidence_preflight_verdict",
        &preflight["source_runtime_application_evidence_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "post_apply_verification_evidence_schema",
        &preflight["post_apply_verification_evidence_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Post-Apply Verification".to_string());
    lines.push(String::new());
    for key in [
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "verification_verdict",
        "verification_reason",
        "expected_effect_checked",
        "expected_effect_passed",
        "presentation_readback_checked",
        "presentation_readback_consistent",
        "failed_clause_ids",
        "ready_for_outcome_ingestion_review",
        "post_apply_verification_performed_by_this_tool",
        "outcome_ingestion_allowed",
        "world_verdict_rewrite_allowed",
        "verification_record_persisted_by_this_tool",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["post_apply_verification"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_review_outcome_ingestion_after_verification",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_verification_record",
        "require_separate_outcome_ingestion_review",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(
    input: &Value,
) -> Value {
    let (input_kind, verification_preflight, review_decision) =
        extract_runtime_executor_outcome_ingestion_review_preflight_input(input);
    let verification_schema_ok = verification_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_PREFLIGHT_SCHEMA,
        );
    let review_schema_ok = review_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_DECISION_SCHEMA);
    let verification = &verification_preflight["post_apply_verification"];
    let verification_guardrails = &verification_preflight["guardrails"];
    let verification_contract = &verification_preflight["agent_action_contract"];
    let review_scope = &review_decision["source_post_apply_verification_scope"];

    let mut failure_reasons = Vec::new();
    if !verification_schema_ok {
        failure_reasons
            .push("runtime_executor_post_apply_verification_preflight_required".to_string());
    }
    if verification_schema_ok
        && verification_preflight["post_apply_verification_preflight_verdict"]
            != "ready_for_outcome_ingestion_review"
    {
        failure_reasons.push("source_post_apply_verification_preflight_not_ready".to_string());
    }
    if verification_schema_ok && verification_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if verification_schema_ok && verification["verification_verdict"] != "verified" {
        failure_reasons.push("source_post_apply_verification_must_be_verified".to_string());
    }
    if verification_schema_ok && verification["ready_for_outcome_ingestion_review"] != true {
        failure_reasons.push(
            "source_post_apply_verification_not_ready_for_outcome_ingestion_review".to_string(),
        );
    }
    if verification_schema_ok && verification["outcome_ingestion_allowed"] != false {
        failure_reasons.push("source_post_apply_verification_must_not_allow_ingestion".to_string());
    }
    if verification_schema_ok && verification["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push("source_post_apply_verification_must_not_rewrite_verdict".to_string());
    }
    if verification_schema_ok
        && (verification_guardrails["read_only"] != true
            || verification_guardrails["writes_state"] != false
            || verification_guardrails["outcome_ingestion_allowed"] != false
            || verification_guardrails["persists_verification_record"] != false)
    {
        failure_reasons.push("source_post_apply_verification_guardrails_not_read_only".to_string());
    }
    if verification_schema_ok
        && (verification_contract["may_review_outcome_ingestion_after_verification"] != true
            || verification_contract["require_separate_outcome_ingestion_review"] != true
            || verification_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || verification_contract["do_not_ingest_outcome"] != true
            || verification_contract["do_not_write_memory"] != true
            || verification_contract["do_not_rewrite_world_verdict"] != true
            || verification_contract["do_not_persist_verification_record"] != true)
    {
        failure_reasons.push("source_post_apply_verification_contract_not_protective".to_string());
    }
    if !review_schema_ok {
        failure_reasons.push("explicit_outcome_ingestion_review_decision_required".to_string());
    }
    if review_schema_ok && review_decision["review_id"].as_str().is_none() {
        failure_reasons.push("outcome_ingestion_review_id_required".to_string());
    }
    if review_schema_ok && review_decision["review_kind"] != "outcome_ingestion_review" {
        failure_reasons.push("outcome_ingestion_review_kind_required".to_string());
    }
    if review_schema_ok && review_decision["decision"] != "approved_for_durable_ingestion_gate" {
        failure_reasons.push("outcome_ingestion_review_decision_not_approved".to_string());
    }
    if review_schema_ok && review_decision["source_world_verdict"] != "not_verified" {
        failure_reasons
            .push("outcome_ingestion_review_must_preserve_not_verified_source".to_string());
    }
    if review_schema_ok && review_decision["reviewed_verification_verdict"] != "verified" {
        failure_reasons.push("outcome_ingestion_review_must_review_verified_evidence".to_string());
    }
    if review_schema_ok && review_decision["expected_effect_confirmed_for_ingestion"] != true {
        failure_reasons.push("outcome_ingestion_review_must_confirm_expected_effect".to_string());
    }
    if review_schema_ok && review_decision["presentation_readback_confirmed_for_ingestion"] != true
    {
        failure_reasons
            .push("outcome_ingestion_review_must_confirm_presentation_readback".to_string());
    }
    if review_schema_ok && review_decision["durable_ingestion_allowed"] != false {
        failure_reasons
            .push("outcome_ingestion_review_must_not_allow_durable_ingestion".to_string());
    }
    if review_schema_ok && review_decision["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push("outcome_ingestion_review_must_not_rewrite_verdict".to_string());
    }
    if review_schema_ok && review_decision["outcome_record_persisted"] != false {
        failure_reasons.push("outcome_ingestion_review_must_not_persist_record".to_string());
    }
    if verification_schema_ok
        && review_schema_ok
        && review_scope["verification_id"] != verification["verification_id"]
    {
        failure_reasons.push("outcome_ingestion_review_verification_scope_mismatch".to_string());
    }
    if verification_schema_ok
        && review_schema_ok
        && review_scope["runtime_application_evidence_id"]
            != verification["runtime_application_evidence_id"]
    {
        failure_reasons
            .push("outcome_ingestion_review_application_evidence_scope_mismatch".to_string());
    }
    if verification_schema_ok
        && review_schema_ok
        && review_scope["source_invocation_request_id"]
            != verification["source_invocation_request_id"]
    {
        failure_reasons.push("outcome_ingestion_review_invocation_scope_mismatch".to_string());
    }
    if verification_schema_ok
        && review_schema_ok
        && review_scope["world_id"] != verification["world_id"]
    {
        failure_reasons.push("outcome_ingestion_review_world_scope_mismatch".to_string());
    }
    if verification_schema_ok
        && review_schema_ok
        && review_scope["branch_id"] != verification["branch_id"]
    {
        failure_reasons.push("outcome_ingestion_review_branch_scope_mismatch".to_string());
    }
    if verification_schema_ok
        && review_schema_ok
        && review_scope["runtime_generation"] != verification["runtime_generation"]
    {
        failure_reasons.push("outcome_ingestion_review_generation_scope_mismatch".to_string());
    }
    if verification_schema_ok
        && review_schema_ok
        && review_scope["patch_id"] != verification["patch_id"]
    {
        failure_reasons.push("outcome_ingestion_review_patch_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "outcome_ingestion_review_preflight_ready_for_durable_ingestion_gate".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "outcome_ingestion_review_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": verification_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_post_apply_verification_preflight_verdict": verification_preflight
            .get("post_apply_verification_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": verification_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "outcome_ingestion_review_decision_schema": review_decision.get("schema").cloned().unwrap_or(Value::Null),
        "outcome_ingestion_review_preflight_verdict": if ready { "ready_for_durable_ingestion_gate" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_outcome_ingestion_review_preflight_guardrails(),
        "outcome_ingestion_review": {
            "review_id": if ready { review_decision.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { review_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { review_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { review_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { review_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { review_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { review_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { review_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { review_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_reason": if ready { review_decision.get("review_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "reviewed_verification_verdict": if ready { review_decision.get("reviewed_verification_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "expected_effect_confirmed_for_ingestion": if ready { review_decision.get("expected_effect_confirmed_for_ingestion").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "presentation_readback_confirmed_for_ingestion": if ready { review_decision.get("presentation_readback_confirmed_for_ingestion").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_ingestion_gate": ready,
            "outcome_ingestion_review_performed_by_this_tool": false,
            "durable_ingestion_allowed": false,
            "world_verdict_rewrite_allowed": false,
            "outcome_record_persisted_by_this_tool": false
        },
        "next_allowed_gate": if ready { "durable_outcome_ingestion_gate" } else { "repair_outcome_ingestion_review_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_outcome_ingestion_review_preflight_only",
            "may_review_durable_outcome_ingestion_after_review": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_ingestion_gate": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_post_apply_verification_preflight": if verification_schema_ok { verification_preflight } else { Value::Null },
        "outcome_ingestion_review_decision": if review_schema_ok { review_decision } else { Value::Null },
        "outcome_ingestion_review_performed_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure outcome-ingestion review preflight: validates explicit review decision without durable ingestion, writing state, or rewriting world verdict"
    })
}

pub fn render_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Outcome-Ingestion Review Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "outcome_ingestion_review_preflight_verdict",
        &preflight["outcome_ingestion_review_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_post_apply_verification_preflight_verdict",
        &preflight["source_post_apply_verification_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "outcome_ingestion_review_decision_schema",
        &preflight["outcome_ingestion_review_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Outcome-Ingestion Review".to_string());
    lines.push(String::new());
    for key in [
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision",
        "review_reason",
        "reviewed_verification_verdict",
        "expected_effect_confirmed_for_ingestion",
        "presentation_readback_confirmed_for_ingestion",
        "ready_for_durable_ingestion_gate",
        "outcome_ingestion_review_performed_by_this_tool",
        "durable_ingestion_allowed",
        "world_verdict_rewrite_allowed",
        "outcome_record_persisted_by_this_tool",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["outcome_ingestion_review"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_review_durable_outcome_ingestion_after_review",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_ingestion_gate",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(
    input: &Value,
) -> Value {
    let (input_kind, review_preflight, gate_decision) =
        extract_runtime_executor_durable_outcome_ingestion_gate_preflight_input(input);
    let review_schema_ok = review_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_SCHEMA,
        );
    let gate_schema_ok = gate_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_DECISION_SCHEMA);
    let review = &review_preflight["outcome_ingestion_review"];
    let review_guardrails = &review_preflight["guardrails"];
    let review_contract = &review_preflight["agent_action_contract"];
    let gate_scope = &gate_decision["source_outcome_ingestion_review_scope"];

    let mut failure_reasons = Vec::new();
    if !review_schema_ok {
        failure_reasons
            .push("runtime_executor_outcome_ingestion_review_preflight_required".to_string());
    }
    if review_schema_ok
        && review_preflight["outcome_ingestion_review_preflight_verdict"]
            != "ready_for_durable_ingestion_gate"
    {
        failure_reasons.push("source_outcome_ingestion_review_preflight_not_ready".to_string());
    }
    if review_schema_ok && review_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if review_schema_ok && review["decision"] != "approved_for_durable_ingestion_gate" {
        failure_reasons.push("source_outcome_ingestion_review_decision_not_approved".to_string());
    }
    if review_schema_ok && review["ready_for_durable_ingestion_gate"] != true {
        failure_reasons.push("source_outcome_ingestion_review_not_ready_for_gate".to_string());
    }
    if review_schema_ok && review["durable_ingestion_allowed"] != false {
        failure_reasons
            .push("source_outcome_ingestion_review_must_not_allow_ingestion".to_string());
    }
    if review_schema_ok && review["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("source_outcome_ingestion_review_must_not_rewrite_verdict".to_string());
    }
    if review_schema_ok
        && (review_guardrails["read_only"] != true
            || review_guardrails["writes_state"] != false
            || review_guardrails["durable_ingestion_allowed"] != false
            || review_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons
            .push("source_outcome_ingestion_review_guardrails_not_read_only".to_string());
    }
    if review_schema_ok
        && (review_contract["may_review_durable_outcome_ingestion_after_review"] != true
            || review_contract["require_separate_durable_ingestion_gate"] != true
            || review_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || review_contract["do_not_ingest_outcome"] != true
            || review_contract["do_not_write_memory"] != true
            || review_contract["do_not_rewrite_world_verdict"] != true
            || review_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push("source_outcome_ingestion_review_contract_not_protective".to_string());
    }
    if !gate_schema_ok {
        failure_reasons
            .push("explicit_durable_outcome_ingestion_gate_decision_required".to_string());
    }
    if gate_schema_ok && gate_decision["gate_id"].as_str().is_none() {
        failure_reasons.push("durable_outcome_ingestion_gate_id_required".to_string());
    }
    if gate_schema_ok && gate_decision["gate_kind"] != "durable_outcome_ingestion_gate" {
        failure_reasons.push("durable_outcome_ingestion_gate_kind_required".to_string());
    }
    if gate_schema_ok && gate_decision["decision"] != "approved_for_durable_ingestion_execution" {
        failure_reasons.push("durable_outcome_ingestion_gate_decision_not_approved".to_string());
    }
    if gate_schema_ok && gate_decision["source_world_verdict"] != "not_verified" {
        failure_reasons
            .push("durable_outcome_ingestion_gate_must_preserve_not_verified_source".to_string());
    }
    if gate_schema_ok
        && gate_decision["reviewed_ingestion_review_decision"]
            != "approved_for_durable_ingestion_gate"
    {
        failure_reasons
            .push("durable_outcome_ingestion_gate_must_review_approved_review".to_string());
    }
    if gate_schema_ok && gate_decision["outcome_payload_complete"] != true {
        failure_reasons
            .push("durable_outcome_ingestion_gate_requires_complete_payload".to_string());
    }
    if gate_schema_ok && gate_decision["idempotency_key"].as_str().is_none() {
        failure_reasons.push("durable_outcome_ingestion_gate_idempotency_key_required".to_string());
    }
    if gate_schema_ok && gate_decision["durable_ingestion_execution_allowed"] != false {
        failure_reasons.push("durable_outcome_ingestion_gate_must_not_allow_execution".to_string());
    }
    if gate_schema_ok && gate_decision["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push("durable_outcome_ingestion_gate_must_not_rewrite_verdict".to_string());
    }
    if gate_schema_ok && gate_decision["outcome_record_persisted"] != false {
        failure_reasons.push("durable_outcome_ingestion_gate_must_not_persist_record".to_string());
    }
    if review_schema_ok && gate_schema_ok && gate_scope["review_id"] != review["review_id"] {
        failure_reasons.push("durable_outcome_ingestion_gate_review_scope_mismatch".to_string());
    }
    if review_schema_ok
        && gate_schema_ok
        && gate_scope["verification_id"] != review["verification_id"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_gate_verification_scope_mismatch".to_string());
    }
    if review_schema_ok
        && gate_schema_ok
        && gate_scope["runtime_application_evidence_id"]
            != review["runtime_application_evidence_id"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_gate_application_evidence_scope_mismatch".to_string());
    }
    if review_schema_ok
        && gate_schema_ok
        && gate_scope["source_invocation_request_id"] != review["source_invocation_request_id"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_gate_invocation_scope_mismatch".to_string());
    }
    if review_schema_ok && gate_schema_ok && gate_scope["world_id"] != review["world_id"] {
        failure_reasons.push("durable_outcome_ingestion_gate_world_scope_mismatch".to_string());
    }
    if review_schema_ok && gate_schema_ok && gate_scope["branch_id"] != review["branch_id"] {
        failure_reasons.push("durable_outcome_ingestion_gate_branch_scope_mismatch".to_string());
    }
    if review_schema_ok
        && gate_schema_ok
        && gate_scope["runtime_generation"] != review["runtime_generation"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_gate_generation_scope_mismatch".to_string());
    }
    if review_schema_ok && gate_schema_ok && gate_scope["patch_id"] != review["patch_id"] {
        failure_reasons.push("durable_outcome_ingestion_gate_patch_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_ingestion_gate_preflight_ready_for_execution".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "durable_outcome_ingestion_gate_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": review_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_outcome_ingestion_review_preflight_verdict": review_preflight
            .get("outcome_ingestion_review_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": review_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_ingestion_gate_decision_schema": gate_decision.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_ingestion_gate_preflight_verdict": if ready { "ready_for_durable_outcome_ingestion_execution" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_ingestion_gate_preflight_guardrails(),
        "durable_outcome_ingestion_gate": {
            "gate_id": if ready { gate_decision.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { gate_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { gate_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { gate_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { gate_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { gate_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { gate_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { gate_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { gate_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { gate_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_reason": if ready { gate_decision.get("gate_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { gate_decision.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { gate_decision.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { gate_decision.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_complete": if ready { gate_decision.get("outcome_payload_complete").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_outcome_ingestion_execution": ready,
            "durable_outcome_ingestion_gate_performed_by_this_tool": false,
            "durable_ingestion_execution_allowed": false,
            "world_verdict_rewrite_allowed": false,
            "outcome_record_persisted_by_this_tool": false
        },
        "next_allowed_gate": if ready { "durable_outcome_ingestion_execution" } else { "repair_durable_outcome_ingestion_gate_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_ingestion_gate_preflight_only",
            "may_execute_durable_outcome_ingestion_after_gate": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_ingestion_execution": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_outcome_ingestion_review_preflight": if review_schema_ok { review_preflight } else { Value::Null },
        "durable_outcome_ingestion_gate_decision": if gate_schema_ok { gate_decision } else { Value::Null },
        "durable_outcome_ingestion_gate_performed_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome-ingestion gate preflight: validates explicit gate decision without durable ingestion, writing state, or rewriting world verdict"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome-Ingestion Gate Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_ingestion_gate_preflight_verdict",
        &preflight["durable_outcome_ingestion_gate_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_outcome_ingestion_review_preflight_verdict",
        &preflight["source_outcome_ingestion_review_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_ingestion_gate_decision_schema",
        &preflight["durable_outcome_ingestion_gate_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome-Ingestion Gate".to_string());
    lines.push(String::new());
    for key in [
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision",
        "gate_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_complete",
        "ready_for_durable_outcome_ingestion_execution",
        "durable_outcome_ingestion_gate_performed_by_this_tool",
        "durable_ingestion_execution_allowed",
        "world_verdict_rewrite_allowed",
        "outcome_record_persisted_by_this_tool",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_ingestion_gate"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_execute_durable_outcome_ingestion_after_gate",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_ingestion_execution",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
    input: &Value,
) -> Value {
    let (input_kind, gate_preflight, execution_decision) =
        extract_runtime_executor_durable_outcome_ingestion_execution_preflight_input(input);
    let gate_schema_ok = gate_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA,
        );
    let execution_schema_ok = execution_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA);
    let gate = &gate_preflight["durable_outcome_ingestion_gate"];
    let gate_guardrails = &gate_preflight["guardrails"];
    let gate_contract = &gate_preflight["agent_action_contract"];
    let execution_scope = &execution_decision["source_durable_outcome_ingestion_gate_scope"];

    let mut failure_reasons = Vec::new();
    if !gate_schema_ok {
        failure_reasons
            .push("runtime_executor_durable_outcome_ingestion_gate_preflight_required".to_string());
    }
    if gate_schema_ok
        && gate_preflight["durable_outcome_ingestion_gate_preflight_verdict"]
            != "ready_for_durable_outcome_ingestion_execution"
    {
        failure_reasons
            .push("source_durable_outcome_ingestion_gate_preflight_not_ready".to_string());
    }
    if gate_schema_ok && gate_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if gate_schema_ok && gate["decision"] != "approved_for_durable_ingestion_execution" {
        failure_reasons
            .push("source_durable_outcome_ingestion_gate_decision_not_approved".to_string());
    }
    if gate_schema_ok && gate["ready_for_durable_outcome_ingestion_execution"] != true {
        failure_reasons
            .push("source_durable_outcome_ingestion_gate_not_ready_for_execution".to_string());
    }
    if gate_schema_ok && gate["durable_ingestion_execution_allowed"] != false {
        failure_reasons
            .push("source_durable_outcome_ingestion_gate_must_not_allow_execution".to_string());
    }
    if gate_schema_ok && gate["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("source_durable_outcome_ingestion_gate_must_not_rewrite_verdict".to_string());
    }
    if gate_schema_ok && gate["outcome_record_persisted_by_this_tool"] != false {
        failure_reasons
            .push("source_durable_outcome_ingestion_gate_must_not_persist_record".to_string());
    }
    if gate_schema_ok
        && (gate_guardrails["read_only"] != true
            || gate_guardrails["writes_state"] != false
            || gate_guardrails["durable_ingestion_execution_allowed"] != false
            || gate_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons
            .push("source_durable_outcome_ingestion_gate_guardrails_not_read_only".to_string());
    }
    if gate_schema_ok
        && (gate_contract["may_execute_durable_outcome_ingestion_after_gate"] != true
            || gate_contract["require_separate_durable_ingestion_execution"] != true
            || gate_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || gate_contract["do_not_ingest_outcome"] != true
            || gate_contract["do_not_write_memory"] != true
            || gate_contract["do_not_rewrite_world_verdict"] != true
            || gate_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons
            .push("source_durable_outcome_ingestion_gate_contract_not_protective".to_string());
    }
    if !execution_schema_ok {
        failure_reasons
            .push("explicit_durable_outcome_ingestion_execution_decision_required".to_string());
    }
    if execution_schema_ok && execution_decision["execution_id"].as_str().is_none() {
        failure_reasons.push("durable_outcome_ingestion_execution_id_required".to_string());
    }
    if execution_schema_ok
        && execution_decision["execution_kind"] != "durable_outcome_ingestion_execution"
    {
        failure_reasons.push("durable_outcome_ingestion_execution_kind_required".to_string());
    }
    if execution_schema_ok
        && execution_decision["decision"]
            != "approved_for_durable_outcome_ingestion_write_implementation"
    {
        failure_reasons
            .push("durable_outcome_ingestion_execution_decision_not_approved".to_string());
    }
    if execution_schema_ok && execution_decision["source_world_verdict"] != "not_verified" {
        failure_reasons.push(
            "durable_outcome_ingestion_execution_must_preserve_not_verified_source".to_string(),
        );
    }
    if execution_schema_ok
        && execution_decision["reviewed_gate_decision"]
            != "approved_for_durable_ingestion_execution"
    {
        failure_reasons
            .push("durable_outcome_ingestion_execution_must_review_approved_gate".to_string());
    }
    if execution_schema_ok && execution_decision["outcome_payload_complete"] != true {
        failure_reasons
            .push("durable_outcome_ingestion_execution_requires_complete_payload".to_string());
    }
    if execution_schema_ok && execution_decision["write_plan_complete"] != true {
        failure_reasons
            .push("durable_outcome_ingestion_execution_requires_complete_write_plan".to_string());
    }
    if execution_schema_ok
        && execution_decision["outcome_payload_digest"]
            .as_str()
            .is_none()
    {
        failure_reasons
            .push("durable_outcome_ingestion_execution_payload_digest_required".to_string());
    }
    if execution_schema_ok && execution_decision["write_plan_id"].as_str().is_none() {
        failure_reasons
            .push("durable_outcome_ingestion_execution_write_plan_id_required".to_string());
    }
    if execution_schema_ok && execution_decision["durable_write_implementation_allowed"] != false {
        failure_reasons
            .push("durable_outcome_ingestion_execution_must_not_allow_write".to_string());
    }
    if execution_schema_ok && execution_decision["durable_outcome_ingestion_performed"] != false {
        failure_reasons.push("durable_outcome_ingestion_execution_must_not_ingest".to_string());
    }
    if execution_schema_ok && execution_decision["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("durable_outcome_ingestion_execution_must_not_rewrite_verdict".to_string());
    }
    if execution_schema_ok && execution_decision["outcome_record_persisted"] != false {
        failure_reasons
            .push("durable_outcome_ingestion_execution_must_not_persist_record".to_string());
    }
    if gate_schema_ok && execution_schema_ok && execution_scope["gate_id"] != gate["gate_id"] {
        failure_reasons.push("durable_outcome_ingestion_execution_gate_scope_mismatch".to_string());
    }
    if gate_schema_ok && execution_schema_ok && execution_scope["review_id"] != gate["review_id"] {
        failure_reasons
            .push("durable_outcome_ingestion_execution_review_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && execution_schema_ok
        && execution_scope["verification_id"] != gate["verification_id"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_execution_verification_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && execution_schema_ok
        && execution_scope["runtime_application_evidence_id"]
            != gate["runtime_application_evidence_id"]
    {
        failure_reasons.push(
            "durable_outcome_ingestion_execution_application_evidence_scope_mismatch".to_string(),
        );
    }
    if gate_schema_ok
        && execution_schema_ok
        && execution_scope["source_invocation_request_id"] != gate["source_invocation_request_id"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_execution_invocation_scope_mismatch".to_string());
    }
    if gate_schema_ok && execution_schema_ok && execution_scope["world_id"] != gate["world_id"] {
        failure_reasons
            .push("durable_outcome_ingestion_execution_world_scope_mismatch".to_string());
    }
    if gate_schema_ok && execution_schema_ok && execution_scope["branch_id"] != gate["branch_id"] {
        failure_reasons
            .push("durable_outcome_ingestion_execution_branch_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && execution_schema_ok
        && execution_scope["runtime_generation"] != gate["runtime_generation"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_execution_generation_scope_mismatch".to_string());
    }
    if gate_schema_ok && execution_schema_ok && execution_scope["patch_id"] != gate["patch_id"] {
        failure_reasons
            .push("durable_outcome_ingestion_execution_patch_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && execution_schema_ok
        && execution_scope["outcome_record_candidate_id"] != gate["outcome_record_candidate_id"]
    {
        failure_reasons.push(
            "durable_outcome_ingestion_execution_outcome_candidate_scope_mismatch".to_string(),
        );
    }
    if gate_schema_ok
        && execution_schema_ok
        && execution_scope["outcome_record_schema"] != gate["outcome_record_schema"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_execution_outcome_schema_scope_mismatch".to_string());
    }
    if gate_schema_ok
        && execution_schema_ok
        && execution_scope["idempotency_key"] != gate["idempotency_key"]
    {
        failure_reasons
            .push("durable_outcome_ingestion_execution_idempotency_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_ingestion_execution_preflight_ready_for_write_implementation".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "durable_outcome_ingestion_execution_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": gate_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_ingestion_gate_preflight_verdict": gate_preflight
            .get("durable_outcome_ingestion_gate_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": gate_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_ingestion_execution_decision_schema": execution_decision.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_ingestion_execution_preflight_verdict": if ready { "ready_for_durable_outcome_ingestion_write_implementation" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_ingestion_execution_preflight_guardrails(),
        "durable_outcome_ingestion_execution": {
            "execution_id": if ready { execution_decision.get("execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_id": if ready { execution_scope.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { execution_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { execution_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { execution_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { execution_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { execution_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { execution_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { execution_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { execution_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { execution_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_reason": if ready { execution_decision.get("execution_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { execution_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { execution_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { execution_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { execution_decision.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_id": if ready { execution_decision.get("write_plan_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_complete": if ready { execution_decision.get("outcome_payload_complete").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_complete": if ready { execution_decision.get("write_plan_complete").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_outcome_ingestion_write_implementation": ready,
            "durable_write_implementation_allowed": false,
            "durable_outcome_ingestion_performed_by_this_tool": false,
            "world_verdict_rewrite_allowed": false,
            "outcome_record_persisted_by_this_tool": false
        },
        "next_allowed_gate": if ready { "durable_outcome_ingestion_write_implementation" } else { "repair_durable_outcome_ingestion_execution_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_ingestion_execution_preflight_only",
            "may_implement_durable_outcome_write_after_preflight": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_write_implementation": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_durable_outcome_ingestion_gate_preflight": if gate_schema_ok { gate_preflight } else { Value::Null },
        "durable_outcome_ingestion_execution_decision": if execution_schema_ok { execution_decision } else { Value::Null },
        "durable_outcome_ingestion_execution_preflight_performed_by_this_tool": true,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome-ingestion execution preflight: validates explicit execution decision without durable writes, memory/store access, or world verdict rewrite"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome-Ingestion Execution Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_ingestion_execution_preflight_verdict",
        &preflight["durable_outcome_ingestion_execution_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_ingestion_gate_preflight_verdict",
        &preflight["source_durable_outcome_ingestion_gate_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_ingestion_execution_decision_schema",
        &preflight["durable_outcome_ingestion_execution_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome-Ingestion Execution".to_string());
    lines.push(String::new());
    for key in [
        "execution_id",
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision",
        "execution_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "write_plan_id",
        "outcome_payload_complete",
        "write_plan_complete",
        "ready_for_durable_outcome_ingestion_write_implementation",
        "durable_write_implementation_allowed",
        "durable_outcome_ingestion_performed_by_this_tool",
        "world_verdict_rewrite_allowed",
        "outcome_record_persisted_by_this_tool",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_ingestion_execution"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_implement_durable_outcome_write_after_preflight",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_write_implementation",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
    input: &Value,
) -> Value {
    let (input_kind, execution_preflight, write_decision) =
        extract_runtime_executor_durable_outcome_write_implementation_preflight_input(input);
    let execution_schema_ok = execution_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
        );
    let write_schema_ok = write_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_DECISION_SCHEMA);
    let execution = &execution_preflight["durable_outcome_ingestion_execution"];
    let execution_guardrails = &execution_preflight["guardrails"];
    let execution_contract = &execution_preflight["agent_action_contract"];
    let write_scope = &write_decision["source_durable_outcome_ingestion_execution_scope"];

    let mut failure_reasons = Vec::new();
    if !execution_schema_ok {
        failure_reasons.push(
            "runtime_executor_durable_outcome_ingestion_execution_preflight_required".to_string(),
        );
    }
    if execution_schema_ok
        && execution_preflight["durable_outcome_ingestion_execution_preflight_verdict"]
            != "ready_for_durable_outcome_ingestion_write_implementation"
    {
        failure_reasons
            .push("source_durable_outcome_ingestion_execution_preflight_not_ready".to_string());
    }
    if execution_schema_ok && execution_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if execution_schema_ok
        && execution["decision"] != "approved_for_durable_outcome_ingestion_write_implementation"
    {
        failure_reasons
            .push("source_durable_outcome_ingestion_execution_decision_not_approved".to_string());
    }
    if execution_schema_ok
        && execution["ready_for_durable_outcome_ingestion_write_implementation"] != true
    {
        failure_reasons
            .push("source_durable_outcome_ingestion_execution_not_ready_for_write".to_string());
    }
    if execution_schema_ok && execution["durable_write_implementation_allowed"] != false {
        failure_reasons
            .push("source_durable_outcome_ingestion_execution_must_not_allow_write".to_string());
    }
    if execution_schema_ok && execution["durable_outcome_ingestion_performed_by_this_tool"] != false
    {
        failure_reasons
            .push("source_durable_outcome_ingestion_execution_must_not_ingest".to_string());
    }
    if execution_schema_ok && execution["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_ingestion_execution_must_not_rewrite_verdict".to_string(),
        );
    }
    if execution_schema_ok && execution["outcome_record_persisted_by_this_tool"] != false {
        failure_reasons
            .push("source_durable_outcome_ingestion_execution_must_not_persist_record".to_string());
    }
    if execution_schema_ok
        && (execution_guardrails["read_only"] != true
            || execution_guardrails["writes_state"] != false
            || execution_guardrails["durable_write_implementation_allowed"] != false
            || execution_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push(
            "source_durable_outcome_ingestion_execution_guardrails_not_read_only".to_string(),
        );
    }
    if execution_schema_ok
        && (execution_contract["may_implement_durable_outcome_write_after_preflight"] != true
            || execution_contract["require_separate_durable_write_implementation"] != true
            || execution_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || execution_contract["do_not_ingest_outcome"] != true
            || execution_contract["do_not_write_memory"] != true
            || execution_contract["do_not_rewrite_world_verdict"] != true
            || execution_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons
            .push("source_durable_outcome_ingestion_execution_contract_not_protective".to_string());
    }
    if !write_schema_ok {
        failure_reasons
            .push("explicit_durable_outcome_write_implementation_decision_required".to_string());
    }
    if write_schema_ok && write_decision["write_implementation_id"].as_str().is_none() {
        failure_reasons.push("durable_outcome_write_implementation_id_required".to_string());
    }
    if write_schema_ok
        && write_decision["write_implementation_kind"] != "durable_outcome_write_implementation"
    {
        failure_reasons.push("durable_outcome_write_implementation_kind_required".to_string());
    }
    if write_schema_ok && write_decision["decision"] != "approved_for_durable_outcome_record_write"
    {
        failure_reasons
            .push("durable_outcome_write_implementation_decision_not_approved".to_string());
    }
    if write_schema_ok && write_decision["source_world_verdict"] != "not_verified" {
        failure_reasons.push(
            "durable_outcome_write_implementation_must_preserve_not_verified_source".to_string(),
        );
    }
    if write_schema_ok
        && write_decision["reviewed_execution_decision"]
            != "approved_for_durable_outcome_ingestion_write_implementation"
    {
        failure_reasons.push(
            "durable_outcome_write_implementation_must_review_approved_execution".to_string(),
        );
    }
    if write_schema_ok && write_decision["outcome_record_write_plan_complete"] != true {
        failure_reasons
            .push("durable_outcome_write_implementation_requires_complete_write_plan".to_string());
    }
    if write_schema_ok && write_decision["write_idempotency_confirmed"] != true {
        failure_reasons.push(
            "durable_outcome_write_implementation_requires_idempotency_confirmation".to_string(),
        );
    }
    if write_schema_ok && write_decision["write_destination"].as_str().is_none() {
        failure_reasons
            .push("durable_outcome_write_implementation_destination_required".to_string());
    }
    if write_schema_ok && write_decision["durable_record_write_allowed"] != false {
        failure_reasons
            .push("durable_outcome_write_implementation_must_not_allow_record_write".to_string());
    }
    if write_schema_ok && write_decision["durable_outcome_record_written"] != false {
        failure_reasons
            .push("durable_outcome_write_implementation_must_not_write_record".to_string());
    }
    if write_schema_ok && write_decision["memory_write_allowed"] != false {
        failure_reasons
            .push("durable_outcome_write_implementation_must_not_allow_memory_write".to_string());
    }
    if write_schema_ok && write_decision["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("durable_outcome_write_implementation_must_not_rewrite_verdict".to_string());
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["execution_id"] != execution["execution_id"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_execution_scope_mismatch".to_string());
    }
    if execution_schema_ok && write_schema_ok && write_scope["gate_id"] != execution["gate_id"] {
        failure_reasons
            .push("durable_outcome_write_implementation_gate_scope_mismatch".to_string());
    }
    if execution_schema_ok && write_schema_ok && write_scope["review_id"] != execution["review_id"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_review_scope_mismatch".to_string());
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["verification_id"] != execution["verification_id"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_verification_scope_mismatch".to_string());
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["runtime_application_evidence_id"]
            != execution["runtime_application_evidence_id"]
    {
        failure_reasons.push(
            "durable_outcome_write_implementation_application_evidence_scope_mismatch".to_string(),
        );
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["source_invocation_request_id"] != execution["source_invocation_request_id"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_invocation_scope_mismatch".to_string());
    }
    if execution_schema_ok && write_schema_ok && write_scope["world_id"] != execution["world_id"] {
        failure_reasons
            .push("durable_outcome_write_implementation_world_scope_mismatch".to_string());
    }
    if execution_schema_ok && write_schema_ok && write_scope["branch_id"] != execution["branch_id"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_branch_scope_mismatch".to_string());
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["runtime_generation"] != execution["runtime_generation"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_generation_scope_mismatch".to_string());
    }
    if execution_schema_ok && write_schema_ok && write_scope["patch_id"] != execution["patch_id"] {
        failure_reasons
            .push("durable_outcome_write_implementation_patch_scope_mismatch".to_string());
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["outcome_record_candidate_id"] != execution["outcome_record_candidate_id"]
    {
        failure_reasons.push(
            "durable_outcome_write_implementation_outcome_candidate_scope_mismatch".to_string(),
        );
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["outcome_record_schema"] != execution["outcome_record_schema"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_outcome_schema_scope_mismatch".to_string());
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["idempotency_key"] != execution["idempotency_key"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_idempotency_scope_mismatch".to_string());
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["outcome_payload_digest"] != execution["outcome_payload_digest"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_payload_digest_scope_mismatch".to_string());
    }
    if execution_schema_ok
        && write_schema_ok
        && write_scope["write_plan_id"] != execution["write_plan_id"]
    {
        failure_reasons
            .push("durable_outcome_write_implementation_write_plan_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_write_implementation_preflight_ready_for_record_write".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "durable_outcome_write_implementation_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": execution_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_ingestion_execution_preflight_verdict": execution_preflight
            .get("durable_outcome_ingestion_execution_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": execution_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_write_implementation_decision_schema": write_decision.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_write_implementation_preflight_verdict": if ready { "ready_for_durable_outcome_record_write" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_write_implementation_preflight_guardrails(),
        "durable_outcome_write_implementation": {
            "write_implementation_id": if ready { write_decision.get("write_implementation_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_id": if ready { write_scope.get("execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_id": if ready { write_scope.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { write_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { write_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { write_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { write_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { write_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { write_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { write_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { write_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { write_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_reason": if ready { write_decision.get("write_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { write_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { write_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { write_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { write_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_id": if ready { write_scope.get("write_plan_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { write_decision.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_write_plan_complete": if ready { write_decision.get("outcome_record_write_plan_complete").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_idempotency_confirmed": if ready { write_decision.get("write_idempotency_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_outcome_record_write": ready,
            "durable_record_write_allowed": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "next_allowed_gate": if ready { "durable_outcome_record_write" } else { "repair_durable_outcome_write_implementation_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_write_implementation_preflight_only",
            "may_write_durable_outcome_record_after_preflight": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_record_write": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_durable_outcome_ingestion_execution_preflight": if execution_schema_ok { execution_preflight } else { Value::Null },
        "durable_outcome_write_implementation_decision": if write_schema_ok { write_decision } else { Value::Null },
        "durable_outcome_write_implementation_preflight_performed_by_this_tool": true,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome write-implementation preflight: validates explicit record-write implementation decision without durable writes, memory/store access, or world verdict rewrite"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome Write-Implementation Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_write_implementation_preflight_verdict",
        &preflight["durable_outcome_write_implementation_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_ingestion_execution_preflight_verdict",
        &preflight["source_durable_outcome_ingestion_execution_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_write_implementation_decision_schema",
        &preflight["durable_outcome_write_implementation_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome Write Implementation".to_string());
    lines.push(String::new());
    for key in [
        "write_implementation_id",
        "execution_id",
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision",
        "write_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "write_plan_id",
        "write_destination",
        "outcome_record_write_plan_complete",
        "write_idempotency_confirmed",
        "ready_for_durable_outcome_record_write",
        "durable_record_write_allowed",
        "durable_outcome_record_written_by_this_tool",
        "memory_write_allowed",
        "world_verdict_rewrite_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_write_implementation"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_write_durable_outcome_record_after_preflight",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_record_write",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(
    input: &Value,
) -> Value {
    let (input_kind, write_preflight, record_decision) =
        extract_runtime_executor_durable_outcome_record_write_preflight_input(input);
    let write_preflight_schema_ok = write_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_PREFLIGHT_SCHEMA,
        );
    let record_decision_schema_ok = record_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_DECISION_SCHEMA);
    let write_implementation = &write_preflight["durable_outcome_write_implementation"];
    let write_guardrails = &write_preflight["guardrails"];
    let write_contract = &write_preflight["agent_action_contract"];
    let record_scope = &record_decision["source_durable_outcome_write_implementation_scope"];

    let mut failure_reasons = Vec::new();
    if !write_preflight_schema_ok {
        failure_reasons.push(
            "runtime_executor_durable_outcome_write_implementation_preflight_required".to_string(),
        );
    }
    if write_preflight_schema_ok
        && write_preflight["durable_outcome_write_implementation_preflight_verdict"]
            != "ready_for_durable_outcome_record_write"
    {
        failure_reasons
            .push("source_durable_outcome_write_implementation_preflight_not_ready".to_string());
    }
    if write_preflight_schema_ok && write_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if write_preflight_schema_ok
        && write_implementation["decision"] != "approved_for_durable_outcome_record_write"
    {
        failure_reasons
            .push("source_durable_outcome_write_implementation_decision_not_approved".to_string());
    }
    if write_preflight_schema_ok
        && write_implementation["ready_for_durable_outcome_record_write"] != true
    {
        failure_reasons.push(
            "source_durable_outcome_write_implementation_not_ready_for_record_write".to_string(),
        );
    }
    if write_preflight_schema_ok && write_implementation["durable_record_write_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_write_implementation_must_not_allow_record_write".to_string(),
        );
    }
    if write_preflight_schema_ok
        && write_implementation["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons
            .push("source_durable_outcome_write_implementation_must_not_write_record".to_string());
    }
    if write_preflight_schema_ok && write_implementation["memory_write_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_write_implementation_must_not_allow_memory_write".to_string(),
        );
    }
    if write_preflight_schema_ok && write_implementation["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_write_implementation_must_not_rewrite_verdict".to_string(),
        );
    }
    if write_preflight_schema_ok
        && (write_guardrails["read_only"] != true
            || write_guardrails["writes_state"] != false
            || write_guardrails["durable_record_write_allowed"] != false
            || write_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push(
            "source_durable_outcome_write_implementation_guardrails_not_read_only".to_string(),
        );
    }
    if write_preflight_schema_ok
        && (write_contract["may_write_durable_outcome_record_after_preflight"] != true
            || write_contract["require_separate_durable_record_write"] != true
            || write_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || write_contract["do_not_ingest_outcome"] != true
            || write_contract["do_not_write_memory"] != true
            || write_contract["do_not_rewrite_world_verdict"] != true
            || write_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push(
            "source_durable_outcome_write_implementation_contract_not_protective".to_string(),
        );
    }
    if !record_decision_schema_ok {
        failure_reasons.push("explicit_durable_outcome_record_write_decision_required".to_string());
    }
    if record_decision_schema_ok && record_decision["record_write_id"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_write_id_required".to_string());
    }
    if record_decision_schema_ok
        && record_decision["record_write_kind"] != "durable_outcome_record_write"
    {
        failure_reasons.push("durable_outcome_record_write_kind_required".to_string());
    }
    if record_decision_schema_ok
        && record_decision["decision"] != "approved_for_durable_outcome_record_write_execution"
    {
        failure_reasons.push("durable_outcome_record_write_decision_not_approved".to_string());
    }
    if record_decision_schema_ok && record_decision["source_world_verdict"] != "not_verified" {
        failure_reasons
            .push("durable_outcome_record_write_must_preserve_not_verified_source".to_string());
    }
    if record_decision_schema_ok
        && record_decision["reviewed_write_implementation_decision"]
            != "approved_for_durable_outcome_record_write"
    {
        failure_reasons.push(
            "durable_outcome_record_write_must_review_approved_write_implementation".to_string(),
        );
    }
    if record_decision_schema_ok && record_decision["outcome_record_payload_complete"] != true {
        failure_reasons.push("durable_outcome_record_write_requires_complete_payload".to_string());
    }
    if record_decision_schema_ok && record_decision["outcome_record_serialization_verified"] != true
    {
        failure_reasons
            .push("durable_outcome_record_write_requires_serialization_verification".to_string());
    }
    if record_decision_schema_ok && record_decision["write_idempotency_confirmed"] != true {
        failure_reasons
            .push("durable_outcome_record_write_requires_idempotency_confirmation".to_string());
    }
    if record_decision_schema_ok && record_decision["write_destination"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_write_destination_required".to_string());
    }
    if record_decision_schema_ok && record_decision["outcome_record_key"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_write_key_required".to_string());
    }
    if record_decision_schema_ok && record_decision["outcome_record_digest"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_write_digest_required".to_string());
    }
    if record_decision_schema_ok
        && record_decision["durable_record_write_execution_allowed"] != false
    {
        failure_reasons
            .push("durable_outcome_record_write_must_not_allow_write_execution".to_string());
    }
    if record_decision_schema_ok && record_decision["durable_outcome_record_written"] != false {
        failure_reasons.push("durable_outcome_record_write_must_not_write_record".to_string());
    }
    if record_decision_schema_ok && record_decision["memory_write_allowed"] != false {
        failure_reasons
            .push("durable_outcome_record_write_must_not_allow_memory_write".to_string());
    }
    if record_decision_schema_ok && record_decision["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push("durable_outcome_record_write_must_not_rewrite_verdict".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["write_implementation_id"]
            != write_implementation["write_implementation_id"]
    {
        failure_reasons
            .push("durable_outcome_record_write_implementation_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["execution_id"] != write_implementation["execution_id"]
    {
        failure_reasons.push("durable_outcome_record_write_execution_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["gate_id"] != write_implementation["gate_id"]
    {
        failure_reasons.push("durable_outcome_record_write_gate_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["review_id"] != write_implementation["review_id"]
    {
        failure_reasons.push("durable_outcome_record_write_review_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["verification_id"] != write_implementation["verification_id"]
    {
        failure_reasons
            .push("durable_outcome_record_write_verification_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["runtime_application_evidence_id"]
            != write_implementation["runtime_application_evidence_id"]
    {
        failure_reasons
            .push("durable_outcome_record_write_application_evidence_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["source_invocation_request_id"]
            != write_implementation["source_invocation_request_id"]
    {
        failure_reasons.push("durable_outcome_record_write_invocation_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["world_id"] != write_implementation["world_id"]
    {
        failure_reasons.push("durable_outcome_record_write_world_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["branch_id"] != write_implementation["branch_id"]
    {
        failure_reasons.push("durable_outcome_record_write_branch_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["runtime_generation"] != write_implementation["runtime_generation"]
    {
        failure_reasons.push("durable_outcome_record_write_generation_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["patch_id"] != write_implementation["patch_id"]
    {
        failure_reasons.push("durable_outcome_record_write_patch_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["outcome_record_candidate_id"]
            != write_implementation["outcome_record_candidate_id"]
    {
        failure_reasons
            .push("durable_outcome_record_write_outcome_candidate_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["outcome_record_schema"] != write_implementation["outcome_record_schema"]
    {
        failure_reasons
            .push("durable_outcome_record_write_outcome_schema_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["idempotency_key"] != write_implementation["idempotency_key"]
    {
        failure_reasons.push("durable_outcome_record_write_idempotency_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["outcome_payload_digest"] != write_implementation["outcome_payload_digest"]
    {
        failure_reasons
            .push("durable_outcome_record_write_payload_digest_scope_mismatch".to_string());
    }
    if write_preflight_schema_ok
        && record_decision_schema_ok
        && record_scope["write_plan_id"] != write_implementation["write_plan_id"]
    {
        failure_reasons.push("durable_outcome_record_write_write_plan_scope_mismatch".to_string());
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_record_write_preflight_ready_for_write_execution".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "durable_outcome_record_write_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": write_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_write_implementation_preflight_verdict": write_preflight
            .get("durable_outcome_write_implementation_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": write_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_record_write_decision_schema": record_decision.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_record_write_preflight_verdict": if ready { "ready_for_durable_outcome_record_write_execution" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_record_write_preflight_guardrails(),
        "durable_outcome_record_write": {
            "record_write_id": if ready { record_decision.get("record_write_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_implementation_id": if ready { record_scope.get("write_implementation_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_id": if ready { record_scope.get("execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_id": if ready { record_scope.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { record_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { record_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { record_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { record_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { record_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { record_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { record_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { record_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { record_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_reason": if ready { record_decision.get("record_write_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { record_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { record_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { record_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { record_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_id": if ready { record_scope.get("write_plan_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { record_decision.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { record_decision.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { record_decision.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_payload_complete": if ready { record_decision.get("outcome_record_payload_complete").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_serialization_verified": if ready { record_decision.get("outcome_record_serialization_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_idempotency_confirmed": if ready { record_decision.get("write_idempotency_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_outcome_record_write_execution": ready,
            "durable_record_write_execution_allowed": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "next_allowed_gate": if ready { "durable_outcome_record_write_execution" } else { "repair_durable_outcome_record_write_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_write_preflight_only",
            "may_execute_durable_outcome_record_write_after_preflight": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_record_write_execution": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_durable_outcome_write_implementation_preflight": if write_preflight_schema_ok { write_preflight } else { Value::Null },
        "durable_outcome_record_write_decision": if record_decision_schema_ok { record_decision } else { Value::Null },
        "durable_outcome_record_write_preflight_performed_by_this_tool": true,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome record-write preflight: validates explicit record write decision without durable writes, memory/store access, or world verdict rewrite"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome Record-Write Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_write_preflight_verdict",
        &preflight["durable_outcome_record_write_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_write_implementation_preflight_verdict",
        &preflight["source_durable_outcome_write_implementation_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_write_decision_schema",
        &preflight["durable_outcome_record_write_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome Record Write".to_string());
    lines.push(String::new());
    for key in [
        "record_write_id",
        "write_implementation_id",
        "execution_id",
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision",
        "record_write_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "write_plan_id",
        "write_destination",
        "outcome_record_key",
        "outcome_record_digest",
        "outcome_record_payload_complete",
        "outcome_record_serialization_verified",
        "write_idempotency_confirmed",
        "ready_for_durable_outcome_record_write_execution",
        "durable_record_write_execution_allowed",
        "durable_outcome_record_written_by_this_tool",
        "memory_write_allowed",
        "world_verdict_rewrite_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_record_write"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_execute_durable_outcome_record_write_after_preflight",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_record_write_execution",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
    input: &Value,
) -> Value {
    let (input_kind, record_preflight, execution_decision) =
        extract_runtime_executor_durable_outcome_record_write_execution_preflight_input(input);
    let record_preflight_schema_ok = record_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_PREFLIGHT_SCHEMA,
        );
    let execution_decision_schema_ok = execution_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_DECISION_SCHEMA);
    let record_write = &record_preflight["durable_outcome_record_write"];
    let record_guardrails = &record_preflight["guardrails"];
    let record_contract = &record_preflight["agent_action_contract"];
    let execution_scope = &execution_decision["source_durable_outcome_record_write_scope"];

    let mut failure_reasons = Vec::new();
    if !record_preflight_schema_ok {
        failure_reasons
            .push("runtime_executor_durable_outcome_record_write_preflight_required".to_string());
    }
    if record_preflight_schema_ok
        && record_preflight["durable_outcome_record_write_preflight_verdict"]
            != "ready_for_durable_outcome_record_write_execution"
    {
        failure_reasons.push("source_durable_outcome_record_write_preflight_not_ready".to_string());
    }
    if record_preflight_schema_ok && record_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if record_preflight_schema_ok
        && record_write["decision"] != "approved_for_durable_outcome_record_write_execution"
    {
        failure_reasons
            .push("source_durable_outcome_record_write_decision_not_approved".to_string());
    }
    if record_preflight_schema_ok
        && record_write["ready_for_durable_outcome_record_write_execution"] != true
    {
        failure_reasons
            .push("source_durable_outcome_record_write_not_ready_for_execution".to_string());
    }
    if record_preflight_schema_ok && record_write["durable_record_write_execution_allowed"] != false
    {
        failure_reasons
            .push("source_durable_outcome_record_write_must_not_allow_execution".to_string());
    }
    if record_preflight_schema_ok
        && record_write["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons
            .push("source_durable_outcome_record_write_must_not_write_record".to_string());
    }
    if record_preflight_schema_ok && record_write["memory_write_allowed"] != false {
        failure_reasons
            .push("source_durable_outcome_record_write_must_not_allow_memory_write".to_string());
    }
    if record_preflight_schema_ok && record_write["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("source_durable_outcome_record_write_must_not_rewrite_verdict".to_string());
    }
    if record_preflight_schema_ok
        && (record_guardrails["read_only"] != true
            || record_guardrails["writes_state"] != false
            || record_guardrails["durable_record_write_execution_allowed"] != false
            || record_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons
            .push("source_durable_outcome_record_write_guardrails_not_read_only".to_string());
    }
    if record_preflight_schema_ok
        && (record_contract["may_execute_durable_outcome_record_write_after_preflight"] != true
            || record_contract["require_separate_durable_record_write_execution"] != true
            || record_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || record_contract["do_not_ingest_outcome"] != true
            || record_contract["do_not_write_memory"] != true
            || record_contract["do_not_rewrite_world_verdict"] != true
            || record_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons
            .push("source_durable_outcome_record_write_contract_not_protective".to_string());
    }
    if !execution_decision_schema_ok {
        failure_reasons
            .push("explicit_durable_outcome_record_write_execution_decision_required".to_string());
    }
    if execution_decision_schema_ok
        && execution_decision["record_write_execution_id"]
            .as_str()
            .is_none()
    {
        failure_reasons.push("durable_outcome_record_write_execution_id_required".to_string());
    }
    if execution_decision_schema_ok
        && execution_decision["record_write_execution_kind"]
            != "durable_outcome_record_write_execution"
    {
        failure_reasons.push("durable_outcome_record_write_execution_kind_required".to_string());
    }
    if execution_decision_schema_ok
        && execution_decision["decision"] != "approved_for_durable_outcome_record_persistence"
    {
        failure_reasons
            .push("durable_outcome_record_write_execution_decision_not_approved".to_string());
    }
    if execution_decision_schema_ok && execution_decision["source_world_verdict"] != "not_verified"
    {
        failure_reasons.push(
            "durable_outcome_record_write_execution_must_preserve_not_verified_source".to_string(),
        );
    }
    if execution_decision_schema_ok
        && execution_decision["reviewed_record_write_decision"]
            != "approved_for_durable_outcome_record_write_execution"
    {
        failure_reasons.push(
            "durable_outcome_record_write_execution_must_review_approved_record_write".to_string(),
        );
    }
    if execution_decision_schema_ok && execution_decision["write_destination_verified"] != true {
        failure_reasons.push(
            "durable_outcome_record_write_execution_requires_destination_verification".to_string(),
        );
    }
    if execution_decision_schema_ok && execution_decision["outcome_record_digest_verified"] != true
    {
        failure_reasons.push(
            "durable_outcome_record_write_execution_requires_digest_verification".to_string(),
        );
    }
    if execution_decision_schema_ok && execution_decision["idempotent_upsert_confirmed"] != true {
        failure_reasons
            .push("durable_outcome_record_write_execution_requires_idempotent_upsert".to_string());
    }
    if execution_decision_schema_ok && execution_decision["store_transaction_plan_complete"] != true
    {
        failure_reasons
            .push("durable_outcome_record_write_execution_requires_transaction_plan".to_string());
    }
    if execution_decision_schema_ok && execution_decision["write_destination"].as_str().is_none() {
        failure_reasons
            .push("durable_outcome_record_write_execution_destination_required".to_string());
    }
    if execution_decision_schema_ok && execution_decision["outcome_record_key"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_write_execution_key_required".to_string());
    }
    if execution_decision_schema_ok
        && execution_decision["outcome_record_digest"]
            .as_str()
            .is_none()
    {
        failure_reasons.push("durable_outcome_record_write_execution_digest_required".to_string());
    }
    if execution_decision_schema_ok
        && execution_decision["durable_record_persistence_allowed"] != false
    {
        failure_reasons
            .push("durable_outcome_record_write_execution_must_not_allow_persistence".to_string());
    }
    if execution_decision_schema_ok && execution_decision["durable_outcome_record_written"] != false
    {
        failure_reasons
            .push("durable_outcome_record_write_execution_must_not_write_record".to_string());
    }
    if execution_decision_schema_ok && execution_decision["memory_write_allowed"] != false {
        failure_reasons
            .push("durable_outcome_record_write_execution_must_not_allow_memory_write".to_string());
    }
    if execution_decision_schema_ok && execution_decision["world_verdict_rewrite_allowed"] != false
    {
        failure_reasons
            .push("durable_outcome_record_write_execution_must_not_rewrite_verdict".to_string());
    }

    for (scope_key, source_key, reason) in [
        (
            "record_write_id",
            "record_write_id",
            "durable_outcome_record_write_execution_record_write_scope_mismatch",
        ),
        (
            "write_implementation_id",
            "write_implementation_id",
            "durable_outcome_record_write_execution_implementation_scope_mismatch",
        ),
        (
            "execution_id",
            "execution_id",
            "durable_outcome_record_write_execution_ingestion_execution_scope_mismatch",
        ),
        (
            "gate_id",
            "gate_id",
            "durable_outcome_record_write_execution_gate_scope_mismatch",
        ),
        (
            "review_id",
            "review_id",
            "durable_outcome_record_write_execution_review_scope_mismatch",
        ),
        (
            "verification_id",
            "verification_id",
            "durable_outcome_record_write_execution_verification_scope_mismatch",
        ),
        (
            "runtime_application_evidence_id",
            "runtime_application_evidence_id",
            "durable_outcome_record_write_execution_application_evidence_scope_mismatch",
        ),
        (
            "source_invocation_request_id",
            "source_invocation_request_id",
            "durable_outcome_record_write_execution_invocation_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "durable_outcome_record_write_execution_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "durable_outcome_record_write_execution_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "durable_outcome_record_write_execution_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "durable_outcome_record_write_execution_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "durable_outcome_record_write_execution_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "durable_outcome_record_write_execution_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "durable_outcome_record_write_execution_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "durable_outcome_record_write_execution_payload_digest_scope_mismatch",
        ),
        (
            "write_plan_id",
            "write_plan_id",
            "durable_outcome_record_write_execution_write_plan_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "durable_outcome_record_write_execution_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "durable_outcome_record_write_execution_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "durable_outcome_record_write_execution_digest_scope_mismatch",
        ),
    ] {
        if record_preflight_schema_ok
            && execution_decision_schema_ok
            && execution_scope[scope_key] != record_write[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_record_write_execution_preflight_ready_for_persistence".to_string()
    } else {
        failure_reasons.first().cloned().unwrap_or_else(|| {
            "durable_outcome_record_write_execution_preflight_blocked".to_string()
        })
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": record_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_record_write_preflight_verdict": record_preflight
            .get("durable_outcome_record_write_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": record_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_record_write_execution_decision_schema": execution_decision.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_record_write_execution_preflight_verdict": if ready { "ready_for_durable_outcome_record_persistence" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_record_write_execution_preflight_guardrails(),
        "durable_outcome_record_write_execution": {
            "record_write_execution_id": if ready { execution_decision.get("record_write_execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_id": if ready { execution_scope.get("record_write_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_implementation_id": if ready { execution_scope.get("write_implementation_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_id": if ready { execution_scope.get("execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_id": if ready { execution_scope.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { execution_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { execution_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { execution_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { execution_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { execution_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { execution_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { execution_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { execution_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { execution_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_execution_reason": if ready { execution_decision.get("record_write_execution_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { execution_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { execution_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { execution_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { execution_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_id": if ready { execution_scope.get("write_plan_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { execution_decision.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { execution_decision.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { execution_decision.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination_verified": if ready { execution_decision.get("write_destination_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest_verified": if ready { execution_decision.get("outcome_record_digest_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotent_upsert_confirmed": if ready { execution_decision.get("idempotent_upsert_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "store_transaction_plan_complete": if ready { execution_decision.get("store_transaction_plan_complete").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_outcome_record_persistence": ready,
            "durable_record_persistence_allowed": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "next_allowed_gate": if ready { "durable_outcome_record_persistence" } else { "repair_durable_outcome_record_write_execution_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_write_execution_preflight_only",
            "may_persist_durable_outcome_record_after_preflight": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_outcome_record_persistence": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_durable_outcome_record_write_preflight": if record_preflight_schema_ok { record_preflight } else { Value::Null },
        "durable_outcome_record_write_execution_decision": if execution_decision_schema_ok { execution_decision } else { Value::Null },
        "durable_outcome_record_write_execution_preflight_performed_by_this_tool": true,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome record-write execution preflight: validates explicit execution authority without durable persistence, memory/store access, or world verdict rewrite"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome Record-Write Execution Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_write_execution_preflight_verdict",
        &preflight["durable_outcome_record_write_execution_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_record_write_preflight_verdict",
        &preflight["source_durable_outcome_record_write_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_write_execution_decision_schema",
        &preflight["durable_outcome_record_write_execution_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome Record Write Execution".to_string());
    lines.push(String::new());
    for key in [
        "record_write_execution_id",
        "record_write_id",
        "write_implementation_id",
        "execution_id",
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision",
        "record_write_execution_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "write_plan_id",
        "write_destination",
        "outcome_record_key",
        "outcome_record_digest",
        "write_destination_verified",
        "outcome_record_digest_verified",
        "idempotent_upsert_confirmed",
        "store_transaction_plan_complete",
        "ready_for_durable_outcome_record_persistence",
        "durable_record_persistence_allowed",
        "durable_outcome_record_written_by_this_tool",
        "memory_write_allowed",
        "world_verdict_rewrite_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_record_write_execution"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_persist_durable_outcome_record_after_preflight",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_outcome_record_persistence",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
    input: &Value,
) -> Value {
    let (input_kind, execution_preflight, persistence_decision) =
        extract_runtime_executor_durable_outcome_record_persistence_preflight_input(input);
    let execution_preflight_schema_ok = execution_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
        );
    let persistence_decision_schema_ok = persistence_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_DECISION_SCHEMA);
    let record_execution = &execution_preflight["durable_outcome_record_write_execution"];
    let execution_guardrails = &execution_preflight["guardrails"];
    let execution_contract = &execution_preflight["agent_action_contract"];
    let persistence_scope =
        &persistence_decision["source_durable_outcome_record_write_execution_scope"];

    let mut failure_reasons = Vec::new();
    if !execution_preflight_schema_ok {
        failure_reasons.push(
            "runtime_executor_durable_outcome_record_write_execution_preflight_required"
                .to_string(),
        );
    }
    if execution_preflight_schema_ok
        && execution_preflight["durable_outcome_record_write_execution_preflight_verdict"]
            != "ready_for_durable_outcome_record_persistence"
    {
        failure_reasons
            .push("source_durable_outcome_record_write_execution_preflight_not_ready".to_string());
    }
    if execution_preflight_schema_ok
        && execution_preflight["source_world_verdict"] != "not_verified"
    {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if execution_preflight_schema_ok
        && record_execution["decision"] != "approved_for_durable_outcome_record_persistence"
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_execution_decision_not_approved".to_string(),
        );
    }
    if execution_preflight_schema_ok
        && record_execution["ready_for_durable_outcome_record_persistence"] != true
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_execution_not_ready_for_persistence".to_string(),
        );
    }
    if execution_preflight_schema_ok
        && record_execution["durable_record_persistence_allowed"] != false
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_execution_must_not_allow_persistence".to_string(),
        );
    }
    if execution_preflight_schema_ok
        && record_execution["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_execution_must_not_write_record".to_string(),
        );
    }
    if execution_preflight_schema_ok && record_execution["memory_write_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_record_write_execution_must_not_allow_memory_write".to_string(),
        );
    }
    if execution_preflight_schema_ok && record_execution["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_record_write_execution_must_not_rewrite_verdict".to_string(),
        );
    }
    if execution_preflight_schema_ok
        && (execution_guardrails["read_only"] != true
            || execution_guardrails["writes_state"] != false
            || execution_guardrails["durable_record_persistence_allowed"] != false
            || execution_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_execution_guardrails_not_read_only".to_string(),
        );
    }
    if execution_preflight_schema_ok
        && (execution_contract["may_persist_durable_outcome_record_after_preflight"] != true
            || execution_contract["require_separate_durable_outcome_record_persistence"] != true
            || execution_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || execution_contract["do_not_ingest_outcome"] != true
            || execution_contract["do_not_write_memory"] != true
            || execution_contract["do_not_rewrite_world_verdict"] != true
            || execution_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_execution_contract_not_protective".to_string(),
        );
    }
    if !persistence_decision_schema_ok {
        failure_reasons
            .push("explicit_durable_outcome_record_persistence_decision_required".to_string());
    }
    if persistence_decision_schema_ok && persistence_decision["persistence_id"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_persistence_id_required".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["persistence_kind"] != "durable_outcome_record_persistence"
    {
        failure_reasons.push("durable_outcome_record_persistence_kind_required".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["decision"] != "approved_for_durable_outcome_record_store_write"
    {
        failure_reasons
            .push("durable_outcome_record_persistence_decision_not_approved".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["source_world_verdict"] != "not_verified"
    {
        failure_reasons.push(
            "durable_outcome_record_persistence_must_preserve_not_verified_source".to_string(),
        );
    }
    if persistence_decision_schema_ok
        && persistence_decision["reviewed_record_write_execution_decision"]
            != "approved_for_durable_outcome_record_persistence"
    {
        failure_reasons.push(
            "durable_outcome_record_persistence_must_review_approved_record_write_execution"
                .to_string(),
        );
    }
    if persistence_decision_schema_ok && persistence_decision["persistence_target_verified"] != true
    {
        failure_reasons
            .push("durable_outcome_record_persistence_requires_target_verification".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["outcome_record_digest_verified"] != true
    {
        failure_reasons
            .push("durable_outcome_record_persistence_requires_digest_verification".to_string());
    }
    if persistence_decision_schema_ok && persistence_decision["idempotent_upsert_confirmed"] != true
    {
        failure_reasons
            .push("durable_outcome_record_persistence_requires_idempotent_upsert".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["store_transaction_plan_complete"] != true
    {
        failure_reasons
            .push("durable_outcome_record_persistence_requires_transaction_plan".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["write_destination"].as_str().is_none()
    {
        failure_reasons.push("durable_outcome_record_persistence_destination_required".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["outcome_record_key"]
            .as_str()
            .is_none()
    {
        failure_reasons.push("durable_outcome_record_persistence_key_required".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["outcome_record_digest"]
            .as_str()
            .is_none()
    {
        failure_reasons.push("durable_outcome_record_persistence_digest_required".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["durable_store_write_allowed"] != false
    {
        failure_reasons
            .push("durable_outcome_record_persistence_must_not_allow_store_write".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["durable_outcome_record_written"] != false
    {
        failure_reasons
            .push("durable_outcome_record_persistence_must_not_write_record".to_string());
    }
    if persistence_decision_schema_ok && persistence_decision["memory_write_allowed"] != false {
        failure_reasons
            .push("durable_outcome_record_persistence_must_not_allow_memory_write".to_string());
    }
    if persistence_decision_schema_ok
        && persistence_decision["world_verdict_rewrite_allowed"] != false
    {
        failure_reasons
            .push("durable_outcome_record_persistence_must_not_rewrite_verdict".to_string());
    }

    for (scope_key, source_key, reason) in [
        (
            "record_write_execution_id",
            "record_write_execution_id",
            "durable_outcome_record_persistence_execution_scope_mismatch",
        ),
        (
            "record_write_id",
            "record_write_id",
            "durable_outcome_record_persistence_record_write_scope_mismatch",
        ),
        (
            "write_implementation_id",
            "write_implementation_id",
            "durable_outcome_record_persistence_implementation_scope_mismatch",
        ),
        (
            "execution_id",
            "execution_id",
            "durable_outcome_record_persistence_ingestion_execution_scope_mismatch",
        ),
        (
            "gate_id",
            "gate_id",
            "durable_outcome_record_persistence_gate_scope_mismatch",
        ),
        (
            "review_id",
            "review_id",
            "durable_outcome_record_persistence_review_scope_mismatch",
        ),
        (
            "verification_id",
            "verification_id",
            "durable_outcome_record_persistence_verification_scope_mismatch",
        ),
        (
            "runtime_application_evidence_id",
            "runtime_application_evidence_id",
            "durable_outcome_record_persistence_application_evidence_scope_mismatch",
        ),
        (
            "source_invocation_request_id",
            "source_invocation_request_id",
            "durable_outcome_record_persistence_invocation_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "durable_outcome_record_persistence_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "durable_outcome_record_persistence_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "durable_outcome_record_persistence_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "durable_outcome_record_persistence_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "durable_outcome_record_persistence_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "durable_outcome_record_persistence_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "durable_outcome_record_persistence_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "durable_outcome_record_persistence_payload_digest_scope_mismatch",
        ),
        (
            "write_plan_id",
            "write_plan_id",
            "durable_outcome_record_persistence_write_plan_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "durable_outcome_record_persistence_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "durable_outcome_record_persistence_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "durable_outcome_record_persistence_digest_scope_mismatch",
        ),
    ] {
        if execution_preflight_schema_ok
            && persistence_decision_schema_ok
            && persistence_scope[scope_key] != record_execution[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_record_persistence_preflight_ready_for_store_write".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "durable_outcome_record_persistence_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": execution_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_record_write_execution_preflight_verdict": execution_preflight
            .get("durable_outcome_record_write_execution_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": execution_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_record_persistence_decision_schema": persistence_decision.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_record_persistence_preflight_verdict": if ready { "ready_for_durable_outcome_record_store_write" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_record_persistence_preflight_guardrails(),
        "durable_outcome_record_persistence": {
            "persistence_id": if ready { persistence_decision.get("persistence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_execution_id": if ready { persistence_scope.get("record_write_execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_id": if ready { persistence_scope.get("record_write_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_implementation_id": if ready { persistence_scope.get("write_implementation_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_id": if ready { persistence_scope.get("execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_id": if ready { persistence_scope.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { persistence_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { persistence_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { persistence_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { persistence_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { persistence_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { persistence_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { persistence_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { persistence_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { persistence_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persistence_reason": if ready { persistence_decision.get("persistence_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { persistence_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { persistence_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { persistence_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { persistence_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_id": if ready { persistence_scope.get("write_plan_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { persistence_decision.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { persistence_decision.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { persistence_decision.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persistence_target_verified": if ready { persistence_decision.get("persistence_target_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest_verified": if ready { persistence_decision.get("outcome_record_digest_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotent_upsert_confirmed": if ready { persistence_decision.get("idempotent_upsert_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "store_transaction_plan_complete": if ready { persistence_decision.get("store_transaction_plan_complete").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_outcome_record_store_write": ready,
            "durable_store_write_allowed": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "next_allowed_gate": if ready { "durable_outcome_record_store_write" } else { "repair_durable_outcome_record_persistence_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_persistence_preflight_only",
            "may_execute_durable_outcome_record_store_write_after_preflight": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_outcome_record_store_write": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_durable_outcome_record_write_execution_preflight": if execution_preflight_schema_ok { execution_preflight } else { Value::Null },
        "durable_outcome_record_persistence_decision": if persistence_decision_schema_ok { persistence_decision } else { Value::Null },
        "durable_outcome_record_persistence_preflight_performed_by_this_tool": true,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome record persistence preflight: validates explicit persistence authority without durable writes, memory/store access, or world verdict rewrite"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome Record Persistence Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_persistence_preflight_verdict",
        &preflight["durable_outcome_record_persistence_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_record_write_execution_preflight_verdict",
        &preflight["source_durable_outcome_record_write_execution_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_persistence_decision_schema",
        &preflight["durable_outcome_record_persistence_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome Record Persistence".to_string());
    lines.push(String::new());
    for key in [
        "persistence_id",
        "record_write_execution_id",
        "record_write_id",
        "write_implementation_id",
        "execution_id",
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision",
        "persistence_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "write_plan_id",
        "write_destination",
        "outcome_record_key",
        "outcome_record_digest",
        "persistence_target_verified",
        "outcome_record_digest_verified",
        "idempotent_upsert_confirmed",
        "store_transaction_plan_complete",
        "ready_for_durable_outcome_record_store_write",
        "durable_store_write_allowed",
        "durable_outcome_record_written_by_this_tool",
        "memory_write_allowed",
        "world_verdict_rewrite_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_record_persistence"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_execute_durable_outcome_record_store_write_after_preflight",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_outcome_record_store_write",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
    input: &Value,
) -> Value {
    let (input_kind, persistence_preflight, store_write_decision) =
        extract_runtime_executor_durable_outcome_record_store_write_execution_preflight_input(
            input,
        );
    let persistence_preflight_schema_ok = persistence_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_PREFLIGHT_SCHEMA,
        );
    let store_write_decision_schema_ok = store_write_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_DECISION_SCHEMA);
    let persistence = &persistence_preflight["durable_outcome_record_persistence"];
    let persistence_guardrails = &persistence_preflight["guardrails"];
    let persistence_contract = &persistence_preflight["agent_action_contract"];
    let store_write_scope =
        &store_write_decision["source_durable_outcome_record_persistence_scope"];

    let mut failure_reasons = Vec::new();
    if !persistence_preflight_schema_ok {
        failure_reasons.push(
            "runtime_executor_durable_outcome_record_persistence_preflight_required".to_string(),
        );
    }
    if persistence_preflight_schema_ok
        && persistence_preflight["durable_outcome_record_persistence_preflight_verdict"]
            != "ready_for_durable_outcome_record_store_write"
    {
        failure_reasons
            .push("source_durable_outcome_record_persistence_preflight_not_ready".to_string());
    }
    if persistence_preflight_schema_ok
        && persistence_preflight["source_world_verdict"] != "not_verified"
    {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if persistence_preflight_schema_ok
        && persistence["decision"] != "approved_for_durable_outcome_record_store_write"
    {
        failure_reasons
            .push("source_durable_outcome_record_persistence_decision_not_approved".to_string());
    }
    if persistence_preflight_schema_ok
        && persistence["ready_for_durable_outcome_record_store_write"] != true
    {
        failure_reasons.push(
            "source_durable_outcome_record_persistence_not_ready_for_store_write".to_string(),
        );
    }
    if persistence_preflight_schema_ok && persistence["durable_store_write_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_record_persistence_must_not_allow_store_write".to_string(),
        );
    }
    if persistence_preflight_schema_ok
        && persistence["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons
            .push("source_durable_outcome_record_persistence_must_not_write_record".to_string());
    }
    if persistence_preflight_schema_ok && persistence["memory_write_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_record_persistence_must_not_allow_memory_write".to_string(),
        );
    }
    if persistence_preflight_schema_ok && persistence["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("source_durable_outcome_record_persistence_must_not_rewrite_verdict".to_string());
    }
    if persistence_preflight_schema_ok
        && (persistence_guardrails["read_only"] != true
            || persistence_guardrails["writes_state"] != false
            || persistence_guardrails["durable_store_write_allowed"] != false
            || persistence_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons
            .push("source_durable_outcome_record_persistence_guardrails_not_read_only".to_string());
    }
    if persistence_preflight_schema_ok
        && (persistence_contract["may_execute_durable_outcome_record_store_write_after_preflight"]
            != true
            || persistence_contract["require_separate_durable_outcome_record_store_write"] != true
            || persistence_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || persistence_contract["do_not_ingest_outcome"] != true
            || persistence_contract["do_not_write_memory"] != true
            || persistence_contract["do_not_rewrite_world_verdict"] != true
            || persistence_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons
            .push("source_durable_outcome_record_persistence_contract_not_protective".to_string());
    }
    if !store_write_decision_schema_ok {
        failure_reasons.push(
            "explicit_durable_outcome_record_store_write_execution_decision_required".to_string(),
        );
    }
    if store_write_decision_schema_ok
        && store_write_decision["store_write_execution_id"]
            .as_str()
            .is_none()
    {
        failure_reasons
            .push("durable_outcome_record_store_write_execution_id_required".to_string());
    }
    if store_write_decision_schema_ok
        && store_write_decision["store_write_execution_kind"]
            != "durable_outcome_record_store_write_execution"
    {
        failure_reasons
            .push("durable_outcome_record_store_write_execution_kind_required".to_string());
    }
    if store_write_decision_schema_ok
        && store_write_decision["decision"] != "approved_for_durable_outcome_record_write_evidence"
    {
        failure_reasons
            .push("durable_outcome_record_store_write_execution_decision_not_approved".to_string());
    }
    if store_write_decision_schema_ok
        && store_write_decision["source_world_verdict"] != "not_verified"
    {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_must_preserve_not_verified_source"
                .to_string(),
        );
    }
    if store_write_decision_schema_ok
        && store_write_decision["reviewed_persistence_decision"]
            != "approved_for_durable_outcome_record_store_write"
    {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_must_review_approved_persistence"
                .to_string(),
        );
    }
    if store_write_decision_schema_ok && store_write_decision["persistence_target_verified"] != true
    {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_requires_target_verification".to_string(),
        );
    }
    if store_write_decision_schema_ok
        && store_write_decision["outcome_record_digest_verified"] != true
    {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_requires_digest_verification".to_string(),
        );
    }
    if store_write_decision_schema_ok && store_write_decision["idempotent_upsert_confirmed"] != true
    {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_requires_idempotent_upsert".to_string(),
        );
    }
    if store_write_decision_schema_ok
        && store_write_decision["store_transaction_plan_complete"] != true
    {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_requires_transaction_plan".to_string(),
        );
    }
    if store_write_decision_schema_ok
        && store_write_decision["write_destination"].as_str().is_none()
    {
        failure_reasons
            .push("durable_outcome_record_store_write_execution_destination_required".to_string());
    }
    if store_write_decision_schema_ok
        && store_write_decision["outcome_record_key"]
            .as_str()
            .is_none()
    {
        failure_reasons
            .push("durable_outcome_record_store_write_execution_key_required".to_string());
    }
    if store_write_decision_schema_ok
        && store_write_decision["outcome_record_digest"]
            .as_str()
            .is_none()
    {
        failure_reasons
            .push("durable_outcome_record_store_write_execution_digest_required".to_string());
    }
    if store_write_decision_schema_ok
        && store_write_decision["durable_store_write_execution_allowed"] != false
    {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_must_not_allow_execution".to_string(),
        );
    }
    if store_write_decision_schema_ok
        && store_write_decision["durable_outcome_record_written"] != false
    {
        failure_reasons
            .push("durable_outcome_record_store_write_execution_must_not_write_record".to_string());
    }
    if store_write_decision_schema_ok && store_write_decision["memory_write_allowed"] != false {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_must_not_allow_memory_write".to_string(),
        );
    }
    if store_write_decision_schema_ok
        && store_write_decision["world_verdict_rewrite_allowed"] != false
    {
        failure_reasons.push(
            "durable_outcome_record_store_write_execution_must_not_rewrite_verdict".to_string(),
        );
    }

    for (scope_key, source_key, reason) in [
        (
            "persistence_id",
            "persistence_id",
            "durable_outcome_record_store_write_execution_persistence_scope_mismatch",
        ),
        (
            "record_write_execution_id",
            "record_write_execution_id",
            "durable_outcome_record_store_write_execution_record_execution_scope_mismatch",
        ),
        (
            "record_write_id",
            "record_write_id",
            "durable_outcome_record_store_write_execution_record_write_scope_mismatch",
        ),
        (
            "write_implementation_id",
            "write_implementation_id",
            "durable_outcome_record_store_write_execution_implementation_scope_mismatch",
        ),
        (
            "execution_id",
            "execution_id",
            "durable_outcome_record_store_write_execution_ingestion_execution_scope_mismatch",
        ),
        (
            "gate_id",
            "gate_id",
            "durable_outcome_record_store_write_execution_gate_scope_mismatch",
        ),
        (
            "review_id",
            "review_id",
            "durable_outcome_record_store_write_execution_review_scope_mismatch",
        ),
        (
            "verification_id",
            "verification_id",
            "durable_outcome_record_store_write_execution_verification_scope_mismatch",
        ),
        (
            "runtime_application_evidence_id",
            "runtime_application_evidence_id",
            "durable_outcome_record_store_write_execution_application_evidence_scope_mismatch",
        ),
        (
            "source_invocation_request_id",
            "source_invocation_request_id",
            "durable_outcome_record_store_write_execution_invocation_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "durable_outcome_record_store_write_execution_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "durable_outcome_record_store_write_execution_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "durable_outcome_record_store_write_execution_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "durable_outcome_record_store_write_execution_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "durable_outcome_record_store_write_execution_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "durable_outcome_record_store_write_execution_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "durable_outcome_record_store_write_execution_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "durable_outcome_record_store_write_execution_payload_digest_scope_mismatch",
        ),
        (
            "write_plan_id",
            "write_plan_id",
            "durable_outcome_record_store_write_execution_write_plan_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "durable_outcome_record_store_write_execution_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "durable_outcome_record_store_write_execution_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "durable_outcome_record_store_write_execution_digest_scope_mismatch",
        ),
    ] {
        if persistence_preflight_schema_ok
            && store_write_decision_schema_ok
            && store_write_scope[scope_key] != persistence[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_record_store_write_execution_preflight_ready_for_write_evidence"
            .to_string()
    } else {
        failure_reasons.first().cloned().unwrap_or_else(|| {
            "durable_outcome_record_store_write_execution_preflight_blocked".to_string()
        })
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": persistence_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_record_persistence_preflight_verdict": persistence_preflight
            .get("durable_outcome_record_persistence_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": persistence_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_record_store_write_execution_decision_schema": store_write_decision.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_record_store_write_execution_preflight_verdict": if ready { "ready_for_durable_outcome_record_write_evidence" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_record_store_write_execution_preflight_guardrails(),
        "durable_outcome_record_store_write_execution": {
            "store_write_execution_id": if ready { store_write_decision.get("store_write_execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persistence_id": if ready { store_write_scope.get("persistence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_execution_id": if ready { store_write_scope.get("record_write_execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_id": if ready { store_write_scope.get("record_write_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_implementation_id": if ready { store_write_scope.get("write_implementation_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_id": if ready { store_write_scope.get("execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_id": if ready { store_write_scope.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { store_write_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { store_write_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { store_write_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { store_write_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { store_write_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { store_write_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { store_write_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { store_write_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { store_write_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "store_write_execution_reason": if ready { store_write_decision.get("store_write_execution_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { store_write_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { store_write_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { store_write_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { store_write_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_id": if ready { store_write_scope.get("write_plan_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { store_write_decision.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { store_write_decision.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { store_write_decision.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persistence_target_verified": if ready { store_write_decision.get("persistence_target_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest_verified": if ready { store_write_decision.get("outcome_record_digest_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotent_upsert_confirmed": if ready { store_write_decision.get("idempotent_upsert_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "store_transaction_plan_complete": if ready { store_write_decision.get("store_transaction_plan_complete").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_outcome_record_write_evidence": ready,
            "durable_store_write_execution_allowed": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "next_allowed_gate": if ready { "durable_outcome_record_write_evidence" } else { "repair_durable_outcome_record_store_write_execution_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_store_write_execution_preflight_only",
            "may_execute_durable_outcome_record_store_write_after_preflight": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_outcome_record_store_write_execution": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "source_durable_outcome_record_persistence_preflight": if persistence_preflight_schema_ok { persistence_preflight } else { Value::Null },
        "durable_outcome_record_store_write_execution_decision": if store_write_decision_schema_ok { store_write_decision } else { Value::Null },
        "durable_outcome_record_store_write_execution_preflight_performed_by_this_tool": true,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome record store-write execution preflight: validates explicit store-write execution authority without durable writes, memory/store access, or world verdict rewrite"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome Record Store-Write Execution Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_store_write_execution_preflight_verdict",
        &preflight["durable_outcome_record_store_write_execution_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_record_persistence_preflight_verdict",
        &preflight["source_durable_outcome_record_persistence_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_store_write_execution_decision_schema",
        &preflight["durable_outcome_record_store_write_execution_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome Record Store Write Execution".to_string());
    lines.push(String::new());
    for key in [
        "store_write_execution_id",
        "persistence_id",
        "record_write_execution_id",
        "record_write_id",
        "write_implementation_id",
        "execution_id",
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision",
        "store_write_execution_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "write_plan_id",
        "write_destination",
        "outcome_record_key",
        "outcome_record_digest",
        "persistence_target_verified",
        "outcome_record_digest_verified",
        "idempotent_upsert_confirmed",
        "store_transaction_plan_complete",
        "ready_for_durable_outcome_record_write_evidence",
        "durable_store_write_execution_allowed",
        "durable_outcome_record_written_by_this_tool",
        "memory_write_allowed",
        "world_verdict_rewrite_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_record_store_write_execution"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_execute_durable_outcome_record_store_write_after_preflight",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_outcome_record_store_write_execution",
        "require_world_verdict_rewrite_gate_after_ingestion",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
    input: &Value,
) -> Value {
    let (input_kind, store_write_preflight, write_evidence) =
        extract_runtime_executor_durable_outcome_record_write_evidence_preflight_input(input);
    let store_write_preflight_schema_ok = store_write_preflight
        .get("schema")
        .and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
        );
    let write_evidence_schema_ok = write_evidence.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_SCHEMA);
    let store_write = &store_write_preflight["durable_outcome_record_store_write_execution"];
    let store_write_guardrails = &store_write_preflight["guardrails"];
    let store_write_contract = &store_write_preflight["agent_action_contract"];
    let evidence_scope =
        &write_evidence["source_durable_outcome_record_store_write_execution_scope"];

    let mut failure_reasons = Vec::new();
    if !store_write_preflight_schema_ok {
        failure_reasons.push(
            "runtime_executor_durable_outcome_record_store_write_execution_preflight_required"
                .to_string(),
        );
    }
    if store_write_preflight_schema_ok
        && store_write_preflight["durable_outcome_record_store_write_execution_preflight_verdict"]
            != "ready_for_durable_outcome_record_write_evidence"
    {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_preflight_not_ready".to_string(),
        );
    }
    if store_write_preflight_schema_ok
        && store_write_preflight["source_world_verdict"] != "not_verified"
    {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if store_write_preflight_schema_ok
        && store_write["decision"] != "approved_for_durable_outcome_record_write_evidence"
    {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_decision_not_approved".to_string(),
        );
    }
    if store_write_preflight_schema_ok
        && store_write["ready_for_durable_outcome_record_write_evidence"] != true
    {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_not_ready_for_evidence"
                .to_string(),
        );
    }
    if store_write_preflight_schema_ok
        && store_write["durable_store_write_execution_allowed"] != false
    {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_must_not_allow_execution"
                .to_string(),
        );
    }
    if store_write_preflight_schema_ok
        && store_write["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_must_not_write_record".to_string(),
        );
    }
    if store_write_preflight_schema_ok && store_write["memory_write_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_must_not_allow_memory_write"
                .to_string(),
        );
    }
    if store_write_preflight_schema_ok && store_write["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_must_not_rewrite_verdict"
                .to_string(),
        );
    }
    if store_write_preflight_schema_ok
        && (store_write_guardrails["read_only"] != true
            || store_write_guardrails["writes_state"] != false
            || store_write_guardrails["durable_store_write_execution_allowed"] != false
            || store_write_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_guardrails_not_read_only"
                .to_string(),
        );
    }
    if store_write_preflight_schema_ok
        && (store_write_contract["may_execute_durable_outcome_record_store_write_after_preflight"]
            != true
            || store_write_contract["require_separate_durable_outcome_record_store_write_execution"]
                != true
            || store_write_contract["require_world_verdict_rewrite_gate_after_ingestion"] != true
            || store_write_contract["do_not_ingest_outcome"] != true
            || store_write_contract["do_not_write_memory"] != true
            || store_write_contract["do_not_rewrite_world_verdict"] != true
            || store_write_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push(
            "source_durable_outcome_record_store_write_execution_contract_not_protective"
                .to_string(),
        );
    }
    if !write_evidence_schema_ok {
        failure_reasons.push("explicit_durable_outcome_record_write_evidence_required".to_string());
    }
    if write_evidence_schema_ok && write_evidence["write_evidence_id"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_write_evidence_id_required".to_string());
    }
    if write_evidence_schema_ok
        && write_evidence["evidence_kind"] != "durable_outcome_record_write_evidence"
    {
        failure_reasons.push("durable_outcome_record_write_evidence_kind_required".to_string());
    }
    if write_evidence_schema_ok && write_evidence["source_world_verdict"] != "not_verified" {
        failure_reasons.push(
            "durable_outcome_record_write_evidence_must_preserve_not_verified_source".to_string(),
        );
    }
    if write_evidence_schema_ok
        && write_evidence["reviewed_store_write_execution_decision"]
            != "approved_for_durable_outcome_record_write_evidence"
    {
        failure_reasons.push(
            "durable_outcome_record_write_evidence_must_review_approved_store_write_execution"
                .to_string(),
        );
    }
    if write_evidence_schema_ok && write_evidence["durable_outcome_record_write_observed"] != true {
        failure_reasons
            .push("durable_outcome_record_write_evidence_requires_write_observed".to_string());
    }
    if write_evidence_schema_ok && write_evidence["store_write_acknowledged"] != true {
        failure_reasons
            .push("durable_outcome_record_write_evidence_requires_store_ack".to_string());
    }
    if write_evidence_schema_ok && write_evidence["record_readback_verified"] != true {
        failure_reasons.push("durable_outcome_record_write_evidence_requires_readback".to_string());
    }
    if write_evidence_schema_ok && write_evidence["outcome_record_digest_verified"] != true {
        failure_reasons
            .push("durable_outcome_record_write_evidence_requires_digest_verification".to_string());
    }
    if write_evidence_schema_ok && write_evidence["idempotency_key_confirmed"] != true {
        failure_reasons
            .push("durable_outcome_record_write_evidence_requires_idempotency".to_string());
    }
    if write_evidence_schema_ok && write_evidence["write_destination"].as_str().is_none() {
        failure_reasons
            .push("durable_outcome_record_write_evidence_destination_required".to_string());
    }
    if write_evidence_schema_ok && write_evidence["outcome_record_key"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_write_evidence_key_required".to_string());
    }
    if write_evidence_schema_ok && write_evidence["outcome_record_digest"].as_str().is_none() {
        failure_reasons.push("durable_outcome_record_write_evidence_digest_required".to_string());
    }
    if write_evidence_schema_ok
        && write_evidence["persisted_outcome_record_key"] != write_evidence["outcome_record_key"]
    {
        failure_reasons
            .push("durable_outcome_record_write_evidence_persisted_key_mismatch".to_string());
    }
    if write_evidence_schema_ok
        && write_evidence["persisted_outcome_record_digest"]
            != write_evidence["outcome_record_digest"]
    {
        failure_reasons
            .push("durable_outcome_record_write_evidence_persisted_digest_mismatch".to_string());
    }
    if write_evidence_schema_ok
        && write_evidence["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons
            .push("durable_outcome_record_write_evidence_must_not_write_by_this_tool".to_string());
    }
    if write_evidence_schema_ok && write_evidence["memory_write_allowed"] != false {
        failure_reasons
            .push("durable_outcome_record_write_evidence_must_not_allow_memory_write".to_string());
    }
    if write_evidence_schema_ok && write_evidence["outcome_ingestion_allowed"] != false {
        failure_reasons
            .push("durable_outcome_record_write_evidence_must_not_allow_ingestion".to_string());
    }
    if write_evidence_schema_ok && write_evidence["world_verdict_rewrite_allowed"] != false {
        failure_reasons
            .push("durable_outcome_record_write_evidence_must_not_rewrite_verdict".to_string());
    }

    for (scope_key, source_key, reason) in [
        (
            "store_write_execution_id",
            "store_write_execution_id",
            "durable_outcome_record_write_evidence_store_write_execution_scope_mismatch",
        ),
        (
            "persistence_id",
            "persistence_id",
            "durable_outcome_record_write_evidence_persistence_scope_mismatch",
        ),
        (
            "record_write_execution_id",
            "record_write_execution_id",
            "durable_outcome_record_write_evidence_record_execution_scope_mismatch",
        ),
        (
            "record_write_id",
            "record_write_id",
            "durable_outcome_record_write_evidence_record_write_scope_mismatch",
        ),
        (
            "write_implementation_id",
            "write_implementation_id",
            "durable_outcome_record_write_evidence_implementation_scope_mismatch",
        ),
        (
            "execution_id",
            "execution_id",
            "durable_outcome_record_write_evidence_ingestion_execution_scope_mismatch",
        ),
        (
            "gate_id",
            "gate_id",
            "durable_outcome_record_write_evidence_gate_scope_mismatch",
        ),
        (
            "review_id",
            "review_id",
            "durable_outcome_record_write_evidence_review_scope_mismatch",
        ),
        (
            "verification_id",
            "verification_id",
            "durable_outcome_record_write_evidence_verification_scope_mismatch",
        ),
        (
            "runtime_application_evidence_id",
            "runtime_application_evidence_id",
            "durable_outcome_record_write_evidence_application_evidence_scope_mismatch",
        ),
        (
            "source_invocation_request_id",
            "source_invocation_request_id",
            "durable_outcome_record_write_evidence_invocation_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "durable_outcome_record_write_evidence_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "durable_outcome_record_write_evidence_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "durable_outcome_record_write_evidence_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "durable_outcome_record_write_evidence_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "durable_outcome_record_write_evidence_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "durable_outcome_record_write_evidence_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "durable_outcome_record_write_evidence_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "durable_outcome_record_write_evidence_payload_digest_scope_mismatch",
        ),
        (
            "write_plan_id",
            "write_plan_id",
            "durable_outcome_record_write_evidence_write_plan_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "durable_outcome_record_write_evidence_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "durable_outcome_record_write_evidence_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "durable_outcome_record_write_evidence_digest_scope_mismatch",
        ),
    ] {
        if store_write_preflight_schema_ok
            && write_evidence_schema_ok
            && evidence_scope[scope_key] != store_write[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_record_write_evidence_preflight_ready_for_evidence_review".to_string()
    } else {
        failure_reasons.first().cloned().unwrap_or_else(|| {
            "durable_outcome_record_write_evidence_preflight_blocked".to_string()
        })
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": store_write_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_record_store_write_execution_preflight_verdict": store_write_preflight
            .get("durable_outcome_record_store_write_execution_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": store_write_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_record_write_evidence_schema": write_evidence.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_record_write_evidence_preflight_verdict": if ready { "ready_for_durable_outcome_record_write_evidence_review" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_record_write_evidence_preflight_guardrails(),
        "durable_outcome_record_write_evidence": {
            "write_evidence_id": if ready { write_evidence.get("write_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "store_write_execution_id": if ready { evidence_scope.get("store_write_execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persistence_id": if ready { evidence_scope.get("persistence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_execution_id": if ready { evidence_scope.get("record_write_execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_id": if ready { evidence_scope.get("record_write_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_implementation_id": if ready { evidence_scope.get("write_implementation_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_id": if ready { evidence_scope.get("execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_id": if ready { evidence_scope.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { evidence_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { evidence_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { evidence_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { evidence_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { evidence_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { evidence_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { evidence_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { evidence_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "evidence_kind": if ready { write_evidence.get("evidence_kind").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_evidence_reason": if ready { write_evidence.get("write_evidence_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { evidence_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { evidence_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { evidence_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { evidence_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_id": if ready { evidence_scope.get("write_plan_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { write_evidence.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { write_evidence.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { write_evidence.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_key": if ready { write_evidence.get("persisted_outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_digest": if ready { write_evidence.get("persisted_outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "durable_outcome_record_write_observed": if ready { write_evidence.get("durable_outcome_record_write_observed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "store_write_acknowledged": if ready { write_evidence.get("store_write_acknowledged").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_readback_verified": if ready { write_evidence.get("record_readback_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest_verified": if ready { write_evidence.get("outcome_record_digest_verified").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key_confirmed": if ready { write_evidence.get("idempotency_key_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_durable_outcome_record_write_evidence_review": ready,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "next_allowed_gate": if ready { "durable_outcome_record_write_evidence_review" } else { "repair_durable_outcome_record_write_evidence_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_write_evidence_preflight_only",
            "may_review_durable_outcome_record_write_evidence_after_preflight": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_outcome_record_write_evidence_review": true,
            "require_world_verdict_rewrite_gate_after_evidence_review": true
        },
        "source_durable_outcome_record_store_write_execution_preflight": if store_write_preflight_schema_ok { store_write_preflight } else { Value::Null },
        "durable_outcome_record_write_evidence_input": if write_evidence_schema_ok { write_evidence } else { Value::Null },
        "durable_outcome_record_write_evidence_preflight_performed_by_this_tool": true,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome record write-evidence preflight: validates supplied external write evidence without durable writes, memory/store access, ingestion, or world verdict rewrite"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome Record Write Evidence Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_write_evidence_preflight_verdict",
        &preflight["durable_outcome_record_write_evidence_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_record_store_write_execution_preflight_verdict",
        &preflight["source_durable_outcome_record_store_write_execution_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_write_evidence_schema",
        &preflight["durable_outcome_record_write_evidence_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome Record Write Evidence".to_string());
    lines.push(String::new());
    for key in [
        "write_evidence_id",
        "store_write_execution_id",
        "persistence_id",
        "record_write_execution_id",
        "record_write_id",
        "write_implementation_id",
        "execution_id",
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "evidence_kind",
        "write_evidence_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "write_plan_id",
        "write_destination",
        "outcome_record_key",
        "outcome_record_digest",
        "persisted_outcome_record_key",
        "persisted_outcome_record_digest",
        "durable_outcome_record_write_observed",
        "store_write_acknowledged",
        "record_readback_verified",
        "outcome_record_digest_verified",
        "idempotency_key_confirmed",
        "ready_for_durable_outcome_record_write_evidence_review",
        "durable_outcome_record_written_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed",
        "world_verdict_rewrite_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_record_write_evidence"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_review_durable_outcome_record_write_evidence_after_preflight",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_durable_outcome_record_write_evidence_review",
        "require_world_verdict_rewrite_gate_after_evidence_review",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
    input: &Value,
) -> Value {
    let (input_kind, write_evidence_preflight, review_decision) =
        extract_runtime_executor_durable_outcome_record_write_evidence_review_preflight_input(
            input,
        );
    let write_evidence_preflight_schema_ok = write_evidence_preflight
        .get("schema")
        .and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_PREFLIGHT_SCHEMA,
        );
    let review_schema_ok = review_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_DECISION_SCHEMA);
    let write_evidence = &write_evidence_preflight["durable_outcome_record_write_evidence"];
    let write_evidence_guardrails = &write_evidence_preflight["guardrails"];
    let write_evidence_contract = &write_evidence_preflight["agent_action_contract"];
    let review_scope = &review_decision["source_durable_outcome_record_write_evidence_scope"];

    let mut failure_reasons = Vec::new();
    if !write_evidence_preflight_schema_ok {
        failure_reasons.push(
            "runtime_executor_durable_outcome_record_write_evidence_preflight_required".to_string(),
        );
    }
    if write_evidence_preflight_schema_ok
        && write_evidence_preflight["durable_outcome_record_write_evidence_preflight_verdict"]
            != "ready_for_durable_outcome_record_write_evidence_review"
    {
        failure_reasons
            .push("source_durable_outcome_record_write_evidence_preflight_not_ready".to_string());
    }
    if write_evidence_preflight_schema_ok
        && write_evidence_preflight["source_world_verdict"] != "not_verified"
    {
        failure_reasons.push("source_world_verdict_must_remain_not_verified".to_string());
    }
    if write_evidence_preflight_schema_ok
        && write_evidence["evidence_kind"] != "durable_outcome_record_write_evidence"
    {
        failure_reasons
            .push("source_durable_outcome_record_write_evidence_kind_required".to_string());
    }
    if write_evidence_preflight_schema_ok
        && write_evidence["ready_for_durable_outcome_record_write_evidence_review"] != true
    {
        failure_reasons
            .push("source_durable_outcome_record_write_evidence_not_ready_for_review".to_string());
    }
    for (key, reason) in [
        (
            "durable_outcome_record_write_observed",
            "source_durable_outcome_record_write_evidence_requires_write_observed",
        ),
        (
            "store_write_acknowledged",
            "source_durable_outcome_record_write_evidence_requires_store_ack",
        ),
        (
            "record_readback_verified",
            "source_durable_outcome_record_write_evidence_requires_readback",
        ),
        (
            "outcome_record_digest_verified",
            "source_durable_outcome_record_write_evidence_requires_digest_verification",
        ),
        (
            "idempotency_key_confirmed",
            "source_durable_outcome_record_write_evidence_requires_idempotency",
        ),
    ] {
        if write_evidence_preflight_schema_ok && write_evidence[key] != true {
            failure_reasons.push(reason.to_string());
        }
    }
    if write_evidence_preflight_schema_ok
        && write_evidence["persisted_outcome_record_key"] != write_evidence["outcome_record_key"]
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_evidence_persisted_key_mismatch".to_string(),
        );
    }
    if write_evidence_preflight_schema_ok
        && write_evidence["persisted_outcome_record_digest"]
            != write_evidence["outcome_record_digest"]
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_evidence_persisted_digest_mismatch".to_string(),
        );
    }
    if write_evidence_preflight_schema_ok
        && write_evidence["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_evidence_must_not_write_by_this_tool".to_string(),
        );
    }
    if write_evidence_preflight_schema_ok && write_evidence["memory_write_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_record_write_evidence_must_not_allow_memory_write".to_string(),
        );
    }
    if write_evidence_preflight_schema_ok && write_evidence["outcome_ingestion_allowed"] != false {
        failure_reasons.push(
            "source_durable_outcome_record_write_evidence_must_not_allow_ingestion".to_string(),
        );
    }
    if write_evidence_preflight_schema_ok
        && write_evidence["world_verdict_rewrite_allowed"] != false
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_evidence_must_not_rewrite_verdict".to_string(),
        );
    }
    if write_evidence_preflight_schema_ok
        && (write_evidence_guardrails["read_only"] != true
            || write_evidence_guardrails["writes_state"] != false
            || write_evidence_guardrails["outcome_ingestion_allowed"] != false
            || write_evidence_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_evidence_guardrails_not_read_only".to_string(),
        );
    }
    if write_evidence_preflight_schema_ok
        && (write_evidence_contract["may_review_durable_outcome_record_write_evidence_after_preflight"]
            != true
            || write_evidence_contract["require_separate_durable_outcome_record_write_evidence_review"]
                != true
            || write_evidence_contract["require_world_verdict_rewrite_gate_after_evidence_review"]
                != true
            || write_evidence_contract["do_not_ingest_outcome"] != true
            || write_evidence_contract["do_not_write_memory"] != true
            || write_evidence_contract["do_not_rewrite_world_verdict"] != true
            || write_evidence_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push(
            "source_durable_outcome_record_write_evidence_contract_not_protective".to_string(),
        );
    }
    if !review_schema_ok {
        failure_reasons.push(
            "explicit_durable_outcome_record_write_evidence_review_decision_required".to_string(),
        );
    }
    if review_schema_ok && review_decision["review_decision_id"].as_str().is_none() {
        failure_reasons
            .push("durable_outcome_record_write_evidence_review_decision_id_required".to_string());
    }
    if review_schema_ok
        && review_decision["review_kind"] != "durable_outcome_record_write_evidence_review"
    {
        failure_reasons
            .push("durable_outcome_record_write_evidence_review_kind_required".to_string());
    }
    if review_schema_ok && review_decision["decision"] != "approved_for_world_verdict_rewrite_gate"
    {
        failure_reasons
            .push("durable_outcome_record_write_evidence_review_decision_not_approved".to_string());
    }
    if review_schema_ok && review_decision["source_world_verdict"] != "not_verified" {
        failure_reasons.push(
            "durable_outcome_record_write_evidence_review_must_preserve_not_verified_source"
                .to_string(),
        );
    }
    if review_schema_ok
        && review_decision["reviewed_write_evidence_preflight_verdict"]
            != "ready_for_durable_outcome_record_write_evidence_review"
    {
        failure_reasons.push(
            "durable_outcome_record_write_evidence_review_must_review_ready_preflight".to_string(),
        );
    }
    for (key, reason) in [
        (
            "durable_outcome_record_write_confirmed",
            "durable_outcome_record_write_evidence_review_requires_write_confirmation",
        ),
        (
            "store_ack_confirmed",
            "durable_outcome_record_write_evidence_review_requires_store_ack",
        ),
        (
            "record_readback_confirmed",
            "durable_outcome_record_write_evidence_review_requires_readback",
        ),
        (
            "outcome_record_digest_confirmed",
            "durable_outcome_record_write_evidence_review_requires_digest_confirmation",
        ),
        (
            "idempotency_key_confirmed",
            "durable_outcome_record_write_evidence_review_requires_idempotency",
        ),
        (
            "persisted_key_confirmed",
            "durable_outcome_record_write_evidence_review_requires_persisted_key",
        ),
        (
            "persisted_digest_confirmed",
            "durable_outcome_record_write_evidence_review_requires_persisted_digest",
        ),
        (
            "reviewer_attestation_present",
            "durable_outcome_record_write_evidence_review_requires_reviewer_attestation",
        ),
    ] {
        if review_schema_ok && review_decision[key] != true {
            failure_reasons.push(reason.to_string());
        }
    }
    if review_schema_ok && review_decision["outcome_ingestion_allowed"] != false {
        failure_reasons.push(
            "durable_outcome_record_write_evidence_review_must_not_allow_ingestion".to_string(),
        );
    }
    if review_schema_ok && review_decision["memory_write_allowed"] != false {
        failure_reasons.push(
            "durable_outcome_record_write_evidence_review_must_not_allow_memory_write".to_string(),
        );
    }
    if review_schema_ok && review_decision["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push(
            "durable_outcome_record_write_evidence_review_must_not_rewrite_verdict".to_string(),
        );
    }
    if review_schema_ok && review_decision["durable_outcome_record_written_by_this_tool"] != false {
        failure_reasons.push(
            "durable_outcome_record_write_evidence_review_must_not_write_by_this_tool".to_string(),
        );
    }

    for (scope_key, source_key, reason) in [
        (
            "write_evidence_id",
            "write_evidence_id",
            "durable_outcome_record_write_evidence_review_evidence_scope_mismatch",
        ),
        (
            "store_write_execution_id",
            "store_write_execution_id",
            "durable_outcome_record_write_evidence_review_store_write_execution_scope_mismatch",
        ),
        (
            "persistence_id",
            "persistence_id",
            "durable_outcome_record_write_evidence_review_persistence_scope_mismatch",
        ),
        (
            "record_write_execution_id",
            "record_write_execution_id",
            "durable_outcome_record_write_evidence_review_record_execution_scope_mismatch",
        ),
        (
            "record_write_id",
            "record_write_id",
            "durable_outcome_record_write_evidence_review_record_write_scope_mismatch",
        ),
        (
            "write_implementation_id",
            "write_implementation_id",
            "durable_outcome_record_write_evidence_review_implementation_scope_mismatch",
        ),
        (
            "execution_id",
            "execution_id",
            "durable_outcome_record_write_evidence_review_ingestion_execution_scope_mismatch",
        ),
        (
            "gate_id",
            "gate_id",
            "durable_outcome_record_write_evidence_review_gate_scope_mismatch",
        ),
        (
            "review_id",
            "review_id",
            "durable_outcome_record_write_evidence_review_ingestion_review_scope_mismatch",
        ),
        (
            "verification_id",
            "verification_id",
            "durable_outcome_record_write_evidence_review_verification_scope_mismatch",
        ),
        (
            "runtime_application_evidence_id",
            "runtime_application_evidence_id",
            "durable_outcome_record_write_evidence_review_application_evidence_scope_mismatch",
        ),
        (
            "source_invocation_request_id",
            "source_invocation_request_id",
            "durable_outcome_record_write_evidence_review_invocation_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "durable_outcome_record_write_evidence_review_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "durable_outcome_record_write_evidence_review_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "durable_outcome_record_write_evidence_review_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "durable_outcome_record_write_evidence_review_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "durable_outcome_record_write_evidence_review_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "durable_outcome_record_write_evidence_review_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "durable_outcome_record_write_evidence_review_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "durable_outcome_record_write_evidence_review_payload_digest_scope_mismatch",
        ),
        (
            "write_plan_id",
            "write_plan_id",
            "durable_outcome_record_write_evidence_review_write_plan_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "durable_outcome_record_write_evidence_review_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "durable_outcome_record_write_evidence_review_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "durable_outcome_record_write_evidence_review_digest_scope_mismatch",
        ),
        (
            "persisted_outcome_record_key",
            "persisted_outcome_record_key",
            "durable_outcome_record_write_evidence_review_persisted_key_scope_mismatch",
        ),
        (
            "persisted_outcome_record_digest",
            "persisted_outcome_record_digest",
            "durable_outcome_record_write_evidence_review_persisted_digest_scope_mismatch",
        ),
    ] {
        if write_evidence_preflight_schema_ok
            && review_schema_ok
            && review_scope[scope_key] != write_evidence[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "durable_outcome_record_write_evidence_review_preflight_ready_for_world_verdict_rewrite_gate"
            .to_string()
    } else {
        failure_reasons.first().cloned().unwrap_or_else(|| {
            "durable_outcome_record_write_evidence_review_preflight_blocked".to_string()
        })
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": write_evidence_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_record_write_evidence_preflight_verdict": write_evidence_preflight
            .get("durable_outcome_record_write_evidence_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": write_evidence_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "durable_outcome_record_write_evidence_review_decision_schema": review_decision.get("schema").cloned().unwrap_or(Value::Null),
        "durable_outcome_record_write_evidence_review_preflight_verdict": if ready { "ready_for_world_verdict_rewrite_gate" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_durable_outcome_record_write_evidence_review_preflight_guardrails(),
        "durable_outcome_record_write_evidence_review": {
            "review_decision_id": if ready { review_decision.get("review_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_evidence_id": if ready { review_scope.get("write_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "store_write_execution_id": if ready { review_scope.get("store_write_execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persistence_id": if ready { review_scope.get("persistence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_execution_id": if ready { review_scope.get("record_write_execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_write_id": if ready { review_scope.get("record_write_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_implementation_id": if ready { review_scope.get("write_implementation_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_id": if ready { review_scope.get("execution_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "gate_id": if ready { review_scope.get("gate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_id": if ready { review_scope.get("review_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verification_id": if ready { review_scope.get("verification_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_application_evidence_id": if ready { review_scope.get("runtime_application_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_invocation_request_id": if ready { review_scope.get("source_invocation_request_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { review_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { review_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { review_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { review_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_kind": if ready { review_decision.get("review_kind").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { review_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "review_reason": if ready { review_decision.get("review_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { review_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { review_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { review_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { review_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_plan_id": if ready { review_scope.get("write_plan_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { review_scope.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { review_scope.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { review_scope.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_key": if ready { review_scope.get("persisted_outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_digest": if ready { review_scope.get("persisted_outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "durable_outcome_record_write_confirmed": if ready { review_decision.get("durable_outcome_record_write_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "store_ack_confirmed": if ready { review_decision.get("store_ack_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "record_readback_confirmed": if ready { review_decision.get("record_readback_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest_confirmed": if ready { review_decision.get("outcome_record_digest_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key_confirmed": if ready { review_decision.get("idempotency_key_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_key_confirmed": if ready { review_decision.get("persisted_key_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_digest_confirmed": if ready { review_decision.get("persisted_digest_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "reviewer_attestation_present": if ready { review_decision.get("reviewer_attestation_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_world_verdict_rewrite_gate": ready,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "next_allowed_gate": if ready { "world_verdict_rewrite_gate" } else { "repair_durable_outcome_record_write_evidence_review_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_write_evidence_review_preflight_only",
            "may_enter_world_verdict_rewrite_gate_after_preflight": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_world_verdict_rewrite_gate": true
        },
        "source_durable_outcome_record_write_evidence_preflight": if write_evidence_preflight_schema_ok { write_evidence_preflight } else { Value::Null },
        "durable_outcome_record_write_evidence_review_decision": if review_schema_ok { review_decision } else { Value::Null },
        "durable_outcome_record_write_evidence_review_preflight_performed_by_this_tool": true,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure durable outcome record write-evidence review preflight: validates explicit review decision without durable writes, memory/store access, ingestion, or world verdict rewrite"
    })
}

pub fn render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Durable Outcome Record Write Evidence Review Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_write_evidence_review_preflight_verdict",
        &preflight["durable_outcome_record_write_evidence_review_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_record_write_evidence_preflight_verdict",
        &preflight["source_durable_outcome_record_write_evidence_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "durable_outcome_record_write_evidence_review_decision_schema",
        &preflight["durable_outcome_record_write_evidence_review_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Durable Outcome Record Write Evidence Review".to_string());
    lines.push(String::new());
    for key in [
        "review_decision_id",
        "write_evidence_id",
        "store_write_execution_id",
        "persistence_id",
        "record_write_execution_id",
        "record_write_id",
        "write_implementation_id",
        "execution_id",
        "gate_id",
        "review_id",
        "verification_id",
        "runtime_application_evidence_id",
        "source_invocation_request_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "review_kind",
        "decision",
        "review_reason",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "write_plan_id",
        "write_destination",
        "outcome_record_key",
        "outcome_record_digest",
        "persisted_outcome_record_key",
        "persisted_outcome_record_digest",
        "durable_outcome_record_write_confirmed",
        "store_ack_confirmed",
        "record_readback_confirmed",
        "outcome_record_digest_confirmed",
        "idempotency_key_confirmed",
        "persisted_key_confirmed",
        "persisted_digest_confirmed",
        "reviewer_attestation_present",
        "ready_for_world_verdict_rewrite_gate",
        "durable_outcome_record_written_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed",
        "world_verdict_rewrite_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["durable_outcome_record_write_evidence_review"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_enter_world_verdict_rewrite_gate_after_preflight",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_world_verdict_rewrite_gate",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(
    input: &Value,
) -> Value {
    let (input_kind, review_preflight, rewrite_decision) =
        extract_runtime_executor_world_verdict_rewrite_gate_input(input);
    let review_preflight_schema_ok = review_preflight
        .get("schema")
        .and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
        );
    let rewrite_schema_ok = rewrite_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_DECISION_SCHEMA);
    let reviewed_evidence = &review_preflight["durable_outcome_record_write_evidence_review"];
    let review_guardrails = &review_preflight["guardrails"];
    let review_contract = &review_preflight["agent_action_contract"];
    let rewrite_scope =
        &rewrite_decision["source_durable_outcome_record_write_evidence_review_scope"];

    let mut failure_reasons = Vec::new();
    if !review_preflight_schema_ok {
        failure_reasons.push(
            "runtime_executor_durable_outcome_record_write_evidence_review_preflight_required"
                .to_string(),
        );
    }
    if review_preflight_schema_ok
        && review_preflight["durable_outcome_record_write_evidence_review_preflight_verdict"]
            != "ready_for_world_verdict_rewrite_gate"
    {
        failure_reasons.push("source_world_verdict_rewrite_gate_preflight_not_ready".to_string());
    }
    if review_preflight_schema_ok && review_preflight["source_world_verdict"] != "not_verified" {
        failure_reasons.push("source_world_verdict_must_be_not_verified".to_string());
    }
    if review_preflight_schema_ok
        && reviewed_evidence["ready_for_world_verdict_rewrite_gate"] != true
    {
        failure_reasons.push("source_review_not_ready_for_world_verdict_rewrite_gate".to_string());
    }
    if review_preflight_schema_ok
        && reviewed_evidence["decision"] != "approved_for_world_verdict_rewrite_gate"
    {
        failure_reasons.push("source_review_decision_not_approved_for_rewrite_gate".to_string());
    }
    if review_preflight_schema_ok && reviewed_evidence["world_verdict_rewrite_allowed"] != false {
        failure_reasons.push("source_review_preflight_must_not_have_rewritten_verdict".to_string());
    }
    if review_preflight_schema_ok
        && (review_guardrails["read_only"] != true
            || review_guardrails["writes_state"] != false
            || review_guardrails["outcome_ingestion_allowed"] != false
            || review_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push("source_review_guardrails_not_read_only".to_string());
    }
    if review_preflight_schema_ok
        && (review_contract["may_enter_world_verdict_rewrite_gate_after_preflight"] != true
            || review_contract["require_separate_world_verdict_rewrite_gate"] != true
            || review_contract["do_not_ingest_outcome"] != true
            || review_contract["do_not_write_memory"] != true
            || review_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push("source_review_contract_not_protective".to_string());
    }
    if !rewrite_schema_ok {
        failure_reasons.push("explicit_world_verdict_rewrite_decision_required".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["rewrite_decision_id"].as_str().is_none() {
        failure_reasons.push("world_verdict_rewrite_decision_id_required".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["decision_kind"] != "world_verdict_rewrite" {
        failure_reasons.push("world_verdict_rewrite_decision_kind_required".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["decision"] != "rewrite_world_verdict_to_verified" {
        failure_reasons.push("world_verdict_rewrite_decision_not_approved".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["source_world_verdict"] != "not_verified" {
        failure_reasons.push("world_verdict_rewrite_source_must_be_not_verified".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["target_world_verdict"] != "verified" {
        failure_reasons.push("world_verdict_rewrite_target_must_be_verified".to_string());
    }
    if rewrite_schema_ok
        && rewrite_decision["reviewed_write_evidence_review_preflight_verdict"]
            != "ready_for_world_verdict_rewrite_gate"
    {
        failure_reasons.push("world_verdict_rewrite_must_review_ready_g16_preflight".to_string());
    }
    for (key, reason) in [
        (
            "verified_outcome_claim_present",
            "world_verdict_rewrite_requires_verified_outcome_claim",
        ),
        (
            "reviewer_attestation_present",
            "world_verdict_rewrite_requires_reviewer_attestation",
        ),
        (
            "evidence_lineage_preserved",
            "world_verdict_rewrite_requires_evidence_lineage",
        ),
        (
            "outcome_record_digest_confirmed",
            "world_verdict_rewrite_requires_outcome_record_digest",
        ),
        (
            "idempotency_key_confirmed",
            "world_verdict_rewrite_requires_idempotency",
        ),
        (
            "persisted_key_confirmed",
            "world_verdict_rewrite_requires_persisted_key",
        ),
        (
            "persisted_digest_confirmed",
            "world_verdict_rewrite_requires_persisted_digest",
        ),
    ] {
        if rewrite_schema_ok && rewrite_decision[key] != true {
            failure_reasons.push(reason.to_string());
        }
    }
    if rewrite_schema_ok && rewrite_decision["world_verdict_rewrite_allowed"] != true {
        failure_reasons.push("world_verdict_rewrite_decision_must_allow_rewrite".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["outcome_ingestion_allowed"] != false {
        failure_reasons.push("world_verdict_rewrite_gate_must_not_allow_ingestion".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["memory_write_allowed"] != false {
        failure_reasons.push("world_verdict_rewrite_gate_must_not_allow_memory_write".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons
            .push("world_verdict_rewrite_gate_must_not_write_outcome_record".to_string());
    }
    if rewrite_schema_ok && rewrite_decision["world_verdict_persisted_by_this_tool"] != false {
        failure_reasons.push("world_verdict_rewrite_gate_must_not_persist_verdict".to_string());
    }

    for (scope_key, source_key, reason) in [
        (
            "review_decision_id",
            "review_decision_id",
            "world_verdict_rewrite_review_decision_scope_mismatch",
        ),
        (
            "write_evidence_id",
            "write_evidence_id",
            "world_verdict_rewrite_evidence_scope_mismatch",
        ),
        (
            "store_write_execution_id",
            "store_write_execution_id",
            "world_verdict_rewrite_store_write_execution_scope_mismatch",
        ),
        (
            "persistence_id",
            "persistence_id",
            "world_verdict_rewrite_persistence_scope_mismatch",
        ),
        (
            "record_write_execution_id",
            "record_write_execution_id",
            "world_verdict_rewrite_record_execution_scope_mismatch",
        ),
        (
            "record_write_id",
            "record_write_id",
            "world_verdict_rewrite_record_write_scope_mismatch",
        ),
        (
            "write_implementation_id",
            "write_implementation_id",
            "world_verdict_rewrite_implementation_scope_mismatch",
        ),
        (
            "execution_id",
            "execution_id",
            "world_verdict_rewrite_ingestion_execution_scope_mismatch",
        ),
        (
            "gate_id",
            "gate_id",
            "world_verdict_rewrite_gate_scope_mismatch",
        ),
        (
            "review_id",
            "review_id",
            "world_verdict_rewrite_ingestion_review_scope_mismatch",
        ),
        (
            "verification_id",
            "verification_id",
            "world_verdict_rewrite_verification_scope_mismatch",
        ),
        (
            "runtime_application_evidence_id",
            "runtime_application_evidence_id",
            "world_verdict_rewrite_application_evidence_scope_mismatch",
        ),
        (
            "source_invocation_request_id",
            "source_invocation_request_id",
            "world_verdict_rewrite_invocation_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "world_verdict_rewrite_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "world_verdict_rewrite_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "world_verdict_rewrite_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "world_verdict_rewrite_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "world_verdict_rewrite_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "world_verdict_rewrite_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "world_verdict_rewrite_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "world_verdict_rewrite_payload_digest_scope_mismatch",
        ),
        (
            "write_plan_id",
            "write_plan_id",
            "world_verdict_rewrite_write_plan_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "world_verdict_rewrite_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "world_verdict_rewrite_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "world_verdict_rewrite_digest_scope_mismatch",
        ),
        (
            "persisted_outcome_record_key",
            "persisted_outcome_record_key",
            "world_verdict_rewrite_persisted_key_scope_mismatch",
        ),
        (
            "persisted_outcome_record_digest",
            "persisted_outcome_record_digest",
            "world_verdict_rewrite_persisted_digest_scope_mismatch",
        ),
    ] {
        if review_preflight_schema_ok
            && rewrite_schema_ok
            && rewrite_scope[scope_key] != reviewed_evidence[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "world_verdict_rewrite_gate_ready_for_verified_outcome_ingestion_gate".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "world_verdict_rewrite_gate_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA,
        "input_kind": input_kind,
        "source_schema": review_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_durable_outcome_record_write_evidence_review_preflight_verdict": review_preflight
            .get("durable_outcome_record_write_evidence_review_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": review_preflight
            .get("source_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "world_verdict_rewrite_decision_schema": rewrite_decision.get("schema").cloned().unwrap_or(Value::Null),
        "world_verdict_rewrite_gate_verdict": if ready { "ready_for_verified_outcome_ingestion_gate" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_world_verdict_rewrite_gate_guardrails(),
        "world_verdict_rewrite": {
            "rewrite_decision_id": if ready { rewrite_decision.get("rewrite_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_review_decision_id": if ready { rewrite_scope.get("review_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_evidence_id": if ready { rewrite_scope.get("write_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { rewrite_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { rewrite_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { rewrite_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { rewrite_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision_kind": if ready { rewrite_decision.get("decision_kind").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { rewrite_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "rewrite_reason": if ready { rewrite_decision.get("rewrite_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "previous_world_verdict": if ready { rewrite_decision.get("source_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "rewritten_world_verdict": if ready { rewrite_decision.get("target_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { rewrite_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { rewrite_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { rewrite_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { rewrite_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { rewrite_scope.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { rewrite_scope.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { rewrite_scope.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_key": if ready { rewrite_scope.get("persisted_outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_digest": if ready { rewrite_scope.get("persisted_outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_outcome_claim_present": if ready { rewrite_decision.get("verified_outcome_claim_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "reviewer_attestation_present": if ready { rewrite_decision.get("reviewer_attestation_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "evidence_lineage_preserved": if ready { rewrite_decision.get("evidence_lineage_preserved").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_verified_outcome_ingestion_gate": ready,
            "world_verdict_rewrite_allowed": ready,
            "world_verdict_rewrite_output_only": true,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": if ready { "verified_outcome_ingestion_gate" } else { "repair_world_verdict_rewrite_gate_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_world_verdict_rewrite_gate_only",
            "may_enter_verified_outcome_ingestion_gate_after_rewrite": ready,
            "may_emit_verified_outcome_package": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_gate": true
        },
        "source_durable_outcome_record_write_evidence_review_preflight": if review_preflight_schema_ok { review_preflight } else { Value::Null },
        "world_verdict_rewrite_decision": if rewrite_schema_ok { rewrite_decision } else { Value::Null },
        "world_verdict_rewrite_gate_performed_by_this_tool": true,
        "world_verdict_rewrite_performed_by_this_tool": ready,
        "world_verdict_persisted_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "verified_outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure world verdict rewrite gate: emits a bounded verified verdict package without durable writes, memory/store access, MCP exposure, or verified-outcome ingestion"
    })
}

pub fn render_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(
    gate: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor World Verdict Rewrite Gate".to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &gate["schema"]);
    push_markdown_kv(
        &mut lines,
        "world_verdict_rewrite_gate_verdict",
        &gate["world_verdict_rewrite_gate_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &gate["status"]);
    push_markdown_kv(&mut lines, "reason", &gate["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_durable_outcome_record_write_evidence_review_preflight_verdict",
        &gate["source_durable_outcome_record_write_evidence_review_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "world_verdict_rewrite_decision_schema",
        &gate["world_verdict_rewrite_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &gate["failure_reasons"]);

    lines.push(String::new());
    lines.push("## World Verdict Rewrite".to_string());
    lines.push(String::new());
    for key in [
        "rewrite_decision_id",
        "source_review_decision_id",
        "write_evidence_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision_kind",
        "decision",
        "rewrite_reason",
        "previous_world_verdict",
        "rewritten_world_verdict",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "outcome_record_key",
        "outcome_record_digest",
        "persisted_outcome_record_key",
        "persisted_outcome_record_digest",
        "verified_outcome_claim_present",
        "reviewer_attestation_present",
        "evidence_lineage_preserved",
        "ready_for_verified_outcome_ingestion_gate",
        "world_verdict_rewrite_allowed",
        "world_verdict_rewrite_output_only",
        "world_verdict_persisted_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(&mut lines, key, &gate["world_verdict_rewrite"][key]);
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_enter_verified_outcome_ingestion_gate_after_rewrite",
        "may_emit_verified_outcome_package",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_ingestion_gate",
    ] {
        push_markdown_kv(&mut lines, key, &gate["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(
    input: &Value,
) -> Value {
    let (input_kind, rewrite_gate, ingestion_decision) =
        extract_runtime_executor_verified_outcome_ingestion_gate_input(input);
    let rewrite_gate_schema_ok = rewrite_gate.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA);
    let ingestion_schema_ok = ingestion_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_DECISION_SCHEMA);
    let rewrite = &rewrite_gate["world_verdict_rewrite"];
    let rewrite_guardrails = &rewrite_gate["guardrails"];
    let rewrite_contract = &rewrite_gate["agent_action_contract"];
    let ingestion_scope = &ingestion_decision["source_world_verdict_rewrite_scope"];

    let mut failure_reasons = Vec::new();
    if !rewrite_gate_schema_ok {
        failure_reasons.push("runtime_executor_world_verdict_rewrite_gate_required".to_string());
    }
    if rewrite_gate_schema_ok
        && rewrite_gate["world_verdict_rewrite_gate_verdict"]
            != "ready_for_verified_outcome_ingestion_gate"
    {
        failure_reasons.push("source_world_verdict_rewrite_gate_not_ready".to_string());
    }
    if rewrite_gate_schema_ok
        && rewrite_gate["next_allowed_gate"] != "verified_outcome_ingestion_gate"
    {
        failure_reasons.push("source_world_verdict_rewrite_gate_next_gate_mismatch".to_string());
    }
    if rewrite_gate_schema_ok && rewrite["ready_for_verified_outcome_ingestion_gate"] != true {
        failure_reasons
            .push("source_rewrite_not_ready_for_verified_outcome_ingestion_gate".to_string());
    }
    if rewrite_gate_schema_ok && rewrite["previous_world_verdict"] != "not_verified" {
        failure_reasons.push("source_previous_world_verdict_must_be_not_verified".to_string());
    }
    if rewrite_gate_schema_ok && rewrite["rewritten_world_verdict"] != "verified" {
        failure_reasons.push("source_rewritten_world_verdict_must_be_verified".to_string());
    }
    if rewrite_gate_schema_ok
        && (rewrite["world_verdict_rewrite_output_only"] != true
            || rewrite["world_verdict_persisted_by_this_tool"] != false
            || rewrite["durable_outcome_record_written_by_this_tool"] != false
            || rewrite["memory_write_allowed"] != false
            || rewrite["outcome_ingestion_allowed"] != false)
    {
        failure_reasons.push("source_world_verdict_rewrite_boundary_not_output_only".to_string());
    }
    if rewrite_gate_schema_ok
        && (rewrite_gate["world_verdict_persisted_by_this_tool"] != false
            || rewrite_gate["durable_outcome_record_written_by_this_tool"] != false
            || rewrite_gate["verified_outcome_ingestion_performed_by_this_tool"] != false
            || rewrite_gate["writes_state"] != false
            || rewrite_gate["store_access_required"] != false
            || rewrite_gate["mcp_tool_registered"] != false)
    {
        failure_reasons.push("source_world_verdict_rewrite_gate_must_be_output_only".to_string());
    }
    if rewrite_gate_schema_ok
        && (rewrite_guardrails["read_only"] != true
            || rewrite_guardrails["writes_state"] != false
            || rewrite_guardrails["verified_outcome_ingestion_allowed"] != false
            || rewrite_guardrails["persists_world_verdict"] != false
            || rewrite_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push("source_world_verdict_rewrite_guardrails_not_protective".to_string());
    }
    if rewrite_gate_schema_ok
        && (rewrite_contract["may_enter_verified_outcome_ingestion_gate_after_rewrite"] != true
            || rewrite_contract["require_separate_verified_outcome_ingestion_gate"] != true
            || rewrite_contract["do_not_ingest_outcome"] != true
            || rewrite_contract["do_not_write_memory"] != true
            || rewrite_contract["do_not_persist_world_verdict"] != true
            || rewrite_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push("source_world_verdict_rewrite_contract_not_protective".to_string());
    }
    if !ingestion_schema_ok {
        failure_reasons.push("explicit_verified_outcome_ingestion_decision_required".to_string());
    }
    if ingestion_schema_ok
        && ingestion_decision["ingestion_decision_id"]
            .as_str()
            .is_none()
    {
        failure_reasons.push("verified_outcome_ingestion_decision_id_required".to_string());
    }
    if ingestion_schema_ok && ingestion_decision["decision_kind"] != "verified_outcome_ingestion" {
        failure_reasons.push("verified_outcome_ingestion_decision_kind_required".to_string());
    }
    if ingestion_schema_ok && ingestion_decision["decision"] != "admit_verified_outcome_package" {
        failure_reasons.push("verified_outcome_ingestion_decision_not_approved".to_string());
    }
    if ingestion_schema_ok && ingestion_decision["source_world_verdict"] != "verified" {
        failure_reasons.push("verified_outcome_ingestion_source_must_be_verified".to_string());
    }
    if ingestion_schema_ok
        && ingestion_decision["reviewed_world_verdict_rewrite_gate_verdict"]
            != "ready_for_verified_outcome_ingestion_gate"
    {
        failure_reasons
            .push("verified_outcome_ingestion_must_review_ready_rewrite_gate".to_string());
    }
    for (key, reason) in [
        (
            "bounded_verified_verdict_package_present",
            "verified_outcome_ingestion_requires_bounded_package",
        ),
        (
            "verified_outcome_claim_present",
            "verified_outcome_ingestion_requires_verified_outcome_claim",
        ),
        (
            "world_verdict_rewrite_output_only_confirmed",
            "verified_outcome_ingestion_requires_output_only_rewrite",
        ),
        (
            "reviewer_attestation_present",
            "verified_outcome_ingestion_requires_reviewer_attestation",
        ),
        (
            "evidence_lineage_preserved",
            "verified_outcome_ingestion_requires_evidence_lineage",
        ),
        (
            "outcome_record_digest_confirmed",
            "verified_outcome_ingestion_requires_outcome_record_digest",
        ),
        (
            "idempotency_key_confirmed",
            "verified_outcome_ingestion_requires_idempotency",
        ),
        (
            "persisted_key_confirmed",
            "verified_outcome_ingestion_requires_persisted_key",
        ),
        (
            "persisted_digest_confirmed",
            "verified_outcome_ingestion_requires_persisted_digest",
        ),
        (
            "verified_outcome_ingestion_allowed",
            "verified_outcome_ingestion_decision_must_allow_ingestion",
        ),
    ] {
        if ingestion_schema_ok && ingestion_decision[key] != true {
            failure_reasons.push(reason.to_string());
        }
    }
    if ingestion_schema_ok && ingestion_decision["store_write_allowed"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_gate_must_not_allow_store_write".to_string());
    }
    if ingestion_schema_ok && ingestion_decision["memory_write_allowed"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_gate_must_not_allow_memory_write".to_string());
    }
    if ingestion_schema_ok && ingestion_decision["verified_outcome_ingested_by_this_tool"] != false
    {
        failure_reasons.push("verified_outcome_ingestion_gate_must_not_ingest_outcome".to_string());
    }
    if ingestion_schema_ok
        && ingestion_decision["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons
            .push("verified_outcome_ingestion_gate_must_not_write_outcome_record".to_string());
    }
    if ingestion_schema_ok && ingestion_decision["world_verdict_persisted_by_this_tool"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_gate_must_not_persist_verdict".to_string());
    }

    for (scope_key, source_key, reason) in [
        (
            "rewrite_decision_id",
            "rewrite_decision_id",
            "verified_outcome_ingestion_rewrite_decision_scope_mismatch",
        ),
        (
            "source_review_decision_id",
            "source_review_decision_id",
            "verified_outcome_ingestion_review_decision_scope_mismatch",
        ),
        (
            "write_evidence_id",
            "write_evidence_id",
            "verified_outcome_ingestion_evidence_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "verified_outcome_ingestion_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "verified_outcome_ingestion_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "verified_outcome_ingestion_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "verified_outcome_ingestion_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "verified_outcome_ingestion_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "verified_outcome_ingestion_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "verified_outcome_ingestion_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "verified_outcome_ingestion_payload_digest_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "verified_outcome_ingestion_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "verified_outcome_ingestion_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "verified_outcome_ingestion_digest_scope_mismatch",
        ),
        (
            "persisted_outcome_record_key",
            "persisted_outcome_record_key",
            "verified_outcome_ingestion_persisted_key_scope_mismatch",
        ),
        (
            "persisted_outcome_record_digest",
            "persisted_outcome_record_digest",
            "verified_outcome_ingestion_persisted_digest_scope_mismatch",
        ),
    ] {
        if rewrite_gate_schema_ok
            && ingestion_schema_ok
            && ingestion_scope[scope_key] != rewrite[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "verified_outcome_ingestion_gate_ready_for_verified_outcome_admission".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "verified_outcome_ingestion_gate_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_GATE_SCHEMA,
        "input_kind": input_kind,
        "source_schema": rewrite_gate.get("schema").cloned().unwrap_or(Value::Null),
        "source_world_verdict_rewrite_gate_verdict": rewrite_gate
            .get("world_verdict_rewrite_gate_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": rewrite
            .get("previous_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "rewritten_world_verdict": rewrite
            .get("rewritten_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "verified_outcome_ingestion_decision_schema": ingestion_decision.get("schema").cloned().unwrap_or(Value::Null),
        "verified_outcome_ingestion_gate_verdict": if ready { "ready_for_verified_outcome_admission" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_verified_outcome_ingestion_gate_guardrails(),
        "verified_outcome_ingestion_gate": {
            "ingestion_decision_id": if ready { ingestion_decision.get("ingestion_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_rewrite_decision_id": if ready { ingestion_scope.get("rewrite_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_review_decision_id": if ready { ingestion_scope.get("source_review_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_evidence_id": if ready { ingestion_scope.get("write_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { ingestion_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { ingestion_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { ingestion_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { ingestion_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision_kind": if ready { ingestion_decision.get("decision_kind").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { ingestion_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ingestion_reason": if ready { ingestion_decision.get("ingestion_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "previous_world_verdict": if ready { rewrite.get("previous_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_world_verdict": if ready { ingestion_decision.get("source_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { ingestion_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { ingestion_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { ingestion_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { ingestion_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { ingestion_scope.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { ingestion_scope.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { ingestion_scope.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_key": if ready { ingestion_scope.get("persisted_outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_digest": if ready { ingestion_scope.get("persisted_outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "bounded_verified_verdict_package_present": if ready { ingestion_decision.get("bounded_verified_verdict_package_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_outcome_claim_present": if ready { ingestion_decision.get("verified_outcome_claim_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_verdict_rewrite_output_only_confirmed": if ready { ingestion_decision.get("world_verdict_rewrite_output_only_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "reviewer_attestation_present": if ready { ingestion_decision.get("reviewer_attestation_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "evidence_lineage_preserved": if ready { ingestion_decision.get("evidence_lineage_preserved").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_verified_outcome_admission": ready,
            "verified_outcome_admission_package_emitted_by_this_tool": ready,
            "verified_outcome_ingestion_gate_output_only": true,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "store_write_allowed": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": if ready { "verified_outcome_admission_gate" } else { "repair_verified_outcome_ingestion_gate_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_gate_only",
            "may_enter_verified_outcome_admission_gate_after_ingestion_decision": ready,
            "may_emit_verified_outcome_admission_package": ready,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_write_store": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_admission_gate": true
        },
        "source_world_verdict_rewrite_gate": if rewrite_gate_schema_ok { rewrite_gate } else { Value::Null },
        "verified_outcome_ingestion_decision": if ingestion_schema_ok { ingestion_decision } else { Value::Null },
        "verified_outcome_ingestion_gate_performed_by_this_tool": true,
        "verified_outcome_ingestion_decision_accepted_by_this_tool": ready,
        "verified_outcome_ingestion_performed_by_this_tool": false,
        "verified_outcome_admission_package_emitted_by_this_tool": ready,
        "world_verdict_persisted_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure verified outcome ingestion gate: emits a bounded admission package without store writes, memory writes, MCP exposure, world-verdict persistence, or verified-outcome ingestion"
    })
}

pub fn render_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(
    gate: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Verified Outcome Ingestion Gate".to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &gate["schema"]);
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_gate_verdict",
        &gate["verified_outcome_ingestion_gate_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &gate["status"]);
    push_markdown_kv(&mut lines, "reason", &gate["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_world_verdict_rewrite_gate_verdict",
        &gate["source_world_verdict_rewrite_gate_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_decision_schema",
        &gate["verified_outcome_ingestion_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &gate["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Verified Outcome Ingestion Gate".to_string());
    lines.push(String::new());
    for key in [
        "ingestion_decision_id",
        "source_rewrite_decision_id",
        "source_review_decision_id",
        "write_evidence_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision_kind",
        "decision",
        "ingestion_reason",
        "previous_world_verdict",
        "verified_world_verdict",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "outcome_record_key",
        "outcome_record_digest",
        "persisted_outcome_record_key",
        "persisted_outcome_record_digest",
        "verified_outcome_claim_present",
        "bounded_verified_verdict_package_present",
        "world_verdict_rewrite_output_only_confirmed",
        "reviewer_attestation_present",
        "evidence_lineage_preserved",
        "ready_for_verified_outcome_admission",
        "verified_outcome_admission_package_emitted_by_this_tool",
        "verified_outcome_ingestion_gate_output_only",
        "verified_outcome_ingested_by_this_tool",
        "world_verdict_persisted_by_this_tool",
        "store_write_allowed",
        "memory_write_allowed",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &gate["verified_outcome_ingestion_gate"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_enter_verified_outcome_admission_gate_after_ingestion_decision",
        "may_emit_verified_outcome_admission_package",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_write_store",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_admission_gate",
    ] {
        push_markdown_kv(&mut lines, key, &gate["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
    input: &Value,
) -> Value {
    let (input_kind, ingestion_gate, execution_decision) =
        extract_runtime_executor_verified_outcome_ingestion_execution_preflight_input(input);
    let ingestion_gate_schema_ok = ingestion_gate.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_GATE_SCHEMA);
    let execution_schema_ok = execution_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA);
    let gate = &ingestion_gate["verified_outcome_ingestion_gate"];
    let gate_guardrails = &ingestion_gate["guardrails"];
    let gate_contract = &ingestion_gate["agent_action_contract"];
    let execution_scope = &execution_decision["source_verified_outcome_ingestion_gate_scope"];

    let mut failure_reasons = Vec::new();
    if !ingestion_gate_schema_ok {
        failure_reasons
            .push("runtime_executor_verified_outcome_ingestion_gate_required".to_string());
    }
    if ingestion_gate_schema_ok
        && ingestion_gate["verified_outcome_ingestion_gate_verdict"]
            != "ready_for_verified_outcome_admission"
    {
        failure_reasons.push("source_verified_outcome_ingestion_gate_not_ready".to_string());
    }
    if ingestion_gate_schema_ok
        && ingestion_gate["next_allowed_gate"] != "verified_outcome_admission_gate"
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_gate_next_gate_mismatch".to_string());
    }
    if ingestion_gate_schema_ok && gate["ready_for_verified_outcome_admission"] != true {
        failure_reasons.push("source_gate_not_ready_for_verified_outcome_admission".to_string());
    }
    if ingestion_gate_schema_ok && gate["previous_world_verdict"] != "not_verified" {
        failure_reasons.push("source_previous_world_verdict_must_be_not_verified".to_string());
    }
    if ingestion_gate_schema_ok && gate["verified_world_verdict"] != "verified" {
        failure_reasons.push("source_verified_world_verdict_must_be_verified".to_string());
    }
    if ingestion_gate_schema_ok
        && (gate["verified_outcome_admission_package_emitted_by_this_tool"] != true
            || gate["verified_outcome_ingestion_gate_output_only"] != true
            || gate["verified_outcome_ingested_by_this_tool"] != false
            || gate["world_verdict_persisted_by_this_tool"] != false
            || gate["durable_outcome_record_written_by_this_tool"] != false
            || gate["store_write_allowed"] != false
            || gate["memory_write_allowed"] != false
            || gate["outcome_ingestion_allowed"] != false)
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_gate_boundary_not_output_only".to_string());
    }
    if ingestion_gate_schema_ok
        && (ingestion_gate["verified_outcome_ingestion_performed_by_this_tool"] != false
            || ingestion_gate["world_verdict_persisted_by_this_tool"] != false
            || ingestion_gate["durable_outcome_record_written_by_this_tool"] != false
            || ingestion_gate["writes_state"] != false
            || ingestion_gate["store_access_required"] != false
            || ingestion_gate["mcp_tool_registered"] != false)
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_gate_must_be_output_only".to_string());
    }
    if ingestion_gate_schema_ok
        && (gate_guardrails["read_only"] != true
            || gate_guardrails["writes_state"] != false
            || gate_guardrails["performs_verified_outcome_ingestion"] != false
            || gate_guardrails["store_write_allowed"] != false
            || gate_guardrails["persists_world_verdict"] != false
            || gate_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_guardrails_not_protective".to_string());
    }
    if ingestion_gate_schema_ok
        && (gate_contract["may_enter_verified_outcome_admission_gate_after_ingestion_decision"]
            != true
            || gate_contract["require_separate_verified_outcome_admission_gate"] != true
            || gate_contract["do_not_ingest_outcome"] != true
            || gate_contract["do_not_write_memory"] != true
            || gate_contract["do_not_write_store"] != true
            || gate_contract["do_not_persist_world_verdict"] != true
            || gate_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_contract_not_protective".to_string());
    }
    if !execution_schema_ok {
        failure_reasons
            .push("explicit_verified_outcome_ingestion_execution_decision_required".to_string());
    }
    if execution_schema_ok
        && execution_decision["execution_decision_id"]
            .as_str()
            .is_none()
    {
        failure_reasons
            .push("verified_outcome_ingestion_execution_decision_id_required".to_string());
    }
    if execution_schema_ok
        && execution_decision["decision_kind"] != "verified_outcome_ingestion_execution"
    {
        failure_reasons
            .push("verified_outcome_ingestion_execution_decision_kind_required".to_string());
    }
    if execution_schema_ok
        && execution_decision["decision"]
            != "approved_for_verified_outcome_ingestion_execution_preflight"
    {
        failure_reasons
            .push("verified_outcome_ingestion_execution_decision_not_approved".to_string());
    }
    if execution_schema_ok && execution_decision["source_world_verdict"] != "not_verified" {
        failure_reasons
            .push("verified_outcome_ingestion_execution_source_must_be_not_verified".to_string());
    }
    if execution_schema_ok && execution_decision["verified_world_verdict"] != "verified" {
        failure_reasons
            .push("verified_outcome_ingestion_execution_verdict_must_be_verified".to_string());
    }
    if execution_schema_ok
        && execution_decision["reviewed_verified_outcome_ingestion_gate_verdict"]
            != "ready_for_verified_outcome_admission"
    {
        failure_reasons
            .push("verified_outcome_ingestion_execution_must_review_ready_g18_gate".to_string());
    }
    for (key, reason) in [
        (
            "verified_outcome_package_confirmed",
            "verified_outcome_ingestion_execution_requires_package_confirmation",
        ),
        (
            "ingestion_gate_output_confirmed",
            "verified_outcome_ingestion_execution_requires_gate_output_confirmation",
        ),
        (
            "reviewer_attestation_present",
            "verified_outcome_ingestion_execution_requires_reviewer_attestation",
        ),
        (
            "evidence_lineage_preserved",
            "verified_outcome_ingestion_execution_requires_evidence_lineage",
        ),
        (
            "outcome_record_digest_confirmed",
            "verified_outcome_ingestion_execution_requires_outcome_record_digest",
        ),
        (
            "idempotency_key_confirmed",
            "verified_outcome_ingestion_execution_requires_idempotency",
        ),
        (
            "persisted_key_confirmed",
            "verified_outcome_ingestion_execution_requires_persisted_key",
        ),
        (
            "persisted_digest_confirmed",
            "verified_outcome_ingestion_execution_requires_persisted_digest",
        ),
        (
            "execution_boundary_acknowledged",
            "verified_outcome_ingestion_execution_requires_boundary_acknowledgement",
        ),
    ] {
        if execution_schema_ok && execution_decision[key] != true {
            failure_reasons.push(reason.to_string());
        }
    }
    if execution_schema_ok && execution_decision["outcome_ingestion_allowed"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_preflight_must_not_allow_ingestion".to_string(),
        );
    }
    if execution_schema_ok && execution_decision["memory_write_allowed"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_preflight_must_not_allow_memory_write"
                .to_string(),
        );
    }
    if execution_schema_ok && execution_decision["verified_outcome_ingested_by_this_tool"] != false
    {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_preflight_must_not_ingest_outcome".to_string(),
        );
    }
    if execution_schema_ok
        && execution_decision["durable_outcome_record_written_by_this_tool"] != false
    {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_preflight_must_not_write_outcome_record"
                .to_string(),
        );
    }
    if execution_schema_ok && execution_decision["world_verdict_persisted_by_this_tool"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_preflight_must_not_persist_verdict".to_string(),
        );
    }

    for (scope_key, source_key, reason) in [
        (
            "ingestion_decision_id",
            "ingestion_decision_id",
            "verified_outcome_ingestion_execution_ingestion_decision_scope_mismatch",
        ),
        (
            "source_rewrite_decision_id",
            "source_rewrite_decision_id",
            "verified_outcome_ingestion_execution_rewrite_decision_scope_mismatch",
        ),
        (
            "source_review_decision_id",
            "source_review_decision_id",
            "verified_outcome_ingestion_execution_review_decision_scope_mismatch",
        ),
        (
            "write_evidence_id",
            "write_evidence_id",
            "verified_outcome_ingestion_execution_evidence_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "verified_outcome_ingestion_execution_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "verified_outcome_ingestion_execution_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "verified_outcome_ingestion_execution_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "verified_outcome_ingestion_execution_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "verified_outcome_ingestion_execution_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "verified_outcome_ingestion_execution_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "verified_outcome_ingestion_execution_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "verified_outcome_ingestion_execution_payload_digest_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "verified_outcome_ingestion_execution_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "verified_outcome_ingestion_execution_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "verified_outcome_ingestion_execution_digest_scope_mismatch",
        ),
        (
            "persisted_outcome_record_key",
            "persisted_outcome_record_key",
            "verified_outcome_ingestion_execution_persisted_key_scope_mismatch",
        ),
        (
            "persisted_outcome_record_digest",
            "persisted_outcome_record_digest",
            "verified_outcome_ingestion_execution_persisted_digest_scope_mismatch",
        ),
    ] {
        if ingestion_gate_schema_ok
            && execution_schema_ok
            && execution_scope[scope_key] != gate[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "verified_outcome_ingestion_execution_preflight_ready_for_execution_commit".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "verified_outcome_ingestion_execution_preflight_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": ingestion_gate.get("schema").cloned().unwrap_or(Value::Null),
        "source_verified_outcome_ingestion_gate_verdict": ingestion_gate
            .get("verified_outcome_ingestion_gate_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": gate
            .get("previous_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "verified_world_verdict": gate
            .get("verified_world_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "verified_outcome_ingestion_execution_decision_schema": execution_decision.get("schema").cloned().unwrap_or(Value::Null),
        "verified_outcome_ingestion_execution_preflight_verdict": if ready { "ready_for_verified_outcome_ingestion_execution_commit" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_verified_outcome_ingestion_execution_preflight_guardrails(),
        "verified_outcome_ingestion_execution": {
            "execution_decision_id": if ready { execution_decision.get("execution_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_ingestion_decision_id": if ready { execution_scope.get("ingestion_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_rewrite_decision_id": if ready { execution_scope.get("source_rewrite_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_review_decision_id": if ready { execution_scope.get("source_review_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_evidence_id": if ready { execution_scope.get("write_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { execution_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { execution_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { execution_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { execution_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision_kind": if ready { execution_decision.get("decision_kind").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { execution_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_reason": if ready { execution_decision.get("execution_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "previous_world_verdict": if ready { execution_decision.get("source_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_world_verdict": if ready { execution_decision.get("verified_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { execution_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { execution_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { execution_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { execution_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { execution_scope.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { execution_scope.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { execution_scope.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_key": if ready { execution_scope.get("persisted_outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_digest": if ready { execution_scope.get("persisted_outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_outcome_package_confirmed": if ready { execution_decision.get("verified_outcome_package_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ingestion_gate_output_confirmed": if ready { execution_decision.get("ingestion_gate_output_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "reviewer_attestation_present": if ready { execution_decision.get("reviewer_attestation_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "evidence_lineage_preserved": if ready { execution_decision.get("evidence_lineage_preserved").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_verified_outcome_ingestion_execution_commit": ready,
            "verified_outcome_ingestion_execution_preflight_output_only": true,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": if ready { "verified_outcome_ingestion_execution_commit" } else { "repair_verified_outcome_ingestion_execution_preflight_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_execution_preflight_only",
            "may_enter_verified_outcome_ingestion_execution_commit_after_preflight": ready,
            "may_execute_verified_outcome_ingestion": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_execution_commit": true
        },
        "source_verified_outcome_ingestion_gate": if ingestion_gate_schema_ok { ingestion_gate } else { Value::Null },
        "verified_outcome_ingestion_execution_decision": if execution_schema_ok { execution_decision } else { Value::Null },
        "verified_outcome_ingestion_execution_preflight_performed_by_this_tool": true,
        "verified_outcome_ingestion_performed_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure verified outcome ingestion execution preflight: emits a bounded commit-ready package without durable writes, memory/store access, MCP exposure, world-verdict persistence, or verified-outcome ingestion"
    })
}

pub fn render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
    preflight: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Verified Outcome Ingestion Execution Preflight"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &preflight["schema"]);
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_execution_preflight_verdict",
        &preflight["verified_outcome_ingestion_execution_preflight_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &preflight["status"]);
    push_markdown_kv(&mut lines, "reason", &preflight["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_verified_outcome_ingestion_gate_verdict",
        &preflight["source_verified_outcome_ingestion_gate_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_execution_decision_schema",
        &preflight["verified_outcome_ingestion_execution_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &preflight["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Verified Outcome Ingestion Execution".to_string());
    lines.push(String::new());
    for key in [
        "execution_decision_id",
        "source_ingestion_decision_id",
        "source_rewrite_decision_id",
        "source_review_decision_id",
        "write_evidence_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision_kind",
        "decision",
        "execution_reason",
        "previous_world_verdict",
        "verified_world_verdict",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "outcome_record_key",
        "outcome_record_digest",
        "persisted_outcome_record_key",
        "persisted_outcome_record_digest",
        "verified_outcome_package_confirmed",
        "ingestion_gate_output_confirmed",
        "reviewer_attestation_present",
        "evidence_lineage_preserved",
        "ready_for_verified_outcome_ingestion_execution_commit",
        "verified_outcome_ingestion_execution_preflight_output_only",
        "verified_outcome_ingested_by_this_tool",
        "world_verdict_persisted_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &preflight["verified_outcome_ingestion_execution"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_enter_verified_outcome_ingestion_execution_commit_after_preflight",
        "may_execute_verified_outcome_ingestion",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_ingestion_execution_commit",
    ] {
        push_markdown_kv(&mut lines, key, &preflight["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
    input: &Value,
) -> Value {
    let (input_kind, execution_preflight, commit_decision) =
        extract_runtime_executor_verified_outcome_ingestion_execution_commit_input(input);
    let preflight_schema_ok = execution_preflight.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
        );
    let commit_schema_ok = commit_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA);
    let execution = &execution_preflight["verified_outcome_ingestion_execution"];
    let preflight_guardrails = &execution_preflight["guardrails"];
    let preflight_contract = &execution_preflight["agent_action_contract"];
    let commit_scope =
        &commit_decision["source_verified_outcome_ingestion_execution_preflight_scope"];

    let mut failure_reasons = Vec::new();
    if !preflight_schema_ok {
        failure_reasons.push(
            "runtime_executor_verified_outcome_ingestion_execution_preflight_required".to_string(),
        );
    }
    if preflight_schema_ok
        && execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"]
            != "ready_for_verified_outcome_ingestion_execution_commit"
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_execution_preflight_not_ready".to_string());
    }
    if preflight_schema_ok
        && execution_preflight["next_allowed_gate"] != "verified_outcome_ingestion_execution_commit"
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_preflight_next_gate_mismatch".to_string(),
        );
    }
    if preflight_schema_ok
        && execution["ready_for_verified_outcome_ingestion_execution_commit"] != true
    {
        failure_reasons.push("source_execution_preflight_not_ready_for_commit".to_string());
    }
    if preflight_schema_ok && execution["previous_world_verdict"] != "not_verified" {
        failure_reasons.push("source_previous_world_verdict_must_be_not_verified".to_string());
    }
    if preflight_schema_ok && execution["verified_world_verdict"] != "verified" {
        failure_reasons.push("source_verified_world_verdict_must_be_verified".to_string());
    }
    if preflight_schema_ok
        && (execution["verified_outcome_ingestion_execution_preflight_output_only"] != true
            || execution["verified_outcome_ingested_by_this_tool"] != false
            || execution["world_verdict_persisted_by_this_tool"] != false
            || execution["durable_outcome_record_written_by_this_tool"] != false
            || execution["memory_write_allowed"] != false
            || execution["outcome_ingestion_allowed"] != false)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_preflight_boundary_not_output_only"
                .to_string(),
        );
    }
    if preflight_schema_ok
        && (execution_preflight["verified_outcome_ingestion_performed_by_this_tool"] != false
            || execution_preflight["verified_outcome_ingested_by_this_tool"] != false
            || execution_preflight["world_verdict_persisted_by_this_tool"] != false
            || execution_preflight["durable_outcome_record_written_by_this_tool"] != false
            || execution_preflight["writes_state"] != false
            || execution_preflight["store_access_required"] != false
            || execution_preflight["mcp_tool_registered"] != false)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_preflight_must_be_output_only".to_string(),
        );
    }
    if preflight_schema_ok
        && (preflight_guardrails["read_only"] != true
            || preflight_guardrails["writes_state"] != false
            || preflight_guardrails["performs_verified_outcome_ingestion"] != false
            || preflight_guardrails["verified_outcome_ingestion_allowed"] != false
            || preflight_guardrails["persists_world_verdict"] != false
            || preflight_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_preflight_guardrails_not_protective"
                .to_string(),
        );
    }
    if preflight_schema_ok
        && (preflight_contract["may_enter_verified_outcome_ingestion_execution_commit_after_preflight"]
            != true
            || preflight_contract["may_execute_verified_outcome_ingestion"] != false
            || preflight_contract["require_separate_verified_outcome_ingestion_execution_commit"]
                != true
            || preflight_contract["do_not_ingest_outcome"] != true
            || preflight_contract["do_not_write_memory"] != true
            || preflight_contract["do_not_persist_world_verdict"] != true
            || preflight_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_preflight_contract_not_protective"
                .to_string(),
        );
    }
    if !commit_schema_ok {
        failure_reasons.push(
            "explicit_verified_outcome_ingestion_execution_commit_decision_required".to_string(),
        );
    }
    if commit_schema_ok && commit_decision["commit_decision_id"].as_str().is_none() {
        failure_reasons
            .push("verified_outcome_ingestion_execution_commit_decision_id_required".to_string());
    }
    if commit_schema_ok
        && commit_decision["decision_kind"] != "verified_outcome_ingestion_execution_commit"
    {
        failure_reasons
            .push("verified_outcome_ingestion_execution_commit_decision_kind_required".to_string());
    }
    if commit_schema_ok
        && commit_decision["decision"] != "approved_for_verified_outcome_ingestion_apply"
    {
        failure_reasons
            .push("verified_outcome_ingestion_execution_commit_decision_not_approved".to_string());
    }
    if commit_schema_ok && commit_decision["source_world_verdict"] != "not_verified" {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_commit_source_must_be_not_verified".to_string(),
        );
    }
    if commit_schema_ok && commit_decision["verified_world_verdict"] != "verified" {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_commit_verdict_must_be_verified".to_string(),
        );
    }
    if commit_schema_ok
        && commit_decision["reviewed_verified_outcome_ingestion_execution_preflight_verdict"]
            != "ready_for_verified_outcome_ingestion_execution_commit"
    {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_commit_must_review_ready_g19_preflight"
                .to_string(),
        );
    }
    for (key, reason) in [
        (
            "execution_preflight_package_confirmed",
            "verified_outcome_ingestion_execution_commit_requires_preflight_package",
        ),
        (
            "verified_outcome_package_confirmed",
            "verified_outcome_ingestion_execution_commit_requires_verified_package",
        ),
        (
            "reviewer_attestation_present",
            "verified_outcome_ingestion_execution_commit_requires_reviewer_attestation",
        ),
        (
            "evidence_lineage_preserved",
            "verified_outcome_ingestion_execution_commit_requires_evidence_lineage",
        ),
        (
            "outcome_record_digest_confirmed",
            "verified_outcome_ingestion_execution_commit_requires_outcome_record_digest",
        ),
        (
            "idempotency_key_confirmed",
            "verified_outcome_ingestion_execution_commit_requires_idempotency",
        ),
        (
            "persisted_key_confirmed",
            "verified_outcome_ingestion_execution_commit_requires_persisted_key",
        ),
        (
            "persisted_digest_confirmed",
            "verified_outcome_ingestion_execution_commit_requires_persisted_digest",
        ),
        (
            "apply_boundary_acknowledged",
            "verified_outcome_ingestion_execution_commit_requires_apply_boundary",
        ),
    ] {
        if commit_schema_ok && commit_decision[key] != true {
            failure_reasons.push(reason.to_string());
        }
    }
    if commit_schema_ok && commit_decision["outcome_ingestion_allowed"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_commit_must_not_allow_ingestion".to_string(),
        );
    }
    if commit_schema_ok && commit_decision["memory_write_allowed"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_commit_must_not_allow_memory_write".to_string(),
        );
    }
    if commit_schema_ok && commit_decision["verified_outcome_ingested_by_this_tool"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_commit_must_not_ingest_outcome".to_string(),
        );
    }
    if commit_schema_ok && commit_decision["durable_outcome_record_written_by_this_tool"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_commit_must_not_write_outcome_record".to_string(),
        );
    }
    if commit_schema_ok && commit_decision["world_verdict_persisted_by_this_tool"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_execution_commit_must_not_persist_verdict".to_string(),
        );
    }

    for (scope_key, source_key, reason) in [
        (
            "execution_decision_id",
            "execution_decision_id",
            "verified_outcome_ingestion_execution_commit_execution_decision_scope_mismatch",
        ),
        (
            "source_ingestion_decision_id",
            "source_ingestion_decision_id",
            "verified_outcome_ingestion_execution_commit_ingestion_decision_scope_mismatch",
        ),
        (
            "source_rewrite_decision_id",
            "source_rewrite_decision_id",
            "verified_outcome_ingestion_execution_commit_rewrite_decision_scope_mismatch",
        ),
        (
            "source_review_decision_id",
            "source_review_decision_id",
            "verified_outcome_ingestion_execution_commit_review_decision_scope_mismatch",
        ),
        (
            "write_evidence_id",
            "write_evidence_id",
            "verified_outcome_ingestion_execution_commit_evidence_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "verified_outcome_ingestion_execution_commit_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "verified_outcome_ingestion_execution_commit_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "verified_outcome_ingestion_execution_commit_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "verified_outcome_ingestion_execution_commit_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "verified_outcome_ingestion_execution_commit_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "verified_outcome_ingestion_execution_commit_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "verified_outcome_ingestion_execution_commit_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "verified_outcome_ingestion_execution_commit_payload_digest_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "verified_outcome_ingestion_execution_commit_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "verified_outcome_ingestion_execution_commit_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "verified_outcome_ingestion_execution_commit_digest_scope_mismatch",
        ),
        (
            "persisted_outcome_record_key",
            "persisted_outcome_record_key",
            "verified_outcome_ingestion_execution_commit_persisted_key_scope_mismatch",
        ),
        (
            "persisted_outcome_record_digest",
            "persisted_outcome_record_digest",
            "verified_outcome_ingestion_execution_commit_persisted_digest_scope_mismatch",
        ),
    ] {
        if preflight_schema_ok
            && commit_schema_ok
            && commit_scope[scope_key] != execution[source_key]
        {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "verified_outcome_ingestion_execution_commit_ready_for_apply".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "verified_outcome_ingestion_execution_commit_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA,
        "input_kind": input_kind,
        "source_schema": execution_preflight.get("schema").cloned().unwrap_or(Value::Null),
        "source_verified_outcome_ingestion_execution_preflight_verdict": execution_preflight
            .get("verified_outcome_ingestion_execution_preflight_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": execution.get("previous_world_verdict").cloned().unwrap_or(Value::Null),
        "verified_world_verdict": execution.get("verified_world_verdict").cloned().unwrap_or(Value::Null),
        "verified_outcome_ingestion_execution_commit_decision_schema": commit_decision.get("schema").cloned().unwrap_or(Value::Null),
        "verified_outcome_ingestion_execution_commit_verdict": if ready { "ready_for_verified_outcome_ingestion_apply" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_verified_outcome_ingestion_execution_commit_guardrails(),
        "verified_outcome_ingestion_execution_commit": {
            "commit_decision_id": if ready { commit_decision.get("commit_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_execution_decision_id": if ready { commit_scope.get("execution_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_ingestion_decision_id": if ready { commit_scope.get("source_ingestion_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_rewrite_decision_id": if ready { commit_scope.get("source_rewrite_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_review_decision_id": if ready { commit_scope.get("source_review_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_evidence_id": if ready { commit_scope.get("write_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { commit_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { commit_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { commit_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { commit_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision_kind": if ready { commit_decision.get("decision_kind").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { commit_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "commit_reason": if ready { commit_decision.get("commit_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "previous_world_verdict": if ready { commit_decision.get("source_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_world_verdict": if ready { commit_decision.get("verified_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { commit_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { commit_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { commit_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { commit_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { commit_scope.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { commit_scope.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { commit_scope.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_key": if ready { commit_scope.get("persisted_outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_digest": if ready { commit_scope.get("persisted_outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "execution_preflight_package_confirmed": if ready { commit_decision.get("execution_preflight_package_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_outcome_package_confirmed": if ready { commit_decision.get("verified_outcome_package_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "reviewer_attestation_present": if ready { commit_decision.get("reviewer_attestation_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "evidence_lineage_preserved": if ready { commit_decision.get("evidence_lineage_preserved").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_verified_outcome_ingestion_apply": ready,
            "verified_outcome_ingestion_execution_commit_output_only": true,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": if ready { "verified_outcome_ingestion_apply" } else { "repair_verified_outcome_ingestion_execution_commit_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_execution_commit_only",
            "may_enter_verified_outcome_ingestion_apply_after_commit": ready,
            "may_execute_verified_outcome_ingestion": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_apply": true
        },
        "source_verified_outcome_ingestion_execution_preflight": if preflight_schema_ok { execution_preflight } else { Value::Null },
        "verified_outcome_ingestion_execution_commit_decision": if commit_schema_ok { commit_decision } else { Value::Null },
        "verified_outcome_ingestion_execution_commit_performed_by_this_tool": true,
        "verified_outcome_ingestion_performed_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure verified outcome ingestion execution commit gate: emits a bounded apply-ready package without durable writes, memory/store access, MCP exposure, world-verdict persistence, or verified-outcome ingestion"
    })
}

pub fn render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
    commit: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Verified Outcome Ingestion Execution Commit"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &commit["schema"]);
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_execution_commit_verdict",
        &commit["verified_outcome_ingestion_execution_commit_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &commit["status"]);
    push_markdown_kv(&mut lines, "reason", &commit["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_verified_outcome_ingestion_execution_preflight_verdict",
        &commit["source_verified_outcome_ingestion_execution_preflight_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_execution_commit_decision_schema",
        &commit["verified_outcome_ingestion_execution_commit_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &commit["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Verified Outcome Ingestion Execution Commit".to_string());
    lines.push(String::new());
    for key in [
        "commit_decision_id",
        "source_execution_decision_id",
        "source_ingestion_decision_id",
        "source_rewrite_decision_id",
        "source_review_decision_id",
        "write_evidence_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision_kind",
        "decision",
        "commit_reason",
        "previous_world_verdict",
        "verified_world_verdict",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "outcome_record_key",
        "outcome_record_digest",
        "persisted_outcome_record_key",
        "persisted_outcome_record_digest",
        "execution_preflight_package_confirmed",
        "verified_outcome_package_confirmed",
        "reviewer_attestation_present",
        "evidence_lineage_preserved",
        "ready_for_verified_outcome_ingestion_apply",
        "verified_outcome_ingestion_execution_commit_output_only",
        "verified_outcome_ingested_by_this_tool",
        "world_verdict_persisted_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &commit["verified_outcome_ingestion_execution_commit"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_enter_verified_outcome_ingestion_apply_after_commit",
        "may_execute_verified_outcome_ingestion",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_ingestion_apply",
    ] {
        push_markdown_kv(&mut lines, key, &commit["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(
    input: &Value,
) -> Value {
    let (input_kind, commit, apply_decision) =
        extract_runtime_executor_verified_outcome_ingestion_apply_gate_input(input);
    let commit_schema_ok = commit.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA,
        );
    let apply_schema_ok = apply_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA);
    let committed = &commit["verified_outcome_ingestion_execution_commit"];
    let commit_guardrails = &commit["guardrails"];
    let commit_contract = &commit["agent_action_contract"];
    let apply_scope = &apply_decision["source_verified_outcome_ingestion_execution_commit_scope"];

    let mut failure_reasons = Vec::new();
    if !commit_schema_ok {
        failure_reasons.push(
            "runtime_executor_verified_outcome_ingestion_execution_commit_required".to_string(),
        );
    }
    if commit_schema_ok
        && commit["verified_outcome_ingestion_execution_commit_verdict"]
            != "ready_for_verified_outcome_ingestion_apply"
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_execution_commit_not_ready".to_string());
    }
    if commit_schema_ok && commit["next_allowed_gate"] != "verified_outcome_ingestion_apply" {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_commit_next_gate_mismatch".to_string(),
        );
    }
    if commit_schema_ok && committed["ready_for_verified_outcome_ingestion_apply"] != true {
        failure_reasons.push("source_commit_not_ready_for_apply".to_string());
    }
    if commit_schema_ok && committed["previous_world_verdict"] != "not_verified" {
        failure_reasons.push("source_previous_world_verdict_must_be_not_verified".to_string());
    }
    if commit_schema_ok && committed["verified_world_verdict"] != "verified" {
        failure_reasons.push("source_verified_world_verdict_must_be_verified".to_string());
    }
    if commit_schema_ok
        && (committed["verified_outcome_ingestion_execution_commit_output_only"] != true
            || committed["verified_outcome_ingested_by_this_tool"] != false
            || committed["world_verdict_persisted_by_this_tool"] != false
            || committed["durable_outcome_record_written_by_this_tool"] != false
            || committed["memory_write_allowed"] != false
            || committed["outcome_ingestion_allowed"] != false)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_commit_boundary_not_output_only"
                .to_string(),
        );
    }
    if commit_schema_ok
        && (commit["verified_outcome_ingestion_performed_by_this_tool"] != false
            || commit["verified_outcome_ingested_by_this_tool"] != false
            || commit["world_verdict_persisted_by_this_tool"] != false
            || commit["durable_outcome_record_written_by_this_tool"] != false
            || commit["writes_state"] != false
            || commit["store_access_required"] != false
            || commit["mcp_tool_registered"] != false)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_commit_must_be_output_only".to_string(),
        );
    }
    if commit_schema_ok
        && (commit_guardrails["read_only"] != true
            || commit_guardrails["writes_state"] != false
            || commit_guardrails["performs_verified_outcome_ingestion"] != false
            || commit_guardrails["verified_outcome_ingestion_allowed"] != false
            || commit_guardrails["persists_world_verdict"] != false
            || commit_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_commit_guardrails_not_protective"
                .to_string(),
        );
    }
    if commit_schema_ok
        && (commit_contract["may_enter_verified_outcome_ingestion_apply_after_commit"] != true
            || commit_contract["may_execute_verified_outcome_ingestion"] != false
            || commit_contract["require_separate_verified_outcome_ingestion_apply"] != true
            || commit_contract["do_not_ingest_outcome"] != true
            || commit_contract["do_not_write_memory"] != true
            || commit_contract["do_not_persist_world_verdict"] != true
            || commit_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_execution_commit_contract_not_protective"
                .to_string(),
        );
    }
    if !apply_schema_ok {
        failure_reasons
            .push("explicit_verified_outcome_ingestion_apply_decision_required".to_string());
    }
    if apply_schema_ok && apply_decision["apply_decision_id"].as_str().is_none() {
        failure_reasons.push("verified_outcome_ingestion_apply_decision_id_required".to_string());
    }
    if apply_schema_ok && apply_decision["decision_kind"] != "verified_outcome_ingestion_apply" {
        failure_reasons.push("verified_outcome_ingestion_apply_decision_kind_required".to_string());
    }
    if apply_schema_ok
        && apply_decision["decision"] != "approved_for_verified_outcome_ingestion_writer"
    {
        failure_reasons.push("verified_outcome_ingestion_apply_decision_not_approved".to_string());
    }
    if apply_schema_ok && apply_decision["source_world_verdict"] != "not_verified" {
        failure_reasons
            .push("verified_outcome_ingestion_apply_source_must_be_not_verified".to_string());
    }
    if apply_schema_ok && apply_decision["verified_world_verdict"] != "verified" {
        failure_reasons
            .push("verified_outcome_ingestion_apply_verdict_must_be_verified".to_string());
    }
    if apply_schema_ok
        && apply_decision["reviewed_verified_outcome_ingestion_execution_commit_verdict"]
            != "ready_for_verified_outcome_ingestion_apply"
    {
        failure_reasons
            .push("verified_outcome_ingestion_apply_must_review_ready_g20_commit".to_string());
    }
    for (key, reason) in [
        (
            "commit_package_confirmed",
            "verified_outcome_ingestion_apply_requires_commit_package",
        ),
        (
            "execution_preflight_package_confirmed",
            "verified_outcome_ingestion_apply_requires_preflight_package",
        ),
        (
            "verified_outcome_package_confirmed",
            "verified_outcome_ingestion_apply_requires_verified_package",
        ),
        (
            "reviewer_attestation_present",
            "verified_outcome_ingestion_apply_requires_reviewer_attestation",
        ),
        (
            "evidence_lineage_preserved",
            "verified_outcome_ingestion_apply_requires_evidence_lineage",
        ),
        (
            "outcome_record_digest_confirmed",
            "verified_outcome_ingestion_apply_requires_outcome_record_digest",
        ),
        (
            "idempotency_key_confirmed",
            "verified_outcome_ingestion_apply_requires_idempotency",
        ),
        (
            "persisted_key_confirmed",
            "verified_outcome_ingestion_apply_requires_persisted_key",
        ),
        (
            "persisted_digest_confirmed",
            "verified_outcome_ingestion_apply_requires_persisted_digest",
        ),
        (
            "writer_boundary_acknowledged",
            "verified_outcome_ingestion_apply_requires_writer_boundary",
        ),
    ] {
        if apply_schema_ok && apply_decision[key] != true {
            failure_reasons.push(reason.to_string());
        }
    }
    if apply_schema_ok && apply_decision["outcome_ingestion_allowed_by_this_tool"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_apply_must_not_allow_ingestion_by_this_tool".to_string(),
        );
    }
    if apply_schema_ok && apply_decision["memory_write_allowed"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_apply_must_not_allow_memory_write".to_string());
    }
    if apply_schema_ok && apply_decision["verified_outcome_ingested_by_this_tool"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_apply_must_not_ingest_outcome".to_string());
    }
    if apply_schema_ok && apply_decision["durable_outcome_record_written_by_this_tool"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_apply_must_not_write_outcome_record".to_string());
    }
    if apply_schema_ok && apply_decision["world_verdict_persisted_by_this_tool"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_apply_must_not_persist_verdict".to_string());
    }

    for (scope_key, source_key, reason) in [
        (
            "commit_decision_id",
            "commit_decision_id",
            "verified_outcome_ingestion_apply_commit_decision_scope_mismatch",
        ),
        (
            "source_execution_decision_id",
            "source_execution_decision_id",
            "verified_outcome_ingestion_apply_execution_decision_scope_mismatch",
        ),
        (
            "source_ingestion_decision_id",
            "source_ingestion_decision_id",
            "verified_outcome_ingestion_apply_ingestion_decision_scope_mismatch",
        ),
        (
            "source_rewrite_decision_id",
            "source_rewrite_decision_id",
            "verified_outcome_ingestion_apply_rewrite_decision_scope_mismatch",
        ),
        (
            "source_review_decision_id",
            "source_review_decision_id",
            "verified_outcome_ingestion_apply_review_decision_scope_mismatch",
        ),
        (
            "write_evidence_id",
            "write_evidence_id",
            "verified_outcome_ingestion_apply_evidence_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "verified_outcome_ingestion_apply_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "verified_outcome_ingestion_apply_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "verified_outcome_ingestion_apply_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "verified_outcome_ingestion_apply_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "verified_outcome_ingestion_apply_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "verified_outcome_ingestion_apply_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "verified_outcome_ingestion_apply_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "verified_outcome_ingestion_apply_payload_digest_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "verified_outcome_ingestion_apply_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "verified_outcome_ingestion_apply_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "verified_outcome_ingestion_apply_digest_scope_mismatch",
        ),
        (
            "persisted_outcome_record_key",
            "persisted_outcome_record_key",
            "verified_outcome_ingestion_apply_persisted_key_scope_mismatch",
        ),
        (
            "persisted_outcome_record_digest",
            "persisted_outcome_record_digest",
            "verified_outcome_ingestion_apply_persisted_digest_scope_mismatch",
        ),
    ] {
        if commit_schema_ok && apply_schema_ok && apply_scope[scope_key] != committed[source_key] {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "verified_outcome_ingestion_apply_ready_for_writer".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "verified_outcome_ingestion_apply_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_GATE_SCHEMA,
        "input_kind": input_kind,
        "source_schema": commit.get("schema").cloned().unwrap_or(Value::Null),
        "source_verified_outcome_ingestion_execution_commit_verdict": commit
            .get("verified_outcome_ingestion_execution_commit_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": committed.get("previous_world_verdict").cloned().unwrap_or(Value::Null),
        "verified_world_verdict": committed.get("verified_world_verdict").cloned().unwrap_or(Value::Null),
        "verified_outcome_ingestion_apply_decision_schema": apply_decision.get("schema").cloned().unwrap_or(Value::Null),
        "verified_outcome_ingestion_apply_verdict": if ready { "ready_for_verified_outcome_ingestion_writer" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_verified_outcome_ingestion_apply_gate_guardrails(),
        "verified_outcome_ingestion_apply": {
            "apply_decision_id": if ready { apply_decision.get("apply_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "commit_decision_id": if ready { apply_scope.get("commit_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_execution_decision_id": if ready { apply_scope.get("source_execution_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_ingestion_decision_id": if ready { apply_scope.get("source_ingestion_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_rewrite_decision_id": if ready { apply_scope.get("source_rewrite_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_review_decision_id": if ready { apply_scope.get("source_review_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_evidence_id": if ready { apply_scope.get("write_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { apply_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { apply_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { apply_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { apply_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision_kind": if ready { apply_decision.get("decision_kind").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { apply_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "apply_reason": if ready { apply_decision.get("apply_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "previous_world_verdict": if ready { apply_decision.get("source_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_world_verdict": if ready { apply_decision.get("verified_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { apply_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { apply_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { apply_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { apply_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { apply_scope.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { apply_scope.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { apply_scope.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_key": if ready { apply_scope.get("persisted_outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_digest": if ready { apply_scope.get("persisted_outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "commit_package_confirmed": if ready { apply_decision.get("commit_package_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_outcome_package_confirmed": if ready { apply_decision.get("verified_outcome_package_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "reviewer_attestation_present": if ready { apply_decision.get("reviewer_attestation_present").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "evidence_lineage_preserved": if ready { apply_decision.get("evidence_lineage_preserved").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_verified_outcome_ingestion_writer": ready,
            "verified_outcome_ingestion_apply_gate_output_only": true,
            "verified_outcome_ingestion_writer_allowed_after_gate": ready,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed_by_this_tool": false
        },
        "next_allowed_gate": if ready { "verified_outcome_ingestion_writer" } else { "repair_verified_outcome_ingestion_apply_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_apply_gate_only",
            "may_invoke_verified_outcome_ingestion_writer_after_apply": ready,
            "may_execute_verified_outcome_ingestion_by_this_tool": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_writer": true
        },
        "source_verified_outcome_ingestion_execution_commit": if commit_schema_ok { commit } else { Value::Null },
        "verified_outcome_ingestion_apply_decision": if apply_schema_ok { apply_decision } else { Value::Null },
        "verified_outcome_ingestion_apply_gate_performed_by_this_tool": true,
        "verified_outcome_ingestion_performed_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure verified outcome ingestion apply gate: emits a bounded writer-ready package without durable writes, memory/store access, MCP exposure, world-verdict persistence, or verified-outcome ingestion"
    })
}

pub fn render_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(
    apply: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Verified Outcome Ingestion Apply Gate"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &apply["schema"]);
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_apply_verdict",
        &apply["verified_outcome_ingestion_apply_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &apply["status"]);
    push_markdown_kv(&mut lines, "reason", &apply["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_verified_outcome_ingestion_execution_commit_verdict",
        &apply["source_verified_outcome_ingestion_execution_commit_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_apply_decision_schema",
        &apply["verified_outcome_ingestion_apply_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &apply["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Verified Outcome Ingestion Apply".to_string());
    lines.push(String::new());
    for key in [
        "apply_decision_id",
        "commit_decision_id",
        "source_execution_decision_id",
        "source_ingestion_decision_id",
        "source_rewrite_decision_id",
        "source_review_decision_id",
        "write_evidence_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision_kind",
        "decision",
        "apply_reason",
        "previous_world_verdict",
        "verified_world_verdict",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "outcome_record_key",
        "outcome_record_digest",
        "persisted_outcome_record_key",
        "persisted_outcome_record_digest",
        "commit_package_confirmed",
        "verified_outcome_package_confirmed",
        "reviewer_attestation_present",
        "evidence_lineage_preserved",
        "ready_for_verified_outcome_ingestion_writer",
        "verified_outcome_ingestion_apply_gate_output_only",
        "verified_outcome_ingestion_writer_allowed_after_gate",
        "verified_outcome_ingested_by_this_tool",
        "world_verdict_persisted_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed_by_this_tool",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &apply["verified_outcome_ingestion_apply"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_invoke_verified_outcome_ingestion_writer_after_apply",
        "may_execute_verified_outcome_ingestion_by_this_tool",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_ingestion_writer",
    ] {
        push_markdown_kv(&mut lines, key, &apply["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
}

pub fn build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(
    input: &Value,
) -> Value {
    let (input_kind, apply_gate, writer_decision) =
        extract_runtime_executor_verified_outcome_ingestion_writer_input(input);
    let apply_schema_ok = apply_gate.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_GATE_SCHEMA,
        );
    let writer_schema_ok = writer_decision.get("schema").and_then(Value::as_str)
        == Some(LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_DECISION_SCHEMA);
    let apply = &apply_gate["verified_outcome_ingestion_apply"];
    let apply_guardrails = &apply_gate["guardrails"];
    let apply_contract = &apply_gate["agent_action_contract"];
    let writer_scope = &writer_decision["source_verified_outcome_ingestion_apply_scope"];

    let mut failure_reasons = Vec::new();
    if !apply_schema_ok {
        failure_reasons
            .push("runtime_executor_verified_outcome_ingestion_apply_gate_required".to_string());
    }
    if apply_schema_ok
        && apply_gate["verified_outcome_ingestion_apply_verdict"]
            != "ready_for_verified_outcome_ingestion_writer"
    {
        failure_reasons.push("source_verified_outcome_ingestion_apply_gate_not_ready".to_string());
    }
    if apply_schema_ok && apply_gate["next_allowed_gate"] != "verified_outcome_ingestion_writer" {
        failure_reasons
            .push("source_verified_outcome_ingestion_apply_gate_next_gate_mismatch".to_string());
    }
    if apply_schema_ok && apply["ready_for_verified_outcome_ingestion_writer"] != true {
        failure_reasons.push("source_apply_gate_not_ready_for_writer".to_string());
    }
    if apply_schema_ok && apply["previous_world_verdict"] != "not_verified" {
        failure_reasons.push("source_previous_world_verdict_must_be_not_verified".to_string());
    }
    if apply_schema_ok && apply["verified_world_verdict"] != "verified" {
        failure_reasons.push("source_verified_world_verdict_must_be_verified".to_string());
    }
    if apply_schema_ok
        && (apply["verified_outcome_ingestion_apply_gate_output_only"] != true
            || apply["verified_outcome_ingested_by_this_tool"] != false
            || apply["world_verdict_persisted_by_this_tool"] != false
            || apply["durable_outcome_record_written_by_this_tool"] != false
            || apply["memory_write_allowed"] != false
            || apply["outcome_ingestion_allowed_by_this_tool"] != false)
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_apply_boundary_not_output_only".to_string());
    }
    if apply_schema_ok
        && (apply_gate["verified_outcome_ingestion_performed_by_this_tool"] != false
            || apply_gate["verified_outcome_ingested_by_this_tool"] != false
            || apply_gate["world_verdict_persisted_by_this_tool"] != false
            || apply_gate["durable_outcome_record_written_by_this_tool"] != false
            || apply_gate["writes_state"] != false
            || apply_gate["store_access_required"] != false
            || apply_gate["mcp_tool_registered"] != false)
    {
        failure_reasons
            .push("source_verified_outcome_ingestion_apply_gate_must_be_output_only".to_string());
    }
    if apply_schema_ok
        && (apply_guardrails["read_only"] != true
            || apply_guardrails["writes_state"] != false
            || apply_guardrails["performs_verified_outcome_ingestion"] != false
            || apply_guardrails["outcome_ingestion_allowed_by_this_tool"] != false
            || apply_guardrails["persists_world_verdict"] != false
            || apply_guardrails["persists_outcome_record"] != false)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_apply_gate_guardrails_not_protective".to_string(),
        );
    }
    if apply_schema_ok
        && (apply_contract["may_invoke_verified_outcome_ingestion_writer_after_apply"] != true
            || apply_contract["may_execute_verified_outcome_ingestion_by_this_tool"] != false
            || apply_contract["require_separate_verified_outcome_ingestion_writer"] != true
            || apply_contract["do_not_ingest_outcome"] != true
            || apply_contract["do_not_write_memory"] != true
            || apply_contract["do_not_persist_world_verdict"] != true
            || apply_contract["do_not_persist_outcome_record"] != true)
    {
        failure_reasons.push(
            "source_verified_outcome_ingestion_apply_gate_contract_not_protective".to_string(),
        );
    }
    if !writer_schema_ok {
        failure_reasons
            .push("explicit_verified_outcome_ingestion_writer_decision_required".to_string());
    }
    if writer_schema_ok && writer_decision["writer_decision_id"].as_str().is_none() {
        failure_reasons.push("verified_outcome_ingestion_writer_decision_id_required".to_string());
    }
    if writer_schema_ok && writer_decision["decision_kind"] != "verified_outcome_ingestion_writer" {
        failure_reasons
            .push("verified_outcome_ingestion_writer_decision_kind_required".to_string());
    }
    if writer_schema_ok
        && writer_decision["decision"] != "approved_for_verified_outcome_ingestion_writer_execution"
    {
        failure_reasons.push("verified_outcome_ingestion_writer_decision_not_approved".to_string());
    }
    if writer_schema_ok && writer_decision["source_world_verdict"] != "not_verified" {
        failure_reasons
            .push("verified_outcome_ingestion_writer_source_must_be_not_verified".to_string());
    }
    if writer_schema_ok && writer_decision["verified_world_verdict"] != "verified" {
        failure_reasons
            .push("verified_outcome_ingestion_writer_verdict_must_be_verified".to_string());
    }
    if writer_schema_ok
        && writer_decision["reviewed_verified_outcome_ingestion_apply_verdict"]
            != "ready_for_verified_outcome_ingestion_writer"
    {
        failure_reasons
            .push("verified_outcome_ingestion_writer_must_review_ready_g21_apply".to_string());
    }
    for (key, reason) in [
        (
            "apply_package_confirmed",
            "verified_outcome_ingestion_writer_requires_apply_package",
        ),
        (
            "commit_package_confirmed",
            "verified_outcome_ingestion_writer_requires_commit_package",
        ),
        (
            "verified_outcome_package_confirmed",
            "verified_outcome_ingestion_writer_requires_verified_package",
        ),
        (
            "writer_payload_confirmed",
            "verified_outcome_ingestion_writer_requires_payload",
        ),
        (
            "writer_destination_confirmed",
            "verified_outcome_ingestion_writer_requires_destination",
        ),
        (
            "writer_idempotency_confirmed",
            "verified_outcome_ingestion_writer_requires_idempotency",
        ),
        (
            "writer_boundary_acknowledged",
            "verified_outcome_ingestion_writer_requires_writer_boundary",
        ),
        (
            "rollback_plan_confirmed",
            "verified_outcome_ingestion_writer_requires_rollback_plan",
        ),
    ] {
        if writer_schema_ok && writer_decision[key] != true {
            failure_reasons.push(reason.to_string());
        }
    }
    if writer_schema_ok && writer_decision["outcome_ingestion_allowed_by_this_tool"] != false {
        failure_reasons.push(
            "verified_outcome_ingestion_writer_must_not_allow_ingestion_by_this_tool".to_string(),
        );
    }
    if writer_schema_ok && writer_decision["memory_write_allowed"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_writer_must_not_allow_memory_write".to_string());
    }
    if writer_schema_ok && writer_decision["verified_outcome_ingested_by_this_tool"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_writer_must_not_ingest_outcome".to_string());
    }
    if writer_schema_ok && writer_decision["durable_outcome_record_written_by_this_tool"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_writer_must_not_write_outcome_record".to_string());
    }
    if writer_schema_ok && writer_decision["world_verdict_persisted_by_this_tool"] != false {
        failure_reasons
            .push("verified_outcome_ingestion_writer_must_not_persist_verdict".to_string());
    }

    for (scope_key, source_key, reason) in [
        (
            "apply_decision_id",
            "apply_decision_id",
            "verified_outcome_ingestion_writer_apply_decision_scope_mismatch",
        ),
        (
            "commit_decision_id",
            "commit_decision_id",
            "verified_outcome_ingestion_writer_commit_decision_scope_mismatch",
        ),
        (
            "source_execution_decision_id",
            "source_execution_decision_id",
            "verified_outcome_ingestion_writer_execution_decision_scope_mismatch",
        ),
        (
            "source_ingestion_decision_id",
            "source_ingestion_decision_id",
            "verified_outcome_ingestion_writer_ingestion_decision_scope_mismatch",
        ),
        (
            "source_rewrite_decision_id",
            "source_rewrite_decision_id",
            "verified_outcome_ingestion_writer_rewrite_decision_scope_mismatch",
        ),
        (
            "source_review_decision_id",
            "source_review_decision_id",
            "verified_outcome_ingestion_writer_review_decision_scope_mismatch",
        ),
        (
            "write_evidence_id",
            "write_evidence_id",
            "verified_outcome_ingestion_writer_evidence_scope_mismatch",
        ),
        (
            "world_id",
            "world_id",
            "verified_outcome_ingestion_writer_world_scope_mismatch",
        ),
        (
            "branch_id",
            "branch_id",
            "verified_outcome_ingestion_writer_branch_scope_mismatch",
        ),
        (
            "runtime_generation",
            "runtime_generation",
            "verified_outcome_ingestion_writer_generation_scope_mismatch",
        ),
        (
            "patch_id",
            "patch_id",
            "verified_outcome_ingestion_writer_patch_scope_mismatch",
        ),
        (
            "outcome_record_candidate_id",
            "outcome_record_candidate_id",
            "verified_outcome_ingestion_writer_outcome_candidate_scope_mismatch",
        ),
        (
            "outcome_record_schema",
            "outcome_record_schema",
            "verified_outcome_ingestion_writer_outcome_schema_scope_mismatch",
        ),
        (
            "idempotency_key",
            "idempotency_key",
            "verified_outcome_ingestion_writer_idempotency_scope_mismatch",
        ),
        (
            "outcome_payload_digest",
            "outcome_payload_digest",
            "verified_outcome_ingestion_writer_payload_digest_scope_mismatch",
        ),
        (
            "write_destination",
            "write_destination",
            "verified_outcome_ingestion_writer_destination_scope_mismatch",
        ),
        (
            "outcome_record_key",
            "outcome_record_key",
            "verified_outcome_ingestion_writer_key_scope_mismatch",
        ),
        (
            "outcome_record_digest",
            "outcome_record_digest",
            "verified_outcome_ingestion_writer_digest_scope_mismatch",
        ),
        (
            "persisted_outcome_record_key",
            "persisted_outcome_record_key",
            "verified_outcome_ingestion_writer_persisted_key_scope_mismatch",
        ),
        (
            "persisted_outcome_record_digest",
            "persisted_outcome_record_digest",
            "verified_outcome_ingestion_writer_persisted_digest_scope_mismatch",
        ),
    ] {
        if apply_schema_ok && writer_schema_ok && writer_scope[scope_key] != apply[source_key] {
            failure_reasons.push(reason.to_string());
        }
    }

    let ready = failure_reasons.is_empty();
    let reason = if ready {
        "verified_outcome_ingestion_writer_ready_for_execution".to_string()
    } else {
        failure_reasons
            .first()
            .cloned()
            .unwrap_or_else(|| "verified_outcome_ingestion_writer_blocked".to_string())
    };

    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_SCHEMA,
        "input_kind": input_kind,
        "source_schema": apply_gate.get("schema").cloned().unwrap_or(Value::Null),
        "source_verified_outcome_ingestion_apply_verdict": apply_gate
            .get("verified_outcome_ingestion_apply_verdict")
            .cloned()
            .unwrap_or(Value::Null),
        "source_world_verdict": apply.get("previous_world_verdict").cloned().unwrap_or(Value::Null),
        "verified_world_verdict": apply.get("verified_world_verdict").cloned().unwrap_or(Value::Null),
        "verified_outcome_ingestion_writer_decision_schema": writer_decision.get("schema").cloned().unwrap_or(Value::Null),
        "verified_outcome_ingestion_writer_verdict": if ready { "ready_for_verified_outcome_ingestion_writer_execution" } else { "blocked" },
        "status": if ready { "ready" } else { "blocked" },
        "reason": reason,
        "failure_reasons": unique_strings(failure_reasons),
        "guardrails": runtime_executor_verified_outcome_ingestion_writer_guardrails(),
        "verified_outcome_ingestion_writer": {
            "writer_decision_id": if ready { writer_decision.get("writer_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "apply_decision_id": if ready { writer_scope.get("apply_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "commit_decision_id": if ready { writer_scope.get("commit_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_execution_decision_id": if ready { writer_scope.get("source_execution_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_ingestion_decision_id": if ready { writer_scope.get("source_ingestion_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_rewrite_decision_id": if ready { writer_scope.get("source_rewrite_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "source_review_decision_id": if ready { writer_scope.get("source_review_decision_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_evidence_id": if ready { writer_scope.get("write_evidence_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "world_id": if ready { writer_scope.get("world_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "branch_id": if ready { writer_scope.get("branch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "runtime_generation": if ready { writer_scope.get("runtime_generation").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "patch_id": if ready { writer_scope.get("patch_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision_kind": if ready { writer_decision.get("decision_kind").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "decision": if ready { writer_decision.get("decision").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "writer_reason": if ready { writer_decision.get("writer_reason").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "previous_world_verdict": if ready { writer_decision.get("source_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_world_verdict": if ready { writer_decision.get("verified_world_verdict").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_candidate_id": if ready { writer_scope.get("outcome_record_candidate_id").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_schema": if ready { writer_scope.get("outcome_record_schema").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "idempotency_key": if ready { writer_scope.get("idempotency_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_payload_digest": if ready { writer_scope.get("outcome_payload_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "write_destination": if ready { writer_scope.get("write_destination").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_key": if ready { writer_scope.get("outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "outcome_record_digest": if ready { writer_scope.get("outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_key": if ready { writer_scope.get("persisted_outcome_record_key").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "persisted_outcome_record_digest": if ready { writer_scope.get("persisted_outcome_record_digest").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "apply_package_confirmed": if ready { writer_decision.get("apply_package_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "commit_package_confirmed": if ready { writer_decision.get("commit_package_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "verified_outcome_package_confirmed": if ready { writer_decision.get("verified_outcome_package_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "writer_payload_confirmed": if ready { writer_decision.get("writer_payload_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "writer_destination_confirmed": if ready { writer_decision.get("writer_destination_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "writer_idempotency_confirmed": if ready { writer_decision.get("writer_idempotency_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "rollback_plan_confirmed": if ready { writer_decision.get("rollback_plan_confirmed").cloned().unwrap_or(Value::Null) } else { Value::Null },
            "ready_for_verified_outcome_ingestion_writer_execution": ready,
            "verified_outcome_ingestion_writer_output_only": true,
            "verified_outcome_ingestion_writer_execution_allowed_after_gate": ready,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed_by_this_tool": false
        },
        "next_allowed_gate": if ready { "verified_outcome_ingestion_writer_execution" } else { "repair_verified_outcome_ingestion_writer_input" },
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_writer_gate_only",
            "may_invoke_verified_outcome_ingestion_writer_execution_after_writer": ready,
            "may_execute_verified_outcome_ingestion_by_this_tool": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_writer_execution": true
        },
        "source_verified_outcome_ingestion_apply_gate": if apply_schema_ok { apply_gate } else { Value::Null },
        "verified_outcome_ingestion_writer_decision": if writer_schema_ok { writer_decision } else { Value::Null },
        "verified_outcome_ingestion_writer_gate_performed_by_this_tool": true,
        "verified_outcome_ingestion_performed_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "note": "pure verified outcome ingestion writer gate: emits a bounded writer-execution package without durable writes, memory/store access, MCP exposure, world-verdict persistence, or verified-outcome ingestion"
    })
}

pub fn render_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(
    writer: &Value,
) -> String {
    let mut lines = Vec::new();
    lines.push(
        "# LSWR Interaction Feedback Runtime Executor Verified Outcome Ingestion Writer"
            .to_string(),
    );
    lines.push(String::new());
    push_markdown_kv(&mut lines, "schema", &writer["schema"]);
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_writer_verdict",
        &writer["verified_outcome_ingestion_writer_verdict"],
    );
    push_markdown_kv(&mut lines, "status", &writer["status"]);
    push_markdown_kv(&mut lines, "reason", &writer["reason"]);
    push_markdown_kv(
        &mut lines,
        "source_verified_outcome_ingestion_apply_verdict",
        &writer["source_verified_outcome_ingestion_apply_verdict"],
    );
    push_markdown_kv(
        &mut lines,
        "verified_outcome_ingestion_writer_decision_schema",
        &writer["verified_outcome_ingestion_writer_decision_schema"],
    );
    push_markdown_kv(&mut lines, "failure_reasons", &writer["failure_reasons"]);

    lines.push(String::new());
    lines.push("## Verified Outcome Ingestion Writer".to_string());
    lines.push(String::new());
    for key in [
        "writer_decision_id",
        "apply_decision_id",
        "commit_decision_id",
        "source_execution_decision_id",
        "source_ingestion_decision_id",
        "source_rewrite_decision_id",
        "source_review_decision_id",
        "write_evidence_id",
        "world_id",
        "branch_id",
        "runtime_generation",
        "patch_id",
        "decision_kind",
        "decision",
        "writer_reason",
        "previous_world_verdict",
        "verified_world_verdict",
        "outcome_record_candidate_id",
        "outcome_record_schema",
        "idempotency_key",
        "outcome_payload_digest",
        "outcome_record_key",
        "outcome_record_digest",
        "persisted_outcome_record_key",
        "persisted_outcome_record_digest",
        "apply_package_confirmed",
        "commit_package_confirmed",
        "verified_outcome_package_confirmed",
        "writer_payload_confirmed",
        "writer_destination_confirmed",
        "writer_idempotency_confirmed",
        "rollback_plan_confirmed",
        "ready_for_verified_outcome_ingestion_writer_execution",
        "verified_outcome_ingestion_writer_output_only",
        "verified_outcome_ingestion_writer_execution_allowed_after_gate",
        "verified_outcome_ingested_by_this_tool",
        "world_verdict_persisted_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed_by_this_tool",
    ] {
        push_markdown_kv(
            &mut lines,
            key,
            &writer["verified_outcome_ingestion_writer"][key],
        );
    }

    lines.push(String::new());
    lines.push("## Agent Action Contract".to_string());
    lines.push(String::new());
    for key in [
        "mode",
        "may_invoke_verified_outcome_ingestion_writer_execution_after_writer",
        "may_execute_verified_outcome_ingestion_by_this_tool",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_ingestion_writer_execution",
    ] {
        push_markdown_kv(&mut lines, key, &writer["agent_action_contract"][key]);
    }

    lines.push(String::new());
    lines.join("\n")
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
            return ("evidence_packet", Some(input.clone()), None);
        }
        Some(LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA) => {
            return (
                "fixture",
                Some(build_interaction_feedback_evidence_packet(input)),
                None,
            );
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

fn next_revision_plan_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "implicit_live_runtime_lookup_allowed": false,
        "default_profile_exposure_allowed": false,
        "outcome_ingestion_allowed": false,
        "feedback_changes_world_verdict_allowed": false,
        "applies_patch": false
    })
}

fn semantic_patch_draft_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "implicit_live_runtime_lookup_allowed": false,
        "default_profile_exposure_allowed": false,
        "outcome_ingestion_allowed": false,
        "feedback_changes_world_verdict_allowed": false,
        "applies_patch": false
    })
}

fn semantic_patch_operation_hint(next_revision: &Value) -> &'static str {
    let feedback_issue = next_revision["feedback_issue"].as_str().unwrap_or("");
    let failed_clause_ids = next_revision["failed_clause_ids"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let failed_walkway = failed_clause_ids
        .iter()
        .any(|clause| clause.as_str().unwrap_or("").contains("walkway_clearance"));

    if feedback_issue == "visual_density_too_high" && failed_walkway {
        "increase_walkway_clearance_by_repositioning_entity"
    } else {
        "revise_selected_entities_from_feedback"
    }
}

fn semantic_patch_reason(next_revision: &Value) -> String {
    let feedback_issue = next_revision["feedback_issue"]
        .as_str()
        .unwrap_or("unknown_feedback_issue");
    let failed_clause_ids = markdown_value(&next_revision["failed_clause_ids"]);
    format!(
        "Draft a revision that addresses `{feedback_issue}` while preserving failed verification clauses `{failed_clause_ids}` as required evidence."
    )
}

fn semantic_patch_expected_effect_requirements(next_revision: &Value) -> Value {
    let mut requirements = vec![json!({
        "target": next_revision
            .get("selected_entities")
            .and_then(Value::as_array)
            .and_then(|entities| entities.first())
            .cloned()
            .unwrap_or(Value::Null),
        "metric": "screen_area",
        "to_op": ">",
        "to_value": 0.0,
        "source": "preserve_visible_entity_readability"
    })];

    let failed_clause_ids = next_revision["failed_clause_ids"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    if failed_clause_ids
        .iter()
        .any(|clause| clause.as_str().unwrap_or("").contains("walkway_clearance"))
    {
        requirements.push(json!({
            "target": "arrival_area.main_walkway",
            "metric": "walkway_clearance_cells",
            "to_op": ">=",
            "to_value": 2,
            "source": "failed_clause_repair"
        }));
    }

    Value::Array(requirements)
}

fn extract_execution_preflight_input(input: &Value) -> (&'static str, Value, Option<Value>) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA)
    {
        return ("semantic_patch_draft", input.clone(), None);
    }

    if let Some(draft) = input.get("draft") {
        let normalized_draft = if draft.get("schema").and_then(Value::as_str)
            == Some(LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA)
        {
            draft.clone()
        } else {
            build_interaction_feedback_semantic_patch_draft(draft)
        };
        return (
            "draft_wrapper",
            normalized_draft,
            input.get("argument_context").cloned(),
        );
    }

    (
        "implicit_draft_from_input",
        build_interaction_feedback_semantic_patch_draft(input),
        input.get("argument_context").cloned(),
    )
}

fn extract_apply_request_input(input: &Value) -> (&'static str, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_SCHEMA)
    {
        return ("patch_execution_preflight", input.clone());
    }

    if let Some(preflight) = input.get("preflight") {
        return ("preflight_wrapper", preflight.clone());
    }

    ("invalid_input", input.clone())
}

fn extract_runtime_executor_design_preflight_input(input: &Value) -> (&'static str, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA)
    {
        return ("patch_apply_request", input.clone());
    }

    if let Some(apply_request) = input.get("apply_request") {
        return ("apply_request_wrapper", apply_request.clone());
    }

    ("invalid_input", input.clone())
}

fn extract_live_runtime_lookup_design_preflight_input(input: &Value) -> (&'static str, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA)
    {
        return ("runtime_executor_design_preflight", input.clone());
    }

    if let Some(design_preflight) = input.get("design_preflight") {
        return ("design_preflight_wrapper", design_preflight.clone());
    }

    ("invalid_input", input.clone())
}

fn extract_runtime_executor_live_lookup_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA)
    {
        return (
            "runtime_executor_design_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let design_preflight = input
        .get("design_preflight")
        .or_else(|| input.get("runtime_executor_design_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let lookup_snapshot = input
        .get("lookup_snapshot")
        .or_else(|| input.get("live_lookup_snapshot"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("design_preflight").is_some()
        || input.get("runtime_executor_design_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("lookup_snapshot").is_some()
        || input.get("live_lookup_snapshot").is_some()
    {
        (
            "design_preflight_with_lookup_snapshot_wrapper",
            design_preflight,
            lookup_snapshot,
        )
    } else {
        ("invalid_input", design_preflight, lookup_snapshot)
    }
}

fn extract_runtime_executor_operator_submission_token_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA)
    {
        return (
            "runtime_executor_live_lookup_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let lookup_preflight = input
        .get("lookup_preflight")
        .or_else(|| input.get("runtime_executor_live_lookup_preflight"))
        .or_else(|| input.get("live_lookup_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let operator_decision = input
        .get("operator_decision")
        .or_else(|| input.get("operator_submission_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("lookup_preflight").is_some()
        || input
            .get("runtime_executor_live_lookup_preflight")
            .is_some()
        || input.get("live_lookup_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("operator_decision").is_some()
        || input.get("operator_submission_decision").is_some()
    {
        (
            "live_lookup_preflight_with_operator_decision_wrapper",
            lookup_preflight,
            operator_decision,
        )
    } else {
        ("invalid_input", lookup_preflight, operator_decision)
    }
}

fn extract_runtime_executor_patch_application_gate_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_operator_submission_token_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let submission_preflight = input
        .get("submission_token_preflight")
        .or_else(|| input.get("operator_submission_token_preflight"))
        .or_else(|| input.get("runtime_executor_operator_submission_token_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let gate_decision = input
        .get("patch_application_gate_decision")
        .or_else(|| input.get("gate_decision"))
        .or_else(|| input.get("patch_application_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("submission_token_preflight").is_some()
        || input.get("operator_submission_token_preflight").is_some()
        || input
            .get("runtime_executor_operator_submission_token_preflight")
            .is_some()
        || input.get("preflight").is_some()
        || input.get("patch_application_gate_decision").is_some()
        || input.get("gate_decision").is_some()
        || input.get("patch_application_decision").is_some()
    {
        (
            "operator_submission_token_preflight_with_patch_application_gate_decision_wrapper",
            submission_preflight,
            gate_decision,
        )
    } else {
        ("invalid_input", submission_preflight, gate_decision)
    }
}

fn extract_runtime_executor_patch_executor_invocation_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_SCHEMA)
    {
        return (
            "runtime_executor_patch_application_gate_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let gate_preflight = input
        .get("patch_application_gate_preflight")
        .or_else(|| input.get("runtime_executor_patch_application_gate_preflight"))
        .or_else(|| input.get("gate_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let invocation_decision = input
        .get("patch_executor_invocation_decision")
        .or_else(|| input.get("executor_invocation_decision"))
        .or_else(|| input.get("invocation_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("patch_application_gate_preflight").is_some()
        || input
            .get("runtime_executor_patch_application_gate_preflight")
            .is_some()
        || input.get("gate_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("patch_executor_invocation_decision").is_some()
        || input.get("executor_invocation_decision").is_some()
        || input.get("invocation_decision").is_some()
    {
        (
            "patch_application_gate_preflight_with_patch_executor_invocation_decision_wrapper",
            gate_preflight,
            invocation_decision,
        )
    } else {
        ("invalid_input", gate_preflight, invocation_decision)
    }
}

fn extract_runtime_executor_patch_runtime_application_evidence_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_patch_executor_invocation_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let invocation_preflight = input
        .get("patch_executor_invocation_preflight")
        .or_else(|| input.get("runtime_executor_patch_executor_invocation_preflight"))
        .or_else(|| input.get("invocation_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let application_evidence = input
        .get("patch_runtime_application_evidence")
        .or_else(|| input.get("runtime_application_evidence"))
        .or_else(|| input.get("application_evidence"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("patch_executor_invocation_preflight").is_some()
        || input
            .get("runtime_executor_patch_executor_invocation_preflight")
            .is_some()
        || input.get("invocation_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("patch_runtime_application_evidence").is_some()
        || input.get("runtime_application_evidence").is_some()
        || input.get("application_evidence").is_some()
    {
        (
            "patch_executor_invocation_preflight_with_runtime_application_evidence_wrapper",
            invocation_preflight,
            application_evidence,
        )
    } else {
        ("invalid_input", invocation_preflight, application_evidence)
    }
}

fn extract_runtime_executor_post_apply_verification_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_patch_runtime_application_evidence_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let application_preflight = input
        .get("patch_runtime_application_evidence_preflight")
        .or_else(|| input.get("runtime_application_evidence_preflight"))
        .or_else(|| input.get("application_evidence_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let verification_evidence = input
        .get("post_apply_verification_evidence")
        .or_else(|| input.get("verification_evidence"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("patch_runtime_application_evidence_preflight")
        .is_some()
        || input
            .get("runtime_application_evidence_preflight")
            .is_some()
        || input.get("application_evidence_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("post_apply_verification_evidence").is_some()
        || input.get("verification_evidence").is_some()
    {
        (
            "runtime_application_evidence_preflight_with_post_apply_verification_evidence_wrapper",
            application_preflight,
            verification_evidence,
        )
    } else {
        (
            "invalid_input",
            application_preflight,
            verification_evidence,
        )
    }
}

fn extract_runtime_executor_outcome_ingestion_review_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_PREFLIGHT_SCHEMA)
    {
        return (
            "runtime_executor_post_apply_verification_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let verification_preflight = input
        .get("post_apply_verification_preflight")
        .or_else(|| input.get("runtime_executor_post_apply_verification_preflight"))
        .or_else(|| input.get("verification_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let review_decision = input
        .get("outcome_ingestion_review_decision")
        .or_else(|| input.get("ingestion_review_decision"))
        .or_else(|| input.get("review_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("post_apply_verification_preflight").is_some()
        || input
            .get("runtime_executor_post_apply_verification_preflight")
            .is_some()
        || input.get("verification_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("outcome_ingestion_review_decision").is_some()
        || input.get("ingestion_review_decision").is_some()
        || input.get("review_decision").is_some()
    {
        (
            "post_apply_verification_preflight_with_outcome_ingestion_review_decision_wrapper",
            verification_preflight,
            review_decision,
        )
    } else {
        ("invalid_input", verification_preflight, review_decision)
    }
}

fn extract_runtime_executor_durable_outcome_ingestion_gate_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_outcome_ingestion_review_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let review_preflight = input
        .get("outcome_ingestion_review_preflight")
        .or_else(|| input.get("runtime_executor_outcome_ingestion_review_preflight"))
        .or_else(|| input.get("ingestion_review_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let gate_decision = input
        .get("durable_outcome_ingestion_gate_decision")
        .or_else(|| input.get("outcome_ingestion_gate_decision"))
        .or_else(|| input.get("gate_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("outcome_ingestion_review_preflight").is_some()
        || input
            .get("runtime_executor_outcome_ingestion_review_preflight")
            .is_some()
        || input.get("ingestion_review_preflight").is_some()
        || input.get("preflight").is_some()
        || input
            .get("durable_outcome_ingestion_gate_decision")
            .is_some()
        || input.get("outcome_ingestion_gate_decision").is_some()
        || input.get("gate_decision").is_some()
    {
        (
            "outcome_ingestion_review_preflight_with_durable_outcome_ingestion_gate_decision_wrapper",
            review_preflight,
            gate_decision,
        )
    } else {
        ("invalid_input", review_preflight, gate_decision)
    }
}

fn extract_runtime_executor_durable_outcome_ingestion_execution_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_ingestion_gate_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let gate_preflight = input
        .get("durable_outcome_ingestion_gate_preflight")
        .or_else(|| input.get("runtime_executor_durable_outcome_ingestion_gate_preflight"))
        .or_else(|| input.get("outcome_ingestion_gate_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let execution_decision = input
        .get("durable_outcome_ingestion_execution_decision")
        .or_else(|| input.get("outcome_ingestion_execution_decision"))
        .or_else(|| input.get("execution_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_ingestion_gate_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_ingestion_gate_preflight")
            .is_some()
        || input.get("outcome_ingestion_gate_preflight").is_some()
        || input.get("preflight").is_some()
        || input
            .get("durable_outcome_ingestion_execution_decision")
            .is_some()
        || input.get("outcome_ingestion_execution_decision").is_some()
        || input.get("execution_decision").is_some()
    {
        (
            "durable_outcome_ingestion_gate_preflight_with_durable_outcome_ingestion_execution_decision_wrapper",
            gate_preflight,
            execution_decision,
        )
    } else {
        ("invalid_input", gate_preflight, execution_decision)
    }
}

fn extract_runtime_executor_durable_outcome_write_implementation_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_ingestion_execution_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let execution_preflight = input
        .get("durable_outcome_ingestion_execution_preflight")
        .or_else(|| input.get("runtime_executor_durable_outcome_ingestion_execution_preflight"))
        .or_else(|| input.get("outcome_ingestion_execution_preflight"))
        .or_else(|| input.get("execution_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let write_decision = input
        .get("durable_outcome_write_implementation_decision")
        .or_else(|| input.get("outcome_write_implementation_decision"))
        .or_else(|| input.get("write_implementation_decision"))
        .or_else(|| input.get("write_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_ingestion_execution_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_ingestion_execution_preflight")
            .is_some()
        || input.get("outcome_ingestion_execution_preflight").is_some()
        || input.get("execution_preflight").is_some()
        || input.get("preflight").is_some()
        || input
            .get("durable_outcome_write_implementation_decision")
            .is_some()
        || input.get("outcome_write_implementation_decision").is_some()
        || input.get("write_implementation_decision").is_some()
        || input.get("write_decision").is_some()
    {
        (
            "durable_outcome_ingestion_execution_preflight_with_durable_outcome_write_implementation_decision_wrapper",
            execution_preflight,
            write_decision,
        )
    } else {
        ("invalid_input", execution_preflight, write_decision)
    }
}

fn extract_runtime_executor_durable_outcome_record_write_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_write_implementation_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let write_preflight = input
        .get("durable_outcome_write_implementation_preflight")
        .or_else(|| input.get("runtime_executor_durable_outcome_write_implementation_preflight"))
        .or_else(|| input.get("outcome_write_implementation_preflight"))
        .or_else(|| input.get("write_implementation_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let record_decision = input
        .get("durable_outcome_record_write_decision")
        .or_else(|| input.get("outcome_record_write_decision"))
        .or_else(|| input.get("record_write_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_write_implementation_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_write_implementation_preflight")
            .is_some()
        || input
            .get("outcome_write_implementation_preflight")
            .is_some()
        || input.get("write_implementation_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("durable_outcome_record_write_decision").is_some()
        || input.get("outcome_record_write_decision").is_some()
        || input.get("record_write_decision").is_some()
    {
        (
            "durable_outcome_write_implementation_preflight_with_durable_outcome_record_write_decision_wrapper",
            write_preflight,
            record_decision,
        )
    } else {
        ("invalid_input", write_preflight, record_decision)
    }
}

fn extract_runtime_executor_durable_outcome_record_write_execution_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_record_write_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let record_preflight = input
        .get("durable_outcome_record_write_preflight")
        .or_else(|| input.get("runtime_executor_durable_outcome_record_write_preflight"))
        .or_else(|| input.get("outcome_record_write_preflight"))
        .or_else(|| input.get("record_write_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let execution_decision = input
        .get("durable_outcome_record_write_execution_decision")
        .or_else(|| input.get("outcome_record_write_execution_decision"))
        .or_else(|| input.get("record_write_execution_decision"))
        .or_else(|| input.get("execution_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_record_write_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_record_write_preflight")
            .is_some()
        || input.get("outcome_record_write_preflight").is_some()
        || input.get("record_write_preflight").is_some()
        || input.get("preflight").is_some()
        || input
            .get("durable_outcome_record_write_execution_decision")
            .is_some()
        || input
            .get("outcome_record_write_execution_decision")
            .is_some()
        || input.get("record_write_execution_decision").is_some()
        || input.get("execution_decision").is_some()
    {
        (
            "durable_outcome_record_write_preflight_with_durable_outcome_record_write_execution_decision_wrapper",
            record_preflight,
            execution_decision,
        )
    } else {
        ("invalid_input", record_preflight, execution_decision)
    }
}

fn extract_runtime_executor_durable_outcome_record_persistence_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_record_write_execution_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let execution_preflight = input
        .get("durable_outcome_record_write_execution_preflight")
        .or_else(|| input.get("runtime_executor_durable_outcome_record_write_execution_preflight"))
        .or_else(|| input.get("outcome_record_write_execution_preflight"))
        .or_else(|| input.get("record_write_execution_preflight"))
        .or_else(|| input.get("execution_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let persistence_decision = input
        .get("durable_outcome_record_persistence_decision")
        .or_else(|| input.get("outcome_record_persistence_decision"))
        .or_else(|| input.get("record_persistence_decision"))
        .or_else(|| input.get("persistence_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_record_write_execution_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_record_write_execution_preflight")
            .is_some()
        || input
            .get("outcome_record_write_execution_preflight")
            .is_some()
        || input.get("record_write_execution_preflight").is_some()
        || input.get("execution_preflight").is_some()
        || input.get("preflight").is_some()
        || input
            .get("durable_outcome_record_persistence_decision")
            .is_some()
        || input.get("outcome_record_persistence_decision").is_some()
        || input.get("record_persistence_decision").is_some()
        || input.get("persistence_decision").is_some()
    {
        (
            "durable_outcome_record_write_execution_preflight_with_durable_outcome_record_persistence_decision_wrapper",
            execution_preflight,
            persistence_decision,
        )
    } else {
        ("invalid_input", execution_preflight, persistence_decision)
    }
}

fn extract_runtime_executor_durable_outcome_record_store_write_execution_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_record_persistence_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let persistence_preflight = input
        .get("durable_outcome_record_persistence_preflight")
        .or_else(|| input.get("runtime_executor_durable_outcome_record_persistence_preflight"))
        .or_else(|| input.get("outcome_record_persistence_preflight"))
        .or_else(|| input.get("record_persistence_preflight"))
        .or_else(|| input.get("persistence_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let store_write_decision = input
        .get("durable_outcome_record_store_write_execution_decision")
        .or_else(|| input.get("outcome_record_store_write_execution_decision"))
        .or_else(|| input.get("record_store_write_execution_decision"))
        .or_else(|| input.get("store_write_execution_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_record_persistence_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_record_persistence_preflight")
            .is_some()
        || input.get("outcome_record_persistence_preflight").is_some()
        || input.get("record_persistence_preflight").is_some()
        || input.get("persistence_preflight").is_some()
        || input.get("preflight").is_some()
        || input
            .get("durable_outcome_record_store_write_execution_decision")
            .is_some()
        || input
            .get("outcome_record_store_write_execution_decision")
            .is_some()
        || input.get("record_store_write_execution_decision").is_some()
        || input.get("store_write_execution_decision").is_some()
    {
        (
            "durable_outcome_record_persistence_preflight_with_durable_outcome_record_store_write_execution_decision_wrapper",
            persistence_preflight,
            store_write_decision,
        )
    } else {
        ("invalid_input", persistence_preflight, store_write_decision)
    }
}

fn extract_runtime_executor_durable_outcome_record_write_evidence_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_record_store_write_execution_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let store_write_preflight = input
        .get("durable_outcome_record_store_write_execution_preflight")
        .or_else(|| {
            input.get("runtime_executor_durable_outcome_record_store_write_execution_preflight")
        })
        .or_else(|| input.get("outcome_record_store_write_execution_preflight"))
        .or_else(|| input.get("record_store_write_execution_preflight"))
        .or_else(|| input.get("store_write_execution_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let write_evidence = input
        .get("durable_outcome_record_write_evidence")
        .or_else(|| input.get("outcome_record_write_evidence"))
        .or_else(|| input.get("record_write_evidence"))
        .or_else(|| input.get("write_evidence"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_record_store_write_execution_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_record_store_write_execution_preflight")
            .is_some()
        || input
            .get("outcome_record_store_write_execution_preflight")
            .is_some()
        || input
            .get("record_store_write_execution_preflight")
            .is_some()
        || input.get("store_write_execution_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("durable_outcome_record_write_evidence").is_some()
        || input.get("outcome_record_write_evidence").is_some()
        || input.get("record_write_evidence").is_some()
        || input.get("write_evidence").is_some()
    {
        (
            "durable_outcome_record_store_write_execution_preflight_with_durable_outcome_record_write_evidence_wrapper",
            store_write_preflight,
            write_evidence,
        )
    } else {
        ("invalid_input", store_write_preflight, write_evidence)
    }
}

fn extract_runtime_executor_durable_outcome_record_write_evidence_review_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_record_write_evidence_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let write_evidence_preflight = input
        .get("durable_outcome_record_write_evidence_preflight")
        .or_else(|| input.get("runtime_executor_durable_outcome_record_write_evidence_preflight"))
        .or_else(|| input.get("outcome_record_write_evidence_preflight"))
        .or_else(|| input.get("record_write_evidence_preflight"))
        .or_else(|| input.get("write_evidence_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let review_decision = input
        .get("durable_outcome_record_write_evidence_review_decision")
        .or_else(|| input.get("outcome_record_write_evidence_review_decision"))
        .or_else(|| input.get("record_write_evidence_review_decision"))
        .or_else(|| input.get("write_evidence_review_decision"))
        .or_else(|| input.get("review_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_record_write_evidence_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_record_write_evidence_preflight")
            .is_some()
        || input
            .get("outcome_record_write_evidence_preflight")
            .is_some()
        || input.get("record_write_evidence_preflight").is_some()
        || input.get("write_evidence_preflight").is_some()
        || input.get("preflight").is_some()
        || input
            .get("durable_outcome_record_write_evidence_review_decision")
            .is_some()
        || input
            .get("outcome_record_write_evidence_review_decision")
            .is_some()
        || input.get("record_write_evidence_review_decision").is_some()
        || input.get("write_evidence_review_decision").is_some()
        || input.get("review_decision").is_some()
    {
        (
            "durable_outcome_record_write_evidence_preflight_with_durable_outcome_record_write_evidence_review_decision_wrapper",
            write_evidence_preflight,
            review_decision,
        )
    } else {
        ("invalid_input", write_evidence_preflight, review_decision)
    }
}

fn extract_runtime_executor_world_verdict_rewrite_gate_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_durable_outcome_record_write_evidence_review_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let review_preflight = input
        .get("durable_outcome_record_write_evidence_review_preflight")
        .or_else(|| {
            input.get("runtime_executor_durable_outcome_record_write_evidence_review_preflight")
        })
        .or_else(|| input.get("outcome_record_write_evidence_review_preflight"))
        .or_else(|| input.get("write_evidence_review_preflight"))
        .or_else(|| input.get("review_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let rewrite_decision = input
        .get("world_verdict_rewrite_decision")
        .or_else(|| input.get("verdict_rewrite_decision"))
        .or_else(|| input.get("rewrite_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("durable_outcome_record_write_evidence_review_preflight")
        .is_some()
        || input
            .get("runtime_executor_durable_outcome_record_write_evidence_review_preflight")
            .is_some()
        || input
            .get("outcome_record_write_evidence_review_preflight")
            .is_some()
        || input.get("write_evidence_review_preflight").is_some()
        || input.get("review_preflight").is_some()
        || input.get("preflight").is_some()
        || input.get("world_verdict_rewrite_decision").is_some()
        || input.get("verdict_rewrite_decision").is_some()
        || input.get("rewrite_decision").is_some()
    {
        (
            "durable_outcome_record_write_evidence_review_preflight_with_world_verdict_rewrite_decision_wrapper",
            review_preflight,
            rewrite_decision,
        )
    } else {
        ("invalid_input", review_preflight, rewrite_decision)
    }
}

fn extract_runtime_executor_verified_outcome_ingestion_gate_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA)
    {
        return (
            "runtime_executor_world_verdict_rewrite_gate",
            input.clone(),
            Value::Null,
        );
    }

    let rewrite_gate = input
        .get("world_verdict_rewrite_gate")
        .or_else(|| input.get("runtime_executor_world_verdict_rewrite_gate"))
        .or_else(|| input.get("rewrite_gate"))
        .or_else(|| input.get("gate"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let ingestion_decision = input
        .get("verified_outcome_ingestion_decision")
        .or_else(|| input.get("outcome_ingestion_decision"))
        .or_else(|| input.get("ingestion_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("world_verdict_rewrite_gate").is_some()
        || input
            .get("runtime_executor_world_verdict_rewrite_gate")
            .is_some()
        || input.get("rewrite_gate").is_some()
        || input.get("gate").is_some()
        || input.get("verified_outcome_ingestion_decision").is_some()
        || input.get("outcome_ingestion_decision").is_some()
        || input.get("ingestion_decision").is_some()
    {
        (
            "world_verdict_rewrite_gate_with_verified_outcome_ingestion_decision_wrapper",
            rewrite_gate,
            ingestion_decision,
        )
    } else {
        ("invalid_input", rewrite_gate, ingestion_decision)
    }
}

fn extract_runtime_executor_verified_outcome_ingestion_execution_preflight_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_GATE_SCHEMA)
    {
        return (
            "runtime_executor_verified_outcome_ingestion_gate",
            input.clone(),
            Value::Null,
        );
    }

    let ingestion_gate = input
        .get("verified_outcome_ingestion_gate")
        .or_else(|| input.get("runtime_executor_verified_outcome_ingestion_gate"))
        .or_else(|| input.get("ingestion_gate"))
        .or_else(|| input.get("gate"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let execution_decision = input
        .get("verified_outcome_ingestion_execution_decision")
        .or_else(|| input.get("outcome_ingestion_execution_decision"))
        .or_else(|| input.get("execution_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("verified_outcome_ingestion_gate").is_some()
        || input
            .get("runtime_executor_verified_outcome_ingestion_gate")
            .is_some()
        || input.get("ingestion_gate").is_some()
        || input.get("gate").is_some()
        || input
            .get("verified_outcome_ingestion_execution_decision")
            .is_some()
        || input.get("outcome_ingestion_execution_decision").is_some()
        || input.get("execution_decision").is_some()
    {
        (
            "verified_outcome_ingestion_gate_with_verified_outcome_ingestion_execution_decision_wrapper",
            ingestion_gate,
            execution_decision,
        )
    } else {
        ("invalid_input", ingestion_gate, execution_decision)
    }
}

fn extract_runtime_executor_verified_outcome_ingestion_execution_commit_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
        )
    {
        return (
            "runtime_executor_verified_outcome_ingestion_execution_preflight",
            input.clone(),
            Value::Null,
        );
    }

    let execution_preflight = input
        .get("verified_outcome_ingestion_execution_preflight")
        .or_else(|| input.get("runtime_executor_verified_outcome_ingestion_execution_preflight"))
        .or_else(|| input.get("execution_preflight"))
        .or_else(|| input.get("preflight"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let commit_decision = input
        .get("verified_outcome_ingestion_execution_commit_decision")
        .or_else(|| input.get("outcome_ingestion_execution_commit_decision"))
        .or_else(|| input.get("commit_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("verified_outcome_ingestion_execution_preflight")
        .is_some()
        || input
            .get("runtime_executor_verified_outcome_ingestion_execution_preflight")
            .is_some()
        || input.get("execution_preflight").is_some()
        || input.get("preflight").is_some()
        || input
            .get("verified_outcome_ingestion_execution_commit_decision")
            .is_some()
        || input
            .get("outcome_ingestion_execution_commit_decision")
            .is_some()
        || input.get("commit_decision").is_some()
    {
        (
            "verified_outcome_ingestion_execution_preflight_with_commit_decision_wrapper",
            execution_preflight,
            commit_decision,
        )
    } else {
        ("invalid_input", execution_preflight, commit_decision)
    }
}

fn extract_runtime_executor_verified_outcome_ingestion_apply_gate_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA,
        )
    {
        return (
            "runtime_executor_verified_outcome_ingestion_execution_commit",
            input.clone(),
            Value::Null,
        );
    }

    let commit = input
        .get("verified_outcome_ingestion_execution_commit")
        .or_else(|| input.get("runtime_executor_verified_outcome_ingestion_execution_commit"))
        .or_else(|| input.get("execution_commit"))
        .or_else(|| input.get("commit"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let apply_decision = input
        .get("verified_outcome_ingestion_apply_decision")
        .or_else(|| input.get("outcome_ingestion_apply_decision"))
        .or_else(|| input.get("apply_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input
        .get("verified_outcome_ingestion_execution_commit")
        .is_some()
        || input
            .get("runtime_executor_verified_outcome_ingestion_execution_commit")
            .is_some()
        || input.get("execution_commit").is_some()
        || input.get("commit").is_some()
        || input
            .get("verified_outcome_ingestion_apply_decision")
            .is_some()
        || input.get("outcome_ingestion_apply_decision").is_some()
        || input.get("apply_decision").is_some()
    {
        (
            "verified_outcome_ingestion_execution_commit_with_apply_decision_wrapper",
            commit,
            apply_decision,
        )
    } else {
        ("invalid_input", commit, apply_decision)
    }
}

fn extract_runtime_executor_verified_outcome_ingestion_writer_input(
    input: &Value,
) -> (&'static str, Value, Value) {
    if input.get("schema").and_then(Value::as_str)
        == Some(
            LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_GATE_SCHEMA,
        )
    {
        return (
            "runtime_executor_verified_outcome_ingestion_apply_gate",
            input.clone(),
            Value::Null,
        );
    }

    let apply_gate = input
        .get("verified_outcome_ingestion_apply_gate")
        .or_else(|| input.get("runtime_executor_verified_outcome_ingestion_apply_gate"))
        .or_else(|| input.get("apply_gate"))
        .or_else(|| input.get("apply"))
        .cloned()
        .unwrap_or_else(|| input.clone());
    let writer_decision = input
        .get("verified_outcome_ingestion_writer_decision")
        .or_else(|| input.get("outcome_ingestion_writer_decision"))
        .or_else(|| input.get("writer_decision"))
        .cloned()
        .unwrap_or(Value::Null);

    if input.get("verified_outcome_ingestion_apply_gate").is_some()
        || input
            .get("runtime_executor_verified_outcome_ingestion_apply_gate")
            .is_some()
        || input.get("apply_gate").is_some()
        || input.get("apply").is_some()
        || input
            .get("verified_outcome_ingestion_writer_decision")
            .is_some()
        || input.get("outcome_ingestion_writer_decision").is_some()
        || input.get("writer_decision").is_some()
    {
        (
            "verified_outcome_ingestion_apply_gate_with_writer_decision_wrapper",
            apply_gate,
            writer_decision,
        )
    } else {
        ("invalid_input", apply_gate, writer_decision)
    }
}

fn validate_argument_context(argument_context: Option<&Value>) -> Value {
    let Some(context) = argument_context else {
        return json!({
            "accepted": false,
            "reason": "explicit_argument_context_required",
            "context_schema": Value::Null,
            "selected_argument": Value::Null,
            "live_runtime_queried_by_preflight": false
        });
    };

    if context.get("schema").and_then(Value::as_str)
        != Some(LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA)
    {
        return json!({
            "accepted": false,
            "reason": "argument_context_schema_mismatch",
            "context_schema": context.get("schema").cloned().unwrap_or(Value::Null),
            "selected_argument": Value::Null,
            "live_runtime_queried_by_preflight": false
        });
    }

    if context
        .get("live_runtime_queried_by_preflight")
        .and_then(Value::as_bool)
        != Some(false)
    {
        return json!({
            "accepted": false,
            "reason": "argument_context_claims_preflight_live_runtime_query",
            "context_schema": context.get("schema").cloned().unwrap_or(Value::Null),
            "selected_argument": Value::Null,
            "live_runtime_queried_by_preflight": context
                .get("live_runtime_queried_by_preflight")
                .cloned()
                .unwrap_or(Value::Null)
        });
    }

    let selected_argument = context
        .get("candidate_arguments")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .find(|candidate| {
            candidate.get("argument_path").and_then(Value::as_str) == Some("patch.args.cell")
                && candidate
                    .get("satisfies_expected_effect")
                    .and_then(Value::as_bool)
                    == Some(true)
                && candidate.get("value").is_some()
        })
        .cloned()
        .unwrap_or(Value::Null);

    if selected_argument.is_null() {
        return json!({
            "accepted": false,
            "reason": "no_satisfying_patch_args_cell_candidate",
            "context_schema": context.get("schema").cloned().unwrap_or(Value::Null),
            "selected_argument": Value::Null,
            "live_runtime_queried_by_preflight": false
        });
    }

    json!({
        "accepted": true,
        "reason": "explicit_argument_context_accepted",
        "context_schema": context.get("schema").cloned().unwrap_or(Value::Null),
        "selected_argument": selected_argument,
        "live_runtime_queried_by_preflight": false
    })
}

fn execution_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "implicit_live_runtime_lookup_allowed": false,
        "default_profile_exposure_allowed": false,
        "outcome_ingestion_allowed": false,
        "feedback_changes_world_verdict_allowed": false,
        "applies_patch": false
    })
}

fn apply_request_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "implicit_live_runtime_lookup_allowed": false,
        "default_profile_exposure_allowed": false,
        "submits_apply_request": false,
        "outcome_ingestion_allowed": false,
        "feedback_changes_world_verdict_allowed": false,
        "applies_patch": false,
        "external_executor_required": true
    })
}

fn runtime_executor_design_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "implicit_live_runtime_lookup_allowed": false,
        "default_profile_exposure_allowed": false,
        "submits_apply_request": false,
        "outcome_ingestion_allowed": false,
        "feedback_changes_world_verdict_allowed": false,
        "applies_patch": false,
        "runtime_executor_design_only": true
    })
}

fn live_runtime_lookup_design_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "contacts_live_runtime": false,
        "opens_socket": false,
        "implicit_live_runtime_lookup_allowed": false,
        "default_profile_exposure_allowed": false,
        "submits_apply_request": false,
        "outcome_ingestion_allowed": false,
        "feedback_changes_world_verdict_allowed": false,
        "applies_patch": false,
        "live_runtime_lookup_design_only": true
    })
}

fn runtime_executor_live_lookup_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_explicit_lookup_snapshot": true,
        "lookup_performed_by_this_tool": false,
        "implicit_live_runtime_lookup_allowed": false,
        "default_profile_exposure_allowed": false,
        "submits_apply_request": false,
        "outcome_ingestion_allowed": false,
        "feedback_changes_world_verdict_allowed": false,
        "applies_patch": false,
        "verifies_post_apply_result": false,
        "runtime_executor_live_lookup_preflight_only": true
    })
}

fn runtime_executor_operator_submission_token_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_live_lookup_preflight": true,
        "requires_explicit_operator_decision": true,
        "operator_authority_scope": "operator_submission_token_only",
        "submits_apply_request": false,
        "applies_patch": false,
        "verifies_post_apply_result": false,
        "outcome_ingestion_allowed": false,
        "persists_submission_token": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_operator_submission_token_preflight_only": true
    })
}

fn runtime_executor_patch_application_gate_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_operator_submission_token_preflight": true,
        "requires_explicit_patch_application_gate_decision": true,
        "patch_application_authority_scope": "patch_application_executor_invocation_gate_only",
        "invokes_patch_executor": false,
        "submits_apply_request": false,
        "applies_patch": false,
        "verifies_post_apply_result": false,
        "outcome_ingestion_allowed": false,
        "persists_submission_token": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_patch_application_gate_preflight_only": true
    })
}

fn runtime_executor_patch_executor_invocation_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_patch_application_gate_preflight": true,
        "requires_explicit_patch_executor_invocation_decision": true,
        "patch_executor_invocation_authority_scope": "separate_patch_executor_invocation_only",
        "emits_invocation_request_envelope": true,
        "invokes_patch_executor": false,
        "submits_executor_queue": false,
        "submits_apply_request": false,
        "applies_patch": false,
        "verifies_post_apply_result": false,
        "outcome_ingestion_allowed": false,
        "persists_submission_token": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_patch_executor_invocation_preflight_only": true
    })
}

fn runtime_executor_patch_runtime_application_evidence_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_patch_executor_invocation_preflight": true,
        "requires_explicit_patch_runtime_application_evidence": true,
        "evidence_kind": "external_executor_claim",
        "invokes_patch_executor": false,
        "submits_executor_queue": false,
        "submits_apply_request": false,
        "applies_patch": false,
        "verifies_post_apply_result": false,
        "outcome_ingestion_allowed": false,
        "persists_evidence_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_patch_runtime_application_evidence_preflight_only": true
    })
}

fn runtime_executor_post_apply_verification_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_runtime_application_evidence_preflight": true,
        "requires_explicit_post_apply_verification_evidence": true,
        "evidence_kind": "post_apply_verification",
        "performs_post_apply_verification": false,
        "outcome_ingestion_allowed": false,
        "persists_verification_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_post_apply_verification_preflight_only": true
    })
}

fn runtime_executor_outcome_ingestion_review_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_post_apply_verification_preflight": true,
        "requires_explicit_outcome_ingestion_review_decision": true,
        "review_kind": "outcome_ingestion_review",
        "performs_outcome_ingestion_review": false,
        "durable_ingestion_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_outcome_ingestion_review_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_ingestion_gate_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_outcome_ingestion_review_preflight": true,
        "requires_explicit_durable_outcome_ingestion_gate_decision": true,
        "gate_kind": "durable_outcome_ingestion_gate",
        "performs_durable_outcome_ingestion_gate": false,
        "durable_ingestion_execution_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_ingestion_gate_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_ingestion_execution_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_ingestion_gate_preflight": true,
        "requires_explicit_durable_outcome_ingestion_execution_decision": true,
        "execution_kind": "durable_outcome_ingestion_execution",
        "performs_durable_outcome_ingestion_execution_preflight": true,
        "durable_write_implementation_allowed": false,
        "durable_outcome_ingestion_performed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_ingestion_execution_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_write_implementation_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_ingestion_execution_preflight": true,
        "requires_explicit_durable_outcome_write_implementation_decision": true,
        "write_implementation_kind": "durable_outcome_write_implementation",
        "performs_durable_outcome_write_implementation_preflight": true,
        "durable_record_write_allowed": false,
        "durable_outcome_record_persisted": false,
        "memory_write_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_write_implementation_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_record_write_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_write_implementation_preflight": true,
        "requires_explicit_durable_outcome_record_write_decision": true,
        "record_write_kind": "durable_outcome_record_write",
        "performs_durable_outcome_record_write_preflight": true,
        "durable_record_write_execution_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_record_write_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_record_write_execution_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_record_write_preflight": true,
        "requires_explicit_durable_outcome_record_write_execution_decision": true,
        "record_write_execution_kind": "durable_outcome_record_write_execution",
        "performs_durable_outcome_record_write_execution_preflight": true,
        "durable_record_persistence_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_record_write_execution_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_record_persistence_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_record_write_execution_preflight": true,
        "requires_explicit_durable_outcome_record_persistence_decision": true,
        "persistence_kind": "durable_outcome_record_persistence",
        "performs_durable_outcome_record_persistence_preflight": true,
        "durable_store_write_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_record_persistence_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_record_store_write_execution_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_record_persistence_preflight": true,
        "requires_explicit_durable_outcome_record_store_write_execution_decision": true,
        "store_write_execution_kind": "durable_outcome_record_store_write_execution",
        "performs_durable_outcome_record_store_write_execution_preflight": true,
        "durable_store_write_execution_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_record_store_write_execution_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_record_write_evidence_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_record_store_write_execution_preflight": true,
        "requires_explicit_durable_outcome_record_write_evidence": true,
        "evidence_kind": "durable_outcome_record_write_evidence",
        "performs_durable_outcome_record_write_evidence_preflight": true,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_record_write_evidence_preflight_only": true
    })
}

fn runtime_executor_durable_outcome_record_write_evidence_review_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "none",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_record_write_evidence_preflight": true,
        "requires_explicit_durable_outcome_record_write_evidence_review_decision": true,
        "review_kind": "durable_outcome_record_write_evidence_review",
        "performs_durable_outcome_record_write_evidence_review_preflight": true,
        "performs_durable_outcome_record_write_evidence_review": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "persists_outcome_record": false,
        "feedback_changes_world_verdict_allowed": false,
        "runtime_executor_durable_outcome_record_write_evidence_review_preflight_only": true
    })
}

fn runtime_executor_world_verdict_rewrite_gate_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "output_only",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_durable_outcome_record_write_evidence_review_preflight": true,
        "requires_explicit_world_verdict_rewrite_decision": true,
        "decision_kind": "world_verdict_rewrite",
        "performs_world_verdict_rewrite_gate": true,
        "performs_world_verdict_rewrite_output": true,
        "persists_world_verdict": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "verified_outcome_ingestion_allowed": false,
        "persists_outcome_record": false,
        "runtime_executor_world_verdict_rewrite_gate_only": true
    })
}

fn runtime_executor_verified_outcome_ingestion_gate_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "output_only",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_world_verdict_rewrite_gate": true,
        "requires_explicit_verified_outcome_ingestion_decision": true,
        "decision_kind": "verified_outcome_ingestion",
        "performs_verified_outcome_ingestion_gate": true,
        "performs_verified_outcome_admission_output": true,
        "performs_verified_outcome_ingestion": false,
        "persists_world_verdict": false,
        "durable_outcome_record_written": false,
        "store_write_allowed": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "persists_outcome_record": false,
        "runtime_executor_verified_outcome_ingestion_gate_only": true
    })
}

fn runtime_executor_verified_outcome_ingestion_execution_preflight_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "output_only",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_verified_outcome_ingestion_gate": true,
        "requires_explicit_verified_outcome_ingestion_execution_decision": true,
        "decision_kind": "verified_outcome_ingestion_execution",
        "performs_verified_outcome_ingestion_execution_preflight": true,
        "performs_verified_outcome_ingestion": false,
        "persists_world_verdict": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "verified_outcome_ingestion_allowed": false,
        "persists_outcome_record": false,
        "runtime_executor_verified_outcome_ingestion_execution_preflight_only": true
    })
}

fn runtime_executor_verified_outcome_ingestion_execution_commit_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "output_only",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_verified_outcome_ingestion_execution_preflight": true,
        "requires_explicit_verified_outcome_ingestion_execution_commit_decision": true,
        "decision_kind": "verified_outcome_ingestion_execution_commit",
        "performs_verified_outcome_ingestion_execution_commit_gate": true,
        "performs_verified_outcome_ingestion": false,
        "persists_world_verdict": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "verified_outcome_ingestion_allowed": false,
        "persists_outcome_record": false,
        "runtime_executor_verified_outcome_ingestion_execution_commit_only": true
    })
}

fn runtime_executor_verified_outcome_ingestion_apply_gate_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "output_only",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_verified_outcome_ingestion_execution_commit": true,
        "requires_explicit_verified_outcome_ingestion_apply_decision": true,
        "decision_kind": "verified_outcome_ingestion_apply",
        "performs_verified_outcome_ingestion_apply_gate": true,
        "performs_verified_outcome_ingestion": false,
        "persists_world_verdict": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "verified_outcome_ingestion_writer_allowed_after_gate": true,
        "persists_outcome_record": false,
        "runtime_executor_verified_outcome_ingestion_apply_gate_only": true
    })
}

fn runtime_executor_verified_outcome_ingestion_writer_guardrails() -> Value {
    json!({
        "read_only": true,
        "mutation_surface": "output_only",
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false,
        "queries_live_runtime": false,
        "requires_ready_verified_outcome_ingestion_apply_gate": true,
        "requires_explicit_verified_outcome_ingestion_writer_decision": true,
        "decision_kind": "verified_outcome_ingestion_writer",
        "performs_verified_outcome_ingestion_writer_gate": true,
        "performs_verified_outcome_ingestion": false,
        "persists_world_verdict": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "verified_outcome_ingestion_writer_execution_allowed_after_gate": true,
        "persists_outcome_record": false,
        "runtime_executor_verified_outcome_ingestion_writer_gate_only": true
    })
}

fn apply_request_id_for_patch(patch_id: &Value) -> Value {
    let Some(patch_id) = patch_id.as_str() else {
        return Value::Null;
    };
    let suffix = patch_id.strip_prefix("patch_").unwrap_or(patch_id);
    json!(format!("apply_request_{suffix}"))
}

fn executor_design_request_id_for_apply_request(request_id: &Value) -> Value {
    let Some(request_id) = request_id.as_str() else {
        return Value::Null;
    };
    let suffix = request_id
        .strip_prefix("apply_request_")
        .unwrap_or(request_id);
    json!(format!("runtime_executor_design_{suffix}"))
}

fn live_runtime_lookup_design_request_id_for_design_request(design_request_id: &Value) -> Value {
    let Some(design_request_id) = design_request_id.as_str() else {
        return Value::Null;
    };
    let suffix = design_request_id
        .strip_prefix("runtime_executor_design_")
        .unwrap_or(design_request_id);
    json!(format!("live_runtime_lookup_design_{suffix}"))
}

fn live_lookup_evidence_id_for_design_request(design_request_id: &Value) -> Value {
    let Some(design_request_id) = design_request_id.as_str() else {
        return Value::Null;
    };
    let suffix = design_request_id
        .strip_prefix("runtime_executor_design_")
        .unwrap_or(design_request_id);
    json!(format!("live_lookup_{suffix}"))
}

fn operator_submission_token_id_for_patch(patch_id: &Value) -> Value {
    let Some(patch_id) = patch_id.as_str() else {
        return Value::Null;
    };
    let suffix = patch_id.strip_prefix("patch_").unwrap_or(patch_id);
    json!(format!("submit_patch_{suffix}"))
}

fn operator_submission_idempotency_key(
    patch_id: &Value,
    runtime_generation: &Value,
    decision_id: &Value,
) -> Value {
    let (Some(patch_id), Some(runtime_generation), Some(decision_id)) = (
        patch_id.as_str(),
        runtime_generation.as_str(),
        decision_id.as_str(),
    ) else {
        return Value::Null;
    };
    json!(format!("{patch_id}/{runtime_generation}/{decision_id}"))
}

fn patch_application_gate_id_for_patch(patch_id: &Value) -> Value {
    let Some(patch_id) = patch_id.as_str() else {
        return Value::Null;
    };
    let suffix = patch_id.strip_prefix("patch_").unwrap_or(patch_id);
    json!(format!("patch_application_gate_{suffix}"))
}

fn patch_application_gate_idempotency_key(
    patch_id: &Value,
    runtime_generation: &Value,
    token_id: &Value,
    decision_id: &Value,
) -> Value {
    let (Some(patch_id), Some(runtime_generation), Some(token_id), Some(decision_id)) = (
        patch_id.as_str(),
        runtime_generation.as_str(),
        token_id.as_str(),
        decision_id.as_str(),
    ) else {
        return Value::Null;
    };
    json!(format!(
        "{patch_id}/{runtime_generation}/{token_id}/{decision_id}"
    ))
}

fn patch_executor_invocation_request_id_for_patch(patch_id: &Value) -> Value {
    let Some(patch_id) = patch_id.as_str() else {
        return Value::Null;
    };
    let suffix = patch_id.strip_prefix("patch_").unwrap_or(patch_id);
    json!(format!("patch_executor_invocation_{suffix}"))
}

fn patch_executor_invocation_idempotency_key(
    patch_id: &Value,
    runtime_generation: &Value,
    gate_id: &Value,
    decision_id: &Value,
) -> Value {
    let (Some(patch_id), Some(runtime_generation), Some(gate_id), Some(decision_id)) = (
        patch_id.as_str(),
        runtime_generation.as_str(),
        gate_id.as_str(),
        decision_id.as_str(),
    ) else {
        return Value::Null;
    };
    json!(format!(
        "{patch_id}/{runtime_generation}/{gate_id}/{decision_id}"
    ))
}

fn lookup_snapshot_covers_patch_entities(lookup_snapshot: &Value, patch: &Value) -> bool {
    let Some(patch_entities) = patch["target_entities"].as_array() else {
        return false;
    };
    let Some(snapshot_entities) = lookup_snapshot["entities_present"].as_array() else {
        return false;
    };

    patch_entities.iter().all(|entity| {
        snapshot_entities
            .iter()
            .any(|snapshot_entity| snapshot_entity == entity)
    })
}

fn unique_strings(items: Vec<String>) -> Vec<String> {
    let mut unique = Vec::new();
    for item in items {
        if !unique.contains(&item) {
            unique.push(item);
        }
    }
    unique
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
        assert!(
            report
                .failure_reasons
                .contains(&"schema_mismatch".to_string())
        );
        assert!(
            report
                .failure_reasons
                .contains(&"primary_readback_requires_screenshot".to_string())
        );
        assert!(
            report
                .failure_reasons
                .contains(&"event_sequence_mismatch".to_string())
        );
        assert_eq!(report.to_value()["writes_state"], false);
        assert_eq!(report.to_value()["store_access_required"], false);
        assert_eq!(report.to_value()["mcp_tool_registered"], false);
    }
}
