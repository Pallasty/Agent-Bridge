use std::{fs, path::PathBuf};

fn source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(path).unwrap_or_default()
}

#[test]
fn agent_md_drift_classifier_has_the_preregistered_private_dream_boundary() {
    let cli = source("src/cli/mod.rs");
    let module = source("src/cli/dream.rs");
    let composition_root = source("src/main.rs");

    assert!(
        cli.contains("pub(super) use dream::{")
            && cli.contains("drift_tokens")
            && cli.contains("drift_coverage_ratio")
            && cli.contains("triage_agent_md_drift_candidate")
            && cli.contains("AGENT_MD_DRIFT_COVERAGE_THRESHOLD"),
        "cli must re-export the private deterministic AGENT.md drift boundary"
    );

    for owned in [
        "pub(crate) const AGENT_MD_DRIFT_COVERAGE_THRESHOLD",
        "pub(crate) fn drift_tokens(",
        "pub(crate) fn drift_coverage_ratio(",
        "pub(crate) struct AgentMdTriageDecision",
        "pub(crate) fn triage_agent_md_drift_candidate(",
        "fn contains_any(",
    ] {
        assert!(module.contains(owned), "cli::dream must own {owned}");
        assert!(
            !composition_root.contains(owned.trim_start_matches("pub(crate) ")),
            "main.rs must not continue to own {owned}"
        );
    }

    for retained in [
        "enum DreamOp",
        "AgentMdDrift {",
        "DreamOp::AgentMdDrift {",
        "async fn run_dream_agent_md_drift(",
        "agent_md_path_override.unwrap_or_else(ab_bridge::mcp_tools::agent_profile_path)",
        "std::fs::read_to_string(&agent_md_path)",
        "default_db_path()",
        "SqliteStore::open(&db_path)",
        "std::time::SystemTime::now()",
        "list_memories(Some(\"lesson\")",
        "r.status == \"active\" && r.created_at >= cutoff",
        "ab_bridge::mcp_tools::sanitise_target_for_key(&lesson.key)",
        "store.memory_save(&mem).await.is_ok()",
        "AgentMdDriftReport {",
        "serde_json::to_string_pretty(&report)",
        "println!",
        "Ok(())",
        "AGENT.md is NEVER auto-edited",
    ] {
        assert!(
            composition_root.contains(retained),
            "main.rs must retain AGENT.md drift authority/order marker {retained}"
        );
    }

    for forbidden in [
        "MemoryRecord",
        "MemoryListSort",
        "SqliteStore",
        "StateStore",
        "list_memories",
        "memory_save",
        "agent_profile_path",
        "sanitise_target_for_key",
        "std::env",
        "std::fs",
        "SystemTime",
        "UNIX_EPOCH",
        "serde::Serialize",
        "serde_json",
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
            "cli::dream deterministic drift boundary must not absorb {forbidden} authority"
        );
    }
}
