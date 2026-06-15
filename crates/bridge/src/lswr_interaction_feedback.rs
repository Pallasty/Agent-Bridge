use std::collections::{BTreeMap, BTreeSet};

use serde_json::{json, Value};

pub const LSWR_INTERACTION_FEEDBACK_FIXTURE_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_fixture.v0";
pub const LSWR_INTERACTION_FEEDBACK_VALIDATION_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_validation.v0";
pub const LSWR_INTERACTION_FEEDBACK_READBACK_SCHEMA: &str =
    "agent_bridge.lswr.interaction_feedback_readback.v0";

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
