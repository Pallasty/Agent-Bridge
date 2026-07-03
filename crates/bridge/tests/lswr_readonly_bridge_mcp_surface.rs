use ab_bridge::mcp_tools::{
    lswr_readonly_bridge_display_mcp_surface_report,
    LSWR_READONLY_BRIDGE_DISPLAY_MCP_SURFACE_REPORT_SCHEMA,
};
use serde_json::Value;

const MCP_SURFACE_JSON: &str = include_str!("fixtures/lswr_readonly_bridge_mcp_surface_v0.json");

#[test]
fn mcp_surface_fixture_matches_builder() {
    let report = lswr_readonly_bridge_display_mcp_surface_report();
    let expected: Value = serde_json::from_str(MCP_SURFACE_JSON).expect("mcp surface fixture json");

    assert_eq!(report, expected);
}

#[test]
fn mcp_surface_reports_all_dev_only_visibility() {
    let report = lswr_readonly_bridge_display_mcp_surface_report();

    assert_eq!(
        report["schema"],
        LSWR_READONLY_BRIDGE_DISPLAY_MCP_SURFACE_REPORT_SCHEMA
    );
    assert_eq!(report["verdict"], "passed");
    // Ceremony-gated (2026-07 prune): hidden from profile-all by default.
    assert_eq!(report["visible_in"], serde_json::json!(["all-dev"]));

    assert_profile(&report, "profile-all", false);
    assert_profile(&report, "all-dev", true);
    assert_profile(&report, "profile-standard", false);
    assert_profile(&report, "codex-essential", false);
    assert_profile(&report, "codex-lean", false);
}

#[test]
fn mcp_surface_schema_is_explicit_packet_only() {
    let report = lswr_readonly_bridge_display_mcp_surface_report();
    let schema = &report["tool_schema"];

    assert_eq!(schema["present"], true);
    assert_eq!(schema["input_keys"], serde_json::json!(["report_packet"]));
    assert_eq!(schema["required"], serde_json::json!(["report_packet"]));
    assert_eq!(schema["additional_properties"], false);
    assert_eq!(schema["forbidden_input_keys_absent"], true);
    assert_eq!(schema["description_mentions_read_only"], true);
    assert_eq!(schema["description_mentions_explicit"], true);
    assert!(schema["input_schema"]["properties"]
        .get("report_packet")
        .is_some());
    assert!(schema["input_schema"]["properties"]
        .get("packet_path")
        .is_none());
    assert!(schema["input_schema"]["properties"]
        .get("live_runtime")
        .is_none());
    assert!(schema["input_schema"]["properties"]
        .get("gui_capture")
        .is_none());
}

#[test]
fn mcp_surface_markdown_lists_profiles_and_checks() {
    let report = lswr_readonly_bridge_display_mcp_surface_report();
    let markdown = report["report_markdown"].as_str().expect("report markdown");

    assert!(markdown.contains("# LSWR Read-Only Bridge MCP Surface"));
    assert!(markdown.contains("`profile-all`: registered=`false` expected=`false`"));
    assert!(markdown.contains("`profile-standard`: registered=`false` expected=`false`"));
    assert!(markdown.contains("`codex-essential`: registered=`false` expected=`false`"));
    assert!(markdown.contains("`explicit_packet_only`: `passed`"));
}

#[test]
fn mcp_surface_fixture_keeps_stable_pretty_json() {
    let report: Value = serde_json::from_str(MCP_SURFACE_JSON).expect("mcp surface fixture json");
    let pretty = serde_json::to_string_pretty(&report).expect("pretty mcp surface json");

    assert_eq!(format!("{pretty}\n"), MCP_SURFACE_JSON);
}

fn assert_profile(report: &Value, label: &str, expected_registered: bool) {
    let row = report["profile_rows"]
        .as_array()
        .expect("profile rows")
        .iter()
        .find(|row| row["label"] == label)
        .unwrap_or_else(|| panic!("missing profile row {label}"));

    assert_eq!(row["registered"], expected_registered);
    assert_eq!(row["expected_registered"], expected_registered);
    assert_eq!(row["matches_expected"], true);
}
