use ab_world_core::{
    ActionId, AdapterEvidence, AuthorityMode, BranchId, EntityId, Event, EventId, EventProvenance,
    EventRefs, Participant, ParticipantId, ParticipantKind, TargetRef, Verdict, Verification,
    WorldId, WorldLedger, SCHEMA_EVENT,
};
use serde_json::{json, Value};

const NEXUS_FIXTURE: &str = include_str!("fixtures/nexus_causal_seed.json");

#[test]
fn nexus_causal_seed_maps_into_world_core_without_visual_fields() {
    let packet: Value = serde_json::from_str(NEXUS_FIXTURE).expect("fixture json");
    let world_id = WorldId::from_raw(packet["world"]["world_id"].as_str().expect("world_id"));
    let branch_id = BranchId::from_raw(packet["world"]["branch_id"].as_str().expect("branch_id"));

    let mut ledger = WorldLedger::new();
    for raw_event in packet["events"].as_array().expect("events") {
        ledger
            .append_event(map_event(raw_event, &world_id, &branch_id))
            .expect("event mapping");
    }

    assert_eq!(ledger.events().len(), 5);
    assert_eq!(ledger.verifications().len(), 3);
    assert_eq!(
        ledger
            .query_events_by_participant(&ParticipantId::from_raw("runtime:nexus"))
            .len(),
        4
    );
    assert_eq!(
        ledger
            .query_events_by_entity(&EntityId::from_raw("settlement:onsen"))
            .len(),
        5
    );

    let food_warning = ledger
        .event_by_id(&EventId::from_raw("evt_food_warning"))
        .expect("food warning event");
    assert_eq!(food_warning.event_type, "nexus.food_warning");
    assert_eq!(food_warning.refs.events[0].as_str(), "evt_tax_change");

    let causal_checks = ledger.query_events_by_type("runtime.causal_verification");
    assert_eq!(causal_checks.len(), 2);
    assert!(causal_checks
        .iter()
        .all(|event| event.refs.adapter.as_deref() == Some("nexus")));

    let verified = ledger.query_verifications_by_verdict(Verdict::Verified);
    assert_eq!(verified.len(), 1);
    assert_eq!(verified[0].method, "nexus_event_causal_verification");
    assert_eq!(
        verified[0].verified_to.as_ref().unwrap(),
        &TargetRef::event(&EventId::from_raw("evt_food_warning"))
    );
    assert_eq!(verified[0].evidence.adapter_kind, "nexus");
    assert_eq!(verified[0].evidence.payload["hash_chain_valid"], true);
    assert_eq!(
        verified[0].evidence.payload["expected_causal_edge"]["present"],
        true
    );
    assert!(verified[0].evidence.payload.get("screen_area").is_none());
    assert!(verified[0].evidence.payload.get("pixel_coverage").is_none());

    let not_verified = ledger.query_verifications_by_verdict(Verdict::NotVerified);
    assert_eq!(not_verified.len(), 1);
    assert_eq!(
        not_verified[0].reason.as_deref(),
        Some("causal_edge_absent")
    );
    assert!(not_verified[0].verified_to.is_none());
    assert_eq!(
        not_verified[0].evidence.payload["nexus_original_verified_to"],
        "event:evt_trade_surge"
    );
    assert_eq!(
        not_verified[0].evidence.payload["expected_causal_edge"]["present"],
        false
    );

    let blocked = ledger.query_verifications_by_verdict(Verdict::Blocked);
    assert_eq!(blocked.len(), 1);
    assert_eq!(blocked[0].reason.as_deref(), Some("autonomy_limit"));
    assert!(blocked[0].verified_to.is_none());
    assert_eq!(
        blocked[0].evidence.payload["safety_policy"],
        "autonomy_limit"
    );
    assert_eq!(
        blocked[0].evidence.payload["required_authority"],
        "human.accept"
    );
}

fn map_event(raw: &Value, world_id: &WorldId, branch_id: &BranchId) -> Event {
    let source = map_participant(&raw["source"], &raw["event_type"]);
    let mut event = Event::new(
        raw["event_type"].as_str().expect("event_type"),
        world_id.clone(),
        source,
        EventProvenance {
            adapter: Some("nexus".to_string()),
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
    let participant_kind = match raw["participant_kind"].as_str() {
        Some("human") => ParticipantKind::Human,
        Some("ai") => ParticipantKind::Ai,
        Some("adapter") => ParticipantKind::Adapter,
        Some("system") => ParticipantKind::System,
        Some("runtime") => ParticipantKind::Runtime,
        _ if participant_id.starts_with("human:")
            || event_type.as_str().unwrap_or("").starts_with("human.") =>
        {
            ParticipantKind::Human
        }
        _ if participant_id.starts_with("ai:") => ParticipantKind::Ai,
        _ => ParticipantKind::Runtime,
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
        .map(EntityId::from_raw)
        .collect();
    refs.events = raw["events"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(EventId::from_raw)
        .collect();
    refs.adapter = raw["adapter"].as_str().map(str::to_string);
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
            evidence_payload["nexus_original_verified_to"] = json!(raw_target);
        }
    }
    let adapter_kind = raw["evidence"]["adapter_kind"].as_str().unwrap_or("nexus");
    Verification::new(
        raw["action_id"].as_str().map(ActionId::from_raw),
        verdict,
        raw["reason"].as_str().map(str::to_string),
        raw["method"].as_str().expect("method"),
        verified_to,
        AdapterEvidence::new(
            adapter_kind,
            raw["method"].as_str().expect("method"),
            "mapped from Nexus causal fixture",
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
