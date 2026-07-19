#!/usr/bin/env python3
"""Exercise the G1.4 protocol shape with public synthetic data only.

This default-off laboratory does not launch candidate code, apply or observe a
native sandbox, read a real corpus, consume a real freeze capability, execute a
sealed experiment, mutate retrieval, write the live store, or register runtime
behavior. Its sandbox input is an explicitly synthetic policy attestation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NoReturn

from engram_g1_corpus_design import read_stable_bounded_file


MODE = "PUBLIC_SYNTHETIC_PROTOCOL_KAT"
IMPLEMENTATION_VERSION = "engram_g14_public_synthetic_protocol_harness_v0"
CONTRACT_SCHEMA = (
    "agent_bridge.engram_g1_4_public_synthetic_protocol_harness_contract.v0"
)
CONTRACT_ID = "engram_g14_public_synthetic_protocol_harness_20260718"
CONTRACT_SHA256 = "6fae57e239594978810d03d2aee33133d3af8439527dd6aadef6884d5bba1b9d"
FIXTURE_SCHEMA = "agent_bridge.engram_g1_4_public_synthetic_protocol_harness_fixture.v0"
FIXTURE_ID = "PUBLIC_SYNTHETIC_G1_4_PROTOCOL_HARNESS_KAT_V0"
FIXTURE_SHA256 = "477cf9b326f52fc3f8ce9138346bb55e2692e5b473ac5f0c5d9b24e457350607"
RECEIPT_SCHEMA = "agent_bridge.engram_g1_4_public_synthetic_protocol_harness_receipt.v0"
PREDECESSOR_COMMIT = "6304546b0e0ffec8f6f7b9aa8afbc1c25a48f7a0"
PREDECESSOR_CONTRACT_SHA256 = (
    "dca8ac03fbc915d70c6470492136ca9e554722aeed8d789e85714ece7e60ea41"
)
PREDECESSOR_VALIDATOR_SHA256 = (
    "9e03d53b19eb9dd273ac6dc49cde7a9a93221de50be58eede37d25729374cd1c"
)
PREDECESSOR_CHECKER_SHA256 = (
    "49d3734eb52a73235cc858e7ae43d0de99999eb0f693f76661375e22683c5a92"
)
SANDBOX_PROFILE = "nono_landlock_or_seatbelt_deny_by_default_offline_runner_v1"
SANDBOX_EVIDENCE_KIND = "public_synthetic_policy_attestation_not_kernel_enforcement"
ONLY_PERMITTED_SUCCESSOR = (
    "separate_public_synthetic_native_sandbox_adapter_preregistration_design_review"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PHASES = (
    "development_lock",
    "development_feedback",
    "final_lock",
    "blinded_run_plan",
    "sandbox_attestation",
    "qualification",
    "synthetic_run",
    "decision",
    "mapping_reveal",
)
DEVELOPMENT_LOCK_FIELDS = (
    "source_tree_sha256",
    "configuration_sha256",
    "dependency_lock_sha256",
)
FINAL_LOCK_FIELDS = (
    "source_tree_sha256",
    "configuration_sha256",
    "dependency_lock_sha256",
    "toolchain_and_build_flags_sha256",
    "feature_flags_and_model_assets_sha256",
    "environment_allowlist_sha256",
    "sandbox_profile_sha256",
    "output_schema_sha256",
    "resource_budget_sha256",
    "protocol_contract_and_runner_version_sha256",
)
OPAQUE_ARM_IDS = ("arm_0", "arm_1", "arm_2", "arm_3", "arm_4")
ARM_MAPPING = {
    "arm_0": "stable_control",
    "arm_1": "density_only",
    "arm_2": "clustered_reorganization",
    "arm_3": "mechanism_off",
    "arm_4": "cluster_shuffled",
}
COMPARATORS = ("stable_control", "density_only")
FALSIFIERS = ("mechanism_off", "cluster_shuffled")
ALLOWED_CANARIES = (
    "candidate_code_read",
    "dependency_read",
    "ephemeral_scratch_write",
)
DENIED_CANARIES = (
    "repository_metadata_read",
    "private_manifest_read",
    "live_store_read",
    "network_connect",
    "subprocess_spawn",
    "dynamic_plugin_load",
    "non_scratch_write",
    "wall_clock_read",
    "external_entropy_read",
    "extra_inherited_fd_use",
    "free_form_output",
)
REQUIRED_CANARIES = ALLOWED_CANARIES + DENIED_CANARIES
INVOCATION_STATUSES = (
    "ok",
    "missing",
    "timeout",
    "crash",
    "schema_error",
    "sandbox_fault",
)
MANUAL_AUDIT_EVENTS = (
    "first_real_freeze_capability_consumption_or_private_run_plan_open",
    "candidate_or_runner_source_config_dependency_or_toolchain_change_after_final_lock",
    "fit_development_sealed_or_partition_access_policy_widening",
    "metric_threshold_arm_resource_retry_or_missingness_policy_change_after_any_observation",
    "sealed_partition_unblinding_selective_retry_or_rerun",
    "sandbox_filesystem_network_subprocess_log_output_or_side_channel_policy_change",
    "first_real_protocol_runner_enablement",
    "suspected_secret_privacy_identity_corpus_or_result_exposure",
)

REGISTERED_CONTRACT_PATH = (
    Path(__file__).resolve().parent
    / "fixtures/engram_g14_public_synthetic_protocol_harness_contract_v0.json"
)
REGISTERED_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures/engram_g14_public_synthetic_protocol_harness_fixture_v0.json"
)


class HarnessError(RuntimeError):
    """Typed fail-closed error from the public synthetic harness."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _fail(code: str, detail: str) -> NoReturn:
    raise HarnessError(code, detail)


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        _fail(code, detail)


def _exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    _require(type(value) is dict, "E_SCHEMA", f"{path} must be an object")
    actual = set(value)
    _require(
        actual == expected,
        "E_SCHEMA",
        f"{path} fields mismatch: missing={sorted(expected - actual)}, "
        f"extra={sorted(actual - expected)}",
    )
    return value


def _exact_value(actual: Any, expected: Any, path: str) -> None:
    _require(
        type(actual) is type(expected) and actual == expected,
        "E_POLICY",
        f"{path} must remain {expected!r}",
    )


def _semantic_value(actual: Any, expected: Any, path: str) -> None:
    if isinstance(expected, dict):
        obj = _exact_keys(actual, set(expected), path)
        for key, value in expected.items():
            _semantic_value(obj[key], value, f"{path}.{key}")
        return
    if isinstance(expected, (list, tuple)):
        _require(type(actual) is list, "E_SCHEMA", f"{path} must be an array")
        _require(
            len(actual) == len(expected),
            "E_POLICY",
            f"{path} length must remain {len(expected)}",
        )
        for index, value in enumerate(expected):
            _semantic_value(actual[index], value, f"{path}[{index}]")
        return
    _exact_value(actual, expected, path)


def _policy_section(
    actual: Any,
    path: str,
    *,
    literals: dict[str, Any] | None = None,
    true_fields: tuple[str, ...] = (),
    false_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    values = literals or {}
    fields = set(values) | set(true_fields) | set(false_fields)
    _require(
        len(fields) == len(values) + len(true_fields) + len(false_fields),
        "E_INTERNAL",
        f"overlapping policy declaration at {path}",
    )
    section = _exact_keys(actual, fields, path)
    for key, expected in values.items():
        _semantic_value(section[key], expected, f"{path}.{key}")
    for key in true_fields:
        _exact_value(section[key], True, f"{path}.{key}")
    for key in false_fields:
        _exact_value(section[key], False, f"{path}.{key}")
    return section


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail("E_CANONICAL", f"value is outside the closed JSON domain: {exc}")


def canonical_sha256(value: Any) -> str:
    return _sha256(canonical_bytes(value))


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("E_DUPLICATE_JSON_KEY", f"duplicate field {key!r}")
        result[key] = value
    return result


def _reject_float(value: str) -> NoReturn:
    _fail("E_JSON_NUMBER", f"floating-point value is forbidden: {value}")


def _reject_constant(value: str) -> NoReturn:
    _fail("E_JSON_NUMBER", f"non-standard JSON constant is forbidden: {value}")


def decode_closed_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_pairs,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except HarnessError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("E_JSON", f"{label} is not closed UTF-8 JSON: {exc}")
    return _exact_keys(value, set(value) if type(value) is dict else set(), label)


def _read_pinned_json(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    try:
        raw = read_stable_bounded_file(path)
    except OSError as exc:
        _fail("E_INPUT", f"failed to read {label}: {exc}")
    _require(
        _sha256(raw) == expected_sha256,
        "E_RAW_PIN",
        f"{label} bytes do not match the registered SHA-256",
    )
    return decode_closed_json(raw, label)


def _require_sha256(value: Any, path: str) -> str:
    _require(
        type(value) is str and SHA256_RE.fullmatch(value) is not None,
        "E_SHA256",
        f"{path} must be lowercase SHA-256",
    )
    return value


def validate_contract_semantics(value: dict[str, Any]) -> dict[str, Any]:
    """Validate policy independently of the registered contract byte pin."""

    contract = _exact_keys(
        value,
        {
            "schema",
            "contract_id",
            "stage",
            "predecessor_preregistration",
            "registered_fixture",
            "scope",
            "protocol_state_machine",
            "candidate_artifact_lock_model",
            "access_and_blinding_model",
            "sandbox_attestation_model",
            "determinism_and_state_isolation_model",
            "run_lifecycle_model",
            "decision_rule_model",
            "receipt_model",
            "human_audit_policy",
            "state_machine",
            "boundaries",
        },
        "contract",
    )
    _exact_value(contract["schema"], CONTRACT_SCHEMA, "contract.schema")
    _exact_value(contract["contract_id"], CONTRACT_ID, "contract.contract_id")
    _exact_value(
        contract["stage"],
        "g1_4_public_synthetic_protocol_harness_implementation_gate_only",
        "contract.stage",
    )
    _policy_section(
        contract["predecessor_preregistration"],
        "contract.predecessor_preregistration",
        literals={
            "commit": PREDECESSOR_COMMIT,
            "contract_id": "engram_g14_candidate_protocol_preregistration_20260718",
            "contract_sha256": PREDECESSOR_CONTRACT_SHA256,
            "validator_sha256": PREDECESSOR_VALIDATOR_SHA256,
            "checker_sha256": PREDECESSOR_CHECKER_SHA256,
        },
        true_fields=("immutable",),
    )
    _policy_section(
        contract["registered_fixture"],
        "contract.registered_fixture",
        literals={
            "schema": FIXTURE_SCHEMA,
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
        },
        true_fields=("public_synthetic_fixture", "immutable"),
        false_fields=("production_admissible",),
    )
    _policy_section(
        contract["scope"],
        "contract.scope",
        literals={
            "artifact_kind": "public_synthetic_offline_protocol_harness_implementation_gate",
            "exact_mode": MODE,
            "permitted_output": "redacted_public_synthetic_protocol_receipt_no_authority",
            "only_permitted_successor": ONLY_PERMITTED_SUCCESSOR,
        },
        true_fields=(
            "explicit_boolean_enable_required",
            "public_synthetic_fixture_marker_required",
        ),
        false_fields=(
            "enabled_by_default",
            "production_admissible",
            "production_mode_representable",
            "accepts_real_candidate_source_or_configuration",
            "accepts_real_fit_development_or_sealed_material",
            "accepts_real_freeze_capability",
            "launches_candidate_or_untrusted_process",
            "applies_native_sandbox_policy",
            "observes_native_sandbox_enforcement",
            "registers_mcp_or_runtime_surface",
            "touches_live_store_or_retrieval",
            "opens_candidate_implementation",
            "opens_private_data_access",
            "opens_g1_4_execution",
        ),
    )
    _policy_section(
        contract["protocol_state_machine"],
        "contract.protocol_state_machine",
        literals={"required_phases_in_order": list(PHASES)},
        true_fields=(
            "phase_order_is_closed",
            "out_of_order_transition_fails_closed",
            "terminal_failure_is_absorbing",
            "implementation_is_in_memory_and_public_synthetic_only",
        ),
    )
    _policy_section(
        contract["candidate_artifact_lock_model"],
        "contract.candidate_artifact_lock_model",
        literals={
            "two_phase_lock_profile": "development_lock_then_final_sealed_lock_v1",
            "development_lock_fields_in_order": list(DEVELOPMENT_LOCK_FIELDS),
            "maximum_reviewer_mediated_development_feedback_rounds": 2,
            "final_lock_fields_in_order": list(FINAL_LOCK_FIELDS),
        },
        true_fields=(
            "feedback_is_predeclared_aggregate_only",
            "feedback_round_numbers_are_contiguous_from_one",
            "final_lock_required_before_run_plan",
            "post_final_lock_mutation_forbidden",
            "candidate_self_approval_forbidden",
        ),
    )
    _policy_section(
        contract["access_and_blinding_model"],
        "contract.access_and_blinding_model",
        true_fields=(
            "fixture_contains_only_public_synthetic_aggregates",
            "arm_mapping_commitment_required_before_run_plan",
            "opaque_arm_ids_required_during_scoring",
            "synthetic_predecision_and_postdecision_material_split_required",
            "synthetic_decision_input_custodian_split_required",
            "mapping_reveal_forbidden_before_decision_receipt",
            "candidate_authored_targets_or_scoring_forbidden",
            "private_manifest_path_or_group_identifier_forbidden",
        ),
        false_fields=(
            "real_fit_development_or_sealed_access_present",
            "scorer_view_contains_mapping_before_decision",
        ),
    )
    _policy_section(
        contract["sandbox_attestation_model"],
        "contract.sandbox_attestation_model",
        literals={
            "profile": SANDBOX_PROFILE,
            "evidence_kind": SANDBOX_EVIDENCE_KIND,
            "required_canaries_in_order": list(REQUIRED_CANARIES),
            "required_allowed_canaries_in_order": list(ALLOWED_CANARIES),
            "required_denied_canaries_in_order": list(DENIED_CANARIES),
        },
        true_fields=(
            "support_apply_and_active_reports_all_required",
            "active_report_alone_is_never_sufficient",
            "every_canary_observation_must_equal_expected",
            "environment_mount_output_and_resource_bindings_required",
            "unsupported_apply_failure_or_canary_mismatch_invalidates_entire_run",
        ),
        false_fields=(
            "native_sandbox_enforcement_implemented_by_this_gate",
            "native_sandbox_enforcement_verified_by_this_gate",
        ),
    )
    _policy_section(
        contract["determinism_and_state_isolation_model"],
        "contract.determinism_and_state_isolation_model",
        true_fields=(
            "registered_seed_schedule_commitment_required",
            "two_identical_fit_qualification_replays_required",
            "ranked_outputs_must_match_byte_for_byte",
            "fresh_invocation_id_per_arm_group_and_replay_required",
            "invocation_ids_must_be_globally_unique",
            "cross_arm_group_partition_or_replay_state_forbidden",
            "ephemeral_scratch_destroyed_after_each_invocation_required",
            "resource_and_cache_policy_equal_across_arms_required",
            "nondeterminism_or_state_reuse_invalidates_entire_run",
        ),
    )
    _policy_section(
        contract["run_lifecycle_model"],
        "contract.run_lifecycle_model",
        true_fields=(
            "synthetic_capability_marker_required",
            "one_shot_run_id_required",
            "run_id_consumed_before_attempt_specific_validation",
            "run_plan_receipt_required_before_invocation",
            "per_invocation_receipt_required",
            "missing_timeout_crash_schema_or_sandbox_fault_is_failure",
            "any_fault_invalidates_entire_run",
            "selective_retry_or_partial_rerun_forbidden",
            "invalidated_run_id_cannot_be_reused",
            "partial_or_intermediate_results_not_released",
            "decision_receipt_required_before_mapping_reveal",
        ),
        false_fields=("real_authenticated_freeze_capability_accepted",),
    )
    _policy_section(
        contract["decision_rule_model"],
        "contract.decision_rule_model",
        literals={
            "candidate_minimum_paired_primary_repairs_vs_each_comparator": 2,
            "maximum_new_exact_misses": 0,
            "maximum_new_related_misses": 0,
            "maximum_no_relevant_gap_regressions": 0,
            "maximum_per_mode_unrelated_intrusion_increases": 0,
            "maximum_exact_mrr_absolute_loss": "0.05",
            "maximum_related_mrr_absolute_loss": "0.05",
            "maximum_primary_repairs_for_each_falsifier_vs_each_comparator": 1,
        },
        true_fields=(
            "candidate_repairs_must_exceed_each_falsifier_vs_each_comparator",
            "all_comparisons_are_paired_by_episode_group",
            "all_guards_apply_simultaneously",
            "fit_and_development_cannot_decide_final_verdict",
            "post_observation_rule_change_forbidden",
        ),
    )
    _policy_section(
        contract["receipt_model"],
        "contract.receipt_model",
        literals={
            "schemas_in_order": [
                "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
                "agent_bridge.engram_g1_4_synthetic_blinded_run_plan_receipt.v0",
                "agent_bridge.engram_g1_4_synthetic_sandbox_attestation_receipt.v0",
                "agent_bridge.engram_g1_4_synthetic_qualification_receipt.v0",
                "agent_bridge.engram_g1_4_synthetic_invocation_receipt.v0",
                "agent_bridge.engram_g1_4_synthetic_decision_receipt.v0",
                "agent_bridge.engram_g1_4_synthetic_mapping_reveal_receipt.v0",
            ]
        },
        true_fields=(
            "append_only_sequence_and_hash_chain_required",
            "payload_embedded_and_commitment_recomputed_on_verify",
            "predecision_scoring_chain_head_frozen_before_scorer",
            "receipt_binds_contract_fixture_runner_sandbox_resources_and_predecessor",
            "closed_schema_and_bounded_output_required",
            "tamper_or_reorder_invalidates_chain",
        ),
        false_fields=(
            "public_receipt_contains_raw_query_target_manifest_group_family_partition_or_identity",
            "public_receipt_contains_candidate_authored_free_form_text",
            "public_receipt_contains_arm_mapping_before_decision",
        ),
    )
    _policy_section(
        contract["human_audit_policy"],
        "contract.human_audit_policy",
        literals={"manual_safety_audit_required_for": list(MANUAL_AUDIT_EVENTS)},
        true_fields=(
            "reversible_failure_requires_automatic_rollback",
            "rollback_failure_requires_durable_lesson",
            "rollback_failure_path_exercised_by_harness",
        ),
        false_fields=(
            "routine_public_synthetic_validation_requires_human_approval",
            "unchanged_public_synthetic_rerun_requires_human_approval",
            "fail_closed_denial_requires_human_approval",
            "manual_safety_audit_is_a_per_run_gate",
            "manual_audit_outcome_may_be_inferred_by_harness",
        ),
    )
    _policy_section(
        contract["state_machine"],
        "contract.state_machine",
        literals={
            "current_state": "PUBLIC_SYNTHETIC_PROTOCOL_HARNESS_IMPLEMENTATION_GATE",
            "representable_states": [
                "DEFAULT_OFF",
                "PUBLIC_SYNTHETIC_PROTOCOL_HARNESS_EXERCISED_NO_AUTHORITY",
                "INVALIDATED_NO_RETRY",
                "REJECTED_FAIL_CLOSED",
            ],
        },
        true_fields=("public_synthetic_harness_implementation_present",),
        false_fields=(
            "native_sandbox_adapter_implementation_present",
            "candidate_implementation_present",
            "real_freeze_capability_present",
            "private_run_plan_present",
            "sealed_run_present",
            "positive_execution_or_data_authority_state_representable",
        ),
    )
    _policy_section(
        contract["boundaries"],
        "contract.boundaries",
        true_fields=(
            "g1_4_design_preregistration_bound",
            "public_synthetic_protocol_harness_implemented",
        ),
        false_fields=(
            "observes_real_role_corpus_candidate_or_result_evidence",
            "native_sandbox_enforcement_verified",
            "candidate_manifest_access_authority",
            "candidate_fit_access_authority",
            "candidate_development_access_authority",
            "candidate_sealed_access_authority",
            "candidate_implementation_authority",
            "protocol_execution_authority",
            "sealed_evaluation_authority",
            "result_unblinding_or_release_authority",
            "biocortex_experiment_execution_authority",
            "retrieval_order_mutation_authority",
            "live_store_write_authority",
            "runtime_promotion_authority",
        ),
    )
    return contract


def validate_fixture_semantics(value: dict[str, Any]) -> dict[str, Any]:
    """Validate the public synthetic fixture below its separate raw-byte pin."""

    fixture = _exact_keys(
        value,
        {
            "schema",
            "fixture_id",
            "mode",
            "public_synthetic_fixture",
            "production_admissible",
            "candidate_artifact",
            "blinding",
            "sandbox_attestation",
            "qualification",
            "synthetic_run",
            "decision_input",
            "expected",
        },
        "fixture",
    )
    _exact_value(fixture["schema"], FIXTURE_SCHEMA, "fixture.schema")
    _exact_value(fixture["fixture_id"], FIXTURE_ID, "fixture.fixture_id")
    _exact_value(fixture["mode"], MODE, "fixture.mode")
    _exact_value(
        fixture["public_synthetic_fixture"], True, "fixture.public_synthetic_fixture"
    )
    _exact_value(
        fixture["production_admissible"], False, "fixture.production_admissible"
    )

    artifact = _exact_keys(
        fixture["candidate_artifact"],
        {"development_lock", "development_feedback_rounds", "final_lock"},
        "fixture.candidate_artifact",
    )
    for name, fields in (
        ("development_lock", DEVELOPMENT_LOCK_FIELDS),
        ("final_lock", FINAL_LOCK_FIELDS),
    ):
        lock = _exact_keys(
            artifact[name], set(fields), f"fixture.candidate_artifact.{name}"
        )
        for field in fields:
            _require_sha256(lock[field], f"fixture.candidate_artifact.{name}.{field}")
    feedback = artifact["development_feedback_rounds"]
    _require(type(feedback) is list, "E_SCHEMA", "feedback rounds must be an array")
    _require(len(feedback) <= 2, "E_FEEDBACK_BUDGET", "feedback budget exceeded")
    for index, row in enumerate(feedback):
        path = f"fixture.candidate_artifact.development_feedback_rounds[{index}]"
        item = _exact_keys(
            row,
            {
                "round",
                "aggregate_receipt_sha256",
                "aggregate_only",
                "raw_probe_or_partition_material_present",
            },
            path,
        )
        _exact_value(item["round"], index + 1, f"{path}.round")
        _require_sha256(
            item["aggregate_receipt_sha256"], f"{path}.aggregate_receipt_sha256"
        )
        _exact_value(item["aggregate_only"], True, f"{path}.aggregate_only")
        _exact_value(
            item["raw_probe_or_partition_material_present"],
            False,
            f"{path}.raw_probe_or_partition_material_present",
        )

    blinding = _exact_keys(
        fixture["blinding"],
        {"predecision", "postdecision_reveal"},
        "fixture.blinding",
    )
    predecision = _exact_keys(
        blinding["predecision"],
        {
            "arm_mapping_commitment_sha256",
            "opaque_arm_ids_in_execution_order",
            "scorer_visible_arm_ids",
            "mapping_reveal_available_to_scorer_before_decision",
        },
        "fixture.blinding.predecision",
    )
    _require_sha256(
        predecision["arm_mapping_commitment_sha256"],
        "fixture.blinding.predecision.arm_mapping_commitment_sha256",
    )
    _semantic_value(
        predecision["opaque_arm_ids_in_execution_order"],
        OPAQUE_ARM_IDS,
        "fixture.blinding.predecision.opaque_arm_ids_in_execution_order",
    )
    _semantic_value(
        predecision["scorer_visible_arm_ids"],
        OPAQUE_ARM_IDS,
        "fixture.blinding.predecision.scorer_visible_arm_ids",
    )
    _semantic_value(
        blinding["postdecision_reveal"],
        ARM_MAPPING,
        "fixture.blinding.postdecision_reveal",
    )
    _exact_value(
        predecision["mapping_reveal_available_to_scorer_before_decision"],
        False,
        "fixture.blinding.predecision.mapping_reveal_available_to_scorer_before_decision",
    )

    sandbox = _exact_keys(
        fixture["sandbox_attestation"],
        {
            "evidence_kind",
            "platform",
            "profile",
            "support_reported",
            "policy_apply_reported",
            "active_reported",
            "native_enforcement_observed",
            "environment_allowlist_sha256",
            "mount_set_sha256",
            "output_schema_sha256",
            "resource_budget_sha256",
            "runner_sha256",
            "resource_ceilings",
            "canaries",
        },
        "fixture.sandbox_attestation",
    )
    _exact_value(
        sandbox["evidence_kind"],
        SANDBOX_EVIDENCE_KIND,
        "fixture.sandbox_attestation.evidence_kind",
    )
    _exact_value(
        sandbox["platform"],
        "public_synthetic_cross_platform_policy_model",
        "fixture.sandbox_attestation.platform",
    )
    _exact_value(
        sandbox["profile"], SANDBOX_PROFILE, "fixture.sandbox_attestation.profile"
    )
    for field in (
        "support_reported",
        "policy_apply_reported",
        "active_reported",
        "native_enforcement_observed",
    ):
        _require(
            type(sandbox[field]) is bool,
            "E_SCHEMA",
            f"fixture.sandbox_attestation.{field} must be boolean",
        )
    for field in (
        "environment_allowlist_sha256",
        "mount_set_sha256",
        "output_schema_sha256",
        "resource_budget_sha256",
        "runner_sha256",
    ):
        _require_sha256(sandbox[field], f"fixture.sandbox_attestation.{field}")
    ceilings = _exact_keys(
        sandbox["resource_ceilings"],
        {
            "cpu_millis",
            "memory_bytes",
            "wall_time_millis",
            "file_count",
            "writable_bytes",
            "output_bytes",
        },
        "fixture.sandbox_attestation.resource_ceilings",
    )
    for field, amount in ceilings.items():
        _require(
            type(amount) is int and amount > 0,
            "E_RESOURCE",
            f"resource ceiling {field} must be a positive integer",
        )
    canaries = sandbox["canaries"]
    _require(type(canaries) is list, "E_SCHEMA", "sandbox canaries must be an array")
    _require(
        len(canaries) == len(REQUIRED_CANARIES),
        "E_SANDBOX_CANARY",
        "sandbox canary count drifted",
    )
    for index, name in enumerate(REQUIRED_CANARIES):
        path = f"fixture.sandbox_attestation.canaries[{index}]"
        canary = _exact_keys(canaries[index], {"name", "expected", "observed"}, path)
        expected = "allow" if name in ALLOWED_CANARIES else "deny"
        _exact_value(canary["name"], name, f"{path}.name")
        _exact_value(canary["expected"], expected, f"{path}.expected")
        _require(
            type(canary["observed"]) is str and canary["observed"] in {"allow", "deny"},
            "E_SANDBOX_CANARY",
            f"{path}.observed must be allow or deny",
        )

    qualification = _exact_keys(
        fixture["qualification"],
        {"seed_schedule_commitment_sha256", "replays"},
        "fixture.qualification",
    )
    _require_sha256(
        qualification["seed_schedule_commitment_sha256"],
        "fixture.qualification.seed_schedule_commitment_sha256",
    )
    replays = qualification["replays"]
    _require(
        type(replays) is list and len(replays) == 2,
        "E_DETERMINISM",
        "exactly two qualification replays are required",
    )
    for index, replay in enumerate(replays):
        path = f"fixture.qualification.replays[{index}]"
        item = _exact_keys(
            replay,
            {"replay", "invocation_ids", "ranked_output_commitments_by_opaque_arm"},
            path,
        )
        _exact_value(item["replay"], index + 1, f"{path}.replay")
        ids = item["invocation_ids"]
        _require(
            type(ids) is list and len(ids) == len(OPAQUE_ARM_IDS),
            "E_STATE_REUSE",
            f"{path}.invocation_ids count drifted",
        )
        for invocation_id in ids:
            _require_sha256(invocation_id, f"{path}.invocation_ids")
        outputs = _exact_keys(
            item["ranked_output_commitments_by_opaque_arm"],
            set(OPAQUE_ARM_IDS),
            f"{path}.ranked_output_commitments_by_opaque_arm",
        )
        for arm in OPAQUE_ARM_IDS:
            values = outputs[arm]
            _require(
                type(values) is list and len(values) == 2,
                "E_DETERMINISM",
                f"{path}.{arm} output count drifted",
            )
            for output in values:
                _require_sha256(output, f"{path}.{arm}")

    run = _exact_keys(
        fixture["synthetic_run"],
        {
            "run_id",
            "synthetic_capability_sha256",
            "real_freeze_capability_present",
            "partition_shape",
            "one_shot",
            "invocations",
        },
        "fixture.synthetic_run",
    )
    _exact_value(
        run["run_id"], "public_synthetic_g14_run_v0", "fixture.synthetic_run.run_id"
    )
    _require_sha256(
        run["synthetic_capability_sha256"],
        "fixture.synthetic_run.synthetic_capability_sha256",
    )
    _exact_value(
        run["real_freeze_capability_present"],
        False,
        "fixture.synthetic_run.real_freeze_capability_present",
    )
    _exact_value(
        run["partition_shape"],
        "public_synthetic_sealed_shape_only",
        "fixture.synthetic_run.partition_shape",
    )
    _exact_value(run["one_shot"], True, "fixture.synthetic_run.one_shot")
    invocations = run["invocations"]
    _require(
        type(invocations) is list and len(invocations) == len(OPAQUE_ARM_IDS),
        "E_INVOCATION",
        "synthetic invocation count drifted",
    )
    for index, invocation in enumerate(invocations):
        path = f"fixture.synthetic_run.invocations[{index}]"
        item = _exact_keys(
            invocation,
            {
                "ordinal",
                "opaque_arm_id",
                "invocation_id",
                "status",
                "output_schema_valid",
                "scratch_destroyed",
                "resource_budget_match",
            },
            path,
        )
        _exact_value(item["ordinal"], index + 1, f"{path}.ordinal")
        _exact_value(
            item["opaque_arm_id"], OPAQUE_ARM_IDS[index], f"{path}.opaque_arm_id"
        )
        _require_sha256(item["invocation_id"], f"{path}.invocation_id")
        _require(
            type(item["status"]) is str and item["status"] in INVOCATION_STATUSES,
            "E_INVOCATION",
            f"{path}.status is outside the closed status set",
        )
        for field in (
            "output_schema_valid",
            "scratch_destroyed",
            "resource_budget_match",
        ):
            _require(
                type(item[field]) is bool,
                "E_SCHEMA",
                f"{path}.{field} must be boolean",
            )

    _validate_decision_shape(fixture["decision_input"])
    expected = _policy_section(
        fixture["expected"],
        "fixture.expected",
        literals={
            "verdict": "PASS_PUBLIC_SYNTHETIC_PROTOCOL_HARNESS_NO_AUTHORITY",
            "decision": "SYNTHETIC_CANDIDATE_RULE_PASS_NO_EXPERIMENT_AUTHORITY",
            "receipt_count": 14,
        },
        false_fields=(
            "native_sandbox_enforcement_verified",
            "g1_4_execution_open",
            "production_admissible",
        ),
    )
    _require(expected is not None, "E_INTERNAL", "expected receipt missing")
    return fixture


def _validate_decision_shape(value: Any) -> dict[str, Any]:
    decision = _exact_keys(
        value,
        {
            "candidate_comparisons",
            "falsifier_comparisons",
            "paired_by_episode_group",
            "sealed_shape_is_decisive",
            "fit_or_development_used_for_final_verdict",
        },
        "fixture.decision_input",
    )
    for field in ("paired_by_episode_group", "sealed_shape_is_decisive"):
        _exact_value(decision[field], True, f"fixture.decision_input.{field}")
    _exact_value(
        decision["fit_or_development_used_for_final_verdict"],
        False,
        "fixture.decision_input.fit_or_development_used_for_final_verdict",
    )
    rows = decision["candidate_comparisons"]
    _require(
        type(rows) is list and len(rows) == 2,
        "E_DECISION",
        "two comparator rows are required",
    )
    for index, comparator in enumerate(COMPARATORS):
        path = f"fixture.decision_input.candidate_comparisons[{index}]"
        row = _exact_keys(
            rows[index],
            {
                "comparator",
                "candidate_primary_repairs",
                "new_exact_misses",
                "new_related_misses",
                "no_relevant_gap_regressions",
                "per_mode_unrelated_intrusion_increases",
                "exact_mrr_absolute_loss",
                "related_mrr_absolute_loss",
            },
            path,
        )
        _exact_value(row["comparator"], comparator, f"{path}.comparator")
        for field in (
            "candidate_primary_repairs",
            "new_exact_misses",
            "new_related_misses",
            "no_relevant_gap_regressions",
            "per_mode_unrelated_intrusion_increases",
        ):
            _require(
                type(row[field]) is int and row[field] >= 0,
                "E_DECISION",
                f"{path}.{field} must be a non-negative integer",
            )
        for field in ("exact_mrr_absolute_loss", "related_mrr_absolute_loss"):
            _decimal(row[field], f"{path}.{field}")
    falsifiers = decision["falsifier_comparisons"]
    _require(
        type(falsifiers) is list and len(falsifiers) == 2,
        "E_DECISION",
        "two falsifier rows are required",
    )
    for index, falsifier in enumerate(FALSIFIERS):
        path = f"fixture.decision_input.falsifier_comparisons[{index}]"
        row = _exact_keys(
            falsifiers[index],
            {"falsifier", "repairs_vs_stable_control", "repairs_vs_density_only"},
            path,
        )
        _exact_value(row["falsifier"], falsifier, f"{path}.falsifier")
        for field in ("repairs_vs_stable_control", "repairs_vs_density_only"):
            _require(
                type(row[field]) is int and row[field] >= 0,
                "E_DECISION",
                f"{path}.{field} must be a non-negative integer",
            )
    return decision


def _decimal(value: Any, path: str) -> Decimal:
    _require(type(value) is str, "E_DECISION", f"{path} must be a decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation:
        _fail("E_DECISION", f"{path} is not a finite decimal")
    _require(
        number.is_finite() and number >= 0,
        "E_DECISION",
        f"{path} must be finite and non-negative",
    )
    return number


def validate_predecessor_artifacts(repo_root: Path) -> None:
    expected = {
        repo_root
        / "scripts/eval/fixtures/engram_g14_candidate_protocol_preregistration_contract_v0.json": PREDECESSOR_CONTRACT_SHA256,
        repo_root
        / "scripts/eval/engram_g14_candidate_protocol_preregistration.py": PREDECESSOR_VALIDATOR_SHA256,
        repo_root
        / "scripts/check-engram-g14-candidate-protocol-preregistration.sh": PREDECESSOR_CHECKER_SHA256,
    }
    for path, digest in expected.items():
        try:
            raw = read_stable_bounded_file(path)
        except OSError as exc:
            _fail("E_PREDECESSOR", f"failed to read {path.name}: {exc}")
        _require(
            _sha256(raw) == digest,
            "E_PREDECESSOR",
            f"predecessor artifact drifted: {path.name}",
        )


def implementation_sha256() -> str:
    return _sha256(Path(__file__).resolve().read_bytes())


class ReceiptChain:
    """Append-only in-memory public synthetic receipt chain."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(
        self, schema: str, phase: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        sequence = len(self.events) + 1
        previous_sha256 = self.events[-1]["event_sha256"] if self.events else "0" * 64
        embedded_payload = copy.deepcopy(payload)
        body = {
            "schema": schema,
            "sequence": sequence,
            "previous_sha256": previous_sha256,
            "phase": phase,
            "payload": embedded_payload,
            "payload_sha256": canonical_sha256(embedded_payload),
            "synthetic_only": True,
            "production_admissible": False,
        }
        event = {**body, "event_sha256": canonical_sha256(body)}
        self.events.append(event)
        return copy.deepcopy(event)

    @staticmethod
    def verify(events: list[dict[str, Any]]) -> str:
        previous = "0" * 64
        for index, event in enumerate(events):
            path = f"receipt_chain[{index}]"
            row = _exact_keys(
                event,
                {
                    "schema",
                    "sequence",
                    "previous_sha256",
                    "phase",
                    "payload",
                    "payload_sha256",
                    "synthetic_only",
                    "production_admissible",
                    "event_sha256",
                },
                path,
            )
            _exact_value(row["sequence"], index + 1, f"{path}.sequence")
            _exact_value(row["previous_sha256"], previous, f"{path}.previous_sha256")
            _require(
                type(row["payload"]) is dict,
                "E_SCHEMA",
                f"{path}.payload must be an object",
            )
            _exact_value(
                row["payload_sha256"],
                canonical_sha256(row["payload"]),
                f"{path}.payload_sha256",
            )
            _exact_value(row["synthetic_only"], True, f"{path}.synthetic_only")
            _exact_value(
                row["production_admissible"], False, f"{path}.production_admissible"
            )
            body = {key: value for key, value in row.items() if key != "event_sha256"}
            expected = canonical_sha256(body)
            _exact_value(row["event_sha256"], expected, f"{path}.event_sha256")
            previous = expected
        return previous


def _freeze_expected_scoring_receipt_head(fixture: dict[str, Any]) -> str:
    """Freeze the exact predecision chain head before scorer execution."""

    chain = ReceiptChain()
    artifact = fixture["candidate_artifact"]
    blinding = fixture["blinding"]
    sandbox = fixture["sandbox_attestation"]
    qualification = fixture["qualification"]
    run = fixture["synthetic_run"]
    development_digest = canonical_sha256(artifact["development_lock"])
    final_digest = canonical_sha256(artifact["final_lock"])

    chain.append(
        "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
        "development_lock",
        {
            "lock_sha256": development_digest,
            "lock_kind": "development",
            "contract_sha256": CONTRACT_SHA256,
            "fixture_sha256": FIXTURE_SHA256,
            "implementation_sha256": implementation_sha256(),
            "predecessor_commit": PREDECESSOR_COMMIT,
            "predecessor_contract_sha256": PREDECESSOR_CONTRACT_SHA256,
        },
    )
    for feedback in artifact["development_feedback_rounds"]:
        chain.append(
            "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
            "development_feedback",
            {
                "round": feedback["round"],
                "aggregate_receipt_sha256": feedback["aggregate_receipt_sha256"],
            },
        )
    chain.append(
        "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
        "final_lock",
        {
            "lock_sha256": final_digest,
            "development_lock_sha256": development_digest,
            "feedback_round_count": len(artifact["development_feedback_rounds"]),
        },
    )
    chain.append(
        "agent_bridge.engram_g1_4_synthetic_blinded_run_plan_receipt.v0",
        "blinded_run_plan",
        {
            "arm_mapping_commitment_sha256": blinding["arm_mapping_commitment_sha256"],
            "opaque_arm_count": len(OPAQUE_ARM_IDS),
            "final_lock_sha256": final_digest,
            "synthetic_capability_sha256": run["synthetic_capability_sha256"],
            "runner_sha256": sandbox["runner_sha256"],
            "mapping_present": False,
        },
    )
    chain.append(
        "agent_bridge.engram_g1_4_synthetic_sandbox_attestation_receipt.v0",
        "sandbox_attestation",
        {
            "profile": SANDBOX_PROFILE,
            "evidence_kind": SANDBOX_EVIDENCE_KIND,
            "canary_count": len(REQUIRED_CANARIES),
            "all_canaries_match": True,
            "native_enforcement_verified": False,
            "resource_budget_sha256": sandbox["resource_budget_sha256"],
            "mount_set_sha256": sandbox["mount_set_sha256"],
            "environment_allowlist_sha256": sandbox["environment_allowlist_sha256"],
            "output_schema_sha256": sandbox["output_schema_sha256"],
            "runner_sha256": sandbox["runner_sha256"],
        },
    )
    chain.append(
        "agent_bridge.engram_g1_4_synthetic_qualification_receipt.v0",
        "qualification",
        {
            "replay_count": 2,
            "outputs_identical": True,
            "seed_schedule_commitment_sha256": qualification[
                "seed_schedule_commitment_sha256"
            ],
        },
    )
    for invocation in run["invocations"]:
        chain.append(
            "agent_bridge.engram_g1_4_synthetic_invocation_receipt.v0",
            "synthetic_run",
            {
                "ordinal": invocation["ordinal"],
                "opaque_arm_id": invocation["opaque_arm_id"],
                "invocation_commitment_sha256": canonical_sha256(invocation),
                "status": "ok",
                "scratch_destroyed": True,
            },
        )
    return ReceiptChain.verify(chain.events)


class CandidateArtifactState:
    """Two-phase public synthetic candidate-lock state."""

    def __init__(self) -> None:
        self.development_digest: str | None = None
        self.feedback_count = 0
        self.final_digest: str | None = None

    def register_development_lock(self, lock: dict[str, Any]) -> str:
        _require(
            self.development_digest is None,
            "E_LOCK_REPLAY",
            "development lock already exists",
        )
        self.development_digest = canonical_sha256(lock)
        return self.development_digest

    def record_feedback(self, row: dict[str, Any]) -> None:
        _require(
            self.development_digest is not None,
            "E_PHASE",
            "feedback requires a development lock",
        )
        _require(
            self.final_digest is None,
            "E_FINAL_LOCK",
            "feedback after final lock is forbidden",
        )
        _require(
            self.feedback_count < 2,
            "E_FEEDBACK_BUDGET",
            "development feedback budget exceeded",
        )
        _exact_value(row["round"], self.feedback_count + 1, "feedback.round")
        self.feedback_count += 1

    def register_final_lock(self, lock: dict[str, Any]) -> str:
        _require(
            self.development_digest is not None,
            "E_PHASE",
            "final lock requires development lock",
        )
        _require(
            self.final_digest is None, "E_LOCK_REPLAY", "final lock already exists"
        )
        self.final_digest = canonical_sha256(lock)
        return self.final_digest

    def assert_unchanged(self, lock: dict[str, Any]) -> None:
        _require(self.final_digest is not None, "E_FINAL_LOCK", "final lock is missing")
        _require(
            canonical_sha256(lock) == self.final_digest,
            "E_FINAL_LOCK_DRIFT",
            "final lock material changed",
        )


class SyntheticRunRegistry:
    """Process-local one-shot registry and rollback-lesson model."""

    def __init__(self) -> None:
        self.states: dict[str, str] = {}
        self.synthetic_lessons: list[dict[str, Any]] = []

    def claim(self, run_id: str) -> None:
        _require(
            run_id not in self.states, "E_RUN_REPLAY", "run id was already consumed"
        )
        self.states[run_id] = "ACTIVE"

    def invalidate(
        self, run_id: str, reason_code: str, *, rollback_succeeded: bool = True
    ) -> None:
        _require(
            self.states.get(run_id) == "ACTIVE", "E_RUN_STATE", "run is not active"
        )
        self.states[run_id] = "INVALIDATED_NO_RETRY"
        if not rollback_succeeded:
            lesson = {
                "schema": "agent_bridge.engram_g1_4_synthetic_rollback_lesson.v0",
                "run_commitment_sha256": _sha256(run_id.encode("utf-8")),
                "reason_code": reason_code,
                "synthetic_only": True,
                "durable_in_real_implementation_required": True,
                "production_admissible": False,
            }
            self.synthetic_lessons.append(lesson)

    def complete(self, run_id: str) -> None:
        _require(
            self.states.get(run_id) == "ACTIVE", "E_RUN_STATE", "run is not active"
        )
        self.states[run_id] = "COMPLETED_SYNTHETIC_NO_AUTHORITY"


def evaluate_decision(value: dict[str, Any]) -> tuple[str, list[str]]:
    """Apply the preregistered decision guards to aggregate synthetic input."""

    decision = _validate_decision_shape(value)
    reasons: list[str] = []
    candidate_repairs: dict[str, int] = {}
    for row in decision["candidate_comparisons"]:
        comparator = row["comparator"]
        candidate_repairs[comparator] = row["candidate_primary_repairs"]
        if row["candidate_primary_repairs"] < 2:
            reasons.append(f"candidate_repairs_below_two_vs_{comparator}")
        for field in (
            "new_exact_misses",
            "new_related_misses",
            "no_relevant_gap_regressions",
            "per_mode_unrelated_intrusion_increases",
        ):
            if row[field] != 0:
                reasons.append(f"{field}_nonzero_vs_{comparator}")
        if _decimal(
            row["exact_mrr_absolute_loss"], "exact_mrr_absolute_loss"
        ) > Decimal("0.05"):
            reasons.append(f"exact_mrr_loss_exceeded_vs_{comparator}")
        if _decimal(
            row["related_mrr_absolute_loss"], "related_mrr_absolute_loss"
        ) > Decimal("0.05"):
            reasons.append(f"related_mrr_loss_exceeded_vs_{comparator}")
    for row in decision["falsifier_comparisons"]:
        falsifier = row["falsifier"]
        for comparator in COMPARATORS:
            repairs = row[f"repairs_vs_{comparator}"]
            if repairs > 1:
                reasons.append(f"{falsifier}_repairs_above_one_vs_{comparator}")
            if candidate_repairs[comparator] <= repairs:
                reasons.append(f"candidate_not_above_{falsifier}_vs_{comparator}")
    if reasons:
        return "SYNTHETIC_CANDIDATE_RULE_FAIL_NO_EXPERIMENT_AUTHORITY", reasons
    return "SYNTHETIC_CANDIDATE_RULE_PASS_NO_EXPERIMENT_AUTHORITY", []


class SyntheticProtocolCustodian:
    """Synthetic decision/reveal boundary outside the scorer-facing view."""

    def __init__(
        self,
        mapping: dict[str, str],
        commitment_sha256: str,
        decision_input: dict[str, Any],
        expected_scoring_head_sha256: str,
    ) -> None:
        self.__mapping = copy.deepcopy(mapping)
        self.__commitment_sha256 = commitment_sha256
        self.__decision_input = copy.deepcopy(decision_input)
        _require_sha256(
            expected_scoring_head_sha256,
            "custodian.expected_scoring_head_sha256",
        )
        self.__expected_scoring_head_sha256 = expected_scoring_head_sha256
        self.__decision: str | None = None
        self.__reason_count: int | None = None
        self.__scoring_head_sha256: str | None = None
        self.__revealed = False

    def validate_precommitment(self) -> None:
        _require(
            canonical_sha256(self.__mapping) == self.__commitment_sha256,
            "E_ARM_MAPPING_COMMITMENT",
            "arm mapping does not match its precommitment",
        )

    def __verify_complete_scoring_receipts(
        self, receipt_events: list[dict[str, Any]]
    ) -> str:
        head = ReceiptChain.verify(receipt_events)
        _require(bool(receipt_events), "E_PHASE", "scoring receipt is missing")
        _require(
            head == self.__expected_scoring_head_sha256,
            "E_RECEIPT_ANCHOR",
            "scoring chain differs from its predecision frozen head",
        )
        _exact_value(
            receipt_events[-1]["phase"],
            "synthetic_run",
            "decision.previous_phase",
        )
        invocation_receipts = [
            event for event in receipt_events if event["phase"] == "synthetic_run"
        ]
        _require(
            len(invocation_receipts) == len(OPAQUE_ARM_IDS),
            "E_INVOCATION",
            "decision requires one receipt per opaque arm",
        )
        for index, event in enumerate(invocation_receipts):
            payload = _exact_keys(
                event["payload"],
                {
                    "ordinal",
                    "opaque_arm_id",
                    "invocation_commitment_sha256",
                    "status",
                    "scratch_destroyed",
                },
                f"decision.invocation_receipts[{index}].payload",
            )
            _exact_value(payload["ordinal"], index + 1, "decision.ordinal")
            _exact_value(
                payload["opaque_arm_id"], OPAQUE_ARM_IDS[index], "decision.opaque_arm"
            )
            _require_sha256(
                payload["invocation_commitment_sha256"],
                "decision.invocation_commitment_sha256",
            )
            _exact_value(payload["status"], "ok", "decision.invocation_status")
            _exact_value(
                payload["scratch_destroyed"], True, "decision.scratch_destroyed"
            )
        return head

    def decide_after_scoring(
        self, receipt_events: list[dict[str, Any]]
    ) -> tuple[str, list[str]]:
        _require(
            self.__decision is None,
            "E_DECISION_REPLAY",
            "custodian decision was already frozen",
        )
        self.__scoring_head_sha256 = self.__verify_complete_scoring_receipts(
            receipt_events
        )
        decision, reasons = evaluate_decision(copy.deepcopy(self.__decision_input))
        self.__decision = decision
        self.__reason_count = len(reasons)
        return decision, reasons

    def reveal_after_decision(
        self, receipt_events: list[dict[str, Any]]
    ) -> dict[str, str]:
        _require(not self.__revealed, "E_REVEAL_REPLAY", "mapping was already revealed")
        _require(
            self.__decision is not None
            and self.__reason_count is not None
            and self.__scoring_head_sha256 is not None,
            "E_DECISION_STATE",
            "mapping reveal requires this custodian's frozen decision",
        )
        ReceiptChain.verify(receipt_events)
        _require(bool(receipt_events), "E_REVEAL_ORDER", "decision receipt is missing")
        decision_receipt = receipt_events[-1]
        _exact_value(decision_receipt["phase"], "decision", "reveal.previous_phase")
        _exact_value(
            decision_receipt["schema"],
            "agent_bridge.engram_g1_4_synthetic_decision_receipt.v0",
            "reveal.decision_schema",
        )
        _exact_value(
            decision_receipt["previous_sha256"],
            self.__scoring_head_sha256,
            "reveal.scoring_head_sha256",
        )
        _exact_value(
            self.__verify_complete_scoring_receipts(receipt_events[:-1]),
            self.__scoring_head_sha256,
            "reveal.reverified_scoring_head_sha256",
        )
        decision_payload = _exact_keys(
            decision_receipt["payload"],
            {"decision", "reason_count", "decision_frozen", "mapping_present"},
            "reveal.decision_payload",
        )
        _exact_value(decision_payload["decision"], self.__decision, "reveal.decision")
        _exact_value(
            decision_payload["reason_count"],
            self.__reason_count,
            "reveal.reason_count",
        )
        _exact_value(
            decision_payload["decision_frozen"],
            True,
            "reveal.decision_frozen",
        )
        _exact_value(
            decision_payload["mapping_present"],
            False,
            "reveal.mapping_present",
        )
        self.__revealed = True
        return copy.deepcopy(self.__mapping)


class SyntheticProtocolHarness:
    """Default-off in-memory protocol harness; never a native sandbox runner."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        registry: SyntheticRunRegistry | None = None,
        rollback_succeeds: bool = True,
    ) -> None:
        _require(
            type(rollback_succeeds) is bool,
            "E_SCHEMA",
            "rollback_succeeds must be boolean",
        )
        self.enabled = enabled
        self.registry = registry or SyntheticRunRegistry()
        self.rollback_succeeds = rollback_succeeds
        self.receipts = ReceiptChain()
        self.artifact = CandidateArtifactState()
        self.phase_index = -1
        self.state = "DEFAULT_OFF"
        self.run_id: str | None = None

    def _advance(self, phase: str) -> None:
        expected_index = self.phase_index + 1
        _require(expected_index < len(PHASES), "E_PHASE", "protocol already terminated")
        _exact_value(phase, PHASES[expected_index], "protocol.phase")
        self.phase_index = expected_index

    def _invalidate(self, error: HarnessError) -> None:
        self.state = "REJECTED_FAIL_CLOSED"
        if (
            self.run_id is not None
            and self.registry.states.get(self.run_id) == "ACTIVE"
        ):
            self.registry.invalidate(
                self.run_id,
                error.code,
                rollback_succeeded=self.rollback_succeeds,
            )
            self.state = "INVALIDATED_NO_RETRY"

    def exercise(self, fixture: dict[str, Any]) -> dict[str, Any]:
        _require(
            self.enabled is True,
            "E_DEFAULT_OFF",
            "explicit public-synthetic enable is required",
        )
        validate_fixture_semantics(fixture)
        scorer_view = copy.deepcopy(fixture)
        decision_input = scorer_view.pop("decision_input")
        expected_result = scorer_view.pop("expected")
        split_blinding = scorer_view["blinding"]
        reveal_material = split_blinding.pop("postdecision_reveal")
        predecision = split_blinding.pop("predecision")
        scorer_view["blinding"] = predecision
        expected_scoring_head_sha256 = _freeze_expected_scoring_receipt_head(
            scorer_view
        )
        custodian = SyntheticProtocolCustodian(
            reveal_material,
            predecision["arm_mapping_commitment_sha256"],
            decision_input,
            expected_scoring_head_sha256,
        )
        self.state = "RUNNING_PUBLIC_SYNTHETIC_PROTOCOL"
        try:
            self.run_id = scorer_view["synthetic_run"]["run_id"]
            self.registry.claim(self.run_id)
            custodian.validate_precommitment()
            self._exercise_predecision(scorer_view)
            decision, reasons = custodian.decide_after_scoring(self.receipts.events)
            self._record_decision(decision, reasons)
            mapping = custodian.reveal_after_decision(self.receipts.events)
            return self._finish_after_reveal(
                scorer_view,
                expected_result,
                mapping,
                decision,
                reasons,
            )
        except HarnessError as exc:
            self._invalidate(exc)
            raise

    def _exercise_predecision(self, fixture: dict[str, Any]) -> None:
        artifact = fixture["candidate_artifact"]
        self._advance("development_lock")
        development_digest = self.artifact.register_development_lock(
            artifact["development_lock"]
        )
        self.receipts.append(
            "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
            "development_lock",
            {
                "lock_sha256": development_digest,
                "lock_kind": "development",
                "contract_sha256": CONTRACT_SHA256,
                "fixture_sha256": FIXTURE_SHA256,
                "implementation_sha256": implementation_sha256(),
                "predecessor_commit": PREDECESSOR_COMMIT,
                "predecessor_contract_sha256": PREDECESSOR_CONTRACT_SHA256,
            },
        )

        self._advance("development_feedback")
        for feedback in artifact["development_feedback_rounds"]:
            self.artifact.record_feedback(feedback)
            self.receipts.append(
                "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
                "development_feedback",
                {
                    "round": feedback["round"],
                    "aggregate_receipt_sha256": feedback["aggregate_receipt_sha256"],
                },
            )

        self._advance("final_lock")
        final_digest = self.artifact.register_final_lock(artifact["final_lock"])
        self.receipts.append(
            "agent_bridge.engram_g1_4_synthetic_candidate_lock_receipt.v0",
            "final_lock",
            {
                "lock_sha256": final_digest,
                "development_lock_sha256": development_digest,
                "feedback_round_count": self.artifact.feedback_count,
            },
        )

        self._advance("blinded_run_plan")
        blinding = fixture["blinding"]
        run = fixture["synthetic_run"]
        sandbox = fixture["sandbox_attestation"]
        self.artifact.assert_unchanged(artifact["final_lock"])
        self.receipts.append(
            "agent_bridge.engram_g1_4_synthetic_blinded_run_plan_receipt.v0",
            "blinded_run_plan",
            {
                "arm_mapping_commitment_sha256": blinding[
                    "arm_mapping_commitment_sha256"
                ],
                "opaque_arm_count": len(OPAQUE_ARM_IDS),
                "final_lock_sha256": final_digest,
                "synthetic_capability_sha256": run["synthetic_capability_sha256"],
                "runner_sha256": sandbox["runner_sha256"],
                "mapping_present": False,
            },
        )

        self._advance("sandbox_attestation")
        for field in ("support_reported", "policy_apply_reported", "active_reported"):
            _require(
                sandbox[field] is True,
                "E_SANDBOX_UNAVAILABLE",
                f"sandbox {field} is false",
            )
        _require(
            sandbox["native_enforcement_observed"] is False,
            "E_NATIVE_SANDBOX_CLAIM",
            "synthetic attestation cannot claim native enforcement",
        )
        for canary in sandbox["canaries"]:
            _require(
                canary["observed"] == canary["expected"],
                "E_SANDBOX_CANARY",
                f"canary mismatch: {canary['name']}",
            )
        self.receipts.append(
            "agent_bridge.engram_g1_4_synthetic_sandbox_attestation_receipt.v0",
            "sandbox_attestation",
            {
                "profile": SANDBOX_PROFILE,
                "evidence_kind": SANDBOX_EVIDENCE_KIND,
                "canary_count": len(REQUIRED_CANARIES),
                "all_canaries_match": True,
                "native_enforcement_verified": False,
                "resource_budget_sha256": sandbox["resource_budget_sha256"],
                "mount_set_sha256": sandbox["mount_set_sha256"],
                "environment_allowlist_sha256": sandbox["environment_allowlist_sha256"],
                "output_schema_sha256": sandbox["output_schema_sha256"],
                "runner_sha256": sandbox["runner_sha256"],
            },
        )

        self._advance("qualification")
        qualification = fixture["qualification"]
        replays = qualification["replays"]
        qualification_invocation_ids = [
            invocation_id
            for replay in replays
            for invocation_id in replay["invocation_ids"]
        ]
        _require(
            len(qualification_invocation_ids) == len(set(qualification_invocation_ids)),
            "E_STATE_REUSE",
            "qualification invocation IDs were reused",
        )
        _require(
            canonical_bytes(replays[0]["ranked_output_commitments_by_opaque_arm"])
            == canonical_bytes(replays[1]["ranked_output_commitments_by_opaque_arm"]),
            "E_DETERMINISM",
            "qualification replay outputs diverged",
        )
        self.receipts.append(
            "agent_bridge.engram_g1_4_synthetic_qualification_receipt.v0",
            "qualification",
            {
                "replay_count": 2,
                "outputs_identical": True,
                "seed_schedule_commitment_sha256": qualification[
                    "seed_schedule_commitment_sha256"
                ],
            },
        )

        self._advance("synthetic_run")
        run_invocation_ids = [
            invocation["invocation_id"] for invocation in run["invocations"]
        ]
        _require(
            len(run_invocation_ids) == len(set(run_invocation_ids)),
            "E_STATE_REUSE",
            "run invocation IDs were reused",
        )
        _require(
            not (set(run_invocation_ids) & set(qualification_invocation_ids)),
            "E_STATE_REUSE",
            "run reused a qualification invocation ID",
        )
        for invocation in run["invocations"]:
            _require(
                invocation["status"] == "ok",
                "E_INVOCATION",
                "invocation did not complete",
            )
            _require(
                invocation["output_schema_valid"] is True,
                "E_OUTPUT_SCHEMA",
                "invocation output schema failed",
            )
            _require(
                invocation["scratch_destroyed"] is True,
                "E_STATE_REUSE",
                "invocation scratch survived",
            )
            _require(
                invocation["resource_budget_match"] is True,
                "E_RESOURCE",
                "invocation resource budget drifted",
            )
            self.receipts.append(
                "agent_bridge.engram_g1_4_synthetic_invocation_receipt.v0",
                "synthetic_run",
                {
                    "ordinal": invocation["ordinal"],
                    "opaque_arm_id": invocation["opaque_arm_id"],
                    "invocation_commitment_sha256": canonical_sha256(invocation),
                    "status": "ok",
                    "scratch_destroyed": True,
                },
            )

    def _record_decision(self, decision: str, reasons: list[str]) -> None:
        self._advance("decision")
        self.receipts.append(
            "agent_bridge.engram_g1_4_synthetic_decision_receipt.v0",
            "decision",
            {
                "decision": decision,
                "reason_count": len(reasons),
                "decision_frozen": True,
                "mapping_present": False,
            },
        )

    def _finish_after_reveal(
        self,
        fixture: dict[str, Any],
        expected_result: dict[str, Any],
        mapping: dict[str, str],
        decision: str,
        reasons: list[str],
    ) -> dict[str, Any]:
        blinding = fixture["blinding"]

        self._advance("mapping_reveal")
        _require(
            self.phase_index == PHASES.index("mapping_reveal"),
            "E_REVEAL_ORDER",
            "mapping reveal preceded decision",
        )
        _require(
            canonical_sha256(mapping) == blinding["arm_mapping_commitment_sha256"],
            "E_ARM_MAPPING_COMMITMENT",
            "mapping reveal drifted",
        )
        self.receipts.append(
            "agent_bridge.engram_g1_4_synthetic_mapping_reveal_receipt.v0",
            "mapping_reveal",
            {
                "arm_mapping_commitment_sha256": blinding[
                    "arm_mapping_commitment_sha256"
                ],
                "revealed_after_decision": True,
                "public_receipt_contains_mapping": False,
            },
        )

        head = ReceiptChain.verify(self.receipts.events)
        self.state = "PUBLIC_SYNTHETIC_PROTOCOL_HARNESS_EXERCISED_NO_AUTHORITY"
        result = {
            "schema": RECEIPT_SCHEMA,
            "contract_id": CONTRACT_ID,
            "contract_sha256": CONTRACT_SHA256,
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
            "implementation_version": IMPLEMENTATION_VERSION,
            "implementation_sha256": implementation_sha256(),
            "predecessor_commit": PREDECESSOR_COMMIT,
            "predecessor_contract_sha256": PREDECESSOR_CONTRACT_SHA256,
            "mode": MODE,
            "verdict": "PASS_PUBLIC_SYNTHETIC_PROTOCOL_HARNESS_NO_AUTHORITY",
            "decision": decision,
            "decision_reason_count": len(reasons),
            "state": self.state,
            "receipt_count": len(self.receipts.events),
            "receipt_chain_head_sha256": head,
            "sandbox_profile": SANDBOX_PROFILE,
            "sandbox_evidence_kind": SANDBOX_EVIDENCE_KIND,
            "synthetic_canary_count": len(REQUIRED_CANARIES),
            "public_synthetic_protocol_harness_implemented": True,
            "native_sandbox_enforcement_implemented": False,
            "native_sandbox_enforcement_verified": False,
            "real_candidate_implementation_present": False,
            "real_freeze_capability_consumed": False,
            "private_corpus_accessed": False,
            "sealed_evaluation_executed": False,
            "g1_4_execution_open": False,
            "result_unblinding_or_release_authority": False,
            "retrieval_order_mutation_authority": False,
            "live_store_write_authority": False,
            "runtime_promotion_authority": False,
            "production_admissible": False,
            "only_permitted_successor": ONLY_PERMITTED_SUCCESSOR,
        }
        expected = expected_result
        _exact_value(result["verdict"], expected["verdict"], "result.verdict")
        _exact_value(result["decision"], expected["decision"], "result.decision")
        _exact_value(
            result["receipt_count"], expected["receipt_count"], "result.receipt_count"
        )
        _exact_value(
            result["native_sandbox_enforcement_verified"],
            expected["native_sandbox_enforcement_verified"],
            "result.native_sandbox_enforcement_verified",
        )
        _exact_value(
            result["g1_4_execution_open"],
            expected["g1_4_execution_open"],
            "result.g1_4_execution_open",
        )
        _exact_value(
            result["production_admissible"],
            expected["production_admissible"],
            "result.production_admissible",
        )
        self.registry.complete(self.run_id)
        return result


def validate_registered_contract() -> dict[str, Any]:
    contract = _read_pinned_json(REGISTERED_CONTRACT_PATH, CONTRACT_SHA256, "contract")
    validate_contract_semantics(contract)
    validate_predecessor_artifacts(Path(__file__).resolve().parents[2])
    return contract


def exercise_registered(*, enabled: bool) -> dict[str, Any]:
    validate_registered_contract()
    fixture = _read_pinned_json(REGISTERED_FIXTURE_PATH, FIXTURE_SHA256, "fixture")
    validate_fixture_semantics(fixture)
    return SyntheticProtocolHarness(enabled=enabled).exercise(fixture)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate-contract")
    exercise = subparsers.add_parser("exercise")
    exercise.add_argument("--enable-public-synthetic", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "validate-contract":
            contract = validate_registered_contract()
            output = {
                "schema": "agent_bridge.engram_g1_4_public_synthetic_protocol_harness_contract_receipt.v0",
                "contract_id": contract["contract_id"],
                "contract_sha256": CONTRACT_SHA256,
                "fixture_sha256": FIXTURE_SHA256,
                "implementation_sha256": implementation_sha256(),
                "verdict": "PUBLIC_SYNTHETIC_PROTOCOL_HARNESS_CONTRACT_VALID_NO_AUTHORITY",
                "production_admissible": False,
                "g1_4_execution_open": False,
            }
        else:
            output = exercise_registered(enabled=args.enable_public_synthetic)
        print(json.dumps(output, sort_keys=True, indent=2))
        return 0
    except HarnessError as exc:
        print(f"engram G1.4 public synthetic harness rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
