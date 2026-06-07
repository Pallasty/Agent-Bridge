use ab_bridge::lswr_snapshot_consumer::ReadOnlyBridgeConsumerSummary;
use ab_bridge::lswr_snapshot_report_packet::{
    LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA, ReadOnlyBridgeReportPacket,
    build_readonly_bridge_report_packet,
};

const CONSUMER_SUMMARY_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_consumer_summary_v0.json");
const DETAILED_REPORT: &str = include_str!("fixtures/lswr_readonly_bridge_report_detailed_v0.md");
const REPORT_PACKET_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_report_packet_v0.json");

#[test]
fn report_packet_fixture_matches_consumer_summary() {
    let summary: ReadOnlyBridgeConsumerSummary =
        serde_json::from_str(CONSUMER_SUMMARY_JSON).expect("consumer summary fixture json");
    let packet = build_readonly_bridge_report_packet(&summary);
    let expected: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");

    assert_eq!(packet, expected);
}

#[test]
fn report_packet_embeds_stable_markdown_report() {
    let packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");

    assert_eq!(packet.report_markdown, DETAILED_REPORT);
}

#[test]
fn report_packet_keeps_readonly_bridge_safety_visible() {
    let packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");

    assert_eq!(packet.schema, LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA);
    assert_eq!(
        packet.summary_schema,
        "agent_bridge.lswr.readonly_bridge_consumer_summary.v0"
    );
    assert_eq!(
        packet.report_schema,
        "agent_bridge.lswr.readonly_bridge_report.v0"
    );
    assert_eq!(packet.readback_mode, "detailed_snapshot");
    assert!(packet.read_only_confirmed);
    assert!(packet.safety.read_only);
    assert_eq!(packet.safety.mutation_surface, "none");
    assert!(!packet.safety.mcp_tool_registration);
    assert!(!packet.safety.patch);
    assert!(!packet.safety.action);
    assert!(!packet.safety.invoke);
}

#[test]
fn report_packet_fixture_keeps_stable_pretty_json() {
    let packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    let pretty = serde_json::to_string_pretty(&packet).expect("pretty report packet json");

    assert_eq!(format!("{pretty}\n"), REPORT_PACKET_JSON);
}
