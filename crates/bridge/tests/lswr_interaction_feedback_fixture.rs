use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_consumption_report, build_interaction_feedback_evidence_packet,
    build_interaction_feedback_live_runtime_lookup_design_preflight,
    build_interaction_feedback_next_revision_plan,
    build_interaction_feedback_packet_consumption_preflight,
    build_interaction_feedback_patch_apply_request,
    build_interaction_feedback_patch_execution_preflight, build_interaction_feedback_readback,
    build_interaction_feedback_runtime_executor_design_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight,
    build_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight,
    build_interaction_feedback_runtime_executor_live_lookup_preflight,
    build_interaction_feedback_runtime_executor_operator_submission_token_preflight,
    build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight,
    build_interaction_feedback_runtime_executor_patch_application_gate_preflight,
    build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight,
    build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight,
    build_interaction_feedback_runtime_executor_post_apply_verification_preflight,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution,
    build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate,
    build_interaction_feedback_semantic_patch_draft,
    build_interaction_feedback_validation_envelope,
    render_interaction_feedback_consumption_preflight_report,
    render_interaction_feedback_live_runtime_lookup_design_preflight,
    render_interaction_feedback_next_revision_plan,
    render_interaction_feedback_patch_apply_request,
    render_interaction_feedback_patch_execution_preflight,
    render_interaction_feedback_runtime_executor_design_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight,
    render_interaction_feedback_runtime_executor_live_lookup_preflight,
    render_interaction_feedback_runtime_executor_operator_submission_token_preflight,
    render_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight,
    render_interaction_feedback_runtime_executor_patch_application_gate_preflight,
    render_interaction_feedback_runtime_executor_patch_executor_invocation_preflight,
    render_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight,
    render_interaction_feedback_runtime_executor_post_apply_verification_preflight,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution,
    render_interaction_feedback_runtime_executor_world_verdict_rewrite_gate,
    render_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_validation_envelope, validate_interaction_feedback_fixture,
    LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA, LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_LIVE_RUNTIME_LOOKUP_DESIGN_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_ADMISSION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_GATE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_GATE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_PERSISTENCE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_EXECUTION_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_EVIDENCE_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_ADMISSION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_PERSISTENCE_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_STORE_WRITE_EXECUTION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_EXECUTION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_REVIEW_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_DECISION_SCHEMA,
};
use serde_json::{json, Value};

const FIXTURE_JSON: &str = include_str!("fixtures/lswr_interaction_feedback_fixture_v0.json");
const ENVELOPE_MARKDOWN: &str =
    include_str!("fixtures/lswr_interaction_feedback_validation_envelope_v0.md");
const CONSUMPTION_MARKDOWN: &str =
    include_str!("fixtures/lswr_interaction_feedback_consumption_report_v0.md");

#[test]
fn interaction_feedback_fixture_validates_through_pure_module() {
    let fixture = fixture();
    let report = validate_interaction_feedback_fixture(&fixture);

    assert_eq!(fixture["schema"], LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA);
    assert_eq!(fixture["requires_screenshot_for_primary_readback"], false);
    assert_eq!(fixture["events"].as_array().expect("events").len(), 8);
    assert_eq!(fixture["feedback"].as_array().expect("feedback").len(), 1);
    assert!(report.valid, "{:?}", report.failure_reasons);
    assert!(report.failure_reasons.is_empty());

    let report_value = report.to_value();
    assert_eq!(
        report_value["schema"],
        LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA
    );
    assert_eq!(report_value["writes_state"], false);
    assert_eq!(report_value["store_access_required"], false);
    assert_eq!(report_value["mcp_tool_registered"], false);

    for forbidden in [
        "memory_save",
        "lswr_outcome_admissions_ingest",
        "dry_run=false",
    ] {
        assert!(
            !FIXTURE_JSON.contains(forbidden),
            "fixture must stay out of write/persistence surfaces: {forbidden}"
        );
    }
}

#[test]
fn interaction_feedback_fixture_builds_expected_readback_report() {
    let fixture = fixture();
    let readback = build_interaction_feedback_readback(&fixture);

    assert_eq!(
        readback["schema"],
        LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA
    );
    assert_eq!(readback["requires_screenshot_for_primary_readback"], false);
    assert_eq!(
        readback,
        json!({
            "schema": LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA,
            "selected_entities": ["bath"],
            "latest_visible_change": "patch_arrival_bath_move_001",
            "latest_verification_verdict": "not_verified",
            "latest_verification_reason": "expected_effect_clause_failed",
            "failed_clause_ids": ["effect_walkway_clearance_001"],
            "latest_human_decision": "reject",
            "latest_feedback_issue": "visual_density_too_high",
            "next_revision_patch_id": "patch_arrival_bath_move_002",
            "revision_should_cite": [
                "verify_patch_arrival_bath_move_001",
                "fb_arrival_crowded_001"
            ],
            "requires_screenshot_for_primary_readback": false
        })
    );
}

#[test]
fn interaction_feedback_fixture_builds_readonly_validation_envelope() {
    let fixture = fixture();
    let envelope = build_interaction_feedback_validation_envelope(&fixture);

    assert_eq!(
        envelope["schema"],
        LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA
    );
    assert_eq!(
        envelope["fixture_schema"],
        LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA
    );
    assert_eq!(
        envelope["expected_fixture_schema"],
        LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA
    );
    assert_eq!(
        envelope["validation_schema"],
        LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA
    );
    assert_eq!(
        envelope["readback_schema"],
        LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA
    );
    assert_eq!(envelope["readback_mode"], "interaction_feedback_detailed");
    assert_eq!(envelope["requires_screenshot_for_primary_readback"], false);
    assert_eq!(envelope["valid"], true);
    assert_eq!(envelope["failure_reasons"], json!([]));
    assert_eq!(envelope["guardrails"]["read_only"], true);
    assert_eq!(envelope["guardrails"]["mutation_surface"], "none");
    assert_eq!(envelope["guardrails"]["writes_state"], false);
    assert_eq!(envelope["guardrails"]["store_access_required"], false);
    assert_eq!(envelope["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        envelope["guardrails"]["primary_readback_requires_screenshot"],
        false
    );
    assert_eq!(
        envelope["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        envelope["report"]["schema"],
        LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA
    );
    assert_eq!(envelope["report"]["readback"], envelope["readback"]);
    assert_eq!(
        envelope["next_agent_action_contract"]["preserve_failed_world_verdict"],
        true
    );
    assert_eq!(
        envelope["next_agent_action_contract"]["forbid_ingestion_or_state_write"],
        true
    );
}

#[test]
fn interaction_feedback_validation_envelope_renders_stable_markdown() {
    let fixture = fixture();
    let envelope = build_interaction_feedback_validation_envelope(&fixture);
    let markdown = render_interaction_feedback_validation_envelope(&envelope);

    assert_eq!(markdown, ENVELOPE_MARKDOWN);
}

#[test]
fn interaction_feedback_fixture_builds_evidence_packet() {
    let fixture = fixture();
    let packet = build_interaction_feedback_evidence_packet(&fixture);

    assert_eq!(
        packet["schema"],
        LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA
    );
    assert_eq!(packet["fixture_id"], "lswr_interaction_feedback_loop_001");
    assert_eq!(
        packet["fixture_schema"],
        LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA
    );
    assert_eq!(
        packet["envelope_schema"],
        LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA
    );
    assert_eq!(
        packet["validation_schema"],
        LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA
    );
    assert_eq!(
        packet["readback_schema"],
        LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA
    );
    assert_eq!(packet["readback_mode"], "interaction_feedback_detailed");
    assert_eq!(packet["valid"], true);
    assert_eq!(packet["failure_reasons"], json!([]));
    assert_eq!(packet["markdown"], ENVELOPE_MARKDOWN);
    assert_eq!(
        packet["envelope"]["schema"],
        LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA
    );
    assert_eq!(packet["guardrails"]["read_only"], true);
    assert_eq!(packet["guardrails"]["writes_state"], false);
    assert_eq!(packet["guardrails"]["store_access_required"], false);
    assert_eq!(packet["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        packet["note"],
        "local evidence only: pure fixture render, no MCP call, no store access, no memory write"
    );
}

#[test]
fn interaction_feedback_consumption_preflight_accepts_explicit_fixture() {
    let fixture = fixture();
    let preflight = build_interaction_feedback_packet_consumption_preflight(&fixture);

    assert_eq!(
        preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(preflight["input_kind"], "fixture");
    assert_eq!(preflight["accepted"], true);
    assert_eq!(preflight["preflight_verdict"], "accepted");
    assert_eq!(preflight["world_verdict"], "not_verified");
    assert_eq!(
        preflight["reason"],
        "explicit_input_consumption_preflight_passed"
    );
    assert_eq!(preflight["failure_reasons"], json!([]));
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["implicit_live_runtime_lookup_allowed"],
        false
    );
    assert_eq!(preflight["implicit_live_runtime_lookup_attempted"], false);
    assert_eq!(
        preflight["packet_schema"],
        LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA
    );
    assert_eq!(
        preflight["fixture_id"],
        "lswr_interaction_feedback_loop_001"
    );
    assert_eq!(
        preflight["readback"]["revision_should_cite"],
        json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    );
    assert_consumption_gates_pass(&preflight);
}

#[test]
fn interaction_feedback_consumption_preflight_accepts_explicit_packet() {
    let fixture = fixture();
    let packet = build_interaction_feedback_evidence_packet(&fixture);
    let preflight = build_interaction_feedback_packet_consumption_preflight(&packet);

    assert_eq!(preflight["input_kind"], "evidence_packet");
    assert_eq!(preflight["accepted"], true);
    assert_eq!(preflight["world_verdict"], "not_verified");
    assert_eq!(
        preflight["packet_schema"],
        LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA
    );
    assert_eq!(
        preflight["packet"]["schema"],
        LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA
    );
    assert_consumption_gates_pass(&preflight);
}

#[test]
fn interaction_feedback_consumption_preflight_accepts_wrapped_fixture() {
    let fixture = fixture();
    let preflight =
        build_interaction_feedback_packet_consumption_preflight(&json!({ "fixture": fixture }));

    assert_eq!(preflight["input_kind"], "fixture_wrapper");
    assert_eq!(preflight["accepted"], true);
    assert_eq!(preflight["world_verdict"], "not_verified");
    assert_consumption_gates_pass(&preflight);
}

#[test]
fn interaction_feedback_consumption_preflight_blocks_missing_input() {
    let preflight = build_interaction_feedback_packet_consumption_preflight(&json!({}));

    assert_eq!(
        preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(preflight["input_kind"], "missing_or_invalid");
    assert_eq!(preflight["accepted"], false);
    assert_eq!(preflight["preflight_verdict"], "blocked");
    assert_eq!(preflight["world_verdict"], "not_verified");
    assert_eq!(preflight["reason"], "C1:explicit_input_only");
    assert_eq!(
        preflight["guardrails"]["implicit_live_runtime_lookup_allowed"],
        false
    );
    assert_eq!(preflight["implicit_live_runtime_lookup_attempted"], false);
    assert_eq!(preflight["packet"], Value::Null);
    assert!(preflight["blockers"]
        .as_array()
        .expect("blockers")
        .contains(&json!("explicit_packet_or_fixture_required")));
    assert_eq!(preflight["acceptance_matrix"][0]["gate"], "C1");
    assert_eq!(preflight["acceptance_matrix"][0]["passed"], false);
    assert_eq!(preflight["acceptance_matrix"][1]["gate"], "C2");
    assert_eq!(preflight["acceptance_matrix"][1]["passed"], false);
}

#[test]
fn interaction_feedback_consumption_preflight_rejects_laundered_packet() {
    let fixture = fixture();
    let mut packet = build_interaction_feedback_evidence_packet(&fixture);
    packet["guardrails"]["writes_state"] = json!(true);
    packet["readback"]["latest_verification_verdict"] = json!("verified");

    let preflight = build_interaction_feedback_packet_consumption_preflight(&packet);

    assert_eq!(preflight["input_kind"], "evidence_packet");
    assert_eq!(preflight["accepted"], false);
    assert_eq!(preflight["preflight_verdict"], "blocked");
    assert_eq!(preflight["world_verdict"], "verified");
    assert_eq!(preflight["acceptance_matrix"][1]["gate"], "C2");
    assert_eq!(preflight["acceptance_matrix"][1]["passed"], false);
    assert_eq!(preflight["acceptance_matrix"][2]["gate"], "C3");
    assert_eq!(preflight["acceptance_matrix"][2]["passed"], false);
    assert!(preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("C2:guardrails_preserved")));
    assert!(preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("C3:no_verification_laundering")));
    assert_eq!(preflight["implicit_live_runtime_lookup_attempted"], false);
}

#[test]
fn interaction_feedback_consumption_report_renders_stable_markdown() {
    let fixture = fixture();
    let preflight = build_interaction_feedback_packet_consumption_preflight(&fixture);
    let markdown = render_interaction_feedback_consumption_preflight_report(&preflight);
    let report = build_interaction_feedback_consumption_report(&fixture);

    assert_eq!(markdown, CONSUMPTION_MARKDOWN);
    assert_eq!(
        report["schema"],
        LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_SCHEMA
    );
    assert_eq!(
        report["preflight_schema"],
        LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(report["accepted"], true);
    assert_eq!(report["preflight_verdict"], "accepted");
    assert_eq!(report["world_verdict"], "not_verified");
    assert_eq!(report["markdown"], CONSUMPTION_MARKDOWN);
    assert_eq!(report["markdown_source"], "preflight");
    assert_eq!(report["json_canonical"], true);
    assert_eq!(report["preflight"], preflight);
    assert_eq!(report["input_contract"]["explicit_input_required"], true);
    assert_eq!(report["implicit_live_runtime_lookup_attempted"], false);
    assert_eq!(report["writes_state"], false);
    assert_eq!(report["store_access_required"], false);
    assert_eq!(report["mcp_tool_registered"], false);
}

#[test]
fn interaction_feedback_consumption_report_accepts_explicit_preflight() {
    let fixture = fixture();
    let preflight = build_interaction_feedback_packet_consumption_preflight(&fixture);
    let report = build_interaction_feedback_consumption_report(&preflight);

    assert_eq!(report["accepted"], true);
    assert_eq!(report["input_kind"], "fixture");
    assert_eq!(report["preflight"], preflight);
    assert_eq!(report["markdown"], CONSUMPTION_MARKDOWN);
}

#[test]
fn interaction_feedback_consumption_report_renders_blocked_missing_input() {
    let report = build_interaction_feedback_consumption_report(&json!({}));
    let markdown = report["markdown"].as_str().expect("markdown");

    assert_eq!(report["accepted"], false);
    assert_eq!(report["preflight_verdict"], "blocked");
    assert_eq!(report["world_verdict"], "not_verified");
    assert!(markdown.contains("- C1 explicit_input_only: `failed`"));
    assert!(markdown.contains("- C5 human_can_audit_same_result: `failed`"));
    assert!(markdown.contains("explicit_packet_or_fixture_required"));
    assert!(markdown.contains("- implicit_live_runtime_lookup_attempted: `false`"));
}

#[test]
fn interaction_feedback_consumption_report_does_not_rewrite_laundered_verdict() {
    let fixture = fixture();
    let mut packet = build_interaction_feedback_evidence_packet(&fixture);
    packet["guardrails"]["writes_state"] = json!(true);
    packet["readback"]["latest_verification_verdict"] = json!("verified");

    let report = build_interaction_feedback_consumption_report(&packet);
    let markdown = report["markdown"].as_str().expect("markdown");

    assert_eq!(report["accepted"], false);
    assert_eq!(report["preflight_verdict"], "blocked");
    assert_eq!(report["world_verdict"], "verified");
    assert!(markdown.contains("- world_verdict: `verified`"));
    assert!(markdown.contains("- C2 guardrails_preserved: `failed`"));
    assert!(markdown.contains("- C3 no_verification_laundering: `failed`"));
    assert!(markdown.contains("- feedback_changes_world_verdict_allowed: `false`"));
}

#[test]
fn interaction_feedback_next_revision_plan_selects_report_cited_patch() {
    let fixture = fixture();
    let report = build_interaction_feedback_consumption_report(&fixture);
    let plan = build_interaction_feedback_next_revision_plan(&report);
    let markdown = render_interaction_feedback_next_revision_plan(&plan);

    assert_eq!(
        plan["schema"],
        LSWR_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_SCHEMA
    );
    assert_eq!(
        plan["source_schema"],
        LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_SCHEMA
    );
    assert_eq!(plan["source_accepted"], true);
    assert_eq!(plan["plan_verdict"], "ready_for_revision");
    assert_eq!(plan["status"], "ready");
    assert_eq!(plan["source_world_verdict"], "not_verified");
    assert_eq!(
        plan["next_revision"]["patch_id"],
        "patch_arrival_bath_move_002"
    );
    assert_eq!(
        plan["next_revision"]["failed_clause_ids"],
        json!(["effect_walkway_clearance_001"])
    );
    assert_eq!(
        plan["next_revision"]["feedback_issue"],
        "visual_density_too_high"
    );
    assert_eq!(
        plan["next_revision"]["must_cite"],
        json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    );
    assert_eq!(
        plan["next_revision"]["preserved_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        plan["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(plan["guardrails"]["applies_patch"], false);
    assert_eq!(plan["implicit_live_runtime_lookup_attempted"], false);
    assert_eq!(plan["writes_state"], false);
    assert_eq!(plan["store_access_required"], false);
    assert_eq!(plan["mcp_tool_registered"], false);

    assert!(markdown.contains("- plan_verdict: `ready_for_revision`"));
    assert!(markdown.contains("- patch_id: `patch_arrival_bath_move_002`"));
    assert!(markdown
        .contains("- must_cite: `verify_patch_arrival_bath_move_001, fb_arrival_crowded_001`"));
    assert!(markdown.contains("- preserved_world_verdict: `not_verified`"));
}

#[test]
fn interaction_feedback_next_revision_plan_accepts_fixture_directly() {
    let plan = build_interaction_feedback_next_revision_plan(&fixture());

    assert_eq!(plan["plan_verdict"], "ready_for_revision");
    assert_eq!(plan["source_accepted"], true);
    assert_eq!(plan["next_revision"]["allowed_to_apply"], false);
    assert_eq!(plan["next_revision"]["allowed_to_ingest"], false);
}

#[test]
fn interaction_feedback_next_revision_plan_blocks_laundered_source() {
    let fixture = fixture();
    let mut packet = build_interaction_feedback_evidence_packet(&fixture);
    packet["guardrails"]["writes_state"] = json!(true);
    packet["readback"]["latest_verification_verdict"] = json!("verified");

    let plan = build_interaction_feedback_next_revision_plan(&packet);
    let markdown = render_interaction_feedback_next_revision_plan(&plan);

    assert_eq!(plan["source_accepted"], false);
    assert_eq!(plan["plan_verdict"], "blocked");
    assert_eq!(plan["status"], "blocked");
    assert_eq!(plan["source_world_verdict"], "verified");
    assert_eq!(
        plan["failure_reasons"],
        json!([
            "source_report_not_accepted",
            "world_verdict_must_remain_not_verified"
        ])
    );
    assert_eq!(plan["next_revision"]["allowed_to_apply"], false);
    assert_eq!(
        plan["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(plan["guardrails"]["writes_state"], false);
    assert_eq!(plan["guardrails"]["queries_live_runtime"], false);
    assert!(markdown.contains("- source_world_verdict: `verified`"));
    assert!(markdown.contains("- plan_verdict: `blocked`"));
    assert!(markdown.contains("world_verdict_must_remain_not_verified"));
}

#[test]
fn interaction_feedback_semantic_patch_draft_uses_accepted_plan_without_applying() {
    let plan = build_interaction_feedback_next_revision_plan(&fixture());
    let draft = build_interaction_feedback_semantic_patch_draft(&plan);
    let markdown = render_interaction_feedback_semantic_patch_draft(&draft);

    assert_eq!(
        draft["schema"],
        LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA
    );
    assert_eq!(
        draft["source_schema"],
        LSWR_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_SCHEMA
    );
    assert_eq!(draft["source_plan_verdict"], "ready_for_revision");
    assert_eq!(draft["source_world_verdict"], "not_verified");
    assert_eq!(draft["draft_verdict"], "drafted");
    assert_eq!(draft["status"], "drafted");
    assert_eq!(
        draft["semantic_patch_draft"]["patch_id"],
        "patch_arrival_bath_move_002"
    );
    assert_eq!(
        draft["semantic_patch_draft"]["operation_hint"],
        "increase_walkway_clearance_by_repositioning_entity"
    );
    assert_eq!(
        draft["semantic_patch_draft"]["target_entities"],
        json!(["bath"])
    );
    assert_eq!(
        draft["semantic_patch_draft"]["revision_sources"],
        json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    );
    assert_eq!(
        draft["semantic_patch_draft"]["constraints"]["preserve_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        draft["semantic_patch_draft"]["constraints"]["expected_effect_requirements"],
        json!([
            {
                "target": "bath",
                "metric": "screen_area",
                "to_op": ">",
                "to_value": 0.0,
                "source": "preserve_visible_entity_readability"
            },
            {
                "target": "arrival_area.main_walkway",
                "metric": "walkway_clearance_cells",
                "to_op": ">=",
                "to_value": 2,
                "source": "failed_clause_repair"
            }
        ])
    );
    assert_eq!(
        draft["semantic_patch_draft"]["unresolved_arguments"],
        json!(["patch.args.cell"])
    );
    assert_eq!(
        draft["semantic_patch_draft"]["requires_live_world_state_for_arguments"],
        true
    );
    assert_eq!(
        draft["semantic_patch_draft"]["live_world_state_queried"],
        false
    );
    assert_eq!(draft["semantic_patch_draft"]["apply_allowed"], false);
    assert_eq!(draft["semantic_patch_draft"]["ingest_allowed"], false);
    assert_eq!(draft["guardrails"]["queries_live_runtime"], false);
    assert_eq!(draft["guardrails"]["applies_patch"], false);
    assert_eq!(
        draft["agent_action_contract"]["resolve_arguments_before_apply"],
        true
    );
    assert_eq!(draft["agent_action_contract"]["do_not_apply_patch"], true);
    assert_eq!(
        draft["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(draft["writes_state"], false);
    assert_eq!(draft["store_access_required"], false);
    assert_eq!(draft["mcp_tool_registered"], false);

    assert!(markdown.contains("- draft_verdict: `drafted`"));
    assert!(markdown.contains("- patch_id: `patch_arrival_bath_move_002`"));
    assert!(
        markdown.contains("- operation_hint: `increase_walkway_clearance_by_repositioning_entity`")
    );
    assert!(markdown.contains("- unresolved_arguments: `patch.args.cell`"));
    assert!(markdown.contains("- preserve_world_verdict: `not_verified`"));
}

#[test]
fn interaction_feedback_semantic_patch_draft_accepts_fixture_directly() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());

    assert_eq!(draft["draft_verdict"], "drafted");
    assert_eq!(
        draft["semantic_patch_draft"]["patch_id"],
        "patch_arrival_bath_move_002"
    );
    assert_eq!(draft["semantic_patch_draft"]["apply_allowed"], false);
    assert_eq!(draft["implicit_live_runtime_lookup_attempted"], false);
}

#[test]
fn interaction_feedback_semantic_patch_draft_blocks_laundered_plan() {
    let fixture = fixture();
    let mut packet = build_interaction_feedback_evidence_packet(&fixture);
    packet["guardrails"]["writes_state"] = json!(true);
    packet["readback"]["latest_verification_verdict"] = json!("verified");

    let draft = build_interaction_feedback_semantic_patch_draft(&packet);
    let markdown = render_interaction_feedback_semantic_patch_draft(&draft);

    assert_eq!(draft["draft_verdict"], "blocked");
    assert_eq!(draft["status"], "blocked");
    assert_eq!(draft["source_plan_verdict"], "blocked");
    assert_eq!(draft["source_world_verdict"], "verified");
    assert!(draft["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_plan_not_ready")));
    assert!(draft["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_world_verdict_must_remain_not_verified")));
    assert_eq!(draft["semantic_patch_draft"]["apply_allowed"], false);
    assert_eq!(draft["guardrails"]["writes_state"], false);
    assert_eq!(draft["agent_action_contract"]["do_not_apply_patch"], true);
    assert!(markdown.contains("- draft_verdict: `blocked`"));
    assert!(markdown.contains("- source_world_verdict: `verified`"));
}

#[test]
fn interaction_feedback_patch_execution_preflight_blocks_without_argument_context() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&draft);
    let markdown = render_interaction_feedback_patch_execution_preflight(&preflight);

    assert_eq!(
        preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(preflight["input_kind"], "semantic_patch_draft");
    assert_eq!(preflight["source_draft_verdict"], "drafted");
    assert_eq!(preflight["source_world_verdict"], "not_verified");
    assert_eq!(preflight["preflight_verdict"], "blocked");
    assert_eq!(preflight["status"], "blocked");
    assert_eq!(preflight["reason"], "explicit_argument_context_required");
    assert_eq!(
        preflight["argument_context_status"]["reason"],
        "explicit_argument_context_required"
    );
    assert_eq!(
        preflight["failure_reasons"],
        json!([
            "explicit_argument_context_required",
            "patch_args_cell_unresolved"
        ])
    );
    assert_eq!(preflight["resolved_patch"]["args"], Value::Null);
    assert_eq!(
        preflight["resolved_patch"]["ready_for_execution_request"],
        false
    );
    assert_eq!(preflight["resolved_patch"]["execution_performed"], false);
    assert_eq!(
        preflight["resolved_patch"]["apply_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_request_separate_apply_after_preflight"],
        false
    );
    assert_eq!(preflight["implicit_live_runtime_lookup_attempted"], false);
    assert_execution_preflight_read_only(&preflight);

    assert!(markdown.contains("- preflight_verdict: `blocked`"));
    assert!(markdown.contains("- reason: `explicit_argument_context_required`"));
    assert!(markdown.contains("- ready_for_execution_request: `false`"));
}

#[test]
fn interaction_feedback_patch_execution_preflight_resolves_explicit_argument_context() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let markdown = render_interaction_feedback_patch_execution_preflight(&preflight);

    assert_eq!(
        preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(preflight["input_kind"], "draft_wrapper");
    assert_eq!(preflight["source_draft_verdict"], "drafted");
    assert_eq!(preflight["source_world_verdict"], "not_verified");
    assert_eq!(
        preflight["preflight_verdict"],
        "ready_for_execution_request"
    );
    assert_eq!(preflight["status"], "ready");
    assert_eq!(
        preflight["reason"],
        "explicit_argument_context_execution_preflight_ready"
    );
    assert_eq!(preflight["failure_reasons"], json!([]));
    assert_eq!(preflight["argument_context_status"]["accepted"], true);
    assert_eq!(
        preflight["argument_context_status"]["context_schema"],
        LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA
    );
    assert_eq!(preflight["resolved_patch"]["args"]["cell"], json!([5, 2]));
    assert_eq!(
        preflight["resolved_patch"]["resolved_arguments"]["patch.args.cell"],
        json!([5, 2])
    );
    assert_eq!(
        preflight["resolved_patch"]["required_citations"],
        json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    );
    assert_eq!(
        preflight["resolved_patch"]["ready_for_execution_request"],
        true
    );
    assert_eq!(preflight["resolved_patch"]["execution_performed"], false);
    assert_eq!(
        preflight["resolved_patch"]["apply_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_request_separate_apply_after_preflight"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(preflight["implicit_live_runtime_lookup_attempted"], false);
    assert_execution_preflight_read_only(&preflight);

    assert!(markdown.contains("- preflight_verdict: `ready_for_execution_request`"));
    assert!(markdown.contains("- resolved_arguments: `{\"patch.args.cell\":[5,2]}`"));
    assert!(markdown.contains("- execution_performed: `false`"));
}

#[test]
fn interaction_feedback_patch_execution_preflight_blocks_laundered_draft() {
    let fixture = fixture();
    let mut packet = build_interaction_feedback_evidence_packet(&fixture);
    packet["guardrails"]["writes_state"] = json!(true);
    packet["readback"]["latest_verification_verdict"] = json!("verified");
    let draft = build_interaction_feedback_semantic_patch_draft(&packet);
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));

    assert_eq!(preflight["preflight_verdict"], "blocked");
    assert_eq!(preflight["status"], "blocked");
    assert_eq!(preflight["source_draft_verdict"], "blocked");
    assert_eq!(preflight["source_world_verdict"], "verified");
    assert!(preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_draft_not_drafted")));
    assert!(preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_world_verdict_must_remain_not_verified")));
    assert_eq!(
        preflight["resolved_patch"]["ready_for_execution_request"],
        false
    );
    assert_eq!(preflight["resolved_patch"]["execution_performed"], false);
    assert_eq!(
        preflight["resolved_patch"]["apply_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_execution_preflight_read_only(&preflight);
}

#[test]
fn interaction_feedback_patch_apply_request_blocks_without_ready_preflight() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&draft);
    let request = build_interaction_feedback_patch_apply_request(&preflight);
    let markdown = render_interaction_feedback_patch_apply_request(&request);

    assert_eq!(
        request["schema"],
        LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA
    );
    assert_eq!(request["input_kind"], "patch_execution_preflight");
    assert_eq!(request["source_preflight_verdict"], "blocked");
    assert_eq!(request["source_world_verdict"], "not_verified");
    assert_eq!(request["apply_request_verdict"], "blocked");
    assert_eq!(request["status"], "blocked");
    assert_eq!(request["reason"], "source_preflight_not_ready");
    assert!(request["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_preflight_not_ready")));
    assert!(request["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("resolved_patch_not_ready")));
    assert!(request["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("resolved_patch_args_required")));
    assert_eq!(
        request["apply_request"]["ready_for_external_submission"],
        false
    );
    assert_eq!(request["apply_request"]["patch"], Value::Null);
    assert_eq!(request["apply_request"]["apply_performed"], false);
    assert_eq!(request["apply_request"]["submitted_by_this_tool"], false);
    assert_apply_request_read_only(&request);

    assert!(markdown.contains("- apply_request_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_external_submission: `false`"));
}

#[test]
fn interaction_feedback_patch_apply_request_builds_external_executor_request() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let request = build_interaction_feedback_patch_apply_request(&preflight);
    let markdown = render_interaction_feedback_patch_apply_request(&request);

    assert_eq!(
        request["schema"],
        LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA
    );
    assert_eq!(request["input_kind"], "patch_execution_preflight");
    assert_eq!(
        request["source_preflight_verdict"],
        "ready_for_execution_request"
    );
    assert_eq!(request["source_world_verdict"], "not_verified");
    assert_eq!(
        request["apply_request_verdict"],
        "ready_for_external_executor"
    );
    assert_eq!(request["status"], "ready");
    assert_eq!(request["reason"], "external_apply_request_ready");
    assert_eq!(request["failure_reasons"], json!([]));
    assert_eq!(
        request["apply_request"]["request_id"],
        "apply_request_arrival_bath_move_002"
    );
    assert_eq!(
        request["apply_request"]["target_runtime"]["world_id"],
        "onsen_live_session"
    );
    assert_eq!(
        request["apply_request"]["target_runtime"]["executor"],
        "separate_lswr_patch_executor"
    );
    assert_eq!(
        request["apply_request"]["patch"]["patch_id"],
        "patch_arrival_bath_move_002"
    );
    assert_eq!(
        request["apply_request"]["patch"]["args"]["cell"],
        json!([5, 2])
    );
    assert_eq!(
        request["apply_request"]["patch"]["required_citations"],
        json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    );
    assert_eq!(
        request["apply_request"]["ready_for_external_submission"],
        true
    );
    assert_eq!(request["apply_request"]["requires_operator_gate"], true);
    assert_eq!(request["apply_request"]["requires_external_executor"], true);
    assert_eq!(request["apply_request"]["apply_performed"], false);
    assert_eq!(request["apply_request"]["submitted_by_this_tool"], false);
    assert_eq!(
        request["agent_action_contract"]["may_submit_to_separate_executor_after_operator_gate"],
        true
    );
    assert_eq!(
        request["agent_action_contract"]["do_not_submit_patch_from_this_tool"],
        true
    );
    assert_apply_request_read_only(&request);

    assert!(markdown.contains("- apply_request_verdict: `ready_for_external_executor`"));
    assert!(markdown.contains("- request_id: `apply_request_arrival_bath_move_002`"));
    assert!(markdown.contains("- submitted_by_this_tool: `false`"));
}

#[test]
fn interaction_feedback_patch_apply_request_requires_explicit_preflight_input() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let request = build_interaction_feedback_patch_apply_request(&draft);

    assert_eq!(request["input_kind"], "invalid_input");
    assert_eq!(
        request["source_schema"],
        LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA
    );
    assert_eq!(request["apply_request_verdict"], "blocked");
    assert_eq!(request["status"], "blocked");
    assert_eq!(request["reason"], "patch_execution_preflight_required");
    assert_eq!(
        request["failure_reasons"],
        json!(["patch_execution_preflight_required"])
    );
    assert_eq!(
        request["apply_request"]["ready_for_external_submission"],
        false
    );
    assert_eq!(request["source_preflight"], Value::Null);
    assert_apply_request_read_only(&request);
}

#[test]
fn interaction_feedback_patch_apply_request_blocks_tampered_preflight_authority() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let mut preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    preflight["resolved_patch"]["execution_performed"] = json!(true);
    preflight["resolved_patch"]["apply_allowed_by_this_tool"] = json!(true);
    preflight["guardrails"]["applies_patch"] = json!(true);

    let request = build_interaction_feedback_patch_apply_request(&preflight);

    assert_eq!(request["apply_request_verdict"], "blocked");
    assert!(request["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_preflight_must_not_execute_patch")));
    assert!(request["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_preflight_apply_authority_must_remain_false")));
    assert!(request["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_preflight_guardrails_not_read_only")));
    assert_eq!(
        request["apply_request"]["ready_for_external_submission"],
        false
    );
    assert_apply_request_read_only(&request);
}

#[test]
fn interaction_feedback_runtime_executor_design_preflight_blocks_without_ready_apply_request() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&draft);
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let design_preflight =
        build_interaction_feedback_runtime_executor_design_preflight(&apply_request);
    let markdown = render_interaction_feedback_runtime_executor_design_preflight(&design_preflight);

    assert_eq!(
        design_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA
    );
    assert_eq!(design_preflight["input_kind"], "patch_apply_request");
    assert_eq!(design_preflight["source_apply_request_verdict"], "blocked");
    assert_eq!(design_preflight["source_world_verdict"], "not_verified");
    assert_eq!(design_preflight["design_preflight_verdict"], "blocked");
    assert_eq!(design_preflight["status"], "blocked");
    assert_eq!(design_preflight["reason"], "source_apply_request_not_ready");
    assert!(design_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_apply_request_not_ready")));
    assert!(design_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("external_submission_readiness_missing")));
    assert_eq!(
        design_preflight["executor_design_request"]["ready_for_design_review"],
        false
    );
    assert_eq!(
        design_preflight["executor_design_request"]["ready_for_live_runtime_lookup"],
        false
    );
    assert_eq!(
        design_preflight["executor_design_request"]["ready_for_patch_application"],
        false
    );
    assert_runtime_executor_design_preflight_read_only(&design_preflight);

    assert!(markdown.contains("- design_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_design_review: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_design_preflight_accepts_ready_apply_request() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let design_preflight =
        build_interaction_feedback_runtime_executor_design_preflight(&apply_request);
    let markdown = render_interaction_feedback_runtime_executor_design_preflight(&design_preflight);

    assert_eq!(
        design_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA
    );
    assert_eq!(design_preflight["input_kind"], "patch_apply_request");
    assert_eq!(
        design_preflight["source_apply_request_verdict"],
        "ready_for_external_executor"
    );
    assert_eq!(design_preflight["source_world_verdict"], "not_verified");
    assert_eq!(
        design_preflight["design_preflight_verdict"],
        "ready_for_runtime_executor_design"
    );
    assert_eq!(design_preflight["status"], "ready");
    assert_eq!(
        design_preflight["reason"],
        "runtime_executor_design_preflight_ready"
    );
    assert_eq!(design_preflight["failure_reasons"], json!([]));
    assert_eq!(
        design_preflight["executor_design_request"]["design_request_id"],
        "runtime_executor_design_arrival_bath_move_002"
    );
    assert_eq!(
        design_preflight["executor_design_request"]["source_apply_request_id"],
        "apply_request_arrival_bath_move_002"
    );
    assert_eq!(
        design_preflight["executor_design_request"]["target_runtime"]["executor"],
        "separate_lswr_patch_executor"
    );
    assert_eq!(
        design_preflight["executor_design_request"]["patch"]["args"]["cell"],
        json!([5, 2])
    );
    assert_eq!(
        design_preflight["executor_design_request"]["ready_for_design_review"],
        true
    );
    assert_eq!(
        design_preflight["executor_design_request"]["ready_for_live_runtime_lookup"],
        false
    );
    assert_eq!(
        design_preflight["executor_design_request"]["ready_for_submission"],
        false
    );
    assert_eq!(
        design_preflight["executor_design_request"]["ready_for_patch_application"],
        false
    );
    assert_eq!(
        design_preflight["agent_action_contract"]["may_design_runtime_executor_after_review"],
        true
    );
    assert_runtime_executor_design_preflight_read_only(&design_preflight);

    assert!(markdown.contains("- design_preflight_verdict: `ready_for_runtime_executor_design`"));
    assert!(
        markdown.contains("- design_request_id: `runtime_executor_design_arrival_bath_move_002`")
    );
    assert!(markdown.contains("- ready_for_live_runtime_lookup: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_design_preflight_requires_apply_request_input() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let design_preflight = build_interaction_feedback_runtime_executor_design_preflight(&preflight);

    assert_eq!(design_preflight["input_kind"], "invalid_input");
    assert_eq!(
        design_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_PATCH_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(design_preflight["design_preflight_verdict"], "blocked");
    assert_eq!(design_preflight["status"], "blocked");
    assert_eq!(design_preflight["reason"], "patch_apply_request_required");
    assert_eq!(
        design_preflight["failure_reasons"],
        json!(["patch_apply_request_required"])
    );
    assert_eq!(design_preflight["source_apply_request"], Value::Null);
    assert_runtime_executor_design_preflight_read_only(&design_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_design_preflight_blocks_tampered_apply_request() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let mut apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    apply_request["apply_request"]["apply_performed"] = json!(true);
    apply_request["apply_request"]["submitted_by_this_tool"] = json!(true);
    apply_request["guardrails"]["submits_apply_request"] = json!(true);

    let design_preflight =
        build_interaction_feedback_runtime_executor_design_preflight(&apply_request);

    assert_eq!(design_preflight["design_preflight_verdict"], "blocked");
    assert!(design_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_apply_request_must_not_apply_patch")));
    assert!(design_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_apply_request_must_not_be_submitted")));
    assert!(design_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_apply_request_guardrails_not_read_only")));
    assert_eq!(
        design_preflight["executor_design_request"]["ready_for_design_review"],
        false
    );
    assert_runtime_executor_design_preflight_read_only(&design_preflight);
}

#[test]
fn interaction_feedback_live_runtime_lookup_design_preflight_blocks_without_ready_design() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&draft);
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let design_preflight =
        build_interaction_feedback_runtime_executor_design_preflight(&apply_request);
    let lookup_preflight =
        build_interaction_feedback_live_runtime_lookup_design_preflight(&design_preflight);
    let markdown =
        render_interaction_feedback_live_runtime_lookup_design_preflight(&lookup_preflight);

    assert_eq!(
        lookup_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_LIVE_RUNTIME_LOOKUP_DESIGN_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        lookup_preflight["input_kind"],
        "runtime_executor_design_preflight"
    );
    assert_eq!(
        lookup_preflight["source_design_preflight_verdict"],
        "blocked"
    );
    assert_eq!(lookup_preflight["source_world_verdict"], "not_verified");
    assert_eq!(
        lookup_preflight["lookup_design_preflight_verdict"],
        "blocked"
    );
    assert_eq!(lookup_preflight["status"], "blocked");
    assert_eq!(
        lookup_preflight["reason"],
        "source_design_preflight_not_ready"
    );
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_design_preflight_not_ready")));
    assert_eq!(
        lookup_preflight["lookup_design_request"]["ready_for_lookup_design_review"],
        false
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["ready_for_live_runtime_lookup"],
        false
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["host_contact_attempted"],
        false
    );
    assert_live_runtime_lookup_design_preflight_read_only(&lookup_preflight);

    assert!(markdown.contains("- lookup_design_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_lookup_design_review: `false`"));
}

#[test]
fn interaction_feedback_live_runtime_lookup_design_preflight_accepts_ready_design() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let design_preflight =
        build_interaction_feedback_runtime_executor_design_preflight(&apply_request);
    let lookup_preflight =
        build_interaction_feedback_live_runtime_lookup_design_preflight(&design_preflight);
    let markdown =
        render_interaction_feedback_live_runtime_lookup_design_preflight(&lookup_preflight);

    assert_eq!(
        lookup_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_LIVE_RUNTIME_LOOKUP_DESIGN_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        lookup_preflight["input_kind"],
        "runtime_executor_design_preflight"
    );
    assert_eq!(
        lookup_preflight["source_design_preflight_verdict"],
        "ready_for_runtime_executor_design"
    );
    assert_eq!(lookup_preflight["source_world_verdict"], "not_verified");
    assert_eq!(
        lookup_preflight["lookup_design_preflight_verdict"],
        "ready_for_live_runtime_lookup_design"
    );
    assert_eq!(lookup_preflight["status"], "ready");
    assert_eq!(
        lookup_preflight["reason"],
        "live_runtime_lookup_design_preflight_ready"
    );
    assert_eq!(lookup_preflight["failure_reasons"], json!([]));
    assert_eq!(
        lookup_preflight["lookup_design_request"]["lookup_design_request_id"],
        "live_runtime_lookup_design_arrival_bath_move_002"
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["source_design_request_id"],
        "runtime_executor_design_arrival_bath_move_002"
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["target_runtime"]["executor"],
        "separate_lswr_patch_executor"
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["patch"]["args"]["cell"],
        json!([5, 2])
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["host_binding_requirements"]
            ["host_endpoint_required_from_operator"],
        true
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["host_binding_requirements"]
            ["host_endpoint_provided"],
        false
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["host_binding_requirements"]
            ["network_contact_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["ready_for_lookup_design_review"],
        true
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["ready_for_live_runtime_lookup"],
        false
    );
    assert_eq!(
        lookup_preflight["lookup_design_request"]["live_runtime_lookup_performed"],
        false
    );
    assert_eq!(
        lookup_preflight["agent_action_contract"]["may_design_live_runtime_lookup_after_review"],
        true
    );
    assert_live_runtime_lookup_design_preflight_read_only(&lookup_preflight);

    assert!(markdown
        .contains("- lookup_design_preflight_verdict: `ready_for_live_runtime_lookup_design`"));
    assert!(markdown.contains(
        "- lookup_design_request_id: `live_runtime_lookup_design_arrival_bath_move_002`"
    ));
    assert!(markdown.contains("- ready_for_live_runtime_lookup: `false`"));
}

#[test]
fn interaction_feedback_live_runtime_lookup_design_preflight_requires_design_input() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let lookup_preflight =
        build_interaction_feedback_live_runtime_lookup_design_preflight(&apply_request);

    assert_eq!(lookup_preflight["input_kind"], "invalid_input");
    assert_eq!(
        lookup_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA
    );
    assert_eq!(
        lookup_preflight["lookup_design_preflight_verdict"],
        "blocked"
    );
    assert_eq!(lookup_preflight["status"], "blocked");
    assert_eq!(
        lookup_preflight["reason"],
        "runtime_executor_design_preflight_required"
    );
    assert_eq!(
        lookup_preflight["failure_reasons"],
        json!(["runtime_executor_design_preflight_required"])
    );
    assert_eq!(
        lookup_preflight["source_runtime_executor_design_preflight"],
        Value::Null
    );
    assert_live_runtime_lookup_design_preflight_read_only(&lookup_preflight);
}

#[test]
fn interaction_feedback_live_runtime_lookup_design_preflight_blocks_tampered_design() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let mut design_preflight =
        build_interaction_feedback_runtime_executor_design_preflight(&apply_request);
    design_preflight["executor_design_request"]["ready_for_live_runtime_lookup"] = json!(true);
    design_preflight["executor_design_request"]["execution_performed"] = json!(true);
    design_preflight["guardrails"]["queries_live_runtime"] = json!(true);

    let lookup_preflight =
        build_interaction_feedback_live_runtime_lookup_design_preflight(&design_preflight);

    assert_eq!(
        lookup_preflight["lookup_design_preflight_verdict"],
        "blocked"
    );
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_must_not_allow_live_runtime_lookup")));
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_must_not_have_executed")));
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("source_design_guardrails_not_read_only")));
    assert_eq!(
        lookup_preflight["lookup_design_request"]["ready_for_lookup_design_review"],
        false
    );
    assert_live_runtime_lookup_design_preflight_read_only(&lookup_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_live_lookup_preflight_blocks_without_lookup_snapshot() {
    let design_preflight = ready_runtime_executor_design_preflight();
    let lookup_preflight =
        build_interaction_feedback_runtime_executor_live_lookup_preflight(&design_preflight);
    let markdown =
        render_interaction_feedback_runtime_executor_live_lookup_preflight(&lookup_preflight);

    assert_eq!(
        lookup_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        lookup_preflight["input_kind"],
        "runtime_executor_design_preflight"
    );
    assert_eq!(
        lookup_preflight["source_design_preflight_verdict"],
        "ready_for_runtime_executor_design"
    );
    assert_eq!(lookup_preflight["source_world_verdict"], "not_verified");
    assert_eq!(lookup_preflight["lookup_preflight_verdict"], "blocked");
    assert_eq!(lookup_preflight["status"], "blocked");
    assert_eq!(
        lookup_preflight["reason"],
        "explicit_lookup_snapshot_required"
    );
    assert_eq!(
        lookup_preflight["failure_reasons"],
        json!(["explicit_lookup_snapshot_required"])
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["ready_for_operator_submission_review"],
        false
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["ready_for_submission"],
        false
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["ready_for_patch_application"],
        false
    );
    assert_runtime_executor_live_lookup_preflight_read_only(&lookup_preflight);

    assert!(markdown.contains("- lookup_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_operator_submission_review: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_live_lookup_preflight_accepts_explicit_snapshot() {
    let design_preflight = ready_runtime_executor_design_preflight();
    let lookup_preflight =
        build_interaction_feedback_runtime_executor_live_lookup_preflight(&json!({
            "design_preflight": design_preflight,
            "lookup_snapshot": explicit_live_lookup_snapshot()
        }));
    let markdown =
        render_interaction_feedback_runtime_executor_live_lookup_preflight(&lookup_preflight);

    assert_eq!(
        lookup_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        lookup_preflight["input_kind"],
        "design_preflight_with_lookup_snapshot_wrapper"
    );
    assert_eq!(
        lookup_preflight["lookup_snapshot_schema"],
        LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA
    );
    assert_eq!(
        lookup_preflight["lookup_preflight_verdict"],
        "ready_for_operator_submission_review"
    );
    assert_eq!(lookup_preflight["status"], "ready");
    assert_eq!(
        lookup_preflight["reason"],
        "live_lookup_preflight_ready_for_operator_submission_review"
    );
    assert_eq!(lookup_preflight["failure_reasons"], json!([]));
    assert_eq!(
        lookup_preflight["lookup_evidence"]["lookup_evidence_id"],
        "live_lookup_arrival_bath_move_002"
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["source_design_request_id"],
        "runtime_executor_design_arrival_bath_move_002"
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["source_apply_request_id"],
        "apply_request_arrival_bath_move_002"
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["runtime_family"],
        "lswr"
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["world_id"],
        "onsen_live_session"
    );
    assert_eq!(lookup_preflight["lookup_evidence"]["branch_id"], "main");
    assert_eq!(
        lookup_preflight["lookup_evidence"]["runtime_generation"],
        "runtime_gen_1284"
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["patch_id"],
        "patch_arrival_bath_move_002"
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["target_entities"],
        json!(["bath"])
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["ready_for_operator_submission_review"],
        true
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["ready_for_submission"],
        false
    );
    assert_eq!(
        lookup_preflight["lookup_evidence"]["ready_for_patch_application"],
        false
    );
    assert_eq!(
        lookup_preflight["agent_action_contract"]["may_review_operator_submission_after_gate"],
        true
    );
    assert_runtime_executor_live_lookup_preflight_read_only(&lookup_preflight);

    assert!(markdown.contains("- lookup_preflight_verdict: `ready_for_operator_submission_review`"));
    assert!(markdown.contains("- lookup_evidence_id: `live_lookup_arrival_bath_move_002`"));
    assert!(markdown.contains("- ready_for_submission: `false`"));
    assert!(markdown.contains("- ready_for_patch_application: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_live_lookup_preflight_blocks_mismatched_snapshot() {
    let design_preflight = ready_runtime_executor_design_preflight();
    let mut snapshot = explicit_live_lookup_snapshot();
    snapshot["branch_id"] = json!("experiment");
    snapshot["target_entities_present"] = json!(false);
    snapshot["entities_present"] = json!(["bench"]);
    snapshot["mutation_performed"] = json!(true);

    let lookup_preflight =
        build_interaction_feedback_runtime_executor_live_lookup_preflight(&json!({
            "design_preflight": design_preflight,
            "lookup_snapshot": snapshot
        }));

    assert_eq!(lookup_preflight["lookup_preflight_verdict"], "blocked");
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("lookup_snapshot_must_not_mutate")));
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("branch_id_mismatch")));
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("target_entities_not_present")));
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("lookup_snapshot_missing_patch_entities")));
    assert_eq!(
        lookup_preflight["lookup_evidence"]["ready_for_operator_submission_review"],
        false
    );
    assert_runtime_executor_live_lookup_preflight_read_only(&lookup_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_live_lookup_preflight_requires_design_preflight_input() {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let lookup_preflight =
        build_interaction_feedback_runtime_executor_live_lookup_preflight(&json!({
            "design_preflight": apply_request,
            "lookup_snapshot": explicit_live_lookup_snapshot()
        }));

    assert_eq!(
        lookup_preflight["input_kind"],
        "design_preflight_with_lookup_snapshot_wrapper"
    );
    assert_eq!(
        lookup_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_PATCH_APPLY_REQUEST_SCHEMA
    );
    assert_eq!(lookup_preflight["lookup_preflight_verdict"], "blocked");
    assert_eq!(
        lookup_preflight["reason"],
        "runtime_executor_design_preflight_required"
    );
    assert!(lookup_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("runtime_executor_design_preflight_required")));
    assert_eq!(lookup_preflight["source_design_preflight"], Value::Null);
    assert_runtime_executor_live_lookup_preflight_read_only(&lookup_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_operator_submission_token_preflight_blocks_without_operator_decision(
) {
    let lookup_preflight = ready_runtime_executor_live_lookup_preflight();
    let submission_preflight =
        build_interaction_feedback_runtime_executor_operator_submission_token_preflight(
            &lookup_preflight,
        );
    let markdown = render_interaction_feedback_runtime_executor_operator_submission_token_preflight(
        &submission_preflight,
    );

    assert_eq!(
        submission_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        submission_preflight["input_kind"],
        "runtime_executor_live_lookup_preflight"
    );
    assert_eq!(
        submission_preflight["source_lookup_preflight_verdict"],
        "ready_for_operator_submission_review"
    );
    assert_eq!(submission_preflight["source_world_verdict"], "not_verified");
    assert_eq!(
        submission_preflight["operator_decision_schema"],
        Value::Null
    );
    assert_eq!(
        submission_preflight["submission_token_preflight_verdict"],
        "blocked"
    );
    assert_eq!(submission_preflight["status"], "blocked");
    assert_eq!(
        submission_preflight["reason"],
        "explicit_operator_submission_decision_required"
    );
    assert_eq!(
        submission_preflight["failure_reasons"],
        json!(["explicit_operator_submission_decision_required"])
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["token_id"],
        Value::Null
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]
            ["ready_for_patch_application_gate_review"],
        false
    );
    assert_runtime_executor_operator_submission_token_preflight_read_only(&submission_preflight);

    assert!(markdown.contains("- submission_token_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_patch_application_gate_review: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_operator_submission_token_preflight_accepts_explicit_decision(
) {
    let lookup_preflight = ready_runtime_executor_live_lookup_preflight();
    let submission_preflight =
        build_interaction_feedback_runtime_executor_operator_submission_token_preflight(&json!({
            "lookup_preflight": lookup_preflight,
            "operator_decision": explicit_operator_submission_decision()
        }));
    let markdown = render_interaction_feedback_runtime_executor_operator_submission_token_preflight(
        &submission_preflight,
    );

    assert_eq!(
        submission_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        submission_preflight["input_kind"],
        "live_lookup_preflight_with_operator_decision_wrapper"
    );
    assert_eq!(
        submission_preflight["operator_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA
    );
    assert_eq!(
        submission_preflight["submission_token_preflight_verdict"],
        "ready_for_patch_application_gate_review"
    );
    assert_eq!(submission_preflight["status"], "ready");
    assert_eq!(
        submission_preflight["reason"],
        "operator_submission_token_preflight_ready_for_patch_application_gate_review"
    );
    assert_eq!(submission_preflight["failure_reasons"], json!([]));
    assert_eq!(
        submission_preflight["operator_submission_token"]["token_id"],
        "submit_patch_arrival_bath_move_002"
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["operator_decision_id"],
        "operator_decision_arrival_bath_move_002"
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["operator_id"],
        "human:owner"
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["lookup_evidence_id"],
        "live_lookup_arrival_bath_move_002"
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["runtime_generation"],
        "runtime_gen_1284"
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["patch_id"],
        "patch_arrival_bath_move_002"
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["idempotency_key"],
        "patch_arrival_bath_move_002/runtime_gen_1284/operator_decision_arrival_bath_move_002"
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["token_candidate_emitted_by_this_tool"],
        true
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["submission_token_persisted"],
        false
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]
            ["ready_for_patch_application_gate_review"],
        true
    );
    assert_eq!(
        submission_preflight["operator_submission_token"]["ready_for_executor_submission"],
        false
    );
    assert_eq!(
        submission_preflight["next_allowed_gate"],
        "patch_application_gate_review"
    );
    assert_runtime_executor_operator_submission_token_preflight_read_only(&submission_preflight);

    assert!(markdown.contains(
        "- submission_token_preflight_verdict: `ready_for_patch_application_gate_review`"
    ));
    assert!(markdown.contains("- token_id: `submit_patch_arrival_bath_move_002`"));
    assert!(markdown.contains("- ready_for_executor_submission: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_operator_submission_token_preflight_blocks_bad_decision() {
    let lookup_preflight = ready_runtime_executor_live_lookup_preflight();
    let mut decision = explicit_operator_submission_decision();
    decision["decision"] = json!("rejected");
    decision["approved_scope"]["runtime_generation"] = json!("runtime_gen_stale");
    decision["approved_scope"]["patch_id"] = json!("patch_other");
    decision["patch_application_allowed"] = json!(true);
    decision["writes_state"] = json!(true);

    let submission_preflight =
        build_interaction_feedback_runtime_executor_operator_submission_token_preflight(&json!({
            "lookup_preflight": lookup_preflight,
            "operator_decision": decision
        }));

    assert_eq!(
        submission_preflight["submission_token_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = submission_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("operator_decision_must_be_approved")));
    assert!(failure_reasons.contains(&json!(
        "operator_decision_runtime_generation_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!("operator_decision_patch_scope_mismatch")));
    assert!(failure_reasons.contains(&json!("operator_decision_must_not_allow_patch_application")));
    assert!(failure_reasons.contains(&json!("operator_decision_must_not_write_state")));
    assert_eq!(
        submission_preflight["operator_submission_token"]
            ["ready_for_patch_application_gate_review"],
        false
    );
    assert_runtime_executor_operator_submission_token_preflight_read_only(&submission_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_operator_submission_token_preflight_requires_lookup_input()
{
    let design_preflight = ready_runtime_executor_design_preflight();
    let submission_preflight =
        build_interaction_feedback_runtime_executor_operator_submission_token_preflight(&json!({
            "lookup_preflight": design_preflight,
            "operator_decision": explicit_operator_submission_decision()
        }));

    assert_eq!(
        submission_preflight["input_kind"],
        "live_lookup_preflight_with_operator_decision_wrapper"
    );
    assert_eq!(
        submission_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DESIGN_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        submission_preflight["submission_token_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        submission_preflight["reason"],
        "runtime_executor_live_lookup_preflight_required"
    );
    assert!(submission_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("runtime_executor_live_lookup_preflight_required")));
    assert_eq!(submission_preflight["source_lookup_preflight"], Value::Null);
    assert_runtime_executor_operator_submission_token_preflight_read_only(&submission_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_patch_application_gate_preflight_blocks_without_gate_decision(
) {
    let submission_preflight = ready_runtime_executor_operator_submission_token_preflight();
    let gate_preflight =
        build_interaction_feedback_runtime_executor_patch_application_gate_preflight(
            &submission_preflight,
        );
    let markdown = render_interaction_feedback_runtime_executor_patch_application_gate_preflight(
        &gate_preflight,
    );

    assert_eq!(
        gate_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        gate_preflight["input_kind"],
        "runtime_executor_operator_submission_token_preflight"
    );
    assert_eq!(
        gate_preflight["source_submission_token_preflight_verdict"],
        "ready_for_patch_application_gate_review"
    );
    assert_eq!(gate_preflight["source_world_verdict"], "not_verified");
    assert_eq!(
        gate_preflight["patch_application_gate_decision_schema"],
        Value::Null
    );
    assert_eq!(
        gate_preflight["patch_application_gate_preflight_verdict"],
        "blocked"
    );
    assert_eq!(gate_preflight["status"], "blocked");
    assert_eq!(
        gate_preflight["reason"],
        "explicit_patch_application_gate_decision_required"
    );
    assert_eq!(
        gate_preflight["failure_reasons"],
        json!(["explicit_patch_application_gate_decision_required"])
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["gate_id"],
        Value::Null
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["ready_for_separate_patch_executor_invocation"],
        false
    );
    assert_runtime_executor_patch_application_gate_preflight_read_only(&gate_preflight);

    assert!(markdown.contains("- patch_application_gate_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_separate_patch_executor_invocation: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_patch_application_gate_preflight_accepts_explicit_decision(
) {
    let submission_preflight = ready_runtime_executor_operator_submission_token_preflight();
    let gate_preflight =
        build_interaction_feedback_runtime_executor_patch_application_gate_preflight(&json!({
            "submission_token_preflight": submission_preflight,
            "patch_application_gate_decision": explicit_patch_application_gate_decision()
        }));
    let markdown = render_interaction_feedback_runtime_executor_patch_application_gate_preflight(
        &gate_preflight,
    );

    assert_eq!(
        gate_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        gate_preflight["input_kind"],
        "operator_submission_token_preflight_with_patch_application_gate_decision_wrapper"
    );
    assert_eq!(
        gate_preflight["patch_application_gate_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_DECISION_SCHEMA
    );
    assert_eq!(
        gate_preflight["patch_application_gate_preflight_verdict"],
        "ready_for_separate_executor_invocation"
    );
    assert_eq!(gate_preflight["status"], "ready");
    assert_eq!(
        gate_preflight["reason"],
        "patch_application_gate_preflight_ready_for_separate_executor_invocation"
    );
    assert_eq!(gate_preflight["failure_reasons"], json!([]));
    assert_eq!(
        gate_preflight["patch_application_gate"]["gate_id"],
        "patch_application_gate_arrival_bath_move_002"
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["gate_decision_id"],
        "patch_application_gate_decision_arrival_bath_move_002"
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["operator_submission_token_id"],
        "submit_patch_arrival_bath_move_002"
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["operator_submission_decision_id"],
        "operator_decision_arrival_bath_move_002"
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["patch_id"],
        "patch_arrival_bath_move_002"
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["idempotency_key"],
        "patch_arrival_bath_move_002/runtime_gen_1284/submit_patch_arrival_bath_move_002/patch_application_gate_decision_arrival_bath_move_002"
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["ready_for_separate_patch_executor_invocation"],
        true
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]
            ["separate_patch_executor_invocation_allowed_after_this_gate"],
        true
    );
    assert_eq!(
        gate_preflight["patch_application_gate"]["executor_invocation_performed_by_this_tool"],
        false
    );
    assert_eq!(
        gate_preflight["next_allowed_gate"],
        "separate_patch_application_executor_invocation"
    );
    assert_runtime_executor_patch_application_gate_preflight_read_only(&gate_preflight);

    assert!(markdown.contains(
        "- patch_application_gate_preflight_verdict: `ready_for_separate_executor_invocation`"
    ));
    assert!(markdown.contains("- gate_id: `patch_application_gate_arrival_bath_move_002`"));
    assert!(markdown.contains("- executor_invocation_performed_by_this_tool: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_patch_application_gate_preflight_blocks_bad_decision() {
    let submission_preflight = ready_runtime_executor_operator_submission_token_preflight();
    let mut decision = explicit_patch_application_gate_decision();
    decision["decision"] = json!("rejected");
    decision["approved_scope"]["runtime_generation"] = json!("runtime_gen_stale");
    decision["approved_scope"]["patch_id"] = json!("patch_other");
    decision["separate_patch_executor_invocation_allowed"] = json!(false);
    decision["executor_invocation_performed"] = json!(true);
    decision["writes_state"] = json!(true);

    let gate_preflight =
        build_interaction_feedback_runtime_executor_patch_application_gate_preflight(&json!({
            "submission_token_preflight": submission_preflight,
            "patch_application_gate_decision": decision
        }));

    assert_eq!(
        gate_preflight["patch_application_gate_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = gate_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("patch_application_gate_decision_must_be_approved")));
    assert!(failure_reasons.contains(&json!(
        "patch_application_gate_runtime_generation_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!("patch_application_gate_patch_scope_mismatch")));
    assert!(failure_reasons.contains(&json!(
        "patch_application_gate_must_allow_separate_executor_invocation"
    )));
    assert!(failure_reasons.contains(&json!("patch_application_gate_must_not_invoke_executor")));
    assert!(failure_reasons.contains(&json!("patch_application_gate_must_not_write_state")));
    assert_eq!(
        gate_preflight["patch_application_gate"]["ready_for_separate_patch_executor_invocation"],
        false
    );
    assert_runtime_executor_patch_application_gate_preflight_read_only(&gate_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_patch_application_gate_preflight_requires_submission_input(
) {
    let lookup_preflight = ready_runtime_executor_live_lookup_preflight();
    let gate_preflight =
        build_interaction_feedback_runtime_executor_patch_application_gate_preflight(&json!({
            "submission_token_preflight": lookup_preflight,
            "patch_application_gate_decision": explicit_patch_application_gate_decision()
        }));

    assert_eq!(
        gate_preflight["input_kind"],
        "operator_submission_token_preflight_with_patch_application_gate_decision_wrapper"
    );
    assert_eq!(
        gate_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        gate_preflight["patch_application_gate_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        gate_preflight["reason"],
        "runtime_executor_operator_submission_token_preflight_required"
    );
    assert!(gate_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!(
            "runtime_executor_operator_submission_token_preflight_required"
        )));
    assert_eq!(
        gate_preflight["source_submission_token_preflight"],
        Value::Null
    );
    assert_runtime_executor_patch_application_gate_preflight_read_only(&gate_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_patch_executor_invocation_preflight_blocks_without_invocation_decision(
) {
    let gate_preflight = ready_runtime_executor_patch_application_gate_preflight();
    let invocation_preflight =
        build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(
            &gate_preflight,
        );
    let markdown = render_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(
        &invocation_preflight,
    );

    assert_eq!(
        invocation_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        invocation_preflight["input_kind"],
        "runtime_executor_patch_application_gate_preflight"
    );
    assert_eq!(
        invocation_preflight["source_patch_application_gate_preflight_verdict"],
        "ready_for_separate_executor_invocation"
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_decision_schema"],
        Value::Null
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_preflight_verdict"],
        "blocked"
    );
    assert_eq!(invocation_preflight["status"], "blocked");
    assert_eq!(
        invocation_preflight["reason"],
        "explicit_patch_executor_invocation_decision_required"
    );
    assert_eq!(
        invocation_preflight["failure_reasons"],
        json!(["explicit_patch_executor_invocation_decision_required"])
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]["request_id"],
        Value::Null
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]
            ["ready_for_separate_patch_executor_invocation_request"],
        false
    );
    assert_runtime_executor_patch_executor_invocation_preflight_read_only(&invocation_preflight);

    assert!(markdown.contains("- patch_executor_invocation_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_separate_patch_executor_invocation_request: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_patch_executor_invocation_preflight_accepts_explicit_decision(
) {
    let gate_preflight = ready_runtime_executor_patch_application_gate_preflight();
    let invocation_preflight =
        build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(&json!({
            "patch_application_gate_preflight": gate_preflight,
            "patch_executor_invocation_decision": explicit_patch_executor_invocation_decision()
        }));
    let markdown = render_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(
        &invocation_preflight,
    );

    assert_eq!(
        invocation_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        invocation_preflight["input_kind"],
        "patch_application_gate_preflight_with_patch_executor_invocation_decision_wrapper"
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_DECISION_SCHEMA
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_preflight_verdict"],
        "ready_for_separate_patch_executor_invocation_request"
    );
    assert_eq!(invocation_preflight["status"], "ready");
    assert_eq!(
        invocation_preflight["reason"],
        "patch_executor_invocation_preflight_ready_for_invocation_request"
    );
    assert_eq!(invocation_preflight["failure_reasons"], json!([]));
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]["request_id"],
        "patch_executor_invocation_arrival_bath_move_002"
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]["target_executor"],
        "separate_lswr_patch_executor"
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]["invocation_decision_id"],
        "patch_executor_invocation_decision_arrival_bath_move_002"
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]["patch_application_gate_id"],
        "patch_application_gate_arrival_bath_move_002"
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]["patch_id"],
        "patch_arrival_bath_move_002"
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]["idempotency_key"],
        "patch_arrival_bath_move_002/runtime_gen_1284/patch_application_gate_arrival_bath_move_002/patch_executor_invocation_decision_arrival_bath_move_002"
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]
            ["ready_for_separate_patch_executor_invocation_request"],
        true
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]
            ["invocation_request_emitted_by_this_tool"],
        true
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]
            ["executor_invocation_performed_by_this_tool"],
        false
    );
    assert_eq!(
        invocation_preflight["next_allowed_gate"],
        "separate_patch_executor_runtime_application_evidence"
    );
    assert_runtime_executor_patch_executor_invocation_preflight_read_only(&invocation_preflight);

    assert!(markdown.contains(
        "- patch_executor_invocation_preflight_verdict: `ready_for_separate_patch_executor_invocation_request`"
    ));
    assert!(markdown.contains("- request_id: `patch_executor_invocation_arrival_bath_move_002`"));
    assert!(markdown.contains("- invocation_request_emitted_by_this_tool: `true`"));
    assert!(markdown.contains("- executor_invocation_performed_by_this_tool: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_patch_executor_invocation_preflight_blocks_bad_decision() {
    let gate_preflight = ready_runtime_executor_patch_application_gate_preflight();
    let mut decision = explicit_patch_executor_invocation_decision();
    decision["decision"] = json!("rejected");
    decision["approved_scope"]["runtime_generation"] = json!("runtime_gen_stale");
    decision["approved_scope"]["patch_id"] = json!("patch_other");
    decision["separate_patch_executor_invocation_allowed"] = json!(false);
    decision["executor_invocation_performed"] = json!(true);
    decision["executor_queue_submission_performed"] = json!(true);
    decision["writes_state"] = json!(true);

    let invocation_preflight =
        build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(&json!({
            "patch_application_gate_preflight": gate_preflight,
            "patch_executor_invocation_decision": decision
        }));

    assert_eq!(
        invocation_preflight["patch_executor_invocation_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = invocation_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "patch_executor_invocation_decision_must_be_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_executor_invocation_runtime_generation_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!("patch_executor_invocation_patch_scope_mismatch")));
    assert!(failure_reasons.contains(&json!(
        "patch_executor_invocation_decision_must_allow_invocation"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_executor_invocation_decision_must_not_invoke_executor"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_executor_invocation_decision_must_not_submit_queue"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_executor_invocation_decision_must_not_write_state"
    )));
    assert_eq!(
        invocation_preflight["patch_executor_invocation_request"]
            ["ready_for_separate_patch_executor_invocation_request"],
        false
    );
    assert_runtime_executor_patch_executor_invocation_preflight_read_only(&invocation_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_patch_executor_invocation_preflight_requires_gate_input() {
    let submission_preflight = ready_runtime_executor_operator_submission_token_preflight();
    let invocation_preflight =
        build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(&json!({
            "patch_application_gate_preflight": submission_preflight,
            "patch_executor_invocation_decision": explicit_patch_executor_invocation_decision()
        }));

    assert_eq!(
        invocation_preflight["input_kind"],
        "patch_application_gate_preflight_with_patch_executor_invocation_decision_wrapper"
    );
    assert_eq!(
        invocation_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        invocation_preflight["patch_executor_invocation_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        invocation_preflight["reason"],
        "runtime_executor_patch_application_gate_preflight_required"
    );
    assert!(invocation_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!(
            "runtime_executor_patch_application_gate_preflight_required"
        )));
    assert_eq!(
        invocation_preflight["source_patch_application_gate_preflight"],
        Value::Null
    );
    assert_runtime_executor_patch_executor_invocation_preflight_read_only(&invocation_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight_blocks_without_evidence(
) {
    let invocation_preflight = ready_runtime_executor_patch_executor_invocation_preflight();
    let evidence_preflight =
        build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
            &invocation_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
            &evidence_preflight,
        );

    assert_eq!(
        evidence_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        evidence_preflight["input_kind"],
        "runtime_executor_patch_executor_invocation_preflight"
    );
    assert_eq!(
        evidence_preflight["source_patch_executor_invocation_preflight_verdict"],
        "ready_for_separate_patch_executor_invocation_request"
    );
    assert_eq!(
        evidence_preflight["patch_runtime_application_evidence_schema"],
        Value::Null
    );
    assert_eq!(
        evidence_preflight["patch_runtime_application_evidence_preflight_verdict"],
        "blocked"
    );
    assert_eq!(evidence_preflight["status"], "blocked");
    assert_eq!(
        evidence_preflight["reason"],
        "explicit_patch_runtime_application_evidence_required"
    );
    assert_eq!(
        evidence_preflight["runtime_application_evidence"]["evidence_id"],
        Value::Null
    );
    assert_runtime_executor_patch_runtime_application_evidence_preflight_read_only(
        &evidence_preflight,
    );

    assert!(markdown.contains("- patch_runtime_application_evidence_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- external_patch_application_claimed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight_accepts_explicit_evidence(
) {
    let invocation_preflight = ready_runtime_executor_patch_executor_invocation_preflight();
    let evidence_preflight =
        build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
            &json!({
                "patch_executor_invocation_preflight": invocation_preflight,
                "patch_runtime_application_evidence": explicit_patch_runtime_application_evidence()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
            &evidence_preflight,
        );

    assert_eq!(
        evidence_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        evidence_preflight["patch_runtime_application_evidence_schema"],
        LSWR_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_SCHEMA
    );
    assert_eq!(
        evidence_preflight["patch_runtime_application_evidence_preflight_verdict"],
        "ready_for_post_apply_verification_review"
    );
    assert_eq!(evidence_preflight["status"], "ready");
    assert_eq!(
        evidence_preflight["reason"],
        "patch_runtime_application_evidence_preflight_ready_for_post_apply_verification_review"
    );
    assert_eq!(evidence_preflight["failure_reasons"], json!([]));
    assert_eq!(
        evidence_preflight["runtime_application_evidence"]["evidence_id"],
        "runtime_application_evidence_arrival_bath_move_002"
    );
    assert_eq!(
        evidence_preflight["runtime_application_evidence"]["source_invocation_request_id"],
        "patch_executor_invocation_arrival_bath_move_002"
    );
    assert_eq!(
        evidence_preflight["runtime_application_evidence"]["target_executor"],
        "separate_lswr_patch_executor"
    );
    assert_eq!(
        evidence_preflight["runtime_application_evidence"]["application_status"],
        "applied_claimed_not_verified"
    );
    assert_eq!(
        evidence_preflight["runtime_application_evidence"]["external_executor_invocation_observed"],
        true
    );
    assert_eq!(
        evidence_preflight["runtime_application_evidence"]["external_patch_application_claimed"],
        true
    );
    assert_eq!(
        evidence_preflight["runtime_application_evidence"]
            ["post_apply_verification_performed_by_this_tool"],
        false
    );
    assert_eq!(
        evidence_preflight["next_allowed_gate"],
        "post_apply_verification_preflight"
    );
    assert_runtime_executor_patch_runtime_application_evidence_preflight_read_only(
        &evidence_preflight,
    );

    assert!(markdown.contains(
        "- patch_runtime_application_evidence_preflight_verdict: `ready_for_post_apply_verification_review`"
    ));
    assert!(
        markdown.contains("- evidence_id: `runtime_application_evidence_arrival_bath_move_002`")
    );
    assert!(markdown.contains("- external_patch_application_claimed: `true`"));
    assert!(markdown.contains("- post_apply_verification_performed_by_this_tool: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight_blocks_bad_evidence(
) {
    let invocation_preflight = ready_runtime_executor_patch_executor_invocation_preflight();
    let mut evidence = explicit_patch_runtime_application_evidence();
    evidence["evidence_kind"] = json!("operator_note");
    evidence["source_invocation_request_scope"]["runtime_generation"] = json!("runtime_gen_stale");
    evidence["source_invocation_request_scope"]["patch_id"] = json!("patch_other");
    evidence["executor_invocation_observed"] = json!(false);
    evidence["patch_application_claimed"] = json!(false);
    evidence["post_apply_verification_performed"] = json!(true);
    evidence["world_verdict_rewrite_allowed"] = json!(true);
    evidence["evidence_record_persisted"] = json!(true);

    let evidence_preflight =
        build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
            &json!({
                "patch_executor_invocation_preflight": invocation_preflight,
                "patch_runtime_application_evidence": evidence
            }),
        );

    assert_eq!(
        evidence_preflight["patch_runtime_application_evidence_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = evidence_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "patch_runtime_application_evidence_must_be_external_claim"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_runtime_application_evidence_generation_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_runtime_application_evidence_patch_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_runtime_application_evidence_must_observe_executor_invocation"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_runtime_application_evidence_must_claim_patch_application"
    )));
    assert!(failure_reasons.contains(&json!("patch_runtime_application_evidence_must_not_verify")));
    assert!(failure_reasons.contains(&json!(
        "patch_runtime_application_evidence_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "patch_runtime_application_evidence_must_not_persist_record"
    )));
    assert_runtime_executor_patch_runtime_application_evidence_preflight_read_only(
        &evidence_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight_requires_invocation_input(
) {
    let gate_preflight = ready_runtime_executor_patch_application_gate_preflight();
    let evidence_preflight =
        build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
            &json!({
                "patch_executor_invocation_preflight": gate_preflight,
                "patch_runtime_application_evidence": explicit_patch_runtime_application_evidence()
            }),
        );

    assert_eq!(
        evidence_preflight["input_kind"],
        "patch_executor_invocation_preflight_with_runtime_application_evidence_wrapper"
    );
    assert_eq!(
        evidence_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        evidence_preflight["patch_runtime_application_evidence_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        evidence_preflight["reason"],
        "runtime_executor_patch_executor_invocation_preflight_required"
    );
    assert_eq!(
        evidence_preflight["source_patch_executor_invocation_preflight"],
        Value::Null
    );
    assert_runtime_executor_patch_runtime_application_evidence_preflight_read_only(
        &evidence_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_post_apply_verification_preflight_blocks_without_evidence()
{
    let application_preflight =
        ready_runtime_executor_patch_runtime_application_evidence_preflight();
    let verification_preflight =
        build_interaction_feedback_runtime_executor_post_apply_verification_preflight(
            &application_preflight,
        );
    let markdown = render_interaction_feedback_runtime_executor_post_apply_verification_preflight(
        &verification_preflight,
    );

    assert_eq!(
        verification_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        verification_preflight["input_kind"],
        "runtime_executor_patch_runtime_application_evidence_preflight"
    );
    assert_eq!(
        verification_preflight["source_runtime_application_evidence_preflight_verdict"],
        "ready_for_post_apply_verification_review"
    );
    assert_eq!(
        verification_preflight["post_apply_verification_evidence_schema"],
        Value::Null
    );
    assert_eq!(
        verification_preflight["post_apply_verification_preflight_verdict"],
        "blocked"
    );
    assert_eq!(verification_preflight["status"], "blocked");
    assert_eq!(
        verification_preflight["reason"],
        "explicit_post_apply_verification_evidence_required"
    );
    assert_runtime_executor_post_apply_verification_preflight_read_only(&verification_preflight);

    assert!(markdown.contains("- post_apply_verification_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_outcome_ingestion_review: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_post_apply_verification_preflight_accepts_explicit_evidence(
) {
    let application_preflight =
        ready_runtime_executor_patch_runtime_application_evidence_preflight();
    let verification_preflight =
        build_interaction_feedback_runtime_executor_post_apply_verification_preflight(&json!({
            "patch_runtime_application_evidence_preflight": application_preflight,
            "post_apply_verification_evidence": explicit_post_apply_verification_evidence()
        }));
    let markdown = render_interaction_feedback_runtime_executor_post_apply_verification_preflight(
        &verification_preflight,
    );

    assert_eq!(
        verification_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        verification_preflight["post_apply_verification_evidence_schema"],
        LSWR_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_EVIDENCE_SCHEMA
    );
    assert_eq!(
        verification_preflight["post_apply_verification_preflight_verdict"],
        "ready_for_outcome_ingestion_review"
    );
    assert_eq!(verification_preflight["status"], "ready");
    assert_eq!(
        verification_preflight["reason"],
        "post_apply_verification_preflight_ready_for_outcome_ingestion_review"
    );
    assert_eq!(verification_preflight["failure_reasons"], json!([]));
    assert_eq!(
        verification_preflight["post_apply_verification"]["verification_id"],
        "post_apply_verification_arrival_bath_move_002"
    );
    assert_eq!(
        verification_preflight["post_apply_verification"]["runtime_application_evidence_id"],
        "runtime_application_evidence_arrival_bath_move_002"
    );
    assert_eq!(
        verification_preflight["post_apply_verification"]["verification_verdict"],
        "verified"
    );
    assert_eq!(
        verification_preflight["post_apply_verification"]["expected_effect_passed"],
        true
    );
    assert_eq!(
        verification_preflight["post_apply_verification"]["presentation_readback_consistent"],
        true
    );
    assert_eq!(
        verification_preflight["post_apply_verification"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        verification_preflight["post_apply_verification"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        verification_preflight["next_allowed_gate"],
        "outcome_ingestion_review"
    );
    assert_runtime_executor_post_apply_verification_preflight_read_only(&verification_preflight);

    assert!(markdown.contains(
        "- post_apply_verification_preflight_verdict: `ready_for_outcome_ingestion_review`"
    ));
    assert!(markdown.contains("- verification_verdict: `verified`"));
    assert!(markdown.contains("- outcome_ingestion_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_post_apply_verification_preflight_blocks_bad_evidence() {
    let application_preflight =
        ready_runtime_executor_patch_runtime_application_evidence_preflight();
    let mut evidence = explicit_post_apply_verification_evidence();
    evidence["evidence_kind"] = json!("operator_note");
    evidence["source_runtime_application_evidence_scope"]["runtime_generation"] =
        json!("runtime_gen_stale");
    evidence["source_runtime_application_evidence_scope"]["patch_id"] = json!("patch_other");
    evidence["expected_effect_checked"] = json!(false);
    evidence["presentation_readback_checked"] = json!(false);
    evidence["expected_effect_passed"] = json!(false);
    evidence["outcome_ingestion_allowed"] = json!(true);
    evidence["world_verdict_rewrite_allowed"] = json!(true);
    evidence["verification_record_persisted"] = json!(true);

    let verification_preflight =
        build_interaction_feedback_runtime_executor_post_apply_verification_preflight(&json!({
            "patch_runtime_application_evidence_preflight": application_preflight,
            "post_apply_verification_evidence": evidence
        }));

    assert_eq!(
        verification_preflight["post_apply_verification_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = verification_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("post_apply_verification_evidence_kind_required")));
    assert!(failure_reasons.contains(&json!("post_apply_verification_generation_scope_mismatch")));
    assert!(failure_reasons.contains(&json!("post_apply_verification_patch_scope_mismatch")));
    assert!(failure_reasons.contains(&json!("post_apply_verification_must_check_expected_effect")));
    assert!(failure_reasons.contains(&json!(
        "post_apply_verification_must_check_presentation_readback"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_post_apply_result_requires_expected_effect_passed"
    )));
    assert!(failure_reasons.contains(&json!("post_apply_verification_must_not_allow_ingestion")));
    assert!(failure_reasons.contains(&json!("post_apply_verification_must_not_rewrite_verdict")));
    assert!(failure_reasons.contains(&json!("post_apply_verification_must_not_persist_record")));
    assert_runtime_executor_post_apply_verification_preflight_read_only(&verification_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_post_apply_verification_preflight_requires_application_input(
) {
    let invocation_preflight = ready_runtime_executor_patch_executor_invocation_preflight();
    let verification_preflight =
        build_interaction_feedback_runtime_executor_post_apply_verification_preflight(&json!({
            "patch_runtime_application_evidence_preflight": invocation_preflight,
            "post_apply_verification_evidence": explicit_post_apply_verification_evidence()
        }));

    assert_eq!(
        verification_preflight["input_kind"],
        "runtime_application_evidence_preflight_with_post_apply_verification_evidence_wrapper"
    );
    assert_eq!(
        verification_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        verification_preflight["post_apply_verification_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        verification_preflight["reason"],
        "runtime_executor_patch_runtime_application_evidence_preflight_required"
    );
    assert_eq!(
        verification_preflight["source_runtime_application_evidence_preflight"],
        Value::Null
    );
    assert_runtime_executor_post_apply_verification_preflight_read_only(&verification_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_outcome_ingestion_review_preflight_blocks_without_decision(
) {
    let verification_preflight = ready_runtime_executor_post_apply_verification_preflight();
    let ingestion_preflight =
        build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(
            &verification_preflight,
        );
    let markdown = render_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(
        &ingestion_preflight,
    );

    assert_eq!(
        ingestion_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        ingestion_preflight["input_kind"],
        "runtime_executor_post_apply_verification_preflight"
    );
    assert_eq!(
        ingestion_preflight["source_post_apply_verification_preflight_verdict"],
        "ready_for_outcome_ingestion_review"
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review_decision_schema"],
        Value::Null
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review_preflight_verdict"],
        "blocked"
    );
    assert_eq!(ingestion_preflight["status"], "blocked");
    assert_eq!(
        ingestion_preflight["reason"],
        "explicit_outcome_ingestion_review_decision_required"
    );
    assert_runtime_executor_outcome_ingestion_review_preflight_read_only(&ingestion_preflight);

    assert!(markdown.contains("- outcome_ingestion_review_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_durable_ingestion_gate: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_outcome_ingestion_review_preflight_accepts_explicit_decision(
) {
    let verification_preflight = ready_runtime_executor_post_apply_verification_preflight();
    let ingestion_preflight =
        build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(&json!({
            "post_apply_verification_preflight": verification_preflight,
            "outcome_ingestion_review_decision": explicit_outcome_ingestion_review_decision()
        }));
    let markdown = render_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(
        &ingestion_preflight,
    );

    assert_eq!(
        ingestion_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_DECISION_SCHEMA
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review_preflight_verdict"],
        "ready_for_durable_ingestion_gate"
    );
    assert_eq!(ingestion_preflight["status"], "ready");
    assert_eq!(
        ingestion_preflight["reason"],
        "outcome_ingestion_review_preflight_ready_for_durable_ingestion_gate"
    );
    assert_eq!(ingestion_preflight["failure_reasons"], json!([]));
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review"]["review_id"],
        "outcome_ingestion_review_arrival_bath_move_002"
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review"]["verification_id"],
        "post_apply_verification_arrival_bath_move_002"
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review"]["decision"],
        "approved_for_durable_ingestion_gate"
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review"]["ready_for_durable_ingestion_gate"],
        true
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review"]["durable_ingestion_allowed"],
        false
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        ingestion_preflight["next_allowed_gate"],
        "durable_outcome_ingestion_gate"
    );
    assert_runtime_executor_outcome_ingestion_review_preflight_read_only(&ingestion_preflight);

    assert!(markdown.contains(
        "- outcome_ingestion_review_preflight_verdict: `ready_for_durable_ingestion_gate`"
    ));
    assert!(markdown.contains("- decision: `approved_for_durable_ingestion_gate`"));
    assert!(markdown.contains("- durable_ingestion_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_outcome_ingestion_review_preflight_blocks_bad_decision() {
    let verification_preflight = ready_runtime_executor_post_apply_verification_preflight();
    let mut decision = explicit_outcome_ingestion_review_decision();
    decision["review_kind"] = json!("operator_note");
    decision["decision"] = json!("approved_and_ingest_now");
    decision["source_post_apply_verification_scope"]["verification_id"] =
        json!("post_apply_verification_other");
    decision["source_post_apply_verification_scope"]["patch_id"] = json!("patch_other");
    decision["source_world_verdict"] = json!("verified");
    decision["reviewed_verification_verdict"] = json!("not_verified");
    decision["expected_effect_confirmed_for_ingestion"] = json!(false);
    decision["presentation_readback_confirmed_for_ingestion"] = json!(false);
    decision["durable_ingestion_allowed"] = json!(true);
    decision["world_verdict_rewrite_allowed"] = json!(true);
    decision["outcome_record_persisted"] = json!(true);

    let ingestion_preflight =
        build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(&json!({
            "post_apply_verification_preflight": verification_preflight,
            "outcome_ingestion_review_decision": decision
        }));

    assert_eq!(
        ingestion_preflight["outcome_ingestion_review_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = ingestion_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("outcome_ingestion_review_kind_required")));
    assert!(failure_reasons.contains(&json!("outcome_ingestion_review_decision_not_approved")));
    assert!(failure_reasons.contains(&json!(
        "outcome_ingestion_review_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "outcome_ingestion_review_must_review_verified_evidence"
    )));
    assert!(failure_reasons.contains(&json!(
        "outcome_ingestion_review_must_confirm_expected_effect"
    )));
    assert!(failure_reasons.contains(&json!(
        "outcome_ingestion_review_must_confirm_presentation_readback"
    )));
    assert!(failure_reasons.contains(&json!(
        "outcome_ingestion_review_must_not_allow_durable_ingestion"
    )));
    assert!(failure_reasons.contains(&json!("outcome_ingestion_review_must_not_rewrite_verdict")));
    assert!(failure_reasons.contains(&json!("outcome_ingestion_review_must_not_persist_record")));
    assert!(failure_reasons.contains(&json!(
        "outcome_ingestion_review_verification_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!("outcome_ingestion_review_patch_scope_mismatch")));
    assert_runtime_executor_outcome_ingestion_review_preflight_read_only(&ingestion_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_outcome_ingestion_review_preflight_requires_verification_input(
) {
    let application_preflight =
        ready_runtime_executor_patch_runtime_application_evidence_preflight();
    let ingestion_preflight =
        build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(&json!({
            "post_apply_verification_preflight": application_preflight,
            "outcome_ingestion_review_decision": explicit_outcome_ingestion_review_decision()
        }));

    assert_eq!(
        ingestion_preflight["input_kind"],
        "post_apply_verification_preflight_with_outcome_ingestion_review_decision_wrapper"
    );
    assert_eq!(
        ingestion_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        ingestion_preflight["outcome_ingestion_review_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        ingestion_preflight["reason"],
        "runtime_executor_post_apply_verification_preflight_required"
    );
    assert_eq!(
        ingestion_preflight["source_post_apply_verification_preflight"],
        Value::Null
    );
    assert_runtime_executor_outcome_ingestion_review_preflight_read_only(&ingestion_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight_blocks_without_decision(
) {
    let review_preflight = ready_runtime_executor_outcome_ingestion_review_preflight();
    let gate_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(
            &review_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(
            &gate_preflight,
        );

    assert_eq!(
        gate_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        gate_preflight["input_kind"],
        "runtime_executor_outcome_ingestion_review_preflight"
    );
    assert_eq!(
        gate_preflight["source_outcome_ingestion_review_preflight_verdict"],
        "ready_for_durable_ingestion_gate"
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate_decision_schema"],
        Value::Null
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate_preflight_verdict"],
        "blocked"
    );
    assert_eq!(gate_preflight["status"], "blocked");
    assert_eq!(
        gate_preflight["reason"],
        "explicit_durable_outcome_ingestion_gate_decision_required"
    );
    assert_runtime_executor_durable_outcome_ingestion_gate_preflight_read_only(&gate_preflight);

    assert!(markdown.contains("- durable_outcome_ingestion_gate_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_durable_outcome_ingestion_execution: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight_accepts_explicit_decision(
) {
    let review_preflight = ready_runtime_executor_outcome_ingestion_review_preflight();
    let gate_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(
            &json!({
                "outcome_ingestion_review_preflight": review_preflight,
                "durable_outcome_ingestion_gate_decision": explicit_durable_outcome_ingestion_gate_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(
            &gate_preflight,
        );

    assert_eq!(
        gate_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_DECISION_SCHEMA
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate_preflight_verdict"],
        "ready_for_durable_outcome_ingestion_execution"
    );
    assert_eq!(gate_preflight["status"], "ready");
    assert_eq!(
        gate_preflight["reason"],
        "durable_outcome_ingestion_gate_preflight_ready_for_execution"
    );
    assert_eq!(gate_preflight["failure_reasons"], json!([]));
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate"]["gate_id"],
        "durable_outcome_ingestion_gate_arrival_bath_move_002"
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate"]["review_id"],
        "outcome_ingestion_review_arrival_bath_move_002"
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate"]["decision"],
        "approved_for_durable_ingestion_execution"
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate"]
            ["ready_for_durable_outcome_ingestion_execution"],
        true
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate"]["durable_ingestion_execution_allowed"],
        false
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        gate_preflight["next_allowed_gate"],
        "durable_outcome_ingestion_execution"
    );
    assert_runtime_executor_durable_outcome_ingestion_gate_preflight_read_only(&gate_preflight);

    assert!(markdown.contains(
        "- durable_outcome_ingestion_gate_preflight_verdict: `ready_for_durable_outcome_ingestion_execution`"
    ));
    assert!(markdown.contains("- decision: `approved_for_durable_ingestion_execution`"));
    assert!(markdown.contains("- durable_ingestion_execution_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight_blocks_bad_decision(
) {
    let review_preflight = ready_runtime_executor_outcome_ingestion_review_preflight();
    let mut decision = explicit_durable_outcome_ingestion_gate_decision();
    decision["gate_kind"] = json!("operator_note");
    decision["decision"] = json!("approved_and_write_now");
    decision["source_outcome_ingestion_review_scope"]["review_id"] =
        json!("outcome_ingestion_review_other");
    decision["source_outcome_ingestion_review_scope"]["patch_id"] = json!("patch_other");
    decision["source_world_verdict"] = json!("verified");
    decision["reviewed_ingestion_review_decision"] = json!("blocked");
    decision["outcome_payload_complete"] = json!(false);
    decision["idempotency_key"] = Value::Null;
    decision["durable_ingestion_execution_allowed"] = json!(true);
    decision["world_verdict_rewrite_allowed"] = json!(true);
    decision["outcome_record_persisted"] = json!(true);

    let gate_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(
            &json!({
                "outcome_ingestion_review_preflight": review_preflight,
                "durable_outcome_ingestion_gate_decision": decision
            }),
        );

    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = gate_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("durable_outcome_ingestion_gate_kind_required")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_must_review_approved_review"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_requires_complete_payload"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_idempotency_key_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_must_not_allow_execution"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_must_not_persist_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_review_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_gate_patch_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_ingestion_gate_preflight_read_only(&gate_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight_requires_review_input(
) {
    let verification_preflight = ready_runtime_executor_post_apply_verification_preflight();
    let gate_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(
            &json!({
                "outcome_ingestion_review_preflight": verification_preflight,
                "durable_outcome_ingestion_gate_decision": explicit_durable_outcome_ingestion_gate_decision()
            }),
        );

    assert_eq!(
        gate_preflight["input_kind"],
        "outcome_ingestion_review_preflight_with_durable_outcome_ingestion_gate_decision_wrapper"
    );
    assert_eq!(
        gate_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        gate_preflight["durable_outcome_ingestion_gate_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        gate_preflight["reason"],
        "runtime_executor_outcome_ingestion_review_preflight_required"
    );
    assert_eq!(
        gate_preflight["source_outcome_ingestion_review_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_ingestion_gate_preflight_read_only(&gate_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight_blocks_without_decision(
) {
    let gate_preflight = ready_runtime_executor_durable_outcome_ingestion_gate_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
            &gate_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
            &execution_preflight,
        );

    assert_eq!(
        execution_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["input_kind"],
        "runtime_executor_durable_outcome_ingestion_gate_preflight"
    );
    assert_eq!(
        execution_preflight["source_durable_outcome_ingestion_gate_preflight_verdict"],
        "ready_for_durable_outcome_ingestion_execution"
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution_decision_schema"],
        Value::Null
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(execution_preflight["status"], "blocked");
    assert_eq!(
        execution_preflight["reason"],
        "explicit_durable_outcome_ingestion_execution_decision_required"
    );
    assert_runtime_executor_durable_outcome_ingestion_execution_preflight_read_only(
        &execution_preflight,
    );

    assert!(markdown.contains("- durable_outcome_ingestion_execution_preflight_verdict: `blocked`"));
    assert!(
        markdown.contains("- ready_for_durable_outcome_ingestion_write_implementation: `false`")
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight_accepts_explicit_decision(
) {
    let gate_preflight = ready_runtime_executor_durable_outcome_ingestion_gate_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
            &json!({
                "durable_outcome_ingestion_gate_preflight": gate_preflight,
                "durable_outcome_ingestion_execution_decision": explicit_durable_outcome_ingestion_execution_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
            &execution_preflight,
        );

    assert_eq!(
        execution_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution_preflight_verdict"],
        "ready_for_durable_outcome_ingestion_write_implementation"
    );
    assert_eq!(execution_preflight["status"], "ready");
    assert_eq!(
        execution_preflight["reason"],
        "durable_outcome_ingestion_execution_preflight_ready_for_write_implementation"
    );
    assert_eq!(execution_preflight["failure_reasons"], json!([]));
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution"]["execution_id"],
        "durable_outcome_ingestion_execution_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution"]["gate_id"],
        "durable_outcome_ingestion_gate_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution"]["decision"],
        "approved_for_durable_outcome_ingestion_write_implementation"
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution"]
            ["ready_for_durable_outcome_ingestion_write_implementation"],
        true
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution"]
            ["durable_write_implementation_allowed"],
        false
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution"]
            ["outcome_record_persisted_by_this_tool"],
        false
    );
    assert_eq!(
        execution_preflight["next_allowed_gate"],
        "durable_outcome_ingestion_write_implementation"
    );
    assert_runtime_executor_durable_outcome_ingestion_execution_preflight_read_only(
        &execution_preflight,
    );

    assert!(markdown.contains(
        "- durable_outcome_ingestion_execution_preflight_verdict: `ready_for_durable_outcome_ingestion_write_implementation`"
    ));
    assert!(markdown
        .contains("- decision: `approved_for_durable_outcome_ingestion_write_implementation`"));
    assert!(markdown.contains("- durable_write_implementation_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight_blocks_bad_decision(
) {
    let gate_preflight = ready_runtime_executor_durable_outcome_ingestion_gate_preflight();
    let mut decision = explicit_durable_outcome_ingestion_execution_decision();
    decision["execution_kind"] = json!("operator_note");
    decision["decision"] = json!("approved_and_write_now");
    decision["source_durable_outcome_ingestion_gate_scope"]["gate_id"] =
        json!("durable_outcome_ingestion_gate_other");
    decision["source_durable_outcome_ingestion_gate_scope"]["patch_id"] = json!("patch_other");
    decision["source_world_verdict"] = json!("verified");
    decision["reviewed_gate_decision"] = json!("blocked");
    decision["outcome_payload_complete"] = json!(false);
    decision["write_plan_complete"] = json!(false);
    decision["outcome_payload_digest"] = Value::Null;
    decision["write_plan_id"] = Value::Null;
    decision["durable_write_implementation_allowed"] = json!(true);
    decision["durable_outcome_ingestion_performed"] = json!(true);
    decision["world_verdict_rewrite_allowed"] = json!(true);
    decision["outcome_record_persisted"] = json!(true);

    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
            &json!({
                "durable_outcome_ingestion_gate_preflight": gate_preflight,
                "durable_outcome_ingestion_execution_decision": decision
            }),
        );

    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = execution_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("durable_outcome_ingestion_execution_kind_required")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_must_review_approved_gate"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_requires_complete_payload"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_requires_complete_write_plan"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_payload_digest_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_write_plan_id_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_must_not_allow_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_must_not_ingest"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_must_not_persist_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_gate_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_ingestion_execution_patch_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_ingestion_execution_preflight_read_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight_requires_gate_input(
) {
    let review_preflight = ready_runtime_executor_outcome_ingestion_review_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
            &json!({
                "durable_outcome_ingestion_gate_preflight": review_preflight,
                "durable_outcome_ingestion_execution_decision": explicit_durable_outcome_ingestion_execution_decision()
            }),
        );

    assert_eq!(
        execution_preflight["input_kind"],
        "durable_outcome_ingestion_gate_preflight_with_durable_outcome_ingestion_execution_decision_wrapper"
    );
    assert_eq!(
        execution_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["durable_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        execution_preflight["reason"],
        "runtime_executor_durable_outcome_ingestion_gate_preflight_required"
    );
    assert_eq!(
        execution_preflight["source_durable_outcome_ingestion_gate_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_ingestion_execution_preflight_read_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight_blocks_without_decision(
) {
    let execution_preflight =
        ready_runtime_executor_durable_outcome_ingestion_execution_preflight();
    let write_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
            &execution_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
            &write_preflight,
        );

    assert_eq!(
        write_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        write_preflight["input_kind"],
        "runtime_executor_durable_outcome_ingestion_execution_preflight"
    );
    assert_eq!(
        write_preflight["source_durable_outcome_ingestion_execution_preflight_verdict"],
        "ready_for_durable_outcome_ingestion_write_implementation"
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation_decision_schema"],
        Value::Null
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation_preflight_verdict"],
        "blocked"
    );
    assert_eq!(write_preflight["status"], "blocked");
    assert_eq!(
        write_preflight["reason"],
        "explicit_durable_outcome_write_implementation_decision_required"
    );
    assert_runtime_executor_durable_outcome_write_implementation_preflight_read_only(
        &write_preflight,
    );

    assert!(
        markdown.contains("- durable_outcome_write_implementation_preflight_verdict: `blocked`")
    );
    assert!(markdown.contains("- ready_for_durable_outcome_record_write: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight_accepts_explicit_decision(
) {
    let execution_preflight =
        ready_runtime_executor_durable_outcome_ingestion_execution_preflight();
    let write_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
            &json!({
                "durable_outcome_ingestion_execution_preflight": execution_preflight,
                "durable_outcome_write_implementation_decision": explicit_durable_outcome_write_implementation_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
            &write_preflight,
        );

    assert_eq!(
        write_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_DECISION_SCHEMA
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation_preflight_verdict"],
        "ready_for_durable_outcome_record_write"
    );
    assert_eq!(write_preflight["status"], "ready");
    assert_eq!(
        write_preflight["reason"],
        "durable_outcome_write_implementation_preflight_ready_for_record_write"
    );
    assert_eq!(write_preflight["failure_reasons"], json!([]));
    assert_eq!(
        write_preflight["durable_outcome_write_implementation"]["write_implementation_id"],
        "durable_outcome_write_impl_arrival_bath_move_002"
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation"]["execution_id"],
        "durable_outcome_ingestion_execution_arrival_bath_move_002"
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation"]["decision"],
        "approved_for_durable_outcome_record_write"
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation"]
            ["ready_for_durable_outcome_record_write"],
        true
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation"]["durable_record_write_allowed"],
        false
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        write_preflight["next_allowed_gate"],
        "durable_outcome_record_write"
    );
    assert_runtime_executor_durable_outcome_write_implementation_preflight_read_only(
        &write_preflight,
    );

    assert!(markdown.contains(
        "- durable_outcome_write_implementation_preflight_verdict: `ready_for_durable_outcome_record_write`"
    ));
    assert!(markdown.contains("- decision: `approved_for_durable_outcome_record_write`"));
    assert!(markdown.contains("- durable_record_write_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight_blocks_bad_decision(
) {
    let execution_preflight =
        ready_runtime_executor_durable_outcome_ingestion_execution_preflight();
    let mut decision = explicit_durable_outcome_write_implementation_decision();
    decision["write_implementation_kind"] = json!("operator_note");
    decision["decision"] = json!("approved_and_write_now");
    decision["source_durable_outcome_ingestion_execution_scope"]["execution_id"] =
        json!("durable_outcome_ingestion_execution_other");
    decision["source_durable_outcome_ingestion_execution_scope"]["write_plan_id"] =
        json!("durable_outcome_write_plan_other");
    decision["source_world_verdict"] = json!("verified");
    decision["reviewed_execution_decision"] = json!("blocked");
    decision["outcome_record_write_plan_complete"] = json!(false);
    decision["write_idempotency_confirmed"] = json!(false);
    decision["write_destination"] = Value::Null;
    decision["durable_record_write_allowed"] = json!(true);
    decision["durable_outcome_record_written"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["world_verdict_rewrite_allowed"] = json!(true);

    let write_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
            &json!({
                "durable_outcome_ingestion_execution_preflight": execution_preflight,
                "durable_outcome_write_implementation_decision": decision
            }),
        );

    assert_eq!(
        write_preflight["durable_outcome_write_implementation_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = write_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("durable_outcome_write_implementation_kind_required")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_must_review_approved_execution"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_requires_complete_write_plan"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_requires_idempotency_confirmation"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_destination_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_must_not_allow_record_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_must_not_write_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_execution_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_write_implementation_write_plan_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_write_implementation_preflight_read_only(
        &write_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight_requires_execution_input(
) {
    let gate_preflight = ready_runtime_executor_durable_outcome_ingestion_gate_preflight();
    let write_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
            &json!({
                "durable_outcome_ingestion_execution_preflight": gate_preflight,
                "durable_outcome_write_implementation_decision": explicit_durable_outcome_write_implementation_decision()
            }),
        );

    assert_eq!(
        write_preflight["input_kind"],
        "durable_outcome_ingestion_execution_preflight_with_durable_outcome_write_implementation_decision_wrapper"
    );
    assert_eq!(
        write_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        write_preflight["durable_outcome_write_implementation_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        write_preflight["reason"],
        "runtime_executor_durable_outcome_ingestion_execution_preflight_required"
    );
    assert_eq!(
        write_preflight["source_durable_outcome_ingestion_execution_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_write_implementation_preflight_read_only(
        &write_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_preflight_blocks_without_decision(
) {
    let write_preflight = ready_runtime_executor_durable_outcome_write_implementation_preflight();
    let record_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(
            &write_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(
            &record_preflight,
        );

    assert_eq!(
        record_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        record_preflight["input_kind"],
        "runtime_executor_durable_outcome_write_implementation_preflight"
    );
    assert_eq!(
        record_preflight["source_durable_outcome_write_implementation_preflight_verdict"],
        "ready_for_durable_outcome_record_write"
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write_decision_schema"],
        Value::Null
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write_preflight_verdict"],
        "blocked"
    );
    assert_eq!(record_preflight["status"], "blocked");
    assert_eq!(
        record_preflight["reason"],
        "explicit_durable_outcome_record_write_decision_required"
    );
    assert_runtime_executor_durable_outcome_record_write_preflight_read_only(&record_preflight);

    assert!(markdown.contains("- durable_outcome_record_write_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_durable_outcome_record_write_execution: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_preflight_accepts_explicit_decision(
) {
    let write_preflight = ready_runtime_executor_durable_outcome_write_implementation_preflight();
    let record_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(
            &json!({
                "durable_outcome_write_implementation_preflight": write_preflight,
                "durable_outcome_record_write_decision": explicit_durable_outcome_record_write_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(
            &record_preflight,
        );

    assert_eq!(
        record_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_DECISION_SCHEMA
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write_preflight_verdict"],
        "ready_for_durable_outcome_record_write_execution"
    );
    assert_eq!(record_preflight["status"], "ready");
    assert_eq!(
        record_preflight["reason"],
        "durable_outcome_record_write_preflight_ready_for_write_execution"
    );
    assert_eq!(record_preflight["failure_reasons"], json!([]));
    assert_eq!(
        record_preflight["durable_outcome_record_write"]["record_write_id"],
        "durable_outcome_record_write_arrival_bath_move_002"
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write"]["write_implementation_id"],
        "durable_outcome_write_impl_arrival_bath_move_002"
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write"]["decision"],
        "approved_for_durable_outcome_record_write_execution"
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write"]
            ["ready_for_durable_outcome_record_write_execution"],
        true
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write"]["durable_record_write_execution_allowed"],
        false
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        record_preflight["next_allowed_gate"],
        "durable_outcome_record_write_execution"
    );
    assert_runtime_executor_durable_outcome_record_write_preflight_read_only(&record_preflight);

    assert!(markdown.contains(
        "- durable_outcome_record_write_preflight_verdict: `ready_for_durable_outcome_record_write_execution`"
    ));
    assert!(markdown.contains("- decision: `approved_for_durable_outcome_record_write_execution`"));
    assert!(markdown.contains("- durable_record_write_execution_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_preflight_blocks_bad_decision(
) {
    let write_preflight = ready_runtime_executor_durable_outcome_write_implementation_preflight();
    let mut decision = explicit_durable_outcome_record_write_decision();
    decision["record_write_kind"] = json!("operator_note");
    decision["decision"] = json!("approved_and_write_now");
    decision["source_durable_outcome_write_implementation_scope"]["write_implementation_id"] =
        json!("durable_outcome_write_impl_other");
    decision["source_durable_outcome_write_implementation_scope"]["write_plan_id"] =
        json!("durable_outcome_write_plan_other");
    decision["source_world_verdict"] = json!("verified");
    decision["reviewed_write_implementation_decision"] = json!("blocked");
    decision["outcome_record_payload_complete"] = json!(false);
    decision["outcome_record_serialization_verified"] = json!(false);
    decision["write_idempotency_confirmed"] = json!(false);
    decision["write_destination"] = Value::Null;
    decision["outcome_record_key"] = Value::Null;
    decision["outcome_record_digest"] = Value::Null;
    decision["durable_record_write_execution_allowed"] = json!(true);
    decision["durable_outcome_record_written"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["world_verdict_rewrite_allowed"] = json!(true);

    let record_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(
            &json!({
                "durable_outcome_write_implementation_preflight": write_preflight,
                "durable_outcome_record_write_decision": decision
            }),
        );

    assert_eq!(
        record_preflight["durable_outcome_record_write_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = record_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("durable_outcome_record_write_kind_required")));
    assert!(failure_reasons.contains(&json!("durable_outcome_record_write_decision_not_approved")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_must_review_approved_write_implementation"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_requires_complete_payload"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_requires_serialization_verification"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_requires_idempotency_confirmation"
    )));
    assert!(failure_reasons.contains(&json!("durable_outcome_record_write_destination_required")));
    assert!(failure_reasons.contains(&json!("durable_outcome_record_write_key_required")));
    assert!(failure_reasons.contains(&json!("durable_outcome_record_write_digest_required")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_must_not_allow_write_execution"
    )));
    assert!(failure_reasons.contains(&json!("durable_outcome_record_write_must_not_write_record")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_implementation_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_write_plan_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_record_write_preflight_read_only(&record_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_preflight_requires_write_implementation_input(
) {
    let execution_preflight =
        ready_runtime_executor_durable_outcome_ingestion_execution_preflight();
    let record_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(
            &json!({
                "durable_outcome_write_implementation_preflight": execution_preflight,
                "durable_outcome_record_write_decision": explicit_durable_outcome_record_write_decision()
            }),
        );

    assert_eq!(
        record_preflight["input_kind"],
        "durable_outcome_write_implementation_preflight_with_durable_outcome_record_write_decision_wrapper"
    );
    assert_eq!(
        record_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        record_preflight["durable_outcome_record_write_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        record_preflight["reason"],
        "runtime_executor_durable_outcome_write_implementation_preflight_required"
    );
    assert_eq!(
        record_preflight["source_durable_outcome_write_implementation_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_record_write_preflight_read_only(&record_preflight);
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight_blocks_without_decision(
) {
    let record_preflight = ready_runtime_executor_durable_outcome_record_write_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
            &record_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
            &execution_preflight,
        );

    assert_eq!(
        execution_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["input_kind"],
        "runtime_executor_durable_outcome_record_write_preflight"
    );
    assert_eq!(
        execution_preflight["source_durable_outcome_record_write_preflight_verdict"],
        "ready_for_durable_outcome_record_write_execution"
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution_decision_schema"],
        Value::Null
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(execution_preflight["status"], "blocked");
    assert_eq!(
        execution_preflight["reason"],
        "explicit_durable_outcome_record_write_execution_decision_required"
    );
    assert_runtime_executor_durable_outcome_record_write_execution_preflight_read_only(
        &execution_preflight,
    );

    assert!(
        markdown.contains("- durable_outcome_record_write_execution_preflight_verdict: `blocked`")
    );
    assert!(markdown.contains("- ready_for_durable_outcome_record_persistence: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight_accepts_explicit_decision(
) {
    let record_preflight = ready_runtime_executor_durable_outcome_record_write_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
            &json!({
                "durable_outcome_record_write_preflight": record_preflight,
                "durable_outcome_record_write_execution_decision": explicit_durable_outcome_record_write_execution_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
            &execution_preflight,
        );

    assert_eq!(
        execution_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_DECISION_SCHEMA
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution_preflight_verdict"],
        "ready_for_durable_outcome_record_persistence"
    );
    assert_eq!(execution_preflight["status"], "ready");
    assert_eq!(
        execution_preflight["reason"],
        "durable_outcome_record_write_execution_preflight_ready_for_persistence"
    );
    assert_eq!(execution_preflight["failure_reasons"], json!([]));
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution"]["record_write_execution_id"],
        "durable_outcome_record_write_execution_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution"]["record_write_id"],
        "durable_outcome_record_write_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution"]["decision"],
        "approved_for_durable_outcome_record_persistence"
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution"]
            ["ready_for_durable_outcome_record_persistence"],
        true
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution"]
            ["durable_record_persistence_allowed"],
        false
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        execution_preflight["next_allowed_gate"],
        "durable_outcome_record_persistence"
    );
    assert_runtime_executor_durable_outcome_record_write_execution_preflight_read_only(
        &execution_preflight,
    );

    assert!(markdown.contains(
        "- durable_outcome_record_write_execution_preflight_verdict: `ready_for_durable_outcome_record_persistence`"
    ));
    assert!(markdown.contains("- decision: `approved_for_durable_outcome_record_persistence`"));
    assert!(markdown.contains("- durable_record_persistence_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight_blocks_bad_decision(
) {
    let record_preflight = ready_runtime_executor_durable_outcome_record_write_preflight();
    let mut decision = explicit_durable_outcome_record_write_execution_decision();
    decision["record_write_execution_kind"] = json!("operator_note");
    decision["decision"] = json!("approved_and_persist_now");
    decision["source_durable_outcome_record_write_scope"]["record_write_id"] =
        json!("durable_outcome_record_write_other");
    decision["source_durable_outcome_record_write_scope"]["outcome_record_digest"] =
        json!("sha256:other");
    decision["source_world_verdict"] = json!("verified");
    decision["reviewed_record_write_decision"] = json!("blocked");
    decision["write_destination_verified"] = json!(false);
    decision["outcome_record_digest_verified"] = json!(false);
    decision["idempotent_upsert_confirmed"] = json!(false);
    decision["store_transaction_plan_complete"] = json!(false);
    decision["write_destination"] = Value::Null;
    decision["outcome_record_key"] = Value::Null;
    decision["outcome_record_digest"] = Value::Null;
    decision["durable_record_persistence_allowed"] = json!(true);
    decision["durable_outcome_record_written"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["world_verdict_rewrite_allowed"] = json!(true);

    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
            &json!({
                "durable_outcome_record_write_preflight": record_preflight,
                "durable_outcome_record_write_execution_decision": decision
            }),
        );

    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = execution_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_kind_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_must_review_approved_record_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_requires_destination_verification"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_requires_digest_verification"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_requires_idempotent_upsert"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_requires_transaction_plan"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_destination_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_key_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_digest_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_must_not_allow_persistence"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_must_not_write_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_record_write_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_execution_digest_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_record_write_execution_preflight_read_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight_requires_record_write_input(
) {
    let write_preflight = ready_runtime_executor_durable_outcome_write_implementation_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
            &json!({
                "durable_outcome_record_write_preflight": write_preflight,
                "durable_outcome_record_write_execution_decision": explicit_durable_outcome_record_write_execution_decision()
            }),
        );

    assert_eq!(
        execution_preflight["input_kind"],
        "durable_outcome_record_write_preflight_with_durable_outcome_record_write_execution_decision_wrapper"
    );
    assert_eq!(
        execution_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["durable_outcome_record_write_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        execution_preflight["reason"],
        "runtime_executor_durable_outcome_record_write_preflight_required"
    );
    assert_eq!(
        execution_preflight["source_durable_outcome_record_write_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_record_write_execution_preflight_read_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight_blocks_without_decision(
) {
    let execution_preflight =
        ready_runtime_executor_durable_outcome_record_write_execution_preflight();
    let persistence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
            &execution_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
            &persistence_preflight,
        );

    assert_eq!(
        persistence_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        persistence_preflight["input_kind"],
        "runtime_executor_durable_outcome_record_write_execution_preflight"
    );
    assert_eq!(
        persistence_preflight["source_durable_outcome_record_write_execution_preflight_verdict"],
        "ready_for_durable_outcome_record_persistence"
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence_decision_schema"],
        Value::Null
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence_preflight_verdict"],
        "blocked"
    );
    assert_eq!(persistence_preflight["status"], "blocked");
    assert_eq!(
        persistence_preflight["reason"],
        "explicit_durable_outcome_record_persistence_decision_required"
    );
    assert_runtime_executor_durable_outcome_record_persistence_preflight_read_only(
        &persistence_preflight,
    );

    assert!(markdown.contains("- durable_outcome_record_persistence_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_durable_outcome_record_store_write: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight_accepts_explicit_decision(
) {
    let execution_preflight =
        ready_runtime_executor_durable_outcome_record_write_execution_preflight();
    let persistence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
            &json!({
                "durable_outcome_record_write_execution_preflight": execution_preflight,
                "durable_outcome_record_persistence_decision": explicit_durable_outcome_record_persistence_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
            &persistence_preflight,
        );

    assert_eq!(
        persistence_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_DECISION_SCHEMA
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence_preflight_verdict"],
        "ready_for_durable_outcome_record_store_write"
    );
    assert_eq!(persistence_preflight["status"], "ready");
    assert_eq!(
        persistence_preflight["reason"],
        "durable_outcome_record_persistence_preflight_ready_for_store_write"
    );
    assert_eq!(persistence_preflight["failure_reasons"], json!([]));
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence"]["persistence_id"],
        "durable_outcome_record_persistence_arrival_bath_move_002"
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence"]["record_write_execution_id"],
        "durable_outcome_record_write_execution_arrival_bath_move_002"
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence"]["decision"],
        "approved_for_durable_outcome_record_store_write"
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence"]
            ["ready_for_durable_outcome_record_store_write"],
        true
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence"]["durable_store_write_allowed"],
        false
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        persistence_preflight["next_allowed_gate"],
        "durable_outcome_record_store_write"
    );
    assert_runtime_executor_durable_outcome_record_persistence_preflight_read_only(
        &persistence_preflight,
    );

    assert!(markdown.contains(
        "- durable_outcome_record_persistence_preflight_verdict: `ready_for_durable_outcome_record_store_write`"
    ));
    assert!(markdown.contains("- decision: `approved_for_durable_outcome_record_store_write`"));
    assert!(markdown.contains("- durable_store_write_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight_blocks_bad_decision(
) {
    let execution_preflight =
        ready_runtime_executor_durable_outcome_record_write_execution_preflight();
    let mut decision = explicit_durable_outcome_record_persistence_decision();
    decision["persistence_kind"] = json!("operator_note");
    decision["decision"] = json!("approved_and_write_now");
    decision["source_durable_outcome_record_write_execution_scope"]["record_write_execution_id"] =
        json!("durable_outcome_record_write_execution_other");
    decision["source_durable_outcome_record_write_execution_scope"]["outcome_record_digest"] =
        json!("sha256:other");
    decision["source_world_verdict"] = json!("verified");
    decision["reviewed_record_write_execution_decision"] = json!("blocked");
    decision["persistence_target_verified"] = json!(false);
    decision["outcome_record_digest_verified"] = json!(false);
    decision["idempotent_upsert_confirmed"] = json!(false);
    decision["store_transaction_plan_complete"] = json!(false);
    decision["write_destination"] = Value::Null;
    decision["outcome_record_key"] = Value::Null;
    decision["outcome_record_digest"] = Value::Null;
    decision["durable_store_write_allowed"] = json!(true);
    decision["durable_outcome_record_written"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["world_verdict_rewrite_allowed"] = json!(true);

    let persistence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
            &json!({
                "durable_outcome_record_write_execution_preflight": execution_preflight,
                "durable_outcome_record_persistence_decision": decision
            }),
        );

    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = persistence_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("durable_outcome_record_persistence_kind_required")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_must_review_approved_record_write_execution"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_requires_target_verification"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_requires_digest_verification"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_requires_idempotent_upsert"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_requires_transaction_plan"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_destination_required"
    )));
    assert!(failure_reasons.contains(&json!("durable_outcome_record_persistence_key_required")));
    assert!(failure_reasons.contains(&json!("durable_outcome_record_persistence_digest_required")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_must_not_allow_store_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_must_not_write_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_execution_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_persistence_digest_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_record_persistence_preflight_read_only(
        &persistence_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight_requires_execution_input(
) {
    let record_preflight = ready_runtime_executor_durable_outcome_record_write_preflight();
    let persistence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
            &json!({
                "durable_outcome_record_write_execution_preflight": record_preflight,
                "durable_outcome_record_persistence_decision": explicit_durable_outcome_record_persistence_decision()
            }),
        );

    assert_eq!(
        persistence_preflight["input_kind"],
        "durable_outcome_record_write_execution_preflight_with_durable_outcome_record_persistence_decision_wrapper"
    );
    assert_eq!(
        persistence_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        persistence_preflight["durable_outcome_record_persistence_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        persistence_preflight["reason"],
        "runtime_executor_durable_outcome_record_write_execution_preflight_required"
    );
    assert_eq!(
        persistence_preflight["source_durable_outcome_record_write_execution_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_record_persistence_preflight_read_only(
        &persistence_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight_blocks_without_decision(
) {
    let persistence_preflight =
        ready_runtime_executor_durable_outcome_record_persistence_preflight();
    let store_write_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
            &persistence_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
            &store_write_preflight,
        );

    assert_eq!(
        store_write_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        store_write_preflight["input_kind"],
        "runtime_executor_durable_outcome_record_persistence_preflight"
    );
    assert_eq!(
        store_write_preflight["source_durable_outcome_record_persistence_preflight_verdict"],
        "ready_for_durable_outcome_record_store_write"
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution_decision_schema"],
        Value::Null
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(store_write_preflight["status"], "blocked");
    assert_eq!(
        store_write_preflight["reason"],
        "explicit_durable_outcome_record_store_write_execution_decision_required"
    );
    assert_runtime_executor_durable_outcome_record_store_write_execution_preflight_read_only(
        &store_write_preflight,
    );

    assert!(markdown
        .contains("- durable_outcome_record_store_write_execution_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_durable_outcome_record_write_evidence: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight_accepts_explicit_decision(
) {
    let persistence_preflight =
        ready_runtime_executor_durable_outcome_record_persistence_preflight();
    let store_write_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
            &json!({
                "durable_outcome_record_persistence_preflight": persistence_preflight,
                "durable_outcome_record_store_write_execution_decision": explicit_durable_outcome_record_store_write_execution_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
            &store_write_preflight,
        );

    assert_eq!(
        store_write_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_DECISION_SCHEMA
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution_preflight_verdict"],
        "ready_for_durable_outcome_record_write_evidence"
    );
    assert_eq!(store_write_preflight["status"], "ready");
    assert_eq!(
        store_write_preflight["reason"],
        "durable_outcome_record_store_write_execution_preflight_ready_for_write_evidence"
    );
    assert_eq!(store_write_preflight["failure_reasons"], json!([]));
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution"]
            ["store_write_execution_id"],
        "durable_outcome_record_store_write_execution_arrival_bath_move_002"
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution"]["persistence_id"],
        "durable_outcome_record_persistence_arrival_bath_move_002"
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution"]["decision"],
        "approved_for_durable_outcome_record_write_evidence"
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution"]
            ["ready_for_durable_outcome_record_write_evidence"],
        true
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution"]
            ["durable_store_write_execution_allowed"],
        false
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        store_write_preflight["next_allowed_gate"],
        "durable_outcome_record_write_evidence"
    );
    assert_runtime_executor_durable_outcome_record_store_write_execution_preflight_read_only(
        &store_write_preflight,
    );

    assert!(markdown.contains(
        "- durable_outcome_record_store_write_execution_preflight_verdict: `ready_for_durable_outcome_record_write_evidence`"
    ));
    assert!(markdown.contains("- decision: `approved_for_durable_outcome_record_write_evidence`"));
    assert!(markdown.contains("- durable_store_write_execution_allowed: `false`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight_blocks_bad_decision(
) {
    let persistence_preflight =
        ready_runtime_executor_durable_outcome_record_persistence_preflight();
    let mut decision = explicit_durable_outcome_record_store_write_execution_decision();
    decision["store_write_execution_kind"] = json!("operator_note");
    decision["decision"] = json!("approved_and_write_now");
    decision["source_durable_outcome_record_persistence_scope"]["persistence_id"] =
        json!("durable_outcome_record_persistence_other");
    decision["source_durable_outcome_record_persistence_scope"]["outcome_record_digest"] =
        json!("sha256:other");
    decision["source_world_verdict"] = json!("verified");
    decision["reviewed_persistence_decision"] = json!("blocked");
    decision["persistence_target_verified"] = json!(false);
    decision["outcome_record_digest_verified"] = json!(false);
    decision["idempotent_upsert_confirmed"] = json!(false);
    decision["store_transaction_plan_complete"] = json!(false);
    decision["write_destination"] = Value::Null;
    decision["outcome_record_key"] = Value::Null;
    decision["outcome_record_digest"] = Value::Null;
    decision["durable_store_write_execution_allowed"] = json!(true);
    decision["durable_outcome_record_written"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["world_verdict_rewrite_allowed"] = json!(true);

    let store_write_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
            &json!({
                "durable_outcome_record_persistence_preflight": persistence_preflight,
                "durable_outcome_record_store_write_execution_decision": decision
            }),
        );

    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = store_write_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_kind_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_must_review_approved_persistence"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_requires_target_verification"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_requires_digest_verification"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_requires_idempotent_upsert"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_requires_transaction_plan"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_destination_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_key_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_digest_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_must_not_allow_execution"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_must_not_write_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_persistence_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_store_write_execution_digest_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_record_store_write_execution_preflight_read_only(
        &store_write_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight_requires_persistence_input(
) {
    let execution_preflight =
        ready_runtime_executor_durable_outcome_record_write_execution_preflight();
    let store_write_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
            &json!({
                "durable_outcome_record_persistence_preflight": execution_preflight,
                "durable_outcome_record_store_write_execution_decision": explicit_durable_outcome_record_store_write_execution_decision()
            }),
        );

    assert_eq!(
        store_write_preflight["input_kind"],
        "durable_outcome_record_persistence_preflight_with_durable_outcome_record_store_write_execution_decision_wrapper"
    );
    assert_eq!(
        store_write_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        store_write_preflight["durable_outcome_record_store_write_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        store_write_preflight["reason"],
        "runtime_executor_durable_outcome_record_persistence_preflight_required"
    );
    assert_eq!(
        store_write_preflight["source_durable_outcome_record_persistence_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_record_store_write_execution_preflight_read_only(
        &store_write_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight_blocks_without_evidence(
) {
    let store_write_preflight =
        ready_runtime_executor_durable_outcome_record_store_write_execution_preflight();
    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
            &store_write_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
            &write_evidence_preflight,
        );

    assert_eq!(
        write_evidence_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        write_evidence_preflight["input_kind"],
        "runtime_executor_durable_outcome_record_store_write_execution_preflight"
    );
    assert_eq!(
        write_evidence_preflight
            ["source_durable_outcome_record_store_write_execution_preflight_verdict"],
        "ready_for_durable_outcome_record_write_evidence"
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence_schema"],
        Value::Null
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence_preflight_verdict"],
        "blocked"
    );
    assert_eq!(write_evidence_preflight["status"], "blocked");
    assert_eq!(
        write_evidence_preflight["reason"],
        "explicit_durable_outcome_record_write_evidence_required"
    );
    assert_runtime_executor_durable_outcome_record_write_evidence_preflight_read_only(
        &write_evidence_preflight,
    );

    assert!(
        markdown.contains("- durable_outcome_record_write_evidence_preflight_verdict: `blocked`")
    );
    assert!(markdown.contains("- ready_for_durable_outcome_record_write_evidence_review: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight_accepts_explicit_evidence(
) {
    let store_write_preflight =
        ready_runtime_executor_durable_outcome_record_store_write_execution_preflight();
    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
            &json!({
                "durable_outcome_record_store_write_execution_preflight": store_write_preflight,
                "durable_outcome_record_write_evidence": explicit_durable_outcome_record_write_evidence()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
            &write_evidence_preflight,
        );

    assert_eq!(
        write_evidence_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_SCHEMA
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence_preflight_verdict"],
        "ready_for_durable_outcome_record_write_evidence_review"
    );
    assert_eq!(write_evidence_preflight["status"], "ready");
    assert_eq!(
        write_evidence_preflight["reason"],
        "durable_outcome_record_write_evidence_preflight_ready_for_evidence_review"
    );
    assert_eq!(write_evidence_preflight["failure_reasons"], json!([]));
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence"]["write_evidence_id"],
        "durable_outcome_record_write_evidence_arrival_bath_move_002"
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence"]
            ["store_write_execution_id"],
        "durable_outcome_record_store_write_execution_arrival_bath_move_002"
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence"]
            ["durable_outcome_record_write_observed"],
        true
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence"]
            ["ready_for_durable_outcome_record_write_evidence_review"],
        true
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        write_evidence_preflight["next_allowed_gate"],
        "durable_outcome_record_write_evidence_review"
    );
    assert_runtime_executor_durable_outcome_record_write_evidence_preflight_read_only(
        &write_evidence_preflight,
    );

    assert!(markdown.contains(
        "- durable_outcome_record_write_evidence_preflight_verdict: `ready_for_durable_outcome_record_write_evidence_review`"
    ));
    assert!(markdown.contains("- evidence_kind: `durable_outcome_record_write_evidence`"));
    assert!(markdown.contains("- durable_outcome_record_write_observed: `true`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight_blocks_bad_evidence(
) {
    let store_write_preflight =
        ready_runtime_executor_durable_outcome_record_store_write_execution_preflight();
    let mut evidence = explicit_durable_outcome_record_write_evidence();
    evidence["evidence_kind"] = json!("operator_note");
    evidence["source_durable_outcome_record_store_write_execution_scope"]
        ["store_write_execution_id"] = json!("durable_outcome_record_store_write_execution_other");
    evidence["source_durable_outcome_record_store_write_execution_scope"]
        ["outcome_record_digest"] = json!("sha256:other");
    evidence["source_world_verdict"] = json!("verified");
    evidence["reviewed_store_write_execution_decision"] = json!("blocked");
    evidence["durable_outcome_record_write_observed"] = json!(false);
    evidence["store_write_acknowledged"] = json!(false);
    evidence["record_readback_verified"] = json!(false);
    evidence["outcome_record_digest_verified"] = json!(false);
    evidence["idempotency_key_confirmed"] = json!(false);
    evidence["write_destination"] = Value::Null;
    evidence["outcome_record_key"] = Value::Null;
    evidence["outcome_record_digest"] = Value::Null;
    evidence["persisted_outcome_record_key"] = json!("other-key");
    evidence["persisted_outcome_record_digest"] = json!("sha256:other");
    evidence["durable_outcome_record_written_by_this_tool"] = json!(true);
    evidence["memory_write_allowed"] = json!(true);
    evidence["outcome_ingestion_allowed"] = json!(true);
    evidence["world_verdict_rewrite_allowed"] = json!(true);

    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
            &json!({
                "durable_outcome_record_store_write_execution_preflight": store_write_preflight,
                "durable_outcome_record_write_evidence": evidence
            }),
        );

    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = write_evidence_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_kind_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_must_review_approved_store_write_execution"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_requires_write_observed"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_requires_store_ack"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_requires_readback"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_requires_digest_verification"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_requires_idempotency"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_destination_required"
    )));
    assert!(failure_reasons.contains(&json!("durable_outcome_record_write_evidence_key_required")));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_digest_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_persisted_key_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_persisted_digest_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_must_not_write_by_this_tool"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_must_not_allow_ingestion"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_store_write_execution_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_digest_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_record_write_evidence_preflight_read_only(
        &write_evidence_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight_requires_store_write_input(
) {
    let persistence_preflight =
        ready_runtime_executor_durable_outcome_record_persistence_preflight();
    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
            &json!({
                "durable_outcome_record_store_write_execution_preflight": persistence_preflight,
                "durable_outcome_record_write_evidence": explicit_durable_outcome_record_write_evidence()
            }),
        );

    assert_eq!(
        write_evidence_preflight["input_kind"],
        "durable_outcome_record_store_write_execution_preflight_with_durable_outcome_record_write_evidence_wrapper"
    );
    assert_eq!(
        write_evidence_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        write_evidence_preflight["durable_outcome_record_write_evidence_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        write_evidence_preflight["reason"],
        "runtime_executor_durable_outcome_record_store_write_execution_preflight_required"
    );
    assert_eq!(
        write_evidence_preflight["source_durable_outcome_record_store_write_execution_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_record_write_evidence_preflight_read_only(
        &write_evidence_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight_blocks_without_review(
) {
    let write_evidence_preflight =
        ready_runtime_executor_durable_outcome_record_write_evidence_preflight();
    let review_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
            &write_evidence_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
            &review_preflight,
        );

    assert_eq!(
        review_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        review_preflight["input_kind"],
        "runtime_executor_durable_outcome_record_write_evidence_preflight"
    );
    assert_eq!(
        review_preflight["source_durable_outcome_record_write_evidence_preflight_verdict"],
        "ready_for_durable_outcome_record_write_evidence_review"
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review_decision_schema"],
        Value::Null
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review_preflight_verdict"],
        "blocked"
    );
    assert_eq!(review_preflight["status"], "blocked");
    assert_eq!(
        review_preflight["reason"],
        "explicit_durable_outcome_record_write_evidence_review_decision_required"
    );
    assert_runtime_executor_durable_outcome_record_write_evidence_review_preflight_read_only(
        &review_preflight,
    );

    assert!(markdown
        .contains("- durable_outcome_record_write_evidence_review_preflight_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_world_verdict_rewrite_gate: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight_accepts_explicit_review(
) {
    let write_evidence_preflight =
        ready_runtime_executor_durable_outcome_record_write_evidence_preflight();
    let review_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
            &json!({
                "durable_outcome_record_write_evidence_preflight": write_evidence_preflight,
                "durable_outcome_record_write_evidence_review_decision":
                    explicit_durable_outcome_record_write_evidence_review_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
            &review_preflight,
        );

    assert_eq!(
        review_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_DECISION_SCHEMA
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review_preflight_verdict"],
        "ready_for_world_verdict_rewrite_gate",
        "failure_reasons={}",
        review_preflight["failure_reasons"]
    );
    assert_eq!(review_preflight["status"], "ready");
    assert_eq!(
        review_preflight["reason"],
        "durable_outcome_record_write_evidence_review_preflight_ready_for_world_verdict_rewrite_gate"
    );
    assert_eq!(review_preflight["failure_reasons"], json!([]));
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review"]["review_decision_id"],
        "durable_outcome_record_write_evidence_review_arrival_bath_move_002"
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review"]["write_evidence_id"],
        "durable_outcome_record_write_evidence_arrival_bath_move_002"
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review"]["decision"],
        "approved_for_world_verdict_rewrite_gate"
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review"]
            ["ready_for_world_verdict_rewrite_gate"],
        true
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review"]
            ["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        review_preflight["next_allowed_gate"],
        "world_verdict_rewrite_gate"
    );
    assert_runtime_executor_durable_outcome_record_write_evidence_review_preflight_read_only(
        &review_preflight,
    );

    assert!(markdown.contains(
        "- durable_outcome_record_write_evidence_review_preflight_verdict: `ready_for_world_verdict_rewrite_gate`"
    ));
    assert!(markdown.contains("- decision: `approved_for_world_verdict_rewrite_gate`"));
    assert!(markdown.contains("- ready_for_world_verdict_rewrite_gate: `true`"));
    assert!(markdown.contains("- world_verdict_rewrite_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight_blocks_bad_review(
) {
    let write_evidence_preflight =
        ready_runtime_executor_durable_outcome_record_write_evidence_preflight();
    let mut review = explicit_durable_outcome_record_write_evidence_review_decision();
    review["review_kind"] = json!("operator_note");
    review["decision"] = json!("rewrite_now");
    review["source_durable_outcome_record_write_evidence_scope"]["write_evidence_id"] =
        json!("durable_outcome_record_write_evidence_other");
    review["source_durable_outcome_record_write_evidence_scope"]["outcome_record_digest"] =
        json!("sha256:other");
    review["source_world_verdict"] = json!("verified");
    review["reviewed_write_evidence_preflight_verdict"] = json!("blocked");
    review["durable_outcome_record_write_confirmed"] = json!(false);
    review["store_ack_confirmed"] = json!(false);
    review["record_readback_confirmed"] = json!(false);
    review["outcome_record_digest_confirmed"] = json!(false);
    review["idempotency_key_confirmed"] = json!(false);
    review["persisted_key_confirmed"] = json!(false);
    review["persisted_digest_confirmed"] = json!(false);
    review["reviewer_attestation_present"] = json!(false);
    review["outcome_ingestion_allowed"] = json!(true);
    review["memory_write_allowed"] = json!(true);
    review["world_verdict_rewrite_allowed"] = json!(true);
    review["durable_outcome_record_written_by_this_tool"] = json!(true);

    let review_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
            &json!({
                "durable_outcome_record_write_evidence_preflight": write_evidence_preflight,
                "durable_outcome_record_write_evidence_review_decision": review
            }),
        );

    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = review_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_kind_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_must_preserve_not_verified_source"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_must_review_ready_preflight"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_requires_write_confirmation"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_requires_store_ack"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_requires_readback"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_requires_digest_confirmation"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_requires_idempotency"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_requires_persisted_key"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_requires_persisted_digest"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_requires_reviewer_attestation"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_must_not_allow_ingestion"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_must_not_rewrite_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_must_not_write_by_this_tool"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_evidence_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "durable_outcome_record_write_evidence_review_digest_scope_mismatch"
    )));
    assert_runtime_executor_durable_outcome_record_write_evidence_review_preflight_read_only(
        &review_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight_requires_evidence_input(
) {
    let store_write_preflight =
        ready_runtime_executor_durable_outcome_record_store_write_execution_preflight();
    let review_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
            &json!({
                "durable_outcome_record_write_evidence_preflight": store_write_preflight,
                "durable_outcome_record_write_evidence_review_decision":
                    explicit_durable_outcome_record_write_evidence_review_decision()
            }),
        );

    assert_eq!(
        review_preflight["input_kind"],
        "durable_outcome_record_write_evidence_preflight_with_durable_outcome_record_write_evidence_review_decision_wrapper"
    );
    assert_eq!(
        review_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        review_preflight["durable_outcome_record_write_evidence_review_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        review_preflight["reason"],
        "runtime_executor_durable_outcome_record_write_evidence_preflight_required"
    );
    assert_eq!(
        review_preflight["source_durable_outcome_record_write_evidence_preflight"],
        Value::Null
    );
    assert_runtime_executor_durable_outcome_record_write_evidence_review_preflight_read_only(
        &review_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_world_verdict_rewrite_gate_blocks_without_decision() {
    let review_preflight =
        ready_runtime_executor_durable_outcome_record_write_evidence_review_preflight();
    let rewrite_gate =
        build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(&review_preflight);
    let markdown =
        render_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(&rewrite_gate);

    assert_eq!(
        rewrite_gate["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA
    );
    assert_eq!(
        rewrite_gate["input_kind"],
        "runtime_executor_durable_outcome_record_write_evidence_review_preflight"
    );
    assert_eq!(
        rewrite_gate["source_durable_outcome_record_write_evidence_review_preflight_verdict"],
        "ready_for_world_verdict_rewrite_gate"
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite_decision_schema"],
        Value::Null
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite_gate_verdict"],
        "blocked"
    );
    assert_eq!(rewrite_gate["status"], "blocked");
    assert_eq!(
        rewrite_gate["reason"],
        "explicit_world_verdict_rewrite_decision_required"
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite"]["ready_for_verified_outcome_ingestion_gate"],
        false
    );
    assert_runtime_executor_world_verdict_rewrite_gate_output_only(&rewrite_gate);

    assert!(markdown.contains("- world_verdict_rewrite_gate_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_gate: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_world_verdict_rewrite_gate_accepts_explicit_rewrite() {
    let review_preflight =
        ready_runtime_executor_durable_outcome_record_write_evidence_review_preflight();
    let rewrite_gate =
        build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(&json!({
            "durable_outcome_record_write_evidence_review_preflight": review_preflight,
            "world_verdict_rewrite_decision": explicit_world_verdict_rewrite_decision()
        }));
    let markdown =
        render_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(&rewrite_gate);

    assert_eq!(
        rewrite_gate["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_DECISION_SCHEMA
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite_gate_verdict"],
        "ready_for_verified_outcome_ingestion_gate",
        "failure_reasons={}",
        rewrite_gate["failure_reasons"]
    );
    assert_eq!(rewrite_gate["status"], "ready");
    assert_eq!(
        rewrite_gate["reason"],
        "world_verdict_rewrite_gate_ready_for_verified_outcome_ingestion_gate"
    );
    assert_eq!(rewrite_gate["failure_reasons"], json!([]));
    assert_eq!(
        rewrite_gate["world_verdict_rewrite"]["rewrite_decision_id"],
        "world_verdict_rewrite_arrival_bath_move_002"
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite"]["previous_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite"]["rewritten_world_verdict"],
        "verified"
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite"]["ready_for_verified_outcome_ingestion_gate"],
        true
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite"]["world_verdict_rewrite_output_only"],
        true
    );
    assert_eq!(
        rewrite_gate["next_allowed_gate"],
        "verified_outcome_ingestion_gate"
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite_performed_by_this_tool"],
        true
    );
    assert_runtime_executor_world_verdict_rewrite_gate_output_only(&rewrite_gate);

    assert!(markdown.contains(
        "- world_verdict_rewrite_gate_verdict: `ready_for_verified_outcome_ingestion_gate`"
    ));
    assert!(markdown.contains("- previous_world_verdict: `not_verified`"));
    assert!(markdown.contains("- rewritten_world_verdict: `verified`"));
}

#[test]
fn interaction_feedback_runtime_executor_world_verdict_rewrite_gate_blocks_bad_rewrite() {
    let review_preflight =
        ready_runtime_executor_durable_outcome_record_write_evidence_review_preflight();
    let mut rewrite = explicit_world_verdict_rewrite_decision();
    rewrite["decision_kind"] = json!("operator_note");
    rewrite["decision"] = json!("rewrite_now");
    rewrite["source_world_verdict"] = json!("verified");
    rewrite["target_world_verdict"] = json!("not_verified");
    rewrite["reviewed_write_evidence_review_preflight_verdict"] = json!("blocked");
    rewrite["verified_outcome_claim_present"] = json!(false);
    rewrite["reviewer_attestation_present"] = json!(false);
    rewrite["evidence_lineage_preserved"] = json!(false);
    rewrite["outcome_record_digest_confirmed"] = json!(false);
    rewrite["idempotency_key_confirmed"] = json!(false);
    rewrite["persisted_key_confirmed"] = json!(false);
    rewrite["persisted_digest_confirmed"] = json!(false);
    rewrite["world_verdict_rewrite_allowed"] = json!(false);
    rewrite["outcome_ingestion_allowed"] = json!(true);
    rewrite["memory_write_allowed"] = json!(true);
    rewrite["durable_outcome_record_written_by_this_tool"] = json!(true);
    rewrite["world_verdict_persisted_by_this_tool"] = json!(true);
    rewrite["source_durable_outcome_record_write_evidence_review_scope"]["review_decision_id"] =
        json!("other_review");
    rewrite["source_durable_outcome_record_write_evidence_review_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let rewrite_gate =
        build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(&json!({
            "durable_outcome_record_write_evidence_review_preflight": review_preflight,
            "world_verdict_rewrite_decision": rewrite
        }));

    assert_eq!(
        rewrite_gate["world_verdict_rewrite_gate_verdict"],
        "blocked"
    );
    let failure_reasons = rewrite_gate["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_decision_kind_required")));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_decision_not_approved")));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_source_must_be_not_verified")));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_target_must_be_verified")));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_must_review_ready_g16_preflight"
    )));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_requires_verified_outcome_claim"
    )));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_requires_reviewer_attestation"
    )));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_requires_evidence_lineage")));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_requires_outcome_record_digest"
    )));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_requires_idempotency")));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_requires_persisted_key")));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_requires_persisted_digest")));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_decision_must_allow_rewrite")));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_gate_must_not_allow_ingestion"
    )));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_gate_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_gate_must_not_write_outcome_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_gate_must_not_persist_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "world_verdict_rewrite_review_decision_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!("world_verdict_rewrite_digest_scope_mismatch")));
    assert_runtime_executor_world_verdict_rewrite_gate_output_only(&rewrite_gate);
}

#[test]
fn interaction_feedback_runtime_executor_world_verdict_rewrite_gate_requires_review_preflight() {
    let write_evidence_preflight =
        ready_runtime_executor_durable_outcome_record_write_evidence_preflight();
    let rewrite_gate =
        build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(&json!({
            "durable_outcome_record_write_evidence_review_preflight": write_evidence_preflight,
            "world_verdict_rewrite_decision": explicit_world_verdict_rewrite_decision()
        }));

    assert_eq!(
        rewrite_gate["input_kind"],
        "durable_outcome_record_write_evidence_review_preflight_with_world_verdict_rewrite_decision_wrapper"
    );
    assert_eq!(
        rewrite_gate["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        rewrite_gate["world_verdict_rewrite_gate_verdict"],
        "blocked"
    );
    assert_eq!(
        rewrite_gate["reason"],
        "runtime_executor_durable_outcome_record_write_evidence_review_preflight_required"
    );
    assert_eq!(
        rewrite_gate["source_durable_outcome_record_write_evidence_review_preflight"],
        Value::Null
    );
    assert_runtime_executor_world_verdict_rewrite_gate_output_only(&rewrite_gate);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_blocks_without_decision() {
    let rewrite_gate = ready_runtime_executor_world_verdict_rewrite_gate();
    let ingestion_gate =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(&rewrite_gate);
    let markdown = render_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(
        &ingestion_gate,
    );

    assert_eq!(
        ingestion_gate["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_GATE_SCHEMA
    );
    assert_eq!(
        ingestion_gate["input_kind"],
        "runtime_executor_world_verdict_rewrite_gate"
    );
    assert_eq!(
        ingestion_gate["source_world_verdict_rewrite_gate_verdict"],
        "ready_for_verified_outcome_ingestion_gate"
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_decision_schema"],
        Value::Null
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate_verdict"],
        "blocked"
    );
    assert_eq!(ingestion_gate["status"], "blocked");
    assert_eq!(
        ingestion_gate["reason"],
        "explicit_verified_outcome_ingestion_decision_required"
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate"]["ready_for_verified_outcome_admission"],
        false
    );
    assert_runtime_executor_verified_outcome_ingestion_gate_output_only(&ingestion_gate);

    assert!(markdown.contains("- verified_outcome_ingestion_gate_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_verified_outcome_admission: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_accepts_explicit_decision()
{
    let rewrite_gate = ready_runtime_executor_world_verdict_rewrite_gate();
    let ingestion_gate =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(&json!({
            "world_verdict_rewrite_gate": rewrite_gate,
            "verified_outcome_ingestion_decision": explicit_verified_outcome_ingestion_decision()
        }));
    let markdown = render_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(
        &ingestion_gate,
    );

    assert_eq!(
        ingestion_gate["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_GATE_SCHEMA
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_DECISION_SCHEMA
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate_verdict"],
        "ready_for_verified_outcome_admission",
        "failure_reasons={}",
        ingestion_gate["failure_reasons"]
    );
    assert_eq!(ingestion_gate["status"], "ready");
    assert_eq!(
        ingestion_gate["reason"],
        "verified_outcome_ingestion_gate_ready_for_verified_outcome_admission"
    );
    assert_eq!(ingestion_gate["failure_reasons"], json!([]));
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate"]["ingestion_decision_id"],
        "verified_outcome_ingestion_arrival_bath_move_002"
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate"]["previous_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate"]["verified_world_verdict"],
        "verified"
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate"]["ready_for_verified_outcome_admission"],
        true
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate"]
            ["verified_outcome_admission_package_emitted_by_this_tool"],
        true
    );
    assert_eq!(
        ingestion_gate["next_allowed_gate"],
        "verified_outcome_admission_gate"
    );
    assert_runtime_executor_verified_outcome_ingestion_gate_output_only(&ingestion_gate);

    assert!(markdown.contains(
        "- verified_outcome_ingestion_gate_verdict: `ready_for_verified_outcome_admission`"
    ));
    assert!(markdown.contains("- previous_world_verdict: `not_verified`"));
    assert!(markdown.contains("- verified_world_verdict: `verified`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_blocks_bad_decision() {
    let rewrite_gate = ready_runtime_executor_world_verdict_rewrite_gate();
    let mut decision = explicit_verified_outcome_ingestion_decision();
    decision["decision_kind"] = json!("operator_note");
    decision["decision"] = json!("ingest_now");
    decision["source_world_verdict"] = json!("not_verified");
    decision["reviewed_world_verdict_rewrite_gate_verdict"] = json!("blocked");
    decision["bounded_verified_verdict_package_present"] = json!(false);
    decision["verified_outcome_claim_present"] = json!(false);
    decision["world_verdict_rewrite_output_only_confirmed"] = json!(false);
    decision["reviewer_attestation_present"] = json!(false);
    decision["evidence_lineage_preserved"] = json!(false);
    decision["outcome_record_digest_confirmed"] = json!(false);
    decision["idempotency_key_confirmed"] = json!(false);
    decision["persisted_key_confirmed"] = json!(false);
    decision["persisted_digest_confirmed"] = json!(false);
    decision["verified_outcome_ingestion_allowed"] = json!(false);
    decision["store_write_allowed"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["verified_outcome_ingested_by_this_tool"] = json!(true);
    decision["durable_outcome_record_written_by_this_tool"] = json!(true);
    decision["world_verdict_persisted_by_this_tool"] = json!(true);
    decision["source_world_verdict_rewrite_scope"]["rewrite_decision_id"] = json!("other_rewrite");
    decision["source_world_verdict_rewrite_scope"]["outcome_record_digest"] = json!("sha256:other");

    let ingestion_gate =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(&json!({
            "world_verdict_rewrite_gate": rewrite_gate,
            "verified_outcome_ingestion_decision": decision
        }));

    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate_verdict"],
        "blocked"
    );
    let failure_reasons = ingestion_gate["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!("verified_outcome_ingestion_decision_kind_required")));
    assert!(failure_reasons.contains(&json!("verified_outcome_ingestion_decision_not_approved")));
    assert!(failure_reasons.contains(&json!("verified_outcome_ingestion_source_must_be_verified")));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_must_review_ready_rewrite_gate"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_requires_bounded_package"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_requires_verified_outcome_claim"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_requires_output_only_rewrite"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_requires_reviewer_attestation"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_requires_evidence_lineage"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_requires_outcome_record_digest"
    )));
    assert!(failure_reasons.contains(&json!("verified_outcome_ingestion_requires_idempotency")));
    assert!(failure_reasons.contains(&json!("verified_outcome_ingestion_requires_persisted_key")));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_requires_persisted_digest"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_decision_must_allow_ingestion"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_gate_must_not_allow_store_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_gate_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_gate_must_not_ingest_outcome"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_gate_must_not_write_outcome_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_gate_must_not_persist_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_rewrite_decision_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!("verified_outcome_ingestion_digest_scope_mismatch")));
    assert_runtime_executor_verified_outcome_ingestion_gate_output_only(&ingestion_gate);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_requires_rewrite_gate() {
    let review_preflight =
        ready_runtime_executor_durable_outcome_record_write_evidence_review_preflight();
    let ingestion_gate =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(&json!({
            "world_verdict_rewrite_gate": review_preflight,
            "verified_outcome_ingestion_decision": explicit_verified_outcome_ingestion_decision()
        }));

    assert_eq!(
        ingestion_gate["input_kind"],
        "world_verdict_rewrite_gate_with_verified_outcome_ingestion_decision_wrapper"
    );
    assert_eq!(
        ingestion_gate["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        ingestion_gate["verified_outcome_ingestion_gate_verdict"],
        "blocked"
    );
    assert_eq!(
        ingestion_gate["reason"],
        "runtime_executor_world_verdict_rewrite_gate_required"
    );
    assert_eq!(
        ingestion_gate["source_world_verdict_rewrite_gate"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_gate_output_only(&ingestion_gate);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_blocks_without_decision(
) {
    let ingestion_gate = ready_runtime_executor_verified_outcome_ingestion_gate();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &ingestion_gate,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &execution_preflight,
        );

    assert_eq!(
        execution_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["input_kind"],
        "runtime_executor_verified_outcome_ingestion_gate"
    );
    assert_eq!(
        execution_preflight["source_verified_outcome_ingestion_gate_verdict"],
        "ready_for_verified_outcome_admission"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_decision_schema"],
        Value::Null
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(execution_preflight["status"], "blocked");
    assert_eq!(
        execution_preflight["reason"],
        "explicit_verified_outcome_ingestion_execution_decision_required"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]
            ["ready_for_verified_outcome_ingestion_execution_commit"],
        false
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );

    assert!(
        markdown.contains("- verified_outcome_ingestion_execution_preflight_verdict: `blocked`")
    );
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_execution_commit: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_accepts_explicit_decision(
) {
    let ingestion_gate = ready_runtime_executor_verified_outcome_ingestion_gate();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &json!({
                "verified_outcome_ingestion_gate": ingestion_gate,
                "verified_outcome_ingestion_execution_decision":
                    explicit_verified_outcome_ingestion_execution_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &execution_preflight,
        );

    assert_eq!(
        execution_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution_commit",
        "failure_reasons={}",
        execution_preflight["failure_reasons"]
    );
    assert_eq!(execution_preflight["status"], "ready");
    assert_eq!(
        execution_preflight["reason"],
        "verified_outcome_ingestion_execution_preflight_ready_for_execution_commit"
    );
    assert_eq!(execution_preflight["failure_reasons"], json!([]));
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]["execution_decision_id"],
        "verified_outcome_ingestion_execution_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]["previous_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]["verified_world_verdict"],
        "verified"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]
            ["ready_for_verified_outcome_ingestion_execution_commit"],
        true
    );
    assert_eq!(
        execution_preflight["next_allowed_gate"],
        "verified_outcome_ingestion_execution_commit"
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );

    assert!(markdown.contains(
        "- verified_outcome_ingestion_execution_preflight_verdict: `ready_for_verified_outcome_ingestion_execution_commit`"
    ));
    assert!(markdown.contains("- previous_world_verdict: `not_verified`"));
    assert!(markdown.contains("- verified_world_verdict: `verified`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_accepts_admission_preflight(
) {
    let admission_preflight =
        ready_runtime_executor_verified_outcome_ingestion_admission_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &json!({
                "verified_outcome_ingestion_admission_preflight": admission_preflight,
                "verified_outcome_ingestion_execution_decision":
                    explicit_verified_outcome_ingestion_execution_decision_for_admission_preflight()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &execution_preflight,
        );

    assert_eq!(
        execution_preflight["input_kind"],
        "verified_outcome_ingestion_admission_preflight_with_verified_outcome_ingestion_execution_decision_wrapper"
    );
    assert_eq!(
        execution_preflight["source_verified_outcome_ingestion_admission_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution_commit",
        "failure_reasons={}",
        execution_preflight["failure_reasons"]
    );
    assert_eq!(execution_preflight["status"], "ready");
    assert_eq!(execution_preflight["failure_reasons"], json!([]));
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]["source_admission_decision_id"],
        "verified_outcome_ingestion_admission_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]
            ["source_write_evidence_review_decision_id"],
        "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]["source_ingestion_decision_id"],
        "verified_outcome_ingestion_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]
            ["admission_preflight_confirmed"],
        true
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]["admission_decision_confirmed"],
        true
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]
            ["ready_for_verified_outcome_ingestion_execution_commit"],
        true
    );
    assert_eq!(
        execution_preflight["source_verified_outcome_ingestion_gate"],
        Value::Null
    );
    assert_ne!(
        execution_preflight["source_verified_outcome_ingestion_admission_preflight"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );

    assert!(markdown.contains(
        "- source_verified_outcome_ingestion_admission_preflight_verdict: `ready_for_verified_outcome_ingestion_execution`"
    ));
    assert!(markdown.contains("- admission_preflight_confirmed: `true`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_blocks_bad_admission_preflight(
) {
    let mut admission_preflight =
        ready_runtime_executor_verified_outcome_ingestion_admission_preflight();
    admission_preflight["verified_outcome_ingestion_admission_preflight_verdict"] =
        json!("blocked");
    admission_preflight["next_allowed_gate"] =
        json!("repair_verified_outcome_ingestion_admission_input");
    admission_preflight["verified_outcome_ingestion_admission"]
        ["ready_for_verified_outcome_ingestion_execution"] = json!(false);
    admission_preflight["verified_outcome_ingestion_admission"]["previous_world_verdict"] =
        json!("verified");
    admission_preflight["verified_outcome_ingestion_admission"]["verified_world_verdict"] =
        json!("not_verified");
    admission_preflight["verified_outcome_ingestion_admission"]
        ["verified_outcome_ingestion_execution_allowed"] = json!(true);
    admission_preflight["verified_outcome_ingested_by_this_tool"] = json!(true);

    let mut decision =
        explicit_verified_outcome_ingestion_execution_decision_for_admission_preflight();
    decision["reviewed_verified_outcome_ingestion_admission_preflight_verdict"] = json!("blocked");
    decision["admission_preflight_confirmed"] = json!(false);
    decision["admission_decision_confirmed"] = json!(false);
    decision["source_verified_outcome_ingestion_admission_scope"]["admission_decision_id"] =
        json!("other_admission");
    decision["source_verified_outcome_ingestion_admission_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &json!({
                "verified_outcome_ingestion_admission_preflight": admission_preflight,
                "verified_outcome_ingestion_execution_decision": decision
            }),
        );

    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = execution_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "source_verified_outcome_ingestion_admission_preflight_not_ready",
        "source_verified_outcome_ingestion_admission_preflight_next_gate_mismatch",
        "source_verified_outcome_ingestion_admission_not_ready_for_execution",
        "source_previous_world_verdict_must_be_not_verified",
        "source_verified_world_verdict_must_be_verified",
        "source_verified_outcome_ingestion_admission_boundary_not_output_only",
        "source_verified_outcome_ingestion_admission_must_be_output_only",
        "verified_outcome_ingestion_execution_must_review_ready_admission_preflight",
        "verified_outcome_ingestion_execution_requires_admission_preflight_confirmation",
        "verified_outcome_ingestion_execution_requires_admission_decision_confirmation",
        "verified_outcome_ingestion_execution_admission_decision_scope_mismatch",
        "verified_outcome_ingestion_execution_digest_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_blocks_bad_decision(
) {
    let ingestion_gate = ready_runtime_executor_verified_outcome_ingestion_gate();
    let mut decision = explicit_verified_outcome_ingestion_execution_decision();
    decision["decision_kind"] = json!("operator_note");
    decision["decision"] = json!("execute_now");
    decision["source_world_verdict"] = json!("verified");
    decision["verified_world_verdict"] = json!("not_verified");
    decision["reviewed_verified_outcome_ingestion_gate_verdict"] = json!("blocked");
    decision["verified_outcome_package_confirmed"] = json!(false);
    decision["ingestion_gate_output_confirmed"] = json!(false);
    decision["reviewer_attestation_present"] = json!(false);
    decision["evidence_lineage_preserved"] = json!(false);
    decision["outcome_record_digest_confirmed"] = json!(false);
    decision["idempotency_key_confirmed"] = json!(false);
    decision["persisted_key_confirmed"] = json!(false);
    decision["persisted_digest_confirmed"] = json!(false);
    decision["execution_boundary_acknowledged"] = json!(false);
    decision["outcome_ingestion_allowed"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["verified_outcome_ingested_by_this_tool"] = json!(true);
    decision["durable_outcome_record_written_by_this_tool"] = json!(true);
    decision["world_verdict_persisted_by_this_tool"] = json!(true);
    decision["source_verified_outcome_ingestion_gate_scope"]["ingestion_decision_id"] =
        json!("other_ingestion");
    decision["source_verified_outcome_ingestion_gate_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &json!({
                "verified_outcome_ingestion_gate": ingestion_gate,
                "verified_outcome_ingestion_execution_decision": decision
            }),
        );

    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = execution_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_decision_kind_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_source_must_be_not_verified"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_verdict_must_be_verified"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_must_review_ready_g18_gate"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_package_confirmation"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_gate_output_confirmation"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_reviewer_attestation"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_evidence_lineage"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_outcome_record_digest"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_idempotency"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_persisted_key"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_persisted_digest"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_requires_boundary_acknowledgement"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_preflight_must_not_allow_ingestion"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_preflight_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_preflight_must_not_ingest_outcome"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_preflight_must_not_write_outcome_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_preflight_must_not_persist_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_ingestion_decision_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_digest_scope_mismatch"
    )));
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_requires_ingestion_gate(
) {
    let rewrite_gate = ready_runtime_executor_world_verdict_rewrite_gate();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &json!({
                "verified_outcome_ingestion_gate": rewrite_gate,
                "verified_outcome_ingestion_execution_decision":
                    explicit_verified_outcome_ingestion_execution_decision()
            }),
        );

    assert_eq!(
        execution_preflight["input_kind"],
        "verified_outcome_ingestion_gate_with_verified_outcome_ingestion_execution_decision_wrapper"
    );
    assert_eq!(
        execution_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        execution_preflight["reason"],
        "runtime_executor_verified_outcome_ingestion_gate_required"
    );
    assert_eq!(
        execution_preflight["source_verified_outcome_ingestion_gate"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_accepts_admission_preflight_without_decision_blocks(
) {
    let admission_preflight =
        ready_runtime_executor_verified_outcome_ingestion_admission_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &admission_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &execution_preflight,
        );

    assert_eq!(
        execution_preflight["input_kind"],
        "runtime_executor_verified_outcome_ingestion_admission_preflight"
    );
    assert_eq!(
        execution_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_ADMISSION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        execution_preflight["source_verified_outcome_ingestion_admission_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        execution_preflight["reason"],
        "explicit_verified_outcome_ingestion_execution_decision_required"
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );
    assert!(markdown.contains(
        "- source_verified_outcome_ingestion_admission_preflight_verdict: `ready_for_verified_outcome_ingestion_execution`"
    ));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_execution_commit: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_accepts_admission_preflight_decision(
) {
    let admission_preflight =
        ready_runtime_executor_verified_outcome_ingestion_admission_preflight();
    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &json!({
                "verified_outcome_ingestion_admission_preflight": admission_preflight,
                "verified_outcome_ingestion_execution_decision":
                    explicit_verified_outcome_ingestion_execution_decision_for_admission_preflight()
            }),
        );

    assert_eq!(
        execution_preflight["input_kind"],
        "verified_outcome_ingestion_admission_preflight_with_verified_outcome_ingestion_execution_decision_wrapper"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution_commit",
        "failure_reasons={}",
        execution_preflight["failure_reasons"]
    );
    assert_eq!(execution_preflight["failure_reasons"], json!([]));
    assert_eq!(
        execution_preflight["source_verified_outcome_ingestion_admission_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]["source_admission_decision_id"],
        "verified_outcome_ingestion_admission_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]
            ["source_write_evidence_review_decision_id"],
        "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002"
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]
            ["admission_preflight_confirmed"],
        true
    );
    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution"]["admission_decision_confirmed"],
        true
    );
    assert_eq!(
        execution_preflight["next_allowed_gate"],
        "verified_outcome_ingestion_execution_commit"
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight_blocks_bad_admission_decision(
) {
    let admission_preflight =
        ready_runtime_executor_verified_outcome_ingestion_admission_preflight();
    let mut decision =
        explicit_verified_outcome_ingestion_execution_decision_for_admission_preflight();
    decision["reviewed_verified_outcome_ingestion_admission_preflight_verdict"] = json!("blocked");
    decision["admission_preflight_confirmed"] = json!(false);
    decision["admission_decision_confirmed"] = json!(false);
    decision["source_verified_outcome_ingestion_admission_scope"]["admission_decision_id"] =
        json!("other_admission");
    decision["source_verified_outcome_ingestion_admission_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let execution_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
            &json!({
                "verified_outcome_ingestion_admission_preflight": admission_preflight,
                "verified_outcome_ingestion_execution_decision": decision
            }),
        );

    assert_eq!(
        execution_preflight["verified_outcome_ingestion_execution_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = execution_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_execution_must_review_ready_admission_preflight",
        "verified_outcome_ingestion_execution_requires_admission_preflight_confirmation",
        "verified_outcome_ingestion_execution_requires_admission_decision_confirmation",
        "verified_outcome_ingestion_execution_admission_decision_scope_mismatch",
        "verified_outcome_ingestion_execution_digest_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
        &execution_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_blocks_without_decision(
) {
    let execution_preflight =
        ready_runtime_executor_verified_outcome_ingestion_execution_preflight();
    let commit =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &execution_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &commit,
        );

    assert_eq!(
        commit["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA
    );
    assert_eq!(
        commit["input_kind"],
        "runtime_executor_verified_outcome_ingestion_execution_preflight"
    );
    assert_eq!(
        commit["source_verified_outcome_ingestion_execution_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution_commit"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_decision_schema"],
        Value::Null
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_verdict"],
        "blocked"
    );
    assert_eq!(commit["status"], "blocked");
    assert_eq!(
        commit["reason"],
        "explicit_verified_outcome_ingestion_execution_commit_decision_required"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]
            ["ready_for_verified_outcome_ingestion_apply"],
        false
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_commit_output_only(&commit);

    assert!(markdown.contains("- verified_outcome_ingestion_execution_commit_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_apply: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_accepts_explicit_decision(
) {
    let execution_preflight =
        ready_runtime_executor_verified_outcome_ingestion_execution_preflight();
    let commit =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &json!({
                "verified_outcome_ingestion_execution_preflight": execution_preflight,
                "verified_outcome_ingestion_execution_commit_decision":
                    explicit_verified_outcome_ingestion_execution_commit_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &commit,
        );

    assert_eq!(
        commit["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_verdict"],
        "ready_for_verified_outcome_ingestion_apply",
        "failure_reasons={}",
        commit["failure_reasons"]
    );
    assert_eq!(commit["status"], "ready");
    assert_eq!(
        commit["reason"],
        "verified_outcome_ingestion_execution_commit_ready_for_apply"
    );
    assert_eq!(commit["failure_reasons"], json!([]));
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["commit_decision_id"],
        "verified_outcome_ingestion_execution_commit_arrival_bath_move_002"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["previous_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["verified_world_verdict"],
        "verified"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]
            ["ready_for_verified_outcome_ingestion_apply"],
        true
    );
    assert_eq!(
        commit["next_allowed_gate"],
        "verified_outcome_ingestion_apply"
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_commit_output_only(&commit);

    assert!(markdown.contains(
        "- verified_outcome_ingestion_execution_commit_verdict: `ready_for_verified_outcome_ingestion_apply`"
    ));
    assert!(markdown.contains("- previous_world_verdict: `not_verified`"));
    assert!(markdown.contains("- verified_world_verdict: `verified`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_accepts_admission_source_decision(
) {
    let execution_preflight =
        ready_runtime_executor_verified_outcome_ingestion_execution_preflight_from_admission_preflight();
    let commit =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &json!({
                "verified_outcome_ingestion_execution_preflight": execution_preflight,
                "verified_outcome_ingestion_execution_commit_decision":
                    explicit_verified_outcome_ingestion_execution_commit_decision_for_admission_preflight()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &commit,
        );

    assert_eq!(
        commit["source_verified_outcome_ingestion_admission_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_verdict"],
        "ready_for_verified_outcome_ingestion_apply",
        "failure_reasons={}",
        commit["failure_reasons"]
    );
    assert_eq!(commit["status"], "ready");
    assert_eq!(commit["failure_reasons"], json!([]));
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["commit_decision_id"],
        "verified_outcome_ingestion_execution_commit_from_admission_arrival_bath_move_002"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["source_execution_decision_id"],
        "verified_outcome_ingestion_execution_from_admission_arrival_bath_move_002"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["source_admission_decision_id"],
        "verified_outcome_ingestion_admission_arrival_bath_move_002"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]
            ["source_write_evidence_review_decision_id"],
        "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["source_commit_decision_id"],
        "verified_outcome_ingestion_execution_commit_arrival_bath_move_002"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["source_prior_execution_decision_id"],
        "verified_outcome_ingestion_execution_arrival_bath_move_002"
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["admission_preflight_confirmed"],
        true
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]["admission_decision_confirmed"],
        true
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit"]
            ["ready_for_verified_outcome_ingestion_apply"],
        true
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_commit_output_only(&commit);

    assert!(markdown.contains(
        "- source_verified_outcome_ingestion_admission_preflight_verdict: `ready_for_verified_outcome_ingestion_execution`"
    ));
    assert!(markdown.contains(
        "- source_admission_decision_id: `verified_outcome_ingestion_admission_arrival_bath_move_002`"
    ));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_blocks_bad_admission_source_decision(
) {
    let execution_preflight =
        ready_runtime_executor_verified_outcome_ingestion_execution_preflight_from_admission_preflight();
    let mut decision =
        explicit_verified_outcome_ingestion_execution_commit_decision_for_admission_preflight();
    decision["admission_preflight_confirmed"] = json!(false);
    decision["admission_decision_confirmed"] = json!(false);
    decision["source_verified_outcome_ingestion_execution_preflight_scope"]
        ["source_admission_decision_id"] = json!("other_admission");
    decision["source_verified_outcome_ingestion_execution_preflight_scope"]
        ["store_write_execution_id"] = json!("other_store_write");

    let commit =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &json!({
                "verified_outcome_ingestion_execution_preflight": execution_preflight,
                "verified_outcome_ingestion_execution_commit_decision": decision
            }),
        );

    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_verdict"],
        "blocked"
    );
    let failure_reasons = commit["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_execution_commit_requires_admission_preflight_confirmation",
        "verified_outcome_ingestion_execution_commit_requires_admission_decision_confirmation",
        "verified_outcome_ingestion_execution_commit_admission_decision_scope_mismatch",
        "verified_outcome_ingestion_execution_commit_store_write_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_execution_commit_output_only(&commit);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_blocks_bad_decision(
) {
    let execution_preflight =
        ready_runtime_executor_verified_outcome_ingestion_execution_preflight();
    let mut decision = explicit_verified_outcome_ingestion_execution_commit_decision();
    decision["decision_kind"] = json!("operator_note");
    decision["decision"] = json!("apply_now");
    decision["source_world_verdict"] = json!("verified");
    decision["verified_world_verdict"] = json!("not_verified");
    decision["reviewed_verified_outcome_ingestion_execution_preflight_verdict"] = json!("blocked");
    decision["execution_preflight_package_confirmed"] = json!(false);
    decision["verified_outcome_package_confirmed"] = json!(false);
    decision["reviewer_attestation_present"] = json!(false);
    decision["evidence_lineage_preserved"] = json!(false);
    decision["outcome_record_digest_confirmed"] = json!(false);
    decision["idempotency_key_confirmed"] = json!(false);
    decision["persisted_key_confirmed"] = json!(false);
    decision["persisted_digest_confirmed"] = json!(false);
    decision["apply_boundary_acknowledged"] = json!(false);
    decision["outcome_ingestion_allowed"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["verified_outcome_ingested_by_this_tool"] = json!(true);
    decision["durable_outcome_record_written_by_this_tool"] = json!(true);
    decision["world_verdict_persisted_by_this_tool"] = json!(true);
    decision["source_verified_outcome_ingestion_execution_preflight_scope"]
        ["execution_decision_id"] = json!("other_execution");
    decision["source_verified_outcome_ingestion_execution_preflight_scope"]
        ["outcome_record_digest"] = json!("sha256:other");

    let commit =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &json!({
                "verified_outcome_ingestion_execution_preflight": execution_preflight,
                "verified_outcome_ingestion_execution_commit_decision": decision
            }),
        );

    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_verdict"],
        "blocked"
    );
    let failure_reasons = commit["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_decision_kind_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_source_must_be_not_verified"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_verdict_must_be_verified"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_must_review_ready_g19_preflight"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_preflight_package"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_verified_package"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_reviewer_attestation"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_evidence_lineage"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_outcome_record_digest"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_idempotency"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_persisted_key"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_persisted_digest"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_requires_apply_boundary"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_must_not_allow_ingestion"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_must_not_ingest_outcome"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_must_not_write_outcome_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_must_not_persist_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_execution_decision_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_execution_commit_digest_scope_mismatch"
    )));
    assert_runtime_executor_verified_outcome_ingestion_execution_commit_output_only(&commit);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_requires_execution_preflight(
) {
    let ingestion_gate = ready_runtime_executor_verified_outcome_ingestion_gate();
    let commit =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &json!({
                "verified_outcome_ingestion_execution_preflight": ingestion_gate,
                "verified_outcome_ingestion_execution_commit_decision":
                    explicit_verified_outcome_ingestion_execution_commit_decision()
            }),
        );

    assert_eq!(
        commit["input_kind"],
        "verified_outcome_ingestion_execution_preflight_with_commit_decision_wrapper"
    );
    assert_eq!(
        commit["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_GATE_SCHEMA
    );
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_verdict"],
        "blocked"
    );
    assert_eq!(
        commit["reason"],
        "runtime_executor_verified_outcome_ingestion_execution_preflight_required"
    );
    assert_eq!(
        commit["source_verified_outcome_ingestion_execution_preflight"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_execution_commit_output_only(&commit);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_blocks_without_decision(
) {
    let commit = ready_runtime_executor_verified_outcome_ingestion_execution_commit();
    let apply =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&commit);
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&apply);

    assert_eq!(
        apply["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_GATE_SCHEMA
    );
    assert_eq!(
        apply["input_kind"],
        "runtime_executor_verified_outcome_ingestion_execution_commit"
    );
    assert_eq!(
        apply["source_verified_outcome_ingestion_execution_commit_verdict"],
        "ready_for_verified_outcome_ingestion_apply"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply_decision_schema"],
        Value::Null
    );
    assert_eq!(apply["verified_outcome_ingestion_apply_verdict"], "blocked");
    assert_eq!(apply["status"], "blocked");
    assert_eq!(
        apply["reason"],
        "explicit_verified_outcome_ingestion_apply_decision_required"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["ready_for_verified_outcome_ingestion_writer"],
        false
    );
    assert_runtime_executor_verified_outcome_ingestion_apply_gate_output_only(&apply);

    assert!(markdown.contains("- verified_outcome_ingestion_apply_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_writer: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_accepts_explicit_decision(
) {
    let commit = ready_runtime_executor_verified_outcome_ingestion_execution_commit();
    let apply =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&json!({
            "verified_outcome_ingestion_execution_commit": commit,
            "verified_outcome_ingestion_apply_decision":
                explicit_verified_outcome_ingestion_apply_decision()
        }));
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&apply);

    assert_eq!(
        apply["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_GATE_SCHEMA
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply_verdict"],
        "ready_for_verified_outcome_ingestion_writer",
        "failure_reasons={}",
        apply["failure_reasons"]
    );
    assert_eq!(apply["status"], "ready");
    assert_eq!(
        apply["reason"],
        "verified_outcome_ingestion_apply_ready_for_writer"
    );
    assert_eq!(apply["failure_reasons"], json!([]));
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["apply_decision_id"],
        "verified_outcome_ingestion_apply_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["commit_decision_id"],
        "verified_outcome_ingestion_execution_commit_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["previous_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["verified_world_verdict"],
        "verified"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["ready_for_verified_outcome_ingestion_writer"],
        true
    );
    assert_eq!(
        apply["next_allowed_gate"],
        "verified_outcome_ingestion_writer"
    );
    assert_runtime_executor_verified_outcome_ingestion_apply_gate_output_only(&apply);

    assert!(markdown.contains(
        "- verified_outcome_ingestion_apply_verdict: `ready_for_verified_outcome_ingestion_writer`"
    ));
    assert!(markdown.contains("- previous_world_verdict: `not_verified`"));
    assert!(markdown.contains("- verified_world_verdict: `verified`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_accepts_admission_source_decision(
) {
    let commit =
        ready_runtime_executor_verified_outcome_ingestion_execution_commit_from_admission_preflight(
        );
    let apply =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&json!({
            "verified_outcome_ingestion_execution_commit": commit,
            "verified_outcome_ingestion_apply_decision":
                explicit_verified_outcome_ingestion_apply_decision_for_admission_source_commit()
        }));
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&apply);

    assert_eq!(
        apply["source_verified_outcome_ingestion_admission_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply_verdict"],
        "ready_for_verified_outcome_ingestion_writer",
        "failure_reasons={}",
        apply["failure_reasons"]
    );
    assert_eq!(apply["status"], "ready");
    assert_eq!(apply["failure_reasons"], json!([]));
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["apply_decision_id"],
        "verified_outcome_ingestion_apply_from_admission_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["commit_decision_id"],
        "verified_outcome_ingestion_execution_commit_from_admission_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["source_admission_decision_id"],
        "verified_outcome_ingestion_admission_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["source_write_evidence_review_decision_id"],
        "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["source_apply_decision_id"],
        "verified_outcome_ingestion_apply_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["source_commit_decision_id"],
        "verified_outcome_ingestion_execution_commit_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["source_prior_execution_decision_id"],
        "verified_outcome_ingestion_execution_arrival_bath_move_002"
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["admission_preflight_confirmed"],
        true
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["admission_decision_confirmed"],
        true
    );
    assert_eq!(
        apply["verified_outcome_ingestion_apply"]["ready_for_verified_outcome_ingestion_writer"],
        true
    );
    assert_runtime_executor_verified_outcome_ingestion_apply_gate_output_only(&apply);

    assert!(markdown.contains(
        "- source_verified_outcome_ingestion_admission_preflight_verdict: `ready_for_verified_outcome_ingestion_execution`"
    ));
    assert!(markdown.contains(
        "- source_admission_decision_id: `verified_outcome_ingestion_admission_arrival_bath_move_002`"
    ));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_blocks_bad_admission_source_decision(
) {
    let commit =
        ready_runtime_executor_verified_outcome_ingestion_execution_commit_from_admission_preflight(
        );
    let mut decision =
        explicit_verified_outcome_ingestion_apply_decision_for_admission_source_commit();
    decision["admission_preflight_confirmed"] = json!(false);
    decision["admission_decision_confirmed"] = json!(false);
    decision["source_verified_outcome_ingestion_execution_commit_scope"]
        ["source_admission_decision_id"] = json!("other_admission");
    decision["source_verified_outcome_ingestion_execution_commit_scope"]
        ["store_write_execution_id"] = json!("other_store_write");

    let apply =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&json!({
            "verified_outcome_ingestion_execution_commit": commit,
            "verified_outcome_ingestion_apply_decision": decision
        }));

    assert_eq!(apply["verified_outcome_ingestion_apply_verdict"], "blocked");
    let failure_reasons = apply["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_apply_requires_admission_preflight_confirmation",
        "verified_outcome_ingestion_apply_requires_admission_decision_confirmation",
        "verified_outcome_ingestion_apply_admission_decision_scope_mismatch",
        "verified_outcome_ingestion_apply_store_write_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_apply_gate_output_only(&apply);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_blocks_bad_decision()
{
    let commit = ready_runtime_executor_verified_outcome_ingestion_execution_commit();
    let mut decision = explicit_verified_outcome_ingestion_apply_decision();
    decision["decision_kind"] = json!("operator_note");
    decision["decision"] = json!("write_now");
    decision["source_world_verdict"] = json!("verified");
    decision["verified_world_verdict"] = json!("not_verified");
    decision["reviewed_verified_outcome_ingestion_execution_commit_verdict"] = json!("blocked");
    decision["commit_package_confirmed"] = json!(false);
    decision["execution_preflight_package_confirmed"] = json!(false);
    decision["verified_outcome_package_confirmed"] = json!(false);
    decision["reviewer_attestation_present"] = json!(false);
    decision["evidence_lineage_preserved"] = json!(false);
    decision["outcome_record_digest_confirmed"] = json!(false);
    decision["idempotency_key_confirmed"] = json!(false);
    decision["persisted_key_confirmed"] = json!(false);
    decision["persisted_digest_confirmed"] = json!(false);
    decision["writer_boundary_acknowledged"] = json!(false);
    decision["outcome_ingestion_allowed_by_this_tool"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["verified_outcome_ingested_by_this_tool"] = json!(true);
    decision["durable_outcome_record_written_by_this_tool"] = json!(true);
    decision["world_verdict_persisted_by_this_tool"] = json!(true);
    decision["source_verified_outcome_ingestion_execution_commit_scope"]["commit_decision_id"] =
        json!("other_commit");
    decision["source_verified_outcome_ingestion_execution_commit_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let apply =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&json!({
            "verified_outcome_ingestion_execution_commit": commit,
            "verified_outcome_ingestion_apply_decision": decision
        }));

    assert_eq!(apply["verified_outcome_ingestion_apply_verdict"], "blocked");
    let failure_reasons = apply["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_decision_kind_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_source_must_be_not_verified"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_verdict_must_be_verified"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_must_review_ready_g20_commit"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_commit_package"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_preflight_package"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_verified_package"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_reviewer_attestation"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_evidence_lineage"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_outcome_record_digest"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_idempotency"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_persisted_key"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_persisted_digest"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_requires_writer_boundary"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_must_not_allow_ingestion_by_this_tool"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_must_not_ingest_outcome"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_must_not_write_outcome_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_must_not_persist_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_commit_decision_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_apply_digest_scope_mismatch"
    )));
    assert_runtime_executor_verified_outcome_ingestion_apply_gate_output_only(&apply);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_requires_commit() {
    let execution_preflight =
        ready_runtime_executor_verified_outcome_ingestion_execution_preflight();
    let apply =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&json!({
            "verified_outcome_ingestion_execution_commit": execution_preflight,
            "verified_outcome_ingestion_apply_decision":
                explicit_verified_outcome_ingestion_apply_decision()
        }));

    assert_eq!(
        apply["input_kind"],
        "verified_outcome_ingestion_execution_commit_with_apply_decision_wrapper"
    );
    assert_eq!(
        apply["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(apply["verified_outcome_ingestion_apply_verdict"], "blocked");
    assert_eq!(
        apply["reason"],
        "runtime_executor_verified_outcome_ingestion_execution_commit_required"
    );
    assert_eq!(
        apply["source_verified_outcome_ingestion_execution_commit"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_apply_gate_output_only(&apply);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_blocks_without_decision()
{
    let apply = ready_runtime_executor_verified_outcome_ingestion_apply_gate();
    let writer =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(&apply);
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(&writer);

    assert_eq!(
        writer["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_SCHEMA
    );
    assert_eq!(
        writer["input_kind"],
        "runtime_executor_verified_outcome_ingestion_apply_gate"
    );
    assert_eq!(
        writer["source_verified_outcome_ingestion_apply_verdict"],
        "ready_for_verified_outcome_ingestion_writer"
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer_decision_schema"],
        Value::Null
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer_verdict"],
        "blocked"
    );
    assert_eq!(writer["status"], "blocked");
    assert_eq!(
        writer["reason"],
        "explicit_verified_outcome_ingestion_writer_decision_required"
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer"]
            ["ready_for_verified_outcome_ingestion_writer_execution"],
        false
    );
    assert_runtime_executor_verified_outcome_ingestion_writer_output_only(&writer);

    assert!(markdown.contains("- verified_outcome_ingestion_writer_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_writer_execution: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_accepts_explicit_decision(
) {
    let apply = ready_runtime_executor_verified_outcome_ingestion_apply_gate();
    let writer =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(&json!({
            "verified_outcome_ingestion_apply_gate": apply,
            "verified_outcome_ingestion_writer_decision":
                explicit_verified_outcome_ingestion_writer_decision()
        }));
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(&writer);

    assert_eq!(
        writer["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_SCHEMA
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_DECISION_SCHEMA
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer_verdict"],
        "ready_for_verified_outcome_ingestion_writer_execution",
        "failure_reasons={}",
        writer["failure_reasons"]
    );
    assert_eq!(writer["status"], "ready");
    assert_eq!(
        writer["reason"],
        "verified_outcome_ingestion_writer_ready_for_execution"
    );
    assert_eq!(writer["failure_reasons"], json!([]));
    assert_eq!(
        writer["verified_outcome_ingestion_writer"]["writer_decision_id"],
        "verified_outcome_ingestion_writer_arrival_bath_move_002"
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer"]["apply_decision_id"],
        "verified_outcome_ingestion_apply_arrival_bath_move_002"
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer"]["previous_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer"]["verified_world_verdict"],
        "verified"
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer"]
            ["ready_for_verified_outcome_ingestion_writer_execution"],
        true
    );
    assert_eq!(
        writer["next_allowed_gate"],
        "verified_outcome_ingestion_writer_execution"
    );
    assert_runtime_executor_verified_outcome_ingestion_writer_output_only(&writer);

    assert!(markdown.contains(
        "- verified_outcome_ingestion_writer_verdict: `ready_for_verified_outcome_ingestion_writer_execution`"
    ));
    assert!(markdown.contains("- previous_world_verdict: `not_verified`"));
    assert!(markdown.contains("- verified_world_verdict: `verified`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_blocks_bad_decision() {
    let apply = ready_runtime_executor_verified_outcome_ingestion_apply_gate();
    let mut decision = explicit_verified_outcome_ingestion_writer_decision();
    decision["decision_kind"] = json!("operator_note");
    decision["decision"] = json!("ingest_now");
    decision["source_world_verdict"] = json!("verified");
    decision["verified_world_verdict"] = json!("not_verified");
    decision["reviewed_verified_outcome_ingestion_apply_verdict"] = json!("blocked");
    decision["apply_package_confirmed"] = json!(false);
    decision["commit_package_confirmed"] = json!(false);
    decision["verified_outcome_package_confirmed"] = json!(false);
    decision["writer_payload_confirmed"] = json!(false);
    decision["writer_destination_confirmed"] = json!(false);
    decision["writer_idempotency_confirmed"] = json!(false);
    decision["writer_boundary_acknowledged"] = json!(false);
    decision["rollback_plan_confirmed"] = json!(false);
    decision["outcome_ingestion_allowed_by_this_tool"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["verified_outcome_ingested_by_this_tool"] = json!(true);
    decision["durable_outcome_record_written_by_this_tool"] = json!(true);
    decision["world_verdict_persisted_by_this_tool"] = json!(true);
    decision["source_verified_outcome_ingestion_apply_scope"]["apply_decision_id"] =
        json!("other_apply");
    decision["source_verified_outcome_ingestion_apply_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let writer =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(&json!({
            "verified_outcome_ingestion_apply_gate": apply,
            "verified_outcome_ingestion_writer_decision": decision
        }));

    assert_eq!(
        writer["verified_outcome_ingestion_writer_verdict"],
        "blocked"
    );
    let failure_reasons = writer["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_decision_kind_required"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_decision_not_approved"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_source_must_be_not_verified"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_verdict_must_be_verified"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_must_review_ready_g21_apply"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_requires_apply_package"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_requires_commit_package"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_requires_verified_package"
    )));
    assert!(failure_reasons.contains(&json!("verified_outcome_ingestion_writer_requires_payload")));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_requires_destination"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_requires_idempotency"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_requires_writer_boundary"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_requires_rollback_plan"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_must_not_allow_ingestion_by_this_tool"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_must_not_allow_memory_write"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_must_not_ingest_outcome"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_must_not_write_outcome_record"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_must_not_persist_verdict"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_apply_decision_scope_mismatch"
    )));
    assert!(failure_reasons.contains(&json!(
        "verified_outcome_ingestion_writer_digest_scope_mismatch"
    )));
    assert_runtime_executor_verified_outcome_ingestion_writer_output_only(&writer);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_requires_apply_gate() {
    let commit = ready_runtime_executor_verified_outcome_ingestion_execution_commit();
    let writer =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(&json!({
            "verified_outcome_ingestion_apply_gate": commit,
            "verified_outcome_ingestion_writer_decision":
                explicit_verified_outcome_ingestion_writer_decision()
        }));

    assert_eq!(
        writer["input_kind"],
        "verified_outcome_ingestion_apply_gate_with_writer_decision_wrapper"
    );
    assert_eq!(
        writer["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA
    );
    assert_eq!(
        writer["verified_outcome_ingestion_writer_verdict"],
        "blocked"
    );
    assert_eq!(
        writer["reason"],
        "runtime_executor_verified_outcome_ingestion_apply_gate_required"
    );
    assert_eq!(
        writer["source_verified_outcome_ingestion_apply_gate"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_writer_output_only(&writer);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution_blocks_without_decision(
) {
    let writer = ready_runtime_executor_verified_outcome_ingestion_writer();
    let execution =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution(
            &writer,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution(
            &execution,
        );

    assert_eq!(
        execution["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_EXECUTION_SCHEMA
    );
    assert_eq!(
        execution["input_kind"],
        "runtime_executor_verified_outcome_ingestion_writer"
    );
    assert_eq!(
        execution["source_verified_outcome_ingestion_writer_verdict"],
        "ready_for_verified_outcome_ingestion_writer_execution"
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution_decision_schema"],
        Value::Null
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution_verdict"],
        "blocked"
    );
    assert_eq!(
        execution["reason"],
        "explicit_verified_outcome_ingestion_writer_execution_decision_required"
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution"]
            ["ready_for_verified_outcome_ingestion_persistence"],
        false
    );
    assert_runtime_executor_verified_outcome_ingestion_writer_execution_output_only(&execution);

    assert!(markdown.contains("- verified_outcome_ingestion_writer_execution_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_persistence: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution_accepts_explicit_decision(
) {
    let writer = ready_runtime_executor_verified_outcome_ingestion_writer();
    let execution =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution(
            &json!({
                "verified_outcome_ingestion_writer": writer,
                "verified_outcome_ingestion_writer_execution_decision":
                    explicit_verified_outcome_ingestion_writer_execution_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution(
            &execution,
        );

    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_EXECUTION_DECISION_SCHEMA
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution_verdict"],
        "ready_for_verified_outcome_ingestion_persistence",
        "failure_reasons={}",
        execution["failure_reasons"]
    );
    assert_eq!(
        execution["reason"],
        "verified_outcome_ingestion_writer_execution_ready_for_persistence"
    );
    assert_eq!(execution["failure_reasons"], json!([]));
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution"]["writer_execution_decision_id"],
        "verified_outcome_ingestion_writer_execution_arrival_bath_move_002"
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution"]["writer_decision_id"],
        "verified_outcome_ingestion_writer_arrival_bath_move_002"
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution"]["previous_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution"]["verified_world_verdict"],
        "verified"
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution"]
            ["ready_for_verified_outcome_ingestion_persistence"],
        true
    );
    assert_eq!(
        execution["next_allowed_gate"],
        "verified_outcome_ingestion_persistence"
    );
    assert_runtime_executor_verified_outcome_ingestion_writer_execution_output_only(&execution);

    assert!(markdown.contains(
        "- verified_outcome_ingestion_writer_execution_verdict: `ready_for_verified_outcome_ingestion_persistence`"
    ));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution_blocks_bad_decision(
) {
    let writer = ready_runtime_executor_verified_outcome_ingestion_writer();
    let mut decision = explicit_verified_outcome_ingestion_writer_execution_decision();
    decision["decision_kind"] = json!("operator_note");
    decision["decision"] = json!("persist_now");
    decision["source_world_verdict"] = json!("verified");
    decision["verified_world_verdict"] = json!("not_verified");
    decision["reviewed_verified_outcome_ingestion_writer_verdict"] = json!("blocked");
    decision["writer_package_confirmed"] = json!(false);
    decision["apply_package_confirmed"] = json!(false);
    decision["verified_outcome_package_confirmed"] = json!(false);
    decision["write_destination_verified"] = json!(false);
    decision["outcome_record_digest_verified"] = json!(false);
    decision["idempotent_upsert_confirmed"] = json!(false);
    decision["store_transaction_plan_complete"] = json!(false);
    decision["rollback_plan_confirmed"] = json!(false);
    decision["write_destination"] = Value::Null;
    decision["outcome_record_key"] = Value::Null;
    decision["outcome_record_digest"] = Value::Null;
    decision["outcome_ingestion_allowed_by_this_tool"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["verified_outcome_ingested_by_this_tool"] = json!(true);
    decision["durable_outcome_record_written_by_this_tool"] = json!(true);
    decision["world_verdict_persisted_by_this_tool"] = json!(true);
    decision["source_verified_outcome_ingestion_writer_scope"]["writer_decision_id"] =
        json!("other_writer");
    decision["source_verified_outcome_ingestion_writer_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let execution =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution(
            &json!({
                "verified_outcome_ingestion_writer": writer,
                "verified_outcome_ingestion_writer_execution_decision": decision
            }),
        );

    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution_verdict"],
        "blocked"
    );
    let failure_reasons = execution["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_writer_execution_decision_kind_required",
        "verified_outcome_ingestion_writer_execution_decision_not_approved",
        "verified_outcome_ingestion_writer_execution_source_must_be_not_verified",
        "verified_outcome_ingestion_writer_execution_verdict_must_be_verified",
        "verified_outcome_ingestion_writer_execution_must_review_ready_g22_writer",
        "verified_outcome_ingestion_writer_execution_requires_writer_package",
        "verified_outcome_ingestion_writer_execution_requires_apply_package",
        "verified_outcome_ingestion_writer_execution_requires_verified_package",
        "verified_outcome_ingestion_writer_execution_requires_destination",
        "verified_outcome_ingestion_writer_execution_requires_digest",
        "verified_outcome_ingestion_writer_execution_requires_idempotent_upsert",
        "verified_outcome_ingestion_writer_execution_requires_transaction_plan",
        "verified_outcome_ingestion_writer_execution_requires_rollback_plan",
        "verified_outcome_ingestion_writer_execution_destination_required",
        "verified_outcome_ingestion_writer_execution_key_required",
        "verified_outcome_ingestion_writer_execution_digest_required",
        "verified_outcome_ingestion_writer_execution_must_not_allow_ingestion_by_this_tool",
        "verified_outcome_ingestion_writer_execution_must_not_allow_memory_write",
        "verified_outcome_ingestion_writer_execution_must_not_ingest_outcome",
        "verified_outcome_ingestion_writer_execution_must_not_write_outcome_record",
        "verified_outcome_ingestion_writer_execution_must_not_persist_verdict",
        "verified_outcome_ingestion_writer_execution_writer_scope_mismatch",
        "verified_outcome_ingestion_writer_execution_digest_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_writer_execution_output_only(&execution);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution_requires_writer(
) {
    let apply = ready_runtime_executor_verified_outcome_ingestion_apply_gate();
    let execution =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution(
            &json!({
                "verified_outcome_ingestion_writer": apply,
                "verified_outcome_ingestion_writer_execution_decision":
                    explicit_verified_outcome_ingestion_writer_execution_decision()
            }),
        );

    assert_eq!(
        execution["input_kind"],
        "verified_outcome_ingestion_writer_with_execution_decision_wrapper"
    );
    assert_eq!(
        execution["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_GATE_SCHEMA
    );
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution_verdict"],
        "blocked"
    );
    assert_eq!(
        execution["reason"],
        "runtime_executor_verified_outcome_ingestion_writer_required"
    );
    assert_eq!(
        execution["source_verified_outcome_ingestion_writer"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_writer_execution_output_only(&execution);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence_blocks_without_decision(
) {
    let execution = ready_runtime_executor_verified_outcome_ingestion_writer_execution();
    let persistence =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence(
            &execution,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence(
            &persistence,
        );

    assert_eq!(
        persistence["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_PERSISTENCE_SCHEMA
    );
    assert_eq!(
        persistence["input_kind"],
        "runtime_executor_verified_outcome_ingestion_writer_execution"
    );
    assert_eq!(
        persistence["source_verified_outcome_ingestion_writer_execution_verdict"],
        "ready_for_verified_outcome_ingestion_persistence"
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence_decision_schema"],
        Value::Null
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence_verdict"],
        "blocked"
    );
    assert_eq!(
        persistence["reason"],
        "explicit_verified_outcome_ingestion_persistence_decision_required"
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence"]
            ["ready_for_verified_outcome_ingestion_store_write"],
        false
    );
    assert_runtime_executor_verified_outcome_ingestion_persistence_output_only(&persistence);

    assert!(markdown.contains("- verified_outcome_ingestion_persistence_verdict: `blocked`"));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_store_write: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence_accepts_explicit_decision(
) {
    let execution = ready_runtime_executor_verified_outcome_ingestion_writer_execution();
    let persistence =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence(
            &json!({
                "verified_outcome_ingestion_writer_execution": execution,
                "verified_outcome_ingestion_persistence_decision":
                    explicit_verified_outcome_ingestion_persistence_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence(
            &persistence,
        );

    assert_eq!(
        persistence["verified_outcome_ingestion_persistence_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_PERSISTENCE_DECISION_SCHEMA
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence_verdict"],
        "ready_for_verified_outcome_ingestion_store_write",
        "failure_reasons={}",
        persistence["failure_reasons"]
    );
    assert_eq!(
        persistence["reason"],
        "verified_outcome_ingestion_persistence_ready_for_store_write"
    );
    assert_eq!(persistence["failure_reasons"], json!([]));
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence"]["persistence_decision_id"],
        "verified_outcome_ingestion_persistence_arrival_bath_move_002"
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence"]["persistence_source_execution_id"],
        "verified_outcome_ingestion_writer_execution_arrival_bath_move_002"
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence"]["previous_world_verdict"],
        "not_verified"
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence"]["verified_world_verdict"],
        "verified"
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence"]
            ["ready_for_verified_outcome_ingestion_store_write"],
        true
    );
    assert_eq!(
        persistence["next_allowed_gate"],
        "verified_outcome_ingestion_store_write"
    );
    assert_runtime_executor_verified_outcome_ingestion_persistence_output_only(&persistence);

    assert!(markdown.contains(
        "- verified_outcome_ingestion_persistence_verdict: `ready_for_verified_outcome_ingestion_store_write`"
    ));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence_blocks_bad_decision(
) {
    let execution = ready_runtime_executor_verified_outcome_ingestion_writer_execution();
    let mut decision = explicit_verified_outcome_ingestion_persistence_decision();
    decision["persistence_kind"] = json!("operator_note");
    decision["decision"] = json!("write_now");
    decision["source_world_verdict"] = json!("verified");
    decision["verified_world_verdict"] = json!("not_verified");
    decision["reviewed_verified_outcome_ingestion_writer_execution_verdict"] = json!("blocked");
    decision["writer_execution_package_confirmed"] = json!(false);
    decision["writer_package_confirmed"] = json!(false);
    decision["verified_outcome_package_confirmed"] = json!(false);
    decision["persistence_target_verified"] = json!(false);
    decision["outcome_record_digest_verified"] = json!(false);
    decision["idempotent_upsert_confirmed"] = json!(false);
    decision["store_transaction_plan_complete"] = json!(false);
    decision["rollback_plan_confirmed"] = json!(false);
    decision["write_destination"] = Value::Null;
    decision["outcome_record_key"] = Value::Null;
    decision["outcome_record_digest"] = Value::Null;
    decision["verified_outcome_store_write_allowed"] = json!(true);
    decision["outcome_ingestion_allowed_by_this_tool"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["verified_outcome_ingested_by_this_tool"] = json!(true);
    decision["durable_outcome_record_written_by_this_tool"] = json!(true);
    decision["world_verdict_persisted_by_this_tool"] = json!(true);
    decision["source_verified_outcome_ingestion_writer_execution_scope"]
        ["persistence_source_execution_id"] = json!("other_execution");
    decision["source_verified_outcome_ingestion_writer_execution_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let persistence =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence(
            &json!({
                "verified_outcome_ingestion_writer_execution": execution,
                "verified_outcome_ingestion_persistence_decision": decision
            }),
        );

    assert_eq!(
        persistence["verified_outcome_ingestion_persistence_verdict"],
        "blocked"
    );
    let failure_reasons = persistence["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_persistence_kind_required",
        "verified_outcome_ingestion_persistence_decision_not_approved",
        "verified_outcome_ingestion_persistence_source_must_be_not_verified",
        "verified_outcome_ingestion_persistence_verdict_must_be_verified",
        "verified_outcome_ingestion_persistence_must_review_ready_g23_execution",
        "verified_outcome_ingestion_persistence_requires_writer_execution_package",
        "verified_outcome_ingestion_persistence_requires_writer_package",
        "verified_outcome_ingestion_persistence_requires_verified_package",
        "verified_outcome_ingestion_persistence_requires_target_verification",
        "verified_outcome_ingestion_persistence_requires_digest_verification",
        "verified_outcome_ingestion_persistence_requires_idempotent_upsert",
        "verified_outcome_ingestion_persistence_requires_transaction_plan",
        "verified_outcome_ingestion_persistence_requires_rollback_plan",
        "verified_outcome_ingestion_persistence_destination_required",
        "verified_outcome_ingestion_persistence_key_required",
        "verified_outcome_ingestion_persistence_digest_required",
        "verified_outcome_ingestion_persistence_must_not_allow_store_write",
        "verified_outcome_ingestion_persistence_must_not_allow_ingestion_by_this_tool",
        "verified_outcome_ingestion_persistence_must_not_allow_memory_write",
        "verified_outcome_ingestion_persistence_must_not_ingest_outcome",
        "verified_outcome_ingestion_persistence_must_not_write_outcome_record",
        "verified_outcome_ingestion_persistence_must_not_persist_verdict",
        "verified_outcome_ingestion_persistence_execution_scope_mismatch",
        "verified_outcome_ingestion_persistence_digest_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_persistence_output_only(&persistence);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence_requires_execution()
{
    let writer = ready_runtime_executor_verified_outcome_ingestion_writer();
    let persistence =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence(
            &json!({
                "verified_outcome_ingestion_writer_execution": writer,
                "verified_outcome_ingestion_persistence_decision":
                    explicit_verified_outcome_ingestion_persistence_decision()
            }),
        );

    assert_eq!(
        persistence["input_kind"],
        "verified_outcome_ingestion_writer_execution_with_persistence_decision_wrapper"
    );
    assert_eq!(
        persistence["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_SCHEMA
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence_verdict"],
        "blocked"
    );
    assert_eq!(
        persistence["reason"],
        "runtime_executor_verified_outcome_ingestion_writer_execution_required"
    );
    assert_eq!(
        persistence["source_verified_outcome_ingestion_writer_execution"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_persistence_output_only(&persistence);
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_blocks_without_decision(
) {
    let persistence = ready_runtime_executor_verified_outcome_ingestion_persistence();
    let preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
            &persistence,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
            &preflight,
        );

    assert_eq!(
        preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        preflight["input_kind"],
        "runtime_executor_verified_outcome_ingestion_persistence"
    );
    assert_eq!(
        preflight["source_verified_outcome_ingestion_persistence_verdict"],
        "ready_for_verified_outcome_ingestion_store_write"
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution_decision_schema"],
        Value::Null
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        preflight["reason"],
        "explicit_verified_outcome_ingestion_store_write_execution_decision_required"
    );
    assert_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_output_only(
        &preflight,
    );

    assert!(markdown.contains(
        "- verified_outcome_ingestion_store_write_execution_preflight_verdict: `blocked`"
    ));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_write_evidence: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_accepts_explicit_decision(
) {
    let persistence = ready_runtime_executor_verified_outcome_ingestion_persistence();
    let preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
            &json!({
                "verified_outcome_ingestion_persistence": persistence,
                "verified_outcome_ingestion_store_write_execution_decision":
                    explicit_verified_outcome_ingestion_store_write_execution_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
            &preflight,
        );

    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_STORE_WRITE_EXECUTION_DECISION_SCHEMA
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_write_evidence",
        "failure_reasons={}",
        preflight["failure_reasons"]
    );
    assert_eq!(
        preflight["reason"],
        "verified_outcome_ingestion_store_write_execution_preflight_ready_for_write_evidence"
    );
    assert_eq!(preflight["failure_reasons"], json!([]));
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution"]["store_write_execution_id"],
        "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002"
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution"]["persistence_decision_id"],
        "verified_outcome_ingestion_persistence_arrival_bath_move_002"
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution"]["decision"],
        "approved_for_verified_outcome_ingestion_write_evidence"
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution"]
            ["ready_for_verified_outcome_ingestion_write_evidence"],
        true
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution"]
            ["verified_outcome_store_write_execution_allowed"],
        false
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution"]
            ["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["next_allowed_gate"],
        "verified_outcome_ingestion_write_evidence"
    );
    assert_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_output_only(
        &preflight,
    );

    assert!(markdown.contains(
        "- verified_outcome_ingestion_store_write_execution_preflight_verdict: `ready_for_verified_outcome_ingestion_write_evidence`"
    ));
    assert!(
        markdown.contains("- decision: `approved_for_verified_outcome_ingestion_write_evidence`")
    );
    assert!(markdown.contains("- verified_outcome_store_write_execution_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_blocks_bad_decision(
) {
    let persistence = ready_runtime_executor_verified_outcome_ingestion_persistence();
    let mut decision = explicit_verified_outcome_ingestion_store_write_execution_decision();
    decision["store_write_execution_kind"] = json!("operator_note");
    decision["decision"] = json!("write_now");
    decision["source_world_verdict"] = json!("verified");
    decision["verified_world_verdict"] = json!("not_verified");
    decision["reviewed_verified_outcome_ingestion_persistence_verdict"] = json!("blocked");
    decision["persistence_package_confirmed"] = json!(false);
    decision["writer_execution_package_confirmed"] = json!(false);
    decision["verified_outcome_package_confirmed"] = json!(false);
    decision["persistence_target_verified"] = json!(false);
    decision["outcome_record_digest_verified"] = json!(false);
    decision["idempotent_upsert_confirmed"] = json!(false);
    decision["store_transaction_plan_complete"] = json!(false);
    decision["rollback_plan_confirmed"] = json!(false);
    decision["write_destination"] = Value::Null;
    decision["outcome_record_key"] = Value::Null;
    decision["outcome_record_digest"] = Value::Null;
    decision["verified_outcome_store_write_execution_allowed"] = json!(true);
    decision["verified_outcome_store_written_by_this_tool"] = json!(true);
    decision["outcome_ingestion_allowed_by_this_tool"] = json!(true);
    decision["memory_write_allowed"] = json!(true);
    decision["verified_outcome_ingested_by_this_tool"] = json!(true);
    decision["durable_outcome_record_written_by_this_tool"] = json!(true);
    decision["world_verdict_persisted_by_this_tool"] = json!(true);
    decision["source_verified_outcome_ingestion_persistence_scope"]["persistence_decision_id"] =
        json!("other_persistence");
    decision["source_verified_outcome_ingestion_persistence_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
            &json!({
                "verified_outcome_ingestion_persistence": persistence,
                "verified_outcome_ingestion_store_write_execution_decision": decision
            }),
        );

    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_store_write_execution_kind_required",
        "verified_outcome_ingestion_store_write_execution_decision_not_approved",
        "verified_outcome_ingestion_store_write_execution_source_must_be_not_verified",
        "verified_outcome_ingestion_store_write_execution_verdict_must_be_verified",
        "verified_outcome_ingestion_store_write_execution_must_review_ready_g24_persistence",
        "verified_outcome_ingestion_store_write_execution_requires_persistence_package",
        "verified_outcome_ingestion_store_write_execution_requires_writer_execution_package",
        "verified_outcome_ingestion_store_write_execution_requires_verified_package",
        "verified_outcome_ingestion_store_write_execution_requires_target_verification",
        "verified_outcome_ingestion_store_write_execution_requires_digest_verification",
        "verified_outcome_ingestion_store_write_execution_requires_idempotent_upsert",
        "verified_outcome_ingestion_store_write_execution_requires_transaction_plan",
        "verified_outcome_ingestion_store_write_execution_requires_rollback_plan",
        "verified_outcome_ingestion_store_write_execution_destination_required",
        "verified_outcome_ingestion_store_write_execution_key_required",
        "verified_outcome_ingestion_store_write_execution_digest_required",
        "verified_outcome_ingestion_store_write_execution_must_not_allow_execution",
        "verified_outcome_ingestion_store_write_execution_must_not_write_store",
        "verified_outcome_ingestion_store_write_execution_must_not_allow_ingestion_by_this_tool",
        "verified_outcome_ingestion_store_write_execution_must_not_allow_memory_write",
        "verified_outcome_ingestion_store_write_execution_must_not_ingest_outcome",
        "verified_outcome_ingestion_store_write_execution_must_not_write_outcome_record",
        "verified_outcome_ingestion_store_write_execution_must_not_persist_verdict",
        "verified_outcome_ingestion_store_write_execution_persistence_scope_mismatch",
        "verified_outcome_ingestion_store_write_execution_digest_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_output_only(
        &preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_requires_persistence(
) {
    let execution = ready_runtime_executor_verified_outcome_ingestion_writer_execution();
    let preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
            &json!({
                "verified_outcome_ingestion_persistence": execution,
                "verified_outcome_ingestion_store_write_execution_decision":
                    explicit_verified_outcome_ingestion_store_write_execution_decision()
            }),
        );

    assert_eq!(
        preflight["input_kind"],
        "verified_outcome_ingestion_persistence_with_store_write_execution_decision_wrapper"
    );
    assert_eq!(
        preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_EXECUTION_SCHEMA
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_store_write_execution_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        preflight["reason"],
        "runtime_executor_verified_outcome_ingestion_persistence_required"
    );
    assert_eq!(
        preflight["source_verified_outcome_ingestion_persistence"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_output_only(
        &preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_blocks_without_evidence(
) {
    let store_write_preflight =
        ready_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight();
    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight(
            &store_write_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight(
            &write_evidence_preflight,
        );

    assert_eq!(
        write_evidence_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        write_evidence_preflight["input_kind"],
        "runtime_executor_verified_outcome_ingestion_store_write_execution_preflight"
    );
    assert_eq!(
        write_evidence_preflight
            ["source_verified_outcome_ingestion_store_write_execution_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_write_evidence"
    );
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence_preflight_verdict"],
        "blocked"
    );
    assert_eq!(write_evidence_preflight["status"], "blocked");
    assert_eq!(
        write_evidence_preflight["reason"],
        "explicit_verified_outcome_ingestion_write_evidence_required"
    );
    assert_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_output_only(
        &write_evidence_preflight,
    );
    assert!(markdown
        .contains("- verified_outcome_ingestion_write_evidence_preflight_verdict: `blocked`"));
    assert!(
        markdown.contains("- ready_for_verified_outcome_ingestion_write_evidence_review: `false`")
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_accepts_explicit_evidence(
) {
    let store_write_preflight =
        ready_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight();
    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight(
            &json!({
                "verified_outcome_ingestion_store_write_execution_preflight": store_write_preflight,
                "verified_outcome_ingestion_write_evidence":
                    explicit_verified_outcome_ingestion_write_evidence()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight(
            &write_evidence_preflight,
        );

    assert_eq!(
        write_evidence_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_SCHEMA
    );
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_write_evidence_review",
        "failure_reasons={}",
        write_evidence_preflight["failure_reasons"]
    );
    assert_eq!(
        write_evidence_preflight["reason"],
        "verified_outcome_ingestion_write_evidence_preflight_ready_for_evidence_review"
    );
    assert_eq!(write_evidence_preflight["failure_reasons"], json!([]));
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence"]["write_evidence_id"],
        "verified_outcome_ingestion_write_evidence_arrival_bath_move_002"
    );
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence"]
            ["store_write_execution_id"],
        "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002"
    );
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence"]
            ["source_write_evidence_id"],
        "durable_outcome_record_write_evidence_arrival_bath_move_002"
    );
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence"]
            ["ready_for_verified_outcome_ingestion_write_evidence_review"],
        true
    );
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence"]
            ["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(
        write_evidence_preflight["next_allowed_gate"],
        "verified_outcome_ingestion_write_evidence_review"
    );
    assert_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_output_only(
        &write_evidence_preflight,
    );
    assert!(markdown.contains(
        "- verified_outcome_ingestion_write_evidence_preflight_verdict: `ready_for_verified_outcome_ingestion_write_evidence_review`"
    ));
    assert!(markdown.contains("- evidence_kind: `verified_outcome_ingestion_write_evidence`"));
    assert!(markdown.contains("- verified_outcome_store_written_by_this_tool: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_blocks_bad_evidence(
) {
    let store_write_preflight =
        ready_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight();
    let mut evidence = explicit_verified_outcome_ingestion_write_evidence();
    evidence["evidence_kind"] = json!("operator_note");
    evidence["source_world_verdict"] = json!("verified");
    evidence["verified_world_verdict"] = json!("not_verified");
    evidence["reviewed_store_write_execution_decision"] = json!("write_now");
    evidence["verified_outcome_store_write_observed"] = json!(false);
    evidence["store_write_acknowledged"] = json!(false);
    evidence["record_readback_verified"] = json!(false);
    evidence["outcome_record_digest_verified"] = json!(false);
    evidence["idempotency_key_confirmed"] = json!(false);
    evidence["write_destination"] = Value::Null;
    evidence["outcome_record_key"] = Value::Null;
    evidence["outcome_record_digest"] = Value::Null;
    evidence["persisted_outcome_record_key"] = json!("other-key");
    evidence["persisted_outcome_record_digest"] = json!("sha256:other");
    evidence["verified_outcome_store_written_by_this_tool"] = json!(true);
    evidence["memory_write_allowed"] = json!(true);
    evidence["outcome_ingestion_allowed_by_this_tool"] = json!(true);
    evidence["verified_outcome_ingested_by_this_tool"] = json!(true);
    evidence["durable_outcome_record_written_by_this_tool"] = json!(true);
    evidence["world_verdict_persisted_by_this_tool"] = json!(true);
    evidence["source_verified_outcome_ingestion_store_write_execution_scope"]
        ["store_write_execution_id"] = json!("other_store_write");
    evidence["source_verified_outcome_ingestion_store_write_execution_scope"]
        ["outcome_record_digest"] = json!("sha256:other");

    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight(
            &json!({
                "verified_outcome_ingestion_store_write_execution_preflight": store_write_preflight,
                "verified_outcome_ingestion_write_evidence": evidence
            }),
        );

    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = write_evidence_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_write_evidence_kind_required",
        "verified_outcome_ingestion_write_evidence_source_must_be_not_verified",
        "verified_outcome_ingestion_write_evidence_verdict_must_be_verified",
        "verified_outcome_ingestion_write_evidence_must_review_approved_store_write_execution",
        "verified_outcome_ingestion_write_evidence_requires_store_write_observed",
        "verified_outcome_ingestion_write_evidence_requires_store_ack",
        "verified_outcome_ingestion_write_evidence_requires_readback",
        "verified_outcome_ingestion_write_evidence_requires_digest_verification",
        "verified_outcome_ingestion_write_evidence_requires_idempotency",
        "verified_outcome_ingestion_write_evidence_destination_required",
        "verified_outcome_ingestion_write_evidence_key_required",
        "verified_outcome_ingestion_write_evidence_digest_required",
        "verified_outcome_ingestion_write_evidence_persisted_key_mismatch",
        "verified_outcome_ingestion_write_evidence_persisted_digest_mismatch",
        "verified_outcome_ingestion_write_evidence_must_not_write_store_by_this_tool",
        "verified_outcome_ingestion_write_evidence_must_not_allow_memory_write",
        "verified_outcome_ingestion_write_evidence_must_not_allow_ingestion_by_this_tool",
        "verified_outcome_ingestion_write_evidence_must_not_ingest_outcome",
        "verified_outcome_ingestion_write_evidence_must_not_write_outcome_record",
        "verified_outcome_ingestion_write_evidence_must_not_persist_verdict",
        "verified_outcome_ingestion_write_evidence_store_write_execution_scope_mismatch",
        "verified_outcome_ingestion_write_evidence_digest_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_output_only(
        &write_evidence_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_requires_store_write_preflight(
) {
    let persistence = ready_runtime_executor_verified_outcome_ingestion_persistence();
    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight(
            &json!({
                "verified_outcome_ingestion_store_write_execution_preflight": persistence,
                "verified_outcome_ingestion_write_evidence":
                    explicit_verified_outcome_ingestion_write_evidence()
            }),
        );

    assert_eq!(
        write_evidence_preflight["input_kind"],
        "verified_outcome_ingestion_store_write_execution_preflight_with_write_evidence_wrapper"
    );
    assert_eq!(
        write_evidence_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_PERSISTENCE_SCHEMA
    );
    assert_eq!(
        write_evidence_preflight["verified_outcome_ingestion_write_evidence_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        write_evidence_preflight["reason"],
        "runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_required"
    );
    assert_eq!(
        write_evidence_preflight
            ["source_verified_outcome_ingestion_store_write_execution_preflight"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_output_only(
        &write_evidence_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_blocks_without_review(
) {
    let write_evidence_preflight =
        ready_runtime_executor_verified_outcome_ingestion_write_evidence_preflight();
    let review_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight(
            &write_evidence_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight(
            &review_preflight,
        );

    assert_eq!(
        review_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        review_preflight["input_kind"],
        "runtime_executor_verified_outcome_ingestion_write_evidence_preflight"
    );
    assert_eq!(
        review_preflight["source_verified_outcome_ingestion_write_evidence_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_write_evidence_review"
    );
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review_decision_schema"],
        Value::Null
    );
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        review_preflight["reason"],
        "explicit_verified_outcome_ingestion_write_evidence_review_decision_required"
    );
    assert_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_output_only(
        &review_preflight,
    );
    assert!(markdown.contains(
        "- verified_outcome_ingestion_write_evidence_review_preflight_verdict: `blocked`"
    ));
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_admission: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_accepts_explicit_review(
) {
    let write_evidence_preflight =
        ready_runtime_executor_verified_outcome_ingestion_write_evidence_preflight();
    let review_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight(
            &json!({
                "verified_outcome_ingestion_write_evidence_preflight": write_evidence_preflight,
                "verified_outcome_ingestion_write_evidence_review_decision":
                    explicit_verified_outcome_ingestion_write_evidence_review_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight(
            &review_preflight,
        );

    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_REVIEW_DECISION_SCHEMA
    );
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_admission",
        "failure_reasons={}",
        review_preflight["failure_reasons"]
    );
    assert_eq!(
        review_preflight["reason"],
        "verified_outcome_ingestion_write_evidence_review_preflight_ready_for_admission"
    );
    assert_eq!(review_preflight["failure_reasons"], json!([]));
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review"]["review_decision_id"],
        "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002"
    );
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review"]["write_evidence_id"],
        "verified_outcome_ingestion_write_evidence_arrival_bath_move_002"
    );
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review"]["decision"],
        "approved_for_verified_outcome_ingestion_admission"
    );
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review"]
            ["ready_for_verified_outcome_ingestion_admission"],
        true
    );
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review"]
            ["verified_outcome_admission_allowed"],
        false
    );
    assert_eq!(
        review_preflight["next_allowed_gate"],
        "verified_outcome_ingestion_admission"
    );
    assert_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_output_only(
        &review_preflight,
    );
    assert!(markdown.contains(
        "- verified_outcome_ingestion_write_evidence_review_preflight_verdict: `ready_for_verified_outcome_ingestion_admission`"
    ));
    assert!(markdown.contains("- decision: `approved_for_verified_outcome_ingestion_admission`"));
    assert!(markdown.contains("- verified_outcome_admission_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_blocks_bad_review(
) {
    let write_evidence_preflight =
        ready_runtime_executor_verified_outcome_ingestion_write_evidence_preflight();
    let mut review = explicit_verified_outcome_ingestion_write_evidence_review_decision();
    review["review_kind"] = json!("operator_note");
    review["decision"] = json!("admit_now");
    review["source_world_verdict"] = json!("verified");
    review["verified_world_verdict"] = json!("not_verified");
    review["reviewed_write_evidence_preflight_verdict"] = json!("blocked");
    review["verified_outcome_store_write_confirmed"] = json!(false);
    review["store_ack_confirmed"] = json!(false);
    review["record_readback_confirmed"] = json!(false);
    review["outcome_record_digest_confirmed"] = json!(false);
    review["idempotency_key_confirmed"] = json!(false);
    review["persisted_key_confirmed"] = json!(false);
    review["persisted_digest_confirmed"] = json!(false);
    review["reviewer_attestation_present"] = json!(false);
    review["verified_outcome_admission_allowed"] = json!(true);
    review["outcome_ingestion_allowed_by_this_tool"] = json!(true);
    review["memory_write_allowed"] = json!(true);
    review["world_verdict_persisted_by_this_tool"] = json!(true);
    review["verified_outcome_ingested_by_this_tool"] = json!(true);
    review["verified_outcome_store_written_by_this_tool"] = json!(true);
    review["durable_outcome_record_written_by_this_tool"] = json!(true);
    review["source_verified_outcome_ingestion_write_evidence_scope"]["write_evidence_id"] =
        json!("other_evidence");
    review["source_verified_outcome_ingestion_write_evidence_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let review_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight(
            &json!({
                "verified_outcome_ingestion_write_evidence_preflight": write_evidence_preflight,
                "verified_outcome_ingestion_write_evidence_review_decision": review
            }),
        );

    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = review_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_write_evidence_review_kind_required",
        "verified_outcome_ingestion_write_evidence_review_decision_not_approved",
        "verified_outcome_ingestion_write_evidence_review_must_preserve_not_verified_source",
        "verified_outcome_ingestion_write_evidence_review_must_preserve_verified_verdict",
        "verified_outcome_ingestion_write_evidence_review_must_review_ready_preflight",
        "verified_outcome_ingestion_write_evidence_review_requires_store_write_confirmation",
        "verified_outcome_ingestion_write_evidence_review_requires_store_ack",
        "verified_outcome_ingestion_write_evidence_review_requires_readback",
        "verified_outcome_ingestion_write_evidence_review_requires_digest_confirmation",
        "verified_outcome_ingestion_write_evidence_review_requires_idempotency",
        "verified_outcome_ingestion_write_evidence_review_requires_persisted_key",
        "verified_outcome_ingestion_write_evidence_review_requires_persisted_digest",
        "verified_outcome_ingestion_write_evidence_review_requires_reviewer_attestation",
        "verified_outcome_ingestion_write_evidence_review_must_not_allow_admission",
        "verified_outcome_ingestion_write_evidence_review_must_not_allow_ingestion_by_this_tool",
        "verified_outcome_ingestion_write_evidence_review_must_not_allow_memory_write",
        "verified_outcome_ingestion_write_evidence_review_must_not_persist_verdict",
        "verified_outcome_ingestion_write_evidence_review_must_not_ingest",
        "verified_outcome_ingestion_write_evidence_review_must_not_write_store_by_this_tool",
        "verified_outcome_ingestion_write_evidence_review_must_not_write_outcome_record",
        "verified_outcome_ingestion_write_evidence_review_evidence_scope_mismatch",
        "verified_outcome_ingestion_write_evidence_review_digest_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_output_only(
        &review_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_requires_write_evidence_preflight(
) {
    let store_write_preflight =
        ready_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight();
    let review_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight(
            &json!({
                "verified_outcome_ingestion_write_evidence_preflight": store_write_preflight,
                "verified_outcome_ingestion_write_evidence_review_decision":
                    explicit_verified_outcome_ingestion_write_evidence_review_decision()
            }),
        );

    assert_eq!(
        review_preflight["input_kind"],
        "verified_outcome_ingestion_write_evidence_preflight_with_review_decision_wrapper"
    );
    assert_eq!(
        review_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        review_preflight["verified_outcome_ingestion_write_evidence_review_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        review_preflight["reason"],
        "runtime_executor_verified_outcome_ingestion_write_evidence_preflight_required"
    );
    assert_eq!(
        review_preflight["source_verified_outcome_ingestion_write_evidence_preflight"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_output_only(
        &review_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight_blocks_without_admission_decision(
) {
    let review_preflight =
        ready_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight();
    let admission_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
            &review_preflight,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
            &admission_preflight,
        );

    assert_eq!(
        admission_preflight["schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_ADMISSION_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        admission_preflight["input_kind"],
        "runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight"
    );
    assert_eq!(
        admission_preflight
            ["source_verified_outcome_ingestion_write_evidence_review_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_admission"
    );
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission_decision_schema"],
        Value::Null
    );
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        admission_preflight["reason"],
        "explicit_verified_outcome_ingestion_admission_decision_required"
    );
    assert_runtime_executor_verified_outcome_ingestion_admission_preflight_output_only(
        &admission_preflight,
    );
    assert!(
        markdown.contains("- verified_outcome_ingestion_admission_preflight_verdict: `blocked`")
    );
    assert!(markdown.contains("- ready_for_verified_outcome_ingestion_execution: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight_accepts_explicit_decision(
) {
    let review_preflight =
        ready_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight();
    let admission_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
            &json!({
                "verified_outcome_ingestion_write_evidence_review_preflight": review_preflight,
                "verified_outcome_ingestion_admission_decision":
                    explicit_verified_outcome_ingestion_admission_decision()
            }),
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
            &admission_preflight,
        );

    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission_decision_schema"],
        LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_ADMISSION_DECISION_SCHEMA
    );
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission_preflight_verdict"],
        "ready_for_verified_outcome_ingestion_execution",
        "failure_reasons={}",
        admission_preflight["failure_reasons"]
    );
    assert_eq!(
        admission_preflight["reason"],
        "verified_outcome_ingestion_admission_preflight_ready_for_execution"
    );
    assert_eq!(admission_preflight["failure_reasons"], json!([]));
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission"]["admission_decision_id"],
        "verified_outcome_ingestion_admission_arrival_bath_move_002"
    );
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission"]["review_decision_id"],
        "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002"
    );
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission"]["decision"],
        "approved_for_verified_outcome_ingestion_execution"
    );
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission"]
            ["ready_for_verified_outcome_ingestion_execution"],
        true
    );
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission"]
            ["verified_outcome_ingestion_execution_allowed"],
        false
    );
    assert_eq!(
        admission_preflight["next_allowed_gate"],
        "verified_outcome_ingestion_execution"
    );
    assert_runtime_executor_verified_outcome_ingestion_admission_preflight_output_only(
        &admission_preflight,
    );
    assert!(markdown.contains(
        "- verified_outcome_ingestion_admission_preflight_verdict: `ready_for_verified_outcome_ingestion_execution`"
    ));
    assert!(markdown.contains("- decision: `approved_for_verified_outcome_ingestion_execution`"));
    assert!(markdown.contains("- verified_outcome_ingestion_execution_allowed: `false`"));
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight_blocks_bad_decision(
) {
    let review_preflight =
        ready_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight();
    let mut admission = explicit_verified_outcome_ingestion_admission_decision();
    admission["admission_kind"] = json!("operator_note");
    admission["decision"] = json!("execute_now");
    admission["source_world_verdict"] = json!("verified");
    admission["verified_world_verdict"] = json!("not_verified");
    admission["reviewed_admission_preflight_verdict"] = json!("blocked");
    admission["write_evidence_review_preflight_confirmed"] = json!(false);
    admission["write_evidence_review_decision_confirmed"] = json!(false);
    admission["verified_outcome_store_write_confirmed"] = json!(false);
    admission["store_ack_confirmed"] = json!(false);
    admission["record_readback_confirmed"] = json!(false);
    admission["outcome_record_digest_confirmed"] = json!(false);
    admission["idempotency_key_confirmed"] = json!(false);
    admission["persisted_key_confirmed"] = json!(false);
    admission["persisted_digest_confirmed"] = json!(false);
    admission["operator_attestation_present"] = json!(false);
    admission["verified_outcome_ingestion_execution_allowed"] = json!(true);
    admission["outcome_ingestion_allowed_by_this_tool"] = json!(true);
    admission["memory_write_allowed"] = json!(true);
    admission["world_verdict_persisted_by_this_tool"] = json!(true);
    admission["verified_outcome_ingested_by_this_tool"] = json!(true);
    admission["verified_outcome_store_written_by_this_tool"] = json!(true);
    admission["durable_outcome_record_written_by_this_tool"] = json!(true);
    admission["source_verified_outcome_ingestion_admission_scope"]["review_decision_id"] =
        json!("other_review");
    admission["source_verified_outcome_ingestion_admission_scope"]["outcome_record_digest"] =
        json!("sha256:other");

    let admission_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
            &json!({
                "verified_outcome_ingestion_write_evidence_review_preflight": review_preflight,
                "verified_outcome_ingestion_admission_decision": admission
            }),
        );

    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission_preflight_verdict"],
        "blocked"
    );
    let failure_reasons = admission_preflight["failure_reasons"]
        .as_array()
        .expect("failure reasons");
    for reason in [
        "verified_outcome_ingestion_admission_kind_required",
        "verified_outcome_ingestion_admission_decision_not_approved",
        "verified_outcome_ingestion_admission_must_preserve_not_verified_source",
        "verified_outcome_ingestion_admission_must_preserve_verified_verdict",
        "verified_outcome_ingestion_admission_must_review_ready_preflight",
        "verified_outcome_ingestion_admission_requires_review_preflight_confirmation",
        "verified_outcome_ingestion_admission_requires_review_decision_confirmation",
        "verified_outcome_ingestion_admission_requires_store_write_confirmation",
        "verified_outcome_ingestion_admission_requires_store_ack",
        "verified_outcome_ingestion_admission_requires_readback",
        "verified_outcome_ingestion_admission_requires_digest_confirmation",
        "verified_outcome_ingestion_admission_requires_idempotency",
        "verified_outcome_ingestion_admission_requires_persisted_key",
        "verified_outcome_ingestion_admission_requires_persisted_digest",
        "verified_outcome_ingestion_admission_requires_operator_attestation",
        "verified_outcome_ingestion_admission_must_not_allow_execution",
        "verified_outcome_ingestion_admission_must_not_allow_ingestion_by_this_tool",
        "verified_outcome_ingestion_admission_must_not_allow_memory_write",
        "verified_outcome_ingestion_admission_must_not_persist_verdict",
        "verified_outcome_ingestion_admission_must_not_ingest",
        "verified_outcome_ingestion_admission_must_not_write_store_by_this_tool",
        "verified_outcome_ingestion_admission_must_not_write_outcome_record",
        "verified_outcome_ingestion_admission_review_decision_scope_mismatch",
        "verified_outcome_ingestion_admission_digest_scope_mismatch",
    ] {
        assert!(failure_reasons.contains(&json!(reason)), "{reason}");
    }
    assert_runtime_executor_verified_outcome_ingestion_admission_preflight_output_only(
        &admission_preflight,
    );
}

#[test]
fn interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight_requires_review_preflight(
) {
    let write_evidence_preflight =
        ready_runtime_executor_verified_outcome_ingestion_write_evidence_preflight();
    let admission_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
            &json!({
                "verified_outcome_ingestion_write_evidence_review_preflight": write_evidence_preflight,
                "verified_outcome_ingestion_admission_decision":
                    explicit_verified_outcome_ingestion_admission_decision()
            }),
        );

    assert_eq!(
        admission_preflight["input_kind"],
        "verified_outcome_ingestion_write_evidence_review_preflight_with_admission_decision_wrapper"
    );
    assert_eq!(
        admission_preflight["source_schema"],
        LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_PREFLIGHT_SCHEMA
    );
    assert_eq!(
        admission_preflight["verified_outcome_ingestion_admission_preflight_verdict"],
        "blocked"
    );
    assert_eq!(
        admission_preflight["reason"],
        "runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_required"
    );
    assert_eq!(
        admission_preflight["source_verified_outcome_ingestion_write_evidence_review_preflight"],
        Value::Null
    );
    assert_runtime_executor_verified_outcome_ingestion_admission_preflight_output_only(
        &admission_preflight,
    );
}

#[test]
fn interaction_feedback_validator_reports_tampered_fixture() {
    let mut fixture = fixture();
    fixture["events"][5]["refs"]["cause_event_id"] = json!("missing_event");
    fixture["feedback"][0]["verification_relation"]["changes_world_verdict"] = json!(true);

    let report = validate_interaction_feedback_fixture(&fixture);

    assert!(!report.valid);
    assert!(report
        .failure_reasons
        .contains(&"cause_event_missing:missing_event".to_string()));
    assert!(report
        .failure_reasons
        .contains(&"human_reject_not_anchored_to_verification".to_string()));
    assert!(report
        .failure_reasons
        .contains(&"feedback_changes_world_verdict".to_string()));
}

#[test]
fn interaction_feedback_envelope_reports_tampered_fixture_without_panicking() {
    let mut fixture = fixture();
    fixture["schema"] = json!("wrong.schema");
    fixture["requires_screenshot_for_primary_readback"] = json!(true);

    let envelope = build_interaction_feedback_validation_envelope(&fixture);

    assert_eq!(
        envelope["schema"],
        LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA
    );
    assert_eq!(envelope["fixture_schema"], "wrong.schema");
    assert_eq!(envelope["valid"], false);
    assert!(envelope["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("schema_mismatch")));
    assert!(envelope["failure_reasons"]
        .as_array()
        .expect("failure reasons")
        .contains(&json!("primary_readback_requires_screenshot")));
    assert_eq!(envelope["guardrails"]["writes_state"], false);
    assert_eq!(envelope["guardrails"]["store_access_required"], false);
    assert_eq!(envelope["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(envelope["report"]["valid"], false);
}

#[test]
fn interaction_feedback_fixture_pretty_json_roundtrips() {
    let fixture = fixture();
    let pretty = serde_json::to_string_pretty(&fixture).expect("pretty fixture json");
    let reparsed: Value = serde_json::from_str(&pretty).expect("reparse pretty fixture json");

    assert_eq!(reparsed, fixture);
}

fn fixture() -> Value {
    serde_json::from_str(FIXTURE_JSON).expect("interaction feedback fixture json")
}

fn explicit_argument_context() -> Value {
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA,
        "world_id": "onsen_live_session",
        "branch_id": "main",
        "source": "explicit_fixture_context",
        "live_runtime_queried_by_preflight": false,
        "candidate_arguments": [{
            "argument_path": "patch.args.cell",
            "value": [5, 2],
            "satisfies_expected_effect": true,
            "evidence": {
                "walkway_clearance_cells": 2,
                "screen_area_after_estimate": 0.01,
                "source": "explicit_test_context"
            }
        }]
    })
}

fn ready_runtime_executor_design_preflight() -> Value {
    let draft = build_interaction_feedback_semantic_patch_draft(&fixture());
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": explicit_argument_context()
    }));
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    build_interaction_feedback_runtime_executor_design_preflight(&apply_request)
}

fn explicit_live_lookup_snapshot() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA,
        "runtime_family": "lswr",
        "world_id": "onsen_live_session",
        "branch_id": "main",
        "runtime_generation": "runtime_gen_1284",
        "tick": 1284,
        "lookup_read_only": true,
        "mutation_performed": false,
        "submission_performed": false,
        "application_performed": false,
        "verification_performed": false,
        "outcome_ingestion_allowed": false,
        "target_entities_present": true,
        "patch_target_still_valid": true,
        "entities_present": ["bath"],
        "entity_state": {
            "bath": {
                "entity_id": "bath",
                "space": "arrival_area",
                "cell": [4, 2],
                "visible": true
            }
        },
        "verification_ledger_cursor": "verify_patch_arrival_bath_move_001",
        "presentation_state": {
            "viewport": "onsen_live_root_viewport",
            "render_fresh": true,
            "selected_entities": ["bath"]
        }
    })
}

fn ready_runtime_executor_live_lookup_preflight() -> Value {
    build_interaction_feedback_runtime_executor_live_lookup_preflight(&json!({
        "design_preflight": ready_runtime_executor_design_preflight(),
        "lookup_snapshot": explicit_live_lookup_snapshot()
    }))
}

fn explicit_operator_submission_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA,
        "decision_id": "operator_decision_arrival_bath_move_002",
        "decision": "approved",
        "operator_id": "human:owner",
        "approved_at": "2026-06-16T06:30:00Z",
        "expires_at": "2026-06-16T23:59:59Z",
        "requested_authority": "operator_submission_token_only",
        "approved_scope": {
            "lookup_evidence_id": "live_lookup_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002"
        },
        "submission_performed": false,
        "apply_request_submitted": false,
        "patch_application_allowed": false,
        "verification_allowed": false,
        "outcome_ingestion_allowed": false,
        "writes_state": false
    })
}

fn ready_runtime_executor_operator_submission_token_preflight() -> Value {
    build_interaction_feedback_runtime_executor_operator_submission_token_preflight(&json!({
        "lookup_preflight": ready_runtime_executor_live_lookup_preflight(),
        "operator_decision": explicit_operator_submission_decision()
    }))
}

fn explicit_patch_application_gate_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_DECISION_SCHEMA,
        "decision_id": "patch_application_gate_decision_arrival_bath_move_002",
        "decision": "approved",
        "operator_id": "human:owner",
        "approved_at": "2026-06-16T07:00:00Z",
        "expires_at": "2026-06-16T23:59:59Z",
        "requested_authority": "patch_application_executor_invocation_gate_only",
        "approved_scope": {
            "token_id": "submit_patch_arrival_bath_move_002",
            "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/operator_decision_arrival_bath_move_002",
            "operator_submission_decision_id": "operator_decision_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002"
        },
        "separate_patch_executor_invocation_allowed": true,
        "executor_invocation_performed": false,
        "apply_request_submitted": false,
        "patch_application_performed": false,
        "verification_allowed": false,
        "outcome_ingestion_allowed": false,
        "writes_state": false
    })
}

fn ready_runtime_executor_patch_application_gate_preflight() -> Value {
    build_interaction_feedback_runtime_executor_patch_application_gate_preflight(&json!({
        "submission_token_preflight": ready_runtime_executor_operator_submission_token_preflight(),
        "patch_application_gate_decision": explicit_patch_application_gate_decision()
    }))
}

fn explicit_patch_executor_invocation_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_DECISION_SCHEMA,
        "decision_id": "patch_executor_invocation_decision_arrival_bath_move_002",
        "decision": "approved",
        "operator_id": "human:owner",
        "approved_at": "2026-06-16T07:30:00Z",
        "expires_at": "2026-06-16T23:59:59Z",
        "requested_authority": "separate_patch_executor_invocation_only",
        "approved_scope": {
            "gate_id": "patch_application_gate_arrival_bath_move_002",
            "gate_decision_id": "patch_application_gate_decision_arrival_bath_move_002",
            "gate_idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/submit_patch_arrival_bath_move_002/patch_application_gate_decision_arrival_bath_move_002",
            "operator_submission_token_id": "submit_patch_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002"
        },
        "separate_patch_executor_invocation_allowed": true,
        "executor_invocation_performed": false,
        "executor_queue_submission_performed": false,
        "apply_request_submitted": false,
        "patch_application_performed": false,
        "verification_allowed": false,
        "outcome_ingestion_allowed": false,
        "writes_state": false
    })
}

fn ready_runtime_executor_patch_executor_invocation_preflight() -> Value {
    build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(&json!({
        "patch_application_gate_preflight": ready_runtime_executor_patch_application_gate_preflight(),
        "patch_executor_invocation_decision": explicit_patch_executor_invocation_decision()
    }))
}

fn explicit_patch_runtime_application_evidence() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_SCHEMA,
        "evidence_id": "runtime_application_evidence_arrival_bath_move_002",
        "evidence_kind": "external_executor_claim",
        "target_executor": "separate_lswr_patch_executor",
        "executor_id": "executor:lswr_patch_worker_fixture",
        "executor_invoked_at": "2026-06-16T07:31:00Z",
        "patch_applied_at": "2026-06-16T07:31:02Z",
        "source_invocation_request_scope": {
            "request_id": "patch_executor_invocation_arrival_bath_move_002",
            "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/patch_application_gate_arrival_bath_move_002/patch_executor_invocation_decision_arrival_bath_move_002",
            "invocation_decision_id": "patch_executor_invocation_decision_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002"
        },
        "executor_invocation_observed": true,
        "patch_application_claimed": true,
        "runtime_mutation_claimed": true,
        "application_status": "applied_claimed_not_verified",
        "post_apply_verification_performed": false,
        "outcome_ingestion_allowed": false,
        "world_verdict_rewrite_allowed": false,
        "evidence_record_persisted": false
    })
}

fn ready_runtime_executor_patch_runtime_application_evidence_preflight() -> Value {
    build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
        &json!({
            "patch_executor_invocation_preflight": ready_runtime_executor_patch_executor_invocation_preflight(),
            "patch_runtime_application_evidence": explicit_patch_runtime_application_evidence()
        }),
    )
}

fn explicit_post_apply_verification_evidence() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_EVIDENCE_SCHEMA,
        "verification_id": "post_apply_verification_arrival_bath_move_002",
        "evidence_kind": "post_apply_verification",
        "verified_at": "2026-06-16T07:32:00Z",
        "source_runtime_application_evidence_scope": {
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002"
        },
        "verification_verdict": "verified",
        "verification_reason": "expected_effect_and_presentation_readback_match",
        "expected_effect_checked": true,
        "expected_effect_passed": true,
        "presentation_readback_checked": true,
        "presentation_readback_consistent": true,
        "failed_clause_ids": [],
        "outcome_ingestion_allowed": false,
        "world_verdict_rewrite_allowed": false,
        "verification_record_persisted": false
    })
}

fn ready_runtime_executor_post_apply_verification_preflight() -> Value {
    build_interaction_feedback_runtime_executor_post_apply_verification_preflight(&json!({
        "patch_runtime_application_evidence_preflight": ready_runtime_executor_patch_runtime_application_evidence_preflight(),
        "post_apply_verification_evidence": explicit_post_apply_verification_evidence()
    }))
}

fn explicit_outcome_ingestion_review_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_DECISION_SCHEMA,
        "review_id": "outcome_ingestion_review_arrival_bath_move_002",
        "review_kind": "outcome_ingestion_review",
        "reviewed_at": "2026-06-16T07:33:00Z",
        "source_post_apply_verification_scope": {
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002"
        },
        "decision": "approved_for_durable_ingestion_gate",
        "review_reason": "verified_effect_and_presentation_evidence_ready_for_durable_gate",
        "source_world_verdict": "not_verified",
        "reviewed_verification_verdict": "verified",
        "expected_effect_confirmed_for_ingestion": true,
        "presentation_readback_confirmed_for_ingestion": true,
        "durable_ingestion_allowed": false,
        "world_verdict_rewrite_allowed": false,
        "outcome_record_persisted": false
    })
}

fn ready_runtime_executor_outcome_ingestion_review_preflight() -> Value {
    build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(&json!({
        "post_apply_verification_preflight": ready_runtime_executor_post_apply_verification_preflight(),
        "outcome_ingestion_review_decision": explicit_outcome_ingestion_review_decision()
    }))
}

fn explicit_durable_outcome_ingestion_gate_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_DECISION_SCHEMA,
        "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
        "gate_kind": "durable_outcome_ingestion_gate",
        "gated_at": "2026-06-16T07:34:00Z",
        "source_outcome_ingestion_review_scope": {
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002"
        },
        "decision": "approved_for_durable_ingestion_execution",
        "gate_reason": "reviewed_outcome_ready_for_separate_durable_execution",
        "source_world_verdict": "not_verified",
        "reviewed_ingestion_review_decision": "approved_for_durable_ingestion_gate",
        "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
        "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
        "outcome_payload_complete": true,
        "durable_ingestion_execution_allowed": false,
        "world_verdict_rewrite_allowed": false,
        "outcome_record_persisted": false
    })
}

fn ready_runtime_executor_durable_outcome_ingestion_gate_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_ingestion_gate_preflight(&json!({
        "outcome_ingestion_review_preflight": ready_runtime_executor_outcome_ingestion_review_preflight(),
        "durable_outcome_ingestion_gate_decision": explicit_durable_outcome_ingestion_gate_decision()
    }))
}

fn explicit_durable_outcome_ingestion_execution_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA,
        "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
        "execution_kind": "durable_outcome_ingestion_execution",
        "execution_preflighted_at": "2026-06-16T07:35:00Z",
        "source_durable_outcome_ingestion_gate_scope": {
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002"
        },
        "decision": "approved_for_durable_outcome_ingestion_write_implementation",
        "execution_reason": "gate_ready_and_payload_scoped_for_later_durable_write_implementation",
        "source_world_verdict": "not_verified",
        "reviewed_gate_decision": "approved_for_durable_ingestion_execution",
        "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
        "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
        "outcome_payload_complete": true,
        "write_plan_complete": true,
        "durable_write_implementation_allowed": false,
        "durable_outcome_ingestion_performed": false,
        "world_verdict_rewrite_allowed": false,
        "outcome_record_persisted": false
    })
}

fn ready_runtime_executor_durable_outcome_ingestion_execution_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
        &json!({
            "durable_outcome_ingestion_gate_preflight": ready_runtime_executor_durable_outcome_ingestion_gate_preflight(),
            "durable_outcome_ingestion_execution_decision": explicit_durable_outcome_ingestion_execution_decision()
        }),
    )
}

fn explicit_durable_outcome_write_implementation_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_WRITE_IMPLEMENTATION_DECISION_SCHEMA,
        "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
        "write_implementation_kind": "durable_outcome_write_implementation",
        "write_preflighted_at": "2026-06-16T07:40:00Z",
        "source_durable_outcome_ingestion_execution_scope": {
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002"
        },
        "decision": "approved_for_durable_outcome_record_write",
        "write_reason": "execution_preflight_ready_for_later_record_write",
        "source_world_verdict": "not_verified",
        "reviewed_execution_decision": "approved_for_durable_outcome_ingestion_write_implementation",
        "outcome_record_write_plan_complete": true,
        "write_idempotency_confirmed": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "durable_record_write_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "world_verdict_rewrite_allowed": false
    })
}

fn ready_runtime_executor_durable_outcome_write_implementation_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_write_implementation_preflight(
        &json!({
            "durable_outcome_ingestion_execution_preflight": ready_runtime_executor_durable_outcome_ingestion_execution_preflight(),
            "durable_outcome_write_implementation_decision": explicit_durable_outcome_write_implementation_decision()
        }),
    )
}

fn explicit_durable_outcome_record_write_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_DECISION_SCHEMA,
        "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
        "record_write_kind": "durable_outcome_record_write",
        "record_write_preflighted_at": "2026-06-16T07:45:00Z",
        "source_durable_outcome_write_implementation_scope": {
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002"
        },
        "decision": "approved_for_durable_outcome_record_write_execution",
        "record_write_reason": "write_implementation_preflight_ready_for_later_record_write_execution",
        "source_world_verdict": "not_verified",
        "reviewed_write_implementation_decision": "approved_for_durable_outcome_record_write",
        "outcome_record_payload_complete": true,
        "outcome_record_serialization_verified": true,
        "write_idempotency_confirmed": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "durable_record_write_execution_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "world_verdict_rewrite_allowed": false
    })
}

fn ready_runtime_executor_durable_outcome_record_write_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_preflight(&json!({
        "durable_outcome_write_implementation_preflight": ready_runtime_executor_durable_outcome_write_implementation_preflight(),
        "durable_outcome_record_write_decision": explicit_durable_outcome_record_write_decision()
    }))
}

fn explicit_durable_outcome_record_write_execution_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_DECISION_SCHEMA,
        "record_write_execution_id": "durable_outcome_record_write_execution_arrival_bath_move_002",
        "record_write_execution_kind": "durable_outcome_record_write_execution",
        "record_write_execution_preflighted_at": "2026-06-16T07:50:00Z",
        "source_durable_outcome_record_write_scope": {
            "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_durable_outcome_record_persistence",
        "record_write_execution_reason": "record_write_preflight_ready_for_later_durable_persistence",
        "source_world_verdict": "not_verified",
        "reviewed_record_write_decision": "approved_for_durable_outcome_record_write_execution",
        "write_destination_verified": true,
        "outcome_record_digest_verified": true,
        "idempotent_upsert_confirmed": true,
        "store_transaction_plan_complete": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "durable_record_persistence_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "world_verdict_rewrite_allowed": false
    })
}

fn ready_runtime_executor_durable_outcome_record_write_execution_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_execution_preflight(
        &json!({
            "durable_outcome_record_write_preflight": ready_runtime_executor_durable_outcome_record_write_preflight(),
            "durable_outcome_record_write_execution_decision": explicit_durable_outcome_record_write_execution_decision()
        }),
    )
}

fn explicit_durable_outcome_record_persistence_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_DECISION_SCHEMA,
        "persistence_id": "durable_outcome_record_persistence_arrival_bath_move_002",
        "persistence_kind": "durable_outcome_record_persistence",
        "persistence_preflighted_at": "2026-06-16T07:55:00Z",
        "source_durable_outcome_record_write_execution_scope": {
            "record_write_execution_id": "durable_outcome_record_write_execution_arrival_bath_move_002",
            "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_durable_outcome_record_store_write",
        "persistence_reason": "record_write_execution_preflight_ready_for_later_store_write",
        "source_world_verdict": "not_verified",
        "reviewed_record_write_execution_decision": "approved_for_durable_outcome_record_persistence",
        "persistence_target_verified": true,
        "outcome_record_digest_verified": true,
        "idempotent_upsert_confirmed": true,
        "store_transaction_plan_complete": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "durable_store_write_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "world_verdict_rewrite_allowed": false
    })
}

fn ready_runtime_executor_durable_outcome_record_persistence_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
        &json!({
            "durable_outcome_record_write_execution_preflight": ready_runtime_executor_durable_outcome_record_write_execution_preflight(),
            "durable_outcome_record_persistence_decision": explicit_durable_outcome_record_persistence_decision()
        }),
    )
}

fn explicit_durable_outcome_record_store_write_execution_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_DECISION_SCHEMA,
        "store_write_execution_id": "durable_outcome_record_store_write_execution_arrival_bath_move_002",
        "store_write_execution_kind": "durable_outcome_record_store_write_execution",
        "store_write_execution_preflighted_at": "2026-06-16T08:00:00Z",
        "source_durable_outcome_record_persistence_scope": {
            "persistence_id": "durable_outcome_record_persistence_arrival_bath_move_002",
            "record_write_execution_id": "durable_outcome_record_write_execution_arrival_bath_move_002",
            "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_durable_outcome_record_write_evidence",
        "store_write_execution_reason": "persistence_preflight_ready_for_later_write_evidence",
        "source_world_verdict": "not_verified",
        "reviewed_persistence_decision": "approved_for_durable_outcome_record_store_write",
        "persistence_target_verified": true,
        "outcome_record_digest_verified": true,
        "idempotent_upsert_confirmed": true,
        "store_transaction_plan_complete": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "durable_store_write_execution_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "world_verdict_rewrite_allowed": false
    })
}

fn ready_runtime_executor_durable_outcome_record_store_write_execution_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_record_store_write_execution_preflight(
        &json!({
            "durable_outcome_record_persistence_preflight": ready_runtime_executor_durable_outcome_record_persistence_preflight(),
            "durable_outcome_record_store_write_execution_decision": explicit_durable_outcome_record_store_write_execution_decision()
        }),
    )
}

fn explicit_durable_outcome_record_write_evidence() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_SCHEMA,
        "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
        "evidence_kind": "durable_outcome_record_write_evidence",
        "write_evidence_observed_at": "2026-06-16T08:05:00Z",
        "source_durable_outcome_record_store_write_execution_scope": {
            "store_write_execution_id": "durable_outcome_record_store_write_execution_arrival_bath_move_002",
            "persistence_id": "durable_outcome_record_persistence_arrival_bath_move_002",
            "record_write_execution_id": "durable_outcome_record_write_execution_arrival_bath_move_002",
            "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "write_evidence_reason": "external_store_ack_and_readback_confirm_scoped_outcome_record",
        "source_world_verdict": "not_verified",
        "reviewed_store_write_execution_decision": "approved_for_durable_outcome_record_write_evidence",
        "durable_outcome_record_write_observed": true,
        "store_write_acknowledged": true,
        "record_readback_verified": true,
        "outcome_record_digest_verified": true,
        "idempotency_key_confirmed": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "durable_outcome_record_written_by_this_tool": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "world_verdict_rewrite_allowed": false
    })
}

fn ready_runtime_executor_durable_outcome_record_write_evidence_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
        &json!({
            "durable_outcome_record_store_write_execution_preflight": ready_runtime_executor_durable_outcome_record_store_write_execution_preflight(),
            "durable_outcome_record_write_evidence": explicit_durable_outcome_record_write_evidence()
        }),
    )
}

fn explicit_durable_outcome_record_write_evidence_review_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_DECISION_SCHEMA,
        "review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
        "review_kind": "durable_outcome_record_write_evidence_review",
        "source_durable_outcome_record_write_evidence_scope": {
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": "durable_outcome_record_store_write_execution_arrival_bath_move_002",
            "persistence_id": "durable_outcome_record_persistence_arrival_bath_move_002",
            "record_write_execution_id": "durable_outcome_record_write_execution_arrival_bath_move_002",
            "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_world_verdict_rewrite_gate",
        "review_reason": "external_write_evidence_is_scoped_acknowledged_readback_and_digest_checked",
        "source_world_verdict": "not_verified",
        "reviewed_write_evidence_preflight_verdict": "ready_for_durable_outcome_record_write_evidence_review",
        "durable_outcome_record_write_confirmed": true,
        "store_ack_confirmed": true,
        "record_readback_confirmed": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "reviewer_attestation_present": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "world_verdict_rewrite_allowed": false,
        "durable_outcome_record_written_by_this_tool": false
    })
}

fn ready_runtime_executor_durable_outcome_record_write_evidence_review_preflight() -> Value {
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight(
        &json!({
            "durable_outcome_record_write_evidence_preflight": ready_runtime_executor_durable_outcome_record_write_evidence_preflight(),
            "durable_outcome_record_write_evidence_review_decision":
                explicit_durable_outcome_record_write_evidence_review_decision()
        }),
    )
}

fn explicit_world_verdict_rewrite_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_DECISION_SCHEMA,
        "rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
        "decision_kind": "world_verdict_rewrite",
        "source_durable_outcome_record_write_evidence_review_scope": {
            "review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": "durable_outcome_record_store_write_execution_arrival_bath_move_002",
            "persistence_id": "durable_outcome_record_persistence_arrival_bath_move_002",
            "record_write_execution_id": "durable_outcome_record_write_execution_arrival_bath_move_002",
            "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "rewrite_world_verdict_to_verified",
        "rewrite_reason": "reviewed_durable_outcome_record_write_evidence_supports_verified_world_verdict",
        "source_world_verdict": "not_verified",
        "target_world_verdict": "verified",
        "reviewed_write_evidence_review_preflight_verdict": "ready_for_world_verdict_rewrite_gate",
        "verified_outcome_claim_present": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "world_verdict_rewrite_allowed": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_world_verdict_rewrite_gate() -> Value {
    build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate(&json!({
        "durable_outcome_record_write_evidence_review_preflight":
            ready_runtime_executor_durable_outcome_record_write_evidence_review_preflight(),
        "world_verdict_rewrite_decision": explicit_world_verdict_rewrite_decision()
    }))
}

fn explicit_verified_outcome_ingestion_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_DECISION_SCHEMA,
        "ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion",
        "source_world_verdict_rewrite_scope": {
            "rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "admit_verified_outcome_package",
        "ingestion_reason": "world_verdict_rewrite_output_is_scoped_and_ready_for_separate_admission",
        "source_world_verdict": "verified",
        "reviewed_world_verdict_rewrite_gate_verdict": "ready_for_verified_outcome_ingestion_gate",
        "bounded_verified_verdict_package_present": true,
        "verified_outcome_claim_present": true,
        "world_verdict_rewrite_output_only_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "verified_outcome_ingestion_allowed": true,
        "store_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_gate() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(&json!({
        "world_verdict_rewrite_gate": ready_runtime_executor_world_verdict_rewrite_gate(),
        "verified_outcome_ingestion_decision": explicit_verified_outcome_ingestion_decision()
    }))
}

fn explicit_verified_outcome_ingestion_execution_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA,
        "execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_execution",
        "source_verified_outcome_ingestion_gate_scope": {
            "ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_execution_preflight",
        "execution_reason": "verified_outcome_ingestion_gate_package_is_scoped_and_ready_for_separate_commit_execution",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_gate_verdict": "ready_for_verified_outcome_admission",
        "verified_outcome_package_confirmed": true,
        "ingestion_gate_output_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "execution_boundary_acknowledged": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn explicit_verified_outcome_ingestion_execution_decision_for_admission_preflight() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA,
        "execution_decision_id": "verified_outcome_ingestion_execution_from_admission_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_execution",
        "source_verified_outcome_ingestion_admission_scope": {
            "admission_decision_id": "verified_outcome_ingestion_admission_arrival_bath_move_002",
            "review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
            "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
            "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "source_write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_execution_preflight",
        "execution_reason": "verified_outcome_ingestion_admission_preflight_is_scoped_and_ready_for_separate_commit_execution",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_admission_preflight_verdict": "ready_for_verified_outcome_ingestion_execution",
        "verified_outcome_package_confirmed": true,
        "admission_preflight_confirmed": true,
        "admission_decision_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "execution_boundary_acknowledged": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_execution_preflight() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
        &json!({
            "verified_outcome_ingestion_gate": ready_runtime_executor_verified_outcome_ingestion_gate(),
            "verified_outcome_ingestion_execution_decision":
                explicit_verified_outcome_ingestion_execution_decision()
        }),
    )
}

fn ready_runtime_executor_verified_outcome_ingestion_execution_preflight_from_admission_preflight(
) -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_preflight(
        &json!({
            "verified_outcome_ingestion_admission_preflight":
                ready_runtime_executor_verified_outcome_ingestion_admission_preflight(),
            "verified_outcome_ingestion_execution_decision":
                explicit_verified_outcome_ingestion_execution_decision_for_admission_preflight()
        }),
    )
}

fn explicit_verified_outcome_ingestion_execution_commit_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA,
        "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_execution_commit",
        "source_verified_outcome_ingestion_execution_preflight_scope": {
            "execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_apply",
        "commit_reason": "verified_outcome_ingestion_execution_preflight_is_scoped_and_ready_for_separate_apply",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_execution_preflight_verdict": "ready_for_verified_outcome_ingestion_execution_commit",
        "execution_preflight_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "apply_boundary_acknowledged": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn explicit_verified_outcome_ingestion_execution_commit_decision_for_admission_preflight() -> Value
{
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA,
        "commit_decision_id": "verified_outcome_ingestion_execution_commit_from_admission_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_execution_commit",
        "source_verified_outcome_ingestion_execution_preflight_scope": {
            "execution_decision_id": "verified_outcome_ingestion_execution_from_admission_arrival_bath_move_002",
            "source_admission_decision_id": "verified_outcome_ingestion_admission_arrival_bath_move_002",
            "source_write_evidence_review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
            "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
            "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_apply",
        "commit_reason": "admission_source_verified_outcome_ingestion_execution_preflight_is_scoped_and_ready_for_separate_apply",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_execution_preflight_verdict": "ready_for_verified_outcome_ingestion_execution_commit",
        "execution_preflight_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "admission_preflight_confirmed": true,
        "admission_decision_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "apply_boundary_acknowledged": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_execution_commit() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
        &json!({
            "verified_outcome_ingestion_execution_preflight":
                ready_runtime_executor_verified_outcome_ingestion_execution_preflight(),
            "verified_outcome_ingestion_execution_commit_decision":
                explicit_verified_outcome_ingestion_execution_commit_decision()
        }),
    )
}

fn ready_runtime_executor_verified_outcome_ingestion_execution_commit_from_admission_preflight(
) -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
        &json!({
            "verified_outcome_ingestion_execution_preflight":
                ready_runtime_executor_verified_outcome_ingestion_execution_preflight_from_admission_preflight(),
            "verified_outcome_ingestion_execution_commit_decision":
                explicit_verified_outcome_ingestion_execution_commit_decision_for_admission_preflight()
        }),
    )
}

fn explicit_verified_outcome_ingestion_apply_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA,
        "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_apply",
        "source_verified_outcome_ingestion_execution_commit_scope": {
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_writer",
        "apply_reason": "verified_outcome_ingestion_execution_commit_is_scoped_and_ready_for_separate_writer",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_execution_commit_verdict": "ready_for_verified_outcome_ingestion_apply",
        "commit_package_confirmed": true,
        "execution_preflight_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "writer_boundary_acknowledged": true,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn explicit_verified_outcome_ingestion_apply_decision_for_admission_source_commit() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA,
        "apply_decision_id": "verified_outcome_ingestion_apply_from_admission_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_apply",
        "source_verified_outcome_ingestion_execution_commit_scope": {
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_from_admission_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_from_admission_arrival_bath_move_002",
            "source_admission_decision_id": "verified_outcome_ingestion_admission_arrival_bath_move_002",
            "source_write_evidence_review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
            "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
            "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "source_apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "source_commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_prior_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_writer",
        "apply_reason": "admission_source_verified_outcome_ingestion_execution_commit_is_scoped_and_ready_for_separate_writer",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_execution_commit_verdict": "ready_for_verified_outcome_ingestion_apply",
        "commit_package_confirmed": true,
        "execution_preflight_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "admission_preflight_confirmed": true,
        "admission_decision_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "writer_boundary_acknowledged": true,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_apply_gate() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&json!({
        "verified_outcome_ingestion_execution_commit":
            ready_runtime_executor_verified_outcome_ingestion_execution_commit(),
        "verified_outcome_ingestion_apply_decision":
            explicit_verified_outcome_ingestion_apply_decision()
    }))
}

fn explicit_verified_outcome_ingestion_writer_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_DECISION_SCHEMA,
        "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_writer",
        "source_verified_outcome_ingestion_apply_scope": {
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_writer_execution",
        "writer_reason": "verified_outcome_ingestion_apply_gate_is_scoped_and_ready_for_separate_writer_execution",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_apply_verdict": "ready_for_verified_outcome_ingestion_writer",
        "apply_package_confirmed": true,
        "commit_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "writer_payload_confirmed": true,
        "writer_destination_confirmed": true,
        "writer_idempotency_confirmed": true,
        "writer_boundary_acknowledged": true,
        "rollback_plan_confirmed": true,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_writer() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer(&json!({
        "verified_outcome_ingestion_apply_gate":
            ready_runtime_executor_verified_outcome_ingestion_apply_gate(),
        "verified_outcome_ingestion_writer_decision":
            explicit_verified_outcome_ingestion_writer_decision()
    }))
}

fn ready_runtime_executor_verified_outcome_ingestion_writer_execution() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_writer_execution(
        &json!({
            "verified_outcome_ingestion_writer":
                ready_runtime_executor_verified_outcome_ingestion_writer(),
            "verified_outcome_ingestion_writer_execution_decision":
                explicit_verified_outcome_ingestion_writer_execution_decision()
        }),
    )
}

fn explicit_verified_outcome_ingestion_writer_execution_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITER_EXECUTION_DECISION_SCHEMA,
        "writer_execution_decision_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_writer_execution",
        "source_verified_outcome_ingestion_writer_scope": {
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_persistence",
        "writer_execution_reason": "verified_outcome_ingestion_writer_is_scoped_and_ready_for_separate_persistence",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_writer_verdict": "ready_for_verified_outcome_ingestion_writer_execution",
        "writer_package_confirmed": true,
        "apply_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "write_destination_verified": true,
        "outcome_record_digest_verified": true,
        "idempotent_upsert_confirmed": true,
        "store_transaction_plan_complete": true,
        "rollback_plan_confirmed": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn explicit_verified_outcome_ingestion_persistence_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_PERSISTENCE_DECISION_SCHEMA,
        "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
        "persistence_kind": "verified_outcome_ingestion_persistence",
        "source_verified_outcome_ingestion_writer_execution_scope": {
            "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_store_write",
        "persistence_reason": "verified_outcome_ingestion_persistence_is_scoped_and_ready_for_separate_store_write",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_writer_execution_verdict": "ready_for_verified_outcome_ingestion_persistence",
        "writer_execution_package_confirmed": true,
        "writer_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "persistence_target_verified": true,
        "outcome_record_digest_verified": true,
        "idempotent_upsert_confirmed": true,
        "store_transaction_plan_complete": true,
        "rollback_plan_confirmed": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "verified_outcome_store_write_allowed": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_persistence() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_persistence(&json!({
        "verified_outcome_ingestion_writer_execution":
            ready_runtime_executor_verified_outcome_ingestion_writer_execution(),
        "verified_outcome_ingestion_persistence_decision":
            explicit_verified_outcome_ingestion_persistence_decision()
    }))
}

fn explicit_verified_outcome_ingestion_store_write_execution_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_STORE_WRITE_EXECUTION_DECISION_SCHEMA,
        "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
        "store_write_execution_kind": "verified_outcome_ingestion_store_write_execution",
        "source_verified_outcome_ingestion_persistence_scope": {
            "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
            "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_write_evidence",
        "store_write_execution_reason": "verified_outcome_ingestion_store_write_preflight_ready_for_later_write_evidence",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_persistence_verdict": "ready_for_verified_outcome_ingestion_store_write",
        "persistence_package_confirmed": true,
        "writer_execution_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "persistence_target_verified": true,
        "outcome_record_digest_verified": true,
        "idempotent_upsert_confirmed": true,
        "store_transaction_plan_complete": true,
        "rollback_plan_confirmed": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "verified_outcome_store_write_execution_allowed": false,
        "verified_outcome_store_written_by_this_tool": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
        &json!({
            "verified_outcome_ingestion_persistence":
                ready_runtime_executor_verified_outcome_ingestion_persistence(),
            "verified_outcome_ingestion_store_write_execution_decision":
                explicit_verified_outcome_ingestion_store_write_execution_decision()
        }),
    )
}

fn explicit_verified_outcome_ingestion_write_evidence() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_SCHEMA,
        "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
        "evidence_kind": "verified_outcome_ingestion_write_evidence",
        "write_evidence_observed_at": "2026-06-20T18:40:00Z",
        "source_verified_outcome_ingestion_store_write_execution_scope": {
            "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
            "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
            "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "source_write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "write_evidence_reason": "external_verified_outcome_store_ack_and_readback_confirm_scoped_record",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_store_write_execution_decision": "approved_for_verified_outcome_ingestion_write_evidence",
        "verified_outcome_store_write_observed": true,
        "store_write_acknowledged": true,
        "record_readback_verified": true,
        "outcome_record_digest_verified": true,
        "idempotency_key_confirmed": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "verified_outcome_store_written_by_this_tool": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_write_evidence_preflight() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight(
        &json!({
            "verified_outcome_ingestion_store_write_execution_preflight":
                ready_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(),
            "verified_outcome_ingestion_write_evidence":
                explicit_verified_outcome_ingestion_write_evidence()
        }),
    )
}

fn explicit_verified_outcome_ingestion_write_evidence_review_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_REVIEW_DECISION_SCHEMA,
        "review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
        "review_kind": "verified_outcome_ingestion_write_evidence_review",
        "source_verified_outcome_ingestion_write_evidence_scope": {
            "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
            "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
            "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "source_write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_admission",
        "review_reason": "verified_outcome_ingestion_write_evidence_is_scoped_and_ready_for_separate_admission",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_write_evidence_preflight_verdict": "ready_for_verified_outcome_ingestion_write_evidence_review",
        "verified_outcome_store_write_confirmed": true,
        "store_ack_confirmed": true,
        "record_readback_confirmed": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "reviewer_attestation_present": true,
        "verified_outcome_admission_allowed": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "world_verdict_persisted_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "verified_outcome_store_written_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight(
        &json!({
            "verified_outcome_ingestion_write_evidence_preflight":
                ready_runtime_executor_verified_outcome_ingestion_write_evidence_preflight(),
            "verified_outcome_ingestion_write_evidence_review_decision":
                explicit_verified_outcome_ingestion_write_evidence_review_decision()
        }),
    )
}

fn explicit_verified_outcome_ingestion_admission_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_ADMISSION_DECISION_SCHEMA,
        "admission_decision_id": "verified_outcome_ingestion_admission_arrival_bath_move_002",
        "admission_kind": "verified_outcome_ingestion_admission",
        "source_verified_outcome_ingestion_admission_scope": {
            "review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
            "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
            "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
            "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
            "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
            "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
            "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
            "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
            "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
            "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "source_write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_verified_outcome_ingestion_execution",
        "admission_reason": "verified_outcome_ingestion_write_evidence_review_is_scoped_and_ready_for_separate_execution",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_admission_preflight_verdict": "ready_for_verified_outcome_ingestion_admission",
        "write_evidence_review_preflight_confirmed": true,
        "write_evidence_review_decision_confirmed": true,
        "verified_outcome_store_write_confirmed": true,
        "store_ack_confirmed": true,
        "record_readback_confirmed": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "operator_attestation_present": true,
        "verified_outcome_ingestion_execution_allowed": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "world_verdict_persisted_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "verified_outcome_store_written_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false
    })
}

fn ready_runtime_executor_verified_outcome_ingestion_admission_preflight() -> Value {
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
        &json!({
            "verified_outcome_ingestion_write_evidence_review_preflight":
                ready_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight(),
            "verified_outcome_ingestion_admission_decision":
                explicit_verified_outcome_ingestion_admission_decision()
        }),
    )
}

fn assert_execution_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(preflight["guardrails"]["queries_live_runtime"], false);
    assert_eq!(
        preflight["guardrails"]["implicit_live_runtime_lookup_allowed"],
        false
    );
    assert_eq!(preflight["guardrails"]["applies_patch"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_apply_patch"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_query_live_runtime"],
        true
    );
}

fn assert_apply_request_read_only(request: &Value) {
    assert_eq!(request["writes_state"], false);
    assert_eq!(request["store_access_required"], false);
    assert_eq!(request["mcp_tool_registered"], false);
    assert_eq!(request["implicit_live_runtime_lookup_attempted"], false);
    assert_eq!(request["guardrails"]["read_only"], true);
    assert_eq!(request["guardrails"]["mutation_surface"], "none");
    assert_eq!(request["guardrails"]["writes_state"], false);
    assert_eq!(request["guardrails"]["store_access_required"], false);
    assert_eq!(request["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(request["guardrails"]["queries_live_runtime"], false);
    assert_eq!(
        request["guardrails"]["implicit_live_runtime_lookup_allowed"],
        false
    );
    assert_eq!(request["guardrails"]["submits_apply_request"], false);
    assert_eq!(request["guardrails"]["applies_patch"], false);
    assert_eq!(request["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        request["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(request["agent_action_contract"]["do_not_apply_patch"], true);
    assert_eq!(
        request["agent_action_contract"]["do_not_submit_patch_from_this_tool"],
        true
    );
    assert_eq!(
        request["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        request["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        request["agent_action_contract"]["do_not_query_live_runtime"],
        true
    );
}

fn assert_runtime_executor_design_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(preflight["implicit_live_runtime_lookup_attempted"], false);
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(preflight["guardrails"]["queries_live_runtime"], false);
    assert_eq!(
        preflight["guardrails"]["implicit_live_runtime_lookup_allowed"],
        false
    );
    assert_eq!(preflight["guardrails"]["submits_apply_request"], false);
    assert_eq!(preflight["guardrails"]["applies_patch"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["executor_design_request"]["ready_for_live_runtime_lookup"],
        false
    );
    assert_eq!(
        preflight["executor_design_request"]["ready_for_submission"],
        false
    );
    assert_eq!(
        preflight["executor_design_request"]["ready_for_patch_application"],
        false
    );
    assert_eq!(
        preflight["executor_design_request"]["execution_performed"],
        false
    );
    assert_eq!(
        preflight["executor_design_request"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_query_live_runtime"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_submit_apply_request"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_apply_patch"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
}

fn assert_live_runtime_lookup_design_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(preflight["implicit_live_runtime_lookup_attempted"], false);
    assert_eq!(preflight["live_runtime_contact_attempted"], false);
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(preflight["guardrails"]["queries_live_runtime"], false);
    assert_eq!(preflight["guardrails"]["contacts_live_runtime"], false);
    assert_eq!(preflight["guardrails"]["opens_socket"], false);
    assert_eq!(
        preflight["guardrails"]["implicit_live_runtime_lookup_allowed"],
        false
    );
    assert_eq!(preflight["guardrails"]["submits_apply_request"], false);
    assert_eq!(preflight["guardrails"]["applies_patch"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["host_binding_requirements"]
            ["network_contact_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["host_binding_requirements"]
            ["socket_open_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["ready_for_live_runtime_lookup"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["live_runtime_lookup_performed"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["host_contact_attempted"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["ready_for_submission"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["ready_for_patch_application"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["execution_performed"],
        false
    );
    assert_eq!(
        preflight["lookup_design_request"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_contact_live_runtime"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_open_socket"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_query_live_runtime"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_submit_apply_request"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_apply_patch"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
}

fn assert_runtime_executor_live_lookup_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(preflight["implicit_live_runtime_lookup_attempted"], false);
    assert_eq!(preflight["lookup_performed_by_this_tool"], false);
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(preflight["guardrails"]["queries_live_runtime"], false);
    assert_eq!(
        preflight["guardrails"]["requires_explicit_lookup_snapshot"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["lookup_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["implicit_live_runtime_lookup_allowed"],
        false
    );
    assert_eq!(preflight["guardrails"]["submits_apply_request"], false);
    assert_eq!(preflight["guardrails"]["applies_patch"], false);
    assert_eq!(preflight["guardrails"]["verifies_post_apply_result"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(preflight["lookup_evidence"]["ready_for_submission"], false);
    assert_eq!(
        preflight["lookup_evidence"]["ready_for_patch_application"],
        false
    );
    assert_eq!(preflight["lookup_evidence"]["mutation_performed"], false);
    assert_eq!(
        preflight["lookup_evidence"]["verification_performed"],
        false
    );
    assert_eq!(
        preflight["lookup_evidence"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_submit_apply_request"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_apply_patch"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_verify_post_apply_result"],
        true
    );
}

fn assert_runtime_executor_operator_submission_token_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(preflight["submission_performed_by_this_tool"], false);
    assert_eq!(preflight["apply_request_submitted_by_this_tool"], false);
    assert_eq!(preflight["patch_application_performed_by_this_tool"], false);
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_live_lookup_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_operator_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["operator_authority_scope"],
        "operator_submission_token_only"
    );
    assert_eq!(preflight["guardrails"]["submits_apply_request"], false);
    assert_eq!(preflight["guardrails"]["applies_patch"], false);
    assert_eq!(preflight["guardrails"]["verifies_post_apply_result"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_submission_token"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["operator_submission_token"]["submission_token_persisted"],
        false
    );
    assert_eq!(
        preflight["operator_submission_token"]["ready_for_executor_submission"],
        false
    );
    assert_eq!(
        preflight["operator_submission_token"]["apply_request_submitted"],
        false
    );
    assert_eq!(
        preflight["operator_submission_token"]["patch_application_performed"],
        false
    );
    assert_eq!(
        preflight["operator_submission_token"]["verification_performed"],
        false
    );
    assert_eq!(
        preflight["operator_submission_token"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_submit_apply_request"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_apply_patch"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_verify_post_apply_result"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_submission_token"],
        true
    );
}

fn assert_runtime_executor_patch_application_gate_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["executor_invocation_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["apply_request_submitted_by_this_tool"], false);
    assert_eq!(preflight["patch_application_performed_by_this_tool"], false);
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_operator_submission_token_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_patch_application_gate_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["patch_application_authority_scope"],
        "patch_application_executor_invocation_gate_only"
    );
    assert_eq!(preflight["guardrails"]["invokes_patch_executor"], false);
    assert_eq!(preflight["guardrails"]["submits_apply_request"], false);
    assert_eq!(preflight["guardrails"]["applies_patch"], false);
    assert_eq!(preflight["guardrails"]["verifies_post_apply_result"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_submission_token"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["patch_application_gate"]["executor_invocation_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["patch_application_gate"]["apply_request_submitted"],
        false
    );
    assert_eq!(
        preflight["patch_application_gate"]["patch_application_performed"],
        false
    );
    assert_eq!(
        preflight["patch_application_gate"]["verification_performed"],
        false
    );
    assert_eq!(
        preflight["patch_application_gate"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_invoke_patch_executor"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_submit_apply_request"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_apply_patch"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_verify_post_apply_result"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_submission_token"],
        true
    );
}

fn assert_runtime_executor_patch_executor_invocation_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["executor_invocation_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["executor_queue_submission_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["apply_request_submitted_by_this_tool"], false);
    assert_eq!(preflight["patch_application_performed_by_this_tool"], false);
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_patch_application_gate_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_patch_executor_invocation_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["patch_executor_invocation_authority_scope"],
        "separate_patch_executor_invocation_only"
    );
    assert_eq!(preflight["guardrails"]["invokes_patch_executor"], false);
    assert_eq!(preflight["guardrails"]["submits_executor_queue"], false);
    assert_eq!(preflight["guardrails"]["submits_apply_request"], false);
    assert_eq!(preflight["guardrails"]["applies_patch"], false);
    assert_eq!(preflight["guardrails"]["verifies_post_apply_result"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_submission_token"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["patch_executor_invocation_request"]
            ["executor_invocation_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["patch_executor_invocation_request"]["executor_queue_submission_performed"],
        false
    );
    assert_eq!(
        preflight["patch_executor_invocation_request"]["apply_request_submitted"],
        false
    );
    assert_eq!(
        preflight["patch_executor_invocation_request"]["patch_application_performed"],
        false
    );
    assert_eq!(
        preflight["patch_executor_invocation_request"]["verification_performed"],
        false
    );
    assert_eq!(
        preflight["patch_executor_invocation_request"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_invoke_patch_executor"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_submit_executor_queue"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_submit_apply_request"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_apply_patch"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_verify_post_apply_result"],
        true
    );
}

fn assert_runtime_executor_patch_runtime_application_evidence_preflight_read_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["executor_invocation_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["executor_queue_submission_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["apply_request_submitted_by_this_tool"], false);
    assert_eq!(preflight["patch_application_performed_by_this_tool"], false);
    assert_eq!(
        preflight["post_apply_verification_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["outcome_ingestion_performed_by_this_tool"], false);
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_patch_executor_invocation_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_patch_runtime_application_evidence"],
        true
    );
    assert_eq!(preflight["guardrails"]["invokes_patch_executor"], false);
    assert_eq!(preflight["guardrails"]["submits_executor_queue"], false);
    assert_eq!(preflight["guardrails"]["submits_apply_request"], false);
    assert_eq!(preflight["guardrails"]["applies_patch"], false);
    assert_eq!(preflight["guardrails"]["verifies_post_apply_result"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_evidence_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["runtime_application_evidence"]["post_apply_verification_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["runtime_application_evidence"]["post_apply_verification_performed_by_evidence"],
        false
    );
    assert_eq!(
        preflight["runtime_application_evidence"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["runtime_application_evidence"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["runtime_application_evidence"]["evidence_record_persisted_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_invoke_patch_executor"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_submit_executor_queue"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_apply_patch"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_verify_post_apply_result"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
}

fn assert_runtime_executor_post_apply_verification_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["post_apply_verification_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["outcome_ingestion_performed_by_this_tool"], false);
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_runtime_application_evidence_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_post_apply_verification_evidence"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_post_apply_verification"],
        false
    );
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["persists_verification_record"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["post_apply_verification"]["post_apply_verification_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["post_apply_verification"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["post_apply_verification"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["post_apply_verification"]["verification_record_persisted_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_verification_record"],
        true
    );
}

fn assert_runtime_executor_outcome_ingestion_review_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["outcome_ingestion_review_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_post_apply_verification_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_outcome_ingestion_review_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_outcome_ingestion_review"],
        false
    );
    assert_eq!(preflight["guardrails"]["durable_ingestion_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["outcome_ingestion_review"]["outcome_ingestion_review_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["outcome_ingestion_review"]["durable_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["outcome_ingestion_review"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["outcome_ingestion_review"]["outcome_record_persisted_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_ingestion_gate_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_ingestion_gate_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_outcome_ingestion_review_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_durable_outcome_ingestion_gate_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_ingestion_gate"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["durable_ingestion_execution_allowed"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_gate"]
            ["durable_outcome_ingestion_gate_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_gate"]["durable_ingestion_execution_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_gate"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_gate"]["outcome_record_persisted_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_ingestion_execution_preflight_read_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_durable_outcome_ingestion_gate_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_durable_outcome_ingestion_execution_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_ingestion_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["durable_write_implementation_allowed"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["durable_outcome_ingestion_performed"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_execution"]["durable_write_implementation_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_execution"]
            ["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_execution"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_execution"]["outcome_record_persisted_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_write_implementation_preflight_read_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_write_implementation_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_durable_outcome_ingestion_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_durable_outcome_write_implementation_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_write_implementation_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["durable_record_write_allowed"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_write_implementation"]["durable_record_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_write_implementation"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_write_implementation"]["memory_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_write_implementation"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_record_write_preflight_read_only(preflight: &Value) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_record_write_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_durable_outcome_write_implementation_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_durable_outcome_record_write_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_record_write_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["durable_record_write_execution_allowed"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write"]["durable_record_write_execution_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write"]["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write"]["memory_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_record_write_execution_preflight_read_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_record_write_execution_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_durable_outcome_record_write_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]
            ["requires_explicit_durable_outcome_record_write_execution_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_record_write_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["durable_record_persistence_allowed"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_execution"]["durable_record_persistence_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_execution"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_execution"]["memory_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_execution"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_record_persistence_preflight_read_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_record_persistence_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_durable_outcome_record_write_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_durable_outcome_record_persistence_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_record_persistence_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["durable_store_write_allowed"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_persistence"]["durable_store_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_persistence"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_persistence"]["memory_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_persistence"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["require_separate_durable_outcome_record_store_write"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_record_store_write_execution_preflight_read_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_record_store_write_execution_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_durable_outcome_record_persistence_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]
            ["requires_explicit_durable_outcome_record_store_write_execution_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_record_store_write_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["durable_store_write_execution_allowed"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_store_write_execution"]
            ["durable_store_write_execution_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_store_write_execution"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_store_write_execution"]["memory_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_store_write_execution"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]
            ["require_separate_durable_outcome_record_store_write_execution"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_record_write_evidence_preflight_read_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_record_write_evidence_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]
            ["requires_ready_durable_outcome_record_store_write_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_durable_outcome_record_write_evidence"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_record_write_evidence_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_evidence"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_evidence"]["memory_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_evidence"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_evidence"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]
            ["require_separate_durable_outcome_record_write_evidence_review"],
        true
    );
}

fn assert_runtime_executor_durable_outcome_record_write_evidence_review_preflight_read_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["durable_outcome_record_write_evidence_review_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["world_verdict_rewrite_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "none");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_durable_outcome_record_write_evidence_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]
            ["requires_explicit_durable_outcome_record_write_evidence_review_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_record_write_evidence_review_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_durable_outcome_record_write_evidence_review"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["guardrails"]["feedback_changes_world_verdict_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_evidence_review"]
            ["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_evidence_review"]["memory_write_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_evidence_review"]["outcome_ingestion_allowed"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_record_write_evidence_review"]["world_verdict_rewrite_allowed"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_rewrite_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["require_separate_world_verdict_rewrite_gate"],
        true
    );
}

fn assert_runtime_executor_world_verdict_rewrite_gate_output_only(gate: &Value) {
    assert_eq!(gate["writes_state"], false);
    assert_eq!(gate["store_access_required"], false);
    assert_eq!(gate["mcp_tool_registered"], false);
    assert_eq!(
        gate["world_verdict_rewrite_gate_performed_by_this_tool"],
        true
    );
    assert_eq!(gate["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(gate["durable_outcome_record_written_by_this_tool"], false);
    assert_eq!(
        gate["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(
        gate["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(gate["guardrails"]["read_only"], true);
    assert_eq!(gate["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(gate["guardrails"]["writes_state"], false);
    assert_eq!(gate["guardrails"]["store_access_required"], false);
    assert_eq!(gate["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        gate["guardrails"]["requires_ready_durable_outcome_record_write_evidence_review_preflight"],
        true
    );
    assert_eq!(
        gate["guardrails"]["requires_explicit_world_verdict_rewrite_decision"],
        true
    );
    assert_eq!(
        gate["guardrails"]["performs_world_verdict_rewrite_gate"],
        true
    );
    assert_eq!(
        gate["guardrails"]["performs_world_verdict_rewrite_output"],
        true
    );
    assert_eq!(gate["guardrails"]["persists_world_verdict"], false);
    assert_eq!(gate["guardrails"]["durable_outcome_record_written"], false);
    assert_eq!(gate["guardrails"]["memory_write_allowed"], false);
    assert_eq!(gate["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        gate["guardrails"]["verified_outcome_ingestion_allowed"],
        false
    );
    assert_eq!(gate["guardrails"]["persists_outcome_record"], false);
    assert_eq!(gate["agent_action_contract"]["do_not_ingest_outcome"], true);
    assert_eq!(gate["agent_action_contract"]["do_not_write_memory"], true);
    assert_eq!(
        gate["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        gate["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        gate["agent_action_contract"]["require_separate_verified_outcome_ingestion_gate"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_gate_output_only(gate: &Value) {
    assert_eq!(gate["writes_state"], false);
    assert_eq!(gate["store_access_required"], false);
    assert_eq!(gate["mcp_tool_registered"], false);
    assert_eq!(
        gate["verified_outcome_ingestion_gate_performed_by_this_tool"],
        true
    );
    assert_eq!(
        gate["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(gate["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(gate["durable_outcome_record_written_by_this_tool"], false);
    assert_eq!(
        gate["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(gate["guardrails"]["read_only"], true);
    assert_eq!(gate["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(gate["guardrails"]["writes_state"], false);
    assert_eq!(gate["guardrails"]["store_access_required"], false);
    assert_eq!(gate["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        gate["guardrails"]["requires_ready_world_verdict_rewrite_gate"],
        true
    );
    assert_eq!(
        gate["guardrails"]["requires_explicit_verified_outcome_ingestion_decision"],
        true
    );
    assert_eq!(
        gate["guardrails"]["performs_verified_outcome_ingestion_gate"],
        true
    );
    assert_eq!(
        gate["guardrails"]["performs_verified_outcome_admission_output"],
        true
    );
    assert_eq!(
        gate["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(gate["guardrails"]["persists_world_verdict"], false);
    assert_eq!(gate["guardrails"]["durable_outcome_record_written"], false);
    assert_eq!(gate["guardrails"]["memory_write_allowed"], false);
    assert_eq!(gate["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(gate["guardrails"]["store_write_allowed"], false);
    assert_eq!(gate["guardrails"]["persists_outcome_record"], false);
    assert_eq!(gate["agent_action_contract"]["do_not_ingest_outcome"], true);
    assert_eq!(gate["agent_action_contract"]["do_not_write_memory"], true);
    assert_eq!(gate["agent_action_contract"]["do_not_write_store"], true);
    assert_eq!(
        gate["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        gate["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        gate["agent_action_contract"]["require_separate_verified_outcome_admission_gate"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_admission_preflight_output_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["verified_outcome_ingestion_admission_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["verified_outcome_admission_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(preflight["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]
            ["requires_ready_verified_outcome_ingestion_write_evidence_review_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_verified_outcome_ingestion_admission_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_ingestion_admission_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_admission"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_store_write"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["verified_outcome_ingestion_execution_allowed"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["verified_outcome_admission_performed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["agent_action_contract"]
            ["may_enter_verified_outcome_ingestion_execution_after_preflight"],
        preflight["status"] == "ready"
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_admission_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["require_separate_verified_outcome_ingestion_execution"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_execution_preflight_output_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["verified_outcome_ingestion_execution_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(preflight["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_verified_outcome_ingestion_gate"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_verified_outcome_ingestion_execution_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_ingestion_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(preflight["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["verified_outcome_ingestion_allowed"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_ingestion"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]
            ["require_separate_verified_outcome_ingestion_execution_commit"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_execution_commit_output_only(commit: &Value) {
    assert_eq!(commit["writes_state"], false);
    assert_eq!(commit["store_access_required"], false);
    assert_eq!(commit["mcp_tool_registered"], false);
    assert_eq!(
        commit["verified_outcome_ingestion_execution_commit_performed_by_this_tool"],
        true
    );
    assert_eq!(
        commit["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(commit["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(commit["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(commit["durable_outcome_record_written_by_this_tool"], false);
    assert_eq!(
        commit["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(commit["guardrails"]["read_only"], true);
    assert_eq!(commit["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(commit["guardrails"]["writes_state"], false);
    assert_eq!(commit["guardrails"]["store_access_required"], false);
    assert_eq!(commit["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        commit["guardrails"]["requires_ready_verified_outcome_ingestion_execution_preflight"],
        true
    );
    assert_eq!(
        commit["guardrails"]
            ["requires_explicit_verified_outcome_ingestion_execution_commit_decision"],
        true
    );
    assert_eq!(
        commit["guardrails"]["performs_verified_outcome_ingestion_execution_commit_gate"],
        true
    );
    assert_eq!(
        commit["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(commit["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        commit["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(commit["guardrails"]["memory_write_allowed"], false);
    assert_eq!(commit["guardrails"]["outcome_ingestion_allowed"], false);
    assert_eq!(
        commit["guardrails"]["verified_outcome_ingestion_allowed"],
        false
    );
    assert_eq!(commit["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        commit["agent_action_contract"]["may_execute_verified_outcome_ingestion"],
        false
    );
    assert_eq!(
        commit["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(commit["agent_action_contract"]["do_not_write_memory"], true);
    assert_eq!(
        commit["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        commit["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        commit["agent_action_contract"]["require_separate_verified_outcome_ingestion_apply"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_apply_gate_output_only(apply: &Value) {
    assert_eq!(apply["writes_state"], false);
    assert_eq!(apply["store_access_required"], false);
    assert_eq!(apply["mcp_tool_registered"], false);
    assert_eq!(
        apply["verified_outcome_ingestion_apply_gate_performed_by_this_tool"],
        true
    );
    assert_eq!(
        apply["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(apply["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(apply["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(apply["durable_outcome_record_written_by_this_tool"], false);
    assert_eq!(
        apply["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(apply["guardrails"]["read_only"], true);
    assert_eq!(apply["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(apply["guardrails"]["writes_state"], false);
    assert_eq!(apply["guardrails"]["store_access_required"], false);
    assert_eq!(apply["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        apply["guardrails"]["requires_ready_verified_outcome_ingestion_execution_commit"],
        true
    );
    assert_eq!(
        apply["guardrails"]["accepts_admission_source_verified_outcome_ingestion_execution_commit"],
        true
    );
    assert_eq!(
        apply["guardrails"]["preserves_verified_outcome_ingestion_admission_lineage"],
        true
    );
    assert_eq!(
        apply["guardrails"]["requires_explicit_verified_outcome_ingestion_apply_decision"],
        true
    );
    assert_eq!(
        apply["guardrails"]["performs_verified_outcome_ingestion_apply_gate"],
        true
    );
    assert_eq!(
        apply["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(apply["guardrails"]["persists_world_verdict"], false);
    assert_eq!(apply["guardrails"]["durable_outcome_record_written"], false);
    assert_eq!(apply["guardrails"]["memory_write_allowed"], false);
    assert_eq!(
        apply["guardrails"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(apply["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        apply["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"],
        false
    );
    assert_eq!(
        apply["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(apply["agent_action_contract"]["do_not_write_memory"], true);
    assert_eq!(
        apply["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        apply["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        apply["agent_action_contract"]["require_separate_verified_outcome_ingestion_writer"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_writer_output_only(writer: &Value) {
    assert_eq!(writer["writes_state"], false);
    assert_eq!(writer["store_access_required"], false);
    assert_eq!(writer["mcp_tool_registered"], false);
    assert_eq!(
        writer["verified_outcome_ingestion_writer_gate_performed_by_this_tool"],
        true
    );
    assert_eq!(
        writer["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(writer["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(writer["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(writer["durable_outcome_record_written_by_this_tool"], false);
    assert_eq!(
        writer["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(writer["guardrails"]["read_only"], true);
    assert_eq!(writer["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(writer["guardrails"]["writes_state"], false);
    assert_eq!(writer["guardrails"]["store_access_required"], false);
    assert_eq!(writer["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        writer["guardrails"]["requires_ready_verified_outcome_ingestion_apply_gate"],
        true
    );
    assert_eq!(
        writer["guardrails"]["requires_explicit_verified_outcome_ingestion_writer_decision"],
        true
    );
    assert_eq!(
        writer["guardrails"]["performs_verified_outcome_ingestion_writer_gate"],
        true
    );
    assert_eq!(
        writer["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(writer["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        writer["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(writer["guardrails"]["memory_write_allowed"], false);
    assert_eq!(
        writer["guardrails"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(writer["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        writer["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"],
        false
    );
    assert_eq!(
        writer["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(writer["agent_action_contract"]["do_not_write_memory"], true);
    assert_eq!(
        writer["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        writer["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        writer["agent_action_contract"]
            ["require_separate_verified_outcome_ingestion_writer_execution"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_writer_execution_output_only(
    execution: &Value,
) {
    assert_eq!(execution["writes_state"], false);
    assert_eq!(execution["store_access_required"], false);
    assert_eq!(execution["mcp_tool_registered"], false);
    assert_eq!(
        execution["verified_outcome_ingestion_writer_execution_gate_performed_by_this_tool"],
        true
    );
    assert_eq!(
        execution["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(execution["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(execution["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(
        execution["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        execution["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(execution["guardrails"]["read_only"], true);
    assert_eq!(execution["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(execution["guardrails"]["writes_state"], false);
    assert_eq!(execution["guardrails"]["store_access_required"], false);
    assert_eq!(execution["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        execution["guardrails"]["requires_ready_verified_outcome_ingestion_writer"],
        true
    );
    assert_eq!(
        execution["guardrails"]
            ["requires_explicit_verified_outcome_ingestion_writer_execution_decision"],
        true
    );
    assert_eq!(
        execution["guardrails"]["performs_verified_outcome_ingestion_writer_execution_gate"],
        true
    );
    assert_eq!(
        execution["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(execution["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        execution["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(execution["guardrails"]["memory_write_allowed"], false);
    assert_eq!(
        execution["guardrails"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(execution["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        execution["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"],
        false
    );
    assert_eq!(
        execution["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        execution["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        execution["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        execution["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        execution["agent_action_contract"]
            ["require_separate_verified_outcome_ingestion_persistence"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_persistence_output_only(persistence: &Value) {
    assert_eq!(persistence["writes_state"], false);
    assert_eq!(persistence["store_access_required"], false);
    assert_eq!(persistence["mcp_tool_registered"], false);
    assert_eq!(
        persistence["verified_outcome_ingestion_persistence_gate_performed_by_this_tool"],
        true
    );
    assert_eq!(
        persistence["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(persistence["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(persistence["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(
        persistence["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        persistence["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(persistence["guardrails"]["read_only"], true);
    assert_eq!(persistence["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(persistence["guardrails"]["writes_state"], false);
    assert_eq!(persistence["guardrails"]["store_access_required"], false);
    assert_eq!(persistence["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        persistence["guardrails"]["requires_ready_verified_outcome_ingestion_writer_execution"],
        true
    );
    assert_eq!(
        persistence["guardrails"]
            ["requires_explicit_verified_outcome_ingestion_persistence_decision"],
        true
    );
    assert_eq!(
        persistence["guardrails"]["performs_verified_outcome_ingestion_persistence_gate"],
        true
    );
    assert_eq!(
        persistence["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(
        persistence["guardrails"]["performs_verified_outcome_store_write"],
        false
    );
    assert_eq!(persistence["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        persistence["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(persistence["guardrails"]["memory_write_allowed"], false);
    assert_eq!(
        persistence["guardrails"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        persistence["guardrails"]["verified_outcome_store_write_allowed"],
        false
    );
    assert_eq!(persistence["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        persistence["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"],
        false
    );
    assert_eq!(
        persistence["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        persistence["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        persistence["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        persistence["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        persistence["agent_action_contract"]
            ["require_separate_verified_outcome_ingestion_store_write"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_output_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight
            ["verified_outcome_ingestion_store_write_execution_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(preflight["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]["requires_ready_verified_outcome_ingestion_persistence"],
        true
    );
    assert_eq!(
        preflight["guardrails"]
            ["requires_explicit_verified_outcome_ingestion_store_write_execution_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]
            ["performs_verified_outcome_ingestion_store_write_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_store_write"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["verified_outcome_store_write_execution_allowed"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_store_write_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]
            ["require_separate_verified_outcome_store_write_execution"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]
            ["require_verified_outcome_write_evidence_after_store_write"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_write_evidence_preflight_output_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight["verified_outcome_ingestion_write_evidence_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(preflight["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]
            ["requires_ready_verified_outcome_ingestion_store_write_execution_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["requires_explicit_verified_outcome_ingestion_write_evidence"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_ingestion_write_evidence_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_store_write"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["agent_action_contract"]
            ["may_review_verified_outcome_ingestion_write_evidence_after_preflight"],
        preflight["status"] == "ready"
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_store_write_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]
            ["require_separate_verified_outcome_ingestion_write_evidence_review"],
        true
    );
}

fn assert_runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_output_only(
    preflight: &Value,
) {
    assert_eq!(preflight["writes_state"], false);
    assert_eq!(preflight["store_access_required"], false);
    assert_eq!(preflight["mcp_tool_registered"], false);
    assert_eq!(
        preflight
            ["verified_outcome_ingestion_write_evidence_review_preflight_performed_by_this_tool"],
        true
    );
    assert_eq!(
        preflight["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["verified_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["verified_outcome_ingested_by_this_tool"], false);
    assert_eq!(preflight["world_verdict_persisted_by_this_tool"], false);
    assert_eq!(
        preflight["durable_outcome_record_written_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["durable_outcome_ingestion_performed_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["read_only"], true);
    assert_eq!(preflight["guardrails"]["mutation_surface"], "output_only");
    assert_eq!(preflight["guardrails"]["writes_state"], false);
    assert_eq!(preflight["guardrails"]["store_access_required"], false);
    assert_eq!(preflight["guardrails"]["mcp_tool_registered"], false);
    assert_eq!(
        preflight["guardrails"]
            ["requires_ready_verified_outcome_ingestion_write_evidence_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]
            ["requires_explicit_verified_outcome_ingestion_write_evidence_review_decision"],
        true
    );
    assert_eq!(
        preflight["guardrails"]
            ["performs_verified_outcome_ingestion_write_evidence_review_preflight"],
        true
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_admission"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_store_write"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["performs_verified_outcome_ingestion"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_world_verdict"], false);
    assert_eq!(
        preflight["guardrails"]["durable_outcome_record_written"],
        false
    );
    assert_eq!(preflight["guardrails"]["memory_write_allowed"], false);
    assert_eq!(
        preflight["guardrails"]["outcome_ingestion_allowed_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["verified_outcome_admission_allowed"],
        false
    );
    assert_eq!(
        preflight["guardrails"]["verified_outcome_store_written_by_this_tool"],
        false
    );
    assert_eq!(preflight["guardrails"]["persists_outcome_record"], false);
    assert_eq!(
        preflight["agent_action_contract"]
            ["may_enter_verified_outcome_ingestion_admission_after_preflight"],
        preflight["status"] == "ready"
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_admission_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"],
        false
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_ingest_outcome"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_write_memory"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_world_verdict"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true
    );
    assert_eq!(
        preflight["agent_action_contract"]["require_separate_verified_outcome_ingestion_admission"],
        true
    );
}

fn assert_consumption_gates_pass(preflight: &Value) {
    let gates = preflight["acceptance_matrix"]
        .as_array()
        .expect("acceptance matrix");
    assert_eq!(gates.len(), 5);
    for (idx, expected_id) in ["C1", "C2", "C3", "C4", "C5"].iter().enumerate() {
        assert_eq!(gates[idx]["gate"], *expected_id);
        assert_eq!(gates[idx]["passed"], true, "{expected_id} should pass");
    }
}
