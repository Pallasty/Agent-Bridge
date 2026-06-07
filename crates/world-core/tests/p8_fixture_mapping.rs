use ab_world_core::{
    ActionId, AdapterEvidence, AuthorityMode, BranchId, Event, EventId, EventProvenance, EventRefs,
    Participant, ParticipantId, ParticipantKind, RollbackGroupId, RollbackRecord, TargetRef,
    Verdict, Verification, WorldId, WorldLedger, SCHEMA_EVENT,
};
use serde_json::{json, Value};

const P8_FIXTURE: &str = include_str!("fixtures/p8_world_export.json");

#[test]
fn p8_world_export_maps_into_world_core_without_laundering_truth() {
    let packet: Value = serde_json::from_str(P8_FIXTURE).expect("fixture json");
    assert_p8_contract(&packet);

    let world_id = WorldId::from_raw(packet["world"]["world_id"].as_str().expect("world_id"));
    let branch_id = BranchId::from_raw(packet["world"]["branch_id"].as_str().expect("branch_id"));

    let mut ledger = WorldLedger::new();
    for record in packet["rollback"]["available_groups"]
        .as_array()
        .expect("rollback groups")
    {
        ledger
            .register_rollback(map_rollback_record(record))
            .expect("rollback mapping");
    }

    for raw_event in packet["events"].as_array().expect("events") {
        ledger
            .append_event(map_event(raw_event, &world_id, &branch_id))
            .expect("event mapping");
    }

    assert_eq!(
        ledger.events().len() as u64,
        packet["contract"]["expectations"]["event_count"]
            .as_u64()
            .expect("contract event_count")
    );
    assert_eq!(
        ledger.verifications().len() as u64,
        packet["contract"]["expectations"]["verification_count"]
            .as_u64()
            .expect("contract verification_count")
    );
    assert_eq!(
        ledger.rollback_groups().count() as u64,
        packet["contract"]["expectations"]["rollback_group_count"]
            .as_u64()
            .expect("contract rollback_group_count")
    );
    assert_eq!(ledger.query_events_by_type("human.reject").len(), 1);
    assert_eq!(
        ledger
            .query_events_by_type("runtime.rollback_applied")
            .len(),
        1
    );

    let not_verified = ledger
        .verifications()
        .iter()
        .find(|verification| verification.verdict == Verdict::NotVerified)
        .expect("not_verified record");
    assert_eq!(
        not_verified.reason.as_deref(),
        packet["contract"]["truth_boundary"]["not_verified_reason"].as_str()
    );
    assert!(not_verified.verified_to.is_none());
    assert_eq!(
        not_verified.evidence.payload["p8_original_verified_to"],
        packet["contract"]["truth_boundary"]["not_verified_source_verified_to"]
    );
    assert_eq!(not_verified.evidence.payload["projected"], false);

    let blocked = ledger
        .verifications()
        .iter()
        .find(|verification| verification.verdict == Verdict::Blocked)
        .expect("blocked record");
    assert_eq!(blocked.reason.as_deref(), Some("locked_entity"));
    assert!(blocked.verified_to.is_none());
    assert_eq!(blocked.evidence.payload["policy_checked"], true);

    let rollback_id = RollbackGroupId::from_raw("rb_004");
    let rollback = ledger
        .rollback_group(&rollback_id)
        .expect("rollback rb_004");
    assert_eq!(rollback.actions[0].as_str(), "act_add_entity_004");

    let reject = ledger
        .events()
        .iter()
        .find(|event| event.event_type == "human.reject")
        .expect("human reject event");
    assert_eq!(
        reject.payload["does_not_change_verification"],
        Value::Bool(true)
    );
    let rejected_action = &reject.refs.actions[0];
    let rejected_verification = ledger.query_evidence_by_action(rejected_action);
    assert_eq!(rejected_verification.len(), 1);
    assert_eq!(rejected_verification[0].verdict, Verdict::Verified);

    let rollback_verification = ledger
        .verifications()
        .iter()
        .find(|verification| verification.method == "web_scene_rollback_check")
        .expect("rollback verification");
    assert_eq!(rollback_verification.verdict, Verdict::Verified);
    assert_eq!(
        rollback_verification.evidence.payload["semantic_state_restored"],
        true
    );
}

fn assert_p8_contract(packet: &Value) {
    let contract = &packet["contract"];
    assert_eq!(contract["schema"], "agent_bridge.lswr.web_core_contract.v0");
    assert_eq!(
        contract["contract_id"],
        "p8_web_prototype_to_ab_world_core_v0"
    );
    assert_eq!(contract["fixture_id"], "p8_world_export");
    assert_eq!(
        contract["producer"]["export_surface"],
        "window.lswr.world_export"
    );
    assert_eq!(contract["consumer"]["crate"], "ab-world-core");
    assert_eq!(
        contract["paths"]["fixture"],
        "crates/world-core/tests/fixtures/p8_world_export.json"
    );
    assert_eq!(
        packet["world"]["world_id"],
        contract["expectations"]["world_id"]
    );
    assert_eq!(
        packet["world"]["branch_id"],
        contract["expectations"]["branch_id"]
    );
    assert_eq!(
        packet["projection"]["adapter"],
        contract["expectations"]["projection_adapter"]
    );
    assert_eq!(
        contract["truth_boundary"]["core_mapping_must_clear_not_verified_to"],
        true
    );
}

fn map_event(raw: &Value, world_id: &WorldId, branch_id: &BranchId) -> Event {
    let source = map_participant(&raw["source"], &raw["event_type"]);
    let mut event = Event::new(
        raw["event_type"].as_str().expect("event_type"),
        world_id.clone(),
        source,
        EventProvenance {
            adapter: Some("threejs_web".to_string()),
            source_schema: Some(SCHEMA_EVENT.to_string()),
            raw_available: true,
        },
    );
    event.event_id = EventId::from_raw(raw["event_id"].as_str().expect("event_id"));
    event.branch_id = Some(branch_id.clone());
    event.refs = map_refs(&raw["refs"]);
    event.payload = raw.get("payload").cloned().unwrap_or(Value::Null);
    event.verification = raw
        .get("verification")
        .map(|verification| map_verification(verification).expect("embedded verification"));
    event
}

fn map_participant(raw: &Value, event_type: &Value) -> Participant {
    let participant_id = raw["participant_id"].as_str().unwrap_or("runtime:unknown");
    let participant_kind = if participant_id.starts_with("human:")
        || event_type.as_str().unwrap_or("").starts_with("human.")
    {
        ParticipantKind::Human
    } else if participant_id.starts_with("ai:") {
        ParticipantKind::Ai
    } else {
        ParticipantKind::Runtime
    };
    let authority_mode = match raw["authority_mode"].as_str().unwrap_or("coedit") {
        "observe" => AuthorityMode::Observe,
        "suggest" => AuthorityMode::Suggest,
        "autonomous" => AuthorityMode::Autonomous,
        "locked" => AuthorityMode::Locked,
        _ => AuthorityMode::Coedit,
    };
    Participant {
        participant_id: ParticipantId::from_raw(participant_id),
        participant_kind,
        authority_mode,
        surface: raw["surface"].as_str().map(str::to_string),
    }
}

fn map_refs(raw: &Value) -> EventRefs {
    let mut refs = EventRefs::empty();
    refs.actions = raw["actions"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(ActionId::from_raw)
        .collect();
    refs.entities = raw["entities"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(ab_world_core::EntityId::from_raw)
        .collect();
    refs.rollback_groups = raw["rollback_groups"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(RollbackGroupId::from_raw)
        .collect();
    refs.adapter = Some("threejs_web".to_string());
    refs
}

fn map_verification(raw: &Value) -> ab_world_core::Result<Verification> {
    let verdict = match raw["verdict"].as_str().expect("verdict") {
        "verified" => Verdict::Verified,
        "not_verified" => Verdict::NotVerified,
        "blocked" => Verdict::Blocked,
        other => panic!("unknown verdict {other}"),
    };
    let raw_verified_to = raw["verified_to"].as_str();
    let verified_to = if verdict == Verdict::Verified {
        raw_verified_to.map(parse_target_ref)
    } else {
        None
    };
    let mut evidence_payload = raw["evidence"].clone();
    if verdict != Verdict::Verified {
        if let Some(raw_target) = raw_verified_to {
            evidence_payload["p8_original_verified_to"] = json!(raw_target);
        }
    }
    let adapter_kind = raw["evidence"]["adapter_kind"]
        .as_str()
        .unwrap_or("threejs_web");
    Verification::new(
        raw["action_id"].as_str().map(ActionId::from_raw),
        verdict,
        raw["reason"].as_str().map(str::to_string),
        raw["method"].as_str().expect("method"),
        verified_to,
        AdapterEvidence::new(
            adapter_kind,
            raw["method"].as_str().expect("method"),
            "mapped from P8 world_export fixture",
            true,
            evidence_payload,
        ),
    )
}

fn parse_target_ref(raw: &str) -> TargetRef {
    let (kind, id) = raw.split_once(':').unwrap_or(("raw", raw));
    TargetRef {
        kind: kind.to_string(),
        id: id.to_string(),
    }
}

fn map_rollback_record(raw: &Value) -> RollbackRecord {
    let mut record = RollbackRecord::new(
        RollbackGroupId::from_raw(raw["rollback_group"].as_str().expect("rollback_group")),
        raw["before"].clone(),
        raw["after"].clone(),
    );
    record.actions = raw["actions"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(ActionId::from_raw)
        .collect();
    record.verification_event_id = raw["verification_event_id"].as_str().map(EventId::from_raw);
    record
}
