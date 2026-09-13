const ROOT: &str = include_str!("../src/main.rs");
const CLI: &str = include_str!("../src/cli/mod.rs");

fn ordered(source: &str, markers: &[&str]) {
    let mut offset = 0;
    for marker in markers {
        let relative = source[offset..]
            .find(marker)
            .unwrap_or_else(|| panic!("missing or reordered marker: {marker}"));
        offset += relative + marker.len();
    }
}

#[test]
fn completed_identity_sections_have_a_private_owner() {
    assert!(CLI.contains("pub(super) mod dream_identity_view;"));
    assert!(!ROOT.contains("fn pct_delta("));
    assert!(!ROOT.contains("fn print_identity_section("));
    assert!(!include_str!("../src/lib.rs").contains("mod dream_identity_view"));
}

#[test]
fn identity_admission_acquisition_and_output_order_remain_at_root() {
    let function = ROOT
        .split("async fn run_dream_identity(")
        .nth(1)
        .unwrap()
        .split("\n}\n")
        .next()
        .unwrap();
    ordered(
        function,
        &[
            "if days == 0",
            "--days must be ≥ 1",
            "SystemTime::now()",
            "let window_secs",
            "let cur_start",
            "let prior_start",
            "default_db_path()",
            "SqliteStore::open(&path)",
            "open state.db at",
            ".identity_window(cur_start, now)",
            "identity_window cur:",
            ".identity_window(prior_start, cur_start)",
            "identity_window prior:",
            "if as_json",
            "serde_json::json!",
            "serde_json::to_string_pretty(&payload)?",
            "return Ok(())",
            "# v21 — Identity continuity",
            "DB: {}",
            "cli::dream_identity_view::print_identity_section(&cur, &prior)",
            "Ok(())",
        ],
    );
}

#[test]
fn section_renderer_cannot_acquire_runtime_or_store_authority() {
    let source = std::fs::read_to_string(
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src/cli/dream_identity_view.rs"),
    )
    .expect("private section renderer must exist");
    for forbidden in [
        "SystemTime",
        "Instant",
        "std::fs",
        "std::env",
        "std::process",
        "StateStore",
        "SqliteStore",
        "Hub",
        "async fn",
        "tokio::",
        "eprintln!",
        "pub fn",
    ] {
        assert!(
            !source.contains(forbidden),
            "renderer gained authority: {forbidden}"
        );
    }
    assert!(source.contains("use super::dream::short_key;"));
    assert!(source.contains("fn pct_delta(cur: u64, prior: u64) -> String"));
    assert!(!source.contains("pub(crate) fn pct_delta"));
    assert!(source.contains("pub(crate) fn print_identity_section"));
}
