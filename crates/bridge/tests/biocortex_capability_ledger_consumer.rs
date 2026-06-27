use ab_bridge::biocortex_capability_ledger::{
    consume_biocortex_capability_ledger, BioCortexCapabilityLedgerConsumerSummary,
    BIOCORTEX_CAPABILITY_LEDGER_CONSUMER_SCHEMA,
};

const LEDGER: &str = include_str!("fixtures/biocortex_capability_ledger_schema_v3.txt");
const SUMMARY_JSON: &str =
    include_str!("fixtures/biocortex_capability_ledger_consumer_summary_v0.json");

#[test]
fn capability_ledger_consumer_fixture_matches_summary() {
    let summary = consume_biocortex_capability_ledger(LEDGER);
    let expected: BioCortexCapabilityLedgerConsumerSummary =
        serde_json::from_str(SUMMARY_JSON).expect("consumer summary fixture json");

    assert_eq!(summary, expected);
}

#[test]
fn capability_ledger_consumer_keeps_readonly_boundary_visible() {
    let summary = consume_biocortex_capability_ledger(LEDGER);

    assert_eq!(summary.schema, BIOCORTEX_CAPABILITY_LEDGER_CONSUMER_SCHEMA);
    assert_eq!(summary.verdict, "accepted");
    assert!(summary.read_only_confirmed);
    assert_eq!(summary.downstream_action, "display_or_review_only");
    assert_eq!(
        summary.integration_decision,
        "shadow_only_no_runtime_admission"
    );
    assert!(summary.safety.static_artifact_only);
    assert!(!summary.safety.memory_write_attempted);
    assert!(!summary.safety.retrieval_order_change_attempted);
    assert!(!summary.safety.runtime_authority_observed);
    assert!(!summary.safety.executor_enablement_observed);
    assert!(!summary.safety.mcp_tool_registration);
    assert!(!summary.safety.nexus_world_tick_touched);
    assert!(!summary.safety.aiot_runtime_called);
    assert!(!summary.safety.language_generation_observed);
    assert!(!summary.safety.cognition_claim_observed);
}

#[test]
fn capability_ledger_consumer_rejects_executor_enabled_tamper() {
    let tampered = LEDGER.replace("executor_enabled=false", "executor_enabled=true");
    let summary = consume_biocortex_capability_ledger(&tampered);

    assert_eq!(summary.verdict, "rejected");
    assert!(!summary.read_only_confirmed);
    assert_eq!(summary.downstream_action, "reject_static_ledger_artifact");
    assert_eq!(
        failed_check(&summary, "hard_false_executor"),
        "executor_enabled=true, expected=false"
    );
    assert!(!summary.safety.executor_enablement_observed);
    assert!(!summary.safety.memory_write_attempted);
}

#[test]
fn capability_ledger_consumer_rejects_prose_verdict_laundering() {
    let tampered = LEDGER.replace(
        "source_kind_g_next_verdict=prose_verdict",
        "source_kind_g_next_verdict=executable_report",
    );
    let summary = consume_biocortex_capability_ledger(&tampered);

    assert_eq!(summary.verdict, "rejected");
    assert_eq!(
        failed_check(&summary, "source_g_next_boundary"),
        "source_kind_g_next_verdict=executable_report, expected=prose_verdict"
    );
}

#[test]
fn capability_ledger_consumer_rejects_malformed_ledger() {
    let summary = consume_biocortex_capability_ledger("schema_version:3\n");

    assert_eq!(summary.verdict, "rejected");
    assert_eq!(
        failed_check(&summary, "parse_key_value"),
        "line 1 is not key=value: schema_version:3"
    );
    assert!(!summary.read_only_confirmed);
}

#[test]
fn capability_ledger_consumer_fixture_keeps_stable_pretty_json() {
    let summary: BioCortexCapabilityLedgerConsumerSummary =
        serde_json::from_str(SUMMARY_JSON).expect("consumer summary fixture json");
    let pretty = serde_json::to_string_pretty(&summary).expect("pretty consumer summary json");

    assert_eq!(format!("{pretty}\n"), SUMMARY_JSON);
}

fn failed_check<'a>(summary: &'a BioCortexCapabilityLedgerConsumerSummary, check: &str) -> &'a str {
    summary
        .checks
        .iter()
        .find(|candidate| candidate.check == check)
        .expect("expected dry-run check")
        .evidence
        .as_str()
}
