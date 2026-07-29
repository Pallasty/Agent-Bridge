use ab_store::SqliteStore;
use anyhow::{Context, Result};
use std::path::PathBuf;

/// Read-only workflow feedback report: compose existing store statistics and
/// MCP tool-call telemetry into a maturity scorecard. No control-plane
/// dependencies and no writes.
pub(crate) async fn run_workflow_feedback_report(
    as_json: bool,
    window_secs: i64,
    top_tools: u32,
) -> Result<()> {
    let db_path = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(ab_store::default_db_path);
    let store = SqliteStore::open(&db_path)
        .await
        .context("opening store for workflow feedback report")?;
    let scope = std::env::current_dir()
        .ok()
        .map(|p| format!("project:{}", p.display()));
    let report = ab_bridge::workflow_feedback::build_report(
        &store,
        ab_bridge::workflow_feedback::WorkflowFeedbackReportOptions {
            window_secs,
            top_tools,
            scope,
        },
    )
    .await
    .context("building workflow feedback report")?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report.to_json_value())?);
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}

pub(crate) fn run_workflow_feedback_shadow_score(
    fixtures: &[PathBuf],
    scenarios: &[String],
    as_json: bool,
) -> Result<()> {
    let report = ab_bridge::workflow_feedback::build_shadow_score_report_from_paths(
        fixtures,
        scenarios.to_vec(),
    )
    .context("building workflow feedback shadow score")?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report.to_json_value())?);
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn run_workflow_feedback_promotion_gate(
    shadow_scores: &[PathBuf],
    owner_approval_refs: &[String],
    rollback_refs: &[String],
    behavior_lift_refs: &[String],
    min_shadow_reports: usize,
    min_scenarios: usize,
    min_strong_scenarios: usize,
    min_top_shadow_score: u32,
    as_json: bool,
) -> Result<()> {
    let report = ab_bridge::workflow_feedback::build_promotion_gate_report_from_paths(
        shadow_scores,
        ab_bridge::workflow_feedback::WorkflowFeedbackPromotionGateOptions {
            owner_approval_refs: owner_approval_refs.to_vec(),
            rollback_refs: rollback_refs.to_vec(),
            behavior_lift_refs: behavior_lift_refs.to_vec(),
            min_shadow_reports,
            min_scenarios,
            min_strong_scenarios,
            min_top_shadow_score,
        },
    )
    .context("building workflow feedback promotion gate")?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report.to_json_value())?);
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn run_workflow_feedback_lift_evidence(
    scenario_fixture: &PathBuf,
    shadow_scores: &[PathBuf],
    baseline_correct: Option<u32>,
    baseline_total: Option<u32>,
    min_accuracy: f64,
    min_lift: f64,
    as_json: bool,
) -> Result<()> {
    let report = ab_bridge::workflow_feedback::build_lift_evidence_report_from_paths(
        scenario_fixture,
        shadow_scores,
        ab_bridge::workflow_feedback::WorkflowFeedbackLiftEvidenceOptions {
            baseline_correct,
            baseline_total,
            min_accuracy,
            min_lift,
        },
    )
    .context("building workflow feedback lift evidence")?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report.to_json_value())?);
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}

pub(crate) fn run_workflow_feedback_baseline_evidence(
    scenario_fixture: &PathBuf,
    baseline_observations: &[PathBuf],
    rollback_refs: &[String],
    as_json: bool,
) -> Result<()> {
    let report = ab_bridge::workflow_feedback::build_baseline_evidence_report_from_paths(
        scenario_fixture,
        baseline_observations,
        ab_bridge::workflow_feedback::WorkflowFeedbackBaselineEvidenceOptions {
            rollback_refs: rollback_refs.to_vec(),
        },
    )
    .context("building workflow feedback baseline evidence")?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report.to_json_value())?);
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
pub(crate) fn run_workflow_feedback_owner_review_packet(
    scenario_fixture: &PathBuf,
    baseline_observations: &[PathBuf],
    shadow_scores: &[PathBuf],
    rollback_refs: &[String],
    owner_approval_refs: &[String],
    min_accuracy: f64,
    min_lift: f64,
    min_shadow_reports: usize,
    min_scenarios: usize,
    min_strong_scenarios: usize,
    min_top_shadow_score: u32,
    as_json: bool,
) -> Result<()> {
    let report = ab_bridge::workflow_feedback::build_owner_review_packet_from_paths(
        scenario_fixture,
        baseline_observations,
        shadow_scores,
        ab_bridge::workflow_feedback::WorkflowFeedbackOwnerReviewPacketOptions {
            rollback_refs: rollback_refs.to_vec(),
            owner_approval_refs: owner_approval_refs.to_vec(),
            min_accuracy,
            min_lift,
            min_shadow_reports,
            min_scenarios,
            min_strong_scenarios,
            min_top_shadow_score,
        },
    )
    .context("building workflow feedback owner review packet")?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report.to_json_value())?);
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}

pub(crate) fn run_workflow_feedback_promotion_record(
    owner_review_packet: &PathBuf,
    promotion_scopes: &[String],
    owner_approval_refs: &[String],
    rollback_refs: &[String],
    as_json: bool,
) -> Result<()> {
    let report = ab_bridge::workflow_feedback::build_promotion_record_from_path(
        owner_review_packet,
        ab_bridge::workflow_feedback::WorkflowFeedbackPromotionRecordOptions {
            owner_approval_refs: owner_approval_refs.to_vec(),
            rollback_refs: rollback_refs.to_vec(),
            promotion_scopes: promotion_scopes.to_vec(),
        },
    )
    .context("building workflow feedback promotion record")?;
    if as_json {
        println!("{}", serde_json::to_string_pretty(&report.to_json_value())?);
    } else {
        print!("{}", report.render_markdown());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn missing_fixture() -> PathBuf {
        PathBuf::from("/definitely/missing/agent-bridge-workflow-feedback-fixture.json")
    }

    #[test]
    fn shadow_score_preserves_adapter_error_context() {
        let err = run_workflow_feedback_shadow_score(&[missing_fixture()], &[], true)
            .expect_err("a missing fixture must fail");
        assert!(err
            .to_string()
            .contains("building workflow feedback shadow score"));
    }

    #[test]
    fn promotion_record_preserves_adapter_error_context() {
        let err = run_workflow_feedback_promotion_record(&missing_fixture(), &[], &[], &[], true)
            .expect_err("a missing owner review packet must fail");
        assert!(err
            .to_string()
            .contains("building workflow feedback promotion record"));
    }
}
