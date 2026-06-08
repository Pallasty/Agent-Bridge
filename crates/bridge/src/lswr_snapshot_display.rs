use crate::lswr_snapshot_consumer::{
    ConsumerFeedback, ConsumerRollback, ConsumerVerification, ReadOnlyBridgeConsumerSummary,
};
use crate::lswr_snapshot_report_acceptance::{
    ReadOnlyBridgeAcceptanceGate, ReadOnlyBridgeAcceptanceMatrix,
    build_readonly_bridge_acceptance_matrix,
};
use crate::lswr_snapshot_report_packet::ReadOnlyBridgeReportPacket;
use serde::{Deserialize, Serialize};

pub const LSWR_READONLY_BRIDGE_DISPLAY_MODEL_SCHEMA: &str =
    "agent_bridge.lswr.readonly_bridge_display_model.v0";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeDisplayModel {
    pub schema: String,
    pub packet_schema: String,
    pub acceptance_schema: String,
    pub snapshot_sha256: String,
    pub title: String,
    pub status: DisplayStatus,
    pub safety: DisplaySafety,
    pub badges: Vec<DisplayBadge>,
    pub metrics: Vec<DisplayMetric>,
    pub gate_rows: Vec<DisplayGateRow>,
    pub readback_groups: Vec<DisplayReadbackGroup>,
    pub guidance: Vec<String>,
    pub report_markdown: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisplayStatus {
    pub label: String,
    pub tone: String,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisplaySafety {
    pub wrapper_ready: bool,
    pub matrix_consistent_with_packet: bool,
    pub read_only: bool,
    pub mutation_surface: String,
    pub mcp_tool_registration: bool,
    pub affordances: Vec<DisplayBadge>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisplayBadge {
    pub label: String,
    pub value: String,
    pub tone: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisplayMetric {
    pub label: String,
    pub value: String,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisplayGateRow {
    pub label: String,
    pub verdict: String,
    pub tone: String,
    pub required_for_wrapper: bool,
    pub evidence: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisplayReadbackGroup {
    pub label: String,
    pub count: usize,
    pub tone: String,
    pub items: Vec<DisplayReadbackItem>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DisplayReadbackItem {
    pub label: String,
    pub detail: String,
    pub tone: String,
}

pub fn build_readonly_bridge_display_model_from_packet(
    packet: &ReadOnlyBridgeReportPacket,
) -> ReadOnlyBridgeDisplayModel {
    let matrix = build_readonly_bridge_acceptance_matrix(packet);
    build_readonly_bridge_display_model(packet, &matrix)
}

pub fn build_readonly_bridge_display_model(
    packet: &ReadOnlyBridgeReportPacket,
    matrix: &ReadOnlyBridgeAcceptanceMatrix,
) -> ReadOnlyBridgeDisplayModel {
    let matrix_consistent_with_packet =
        matrix.packet_schema == packet.schema && matrix.snapshot_sha256 == packet.snapshot_sha256;
    let wrapper_ready = matrix_consistent_with_packet
        && matrix.overall_verdict == "accepted"
        && packet.read_only_confirmed;

    ReadOnlyBridgeDisplayModel {
        schema: LSWR_READONLY_BRIDGE_DISPLAY_MODEL_SCHEMA.to_string(),
        packet_schema: packet.schema.clone(),
        acceptance_schema: matrix.schema.clone(),
        snapshot_sha256: packet.snapshot_sha256.clone(),
        title: "LSWR Read-Only Bridge".to_string(),
        status: display_status(&matrix.overall_verdict, matrix_consistent_with_packet),
        safety: display_safety(packet, wrapper_ready, matrix_consistent_with_packet),
        badges: display_badges(packet, matrix, wrapper_ready, matrix_consistent_with_packet),
        metrics: display_metrics(&packet.summary),
        gate_rows: matrix.gates.iter().map(display_gate_row).collect(),
        readback_groups: display_readback_groups(&packet.summary),
        guidance: matrix.guidance.clone(),
        report_markdown: packet.report_markdown.clone(),
    }
}

fn display_status(overall_verdict: &str, matrix_consistent_with_packet: bool) -> DisplayStatus {
    if !matrix_consistent_with_packet {
        return DisplayStatus {
            label: "Rejected".to_string(),
            tone: "danger".to_string(),
            detail: "Acceptance matrix does not match the report packet.".to_string(),
        };
    }

    match overall_verdict {
        "accepted" => DisplayStatus {
            label: "Ready for read-only display".to_string(),
            tone: "success".to_string(),
            detail: "All wrapper-required gates passed.".to_string(),
        },
        "needs_review" => DisplayStatus {
            label: "Needs review".to_string(),
            tone: "warning".to_string(),
            detail: "The packet is read-only, but one or more non-required gates need review."
                .to_string(),
        },
        _ => DisplayStatus {
            label: "Rejected".to_string(),
            tone: "danger".to_string(),
            detail: "One or more wrapper-required gates failed.".to_string(),
        },
    }
}

fn display_safety(
    packet: &ReadOnlyBridgeReportPacket,
    wrapper_ready: bool,
    matrix_consistent_with_packet: bool,
) -> DisplaySafety {
    let safety = &packet.safety;
    DisplaySafety {
        wrapper_ready,
        matrix_consistent_with_packet,
        read_only: safety.read_only,
        mutation_surface: safety.mutation_surface.clone(),
        mcp_tool_registration: safety.mcp_tool_registration,
        affordances: vec![
            affordance_badge("snapshot", safety.snapshot),
            affordance_badge("query", safety.query),
            affordance_badge("patch", safety.patch),
            affordance_badge("action", safety.action),
            affordance_badge("invoke", safety.invoke),
        ],
    }
}

fn display_badges(
    packet: &ReadOnlyBridgeReportPacket,
    matrix: &ReadOnlyBridgeAcceptanceMatrix,
    wrapper_ready: bool,
    matrix_consistent_with_packet: bool,
) -> Vec<DisplayBadge> {
    vec![
        badge(
            "overall",
            &matrix.overall_verdict,
            tone_for_overall(&matrix.overall_verdict),
        ),
        badge(
            "wrapper_ready",
            bool_text(wrapper_ready),
            if wrapper_ready { "success" } else { "danger" },
        ),
        badge(
            "matrix_match",
            bool_text(matrix_consistent_with_packet),
            if matrix_consistent_with_packet {
                "success"
            } else {
                "danger"
            },
        ),
        badge(
            "readback",
            &packet.readback_mode,
            if packet.readback_mode == "detailed_snapshot" {
                "success"
            } else {
                "warning"
            },
        ),
        badge(
            "read_only",
            bool_text(packet.read_only_confirmed),
            if packet.read_only_confirmed {
                "success"
            } else {
                "danger"
            },
        ),
        badge(
            "gates",
            &format!("{}/{}", passed_gate_count(matrix), matrix.gates.len()),
            if matrix.gates.iter().all(|gate| gate.verdict == "passed") {
                "success"
            } else {
                "warning"
            },
        ),
    ]
}

fn display_metrics(summary: &ReadOnlyBridgeConsumerSummary) -> Vec<DisplayMetric> {
    vec![
        metric("actions", summary.counts.actions, "ledger actions"),
        metric("events", summary.counts.events, "ledger events"),
        metric(
            "verifications",
            summary.counts.verifications,
            "verification records",
        ),
        metric(
            "feedback",
            summary.counts.feedback,
            "human feedback records",
        ),
        metric(
            "rollback_records",
            summary.counts.rollback_records,
            "rollback records",
        ),
        metric_option(
            "verified",
            summary.outcome_counts.verified,
            "verified outcomes",
        ),
        metric_option(
            "not_verified",
            summary.outcome_counts.not_verified,
            "not-verified outcomes",
        ),
        metric_option(
            "blocked",
            summary.outcome_counts.blocked,
            "blocked outcomes",
        ),
    ]
}

fn display_gate_row(gate: &ReadOnlyBridgeAcceptanceGate) -> DisplayGateRow {
    DisplayGateRow {
        label: gate.gate.clone(),
        verdict: gate.verdict.clone(),
        tone: tone_for_gate(&gate.verdict).to_string(),
        required_for_wrapper: gate.required_for_wrapper,
        evidence: gate.evidence.clone(),
    }
}

fn display_readback_groups(summary: &ReadOnlyBridgeConsumerSummary) -> Vec<DisplayReadbackGroup> {
    vec![
        readback_group(
            "verified",
            "success",
            summary.verified.iter().map(verification_item).collect(),
        ),
        readback_group(
            "not_verified",
            "warning",
            summary.not_verified.iter().map(verification_item).collect(),
        ),
        readback_group(
            "blocked",
            "danger",
            summary.blocked.iter().map(verification_item).collect(),
        ),
        readback_group(
            "feedback",
            "neutral",
            summary.feedback.iter().map(feedback_item).collect(),
        ),
        readback_group(
            "rollbacks",
            "neutral",
            summary.rollbacks.iter().map(rollback_item).collect(),
        ),
    ]
}

fn verification_item(verification: &ConsumerVerification) -> DisplayReadbackItem {
    DisplayReadbackItem {
        label: verification
            .action_id
            .clone()
            .unwrap_or_else(|| "unknown action".to_string()),
        detail: format!(
            "{} via {}/{}: {}",
            verification.verdict,
            verification.evidence_adapter,
            verification.evidence_method,
            verification.evidence_summary
        ),
        tone: tone_for_verdict(&verification.verdict).to_string(),
    }
}

fn feedback_item(feedback: &ConsumerFeedback) -> DisplayReadbackItem {
    DisplayReadbackItem {
        label: feedback.feedback_id.clone(),
        detail: format!(
            "decision={}, changes_world_verdict={}",
            feedback
                .decision
                .clone()
                .unwrap_or_else(|| "unknown".to_string()),
            bool_text(feedback.changes_world_verdict)
        ),
        tone: if feedback.changes_world_verdict {
            "warning".to_string()
        } else {
            "neutral".to_string()
        },
    }
}

fn rollback_item(rollback: &ConsumerRollback) -> DisplayReadbackItem {
    DisplayReadbackItem {
        label: rollback.rollback_group.clone(),
        detail: format!(
            "actions={}, verification_event_id={}",
            join_or_none(&rollback.actions),
            rollback
                .verification_event_id
                .clone()
                .unwrap_or_else(|| "unknown".to_string())
        ),
        tone: "neutral".to_string(),
    }
}

fn readback_group(
    label: impl Into<String>,
    tone: impl Into<String>,
    items: Vec<DisplayReadbackItem>,
) -> DisplayReadbackGroup {
    DisplayReadbackGroup {
        label: label.into(),
        count: items.len(),
        tone: tone.into(),
        items,
    }
}

fn affordance_badge(label: &str, enabled: bool) -> DisplayBadge {
    let safe_enabled = matches!(label, "snapshot" | "query");
    badge(
        label,
        bool_text(enabled),
        if enabled == safe_enabled {
            "success"
        } else {
            "danger"
        },
    )
}

fn badge(
    label: impl Into<String>,
    value: impl Into<String>,
    tone: impl Into<String>,
) -> DisplayBadge {
    DisplayBadge {
        label: label.into(),
        value: value.into(),
        tone: tone.into(),
    }
}

fn metric(label: &str, value: usize, detail: &str) -> DisplayMetric {
    DisplayMetric {
        label: label.to_string(),
        value: value.to_string(),
        detail: detail.to_string(),
    }
}

fn metric_option(label: &str, value: Option<usize>, detail: &str) -> DisplayMetric {
    DisplayMetric {
        label: label.to_string(),
        value: value
            .map(|value| value.to_string())
            .unwrap_or_else(|| "unknown".to_string()),
        detail: detail.to_string(),
    }
}

fn passed_gate_count(matrix: &ReadOnlyBridgeAcceptanceMatrix) -> usize {
    matrix
        .gates
        .iter()
        .filter(|gate| gate.verdict == "passed")
        .count()
}

fn tone_for_overall(overall_verdict: &str) -> &'static str {
    match overall_verdict {
        "accepted" => "success",
        "needs_review" => "warning",
        _ => "danger",
    }
}

fn tone_for_gate(verdict: &str) -> &'static str {
    match verdict {
        "passed" => "success",
        "warning" => "warning",
        _ => "danger",
    }
}

fn tone_for_verdict(verdict: &str) -> &'static str {
    match verdict {
        "verified" => "success",
        "not_verified" => "warning",
        "blocked" => "danger",
        _ => "neutral",
    }
}

fn bool_text(value: bool) -> &'static str {
    if value { "true" } else { "false" }
}

fn join_or_none(values: &[String]) -> String {
    if values.is_empty() {
        "none".to_string()
    } else {
        values.join(",")
    }
}
