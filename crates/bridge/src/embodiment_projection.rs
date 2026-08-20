//! Read-only reconstruction of Embodiment Loop facts from the event spine.

use ab_store::SemanticEventRecord;
use serde_json::{json, Value};
use std::collections::BTreeMap;

use crate::semantic_event::{Affordance, SemanticEvent, SemanticObject, Verdict, VerdictStatus};

pub const EMBODIMENT_EVENT_SOURCE: &str = "embodiment";
pub const EMBODIMENT_PROJECTION_SCHEMA_V0: &str = "agent_bridge.embodiment_projection.v0";
pub const EMBODIMENT_SNAPSHOT_SCHEMA_V0: &str = "agent_bridge.embodiment_snapshot.v0";
pub const EMBODIMENT_ACTION_LINEAGE_SCHEMA_V0: &str = "agent_bridge.embodiment_action_lineage.v0";

/// Constructs a fact-only embodiment event. Callers supply a bounded payload
/// and must persist it through the existing semantic-event spine themselves.
pub fn embodiment_event(
    ts: i64,
    actor: impl Into<String>,
    action: impl Into<String>,
    body_id: impl Into<String>,
    facts: Value,
    verdict: VerdictStatus,
) -> SemanticEvent {
    let body_id = body_id.into();
    SemanticEvent {
        ts,
        actor: actor.into(),
        source: EMBODIMENT_EVENT_SOURCE.into(),
        action: action.into(),
        target: Some(body_id.clone()),
        object: SemanticObject {
            object_type: "agent_body".into(),
            source_adapter: EMBODIMENT_EVENT_SOURCE.into(),
            label: Some(body_id.clone()),
            object_id: Some(body_id.clone()),
        },
        affordance: Affordance {
            action_type: "observe".into(),
            risk_level: "low".into(),
            requires_gate: false,
            expected_effect: Some("record grounded embodiment state".into()),
        },
        verdict: Verdict {
            status: verdict,
            method: "embodiment_event_receipt".into(),
            evidence: json!({"body_id":body_id}),
        },
        facts,
    }
}

pub fn restart_confirmation_event(
    ts: i64,
    actor: impl Into<String>,
    body_id: impl Into<String>,
    intent_id: impl Into<String>,
) -> SemanticEvent {
    let body_id = body_id.into();
    embodiment_event(
        ts,
        actor,
        "intent_needs_confirmation_after_restart",
        body_id.clone(),
        json!({"body_id": body_id, "intent_id": intent_id.into(), "resumes_action": false}),
        VerdictStatus::Unknown,
    )
}

/// Projects only explicitly tagged embodiment events. Malformed or legacy rows
/// are counted, never guessed into state; this keeps restart recovery fail-closed.
pub fn project_embodiment_events(events: &[SemanticEventRecord]) -> Value {
    let mut rows = Vec::new();
    let mut rejected = 0_u64;
    for event in events
        .iter()
        .filter(|event| event.source == EMBODIMENT_EVENT_SOURCE)
    {
        let Ok(facts) = serde_json::from_str::<Value>(&event.facts) else {
            rejected += 1;
            continue;
        };
        let Some(body_id) = facts
            .get("body_id")
            .and_then(Value::as_str)
            .filter(|id| !id.is_empty())
        else {
            rejected += 1;
            continue;
        };
        rows.push(json!({"ts":event.ts,"action":event.action,"target":event.target,"verdict":event.verdict_status,"body_id":body_id,"facts":facts}));
    }
    rows.sort_by_key(|row| row["ts"].as_i64().unwrap_or_default());
    json!({"schema":EMBODIMENT_PROJECTION_SCHEMA_V0,"read_only":true,"resumes_actions":false,"events":rows,"rejected_rows":rejected})
}

fn fact<'a>(facts: &'a Value, key: &str) -> Option<&'a Value> {
    facts
        .get(key)
        .or_else(|| facts.get("facts").and_then(|nested| nested.get(key)))
}

fn action_receipt_intent_id<'a>(event: &SemanticEventRecord, facts: &'a Value) -> Option<&'a str> {
    if event.source == EMBODIMENT_EVENT_SOURCE && event.action == "action_receipt" {
        fact(facts, "intent_id").and_then(Value::as_str)
    } else {
        facts.get("embodiment_intent_id").and_then(Value::as_str)
    }
    .map(str::trim)
    .filter(|id| !id.is_empty())
}

fn action_receipt_body_id<'a>(event: &SemanticEventRecord, facts: &'a Value) -> Option<&'a str> {
    if event.source == EMBODIMENT_EVENT_SOURCE && event.action == "action_receipt" {
        fact(facts, "body_id").and_then(Value::as_str)
    } else {
        facts
            .pointer("/receipt/body_shadow/body_id")
            .and_then(Value::as_str)
    }
    .map(str::trim)
    .filter(|id| !id.is_empty())
}

/// Only these native event pairs are written by embodiment-aware action
/// surfaces.  A fact key alone must never enroll an unrelated semantic event
/// in the action-lineage audit.
fn is_whitelisted_action_receipt(event: &SemanticEventRecord) -> bool {
    matches!(
        (event.source.as_str(), event.action.as_str()),
        (EMBODIMENT_EVENT_SOURCE, "action_receipt")
            | ("terminal", "send_keys" | "split" | "resize")
            | ("browser", "navigate")
            | (
                "desktop",
                "type" | "key" | "move" | "moveto" | "click" | "scroll"
            )
    )
}

fn is_enrolled_action_receipt(event: &SemanticEventRecord, facts: &Value) -> bool {
    if !is_whitelisted_action_receipt(event) {
        return false;
    }
    (event.source == EMBODIMENT_EVENT_SOURCE && event.action == "action_receipt")
        || facts.get("embodiment_intent_id").is_some()
}

/// Audits only explicit intent identifiers and whitelisted event metadata.
/// Receipt payloads and evidence stay out of the projection.
fn project_action_lineage(events: &[SemanticEventRecord], source_event_limit: usize) -> Value {
    let mut intents = BTreeMap::<String, (i64, String)>::new();
    for event in events
        .iter()
        .filter(|event| event.source == EMBODIMENT_EVENT_SOURCE && event.action == "intent_opened")
    {
        let Ok(facts) = serde_json::from_str::<Value>(&event.facts) else {
            continue;
        };
        let Some(intent_id) = fact(&facts, "intent_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|id| !id.is_empty())
        else {
            continue;
        };
        let Some(body_id) = fact(&facts, "body_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|id| !id.is_empty())
        else {
            continue;
        };
        match intents.get_mut(intent_id) {
            Some((ts, stored_body_id)) if event.ts < *ts => {
                *ts = event.ts;
                *stored_body_id = body_id.to_string();
            }
            None => {
                intents.insert(intent_id.to_string(), (event.ts, body_id.to_string()));
            }
            _ => {}
        }
    }

    let mut rows = Vec::new();
    let mut matched = 0_u64;
    let mut unmatched_in_window = 0_u64;
    let mut out_of_order = 0_u64;
    let mut verified = 0_u64;
    let mut not_verified = 0_u64;
    let mut unknown = 0_u64;
    let mut explicit_body_matches = 0_u64;
    let mut explicit_body_mismatches = 0_u64;
    let mut body_not_recorded = 0_u64;
    let mut coverage_receipts = 0_u64;
    let mut missing_intent_link = 0_u64;

    for event in events {
        let Ok(facts) = serde_json::from_str::<Value>(&event.facts) else {
            continue;
        };
        if !is_enrolled_action_receipt(event, &facts) {
            continue;
        }
        coverage_receipts += 1;
        match event.verdict_status.as_str() {
            "verified" => verified += 1,
            "not_verified" => not_verified += 1,
            _ => unknown += 1,
        }
        let Some(intent_id) = action_receipt_intent_id(event, &facts) else {
            missing_intent_link += 1;
            body_not_recorded += 1;
            if rows.len() < 100 {
                rows.push(json!({
                    "ts": event.ts,
                    "source": event.source,
                    "action": event.action,
                    "target": Value::Null,
                    "intent_id": Value::Null,
                    "lineage_status": "missing_intent_link",
                    "verdict": event.verdict_status,
                    "body_binding_status": "not_recorded",
                }));
            }
            continue;
        };
        let lineage_status = match intents.get(intent_id) {
            Some((intent_ts, _)) if *intent_ts <= event.ts => {
                matched += 1;
                "matched_prior_intent"
            }
            Some(_) => {
                out_of_order += 1;
                "receipt_precedes_intent"
            }
            None => {
                unmatched_in_window += 1;
                "no_prior_intent_in_window"
            }
        };
        let receipt_body_id = action_receipt_body_id(event, &facts);
        let body_binding_status = match (intents.get(intent_id), receipt_body_id) {
            (Some((_, intent_body_id)), Some(receipt_body_id))
                if intent_body_id == receipt_body_id =>
            {
                explicit_body_matches += 1;
                "explicit_match"
            }
            (Some(_), Some(_)) => {
                explicit_body_mismatches += 1;
                "explicit_mismatch"
            }
            _ => {
                body_not_recorded += 1;
                "not_recorded"
            }
        };
        if rows.len() < 100 {
            rows.push(json!({
                "ts": event.ts,
                "source": event.source,
                "action": event.action,
                "target": event.target,
                "intent_id": intent_id,
                "lineage_status": lineage_status,
                "verdict": event.verdict_status,
                "body_binding_status": body_binding_status,
            }));
        }
    }
    rows.sort_by_key(|row| row["ts"].as_i64().unwrap_or_default());
    let receipt_count = matched + unmatched_in_window + out_of_order;
    let source_truncated_possible = events.len() >= source_event_limit;

    json!({
        "schema": EMBODIMENT_ACTION_LINEAGE_SCHEMA_V0,
        "mode": "read_only_audit",
        "source_event_count": events.len(),
        "source_event_limit": source_event_limit,
        "source_truncated_possible": source_truncated_possible,
        "global_completeness_claimed": false,
        "all_actions_traceable_claimed": false,
        "verified_real_world_outcome_claimed": false,
        "counts": {
            "intents": intents.len(),
            "coverage_receipts": coverage_receipts,
            "intent_linked_receipts": receipt_count,
            "missing_intent_link": missing_intent_link,
            "matched_prior_intent": matched,
            "unmatched_in_window": unmatched_in_window,
            "receipt_precedes_intent": out_of_order,
            "verdict": {
                "verified": verified,
                "not_verified": not_verified,
                "unknown": unknown,
            },
            "body_binding": {
                "explicit_match": explicit_body_matches,
                "explicit_mismatch": explicit_body_mismatches,
                "not_recorded": body_not_recorded,
            },
        },
        "traceability_within_window": if receipt_count > 0 {
            Some(matched as f64 / receipt_count as f64)
        } else {
            None
        },
        "intent_link_coverage": if coverage_receipts > 0 {
            Some(receipt_count as f64 / coverage_receipts as f64)
        } else {
            None
        },
        "rows": rows,
        "rows_truncated": coverage_receipts as usize > 100,
        "executes_actions": false,
        "resumes_actions": false,
        "changes_authority": false,
        "policy_change_allowed": false,
        "reason": "lineage is bounded to explicitly enrolled receipts in the selected event window; missing identifiers are counted, while missing bodies, evidence, and events are never inferred",
    })
}

/// Reconstruct only durable intent candidates from the append-only event log.
/// Unknown, failed, or restart-interrupted outcomes remain confirmation-gated.
fn project_open_intents(events: &[SemanticEventRecord]) -> Vec<Value> {
    let mut ordered = events
        .iter()
        .filter(|event| event.source == EMBODIMENT_EVENT_SOURCE)
        .collect::<Vec<_>>();
    ordered.sort_by_key(|event| event.ts);

    let mut states = BTreeMap::<String, Value>::new();
    for event in ordered {
        let Ok(facts) = serde_json::from_str::<Value>(&event.facts) else {
            continue;
        };
        let Some(intent_id) = fact(&facts, "intent_id")
            .and_then(Value::as_str)
            .filter(|id| !id.is_empty())
        else {
            continue;
        };
        let body_id = fact(&facts, "body_id")
            .and_then(Value::as_str)
            .or_else(|| event.target.as_deref())
            .unwrap_or("unknown-body");
        let action_kind = fact(&facts, "action_kind")
            .and_then(Value::as_str)
            .unwrap_or("unknown");

        let state = match event.action.as_str() {
            "intent_opened" => "open",
            "intent_needs_confirmation_after_restart" => "needs_confirmation",
            "action_receipt" if event.verdict_status == "verified" => "completed",
            "action_receipt" => "needs_confirmation",
            _ => continue,
        };
        states.insert(
            intent_id.to_string(),
            json!({
                "intent_id": intent_id,
                "body_id": body_id,
                "action_kind": action_kind,
                "state": state,
                "last_event_ts": event.ts,
                "resumes_action": false,
            }),
        );
    }

    states
        .into_values()
        .filter(|intent| {
            matches!(
                intent.get("state").and_then(Value::as_str),
                Some("open" | "needs_confirmation")
            )
        })
        .collect()
}

/// Add the current local body observation to the fact projection without
/// inferring intents or turning a restart into an execution opportunity.
pub fn project_embodiment_snapshot(
    events: &[SemanticEventRecord],
    body_status: &Value,
    source_event_limit: usize,
) -> Value {
    let mut projection = project_embodiment_events(events);
    let status = body_status
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let observed_at_unix_ms = body_status
        .pointer("/sample/observed_at_unix_ms")
        .and_then(Value::as_i64);
    let body_id = "body-mac";
    let online = status == "ok";

    projection["schema"] = Value::String(EMBODIMENT_SNAPSHOT_SCHEMA_V0.to_string());
    projection["body"] = json!({
        "body_id": body_id,
        "kind": "mac",
        "label": "current mac",
        "authority_scope": "local",
        "online": online,
        "read_only": true,
    });
    projection["observations"] = json!([{
        "schema": "agent_bridge.observation.v0",
        "body_id": body_id,
        "source": "body_status",
        "observed_at_unix_ms": observed_at_unix_ms,
        "freshness": if online { "on_demand" } else { "unavailable" },
        "confidence": if online { 1.0 } else { 0.0 },
        "payload": body_status,
    }]);
    let open_intents = project_open_intents(events);
    projection["open_intents"] = Value::Array(open_intents.clone());
    projection["open_intents_complete"] = Value::Bool(false);
    projection["recovery"] = json!({
        "mode": "confirmation_required",
        "resumes_actions": false,
        "candidate_count": open_intents.len(),
    });
    projection["action_lineage"] = project_action_lineage(events, source_event_limit);
    projection
}

#[cfg(test)]
mod tests {
    use super::*;
    fn event(source: &str, facts: &str) -> SemanticEventRecord {
        SemanticEventRecord {
            ts: 2,
            actor: "test".into(),
            source: source.into(),
            action: "intent_opened".into(),
            target: None,
            verdict_status: "unknown".into(),
            verdict_method: "test".into(),
            evidence: None,
            facts: facts.into(),
            descriptor: None,
        }
    }
    #[test]
    fn projection_ignores_untagged_and_malformed_rows() {
        let projection = project_embodiment_events(&[
            event("browser", r#"{"body_id":"body-mac"}"#),
            event(EMBODIMENT_EVENT_SOURCE, "not-json"),
            event(EMBODIMENT_EVENT_SOURCE, r#"{"body_id":"body-mac"}"#),
        ]);
        assert_eq!(projection["events"].as_array().unwrap().len(), 1);
        assert_eq!(projection["rejected_rows"], 1);
        assert_eq!(projection["resumes_actions"], false);
    }
    #[test]
    fn restart_event_is_unknown_and_never_resumes() {
        let event = restart_confirmation_event(1, "test", "body-mac", "intent-1");
        assert_eq!(event.verdict.status, VerdictStatus::Unknown);
        assert_eq!(event.facts["resumes_action"], false);
    }

    #[test]
    fn snapshot_adds_grounded_body_without_inventing_open_intents() {
        let snapshot = project_embodiment_snapshot(
            &[],
            &json!({
                "status": "ok",
                "sample": { "observed_at_unix_ms": 1234 }
            }),
            500,
        );
        assert_eq!(snapshot["schema"], EMBODIMENT_SNAPSHOT_SCHEMA_V0);
        assert_eq!(snapshot["body"]["body_id"], "body-mac");
        assert_eq!(snapshot["body"]["online"], true);
        assert_eq!(snapshot["observations"][0]["source"], "body_status");
        assert_eq!(snapshot["open_intents"].as_array().unwrap().len(), 0);
        assert_eq!(snapshot["open_intents_complete"], false);
        assert_eq!(snapshot["resumes_actions"], false);
    }

    #[test]
    fn snapshot_replays_intents_and_keeps_restart_recovery_gated() {
        let events = vec![
            event_with(
                1,
                "intent_opened",
                "unknown",
                r#"{"body_id":"body-mac","intent_id":"i-1","action_kind":"terminal_write"}"#,
            ),
            event_with(
                2,
                "intent_needs_confirmation_after_restart",
                "unknown",
                r#"{"body_id":"body-mac","intent_id":"i-1","resumes_action":false}"#,
            ),
        ];
        let snapshot = project_embodiment_snapshot(&events, &json!({"status":"unknown"}), 500);
        assert_eq!(snapshot["open_intents"][0]["intent_id"], "i-1");
        assert_eq!(snapshot["open_intents"][0]["state"], "needs_confirmation");
        assert_eq!(snapshot["open_intents"][0]["resumes_action"], false);
        assert_eq!(snapshot["recovery"]["mode"], "confirmation_required");
        assert_eq!(snapshot["recovery"]["resumes_actions"], false);
    }

    fn event_with(ts: i64, action: &str, verdict: &str, facts: &str) -> SemanticEventRecord {
        SemanticEventRecord {
            ts,
            actor: "test".into(),
            source: EMBODIMENT_EVENT_SOURCE.into(),
            action: action.into(),
            target: Some("body-mac".into()),
            verdict_status: verdict.into(),
            verdict_method: "test".into(),
            evidence: None,
            facts: facts.into(),
            descriptor: None,
        }
    }

    #[test]
    fn action_lineage_joins_native_receipts_without_exposing_payloads() {
        let events = vec![
            event_with(
                10,
                "intent_opened",
                "unknown",
                r#"{"body_id":"body-mac","intent_id":"i-1","action_kind":"terminal_write"}"#,
            ),
            SemanticEventRecord {
                ts: 20,
                actor: "mcp".into(),
                source: "terminal".into(),
                action: "send_keys".into(),
                target: Some("pane-1".into()),
                verdict_status: "verified".into(),
                verdict_method: "test".into(),
                evidence: Some(r#"{"secret":"must-not-project"}"#.into()),
                facts: r#"{"embodiment_intent_id":"i-1","receipt":{"keys":"secret","body_shadow":{"body_id":"body-mac"}}}"#.into(),
                descriptor: None,
            },
        ];
        let audit = project_action_lineage(&events, 500);
        assert_eq!(audit["counts"]["coverage_receipts"], 1);
        assert_eq!(audit["counts"]["intent_linked_receipts"], 1);
        assert_eq!(audit["counts"]["missing_intent_link"], 0);
        assert_eq!(audit["counts"]["matched_prior_intent"], 1);
        assert_eq!(audit["counts"]["unmatched_in_window"], 0);
        assert_eq!(audit["counts"]["verdict"]["verified"], 1);
        assert_eq!(audit["counts"]["body_binding"]["explicit_match"], 1);
        assert_eq!(audit["traceability_within_window"], 1.0);
        assert_eq!(audit["intent_link_coverage"], 1.0);
        assert_eq!(audit["global_completeness_claimed"], false);
        assert_eq!(audit["verified_real_world_outcome_claimed"], false);
        assert!(audit["rows"][0].get("receipt").is_none());
        assert!(audit["rows"][0].get("evidence").is_none());
        assert!(!audit.to_string().contains("secret"));
    }

    #[test]
    fn native_action_receipt_nested_intent_id_closes_lineage() {
        let events = vec![
            event_with(
                10,
                "intent_opened",
                "unknown",
                r#"{"body_id":"body-mac","intent_id":"focus-1","action_kind":"focus_window"}"#,
            ),
            event_with(
                20,
                "action_receipt",
                "verified",
                r#"{"body_id":"body-mac","facts":{"body_id":"body-mac","intent_id":"focus-1","action_kind":"focus_window","resumes_action":false}}"#,
            ),
        ];
        let audit = project_action_lineage(&events, 500);
        assert_eq!(audit["counts"]["intent_linked_receipts"], 1);
        assert_eq!(audit["counts"]["missing_intent_link"], 0);
        assert_eq!(audit["counts"]["matched_prior_intent"], 1);
        let snapshot = project_embodiment_snapshot(&events, &json!({"status":"ok"}), 500);
        assert!(snapshot["open_intents"].as_array().is_some_and(Vec::is_empty));
    }

    #[test]
    fn action_lineage_counts_privacy_minimal_receipt_without_intent() {
        let events = vec![SemanticEventRecord {
            ts: 20,
            actor: "mcp".into(),
            source: "terminal".into(),
            action: "send_keys".into(),
            target: None,
            verdict_status: "not_verified".into(),
            verdict_method: "action_coverage_receipt".into(),
            evidence: Some(r#"{"intent_linked":false}"#.into()),
            facts: r#"{"embodiment_intent_id":null,"receipt":{"schema":"agent_bridge.embodiment_action_coverage.v0","coverage_only":true,"intent_linked":false,"body_id":"body-mac","execution_succeeded":false}}"#.into(),
            descriptor: None,
        }];
        let audit = project_action_lineage(&events, 500);
        assert_eq!(audit["counts"]["coverage_receipts"], 1);
        assert_eq!(audit["counts"]["intent_linked_receipts"], 0);
        assert_eq!(audit["counts"]["missing_intent_link"], 1);
        assert_eq!(audit["counts"]["verdict"]["not_verified"], 1);
        assert_eq!(audit["intent_link_coverage"], 0.0);
        assert_eq!(audit["traceability_within_window"], Value::Null);
        assert_eq!(audit["rows"][0]["intent_id"], Value::Null);
        assert_eq!(audit["rows"][0]["lineage_status"], "missing_intent_link");
        assert_eq!(audit["rows"][0]["target"], Value::Null);
        assert!(!audit.to_string().contains("execution_succeeded"));
        assert!(!audit.to_string().contains("body-mac"));
    }

    #[test]
    fn action_lineage_enrolls_terminal_topology_coverage_receipts() {
        let events = ["split", "resize"]
            .into_iter()
            .enumerate()
            .map(|(index, action)| SemanticEventRecord {
                ts: 20 + index as i64,
                actor: "mcp".into(),
                source: "terminal".into(),
                action: action.into(),
                target: None,
                verdict_status: "unknown".into(),
                verdict_method: "action_coverage_receipt".into(),
                evidence: Some(r#"{"intent_linked":false}"#.into()),
                facts: r#"{"embodiment_intent_id":null,"receipt":{"schema":"agent_bridge.embodiment_action_coverage.v0","coverage_only":true,"intent_linked":false,"body_id":"body-mac","execution_succeeded":true}}"#.into(),
                descriptor: None,
            })
            .collect::<Vec<_>>();
        let audit = project_action_lineage(&events, 500);
        assert_eq!(audit["counts"]["coverage_receipts"], 2);
        assert_eq!(audit["counts"]["intent_linked_receipts"], 0);
        assert_eq!(audit["counts"]["missing_intent_link"], 2);
        assert_eq!(audit["counts"]["verdict"]["unknown"], 2);
        assert_eq!(audit["intent_link_coverage"], 0.0);
        assert_eq!(audit["rows"][0]["action"], "split");
        assert_eq!(audit["rows"][1]["action"], "resize");
        assert!(!audit.to_string().contains("execution_succeeded"));
        assert!(!audit.to_string().contains("body-mac"));
    }

    #[test]
    fn action_lineage_fails_closed_for_unmatched_order_and_truncation() {
        let events = vec![
            SemanticEventRecord {
                ts: 5,
                actor: "mcp".into(),
                source: "browser".into(),
                action: "navigate".into(),
                target: None,
                verdict_status: "unknown".into(),
                verdict_method: "test".into(),
                evidence: None,
                facts: r#"{"embodiment_intent_id":"future-intent","receipt":{}}"#.into(),
                descriptor: None,
            },
            event_with(
                10,
                "intent_opened",
                "unknown",
                r#"{"body_id":"body-mac","intent_id":"future-intent"}"#,
            ),
            SemanticEventRecord {
                ts: 15,
                actor: "mcp".into(),
                source: "terminal".into(),
                action: "send_keys".into(),
                target: None,
                verdict_status: "not_verified".into(),
                verdict_method: "test".into(),
                evidence: None,
                facts: r#"{"embodiment_intent_id":"missing-intent","receipt":{}}"#.into(),
                descriptor: None,
            },
        ];
        let audit = project_action_lineage(&events, events.len());
        assert_eq!(audit["counts"]["receipt_precedes_intent"], 1);
        assert_eq!(audit["counts"]["unmatched_in_window"], 1);
        assert_eq!(audit["counts"]["verdict"]["unknown"], 1);
        assert_eq!(audit["counts"]["verdict"]["not_verified"], 1);
        assert_eq!(audit["counts"]["body_binding"]["not_recorded"], 2);
        assert_eq!(audit["traceability_within_window"], 0.0);
        assert_eq!(audit["source_truncated_possible"], true);
        assert_eq!(audit["all_actions_traceable_claimed"], false);
        assert_eq!(audit["policy_change_allowed"], false);
    }

    #[test]
    fn action_lineage_ignores_unwhitelisted_events_even_with_intent_key() {
        let events = vec![
            event_with(
                10,
                "intent_opened",
                "unknown",
                r#"{"body_id":"body-mac","intent_id":"i-1"}"#,
            ),
            SemanticEventRecord {
                ts: 20,
                actor: "mcp".into(),
                source: "future_adapter".into(),
                action: "write".into(),
                target: Some("opaque-target".into()),
                verdict_status: "verified".into(),
                verdict_method: "test".into(),
                evidence: Some(r#"{"secret":"must-not-project"}"#.into()),
                facts: r#"{"embodiment_intent_id":"i-1","receipt":{"secret":"must-not-project"}}"#
                    .into(),
                descriptor: None,
            },
        ];
        let audit = project_action_lineage(&events, 500);
        assert_eq!(audit["counts"]["intents"], 1);
        assert_eq!(audit["counts"]["intent_linked_receipts"], 0);
        assert_eq!(audit["counts"]["matched_prior_intent"], 0);
        assert!(audit["rows"].as_array().expect("rows").is_empty());
        assert!(!audit.to_string().contains("secret"));
    }
}
