use ab_bridge::lswr_snapshot_wrapper_descriptor::{
    LSWR_READONLY_BRIDGE_WRAPPER_DESCRIPTOR_SCHEMA, ReadOnlyBridgeWrapperDescriptor,
    build_readonly_bridge_wrapper_descriptor,
};

const WRAPPER_DESCRIPTOR_JSON: &str =
    include_str!("fixtures/lswr_readonly_bridge_wrapper_descriptor_v0.json");

#[test]
fn wrapper_descriptor_fixture_matches_builder() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let expected: ReadOnlyBridgeWrapperDescriptor =
        serde_json::from_str(WRAPPER_DESCRIPTOR_JSON).expect("wrapper descriptor fixture json");

    assert_eq!(descriptor, expected);
}

#[test]
fn wrapper_descriptor_is_descriptor_only_not_registered() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();

    assert_eq!(
        descriptor.schema,
        LSWR_READONLY_BRIDGE_WRAPPER_DESCRIPTOR_SCHEMA
    );
    assert_eq!(descriptor.state, "descriptor_only");
    assert_eq!(descriptor.profile_gate.current_exposure, "not_registered");
    assert!(!descriptor.profile_gate.mcp_registry_change);
    assert!(descriptor.profile_gate.requires_separate_registry_change);
    assert_eq!(
        descriptor.profile_gate.codex_essential_status,
        "not_exposed"
    );
}

#[test]
fn wrapper_descriptor_requires_explicit_payload_and_no_live_inputs() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();

    assert_eq!(
        descriptor.input_contract.mode,
        "explicit_report_packet_payload"
    );
    assert!(descriptor.input_contract.requires_explicit_packet_payload);
    assert!(!descriptor.input_contract.accepts_host_path);
    assert!(!descriptor.input_contract.accepts_live_runtime);
    assert!(!descriptor.input_contract.accepts_gui_capture);
}

#[test]
fn wrapper_descriptor_disallows_mutation_and_runtime_capabilities() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let disallowed = &descriptor.safety_contract.disallowed_capabilities;

    assert!(descriptor.safety_contract.read_only);
    assert_eq!(descriptor.safety_contract.mutation_surface, "none");
    assert!(disallowed.iter().any(|capability| capability == "patch"));
    assert!(disallowed.iter().any(|capability| capability == "action"));
    assert!(disallowed.iter().any(|capability| capability == "invoke"));
    assert!(
        disallowed
            .iter()
            .any(|capability| capability == "runtime_launch")
    );
    assert!(
        disallowed
            .iter()
            .any(|capability| capability == "host_path_read")
    );
    assert!(descriptor.output_contract.contains_report_markdown);
    assert!(descriptor.output_contract.contains_display_readback);
    assert!(!descriptor.output_contract.contains_mutating_handles);
}

#[test]
fn wrapper_descriptor_preserves_display_acceptance_boundary() {
    let descriptor = build_readonly_bridge_wrapper_descriptor();

    assert_eq!(
        descriptor.acceptance_contract.required_overall_verdict,
        "accepted"
    );
    assert_eq!(
        descriptor.acceptance_contract.required_display_status_label,
        "Ready for read-only display"
    );
    assert_eq!(
        descriptor.acceptance_contract.required_display_status_tone,
        "success"
    );
    assert!(descriptor.acceptance_contract.required_wrapper_ready);
    assert_eq!(descriptor.acceptance_contract.all_gate_verdict, "passed");
    assert_eq!(
        descriptor.acceptance_contract.required_matrix_gates.len(),
        6
    );
    assert_eq!(
        descriptor.acceptance_contract.review_sensitive_gates,
        vec!["detailed_readback".to_string()]
    );
}

#[test]
fn wrapper_descriptor_fixture_keeps_stable_pretty_json() {
    let descriptor: ReadOnlyBridgeWrapperDescriptor =
        serde_json::from_str(WRAPPER_DESCRIPTOR_JSON).expect("wrapper descriptor fixture json");
    let pretty = serde_json::to_string_pretty(&descriptor).expect("pretty descriptor json");

    assert_eq!(format!("{pretty}\n"), WRAPPER_DESCRIPTOR_JSON);
}
