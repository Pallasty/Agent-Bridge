//! Read-only preflight for the owner's loss-tolerant Resident policy.
//!
//! This policy records the owner's explicit acceptance of privacy exposure and
//! recoverable failures. It does not revise the stricter M1-B0 conclusion:
//! `strict_profile_admitted` therefore remains false. Admission under this
//! separate policy requires only evidence that the remaining irreversible-host-
//! damage boundary is present: a trusted fixed bubblewrap executable, a regular
//! provider file whose content matches the AB-pinned digest, and a compiled
//! invocation contract that makes outer-host persistence read-only and grants
//! no external mutation authority.
//!
//! The preflight never starts the provider, reads authentication material, or
//! writes Resident state. Its serializable report deliberately contains no
//! caller-supplied path.

use ab_agent::resident_codex::RESIDENT_CODEX_NATIVE_SHA256_V0;
use ab_agent::ResidentCodexInvocationContract;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs;
#[cfg(unix)]
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::path::Path;

pub const RESIDENT_RISK_PREFLIGHT_SCHEMA_V0: &str =
    "agent_bridge.resident_xiaoshu.risk_preflight.v0";
pub const RESIDENT_OWNER_RISK_POLICY_ID: &str = "loss_tolerant_irreversible_damage_v0";
pub const RESIDENT_OWNER_LOSS_TOLERANT_NOT_ADMITTED: &str =
    "resident_live_provider_not_admitted_by_owner_loss_tolerant_policy";

const BWRAP_PATH: &str = "/usr/bin/bwrap";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentRiskDisposition {
    /// The owner explicitly accepts this risk under the named policy.
    Accepted,
    /// A bounded control reduces this risk to the owner's admitted boundary.
    Mitigated,
    /// Positive evidence is mandatory for live admission.
    Required,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ResidentRiskEvidenceState {
    Accepted,
    Satisfied,
    Blocked,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentRiskRequirement {
    pub original_strict_requirement: &'static str,
    pub disposition: ResidentRiskDisposition,
    pub state: ResidentRiskEvidenceState,
    pub evidence: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentRiskPreflightEffects {
    pub provider_started: bool,
    pub provider_transport_opened: bool,
    pub authentication_material_read: bool,
    pub resident_state_written: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(deny_unknown_fields)]
pub struct ResidentRiskPreflightReport {
    pub schema_version: &'static str,
    pub policy_id: &'static str,
    pub privacy_constraint_waived: bool,
    pub recoverable_failure_accepted: bool,
    /// The old strict policy remains unadmitted; this field is never derived
    /// from the separate owner policy.
    pub strict_profile_admitted: bool,
    pub owner_loss_tolerant_profile_admitted: bool,
    pub trusted_fixed_bwrap: bool,
    pub provider_is_regular_file: bool,
    pub provider_content_sha256_matches_pin: bool,
    pub outer_host_persistence_read_only: bool,
    pub external_mutation_authority_absent: bool,
    pub requirements: Vec<ResidentRiskRequirement>,
    pub accepted_risks: Vec<&'static str>,
    pub remaining_blockers: Vec<&'static str>,
    pub effects: ResidentRiskPreflightEffects,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct BwrapObservation {
    regular_file: bool,
    root_owned: bool,
    group_or_world_writable: bool,
}

impl BwrapObservation {
    fn trusted(self) -> bool {
        self.regular_file && self.root_owned && !self.group_or_world_writable
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct ProviderObservation {
    regular_file: bool,
    sha256_matches_pin: bool,
}

/// Inspect the fixed local isolation primitive, the selected provider file,
/// and the compiled invocation contract without producing external effects.
pub fn resident_risk_preflight(provider_path: &Path) -> ResidentRiskPreflightReport {
    let contract = ResidentCodexInvocationContract::default();
    build_report(
        observe_bwrap(Path::new(BWRAP_PATH)),
        observe_provider(provider_path, RESIDENT_CODEX_NATIVE_SHA256_V0),
        &contract,
    )
}

/// Admit live cognition under the owner's explicit loss-tolerant policy only.
/// This does not make, imply, or mutate strict M1-B0 admission.
pub fn require_owner_loss_tolerant_admission(provider_path: &Path) -> Result<(), &'static str> {
    resident_risk_preflight(provider_path)
        .owner_loss_tolerant_profile_admitted
        .then_some(())
        .ok_or(RESIDENT_OWNER_LOSS_TOLERANT_NOT_ADMITTED)
}

/// Render the path-free admission evidence used by the operator CLI.
pub fn render_resident_risk_preflight(report: &ResidentRiskPreflightReport) -> String {
    let blockers = if report.remaining_blockers.is_empty() {
        "none".to_string()
    } else {
        report.remaining_blockers.join(",")
    };
    format!(
        "Resident risk preflight\n\
         policy={}\n\
         owner_loss_tolerant_admitted={}; strict_profile_admitted={}\n\
         trusted_fixed_bwrap={}\n\
         provider_regular_file={}; provider_sha256_matches_pin={}\n\
         outer_host_persistence_read_only={}; external_mutation_authority_absent={}\n\
         remaining_blockers={}\n\
         effects: provider_started={}; provider_transport_opened={}; authentication_material_read={}; resident_state_written={}",
        report.policy_id,
        report.owner_loss_tolerant_profile_admitted,
        report.strict_profile_admitted,
        report.trusted_fixed_bwrap,
        report.provider_is_regular_file,
        report.provider_content_sha256_matches_pin,
        report.outer_host_persistence_read_only,
        report.external_mutation_authority_absent,
        blockers,
        report.effects.provider_started,
        report.effects.provider_transport_opened,
        report.effects.authentication_material_read,
        report.effects.resident_state_written,
    )
}

fn build_report(
    bwrap: BwrapObservation,
    provider: ProviderObservation,
    contract: &ResidentCodexInvocationContract,
) -> ResidentRiskPreflightReport {
    let trusted_fixed_bwrap = bwrap.trusted();
    let outer_host_persistence_read_only = contract.outer_host_filesystem == "read_only";
    let external_mutation_authority_absent = !contract.external_mutation_authority;

    let irreversible_host_damage_boundary = trusted_fixed_bwrap
        && outer_host_persistence_read_only
        && external_mutation_authority_absent;
    let pinned_provider = provider.regular_file && provider.sha256_matches_pin;
    let owner_loss_tolerant_profile_admitted = irreversible_host_damage_boundary && pinned_provider;

    let requirements = vec![
        ResidentRiskRequirement {
            original_strict_requirement: "positive_empty_model_tool_manifest",
            disposition: ResidentRiskDisposition::Mitigated,
            state: if external_mutation_authority_absent {
                ResidentRiskEvidenceState::Satisfied
            } else {
                ResidentRiskEvidenceState::Blocked
            },
            evidence: if external_mutation_authority_absent {
                "privacy and read-only tool-surface exposure are accepted, while the compiled contract denies irreversible external mutation authority"
            } else {
                "a positive empty-tool manifest is waived only when the compiled contract denies external mutation authority"
            },
        },
        accepted_requirement(
            "provider_transport_tool_plane_separation",
            "strict transport-separation proof is not required for privacy, while external mutation remains separately prohibited",
        ),
        accepted_requirement(
            "credential_broker_isolation",
            "credential secrecy is waived, but the implementation retains its minimal account-authority envelope",
        ),
        ResidentRiskRequirement {
            original_strict_requirement: "minimal_provider_mount_and_seccomp_policy",
            disposition: ResidentRiskDisposition::Mitigated,
            state: if irreversible_host_damage_boundary {
                ResidentRiskEvidenceState::Satisfied
            } else {
                ResidentRiskEvidenceState::Blocked
            },
            evidence: if irreversible_host_damage_boundary {
                "trusted fixed bubblewrap plus compiled read-only outer-host persistence and no external mutation authority bound irreversible host damage"
            } else {
                "the trusted bubblewrap and compiled outer-host persistence boundary is incomplete"
            },
        },
        accepted_requirement(
            "complete_local_process_set_custody",
            "crash, timeout, orphan, and resource-loss outcomes are accepted when recoverable",
        ),
        ResidentRiskRequirement {
            original_strict_requirement: "pinned_provider_executable",
            disposition: ResidentRiskDisposition::Required,
            state: if pinned_provider {
                ResidentRiskEvidenceState::Satisfied
            } else {
                ResidentRiskEvidenceState::Blocked
            },
            evidence: if pinned_provider {
                "the selected provider is a regular file whose content matches the AB-pinned SHA-256"
            } else {
                "the selected provider is not a regular file or its content does not match the AB-pinned SHA-256"
            },
        },
        accepted_requirement(
            "subject_fenced_durable_continuity_transaction",
            "replay, continuity rollback, and recoverable state loss are explicitly accepted",
        ),
    ];

    let mut remaining_blockers = Vec::new();
    if !trusted_fixed_bwrap {
        remaining_blockers.push("fixed_bwrap_not_trusted");
    }
    if !provider.regular_file {
        remaining_blockers.push("provider_is_not_a_regular_file");
    }
    if !provider.sha256_matches_pin {
        remaining_blockers.push("provider_content_sha256_does_not_match_pin");
    }
    if !outer_host_persistence_read_only {
        remaining_blockers.push("outer_host_persistence_is_not_read_only");
    }
    if !external_mutation_authority_absent {
        remaining_blockers.push("external_mutation_authority_is_present");
    }

    ResidentRiskPreflightReport {
        schema_version: RESIDENT_RISK_PREFLIGHT_SCHEMA_V0,
        policy_id: RESIDENT_OWNER_RISK_POLICY_ID,
        privacy_constraint_waived: true,
        recoverable_failure_accepted: true,
        strict_profile_admitted: false,
        owner_loss_tolerant_profile_admitted,
        trusted_fixed_bwrap,
        provider_is_regular_file: provider.regular_file,
        provider_content_sha256_matches_pin: provider.sha256_matches_pin,
        outer_host_persistence_read_only,
        external_mutation_authority_absent,
        requirements,
        accepted_risks: vec![
            "model_tool_surface_privacy_or_read_only_exposure_accepted",
            "strict_provider_transport_separation_proof_not_required",
            "strict_credential_broker_proof_not_required",
            "recoverable_process_loss_or_orphan_possible",
            "recoverable_continuity_replay_or_rollback_possible",
        ],
        remaining_blockers,
        effects: ResidentRiskPreflightEffects {
            provider_started: false,
            provider_transport_opened: false,
            authentication_material_read: false,
            resident_state_written: false,
        },
    }
}

fn accepted_requirement(
    original_strict_requirement: &'static str,
    evidence: &'static str,
) -> ResidentRiskRequirement {
    ResidentRiskRequirement {
        original_strict_requirement,
        disposition: ResidentRiskDisposition::Accepted,
        state: ResidentRiskEvidenceState::Accepted,
        evidence,
    }
}

#[cfg(unix)]
fn observe_bwrap(path: &Path) -> BwrapObservation {
    let Ok(metadata) = fs::symlink_metadata(path) else {
        return BwrapObservation {
            regular_file: false,
            root_owned: false,
            group_or_world_writable: true,
        };
    };
    BwrapObservation {
        regular_file: metadata.file_type().is_file(),
        root_owned: metadata.uid() == 0,
        group_or_world_writable: metadata.permissions().mode() & 0o022 != 0,
    }
}

#[cfg(not(unix))]
fn observe_bwrap(_path: &Path) -> BwrapObservation {
    BwrapObservation {
        regular_file: false,
        root_owned: false,
        group_or_world_writable: true,
    }
}

fn observe_provider(path: &Path, expected_sha256: &str) -> ProviderObservation {
    let Ok(metadata) = fs::symlink_metadata(path) else {
        return ProviderObservation {
            regular_file: false,
            sha256_matches_pin: false,
        };
    };
    if !metadata.file_type().is_file() {
        return ProviderObservation {
            regular_file: false,
            sha256_matches_pin: false,
        };
    }
    let sha256_matches_pin = fs::read(path)
        .map(|bytes| sha256_hex(&bytes) == expected_sha256)
        .unwrap_or(false);
    ProviderObservation {
        regular_file: true,
        sha256_matches_pin,
    }
}

fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::symlink;
    use tempfile::tempdir;

    fn admitted_contract() -> ResidentCodexInvocationContract {
        let contract = ResidentCodexInvocationContract::default();
        assert_eq!(contract.outer_host_filesystem, "read_only");
        assert!(!contract.external_mutation_authority);
        contract
    }

    fn trusted_bwrap() -> BwrapObservation {
        BwrapObservation {
            regular_file: true,
            root_owned: true,
            group_or_world_writable: false,
        }
    }

    fn report_for_fixture(path: &Path, expected_sha256: &str) -> ResidentRiskPreflightReport {
        build_report(
            trusted_bwrap(),
            observe_provider(path, expected_sha256),
            &admitted_contract(),
        )
    }

    #[test]
    fn matching_dynamic_fixture_admits_only_the_owner_policy() {
        let temporary = tempdir().unwrap();
        let provider = temporary.path().join("provider");
        let content = b"test-only dynamically pinned provider";
        fs::write(&provider, content).unwrap();

        let report = report_for_fixture(&provider, &sha256_hex(content));
        assert!(report.owner_loss_tolerant_profile_admitted);
        assert!(!report.strict_profile_admitted);
        assert!(report.remaining_blockers.is_empty());
        assert_eq!(report.policy_id, "loss_tolerant_irreversible_damage_v0");
        assert!(report.privacy_constraint_waived);
        assert!(report.recoverable_failure_accepted);
        assert!(!report.effects.provider_started);
        assert!(!report.effects.provider_transport_opened);
        assert!(!report.effects.authentication_material_read);
        assert!(!report.effects.resident_state_written);
    }

    #[test]
    fn provider_hash_mismatch_blocks_admission() {
        let temporary = tempdir().unwrap();
        let provider = temporary.path().join("provider");
        fs::write(&provider, b"unexpected provider").unwrap();

        let report = report_for_fixture(&provider, &sha256_hex(b"expected provider"));
        assert!(!report.owner_loss_tolerant_profile_admitted);
        assert!(report
            .remaining_blockers
            .contains(&"provider_content_sha256_does_not_match_pin"));
    }

    #[test]
    fn symlink_and_non_file_provider_are_rejected() {
        let temporary = tempdir().unwrap();
        let target = temporary.path().join("target");
        let link = temporary.path().join("provider-link");
        fs::write(&target, b"provider").unwrap();
        symlink(&target, &link).unwrap();

        for path in [&link, temporary.path()] {
            let report = report_for_fixture(path, &sha256_hex(b"provider"));
            assert!(!report.owner_loss_tolerant_profile_admitted);
            assert!(!report.provider_is_regular_file);
            assert!(report
                .remaining_blockers
                .contains(&"provider_is_not_a_regular_file"));
        }
    }

    #[test]
    fn every_bwrap_precondition_is_mandatory() {
        let provider = ProviderObservation {
            regular_file: true,
            sha256_matches_pin: true,
        };
        let contract = admitted_contract();
        for bwrap in [
            BwrapObservation {
                regular_file: false,
                ..trusted_bwrap()
            },
            BwrapObservation {
                root_owned: false,
                ..trusted_bwrap()
            },
            BwrapObservation {
                group_or_world_writable: true,
                ..trusted_bwrap()
            },
        ] {
            let report = build_report(bwrap, provider, &contract);
            assert!(!report.owner_loss_tolerant_profile_admitted);
            assert!(report
                .remaining_blockers
                .contains(&"fixed_bwrap_not_trusted"));
        }
    }

    #[test]
    fn compiled_invocation_boundary_is_mandatory() {
        let provider = ProviderObservation {
            regular_file: true,
            sha256_matches_pin: true,
        };

        let mut writable_outer_host = admitted_contract();
        writable_outer_host.outer_host_filesystem = "read_write";
        let report = build_report(trusted_bwrap(), provider, &writable_outer_host);
        assert!(!report.owner_loss_tolerant_profile_admitted);
        assert!(report
            .remaining_blockers
            .contains(&"outer_host_persistence_is_not_read_only"));

        let mut mutation_authority = admitted_contract();
        mutation_authority.external_mutation_authority = true;
        let report = build_report(trusted_bwrap(), provider, &mutation_authority);
        assert!(!report.owner_loss_tolerant_profile_admitted);
        assert!(report
            .remaining_blockers
            .contains(&"external_mutation_authority_is_present"));
    }

    #[test]
    fn accepted_risks_do_not_block_when_required_controls_are_satisfied() {
        let report = build_report(
            trusted_bwrap(),
            ProviderObservation {
                regular_file: true,
                sha256_matches_pin: true,
            },
            &admitted_contract(),
        );

        assert_eq!(report.requirements.len(), 7);
        assert_eq!(
            report
                .requirements
                .iter()
                .filter(|requirement| {
                    requirement.disposition == ResidentRiskDisposition::Accepted
                })
                .count(),
            4
        );
        assert_eq!(
            report
                .requirements
                .iter()
                .filter(|requirement| {
                    requirement.disposition == ResidentRiskDisposition::Mitigated
                })
                .count(),
            2
        );
        assert_eq!(
            report
                .requirements
                .iter()
                .filter(|requirement| {
                    requirement.disposition == ResidentRiskDisposition::Required
                })
                .count(),
            1
        );
        assert!(report.owner_loss_tolerant_profile_admitted);
        assert!(report.accepted_risks.len() >= 4);
        assert!(report.remaining_blockers.is_empty());
    }

    #[test]
    fn serialized_report_never_contains_the_provider_path() {
        let temporary = tempdir().unwrap();
        let private_component = "owner-secret-provider-location";
        let provider = temporary.path().join(private_component);
        let content = b"provider";
        fs::write(&provider, content).unwrap();

        let serialized =
            serde_json::to_string(&report_for_fixture(&provider, &sha256_hex(content))).unwrap();
        assert!(!serialized.contains(private_component));
        assert!(!serialized.contains(&temporary.path().display().to_string()));
    }

    #[test]
    fn human_renderer_is_deterministic_and_path_free() {
        let temporary = tempdir().unwrap();
        let private_component = "private-provider-location-for-renderer";
        let provider = temporary.path().join(private_component);
        let content = b"provider";
        fs::write(&provider, content).unwrap();
        let report = report_for_fixture(&provider, &sha256_hex(content));

        let rendered = render_resident_risk_preflight(&report);
        assert_eq!(
            rendered,
            "Resident risk preflight\n\
             policy=loss_tolerant_irreversible_damage_v0\n\
             owner_loss_tolerant_admitted=true; strict_profile_admitted=false\n\
             trusted_fixed_bwrap=true\n\
             provider_regular_file=true; provider_sha256_matches_pin=true\n\
             outer_host_persistence_read_only=true; external_mutation_authority_absent=true\n\
             remaining_blockers=none\n\
             effects: provider_started=false; provider_transport_opened=false; authentication_material_read=false; resident_state_written=false"
        );
        assert!(!rendered.contains(private_component));
        assert!(!rendered.contains(&temporary.path().display().to_string()));
    }
}
