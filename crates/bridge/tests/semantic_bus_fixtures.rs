use serde_json::Value;
use std::collections::HashSet;

const FIXTURES: &[(&str, &str)] = &[
    (
        "desktop_accessible_button",
        include_str!("../fixtures/semantic_bus/desktop_accessible_button.json"),
    ),
    (
        "mobile_ui_node",
        include_str!("../fixtures/semantic_bus/mobile_ui_node.json"),
    ),
    (
        "lswr_world_entity",
        include_str!("../fixtures/semantic_bus/lswr_world_entity.json"),
    ),
    (
        "daemon_http_service",
        include_str!("../fixtures/semantic_bus/daemon_http_service.json"),
    ),
    (
        "palace_memory_region",
        include_str!("../fixtures/semantic_bus/palace_memory_region.json"),
    ),
    (
        "git_topology_preflight",
        include_str!("../fixtures/semantic_bus/git_topology_preflight.json"),
    ),
];

fn str_field<'a>(value: &'a Value, key: &str) -> &'a str {
    value
        .get(key)
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("missing string field {key}"))
}

fn object_field<'a>(value: &'a Value, key: &str) -> &'a Value {
    value
        .get(key)
        .filter(|v| v.is_object())
        .unwrap_or_else(|| panic!("missing object field {key}"))
}

fn array_field<'a>(value: &'a Value, key: &str) -> &'a Vec<Value> {
    value
        .get(key)
        .and_then(Value::as_array)
        .unwrap_or_else(|| panic!("missing array field {key}"))
}

#[test]
fn semantic_bus_fixtures_follow_minimum_contract() {
    let mut fixture_ids = HashSet::new();
    let allowed_verdicts = ["verified", "not_verified", "blocked"];

    for (name, raw) in FIXTURES {
        let fixture: Value =
            serde_json::from_str(raw).unwrap_or_else(|e| panic!("{name} invalid json: {e}"));

        assert_eq!(str_field(&fixture, "schema"), "agent_bridge.semantic_bus.fixture.v0");
        assert_eq!(str_field(&fixture, "fixture_id"), *name);
        assert!(fixture_ids.insert(str_field(&fixture, "fixture_id").to_string()));

        let object = object_field(&fixture, "semantic_object");
        assert_eq!(str_field(object, "schema"), "agent_bridge.semantic_bus.object.v0");
        let object_id = str_field(object, "object_id");
        assert!(!object_id.is_empty());
        assert!(!str_field(object, "object_type").is_empty());
        assert!(!str_field(object, "source_adapter").is_empty());
        assert!(object.get("state").is_some_and(Value::is_object));
        assert!(object.get("relations").is_some_and(Value::is_array));
        assert!(object.get("provenance").is_some_and(Value::is_object));
        let confidence = object
            .get("confidence")
            .and_then(Value::as_f64)
            .expect("confidence");
        assert!((0.0..=1.0).contains(&confidence));

        let affordances = array_field(&fixture, "affordances");
        assert!(!affordances.is_empty(), "{name} affordances");
        for affordance in affordances {
            assert!(!str_field(affordance, "affordance_id").is_empty());
            assert_eq!(str_field(affordance, "object_id"), object_id);
            assert!(!str_field(affordance, "action_type").is_empty());
            assert!(affordance.get("args_schema").is_some_and(Value::is_object));
            assert!(affordance.get("requires_gate").is_some_and(Value::is_boolean));
        }

        let events = array_field(&fixture, "events");
        assert!(!events.is_empty(), "{name} events");
        let mut event_ids = HashSet::new();
        for event in events {
            let event_id = str_field(event, "event_id");
            assert!(event_ids.insert(event_id.to_string()));
            assert!(!str_field(event, "event_type").is_empty());
            assert_eq!(str_field(event, "subject_id"), object_id);
            assert!(event.get("payload_json").is_some_and(Value::is_object));
            assert!(event.get("source_event_ids").is_some_and(Value::is_array));
        }

        let verification = object_field(&fixture, "verification");
        let verdict = str_field(verification, "verdict");
        assert!(allowed_verdicts.contains(&verdict), "{name} verdict {verdict}");
        assert!(!str_field(verification, "method").is_empty());
        assert!(verification.get("evidence").is_some_and(Value::is_object));
        assert!(!str_field(verification, "recover").is_empty());
        assert!(verification.get("raw_available").is_some_and(Value::is_boolean));
        if verdict == "verified" {
            assert!(
                verification
                    .get("verified_to")
                    .and_then(Value::as_str)
                    .is_some_and(|s| !s.is_empty()),
                "{name} verified fixtures need verified_to"
            );
        } else {
            assert!(verification.get("verified_to").is_none_or(Value::is_null));
        }

        let presentation = object_field(&fixture, "presentation");
        assert!(!str_field(presentation, "presentation_id").is_empty());
        let source_event_ids = array_field(presentation, "source_event_ids");
        assert!(!source_event_ids.is_empty(), "{name} presentation source_event_ids");
        for event_id in source_event_ids.iter().filter_map(Value::as_str) {
            assert!(
                event_ids.contains(event_id),
                "{name} presentation links unknown event {event_id}"
            );
        }
        assert!(presentation.get("machine_payload").is_some_and(Value::is_object));
        assert!(presentation.get("ingestion").is_some_and(Value::is_object));
    }

    assert_eq!(fixture_ids.len(), FIXTURES.len());
}
