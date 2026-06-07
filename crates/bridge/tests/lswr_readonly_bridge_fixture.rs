use ab_bridge::lswr_snapshot_bridge::{
    build_readonly_bridge_snapshot, ReadOnlyBridgeSnapshot, ReadOnlyBridgeSnapshotOptions,
    LSWR_READONLY_BRIDGE_SNAPSHOT_SCHEMA,
};
use ab_world_core::{
    Action, ActionId, AdapterEvidence, AuthorityMode, BranchId, EntityId, Event, EventId,
    EventProvenance, Feedback, FeedbackId, Participant, ParticipantId, RollbackGroupId,
    RollbackRecord, TargetRef, Verdict, Verification, WorldId, WorldLedger, WorldLedgerSnapshot,
    SCHEMA_EVENT, SCHEMA_LEDGER_SNAPSHOT,
};
use serde_json::json;

const FIXTURE_JSON: &str = include_str!("fixtures/lswr_readonly_bridge_projection_v0.json");

#[test]
fn readonly_bridge_projection_fixture_matches_generated_projection() {
    let fixture: ReadOnlyBridgeSnapshot =
        serde_json::from_str(FIXTURE_JSON).expect("fixture projection json");
    let generated = build_readonly_bridge_snapshot(
        fixture_snapshot(),
        ReadOnlyBridgeSnapshotOptions {
            include_snapshot: false,
        },
    )
    .expect("generated projection");

    assert_eq!(
        serde_json::to_value(&fixture).expect("fixture value"),
        serde_json::to_value(&generated).expect("generated value")
    );
}

#[test]
fn readonly_bridge_projection_fixture_is_replay_safe() {
    let fixture: ReadOnlyBridgeSnapshot =
        serde_json::from_str(FIXTURE_JSON).expect("fixture projection json");

    assert_eq!(fixture.schema, LSWR_READONLY_BRIDGE_SNAPSHOT_SCHEMA);
    assert_eq!(fixture.snapshot_schema, SCHEMA_LEDGER_SNAPSHOT);
    assert!(fixture.snapshot_sha256.starts_with("sha256:"));
    assert_eq!(fixture.snapshot_sha256.len(), "sha256:".len() + 64);
    assert!(fixture.read_only);
    assert_eq!(fixture.mutation_surface, "none");
    assert!(!fixture.mcp_tool_registration);
    assert!(fixture.affordances.snapshot);
    assert!(fixture.affordances.query);
    assert!(!fixture.affordances.patch);
    assert!(!fixture.affordances.action);
    assert!(!fixture.affordances.invoke);
    assert!(fixture.snapshot.is_none());
}

#[test]
fn readonly_bridge_projection_fixture_keeps_stable_pretty_json() {
    let fixture: ReadOnlyBridgeSnapshot =
        serde_json::from_str(FIXTURE_JSON).expect("fixture projection json");
    let pretty = serde_json::to_string_pretty(&fixture).expect("pretty fixture json");

    assert_eq!(format!("{pretty}\n"), FIXTURE_JSON);
}

fn fixture_snapshot() -> WorldLedgerSnapshot {
    let world_id = WorldId::from_raw("world:readonly_bridge_fixture");
    let branch_id = BranchId::from_raw("branch:readonly_bridge_fixture");
    let entity_id = EntityId::from_raw("entity:cube_readonly_fixture");
    let action_id = ActionId::from_raw("action:move_cube_readonly_fixture");
    let result_event_id = EventId::from_raw("event:move_cube_readonly_fixture_result");
    let human_event_id = EventId::from_raw("event:move_cube_readonly_fixture_accept");
    let rollback_group = RollbackGroupId::from_raw("rollback:move_cube_readonly_fixture");

    let mut action = Action::new(
        "entity.move",
        Participant::ai(
            ParticipantId::from_raw("ai:codex"),
            AuthorityMode::Autonomous,
        ),
    );
    action.action_id = action_id.clone();
    action.target_refs.push(TargetRef::entity(&entity_id));
    action.expected_effect = json!({
        "entity_present": entity_id.as_str(),
        "semantic_position": [1.5, 0.0, -0.5],
        "human_visible": true
    });
    action.rollback_group = Some(rollback_group.clone());

    let verification = Verification::new(
        Some(action_id.clone()),
        Verdict::Verified,
        None,
        "semantic_state_query",
        Some(TargetRef::entity(&entity_id)),
        AdapterEvidence::new(
            "semantic_scene",
            "semantic_state_query",
            "semantic state reports the expected transform",
            true,
            json!({
                "entity_present": true,
                "position": [1.5, 0.0, -0.5]
            }),
        ),
    )
    .expect("verification");

    let mut result_event = Event::new(
        "runtime.action_result",
        world_id.clone(),
        Participant::runtime(ParticipantId::from_raw("runtime:semantic_scene"), "core"),
        EventProvenance {
            adapter: Some("semantic_scene".to_string()),
            source_schema: Some(SCHEMA_EVENT.to_string()),
            raw_available: true,
        },
    );
    result_event.event_id = result_event_id.clone();
    result_event.branch_id = Some(branch_id);
    result_event.refs.entities.push(entity_id.clone());
    result_event.refs.actions.push(action_id.clone());
    result_event
        .refs
        .rollback_groups
        .push(rollback_group.clone());
    result_event.payload = json!({
        "action_type": "entity.move",
        "applied": true,
        "semantic_position": [1.5, 0.0, -0.5]
    });
    result_event.verification = Some(verification);

    let mut human_event = Event::new(
        "human.accept",
        world_id,
        Participant::human(ParticipantId::from_raw("human:owner"), "core_review"),
        EventProvenance {
            adapter: Some("core_review".to_string()),
            source_schema: Some(SCHEMA_EVENT.to_string()),
            raw_available: true,
        },
    );
    human_event.event_id = human_event_id.clone();
    human_event.refs.events.push(result_event_id.clone());
    human_event.refs.actions.push(action_id.clone());
    human_event.refs.entities.push(entity_id.clone());
    human_event.payload = json!({
        "decision": "accept",
        "does_not_change_verification": true
    });

    let mut feedback = Feedback::new(human_event_id);
    feedback.feedback_id = FeedbackId::from_raw("feedback:readonly_bridge_fixture_accept");
    feedback.target.events.push(result_event_id.clone());
    feedback.target.actions.push(action_id.clone());
    feedback.target.entities.push(entity_id);
    feedback.target.rollback_groups.push(rollback_group.clone());
    feedback.raw = json!({"decision": "accept", "surface": "core_review"});
    feedback.normalized = json!({"decision": "accept", "does_not_change_verification": true});

    let mut rollback = RollbackRecord::new(
        rollback_group,
        json!({"entities": [{"entity_id": "entity:cube_readonly_fixture", "position": [0.0, 0.0, 0.0]}]}),
        json!({"entities": [{"entity_id": "entity:cube_readonly_fixture", "position": [1.5, 0.0, -0.5]}]}),
    );
    rollback.actions.push(action_id);
    rollback.verification_event_id = Some(result_event_id);

    let mut ledger = WorldLedger::new();
    ledger.append_action(action).expect("append action");
    ledger.register_rollback(rollback).expect("rollback");
    ledger.append_event(result_event).expect("result event");
    ledger.append_event(human_event).expect("human event");
    ledger.append_feedback(feedback).expect("feedback");
    ledger.to_snapshot()
}
