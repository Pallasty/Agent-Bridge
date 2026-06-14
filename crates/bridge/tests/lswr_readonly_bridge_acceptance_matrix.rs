use ab_bridge::lswr_snapshot_report::render_readonly_bridge_report;
use ab_bridge::lswr_snapshot_report_acceptance::{
    build_readonly_bridge_acceptance_matrix, ReadOnlyBridgeAcceptanceMatrix,
    LSWR_READONLY_BRIDGE_ACCEPTANCE_MATRIX_SCHEMA,
};
use ab_bridge::lswr_snapshot_report_packet::ReadOnlyBridgeReportPacket;

const REPORT_PACKET_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_report_packet_v0.json");
const ACCEPTANCE_MATRIX_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_acceptance_matrix_v0.json");

#[test]
fn acceptance_matrix_fixture_matches_report_packet() {
    let packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    let matrix = build_readonly_bridge_acceptance_matrix(&packet);
    let expected: ReadOnlyBridgeAcceptanceMatrix =
        serde_json::from_str(ACCEPTANCE_MATRIX_JSON).expect("acceptance matrix fixture json");

    assert_eq!(matrix, expected);
}

#[test]
fn acceptance_matrix_accepts_readonly_packet_for_wrapper_planning() {
    let matrix: ReadOnlyBridgeAcceptanceMatrix =
        serde_json::from_str(ACCEPTANCE_MATRIX_JSON).expect("acceptance matrix fixture json");

    assert_eq!(matrix.schema, LSWR_READONLY_BRIDGE_ACCEPTANCE_MATRIX_SCHEMA);
    assert_eq!(
        matrix.packet_schema,
        "agent_bridge.lswr.readonly_bridge_report_packet.v0"
    );
    assert_eq!(matrix.overall_verdict, "accepted");
    assert_eq!(matrix.gates.len(), 7);
    assert!(matrix.gates.iter().all(|gate| gate.verdict == "passed"));
}

#[test]
fn acceptance_matrix_rejects_mutating_affordance() {
    let mut packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    packet.safety.action = true;
    packet.summary.safety.action = true;

    let matrix = build_readonly_bridge_acceptance_matrix(&packet);

    assert_eq!(matrix.overall_verdict, "rejected");
    let safety_gate = matrix
        .gates
        .iter()
        .find(|gate| gate.gate == "read_only_safety")
        .expect("read_only_safety gate");
    assert_eq!(safety_gate.verdict, "failed");
}

#[test]
fn acceptance_matrix_rejects_mutating_query_surface_segment() {
    let mut packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    packet
        .summary
        .query_surfaces
        .push("world.action.query".to_string());

    let matrix = build_readonly_bridge_acceptance_matrix(&packet);

    assert_eq!(matrix.overall_verdict, "rejected");
    let query_gate = matrix
        .gates
        .iter()
        .find(|gate| gate.gate == "query_surface_contract")
        .expect("query_surface_contract gate");
    assert_eq!(query_gate.verdict, "failed");
    assert!(query_gate.evidence.contains("world.action.query"));
}

#[test]
fn acceptance_matrix_marks_counts_only_packet_for_review() {
    let mut packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    packet.readback_mode = "counts_only".to_string();
    packet.summary.readback_mode = "counts_only".to_string();
    packet.summary.outcome_counts.verified = None;
    packet.summary.outcome_counts.not_verified = None;
    packet.summary.outcome_counts.blocked = None;
    packet.summary.outcome_counts.feedback_changes_world_verdict = None;
    packet.summary.verified.clear();
    packet.summary.not_verified.clear();
    packet.summary.blocked.clear();
    packet.summary.feedback.clear();
    packet.summary.rollbacks.clear();
    packet.report_markdown = render_readonly_bridge_report(&packet.summary);

    let matrix = build_readonly_bridge_acceptance_matrix(&packet);

    assert_eq!(matrix.overall_verdict, "needs_review");
    let detailed_gate = matrix
        .gates
        .iter()
        .find(|gate| gate.gate == "detailed_readback")
        .expect("detailed_readback gate");
    let feedback_gate = matrix
        .gates
        .iter()
        .find(|gate| gate.gate == "feedback_verdict_separation")
        .expect("feedback_verdict_separation gate");
    assert_eq!(detailed_gate.verdict, "warning");
    assert_eq!(feedback_gate.verdict, "warning");
}

#[test]
fn acceptance_matrix_rejects_stale_markdown_report() {
    let mut packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    packet.report_markdown.push_str("\nstale local edit\n");

    let matrix = build_readonly_bridge_acceptance_matrix(&packet);

    assert_eq!(matrix.overall_verdict, "rejected");
    let report_gate = matrix
        .gates
        .iter()
        .find(|gate| gate.gate == "report_markdown_consistency")
        .expect("report_markdown_consistency gate");
    assert_eq!(report_gate.verdict, "failed");
}

#[test]
fn acceptance_matrix_fixture_keeps_stable_pretty_json() {
    let matrix: ReadOnlyBridgeAcceptanceMatrix =
        serde_json::from_str(ACCEPTANCE_MATRIX_JSON).expect("acceptance matrix fixture json");
    let pretty = serde_json::to_string_pretty(&matrix).expect("pretty acceptance matrix json");

    assert_eq!(format!("{pretty}\n"), ACCEPTANCE_MATRIX_JSON);
}
