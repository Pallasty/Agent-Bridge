use ab_bridge::lswr_snapshot_wrapper_descriptor::build_readonly_bridge_wrapper_descriptor;
use ab_bridge::lswr_snapshot_wrapper_exposure_dry_run::{
    build_readonly_bridge_wrapper_exposure_dry_run, build_readonly_bridge_wrapper_exposure_request,
    evaluate_readonly_bridge_wrapper_exposure_dry_run,
};
use ab_bridge::lswr_snapshot_wrapper_preflight_report::{
    build_readonly_bridge_wrapper_preflight_report,
    build_readonly_bridge_wrapper_preflight_report_from_parts,
    ReadOnlyBridgeWrapperPreflightReport, LSWR_READONLY_BRIDGE_WRAPPER_PREFLIGHT_REPORT_SCHEMA,
};

const PREFLIGHT_REPORT_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_preflight_report_v0.json");

#[test]
fn preflight_report_fixture_matches_builder() {
    let report = build_readonly_bridge_wrapper_preflight_report();
    let expected: ReadOnlyBridgeWrapperPreflightReport =
        serde_json::from_str(PREFLIGHT_REPORT_JSON).expect("preflight report fixture json");

    assert_eq!(report, expected);
}

#[test]
fn preflight_report_marks_default_dry_run_ready_for_registry_review() {
    let report = build_readonly_bridge_wrapper_preflight_report();

    assert_eq!(
        report.schema,
        LSWR_READONLY_BRIDGE_WRAPPER_PREFLIGHT_REPORT_SCHEMA
    );
    assert_eq!(report.verdict, "ready_for_registry_review");
    assert_eq!(report.status.tone, "success");
    assert_eq!(report.registry_boundary.current_exposure, "not_registered");
    assert_eq!(report.registry_boundary.requested_profile, "all");
    assert!(!report.registry_boundary.applies_registry_change);
    assert!(report.registry_boundary.requires_separate_registry_change);
    assert!(report.check_rows.iter().all(|row| row.verdict == "passed"));
    assert_eq!(report.check_rows.len(), 9);
}

#[test]
fn preflight_report_preserves_readonly_safety_boundary() {
    let report = build_readonly_bridge_wrapper_preflight_report();

    assert!(report.safety_boundary.read_only);
    assert_eq!(
        report.safety_boundary.input_mode,
        "explicit_report_packet_payload"
    );
    assert_eq!(report.safety_boundary.mutation_surface, "none");
    assert!(report.safety_boundary.no_host_path);
    assert!(report.safety_boundary.no_live_runtime);
    assert!(report.safety_boundary.no_gui_capture);
    assert!(report
        .safety_boundary
        .disallowed_capabilities
        .iter()
        .any(|capability| capability == "runtime_launch"));
}

#[test]
fn preflight_report_blocks_descriptor_dry_run_mismatch() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let mut dry_run = build_readonly_bridge_wrapper_exposure_dry_run();
    dry_run.descriptor_schema = "agent_bridge.lswr.mismatched_descriptor.v0".to_string();

    let report = build_readonly_bridge_wrapper_preflight_report_from_parts(&descriptor, &dry_run);

    assert_eq!(report.verdict, "blocked");
    assert_eq!(report.status.tone, "danger");
    assert_failed(&report, "preflight_consistency");
}

#[test]
fn preflight_report_blocks_rejected_dry_run() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let mut request = build_readonly_bridge_wrapper_exposure_request(&descriptor);
    request.allow_action = true;
    let dry_run = evaluate_readonly_bridge_wrapper_exposure_dry_run(&descriptor, &request);

    let report = build_readonly_bridge_wrapper_preflight_report_from_parts(&descriptor, &dry_run);

    assert_eq!(report.verdict, "blocked");
    assert_eq!(report.status.label, "Blocked before registry review");
    assert_failed(&report, "mutation_safety");
}

#[test]
fn preflight_report_markdown_keeps_registry_boundary_visible() {
    let report = build_readonly_bridge_wrapper_preflight_report();

    assert!(report
        .report_markdown
        .contains("# LSWR Read-Only Bridge Wrapper Preflight"));
    assert!(report
        .report_markdown
        .contains("- Applies registry change: `false`"));
    assert!(report
        .report_markdown
        .contains("- Separate registry change required: `true`"));
    assert!(report
        .report_markdown
        .contains("`preflight_consistency`: `passed`"));
}

#[test]
fn preflight_report_fixture_keeps_stable_pretty_json() {
    let report: ReadOnlyBridgeWrapperPreflightReport =
        serde_json::from_str(PREFLIGHT_REPORT_JSON).expect("preflight report fixture json");
    let pretty = serde_json::to_string_pretty(&report).expect("pretty preflight report json");

    assert_eq!(format!("{pretty}\n"), PREFLIGHT_REPORT_JSON);
}

fn assert_failed(report: &ReadOnlyBridgeWrapperPreflightReport, check: &str) {
    assert_eq!(
        report
            .check_rows
            .iter()
            .find(|row| row.label == check)
            .expect("expected preflight check row")
            .verdict,
        "failed"
    );
}
