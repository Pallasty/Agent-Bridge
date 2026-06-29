use ab_bridge::biocortex_composed_limit_cycle::{
    build_biocortex_composed_limit_cycle_display_model_from_packet,
    build_biocortex_composed_limit_cycle_report_packet,
    consume_biocortex_composed_limit_cycle_ledger,
    render_biocortex_composed_limit_cycle_review_artifact, BioCortexComposedLimitCycleDisplayModel,
    BioCortexComposedLimitCycleReportPacket, BIOCORTEX_COMPOSED_LIMIT_CYCLE_CONSUMER_SCHEMA,
    BIOCORTEX_COMPOSED_LIMIT_CYCLE_DISPLAY_MODEL_SCHEMA,
    BIOCORTEX_COMPOSED_LIMIT_CYCLE_REPORT_PACKET_SCHEMA,
    BIOCORTEX_COMPOSED_LIMIT_CYCLE_REVIEW_ARTIFACT_SCHEMA,
};

const LEDGER: &str = include_str!("fixtures/biocortex_composed_limit_cycle_schema_v4.txt");

#[test]
fn composed_limit_cycle_consumer_accepts_schema_v4_shadow_ledger() {
    let summary = consume_biocortex_composed_limit_cycle_ledger(LEDGER);

    assert_eq!(
        summary.schema,
        BIOCORTEX_COMPOSED_LIMIT_CYCLE_CONSUMER_SCHEMA
    );
    assert_eq!(
        summary.input_schema,
        "biocortex.composed_limit_cycle_shadow_adapter.v4"
    );
    assert_eq!(summary.input_schema_version.as_deref(), Some("4"));
    assert_eq!(
        summary.input_generated_by.as_deref(),
        Some("composed_limit_cycle_shadow_adapter")
    );
    assert_eq!(summary.verdict, "accepted");
    assert!(summary.read_only_confirmed);
    assert_eq!(summary.downstream_action, "display_or_review_only");
    assert_eq!(
        summary.integration_decision,
        "shadow_only_no_runtime_admission"
    );
    assert!(summary.compose_criterion_positive_observed);
    assert!(summary.ablation_control_observed);
    assert!(summary.disclosed_caveats_present);
    assert!(summary.safety.static_artifact_only);
    assert!(!summary.safety.memory_write_attempted);
    assert!(!summary.safety.retrieval_order_change_attempted);
    assert!(!summary.safety.runtime_authority_observed);
    assert!(!summary.safety.executor_enablement_observed);
    assert!(!summary.safety.adapter_mutation_observed);
    assert!(!summary.safety.substrate_mechanism_added_observed);
    assert!(!summary.safety.mcp_tool_registration);
    assert!(!summary.safety.language_generation_observed);
    assert!(!summary.safety.cognition_claim_observed);
}

#[test]
fn composed_limit_cycle_consumer_rejects_executor_enabled_tamper() {
    let tampered = LEDGER.replace("executor_enabled=false", "executor_enabled=true");
    let summary = consume_biocortex_composed_limit_cycle_ledger(&tampered);

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
fn composed_limit_cycle_consumer_rejects_caveat_dropping_tampers() {
    for (tampered, check, evidence) in [
        (
            LEDGER.replace(
                "is_auto_associative_attractor=false",
                "is_auto_associative_attractor=true",
            ),
            "scope_no_auto_associative_attractor",
            "is_auto_associative_attractor=true, expected=false",
        ),
        (
            LEDGER.replace(
                "lif_nonlinearity_load_bearing=false",
                "lif_nonlinearity_load_bearing=true",
            ),
            "caveat_lif_nonlinearity_not_load_bearing",
            "lif_nonlinearity_load_bearing=true, expected=false",
        ),
        (
            LEDGER.replace(
                "replay_is_threshold_linear_reproducible=true",
                "replay_is_threshold_linear_reproducible=false",
            ),
            "caveat_threshold_linear_replay_basis",
            "replay_is_threshold_linear_reproducible=false, expected=true",
        ),
        (
            LEDGER.replace(
                "supplied_primitive=assembly_ring_plus_convergence_plus_delay",
                "supplied_primitive=bare_recurrence",
            ),
            "caveat_supplied_primitive_bundle",
            "supplied_primitive=bare_recurrence, expected=assembly_ring_plus_convergence_plus_delay",
        ),
    ] {
        let summary = consume_biocortex_composed_limit_cycle_ledger(&tampered);

        assert_eq!(summary.verdict, "rejected");
        assert!(!summary.read_only_confirmed);
        assert!(!summary.disclosed_caveats_present);
        assert_eq!(failed_check(&summary, check), evidence);
    }
}

#[test]
fn composed_limit_cycle_consumer_rejects_malformed_ledger() {
    let summary = consume_biocortex_composed_limit_cycle_ledger("schema_version:4\n");

    assert_eq!(summary.verdict, "rejected");
    assert_eq!(
        failed_check(&summary, "parse_key_value"),
        "line 1 is not key=value: schema_version:4"
    );
    assert!(!summary.read_only_confirmed);
}

#[test]
fn review_artifact_is_forum_report_readable_without_authority() {
    let summary = consume_biocortex_composed_limit_cycle_ledger(LEDGER);
    let artifact = render_biocortex_composed_limit_cycle_review_artifact(&summary);

    assert!(artifact.contains(BIOCORTEX_COMPOSED_LIMIT_CYCLE_REVIEW_ARTIFACT_SCHEMA));
    assert!(artifact.contains("# BioCortex C1 Composed Limit-Cycle Review Artifact"));
    assert!(artifact.contains("verdict: accepted"));
    assert!(artifact.contains("downstream_action: display_or_review_only"));
    assert!(artifact.contains("integration_decision: shadow_only_no_runtime_admission"));
    assert!(artifact.contains("- compose_criterion_positive_observed: true"));
    assert!(artifact.contains("- ablation_control_observed: true"));
    assert!(artifact.contains("- disclosed_caveats_present: true"));
    assert!(artifact.contains("- memory_write_attempted: false"));
    assert!(artifact.contains("- retrieval_order_change_attempted: false"));
    assert!(artifact.contains("- mcp_tool_registration: false"));
    assert!(artifact.contains("- runtime_authority_observed: false"));
    assert!(artifact.contains("- executor_enablement_observed: false"));
    assert!(artifact.contains("- failed: 0"));
    assert!(artifact.contains("- This artifact is display/review only."));
    assert!(artifact.contains("not owner authorization"));
    assert!(artifact.contains("with its disclosed caveats intact"));
    assert!(!artifact.contains("runtime_authority_observed: true"));
    assert!(!artifact.contains("executor_enablement_observed: true"));
    assert!(!artifact.contains("memory_write_attempted: true"));
}

#[test]
fn report_packet_wraps_static_summary_and_markdown_artifact() {
    let summary = consume_biocortex_composed_limit_cycle_ledger(LEDGER);
    let artifact = render_biocortex_composed_limit_cycle_review_artifact(&summary);
    let packet = build_biocortex_composed_limit_cycle_report_packet(&summary);

    assert_eq!(
        packet.schema,
        BIOCORTEX_COMPOSED_LIMIT_CYCLE_REPORT_PACKET_SCHEMA
    );
    assert_eq!(
        packet.summary_schema,
        BIOCORTEX_COMPOSED_LIMIT_CYCLE_CONSUMER_SCHEMA
    );
    assert_eq!(
        packet.report_schema,
        BIOCORTEX_COMPOSED_LIMIT_CYCLE_REVIEW_ARTIFACT_SCHEMA
    );
    assert_eq!(packet.verdict, "accepted");
    assert!(packet.read_only_confirmed);
    assert!(packet.compose_criterion_positive_observed);
    assert!(packet.ablation_control_observed);
    assert!(packet.disclosed_caveats_present);
    assert_eq!(packet.summary, summary);
    assert_eq!(packet.report_markdown, artifact);
    assert!(packet.safety.static_artifact_only);
    assert!(!packet.safety.memory_write_attempted);
    assert!(!packet.safety.retrieval_order_change_attempted);
    assert!(!packet.safety.runtime_authority_observed);
    assert!(!packet.safety.executor_enablement_observed);
    assert!(!packet.safety.mcp_tool_registration);
}

#[test]
fn display_model_is_ready_for_report_and_board_without_authority() {
    let display_model =
        build_biocortex_composed_limit_cycle_display_model_from_packet(&accepted_packet());

    assert_eq!(
        display_model.schema,
        BIOCORTEX_COMPOSED_LIMIT_CYCLE_DISPLAY_MODEL_SCHEMA
    );
    assert_eq!(
        display_model.packet_schema,
        BIOCORTEX_COMPOSED_LIMIT_CYCLE_REPORT_PACKET_SCHEMA
    );
    assert_eq!(display_model.title, "BioCortex C1 Composed Limit Cycle");
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
    assert!(display_model
        .safety
        .forbidden_surfaces
        .contains(&"caveat_dropping".to_string()));
    assert_eq!(
        badge_value(&display_model, "verdict"),
        Some("accepted".to_string())
    );
    assert_eq!(
        badge_value(&display_model, "caveats"),
        Some("true".to_string())
    );
    assert_eq!(
        metric_value(&display_model, "checks_passed"),
        Some("27".to_string())
    );
    assert_eq!(
        metric_value(&display_model, "required_failed"),
        Some("0".to_string())
    );
    assert!(display_model.failed_checks.is_empty());
    assert!(display_model.report_markdown.contains("verdict: accepted"));
}

#[test]
fn rejected_display_model_blocks_board_visibility_and_names_failed_check() {
    let tampered = LEDGER.replace(
        "is_auto_associative_attractor=false",
        "is_auto_associative_attractor=true",
    );
    let summary = consume_biocortex_composed_limit_cycle_ledger(&tampered);
    let packet = build_biocortex_composed_limit_cycle_report_packet(&summary);
    let display_model = build_biocortex_composed_limit_cycle_display_model_from_packet(&packet);

    assert_eq!(display_model.status.label, "Rejected");
    assert_eq!(display_model.status.tone, "danger");
    assert!(!display_model.safety.display_ready);
    assert!(!display_model.safety.read_only_confirmed);
    assert_eq!(
        badge_value(&display_model, "verdict"),
        Some("rejected".to_string())
    );
    assert_eq!(
        badge_value(&display_model, "caveats"),
        Some("false".to_string())
    );
    assert_eq!(
        metric_value(&display_model, "required_failed"),
        Some("1".to_string())
    );
    assert_eq!(display_model.failed_checks.len(), 1);
    assert_eq!(
        display_model.failed_checks[0].label,
        "scope_no_auto_associative_attractor"
    );
    assert_eq!(display_model.failed_checks[0].tone, "danger");
    assert!(display_model.failed_checks[0]
        .evidence
        .contains("is_auto_associative_attractor=true"));
    assert!(display_model.report_markdown.contains("verdict: rejected"));
}

#[test]
fn display_model_marks_mutating_packet_as_unsafe() {
    let mut packet = accepted_packet();
    packet.safety.memory_write_attempted = true;
    packet.summary.safety.memory_write_attempted = true;
    let display_model = build_biocortex_composed_limit_cycle_display_model_from_packet(&packet);

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
fn display_model_rejects_runtime_decision_words_even_when_safety_flags_are_false() {
    let mut packet = accepted_packet();
    packet.downstream_action = "enable_runtime".to_string();
    packet.integration_decision = "runtime_admission".to_string();
    let display_model = build_biocortex_composed_limit_cycle_display_model_from_packet(&packet);

    assert_eq!(display_model.status.label, "Rejected");
    assert_eq!(display_model.status.tone, "danger");
    assert!(!display_model.safety.display_ready);
    assert!(display_model.safety.read_only_confirmed);
    assert_eq!(
        badge_value(&display_model, "downstream_action"),
        Some("enable_runtime".to_string())
    );
    assert_eq!(
        badge_value(&display_model, "integration_decision"),
        Some("runtime_admission".to_string())
    );
}

#[test]
fn display_model_serializes_as_json_without_runtime_affordances() {
    let display_model =
        build_biocortex_composed_limit_cycle_display_model_from_packet(&accepted_packet());
    let serialized =
        serde_json::to_string_pretty(&display_model).expect("display model pretty json");

    assert!(serialized.contains(BIOCORTEX_COMPOSED_LIMIT_CYCLE_DISPLAY_MODEL_SCHEMA));
    assert!(serialized.contains("\"display_ready\": true"));
    assert!(serialized.contains("\"mutation_surface\": \"none\""));
    assert!(serialized.contains("\"mcp_tool_registration\": false"));
    assert!(!serialized.contains("\"mcp_tool_registration\": true"));
    assert!(!serialized.contains("\"runtime_authority_observed\": true"));
    assert!(!serialized.contains("\"executor_enablement_observed\": true"));
    assert!(!serialized.contains("\"memory_write_attempted\": true"));
}

fn accepted_packet() -> BioCortexComposedLimitCycleReportPacket {
    let summary = consume_biocortex_composed_limit_cycle_ledger(LEDGER);
    build_biocortex_composed_limit_cycle_report_packet(&summary)
}

fn failed_check<'a>(
    summary: &'a ab_bridge::biocortex_composed_limit_cycle::BioCortexComposedLimitCycleConsumerSummary,
    check: &str,
) -> &'a str {
    summary
        .checks
        .iter()
        .find(|candidate| candidate.check == check)
        .expect("expected dry-run check")
        .evidence
        .as_str()
}

fn badge_value(
    display_model: &BioCortexComposedLimitCycleDisplayModel,
    label: &str,
) -> Option<String> {
    display_model
        .badges
        .iter()
        .find(|badge| badge.label == label)
        .map(|badge| badge.value.clone())
}

fn metric_value(
    display_model: &BioCortexComposedLimitCycleDisplayModel,
    label: &str,
) -> Option<String> {
    display_model
        .metrics
        .iter()
        .find(|metric| metric.label == label)
        .map(|metric| metric.value.clone())
}
