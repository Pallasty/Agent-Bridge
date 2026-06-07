use ab_world_core::{
    Action, ActionId, ActionQuery, ActionQueryFilters, ActionQueryId, AdapterEvidence,
    AuthorityMode, BranchId, EntityId, Event, EventId, EventProvenance, EventQuery,
    EventQueryFilters, EventQueryId, EvidenceQuery, EvidenceQueryFilters, EvidenceQueryId,
    Feedback, FeedbackQuery, FeedbackQueryFilters, FeedbackQueryId, Participant, ParticipantId,
    ParticipantKind, RollbackGroupId, RollbackQuery, RollbackQueryFilters, RollbackQueryId,
    RollbackRecord, TargetRef, Verdict, Verification, WorldId, WorldLedger, SCHEMA_ACTION_QUERY,
    SCHEMA_EVENT, SCHEMA_EVENT_QUERY, SCHEMA_EVIDENCE_QUERY, SCHEMA_FEEDBACK_QUERY,
    SCHEMA_ROLLBACK_QUERY,
};
use serde_json::json;

#[test]
fn core_query_closure_reads_action_event_evidence_feedback_and_rollback() {
    let world_id = WorldId::from_raw("world:core_query_closure");
    let branch_id = BranchId::from_raw("branch:acceptance");
    let entity_id = EntityId::from_raw("entity:cube_closure");
    let action_id = ActionId::from_raw("action:move_cube_closure");
    let result_event_id = EventId::from_raw("event:move_cube_closure_result");
    let human_event_id = EventId::from_raw("event:move_cube_closure_accept");
    let rollback_group = RollbackGroupId::from_raw("rollback:move_cube_closure");

    let ai = Participant::ai(
        ParticipantId::from_raw("ai:codex"),
        AuthorityMode::Autonomous,
    );
    let runtime = Participant::runtime(ParticipantId::from_raw("runtime:semantic_scene"), "core");
    let human = Participant::human(ParticipantId::from_raw("human:owner"), "core_review");

    let mut action = Action::new("entity.move", ai);
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
                "semantic_state_hash": "sha256:closure-demo",
                "entity_present": true,
                "position": [1.25, 0.0, -0.75]
            }),
        ),
    )
    .expect("verification");

    let mut result_event = Event::new(
        "runtime.action_result",
        world_id.clone(),
        runtime,
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
        human,
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
    feedback.raw = json!({
        "decision": "accept",
        "surface": "core_review"
    });
    feedback.normalized = json!({
        "decision": "accept",
        "does_not_change_verification": true
    });

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
    ledger.append_event(result_event).expect("result event");
    ledger.append_event(human_event).expect("human event");
    ledger.append_feedback(feedback).expect("feedback");

    let action_response = ledger.query_actions(&ActionQuery::with_id(
        ActionQueryId::from_raw("query:closure:action"),
        ActionQueryFilters {
            action_id: Some(action_id.clone()),
            action_type: Some("entity.move".to_string()),
            source_participant_id: Some(ParticipantId::from_raw("ai:codex")),
            participant_kind: Some(ParticipantKind::Ai),
            authority_mode: Some(AuthorityMode::Autonomous),
            target_ref_kind: Some("entity".to_string()),
            target_ref_id: Some(entity_id.to_string()),
            rollback_group: Some(rollback_group.clone()),
            has_expected_effect: Some(true),
        },
    ));
    assert_eq!(action_response.schema, SCHEMA_ACTION_QUERY);
    assert_eq!(action_response.actions.len(), 1);
    assert_eq!(action_response.summary.action_count, 1);
    assert_eq!(action_response.summary.rollback_linked_action_count, 1);
    assert_eq!(action_response.summary.expected_effect_payload_count, 1);

    let event_response = ledger.query_events(&EventQuery::with_id(
        EventQueryId::from_raw("query:closure:events"),
        EventQueryFilters {
            action_id: Some(action_id.clone()),
            rollback_group: Some(rollback_group.clone()),
            adapter: Some("semantic_scene".to_string()),
            verdict: Some(Verdict::Verified),
            ..EventQueryFilters::default()
        },
    ));
    assert_eq!(event_response.schema, SCHEMA_EVENT_QUERY);
    assert_eq!(event_response.events.len(), 1);
    assert_eq!(event_response.events[0].event_id, result_event_id);
    assert_eq!(
        event_response.summary.event_type_counts["runtime.action_result"],
        1
    );
    assert_eq!(
        event_response.summary.embedded_verdict_counts["verified"],
        1
    );

    let evidence_response = ledger.query_evidence(&EvidenceQuery::with_id(
        EvidenceQueryId::from_raw("query:closure:evidence"),
        EvidenceQueryFilters {
            action_id: Some(action_id.clone()),
            entity_id: Some(entity_id.clone()),
            verdict: Some(Verdict::Verified),
            method: Some("semantic_state_query".to_string()),
            adapter_kind: Some("semantic_scene".to_string()),
            ..EvidenceQueryFilters::default()
        },
    ));
    assert_eq!(evidence_response.schema, SCHEMA_EVIDENCE_QUERY);
    assert_eq!(evidence_response.events.len(), 1);
    assert_eq!(evidence_response.verifications.len(), 1);
    assert_eq!(
        evidence_response.verifications[0]
            .verified_to
            .as_ref()
            .unwrap(),
        &TargetRef::entity(&entity_id)
    );
    assert_eq!(evidence_response.summary.verdict_counts["verified"], 1);
    assert_eq!(
        evidence_response.summary.adapter_counts["semantic_scene"],
        1
    );
    assert!(evidence_response.verifications[0]
        .evidence
        .payload
        .get("screenshot")
        .is_none());
    assert!(evidence_response.verifications[0]
        .evidence
        .payload
        .get("pixel_coverage")
        .is_none());

    let feedback_response = ledger.query_feedback(&FeedbackQuery::with_id(
        FeedbackQueryId::from_raw("query:closure:feedback"),
        FeedbackQueryFilters {
            source_event_id: Some(human_event_id),
            target_event_id: Some(EventId::from_raw("event:move_cube_closure_result")),
            action_id: Some(action_id.clone()),
            entity_id: Some(entity_id),
            rollback_group: Some(rollback_group.clone()),
            adapter: Some("core_review".to_string()),
            changes_world_verdict: Some(false),
            ..FeedbackQueryFilters::default()
        },
    ));
    assert_eq!(feedback_response.schema, SCHEMA_FEEDBACK_QUERY);
    assert_eq!(feedback_response.feedback.len(), 1);
    assert_eq!(
        feedback_response.feedback[0].normalized["decision"],
        "accept"
    );
    assert_eq!(
        feedback_response
            .summary
            .world_verdict_mutation_attempt_count,
        0
    );
    assert_eq!(feedback_response.summary.target_rollback_group_count, 1);

    let rollback_response = ledger.query_rollbacks(&RollbackQuery::with_id(
        RollbackQueryId::from_raw("query:closure:rollback"),
        RollbackQueryFilters {
            rollback_group: Some(rollback_group),
            action_id: Some(action_id),
            verification_event_id: Some(EventId::from_raw("event:move_cube_closure_result")),
            has_verification_event: Some(true),
        },
    ));
    assert_eq!(rollback_response.schema, SCHEMA_ROLLBACK_QUERY);
    assert_eq!(rollback_response.rollback_records.len(), 1);
    assert_eq!(rollback_response.summary.action_ref_count, 1);
    assert_eq!(rollback_response.summary.before_payload_count, 1);
    assert_eq!(rollback_response.summary.after_payload_count, 1);
    assert_eq!(rollback_response.summary.verification_event_count, 1);
}
