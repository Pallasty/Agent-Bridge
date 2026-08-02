use std::{fs, path::PathBuf};

fn source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(path).unwrap_or_default()
}

#[test]
fn skill_retro_aggregator_has_the_preregistered_private_cli_boundary() {
    let cli = source("src/cli/mod.rs");
    let module = source("src/cli/skill_retro.rs");
    let composition_root = source("src/main.rs");

    assert!(
        cli.contains("mod skill_retro;")
            && cli.contains("pub(super) use skill_retro::aggregate_skill_retro;"),
        "cli must declare and privately re-export the SkillRetro aggregator"
    );

    for owned in [
        "pub(crate) struct SkillRetroLessonRow",
        "pub(crate) struct SkillRetroReport",
        "pub(crate) fn aggregate_skill_retro(",
    ] {
        assert!(module.contains(owned), "cli::skill_retro must own {owned}");
        assert!(
            !composition_root.contains(owned.trim_start_matches("pub(crate) ")),
            "main.rs must not continue to own {owned}"
        );
    }

    for retained in [
        "enum DreamOp",
        "SkillRetro {",
        "DreamOp::SkillRetro { days, json }",
        "async fn run_dream_skill_retro(",
        "default_db_path()",
        "SqliteStore::open(&db_path)",
        "std::time::SystemTime::now()",
        "list_memories(Some(\"lesson\")",
        ".filter(|r| r.status == \"active\" && r.created_at >= cutoff)",
        "aggregate_skill_retro(lessons, days, now_secs, cutoff)",
        "serde_json::to_string_pretty(&report)",
        "println!",
        "Ok(())",
        "Cross-week Spearman trend is computed by diffing JSON outputs",
    ] {
        assert!(
            composition_root.contains(retained),
            "main.rs must retain SkillRetro authority/order marker {retained}"
        );
    }

    for forbidden in [
        "default_db_path",
        "SqliteStore",
        "StateStore",
        "MemoryListSort",
        "list_memories",
        "memory_save",
        "status == \"active\"",
        "std::env",
        "std::fs",
        "SystemTime",
        "UNIX_EPOCH",
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
            "cli::skill_retro pure aggregator must not absorb {forbidden} authority"
        );
    }
}
