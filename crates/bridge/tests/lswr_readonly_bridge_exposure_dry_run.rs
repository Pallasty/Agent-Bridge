use ab_bridge::lswr_snapshot_wrapper_descriptor::build_readonly_bridge_wrapper_descriptor;
use ab_bridge::lswr_snapshot_wrapper_exposure_dry_run::{
    LSWR_READONLY_BRIDGE_WRAPPER_EXPOSURE_DRY_RUN_SCHEMA, ReadOnlyBridgeWrapperExposureDryRun,
    build_readonly_bridge_wrapper_exposure_dry_run, build_readonly_bridge_wrapper_exposure_request,
    evaluate_readonly_bridge_wrapper_exposure_dry_run,
};

const EXPOSURE_DRY_RUN_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_exposure_dry_run_v0.json");

#[test]
fn exposure_dry_run_fixture_matches_builder() {
    let dry_run = build_readonly_bridge_wrapper_exposure_dry_run();
    let expected: ReadOnlyBridgeWrapperExposureDryRun =
        serde_json::from_str(EXPOSURE_DRY_RUN_JSON).expect("exposure dry-run fixture json");

    assert_eq!(dry_run, expected);
}

#[test]
fn exposure_dry_run_accepts_safe_all_profile_candidate_without_applying_registry_change() {
    let dry_run = build_readonly_bridge_wrapper_exposure_dry_run();

    assert_eq!(
        dry_run.schema,
        LSWR_READONLY_BRIDGE_WRAPPER_EXPOSURE_DRY_RUN_SCHEMA
    );
    assert_eq!(dry_run.verdict, "accepted");
    assert_eq!(dry_run.requested_profile, "all");
    assert!(!dry_run.applies_registry_change);
    assert!(dry_run.checks.iter().all(|check| check.verdict == "passed"));
}

#[test]
fn exposure_dry_run_rejects_codex_essential_profile() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let mut request = build_readonly_bridge_wrapper_exposure_request(&descriptor);
    request.requested_profile = "codex-essential".to_string();

    let dry_run = evaluate_readonly_bridge_wrapper_exposure_dry_run(&descriptor, &request);

    assert_eq!(dry_run.verdict, "rejected");
    assert_failed(&dry_run, "profile_gate");
    assert!(!dry_run.applies_registry_change);
}

#[test]
fn exposure_dry_run_rejects_host_path_live_runtime_and_gui_capture() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let mut request = build_readonly_bridge_wrapper_exposure_request(&descriptor);
    request.allow_host_path = true;
    request.allow_live_runtime = true;
    request.allow_gui_capture = true;

    let dry_run = evaluate_readonly_bridge_wrapper_exposure_dry_run(&descriptor, &request);

    assert_eq!(dry_run.verdict, "rejected");
    assert_failed(&dry_run, "input_safety");
    assert!(!dry_run.applies_registry_change);
}

#[test]
fn exposure_dry_run_rejects_mutation_affordances() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let mut request = build_readonly_bridge_wrapper_exposure_request(&descriptor);
    request.allow_action = true;
    request.allow_invoke = true;

    let dry_run = evaluate_readonly_bridge_wrapper_exposure_dry_run(&descriptor, &request);

    assert_eq!(dry_run.verdict, "rejected");
    assert_failed(&dry_run, "mutation_safety");
    assert!(!dry_run.applies_registry_change);
}

#[test]
fn exposure_dry_run_rejects_schema_mismatch() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let mut request = build_readonly_bridge_wrapper_exposure_request(&descriptor);
    request.output_schema = "agent_bridge.lswr.unrelated_output.v0".to_string();

    let dry_run = evaluate_readonly_bridge_wrapper_exposure_dry_run(&descriptor, &request);

    assert_eq!(dry_run.verdict, "rejected");
    assert_failed(&dry_run, "schema_contract");
}

#[test]
fn exposure_dry_run_rejects_missing_wrapper_ready_guard() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let mut request = build_readonly_bridge_wrapper_exposure_request(&descriptor);
    request.requires_wrapper_ready = false;

    let dry_run = evaluate_readonly_bridge_wrapper_exposure_dry_run(&descriptor, &request);

    assert_eq!(dry_run.verdict, "rejected");
    assert_failed(&dry_run, "acceptance_guard");
}

#[test]
fn exposure_dry_run_fixture_keeps_stable_pretty_json() {
    let dry_run: ReadOnlyBridgeWrapperExposureDryRun =
        serde_json::from_str(EXPOSURE_DRY_RUN_JSON).expect("exposure dry-run fixture json");
    let pretty = serde_json::to_string_pretty(&dry_run).expect("pretty exposure dry-run json");

    assert_eq!(format!("{pretty}\n"), EXPOSURE_DRY_RUN_JSON);
}

fn assert_failed(dry_run: &ReadOnlyBridgeWrapperExposureDryRun, check: &str) {
    assert_eq!(
        dry_run
            .checks
            .iter()
            .find(|candidate| candidate.check == check)
            .expect("expected dry-run check")
            .verdict,
        "failed"
    );
}
