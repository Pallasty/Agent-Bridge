//! Read-only reconstruction of Embodiment Loop facts from the event spine.

use ab_store::SemanticEventRecord;
use serde_json::{json, Value};
use std::collections::BTreeMap;

use crate::semantic_event::{Affordance, SemanticEvent, SemanticObject, Verdict, VerdictStatus};

pub const EMBODIMENT_EVENT_SOURCE: &str = "embodiment";
pub const EMBODIMENT_PROJECTION_SCHEMA_V0: &str = "agent_bridge.embodiment_projection.v0";
pub const EMBODIMENT_SNAPSHOT_SCHEMA_V0: &str = "agent_bridge.embodiment_snapshot.v0";

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
pub fn project_embodiment_snapshot(events: &[SemanticEventRecord], body_status: &Value) -> Value {
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
        let snapshot = project_embodiment_snapshot(&events, &json!({"status":"unknown"}));
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
}
