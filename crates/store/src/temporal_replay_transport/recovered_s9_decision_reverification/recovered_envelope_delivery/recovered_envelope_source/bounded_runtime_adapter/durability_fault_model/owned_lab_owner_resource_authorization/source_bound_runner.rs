//! S19 private source-bound owned-lab controller and single-use claim kernel.
//!
//! This module is deliberately default-off and private below the S18 owner
//! authorization verifier.  It can consume the S18 opaque verified output,
//! but it has no public runtime caller and contains no process, signal, mount,
//! network, credential, or Agent-Bridge application effect adapter.  The only
//! durable I/O exercised by its tests is an isolated synthetic SQLite claim
//! ledger below the release gate scratch directory.

#![cfg_attr(not(test), allow(dead_code))]

#[cfg(feature = "temporal-evidence-s20-owned-lab-trusted-controller-orchestration-synthetic")]
mod trusted_controller_orchestration;

use super::*;
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::Path;
use std::rc::Rc;
use tokio_rusqlite::rusqlite::{self, params, Connection, OpenFlags};

const S19_MANIFEST_SCHEMA: &str = "agent_bridge.memory_temporal_owned_lab_subject_manifest_s19.v0";
const S19_MANIFEST_PACKET_KIND: &str = "S19_OWNER_REVIEW_SUBJECT_MANIFEST";
const S19_SYNTHETIC_MANIFEST_STATE: &str = "SYNTHETIC_KAT_NON_LIVE_SUBJECT";
const S19_UNSIGNED_MANIFEST_STATE: &str = "FROZEN_UNSIGNED_S19_NON_LIVE_SUBJECT";
const S19_CANONICAL_PROFILE: &str =
    "AB_RESTRICTED_CANONICAL_JSON_S19_V1_COMPACT_SORTED_KEYS_ASCII_VALUES_NO_FLOAT";
const S18_SOURCE_COMMIT: &str = "e97406a552e8f664c6576d22a4091e221d4e356b";
const S18_INTEGRATION_COMMIT: &str = "85f686dde161f25166b8f38c38b9a05bd7957bfd";
const S18_CONTRACT_SHA256: &str =
    "034918f67efea4487dfc28bff7830251dff71e6218317157efae106d07aa8f56";
const S18_SUCCESSOR_SHA256: &str =
    "3a2c446f3dfa4bad343c9ed582712a7c72135860d0a9eda2d4e64a1886e2f675";
const S18_OWNER_SCHEMA_SHA256: &str =
    "cb31843865d12c183b37c65d9d5ffae39a7f42bb8a7f4be2fd4f90c099548e6b";
const S18_ANCHOR_SCHEMA_SHA256: &str =
    "648d7f09dc430675707583e5be85adeb95209f8e26bbae7aad4fad08fbf7350b";
const S18_VERIFIER_SOURCE_SHA256: &str =
    "17af73a6c7793f53372ec15713afa7e329ce8cb001e4b9570bdbb1f0e982c2f6";
const CLAIM_TRANSITION: &str = "UNCLAIMED_TO_CONSUMED_FOR_EXACT_RUN";
const STOP_CLEAR: &str = "CLEAR";
const STOP_TRIGGERED: &str = "TRIGGERED";
const CLAIM_UNCLAIMED: &str = "AUTHORIZED_UNCLAIMED";
const CLAIM_CONSUMED: &str = "CONSUMED_FOR_EXACT_RUN";
const AUTHORITY_CONTROL_APPLICATION_ID: i64 = 1_094_865_689;
const AUTHORITY_CONTROL_USER_VERSION: i64 = 19;
const CLAIM_RECEIPT_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s19/claim-receipt/v1";
const CONTROL_SNAPSHOT_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s19/control-snapshot/v1";
const PREFLIGHT_RECEIPT_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s19/preflight-receipt/v1";
const PERMIT_DOMAIN: &[u8] = b"agent-bridge/biocortex/owned-lab/s19/affine-permit/v1";
const SQLITE_SCHEMA_CATALOG_DOMAIN: &[u8] =
    b"agent-bridge/biocortex/owned-lab/s19/sqlite-schema-catalog/v1";
const SQLITE_PROFILE_V1: &[u8] = b"journal_mode=DELETE;synchronous=EXTRA;temp_store=FILE;mmap_size=0;cache_size=-2048;foreign_keys=ON;trusted_schema=OFF;application_id=1094865689;user_version=19;file_mode=0600;nlink=1;nofollow=true";
const SQLITE_SCHEMA_CATALOG_SHA256: &str =
    "32559198f29827fc9f7a37d100520d7a5685ff99b3d9d40ac91baf9eba965110";

const TOP_LEVEL_KEYS: &[&str] = &[
    "artifact_bindings",
    "build_identity",
    "canonicalization",
    "claim_protocol",
    "control_protocol",
    "experiment_scope",
    "lab_environment",
    "manifest_state",
    "nonclaims",
    "packet_kind",
    "receipt_bindings",
    "safety_policy",
    "schema",
    "test_only",
    "validators",
];
const COMPONENT_KEYS: &[&str] = &[
    "binary_sha256",
    "ruleset_sha256",
    "source_sha256",
    "toolchain_sha256",
];
const VALIDATOR_KEYS: &[&str] = &[
    "live_observation",
    "manifest",
    "owner_authorization",
    "receipt",
];
const BUILD_IDENTITY_KEYS: &[&str] = &[
    "build_profile_sha256",
    "cargo_lock_sha256",
    "controller_binary_sha256",
    "controller_source_sha256",
    "expected_binding_builder_binary_sha256",
    "expected_binding_builder_ruleset_sha256",
    "expected_binding_builder_source_sha256",
    "expected_binding_builder_toolchain_sha256",
    "feature_set_sha256",
    "manifest_builder_binary_sha256",
    "manifest_builder_ruleset_sha256",
    "manifest_builder_source_sha256",
    "manifest_builder_toolchain_sha256",
    "runner_binary_sha256",
    "runner_source_commit",
    "runner_source_sha256",
    "runner_toolchain_sha256",
    "s18_integration_commit",
    "s19_integration_commit",
    "s19_integration_tree",
    "s19_source_commit",
    "s19_source_tree",
    "subject_manifest_schema_sha256",
    "target_triple_sha256",
    "toolchain_manifest_sha256",
];
const ARTIFACT_KEYS: &[&str] = &[
    "assignment_set_sha256",
    "catalog_row_count",
    "catalog_sha256",
    "classifier_binary_sha256",
    "classifier_source_sha256",
    "control_protocol_sha256",
    "expected_oracle_sha256",
    "positive_owner_schema_sha256",
    "s17_observation_schema_sha256",
    "s17_plan_sha256",
    "s18_contract_sha256",
    "s18_owner_trust_anchor_schema_sha256",
    "s18_owner_verifier_source_sha256",
    "s18_successor_gate_sha256",
    "schedule_sha256",
    "sqlite_application_id",
    "sqlite_profile_sha256",
    "sqlite_schema_sha256",
    "sqlite_user_version",
    "target_phase_count",
    "target_phase_unique_match_count",
];
const EXPERIMENT_SCOPE_KEYS: &[&str] = &[
    "assigned_attempt_count",
    "authorized_family_ids",
    "authorized_family_scenario_counts",
    "canary_batch_count",
    "claim_level",
    "family_id_namespace",
    "planned_distinct_fresh_exec_read_count",
    "planned_pidfd_sigkill_attempt_count",
    "planned_total_s16_mapping_phase_record_count",
    "repetition_count",
    "rerun_requires_new_assignment_and_owner_decision",
    "retry_or_implicit_rerun_allowed",
];
const LAB_ENVIRONMENT_KEYS: &[&str] = &[
    "attempt_timeout_seconds",
    "batch_timeout_seconds",
    "boot_id_sha256",
    "build_jobs",
    "candidate_device_identity_sha256",
    "candidate_device_path",
    "candidate_filesystem",
    "candidate_root",
    "cut_ready_timeout_seconds",
    "death_confirmation_timeout_seconds",
    "disk_max_bytes",
    "fresh_exec_timeout_seconds",
    "kernel_identity_sha256",
    "maximum_active_assigned_attempts",
    "maximum_child_processes",
    "maximum_controller_processes",
    "maximum_open_files",
    "maximum_tasks",
    "memory_max_bytes",
    "mount_identity_sha256",
    "mount_options_sha256",
    "mount_point",
    "nested_cargo_allowed",
    "parent_directory_fsync_required",
    "pidfd_signal_timeout_seconds",
    "proposed_cost_ceiling_usd",
    "root_parent_device_inode_sha256",
    "run_root_create_mode",
    "run_root_derivation_profile",
    "run_root_must_not_preexist",
    "same_boot_required",
    "sqlite_database_file_fsync_required",
    "sqlite_journal_mode",
    "sqlite_reopen_mode",
    "sqlite_setup_mode",
    "sqlite_synchronous",
    "swap_max_bytes",
];
const SAFETY_POLICY_KEYS: &[&str] = &[
    "agent_bridge_application_side_effect_allowed",
    "allowed_operation_ids",
    "batch_invalid_on_any_oom",
    "batch_invalid_on_timeout_or_leaked_child",
    "block_device_write_allowed",
    "child_descendants_allowed",
    "cleanup_policy_sha256",
    "credential_access_allowed",
    "drop_caches_allowed",
    "mount_or_unmount_allowed",
    "named_ipc_or_network_control_allowed",
    "network_allowed",
    "numeric_pid_signal_fallback_allowed",
    "paid_resource_allowed",
    "pidfd_identity_recheck_required",
    "pidfd_open_required_before_cut",
    "preflight_policy_sha256",
    "production_access_allowed",
    "provider_access_allowed",
    "reboot_kernel_crash_or_power_fault_allowed",
    "resource_scope_sha256",
    "retention_policy_sha256",
    "review_policy_sha256",
    "root_or_privilege_escalation_allowed",
    "safety_policy_sha256",
    "stop_control_policy_sha256",
];
const CLAIM_PROTOCOL_KEYS: &[&str] = &[
    "affine_permit_cloneable",
    "affine_permit_serializable",
    "authority_control_claim_schema_sha256",
    "authorization_registration_required",
    "cas_failure_allows_automatic_retry",
    "cas_failure_grants_execution",
    "cas_failure_mutates_unclaimed",
    "cas_sql_where_profile",
    "cas_where_required_bindings",
    "claim_implementation_binary_sha256",
    "claim_implementation_source_sha256",
    "claim_implementation_toolchain_sha256",
    "claim_key_derivation_profile",
    "claim_key_sha256",
    "claim_namespace_sha256",
    "claim_receipt_same_transaction",
    "claimed_state",
    "consumed_tombstone_absorbing",
    "consumed_tombstone_deletable",
    "durable_commit_required_before_permit",
    "expected_unclaimed_revision",
    "failed_cas_expected_affected_rows",
    "maximum_successful_claims",
    "missing_row_may_be_created_by_claim",
    "permit_binds_capability_nonce",
    "permit_binds_controller_runner_and_run",
    "single_use_claim_required",
    "successful_cas_expected_affected_rows",
    "successful_claim_then_crash_allows_retry",
    "transition",
    "unclaimed_state",
    "upsert_or_replace_allowed",
];
const CONTROL_PROTOCOL_KEYS: &[&str] = &[
    "absorbing_stop_clear_state",
    "absorbing_stop_triggered_state",
    "anti_rollback_policy_sha256",
    "cas_and_control_reads_same_sqlite_transaction",
    "control_implementation_binary_sha256",
    "control_implementation_source_sha256",
    "control_implementation_toolchain_sha256",
    "control_ledger_identity_sha256",
    "control_snapshot_schema_sha256",
    "current_epoch_source_profile",
    "external_state_is_outside_owner_envelope",
    "missing_or_unknown_control_state_fails_closed",
    "post_claim_pre_start_recheck_required",
    "revocation_epoch_comparison",
    "revocation_epoch_monotonic",
    "revocation_ledger_revision_monotonic",
    "revocation_policy_identity_required",
    "runtime_action_boundary_recheck_required",
    "same_transaction_required_table_ids",
    "stop_ledger_revision_monotonic",
    "stop_policy_identity_required",
    "stop_transition",
    "stop_triggered_is_absorbing",
    "trusted_wall_clock_is_freshness",
];
const RECEIPT_BINDING_KEYS: &[&str] = &[
    "authority_control_claim_schema_sha256",
    "claim_receipt_is_owner_envelope",
    "cleanup_or_custody_receipt_is_owner_envelope",
    "control_snapshot_schema_sha256",
    "post_run_bundle_schema_sha256",
    "post_run_receipts_grant_authority",
    "preflight_receipt_is_owner_envelope",
    "preflight_receipt_schema_sha256",
    "raw_observation_schema_sha256",
    "receipt_hash_domain_profile",
    "receipt_parent_chain",
    "stop_receipt_required_if_triggered",
    "subject_manifest_schema_sha256",
];
const NONCLAIMS_KEYS: &[&str] = &[
    "actual_assigned_attempt_count",
    "actual_cas_claim_count",
    "actual_execution_capability_count",
    "actual_fresh_process_read_count",
    "actual_observation_count",
    "actual_owner_signature_count",
    "actual_owner_trust_anchor_count",
    "actual_runner_launch_count",
    "actual_sigkill_attempt_count",
    "execution_start_permitted",
    "global_runtime_admission",
    "live_root_created",
    "manifest_owner_signed",
    "may_execute_live_canary",
    "owned_lab_execution_authorized",
    "owner_envelope_present",
    "owner_identity_bound",
    "provider_or_production_authority",
    "real_manifest_committed_to_repository",
    "runner_implementation_is_live",
    "s20_admission_satisfied",
    "side_effects_unlocked",
    "single_use_execution_permit_issued",
    "test_fixture_is_owner_authority",
];

#[derive(Clone, Serialize)]
struct ComponentBindingV1 {
    binary_sha256: String,
    ruleset_sha256: String,
    source_sha256: String,
    toolchain_sha256: String,
}

#[derive(Clone, Serialize)]
struct ValidatorBindingsV1 {
    live_observation: ComponentBindingV1,
    manifest: ComponentBindingV1,
    owner_authorization: ComponentBindingV1,
    receipt: ComponentBindingV1,
}

#[derive(Clone, Serialize)]
struct BuildIdentityV1 {
    build_profile_sha256: String,
    cargo_lock_sha256: String,
    controller_binary_sha256: String,
    controller_source_sha256: String,
    expected_binding_builder_binary_sha256: String,
    expected_binding_builder_ruleset_sha256: String,
    expected_binding_builder_source_sha256: String,
    expected_binding_builder_toolchain_sha256: String,
    feature_set_sha256: String,
    manifest_builder_binary_sha256: String,
    manifest_builder_ruleset_sha256: String,
    manifest_builder_source_sha256: String,
    manifest_builder_toolchain_sha256: String,
    runner_binary_sha256: String,
    runner_source_commit: String,
    runner_source_sha256: String,
    runner_toolchain_sha256: String,
    s18_integration_commit: String,
    s19_integration_commit: String,
    s19_integration_tree: String,
    s19_source_commit: String,
    s19_source_tree: String,
    subject_manifest_schema_sha256: String,
    target_triple_sha256: String,
    toolchain_manifest_sha256: String,
}

#[derive(Clone, Serialize)]
struct ArtifactBindingsV1 {
    assignment_set_sha256: String,
    catalog_row_count: u64,
    catalog_sha256: String,
    classifier_binary_sha256: String,
    classifier_source_sha256: String,
    control_protocol_sha256: String,
    expected_oracle_sha256: String,
    positive_owner_schema_sha256: String,
    s17_observation_schema_sha256: String,
    s17_plan_sha256: String,
    s18_contract_sha256: String,
    s18_owner_trust_anchor_schema_sha256: String,
    s18_owner_verifier_source_sha256: String,
    s18_successor_gate_sha256: String,
    schedule_sha256: String,
    sqlite_application_id: u64,
    sqlite_profile_sha256: String,
    sqlite_schema_sha256: String,
    sqlite_user_version: u64,
    target_phase_count: u64,
    target_phase_unique_match_count: u64,
}

#[derive(Clone, Serialize)]
struct ExperimentScopeV1 {
    assigned_attempt_count: u64,
    authorized_family_ids: Vec<String>,
    authorized_family_scenario_counts: BTreeMap<String, u64>,
    canary_batch_count: u64,
    claim_level: String,
    family_id_namespace: String,
    planned_distinct_fresh_exec_read_count: u64,
    planned_pidfd_sigkill_attempt_count: u64,
    planned_total_s16_mapping_phase_record_count: u64,
    repetition_count: u64,
    rerun_requires_new_assignment_and_owner_decision: bool,
    retry_or_implicit_rerun_allowed: bool,
}

#[derive(Clone, Serialize)]
struct LabEnvironmentV1 {
    attempt_timeout_seconds: u64,
    batch_timeout_seconds: u64,
    boot_id_sha256: String,
    build_jobs: u64,
    candidate_device_identity_sha256: String,
    candidate_device_path: String,
    candidate_filesystem: String,
    candidate_root: String,
    cut_ready_timeout_seconds: u64,
    death_confirmation_timeout_seconds: u64,
    disk_max_bytes: u64,
    fresh_exec_timeout_seconds: u64,
    kernel_identity_sha256: String,
    maximum_active_assigned_attempts: u64,
    maximum_child_processes: u64,
    maximum_controller_processes: u64,
    maximum_open_files: u64,
    maximum_tasks: u64,
    memory_max_bytes: u64,
    mount_identity_sha256: String,
    mount_options_sha256: String,
    mount_point: String,
    nested_cargo_allowed: bool,
    parent_directory_fsync_required: bool,
    pidfd_signal_timeout_seconds: u64,
    proposed_cost_ceiling_usd: u64,
    root_parent_device_inode_sha256: String,
    run_root_create_mode: String,
    run_root_derivation_profile: String,
    run_root_must_not_preexist: bool,
    same_boot_required: bool,
    sqlite_database_file_fsync_required: bool,
    sqlite_journal_mode: String,
    sqlite_reopen_mode: String,
    sqlite_setup_mode: String,
    sqlite_synchronous: String,
    swap_max_bytes: u64,
}

#[derive(Clone, Serialize)]
struct SafetyPolicyV1 {
    agent_bridge_application_side_effect_allowed: bool,
    allowed_operation_ids: Vec<String>,
    batch_invalid_on_any_oom: bool,
    batch_invalid_on_timeout_or_leaked_child: bool,
    block_device_write_allowed: bool,
    child_descendants_allowed: bool,
    cleanup_policy_sha256: String,
    credential_access_allowed: bool,
    drop_caches_allowed: bool,
    mount_or_unmount_allowed: bool,
    named_ipc_or_network_control_allowed: bool,
    network_allowed: bool,
    numeric_pid_signal_fallback_allowed: bool,
    paid_resource_allowed: bool,
    pidfd_identity_recheck_required: bool,
    pidfd_open_required_before_cut: bool,
    preflight_policy_sha256: String,
    production_access_allowed: bool,
    provider_access_allowed: bool,
    reboot_kernel_crash_or_power_fault_allowed: bool,
    resource_scope_sha256: String,
    retention_policy_sha256: String,
    review_policy_sha256: String,
    root_or_privilege_escalation_allowed: bool,
    safety_policy_sha256: String,
    stop_control_policy_sha256: String,
}

#[derive(Clone, Serialize)]
struct ClaimProtocolV1 {
    affine_permit_cloneable: bool,
    affine_permit_serializable: bool,
    authority_control_claim_schema_sha256: String,
    authorization_registration_required: bool,
    cas_failure_allows_automatic_retry: bool,
    cas_failure_grants_execution: bool,
    cas_failure_mutates_unclaimed: bool,
    cas_sql_where_profile: String,
    cas_where_required_bindings: Vec<String>,
    claim_implementation_binary_sha256: String,
    claim_implementation_source_sha256: String,
    claim_implementation_toolchain_sha256: String,
    claim_key_derivation_profile: String,
    claim_key_sha256: String,
    claim_namespace_sha256: String,
    claim_receipt_same_transaction: bool,
    claimed_state: String,
    consumed_tombstone_absorbing: bool,
    consumed_tombstone_deletable: bool,
    durable_commit_required_before_permit: bool,
    expected_unclaimed_revision: u64,
    failed_cas_expected_affected_rows: u64,
    maximum_successful_claims: u64,
    missing_row_may_be_created_by_claim: bool,
    permit_binds_capability_nonce: bool,
    permit_binds_controller_runner_and_run: bool,
    single_use_claim_required: bool,
    successful_cas_expected_affected_rows: u64,
    successful_claim_then_crash_allows_retry: bool,
    transition: String,
    unclaimed_state: String,
    upsert_or_replace_allowed: bool,
}

#[derive(Clone, Serialize)]
struct ControlProtocolV1 {
    absorbing_stop_clear_state: String,
    absorbing_stop_triggered_state: String,
    anti_rollback_policy_sha256: String,
    cas_and_control_reads_same_sqlite_transaction: bool,
    control_implementation_binary_sha256: String,
    control_implementation_source_sha256: String,
    control_implementation_toolchain_sha256: String,
    control_ledger_identity_sha256: String,
    control_snapshot_schema_sha256: String,
    current_epoch_source_profile: String,
    external_state_is_outside_owner_envelope: bool,
    missing_or_unknown_control_state_fails_closed: bool,
    post_claim_pre_start_recheck_required: bool,
    revocation_epoch_comparison: String,
    revocation_epoch_monotonic: bool,
    revocation_ledger_revision_monotonic: bool,
    revocation_policy_identity_required: bool,
    runtime_action_boundary_recheck_required: bool,
    same_transaction_required_table_ids: Vec<String>,
    stop_ledger_revision_monotonic: bool,
    stop_policy_identity_required: bool,
    stop_transition: String,
    stop_triggered_is_absorbing: bool,
    trusted_wall_clock_is_freshness: bool,
}

#[derive(Clone, Serialize)]
struct ReceiptBindingsV1 {
    authority_control_claim_schema_sha256: String,
    claim_receipt_is_owner_envelope: bool,
    cleanup_or_custody_receipt_is_owner_envelope: bool,
    control_snapshot_schema_sha256: String,
    post_run_bundle_schema_sha256: String,
    post_run_receipts_grant_authority: bool,
    preflight_receipt_is_owner_envelope: bool,
    preflight_receipt_schema_sha256: String,
    raw_observation_schema_sha256: String,
    receipt_hash_domain_profile: String,
    receipt_parent_chain: Vec<String>,
    stop_receipt_required_if_triggered: bool,
    subject_manifest_schema_sha256: String,
}

#[derive(Clone, Serialize)]
struct NonclaimsV1 {
    actual_assigned_attempt_count: u64,
    actual_cas_claim_count: u64,
    actual_execution_capability_count: u64,
    actual_fresh_process_read_count: u64,
    actual_observation_count: u64,
    actual_owner_signature_count: u64,
    actual_owner_trust_anchor_count: u64,
    actual_runner_launch_count: u64,
    actual_sigkill_attempt_count: u64,
    execution_start_permitted: bool,
    global_runtime_admission: bool,
    live_root_created: bool,
    manifest_owner_signed: bool,
    may_execute_live_canary: bool,
    owned_lab_execution_authorized: bool,
    owner_envelope_present: bool,
    owner_identity_bound: bool,
    provider_or_production_authority: bool,
    real_manifest_committed_to_repository: bool,
    runner_implementation_is_live: bool,
    s20_admission_satisfied: bool,
    side_effects_unlocked: String,
    single_use_execution_permit_issued: bool,
    test_fixture_is_owner_authority: bool,
}

#[derive(Clone, Serialize)]
struct SubjectManifestV1 {
    artifact_bindings: ArtifactBindingsV1,
    build_identity: BuildIdentityV1,
    canonicalization: String,
    claim_protocol: ClaimProtocolV1,
    control_protocol: ControlProtocolV1,
    experiment_scope: ExperimentScopeV1,
    lab_environment: LabEnvironmentV1,
    manifest_state: String,
    nonclaims: NonclaimsV1,
    packet_kind: String,
    receipt_bindings: ReceiptBindingsV1,
    safety_policy: SafetyPolicyV1,
    schema: String,
    test_only: bool,
    validators: ValidatorBindingsV1,
}

/// Typed inputs loaded from frozen build/control-plane facts.  The candidate
/// manifest and owner envelope are intentionally absent from this API.
#[derive(Clone)]
struct IndependentSubjectInputsV1 {
    build_identity: BuildIdentityV1,
    validators: ValidatorBindingsV1,
    artifact_bindings: ArtifactBindingsV1,
    lab_environment: LabEnvironmentV1,
    safety_policy: SafetyPolicyV1,
    claim_protocol: ClaimProtocolV1,
    control_protocol: ControlProtocolV1,
    receipt_bindings: ReceiptBindingsV1,
    test_only: bool,
}

#[derive(Clone)]
struct PinnedOwnerSigningRequestV1 {
    trust_anchor_document_sha256: [u8; 32],
    owner_identity_sha256: [u8; 32],
    owner_key_id: String,
    owner_key_version: u64,
    trust_policy_sha256: [u8; 32],
    decision_nonce_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
    issued_at_utc_audit_only: String,
    expires_at_utc_audit_only: String,
    revocation_epoch: u64,
}

#[must_use]
struct VerifiedS19SubjectV1 {
    canonical_manifest_sha256: [u8; 32],
    schema_sha256: [u8; 32],
    source_commit: [u8; 20],
    integration_commit: [u8; 20],
    controller_binary_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    preflight_observer_binary_sha256: [u8; 32],
    boot_id_sha256: [u8; 32],
    root_parent_identity_sha256: [u8; 32],
    resource_scope_sha256: [u8; 32],
    control_ledger_identity_sha256: [u8; 32],
    anti_rollback_policy_sha256: [u8; 32],
    stop_control_policy_sha256: [u8; 32],
    sqlite_profile_sha256: [u8; 32],
    sqlite_schema_sha256: [u8; 32],
    claim_namespace_sha256: [u8; 32],
    claim_key_sha256: [u8; 32],
    expected_unclaimed_revision: u64,
}

impl fmt::Debug for VerifiedS19SubjectV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("VerifiedS19SubjectV1")
            .field("state", &"[FROZEN_NON_LIVE_SUBJECT_NOT_AUTHORITY]")
            .finish_non_exhaustive()
    }
}

#[must_use]
struct AuthorizedUnclaimedS19SubjectV1 {
    authorization: VerifiedUnclaimedOwnedLabAuthorizationV1,
    subject: VerifiedS19SubjectV1,
    capability_nonce_sha256: [u8; 32],
    revocation_policy_sha256: [u8; 32],
}

impl fmt::Debug for AuthorizedUnclaimedS19SubjectV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("AuthorizedUnclaimedS19SubjectV1")
            .field("state", &"[AUTHENTICATED_UNCLAIMED_NOT_PERMIT]")
            .finish_non_exhaustive()
    }
}

fn hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        write!(&mut output, "{byte:02x}").expect("writing hexadecimal to String cannot fail");
    }
    output
}

fn manifest_error(code: &'static str, detail: &'static str) -> OwnedLabAuthorizationError {
    authorization_error(code, detail)
}

fn validate_digest_and_oid_fields(value: &Value) -> AuthorizationResult<()> {
    match value {
        Value::Array(values) => {
            for item in values {
                validate_digest_and_oid_fields(item)?;
            }
        }
        Value::Object(values) => {
            for (key, item) in values {
                if key.ends_with("_sha256") {
                    let text = item.as_str().ok_or_else(|| {
                        manifest_error("s19_digest_type", "digest field is not a string")
                    })?;
                    let digest = decode_hex_fixed::<32>(text)?;
                    if !nonzero(&digest) {
                        return Err(manifest_error(
                            "s19_digest_zero",
                            "manifest digest commitment is all-zero",
                        ));
                    }
                } else if key.ends_with("_commit") || key.ends_with("_tree") {
                    let text = item.as_str().ok_or_else(|| {
                        manifest_error("s19_oid_type", "Git object field is not a string")
                    })?;
                    let oid = decode_hex_fixed::<20>(text)?;
                    if !nonzero(&oid) {
                        return Err(manifest_error(
                            "s19_oid_zero",
                            "manifest Git object commitment is all-zero",
                        ));
                    }
                }
                validate_digest_and_oid_fields(item)?;
            }
        }
        _ => {}
    }
    Ok(())
}

fn fixed_experiment_scope() -> ExperimentScopeV1 {
    ExperimentScopeV1 {
        assigned_attempt_count: 60,
        authorized_family_ids: vec!["OL00".into(), "OL04".into(), "OL05".into()],
        authorized_family_scenario_counts: BTreeMap::from([
            ("OL00".into(), 1),
            ("OL04".into(), 6),
            ("OL05".into(), 53),
        ]),
        canary_batch_count: 1,
        claim_level: "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY".into(),
        family_id_namespace: "OL00_OL04_OL05_FIRST_BATCH".into(),
        planned_distinct_fresh_exec_read_count: 59,
        planned_pidfd_sigkill_attempt_count: 59,
        planned_total_s16_mapping_phase_record_count: 113,
        repetition_count: 1,
        rerun_requires_new_assignment_and_owner_decision: true,
        retry_or_implicit_rerun_allowed: false,
    }
}

fn fixed_nonclaims() -> NonclaimsV1 {
    NonclaimsV1 {
        actual_assigned_attempt_count: 0,
        actual_cas_claim_count: 0,
        actual_execution_capability_count: 0,
        actual_fresh_process_read_count: 0,
        actual_observation_count: 0,
        actual_owner_signature_count: 0,
        actual_owner_trust_anchor_count: 0,
        actual_runner_launch_count: 0,
        actual_sigkill_attempt_count: 0,
        execution_start_permitted: false,
        global_runtime_admission: false,
        live_root_created: false,
        manifest_owner_signed: false,
        may_execute_live_canary: false,
        owned_lab_execution_authorized: false,
        owner_envelope_present: false,
        owner_identity_bound: false,
        provider_or_production_authority: false,
        real_manifest_committed_to_repository: false,
        runner_implementation_is_live: false,
        s20_admission_satisfied: false,
        side_effects_unlocked: "NONE".into(),
        single_use_execution_permit_issued: false,
        test_fixture_is_owner_authority: false,
    }
}

fn build_subject_manifest_v1(
    inputs: &IndependentSubjectInputsV1,
) -> AuthorizationResult<SubjectManifestV1> {
    if inputs.build_identity.s18_integration_commit != S18_INTEGRATION_COMMIT
        || inputs.artifact_bindings.s18_contract_sha256 != S18_CONTRACT_SHA256
        || inputs.artifact_bindings.s18_successor_gate_sha256 != S18_SUCCESSOR_SHA256
        || inputs.artifact_bindings.positive_owner_schema_sha256 != S18_OWNER_SCHEMA_SHA256
        || inputs
            .artifact_bindings
            .s18_owner_trust_anchor_schema_sha256
            != S18_ANCHOR_SCHEMA_SHA256
        || inputs.artifact_bindings.s18_owner_verifier_source_sha256 != S18_VERIFIER_SOURCE_SHA256
    {
        return Err(manifest_error(
            "s19_s18_binding",
            "typed subject inputs do not bind the frozen S18 release",
        ));
    }
    if inputs.artifact_bindings.sqlite_application_id != AUTHORITY_CONTROL_APPLICATION_ID as u64
        || inputs.artifact_bindings.sqlite_user_version != AUTHORITY_CONTROL_USER_VERSION as u64
        || inputs.lab_environment.sqlite_journal_mode != "DELETE"
        || inputs.lab_environment.sqlite_synchronous != "EXTRA"
        || inputs.lab_environment.sqlite_reopen_mode != "READ_WRITE_EXISTING_WITHOUT_CREATE"
        || inputs.lab_environment.sqlite_setup_mode != "CREATE_NEW_ONLY_DURING_SETUP"
        || !inputs.lab_environment.sqlite_database_file_fsync_required
        || !inputs.lab_environment.parent_directory_fsync_required
        || inputs.artifact_bindings.sqlite_profile_sha256 != hex(&sha256_bytes(SQLITE_PROFILE_V1))
        || inputs.artifact_bindings.sqlite_schema_sha256 != SQLITE_SCHEMA_CATALOG_SHA256
    {
        return Err(manifest_error(
            "s19_sqlite_profile",
            "typed subject inputs do not match the frozen durable SQLite profile",
        ));
    }
    let manifest = SubjectManifestV1 {
        artifact_bindings: inputs.artifact_bindings.clone(),
        build_identity: inputs.build_identity.clone(),
        canonicalization: S19_CANONICAL_PROFILE.into(),
        claim_protocol: inputs.claim_protocol.clone(),
        control_protocol: inputs.control_protocol.clone(),
        experiment_scope: fixed_experiment_scope(),
        lab_environment: inputs.lab_environment.clone(),
        manifest_state: if inputs.test_only {
            S19_SYNTHETIC_MANIFEST_STATE
        } else {
            S19_UNSIGNED_MANIFEST_STATE
        }
        .into(),
        nonclaims: fixed_nonclaims(),
        packet_kind: S19_MANIFEST_PACKET_KIND.into(),
        receipt_bindings: inputs.receipt_bindings.clone(),
        safety_policy: inputs.safety_policy.clone(),
        schema: S19_MANIFEST_SCHEMA.into(),
        test_only: inputs.test_only,
        validators: inputs.validators.clone(),
    };
    let value = serde_json::to_value(&manifest).map_err(|_| {
        manifest_error(
            "s19_manifest_encode",
            "typed subject manifest cannot be encoded",
        )
    })?;
    validate_digest_and_oid_fields(&value)?;
    Ok(manifest)
}

fn validate_closed_manifest_shape(value: &Value) -> AuthorizationResult<()> {
    let manifest = object(value, "s19_manifest_top_level")?;
    exact_keys(manifest, TOP_LEVEL_KEYS, "s19_manifest_top_level_keys")?;
    let nested = |key: &str| -> AuthorizationResult<&Map<String, Value>> {
        manifest.get(key).and_then(Value::as_object).ok_or_else(|| {
            manifest_error("s19_manifest_object", "closed manifest object is missing")
        })
    };
    exact_keys(
        nested("build_identity")?,
        BUILD_IDENTITY_KEYS,
        "s19_build_identity_keys",
    )?;
    let artifacts = nested("artifact_bindings")?;
    exact_keys(artifacts, ARTIFACT_KEYS, "s19_artifact_keys")?;
    let scope = nested("experiment_scope")?;
    exact_keys(scope, EXPERIMENT_SCOPE_KEYS, "s19_experiment_scope_keys")?;
    exact_keys(
        nested("lab_environment")?,
        LAB_ENVIRONMENT_KEYS,
        "s19_lab_environment_keys",
    )?;
    exact_keys(
        nested("safety_policy")?,
        SAFETY_POLICY_KEYS,
        "s19_safety_policy_keys",
    )?;
    exact_keys(
        nested("claim_protocol")?,
        CLAIM_PROTOCOL_KEYS,
        "s19_claim_protocol_keys",
    )?;
    exact_keys(
        nested("control_protocol")?,
        CONTROL_PROTOCOL_KEYS,
        "s19_control_protocol_keys",
    )?;
    exact_keys(
        nested("receipt_bindings")?,
        RECEIPT_BINDING_KEYS,
        "s19_receipt_binding_keys",
    )?;
    exact_keys(nested("nonclaims")?, NONCLAIMS_KEYS, "s19_nonclaims_keys")?;
    let validators = nested("validators")?;
    exact_keys(validators, VALIDATOR_KEYS, "s19_validator_keys")?;
    for key in VALIDATOR_KEYS {
        let component = validators
            .get(*key)
            .and_then(Value::as_object)
            .ok_or_else(|| manifest_error("s19_component", "validator component is missing"))?;
        exact_keys(component, COMPONENT_KEYS, "s19_component_keys")?;
    }
    Ok(())
}

fn verify_subject_manifest_v1(
    candidate_raw: &[u8],
    independent_inputs: &IndependentSubjectInputsV1,
) -> AuthorizationResult<VerifiedS19SubjectV1> {
    let expected = build_subject_manifest_v1(independent_inputs)?;
    let expected_value = serde_json::to_value(&expected).map_err(|_| {
        manifest_error(
            "s19_manifest_encode",
            "typed subject manifest cannot be encoded",
        )
    })?;
    let expected_raw = restricted_canonical_bytes(&expected_value)?;
    let candidate = parse_restricted_canonical(candidate_raw)?;
    validate_closed_manifest_shape(&candidate)?;
    if candidate != expected_value || candidate_raw != expected_raw {
        return Err(manifest_error(
            "s19_independent_expected_binding",
            "candidate manifest differs from independently built typed subject",
        ));
    }
    let manifest_sha256 = sha256_bytes(&expected_raw);
    Ok(VerifiedS19SubjectV1 {
        canonical_manifest_sha256: manifest_sha256,
        schema_sha256: decode_hex_fixed::<32>(
            &independent_inputs
                .build_identity
                .subject_manifest_schema_sha256,
        )?,
        source_commit: decode_hex_fixed::<20>(
            &independent_inputs.build_identity.s19_source_commit,
        )?,
        integration_commit: decode_hex_fixed::<20>(
            &independent_inputs.build_identity.s19_integration_commit,
        )?,
        controller_binary_sha256: decode_hex_fixed::<32>(
            &independent_inputs.build_identity.controller_binary_sha256,
        )?,
        runner_binary_sha256: decode_hex_fixed::<32>(
            &independent_inputs.build_identity.runner_binary_sha256,
        )?,
        preflight_observer_binary_sha256: decode_hex_fixed::<32>(
            &independent_inputs.validators.live_observation.binary_sha256,
        )?,
        boot_id_sha256: decode_hex_fixed::<32>(&independent_inputs.lab_environment.boot_id_sha256)?,
        root_parent_identity_sha256: decode_hex_fixed::<32>(
            &independent_inputs
                .lab_environment
                .root_parent_device_inode_sha256,
        )?,
        resource_scope_sha256: decode_hex_fixed::<32>(
            &independent_inputs.safety_policy.resource_scope_sha256,
        )?,
        control_ledger_identity_sha256: decode_hex_fixed::<32>(
            &independent_inputs
                .control_protocol
                .control_ledger_identity_sha256,
        )?,
        anti_rollback_policy_sha256: decode_hex_fixed::<32>(
            &independent_inputs
                .control_protocol
                .anti_rollback_policy_sha256,
        )?,
        stop_control_policy_sha256: decode_hex_fixed::<32>(
            &independent_inputs.safety_policy.stop_control_policy_sha256,
        )?,
        sqlite_profile_sha256: decode_hex_fixed::<32>(
            &independent_inputs.artifact_bindings.sqlite_profile_sha256,
        )?,
        sqlite_schema_sha256: decode_hex_fixed::<32>(
            &independent_inputs.artifact_bindings.sqlite_schema_sha256,
        )?,
        claim_namespace_sha256: decode_hex_fixed::<32>(
            &independent_inputs.claim_protocol.claim_namespace_sha256,
        )?,
        claim_key_sha256: decode_hex_fixed::<32>(
            &independent_inputs.claim_protocol.claim_key_sha256,
        )?,
        expected_unclaimed_revision: independent_inputs
            .claim_protocol
            .expected_unclaimed_revision,
    })
}

fn build_expected_s18_payload_v1(
    subject: &VerifiedS19SubjectV1,
    inputs: &IndependentSubjectInputsV1,
    signing: &PinnedOwnerSigningRequestV1,
) -> AuthorizationResult<Value> {
    if signing.revocation_epoch == 0 {
        return Err(manifest_error(
            "s19_expected_revocation",
            "pinned signing request revocation epoch must be nonzero",
        ));
    }
    let parts = [
        serde_json::json!({
            "agent_bridge_application_side_effect_allowed": false,
            "assigned_attempt_count": 60,
            "assignment_set_sha256": inputs.artifact_bindings.assignment_set_sha256,
            "atomic_claim_receipt_required_before_start": true,
            "audience": "AGENT_BRIDGE_S18_OWNED_LAB_L1_ONLY",
            "authorization_id_sha256": "ff".repeat(32),
            "authorized_family_ids": ["OL00", "OL04", "OL05"],
            "authorized_family_scenario_counts": {"OL00": 1, "OL04": 6, "OL05": 53},
            "canary_batch_count": 1,
            "capability_nonce_sha256": hex(&signing.capability_nonce_sha256),
            "cas_claim_receipt_sha256": null,
            "claim_key_sha256": inputs.claim_protocol.claim_key_sha256,
            "claim_level": "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY",
            "claim_namespace_sha256": inputs.claim_protocol.claim_namespace_sha256,
            "claimed_run_id_sha256": null,
            "classifier_binary_sha256": inputs.artifact_bindings.classifier_binary_sha256,
            "classifier_source_sha256": inputs.artifact_bindings.classifier_source_sha256,
            "cleanup_policy_sha256": inputs.safety_policy.cleanup_policy_sha256,
            "control_protocol_sha256": inputs.artifact_bindings.control_protocol_sha256,
            "credential_access_allowed": false,
            "decision_expires_at_utc_audit_only": signing.expires_at_utc_audit_only,
            "decision_issued_at_utc_audit_only": signing.issued_at_utc_audit_only,
            "decision_nonce_sha256": hex(&signing.decision_nonce_sha256)
        }),
        serde_json::json!({
            "decision_reason": DECISION_REASON,
            "decision_state": DECISION_STATE,
            "direct_block_device_write_allowed": false,
            "execution_capability_sha256": null,
            "execution_start_permitted": false,
            "expected_oracle_sha256": inputs.artifact_bindings.expected_oracle_sha256,
            "expected_unclaimed_revision": inputs.claim_protocol.expected_unclaimed_revision,
            "family_id_namespace": "OL00_OL04_OL05_FIRST_BATCH",
            "live_observation_validator_binary_sha256": inputs.validators.live_observation.binary_sha256,
            "live_observation_validator_ruleset_sha256": inputs.validators.live_observation.ruleset_sha256,
            "live_observation_validator_source_sha256": inputs.validators.live_observation.source_sha256,
            "live_observation_validator_toolchain_sha256": inputs.validators.live_observation.toolchain_sha256,
            "maximum_successful_claims": 1,
            "mount_or_unmount_allowed": false,
            "network_allowed": false,
            "owner_authorization_validator_binary_sha256": inputs.validators.owner_authorization.binary_sha256,
            "owner_authorization_validator_ruleset_sha256": inputs.validators.owner_authorization.ruleset_sha256,
            "owner_authorization_validator_source_sha256": inputs.validators.owner_authorization.source_sha256,
            "owner_authorization_validator_toolchain_sha256": inputs.validators.owner_authorization.toolchain_sha256,
            "owner_envelope_is_bearer_capability": false,
            "owner_identity_sha256": hex(&signing.owner_identity_sha256),
            "owner_key_id": signing.owner_key_id,
            "owner_key_version": signing.owner_key_version,
            "owner_role": "OWNED_LAB_EXECUTION_OWNER",
            "owner_scope_authorized": true,
            "owned_lab_execution_authorized": false,
            "paid_resource_allowed": false,
            "planned_distinct_fresh_exec_read_count": 59,
            "planned_pidfd_sigkill_attempt_count": 59,
            "planned_total_s16_mapping_phase_record_count": 113,
            "positive_owner_schema_sha256": inputs.artifact_bindings.positive_owner_schema_sha256
        }),
        serde_json::json!({
            "post_run_cleanup_receipt_sha256": null,
            "post_run_custody_receipt_sha256": null,
            "preflight_policy_sha256": inputs.safety_policy.preflight_policy_sha256,
            "process_crash_is_power_loss_proof": false,
            "production_access_allowed": false,
            "provider_access_allowed": false,
            "reboot_kernel_crash_or_power_fault_allowed": false,
            "resource_scope_sha256": inputs.safety_policy.resource_scope_sha256,
            "retention_policy_sha256": inputs.safety_policy.retention_policy_sha256,
            "retry_or_implicit_rerun_allowed": false,
            "revocation_epoch": signing.revocation_epoch,
            "review_policy_sha256": inputs.safety_policy.review_policy_sha256,
            "root_or_privilege_escalation_allowed": false,
            "runner_binary_sha256": inputs.build_identity.runner_binary_sha256,
            "runner_source_commit": inputs.build_identity.runner_source_commit,
            "runner_source_sha256": inputs.build_identity.runner_source_sha256,
            "runner_toolchain_sha256": inputs.build_identity.runner_toolchain_sha256,
            "s16_integration_commit": S16_INTEGRATION_COMMIT,
            "s17_integration_commit": S17_INTEGRATION_COMMIT,
            "s17_observation_schema_sha256": S17_OBSERVATION_SCHEMA_SHA256,
            "s17_pending_owner_schema_sha256": S17_PENDING_OWNER_SCHEMA_SHA256,
            "s17_plan_sha256": S17_PLAN_SHA256,
            "s17_source_commit": S17_SOURCE_COMMIT,
            "s17_successor_gate_sha256": S17_SUCCESSOR_GATE_SHA256,
            "s19_integration_commit": inputs.build_identity.s19_integration_commit,
            "s19_subject_manifest_schema_sha256": hex(&subject.schema_sha256),
            "s19_subject_manifest_sha256": hex(&subject.canonical_manifest_sha256)
        }),
        serde_json::json!({
            "safety_policy_sha256": inputs.safety_policy.safety_policy_sha256,
            "schedule_sha256": inputs.artifact_bindings.schedule_sha256,
            "schema_conformance_alone_authorizes_execution": false,
            "side_effects_unlocked": "NONE",
            "single_use_claim_required": true,
            "single_use_execution_capability_issued": false,
            "sqlite_profile_sha256": inputs.artifact_bindings.sqlite_profile_sha256,
            "sqlite_schema_sha256": inputs.artifact_bindings.sqlite_schema_sha256,
            "stop_control_policy_sha256": inputs.safety_policy.stop_control_policy_sha256,
            "stop_state_at_signing_audit_only": false,
            "timestamps_are_authorization_freshness": false,
            "trusted_time_receipt_sha256": null,
            "trust_anchor_document_sha256": hex(&signing.trust_anchor_document_sha256),
            "trust_policy_sha256": hex(&signing.trust_policy_sha256),
            "use_time_current_revocation_epoch_check_required": true,
            "use_time_external_absorbing_stop_check_required": true,
            "validity_control": "SINGLE_USE_CAS_REVOCATION_EPOCH_AND_ABSORBING_STOP_NOT_WALL_CLOCK"
        }),
    ];
    let mut payload = Map::new();
    for part in parts {
        payload.extend(
            part.as_object()
                .expect("literal expected payload part is an object")
                .clone(),
        );
    }
    let id = authorization_id(&payload)?;
    payload.insert("authorization_id_sha256".into(), Value::String(hex(&id)));
    Ok(Value::Object(payload))
}

fn verify_authorized_unclaimed_subject_v1(
    anchor_raw: &[u8],
    envelope_raw: &[u8],
    manifest_raw: &[u8],
    independent_inputs: &IndependentSubjectInputsV1,
    signing: &PinnedOwnerSigningRequestV1,
) -> AuthorizationResult<AuthorizedUnclaimedS19SubjectV1> {
    let subject = verify_subject_manifest_v1(manifest_raw, independent_inputs)?;
    let payload = build_expected_s18_payload_v1(&subject, independent_inputs, signing)?;
    let expected = ExpectedOwnedLabAuthorizationBindingV1 {
        trust_anchor_document_sha256: signing.trust_anchor_document_sha256,
        payload,
    };
    let authorization =
        verify_unclaimed_owner_authorization_v1(anchor_raw, envelope_raw, &expected)?;
    Ok(AuthorizedUnclaimedS19SubjectV1 {
        authorization,
        subject,
        capability_nonce_sha256: signing.capability_nonce_sha256,
        revocation_policy_sha256: signing.trust_policy_sha256,
    })
}

#[derive(Clone)]
struct ControlSnapshotV1 {
    stop_state: String,
    stop_revision: u64,
    current_revocation_epoch: u64,
    revocation_revision: u64,
    control_ledger_identity_sha256: [u8; 32],
    anti_rollback_policy_sha256: [u8; 32],
    stop_control_policy_sha256: [u8; 32],
    revocation_policy_sha256: [u8; 32],
    sqlite_profile_sha256: [u8; 32],
    sqlite_schema_sha256: [u8; 32],
    snapshot_sha256: [u8; 32],
}

#[derive(Clone)]
struct PreflightProbeV1 {
    run_id_sha256: [u8; 32],
    controller_binary_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    observer_binary_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
    challenge_nonce_sha256: [u8; 32],
    boot_id_sha256: [u8; 32],
    root_parent_identity_sha256: [u8; 32],
    run_root_absent: bool,
    environment_matches_manifest: bool,
    resource_limits_active: bool,
    forbidden_operations_absent: bool,
}

#[must_use]
struct ValidatedPreflightV1 {
    receipt_sha256: [u8; 32],
    run_id_sha256: [u8; 32],
    controller_binary_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
    control_snapshot: ControlSnapshotV1,
}

fn framed_digest(domain: &[u8], fields: &[&[u8]]) -> AuthorizationResult<[u8; 32]> {
    let mut message = Vec::new();
    append_u32_frame(&mut message, domain)?;
    for field in fields {
        message.extend_from_slice(&(field.len() as u64).to_be_bytes());
        message.extend_from_slice(field);
    }
    Ok(sha256_bytes(&message))
}

fn control_snapshot_digest(
    manifest_sha256: &[u8; 32],
    stop_state: &str,
    stop_revision: u64,
    current_revocation_epoch: u64,
    revocation_revision: u64,
    ledger_identity: &[u8; 32],
    anti_rollback_policy_sha256: &[u8; 32],
    stop_control_policy_sha256: &[u8; 32],
    revocation_policy_sha256: &[u8; 32],
    sqlite_profile_sha256: &[u8; 32],
    sqlite_schema_sha256: &[u8; 32],
) -> AuthorizationResult<[u8; 32]> {
    framed_digest(
        CONTROL_SNAPSHOT_DOMAIN,
        &[
            manifest_sha256,
            stop_state.as_bytes(),
            &stop_revision.to_be_bytes(),
            &current_revocation_epoch.to_be_bytes(),
            &revocation_revision.to_be_bytes(),
            ledger_identity,
            anti_rollback_policy_sha256,
            stop_control_policy_sha256,
            revocation_policy_sha256,
            sqlite_profile_sha256,
            sqlite_schema_sha256,
        ],
    )
}

fn controls_match_authorized_subject(
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    controls: &ControlSnapshotV1,
) -> bool {
    controls.stop_state == STOP_CLEAR
        && controls.current_revocation_epoch == authorized.authorization.revocation_epoch
        && controls.stop_revision > 0
        && controls.revocation_revision > 0
        && controls.control_ledger_identity_sha256
            == authorized.subject.control_ledger_identity_sha256
        && controls.anti_rollback_policy_sha256 == authorized.subject.anti_rollback_policy_sha256
        && controls.stop_control_policy_sha256 == authorized.subject.stop_control_policy_sha256
        && controls.revocation_policy_sha256 == authorized.revocation_policy_sha256
        && controls.sqlite_profile_sha256 == authorized.subject.sqlite_profile_sha256
        && controls.sqlite_schema_sha256 == authorized.subject.sqlite_schema_sha256
}

fn validate_preflight_v1(
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    probe: PreflightProbeV1,
    controls: ControlSnapshotV1,
) -> AuthorizationResult<ValidatedPreflightV1> {
    if !controls_match_authorized_subject(authorized, &controls) {
        return Err(manifest_error(
            "s19_preflight_controls",
            "preflight STOP or exact revocation control is not current and clear",
        ));
    }
    let expected_snapshot = control_snapshot_digest(
        &authorized.subject.canonical_manifest_sha256,
        &controls.stop_state,
        controls.stop_revision,
        controls.current_revocation_epoch,
        controls.revocation_revision,
        &controls.control_ledger_identity_sha256,
        &controls.anti_rollback_policy_sha256,
        &controls.stop_control_policy_sha256,
        &controls.revocation_policy_sha256,
        &controls.sqlite_profile_sha256,
        &controls.sqlite_schema_sha256,
    )?;
    if controls.snapshot_sha256 != expected_snapshot
        || probe.controller_binary_sha256 != authorized.subject.controller_binary_sha256
        || probe.runner_binary_sha256 != authorized.subject.runner_binary_sha256
        || probe.observer_binary_sha256 != authorized.subject.preflight_observer_binary_sha256
        || probe.capability_nonce_sha256 != authorized.capability_nonce_sha256
        || probe.boot_id_sha256 != authorized.subject.boot_id_sha256
        || probe.root_parent_identity_sha256 != authorized.subject.root_parent_identity_sha256
        || !probe.run_root_absent
        || !probe.environment_matches_manifest
        || !probe.resource_limits_active
        || !probe.forbidden_operations_absent
        || ![
            &probe.run_id_sha256[..],
            &probe.controller_binary_sha256[..],
            &probe.challenge_nonce_sha256[..],
            &probe.boot_id_sha256[..],
            &probe.root_parent_identity_sha256[..],
        ]
        .iter()
        .all(|value| nonzero(value))
    {
        return Err(manifest_error(
            "s19_preflight_binding",
            "preflight does not bind the exact subject, controls, and safe environment",
        ));
    }
    let receipt_sha256 = framed_digest(
        PREFLIGHT_RECEIPT_DOMAIN,
        &[
            &authorized.subject.canonical_manifest_sha256,
            &authorized.authorization.authorization_id_sha256,
            &authorized.authorization.payload_sha256,
            &probe.run_id_sha256,
            &probe.controller_binary_sha256,
            &probe.runner_binary_sha256,
            &probe.observer_binary_sha256,
            &probe.capability_nonce_sha256,
            &probe.challenge_nonce_sha256,
            &probe.boot_id_sha256,
            &probe.root_parent_identity_sha256,
            &controls.snapshot_sha256,
        ],
    )?;
    Ok(ValidatedPreflightV1 {
        receipt_sha256,
        run_id_sha256: probe.run_id_sha256,
        controller_binary_sha256: probe.controller_binary_sha256,
        runner_binary_sha256: probe.runner_binary_sha256,
        capability_nonce_sha256: probe.capability_nonce_sha256,
        control_snapshot: controls,
    })
}

struct ClaimRequestV1 {
    run_id_sha256: [u8; 32],
    controller_binary_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
    preflight_receipt_sha256: [u8; 32],
    control_snapshot_sha256: [u8; 32],
}

#[must_use]
struct ConsumedClaimV1 {
    claim_receipt_sha256: [u8; 32],
    run_id_sha256: [u8; 32],
    controller_binary_sha256: [u8; 32],
    runner_binary_sha256: [u8; 32],
    capability_nonce_sha256: [u8; 32],
    consumed_revision: u64,
}

enum ClaimAttemptV1 {
    Claimed(ConsumedClaimV1),
    FailedCas,
}

struct ClaimedRunPermitV1 {
    permit_sha256: [u8; 32],
    claim_receipt_sha256: [u8; 32],
    run_id_sha256: [u8; 32],
    next_attempt_index: u64,
    _affine_not_clone_or_serialize: Rc<()>,
}

impl fmt::Debug for ClaimedRunPermitV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ClaimedRunPermitV1")
            .field("state", &"[OPAQUE_PROCESS_LOCAL_AFFINE_PERMIT]")
            .finish_non_exhaustive()
    }
}

struct ActionBoundaryGuardV1<'a> {
    attempt_index: u64,
    _consumed_permit_borrow: &'a mut ClaimedRunPermitV1,
}

fn sqlite_error(code: &'static str, detail: &'static str) -> OwnedLabAuthorizationError {
    manifest_error(code, detail)
}

fn to_sql_integer(value: u64) -> AuthorizationResult<i64> {
    i64::try_from(value)
        .map_err(|_| sqlite_error("s19_sqlite_integer", "u64 does not fit SQLite INTEGER"))
}

#[cfg(test)]
fn sync_file_and_parent(path: &Path) -> AuthorizationResult<()> {
    std::fs::OpenOptions::new()
        .read(true)
        .open(path)
        .and_then(|file| file.sync_all())
        .map_err(|_| sqlite_error("s19_sqlite_fsync", "cannot fsync claim ledger file"))?;
    let parent = path.parent().ok_or_else(|| {
        sqlite_error(
            "s19_sqlite_parent",
            "claim ledger path has no parent directory",
        )
    })?;
    std::fs::File::open(parent)
        .and_then(|directory| directory.sync_all())
        .map_err(|_| sqlite_error("s19_sqlite_fsync", "cannot fsync claim ledger parent"))
}

fn open_ledger_file_without_create(path: &Path) -> AuthorizationResult<Connection> {
    use std::os::unix::fs::MetadataExt as _;

    let metadata = std::fs::symlink_metadata(path).map_err(|_| {
        sqlite_error(
            "s19_sqlite_existing",
            "claim ledger must already exist without symlink",
        )
    })?;
    if !metadata.file_type().is_file()
        || metadata.file_type().is_symlink()
        || metadata.nlink() != 1
        || metadata.mode() & 0o777 != 0o600
    {
        return Err(sqlite_error(
            "s19_sqlite_existing",
            "claim ledger is not one private single-link existing regular file",
        ));
    }
    Connection::open_with_flags(
        path,
        OpenFlags::SQLITE_OPEN_READ_WRITE
            | OpenFlags::SQLITE_OPEN_NO_MUTEX
            | OpenFlags::SQLITE_OPEN_NOFOLLOW,
    )
    .map_err(|_| sqlite_error("s19_sqlite_open", "cannot reopen existing claim ledger"))
}

fn pragma_i64(connection: &Connection, pragma: &str) -> AuthorizationResult<i64> {
    connection
        .query_row(pragma, [], |row| row.get(0))
        .map_err(|_| sqlite_error("s19_sqlite_profile", "cannot read SQLite profile pragma"))
}

fn pragma_text(connection: &Connection, pragma: &str) -> AuthorizationResult<String> {
    connection
        .query_row(pragma, [], |row| row.get(0))
        .map_err(|_| sqlite_error("s19_sqlite_profile", "cannot read SQLite text pragma"))
}

fn sqlite_schema_catalog_digest(connection: &Connection) -> AuthorizationResult<[u8; 32]> {
    let mut statement = connection
        .prepare(
            "SELECT type,name,tbl_name,sql FROM sqlite_schema
             WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name",
        )
        .map_err(|_| sqlite_error("s19_sqlite_schema", "cannot prepare schema catalog read"))?;
    let mut rows = statement
        .query([])
        .map_err(|_| sqlite_error("s19_sqlite_schema", "cannot query schema catalog"))?;
    let mut message = Vec::new();
    append_u32_frame(&mut message, SQLITE_SCHEMA_CATALOG_DOMAIN)?;
    let mut object_count = 0_u64;
    while let Some(row) = rows
        .next()
        .map_err(|_| sqlite_error("s19_sqlite_schema", "cannot iterate schema catalog"))?
    {
        object_count = object_count
            .checked_add(1)
            .ok_or_else(|| sqlite_error("s19_sqlite_schema", "schema object count overflow"))?;
        for index in 0..4 {
            let field: String = row
                .get(index)
                .map_err(|_| sqlite_error("s19_sqlite_schema", "schema catalog field drift"))?;
            message.extend_from_slice(&(field.len() as u64).to_be_bytes());
            message.extend_from_slice(field.as_bytes());
        }
    }
    if object_count != 9 {
        return Err(sqlite_error(
            "s19_sqlite_schema",
            "schema catalog object count drifted",
        ));
    }
    Ok(sha256_bytes(&message))
}

fn open_existing_ledger(path: &Path) -> AuthorizationResult<Connection> {
    let metadata = std::fs::symlink_metadata(path).map_err(|_| {
        sqlite_error(
            "s19_sqlite_existing",
            "claim ledger must already exist without symlink",
        )
    })?;
    if metadata.len() == 0 {
        return Err(sqlite_error(
            "s19_sqlite_existing",
            "existing claim ledger cannot be empty",
        ));
    }
    let connection = open_ledger_file_without_create(path)?;
    connection
        .execute_batch(
            "PRAGMA synchronous=EXTRA;
             PRAGMA temp_store=FILE;
             PRAGMA mmap_size=0;
             PRAGMA cache_size=-2048;
             PRAGMA foreign_keys=ON;
             PRAGMA trusted_schema=OFF;",
        )
        .map_err(|_| sqlite_error("s19_sqlite_profile", "cannot apply SQLite runtime profile"))?;
    let application_id = pragma_i64(&connection, "PRAGMA application_id")?;
    let user_version = pragma_i64(&connection, "PRAGMA user_version")?;
    let journal_mode = pragma_text(&connection, "PRAGMA journal_mode")?;
    if application_id != AUTHORITY_CONTROL_APPLICATION_ID
        || user_version != AUTHORITY_CONTROL_USER_VERSION
        || !journal_mode.eq_ignore_ascii_case("delete")
    {
        return Err(sqlite_error(
            "s19_sqlite_identity",
            "SQLite application, version, or journal identity drifted",
        ));
    }
    let expected_schema_sha256 = decode_hex_fixed::<32>(SQLITE_SCHEMA_CATALOG_SHA256)?;
    if sqlite_schema_catalog_digest(&connection)? != expected_schema_sha256
        || pragma_text(&connection, "PRAGMA quick_check(1)")? != "ok"
    {
        return Err(sqlite_error(
            "s19_sqlite_schema",
            "SQLite schema catalog or integrity check drifted",
        ));
    }
    if pragma_i64(&connection, "PRAGMA synchronous")? != 3
        || pragma_i64(&connection, "PRAGMA temp_store")? != 1
        || pragma_i64(&connection, "PRAGMA mmap_size")? != 0
        || pragma_i64(&connection, "PRAGMA cache_size")? != -2048
        || pragma_i64(&connection, "PRAGMA foreign_keys")? != 1
        || pragma_i64(&connection, "PRAGMA trusted_schema")? != 0
    {
        return Err(sqlite_error(
            "s19_sqlite_profile",
            "SQLite connection-local durability profile drifted",
        ));
    }
    Ok(connection)
}

#[cfg(test)]
fn initialize_new_synthetic_ledger_for_test(
    path: &Path,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    controls: &ControlSnapshotV1,
) -> AuthorizationResult<()> {
    use std::os::unix::fs::OpenOptionsExt as _;
    if !controls_match_authorized_subject(authorized, controls)
        || controls.snapshot_sha256
            != control_snapshot_digest(
                &authorized.subject.canonical_manifest_sha256,
                &controls.stop_state,
                controls.stop_revision,
                controls.current_revocation_epoch,
                controls.revocation_revision,
                &controls.control_ledger_identity_sha256,
                &controls.anti_rollback_policy_sha256,
                &controls.stop_control_policy_sha256,
                &controls.revocation_policy_sha256,
                &controls.sqlite_profile_sha256,
                &controls.sqlite_schema_sha256,
            )?
    {
        return Err(sqlite_error(
            "s19_synthetic_registration",
            "synthetic setup controls do not match the signed subject projection",
        ));
    }
    std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .and_then(|file| file.sync_all())
        .map_err(|_| sqlite_error("s19_sqlite_create_new", "cannot create-new claim ledger"))?;
    let mut connection = open_ledger_file_without_create(path)?;
    connection
        .execute_batch(
            "PRAGMA journal_mode=DELETE;
             PRAGMA synchronous=EXTRA;
             PRAGMA temp_store=FILE;
             PRAGMA mmap_size=0;
             PRAGMA cache_size=-2048;
             PRAGMA foreign_keys=ON;
             PRAGMA trusted_schema=OFF;
             PRAGMA application_id=1094865689;
             PRAGMA user_version=19;
             CREATE TABLE authority_control (
               singleton INTEGER PRIMARY KEY CHECK(singleton=1),
               ledger_identity_sha256 BLOB NOT NULL CHECK(length(ledger_identity_sha256)=32),
               anti_rollback_policy_sha256 BLOB NOT NULL CHECK(length(anti_rollback_policy_sha256)=32),
               stop_control_policy_sha256 BLOB NOT NULL CHECK(length(stop_control_policy_sha256)=32),
               revocation_policy_sha256 BLOB NOT NULL CHECK(length(revocation_policy_sha256)=32),
               sqlite_profile_sha256 BLOB NOT NULL CHECK(length(sqlite_profile_sha256)=32),
               sqlite_schema_sha256 BLOB NOT NULL CHECK(length(sqlite_schema_sha256)=32),
               stop_state TEXT NOT NULL CHECK(stop_state IN ('CLEAR','TRIGGERED')),
               stop_revision INTEGER NOT NULL CHECK(stop_revision>0),
               current_revocation_epoch INTEGER NOT NULL CHECK(current_revocation_epoch>0),
               revocation_revision INTEGER NOT NULL CHECK(revocation_revision>0)
             ) STRICT;
             CREATE TRIGGER authority_control_transition_guard
             BEFORE UPDATE ON authority_control
             WHEN NEW.singleton!=OLD.singleton
               OR NEW.ledger_identity_sha256 IS NOT OLD.ledger_identity_sha256
               OR NEW.anti_rollback_policy_sha256 IS NOT OLD.anti_rollback_policy_sha256
               OR NEW.stop_control_policy_sha256 IS NOT OLD.stop_control_policy_sha256
               OR NEW.revocation_policy_sha256 IS NOT OLD.revocation_policy_sha256
               OR NEW.sqlite_profile_sha256 IS NOT OLD.sqlite_profile_sha256
               OR NEW.sqlite_schema_sha256 IS NOT OLD.sqlite_schema_sha256
               OR (OLD.stop_state='TRIGGERED' AND NEW.stop_state!='TRIGGERED')
               OR (NEW.stop_state!=OLD.stop_state
                   AND NOT (OLD.stop_state='CLEAR' AND NEW.stop_state='TRIGGERED'))
               OR (NEW.stop_state!=OLD.stop_state AND NEW.stop_revision<=OLD.stop_revision)
               OR NEW.stop_revision<OLD.stop_revision
               OR NEW.current_revocation_epoch<OLD.current_revocation_epoch
               OR NEW.revocation_revision<OLD.revocation_revision
               OR (NEW.current_revocation_epoch>OLD.current_revocation_epoch
                   AND NEW.revocation_revision<=OLD.revocation_revision)
             BEGIN SELECT RAISE(ABORT,'S19_CONTROL_TRANSITION_REJECTED'); END;
             CREATE TRIGGER authority_control_delete_guard
             BEFORE DELETE ON authority_control
             BEGIN SELECT RAISE(ABORT,'S19_CONTROL_DELETE_REJECTED'); END;
             CREATE TABLE claim_ledger (
               claim_namespace_sha256 BLOB NOT NULL CHECK(length(claim_namespace_sha256)=32),
               claim_key_sha256 BLOB NOT NULL CHECK(length(claim_key_sha256)=32),
               authorization_id_sha256 BLOB NOT NULL CHECK(length(authorization_id_sha256)=32),
               signed_payload_sha256 BLOB NOT NULL CHECK(length(signed_payload_sha256)=32),
               subject_manifest_sha256 BLOB NOT NULL CHECK(length(subject_manifest_sha256)=32),
               resource_scope_sha256 BLOB NOT NULL CHECK(length(resource_scope_sha256)=32),
               signed_revocation_epoch INTEGER NOT NULL CHECK(signed_revocation_epoch>0),
               state TEXT NOT NULL CHECK(state IN ('AUTHORIZED_UNCLAIMED','CONSUMED_FOR_EXACT_RUN')),
               revision INTEGER NOT NULL CHECK(revision>0),
               successful_claim_count INTEGER NOT NULL CHECK(successful_claim_count IN (0,1)),
               run_id_sha256 BLOB CHECK(run_id_sha256 IS NULL OR length(run_id_sha256)=32),
               controller_binary_sha256 BLOB CHECK(controller_binary_sha256 IS NULL OR length(controller_binary_sha256)=32),
               runner_binary_sha256 BLOB NOT NULL CHECK(length(runner_binary_sha256)=32),
               capability_nonce_sha256 BLOB NOT NULL CHECK(length(capability_nonce_sha256)=32),
               preflight_receipt_sha256 BLOB CHECK(preflight_receipt_sha256 IS NULL OR length(preflight_receipt_sha256)=32),
               control_snapshot_sha256 BLOB CHECK(control_snapshot_sha256 IS NULL OR length(control_snapshot_sha256)=32),
               claim_receipt_sha256 BLOB CHECK(claim_receipt_sha256 IS NULL OR length(claim_receipt_sha256)=32),
               PRIMARY KEY(claim_namespace_sha256,claim_key_sha256)
             ) WITHOUT ROWID, STRICT;
             CREATE TRIGGER claim_ledger_transition_guard
             BEFORE UPDATE ON claim_ledger
             WHEN NOT (
               OLD.state='AUTHORIZED_UNCLAIMED'
               AND OLD.successful_claim_count=0
               AND OLD.run_id_sha256 IS NULL
               AND OLD.controller_binary_sha256 IS NULL
               AND OLD.preflight_receipt_sha256 IS NULL
               AND OLD.control_snapshot_sha256 IS NULL
               AND OLD.claim_receipt_sha256 IS NULL
               AND NEW.state='CONSUMED_FOR_EXACT_RUN'
               AND NEW.revision=OLD.revision+1
               AND NEW.successful_claim_count=1
               AND NEW.run_id_sha256 IS NOT NULL
               AND NEW.controller_binary_sha256 IS NOT NULL
               AND NEW.preflight_receipt_sha256 IS NOT NULL
               AND NEW.control_snapshot_sha256 IS NOT NULL
               AND NEW.claim_receipt_sha256 IS NOT NULL
               AND NEW.claim_namespace_sha256 IS OLD.claim_namespace_sha256
               AND NEW.claim_key_sha256 IS OLD.claim_key_sha256
               AND NEW.authorization_id_sha256 IS OLD.authorization_id_sha256
               AND NEW.signed_payload_sha256 IS OLD.signed_payload_sha256
               AND NEW.subject_manifest_sha256 IS OLD.subject_manifest_sha256
               AND NEW.resource_scope_sha256 IS OLD.resource_scope_sha256
               AND NEW.signed_revocation_epoch=OLD.signed_revocation_epoch
               AND NEW.runner_binary_sha256 IS OLD.runner_binary_sha256
               AND NEW.capability_nonce_sha256 IS OLD.capability_nonce_sha256
             )
             BEGIN SELECT RAISE(ABORT,'S19_CLAIM_TRANSITION_REJECTED'); END;
             CREATE TRIGGER claim_ledger_delete_guard
             BEFORE DELETE ON claim_ledger
             BEGIN SELECT RAISE(ABORT,'S19_CLAIM_DELETE_REJECTED'); END;
             CREATE TABLE claim_receipts (
               claim_receipt_sha256 BLOB PRIMARY KEY CHECK(length(claim_receipt_sha256)=32),
               claim_namespace_sha256 BLOB NOT NULL CHECK(length(claim_namespace_sha256)=32),
               claim_key_sha256 BLOB NOT NULL CHECK(length(claim_key_sha256)=32),
               consumed_revision INTEGER NOT NULL CHECK(consumed_revision>0),
               run_id_sha256 BLOB NOT NULL CHECK(length(run_id_sha256)=32)
             ) WITHOUT ROWID, STRICT;
             CREATE TRIGGER claim_receipts_update_guard
             BEFORE UPDATE ON claim_receipts
             BEGIN SELECT RAISE(ABORT,'S19_CLAIM_RECEIPT_UPDATE_REJECTED'); END;
             CREATE TRIGGER claim_receipts_delete_guard
             BEFORE DELETE ON claim_receipts
             BEGIN SELECT RAISE(ABORT,'S19_CLAIM_RECEIPT_DELETE_REJECTED'); END;",
        )
        .map_err(|_| sqlite_error("s19_sqlite_schema", "cannot initialize claim ledger schema"))?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s19_sqlite_tx", "cannot begin registration transaction"))?;
    transaction
        .execute(
            "INSERT INTO authority_control(
               singleton,ledger_identity_sha256,anti_rollback_policy_sha256,
               stop_control_policy_sha256,revocation_policy_sha256,
               sqlite_profile_sha256,sqlite_schema_sha256,stop_state,stop_revision,
               current_revocation_epoch,revocation_revision
             ) VALUES(1,?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
            params![
                &controls.control_ledger_identity_sha256[..],
                &controls.anti_rollback_policy_sha256[..],
                &controls.stop_control_policy_sha256[..],
                &controls.revocation_policy_sha256[..],
                &controls.sqlite_profile_sha256[..],
                &controls.sqlite_schema_sha256[..],
                controls.stop_state,
                to_sql_integer(controls.stop_revision)?,
                to_sql_integer(controls.current_revocation_epoch)?,
                to_sql_integer(controls.revocation_revision)?,
            ],
        )
        .map_err(|_| sqlite_error("s19_sqlite_register", "cannot register control row"))?;
    transaction
        .execute(
            "INSERT INTO claim_ledger(
               claim_namespace_sha256,claim_key_sha256,authorization_id_sha256,
               signed_payload_sha256,subject_manifest_sha256,resource_scope_sha256,
               signed_revocation_epoch,state,revision,successful_claim_count,
               run_id_sha256,controller_binary_sha256,runner_binary_sha256,
               capability_nonce_sha256,preflight_receipt_sha256,
               control_snapshot_sha256,claim_receipt_sha256
             ) VALUES(?1,?2,?3,?4,?5,?6,?7,'AUTHORIZED_UNCLAIMED',?8,0,
                      NULL,NULL,?9,?10,NULL,NULL,NULL)",
            params![
                &authorized.subject.claim_namespace_sha256[..],
                &authorized.subject.claim_key_sha256[..],
                &authorized.authorization.authorization_id_sha256[..],
                &authorized.authorization.payload_sha256[..],
                &authorized.subject.canonical_manifest_sha256[..],
                &authorized.subject.resource_scope_sha256[..],
                to_sql_integer(authorized.authorization.revocation_epoch)?,
                to_sql_integer(authorized.subject.expected_unclaimed_revision)?,
                &authorized.subject.runner_binary_sha256[..],
                &authorized.capability_nonce_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s19_sqlite_register", "cannot register unclaimed row"))?;
    transaction
        .commit()
        .map_err(|_| sqlite_error("s19_sqlite_commit", "cannot commit registration"))?;
    drop(connection);
    sync_file_and_parent(path)
}

fn read_control_snapshot(
    connection: &Connection,
    manifest_sha256: &[u8; 32],
) -> AuthorizationResult<ControlSnapshotV1> {
    let tuple = connection
        .query_row(
            "SELECT ledger_identity_sha256,anti_rollback_policy_sha256,
                    stop_control_policy_sha256,revocation_policy_sha256,
                    sqlite_profile_sha256,sqlite_schema_sha256,
                    stop_state,stop_revision,current_revocation_epoch,revocation_revision
             FROM authority_control WHERE singleton=1",
            [],
            |row| {
                Ok((
                    row.get::<_, Vec<u8>>(0)?,
                    row.get::<_, Vec<u8>>(1)?,
                    row.get::<_, Vec<u8>>(2)?,
                    row.get::<_, Vec<u8>>(3)?,
                    row.get::<_, Vec<u8>>(4)?,
                    row.get::<_, Vec<u8>>(5)?,
                    row.get::<_, String>(6)?,
                    row.get::<_, i64>(7)?,
                    row.get::<_, i64>(8)?,
                    row.get::<_, i64>(9)?,
                ))
            },
        )
        .map_err(|_| sqlite_error("s19_control_read", "cannot read exact control row"))?;
    let ledger_identity: [u8; 32] = tuple
        .0
        .try_into()
        .map_err(|_| sqlite_error("s19_control_shape", "control identity width drift"))?;
    let anti_rollback_policy_sha256: [u8; 32] = tuple
        .1
        .try_into()
        .map_err(|_| sqlite_error("s19_control_shape", "anti-rollback policy width drift"))?;
    let stop_control_policy_sha256: [u8; 32] = tuple
        .2
        .try_into()
        .map_err(|_| sqlite_error("s19_control_shape", "STOP policy width drift"))?;
    let revocation_policy_sha256: [u8; 32] = tuple
        .3
        .try_into()
        .map_err(|_| sqlite_error("s19_control_shape", "revocation policy width drift"))?;
    let sqlite_profile_sha256: [u8; 32] = tuple
        .4
        .try_into()
        .map_err(|_| sqlite_error("s19_control_shape", "SQLite profile width drift"))?;
    let sqlite_schema_sha256: [u8; 32] = tuple
        .5
        .try_into()
        .map_err(|_| sqlite_error("s19_control_shape", "SQLite schema width drift"))?;
    let stop_revision = u64::try_from(tuple.7)
        .map_err(|_| sqlite_error("s19_control_shape", "negative stop revision"))?;
    let current_revocation_epoch = u64::try_from(tuple.8)
        .map_err(|_| sqlite_error("s19_control_shape", "negative revocation epoch"))?;
    let revocation_revision = u64::try_from(tuple.9)
        .map_err(|_| sqlite_error("s19_control_shape", "negative revocation revision"))?;
    let snapshot_sha256 = control_snapshot_digest(
        manifest_sha256,
        &tuple.6,
        stop_revision,
        current_revocation_epoch,
        revocation_revision,
        &ledger_identity,
        &anti_rollback_policy_sha256,
        &stop_control_policy_sha256,
        &revocation_policy_sha256,
        &sqlite_profile_sha256,
        &sqlite_schema_sha256,
    )?;
    Ok(ControlSnapshotV1 {
        stop_state: tuple.6,
        stop_revision,
        current_revocation_epoch,
        revocation_revision,
        control_ledger_identity_sha256: ledger_identity,
        anti_rollback_policy_sha256,
        stop_control_policy_sha256,
        revocation_policy_sha256,
        sqlite_profile_sha256,
        sqlite_schema_sha256,
        snapshot_sha256,
    })
}

fn claim_receipt_digest(
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    request: &ClaimRequestV1,
    consumed_revision: u64,
) -> AuthorizationResult<[u8; 32]> {
    framed_digest(
        CLAIM_RECEIPT_DOMAIN,
        &[
            &authorized.subject.claim_namespace_sha256,
            &authorized.subject.claim_key_sha256,
            &authorized.authorization.authorization_id_sha256,
            &authorized.authorization.payload_sha256,
            &authorized.subject.canonical_manifest_sha256,
            &authorized.subject.resource_scope_sha256,
            &authorized.authorization.revocation_epoch.to_be_bytes(),
            &request.run_id_sha256,
            &request.controller_binary_sha256,
            &request.runner_binary_sha256,
            &request.capability_nonce_sha256,
            &request.preflight_receipt_sha256,
            &request.control_snapshot_sha256,
            &consumed_revision.to_be_bytes(),
        ],
    )
}

fn try_claim_once_v1(
    connection: &mut Connection,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    preflight: ValidatedPreflightV1,
) -> AuthorizationResult<ClaimAttemptV1> {
    let request = ClaimRequestV1 {
        run_id_sha256: preflight.run_id_sha256,
        controller_binary_sha256: preflight.controller_binary_sha256,
        runner_binary_sha256: preflight.runner_binary_sha256,
        capability_nonce_sha256: preflight.capability_nonce_sha256,
        preflight_receipt_sha256: preflight.receipt_sha256,
        control_snapshot_sha256: preflight.control_snapshot.snapshot_sha256,
    };
    let consumed_revision = authorized
        .subject
        .expected_unclaimed_revision
        .checked_add(1)
        .ok_or_else(|| sqlite_error("s19_claim_revision", "claim revision overflow"))?;
    let receipt_sha256 = claim_receipt_digest(authorized, &request, consumed_revision)?;
    let transaction = connection
        .transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)
        .map_err(|_| sqlite_error("s19_claim_tx", "cannot begin one claim transaction"))?;
    if sqlite_schema_catalog_digest(&transaction)?
        != decode_hex_fixed::<32>(SQLITE_SCHEMA_CATALOG_SHA256)?
    {
        return Err(sqlite_error(
            "s19_claim_schema",
            "schema changed before the linearized claim transaction",
        ));
    }
    let changed = transaction
        .execute(
            "UPDATE claim_ledger
             SET state='CONSUMED_FOR_EXACT_RUN',revision=?1,successful_claim_count=1,
                 run_id_sha256=?2,controller_binary_sha256=?3,
                 preflight_receipt_sha256=?4,control_snapshot_sha256=?5,
                 claim_receipt_sha256=?6
             WHERE claim_namespace_sha256=?7 AND claim_key_sha256=?8
               AND authorization_id_sha256=?9 AND signed_payload_sha256=?10
               AND subject_manifest_sha256=?11 AND resource_scope_sha256=?12
               AND signed_revocation_epoch=?13 AND state='AUTHORIZED_UNCLAIMED'
               AND revision=?14 AND successful_claim_count=0
               AND run_id_sha256 IS NULL AND controller_binary_sha256 IS NULL
               AND runner_binary_sha256=?15 AND capability_nonce_sha256=?16
               AND preflight_receipt_sha256 IS NULL
               AND control_snapshot_sha256 IS NULL AND claim_receipt_sha256 IS NULL
               AND EXISTS(
                 SELECT 1 FROM authority_control
                 WHERE singleton=1 AND ledger_identity_sha256=?17
                   AND stop_state='CLEAR' AND stop_revision=?18
                   AND current_revocation_epoch=?13 AND revocation_revision=?19
                   AND anti_rollback_policy_sha256=?20
                   AND stop_control_policy_sha256=?21
                   AND revocation_policy_sha256=?22
                   AND sqlite_profile_sha256=?23 AND sqlite_schema_sha256=?24
               )",
            params![
                to_sql_integer(consumed_revision)?,
                &request.run_id_sha256[..],
                &request.controller_binary_sha256[..],
                &request.preflight_receipt_sha256[..],
                &request.control_snapshot_sha256[..],
                &receipt_sha256[..],
                &authorized.subject.claim_namespace_sha256[..],
                &authorized.subject.claim_key_sha256[..],
                &authorized.authorization.authorization_id_sha256[..],
                &authorized.authorization.payload_sha256[..],
                &authorized.subject.canonical_manifest_sha256[..],
                &authorized.subject.resource_scope_sha256[..],
                to_sql_integer(authorized.authorization.revocation_epoch)?,
                to_sql_integer(authorized.subject.expected_unclaimed_revision)?,
                &request.runner_binary_sha256[..],
                &request.capability_nonce_sha256[..],
                &preflight.control_snapshot.control_ledger_identity_sha256[..],
                to_sql_integer(preflight.control_snapshot.stop_revision)?,
                to_sql_integer(preflight.control_snapshot.revocation_revision)?,
                &preflight.control_snapshot.anti_rollback_policy_sha256[..],
                &preflight.control_snapshot.stop_control_policy_sha256[..],
                &preflight.control_snapshot.revocation_policy_sha256[..],
                &preflight.control_snapshot.sqlite_profile_sha256[..],
                &preflight.control_snapshot.sqlite_schema_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s19_claim_update", "claim CAS statement failed"))?;
    if changed != 1 {
        transaction
            .rollback()
            .map_err(|_| sqlite_error("s19_claim_rollback", "failed CAS rollback is unknown"))?;
        return Ok(ClaimAttemptV1::FailedCas);
    }
    transaction
        .execute(
            "INSERT INTO claim_receipts(
               claim_receipt_sha256,claim_namespace_sha256,claim_key_sha256,
               consumed_revision,run_id_sha256
             ) VALUES(?1,?2,?3,?4,?5)",
            params![
                &receipt_sha256[..],
                &authorized.subject.claim_namespace_sha256[..],
                &authorized.subject.claim_key_sha256[..],
                to_sql_integer(consumed_revision)?,
                &request.run_id_sha256[..],
            ],
        )
        .map_err(|_| sqlite_error("s19_claim_receipt", "cannot write claim receipt atomically"))?;
    transaction.commit().map_err(|_| {
        sqlite_error(
            "s19_claim_commit",
            "claim commit outcome is not durable-known",
        )
    })?;
    Ok(ClaimAttemptV1::Claimed(ConsumedClaimV1 {
        claim_receipt_sha256: receipt_sha256,
        run_id_sha256: request.run_id_sha256,
        controller_binary_sha256: request.controller_binary_sha256,
        runner_binary_sha256: request.runner_binary_sha256,
        capability_nonce_sha256: request.capability_nonce_sha256,
        consumed_revision,
    }))
}

fn redeem_consumed_claim_after_fresh_controls_v1(
    connection: &Connection,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    claim: ConsumedClaimV1,
) -> AuthorizationResult<ClaimedRunPermitV1> {
    let controls =
        read_control_snapshot(connection, &authorized.subject.canonical_manifest_sha256)?;
    if !controls_match_authorized_subject(authorized, &controls) {
        return Err(manifest_error(
            "s19_post_claim_controls",
            "fresh post-claim STOP/revocation check blocks permit redemption",
        ));
    }
    let stored = connection
        .query_row(
            "SELECT state,revision,claim_receipt_sha256,run_id_sha256,
                    controller_binary_sha256,runner_binary_sha256,
                    capability_nonce_sha256
             FROM claim_ledger
             WHERE claim_namespace_sha256=?1 AND claim_key_sha256=?2",
            params![
                &authorized.subject.claim_namespace_sha256[..],
                &authorized.subject.claim_key_sha256[..]
            ],
            |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, i64>(1)?,
                    row.get::<_, Vec<u8>>(2)?,
                    row.get::<_, Vec<u8>>(3)?,
                    row.get::<_, Vec<u8>>(4)?,
                    row.get::<_, Vec<u8>>(5)?,
                    row.get::<_, Vec<u8>>(6)?,
                ))
            },
        )
        .map_err(|_| sqlite_error("s19_claim_read", "cannot read consumed claim"))?;
    if stored.0 != CLAIM_CONSUMED
        || u64::try_from(stored.1).ok() != Some(claim.consumed_revision)
        || stored.2 != claim.claim_receipt_sha256
        || stored.3 != claim.run_id_sha256
        || stored.4 != claim.controller_binary_sha256
        || stored.5 != claim.runner_binary_sha256
        || stored.6 != claim.capability_nonce_sha256
    {
        return Err(sqlite_error(
            "s19_claim_binding",
            "consumed claim row differs from committed claim receipt",
        ));
    }
    let permit_sha256 = framed_digest(
        PERMIT_DOMAIN,
        &[
            &claim.claim_receipt_sha256,
            &claim.run_id_sha256,
            &claim.controller_binary_sha256,
            &claim.runner_binary_sha256,
            &claim.capability_nonce_sha256,
            &controls.snapshot_sha256,
        ],
    )?;
    Ok(ClaimedRunPermitV1 {
        permit_sha256,
        claim_receipt_sha256: claim.claim_receipt_sha256,
        run_id_sha256: claim.run_id_sha256,
        next_attempt_index: 0,
        _affine_not_clone_or_serialize: Rc::new(()),
    })
}

fn authorize_action_boundary_v1<'a>(
    connection: &Connection,
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    permit: &'a mut ClaimedRunPermitV1,
    expected_attempt_index: u64,
) -> AuthorizationResult<ActionBoundaryGuardV1<'a>> {
    if permit.next_attempt_index != expected_attempt_index || expected_attempt_index >= 60 {
        return Err(manifest_error(
            "s19_attempt_order",
            "action boundary attempt order is not exact",
        ));
    }
    let controls =
        read_control_snapshot(connection, &authorized.subject.canonical_manifest_sha256)?;
    if !controls_match_authorized_subject(authorized, &controls) {
        return Err(manifest_error(
            "s19_action_controls",
            "fresh action-boundary STOP/revocation check blocks the next action",
        ));
    }
    permit.next_attempt_index = expected_attempt_index
        .checked_add(1)
        .ok_or_else(|| manifest_error("s19_attempt_order", "attempt index overflow"))?;
    Ok(ActionBoundaryGuardV1 {
        attempt_index: expected_attempt_index,
        _consumed_permit_borrow: permit,
    })
}

#[cfg(test)]
fn update_controls_for_test(
    connection: &Connection,
    stop_state: &str,
    stop_revision: u64,
    revocation_epoch: u64,
    revocation_revision: u64,
) -> AuthorizationResult<()> {
    connection
        .execute(
            "UPDATE authority_control
             SET stop_state=?1,stop_revision=?2,current_revocation_epoch=?3,
                 revocation_revision=?4 WHERE singleton=1",
            params![
                stop_state,
                to_sql_integer(stop_revision)?,
                to_sql_integer(revocation_epoch)?,
                to_sql_integer(revocation_revision)?,
            ],
        )
        .map(|_| ())
        .map_err(|_| sqlite_error("s19_control_update", "control update rejected"))
}

#[derive(Clone)]
struct PostRunReceiptBundleV1 {
    manifest_sha256: [u8; 32],
    claim_receipt_sha256: [u8; 32],
    run_id_sha256: [u8; 32],
    assigned_attempt_count: u64,
    pidfd_sigkill_attempt_count: u64,
    distinct_fresh_exec_read_count: u64,
    total_s16_mapping_phase_record_count: u64,
    retention_receipt_sha256: [u8; 32],
    semantic_receipt_sha256: [u8; 32],
    batch_result_receipt_sha256: [u8; 32],
    stop_receipt_sha256: Option<[u8; 32]>,
    cleanup_receipt_sha256: [u8; 32],
    custody_receipt_sha256: [u8; 32],
    oom_event_count: u64,
    timeout_or_leaked_child_count: u64,
    retry_count: u64,
}

fn validate_post_run_receipts_v1(
    authorized: &AuthorizedUnclaimedS19SubjectV1,
    permit: &ClaimedRunPermitV1,
    bundle: &PostRunReceiptBundleV1,
) -> AuthorizationResult<()> {
    if bundle.manifest_sha256 != authorized.subject.canonical_manifest_sha256
        || bundle.claim_receipt_sha256 != permit.claim_receipt_sha256
        || bundle.run_id_sha256 != permit.run_id_sha256
        || bundle.assigned_attempt_count != 60
        || bundle.pidfd_sigkill_attempt_count != 59
        || bundle.distinct_fresh_exec_read_count != 59
        || bundle.total_s16_mapping_phase_record_count != 113
        || bundle.oom_event_count != 0
        || bundle.timeout_or_leaked_child_count != 0
        || bundle.retry_count != 0
        || ![
            &bundle.retention_receipt_sha256[..],
            &bundle.semantic_receipt_sha256[..],
            &bundle.batch_result_receipt_sha256[..],
            &bundle.cleanup_receipt_sha256[..],
            &bundle.custody_receipt_sha256[..],
        ]
        .iter()
        .all(|digest| nonzero(digest))
    {
        return Err(manifest_error(
            "s19_post_run_bundle",
            "post-run receipt chain does not preserve exact scope and validity controls",
        ));
    }
    if bundle
        .stop_receipt_sha256
        .as_ref()
        .is_some_and(|digest| !nonzero(digest))
    {
        return Err(manifest_error(
            "s19_stop_receipt",
            "present STOP receipt digest cannot be zero",
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::Ed25519KeyPair;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};

    const RFC8032_TEST_ONLY_SEED: [u8; 32] = [
        0x9d, 0x61, 0xb1, 0x9d, 0xef, 0xfd, 0x5a, 0x60, 0xba, 0x84, 0x4a, 0xf4, 0x92, 0xec, 0x2c,
        0xc4, 0x44, 0x49, 0xc5, 0x69, 0x7b, 0x32, 0x69, 0x19, 0x70, 0x3b, 0xac, 0x03, 0x1c, 0xae,
        0x7f, 0x60,
    ];
    const RFC8032_TEST_ONLY_PUBLIC_KEY: [u8; 32] = [
        0xd7, 0x5a, 0x98, 0x01, 0x82, 0xb1, 0x0a, 0xb7, 0xd5, 0x4b, 0xfe, 0xd3, 0xc9, 0x64, 0x07,
        0x3a, 0x0e, 0xe1, 0x72, 0xf3, 0xda, 0xa6, 0x23, 0x25, 0xaf, 0x02, 0x1a, 0x68, 0xf7, 0x07,
        0x51, 0x1a,
    ];
    static NEXT_PATH: AtomicU64 = AtomicU64::new(1);

    fn repeated(value: u8) -> String {
        hex(&[value; 32])
    }

    fn component(seed: u8) -> ComponentBindingV1 {
        ComponentBindingV1 {
            binary_sha256: repeated(seed),
            ruleset_sha256: repeated(seed.wrapping_add(1)),
            source_sha256: repeated(seed.wrapping_add(2)),
            toolchain_sha256: repeated(seed.wrapping_add(3)),
        }
    }

    fn fixture_inputs() -> IndependentSubjectInputsV1 {
        IndependentSubjectInputsV1 {
            build_identity: BuildIdentityV1 {
                build_profile_sha256: repeated(0x11),
                cargo_lock_sha256: repeated(0x12),
                controller_binary_sha256: repeated(0x13),
                controller_source_sha256: repeated(0x14),
                expected_binding_builder_binary_sha256: repeated(0x15),
                expected_binding_builder_ruleset_sha256: repeated(0x16),
                expected_binding_builder_source_sha256: repeated(0x17),
                expected_binding_builder_toolchain_sha256: repeated(0x18),
                feature_set_sha256: repeated(0x19),
                manifest_builder_binary_sha256: repeated(0x1a),
                manifest_builder_ruleset_sha256: repeated(0x1b),
                manifest_builder_source_sha256: repeated(0x1c),
                manifest_builder_toolchain_sha256: repeated(0x1d),
                runner_binary_sha256: repeated(0x1e),
                runner_source_commit: "11".repeat(20),
                runner_source_sha256: repeated(0x1f),
                runner_toolchain_sha256: repeated(0x20),
                s18_integration_commit: S18_INTEGRATION_COMMIT.into(),
                s19_integration_commit: "22".repeat(20),
                s19_integration_tree: "23".repeat(20),
                s19_source_commit: "24".repeat(20),
                s19_source_tree: "25".repeat(20),
                subject_manifest_schema_sha256: repeated(0x26),
                target_triple_sha256: repeated(0x27),
                toolchain_manifest_sha256: repeated(0x28),
            },
            validators: ValidatorBindingsV1 {
                live_observation: component(0x29),
                manifest: component(0x2d),
                owner_authorization: component(0x31),
                receipt: component(0x35),
            },
            artifact_bindings: ArtifactBindingsV1 {
                assignment_set_sha256: repeated(0x39),
                catalog_row_count: 5_639,
                catalog_sha256: "c09cdc640957594cc7acc2eeea39cb4e59993631ef04a1fa1e26a69c285af853"
                    .into(),
                classifier_binary_sha256: repeated(0x3a),
                classifier_source_sha256: repeated(0x3b),
                control_protocol_sha256: repeated(0x3c),
                expected_oracle_sha256: repeated(0x3d),
                positive_owner_schema_sha256: S18_OWNER_SCHEMA_SHA256.into(),
                s17_observation_schema_sha256: S17_OBSERVATION_SCHEMA_SHA256.into(),
                s17_plan_sha256: S17_PLAN_SHA256.into(),
                s18_contract_sha256: S18_CONTRACT_SHA256.into(),
                s18_owner_trust_anchor_schema_sha256: S18_ANCHOR_SCHEMA_SHA256.into(),
                s18_owner_verifier_source_sha256: S18_VERIFIER_SOURCE_SHA256.into(),
                s18_successor_gate_sha256: S18_SUCCESSOR_SHA256.into(),
                schedule_sha256: repeated(0x3e),
                sqlite_application_id: AUTHORITY_CONTROL_APPLICATION_ID as u64,
                sqlite_profile_sha256: hex(&sha256_bytes(SQLITE_PROFILE_V1)),
                sqlite_schema_sha256: SQLITE_SCHEMA_CATALOG_SHA256.into(),
                sqlite_user_version: AUTHORITY_CONTROL_USER_VERSION as u64,
                target_phase_count: 113,
                target_phase_unique_match_count: 113,
            },
            lab_environment: LabEnvironmentV1 {
                attempt_timeout_seconds: 60,
                batch_timeout_seconds: 900,
                boot_id_sha256: repeated(0x41),
                build_jobs: 1,
                candidate_device_identity_sha256: repeated(0x42),
                candidate_device_path: "/dev/nvme0n1p7".into(),
                candidate_filesystem: "f2fs".into(),
                candidate_root: "/Data/CascadeProjects/.ab-owned-lab".into(),
                cut_ready_timeout_seconds: 10,
                death_confirmation_timeout_seconds: 10,
                disk_max_bytes: 268_435_456,
                fresh_exec_timeout_seconds: 20,
                kernel_identity_sha256: repeated(0x43),
                maximum_active_assigned_attempts: 1,
                maximum_child_processes: 1,
                maximum_controller_processes: 1,
                maximum_open_files: 256,
                maximum_tasks: 16,
                memory_max_bytes: 805_306_368,
                mount_identity_sha256: repeated(0x44),
                mount_options_sha256: repeated(0x45),
                mount_point: "/Data".into(),
                nested_cargo_allowed: false,
                parent_directory_fsync_required: true,
                pidfd_signal_timeout_seconds: 10,
                proposed_cost_ceiling_usd: 0,
                root_parent_device_inode_sha256: repeated(0x46),
                run_root_create_mode: "CREATE_NEW_MODE_0700".into(),
                run_root_derivation_profile:
                    "S19_SOURCE_COMMIT_CONTROLLER_PID_MONOTONIC_COUNTER_RANDOM_NONCE_SHA256".into(),
                run_root_must_not_preexist: true,
                same_boot_required: true,
                sqlite_database_file_fsync_required: true,
                sqlite_journal_mode: "DELETE".into(),
                sqlite_reopen_mode: "READ_WRITE_EXISTING_WITHOUT_CREATE".into(),
                sqlite_setup_mode: "CREATE_NEW_ONLY_DURING_SETUP".into(),
                sqlite_synchronous: "EXTRA".into(),
                swap_max_bytes: 268_435_456,
            },
            safety_policy: SafetyPolicyV1 {
                agent_bridge_application_side_effect_allowed: false,
                allowed_operation_ids: vec![
                    "CREATE_EXACT_RUN_ROOT".into(),
                    "SQLITE_EXACT_PROFILE_SETUP".into(),
                    "SPAWN_ONE_ASSIGNED_CHILD".into(),
                    "PIDFD_OPEN_ASSIGNED_CHILD".into(),
                    "PIDFD_SEND_SIGNAL_SIGKILL".into(),
                    "FRESH_EXEC_REOPEN".into(),
                    "WRITE_BOUND_RECEIPTS".into(),
                    "CLEANUP_EXACT_RUN_ROOT".into(),
                ],
                batch_invalid_on_any_oom: true,
                batch_invalid_on_timeout_or_leaked_child: true,
                block_device_write_allowed: false,
                child_descendants_allowed: false,
                cleanup_policy_sha256: repeated(0x47),
                credential_access_allowed: false,
                drop_caches_allowed: false,
                mount_or_unmount_allowed: false,
                named_ipc_or_network_control_allowed: false,
                network_allowed: false,
                numeric_pid_signal_fallback_allowed: false,
                paid_resource_allowed: false,
                pidfd_identity_recheck_required: true,
                pidfd_open_required_before_cut: true,
                preflight_policy_sha256: repeated(0x48),
                production_access_allowed: false,
                provider_access_allowed: false,
                reboot_kernel_crash_or_power_fault_allowed: false,
                resource_scope_sha256: repeated(0x49),
                retention_policy_sha256: repeated(0x4a),
                review_policy_sha256: repeated(0x4b),
                root_or_privilege_escalation_allowed: false,
                safety_policy_sha256: repeated(0x4c),
                stop_control_policy_sha256: repeated(0x4d),
            },
            claim_protocol: ClaimProtocolV1 {
                affine_permit_cloneable: false,
                affine_permit_serializable: false,
                authority_control_claim_schema_sha256: repeated(0x4e),
                authorization_registration_required: true,
                cas_failure_allows_automatic_retry: false,
                cas_failure_grants_execution: false,
                cas_failure_mutates_unclaimed: false,
                cas_sql_where_profile: "EXACT_ALL_BINDINGS_AND_CONTROLS_SINGLE_UPDATE".into(),
                cas_where_required_bindings: vec![
                    "authorization_id_sha256".into(),
                    "signed_payload_sha256".into(),
                    "subject_manifest_sha256".into(),
                    "resource_scope_sha256".into(),
                    "signed_revocation_epoch".into(),
                    "claim_namespace_sha256".into(),
                    "claim_key_sha256".into(),
                    "revision".into(),
                    "run_id_sha256".into(),
                    "controller_binary_sha256".into(),
                    "runner_binary_sha256".into(),
                    "capability_nonce_sha256".into(),
                    "preflight_receipt_sha256".into(),
                    "control_snapshot_sha256".into(),
                    "stop_revision".into(),
                    "revocation_revision".into(),
                ],
                claim_implementation_binary_sha256: repeated(0x4f),
                claim_implementation_source_sha256: repeated(0x50),
                claim_implementation_toolchain_sha256: repeated(0x51),
                claim_key_derivation_profile: "SHA256_NAMESPACE_AUTHORIZATION_MANIFEST_RUN".into(),
                claim_key_sha256: repeated(0x52),
                claim_namespace_sha256: repeated(0x53),
                claim_receipt_same_transaction: true,
                claimed_state: CLAIM_CONSUMED.into(),
                consumed_tombstone_absorbing: true,
                consumed_tombstone_deletable: false,
                durable_commit_required_before_permit: true,
                expected_unclaimed_revision: 41,
                failed_cas_expected_affected_rows: 0,
                maximum_successful_claims: 1,
                missing_row_may_be_created_by_claim: false,
                permit_binds_capability_nonce: true,
                permit_binds_controller_runner_and_run: true,
                single_use_claim_required: true,
                successful_cas_expected_affected_rows: 1,
                successful_claim_then_crash_allows_retry: false,
                transition: CLAIM_TRANSITION.into(),
                unclaimed_state: CLAIM_UNCLAIMED.into(),
                upsert_or_replace_allowed: false,
            },
            control_protocol: ControlProtocolV1 {
                absorbing_stop_clear_state: STOP_CLEAR.into(),
                absorbing_stop_triggered_state: STOP_TRIGGERED.into(),
                anti_rollback_policy_sha256: repeated(0x54),
                cas_and_control_reads_same_sqlite_transaction: true,
                control_implementation_binary_sha256: repeated(0x55),
                control_implementation_source_sha256: repeated(0x56),
                control_implementation_toolchain_sha256: repeated(0x57),
                control_ledger_identity_sha256: repeated(0x58),
                control_snapshot_schema_sha256: repeated(0x59),
                current_epoch_source_profile:
                    "EXTERNAL_AUTHORITY_CONTROL_LEDGER_EXACT_CURRENT_EPOCH".into(),
                external_state_is_outside_owner_envelope: true,
                missing_or_unknown_control_state_fails_closed: true,
                post_claim_pre_start_recheck_required: true,
                revocation_epoch_comparison: "ANCHOR_FLOOR_LE_EXTERNAL_EQ_SIGNED".into(),
                revocation_epoch_monotonic: true,
                revocation_ledger_revision_monotonic: true,
                revocation_policy_identity_required: true,
                runtime_action_boundary_recheck_required: true,
                same_transaction_required_table_ids: vec![
                    "authority_control".into(),
                    "claim_ledger".into(),
                    "claim_receipts".into(),
                ],
                stop_ledger_revision_monotonic: true,
                stop_policy_identity_required: true,
                stop_transition: "CLEAR_TO_TRIGGERED_ABSORBING".into(),
                stop_triggered_is_absorbing: true,
                trusted_wall_clock_is_freshness: false,
            },
            receipt_bindings: ReceiptBindingsV1 {
                authority_control_claim_schema_sha256: repeated(0x4e),
                claim_receipt_is_owner_envelope: false,
                cleanup_or_custody_receipt_is_owner_envelope: false,
                control_snapshot_schema_sha256: repeated(0x59),
                post_run_bundle_schema_sha256: repeated(0x5a),
                post_run_receipts_grant_authority: false,
                preflight_receipt_is_owner_envelope: false,
                preflight_receipt_schema_sha256: repeated(0x5b),
                raw_observation_schema_sha256: S17_OBSERVATION_SCHEMA_SHA256.into(),
                receipt_hash_domain_profile: "DOMAIN_SEPARATED_PARENT_SHA256_CHAIN".into(),
                receipt_parent_chain: vec![
                    "PREFLIGHT".into(),
                    "CONTROL_SNAPSHOT".into(),
                    "CLAIM".into(),
                    "RAW_OBSERVATIONS".into(),
                    "RETENTION".into(),
                    "SEMANTIC".into(),
                    "BATCH_RESULT".into(),
                    "OPTIONAL_STOP".into(),
                    "CLEANUP".into(),
                    "CUSTODY".into(),
                ],
                stop_receipt_required_if_triggered: true,
                subject_manifest_schema_sha256: repeated(0x26),
            },
            test_only: true,
        }
    }

    fn signing_request(anchor_sha256: [u8; 32]) -> PinnedOwnerSigningRequestV1 {
        PinnedOwnerSigningRequestV1 {
            trust_anchor_document_sha256: anchor_sha256,
            owner_identity_sha256: [0x81; 32],
            owner_key_id: "rfc8032-test-only-owner".into(),
            owner_key_version: 3,
            trust_policy_sha256: [0x82; 32],
            decision_nonce_sha256: [0x83; 32],
            capability_nonce_sha256: [0x4c; 32],
            issued_at_utc_audit_only: "2026-07-17T00:00:00Z".into(),
            expires_at_utc_audit_only: "2026-07-17T00:15:00Z".into(),
            revocation_epoch: 7,
        }
    }

    fn anchor_value() -> Value {
        serde_json::json!({
            "anchor_state": "ACTIVE_OWNER_PINNED_PUBLIC_KEY",
            "audience": "AGENT_BRIDGE_S18_OWNED_LAB_L1_ONLY",
            "authorization_envelope_embedded": false,
            "authorized_claim_level": "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY",
            "authorized_family_namespace": "OL00_OL04_OL05_FIRST_BATCH",
            "canonicalization": CANONICAL_PROFILE,
            "ed25519_public_key_hex": hex(&RFC8032_TEST_ONLY_PUBLIC_KEY),
            "execution_capability_embedded": false,
            "installation_receipt_sha256": repeated(0x91),
            "installation_source": "OWNER_CONTROLLED_OUT_OF_BAND_PIN_NOT_AUTHORIZATION_ENVELOPE",
            "minimum_revocation_epoch": 7,
            "owner_identity_sha256": repeated(0x81),
            "owner_identity_verification_receipt_sha256": repeated(0x92),
            "owner_key_id": "rfc8032-test-only-owner",
            "owner_key_version": 3,
            "owner_role": "OWNED_LAB_EXECUTION_OWNER",
            "packet_kind": "OUT_OF_BAND_OWNED_LAB_OWNER_TRUST_ANCHOR",
            "private_key_present": false,
            "provider_or_production_authority": false,
            "schema": ANCHOR_SCHEMA,
            "self_asserted_key_is_owner_authentication": false,
            "side_effects_unlocked": "NONE",
            "signature_algorithm": "Ed25519",
            "trust_policy_sha256": repeated(0x82)
        })
    }

    fn resign(payload: Value) -> Value {
        let key = Ed25519KeyPair::from_seed_unchecked(&RFC8032_TEST_ONLY_SEED).unwrap();
        let payload_raw = restricted_canonical_bytes(&payload).unwrap();
        let payload_sha = sha256_bytes(&payload_raw);
        let signature: [u8; 64] = key
            .sign(&signed_message(&payload_sha).unwrap())
            .as_ref()
            .try_into()
            .unwrap();
        serde_json::json!({
            "authentication": {
                "detached_signature_hex": hex(&signature),
                "detached_signature_sha256": hex(&sha256_bytes(&signature)),
                "public_key_carried_by_envelope": false,
                "self_asserted_signature_valid": false,
                "signature_algorithm": "Ed25519",
                "signature_message_domain": std::str::from_utf8(MESSAGE_DOMAIN).unwrap(),
                "signed_payload_sha256": hex(&payload_sha)
            },
            "canonicalization": CANONICAL_PROFILE,
            "packet_kind": "OWNER_SIGNED_OWNED_LAB_AUTHORIZATION_ENVELOPE",
            "payload": payload,
            "schema": ENVELOPE_SCHEMA,
            "signature_message_profile": MESSAGE_PROFILE
        })
    }

    struct Fixture {
        anchor_raw: Vec<u8>,
        envelope_raw: Vec<u8>,
        manifest_raw: Vec<u8>,
        inputs: IndependentSubjectInputsV1,
        signing: PinnedOwnerSigningRequestV1,
    }

    fn fixture() -> Fixture {
        let inputs = fixture_inputs();
        let manifest = build_subject_manifest_v1(&inputs).unwrap();
        let manifest_value = serde_json::to_value(manifest).unwrap();
        let manifest_raw = restricted_canonical_bytes(&manifest_value).unwrap();
        let subject = verify_subject_manifest_v1(&manifest_raw, &inputs).unwrap();
        let anchor_raw = restricted_canonical_bytes(&anchor_value()).unwrap();
        let signing = signing_request(sha256_bytes(&anchor_raw));
        let payload = build_expected_s18_payload_v1(&subject, &inputs, &signing).unwrap();
        let envelope_raw = restricted_canonical_bytes(&resign(payload)).unwrap();
        Fixture {
            anchor_raw,
            envelope_raw,
            manifest_raw,
            inputs,
            signing,
        }
    }

    fn authorized(fixture: &Fixture) -> AuthorizedUnclaimedS19SubjectV1 {
        verify_authorized_unclaimed_subject_v1(
            &fixture.anchor_raw,
            &fixture.envelope_raw,
            &fixture.manifest_raw,
            &fixture.inputs,
            &fixture.signing,
        )
        .unwrap()
    }

    fn scratch_path() -> PathBuf {
        let root = std::env::var_os("AB_S19_TEST_SCRATCH")
            .map(PathBuf::from)
            .unwrap_or_else(std::env::temp_dir);
        std::fs::create_dir_all(&root).unwrap();
        root.join(format!(
            "s19-claim-{}-{}.sqlite3",
            std::process::id(),
            NEXT_PATH.fetch_add(1, Ordering::Relaxed)
        ))
    }

    fn controls(authorized: &AuthorizedUnclaimedS19SubjectV1) -> ControlSnapshotV1 {
        let ledger = authorized.subject.control_ledger_identity_sha256;
        let anti_rollback = authorized.subject.anti_rollback_policy_sha256;
        let stop_policy = authorized.subject.stop_control_policy_sha256;
        let revocation_policy = authorized.revocation_policy_sha256;
        let sqlite_profile = authorized.subject.sqlite_profile_sha256;
        let sqlite_schema = authorized.subject.sqlite_schema_sha256;
        let stop_revision = 11;
        let revocation_revision = 13;
        let epoch = authorized.authorization.revocation_epoch;
        ControlSnapshotV1 {
            stop_state: STOP_CLEAR.into(),
            stop_revision,
            current_revocation_epoch: epoch,
            revocation_revision,
            control_ledger_identity_sha256: ledger,
            anti_rollback_policy_sha256: anti_rollback,
            stop_control_policy_sha256: stop_policy,
            revocation_policy_sha256: revocation_policy,
            sqlite_profile_sha256: sqlite_profile,
            sqlite_schema_sha256: sqlite_schema,
            snapshot_sha256: control_snapshot_digest(
                &authorized.subject.canonical_manifest_sha256,
                STOP_CLEAR,
                stop_revision,
                epoch,
                revocation_revision,
                &ledger,
                &anti_rollback,
                &stop_policy,
                &revocation_policy,
                &sqlite_profile,
                &sqlite_schema,
            )
            .unwrap(),
        }
    }

    fn preflight_probe(authorized: &AuthorizedUnclaimedS19SubjectV1) -> PreflightProbeV1 {
        PreflightProbeV1 {
            run_id_sha256: [0x72; 32],
            controller_binary_sha256: authorized.subject.controller_binary_sha256,
            runner_binary_sha256: authorized.subject.runner_binary_sha256,
            observer_binary_sha256: authorized.subject.preflight_observer_binary_sha256,
            capability_nonce_sha256: authorized.capability_nonce_sha256,
            challenge_nonce_sha256: [0x74; 32],
            boot_id_sha256: authorized.subject.boot_id_sha256,
            root_parent_identity_sha256: authorized.subject.root_parent_identity_sha256,
            run_root_absent: true,
            environment_matches_manifest: true,
            resource_limits_active: true,
            forbidden_operations_absent: true,
        }
    }

    fn refresh_control_snapshot_digest(
        authorized: &AuthorizedUnclaimedS19SubjectV1,
        controls: &mut ControlSnapshotV1,
    ) {
        controls.snapshot_sha256 = control_snapshot_digest(
            &authorized.subject.canonical_manifest_sha256,
            &controls.stop_state,
            controls.stop_revision,
            controls.current_revocation_epoch,
            controls.revocation_revision,
            &controls.control_ledger_identity_sha256,
            &controls.anti_rollback_policy_sha256,
            &controls.stop_control_policy_sha256,
            &controls.revocation_policy_sha256,
            &controls.sqlite_profile_sha256,
            &controls.sqlite_schema_sha256,
        )
        .unwrap();
    }

    fn preflight(
        authorized: &AuthorizedUnclaimedS19SubjectV1,
        controls: ControlSnapshotV1,
    ) -> ValidatedPreflightV1 {
        validate_preflight_v1(authorized, preflight_probe(authorized), controls).unwrap()
    }

    fn cleanup(path: &Path) {
        let _ = std::fs::remove_file(path);
    }

    #[test]
    fn s19_typed_manifest_independent_expected_and_s18_opaque_composition_accept() {
        let fixture = fixture();
        let verified = authorized(&fixture);
        assert!(nonzero(&verified.subject.canonical_manifest_sha256));
        assert_eq!(
            hex(&verified.subject.source_commit),
            fixture.inputs.build_identity.s19_source_commit
        );
        assert_eq!(
            hex(&verified.subject.integration_commit),
            fixture.inputs.build_identity.s19_integration_commit
        );
        assert!(nonzero(&verified.authorization.authorization_id_sha256));
        assert!(format!("{verified:?}").contains("NOT_PERMIT"));
        assert_eq!(S18_SOURCE_COMMIT.len(), 40);
    }

    #[test]
    fn s19_committed_synthetic_manifest_frame_matches_typed_builder_exactly() {
        const COMMITTED: &[u8] = include_bytes!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../docs/design/fixtures/biocortex-ab-track-b-owned-lab-subject-manifest-synthetic-s19-v0.json"
        ));
        assert!(COMMITTED.ends_with(b"\n"));
        let canonical_payload = COMMITTED
            .strip_suffix(b"\n")
            .expect("repository fixture framing is exactly one trailing LF");
        assert!(!canonical_payload.contains(&b'\n'));
        let fixture = fixture();
        assert!(
            canonical_payload == fixture.manifest_raw,
            "committed synthetic payload {} differs from typed builder {}",
            hex(&sha256_bytes(canonical_payload)),
            hex(&sha256_bytes(&fixture.manifest_raw))
        );
    }

    #[test]
    fn s19_candidate_manifest_cannot_redefine_independent_expected_binding() {
        let fixture = fixture();
        let mut candidate: Value = serde_json::from_slice(&fixture.manifest_raw).unwrap();
        candidate["build_identity"]["runner_binary_sha256"] = Value::String(repeated(0xaa));
        let candidate_raw = restricted_canonical_bytes(&candidate).unwrap();
        assert_eq!(
            verify_subject_manifest_v1(&candidate_raw, &fixture.inputs)
                .unwrap_err()
                .code(),
            "s19_independent_expected_binding"
        );
    }

    #[test]
    fn s19_manifest_canonical_unknown_duplicate_depth_and_size_reject() {
        let fixture = fixture();
        let mut unknown: Value = serde_json::from_slice(&fixture.manifest_raw).unwrap();
        unknown["unexpected"] = Value::Bool(false);
        assert!(verify_subject_manifest_v1(
            &restricted_canonical_bytes(&unknown).unwrap(),
            &fixture.inputs
        )
        .is_err());
        let duplicate = fixture
            .manifest_raw
            .strip_suffix(b"}")
            .unwrap()
            .iter()
            .copied()
            .chain(b",\"test_only\":true}".iter().copied())
            .collect::<Vec<_>>();
        assert!(verify_subject_manifest_v1(&duplicate, &fixture.inputs).is_err());
        let mut deep = serde_json::json!(0);
        for _ in 0..17 {
            deep = serde_json::json!([deep]);
        }
        assert!(restricted_canonical_bytes(&deep).is_err());
        assert!(parse_restricted_canonical(&vec![b' '; MAX_DOCUMENT_BYTES + 1]).is_err());
    }

    #[test]
    fn s19_preflight_rejects_manifest_bound_control_and_environment_drift() {
        let fixture = fixture();
        let authorized = authorized(&fixture);
        let mut drifted_controls = controls(&authorized);
        drifted_controls.control_ledger_identity_sha256 = [0xa1; 32];
        refresh_control_snapshot_digest(&authorized, &mut drifted_controls);
        assert!(
            validate_preflight_v1(&authorized, preflight_probe(&authorized), drifted_controls)
                .is_err()
        );

        let exact_controls = controls(&authorized);
        let mut drifted_probe = preflight_probe(&authorized);
        drifted_probe.boot_id_sha256 = [0xa2; 32];
        assert!(validate_preflight_v1(&authorized, drifted_probe, exact_controls.clone()).is_err());
        let mut drifted_probe = preflight_probe(&authorized);
        drifted_probe.root_parent_identity_sha256 = [0xa3; 32];
        assert!(validate_preflight_v1(&authorized, drifted_probe, exact_controls.clone()).is_err());
        let mut drifted_probe = preflight_probe(&authorized);
        drifted_probe.observer_binary_sha256 = [0xa4; 32];
        assert!(validate_preflight_v1(&authorized, drifted_probe, exact_controls).is_err());
    }

    #[test]
    fn s19_failed_cas_after_control_drift_leaves_unclaimed_and_never_retries() {
        let fixture = fixture();
        let authorized = authorized(&fixture);
        let initial_controls = controls(&authorized);
        let preflight = preflight(&authorized, initial_controls.clone());
        let path = scratch_path();
        initialize_new_synthetic_ledger_for_test(&path, &authorized, &initial_controls).unwrap();
        let connection = open_existing_ledger(&path).unwrap();
        update_controls_for_test(
            &connection,
            STOP_TRIGGERED,
            initial_controls.stop_revision + 1,
            initial_controls.current_revocation_epoch,
            initial_controls.revocation_revision,
        )
        .unwrap();
        drop(connection);
        let mut connection = open_existing_ledger(&path).unwrap();
        assert!(matches!(
            try_claim_once_v1(&mut connection, &authorized, preflight).unwrap(),
            ClaimAttemptV1::FailedCas
        ));
        let state: (String, i64, i64) = connection
            .query_row(
                "SELECT state,revision,successful_claim_count FROM claim_ledger",
                [],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .unwrap();
        assert_eq!(state, (CLAIM_UNCLAIMED.into(), 41, 0));
        cleanup(&path);
    }

    #[test]
    fn s19_successful_claim_reopen_is_consumed_and_second_claim_fails() {
        let fixture = fixture();
        let authorized = authorized(&fixture);
        let initial_controls = controls(&authorized);
        let first_preflight = preflight(&authorized, initial_controls.clone());
        let path = scratch_path();
        initialize_new_synthetic_ledger_for_test(&path, &authorized, &initial_controls).unwrap();
        let claim = {
            let mut connection = open_existing_ledger(&path).unwrap();
            match try_claim_once_v1(&mut connection, &authorized, first_preflight).unwrap() {
                ClaimAttemptV1::Claimed(claim) => claim,
                ClaimAttemptV1::FailedCas => panic!("first exact claim must succeed"),
            }
        };
        let mut reopened = open_existing_ledger(&path).unwrap();
        let state: String = reopened
            .query_row("SELECT state FROM claim_ledger", [], |row| row.get(0))
            .unwrap();
        assert_eq!(state, CLAIM_CONSUMED);
        let second_controls =
            read_control_snapshot(&reopened, &authorized.subject.canonical_manifest_sha256)
                .unwrap();
        let second_preflight = preflight(&authorized, second_controls);
        assert!(matches!(
            try_claim_once_v1(&mut reopened, &authorized, second_preflight).unwrap(),
            ClaimAttemptV1::FailedCas
        ));
        assert!(reopened
            .execute("UPDATE claim_ledger SET state='AUTHORIZED_UNCLAIMED'", [],)
            .is_err());
        let delete_claim = ["DELETE", "FROM claim_ledger"].join(" ");
        assert!(reopened.execute(&delete_claim, []).is_err());
        let delete_receipt = ["DELETE", "FROM claim_receipts"].join(" ");
        assert!(reopened.execute(&delete_receipt, []).is_err());
        assert!(nonzero(&claim.claim_receipt_sha256));
        cleanup(&path);
    }

    #[test]
    fn s19_claim_then_stop_change_blocks_permit_but_remains_consumed() {
        let fixture = fixture();
        let authorized = authorized(&fixture);
        let initial_controls = controls(&authorized);
        let preflight = preflight(&authorized, initial_controls.clone());
        let path = scratch_path();
        initialize_new_synthetic_ledger_for_test(&path, &authorized, &initial_controls).unwrap();
        let mut connection = open_existing_ledger(&path).unwrap();
        let claim = match try_claim_once_v1(&mut connection, &authorized, preflight).unwrap() {
            ClaimAttemptV1::Claimed(claim) => claim,
            ClaimAttemptV1::FailedCas => panic!("first exact claim must succeed"),
        };
        update_controls_for_test(
            &connection,
            STOP_TRIGGERED,
            initial_controls.stop_revision + 1,
            initial_controls.current_revocation_epoch,
            initial_controls.revocation_revision,
        )
        .unwrap();
        assert!(
            redeem_consumed_claim_after_fresh_controls_v1(&connection, &authorized, claim).is_err()
        );
        let state: String = connection
            .query_row("SELECT state FROM claim_ledger", [], |row| row.get(0))
            .unwrap();
        assert_eq!(state, CLAIM_CONSUMED);
        cleanup(&path);
    }

    #[test]
    fn s19_action_boundary_rechecks_absorbing_stop() {
        let fixture = fixture();
        let authorized = authorized(&fixture);
        let initial_controls = controls(&authorized);
        let preflight = preflight(&authorized, initial_controls.clone());
        let path = scratch_path();
        initialize_new_synthetic_ledger_for_test(&path, &authorized, &initial_controls).unwrap();
        let mut connection = open_existing_ledger(&path).unwrap();
        let claim = match try_claim_once_v1(&mut connection, &authorized, preflight).unwrap() {
            ClaimAttemptV1::Claimed(claim) => claim,
            ClaimAttemptV1::FailedCas => panic!("first exact claim must succeed"),
        };
        let mut permit =
            redeem_consumed_claim_after_fresh_controls_v1(&connection, &authorized, claim).unwrap();
        assert!(nonzero(&permit.permit_sha256));
        {
            let guard =
                authorize_action_boundary_v1(&connection, &authorized, &mut permit, 0).unwrap();
            assert_eq!(guard.attempt_index, 0);
            std::mem::forget(guard);
        }
        assert!(authorize_action_boundary_v1(&connection, &authorized, &mut permit, 0).is_err());
        update_controls_for_test(
            &connection,
            STOP_TRIGGERED,
            initial_controls.stop_revision + 1,
            initial_controls.current_revocation_epoch,
            initial_controls.revocation_revision,
        )
        .unwrap();
        assert!(authorize_action_boundary_v1(&connection, &authorized, &mut permit, 1).is_err());
        cleanup(&path);
    }

    #[test]
    fn s19_stop_is_absorbing_and_revocation_is_monotonic() {
        let fixture = fixture();
        let authorized = authorized(&fixture);
        let initial_controls = controls(&authorized);
        let path = scratch_path();
        initialize_new_synthetic_ledger_for_test(&path, &authorized, &initial_controls).unwrap();
        let connection = open_existing_ledger(&path).unwrap();
        update_controls_for_test(
            &connection,
            STOP_TRIGGERED,
            initial_controls.stop_revision + 1,
            initial_controls.current_revocation_epoch + 1,
            initial_controls.revocation_revision + 1,
        )
        .unwrap();
        assert!(update_controls_for_test(
            &connection,
            STOP_CLEAR,
            initial_controls.stop_revision + 2,
            initial_controls.current_revocation_epoch + 1,
            initial_controls.revocation_revision + 2
        )
        .is_err());
        let delete_control = ["DELETE", "FROM authority_control"].join(" ");
        assert!(connection.execute(&delete_control, []).is_err());
        cleanup(&path);
    }

    #[test]
    fn s19_post_run_validator_keeps_receipts_separate_from_authority() {
        let fixture = fixture();
        let authorized = authorized(&fixture);
        let initial_controls = controls(&authorized);
        let preflight = preflight(&authorized, initial_controls.clone());
        let path = scratch_path();
        initialize_new_synthetic_ledger_for_test(&path, &authorized, &initial_controls).unwrap();
        let mut connection = open_existing_ledger(&path).unwrap();
        let claim = match try_claim_once_v1(&mut connection, &authorized, preflight).unwrap() {
            ClaimAttemptV1::Claimed(claim) => claim,
            ClaimAttemptV1::FailedCas => panic!("first exact claim must succeed"),
        };
        let permit =
            redeem_consumed_claim_after_fresh_controls_v1(&connection, &authorized, claim).unwrap();
        let bundle = PostRunReceiptBundleV1 {
            manifest_sha256: authorized.subject.canonical_manifest_sha256,
            claim_receipt_sha256: permit.claim_receipt_sha256,
            run_id_sha256: permit.run_id_sha256,
            assigned_attempt_count: 60,
            pidfd_sigkill_attempt_count: 59,
            distinct_fresh_exec_read_count: 59,
            total_s16_mapping_phase_record_count: 113,
            retention_receipt_sha256: [0x81; 32],
            semantic_receipt_sha256: [0x82; 32],
            batch_result_receipt_sha256: [0x83; 32],
            stop_receipt_sha256: None,
            cleanup_receipt_sha256: [0x84; 32],
            custody_receipt_sha256: [0x85; 32],
            oom_event_count: 0,
            timeout_or_leaked_child_count: 0,
            retry_count: 0,
        };
        validate_post_run_receipts_v1(&authorized, &permit, &bundle).unwrap();
        let mut invalid = bundle.clone();
        invalid.retry_count = 1;
        assert!(validate_post_run_receipts_v1(&authorized, &permit, &invalid).is_err());
        cleanup(&path);
    }

    #[test]
    fn s19_missing_ledger_never_creates_on_reopen() {
        let path = scratch_path();
        assert!(!path.exists());
        assert!(open_existing_ledger(&path).is_err());
        assert!(!path.exists());
    }

    #[test]
    fn s19_sqlite_schema_profile_is_frozen_and_reopen_verified() {
        let fixture = fixture();
        let authorized = authorized(&fixture);
        let initial_controls = controls(&authorized);
        let path = scratch_path();
        initialize_new_synthetic_ledger_for_test(&path, &authorized, &initial_controls).unwrap();
        let raw_connection = open_ledger_file_without_create(&path).unwrap();
        let actual_schema_sha256 = sqlite_schema_catalog_digest(&raw_connection).unwrap();
        assert_eq!(
            hex(&actual_schema_sha256),
            SQLITE_SCHEMA_CATALOG_SHA256,
            "frozen schema catalog digest must match the actual SQLite catalog"
        );
        drop(raw_connection);
        open_existing_ledger(&path).unwrap();
        let drifted_schema = open_ledger_file_without_create(&path).unwrap();
        drifted_schema
            .execute("CREATE TABLE unexpected_schema_object(value INTEGER)", [])
            .unwrap();
        drop(drifted_schema);
        assert!(open_existing_ledger(&path).is_err());
        cleanup(&path);

        let application_path = scratch_path();
        initialize_new_synthetic_ledger_for_test(&application_path, &authorized, &initial_controls)
            .unwrap();
        let drifted_application = open_ledger_file_without_create(&application_path).unwrap();
        drifted_application
            .execute_batch("PRAGMA application_id=7;")
            .unwrap();
        drop(drifted_application);
        assert!(open_existing_ledger(&application_path).is_err());
        cleanup(&application_path);
    }

    #[test]
    fn s19_current_stage_has_no_live_dispatch_or_real_side_effect_counter() {
        let source = include_str!("source_bound_runner.rs");
        let production = source
            .split("#[cfg(test)]")
            .next()
            .expect("the production source prefix must exist");
        for forbidden in [
            "std::process::Command",
            "pidfd_send_signal(",
            "libc::kill(",
            "TcpStream",
            "reqwest",
            "mount(",
            "umount(",
        ] {
            assert!(!production.contains(forbidden));
        }
        assert_eq!(fixed_nonclaims().actual_assigned_attempt_count, 0);
        assert_eq!(fixed_nonclaims().actual_sigkill_attempt_count, 0);
        assert_eq!(fixed_nonclaims().actual_observation_count, 0);
        assert_eq!(fixed_nonclaims().side_effects_unlocked, "NONE");
    }
}
