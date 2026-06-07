use ab_bridge::lswr_snapshot_display::{
    LSWR_READONLY_BRIDGE_DISPLAY_MODEL_SCHEMA, ReadOnlyBridgeDisplayModel,
    build_readonly_bridge_display_model, build_readonly_bridge_display_model_from_packet,
};
use ab_bridge::lswr_snapshot_report::render_readonly_bridge_report;
use ab_bridge::lswr_snapshot_report_acceptance::build_readonly_bridge_acceptance_matrix;
use ab_bridge::lswr_snapshot_report_packet::ReadOnlyBridgeReportPacket;

const REPORT_PACKET_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_report_packet_v0.json");
const DISPLAY_MODEL_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_display_model_v0.json");

#[test]
fn display_model_fixture_matches_report_packet() {
    let packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    let display_model = build_readonly_bridge_display_model_from_packet(&packet);
    let expected: ReadOnlyBridgeDisplayModel =
        serde_json::from_str(DISPLAY_MODEL_JSON).expect("display model fixture json");

    assert_eq!(display_model, expected);
}

#[test]
fn display_model_exposes_ready_status_and_safety() {
    let display_model: ReadOnlyBridgeDisplayModel =
        serde_json::from_str(DISPLAY_MODEL_JSON).expect("display model fixture json");

    assert_eq!(
        display_model.schema,
        LSWR_READONLY_BRIDGE_DISPLAY_MODEL_SCHEMA
    );
    assert_eq!(display_model.status.tone, "success");
    assert_eq!(display_model.status.label, "Ready for read-only display");
    assert!(display_model.safety.wrapper_ready);
    assert!(display_model.safety.matrix_consistent_with_packet);
    assert!(display_model.safety.read_only);
    assert_eq!(display_model.safety.mutation_surface, "none");
    assert!(!display_model.safety.mcp_tool_registration);
    assert_eq!(display_model.gate_rows.len(), 7);
    assert_eq!(display_model.readback_groups.len(), 5);
}

#[test]
fn display_model_rejects_matrix_packet_mismatch() {
    let packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    let mut matrix = build_readonly_bridge_acceptance_matrix(&packet);
    matrix.snapshot_sha256 = "sha256:mismatch".to_string();

    let display_model = build_readonly_bridge_display_model(&packet, &matrix);

    assert_eq!(display_model.status.tone, "danger");
    assert!(!display_model.safety.wrapper_ready);
    assert!(!display_model.safety.matrix_consistent_with_packet);
    assert_eq!(
        display_model
            .badges
            .iter()
            .find(|badge| badge.label == "matrix_match")
            .expect("matrix_match badge")
            .value,
        "false"
    );
}

#[test]
fn display_model_marks_mutating_affordance_as_unsafe() {
    let mut packet: ReadOnlyBridgeReportPacket =
        serde_json::from_str(REPORT_PACKET_JSON).expect("report packet fixture json");
    packet.safety.action = true;
    packet.summary.safety.action = true;

    let display_model = build_readonly_bridge_display_model_from_packet(&packet);

    assert_eq!(display_model.status.tone, "danger");
    assert!(!display_model.safety.wrapper_ready);
    let action = display_model
        .safety
        .affordances
        .iter()
        .find(|badge| badge.label == "action")
        .expect("action affordance badge");
    assert_eq!(action.value, "true");
    assert_eq!(action.tone, "danger");
}

#[test]
fn display_model_maps_counts_only_packet_to_review_status() {
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

    let display_model = build_readonly_bridge_display_model_from_packet(&packet);

    assert_eq!(display_model.status.tone, "warning");
    assert_eq!(display_model.status.label, "Needs review");
    assert!(!display_model.safety.wrapper_ready);
    assert_eq!(
        display_model
            .badges
            .iter()
            .find(|badge| badge.label == "readback")
            .expect("readback badge")
            .tone,
        "warning"
    );
}

#[test]
fn display_model_fixture_keeps_stable_pretty_json() {
    let display_model: ReadOnlyBridgeDisplayModel =
        serde_json::from_str(DISPLAY_MODEL_JSON).expect("display model fixture json");
    let pretty = serde_json::to_string_pretty(&display_model).expect("pretty display model json");

    assert_eq!(format!("{pretty}\n"), DISPLAY_MODEL_JSON);
}
