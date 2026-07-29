use std::fs;
use std::path::PathBuf;

fn bridge_source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src")
        .join(relative);
    fs::read_to_string(&path).unwrap_or_else(|err| panic!("reading {}: {err}", path.display()))
}

#[test]
fn workflow_feedback_adapters_are_private_without_moving_root_schema_or_dispatch() {
    let cli_mod = bridge_source("cli/mod.rs");
    let main = bridge_source("main.rs");
    let workflow_feedback = bridge_source("cli/workflow_feedback.rs");

    assert!(cli_mod.contains("pub(super) mod workflow_feedback;"));
    assert!(!cli_mod.contains("pub(super) use workflow_feedback::{"));

    let adapters = [
        "run_workflow_feedback_report",
        "run_workflow_feedback_shadow_score",
        "run_workflow_feedback_promotion_gate",
        "run_workflow_feedback_lift_evidence",
        "run_workflow_feedback_baseline_evidence",
        "run_workflow_feedback_owner_review_packet",
        "run_workflow_feedback_promotion_record",
    ];
    for adapter in adapters {
        assert!(
            workflow_feedback.contains(&format!("pub(crate) fn {adapter}"))
                || workflow_feedback.contains(&format!("pub(crate) async fn {adapter}")),
            "{adapter} must be owned by cli::workflow_feedback"
        );
        assert!(
            !main.contains(&format!("fn {adapter}(")),
            "{adapter} must leave main.rs"
        );
        assert!(
            main.contains(&format!("return {adapter}(")),
            "{adapter} dispatch must remain in main.rs"
        );
    }

    for variant in [
        "WorkflowFeedbackReport {",
        "WorkflowFeedbackShadowScore {",
        "WorkflowFeedbackPromotionGate {",
        "WorkflowFeedbackLiftEvidence {",
        "WorkflowFeedbackBaselineEvidence {",
        "WorkflowFeedbackOwnerReviewPacket {",
        "WorkflowFeedbackPromotionRecord {",
    ] {
        assert!(
            main.contains(variant),
            "{variant} root command schema must remain in main.rs"
        );
    }

    assert!(!workflow_feedback.contains("clap::"));
    assert!(!workflow_feedback.contains("Cmd::"));
    assert!(!workflow_feedback.contains("Hub"));
}
