use std::{fs, path::PathBuf};

fn source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(path).unwrap_or_default()
}

#[test]
fn dream_html_renderers_have_the_preregistered_private_cli_boundary() {
    let cli = source("src/cli/mod.rs");
    let module = source("src/cli/dream.rs");
    let composition_root = source("src/main.rs");

    assert!(
        cli.contains("mod dream;")
            && cli.contains("pub(super) use dream::{")
            && cli.contains("render_codebase_report_html")
            && cli.contains("render_promote_html")
            && cli.contains("PromoteDecision")
            && cli.contains("PromoteStatus"),
        "cli must declare and re-export the private Dream HTML result boundary"
    );
    for owned in [
        "pub(crate) fn render_promote_html(",
        "pub(crate) fn render_codebase_report_html(",
        "pub(crate) struct PromoteDecision",
        "pub(crate) enum PromoteStatus",
        "pub(crate) fn short_key(",
        "pub(crate) fn truncate_chars(",
        "fn chip_class(",
        "fn html_escape(",
        "fn url_escape(",
        "fn bar_pct(",
    ] {
        assert!(module.contains(owned), "cli::dream must own {owned}");
        assert!(
            !composition_root.contains(owned.trim_start_matches("pub(crate) ")),
            "main.rs must not continue to own {owned}"
        );
    }

    for retained in [
        "enum DreamOp",
        "DreamOp::Promote {",
        "DreamOp::CodebaseReport {",
        "async fn run_dream_promote(",
        "async fn run_dream_codebase_report(",
        "default_db_path()",
        "SqliteStore::open(&path)",
        "top_coactivation_edges(min_count, limit)",
        ".memory_link(&pair.0, &pair.1, primary_edge_type, weight)",
        "SqliteStore::open(&db_path)",
        "codebase_call_stats(&root_canonical, top_n)",
        "chrono_now_utc_string()",
        "std::fs::write(p, html)",
        "println!",
        "eprintln!",
        "Ok(())",
    ] {
        assert!(
            composition_root.contains(retained),
            "main.rs must retain Dream authority/order marker {retained}"
        );
    }

    for forbidden in [
        "default_db_path",
        "SqliteStore",
        "StateStore",
        "top_coactivation_edges",
        "memory_neighbors",
        "memory_link",
        "codebase_call_stats",
        "std::env",
        "std::fs",
        "current_dir",
        "canonicalize",
        "SystemTime",
        "UNIX_EPOCH",
        "println!",
        "eprintln!",
        "anyhow",
        "Result<",
        "async fn",
        "tokio",
        "Command::new",
        "Hub",
    ] {
        assert!(
            !module.contains(forbidden),
            "cli::dream completed-result renderer must not absorb {forbidden} authority"
        );
    }
}
