mod biocortex;
mod browser_lite;
mod local_control;
mod substrate;
pub(super) mod workflow_feedback;

pub(super) use biocortex::{
    run_biocortex_capability_ledger_report_packet, run_biocortex_retrieval_approval_packet,
    run_biocortex_retrieval_downstream_aio_runtime_evidence_handoff,
    run_biocortex_retrieval_opt_in_authorization_decision_packet,
    run_biocortex_retrieval_opt_in_dry_run, run_biocortex_retrieval_opt_in_evidence_summary,
    run_biocortex_retrieval_opt_in_execution_packet,
    run_biocortex_retrieval_opt_in_order_diff_packet,
    run_biocortex_retrieval_opt_in_post_implementation_review_gate,
    run_biocortex_retrieval_opt_in_redacted_evidence_aggregate,
    run_biocortex_retrieval_opt_in_redacted_order_artifact,
    run_biocortex_retrieval_opt_in_review_packet,
    run_biocortex_retrieval_opt_in_runtime_influence_decision_packet,
    run_biocortex_retrieval_opt_in_runtime_influence_review_request,
    run_biocortex_retrieval_opt_in_runtime_readiness_packet,
    run_biocortex_retrieval_opt_in_runtime_transition_gate,
    run_biocortex_retrieval_opt_in_runtime_trial_review_packet,
    run_biocortex_retrieval_opt_in_status, run_biocortex_shadow_digest,
    run_lswr_interaction_feedback_consumption_preflight, shadow_json_display,
};
pub(super) use browser_lite::{run_browser_lite, BrowserLiteOp};
pub(super) use local_control::{run_a2ui, run_operator_request, A2uiOp, OperatorRequestOp};
pub(super) use substrate::{run_substrate, SubstrateOp};

#[cfg(test)]
mod ownership_tests {
    const ADAPTERS: [&str; 7] = [
        "run_workflow_feedback_report",
        "run_workflow_feedback_shadow_score",
        "run_workflow_feedback_promotion_gate",
        "run_workflow_feedback_lift_evidence",
        "run_workflow_feedback_baseline_evidence",
        "run_workflow_feedback_owner_review_packet",
        "run_workflow_feedback_promotion_record",
    ];

    #[test]
    fn workflow_feedback_module_owns_all_preregistered_adapters() {
        let module = include_str!("workflow_feedback.rs");
        let composition_root = include_str!("../main.rs");

        for adapter in ADAPTERS {
            assert!(
                module.contains(&format!("fn {adapter}(")),
                "cli::workflow_feedback must own {adapter}"
            );
            assert!(
                !composition_root.contains(&format!("fn {adapter}(")),
                "main.rs must not continue to own {adapter}"
            );
        }
    }
}
