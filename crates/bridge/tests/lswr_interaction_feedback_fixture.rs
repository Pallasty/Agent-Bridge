use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_readback, build_interaction_feedback_validation_envelope,
    render_interaction_feedback_validation_envelope, validate_interaction_feedback_fixture,
    LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA, LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_ENVELOPE_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA,
};
use serde_json::{json, Value};

const FIXTURE_JSON: &str = include_str!("fixtures/lswr_interaction_feedback_fixture_v0.json");
const ENVELOPE_MARKDOWN: &str =
    include_str!("fixtures/lswr_interaction_feedback_validation_envelope_v0.md");

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
