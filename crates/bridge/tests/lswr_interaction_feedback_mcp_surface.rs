use ab_bridge::mcp_tools::{
    lswr_interaction_feedback_consumption_report_mcp_surface_report,
    LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_MCP_SURFACE_REPORT_SCHEMA,
};
use serde_json::Value;

#[test]
fn mcp_surface_report_exposes_candidate_under_all_dev_only() {
    let report = lswr_interaction_feedback_consumption_report_mcp_surface_report();

    assert_eq!(
        report["schema"],
        LSWR_INTERACTION_FEEDBACK_CONSUMPTION_REPORT_MCP_SURFACE_REPORT_SCHEMA
    );
    assert_eq!(
        report["tool"],
        "lswr_interaction_feedback_consumption_report"
    );
    assert_eq!(report["decision"], "REGISTERED_NICHE_MCP_GATE");
    assert_eq!(
        report["implementation_status"],
        "IMPLEMENTED_AS_NICHE_MCP_TOOL"
    );
    assert_eq!(report["verdict"], "passed");
    // Ceremony-gated (2026-07 prune): hidden from profile-all by default.
    assert_eq!(report["visible_in"], serde_json::json!(["all-dev"]));
    assert_eq!(report["schema_present_in_all_dev"], true);

    assert_profile(&report, "profile-all", false);
    assert_profile(&report, "all-dev", true);
    assert_profile(&report, "profile-standard", false);
    assert_profile(&report, "codex-essential", false);
    assert_profile(&report, "codex-lean", false);
    assert_profile(&report, "claude-standard", false);
    assert_profile(&report, "gemini-lean", false);
    assert_profile(&report, "hook-lifecycle", false);
}

#[test]
fn mcp_surface_report_preserves_explicit_input_contract() {
    let report = lswr_interaction_feedback_consumption_report_mcp_surface_report();

    assert_eq!(
        report["pure_report_schema"],
        "agent_bridge.lswr.interaction_feedback_consumption_report.v0"
    );
    assert_eq!(
        report["transport_envelope_schema"],
        "agent_bridge.lswr.interaction_feedback_consumption_report_mcp.v0"
    );
    assert_eq!(report["tool_tier"], "niche");
    assert_eq!(
        report["expected_input"]["top_level_keys"],
        serde_json::json!(["report_input"])
    );
    assert_eq!(report["expected_input"]["additional_properties"], false);
    assert_eq!(
        report["expected_input"]["input_mode"],
        "explicit_object_only"
    );
}

#[test]
fn mcp_surface_report_keeps_safety_boundary_read_only() {
    let report = lswr_interaction_feedback_consumption_report_mcp_surface_report();
    let safety = &report["safety_boundary"];

    assert_eq!(safety["read_only"], true);
    assert_eq!(safety["mcp_registry_change"], false);
    assert_eq!(safety["store_access"], false);
    assert_eq!(safety["memory_write"], false);
    assert_eq!(safety["live_runtime_lookup"], false);
    assert_eq!(safety["host_path"], false);
    assert_eq!(safety["file_path"], false);
    assert_eq!(safety["gui_capture"], false);
    assert_eq!(safety["outcome_ingestion"], false);
    assert_eq!(safety["onsen_mutation"], false);
    assert_eq!(safety["mutation_surface"], "none");
    assert_eq!(safety["mcp_surface_change"], "registered_niche_tool_only");
}

#[test]
fn mcp_surface_report_lists_required_checks_and_markdown() {
    let report = lswr_interaction_feedback_consumption_report_mcp_surface_report();
    let checks = report["checks"].as_array().expect("checks");
    let labels = checks
        .iter()
        .map(|check| check["label"].as_str().expect("label"))
        .collect::<Vec<_>>();

    for label in [
        "profile_matrix",
        "all_profile_hidden",
        "all_dev_visible",
        "standard_hidden",
        "codex_essential_hidden",
        "lean_and_hook_hidden",
        "schema_present",
        "explicit_report_input_only",
        "forbidden_inputs_absent",
        "pure_report_schema_available",
    ] {
        assert!(labels.contains(&label), "missing check {label}");
    }
    assert!(checks.iter().all(|check| check["verdict"] == "passed"));

    let markdown = report["report_markdown"].as_str().expect("markdown");
    assert!(markdown.contains("# LSWR Interaction Feedback Consumption Report MCP Surface"));
    assert!(markdown.contains("Decision: `REGISTERED_NICHE_MCP_GATE`"));
    assert!(markdown.contains("`profile-all`: registered=`false` expected=`false`"));
    assert!(markdown.contains("`all-dev`: registered=`true` expected=`true`"));
    assert!(markdown.contains("`profile-standard`: registered=`false` expected=`false`"));
    assert!(markdown.contains("`explicit_report_input_only`: `passed`"));
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
