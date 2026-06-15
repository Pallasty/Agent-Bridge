use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_readback, validate_interaction_feedback_fixture,
    LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA, LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA,
    LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA,
};
use serde_json::{json, Value};

const FIXTURE_JSON: &str = include_str!("fixtures/lswr_interaction_feedback_fixture_v0.json");

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
fn interaction_feedback_fixture_pretty_json_roundtrips() {
    let fixture = fixture();
    let pretty = serde_json::to_string_pretty(&fixture).expect("pretty fixture json");
    let reparsed: Value = serde_json::from_str(&pretty).expect("reparse pretty fixture json");

    assert_eq!(reparsed, fixture);
}

fn fixture() -> Value {
    serde_json::from_str(FIXTURE_JSON).expect("interaction feedback fixture json")
}
