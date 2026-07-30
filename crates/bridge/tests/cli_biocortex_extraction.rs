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
        "run_biocortex_retrieval_opt_in_runtime_trial_review_packet",
        "run_biocortex_retrieval_opt_in_order_diff_packet",
        "run_biocortex_retrieval_opt_in_redacted_order_artifact",
        "run_biocortex_retrieval_opt_in_authorization_decision_packet",
        "run_biocortex_retrieval_opt_in_post_implementation_review_gate",
        "run_biocortex_retrieval_opt_in_runtime_influence_review_request",
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
            && composition_root.contains("BioCortexOp::RetrievalOptInExecutionPacket")
            && composition_root.contains("BioCortexOp::RetrievalOptInRuntimeTrialReviewPacket")
            && composition_root.contains("BioCortexOp::RetrievalOptInOrderDiffPacket")
            && composition_root.contains("BioCortexOp::RetrievalOptInRedactedOrderArtifact")
            && composition_root.contains("BioCortexOp::RetrievalOptInAuthorizationDecisionPacket")
            && composition_root.contains("BioCortexOp::RetrievalOptInPostImplementationReviewGate")
            && composition_root
                .contains("BioCortexOp::RetrievalOptInRuntimeInfluenceReviewRequest"),
        "main.rs must retain the selected dispatch arms"
    );
    assert!(
        composition_root.contains("BioCortexRetrievalApprovalPacketOptions {")
            && composition_root.contains("BioCortexRetrievalOptInAuditOptions {")
            && composition_root.contains("BioCortexRetrievalOptInDryRunOptions {")
            && composition_root.contains("BioCortexRetrievalOptInReviewPacketOptions {")
            && composition_root.contains("BioCortexRetrievalOptInExecutionPacketOptions {")
            && composition_root
                .contains("BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions {")
            && composition_root.contains("BioCortexRetrievalOptInOrderDiffPacketOptions {")
            && composition_root.contains("BioCortexRetrievalOptInRedactedOrderArtifactOptions {")
            && composition_root
                .contains("BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {")
            && composition_root
                .contains("BioCortexRetrievalOptInPostImplementationReviewGateOptions {")
            && composition_root
                .contains("BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {"),
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
        composition_root.contains("std::fs::read_to_string(runtime_trial_json)")
            && composition_root.contains("read runtime-trial JSON at {runtime_trial_json:?}")
            && composition_root.contains("parse runtime-trial JSON at {runtime_trial_json:?}"),
        "main.rs must retain runtime-trial-review input custody and exact errors"
    );
    assert!(
        composition_root.contains("std::fs::read_to_string(source_json)")
            && composition_root.contains("read order-diff source JSON at {source_json:?}")
            && composition_root.contains("parse order-diff source JSON at {source_json:?}"),
        "main.rs must retain order-diff input custody and exact errors"
    );
    assert!(
        composition_root.contains("read redacted-order artifact source JSON at {source_json:?}")
            && composition_root
                .contains("parse redacted-order artifact source JSON at {source_json:?}"),
        "main.rs must retain redacted-order artifact input custody and exact errors"
    );
    assert!(
        composition_root.contains("std::fs::read_to_string(authorization_request_json)")
            && composition_root.contains(
                "read opt-in authorization request JSON at {authorization_request_json:?}",
            )
            && composition_root.contains(
                "parse opt-in authorization request JSON at {authorization_request_json:?}",
            )
            && composition_root.contains("std::fs::read_to_string(authorization_decision_json)")
            && composition_root.contains(
                "read opt-in authorization decision JSON at {authorization_decision_json:?}",
            )
            && composition_root.contains(
                "parse opt-in authorization decision JSON at {authorization_decision_json:?}",
            ),
        "main.rs must retain authorization-decision input custody and exact errors"
    );
    assert!(
        composition_root
            .contains("std::fs::read_to_string(authorization_decision_packet_json)")
            && composition_root.contains(
                "read opt-in authorization decision packet JSON at {authorization_decision_packet_json:?}",
            )
            && composition_root.contains(
                "parse opt-in authorization decision packet JSON at {authorization_decision_packet_json:?}",
            )
            && composition_root.contains("std::fs::read_to_string(opt_in_plan_json)")
            && composition_root
                .contains("read opt-in experiment plan JSON at {opt_in_plan_json:?}")
            && composition_root
                .contains("parse opt-in experiment plan JSON at {opt_in_plan_json:?}"),
        "main.rs must retain post-implementation review-gate input custody and exact errors"
    );
    assert!(
        composition_root
            .contains("std::fs::read_to_string(post_implementation_review_gate_json)")
            && composition_root.contains(
                "read opt-in post-implementation review gate JSON at {post_implementation_review_gate_json:?}",
            )
            && composition_root.contains(
                "parse opt-in post-implementation review gate JSON at {post_implementation_review_gate_json:?}",
            )
            && composition_root.contains("std::fs::read_to_string(redacted_order_artifact_json)")
            && composition_root.contains(
                "read opt-in redacted order artifact JSON at {redacted_order_artifact_json:?}",
            )
            && composition_root.contains(
                "parse opt-in redacted order artifact JSON at {redacted_order_artifact_json:?}",
            )
            && composition_root
                .contains("std::fs::read_to_string(redacted_evidence_aggregate_json)")
            && composition_root.contains(
                "read opt-in redacted evidence aggregate JSON at {redacted_evidence_aggregate_json:?}",
            )
            && composition_root.contains(
                "parse opt-in redacted evidence aggregate JSON at {redacted_evidence_aggregate_json:?}",
            )
            && composition_root.contains("std::fs::read_to_string(evidence_summary_json)")
            && composition_root
                .contains("read opt-in evidence summary JSON at {evidence_summary_json:?}")
            && composition_root
                .contains("parse opt-in evidence summary JSON at {evidence_summary_json:?}")
            && composition_root
                .contains("std::fs::read_to_string(capability_ledger_report_packet_json)")
            && composition_root.contains(
                "read BioCortex capability ledger report packet JSON at {capability_ledger_report_packet_json:?}",
            )
            && composition_root.contains(
                "parse BioCortex capability ledger report packet JSON at {capability_ledger_report_packet_json:?}",
            ),
        "main.rs must retain runtime-influence review-request input custody and exact errors"
    );
    assert!(
        composition_root.contains("fn run_biocortex_retrieval_opt_in_runtime_trial("),
        "main.rs must retain the side-signal-capable runtime-trial executor"
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
        "fn run_biocortex_retrieval_opt_in_runtime_trial(",
        "std::fs::read_to_string(runtime_trial_json)",
        "std::fs::read_to_string(source_json)",
        "std::fs::read_to_string(authorization_request_json)",
        "std::fs::read_to_string(authorization_decision_json)",
        "std::fs::read_to_string(authorization_decision_packet_json)",
        "std::fs::read_to_string(opt_in_plan_json)",
        "std::fs::read_to_string(post_implementation_review_gate_json)",
        "std::fs::read_to_string(redacted_order_artifact_json)",
        "std::fs::read_to_string(redacted_evidence_aggregate_json)",
        "std::fs::read_to_string(evidence_summary_json)",
        "std::fs::read_to_string(capability_ledger_report_packet_json)",
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
