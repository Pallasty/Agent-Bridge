use std::fs;
use std::path::PathBuf;

fn bridge_source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src")
        .join(relative);
    fs::read_to_string(&path).unwrap_or_else(|err| panic!("reading {}: {err}", path.display()))
}

#[test]
fn substrate_family_moves_without_absorbing_dream_correlation_audit() {
    let cli_mod = bridge_source("cli/mod.rs");
    let main = bridge_source("main.rs");
    let substrate = bridge_source("cli/substrate.rs");

    assert!(cli_mod.contains("mod substrate;"));
    assert!(cli_mod.contains("run_substrate"));
    assert!(cli_mod.contains("SubstrateOp"));

    assert!(substrate.contains("pub(crate) enum SubstrateOp"));
    assert!(substrate.contains("pub(crate) async fn run_substrate"));
    for executor in [
        "run_substrate_stats",
        "run_substrate_neighbors",
        "run_substrate_replay",
        "run_substrate_snapshot",
    ] {
        assert!(
            substrate.contains(&format!("fn {executor}(")),
            "cli::substrate must own {executor}"
        );
        assert!(
            !main.contains(&format!("fn {executor}(")),
            "main.rs must not continue to own {executor}"
        );
    }

    for helper in [
        "SnapshotSummary",
        "SnapshotEntry",
        "summarize_snapshot_rows",
        "human_bytes",
        "parse_event_line",
        "mean_f32",
    ] {
        assert!(
            substrate.contains(helper),
            "substrate module must own {helper}"
        );
    }

    assert!(main.contains("Substrate {\n"));
    assert!(main.contains("op: SubstrateOp"));
    assert!(main.contains("return run_substrate(op).await;"));
    assert!(main.contains("| Cmd::Substrate { .. }"));

    assert!(main.contains("enum DreamOp"));
    assert!(main.contains("run_dream_substrate_corr_audit"));
    assert!(!substrate.contains("run_dream_substrate_corr_audit"));
    assert!(!substrate.contains("SqliteStore"));
}
