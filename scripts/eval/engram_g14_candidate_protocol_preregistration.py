#!/usr/bin/env python3
"""Validate the public G1.4 candidate-protocol preregistration contract.

This design-only validator reads no private corpus, candidate implementation,
freeze capability, run plan, or result material. It implements no sandbox,
runner, experiment, authority transition, or runtime surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from engram_g1_corpus_design import (
    InputError,
    read_json,
    read_stable_bounded_file,
    reject_raw_fields,
    require_exact_fields,
    require_exact_value,
    require_list,
    require_object,
    sha256_bytes,
)


CONTRACT_SCHEMA = (
    "agent_bridge.engram_g1_4_candidate_protocol_preregistration_contract.v0"
)
RECEIPT_SCHEMA = (
    "agent_bridge.engram_g1_4_candidate_protocol_preregistration_receipt.v0"
)
CONTRACT_ID = "engram_g14_candidate_protocol_preregistration_20260718"
CONTRACT_SHA256 = "dca8ac03fbc915d70c6470492136ca9e554722aeed8d789e85714ece7e60ea41"
VALIDATOR_SHA256 = sha256_bytes(Path(__file__).resolve().read_bytes())

PREDECESSOR_COMMIT = "bdd0b07b5e9afcc20d030e7e3dcfd404d44e8d54"
PREDECESSOR_CONTRACT_SHA256 = (
    "f9b913c50eaf477c58a11bbf9526070c43137fe91098388d8260f84eb51a3b14"
)
PREDECESSOR_IMPLEMENTATION_SHA256 = (
    "50e35469af07a81b6eef85fba5c83c92076efe1931b2ee932d8e2d05907ebc94"
)
PREDECESSOR_CHECKER_SHA256 = (
    "e9aec0676148591e44181b36bf6f0a3ad62f130e1c92ed88bdd3cf7519b4c69e"
)
PREDECESSOR_SHELL_SHA256 = (
    "6f81855d87d348e1e096adad9df2b271385edea3eed52695532155bac06e4895"
)

ADAPTER_PREREGISTRATION_CONTRACT_SHA256 = (
    "a9d267056fac1662b478d929b011ef971b309db60182f0f1c7563624571945c0"
)
ADAPTER_PREREGISTRATION_VALIDATOR_SHA256 = (
    "632f93b9c9bfcedeca81916ed34be6b4ce8b7b03b916c060b2d1999d06597fde"
)
ADAPTER_PREREGISTRATION_CHECKER_SHA256 = (
    "ea8ac0126306de517175a3dffa2a3722439b93b10a3d9d112ca1732f553e6f29"
)
G1_3_CONTRACT_SHA256 = (
    "5657ac8f4b6fd4f154de7285fd4a62125bf4ea15cba787d25da40701a3ac1504"
)
G1_3_VALIDATOR_SHA256 = (
    "0b7cb3295bc3690bbfeee033de2ddf27a39eb71d0cec68f96e9b27b1a67ef089"
)
G1_3_CHECKER_SHA256 = "e56a6f50a2c0372d0d59390e8792bc4269c4f63e282d49cf1a1bfe1fdd463e39"

EXPECTED_MANUAL_AUDIT_EVENTS = [
    "first_real_freeze_capability_consumption_or_private_run_plan_open",
    "candidate_or_runner_source_config_dependency_or_toolchain_change_after_final_lock",
    "fit_development_sealed_or_partition_access_policy_widening",
    "metric_threshold_arm_resource_retry_or_missingness_policy_change_after_any_observation",
    "sealed_partition_unblinding_selective_retry_or_rerun",
    "sandbox_filesystem_network_subprocess_log_output_or_side_channel_policy_change",
    "first_real_protocol_runner_enablement",
    "suspected_secret_privacy_identity_corpus_or_result_exposure",
]

EXPECTED_THREATS = [
    (
        "predecessor_capability_laundering",
        "real_single_use_authenticated_freeze_capability_exactly_bound_to_protocol_and_final_candidate_lock",
    ),
    (
        "candidate_source_config_dependency_or_runner_drift",
        "two_phase_hash_lock_with_final_sealed_lock_and_claim_time_recheck",
    ),
    (
        "arm_substitution_or_mapping_manipulation",
        "precommitted_arm_mapping_opaque_scoring_and_post_decision_reveal",
    ),
    (
        "private_corpus_membership_label_or_target_leakage",
        "role_separation_bounded_pipe_delivery_no_manifest_paths_and_redacted_receipts",
    ),
    (
        "network_subprocess_plugin_or_filesystem_exfiltration",
        "deny_by_default_nono_landlock_or_seatbelt_offline_sandbox",
    ),
    (
        "stdout_log_output_timing_or_resource_covert_channel",
        "fixed_bounded_output_no_released_logs_equal_resource_ceilings_and_redaction_review",
    ),
    (
        "cross_arm_group_or_partition_state_contamination",
        "fresh_process_per_invocation_and_destroyed_ephemeral_scratch",
    ),
    (
        "nondeterminism_external_entropy_or_clock_dependence",
        "registered_hidden_seed_schedule_two_identical_qualification_replays_and_no_external_entropy",
    ),
    (
        "adaptive_development_tuning_or_feedback_budget_overrun",
        "two_phase_lock_and_two_reviewer_mediated_aggregate_feedback_round_limit",
    ),
    (
        "selective_retry_timeout_missingness_or_partial_rerun_bias",
        "one_shot_sealed_run_whole_run_invalidation_and_no_selective_retry",
    ),
    (
        "post_observation_metric_threshold_arm_or_resource_drift",
        "exact_preregistered_decision_rule_and_versioned_manual_transition_audit",
    ),
    (
        "fit_development_pooling_or_sealed_early_peeking",
        "partition_separation_no_pooling_no_partial_release_and_decision_before_reveal",
    ),
    (
        "resource_budget_or_cache_asymmetry",
        "equal_precommitted_ceilings_mounts_sandbox_and_cache_normalization_across_arms",
    ),
    (
        "candidate_authored_targets_scoring_or_receipts",
        "custodian_owned_targets_independent_scorer_and_append_only_receipts",
    ),
    (
        "receipt_privacy_echo_digest_alias_or_free_form_exfiltration",
        "disjoint_digest_namespaces_salted_commitments_closed_schemas_and_no_candidate_text",
    ),
    (
        "cross_stage_scope_repository_manifest_or_protocol_replay",
        "exact_predecessor_repository_scope_manifest_protocol_runner_candidate_nonce_sequence_and_time_binding",
    ),
]


def require_semantic_value(actual: Any, expected: Any, path: str) -> None:
    """Recursively enforce one independently declared semantic value."""

    if isinstance(expected, dict):
        actual_object = require_object(actual, path)
        require_exact_fields(actual_object, set(expected), path)
        for field, expected_value in expected.items():
            require_semantic_value(
                actual_object[field], expected_value, f"{path}.{field}"
            )
        return
    if isinstance(expected, list):
        actual_list = require_list(actual, path)
        if len(actual_list) != len(expected):
            raise InputError(
                f"{path} length must remain preregistered as {len(expected)}"
            )
        for index, expected_value in enumerate(expected):
            require_semantic_value(
                actual_list[index], expected_value, f"{path}[{index}]"
            )
        return
    if type(actual) is not type(expected):
        raise InputError(
            f"{path} type must remain preregistered as {type(expected).__name__}"
        )
    require_exact_value(actual, expected, path)


def require_policy_section(
    actual: Any,
    path: str,
    *,
    literals: dict[str, Any] | None = None,
    true_fields: tuple[str, ...] = (),
    false_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Validate a closed policy section declared independently of the fixture."""

    literal_values = literals or {}
    expected_fields = set(literal_values) | set(true_fields) | set(false_fields)
    if len(expected_fields) != (
        len(literal_values) + len(true_fields) + len(false_fields)
    ):
        raise AssertionError(f"semantic policy declaration overlaps at {path}")
    section = require_object(actual, path)
    require_exact_fields(section, expected_fields, path)
    for field, expected in literal_values.items():
        require_semantic_value(section[field], expected, f"{path}.{field}")
    for field in true_fields:
        require_semantic_value(section[field], True, f"{path}.{field}")
    for field in false_fields:
        require_semantic_value(section[field], False, f"{path}.{field}")
    return section


def validate_threat_model(actual: Any) -> None:
    path = "contract.threat_model"
    section = require_object(actual, path)
    require_exact_fields(
        section,
        {
            "all_controls_are_future_requirements_not_current_implementation",
            "unimplemented_control_verdict",
            "required_threats",
        },
        path,
    )
    require_semantic_value(
        section["all_controls_are_future_requirements_not_current_implementation"],
        True,
        f"{path}.all_controls_are_future_requirements_not_current_implementation",
    )
    require_semantic_value(
        section["unimplemented_control_verdict"],
        "REJECTED_FAIL_CLOSED",
        f"{path}.unimplemented_control_verdict",
    )
    threats = require_list(section["required_threats"], f"{path}.required_threats")
    if len(threats) != len(EXPECTED_THREATS):
        raise InputError(
            f"{path}.required_threats length must remain preregistered as "
            f"{len(EXPECTED_THREATS)}"
        )
    for index, (threat, control) in enumerate(EXPECTED_THREATS):
        require_policy_section(
            threats[index],
            f"{path}.required_threats[{index}]",
            literals={
                "threat": threat,
                "required_control": control,
                "current_status": "unimplemented_fail_closed",
            },
        )


def validate_contract_semantics(value: dict[str, Any]) -> dict[str, Any]:
    """Validate policy semantics independently of the public raw-byte pin."""

    reject_raw_fields(value, "contract")
    contract = require_object(value, "contract")
    require_exact_fields(
        contract,
        {
            "schema",
            "contract_id",
            "stage",
            "predecessor",
            "transitive_bindings",
            "scope",
            "frozen_experiment_question",
            "frozen_corpus_profile",
            "future_candidate_artifact_lock",
            "future_access_and_blinding",
            "future_execution_sandbox",
            "future_determinism_and_state_isolation",
            "future_run_lifecycle",
            "future_decision_rule",
            "future_receipts_and_redaction",
            "human_audit_policy",
            "threat_model",
            "state_machine",
            "boundaries",
        },
        "contract",
    )
    require_semantic_value(contract["schema"], CONTRACT_SCHEMA, "contract.schema")
    require_semantic_value(contract["contract_id"], CONTRACT_ID, "contract.contract_id")
    require_semantic_value(
        contract["stage"],
        "g1_4_candidate_protocol_preregistration_design_only",
        "contract.stage",
    )
    require_policy_section(
        contract["predecessor"],
        "contract.predecessor",
        literals={
            "stage": "g1_authenticated_freeze_authority_adapter_synthetic_isolated_lab_implementation_gate_only",
            "commit": PREDECESSOR_COMMIT,
            "contract_id": "engram_g1_authenticated_freeze_authority_adapter_isolated_lab_20260718",
            "implementation_version": "engram_g1_authenticated_freeze_authority_adapter_isolated_lab_v0",
            "contract_sha256": PREDECESSOR_CONTRACT_SHA256,
            "implementation_sha256": PREDECESSOR_IMPLEMENTATION_SHA256,
            "checker_sha256": PREDECESSOR_CHECKER_SHA256,
            "shell_entrypoint_sha256": PREDECESSOR_SHELL_SHA256,
        },
        true_fields=("synthetic_only", "immutable"),
        false_fields=("production_authority",),
    )
    require_policy_section(
        contract["transitive_bindings"],
        "contract.transitive_bindings",
        literals={
            "adapter_preregistration_commit": "632918db75f65030d3ac15bc991b51a9c938cba6",
            "adapter_preregistration_contract_sha256": ADAPTER_PREREGISTRATION_CONTRACT_SHA256,
            "adapter_preregistration_validator_sha256": ADAPTER_PREREGISTRATION_VALIDATOR_SHA256,
            "adapter_preregistration_checker_sha256": ADAPTER_PREREGISTRATION_CHECKER_SHA256,
            "g1_3_commit": "7062869196d1a3ff8bb72572a39700e65130cde4",
            "g1_3_contract_sha256": G1_3_CONTRACT_SHA256,
            "g1_3_validator_sha256": G1_3_VALIDATOR_SHA256,
            "g1_3_checker_sha256": G1_3_CHECKER_SHA256,
        },
    )
    require_policy_section(
        contract["scope"],
        "contract.scope",
        literals={
            "artifact_kind": "public_design_contract_only",
            "permitted_output": "deterministic_public_design_receipt_no_authority",
            "only_permitted_successor": "separate_public_synthetic_g1_4_protocol_harness_implementation_gate",
        },
        false_fields=(
            "loads_private_manifest_fit_development_or_sealed_material",
            "loads_real_freeze_capability",
            "loads_candidate_source_or_configuration",
            "implements_candidate",
            "implements_protocol_runner",
            "implements_sandbox",
            "executes_experiment",
            "registers_mcp_or_runtime_surface",
            "touches_live_store_or_retrieval",
            "observes_real_evidence_or_results",
            "opens_candidate_implementation",
            "opens_private_data_access",
            "opens_g1_4_execution",
        ),
    )
    require_policy_section(
        contract["frozen_experiment_question"],
        "contract.frozen_experiment_question",
        literals={
            "question": "can_clustered_reorganization_reduce_unrelated_target_intrusion_without_materially_degrading_exact_or_related_retrieval",
            "candidate_arm": "clustered_reorganization",
            "comparator_arms_in_order": ["stable_control", "density_only"],
            "mechanism_falsifier_arms_in_order": [
                "mechanism_off",
                "cluster_shuffled",
            ],
            "retrieval_modes_in_order": ["fts", "hybrid", "semantic"],
            "top_k": 10,
            "decisive_unit": "paired_episode_group",
            "decisive_partition": "sealed",
            "primary_stratum": "overgeneralization_gap",
        },
        true_fields=(
            "rates_are_diagnostics_not_decision_authority",
            "population_neuroscience_product_or_runtime_claims_forbidden",
        ),
        false_fields=("fit_development_or_sealed_results_may_be_pooled",),
    )
    require_policy_section(
        contract["frozen_corpus_profile"],
        "contract.frozen_corpus_profile",
        literals={
            "total_groups": 30,
            "fit_groups": 12,
            "development_groups": 8,
            "sealed_groups": 10,
            "probes_per_group": 3,
            "probe_classes_in_order": ["exact", "related", "unrelated"],
            "minimum_overgeneralization_gap_groups": 15,
            "minimum_no_relevant_gap_groups": 9,
            "exact_ordinary_retrieval_gap_groups": 3,
            "minimum_sealed_primary_groups": 5,
            "minimum_application_families": 4,
            "maximum_groups_per_application_family": 10,
            "admitted_g0_incident_partition": "fit_only",
        },
        true_fields=("group_split_is_indivisible",),
        false_fields=(
            "candidate_may_change_group_membership_or_partition",
            "implemented_by_this_gate",
        ),
    )
    require_policy_section(
        contract["future_candidate_artifact_lock"],
        "contract.future_candidate_artifact_lock",
        literals={
            "two_phase_lock_profile": "development_lock_then_final_sealed_lock_v1",
            "maximum_reviewer_mediated_development_feedback_rounds": 2,
        },
        true_fields=(
            "development_lock_required_before_development_feedback",
            "final_lock_required_before_any_sealed_access",
            "final_lock_binds_source_tree_sha256",
            "final_lock_binds_configuration_sha256",
            "final_lock_binds_dependency_lock_sha256",
            "final_lock_binds_toolchain_and_build_flags_sha256",
            "final_lock_binds_feature_flags_and_model_assets_sha256",
            "final_lock_binds_environment_allowlist_sha256",
            "final_lock_binds_sandbox_profile_sha256",
            "final_lock_binds_output_schema_sha256",
            "final_lock_binds_resource_budget_sha256",
            "final_lock_binds_protocol_contract_and_runner_version",
            "post_final_lock_source_config_dependency_or_policy_change_forbidden",
            "candidate_self_approval_forbidden",
        ),
        false_fields=("implemented_by_this_gate",),
    )
    require_policy_section(
        contract["future_access_and_blinding"],
        "contract.future_access_and_blinding",
        literals={
            "development_feedback_profile": "reviewer_mediated_predeclared_aggregate_only",
            "probe_delivery_profile": "bounded_evaluator_pipe_without_manifest_path_or_group_identifier",
        },
        true_fields=(
            "candidate_author_may_access_fit",
            "development_feedback_round_limit_enforced",
            "sealed_custodian_alone_may_open_sealed_material",
            "arm_mapping_committed_before_execution",
            "scorer_receives_opaque_arm_ids_until_decision_frozen",
            "arm_mapping_reveal_only_after_append_only_decision_receipt",
            "candidate_process_has_no_private_corpus_path_access",
        ),
        false_fields=(
            "candidate_author_may_access_raw_development",
            "candidate_author_may_access_raw_sealed",
            "candidate_author_may_access_partition_membership_outside_fit",
            "candidate_or_runner_may_author_expected_targets",
            "candidate_or_runner_may_score_own_outputs",
            "implemented_by_this_gate",
        ),
    )
    require_policy_section(
        contract["future_execution_sandbox"],
        "contract.future_execution_sandbox",
        literals={
            "profile": "nono_landlock_or_seatbelt_deny_by_default_offline_runner_v1"
        },
        true_fields=(
            "operating_system_policy_selected_before_real_enablement",
            "network_access_denied",
            "subprocess_spawn_denied",
            "dynamic_plugin_loading_denied",
            "environment_is_explicit_allowlist_only",
            "candidate_code_and_dependencies_read_only",
            "ephemeral_scratch_is_only_writable_filesystem",
            "repository_git_metadata_and_live_store_not_visible",
            "private_manifest_and_partition_paths_not_visible",
            "wall_clock_external_entropy_and_unregistered_randomness_denied",
            "stdout_stderr_and_free_form_logs_not_released_to_candidate_author",
            "output_schema_is_fixed_bounded_and_non_free_form",
            "fixed_output_cardinality_and_size_required",
            "cpu_memory_wall_time_file_count_and_byte_ceilings_equal_across_arms",
            "sandbox_profile_and_mount_set_equal_across_arms",
            "sandbox_escape_or_policy_drift_invalidates_run",
        ),
        false_fields=("implemented_by_this_gate",),
    )
    require_policy_section(
        contract["future_determinism_and_state_isolation"],
        "contract.future_determinism_and_state_isolation",
        true_fields=(
            "registered_seed_schedule_required",
            "seed_schedule_hidden_from_candidate_author_for_sealed_run",
            "two_identical_fit_qualification_replays_required",
            "all_ranked_outputs_must_match_across_qualification_replays",
            "fresh_process_per_arm_and_episode_group_required",
            "cross_group_cross_arm_and_cross_partition_state_forbidden",
            "ephemeral_scratch_destroyed_after_each_invocation",
            "arm_execution_order_precommitted_and_blinded",
            "cache_warmth_and_resource_budget_normalization_required",
            "nondeterminism_or_hidden_state_fails_closed",
        ),
        false_fields=("implemented_by_this_gate",),
    )
    require_policy_section(
        contract["future_run_lifecycle"],
        "contract.future_run_lifecycle",
        true_fields=(
            "real_authenticated_freeze_capability_required",
            "synthetic_predecessor_capability_is_not_real_authority",
            "capability_must_bind_repository_scope_manifest_protocol_runner_and_final_candidate_lock",
            "capability_consumed_atomically_before_private_run_plan_open",
            "append_only_run_plan_receipt_required",
            "append_only_per_invocation_receipts_required",
            "append_only_decision_receipt_required",
            "sealed_execution_is_one_shot",
            "selective_retry_or_partial_rerun_forbidden",
            "infrastructure_fault_invalidates_entire_sealed_run",
            "sealed_rerun_requires_new_protocol_revision_fresh_capability_and_manual_safety_audit",
            "partial_or_intermediate_sealed_results_not_released",
            "decision_receipt_frozen_before_arm_mapping_reveal",
            "live_store_write_retrieval_mutation_and_runtime_promotion_forbidden",
        ),
        false_fields=("implemented_by_this_gate",),
    )
    require_policy_section(
        contract["future_decision_rule"],
        "contract.future_decision_rule",
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
            "missing_timeout_crash_or_schema_invalid_invocation_is_failure",
            "all_guards_apply_simultaneously",
            "fit_and_development_cannot_decide_final_verdict",
            "post_observation_threshold_arm_metric_or_retry_change_forbidden",
        ),
        false_fields=("implemented_by_this_gate",),
    )
    require_policy_section(
        contract["future_receipts_and_redaction"],
        "contract.future_receipts_and_redaction",
        literals={
            "schemas_in_order": [
                "agent_bridge.engram_g1_4_candidate_artifact_lock_receipt.v0",
                "agent_bridge.engram_g1_4_blinded_run_plan_receipt.v0",
                "agent_bridge.engram_g1_4_invocation_receipt.v0",
                "agent_bridge.engram_g1_4_decision_receipt.v0",
            ]
        },
        true_fields=(
            "receipts_bind_contract_candidate_runner_sandbox_resources_and_predecessor",
            "receipts_bind_monotonic_sequence_nonce_and_trusted_time",
            "receipts_are_append_only_and_hash_chained",
            "private_and_public_digest_namespaces_disjoint",
            "low_entropy_private_values_require_salted_commitments",
            "aggregate_counts_below_disclosure_floor_are_suppressed",
            "result_release_requires_redaction_review",
        ),
        false_fields=(
            "public_receipt_contains_raw_query_target_manifest_group_family_partition_or_identity",
            "public_receipt_contains_candidate_authored_free_form_text",
            "implemented_by_this_gate",
        ),
    )
    require_policy_section(
        contract["human_audit_policy"],
        "contract.human_audit_policy",
        literals={"manual_safety_audit_required_for": EXPECTED_MANUAL_AUDIT_EVENTS},
        true_fields=(
            "reversible_failure_requires_automatic_rollback",
            "rollback_failure_requires_durable_lesson",
        ),
        false_fields=(
            "routine_public_contract_validation_requires_human_approval",
            "unchanged_public_synthetic_harness_validation_requires_per_run_human_approval",
            "fail_closed_denial_requires_human_approval",
            "manual_safety_audit_is_a_per_run_gate",
            "manual_audit_outcome_may_be_inferred_by_structural_validator",
        ),
    )
    validate_threat_model(contract["threat_model"])
    require_policy_section(
        contract["state_machine"],
        "contract.state_machine",
        literals={
            "current_state": "G1_4_CANDIDATE_PROTOCOL_PREREGISTERED_DESIGN_ONLY",
            "representable_current_states": [
                "G1_4_CANDIDATE_PROTOCOL_PREREGISTERED_DESIGN_ONLY",
                "REJECTED_FAIL_CLOSED",
            ],
        },
        true_fields=("design_preregistration_present",),
        false_fields=(
            "synthetic_harness_implementation_present",
            "candidate_implementation_present",
            "real_freeze_capability_present",
            "private_run_plan_present",
            "sealed_run_present",
            "positive_execution_or_data_authority_state_representable",
        ),
    )
    require_policy_section(
        contract["boundaries"],
        "contract.boundaries",
        true_fields=("g1_4_design_preregistered",),
        false_fields=(
            "observes_real_role_corpus_candidate_or_result_evidence",
            "authenticated_freeze_authority_verified_for_real_use",
            "ready_for_public_synthetic_harness_implementation_review",
            "candidate_manifest_access_authority",
            "candidate_fit_access_authority",
            "candidate_development_access_authority",
            "candidate_sealed_access_authority",
            "candidate_implementation_authority",
            "protocol_runner_implementation_authority",
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


def validate_public_predecessor_artifacts(repo_root: Path) -> None:
    expected = {
        repo_root
        / "scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_adapter_isolated_lab_contract_v0.json": PREDECESSOR_CONTRACT_SHA256,
        repo_root
        / "scripts/eval/engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py": PREDECESSOR_IMPLEMENTATION_SHA256,
        repo_root
        / "scripts/eval/check_engram_g1_authenticated_freeze_authority_adapter_isolated_lab.py": PREDECESSOR_CHECKER_SHA256,
        repo_root
        / "scripts/check-engram-g1-authenticated-freeze-authority-adapter-isolated-lab.sh": PREDECESSOR_SHELL_SHA256,
        repo_root
        / "scripts/eval/fixtures/engram_g1_authenticated_freeze_authority_adapter_preregistration_contract_v0.json": ADAPTER_PREREGISTRATION_CONTRACT_SHA256,
        repo_root
        / "scripts/eval/engram_g1_authenticated_freeze_authority_adapter_preregistration.py": ADAPTER_PREREGISTRATION_VALIDATOR_SHA256,
        repo_root
        / "scripts/check-engram-g1-authenticated-freeze-authority-adapter-preregistration.sh": ADAPTER_PREREGISTRATION_CHECKER_SHA256,
        repo_root
        / "scripts/eval/fixtures/engram_g1_corpus_freeze_review_contract_v1.json": G1_3_CONTRACT_SHA256,
        repo_root
        / "scripts/eval/engram_g1_corpus_freeze_review.py": G1_3_VALIDATOR_SHA256,
        repo_root
        / "scripts/check-engram-g1-corpus-freeze-review.sh": G1_3_CHECKER_SHA256,
    }
    for path, digest in expected.items():
        try:
            actual = sha256_bytes(read_stable_bounded_file(path))
        except OSError as exc:
            raise InputError(
                f"failed to read public predecessor artifact: {exc}"
            ) from exc
        if actual != digest:
            raise InputError(f"public predecessor artifact drifted: {path.name}")


def validate_contract(value: dict[str, Any], raw: bytes) -> dict[str, Any]:
    if sha256_bytes(raw) != CONTRACT_SHA256:
        raise InputError("G1.4 candidate-protocol contract bytes do not match v0")
    contract = validate_contract_semantics(value)
    validate_public_predecessor_artifacts(Path(__file__).resolve().parents[2])
    return contract


def build_receipt(contract: dict[str, Any]) -> dict[str, Any]:
    question = contract["frozen_experiment_question"]
    artifact = contract["future_candidate_artifact_lock"]
    sandbox = contract["future_execution_sandbox"]
    lifecycle = contract["future_run_lifecycle"]
    decision = contract["future_decision_rule"]
    audit = contract["human_audit_policy"]
    boundaries = contract["boundaries"]
    return {
        "schema": RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": CONTRACT_SHA256,
        "validator_sha256": VALIDATOR_SHA256,
        "predecessor_commit": PREDECESSOR_COMMIT,
        "predecessor_contract_sha256": PREDECESSOR_CONTRACT_SHA256,
        "predecessor_implementation_sha256": PREDECESSOR_IMPLEMENTATION_SHA256,
        "predecessor_checker_sha256": PREDECESSOR_CHECKER_SHA256,
        "predecessor_shell_entrypoint_sha256": PREDECESSOR_SHELL_SHA256,
        "contract_verdict": (
            "G1_4_CANDIDATE_PROTOCOL_PREREGISTERED_DESIGN_ONLY_FAIL_CLOSED"
        ),
        "public_design_contract_only": True,
        "experiment_question": question["question"],
        "candidate_arm": question["candidate_arm"],
        "comparator_arm_count": len(question["comparator_arms_in_order"]),
        "mechanism_falsifier_arm_count": len(
            question["mechanism_falsifier_arms_in_order"]
        ),
        "retrieval_mode_count": len(question["retrieval_modes_in_order"]),
        "top_k": question["top_k"],
        "maximum_development_feedback_rounds": artifact[
            "maximum_reviewer_mediated_development_feedback_rounds"
        ],
        "sandbox_profile": sandbox["profile"],
        "network_access_denied_in_future_runner": sandbox["network_access_denied"],
        "sealed_execution_is_one_shot": lifecycle["sealed_execution_is_one_shot"],
        "selective_retry_forbidden": lifecycle[
            "selective_retry_or_partial_rerun_forbidden"
        ],
        "minimum_paired_primary_repairs_vs_each_comparator": decision[
            "candidate_minimum_paired_primary_repairs_vs_each_comparator"
        ],
        "required_threat_count": len(contract["threat_model"]["required_threats"]),
        "manual_audit_event_count": len(audit["manual_safety_audit_required_for"]),
        "routine_public_validation_requires_human_approval": audit[
            "routine_public_contract_validation_requires_human_approval"
        ],
        "unchanged_public_synthetic_validation_requires_per_run_human_approval": audit[
            "unchanged_public_synthetic_harness_validation_requires_per_run_human_approval"
        ],
        "reversible_failure_requires_automatic_rollback": audit[
            "reversible_failure_requires_automatic_rollback"
        ],
        "rollback_failure_requires_durable_lesson": audit[
            "rollback_failure_requires_durable_lesson"
        ],
        "current_state": contract["state_machine"]["current_state"],
        "validator_implements_sandbox": False,
        "validator_implements_protocol_runner": False,
        "validator_executes_experiment": False,
        **boundaries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    contract_parser = subparsers.add_parser("validate-contract")
    contract_parser.add_argument("--contract", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        value, raw = read_json(args.contract)
        contract = validate_contract(value, raw)
        print(json.dumps(build_receipt(contract), sort_keys=True, indent=2))
        return 0
    except InputError as exc:
        print(
            f"engram G1.4 candidate protocol preregistration rejected: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
