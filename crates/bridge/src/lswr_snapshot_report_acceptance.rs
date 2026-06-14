use crate::lswr_snapshot_consumer::LSWR_READONLY_BRIDGE_CONSUMER_SUMMARY_SCHEMA;
use crate::lswr_snapshot_report::{
    render_readonly_bridge_report, LSWR_READONLY_BRIDGE_REPORT_SCHEMA,
};
use crate::lswr_snapshot_report_packet::{
    ReadOnlyBridgeReportPacket, LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA,
};
use serde::{Deserialize, Serialize};

pub const LSWR_READONLY_BRIDGE_ACCEPTANCE_MATRIX_SCHEMA: &str =
    "agent_bridge.lswr.readonly_bridge_acceptance_matrix.v0";

const PASSED: &str = "passed";
const WARNING: &str = "warning";
const FAILED: &str = "failed";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeAcceptanceMatrix {
    pub schema: String,
    pub packet_schema: String,
    pub snapshot_sha256: String,
    pub overall_verdict: String,
    pub gates: Vec<ReadOnlyBridgeAcceptanceGate>,
    pub guidance: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeAcceptanceGate {
    pub gate: String,
    pub verdict: String,
    pub required_for_wrapper: bool,
    pub evidence: String,
}

pub fn build_readonly_bridge_acceptance_matrix(
    packet: &ReadOnlyBridgeReportPacket,
) -> ReadOnlyBridgeAcceptanceMatrix {
    let gates = vec![
        schema_chain_gate(packet),
        packet_summary_consistency_gate(packet),
        read_only_safety_gate(packet),
        query_surface_gate(packet),
        report_markdown_gate(packet),
        detailed_readback_gate(packet),
        feedback_separation_gate(packet),
    ];
    let overall_verdict = overall_verdict(&gates);

    ReadOnlyBridgeAcceptanceMatrix {
        schema: LSWR_READONLY_BRIDGE_ACCEPTANCE_MATRIX_SCHEMA.to_string(),
        packet_schema: packet.schema.clone(),
        snapshot_sha256: packet.snapshot_sha256.clone(),
        overall_verdict: overall_verdict.clone(),
        gates,
        guidance: guidance_for(&overall_verdict),
    }
}

fn schema_chain_gate(packet: &ReadOnlyBridgeReportPacket) -> ReadOnlyBridgeAcceptanceGate {
    let ok = packet.schema == LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA
        && packet.summary_schema == LSWR_READONLY_BRIDGE_CONSUMER_SUMMARY_SCHEMA
        && packet.summary.schema == LSWR_READONLY_BRIDGE_CONSUMER_SUMMARY_SCHEMA
        && packet.report_schema == LSWR_READONLY_BRIDGE_REPORT_SCHEMA
        && packet.projection_schema == packet.summary.projection_schema
        && packet.snapshot_sha256 == packet.summary.snapshot_sha256;

    gate(
        "schema_chain",
        verdict(ok),
        true,
        format!(
            "packet={}, summary={}, report={}, projection_match={}, snapshot_hash_match={}",
            packet.schema,
            packet.summary.schema,
            packet.report_schema,
            bool_text(packet.projection_schema == packet.summary.projection_schema),
            bool_text(packet.snapshot_sha256 == packet.summary.snapshot_sha256),
        ),
    )
}

fn packet_summary_consistency_gate(
    packet: &ReadOnlyBridgeReportPacket,
) -> ReadOnlyBridgeAcceptanceGate {
    let ok = packet.summary_schema == packet.summary.schema
        && packet.projection_schema == packet.summary.projection_schema
        && packet.snapshot_sha256 == packet.summary.snapshot_sha256
        && packet.readback_mode == packet.summary.readback_mode
        && packet.read_only_confirmed == packet.summary.read_only_confirmed
        && packet.safety == packet.summary.safety;

    gate(
        "packet_summary_consistency",
        verdict(ok),
        true,
        format!(
            "readback_mode={}, top_level_matches_summary={}",
            packet.readback_mode,
            bool_text(ok)
        ),
    )
}

fn read_only_safety_gate(packet: &ReadOnlyBridgeReportPacket) -> ReadOnlyBridgeAcceptanceGate {
    let safety = &packet.safety;
    let ok = packet.read_only_confirmed
        && packet.summary.read_only_confirmed
        && safety == &packet.summary.safety
        && safety.read_only
        && safety.mutation_surface == "none"
        && !safety.mcp_tool_registration
        && safety.snapshot
        && safety.query
        && !safety.patch
        && !safety.action
        && !safety.invoke;

    gate(
        "read_only_safety",
        verdict(ok),
        true,
        format!(
            "read_only={}, mutation_surface={}, mcp_tool_registration={}, affordances=snapshot:{},query:{},patch:{},action:{},invoke:{}",
            bool_text(safety.read_only),
            safety.mutation_surface,
            bool_text(safety.mcp_tool_registration),
            bool_text(safety.snapshot),
            bool_text(safety.query),
            bool_text(safety.patch),
            bool_text(safety.action),
            bool_text(safety.invoke),
        ),
    )
}

fn query_surface_gate(packet: &ReadOnlyBridgeReportPacket) -> ReadOnlyBridgeAcceptanceGate {
    let required = [
        "world.actions.query",
        "world.events.query",
        "world.evidence.query",
        "world.feedback.query",
        "world.rollbacks.query",
    ];
    let missing = required
        .iter()
        .filter(|surface| {
            !packet
                .summary
                .query_surfaces
                .iter()
                .any(|candidate| candidate == **surface)
        })
        .copied()
        .collect::<Vec<_>>();
    let mutation_surfaces = packet
        .summary
        .query_surfaces
        .iter()
        .filter(|surface| has_mutation_segment(surface))
        .cloned()
        .collect::<Vec<_>>();
    let ok = missing.is_empty() && mutation_surfaces.is_empty();

    gate(
        "query_surface_contract",
        verdict(ok),
        true,
        format!(
            "missing={}, mutation_like_surfaces={}",
            join_or_none(&missing),
            join_or_none(&mutation_surfaces)
        ),
    )
}

fn report_markdown_gate(packet: &ReadOnlyBridgeReportPacket) -> ReadOnlyBridgeAcceptanceGate {
    let expected = render_readonly_bridge_report(&packet.summary);
    let ok = packet.report_markdown == expected;

    gate(
        "report_markdown_consistency",
        verdict(ok),
        true,
        format!(
            "rerender_match={}, bytes={}",
            bool_text(ok),
            packet.report_markdown.len()
        ),
    )
}

fn detailed_readback_gate(packet: &ReadOnlyBridgeReportPacket) -> ReadOnlyBridgeAcceptanceGate {
    let summary = &packet.summary;
    let detailed = packet.readback_mode == "detailed_snapshot"
        && summary.readback_mode == "detailed_snapshot"
        && summary.outcome_counts.verified == Some(summary.verified.len())
        && summary.outcome_counts.not_verified == Some(summary.not_verified.len())
        && summary.outcome_counts.blocked == Some(summary.blocked.len())
        && summary
            .outcome_counts
            .feedback_changes_world_verdict
            .is_some();

    let verdict = if detailed {
        PASSED
    } else if packet.readback_mode == "counts_only" || summary.readback_mode == "counts_only" {
        WARNING
    } else {
        FAILED
    };

    gate(
        "detailed_readback",
        verdict,
        false,
        format!(
            "mode={}, verified={}, not_verified={}, blocked={}, feedback_changes_world_verdict={}",
            packet.readback_mode,
            optional_count(summary.outcome_counts.verified),
            optional_count(summary.outcome_counts.not_verified),
            optional_count(summary.outcome_counts.blocked),
            optional_count(summary.outcome_counts.feedback_changes_world_verdict),
        ),
    )
}

fn feedback_separation_gate(packet: &ReadOnlyBridgeReportPacket) -> ReadOnlyBridgeAcceptanceGate {
    let changed = packet
        .summary
        .feedback
        .iter()
        .filter(|entry| entry.changes_world_verdict)
        .count();
    let count_field = packet.summary.outcome_counts.feedback_changes_world_verdict;
    let verdict = if changed == 0 && count_field == Some(0) {
        PASSED
    } else if changed == 0 && count_field.is_none() {
        WARNING
    } else {
        FAILED
    };

    gate(
        "feedback_verdict_separation",
        verdict,
        true,
        format!(
            "feedback_items={}, changes_world_verdict={}, count_field={}",
            packet.summary.feedback.len(),
            changed,
            optional_count(count_field),
        ),
    )
}

fn gate(
    gate: impl Into<String>,
    verdict: impl Into<String>,
    required_for_wrapper: bool,
    evidence: impl Into<String>,
) -> ReadOnlyBridgeAcceptanceGate {
    ReadOnlyBridgeAcceptanceGate {
        gate: gate.into(),
        verdict: verdict.into(),
        required_for_wrapper,
        evidence: evidence.into(),
    }
}

fn verdict(ok: bool) -> &'static str {
    if ok {
        PASSED
    } else {
        FAILED
    }
}

fn overall_verdict(gates: &[ReadOnlyBridgeAcceptanceGate]) -> String {
    if gates
        .iter()
        .any(|gate| gate.required_for_wrapper && gate.verdict == FAILED)
    {
        "rejected".to_string()
    } else if gates
        .iter()
        .any(|gate| gate.verdict == FAILED || gate.verdict == WARNING)
    {
        "needs_review".to_string()
    } else {
        "accepted".to_string()
    }
}

fn guidance_for(overall_verdict: &str) -> Vec<String> {
    match overall_verdict {
        "accepted" => vec![
            "Packet is ready for read-only UI or agent wrapper consumption.".to_string(),
            "MCP exposure still requires a separate profile-gated wrapper change.".to_string(),
            "Keep Step D, #92 present wiring, and #94 ingestion out of this acceptance packet."
                .to_string(),
        ],
        "needs_review" => vec![
            "Only non-required or counts-only gates need review; do not expose as final accepted."
                .to_string(),
            "Prefer regenerating the packet from a detailed snapshot before wrapper exposure."
                .to_string(),
        ],
        _ => vec![
            "Required wrapper gates failed; do not expose this packet through UI, agent, or MCP surfaces."
                .to_string(),
            "Regenerate the packet from the read-only projection path and rerun acceptance."
                .to_string(),
        ],
    }
}

fn bool_text(value: bool) -> &'static str {
    if value {
        "true"
    } else {
        "false"
    }
}

fn optional_count(value: Option<usize>) -> String {
    value
        .map(|value| value.to_string())
        .unwrap_or_else(|| "unknown".to_string())
}

fn join_or_none<T: AsRef<str>>(values: &[T]) -> String {
    if values.is_empty() {
        "none".to_string()
    } else {
        values
            .iter()
            .map(|value| value.as_ref())
            .collect::<Vec<_>>()
            .join(",")
    }
}

fn has_mutation_segment(surface: &str) -> bool {
    surface
        .split('.')
        .any(|segment| matches!(segment, "patch" | "action" | "invoke" | "mutate"))
}
