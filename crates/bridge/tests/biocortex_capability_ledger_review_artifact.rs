use ab_bridge::biocortex_capability_ledger::{
    consume_biocortex_capability_ledger, render_biocortex_capability_ledger_review_artifact,
    BIOCORTEX_CAPABILITY_LEDGER_REVIEW_ARTIFACT_SCHEMA,
};

const LEDGER: &str = include_str!("fixtures/biocortex_capability_ledger_schema_v3.txt");
const REVIEW_ARTIFACT: &str =
    include_str!("fixtures/biocortex_capability_ledger_review_artifact_v0.md");

#[test]
fn review_artifact_fixture_matches_consumer_summary() {
    let summary = consume_biocortex_capability_ledger(LEDGER);

    assert_eq!(
        render_biocortex_capability_ledger_review_artifact(&summary),
        REVIEW_ARTIFACT
    );
}

#[test]
fn review_artifact_is_forum_report_readable_without_authority() {
    let artifact = REVIEW_ARTIFACT;

    assert!(artifact.contains(BIOCORTEX_CAPABILITY_LEDGER_REVIEW_ARTIFACT_SCHEMA));
    assert!(artifact.contains("# BioCortex Capability Ledger Review Artifact"));
    assert!(artifact.contains("verdict: accepted"));
    assert!(artifact.contains("downstream_action: display_or_review_only"));
    assert!(artifact.contains("integration_decision: shadow_only_no_runtime_admission"));
    assert!(artifact.contains("- memory_write_attempted: false"));
    assert!(artifact.contains("- retrieval_order_change_attempted: false"));
    assert!(artifact.contains("- mcp_tool_registration: false"));
    assert!(artifact.contains("- runtime_authority_observed: false"));
    assert!(artifact.contains("- executor_enablement_observed: false"));
    assert!(artifact.contains("- failed: 0"));
    assert!(artifact.contains("- This artifact is display/review only."));
    assert!(artifact.contains("not owner authorization"));
    assert!(!artifact.contains("runtime_authority_observed: true"));
    assert!(!artifact.contains("executor_enablement_observed: true"));
    assert!(!artifact.contains("memory_write_attempted: true"));
}

#[test]
fn rejected_artifact_blocks_visibility_and_names_failed_check() {
    let tampered = LEDGER.replace("executor_enabled=false", "executor_enabled=true");
    let summary = consume_biocortex_capability_ledger(&tampered);
    let artifact = render_biocortex_capability_ledger_review_artifact(&summary);

    assert!(artifact.contains("verdict: rejected"));
    assert!(artifact.contains("read_only_confirmed: false"));
    assert!(artifact.contains("downstream_action: reject_static_ledger_artifact"));
    assert!(artifact.contains("integration_decision: blocked_by_static_ledger_validation"));
    assert!(artifact.contains("- failed: 1"));
    assert!(artifact.contains("- required_failed: 1"));
    assert!(artifact.contains(
        "- hard_false_executor: failed; required=true; evidence=executor_enabled=true, expected=false"
    ));
    assert!(artifact.contains(
        "A rejected artifact must not be surfaced as a valid BioCortex capability summary."
    ));
}
