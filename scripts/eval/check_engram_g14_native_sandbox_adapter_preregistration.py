#!/usr/bin/env python3
"""Independent adversarial checks for the G1.4 native-adapter preregistration."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
VALIDATOR_PATH = SCRIPT_DIR / "engram_g14_native_sandbox_adapter_preregistration.py"
CONTRACT_PATH = (
    SCRIPT_DIR
    / "fixtures/engram_g14_native_sandbox_adapter_preregistration_contract_v0.json"
)
CONTRACT_SCHEMA = (
    "agent_bridge.engram_g1_4_native_sandbox_adapter_preregistration_contract.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_4_native_sandbox_adapter_preregistration_receipt.v0"
)
CONTRACT_ID = "engram_g14_native_sandbox_adapter_preregistration_20260718"
FUTURE_MODE = "PUBLIC_SYNTHETIC_NATIVE_SANDBOX_ADAPTER_KAT"
EXPECTED_NONO_CHECKSUM = (
    "ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee"
)
EXPECTED_HELPER_SHA256 = (
    "2a408d64b34605f434377b3c11f71807f6c81068aa7bcba069c8d3a6dc44cb91"
)
EXPECTED_CONTRACT_SHA256 = (
    "075dd9be4f6097e539db62025e6420b9add0efc030c528c065b612a77f5d78e0"
)
EXPECTED_CONTRACT_SEMANTIC_SHA256 = (
    "3c5b2ce5d356972697044c39bb5ececd391797ddd73fcd3a2c894f3580521333"
)
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
EXPECTED_CANARIES = [
    (
        "candidate_code_read",
        "allow",
        "native_kernel",
        "registered_public_probe_source_root",
    ),
    (
        "dependency_read",
        "allow",
        "native_kernel",
        "registered_public_probe_dependency_root",
    ),
    (
        "ephemeral_scratch_write",
        "allow",
        "native_kernel",
        "per_attempt_ephemeral_scratch_root",
    ),
    (
        "repository_metadata_read",
        "deny",
        "native_kernel",
        "synthetic_repository_metadata_sentinel",
    ),
    (
        "private_manifest_read",
        "deny",
        "native_kernel",
        "synthetic_private_manifest_sentinel",
    ),
    ("live_store_read", "deny", "native_kernel", "synthetic_live_store_sentinel"),
    ("network_connect", "deny", "native_kernel", "loopback_supervisor_canary_endpoint"),
    ("subprocess_spawn", "deny", "native_kernel", "fixed_inert_public_helper"),
    ("dynamic_plugin_load", "deny", "native_kernel", "fixed_public_plugin_sentinel"),
    (
        "non_scratch_write",
        "deny",
        "native_kernel",
        "synthetic_non_scratch_write_sentinel",
    ),
    ("wall_clock_read", "deny", "native_kernel", "fixed_public_clock_probe"),
    ("external_entropy_read", "deny", "native_kernel", "fixed_public_entropy_probe"),
    (
        "extra_inherited_fd_use",
        "deny",
        "launch_boundary",
        "registered_extra_pipe_descriptor",
    ),
    (
        "free_form_output",
        "deny",
        "supervisor_mediation",
        "fixed_oversized_or_unknown_field_output",
    ),
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
EXPECTED_MANUAL_EVENTS = [
    "first_real_freeze_capability_consumption_or_private_run_plan_open",
    "candidate_or_runner_source_config_dependency_or_toolchain_change_after_final_lock",
    "fit_development_sealed_or_partition_access_policy_widening",
    "metric_threshold_arm_resource_retry_or_missingness_policy_change_after_any_observation",
    "sealed_partition_unblinding_selective_retry_or_rerun",
    "sandbox_filesystem_network_subprocess_log_output_or_side_channel_policy_widening_after_preregistration_or_any_real_runner_policy_change",
    "first_real_protocol_runner_enablement",
    "suspected_secret_privacy_identity_corpus_or_result_exposure",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_object(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_CONTRACT_SHA256
    value = json.loads(
        raw.decode("utf-8", errors="strict"),
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicate_pairs,
    )
    assert type(value) is dict
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == EXPECTED_CONTRACT_SEMANTIC_SHA256
    return value


def assert_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    assert type(value) is dict, label
    assert set(value) == expected, (label, set(value), expected)
    return value


def load_validator() -> Any:
    sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location("g14_native_prereg", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTRACT = load_object(CONTRACT_PATH)
VALIDATOR = load_validator()


def assert_independent_contract_boundary() -> None:
    contract = assert_exact_keys(CONTRACT, EXPECTED_TOP_LEVEL_FIELDS, "contract")
    assert contract["schema"] == CONTRACT_SCHEMA
    assert contract["contract_id"] == CONTRACT_ID
    assert contract["stage"] == (
        "g1_4_public_synthetic_native_sandbox_adapter_preregistration_design_review_only"
    )

    predecessor = contract["predecessor_harness"]
    assert predecessor["commit"] == "41bf1b9e33b73e61adc567b668cbf2ed4cb7867c"
    assert predecessor["immutable"] is True
    assert predecessor["contract_sha256"] == (
        "6fae57e239594978810d03d2aee33133d3af8439527dd6aadef6884d5bba1b9d"
    )
    assert predecessor["fixture_sha256"] == (
        "477cf9b326f52fc3f8ce9138346bb55e2692e5b473ac5f0c5d9b24e457350607"
    )

    scope = contract["scope"]
    assert scope["future_exact_mode"] == FUTURE_MODE
    assert scope["authority_class"] == "NONE_DESIGN_VALIDATION_ONLY"
    assert scope["admission_effect"] == "NO_EXECUTION_OR_DATA_AUTHORITY"
    assert scope["permitted_output"] == "closed_design_validation_receipt_no_authority"
    assert scope["design_base_commit"] == DESIGN_BASE_COMMIT
    assert scope["permitted_changed_paths_in_order"] == EXPECTED_CHANGED_PATHS
    assert (
        scope["change_scope_verification_phases_in_order"]
        == EXPECTED_CHANGE_SCOPE_PHASES
    )
    for field in (
        "precommit_phase_compares_base_to_current_tree_index_worktree_and_untracked",
        "postcommit_phase_requires_head_not_equal_base",
        "postcommit_phase_requires_clean_tracked_index_worktree_and_untracked",
        "postcommit_phase_compares_base_to_head",
        "both_phases_require_exact_permitted_path_set",
    ):
        assert scope[field] is True, field
    assert scope["enabled_by_default"] is False
    assert scope["design_contract_only"] is True
    assert scope["public_synthetic_only"] is True
    assert scope["only_permitted_successor"] == (
        "separate_public_synthetic_native_sandbox_adapter_kat_implementation_gate"
    )
    for field in (
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
        assert scope[field] is False, field

    dependency = contract["dependency_and_reference_lock"]
    assert dependency["adapter_dependency"] == "nono"
    assert dependency["exact_version"] == "0.53.0"
    assert dependency["cargo_lock_checksum"] == EXPECTED_NONO_CHECKSUM
    assert dependency["validator_helper_path"] == (
        "scripts/eval/engram_g1_corpus_design.py"
    )
    assert dependency["validator_helper_sha256"] == EXPECTED_HELPER_SHA256
    assert dependency["validator_helper_byte_pin_required_before_validation"] is True
    assert dependency["default_features_enabled"] is False
    assert dependency["workspace_sandbox_runtime_is_evidence_for_this_kat"] is False
    assert dependency["nono_only_satisfies_all_required_canaries"] is False
    assert (
        dependency["macos_nono_profile_process_exec_and_fork_allow_is_accepted"]
        is False
    )
    assert (
        dependency["this_gate_installs_vendors_upgrades_or_executes_dependency"]
        is False
    )

    interface = contract["future_kat_interface"]
    assert interface["mode"] == FUTURE_MODE
    assert interface["required_phases_in_order"] == EXPECTED_PHASES
    assert interface["fixed_public_probe_required"] is True
    assert interface["probe_accepts_arbitrary_path_argument"] is False
    assert interface["probe_accepts_arbitrary_command_or_environment"] is False
    assert interface["external_network_target_allowed"] is False
    assert interface["local_supervisor_endpoint_for_network_canary_only"] is True


def assert_independent_enforcement_boundary() -> None:
    model = CONTRACT["enforcement_responsibility_model"]
    assert model["classes_in_order"] == [
        "native_kernel",
        "launch_boundary",
        "supervisor_mediation",
    ]
    assert model["support_apply_active_and_canary_evidence_are_distinct"] is True
    assert model["active_report_alone_is_sufficient"] is False
    assert model["one_class_may_claim_another_class_without_evidence"] is False
    assert model["missing_required_control_means_platform_supported"] is False
    assert model["unsupported_platform_verdict"] == "REJECTED_FAIL_CLOSED"

    plans = assert_exact_keys(
        CONTRACT["platform_adapter_plans"], {"darwin", "linux"}, "platforms"
    )
    darwin = plans["darwin"]
    assert darwin["nono_filesystem_and_network_is_sufficient_for_full_adapter"] is False
    assert (
        darwin[
            "nono_generated_process_exec_and_fork_allow_must_be_overridden_or_replaced"
        ]
        is True
    )
    assert darwin["private_var_tmp_etc_alias_order_review_required"] is True
    assert darwin["network_mdns_and_local_ipc_exceptions_review_required"] is True
    assert darwin["fallback_to_unsandboxed_execution_allowed"] is False
    linux = plans["linux"]
    assert linux["landlock_alone_is_sufficient_for_full_adapter"] is False
    assert linux["nested_outer_and_inner_filesystem_denial_required"] is True
    assert linux["landlock_abi_and_network_support_report_required"] is True
    assert linux["seccomp_fallback_semantics_and_rule_order_review_required"] is True
    assert linux["fallback_to_unsandboxed_execution_allowed"] is False
    for platform in (darwin, linux):
        assert platform["supplementary_control_absent_verdict"] == (
            "UNSUPPORTED_FAIL_CLOSED"
        )

    canaries = CONTRACT["canary_matrix"]["required_canaries_in_order"]
    observed = [
        (row["name"], row["expected"], row["evidence_owner"], row["synthetic_target"])
        for row in canaries
    ]
    assert observed == EXPECTED_CANARIES
    assert CONTRACT["canary_matrix"]["allow_canary_count"] == 3
    assert CONTRACT["canary_matrix"]["deny_canary_count"] == 11
    assert (
        CONTRACT["canary_matrix"]["all_fourteen_required_for_platform_support"] is True
    )
    assert CONTRACT["canary_matrix"]["partial_canary_pass_is_success"] is False

    controls = CONTRACT["negative_control_model"]
    assert controls["every_canary_requires_registered_liveness_control"] is True
    assert (
        controls["allowed_canary_control_removes_exact_registered_grant_and_must_deny"]
        is True
    )
    assert (
        controls[
            "denied_canary_control_must_succeed_before_enforced_denial_is_admissible"
        ]
        is True
    )
    assert controls["control_attempt_ids_are_distinct_and_bound_to_parent_run"] is True
    assert (
        controls["control_execution_is_never_subject_execution_or_unsandboxed_fallback"]
        is True
    )
    assert controls["negative_controls_use_synthetic_temporary_resources_only"] is True
    assert (
        controls["negative_controls_may_read_real_repository_private_or_live_store"]
        is False
    )
    assert controls["negative_controls_may_contact_external_network"] is False
    assert controls["network_control_uses_loopback_supervisor_endpoint_only"] is True
    assert controls["negative_control_success_is_native_enforcement_proof"] is False


def assert_independent_lifecycle_and_authority() -> None:
    lifecycle = CONTRACT["run_lifecycle_model"]
    assert lifecycle["run_id_claimed_before_attempt_specific_validation"] is True
    assert lifecycle["any_fault_invalidates_entire_attempt"] is True
    assert lifecycle["selective_retry_or_partial_rerun_forbidden"] is True
    assert lifecycle["invalidated_run_id_cannot_be_reused"] is True
    assert lifecycle["automatic_cleanup_and_rollback_required"] is True
    assert lifecycle["cleanup_failure_requires_minimal_durable_lesson"] is True
    assert (
        lifecycle[
            "cleanup_failure_blocks_new_run_claim_until_lesson_is_durable_and_verified"
        ]
        is True
    )
    assert lifecycle["partial_or_intermediate_results_released"] is False

    receipt_machine = CONTRACT["future_receipt_state_machine"]
    rows = receipt_machine["phase_receipts_in_order"]
    observed_rows = [
        (
            row["phase"],
            row["schema"],
            row["evidence_source"],
            row["required_payload_fields_in_order"],
        )
        for row in rows
    ]
    assert observed_rows == EXPECTED_PHASE_RECEIPTS
    assert [row["phase"] for row in rows] == EXPECTED_PHASES
    assert len({row["schema"] for row in rows}) == len(rows) == 11
    assert receipt_machine["each_phase_emits_exactly_one_receipt"] is True
    assert receipt_machine["receipt_sequence_exactly_matches_phase_order"] is True
    assert (
        receipt_machine["every_receipt_binds_run_contract_and_previous_event"] is True
    )
    assert receipt_machine["evidence_source_identity_commitment_required"] is True
    assert receipt_machine["phase_receipt_may_substitute_for_another_phase"] is False
    assert receipt_machine["aggregate_all_true_report_is_admissible"] is False

    lesson = CONTRACT["rollback_lesson_model"]
    assert lesson["schema"] == (
        "agent_bridge.engram_g1_4_native_kat_rollback_failure_lesson.v0"
    )
    assert lesson["writer"] == "supervisor_only"
    assert lesson["durable_store_location_class"] == (
        "agent_bridge_state_dir/engram_g14_public_synthetic_native_kat/rollback_lessons_v0"
    )
    assert lesson["storage_profile"] == (
        "versioned_one_record_per_file_create_new_fsync_file_and_directory"
    )
    assert lesson["required_payload_fields_in_order"] == EXPECTED_LESSON_FIELDS
    assert lesson["raw_paths_candidate_private_logs_or_free_form_text_allowed"] is False
    assert (
        lesson["writer_reopens_and_verifies_durable_bytes_before_acknowledgement"]
        is True
    )
    assert (
        lesson["new_run_claim_blocked_until_required_lesson_is_durable_and_verified"]
        is True
    )
    assert lesson["lesson_write_or_integrity_failure_is_absorbing"] is True
    assert lesson["lesson_store_implemented_or_written_by_this_gate"] is False

    receipts = CONTRACT["receipt_and_anchor_model"]
    assert receipts["expected_chain_head_frozen_before_untrusted_probe_launch"] is True
    assert receipts["independent_checker_constructs_expected_chain"] is True
    assert (
        receipts["process_local_self_consistent_chain_is_authenticity_proof"] is False
    )
    assert (
        receipts[
            "durable_authenticated_prelaunch_anchor_required_before_real_candidate_runner"
        ]
        is True
    )
    assert receipts["durable_authenticated_anchor_implemented_by_this_gate"] is False
    assert (
        receipts["successful_kat_receipt_authorizes_candidate_or_private_execution"]
        is False
    )

    audit = CONTRACT["human_audit_policy"]
    assert audit["manual_safety_audit_required_for"] == EXPECTED_MANUAL_EVENTS
    assert len(set(EXPECTED_MANUAL_EVENTS)) == 8
    assert audit["routine_design_validation_requires_human_approval"] is False
    assert (
        audit["unchanged_public_synthetic_kat_requires_per_run_human_approval"] is False
    )
    assert audit["manual_safety_audit_is_a_per_run_gate"] is False
    assert audit["reversible_failure_requires_automatic_rollback"] is True
    assert audit["rollback_failure_requires_durable_lesson"] is True

    boundaries = CONTRACT["boundaries"]
    positive = {"predecessor_harness_bound", "native_adapter_design_preregistered"}
    for field, value in boundaries.items():
        assert value is (field in positive), (field, value)
    state = CONTRACT["state_machine"]
    assert state["native_adapter_preregistration_present"] is True
    for field, value in state.items():
        if (
            field.endswith("_present")
            and field != "native_adapter_preregistration_present"
        ):
            assert value is False, field
    assert state["positive_execution_or_data_authority_state_representable"] is False


def walk(value: Any, path: tuple[Any, ...] = ()) -> Any:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


def set_path(value: Any, path: tuple[Any, ...], replacement: Any) -> Any:
    if not path:
        return replacement
    cursor = value
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = replacement
    return value


def assert_semantic_mutations_rejected() -> int:
    VALIDATOR.validate_contract_semantics(copy.deepcopy(CONTRACT))
    mutation_count = 0

    def reject(path: tuple[Any, ...], replacement: Any) -> None:
        candidate = set_path(copy.deepcopy(CONTRACT), path, replacement)
        try:
            VALIDATOR.validate_contract_semantics(candidate)
        except VALIDATOR.InputError:
            return
        raise AssertionError(f"semantic mutation accepted at {path!r}")

    for path, value in list(walk(CONTRACT)):
        if isinstance(value, dict):
            if path:
                reject(path, [])
                mutation_count += 1
            if value:
                shortened = copy.deepcopy(value)
                shortened.pop(next(iter(shortened)))
                reject(path, shortened)
                mutation_count += 1
            expanded = copy.deepcopy(value)
            expanded["unexpected_field"] = False
            reject(path, expanded)
            mutation_count += 1
        elif isinstance(value, list):
            reject(path, {})
            mutation_count += 1
            reject(path, value[:-1] if value else ["unexpected"])
            mutation_count += 1
            if len(value) > 1:
                reject(path, list(reversed(value)))
                mutation_count += 1
        elif isinstance(value, bool):
            reject(path, not value)
            reject(path, int(value))
            mutation_count += 2
        elif isinstance(value, int):
            reject(path, value + 1)
            reject(path, str(value))
            mutation_count += 2
        elif isinstance(value, str):
            reject(path, value + "_mutated")
            reject(path, False)
            mutation_count += 2
        else:
            raise AssertionError(f"unsupported JSON type at {path!r}")
    assert mutation_count >= 500, mutation_count
    return mutation_count


def invoke_validator(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "validate-contract",
            "--contract",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def assert_file_boundary_and_receipt() -> None:
    with tempfile.TemporaryDirectory() as raw_scratch:
        scratch = Path(raw_scratch)
        accepted = invoke_validator(CONTRACT_PATH)
        assert accepted.returncode == 0, accepted.stderr
        receipt = json.loads(accepted.stdout)
        assert receipt["schema"] == RECEIPT_SCHEMA
        assert receipt["contract_id"] == CONTRACT_ID
        assert receipt["contract_sha256"] == digest(CONTRACT_PATH)
        assert receipt["future_mode"] == FUTURE_MODE
        assert receipt["canary_count"] == 14
        assert receipt["allowed_canary_count"] == 3
        assert receipt["denied_canary_count"] == 11
        assert receipt["phase_receipt_schema_count"] == 11
        assert receipt["contract_verdict"] == (
            "VALIDATED_NATIVE_SANDBOX_ADAPTER_PREREGISTRATION_DESIGN_ONLY_NO_AUTHORITY"
        )
        assert receipt["authority_class"] == "NONE_DESIGN_VALIDATION_ONLY"
        assert receipt["admission_effect"] == "NO_EXECUTION_OR_DATA_AUTHORITY"
        assert receipt["production_admissible"] is False
        assert receipt["g1_4_execution_open"] is False
        assert receipt["native_execution_authorized"] is False
        assert receipt["candidate_or_private_execution_authorized"] is False
        assert receipt["validator_helper_sha256"] == EXPECTED_HELPER_SHA256
        true_fields = {"design_contract_only", "native_adapter_design_preregistered"}
        for field, value in receipt.items():
            if field in true_fields:
                assert value is True, field
            elif (
                field.endswith("_authority")
                or field.endswith("_implemented")
                or field.endswith("_verified")
                or field.endswith("_executed")
                or field.endswith("_accessed")
            ):
                assert value is False, field

        byte_drift = scratch / "byte-drift.json"
        byte_drift.write_bytes(CONTRACT_PATH.read_bytes() + b"\n")
        rejected = invoke_validator(byte_drift)
        assert rejected.returncode == 2
        assert "contract bytes do not match preregistered v0" in rejected.stderr

        raw = CONTRACT_PATH.read_text(encoding="utf-8")
        schema_line = f'  "schema": "{CONTRACT_SCHEMA}",'
        duplicate = raw.replace(schema_line, f"{schema_line}\n{schema_line}", 1)
        assert duplicate != raw
        duplicate_path = scratch / "duplicate.json"
        duplicate_path.write_text(duplicate, encoding="utf-8")
        rejected = invoke_validator(duplicate_path)
        assert rejected.returncode == 2
        assert "duplicate field" in rejected.stderr

        invalid_utf8 = scratch / "invalid-utf8.json"
        invalid_utf8.write_bytes(b'{"schema":"x","bad":"\xff"}')
        assert invoke_validator(invalid_utf8).returncode == 2

        nonstandard = scratch / "nonstandard.json"
        nonstandard.write_text('{"schema":NaN}', encoding="utf-8")
        rejected = invoke_validator(nonstandard)
        assert rejected.returncode == 2
        assert "non-standard JSON constant" in rejected.stderr

        nonobject = scratch / "nonobject.json"
        nonobject.write_text("[]", encoding="utf-8")
        assert invoke_validator(nonobject).returncode == 2

        hardlink = scratch / "contract-hardlink.json"
        os.link(CONTRACT_PATH, hardlink)
        assert invoke_validator(hardlink).returncode == 0

        symlink = scratch / "contract-symlink.json"
        os.symlink(CONTRACT_PATH, symlink)
        rejected = invoke_validator(symlink)
        assert rejected.returncode == 2
        assert "failed to open design" in rejected.stderr


def assert_supply_chain_and_static_boundary() -> None:
    helper = REPO_ROOT / "scripts/eval/engram_g1_corpus_design.py"
    assert digest(helper) == EXPECTED_HELPER_SHA256

    manifest = (REPO_ROOT / "crates/agent/Cargo.toml").read_text(encoding="utf-8")
    exact_line = 'nono = { version = "=0.53.0", default-features = false }'
    assert manifest.count(exact_line) == 1

    lock = (REPO_ROOT / "Cargo.lock").read_text(encoding="utf-8")
    package_header = re.compile(
        r'\[\[package\]\]\nname = "nono"\nversion = "0\.53\.0"\n'
        r'source = "registry\+https://github\.com/rust-lang/crates\.io-index"\n'
        r'checksum = "ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee"\n'
    )
    assert len(package_header.findall(lock)) == 1

    tree = ast.parse(VALIDATOR_PATH.read_text(encoding="utf-8"))
    banned_import_roots = {
        "ctypes",
        "multiprocessing",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned_import_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".", 1)[0] not in banned_import_roots
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"compile", "eval", "exec", "open"}

    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "--candidate",
        "--private",
        "--capability",
        "--run-plan",
        "nono::Sandbox",
    ):
        assert forbidden not in source, forbidden
    assert source.count("add_argument(") == 1
    assert 'add_argument("--contract"' in source


def main() -> int:
    assert_independent_contract_boundary()
    assert_independent_enforcement_boundary()
    assert_independent_lifecycle_and_authority()
    mutation_count = assert_semantic_mutations_rejected()
    assert_file_boundary_and_receipt()
    assert_supply_chain_and_static_boundary()
    print(
        "native-adapter preregistration checker: VALIDATED "
        f"({mutation_count} semantic mutations rejected; no authority)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
