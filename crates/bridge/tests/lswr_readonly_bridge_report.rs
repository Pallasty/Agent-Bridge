use ab_bridge::lswr_snapshot_bridge::ReadOnlyBridgeSnapshot;
use ab_bridge::lswr_snapshot_consumer::{
    ReadOnlyBridgeConsumerSummary, build_readonly_bridge_consumer_summary,
};
use ab_bridge::lswr_snapshot_report::{
    LSWR_READONLY_BRIDGE_REPORT_SCHEMA, render_readonly_bridge_report,
};

const PROJECTION_JSON: &str = include_str!("fixtures/lswr_readonly_bridge_projection_v0.json");
const CONSUMER_SUMMARY_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_consumer_summary_v0.json");
const DETAILED_REPORT: &str = include_str!("fixtures/lswr_readonly_bridge_report_detailed_v0.md");
const COUNTS_ONLY_REPORT: &str =
    include_str!("fixtures/lswr_readonly_bridge_report_counts_only_v0.md");

#[test]
fn detailed_report_fixture_matches_consumer_summary() {
    let summary: ReadOnlyBridgeConsumerSummary =
        serde_json::from_str(CONSUMER_SUMMARY_JSON).expect("consumer summary fixture json");

    assert_eq!(render_readonly_bridge_report(&summary), DETAILED_REPORT);
}

#[test]
fn counts_only_report_fixture_matches_projection_without_snapshot() {
    let projection: ReadOnlyBridgeSnapshot =
        serde_json::from_str(PROJECTION_JSON).expect("projection fixture json");
    let summary = build_readonly_bridge_consumer_summary(&projection);

    assert_eq!(summary.readback_mode, "counts_only");
    assert_eq!(render_readonly_bridge_report(&summary), COUNTS_ONLY_REPORT);
}

#[test]
fn report_keeps_human_feedback_visible_but_not_verified() {
    let report = DETAILED_REPORT;

    assert!(report.contains(LSWR_READONLY_BRIDGE_REPORT_SCHEMA));
    assert!(report.contains("## Verified"));
    assert!(report.contains("action:move_cube_readonly_fixture"));
    assert!(report.contains("## Feedback"));
    assert!(report.contains("decision: accept"));
    assert!(report.contains("feedback_changes_world_verdict: 0"));
    assert!(!report.contains("changes_world_verdict: true"));
}
