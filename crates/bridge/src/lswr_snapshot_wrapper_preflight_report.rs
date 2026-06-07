use crate::lswr_snapshot_wrapper_descriptor::{
    ReadOnlyBridgeWrapperDescriptor, build_readonly_bridge_wrapper_descriptor,
};
use crate::lswr_snapshot_wrapper_exposure_dry_run::{
    ReadOnlyBridgeWrapperExposureDryRun, WrapperExposureCheck,
    build_readonly_bridge_wrapper_exposure_dry_run,
};
use serde::{Deserialize, Serialize};

pub const LSWR_READONLY_BRIDGE_WRAPPER_PREFLIGHT_REPORT_SCHEMA: &str =
    "agent_bridge.lswr.readonly_bridge_wrapper_preflight_report.v0";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeWrapperPreflightReport {
    pub schema: String,
    pub descriptor_schema: String,
    pub dry_run_schema: String,
    pub wrapper_name: String,
    pub verdict: String,
    pub status: PreflightStatus,
    pub registry_boundary: PreflightRegistryBoundary,
    pub safety_boundary: PreflightSafetyBoundary,
    pub check_rows: Vec<PreflightCheckRow>,
    pub guidance: Vec<String>,
    pub report_markdown: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PreflightStatus {
    pub label: String,
    pub tone: String,
    pub detail: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PreflightRegistryBoundary {
    pub current_exposure: String,
    pub requested_profile: String,
    pub minimum_profile_after_registry: String,
    pub applies_registry_change: bool,
    pub requires_separate_registry_change: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PreflightSafetyBoundary {
    pub read_only: bool,
    pub input_mode: String,
    pub mutation_surface: String,
    pub no_host_path: bool,
    pub no_live_runtime: bool,
    pub no_gui_capture: bool,
    pub allowed_capabilities: Vec<String>,
    pub disallowed_capabilities: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PreflightCheckRow {
    pub label: String,
    pub verdict: String,
    pub required: bool,
    pub tone: String,
    pub evidence: String,
}

pub fn build_readonly_bridge_wrapper_preflight_report() -> ReadOnlyBridgeWrapperPreflightReport {
    let descriptor = build_readonly_bridge_wrapper_descriptor();
    let dry_run = build_readonly_bridge_wrapper_exposure_dry_run();
    build_readonly_bridge_wrapper_preflight_report_from_parts(&descriptor, &dry_run)
}

pub fn build_readonly_bridge_wrapper_preflight_report_from_parts(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    dry_run: &ReadOnlyBridgeWrapperExposureDryRun,
) -> ReadOnlyBridgeWrapperPreflightReport {
    let mut check_rows = vec![preflight_consistency_check(descriptor, dry_run)];
    check_rows.extend(dry_run.checks.iter().map(check_row));
    let verdict = preflight_verdict(&check_rows);
    let status = preflight_status(&verdict);
    let registry_boundary = registry_boundary(descriptor, dry_run);
    let safety_boundary = safety_boundary(descriptor);
    let guidance = preflight_guidance(&verdict, dry_run);
    let report_markdown = render_preflight_report(
        descriptor,
        dry_run,
        &status,
        &registry_boundary,
        &safety_boundary,
        &check_rows,
        &guidance,
    );

    ReadOnlyBridgeWrapperPreflightReport {
        schema: LSWR_READONLY_BRIDGE_WRAPPER_PREFLIGHT_REPORT_SCHEMA.to_string(),
        descriptor_schema: descriptor.schema.clone(),
        dry_run_schema: dry_run.schema.clone(),
        wrapper_name: descriptor.wrapper_name.clone(),
        verdict,
        status,
        registry_boundary,
        safety_boundary,
        check_rows,
        guidance,
        report_markdown,
    }
}

pub fn render_preflight_report(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    dry_run: &ReadOnlyBridgeWrapperExposureDryRun,
    status: &PreflightStatus,
    registry_boundary: &PreflightRegistryBoundary,
    safety_boundary: &PreflightSafetyBoundary,
    check_rows: &[PreflightCheckRow],
    guidance: &[String],
) -> String {
    let mut report = String::new();
    report.push_str("# LSWR Read-Only Bridge Wrapper Preflight\n\n");
    report.push_str(&format!("Status: {} ({})\n\n", status.label, status.tone));
    report.push_str("## Boundary\n\n");
    report.push_str(&format!("- Wrapper: `{}`\n", descriptor.wrapper_name));
    report.push_str(&format!(
        "- Requested tool: `{}`\n",
        dry_run.requested_tool_name
    ));
    report.push_str(&format!(
        "- Requested profile: `{}`\n",
        dry_run.requested_profile
    ));
    report.push_str(&format!(
        "- Current exposure: `{}`\n",
        registry_boundary.current_exposure
    ));
    report.push_str(&format!(
        "- Applies registry change: `{}`\n",
        bool_text(registry_boundary.applies_registry_change)
    ));
    report.push_str(&format!(
        "- Separate registry change required: `{}`\n\n",
        bool_text(registry_boundary.requires_separate_registry_change)
    ));

    report.push_str("## Safety\n\n");
    report.push_str(&format!(
        "- Read-only: `{}`\n",
        bool_text(safety_boundary.read_only)
    ));
    report.push_str(&format!("- Input mode: `{}`\n", safety_boundary.input_mode));
    report.push_str(&format!(
        "- Mutation surface: `{}`\n",
        safety_boundary.mutation_surface
    ));
    report.push_str(&format!(
        "- Host path / live runtime / GUI capture: `{}` / `{}` / `{}`\n\n",
        bool_text(!safety_boundary.no_host_path),
        bool_text(!safety_boundary.no_live_runtime),
        bool_text(!safety_boundary.no_gui_capture)
    ));

    report.push_str("## Checks\n\n");
    for row in check_rows {
        report.push_str(&format!(
            "- `{}`: `{}` ({}) - {}\n",
            row.label, row.verdict, row.tone, row.evidence
        ));
    }

    report.push_str("\n## Guidance\n\n");
    for item in guidance {
        report.push_str(&format!("- {}\n", item));
    }

    report
}

fn preflight_consistency_check(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    dry_run: &ReadOnlyBridgeWrapperExposureDryRun,
) -> PreflightCheckRow {
    let ok = dry_run.descriptor_schema == descriptor.schema
        && dry_run.wrapper_name == descriptor.wrapper_name
        && dry_run.requested_tool_name == descriptor.profile_gate.candidate_tool_name
        && !dry_run.applies_registry_change;

    PreflightCheckRow {
        label: "preflight_consistency".to_string(),
        verdict: verdict_text(ok).to_string(),
        required: true,
        tone: tone_for_verdict(verdict_text(ok)).to_string(),
        evidence: format!(
            "descriptor_schema_match={}, wrapper_match={}, requested_tool_match={}, applies_registry_change={}",
            bool_text(dry_run.descriptor_schema == descriptor.schema),
            bool_text(dry_run.wrapper_name == descriptor.wrapper_name),
            bool_text(dry_run.requested_tool_name == descriptor.profile_gate.candidate_tool_name),
            bool_text(dry_run.applies_registry_change)
        ),
    }
}

fn check_row(check: &WrapperExposureCheck) -> PreflightCheckRow {
    PreflightCheckRow {
        label: check.check.clone(),
        verdict: check.verdict.clone(),
        required: check.required,
        tone: tone_for_verdict(&check.verdict).to_string(),
        evidence: check.evidence.clone(),
    }
}

fn preflight_verdict(check_rows: &[PreflightCheckRow]) -> String {
    if check_rows
        .iter()
        .any(|row| row.required && row.verdict == "failed")
    {
        "blocked".to_string()
    } else {
        "ready_for_registry_review".to_string()
    }
}

fn preflight_status(verdict: &str) -> PreflightStatus {
    match verdict {
        "ready_for_registry_review" => PreflightStatus {
            label: "Ready for separate registry review".to_string(),
            tone: "success".to_string(),
            detail:
                "Descriptor and dry-run agree; no registry mutation has been applied in this slice."
                    .to_string(),
        },
        _ => PreflightStatus {
            label: "Blocked before registry review".to_string(),
            tone: "danger".to_string(),
            detail: "One or more required preflight checks failed; keep the registry unchanged."
                .to_string(),
        },
    }
}

fn registry_boundary(
    descriptor: &ReadOnlyBridgeWrapperDescriptor,
    dry_run: &ReadOnlyBridgeWrapperExposureDryRun,
) -> PreflightRegistryBoundary {
    PreflightRegistryBoundary {
        current_exposure: descriptor.profile_gate.current_exposure.clone(),
        requested_profile: dry_run.requested_profile.clone(),
        minimum_profile_after_registry: descriptor
            .profile_gate
            .minimum_profile_after_registry
            .clone(),
        applies_registry_change: dry_run.applies_registry_change,
        requires_separate_registry_change: descriptor
            .profile_gate
            .requires_separate_registry_change,
    }
}

fn safety_boundary(descriptor: &ReadOnlyBridgeWrapperDescriptor) -> PreflightSafetyBoundary {
    PreflightSafetyBoundary {
        read_only: descriptor.safety_contract.read_only,
        input_mode: descriptor.input_contract.mode.clone(),
        mutation_surface: descriptor.safety_contract.mutation_surface.clone(),
        no_host_path: !descriptor.input_contract.accepts_host_path,
        no_live_runtime: !descriptor.input_contract.accepts_live_runtime,
        no_gui_capture: !descriptor.input_contract.accepts_gui_capture,
        allowed_capabilities: descriptor.safety_contract.allowed_capabilities.clone(),
        disallowed_capabilities: descriptor.safety_contract.disallowed_capabilities.clone(),
    }
}

fn preflight_guidance(verdict: &str, dry_run: &ReadOnlyBridgeWrapperExposureDryRun) -> Vec<String> {
    match verdict {
        "ready_for_registry_review" => vec![
            "Preflight is ready for a separate, explicit MCP registry review slice.".to_string(),
            "Do not reuse this report as proof that a real tool is already registered.".to_string(),
            "When opening registry work, preserve the dry-run rejection cases as profile/tool-policy tests.".to_string(),
        ],
        _ => {
            let mut guidance = vec![
                "Preflight is blocked; keep MCP registry unchanged.".to_string(),
                "Fix failed checks and regenerate the descriptor/dry-run pair before registry review."
                    .to_string(),
            ];
            guidance.extend(dry_run.guidance.clone());
            guidance
        }
    }
}

fn verdict_text(ok: bool) -> &'static str {
    if ok { "passed" } else { "failed" }
}

fn tone_for_verdict(verdict: &str) -> &'static str {
    match verdict {
        "passed" => "success",
        _ => "danger",
    }
}

fn bool_text(value: bool) -> &'static str {
    if value { "true" } else { "false" }
}
