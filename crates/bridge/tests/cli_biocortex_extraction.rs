use std::{fs, path::PathBuf};

fn source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(path).unwrap_or_default()
}

#[test]
fn biocortex_evidence_entry_has_the_preregistered_module_boundary() {
    let cli = source("src/cli/mod.rs");
    let module = source("src/cli/biocortex.rs");
    let composition_root = source("src/main.rs");

    assert!(
        cli.contains("mod biocortex;"),
        "cli must declare a private biocortex module"
    );

    for adapter in [
        "run_biocortex_shadow_digest",
        "run_biocortex_capability_ledger_report_packet",
        "shadow_json_display",
    ] {
        assert!(
            module.contains(&format!("fn {adapter}(")),
            "cli::biocortex must own {adapter}"
        );
        assert!(
            !composition_root.contains(&format!("fn {adapter}(")),
            "main.rs must not continue to own {adapter}"
        );
    }

    assert!(
        composition_root.contains("enum BioCortexOp"),
        "main.rs must retain the complete BioCortex clap schema"
    );
    assert!(
        composition_root.contains("BioCortexOp::ShadowDigest")
            && composition_root.contains("BioCortexOp::CapabilityLedgerReportPacket"),
        "main.rs must retain both selected dispatch arms"
    );
    assert!(
        composition_root.contains("run_biocortex_replay_compare"),
        "main.rs must retain ReplayCompare"
    );

    for forbidden in [
        "run_biocortex_replay_compare",
        "run_biocortex_retrieval_opt_in_store_trial",
        "run_biocortex_retrieval_opt_in_runtime_transition_gate",
        "SqliteStore",
        "BioCortexOp",
    ] {
        assert!(
            !module.contains(forbidden),
            "cli::biocortex must not absorb {forbidden}"
        );
    }
}
