#!/usr/bin/env python3
"""Validate the public-synthetic G1.4 native-adapter preregistration.

This is a design-only validator. It does not compile or apply Seatbelt,
Landlock, seccomp, bwrap, or nono policy; launch a process; inspect a private
corpus; consume a capability; or register a runtime surface.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

from engram_g1_corpus_design import (
    InputError,
    read_json,
    read_stable_bounded_file,
    reject_raw_fields,
    render_json,
    require_exact_fields,
    require_exact_value,
    require_list,
    require_object,
    sha256_bytes,
    sha256_canonical,
)

CONTRACT_SCHEMA = (
    "agent_bridge.engram_g1_4_native_sandbox_adapter_preregistration_contract.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_4_native_sandbox_adapter_preregistration_receipt.v0"
)
CONTRACT_ID = "engram_g14_native_sandbox_adapter_preregistration_20260718"
CONTRACT_SHA256 = "075dd9be4f6097e539db62025e6420b9add0efc030c528c065b612a77f5d78e0"
CONTRACT_SEMANTIC_SHA256 = (
    "3c5b2ce5d356972697044c39bb5ececd391797ddd73fcd3a2c894f3580521333"
)
PREDECESSOR_COMMIT = "41bf1b9e33b73e61adc567b668cbf2ed4cb7867c"
PREDECESSOR_ARTIFACTS = {
    "implementation": (
        "scripts/eval/engram_g14_public_synthetic_protocol_harness.py",
        "52cc851419880f93d8585fee1a4378788564bbcadbeb84161d4e40e67c51ed05",
    ),
    "checker": (
        "scripts/eval/check_engram_g14_public_synthetic_protocol_harness.py",
        "bc896b9d284cc644be965dcb7fa20ea80ff5629783922ce7b54bfedd3ed9df10",
    ),
    "contract": (
        "scripts/eval/fixtures/engram_g14_public_synthetic_protocol_harness_contract_v0.json",
        "6fae57e239594978810d03d2aee33133d3af8439527dd6aadef6884d5bba1b9d",
    ),
    "fixture": (
        "scripts/eval/fixtures/engram_g14_public_synthetic_protocol_harness_fixture_v0.json",
        "477cf9b326f52fc3f8ce9138346bb55e2692e5b473ac5f0c5d9b24e457350607",
    ),
    "shell_entrypoint": (
        "scripts/check-engram-g14-public-synthetic-protocol-harness.sh",
        "c236e05e22413a0cf0027a2b40e556deec7fb3c6a8319ec04d8c7d7919927425",
    ),
}
NONO_VERSION = "0.53.0"
NONO_CHECKSUM = "ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee"
VALIDATOR_HELPER_SHA256 = (
    "2a408d64b34605f434377b3c11f71807f6c81068aa7bcba069c8d3a6dc44cb91"
)
FUTURE_MODE = "PUBLIC_SYNTHETIC_NATIVE_SANDBOX_ADAPTER_KAT"
ONLY_SUCCESSOR = (
    "separate_public_synthetic_native_sandbox_adapter_kat_implementation_gate"
)
EXPECTED_PHASES = [
    "artifact_preflight",
    "one_shot_claim",
    "platform_support",
    "policy_compile",
    "policy_apply",
    "active_attestation",
    "negative_controls",
    "allowed_canaries",
    "denied_canaries",
    "cleanup",
    "receipt_finalize",
]
EXPECTED_CLASSES = ["native_kernel", "launch_boundary", "supervisor_mediation"]
DESIGN_BASE_COMMIT = "36d3e8a4f05caa2731dc8224b035e2f1ac4f4d73"
EXPECTED_CHANGED_PATHS = [
    "docs/design/ENGRAM_G1_4_NATIVE_SANDBOX_ADAPTER_PREREGISTRATION_2026_07_18.md",
    "docs/design/ENGRAM_G1_4_NATIVE_SANDBOX_ADAPTER_PREREGISTRATION_RESULT_2026_07_18.md",
    "scripts/check-engram-g14-native-sandbox-adapter-preregistration.sh",
    "scripts/eval/README.md",
    "scripts/eval/check_engram_g14_native_sandbox_adapter_preregistration.py",
    "scripts/eval/engram_g14_native_sandbox_adapter_preregistration.py",
    "scripts/eval/fixtures/engram_g14_native_sandbox_adapter_preregistration_contract_v0.json",
]
EXPECTED_CHANGE_SCOPE_PHASES = ["precommit", "postcommit"]
EXPECTED_CANARIES = [
    ("candidate_code_read", "allow", "native_kernel"),
    ("dependency_read", "allow", "native_kernel"),
    ("ephemeral_scratch_write", "allow", "native_kernel"),
    ("repository_metadata_read", "deny", "native_kernel"),
    ("private_manifest_read", "deny", "native_kernel"),
    ("live_store_read", "deny", "native_kernel"),
    ("network_connect", "deny", "native_kernel"),
    ("subprocess_spawn", "deny", "native_kernel"),
    ("dynamic_plugin_load", "deny", "native_kernel"),
    ("non_scratch_write", "deny", "native_kernel"),
    ("wall_clock_read", "deny", "native_kernel"),
    ("external_entropy_read", "deny", "native_kernel"),
    ("extra_inherited_fd_use", "deny", "launch_boundary"),
    ("free_form_output", "deny", "supervisor_mediation"),
]
EXPECTED_PHASE_RECEIPTS = [
    (
        "artifact_preflight",
        "agent_bridge.engram_g1_4_native_kat_artifact_preflight_receipt.v0",
        "supervisor_prelaunch_verifier",
        [
            "contract_sha256",
            "probe_source_sha256",
            "probe_build_sha256",
            "dependency_lock_sha256",
            "fixture_sha256",
        ],
    ),
    (
        "one_shot_claim",
        "agent_bridge.engram_g1_4_native_kat_one_shot_claim_receipt.v0",
        "supervisor_attempt_registry",
        ["run_id_commitment_sha256", "claim_sequence", "claim_consumed"],
    ),
    (
        "platform_support",
        "agent_bridge.engram_g1_4_native_kat_platform_support_receipt.v0",
        "supervisor_captured_platform_probe",
        [
            "platform",
            "kernel_and_abi_commitment_sha256",
            "primitive_support_matrix_sha256",
            "all_required_controls_supported",
        ],
    ),
    (
        "policy_compile",
        "agent_bridge.engram_g1_4_native_kat_policy_compile_receipt.v0",
        "supervisor_captured_policy_compiler",
        [
            "policy_input_sha256",
            "generated_policy_sha256",
            "dependency_and_rule_order_sha256",
            "compile_succeeded",
        ],
    ),
    (
        "policy_apply",
        "agent_bridge.engram_g1_4_native_kat_policy_apply_receipt.v0",
        "native_apply_boundary_captured_by_supervisor",
        [
            "generated_policy_sha256",
            "subject_process_identity_commitment_sha256",
            "apply_result_code",
            "apply_succeeded",
        ],
    ),
    (
        "active_attestation",
        "agent_bridge.engram_g1_4_native_kat_active_attestation_receipt.v0",
        "native_subject_boundary_captured_by_supervisor",
        [
            "support_receipt_sha256",
            "apply_receipt_sha256",
            "subject_process_identity_commitment_sha256",
            "active_reported",
        ],
    ),
    (
        "negative_controls",
        "agent_bridge.engram_g1_4_native_kat_negative_controls_receipt.v0",
        "supervisor_control_runner",
        [
            "control_fixture_sha256",
            "control_attempt_set_sha256",
            "live_control_count",
            "all_controls_unambiguous",
        ],
    ),
    (
        "allowed_canaries",
        "agent_bridge.engram_g1_4_native_kat_allowed_canaries_receipt.v0",
        "sandboxed_probe_captured_by_supervisor",
        [
            "subject_process_identity_commitment_sha256",
            "allowed_canary_observations_sha256",
            "allowed_canary_count",
            "all_allowed_canaries_matched",
        ],
    ),
    (
        "denied_canaries",
        "agent_bridge.engram_g1_4_native_kat_denied_canaries_receipt.v0",
        "sandboxed_probe_captured_by_supervisor",
        [
            "subject_process_identity_commitment_sha256",
            "denied_canary_observations_sha256",
            "denied_canary_count",
            "all_denied_canaries_matched",
        ],
    ),
    (
        "cleanup",
        "agent_bridge.engram_g1_4_native_kat_cleanup_receipt.v0",
        "supervisor_cleanup_verifier",
        [
            "synthetic_root_commitment_sha256",
            "cleanup_target_set_sha256",
            "residue_count",
            "cleanup_verified",
        ],
    ),
    (
        "receipt_finalize",
        "agent_bridge.engram_g1_4_native_kat_final_receipt.v0",
        "supervisor_receipt_finalizer",
        [
            "previous_event_sha256",
            "expected_chain_head_sha256",
            "authority_class",
            "production_admissible",
            "g1_4_execution_open",
            "verdict",
        ],
    ),
]
EXPECTED_LESSON_FIELDS = [
    "lesson_id_sha256",
    "parent_run_id_commitment_sha256",
    "failure_phase",
    "reason_code",
    "cleanup_target_set_sha256",
    "residue_count",
    "lesson_sequence",
    "previous_lesson_sha256",
    "lesson_sha256",
]
EXPECTED_MANUAL_AUDIT_EVENTS = [
    "first_real_freeze_capability_consumption_or_private_run_plan_open",
    "candidate_or_runner_source_config_dependency_or_toolchain_change_after_final_lock",
    "fit_development_sealed_or_partition_access_policy_widening",
    "metric_threshold_arm_resource_retry_or_missingness_policy_change_after_any_observation",
    "sealed_partition_unblinding_selective_retry_or_rerun",
    "sandbox_filesystem_network_subprocess_log_output_or_side_channel_policy_widening_after_preregistration_or_any_real_runner_policy_change",
    "first_real_protocol_runner_enablement",
    "suspected_secret_privacy_identity_corpus_or_result_exposure",
]
EXPECTED_TOP_LEVEL_FIELDS = {
    "schema",
    "contract_id",
    "stage",
    "predecessor_harness",
    "scope",
    "dependency_and_reference_lock",
    "future_kat_interface",
    "enforcement_responsibility_model",
    "platform_adapter_plans",
    "canary_matrix",
    "negative_control_model",
    "run_lifecycle_model",
    "future_receipt_state_machine",
    "rollback_lesson_model",
    "receipt_and_anchor_model",
    "human_audit_policy",
    "threat_model",
    "state_machine",
    "boundaries",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def require_bool_field(
    section: dict[str, Any], field: str, expected: bool, path: str
) -> None:
    value = section[field]
    if type(value) is not bool:
        raise InputError(f"{path}.{field} must remain boolean")
    require_exact_value(value, expected, f"{path}.{field}")


def validate_predecessor(contract: dict[str, Any]) -> None:
    path = "contract.predecessor_harness"
    predecessor = require_object(contract["predecessor_harness"], path)
    require_exact_fields(
        predecessor,
        {
            "commit",
            "contract_id",
            "implementation_sha256",
            "checker_sha256",
            "contract_sha256",
            "fixture_sha256",
            "shell_entrypoint_sha256",
            "immutable",
        },
        path,
    )
    require_exact_value(predecessor["commit"], PREDECESSOR_COMMIT, f"{path}.commit")
    require_exact_value(
        predecessor["contract_id"],
        "engram_g14_public_synthetic_protocol_harness_20260718",
        f"{path}.contract_id",
    )
    for name, (_, expected_digest) in PREDECESSOR_ARTIFACTS.items():
        field = f"{name}_sha256"
        require_exact_value(predecessor[field], expected_digest, f"{path}.{field}")
    require_bool_field(predecessor, "immutable", True, path)


def validate_scope(contract: dict[str, Any]) -> None:
    path = "contract.scope"
    scope = require_object(contract["scope"], path)
    require_exact_value(
        scope["future_exact_mode"], FUTURE_MODE, f"{path}.future_exact_mode"
    )
    require_exact_value(
        scope["only_permitted_successor"],
        ONLY_SUCCESSOR,
        f"{path}.only_permitted_successor",
    )
    require_exact_value(
        scope["authority_class"],
        "NONE_DESIGN_VALIDATION_ONLY",
        f"{path}.authority_class",
    )
    require_exact_value(
        scope["admission_effect"],
        "NO_EXECUTION_OR_DATA_AUTHORITY",
        f"{path}.admission_effect",
    )
    require_exact_value(
        scope["permitted_output"],
        "closed_design_validation_receipt_no_authority",
        f"{path}.permitted_output",
    )
    require_exact_value(
        scope["design_base_commit"], DESIGN_BASE_COMMIT, f"{path}.design_base_commit"
    )
    require_exact_value(
        scope["permitted_changed_paths_in_order"],
        EXPECTED_CHANGED_PATHS,
        f"{path}.permitted_changed_paths_in_order",
    )
    require_exact_value(
        scope["change_scope_verification_phases_in_order"],
        EXPECTED_CHANGE_SCOPE_PHASES,
        f"{path}.change_scope_verification_phases_in_order",
    )
    for field in (
        "design_contract_only",
        "public_synthetic_only",
        "precommit_phase_compares_base_to_current_tree_index_worktree_and_untracked",
        "postcommit_phase_requires_head_not_equal_base",
        "postcommit_phase_requires_clean_tracked_index_worktree_and_untracked",
        "postcommit_phase_compares_base_to_head",
        "both_phases_require_exact_permitted_path_set",
    ):
        require_bool_field(scope, field, True, path)
    for field in (
        "enabled_by_default",
        "production_admissible",
        "accepts_candidate_source_configuration_or_binary",
        "accepts_fit_development_sealed_or_private_material",
        "accepts_real_freeze_capability_or_run_plan",
        "launches_any_process",
        "compiles_or_applies_native_policy",
        "observes_native_enforcement",
        "modifies_workspace_sandbox_runtime",
        "registers_mcp_tool_or_runtime_surface",
        "touches_live_store_retrieval_or_database",
        "opens_candidate_implementation",
        "opens_private_data_access",
        "opens_g1_4_execution",
    ):
        require_bool_field(scope, field, False, path)


def validate_dependency_lock(contract: dict[str, Any]) -> None:
    path = "contract.dependency_and_reference_lock"
    lock = require_object(contract["dependency_and_reference_lock"], path)
    require_exact_value(
        lock["adapter_dependency"], "nono", f"{path}.adapter_dependency"
    )
    require_exact_value(lock["exact_version"], NONO_VERSION, f"{path}.exact_version")
    require_exact_value(
        lock["cargo_lock_checksum"], NONO_CHECKSUM, f"{path}.cargo_lock_checksum"
    )
    require_exact_value(
        lock["validator_helper_path"],
        "scripts/eval/engram_g1_corpus_design.py",
        f"{path}.validator_helper_path",
    )
    require_exact_value(
        lock["validator_helper_sha256"],
        VALIDATOR_HELPER_SHA256,
        f"{path}.validator_helper_sha256",
    )
    for field in (
        "dependency_source_rule_order_and_transitive_review_required_before_implementation",
        "version_checksum_feature_or_rule_order_drift_requires_new_revision",
        "validator_helper_byte_pin_required_before_validation",
    ):
        require_bool_field(lock, field, True, path)
    for field in (
        "default_features_enabled",
        "workspace_sandbox_runtime_is_evidence_for_this_kat",
        "existing_workspace_network_open_profile_is_admissible",
        "existing_workspace_child_exec_success_is_admissible",
        "nono_only_satisfies_all_required_canaries",
        "macos_nono_profile_process_exec_and_fork_allow_is_accepted",
        "this_gate_installs_vendors_upgrades_or_executes_dependency",
    ):
        require_bool_field(lock, field, False, path)


def validate_future_interface(contract: dict[str, Any]) -> None:
    path = "contract.future_kat_interface"
    interface = require_object(contract["future_kat_interface"], path)
    require_exact_value(interface["mode"], FUTURE_MODE, f"{path}.mode")
    require_exact_value(
        require_list(
            interface["required_phases_in_order"], f"{path}.required_phases_in_order"
        ),
        EXPECTED_PHASES,
        f"{path}.required_phases_in_order",
    )
    for field in (
        "explicit_boolean_enable_required",
        "public_synthetic_fixture_marker_required",
        "fixed_public_probe_required",
        "probe_source_and_build_artifacts_sha256_required",
        "synthetic_temporary_roots_and_sentinels_only",
        "local_supervisor_endpoint_for_network_canary_only",
        "phase_order_is_closed",
        "out_of_order_transition_fails_closed",
        "terminal_failure_is_absorbing",
    ):
        require_bool_field(interface, field, True, path)
    for field in (
        "probe_accepts_arbitrary_path_argument",
        "probe_accepts_arbitrary_command_or_environment",
        "probe_contains_candidate_or_private_material",
        "external_network_target_allowed",
    ):
        require_bool_field(interface, field, False, path)


def validate_enforcement_model(contract: dict[str, Any]) -> None:
    path = "contract.enforcement_responsibility_model"
    model = require_object(contract["enforcement_responsibility_model"], path)
    require_exact_value(
        model["classes_in_order"], EXPECTED_CLASSES, f"{path}.classes_in_order"
    )
    require_exact_value(
        model["unsupported_platform_verdict"],
        "REJECTED_FAIL_CLOSED",
        f"{path}.unsupported_platform_verdict",
    )
    require_bool_field(
        model, "support_apply_active_and_canary_evidence_are_distinct", True, path
    )
    for field in (
        "active_report_alone_is_sufficient",
        "one_class_may_claim_another_class_without_evidence",
        "missing_required_control_means_platform_supported",
    ):
        require_bool_field(model, field, False, path)


def validate_platform_plans(contract: dict[str, Any]) -> None:
    path = "contract.platform_adapter_plans"
    plans = require_object(contract["platform_adapter_plans"], path)
    require_exact_fields(plans, {"darwin", "linux"}, path)
    darwin = require_object(plans["darwin"], f"{path}.darwin")
    linux = require_object(plans["linux"], f"{path}.linux")
    require_exact_value(darwin["platform"], "darwin", f"{path}.darwin.platform")
    require_exact_value(linux["platform"], "linux", f"{path}.linux.platform")
    require_bool_field(
        darwin,
        "nono_filesystem_and_network_is_sufficient_for_full_adapter",
        False,
        f"{path}.darwin",
    )
    require_bool_field(
        darwin,
        "nono_generated_process_exec_and_fork_allow_must_be_overridden_or_replaced",
        True,
        f"{path}.darwin",
    )
    require_bool_field(
        linux,
        "landlock_alone_is_sufficient_for_full_adapter",
        False,
        f"{path}.linux",
    )
    require_bool_field(
        linux,
        "nested_outer_and_inner_filesystem_denial_required",
        True,
        f"{path}.linux",
    )
    for platform, section in (("darwin", darwin), ("linux", linux)):
        require_exact_value(
            section["supplementary_control_absent_verdict"],
            "UNSUPPORTED_FAIL_CLOSED",
            f"{path}.{platform}.supplementary_control_absent_verdict",
        )
        require_bool_field(
            section,
            "fallback_to_unsandboxed_execution_allowed",
            False,
            f"{path}.{platform}",
        )


def validate_canaries(contract: dict[str, Any]) -> None:
    path = "contract.canary_matrix"
    matrix = require_object(contract["canary_matrix"], path)
    canaries = require_list(
        matrix["required_canaries_in_order"], f"{path}.required_canaries_in_order"
    )
    if len(canaries) != len(EXPECTED_CANARIES):
        raise InputError(
            f"{path}.required_canaries_in_order must contain exactly 14 entries"
        )
    for index, (name, expected, owner) in enumerate(EXPECTED_CANARIES):
        canary_path = f"{path}.required_canaries_in_order[{index}]"
        canary = require_object(canaries[index], canary_path)
        require_exact_fields(
            canary,
            {"name", "expected", "evidence_owner", "synthetic_target"},
            canary_path,
        )
        require_exact_value(canary["name"], name, f"{canary_path}.name")
        require_exact_value(canary["expected"], expected, f"{canary_path}.expected")
        require_exact_value(
            canary["evidence_owner"], owner, f"{canary_path}.evidence_owner"
        )
        if (
            type(canary["synthetic_target"]) is not str
            or not canary["synthetic_target"]
        ):
            raise InputError(
                f"{canary_path}.synthetic_target must remain a non-empty label"
            )
    require_exact_value(matrix["allow_canary_count"], 3, f"{path}.allow_canary_count")
    require_exact_value(matrix["deny_canary_count"], 11, f"{path}.deny_canary_count")
    require_bool_field(matrix, "all_fourteen_required_for_platform_support", True, path)
    require_bool_field(matrix, "partial_canary_pass_is_success", False, path)


def validate_future_receipts_and_lessons(contract: dict[str, Any]) -> None:
    lifecycle_path = "contract.run_lifecycle_model"
    lifecycle = require_object(contract["run_lifecycle_model"], lifecycle_path)
    require_bool_field(
        lifecycle,
        "cleanup_failure_blocks_new_run_claim_until_lesson_is_durable_and_verified",
        True,
        lifecycle_path,
    )

    path = "contract.future_receipt_state_machine"
    state_machine = require_object(contract["future_receipt_state_machine"], path)
    rows = require_list(
        state_machine["phase_receipts_in_order"], f"{path}.phase_receipts_in_order"
    )
    if len(rows) != len(EXPECTED_PHASE_RECEIPTS):
        raise InputError(f"{path}.phase_receipts_in_order must contain exactly 11 rows")
    for index, (phase, schema, source, fields) in enumerate(EXPECTED_PHASE_RECEIPTS):
        row_path = f"{path}.phase_receipts_in_order[{index}]"
        row = require_object(rows[index], row_path)
        require_exact_fields(
            row,
            {
                "phase",
                "schema",
                "evidence_source",
                "required_payload_fields_in_order",
            },
            row_path,
        )
        require_exact_value(row["phase"], phase, f"{row_path}.phase")
        require_exact_value(row["schema"], schema, f"{row_path}.schema")
        require_exact_value(
            row["evidence_source"], source, f"{row_path}.evidence_source"
        )
        require_exact_value(
            row["required_payload_fields_in_order"],
            fields,
            f"{row_path}.required_payload_fields_in_order",
        )
    for field in (
        "each_phase_emits_exactly_one_receipt",
        "every_phase_schema_is_distinct",
        "receipt_sequence_exactly_matches_phase_order",
        "every_receipt_binds_run_contract_and_previous_event",
        "evidence_source_identity_commitment_required",
        "missing_duplicate_reordered_or_source_unbound_receipt_invalidates_attempt",
    ):
        require_bool_field(state_machine, field, True, path)
    for field in (
        "phase_receipt_may_substitute_for_another_phase",
        "aggregate_all_true_report_is_admissible",
    ):
        require_bool_field(state_machine, field, False, path)

    lesson_path = "contract.rollback_lesson_model"
    lesson = require_object(contract["rollback_lesson_model"], lesson_path)
    require_exact_value(
        lesson["schema"],
        "agent_bridge.engram_g1_4_native_kat_rollback_failure_lesson.v0",
        f"{lesson_path}.schema",
    )
    require_exact_value(lesson["writer"], "supervisor_only", f"{lesson_path}.writer")
    require_exact_value(
        lesson["durable_store_location_class"],
        "agent_bridge_state_dir/engram_g14_public_synthetic_native_kat/rollback_lessons_v0",
        f"{lesson_path}.durable_store_location_class",
    )
    require_exact_value(
        lesson["storage_profile"],
        "versioned_one_record_per_file_create_new_fsync_file_and_directory",
        f"{lesson_path}.storage_profile",
    )
    require_exact_value(
        lesson["required_payload_fields_in_order"],
        EXPECTED_LESSON_FIELDS,
        f"{lesson_path}.required_payload_fields_in_order",
    )
    for field in (
        "writer_reopens_and_verifies_durable_bytes_before_acknowledgement",
        "new_run_claim_blocked_until_required_lesson_is_durable_and_verified",
        "lesson_write_or_integrity_failure_is_absorbing",
    ):
        require_bool_field(lesson, field, True, lesson_path)
    for field in (
        "raw_paths_candidate_private_logs_or_free_form_text_allowed",
        "lesson_store_implemented_or_written_by_this_gate",
    ):
        require_bool_field(lesson, field, False, lesson_path)


def validate_audit_and_boundaries(contract: dict[str, Any]) -> None:
    path = "contract.human_audit_policy"
    audit = require_object(contract["human_audit_policy"], path)
    require_exact_value(
        audit["manual_safety_audit_required_for"],
        EXPECTED_MANUAL_AUDIT_EVENTS,
        f"{path}.manual_safety_audit_required_for",
    )
    for field in (
        "routine_design_validation_requires_human_approval",
        "unchanged_public_synthetic_kat_requires_per_run_human_approval",
        "fail_closed_denial_requires_human_approval",
        "manual_safety_audit_is_a_per_run_gate",
        "manual_audit_outcome_may_be_inferred_by_validator",
    ):
        require_bool_field(audit, field, False, path)
    for field in (
        "reversible_failure_requires_automatic_rollback",
        "rollback_failure_requires_durable_lesson",
    ):
        require_bool_field(audit, field, True, path)

    state_path = "contract.state_machine"
    state = require_object(contract["state_machine"], state_path)
    require_exact_value(
        state["current_state"],
        "PUBLIC_SYNTHETIC_NATIVE_SANDBOX_ADAPTER_PREREGISTERED_DESIGN_ONLY",
        f"{state_path}.current_state",
    )
    require_bool_field(
        state, "native_adapter_preregistration_present", True, state_path
    )
    for field in (
        "native_adapter_implementation_present",
        "native_policy_execution_present",
        "public_probe_implementation_present",
        "candidate_implementation_present",
        "real_freeze_capability_present",
        "private_run_plan_present",
        "positive_execution_or_data_authority_state_representable",
    ):
        require_bool_field(state, field, False, state_path)

    boundary_path = "contract.boundaries"
    boundaries = require_object(contract["boundaries"], boundary_path)
    positive = {"predecessor_harness_bound", "native_adapter_design_preregistered"}
    for field, value in boundaries.items():
        require_bool_field(boundaries, field, field in positive, boundary_path)


def validate_contract_semantics(value: dict[str, Any]) -> dict[str, Any]:
    """Validate closed semantics independently of the raw-file byte pin."""

    reject_raw_fields(value, "contract")
    contract = require_object(value, "contract")
    require_exact_fields(contract, EXPECTED_TOP_LEVEL_FIELDS, "contract")
    require_exact_value(contract["schema"], CONTRACT_SCHEMA, "contract.schema")
    require_exact_value(contract["contract_id"], CONTRACT_ID, "contract.contract_id")
    require_exact_value(
        contract["stage"],
        "g1_4_public_synthetic_native_sandbox_adapter_preregistration_design_review_only",
        "contract.stage",
    )
    if sha256_canonical(contract) != CONTRACT_SEMANTIC_SHA256:
        raise InputError("contract semantic commitment does not match preregistered v0")
    validate_predecessor(contract)
    validate_scope(contract)
    validate_dependency_lock(contract)
    validate_future_interface(contract)
    validate_enforcement_model(contract)
    validate_platform_plans(contract)
    validate_canaries(contract)
    validate_future_receipts_and_lessons(contract)
    validate_audit_and_boundaries(contract)
    return contract


def validate_repository_bindings(contract: dict[str, Any]) -> None:
    root = repo_root()
    for name, (relative_path, expected_digest) in PREDECESSOR_ARTIFACTS.items():
        raw = read_stable_bounded_file(root / relative_path)
        actual = sha256_bytes(raw)
        if actual != expected_digest:
            raise InputError(
                f"predecessor {name} bytes do not match preregistered harness"
            )

    helper_raw = read_stable_bounded_file(
        root / "scripts/eval/engram_g1_corpus_design.py"
    )
    if sha256_bytes(helper_raw) != VALIDATOR_HELPER_SHA256:
        raise InputError("validator helper bytes do not match preregistered pin")

    manifest_text = read_stable_bounded_file(root / "crates/agent/Cargo.toml").decode(
        "utf-8"
    )
    expected_manifest_line = 'nono = { version = "=0.53.0", default-features = false }'
    if manifest_text.count(expected_manifest_line) != 1:
        raise InputError("crates/agent Cargo manifest no longer has the exact nono pin")

    lock_text = read_stable_bounded_file(root / "Cargo.lock").decode("utf-8")
    package_header = re.compile(
        r'\[\[package\]\]\nname = "nono"\nversion = "0\.53\.0"\n'
        r'source = "registry\+https://github\.com/rust-lang/crates\.io-index"\n'
        r'checksum = "ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee"\n'
    )
    if len(package_header.findall(lock_text)) != 1:
        raise InputError(
            "Cargo.lock no longer has the exact preregistered nono package"
        )
    require_exact_value(
        contract["dependency_and_reference_lock"]["exact_version"],
        NONO_VERSION,
        "contract.dependency_and_reference_lock.exact_version",
    )


def build_receipt(contract: dict[str, Any], raw: bytes) -> dict[str, Any]:
    canaries = contract["canary_matrix"]["required_canaries_in_order"]
    return {
        "schema": RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": sha256_bytes(raw),
        "contract_semantic_sha256": sha256_canonical(contract),
        "validator_sha256": hashlib.sha256(
            Path(__file__).resolve().read_bytes()
        ).hexdigest(),
        "predecessor_commit": PREDECESSOR_COMMIT,
        "predecessor_contract_sha256": PREDECESSOR_ARTIFACTS["contract"][1],
        "predecessor_fixture_sha256": PREDECESSOR_ARTIFACTS["fixture"][1],
        "predecessor_implementation_sha256": PREDECESSOR_ARTIFACTS["implementation"][1],
        "predecessor_checker_sha256": PREDECESSOR_ARTIFACTS["checker"][1],
        "predecessor_shell_entrypoint_sha256": PREDECESSOR_ARTIFACTS[
            "shell_entrypoint"
        ][1],
        "nono_version": NONO_VERSION,
        "nono_cargo_lock_checksum": NONO_CHECKSUM,
        "validator_helper_sha256": VALIDATOR_HELPER_SHA256,
        "design_base_commit": DESIGN_BASE_COMMIT,
        "future_mode": FUTURE_MODE,
        "platform_plan_count": 2,
        "phase_receipt_schema_count": len(EXPECTED_PHASE_RECEIPTS),
        "canary_count": len(canaries),
        "allowed_canary_count": 3,
        "denied_canary_count": 11,
        "enforcement_responsibility_class_count": 3,
        "manual_audit_event_count": len(EXPECTED_MANUAL_AUDIT_EVENTS),
        "contract_verdict": "VALIDATED_NATIVE_SANDBOX_ADAPTER_PREREGISTRATION_DESIGN_ONLY_NO_AUTHORITY",
        "authority_class": "NONE_DESIGN_VALIDATION_ONLY",
        "admission_effect": "NO_EXECUTION_OR_DATA_AUTHORITY",
        "production_admissible": False,
        "g1_4_execution_open": False,
        "native_execution_authorized": False,
        "candidate_or_private_execution_authorized": False,
        "design_contract_only": True,
        "native_adapter_design_preregistered": True,
        "native_adapter_implemented": False,
        "native_policy_executed": False,
        "native_enforcement_verified": False,
        "public_native_kat_executed": False,
        "candidate_or_private_material_accessed": False,
        "durable_authenticated_anchor_implemented": False,
        "rollback_lesson_store_implemented": False,
        "candidate_implementation_authority": False,
        "protocol_execution_authority": False,
        "sealed_evaluation_authority": False,
        "result_release_authority": False,
        "retrieval_mutation_authority": False,
        "live_store_write_authority": False,
        "runtime_promotion_authority": False,
        "only_permitted_successor": ONLY_SUCCESSOR,
    }


def validate_contract(path: Path) -> dict[str, Any]:
    contract, raw = read_json(path)
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("contract bytes do not match preregistered v0")
    validate_contract_semantics(contract)
    validate_repository_bindings(contract)
    return build_receipt(contract, raw)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-contract")
    validate.add_argument("--contract", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        receipt = validate_contract(args.contract)
    except (InputError, OSError, UnicodeError) as exc:
        print(f"E_CONTRACT: {exc}", file=sys.stderr)
        return 2
    print(render_json(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
