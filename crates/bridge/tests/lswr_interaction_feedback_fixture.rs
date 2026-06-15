use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_consumption_report, build_interaction_feedback_evidence_packet,
    build_interaction_feedback_next_revision_plan,
    build_interaction_feedback_packet_consumption_preflight, build_interaction_feedback_readback,
    build_interaction_feedback_semantic_patch_draft,
    build_interaction_feedback_validation_envelope,
    render_interaction_feedback_consumption_preflight_report,
    render_interaction_feedback_next_revision_plan,
    render_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_validation_envelope, validate_interaction_feedback_fixture,
    LSWR_INTERACTION_FEEDBACK_CONSUMPTION_PREFLIGHT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_EVIDENCE_PACKET_SCHEMA, LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_NEXT_REVISION_PLAN_SCHEMA, LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_SEMANTIC_PATCH_DRAFT_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA,
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
