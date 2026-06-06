use crate::*;
use serde_json::{json, Value};

fn world_id() -> WorldId {
    WorldId::from_raw("lswr_web_proto_01")
}

fn ai() -> Participant {
    Participant::ai(ParticipantId::from_raw("ai:codex"), AuthorityMode::Coedit)
}

fn human() -> Participant {
    Participant::human(ParticipantId::from_raw("human:owner"), "web_scene")
}

fn provenance() -> EventProvenance {
    EventProvenance {
        adapter: Some("threejs_web".to_string()),
        source_schema: Some(SCHEMA_EVENT.to_string()),
        raw_available: true,
    }
}

fn evidence(method: &str, payload: Value) -> AdapterEvidence {
    AdapterEvidence::new("threejs_web", method, "fixture evidence", true, payload)
}

#[test]
fn serde_round_trip_for_core_records() {
    let action = Action {
        schema: SCHEMA_ACTION.to_string(),
        action_id: ActionId::from_raw("act_add_cube_02"),
        action_type: "add_entity".to_string(),
        source: ai(),
        target_refs: vec![TargetRef::entity(&EntityId::from_raw("cube_02"))],
        expected_effect: json!({"entity_present": "cube_02", "human_visible": true}),
        rollback_group: Some(RollbackGroupId::from_raw("rb_001")),
    };
    let verification = Verification::new(
        Some(action.action_id.clone()),
        Verdict::Verified,
        None,
        "web_scene_projection_check",
        Some(TargetRef::entity(&EntityId::from_raw("cube_02"))),
        evidence(
            "web_scene_projection_check",
            json!({"projected": true, "bounds_nonzero": true}),
        ),
    )
    .unwrap();
    let mut event = Event::new("runtime.action_result", world_id(), ai(), provenance());
    event.refs.actions.push(action.action_id.clone());
    event.verification = Some(verification.clone());
    let rollback = RollbackRecord::new(
        RollbackGroupId::from_raw("rb_001"),
        json!({"entities": []}),
        json!({"entities": [{"entity_id": "cube_02"}]}),
    );

    let encoded = serde_json::to_string(&(action, event, verification, rollback)).unwrap();
    let decoded: (Action, Event, Verification, RollbackRecord) =
        serde_json::from_str(&encoded).unwrap();

    assert_eq!(decoded.0.action_type, "add_entity");
    assert_eq!(decoded.1.event_type, "runtime.action_result");
    assert_eq!(decoded.2.verdict, Verdict::Verified);
    assert_eq!(decoded.3.rollback_group.as_str(), "rb_001");
}

#[test]
fn not_verified_and_blocked_require_reasons() {
    let not_verified = Verification::new(
        None,
        Verdict::NotVerified,
        None,
        "web_scene_projection_check",
        None,
        evidence("web_scene_projection_check", json!({})),
    );
    assert_eq!(
        not_verified.unwrap_err(),
        WorldCoreError::MissingReason {
            verdict: Verdict::NotVerified
        }
    );

    let blocked = Verification::new(
        None,
        Verdict::Blocked,
        Some("".to_string()),
        "world_policy_check",
        None,
        evidence("world_policy_check", json!({})),
    );
    assert_eq!(
        blocked.unwrap_err(),
        WorldCoreError::MissingReason {
            verdict: Verdict::Blocked
        }
    );
}

#[test]
fn verified_to_is_only_allowed_for_verified() {
    let target = TargetRef::entity(&EntityId::from_raw("cube_01"));
    let missing_target = Verification::new(
        None,
        Verdict::Verified,
        None,
        "web_scene_projection_check",
        None,
        evidence("web_scene_projection_check", json!({})),
    );
    assert_eq!(
        missing_target.unwrap_err(),
        WorldCoreError::MissingVerifiedTo
    );

    let not_verified_with_target = Verification::new(
        None,
        Verdict::NotVerified,
        Some("projection_object_absent".to_string()),
        "web_scene_projection_check",
        Some(target),
        evidence("web_scene_projection_check", json!({})),
    );
    assert_eq!(
        not_verified_with_target.unwrap_err(),
        WorldCoreError::VerifiedToNotAllowed {
            verdict: Verdict::NotVerified
        }
    );
}

#[test]
fn human_decision_does_not_mutate_prior_verification() {
    let action_id = ActionId::from_raw("act_material_cube_01");
    let verification = Verification::new(
        Some(action_id.clone()),
        Verdict::NotVerified,
        Some("projection_object_absent".to_string()),
        "web_scene_projection_check",
        None,
        evidence(
            "web_scene_projection_check",
            json!({"projected": false, "unprojected_entities": ["cube_01"]}),
        ),
    )
    .unwrap();

    let mut ledger = WorldLedger::new();
    ledger.append_verification(verification.clone()).unwrap();

    let mut reject = Event::new("human.reject", world_id(), human(), provenance());
    reject.refs.actions.push(action_id.clone());
    reject.payload = json!({
        "decision": "reject",
        "does_not_change_verification": true
    });
    ledger.append_event(reject).unwrap();

    let evidence = ledger.query_evidence_by_action(&action_id);
    assert_eq!(evidence.len(), 1);
    assert_eq!(evidence[0].verdict, Verdict::NotVerified);
    assert_eq!(
        evidence[0].reason.as_deref(),
        Some("projection_object_absent")
    );

    let mut invalid_accept = Event::new("human.accept", world_id(), human(), provenance());
    invalid_accept.payload = json!({
        "decision": "accept",
        "changes_world_verdict": true
    });
    assert_eq!(
        ledger.append_event(invalid_accept).unwrap_err(),
        WorldCoreError::HumanDecisionChangesVerification
    );
}

#[test]
fn adapter_evidence_can_hold_web_and_nexus_payloads_without_core_fields() {
    let web = evidence(
        "web_scene_projection_check",
        json!({
            "projected": false,
            "reason": "projection_object_absent",
            "unprojected_entities": ["cube_02"]
        }),
    );
    let nexus = AdapterEvidence::new(
        "nexus",
        "nexus_event_causal_verification",
        "expected causal edge present",
        true,
        json!({
            "event_id": "evt_food_warning",
            "hash_chain_valid": true,
            "expected_causal_edge": {
                "cause_id": "evt_tax_change",
                "consequence_id": "evt_food_warning",
                "edge_type": "direct",
                "present": true
            }
        }),
    );

    assert_eq!(web.payload["unprojected_entities"][0], "cube_02");
    assert_eq!(nexus.payload["expected_causal_edge"]["edge_type"], "direct");
    assert_eq!(web.adapter_kind, "threejs_web");
    assert_eq!(nexus.adapter_kind, "nexus");
}

#[test]
fn rollback_group_registration_and_query_are_ledger_visible() {
    let action_id = ActionId::from_raw("act_move_cube_01");
    let group_id = RollbackGroupId::from_raw("rb_002");
    let mut record = RollbackRecord::new(
        group_id.clone(),
        json!({"entities": [{"entity_id": "cube_01", "position": [0, 1, 0]}]}),
        json!({"entities": [{"entity_id": "cube_01", "position": [-2, 1, 0]}]}),
    );
    record.actions.push(action_id);

    let mut ledger = WorldLedger::new();
    ledger.register_rollback(record).unwrap();
    let fetched = ledger.rollback_group(&group_id).unwrap();
    assert_eq!(fetched.rollback_group, group_id);
    assert_eq!(fetched.actions.len(), 1);

    let duplicate = RollbackRecord::new(group_id.clone(), json!({}), json!({}));
    assert_eq!(
        ledger.register_rollback(duplicate).unwrap_err(),
        WorldCoreError::DuplicateRollbackGroup(group_id.to_string())
    );
}
