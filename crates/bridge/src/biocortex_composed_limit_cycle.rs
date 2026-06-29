//! Static BioCortex C1 composed-limit-cycle consumer dry-run.
//!
//! This module parses a precomputed BioCortex schema-v4 C1 ledger as an inert
//! artifact. It deliberately does not call BioCortex, Agent-Bridge memory,
//! retrieval, MCP registration, Nexus, AiOT, network APIs, or runtime/executor
//! paths.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const BIOCORTEX_COMPOSED_LIMIT_CYCLE_CONSUMER_SCHEMA: &str =
    "agent_bridge.biocortex_composed_limit_cycle.consumer_dry_run.v0";
pub const BIOCORTEX_COMPOSED_LIMIT_CYCLE_REVIEW_ARTIFACT_SCHEMA: &str =
    "agent_bridge.biocortex_composed_limit_cycle.review_artifact.v0";
pub const BIOCORTEX_COMPOSED_LIMIT_CYCLE_REPORT_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_composed_limit_cycle.report_packet.v0";
pub const BIOCORTEX_COMPOSED_LIMIT_CYCLE_DISPLAY_MODEL_SCHEMA: &str =
    "agent_bridge.biocortex_composed_limit_cycle.display_model.v0";

const PASSED: &str = "passed";
const FAILED: &str = "failed";

const REQUIRED_FIELDS: &[(&str, &str, &str)] = &[
    ("schema_version", "4", "schema_version"),
    ("crate", "biocortex-rs", "producer_crate"),
    (
        "generated_by",
        "composed_limit_cycle_shadow_adapter",
        "producer_identity",
    ),
    ("mode", "read_only_shadow", "shadow_mode"),
    (
        "source_reports",
        "composed_limit_cycle",
        "source_report_family",
    ),
    (
        "source_kind_composed_limit_cycle",
        "executable_report",
        "source_composed_limit_cycle",
    ),
    (
        "reframe_compose_criterion_positive",
        "true",
        "capability_reframe_compose_positive",
    ),
    (
        "plasticity_composes_self_sustaining_cycle",
        "true",
        "capability_plasticity_composes_cycle",
    ),
    (
        "ablation_abolishes_the_cycle",
        "true",
        "control_ablation_abolishes_cycle",
    ),
    (
        "content_is_learned_not_wired",
        "true",
        "control_content_learned_not_wired",
    ),
    (
        "assembly_convergence_load_bearing",
        "true",
        "control_convergence_load_bearing",
    ),
    (
        "supplied_primitive",
        "assembly_ring_plus_convergence_plus_delay",
        "caveat_supplied_primitive_bundle",
    ),
    (
        "lif_nonlinearity_load_bearing",
        "false",
        "caveat_lif_nonlinearity_not_load_bearing",
    ),
    (
        "replay_is_threshold_linear_reproducible",
        "true",
        "caveat_threshold_linear_replay_basis",
    ),
    (
        "is_auto_associative_attractor",
        "false",
        "scope_no_auto_associative_attractor",
    ),
    (
        "is_multi_pattern_content_addressable",
        "false",
        "scope_no_multi_pattern_content_addressing",
    ),
    (
        "substrate_mechanism_added",
        "false",
        "hard_false_substrate_mechanism",
    ),
    (
        "runtime_authority_granted",
        "false",
        "hard_false_runtime_authority",
    ),
    ("executor_enabled", "false", "hard_false_executor"),
    (
        "adapter_mutation_api_exposed",
        "false",
        "hard_false_adapter_mutation",
    ),
    ("ab_memory_mutated", "false", "hard_false_ab_memory"),
    (
        "retrieval_order_mutated",
        "false",
        "hard_false_retrieval_order",
    ),
    (
        "language_generated",
        "false",
        "hard_false_language_generation",
    ),
    ("cognition_claimed", "false", "hard_false_cognition"),
    (
        "recommended_default_path",
        "read_only_application_shadow_adapter",
        "recommended_default_path_read_only",
    ),
    (
        "open_limitation",
        "single_ring_traveling_wave_not_auto_associative_attractor_no_autonomous_objective_discovery",
        "open_limitation_non_escalation",
    ),
];

const CAVEAT_CHECKS: &[&str] = &[
    "caveat_supplied_primitive_bundle",
    "caveat_lif_nonlinearity_not_load_bearing",
    "caveat_threshold_linear_replay_basis",
    "scope_no_auto_associative_attractor",
    "scope_no_multi_pattern_content_addressing",
    "open_limitation_non_escalation",
];

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleConsumerSummary {
    pub schema: String,
    pub input_schema: String,
    pub input_schema_version: Option<String>,
    pub input_mode: Option<String>,
    pub input_generated_by: Option<String>,
    pub input_source_commit: Option<String>,
    pub verdict: String,
    pub read_only_confirmed: bool,
    pub downstream_action: String,
    pub integration_decision: String,
    pub compose_criterion_positive_observed: bool,
    pub ablation_control_observed: bool,
    pub disclosed_caveats_present: bool,
    pub safety: BioCortexComposedLimitCycleConsumerSafety,
    pub checks: Vec<BioCortexComposedLimitCycleConsumerCheck>,
    pub guidance: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleConsumerSafety {
    pub static_artifact_only: bool,
    pub memory_write_attempted: bool,
    pub retrieval_order_change_attempted: bool,
    pub runtime_authority_observed: bool,
    pub executor_enablement_observed: bool,
    pub adapter_mutation_observed: bool,
    pub substrate_mechanism_added_observed: bool,
    pub mcp_tool_registration: bool,
    pub nexus_world_tick_touched: bool,
    pub aiot_runtime_called: bool,
    pub language_generation_observed: bool,
    pub cognition_claim_observed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleConsumerCheck {
    pub check: String,
    pub verdict: String,
    pub required: bool,
    pub evidence: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleReportPacket {
    pub schema: String,
    pub summary_schema: String,
    pub report_schema: String,
    pub input_schema: String,
    pub input_schema_version: Option<String>,
    pub input_mode: Option<String>,
    pub input_generated_by: Option<String>,
    pub input_source_commit: Option<String>,
    pub verdict: String,
    pub read_only_confirmed: bool,
    pub downstream_action: String,
    pub integration_decision: String,
    pub compose_criterion_positive_observed: bool,
    pub ablation_control_observed: bool,
    pub disclosed_caveats_present: bool,
    pub safety: BioCortexComposedLimitCycleConsumerSafety,
    pub summary: BioCortexComposedLimitCycleConsumerSummary,
    pub report_markdown: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleDisplayModel {
    pub schema: String,
    pub packet_schema: String,
    pub summary_schema: String,
    pub report_schema: String,
    pub title: String,
    pub status: BioCortexComposedLimitCycleDisplayStatus,
    pub safety: BioCortexComposedLimitCycleDisplaySafety,
    pub badges: Vec<BioCortexComposedLimitCycleDisplayBadge>,
    pub metrics: Vec<BioCortexComposedLimitCycleDisplayMetric>,
    pub failed_checks: Vec<BioCortexComposedLimitCycleDisplayFailedCheck>,
    pub guidance: Vec<String>,
    pub report_markdown: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleDisplayStatus {
    pub label: String,
    pub tone: String,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleDisplaySafety {
    pub display_ready: bool,
    pub read_only_confirmed: bool,
    pub static_artifact_only: bool,
    pub mutation_surface: String,
    pub memory_write_attempted: bool,
    pub retrieval_order_change_attempted: bool,
    pub runtime_authority_observed: bool,
    pub executor_enablement_observed: bool,
    pub adapter_mutation_observed: bool,
    pub substrate_mechanism_added_observed: bool,
    pub mcp_tool_registration: bool,
    pub nexus_world_tick_touched: bool,
    pub aiot_runtime_called: bool,
    pub language_generation_observed: bool,
    pub cognition_claim_observed: bool,
    pub allowed_surfaces: Vec<String>,
    pub forbidden_surfaces: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleDisplayBadge {
    pub label: String,
    pub value: String,
    pub tone: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleDisplayMetric {
    pub label: String,
    pub value: String,
    pub detail: String,
    pub tone: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexComposedLimitCycleDisplayFailedCheck {
    pub label: String,
    pub required: bool,
    pub evidence: String,
    pub tone: String,
}

pub fn consume_biocortex_composed_limit_cycle_ledger(
    ledger: &str,
) -> BioCortexComposedLimitCycleConsumerSummary {
    let (fields, parse_check) = parse_ledger(ledger);
    let mut checks = vec![parse_check];
    if !fields.is_empty() {
        checks.extend(REQUIRED_FIELDS.iter().map(|(field, expected, check_name)| {
            required_field_check(&fields, field, expected, check_name)
        }));
    }

    let accepted = checks.iter().all(|check| check.verdict == PASSED);
    let verdict = if accepted { "accepted" } else { "rejected" };
    let disclosed_caveats_present = caveat_checks_passed(&checks);

    BioCortexComposedLimitCycleConsumerSummary {
        schema: BIOCORTEX_COMPOSED_LIMIT_CYCLE_CONSUMER_SCHEMA.to_string(),
        input_schema: "biocortex.composed_limit_cycle_shadow_adapter.v4".to_string(),
        input_schema_version: fields.get("schema_version").cloned(),
        input_mode: fields.get("mode").cloned(),
        input_generated_by: fields.get("generated_by").cloned(),
        input_source_commit: fields.get("source_commit").cloned(),
        verdict: verdict.to_string(),
        read_only_confirmed: accepted,
        downstream_action: if accepted {
            "display_or_review_only"
        } else {
            "reject_static_ledger_artifact"
        }
        .to_string(),
        integration_decision: if accepted {
            "shadow_only_no_runtime_admission"
        } else {
            "blocked_by_static_ledger_validation"
        }
        .to_string(),
        compose_criterion_positive_observed: field_equals(
            &fields,
            "reframe_compose_criterion_positive",
            "true",
        ),
        ablation_control_observed: field_equals(&fields, "ablation_abolishes_the_cycle", "true"),
        disclosed_caveats_present,
        safety: BioCortexComposedLimitCycleConsumerSafety {
            static_artifact_only: true,
            memory_write_attempted: false,
            retrieval_order_change_attempted: false,
            runtime_authority_observed: false,
            executor_enablement_observed: false,
            adapter_mutation_observed: false,
            substrate_mechanism_added_observed: false,
            mcp_tool_registration: false,
            nexus_world_tick_touched: false,
            aiot_runtime_called: false,
            language_generation_observed: false,
            cognition_claim_observed: false,
        },
        checks,
        guidance: guidance_for(verdict),
    }
}

pub fn render_biocortex_composed_limit_cycle_review_artifact(
    summary: &BioCortexComposedLimitCycleConsumerSummary,
) -> String {
    let mut lines = Vec::new();
    let passed = summary
        .checks
        .iter()
        .filter(|check| check.verdict == PASSED)
        .count();
    let failed = summary
        .checks
        .iter()
        .filter(|check| check.verdict == FAILED)
        .count();
    let required_failed = summary
        .checks
        .iter()
        .filter(|check| check.required && check.verdict == FAILED)
        .count();

    lines.push("# BioCortex C1 Composed Limit-Cycle Review Artifact".to_string());
    lines.push(String::new());
    push_kv(
        &mut lines,
        "report_schema",
        BIOCORTEX_COMPOSED_LIMIT_CYCLE_REVIEW_ARTIFACT_SCHEMA,
    );
    push_kv(&mut lines, "summary_schema", &summary.schema);
    push_kv(&mut lines, "input_schema", &summary.input_schema);
    push_kv(
        &mut lines,
        "input_schema_version",
        optional_text(summary.input_schema_version.as_deref()),
    );
    push_kv(
        &mut lines,
        "input_mode",
        optional_text(summary.input_mode.as_deref()),
    );
    push_kv(
        &mut lines,
        "input_generated_by",
        optional_text(summary.input_generated_by.as_deref()),
    );
    push_kv(
        &mut lines,
        "input_source_commit",
        optional_text(summary.input_source_commit.as_deref()),
    );
    push_kv(&mut lines, "verdict", &summary.verdict);
    push_kv(
        &mut lines,
        "read_only_confirmed",
        bool_text(summary.read_only_confirmed),
    );
    push_kv(&mut lines, "downstream_action", &summary.downstream_action);
    push_kv(
        &mut lines,
        "integration_decision",
        &summary.integration_decision,
    );

    lines.push(String::new());
    lines.push("## C1 Observations".to_string());
    push_bullet_kv(
        &mut lines,
        "compose_criterion_positive_observed",
        bool_text(summary.compose_criterion_positive_observed),
    );
    push_bullet_kv(
        &mut lines,
        "ablation_control_observed",
        bool_text(summary.ablation_control_observed),
    );
    push_bullet_kv(
        &mut lines,
        "disclosed_caveats_present",
        bool_text(summary.disclosed_caveats_present),
    );

    lines.push(String::new());
    lines.push("## Safety".to_string());
    push_bullet_kv(
        &mut lines,
        "static_artifact_only",
        bool_text(summary.safety.static_artifact_only),
    );
    push_bullet_kv(
        &mut lines,
        "memory_write_attempted",
        bool_text(summary.safety.memory_write_attempted),
    );
    push_bullet_kv(
        &mut lines,
        "retrieval_order_change_attempted",
        bool_text(summary.safety.retrieval_order_change_attempted),
    );
    push_bullet_kv(
        &mut lines,
        "runtime_authority_observed",
        bool_text(summary.safety.runtime_authority_observed),
    );
    push_bullet_kv(
        &mut lines,
        "executor_enablement_observed",
        bool_text(summary.safety.executor_enablement_observed),
    );
    push_bullet_kv(
        &mut lines,
        "adapter_mutation_observed",
        bool_text(summary.safety.adapter_mutation_observed),
    );
    push_bullet_kv(
        &mut lines,
        "substrate_mechanism_added_observed",
        bool_text(summary.safety.substrate_mechanism_added_observed),
    );
    push_bullet_kv(
        &mut lines,
        "mcp_tool_registration",
        bool_text(summary.safety.mcp_tool_registration),
    );
    push_bullet_kv(
        &mut lines,
        "nexus_world_tick_touched",
        bool_text(summary.safety.nexus_world_tick_touched),
    );
    push_bullet_kv(
        &mut lines,
        "aiot_runtime_called",
        bool_text(summary.safety.aiot_runtime_called),
    );
    push_bullet_kv(
        &mut lines,
        "language_generation_observed",
        bool_text(summary.safety.language_generation_observed),
    );
    push_bullet_kv(
        &mut lines,
        "cognition_claim_observed",
        bool_text(summary.safety.cognition_claim_observed),
    );

    lines.push(String::new());
    lines.push("## Required Checks".to_string());
    push_bullet_kv(&mut lines, "passed", passed.to_string());
    push_bullet_kv(&mut lines, "failed", failed.to_string());
    push_bullet_kv(&mut lines, "required_failed", required_failed.to_string());

    lines.push(String::new());
    lines.push("## Failed Checks".to_string());
    let failed_checks = summary
        .checks
        .iter()
        .filter(|check| check.verdict == FAILED)
        .collect::<Vec<_>>();
    if failed_checks.is_empty() {
        lines.push("- none".to_string());
    } else {
        for check in failed_checks {
            lines.push(format!(
                "- {}: {}; required={}; evidence={}",
                one_line(&check.check),
                one_line(&check.verdict),
                bool_text(check.required),
                one_line(&check.evidence)
            ));
        }
    }

    lines.push(String::new());
    lines.push("## Guidance".to_string());
    push_string_list(&mut lines, &summary.guidance);

    lines.push(String::new());
    lines.push("## Boundary".to_string());
    lines.push("- This artifact is display/review only.".to_string());
    lines.push(
        "- It is not owner authorization, runtime admission, MCP tool registration, retrieval influence, memory mutation, language generation, or cognition evidence."
            .to_string(),
    );
    lines
        .push("- The C1 positive may only be shown with its disclosed caveats intact.".to_string());
    lines.push(
        "- A rejected artifact must not be surfaced as a valid BioCortex C1 capability summary."
            .to_string(),
    );

    format!("{}\n", lines.join("\n"))
}

pub fn build_biocortex_composed_limit_cycle_report_packet(
    summary: &BioCortexComposedLimitCycleConsumerSummary,
) -> BioCortexComposedLimitCycleReportPacket {
    BioCortexComposedLimitCycleReportPacket {
        schema: BIOCORTEX_COMPOSED_LIMIT_CYCLE_REPORT_PACKET_SCHEMA.to_string(),
        summary_schema: summary.schema.clone(),
        report_schema: BIOCORTEX_COMPOSED_LIMIT_CYCLE_REVIEW_ARTIFACT_SCHEMA.to_string(),
        input_schema: summary.input_schema.clone(),
        input_schema_version: summary.input_schema_version.clone(),
        input_mode: summary.input_mode.clone(),
        input_generated_by: summary.input_generated_by.clone(),
        input_source_commit: summary.input_source_commit.clone(),
        verdict: summary.verdict.clone(),
        read_only_confirmed: summary.read_only_confirmed,
        downstream_action: summary.downstream_action.clone(),
        integration_decision: summary.integration_decision.clone(),
        compose_criterion_positive_observed: summary.compose_criterion_positive_observed,
        ablation_control_observed: summary.ablation_control_observed,
        disclosed_caveats_present: summary.disclosed_caveats_present,
        safety: summary.safety.clone(),
        summary: summary.clone(),
        report_markdown: render_biocortex_composed_limit_cycle_review_artifact(summary),
    }
}

pub fn build_biocortex_composed_limit_cycle_display_model_from_packet(
    packet: &BioCortexComposedLimitCycleReportPacket,
) -> BioCortexComposedLimitCycleDisplayModel {
    let passed = check_count(packet, PASSED);
    let failed = check_count(packet, FAILED);
    let required_failed = required_failed_count(packet);
    let unsafe_surface = unsafe_display_surface_observed(&packet.safety);
    let read_only_display =
        packet.read_only_confirmed && packet.safety.static_artifact_only && !unsafe_surface;
    let display_ready = packet.verdict == "accepted"
        && read_only_display
        && display_only_decision(packet)
        && packet.compose_criterion_positive_observed
        && packet.ablation_control_observed
        && packet.disclosed_caveats_present
        && required_failed == 0;

    BioCortexComposedLimitCycleDisplayModel {
        schema: BIOCORTEX_COMPOSED_LIMIT_CYCLE_DISPLAY_MODEL_SCHEMA.to_string(),
        packet_schema: packet.schema.clone(),
        summary_schema: packet.summary_schema.clone(),
        report_schema: packet.report_schema.clone(),
        title: "BioCortex C1 Composed Limit Cycle".to_string(),
        status: display_status(display_ready),
        safety: display_safety(packet, display_ready, read_only_display),
        badges: vec![
            display_badge(
                "verdict",
                &packet.verdict,
                if display_ready { "success" } else { "danger" },
            ),
            display_badge(
                "read_only",
                bool_text(read_only_display),
                if read_only_display {
                    "success"
                } else {
                    "danger"
                },
            ),
            display_badge(
                "caveats",
                bool_text(packet.disclosed_caveats_present),
                if packet.disclosed_caveats_present {
                    "success"
                } else {
                    "danger"
                },
            ),
            display_badge(
                "downstream_action",
                &packet.downstream_action,
                if display_ready { "success" } else { "danger" },
            ),
            display_badge(
                "integration_decision",
                &packet.integration_decision,
                if display_ready { "success" } else { "danger" },
            ),
        ],
        metrics: vec![
            display_metric(
                "checks_passed",
                passed,
                "Consumer checks with passed verdict.",
                if failed == 0 { "success" } else { "warning" },
            ),
            display_metric(
                "checks_failed",
                failed,
                "Consumer checks with failed verdict.",
                if failed == 0 { "success" } else { "danger" },
            ),
            display_metric(
                "required_failed",
                required_failed,
                "Required consumer checks with failed verdict.",
                if required_failed == 0 {
                    "success"
                } else {
                    "danger"
                },
            ),
        ],
        failed_checks: packet
            .summary
            .checks
            .iter()
            .filter(|check| check.verdict == FAILED)
            .map(|check| BioCortexComposedLimitCycleDisplayFailedCheck {
                label: one_line(&check.check),
                required: check.required,
                evidence: one_line(&check.evidence),
                tone: if check.required { "danger" } else { "warning" }.to_string(),
            })
            .collect(),
        guidance: packet.summary.guidance.clone(),
        report_markdown: packet.report_markdown.clone(),
    }
}

fn parse_ledger(
    ledger: &str,
) -> (
    BTreeMap<String, String>,
    BioCortexComposedLimitCycleConsumerCheck,
) {
    let mut fields = BTreeMap::new();
    for (index, raw_line) in ledger.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            return (
                BTreeMap::new(),
                check(
                    "parse_key_value",
                    false,
                    true,
                    format!("line {} is not key=value: {line}", index + 1),
                ),
            );
        };
        if key.is_empty() {
            return (
                BTreeMap::new(),
                check(
                    "parse_key_value",
                    false,
                    true,
                    format!("line {} has an empty key", index + 1),
                ),
            );
        }
        if fields.insert(key.to_string(), value.to_string()).is_some() {
            return (
                BTreeMap::new(),
                check(
                    "parse_key_value",
                    false,
                    true,
                    format!("duplicate ledger key: {key}"),
                ),
            );
        }
    }

    let parsed_count = fields.len();
    (
        fields,
        check(
            "parse_key_value",
            parsed_count > 0,
            true,
            format!("parsed_fields={parsed_count}"),
        ),
    )
}

fn required_field_check(
    fields: &BTreeMap<String, String>,
    field: &str,
    expected: &str,
    check_name: &str,
) -> BioCortexComposedLimitCycleConsumerCheck {
    let actual = fields.get(field).map(String::as_str).unwrap_or("<missing>");
    check(
        check_name,
        actual == expected,
        true,
        format!("{field}={actual}, expected={expected}"),
    )
}

fn check(
    check: &str,
    ok: bool,
    required: bool,
    evidence: String,
) -> BioCortexComposedLimitCycleConsumerCheck {
    BioCortexComposedLimitCycleConsumerCheck {
        check: check.to_string(),
        verdict: if ok { PASSED } else { FAILED }.to_string(),
        required,
        evidence,
    }
}

fn caveat_checks_passed(checks: &[BioCortexComposedLimitCycleConsumerCheck]) -> bool {
    CAVEAT_CHECKS.iter().all(|name| {
        checks
            .iter()
            .any(|check| check.check == *name && check.verdict == PASSED)
    })
}

fn field_equals(fields: &BTreeMap<String, String>, field: &str, expected: &str) -> bool {
    fields.get(field).map(String::as_str) == Some(expected)
}

fn guidance_for(verdict: &str) -> Vec<String> {
    if verdict == "accepted" {
        vec![
            "C1 ledger may be displayed or attached to a human review packet with caveats intact."
                .to_string(),
            "Do not write Agent-Bridge memory or graph edges from this artifact.".to_string(),
            "Do not mutate retrieval order, register MCP tools, or enable runtime/shadow execution."
                .to_string(),
        ]
    } else {
        vec![
            "Reject the C1 ledger artifact and do not surface it as a valid BioCortex capability summary."
                .to_string(),
            "Keep runtime, retrieval, and memory surfaces untouched while investigating the failed check."
                .to_string(),
        ]
    }
}

fn display_status(display_ready: bool) -> BioCortexComposedLimitCycleDisplayStatus {
    if display_ready {
        BioCortexComposedLimitCycleDisplayStatus {
            label: "Ready for read-only display".to_string(),
            tone: "success".to_string(),
            detail:
                "Static C1 summary may be shown in reports, dashboards, forum posts, or handoff packets."
                    .to_string(),
        }
    } else {
        BioCortexComposedLimitCycleDisplayStatus {
            label: "Rejected".to_string(),
            tone: "danger".to_string(),
            detail:
                "Static C1 validation failed or unsafe affordances were observed; do not surface as a valid BioCortex capability summary."
                    .to_string(),
        }
    }
}

fn display_safety(
    packet: &BioCortexComposedLimitCycleReportPacket,
    display_ready: bool,
    read_only_display: bool,
) -> BioCortexComposedLimitCycleDisplaySafety {
    let safety = &packet.safety;
    BioCortexComposedLimitCycleDisplaySafety {
        display_ready,
        read_only_confirmed: read_only_display,
        static_artifact_only: safety.static_artifact_only,
        mutation_surface: if unsafe_display_surface_observed(safety) {
            "unsafe_affordance_observed"
        } else {
            "none"
        }
        .to_string(),
        memory_write_attempted: safety.memory_write_attempted,
        retrieval_order_change_attempted: safety.retrieval_order_change_attempted,
        runtime_authority_observed: safety.runtime_authority_observed,
        executor_enablement_observed: safety.executor_enablement_observed,
        adapter_mutation_observed: safety.adapter_mutation_observed,
        substrate_mechanism_added_observed: safety.substrate_mechanism_added_observed,
        mcp_tool_registration: safety.mcp_tool_registration,
        nexus_world_tick_touched: safety.nexus_world_tick_touched,
        aiot_runtime_called: safety.aiot_runtime_called,
        language_generation_observed: safety.language_generation_observed,
        cognition_claim_observed: safety.cognition_claim_observed,
        allowed_surfaces: vec![
            "forum_post_body".to_string(),
            "report_markdown".to_string(),
            "dashboard_card".to_string(),
            "handoff_packet".to_string(),
        ],
        forbidden_surfaces: vec![
            "memory_write".to_string(),
            "graph_edge_mutation".to_string(),
            "retrieval_order_change".to_string(),
            "mcp_tool_registration".to_string(),
            "runtime_admission".to_string(),
            "executor_enablement".to_string(),
            "adapter_mutation".to_string(),
            "substrate_mechanism_addition".to_string(),
            "nexus_world_tick".to_string(),
            "aiot_runtime_call".to_string(),
            "language_generation".to_string(),
            "cognition_claim".to_string(),
            "caveat_dropping".to_string(),
        ],
    }
}

fn check_count(packet: &BioCortexComposedLimitCycleReportPacket, verdict: &str) -> usize {
    packet
        .summary
        .checks
        .iter()
        .filter(|check| check.verdict == verdict)
        .count()
}

fn required_failed_count(packet: &BioCortexComposedLimitCycleReportPacket) -> usize {
    packet
        .summary
        .checks
        .iter()
        .filter(|check| check.required && check.verdict == FAILED)
        .count()
}

fn unsafe_display_surface_observed(safety: &BioCortexComposedLimitCycleConsumerSafety) -> bool {
    safety.memory_write_attempted
        || safety.retrieval_order_change_attempted
        || safety.runtime_authority_observed
        || safety.executor_enablement_observed
        || safety.adapter_mutation_observed
        || safety.substrate_mechanism_added_observed
        || safety.mcp_tool_registration
        || safety.nexus_world_tick_touched
        || safety.aiot_runtime_called
        || safety.language_generation_observed
        || safety.cognition_claim_observed
        || !safety.static_artifact_only
}

fn display_only_decision(packet: &BioCortexComposedLimitCycleReportPacket) -> bool {
    packet.downstream_action == "display_or_review_only"
        && packet.integration_decision == "shadow_only_no_runtime_admission"
}

fn display_badge(
    label: impl Into<String>,
    value: impl Into<String>,
    tone: impl Into<String>,
) -> BioCortexComposedLimitCycleDisplayBadge {
    BioCortexComposedLimitCycleDisplayBadge {
        label: label.into(),
        value: value.into(),
        tone: tone.into(),
    }
}

fn display_metric(
    label: impl Into<String>,
    value: usize,
    detail: impl Into<String>,
    tone: impl Into<String>,
) -> BioCortexComposedLimitCycleDisplayMetric {
    BioCortexComposedLimitCycleDisplayMetric {
        label: label.into(),
        value: value.to_string(),
        detail: detail.into(),
        tone: tone.into(),
    }
}

fn push_kv(lines: &mut Vec<String>, key: &str, value: impl AsRef<str>) {
    lines.push(format!("{key}: {}", one_line(value.as_ref())));
}

fn push_bullet_kv(lines: &mut Vec<String>, key: &str, value: impl AsRef<str>) {
    lines.push(format!("- {key}: {}", one_line(value.as_ref())));
}

fn push_string_list(lines: &mut Vec<String>, values: &[String]) {
    if values.is_empty() {
        lines.push("- none".to_string());
        return;
    }

    for value in values {
        lines.push(format!("- {}", one_line(value)));
    }
}

fn bool_text(value: bool) -> &'static str {
    if value {
        "true"
    } else {
        "false"
    }
}

fn optional_text(value: Option<&str>) -> &str {
    value.unwrap_or("none")
}

fn one_line(value: &str) -> String {
    value.split_whitespace().collect::<Vec<_>>().join(" ")
}
