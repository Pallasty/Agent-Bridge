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
        "linux_desktop_snapshot_state",
        include_str!("../fixtures/semantic_bus/linux_desktop_snapshot_state.json"),
    ),
    (
        "linux_desktop_verify_postcondition",
        include_str!("../fixtures/semantic_bus/linux_desktop_verify_postcondition.json"),
    ),
    (
        "linux_vision_grounding_ocr_fallback",
        include_str!("../fixtures/semantic_bus/linux_vision_grounding_ocr_fallback.json"),
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

const LINUX_ADAPTER_CONFORMANCE_FIXTURES: &[(&str, &str)] = &[
    (
        "daemon_http_service",
        include_str!("../fixtures/semantic_bus/daemon_http_service.json"),
    ),
    (
        "linux_desktop_snapshot_state",
        include_str!("../fixtures/semantic_bus/linux_desktop_snapshot_state.json"),
    ),
    (
        "linux_desktop_verify_postcondition",
        include_str!("../fixtures/semantic_bus/linux_desktop_verify_postcondition.json"),
    ),
    (
        "linux_vision_grounding_ocr_fallback",
        include_str!("../fixtures/semantic_bus/linux_vision_grounding_ocr_fallback.json"),
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

fn bool_field(value: &Value, key: &str) -> bool {
    value
        .get(key)
        .and_then(Value::as_bool)
        .unwrap_or_else(|| panic!("missing bool field {key}"))
}

fn string_array_field(value: &Value, key: &str) -> HashSet<String> {
    array_field(value, key)
        .iter()
        .map(|v| {
            v.as_str()
                .unwrap_or_else(|| panic!("{key} must contain only strings"))
                .to_string()
        })
        .collect()
}

#[test]
fn semantic_bus_fixtures_follow_minimum_contract() {
    let mut fixture_ids = HashSet::new();
    let allowed_verdicts = ["verified", "not_verified", "blocked"];

    for (name, raw) in FIXTURES {
        let fixture: Value =
            serde_json::from_str(raw).unwrap_or_else(|e| panic!("{name} invalid json: {e}"));

        assert_eq!(
            str_field(&fixture, "schema"),
            "agent_bridge.semantic_bus.fixture.v0"
        );
        assert_eq!(str_field(&fixture, "fixture_id"), *name);
        assert!(fixture_ids.insert(str_field(&fixture, "fixture_id").to_string()));

        let object = object_field(&fixture, "semantic_object");
        assert_eq!(
            str_field(object, "schema"),
            "agent_bridge.semantic_bus.object.v0"
        );
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
            assert!(
                affordance
                    .get("requires_gate")
                    .is_some_and(Value::is_boolean)
            );
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
        assert!(
            allowed_verdicts.contains(&verdict),
            "{name} verdict {verdict}"
        );
        assert!(!str_field(verification, "method").is_empty());
        assert!(verification.get("evidence").is_some_and(Value::is_object));
        assert!(!str_field(verification, "recover").is_empty());
        assert!(
            verification
                .get("raw_available")
                .is_some_and(Value::is_boolean)
        );
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
        assert!(
            !source_event_ids.is_empty(),
            "{name} presentation source_event_ids"
        );
        for event_id in source_event_ids.iter().filter_map(Value::as_str) {
            assert!(
                event_ids.contains(event_id),
                "{name} presentation links unknown event {event_id}"
            );
        }
        assert!(
            presentation
                .get("machine_payload")
                .is_some_and(Value::is_object)
        );
        assert!(presentation.get("ingestion").is_some_and(Value::is_object));
    }

    assert_eq!(fixture_ids.len(), FIXTURES.len());
}

#[test]
fn linux_adapter_conformance_fixtures_pin_read_only_semantics() {
    let allowed_tools = [
        "daemon_http",
        "desktop_snapshot",
        "desktop_verify",
        "vision_grounding_ocr",
    ];
    let allowed_recover = ["proceed", "retry", "replan", "escalate"];

    for (name, raw) in LINUX_ADAPTER_CONFORMANCE_FIXTURES {
        let fixture: Value =
            serde_json::from_str(raw).unwrap_or_else(|e| panic!("{name} invalid json: {e}"));
        assert_eq!(str_field(&fixture, "fixture_id"), *name);

        let contract = object_field(&fixture, "adapter_contract");
        assert_eq!(
            str_field(contract, "schema"),
            "agent_bridge.semantic_bus.adapter_conformance.v0"
        );
        let adapter_family = str_field(contract, "adapter_family");
        assert!(
            matches!(adapter_family, "linux_desktop" | "process_daemon"),
            "{name} unexpected adapter family {adapter_family}"
        );
        let tool = str_field(contract, "tool");
        assert!(
            allowed_tools.contains(&tool),
            "{name} unexpected tool {tool}"
        );
        assert!(
            bool_field(contract, "read_only"),
            "{name} must be read-only"
        );
        assert!(
            !bool_field(contract, "broad_host_mutation"),
            "{name} must not expose broad host mutation"
        );
        assert_eq!(str_field(contract, "mutation_surface"), "none");
        assert!(!str_field(contract, "isolation").is_empty());

        let channels = string_array_field(contract, "channels");
        assert!(!channels.is_empty(), "{name} channels");
        let fallback_order = string_array_field(contract, "fallback_order");
        assert!(!fallback_order.is_empty(), "{name} fallback_order");

        let object = object_field(&fixture, "semantic_object");
        let source_adapter = str_field(object, "source_adapter");
        if adapter_family == "linux_desktop" {
            assert!(
                source_adapter.starts_with("linux."),
                "{name} source_adapter {source_adapter}"
            );
        }
        if tool == "daemon_http" {
            assert_eq!(source_adapter, "process.http");
            assert!(channels.contains("http_health"));
        }
        if tool == "desktop_snapshot" {
            assert!(channels.contains("sway_tree"));
            assert!(channels.contains("atspi"));
            assert!(
                fallback_order.contains("vision_grounding_ocr"),
                "{name} should keep OCR as fallback"
            );
        }
        if tool == "desktop_verify" {
            assert!(channels.contains("atspi"));
            assert!(fallback_order.contains("vision_grounding_ocr"));
        }
        if tool == "vision_grounding_ocr" {
            assert!(channels.contains("screenshot"));
            assert!(channels.contains("ocr"));
            let fallback_for = string_array_field(contract, "fallback_for");
            assert!(
                fallback_for.contains("desktop_snapshot")
                    || fallback_for.contains("desktop_verify"),
                "{name} OCR fixture must declare semantic surfaces it falls back for"
            );
            assert_eq!(
                str_field(object, "source_adapter"),
                "linux.vision.ocr",
                "{name} OCR fixture must not pretend to be semantic bus state"
            );
        }

        let verification = object_field(&fixture, "verification");
        let recover = str_field(verification, "recover");
        assert!(
            allowed_recover.contains(&recover),
            "{name} recover hint {recover}"
        );

        for affordance in array_field(&fixture, "affordances") {
            let action_type = str_field(affordance, "action_type");
            if matches!(
                action_type,
                "desktop.action.coordinate_click" | "desktop.invoke"
            ) {
                assert!(
                    bool_field(affordance, "requires_gate"),
                    "{name} {action_type} must require a gate"
                );
            }
        }
    }
}
