//! Static BioCortex capability-ledger consumer dry-run.
//!
//! This module parses a precomputed BioCortex schema-v3 capability ledger as an
//! inert artifact. It deliberately does not call BioCortex, Agent-Bridge memory,
//! retrieval, MCP registration, Nexus, AiOT, network APIs, or runtime/executor
//! paths.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const BIOCORTEX_CAPABILITY_LEDGER_CONSUMER_SCHEMA: &str =
    "agent_bridge.biocortex_capability_ledger.consumer_dry_run.v0";
pub const BIOCORTEX_CAPABILITY_LEDGER_REVIEW_ARTIFACT_SCHEMA: &str =
    "agent_bridge.biocortex_capability_ledger.review_artifact.v0";
pub const BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_capability_ledger.report_packet.v0";
pub const BIOCORTEX_CAPABILITY_LEDGER_DISPLAY_MODEL_SCHEMA: &str =
    "agent_bridge.biocortex_capability_ledger.display_model.v0";

const PASSED: &str = "passed";
const FAILED: &str = "failed";

const REQUIRED_FIELDS: &[(&str, &str, &str)] = &[
    ("schema_version", "3", "schema_version"),
    (
        "generated_by",
        "capability_ledger_shadow_adapter",
        "producer_identity",
    ),
    ("mode", "read_only_shadow", "shadow_mode"),
    (
        "source_kind_scaled_morphology_benchmark",
        "executable_report",
        "source_scaled_morphology",
    ),
    (
        "source_kind_temporal_credit_window",
        "executable_report",
        "source_temporal_credit",
    ),
    (
        "source_kind_scale_capstone",
        "executable_report",
        "source_scale_capstone",
    ),
    (
        "source_kind_retrieval_engine",
        "executable_report",
        "source_retrieval_engine",
    ),
    (
        "source_kind_g_next_verdict",
        "prose_verdict",
        "source_g_next_boundary",
    ),
    (
        "source_kind_scale_axis_verdict",
        "prose_verdict",
        "source_scale_axis_boundary",
    ),
    (
        "regional_scale_positive",
        "true",
        "capability_regional_scale",
    ),
    (
        "retrieval_projection_positive_read_only",
        "true",
        "capability_retrieval_projection_read_only",
    ),
    (
        "capacity_scales_with_size",
        "true",
        "capability_capacity_scales_with_size",
    ),
    (
        "scale_new_function_emergence",
        "false",
        "boundary_no_new_function_emergence",
    ),
    (
        "valence_is_supplied_world_interface",
        "true",
        "boundary_valence_supplied",
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
];

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerConsumerSummary {
    pub schema: String,
    pub input_schema: String,
    pub input_schema_version: Option<String>,
    pub input_mode: Option<String>,
    pub input_generated_by: Option<String>,
    pub verdict: String,
    pub read_only_confirmed: bool,
    pub downstream_action: String,
    pub integration_decision: String,
    pub safety: BioCortexCapabilityLedgerConsumerSafety,
    pub checks: Vec<BioCortexCapabilityLedgerConsumerCheck>,
    pub guidance: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerConsumerSafety {
    pub static_artifact_only: bool,
    pub memory_write_attempted: bool,
    pub retrieval_order_change_attempted: bool,
    pub runtime_authority_observed: bool,
    pub executor_enablement_observed: bool,
    pub mcp_tool_registration: bool,
    pub nexus_world_tick_touched: bool,
    pub aiot_runtime_called: bool,
    pub language_generation_observed: bool,
    pub cognition_claim_observed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerConsumerCheck {
    pub check: String,
    pub verdict: String,
    pub required: bool,
    pub evidence: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerReportPacket {
    pub schema: String,
    pub summary_schema: String,
    pub report_schema: String,
    pub input_schema: String,
    pub input_schema_version: Option<String>,
    pub input_mode: Option<String>,
    pub input_generated_by: Option<String>,
    pub verdict: String,
    pub read_only_confirmed: bool,
    pub downstream_action: String,
    pub integration_decision: String,
    pub safety: BioCortexCapabilityLedgerConsumerSafety,
    pub summary: BioCortexCapabilityLedgerConsumerSummary,
    pub report_markdown: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerDisplayModel {
    pub schema: String,
    pub packet_schema: String,
    pub summary_schema: String,
    pub report_schema: String,
    pub title: String,
    pub status: BioCortexCapabilityLedgerDisplayStatus,
    pub safety: BioCortexCapabilityLedgerDisplaySafety,
    pub badges: Vec<BioCortexCapabilityLedgerDisplayBadge>,
    pub metrics: Vec<BioCortexCapabilityLedgerDisplayMetric>,
    pub failed_checks: Vec<BioCortexCapabilityLedgerDisplayFailedCheck>,
    pub guidance: Vec<String>,
    pub report_markdown: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerDisplayStatus {
    pub label: String,
    pub tone: String,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerDisplaySafety {
    pub display_ready: bool,
    pub read_only_confirmed: bool,
    pub static_artifact_only: bool,
    pub mutation_surface: String,
    pub memory_write_attempted: bool,
    pub retrieval_order_change_attempted: bool,
    pub runtime_authority_observed: bool,
    pub executor_enablement_observed: bool,
    pub mcp_tool_registration: bool,
    pub nexus_world_tick_touched: bool,
    pub aiot_runtime_called: bool,
    pub language_generation_observed: bool,
    pub cognition_claim_observed: bool,
    pub allowed_surfaces: Vec<String>,
    pub forbidden_surfaces: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerDisplayBadge {
    pub label: String,
    pub value: String,
    pub tone: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerDisplayMetric {
    pub label: String,
    pub value: String,
    pub detail: String,
    pub tone: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerDisplayFailedCheck {
    pub label: String,
    pub required: bool,
    pub evidence: String,
    pub tone: String,
}

pub fn consume_biocortex_capability_ledger(
    ledger: &str,
) -> BioCortexCapabilityLedgerConsumerSummary {
    let (fields, parse_check) = parse_ledger(ledger);
    let mut checks = vec![parse_check];
    if !fields.is_empty() {
        checks.extend(REQUIRED_FIELDS.iter().map(|(field, expected, check_name)| {
            required_field_check(&fields, field, expected, check_name)
        }));
    }

    let accepted = checks.iter().all(|check| check.verdict == PASSED);
    let verdict = if accepted { "accepted" } else { "rejected" };

    BioCortexCapabilityLedgerConsumerSummary {
        schema: BIOCORTEX_CAPABILITY_LEDGER_CONSUMER_SCHEMA.to_string(),
        input_schema: "biocortex.capability_ledger.v3".to_string(),
        input_schema_version: fields.get("schema_version").cloned(),
        input_mode: fields.get("mode").cloned(),
        input_generated_by: fields.get("generated_by").cloned(),
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
        safety: BioCortexCapabilityLedgerConsumerSafety {
            static_artifact_only: true,
            memory_write_attempted: false,
            retrieval_order_change_attempted: false,
            runtime_authority_observed: false,
            executor_enablement_observed: false,
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

fn parse_ledger(
    ledger: &str,
) -> (
    BTreeMap<String, String>,
    BioCortexCapabilityLedgerConsumerCheck,
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
) -> BioCortexCapabilityLedgerConsumerCheck {
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
) -> BioCortexCapabilityLedgerConsumerCheck {
    BioCortexCapabilityLedgerConsumerCheck {
        check: check.to_string(),
        verdict: if ok { PASSED } else { FAILED }.to_string(),
        required,
        evidence,
    }
}

fn guidance_for(verdict: &str) -> Vec<String> {
    if verdict == "accepted" {
        vec![
            "Ledger may be displayed or attached to a human review packet.".to_string(),
            "Do not write Agent-Bridge memory or graph edges from this artifact.".to_string(),
            "Do not mutate retrieval order, register MCP tools, or enable runtime/shadow execution."
                .to_string(),
        ]
    } else {
        vec![
            "Reject the ledger artifact and do not surface it as a valid BioCortex capability summary."
                .to_string(),
            "Keep runtime, retrieval, and memory surfaces untouched while investigating the failed check."
                .to_string(),
        ]
    }
}

pub fn render_biocortex_capability_ledger_review_artifact(
    summary: &BioCortexCapabilityLedgerConsumerSummary,
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

    lines.push("# BioCortex Capability Ledger Review Artifact".to_string());
    lines.push(String::new());
    push_kv(
        &mut lines,
        "report_schema",
        BIOCORTEX_CAPABILITY_LEDGER_REVIEW_ARTIFACT_SCHEMA,
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
    lines.push(
        "- A rejected artifact must not be surfaced as a valid BioCortex capability summary."
            .to_string(),
    );

    format!("{}\n", lines.join("\n"))
}

pub fn build_biocortex_capability_ledger_report_packet(
    summary: &BioCortexCapabilityLedgerConsumerSummary,
) -> BioCortexCapabilityLedgerReportPacket {
    BioCortexCapabilityLedgerReportPacket {
        schema: BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA.to_string(),
        summary_schema: summary.schema.clone(),
        report_schema: BIOCORTEX_CAPABILITY_LEDGER_REVIEW_ARTIFACT_SCHEMA.to_string(),
        input_schema: summary.input_schema.clone(),
        input_schema_version: summary.input_schema_version.clone(),
        input_mode: summary.input_mode.clone(),
        input_generated_by: summary.input_generated_by.clone(),
        verdict: summary.verdict.clone(),
        read_only_confirmed: summary.read_only_confirmed,
        downstream_action: summary.downstream_action.clone(),
        integration_decision: summary.integration_decision.clone(),
        safety: summary.safety.clone(),
        summary: summary.clone(),
        report_markdown: render_biocortex_capability_ledger_review_artifact(summary),
    }
}

pub fn build_biocortex_capability_ledger_display_model_from_packet(
    packet: &BioCortexCapabilityLedgerReportPacket,
) -> BioCortexCapabilityLedgerDisplayModel {
    let passed = check_count(packet, PASSED);
    let failed = check_count(packet, FAILED);
    let required_failed = required_failed_count(packet);
    let unsafe_surface = unsafe_display_surface_observed(&packet.safety);
    let read_only_display =
        packet.read_only_confirmed && packet.safety.static_artifact_only && !unsafe_surface;
    let display_ready = packet.verdict == "accepted" && read_only_display && required_failed == 0;

    BioCortexCapabilityLedgerDisplayModel {
        schema: BIOCORTEX_CAPABILITY_LEDGER_DISPLAY_MODEL_SCHEMA.to_string(),
        packet_schema: packet.schema.clone(),
        summary_schema: packet.summary_schema.clone(),
        report_schema: packet.report_schema.clone(),
        title: "BioCortex Capability Ledger".to_string(),
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
            .map(|check| BioCortexCapabilityLedgerDisplayFailedCheck {
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

fn display_status(display_ready: bool) -> BioCortexCapabilityLedgerDisplayStatus {
    if display_ready {
        BioCortexCapabilityLedgerDisplayStatus {
            label: "Ready for read-only display".to_string(),
            tone: "success".to_string(),
            detail:
                "Static ledger summary may be shown in reports, dashboards, forum posts, or handoff packets."
                    .to_string(),
        }
    } else {
        BioCortexCapabilityLedgerDisplayStatus {
            label: "Rejected".to_string(),
            tone: "danger".to_string(),
            detail:
                "Static ledger validation failed or unsafe affordances were observed; do not surface as a valid BioCortex capability summary."
                    .to_string(),
        }
    }
}

fn display_safety(
    packet: &BioCortexCapabilityLedgerReportPacket,
    display_ready: bool,
    read_only_display: bool,
) -> BioCortexCapabilityLedgerDisplaySafety {
    let safety = &packet.safety;
    BioCortexCapabilityLedgerDisplaySafety {
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
            "nexus_world_tick".to_string(),
            "aiot_runtime_call".to_string(),
            "language_generation".to_string(),
            "cognition_claim".to_string(),
        ],
    }
}

fn check_count(packet: &BioCortexCapabilityLedgerReportPacket, verdict: &str) -> usize {
    packet
        .summary
        .checks
        .iter()
        .filter(|check| check.verdict == verdict)
        .count()
}

fn required_failed_count(packet: &BioCortexCapabilityLedgerReportPacket) -> usize {
    packet
        .summary
        .checks
        .iter()
        .filter(|check| check.required && check.verdict == FAILED)
        .count()
}

fn unsafe_display_surface_observed(safety: &BioCortexCapabilityLedgerConsumerSafety) -> bool {
    safety.memory_write_attempted
        || safety.retrieval_order_change_attempted
        || safety.runtime_authority_observed
        || safety.executor_enablement_observed
        || safety.mcp_tool_registration
        || safety.nexus_world_tick_touched
        || safety.aiot_runtime_called
        || safety.language_generation_observed
        || safety.cognition_claim_observed
        || !safety.static_artifact_only
}

fn display_badge(
    label: impl Into<String>,
    value: impl Into<String>,
    tone: impl Into<String>,
) -> BioCortexCapabilityLedgerDisplayBadge {
    BioCortexCapabilityLedgerDisplayBadge {
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
) -> BioCortexCapabilityLedgerDisplayMetric {
    BioCortexCapabilityLedgerDisplayMetric {
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
