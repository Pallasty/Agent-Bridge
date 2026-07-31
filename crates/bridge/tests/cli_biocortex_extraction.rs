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
        "run_biocortex_retrieval_opt_in_runtime_influence_decision_packet",
        "run_biocortex_retrieval_opt_in_runtime_readiness_packet",
        "run_biocortex_retrieval_opt_in_runtime_transition_gate",
        "run_biocortex_retrieval_downstream_aio_runtime_evidence_handoff",
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
                .contains("BioCortexOp::RetrievalOptInRuntimeInfluenceReviewRequest")
            && composition_root
                .contains("BioCortexOp::RetrievalOptInRuntimeInfluenceDecisionPacket")
            && composition_root.contains("BioCortexOp::RetrievalOptInRuntimeReadinessPacket")
            && composition_root.contains("BioCortexOp::RetrievalOptInRuntimeTransitionGate")
            && composition_root
                .contains("BioCortexOp::RetrievalDownstreamAioRuntimeEvidenceHandoff"),
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
                .contains("BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {")
            && composition_root
                .contains("BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {")
            && composition_root.contains("BioCortexRetrievalOptInRuntimeReadinessPacketOptions {")
            && composition_root.contains("BioCortexRetrievalOptInRuntimeTransitionGateOptions {")
            && composition_root
                .contains("BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions {"),
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
        composition_root
            .contains("std::fs::read_to_string(runtime_influence_review_request_json)")
            && composition_root.contains(
                "read opt-in runtime influence review request JSON at {runtime_influence_review_request_json:?}",
            )
            && composition_root.contains(
                "parse opt-in runtime influence review request JSON at {runtime_influence_review_request_json:?}",
            )
            && composition_root
                .contains("std::fs::read_to_string(runtime_influence_decision_json)")
            && composition_root.contains(
                "read opt-in runtime influence decision JSON at {runtime_influence_decision_json:?}",
            )
            && composition_root.contains(
                "parse opt-in runtime influence decision JSON at {runtime_influence_decision_json:?}",
            ),
        "main.rs must retain runtime-influence decision-packet input custody and exact errors"
    );
    assert!(
        composition_root
            .contains("std::fs::read_to_string(runtime_influence_decision_packet_json)")
            && composition_root.contains(
                "read opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}",
            )
            && composition_root.contains(
                "parse opt-in runtime influence decision packet JSON at {runtime_influence_decision_packet_json:?}",
            )
            && composition_root.contains("std::fs::read_to_string(store_trial_json)")
            && composition_root
                .contains("read opt-in store trial JSON at {store_trial_json:?}")
            && composition_root
                .contains("parse opt-in store trial JSON at {store_trial_json:?}")
            && composition_root.contains("std::fs::read_to_string(batch_diagnostics_json)")
            && composition_root
                .contains("read opt-in batch diagnostics JSON at {batch_diagnostics_json:?}")
            && composition_root
                .contains("parse opt-in batch diagnostics JSON at {batch_diagnostics_json:?}"),
        "main.rs must retain runtime-readiness input custody and exact errors"
    );
    assert!(
        composition_root.contains("std::fs::read_to_string(runtime_readiness_packet_json)")
            && composition_root.contains(
                "read opt-in runtime readiness packet JSON at {runtime_readiness_packet_json:?}",
            )
            && composition_root.contains(
                "parse opt-in runtime readiness packet JSON at {runtime_readiness_packet_json:?}",
            )
            && composition_root.contains("operator_disabled: *operator_disabled")
            && composition_root.contains("|| cli_env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV)",),
        "main.rs must retain runtime-transition input and operator-disable custody"
    );
    let checkpoint_read = composition_root
        .find("std::fs::read_to_string(checkpoint_selection_json)")
        .expect("main.rs must retain downstream checkpoint input custody");
    let review_read = composition_root
        .find("std::fs::read_to_string(post_semantic_diverse_review_json)")
        .expect("main.rs must retain downstream review input custody");
    let controlled_read = composition_root
        .find("let controlled_body = std::fs::read_to_string(")
        .expect("main.rs must retain optional controlled-readiness input custody");
    assert!(
        checkpoint_read < review_read && review_read < controlled_read,
        "main.rs must retain checkpoint -> review -> optional controlled-readiness precedence"
    );
    assert!(
        composition_root.contains(
            "read downstream AIO checkpoint selection JSON at {checkpoint_selection_json:?}",
        ) && composition_root.contains(
            "parse downstream AIO checkpoint selection JSON at {checkpoint_selection_json:?}",
        ) && composition_root.contains(
            "read post-semantic-diverse review JSON at {post_semantic_diverse_review_json:?}",
        ) && composition_root.contains(
            "parse post-semantic-diverse review JSON at {post_semantic_diverse_review_json:?}",
        ) && composition_root.contains(
            "let controlled_trial_readiness = if let Some(controlled_trial_readiness_json)",
        ) && composition_root.contains("controlled_trial_readiness_json.as_deref()")
            && composition_root.contains(
                "read controlled trial readiness JSON at {controlled_trial_readiness_json:?}",
            )
            && composition_root.contains(
                "parse controlled trial readiness JSON at {controlled_trial_readiness_json:?}",
            ),
        "main.rs must retain downstream handoff exact errors and optional-input semantics"
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
        "std::fs::read_to_string(runtime_influence_review_request_json)",
        "std::fs::read_to_string(runtime_influence_decision_json)",
        "std::fs::read_to_string(runtime_influence_decision_packet_json)",
        "std::fs::read_to_string(store_trial_json)",
        "std::fs::read_to_string(batch_diagnostics_json)",
        "std::fs::read_to_string(runtime_readiness_packet_json)",
        "std::fs::read_to_string(checkpoint_selection_json)",
        "std::fs::read_to_string(post_semantic_diverse_review_json)",
        "std::fs::read_to_string(controlled_trial_readiness_json)",
        "cli_env_truthy",
        "BIOCORTEX_RETRIEVAL_DISABLE_ENV",
        "run_biocortex_retrieval_opt_in_store_trial",
        "SqliteStore",
        "BioCortexOp",
    ] {
        assert!(
            !module.contains(forbidden),
            "cli::biocortex must not absorb {forbidden}"
        );
    }
}
