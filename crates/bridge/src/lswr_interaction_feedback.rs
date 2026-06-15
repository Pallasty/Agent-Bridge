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
pub const LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_consumption_report.v0";
pub const LSWR_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_next_revision_plan.v0";
pub const LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_semantic_patch_draft.v0";

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
