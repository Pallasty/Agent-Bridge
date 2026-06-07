use ab_world_core::{
    Action, ActionId, ActionQuery, ActionQueryFilters, ActionQueryId, AdapterEvidence,
    AuthorityMode, BranchId, EntityId, Event, EventId, EventProvenance, EventQuery,
    EventQueryFilters, EventQueryId, EvidenceQuery, EvidenceQueryFilters, EvidenceQueryId,
    Feedback, FeedbackQuery, FeedbackQueryFilters, FeedbackQueryId, Participant, ParticipantId,
    ParticipantKind, RollbackGroupId, RollbackQuery, RollbackQueryFilters, RollbackQueryId,
    RollbackRecord, TargetRef, Verdict, Verification, WorldCoreError, WorldId, WorldLedger,
    WorldLedgerSnapshot, SCHEMA_EVENT, SCHEMA_LEDGER_SNAPSHOT,
};
use serde_json::json;

#[derive(Debug, Clone)]
struct ClosureRefs {
    action_id: ActionId,
    entity_id: EntityId,
    result_event_id: EventId,
    human_event_id: EventId,
    rollback_group: RollbackGroupId,
}

#[test]
fn ledger_snapshot_round_trip_preserves_query_closure() {
    let (ledger, refs) = build_closure_ledger();

    let snapshot = ledger.to_snapshot();
    assert_eq!(snapshot.schema, SCHEMA_LEDGER_SNAPSHOT);
    assert_eq!(snapshot.actions.len(), 1);
    assert_eq!(snapshot.events.len(), 2);
    assert_eq!(snapshot.verifications.len(), 1);
    assert_eq!(snapshot.feedback.len(), 1);
    assert_eq!(snapshot.rollback_records.len(), 2);
    assert_eq!(
        snapshot.rollback_records[0].rollback_group.as_str(),
        "rollback:auxiliary_a"
    );
    assert_eq!(
        snapshot.rollback_records[1].rollback_group.as_str(),
        "rollback:move_cube_closure"
    );

    let encoded = serde_json::to_string_pretty(&snapshot).expect("snapshot json");
    let decoded: WorldLedgerSnapshot =
        serde_json::from_str(&encoded).expect("snapshot json decode");
    let restored = WorldLedger::from_snapshot(decoded).expect("snapshot import");

    assert_eq!(restored.to_snapshot(), snapshot);

    assert_eq!(
        restored.query_actions(&action_query(&refs)).summary,
        ledger.query_actions(&action_query(&refs)).summary
    );
    assert_eq!(
        restored.query_events(&event_query(&refs)).summary,
        ledger.query_events(&event_query(&refs)).summary
    );
    assert_eq!(
        restored.query_evidence(&evidence_query(&refs)).summary,
        ledger.query_evidence(&evidence_query(&refs)).summary
    );
    assert_eq!(
        restored.query_feedback(&feedback_query(&refs)).summary,
        ledger.query_feedback(&feedback_query(&refs)).summary
    );
    assert_eq!(
        restored.query_rollbacks(&rollback_query(&refs)).summary,
        ledger.query_rollbacks(&rollback_query(&refs)).summary
    );
}

#[test]
fn ledger_snapshot_import_validates_schema_and_core_invariants() {
    let (ledger, _) = build_closure_ledger();

    let mut bad_schema = ledger.to_snapshot();
    bad_schema.schema = "agent_bridge.lswr.ledger_snapshot.v999".to_string();
    assert_eq!(
        WorldLedger::from_snapshot(bad_schema).unwrap_err(),
        WorldCoreError::InvalidLedgerSnapshotSchema(
            "agent_bridge.lswr.ledger_snapshot.v999".to_string()
        )
    );

    let mut duplicate_action = ledger.to_snapshot();
    duplicate_action
        .actions
        .push(duplicate_action.actions[0].clone());
    assert_eq!(
        WorldLedger::from_snapshot(duplicate_action).unwrap_err(),
        WorldCoreError::DuplicateAction("action:move_cube_closure".to_string())
    );

    let mut laundering_feedback = ledger.to_snapshot();
    laundering_feedback.feedback[0].changes_world_verdict = true;
    assert_eq!(
        WorldLedger::from_snapshot(laundering_feedback).unwrap_err(),
        WorldCoreError::HumanDecisionChangesVerification
    );
}

fn build_closure_ledger() -> (WorldLedger, ClosureRefs) {
    let world_id = WorldId::from_raw("world:ledger_snapshot");
    let branch_id = BranchId::from_raw("branch:snapshot");
    let entity_id = EntityId::from_raw("entity:cube_closure");
    let action_id = ActionId::from_raw("action:move_cube_closure");
    let result_event_id = EventId::from_raw("event:move_cube_closure_result");
    let human_event_id = EventId::from_raw("event:move_cube_closure_accept");
    let rollback_group = RollbackGroupId::from_raw("rollback:move_cube_closure");

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
        "semantic_position": [1.25, 0.0, -0.75],
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
            "semantic state reports the moved entity at the expected transform",
            true,
            json!({
                "semantic_state_hash": "sha256:snapshot-demo",
                "entity_present": true,
                "position": [1.25, 0.0, -0.75]
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
        "semantic_position": [1.25, 0.0, -0.75]
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
        "decision_scope": "semantic_result",
        "does_not_change_verification": true
    });

    let mut feedback = Feedback::new(human_event_id.clone());
    feedback.target.events.push(result_event_id.clone());
    feedback.target.actions.push(action_id.clone());
    feedback.target.entities.push(entity_id.clone());
    feedback.target.rollback_groups.push(rollback_group.clone());
    feedback.target.adapter = Some("core_review".to_string());
    feedback.raw = json!({"decision": "accept", "surface": "core_review"});
    feedback.normalized = json!({"decision": "accept", "does_not_change_verification": true});

    let mut auxiliary_rollback = RollbackRecord::new(
        RollbackGroupId::from_raw("rollback:auxiliary_a"),
        json!({"entities": []}),
        json!({"entities": []}),
    );
    auxiliary_rollback
        .actions
        .push(ActionId::from_raw("action:auxiliary"));

    let mut rollback = RollbackRecord::new(
        rollback_group.clone(),
        json!({"entities": [{"entity_id": entity_id.as_str(), "position": [0.0, 0.0, 0.0]}]}),
        json!({"entities": [{"entity_id": entity_id.as_str(), "position": [1.25, 0.0, -0.75]}]}),
    );
    rollback.actions.push(action_id.clone());
    rollback.verification_event_id = Some(result_event_id.clone());

    let mut ledger = WorldLedger::new();
    ledger.append_action(action).expect("append action");
    ledger.register_rollback(rollback).expect("rollback");
    ledger
        .register_rollback(auxiliary_rollback)
        .expect("auxiliary rollback");
    ledger.append_event(result_event).expect("result event");
    ledger.append_event(human_event).expect("human event");
    ledger.append_feedback(feedback).expect("feedback");

    (
        ledger,
        ClosureRefs {
            action_id,
            entity_id,
            result_event_id,
            human_event_id,
            rollback_group,
        },
    )
}

fn action_query(refs: &ClosureRefs) -> ActionQuery {
    ActionQuery::with_id(
        ActionQueryId::from_raw("query:snapshot:action"),
        ActionQueryFilters {
            action_id: Some(refs.action_id.clone()),
            action_type: Some("entity.move".to_string()),
            source_participant_id: Some(ParticipantId::from_raw("ai:codex")),
            participant_kind: Some(ParticipantKind::Ai),
            authority_mode: Some(AuthorityMode::Autonomous),
            target_ref_kind: Some("entity".to_string()),
            target_ref_id: Some(refs.entity_id.to_string()),
            rollback_group: Some(refs.rollback_group.clone()),
            has_expected_effect: Some(true),
        },
    )
}

fn event_query(refs: &ClosureRefs) -> EventQuery {
    EventQuery::with_id(
        EventQueryId::from_raw("query:snapshot:events"),
        EventQueryFilters {
            action_id: Some(refs.action_id.clone()),
            rollback_group: Some(refs.rollback_group.clone()),
            adapter: Some("semantic_scene".to_string()),
            verdict: Some(Verdict::Verified),
            ..EventQueryFilters::default()
        },
    )
}

fn evidence_query(refs: &ClosureRefs) -> EvidenceQuery {
    EvidenceQuery::with_id(
        EvidenceQueryId::from_raw("query:snapshot:evidence"),
        EvidenceQueryFilters {
            action_id: Some(refs.action_id.clone()),
            entity_id: Some(refs.entity_id.clone()),
            verdict: Some(Verdict::Verified),
            method: Some("semantic_state_query".to_string()),
            adapter_kind: Some("semantic_scene".to_string()),
            ..EvidenceQueryFilters::default()
        },
    )
}

fn feedback_query(refs: &ClosureRefs) -> FeedbackQuery {
    FeedbackQuery::with_id(
        FeedbackQueryId::from_raw("query:snapshot:feedback"),
        FeedbackQueryFilters {
            source_event_id: Some(refs.human_event_id.clone()),
            target_event_id: Some(refs.result_event_id.clone()),
            action_id: Some(refs.action_id.clone()),
            entity_id: Some(refs.entity_id.clone()),
            rollback_group: Some(refs.rollback_group.clone()),
            adapter: Some("core_review".to_string()),
            changes_world_verdict: Some(false),
            ..FeedbackQueryFilters::default()
        },
    )
}

fn rollback_query(refs: &ClosureRefs) -> RollbackQuery {
    RollbackQuery::with_id(
        RollbackQueryId::from_raw("query:snapshot:rollback"),
        RollbackQueryFilters {
            rollback_group: Some(refs.rollback_group.clone()),
            action_id: Some(refs.action_id.clone()),
            verification_event_id: Some(refs.result_event_id.clone()),
            has_verification_event: Some(true),
        },
    )
}
