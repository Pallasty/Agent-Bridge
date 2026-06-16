use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_consumption_report, build_interaction_feedback_evidence_packet,
    build_interaction_feedback_live_runtime_lookup_design_preflight,
    build_interaction_feedback_next_revision_plan,
    build_interaction_feedback_packet_consumption_preflight,
    build_interaction_feedback_patch_apply_request,
    build_interaction_feedback_patch_execution_preflight, build_interaction_feedback_readback,
    build_interaction_feedback_runtime_executor_design_preflight,
    build_interaction_feedback_runtime_executor_live_lookup_preflight,
    build_interaction_feedback_runtime_executor_operator_submission_token_preflight,
    build_interaction_feedback_semantic_patch_draft,
    build_interaction_feedback_validation_envelope,
    render_interaction_feedback_consumption_preflight_report,
    render_interaction_feedback_live_runtime_lookup_design_preflight,
    render_interaction_feedback_next_revision_plan,
    render_interaction_feedback_patch_apply_request,
    render_interaction_feedback_patch_execution_preflight,
    render_interaction_feedback_runtime_executor_design_preflight,
    render_interaction_feedback_runtime_executor_live_lookup_preflight,
    render_interaction_feedback_runtime_executor_operator_submission_token_preflight,
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
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_LIVE_LOOKUP_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_TOKEN_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA, LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA,
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
