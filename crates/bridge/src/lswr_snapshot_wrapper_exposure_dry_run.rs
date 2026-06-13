use crate::lswr_snapshot_wrapper_descriptor::{
    build_readonly_bridge_wrapper_descriptor, ReadOnlyBridgeWrapperDescriptor,
    LSWR_READONLY_BRIDGE_WRAPPER_DESCRIPTOR_SCHEMA,
};
use serde::{Deserialize, Serialize};

pub const LSWR_READONLY_BRIDGE_WRAPPER_EXPOSURE_DRY_RUN_SCHEMA: &str =
    "agent_bridge.lswr.readonly_bridge_wrapper_exposure_dry_run.v0";

const PASSED: &str = "passed";
const FAILED: &str = "failed";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WrapperExposureRequest {
    pub tool_name: String,
    pub requested_profile: String,
    pub registry_change_mode: String,
    pub input_mode: String,
    pub input_schema: String,
    pub output_schema: String,
    pub requires_wrapper_ready: bool,
    pub allow_host_path: bool,
    pub allow_live_runtime: bool,
    pub allow_gui_capture: bool,
    pub allow_mutation: bool,
    pub allow_patch: bool,
    pub allow_action: bool,
    pub allow_invoke: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeWrapperExposureDryRun {
    pub schema: String,
    pub descriptor_schema: String,
    pub wrapper_name: String,
    pub requested_tool_name: String,
    pub requested_profile: String,
    pub verdict: String,
    pub applies_registry_change: bool,
    pub checks: Vec<WrapperExposureCheck>,
    pub guidance: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WrapperExposureCheck {
    pub check: String,
    pub verdict: String,
    pub required: bool,
    pub evidence: String,
}

pub fn build_readonly_bridge_wrapper_exposure_request(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
) -> WrapperExposureRequest {
    WrapperExposureRequest {
        tool_name: descriptor.profile_gate.candidate_tool_name.clone(),
        requested_profile: descriptor
            .profile_gate
            .minimum_profile_after_registry
            .clone(),
        registry_change_mode: "dry_run_only".to_string(),
        input_mode: descriptor.input_contract.mode.clone(),
        input_schema: descriptor.input_contract.required_schema.clone(),
        output_schema: descriptor.output_contract.schema.clone(),
        requires_wrapper_ready: descriptor.acceptance_contract.required_wrapper_ready,
        allow_host_path: false,
        allow_live_runtime: false,
        allow_gui_capture: false,
        allow_mutation: false,
        allow_patch: false,
        allow_action: false,
        allow_invoke: false,
    }
}

pub fn build_readonly_bridge_wrapper_exposure_dry_run() -> ReadOnlyBridgeWrapperExposureDryRun {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let request = build_readonly_bridge_wrapper_exposure_request(&descriptor);
    evaluate_readonly_bridge_wrapper_exposure_dry_run(&descriptor, &request)
}

pub fn evaluate_readonly_bridge_wrapper_exposure_dry_run(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    request: &WrapperExposureRequest,
) -> ReadOnlyBridgeWrapperExposureDryRun {
    let checks = vec![
        descriptor_state_check(descriptor),
        registry_mode_check(request),
        tool_name_check(descriptor, request),
        profile_gate_check(descriptor, request),
        schema_contract_check(descriptor, request),
        input_safety_check(descriptor, request),
        mutation_safety_check(request),
        acceptance_guard_check(descriptor, request),
    ];
    let verdict = dry_run_verdict(&checks);

    ReadOnlyBridgeWrapperExposureDryRun {
        schema: LSWR_READONLY_BRIDGE_WRAPPER_EXPOSURE_DRY_RUN_SCHEMA.to_string(),
        descriptor_schema: descriptor.schema.clone(),
        wrapper_name: descriptor.wrapper_name.clone(),
        requested_tool_name: request.tool_name.clone(),
        requested_profile: request.requested_profile.clone(),
        verdict: verdict.clone(),
        applies_registry_change: false,
        checks,
        guidance: guidance_for(&verdict),
    }
}

fn descriptor_state_check(descriptor: &ReadOnlyBridgeWrapperDescriptor) -> WrapperExposureCheck {
    let ok = descriptor.schema == LSWR_READONLY_BRIDGE_WRAPPER_DESCRIPTOR_SCHEMA
        && descriptor.state == "descriptor_only"
        && !descriptor.profile_gate.mcp_registry_change
        && descriptor.profile_gate.requires_separate_registry_change;

    check(
        "descriptor_state",
        ok,
        true,
        format!(
            "schema={}, state={}, mcp_registry_change={}, requires_separate_registry_change={}",
            descriptor.schema,
            descriptor.state,
            bool_text(descriptor.profile_gate.mcp_registry_change),
            bool_text(descriptor.profile_gate.requires_separate_registry_change)
        ),
    )
}

fn registry_mode_check(request: &WrapperExposureRequest) -> WrapperExposureCheck {
    let ok = request.registry_change_mode == "dry_run_only";
    check(
        "registry_mode",
        ok,
        true,
        format!(
            "registry_change_mode={}, applies_registry_change=false",
            request.registry_change_mode
        ),
    )
}

fn tool_name_check(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    request: &WrapperExposureRequest,
) -> WrapperExposureCheck {
    let ok = request.tool_name == descriptor.wrapper_name
        && request.tool_name == descriptor.profile_gate.candidate_tool_name;
    check(
        "tool_name",
        ok,
        true,
        format!(
            "requested={}, descriptor={}, candidate={}",
            request.tool_name, descriptor.wrapper_name, descriptor.profile_gate.candidate_tool_name
        ),
    )
}

fn profile_gate_check(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    request: &WrapperExposureRequest,
) -> WrapperExposureCheck {
    let ok = request.requested_profile == descriptor.profile_gate.minimum_profile_after_registry
        && descriptor.profile_gate.codex_essential_status == "not_exposed";
    check(
        "profile_gate",
        ok,
        true,
        format!(
            "requested={}, minimum_after_registry={}, codex_essential_status={}",
            request.requested_profile,
            descriptor.profile_gate.minimum_profile_after_registry,
            descriptor.profile_gate.codex_essential_status
        ),
    )
}

fn schema_contract_check(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    request: &WrapperExposureRequest,
) -> WrapperExposureCheck {
    let ok = request.input_schema == descriptor.input_contract.required_schema
        && request.output_schema == descriptor.output_contract.schema;
    check(
        "schema_contract",
        ok,
        true,
        format!(
            "input={}, required_input={}, output={}, required_output={}",
            request.input_schema,
            descriptor.input_contract.required_schema,
            request.output_schema,
            descriptor.output_contract.schema
        ),
    )
}

fn input_safety_check(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    request: &WrapperExposureRequest,
) -> WrapperExposureCheck {
    let ok = request.input_mode == descriptor.input_contract.mode
        && descriptor.input_contract.requires_explicit_packet_payload
        && !request.allow_host_path
        && !request.allow_live_runtime
        && !request.allow_gui_capture;
    check(
        "input_safety",
        ok,
        true,
        format!(
            "mode={}, explicit_payload={}, host_path={}, live_runtime={}, gui_capture={}",
            request.input_mode,
            bool_text(descriptor.input_contract.requires_explicit_packet_payload),
            bool_text(request.allow_host_path),
            bool_text(request.allow_live_runtime),
            bool_text(request.allow_gui_capture)
        ),
    )
}

fn mutation_safety_check(request: &WrapperExposureRequest) -> WrapperExposureCheck {
    let ok = !request.allow_mutation
        && !request.allow_patch
        && !request.allow_action
        && !request.allow_invoke;
    check(
        "mutation_safety",
        ok,
        true,
        format!(
            "mutation={}, patch={}, action={}, invoke={}",
            bool_text(request.allow_mutation),
            bool_text(request.allow_patch),
            bool_text(request.allow_action),
            bool_text(request.allow_invoke)
        ),
    )
}

fn acceptance_guard_check(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    request: &WrapperExposureRequest,
) -> WrapperExposureCheck {
    let ok = request.requires_wrapper_ready
        && descriptor.acceptance_contract.required_wrapper_ready
        && descriptor.acceptance_contract.required_overall_verdict == "accepted"
        && descriptor.acceptance_contract.required_display_status_tone == "success"
        && descriptor.acceptance_contract.all_gate_verdict == "passed";
    check(
        "acceptance_guard",
        ok,
        true,
        format!(
            "requires_wrapper_ready={}, overall={}, status_tone={}, all_gate_verdict={}",
            bool_text(request.requires_wrapper_ready),
            descriptor.acceptance_contract.required_overall_verdict,
            descriptor.acceptance_contract.required_display_status_tone,
            descriptor.acceptance_contract.all_gate_verdict
        ),
    )
}

fn dry_run_verdict(checks: &[WrapperExposureCheck]) -> String {
    if checks
        .iter()
        .any(|check| check.required && check.verdict == FAILED)
    {
        "rejected".to_string()
    } else {
        "accepted".to_string()
    }
}

fn guidance_for(verdict: &str) -> Vec<String> {
    match verdict {
        "accepted" => vec![
            "Dry-run request is compatible with the read-only wrapper descriptor.".to_string(),
            "No registry mutation was applied; open a separate MCP registration slice before exposing a real tool.".to_string(),
            "Keep live runtime, GUI capture, host path reads, and mutation affordances outside the wrapper.".to_string(),
        ],
        _ => vec![
            "Do not expose this wrapper candidate until failed dry-run checks are fixed.".to_string(),
            "Keep MCP registry unchanged and regenerate the request from the descriptor.".to_string(),
        ],
    }
}

fn check(
    name: impl Into<String>,
    ok: bool,
    required: bool,
    evidence: impl Into<String>,
) -> WrapperExposureCheck {
    WrapperExposureCheck {
        check: name.into(),
        verdict: if ok { PASSED } else { FAILED }.to_string(),
        required,
        evidence: evidence.into(),
    }
}

fn bool_text(value: bool) -> &'static str {
    if value {
        "true"
    } else {
        "false"
    }
}
