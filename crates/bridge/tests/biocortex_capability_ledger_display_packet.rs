use ab_bridge::biocortex_capability_ledger::{
    build_biocortex_capability_ledger_display_model_from_packet,
    build_biocortex_capability_ledger_report_packet, consume_biocortex_capability_ledger,
    BioCortexCapabilityLedgerDisplayModel, BioCortexCapabilityLedgerReportPacket,
    BIOCORTEX_CAPABILITY_LEDGER_DISPLAY_MODEL_SCHEMA,
    BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA,
    BIOCORTEX_CAPABILITY_LEDGER_REVIEW_ARTIFACT_SCHEMA,
};

const LEDGER: &str = include_str!("fixtures/biocortex_capability_ledger_schema_v3.txt");
const REVIEW_ARTIFACT: &str =
    include_str!("fixtures/biocortex_capability_ledger_review_artifact_v0.md");

#[test]
fn report_packet_wraps_static_summary_and_markdown_artifact() {
    let summary = consume_biocortex_capability_ledger(LEDGER);
    let packet = build_biocortex_capability_ledger_report_packet(&summary);

    assert_eq!(
        packet.schema,
        BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA
    );
    assert_eq!(
        packet.summary_schema,
        "agent_bridge.biocortex_capability_ledger.consumer_dry_run.v0"
    );
    assert_eq!(
        packet.report_schema,
        BIOCORTEX_CAPABILITY_LEDGER_REVIEW_ARTIFACT_SCHEMA
    );
    assert_eq!(packet.verdict, "accepted");
    assert!(packet.read_only_confirmed);
    assert_eq!(packet.downstream_action, "display_or_review_only");
    assert_eq!(
        packet.integration_decision,
        "shadow_only_no_runtime_admission"
    );
    assert_eq!(packet.summary, summary);
    assert_eq!(packet.report_markdown, REVIEW_ARTIFACT);
    assert!(packet.safety.static_artifact_only);
    assert!(!packet.safety.memory_write_attempted);
    assert!(!packet.safety.retrieval_order_change_attempted);
    assert!(!packet.safety.runtime_authority_observed);
    assert!(!packet.safety.executor_enablement_observed);
    assert!(!packet.safety.mcp_tool_registration);
}

#[test]
fn display_model_is_ready_for_report_and_board_without_authority() {
    let packet = accepted_packet();
    let display_model = build_biocortex_capability_ledger_display_model_from_packet(&packet);

    assert_eq!(
        display_model.schema,
        BIOCORTEX_CAPABILITY_LEDGER_DISPLAY_MODEL_SCHEMA
    );
    assert_eq!(
        display_model.packet_schema,
        BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA
    );
    assert_eq!(display_model.status.label, "Ready for read-only display");
    assert_eq!(display_model.status.tone, "success");
    assert!(display_model.safety.display_ready);
    assert!(display_model.safety.read_only_confirmed);
    assert!(display_model.safety.static_artifact_only);
    assert_eq!(display_model.safety.mutation_surface, "none");
    assert!(!display_model.safety.mcp_tool_registration);
    assert!(display_model
        .safety
        .allowed_surfaces
        .contains(&"forum_post_body".to_string()));
    assert!(display_model
        .safety
        .allowed_surfaces
        .contains(&"dashboard_card".to_string()));
    assert!(display_model
        .safety
        .forbidden_surfaces
        .contains(&"memory_write".to_string()));
    assert!(display_model
        .safety
        .forbidden_surfaces
        .contains(&"runtime_admission".to_string()));
    assert_eq!(
        badge_value(&display_model, "verdict"),
        Some("accepted".to_string())
    );
    assert_eq!(
        metric_value(&display_model, "checks_passed"),
        Some("22".to_string())
    );
    assert_eq!(
        metric_value(&display_model, "required_failed"),
        Some("0".to_string())
    );
    assert!(display_model.failed_checks.is_empty());
    assert_eq!(display_model.report_markdown, REVIEW_ARTIFACT);
}

#[test]
fn rejected_display_model_blocks_board_visibility_and_names_failed_check() {
    let tampered = LEDGER.replace("executor_enabled=false", "executor_enabled=true");
    let summary = consume_biocortex_capability_ledger(&tampered);
    let packet = build_biocortex_capability_ledger_report_packet(&summary);
    let display_model = build_biocortex_capability_ledger_display_model_from_packet(&packet);

    assert_eq!(display_model.status.label, "Rejected");
    assert_eq!(display_model.status.tone, "danger");
    assert!(!display_model.safety.display_ready);
    assert!(!display_model.safety.read_only_confirmed);
    assert_eq!(
        badge_value(&display_model, "verdict"),
        Some("rejected".to_string())
    );
    assert_eq!(
        metric_value(&display_model, "required_failed"),
        Some("1".to_string())
    );
    assert_eq!(display_model.failed_checks.len(), 1);
    assert_eq!(display_model.failed_checks[0].label, "hard_false_executor");
    assert_eq!(display_model.failed_checks[0].tone, "danger");
    assert!(display_model.failed_checks[0]
        .evidence
        .contains("executor_enabled=true"));
    assert!(display_model.report_markdown.contains("verdict: rejected"));
}

#[test]
fn display_model_marks_mutating_packet_as_unsafe() {
    let mut packet = accepted_packet();
    packet.safety.memory_write_attempted = true;
    packet.summary.safety.memory_write_attempted = true;
    let display_model = build_biocortex_capability_ledger_display_model_from_packet(&packet);

    assert_eq!(display_model.status.label, "Rejected");
    assert_eq!(display_model.status.tone, "danger");
    assert!(!display_model.safety.display_ready);
    assert!(display_model.safety.memory_write_attempted);
    assert_eq!(
        badge_value(&display_model, "read_only"),
        Some("false".to_string())
    );
}

#[test]
fn display_model_serializes_as_json_without_runtime_affordances() {
    let display_model =
        build_biocortex_capability_ledger_display_model_from_packet(&accepted_packet());
    let serialized =
        serde_json::to_string_pretty(&display_model).expect("display model pretty json");

    assert!(serialized.contains(BIOCORTEX_CAPABILITY_LEDGER_DISPLAY_MODEL_SCHEMA));
    assert!(serialized.contains("\"display_ready\": true"));
    assert!(serialized.contains("\"mutation_surface\": \"none\""));
    assert!(serialized.contains("\"mcp_tool_registration\": false"));
    assert!(!serialized.contains("\"mcp_tool_registration\": true"));
    assert!(!serialized.contains("\"runtime_authority_observed\": true"));
    assert!(!serialized.contains("\"executor_enablement_observed\": true"));
    assert!(!serialized.contains("\"memory_write_attempted\": true"));
}

fn accepted_packet() -> BioCortexCapabilityLedgerReportPacket {
    let summary = consume_biocortex_capability_ledger(LEDGER);
    build_biocortex_capability_ledger_report_packet(&summary)
}

fn badge_value(
    display_model: &BioCortexCapabilityLedgerDisplayModel,
    label: &str,
) -> Option<String> {
    display_model
        .badges
        .iter()
        .find(|badge| badge.label == label)
        .map(|badge| badge.value.clone())
}

fn metric_value(
    display_model: &BioCortexCapabilityLedgerDisplayModel,
    label: &str,
) -> Option<String> {
    display_model
        .metrics
        .iter()
        .find(|metric| metric.label == label)
        .map(|metric| metric.value.clone())
}
