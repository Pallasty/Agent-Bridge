const ROOT: &str = include_str!("../src/main.rs");
const PRESENTATION: &str = include_str!("../src/cli/instinct_presentation.rs");

fn arm(name: &str) -> &str {
    let dispatch = ROOT
        .split("if let Cmd::Instinct { op } = &cmd {")
        .nth(1)
        .unwrap();
    let tail = dispatch
        .split(&format!("InstinctOp::{name} "))
        .nth(1)
        .unwrap();
    tail.split("            InstinctOp::").next().unwrap()
}

fn ordered(source: &str, markers: &[&str]) {
    let mut remaining = source;
    for marker in markers {
        let index = remaining
            .find(marker)
            .unwrap_or_else(|| panic!("missing or out of order: {marker}"));
        remaining = &remaining[index + marker.len()..];
    }
}

#[test]
fn completed_result_presentation_has_no_state_or_execution_authority() {
    for forbidden in [
        "std::fs",
        "std::process",
        "std::env",
        "tokio::",
        "SqliteStore",
        "StateStore",
        "Hub",
        "SystemTime",
        "Instant",
        "Path",
        "observer_",
        "memory_save",
        "&mut Value",
    ] {
        assert!(
            !PRESENTATION.contains(forbidden),
            "renderer gained authority: {forbidden}"
        );
    }
    assert!(include_str!("../src/cli/mod.rs").contains("pub(super) mod instinct_presentation;"));
    assert!(!include_str!("../src/lib.rs").contains("mod instinct_presentation"));
}

#[test]
fn memory_admission_save_and_receipt_stay_ordered_before_presentation() {
    ordered(
        arm("MemoryWrite"),
        &[
            "observer_memory_write_plan(preflight_json, *write)",
            "if *write {",
            "\"writes_memory\"",
            "memory write blocked:",
            "memory_record_from_instinct_plan(&record)",
            "SqliteStore::open(&path)",
            ".memory_save(&mem)",
            "observer_memory_write_receipt(",
            "plan[\"status\"] = json!(\"saved\")",
            "plan[\"receipt\"] = receipt",
            "render_memory_write(&plan, *write, *json)",
        ],
    );
    let prepare = ROOT
        .split("fn memory_record_from_instinct_plan(")
        .nth(1)
        .unwrap();
    ordered(
        prepare,
        &[
            "prepare_memory_record(value)?",
            "SystemTime::now()",
            "prepared.into_record(now)",
        ],
    );
    ordered(
        include_str!("../src/cli/instinct_memory.rs"),
        &[
            "memory_record.key is required",
            "memory_record.kind is required",
            "memory_record.content is required",
            "Ok(PreparedMemoryRecord",
        ],
    );
}

#[test]
fn domain_acquisition_errors_and_writes_precede_all_nine_renderers() {
    for (op, domain, renderer) in [
        (
            "Candidates",
            "observer_candidate_preview",
            "render_candidates",
        ),
        (
            "ReviewPacket",
            "observer_review_packet",
            "render_review_packet",
        ),
        (
            "ReviewDecision",
            "observer_review_decision",
            "render_review_decision",
        ),
        (
            "MemoryPreflight",
            "observer_memory_preflight",
            "render_memory_preflight",
        ),
        (
            "MemoryWrite",
            "observer_memory_write_plan",
            "render_memory_write",
        ),
        (
            "ReviewStatus",
            "observer_review_status",
            "render_review_status",
        ),
        (
            "ReviewInbox",
            "observer_review_inbox",
            "render_review_inbox",
        ),
        (
            "ReviewContext",
            "observer_review_context",
            "render_review_context",
        ),
        ("RotateLog", "rotate_observer_log", "render_rotate_log"),
    ] {
        ordered(arm(op), &[domain, renderer]);
        assert!(PRESENTATION.contains(&format!("fn {renderer}(")));
        assert!(!ROOT.contains(&format!("fn {renderer}(")));
    }
}

#[test]
fn local_excerpt_remains_explicit_at_acquisition_and_presentation() {
    ordered(
        arm("ReviewContext"),
        &[
            "observer_review_context(",
            "*include_local_excerpt",
            ".context(\"read instinct observer review context\")?",
            "render_review_context(",
            "*include_local_excerpt",
        ],
    );
    ordered(
        PRESENTATION
            .split("fn render_review_context(")
            .nth(1)
            .unwrap(),
        &[
            "if as_json",
            "if include_local_excerpt",
            "\"/local_log_match/prompt_excerpt\"",
            "local_prompt_excerpt={excerpt}",
        ],
    );
}
