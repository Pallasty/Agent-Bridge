mod local_control;
pub(super) mod workflow_feedback;

pub(super) use local_control::{run_a2ui, run_operator_request, A2uiOp, OperatorRequestOp};

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
