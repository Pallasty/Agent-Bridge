use ab_bridge::lswr_snapshot_bridge::{
    build_readonly_bridge_snapshot, ReadOnlyBridgeSnapshot, ReadOnlyBridgeSnapshotOptions,
};
use ab_bridge::lswr_snapshot_consumer::{
    build_readonly_bridge_consumer_summary, ReadOnlyBridgeConsumerSummary,
    LSWR_READONLY_BRIDGE_CONSUMER_SUMMARY_SCHEMA,
};
use ab_world_core::WorldLedgerSnapshot;

const LEDGER_SNAPSHOT_JSON: &str = include_str!("fixtures/lswr_ledger_snapshot_v0.json");
const PROJECTION_JSON: &str = include_str!("fixtures/lswr_readonly_bridge_projection_v0.json");
const CONSUMER_SUMMARY_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_consumer_summary_v0.json");

#[test]
fn consumer_summary_fixture_matches_generated_detailed_summary() {
    let snapshot: WorldLedgerSnapshot =
        serde_json::from_str(LEDGER_SNAPSHOT_JSON).expect("ledger snapshot fixture json");
    let projection = build_readonly_bridge_snapshot(
        snapshot,
        ReadOnlyBridgeSnapshotOptions {
            include_snapshot: true,
        },
    )
    .expect("readonly bridge projection");
    let summary = build_readonly_bridge_consumer_summary(&projection);
    let expected: ReadOnlyBridgeConsumerSummary =
        serde_json::from_str(CONSUMER_SUMMARY_JSON).expect("consumer summary fixture json");

    assert_eq!(summary, expected);
}

#[test]
fn consumer_summary_keeps_human_feedback_separate_from_verification() {
    let summary: ReadOnlyBridgeConsumerSummary =
        serde_json::from_str(CONSUMER_SUMMARY_JSON).expect("consumer summary fixture json");

    assert_eq!(summary.schema, LSWR_READONLY_BRIDGE_CONSUMER_SUMMARY_SCHEMA);
    assert_eq!(summary.readback_mode, "detailed_snapshot");
    assert!(summary.read_only_confirmed);
    assert_eq!(summary.outcome_counts.verified, Some(1));
    assert_eq!(summary.outcome_counts.not_verified, Some(0));
    assert_eq!(summary.outcome_counts.blocked, Some(0));
    assert_eq!(
        summary.outcome_counts.feedback_changes_world_verdict,
        Some(0)
    );
    assert_eq!(summary.verified.len(), 1);
    assert_eq!(summary.feedback.len(), 1);
    assert_eq!(summary.feedback[0].decision.as_deref(), Some("accept"));
    assert!(!summary.feedback[0].changes_world_verdict);
}

#[test]
fn consumer_summary_degrades_to_counts_only_without_embedded_snapshot() {
    let projection: ReadOnlyBridgeSnapshot =
        serde_json::from_str(PROJECTION_JSON).expect("projection fixture json");
    assert!(projection.snapshot.is_none());

    let summary = build_readonly_bridge_consumer_summary(&projection);

    assert_eq!(summary.readback_mode, "counts_only");
    assert!(summary.read_only_confirmed);
    assert_eq!(summary.counts.actions, 1);
    assert_eq!(summary.counts.verifications, 1);
    assert_eq!(summary.outcome_counts.verified, None);
    assert_eq!(summary.outcome_counts.feedback_changes_world_verdict, None);
    assert!(summary.verified.is_empty());
    assert!(summary.feedback.is_empty());
    assert!(summary.rollbacks.is_empty());
}

#[test]
fn consumer_summary_fixture_keeps_stable_pretty_json() {
    let fixture: ReadOnlyBridgeConsumerSummary =
        serde_json::from_str(CONSUMER_SUMMARY_JSON).expect("consumer summary fixture json");
    let pretty = serde_json::to_string_pretty(&fixture).expect("pretty consumer summary json");

    assert_eq!(format!("{pretty}\n"), CONSUMER_SUMMARY_JSON);
}
