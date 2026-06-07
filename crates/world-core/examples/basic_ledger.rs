use ab_world_core::{
    Action, ActionId, AdapterEvidence, AuthorityMode, BranchId, EntityId, Event, EventId,
    EventProvenance, Feedback, Participant, ParticipantId, RollbackGroupId, RollbackRecord,
    TargetRef, Verdict, Verification, WorldId, WorldLedger, WorldRef, SCHEMA_EVENT,
};
use serde_json::json;

fn main() -> ab_world_core::Result<()> {
    let world_id = WorldId::from_raw("world:demo");
    let branch_id = BranchId::from_raw("branch:main");
    let entity_id = EntityId::from_raw("entity:cube_01");
    let rollback_group = RollbackGroupId::from_raw("rollback:move_cube_01");
    let world = WorldRef::new(world_id.clone(), branch_id.clone());

    let ai = Participant::ai(
        ParticipantId::from_raw("ai:codex"),
        AuthorityMode::Autonomous,
    );
    let runtime = Participant::runtime(ParticipantId::from_raw("runtime:web"), "threejs_scene");
    let human = Participant::human(ParticipantId::from_raw("human:owner"), "browser_ui");

    let mut action = Action::new("entity.move", ai);
    action.action_id = ActionId::from_raw("action:move_cube_01");
    action.target_refs.push(TargetRef::entity(&entity_id));
    action.expected_effect = json!({
        "entity_present": entity_id.as_str(),
        "position": [1.5, 1.0, -0.5],
        "human_visible": true
    });
    action.rollback_group = Some(rollback_group.clone());

    let verification = Verification::new(
        Some(action.action_id.clone()),
        Verdict::Verified,
        None,
        "web_scene_projection_check",
        Some(TargetRef::entity(&entity_id)),
        AdapterEvidence::new(
            "threejs_web",
            "web_scene_projection_check",
            "entity was projected, hit-testable, and visible to the human",
            true,
            json!({
                "bounds_nonzero": true,
                "hit_testable": true,
                "pixel_coverage": 0.087
            }),
        ),
    )?;

    let mut runtime_event = Event::new(
        "runtime.action_result",
        world_id.clone(),
        runtime,
        EventProvenance {
            adapter: Some("threejs_web".to_string()),
            source_schema: Some(SCHEMA_EVENT.to_string()),
            raw_available: true,
        },
    );
    runtime_event.event_id = EventId::from_raw("event:move_cube_01");
    runtime_event.branch_id = Some(branch_id);
    runtime_event.refs.entities.push(entity_id.clone());
    runtime_event.refs.actions.push(action.action_id.clone());
    runtime_event
        .refs
        .rollback_groups
        .push(rollback_group.clone());
    runtime_event.payload = json!({
        "action_type": action.action_type,
        "applied": true,
        "position": [1.5, 1.0, -0.5]
    });
    runtime_event.verification = Some(verification);

    let mut human_event = Event::new(
        "human.accept",
        world_id,
        human,
        EventProvenance {
            adapter: Some("browser_ui".to_string()),
            source_schema: Some(SCHEMA_EVENT.to_string()),
            raw_available: true,
        },
    );
    human_event.event_id = EventId::from_raw("event:human_accept_01");
    human_event.refs.actions.push(action.action_id.clone());
    human_event.refs.events.push(runtime_event.event_id.clone());
    human_event.payload = json!({
        "decision": "accept",
        "decision_scope": "presentation",
        "does_not_change_verification": true
    });

    let mut feedback = Feedback::new(human_event.event_id.clone());
    feedback.target.actions.push(action.action_id.clone());
    feedback.raw = json!({
        "input": "accept_button",
        "surface": "browser_ui"
    });
    feedback.normalized = json!({
        "decision": "accept",
        "decision_scope": "presentation"
    });

    let mut rollback = RollbackRecord::new(
        rollback_group.clone(),
        json!({
            "entities": [{
                "entity_id": entity_id.as_str(),
                "position": [0.0, 1.0, 0.0]
            }]
        }),
        json!({
            "entities": [{
                "entity_id": entity_id.as_str(),
                "position": [1.5, 1.0, -0.5]
            }]
        }),
    );
    rollback.actions.push(action.action_id.clone());
    rollback.verification_event_id = Some(EventId::from_raw("event:move_cube_01"));

    let mut ledger = WorldLedger::new();
    ledger.append_action(action.clone())?;
    ledger.register_rollback(rollback)?;
    ledger.append_event(runtime_event)?;
    ledger.append_event(human_event)?;
    ledger.append_feedback(feedback)?;

    let evidence = ledger.query_evidence_by_action(&action.action_id);
    let summary = json!({
        "world": world,
        "actions": ledger.actions().len(),
        "events": ledger.events().len(),
        "verifications": ledger.verifications().len(),
        "feedback": ledger.feedback().len(),
        "rollback_groups": ledger.rollback_groups().count(),
        "action_evidence": evidence.iter().map(|record| {
            json!({
                "verdict": record.verdict.to_string(),
                "method": record.method,
                "verified_to": record.verified_to.as_ref().map(|target| {
                    json!({
                        "kind": target.kind.as_str(),
                        "id": target.id.as_str()
                    })
                })
            })
        }).collect::<Vec<_>>()
    });

    println!(
        "{}",
        serde_json::to_string_pretty(&summary).expect("summary json")
    );
    Ok(())
}
