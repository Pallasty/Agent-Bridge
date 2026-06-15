use std::collections::{BTreeMap, BTreeSet};

use serde_json::{json, Value};

const FIXTURE_JSON: &str = include_str!("fixtures/lswr_interaction_feedback_fixture_v0.json");

#[test]
fn interaction_feedback_fixture_has_expected_loop_and_boundaries() {
    let fixture = fixture();

    assert_eq!(
        fixture["schema"],
        "agent_bridge.lswr.interaction_feedback_fixture.v0"
    );
    assert_eq!(fixture["requires_screenshot_for_primary_readback"], false);
    assert_eq!(fixture["events"].as_array().expect("events").len(), 8);
    assert_eq!(fixture["feedback"].as_array().expect("feedback").len(), 1);

    let event_types: Vec<&str> = events(&fixture)
        .iter()
        .map(|event| event["event_type"].as_str().expect("event_type"))
        .collect();
    assert_eq!(
        event_types,
        vec![
            "human.select",
            "ai.patch_proposed",
            "runtime.patch_result",
            "presentation.state_changed",
            "runtime.verification_result",
            "human.reject",
            "feedback.explicit_text",
            "ai.patch_proposed",
        ]
    );

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
fn interaction_feedback_fixture_preserves_causality_and_verification_honesty() {
    let fixture = fixture();
    let events = events(&fixture);
    let mut event_positions = BTreeMap::new();

    for (idx, event) in events.iter().enumerate() {
        let event_id = event["event_id"].as_str().expect("event_id");
        assert!(
            event_positions.insert(event_id, idx).is_none(),
            "duplicate event id: {event_id}"
        );
    }

    for (idx, event) in events.iter().enumerate() {
        let cause = event["refs"]["cause_event_id"].as_str();
        if let Some(cause) = cause {
            let cause_idx = *event_positions
                .get(cause)
                .unwrap_or_else(|| panic!("missing cause event: {cause}"));
            assert!(
                cause_idx < idx,
                "cause event must appear before child event: {cause}"
            );
        }
    }

    let verification = event_by_id(&fixture, "evt_verify_patch_001");
    assert_eq!(verification["verification"]["verdict"], "not_verified");
    assert_eq!(
        verification["verification"]["reason"],
        "expected_effect_clause_failed"
    );
    assert_eq!(
        verification["verification"]["evidence"]["failed_clause_ids"],
        json!(["effect_walkway_clearance_001"])
    );

    let reject = event_by_id(&fixture, "evt_human_reject_001");
    assert_eq!(reject["payload"]["decision"], "reject");
    assert_eq!(reject["payload"]["does_not_change_verification"], true);
    assert_eq!(
        reject["refs"]["cause_event_id"], "evt_verify_patch_001",
        "human review must point at verification instead of rewriting it"
    );

    assert_eq!(
        fixture["verification_page"]["verifications"][0]["verdict"],
        "not_verified"
    );
}

#[test]
fn interaction_feedback_fixture_preserves_feedback_and_revision_hints() {
    let fixture = fixture();
    let feedback_event = event_by_id(&fixture, "evt_feedback_text_001");
    let feedback_record = &fixture["feedback"][0];

    assert_eq!(
        feedback_event["payload"]["raw"]["text"],
        feedback_record["raw"]["text"]
    );
    assert_eq!(
        feedback_record["verification_relation"]["changes_world_verdict"],
        false
    );
    assert_eq!(
        feedback_record["verification_relation"]["related_verification_event_id"],
        "evt_verify_patch_001"
    );

    let revision_patch = &event_by_id(&fixture, "evt_ai_patch_proposed_002")["payload"]["patch"];
    let sources: BTreeSet<&str> = revision_patch["revision_sources"]
        .as_array()
        .expect("revision sources")
        .iter()
        .map(|value| value.as_str().expect("source"))
        .collect();

    assert!(sources.contains("verify_patch_arrival_bath_move_001"));
    assert!(sources.contains("fb_arrival_crowded_001"));

    let report = readback_report(&fixture);
    assert_eq!(
        report,
        json!({
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
            ]
        })
    );
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

fn events(fixture: &Value) -> Vec<&Value> {
    fixture["events"]
        .as_array()
        .expect("events")
        .iter()
        .collect()
}

fn event_by_id<'a>(fixture: &'a Value, id: &str) -> &'a Value {
    events(fixture)
        .into_iter()
        .find(|event| event["event_id"] == id)
        .unwrap_or_else(|| panic!("missing event: {id}"))
}

fn readback_report(fixture: &Value) -> Value {
    fixture["expected_agent_readback"].clone()
}
