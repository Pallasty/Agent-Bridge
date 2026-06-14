use crate::lswr_snapshot_consumer::{ConsumerSafety, ReadOnlyBridgeConsumerSummary};
use crate::lswr_snapshot_report::{
    render_readonly_bridge_report, LSWR_READONLY_BRIDGE_REPORT_SCHEMA,
};
use serde::{Deserialize, Serialize};

pub const LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA: &str =
    "agent_bridge.lswr.readonly_bridge_report_packet.v0";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeReportPacket {
    pub schema: String,
    pub summary_schema: String,
    pub report_schema: String,
    pub projection_schema: String,
    pub snapshot_sha256: String,
    pub readback_mode: String,
    pub read_only_confirmed: bool,
    pub safety: ConsumerSafety,
    pub summary: ReadOnlyBridgeConsumerSummary,
    pub report_markdown: String,
}

pub fn build_readonly_bridge_report_packet(
    summary: &ReadOnlyBridgeConsumerSummary,
) -> ReadOnlyBridgeReportPacket {
    ReadOnlyBridgeReportPacket {
        schema: LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA.to_string(),
        summary_schema: summary.schema.clone(),
        report_schema: LSWR_READONLY_BRIDGE_REPORT_SCHEMA.to_string(),
        projection_schema: summary.projection_schema.clone(),
        snapshot_sha256: summary.snapshot_sha256.clone(),
        readback_mode: summary.readback_mode.clone(),
        read_only_confirmed: summary.read_only_confirmed,
        safety: summary.safety.clone(),
        summary: summary.clone(),
        report_markdown: render_readonly_bridge_report(summary),
    }
}
