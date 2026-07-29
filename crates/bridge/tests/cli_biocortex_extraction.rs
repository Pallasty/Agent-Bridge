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
        "run_biocortex_retrieval_approval_packet",
        "run_biocortex_retrieval_opt_in_status",
        "run_biocortex_retrieval_opt_in_dry_run",
        "run_biocortex_retrieval_opt_in_review_packet",
        "run_biocortex_retrieval_opt_in_execution_packet",
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
            && composition_root.contains("BioCortexOp::CapabilityLedgerReportPacket")
            && composition_root.contains("BioCortexOp::RetrievalApprovalPacket")
            && composition_root.contains("BioCortexOp::RetrievalOptInStatus")
            && composition_root.contains("BioCortexOp::RetrievalOptInDryRun")
            && composition_root.contains("BioCortexOp::RetrievalOptInReviewPacket")
            && composition_root.contains("BioCortexOp::RetrievalOptInExecutionPacket"),
        "main.rs must retain the selected dispatch arms"
    );
    assert!(
        composition_root.contains("BioCortexRetrievalApprovalPacketOptions {")
            && composition_root.contains("BioCortexRetrievalOptInAuditOptions {")
            && composition_root.contains("BioCortexRetrievalOptInDryRunOptions {")
            && composition_root.contains("BioCortexRetrievalOptInReviewPacketOptions {")
            && composition_root.contains("BioCortexRetrievalOptInExecutionPacketOptions {"),
        "main.rs must retain retrieval option assembly"
    );
    assert!(
        composition_root.contains("std::fs::read_to_string(dry_run_json)")
            && composition_root.contains("read dry-run JSON at {dry_run_json:?}")
            && composition_root.contains("parse dry-run JSON at {dry_run_json:?}"),
        "main.rs must retain review-packet input custody and exact errors"
    );
    assert!(
        composition_root.contains("std::fs::read_to_string(review_packet_json)")
            && composition_root.contains("read review-packet JSON at {review_packet_json:?}")
            && composition_root.contains("parse review-packet JSON at {review_packet_json:?}"),
        "main.rs must retain execution-packet input custody and exact errors"
    );
    assert!(
        composition_root.contains("read_optional_json_file("),
        "main.rs must retain optional JSON file loading"
    );
    assert!(
        composition_root.contains("run_biocortex_replay_compare"),
        "main.rs must retain ReplayCompare"
    );

    for forbidden in [
        "run_biocortex_replay_compare",
        "read_optional_json_file",
        "std::fs::read_to_string(dry_run_json)",
        "std::fs::read_to_string(review_packet_json)",
        "run_biocortex_retrieval_opt_in_runtime_trial",
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
