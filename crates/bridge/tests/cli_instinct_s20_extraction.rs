#[path = "../src/cli/instinct_memory.rs"]
mod instinct_memory;

use serde_json::json;

#[test]
fn invalid_required_fields_keep_short_circuit_order() {
    for (value, expected) in [
        (json!(null), "memory_record.key is required"),
        (
            json!({"key": "\u{2003}", "kind": "lesson", "content": "body"}),
            "memory_record.key is required",
        ),
        (
            json!({"key": "key", "kind": false, "content": null}),
            "memory_record.kind is required",
        ),
        (
            json!({"key": "key", "kind": "custom-kind", "content": "\t"}),
            "memory_record.content is required",
        ),
    ] {
        match instinct_memory::prepare_memory_record(&value) {
            Ok(_) => panic!("invalid required field accepted"),
            Err(error) => assert_eq!(error.to_string(), expected),
        }
    }
}

#[test]
fn prepared_values_preserve_normalization_and_reset_lifecycle_fields() {
    let value = json!({
        "key": " key ", "kind": " custom-kind ", "content": "\u{2003}body\u{2003}",
        "tags": [" first ", false, "", "first", " second "],
        "related_keys": [null, " related ", "related"], "scope": " domain:fixture ",
        "importance": 4.0, "created_at": 99, "updated_at": 88,
        "last_accessed_at": 77, "access_count": 66, "status": "archived",
        "trigger_pattern": "ignored", "superseded_by": "ignored"
    });
    let record = instinct_memory::prepare_memory_record(&value)
        .unwrap()
        .into_record(-17);
    assert_eq!(record.key, "key");
    assert_eq!(record.kind, "custom-kind");
    assert_eq!(record.content, "body");
    assert_eq!(record.tags, ["first", "first", "second"]);
    assert_eq!(record.related_keys, ["related", "related"]);
    assert_eq!(record.scope.as_deref(), Some("domain:fixture"));
    assert_eq!(record.importance, 1.0);
    assert_eq!((record.created_at, record.updated_at), (-17, -17));
    assert_eq!((record.last_accessed_at, record.access_count), (0, 0));
    assert_eq!(record.status, "active");
    assert!(record.trigger_pattern.is_none() && record.superseded_by.is_none());
}

#[test]
fn preparation_has_no_clock_or_write_capability() {
    let source = include_str!("../src/cli/instinct_memory.rs");
    for forbidden in [
        "SystemTime",
        "Instant",
        "std::fs",
        "std::env",
        "std::process",
        "SqliteStore",
        "StateStore",
        "Hub",
        "tokio::",
        "memory_save",
    ] {
        assert!(
            !source.contains(forbidden),
            "preparation gained authority: {forbidden}"
        );
    }
    let fields = source
        .split("struct PreparedMemoryRecord {")
        .nth(1)
        .unwrap()
        .split('}')
        .next()
        .unwrap();
    assert!(
        !fields.contains("pub"),
        "prepared fields must not bypass validation"
    );
    assert!(include_str!("../src/cli/mod.rs").contains("pub(super) mod instinct_memory;"));
    assert!(!include_str!("../src/lib.rs").contains("mod instinct_memory"));
    assert!(source.contains("fn into_record(self, now: i64)"));
}
