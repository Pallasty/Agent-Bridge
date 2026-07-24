//! Read-only reconstruction of Embodiment Loop facts from the event spine.

use ab_store::SemanticEventRecord;
use serde_json::{json, Value};

use crate::semantic_event::{Affordance, SemanticEvent, SemanticObject, Verdict, VerdictStatus};

pub const EMBODIMENT_EVENT_SOURCE: &str = "embodiment";
pub const EMBODIMENT_PROJECTION_SCHEMA_V0: &str = "agent_bridge.embodiment_projection.v0";

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
}
