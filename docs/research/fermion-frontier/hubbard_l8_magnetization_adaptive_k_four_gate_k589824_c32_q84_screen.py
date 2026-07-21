#!/usr/bin/env python3
"""Source-pinned, diagnostic-only M K=589824/C=32 q84 screen.

Execution always starts at checkpoint one through a fresh same-byte copy of the
exact four-gate control-flow parent.  The K573440/C32 q84 route is an exact
post-replay reference only: it is never compiled, executed, or used for state
resume.  This C32 route replaces the predecessor's never-selected, 84/84
infeasible K=65536 row with K=589824.  It preserves the selected-K and physical
state trajectory through q83, but deliberately does not claim candidate-row
prefix identity because predecessor indices 1..31 become indices 0..30.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple


SELF_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k589824_c32_q84_screen.py"
)
CONTROL_FLOW_PARENT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k589824.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_k573440_c32_q84_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_k573440_c32_q84_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k589824_c32_q84_transcript.json"
)

EXPECTED_CONTROL_FLOW_PARENT_SHA256 = (
    "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614"
)
EXPECTED_V6_BASELINE_CONFIGURATION_SHA256 = (
    "3e7f9ff0546addfaa23f351f3569b102d0c3ebb578dbc4873b042bac21070af2"
)
EXPECTED_V2_ARITHMETIC_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "9eded142673fcb548d585d0071f5c550970c48c24d50c5ef1fc43b6257b1775d"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "6906e56af531063800742e95304682f9bcd123d0086806d59691e0b099772b1a"
)
EXPECTED_KERNEL_SOURCE_LAYERS_SHA256 = (
    "5cff48004d16935c4f5c368b509f21cbe6263ba75452b561c3a22a4afc9a2ad9"
)
EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256 = (
    "2c6648cf4336cec395ef9bc3a1774a17af4933c5b062b77563b680ca69196335"
)
EXPECTED_KERNEL_CROSS_ROUTE_REFERENCE_SHA256 = (
    "453a979f2fef788d5052bdbc66051757b4f1913a7d571c3b3b7aa41dada62c20"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256 = (
    "c644dfeaf2a0b27be40403715aec8711818ae11ff575b230339af745f0a56ff1"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256 = (
    "fb6d6c241ab7ee2f535aa2f1cdff38a5e8f47bab1035ba29249332ca2d4f3f39"
)
EXPECTED_CROSS_ROUTE_KERNEL_SHA256 = (
    "7758cc1bf0cd71545a7135c92848059dc69e5d934c79f1d8c60ea61019459254"
)
EXPECTED_CROSS_ROUTE_KERNEL_MANIFEST_SHA256 = (
    "36694fa3e72ad78fde91826c6a1ae81ae5a7f07e51db2d008769d97eabce5b1a"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "1246023edea93e89db2ec0071c51c1cb15f60b8a928b934aad08cebb593240b2"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "f379f6a72caba82c0f1aca599ef9872666cfed8b4ea72003194438ed01806f48"
)
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "35479fdf0715400b6b022ad5a538edc5eb21ed3f08b25896555496763f6ba26d"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "cb4e935c2e8bd0458d7164701d79251b9a5d5f3d80f949ff8f8953ce561b6cc6"
)
EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256 = (
    "1f2587a16f11ab3b6eb02aedcaf661bda5ba3acfc1afffe1cc06e03c79cc76c7"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "8858e3d76caf4c3fbb6d9e589544e9fbd14d6871cd8ca50a44ed7c96f09f8596"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "54b79fb46252b6457fb2e428cf5fae87969e96d1e88c42519a48bb588081f563"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_PREDECESSOR_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "magnetization"
BASE_PARENT_HORIZON = 80
EXTENDED_HORIZON = 84
K65536 = 65_536
K540672 = 540_672
K557056 = 557_056
K573440 = 573_440
K589824 = 589_824

V6_M_CANDIDATES = tuple(range(65_536, 524_288 + 1, 16_384))
PREDECESSOR_M_CANDIDATES = V6_M_CANDIDATES + (K540672, K557056, K573440)
M_CANDIDATES = PREDECESSOR_M_CANDIDATES[1:] + (K589824,)
EXPECTED_V6_M_CANDIDATE_SHA256 = (
    "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
)
EXPECTED_V6_D_CANDIDATE_SHA256 = (
    "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
)
EXPECTED_PREDECESSOR_CANDIDATE_SHA256 = (
    "b46d0b11cbb16260d7d3b76b4a42d0013c74dae767e39a5b11bf50d8fdddb428"
)
EXPECTED_CANDIDATE_SHA256 = (
    "94c062a2f562b7ce9e095ce9585ac4087b7bfef2af492b45762ca5d732ae9b80"
)
EXPECTED_Q1_Q83_INDEX_INVARIANT_COMMON_SHA256 = (
    "04c22b5646ee01020209442b6d81856bad68db84b0dcd9f865da523a56c543d6"
)
EXPECTED_Q1_Q83_NORMALIZED_ROWS_SHA256 = (
    "0a6216b02eac9e36e2ef6290a751ae0288f6aa99f74f8b569a3f1a208ee2f796"
)
EXPECTED_Q84_SHARED_PROPAGATION_SHA256 = (
    "ab9b8824bd930b9fc8a07e9b4cfdddaa9b631fe46b7a2b739b2d722bb73730df"
)
EXPECTED_Q84_NORMALIZED_PREDECESSOR_ROWS_SHA256 = (
    "84a1df7e0648d2f4f2f18bc9fbbc6704c64e7bfaa0b659909add2e8b97f25a29"
)
EXPECTED_REMOVED_K65536_ROW_SET_SHA256 = (
    "01eaffaa790187714ae2a81acd0bea6f779df99c4dfc6b0dc9b1693e13b98d96"
)
EXPECTED_Q84_SUCCESS_HISTORY_SHA256 = (
    "ba0a38f3cdf13114aaa7e00f2889bc221ad7afa1b42d038cc4a4ed710a21df5c"
)
EXPECTED_SELECTED_INDEX_HISTORY_SHA256 = (
    "b7330885358789963e7d36b8b0c9beee32fd630aba6df3726557a2f640e9583f"
)

EXPECTED_V6_POLICY_CAPS = {
    "max_candidate_K": 524_288,
    "max_output_terms_if_successful": 524_288,
    "max_single_expansion_terms": 786_432,
    "max_digest_terms": 786_432,
    "max_term_gate_visits": 536_870_912,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}
EXPECTED_V6_POLICY_CAPS_SHA256 = (
    "32a0619246b07e67e6d4f237f808fc5c5163c1149c50230bf962ab1851a6f25a"
)
EXPECTED_PREDECESSOR_POLICY_CAPS = {
    **EXPECTED_V6_POLICY_CAPS,
    "max_candidate_K": K573440,
    "max_output_terms_if_successful": K573440,
}
POLICY_CAPS_BASE = {
    **EXPECTED_PREDECESSOR_POLICY_CAPS,
    "max_candidate_K": K589824,
    "max_output_terms_if_successful": K589824,
}

EXPECTED_V2_KERNEL_CAPABILITY_LIMITS = {
    "max_candidate_count": 32,
    "max_digest_terms": 1_048_576,
    "max_expansion_coefficient_tick_bits": 192,
    "max_product_bits": 384,
    "max_retained_K": 524_288,
    "max_single_expansion_terms": 1_048_576,
    "max_source_bytes": 196_608,
    "max_suffix_accumulator_bits": 224,
    "max_term_gate_visits": 1_000_000_000,
    "max_trigonometric_tick_bits": 66,
}
EXPECTED_PREDECESSOR_KERNEL_CAPABILITY_LIMITS = {
    **EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
    "max_retained_K": K573440,
}
EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS = {
    **EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
    "max_retained_K": K589824,
}
EXPECTED_CROSS_ROUTE_KERNEL_CAPABILITY_LIMITS = {
    **EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
    "max_candidate_count": 34,
    "max_retained_K": K589824,
}
EXPECTED_PARENT_EXECUTION_COMPONENTS = (
    {
        "relative_path": CONTROL_FLOW_PARENT_NAME,
        "role": "four_gate_screen_execution_source",
        "sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
    },
    {
        "relative_path": "hubbard_l8_adaptive_k_v2_design_probe.py",
        "role": "v2_helper_provider_not_run_entrypoint",
        "sha256": "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3",
    },
    {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "role": "v6_candidates_and_caps_reference_only",
        "sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
    },
    {
        "relative_path": V2_ARITHMETIC_NAME,
        "role": "v2_arithmetic_kernel",
        "sha256": EXPECTED_V2_ARITHMETIC_SHA256,
    },
    {
        "relative_path": "hubbard_l8_observable_interval_step_checker.py",
        "role": "root_sequence_and_trigonometry_source",
        "sha256": "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_checker.py",
        "role": "magnetization_boundary_parent_source",
        "sha256": "4e471b6f22838b2e9621adeeb757e7fa8277e3d8c4985eee392b182530c0c717",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_contract.json",
        "role": "magnetization_boundary_parent_source",
        "sha256": "fb1d5e82819d39f217a8c1c7f4979a689f4d46b8d691a8f464cad9012c197387",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_template.json",
        "role": "magnetization_boundary_parent_source",
        "sha256": "b68544091be417eed5310d8579eb8dc4d1a51e1863ed1fb7a8cbfa1fc6004eb6",
    },
    {
        "relative_path": "hubbard_l8_interval_checkpoints/staggered_magnetization_boundary_003.b85",
        "role": "magnetization_encoded_input_boundary",
        "sha256": "91aecef5a3b79279e394c8995072d19565f4898e0ba29ddd7685ea9e535d9c84",
    },
)

EXPECTED_PARENT_SOURCE_CUSTODY = {
    "hubbard_l8_adaptive_k_v2_design_probe.py": (
        "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
    ),
    V6_BASELINE_CONFIGURATION_NAME: EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
    V2_ARITHMETIC_NAME: EXPECTED_V2_ARITHMETIC_SHA256,
    "hubbard_l8_observable_interval_step_checker.py": (
        "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a"
    ),
    "hubbard_l8_magnetization_interval_step3_checker.py": (
        "4e471b6f22838b2e9621adeeb757e7fa8277e3d8c4985eee392b182530c0c717"
    ),
    "hubbard_l8_magnetization_interval_step3_contract.json": (
        "fb1d5e82819d39f217a8c1c7f4979a689f4d46b8d691a8f464cad9012c197387"
    ),
    "hubbard_l8_magnetization_interval_step3_template.json": (
        "b68544091be417eed5310d8579eb8dc4d1a51e1863ed1fb7a8cbfa1fc6004eb6"
    ),
}

CANDIDATE_RECORD_KEYS = frozenset({
    "candidate_index",
    "configured_K",
    "effective_retained_count",
    "dropped_term_count",
    "drop_ticks",
    "E_after_if_selected_ticks",
    "feasible_under_current_prefix_cap",
})
FAILURE_ONLY_RECORD_KEYS = frozenset({
    "minimum_effective_K_to_meet_prefix",
    "required_K_excess_over_policy_maximum",
    "maximum_candidate_drop_excess_over_slack_ticks",
})
SUCCESS_ONLY_RECORD_KEYS = frozenset({
    "selected_effective_retained_count",
    "selected_dropped_term_count",
    "selected_drop_ticks",
    "selected_dropped_terms_sha256",
    "retained_expansion_count",
    "retained_expansion_sha256",
    "minimum_retained_abs_upper_ticks",
    "maximum_dropped_abs_upper_ticks",
    "E_after_ticks",
})
FAILURE_RECORD_KEYS = frozenset({
    "E_before_ticks",
    "batch_in_stage",
    "budget_prefix_cap_ticks",
    "candidate_records",
    "checkpoint_index_zero_based",
    "checkpoint_number_one_based",
    "gate_batch_sha256",
    "gate_occurrence_first_zero_based",
    "gate_occurrence_last_zero_based",
    "input_expansion_count",
    "input_expansion_sha256",
    "maximum_candidate_drop_excess_over_slack_ticks",
    "maximum_expansion_coefficient_tick_bits",
    "maximum_product_bits",
    "minimum_effective_K_to_meet_prefix",
    "peak_live_terms_cumulative",
    "peak_live_terms_this_checkpoint",
    "prefix_slack_before_selection_ticks",
    "pretruncation_expansion_count",
    "pretruncation_expansion_sha256",
    "ranked_suffix_sha256",
    "required_K_excess_over_policy_maximum",
    "rounding_cumulative_scaled_ticks_squared",
    "rounding_increment_scaled_ticks_squared",
    "selected_K",
    "selected_candidate_index",
    "stage_group",
    "stage_index",
    "status",
    "term_gate_visits_cumulative",
    "term_gate_visits_increment",
})
SUCCESS_RECORD_KEYS = (
    FAILURE_RECORD_KEYS - FAILURE_ONLY_RECORD_KEYS | SUCCESS_ONLY_RECORD_KEYS
)
EXPECTED_PARENT_RESULT_KEYS = frozenset({
    "schema_version",
    "transcript_fingerprint",
    "status",
    "screen_terminal_condition",
    "observable_id",
    "input_step_index",
    "attempted_child_step_index",
    "screen_source_sha256",
    "same_byte_self_execution",
    "v2_helper_source_sha256",
    "v2_helper_compiled_from_verified_bytes",
    "v2_helper_module_isolated",
    "v2_run_entrypoint_called",
    "v6_configuration_source_sha256",
    "v6_configuration_compiled_from_verified_bytes",
    "v6_configuration_module_isolated",
    "v6_execution_invoked",
    "v6_same_byte_execution_parent",
    "control_flow_owned_by_screen",
    "screen_execution_components",
    "screen_execution_components_sha256",
    "configuration_reference",
    "configuration_reference_sha256",
    "checkpoint_transform",
    "checkpoint_transform_sha256",
    "arithmetic_kernel_commit",
    "source_custody",
    "parent_expected_witness_sha256",
    "input_boundary_custody",
    "input_cumulative_drop_ticks",
    "maximum_cumulative_drop_ticks",
    "remaining_mapped_steps_including_attempt",
    "future_checkpoint_denominator",
    "prefix_cap_formula",
    "candidate_K_values",
    "candidate_K_values_sha256",
    "candidate_policy_precommitted_at_probe_time",
    "selection_rule",
    "single_propagation_and_single_ranking_per_checkpoint",
    "sequence",
    "screen_horizon_checkpoint_count",
    "horizon_checkpoint_attempted",
    "horizon_reached_with_committed_checkpoint",
    "kernel_capability_limits",
    "proposed_policy_caps",
    "root_globals_before",
    "root_globals_after",
    "root_globals_unchanged",
    "attempted_checkpoint_count",
    "completed_checkpoint_count",
    "failure_checkpoint_included",
    "selected_K_history",
    "selected_K_history_sha256",
    "records",
    "records_sha256",
    "failure_record_sha256",
    "last_committed_cumulative_drop_ticks",
    "observed_peak_single_expansion_terms",
    "observed_term_gate_visits_including_terminal_attempt",
    "observed_maximum_expansion_coefficient_tick_bits",
    "observed_maximum_product_bits",
    "observed_rounding_cumulative_scaled_ticks_squared",
    "child_boundary_committed",
    "positive_artifact_generated",
    "runtime_RSS_host_timestamp_and_float_fields_excluded",
})
RELABELLED_ADDED_TOP_LEVEL_KEYS = frozenset({
    "arithmetic_kernel_commit_role",
    "configuration_override",
    "configuration_override_sha256",
    "control_flow_owned_by_verified_parent",
    "control_flow_parent_compiled_from_verified_bytes",
    "control_flow_parent_module_isolated",
    "control_flow_parent_private_entrypoint_called",
    "control_flow_parent_relative_path",
    "control_flow_parent_runtime_horizon_override_applied",
    "control_flow_parent_same_byte_execution",
    "control_flow_parent_source_sha256",
    "diagnostic_candidate_ladder_precommitted_before_replay",
    "diagnostic_horizon_precommitted_before_replay",
    "kernel_capability_override",
    "kernel_capability_override_sha256",
    "kernel_capability_wrapper_compiled_from_verified_bytes",
    "kernel_capability_wrapper_module_isolated",
    "kernel_capability_wrapper_relative_path",
    "kernel_capability_wrapper_source_sha256",
    "parent_horizon_override",
    "parent_horizon_override_sha256",
    "predecessor_handoff_validation",
    "predecessor_handoff_validation_sha256",
    "route_predecessor_reference",
    "route_predecessor_reference_sha256",
    "v2_arithmetic_compiled_from_verified_bytes",
    "v2_arithmetic_source_sha256",
    "v6_configuration_source_used_as_baseline_only",
    "v6_runtime_configuration_override_applied",
})
EXPECTED_RELABELLED_RESULT_KEYS = (
    EXPECTED_PARENT_RESULT_KEYS | RELABELLED_ADDED_TOP_LEVEL_KEYS
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def bounded_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"byte cap exceeded: {path.name}")
    return payload


def checked_repo_file(repo: Path, relative_path: str) -> Path:
    if type(relative_path) is not str or not relative_path:
        raise RuntimeError("relative path is not a nonempty string")
    repo = repo.resolve()
    path = (repo / relative_path).resolve()
    try:
        path.relative_to(repo)
    except ValueError as exc:
        raise RuntimeError("path escapes the repository") from exc
    return path


def compile_isolated(name: str, path: Path, payload: bytes) -> Any:
    if type(payload) is not bytes:
        raise RuntimeError("isolated module payload must be exact bytes")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def load_pinned_module(
    repo: Path,
    relative_path: str,
    expected_sha: str,
    module_name: str,
) -> Tuple[Any, bytes]:
    path = checked_repo_file(repo, relative_path)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != expected_sha:
        raise RuntimeError(f"source pin drift for {relative_path}: {observed}")
    return compile_isolated(module_name, path, payload), payload


def changed_mapping_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    return {
        key for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    }


def require_exact_keys(
    value: Any,
    expected: frozenset[str],
    label: str,
) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"{label} is not an exact dict")
    observed = frozenset(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise RuntimeError(
            f"{label} exact key-set drift: missing={missing}, extra={extra}"
        )


def require_exact_source_custody(
    value: Any,
    expected: Mapping[str, str],
    label: str,
) -> None:
    if type(value) is not dict:
        raise RuntimeError(f"{label} is not an exact dict")
    observed_keys = frozenset(value)
    expected_keys = frozenset(expected)
    missing = sorted(expected_keys - observed_keys)
    extra = sorted(observed_keys - expected_keys)
    wrong_hash = sorted(
        key
        for key in expected_keys & observed_keys
        if type(value[key]) is not str or value[key] != expected[key]
    )
    if missing or extra or wrong_hash:
        raise RuntimeError(
            f"{label} exact custody drift: missing={missing}, extra={extra}, "
            f"wrong_hash={wrong_hash}"
        )


def require_handoff_top_level_keys(result: Any) -> None:
    if type(result) is not dict:
        raise RuntimeError("M q84 result is not an exact dict")
    observed = frozenset(result)
    if observed not in {
        EXPECTED_PARENT_RESULT_KEYS,
        EXPECTED_RELABELLED_RESULT_KEYS,
    }:
        expected = (
            EXPECTED_RELABELLED_RESULT_KEYS
            if RELABELLED_ADDED_TOP_LEVEL_KEYS <= observed
            else EXPECTED_PARENT_RESULT_KEYS
        )
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise RuntimeError(
            "M q84 top-level exact key-set drift: "
            f"missing={missing}, extra={extra}"
        )


def validate_local_configuration() -> None:
    if len(V6_M_CANDIDATES) != 29:
        raise RuntimeError("v6 M candidate count drift")
    if len(PREDECESSOR_M_CANDIDATES) != 32 or len(M_CANDIDATES) != 32:
        raise RuntimeError("M route candidate count drift")
    if PREDECESSOR_M_CANDIDATES[0] != K65536:
        raise RuntimeError("M predecessor removable slot drift")
    if M_CANDIDATES != PREDECESSOR_M_CANDIDATES[1:] + (K589824,):
        raise RuntimeError("M K589824 route is not the exact C32 replacement")
    if K65536 in M_CANDIDATES:
        raise RuntimeError("M K65536 candidate was not removed")
    if any(type(value) is not int or value <= 0 for value in M_CANDIDATES):
        raise RuntimeError("M candidate value drift")
    if any(left >= right for left, right in zip(M_CANDIDATES, M_CANDIDATES[1:])):
        raise RuntimeError("M candidate order drift")
    if sha256(canonical_bytes(list(PREDECESSOR_M_CANDIDATES))) != (
        EXPECTED_PREDECESSOR_CANDIDATE_SHA256
    ):
        raise RuntimeError("M predecessor candidate digest drift")
    if sha256(canonical_bytes(list(M_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("M candidate digest drift")
    expected = {"max_candidate_K", "max_output_terms_if_successful"}
    if changed_mapping_keys(EXPECTED_V6_POLICY_CAPS, POLICY_CAPS_BASE) != expected:
        raise RuntimeError("direct v6 policy override changed a non-K field")
    if changed_mapping_keys(EXPECTED_PREDECESSOR_POLICY_CAPS, POLICY_CAPS_BASE) != expected:
        raise RuntimeError("route policy override changed a non-K field")
    if POLICY_CAPS_BASE["max_candidate_K"] != M_CANDIDATES[-1]:
        raise RuntimeError("policy maximum and M ladder maximum disagree")
    if BASE_PARENT_HORIZON != 80 or EXTENDED_HORIZON != 84:
        raise RuntimeError("M q84 horizon contract drift")


def load_control_flow_parent(repo: Path) -> Any:
    parent, _payload = load_pinned_module(
        repo,
        CONTROL_FLOW_PARENT_NAME,
        EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_control_flow_parent_for_m_k589824_c32_q84",
    )
    if parent.KERNEL_NAME != V2_ARITHMETIC_NAME:
        raise RuntimeError("control-flow parent v2 kernel path drift")
    if parent.EXPECTED_KERNEL_SHA256 != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError("control-flow parent v2 kernel pin drift")
    if parent.V6_CONFIGURATION_NAME != V6_BASELINE_CONFIGURATION_NAME:
        raise RuntimeError("control-flow parent v6 configuration path drift")
    if parent.EXPECTED_V6_CONFIGURATION_SHA256 != (
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256
    ):
        raise RuntimeError("control-flow parent v6 configuration pin drift")
    horizons = {
        mode: config["horizon_checkpoint_count"]
        for mode, config in parent.MODE_CONFIG.items()
    }
    if horizons != {MODE: BASE_PARENT_HORIZON, "double_occupancy": 66}:
        raise RuntimeError("control-flow parent baseline horizon drift")
    return parent


def load_configured_v6_baseline(repo: Path) -> Tuple[Any, Tuple[int, ...]]:
    configuration, _payload = load_pinned_module(
        repo,
        V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_configuration_for_m_k589824_c32_q84",
    )
    if configuration.POLICY_CAPS_BASE != EXPECTED_V6_POLICY_CAPS:
        raise RuntimeError("v6 baseline policy caps drift")
    if sha256(canonical_bytes(configuration.POLICY_CAPS_BASE)) != (
        EXPECTED_V6_POLICY_CAPS_SHA256
    ):
        raise RuntimeError("v6 baseline policy digest drift")
    baseline_m = tuple(configuration.MODE_CONFIG[MODE]["candidates"])
    baseline_d = tuple(configuration.MODE_CONFIG["double_occupancy"]["candidates"])
    if sha256(canonical_bytes(list(baseline_m))) != EXPECTED_V6_M_CANDIDATE_SHA256:
        raise RuntimeError("v6 baseline M candidate digest drift")
    if sha256(canonical_bytes(list(baseline_d))) != EXPECTED_V6_D_CANDIDATE_SHA256:
        raise RuntimeError("v6 baseline D candidate digest drift")
    if baseline_m != V6_M_CANDIDATES:
        raise RuntimeError("M direct construction from v6 drift")
    before_d = copy.deepcopy(configuration.MODE_CONFIG["double_occupancy"])
    runtime_config = copy.deepcopy(configuration.MODE_CONFIG)
    runtime_config[MODE]["candidates"] = tuple(M_CANDIDATES)
    configuration.MODE_CONFIG = runtime_config
    configuration.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    if configuration.MODE_CONFIG["double_occupancy"] != before_d:
        raise RuntimeError("configured v6 changed double occupancy")
    return configuration, baseline_m


def load_kernel_wrapper(repo: Path) -> Tuple[Any, str, Dict[str, Any]]:
    wrapper_path = checked_repo_file(repo, KERNEL_WRAPPER_NAME)
    wrapper_payload = bounded_bytes(wrapper_path, MAX_PINNED_SOURCE_BYTES)
    wrapper_sha = sha256(wrapper_payload)
    if wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError(f"source pin drift for {KERNEL_WRAPPER_NAME}: {wrapper_sha}")
    v2_path = checked_repo_file(repo, V2_ARITHMETIC_NAME)
    v2_payload = bounded_bytes(v2_path, MAX_PINNED_SOURCE_BYTES)
    if sha256(v2_payload) != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError("arithmetic-v2 source pin drift")
    wrapper = types.ModuleType("pinned_k589824_arithmetic_capability_wrapper")
    wrapper.__file__ = str(wrapper_path)
    wrapper.__package__ = ""
    wrapper.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = wrapper_payload
    wrapper.__dict__["_VERIFIED_BASE_KERNEL_SOURCE_BYTES"] = v2_payload
    exec(compile(wrapper_payload, wrapper.__file__, "exec"), wrapper.__dict__)
    expected_constants = {
        "BASE_KERNEL_NAME": V2_ARITHMETIC_NAME,
        "EXPECTED_BASE_KERNEL_SHA256": EXPECTED_V2_ARITHMETIC_SHA256,
        "EXPECTED_ROUTE_PREDECESSOR_SHA256": EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256,
        "EXPECTED_ROUTE_PREDECESSOR_MANIFEST_SHA256": (
            EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256
        ),
        "EXPECTED_CROSS_ROUTE_REFERENCE_SHA256": (
            EXPECTED_CROSS_ROUTE_KERNEL_SHA256
        ),
        "EXPECTED_CROSS_ROUTE_REFERENCE_MANIFEST_SHA256": (
            EXPECTED_CROSS_ROUTE_KERNEL_MANIFEST_SHA256
        ),
        "EXPECTED_BASE_RESOURCE_LIMITS": EXPECTED_V2_KERNEL_CAPABILITY_LIMITS,
        "EXPECTED_ROUTE_PREDECESSOR_RESOURCE_LIMITS": (
            EXPECTED_PREDECESSOR_KERNEL_CAPABILITY_LIMITS
        ),
        "EXPECTED_CROSS_ROUTE_REFERENCE_RESOURCE_LIMITS": (
            EXPECTED_CROSS_ROUTE_KERNEL_CAPABILITY_LIMITS
        ),
        "EXTENDED_RESOURCE_LIMITS": EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
    }
    for name, expected in expected_constants.items():
        if getattr(wrapper, name, None) != expected:
            raise RuntimeError(f"kernel wrapper contract drift: {name}")
    if wrapper.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS:
        raise RuntimeError("kernel wrapper effective limits drift")
    manifest = wrapper.capability_manifest()
    manifest_sha = sha256(canonical_bytes(manifest))
    if manifest_sha != EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256:
        raise RuntimeError("kernel capability manifest pin drift")
    if wrapper.capability_manifest_sha256() != manifest_sha:
        raise RuntimeError("kernel capability manifest digest API drift")
    if [item.get("relative_path") for item in manifest.get("source_layers", ())] != [
        KERNEL_WRAPPER_NAME,
        V2_ARITHMETIC_NAME,
    ]:
        raise RuntimeError("kernel execution source-layer drift")
    if sha256(canonical_bytes(manifest["source_layers"])) != EXPECTED_KERNEL_SOURCE_LAYERS_SHA256:
        raise RuntimeError("kernel execution source-layer digest drift")
    route = manifest.get("route_predecessor_reference")
    if type(route) is not dict:
        raise RuntimeError("kernel route predecessor reference drift")
    if sha256(canonical_bytes(route)) != EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256:
        raise RuntimeError("kernel route predecessor reference digest drift")
    if route.get("source_sha256") != EXPECTED_ROUTE_PREDECESSOR_KERNEL_SHA256:
        raise RuntimeError("kernel route predecessor source pin drift")
    if route.get("capability_manifest_sha256") != (
        EXPECTED_ROUTE_PREDECESSOR_KERNEL_MANIFEST_SHA256
    ):
        raise RuntimeError("kernel route predecessor manifest pin drift")
    if any(route.get(key) is not False for key in (
        "compiled", "executed", "execution_source_layer"
    )):
        raise RuntimeError("kernel route predecessor became an execution layer")
    cross_route = manifest.get("cross_route_reference")
    if type(cross_route) is not dict:
        raise RuntimeError("kernel cross-route reference drift")
    if sha256(canonical_bytes(cross_route)) != (
        EXPECTED_KERNEL_CROSS_ROUTE_REFERENCE_SHA256
    ):
        raise RuntimeError("kernel cross-route reference digest drift")
    if (
        cross_route.get("source_sha256") != EXPECTED_CROSS_ROUTE_KERNEL_SHA256
        or cross_route.get("capability_manifest_sha256")
        != EXPECTED_CROSS_ROUTE_KERNEL_MANIFEST_SHA256
        or cross_route.get("effective_resource_limits")
        != EXPECTED_CROSS_ROUTE_KERNEL_CAPABILITY_LIMITS
    ):
        raise RuntimeError("kernel cross-route provenance drift")
    if any(cross_route.get(key) is not False for key in (
        "compiled", "executed", "execution_source_layer"
    )):
        raise RuntimeError("kernel cross-route reference became an execution layer")
    return wrapper, wrapper_sha, manifest


def load_route_predecessor_reference(
    repo: Path,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    screen_path = checked_repo_file(repo, ROUTE_PREDECESSOR_SCREEN_NAME)
    screen_payload = bounded_bytes(screen_path, MAX_PINNED_SOURCE_BYTES)
    if sha256(screen_payload) != EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256:
        raise RuntimeError("route predecessor screen source pin drift")
    transcript_path = checked_repo_file(repo, ROUTE_PREDECESSOR_TRANSCRIPT_NAME)
    raw = bounded_bytes(transcript_path, MAX_PREDECESSOR_TRANSCRIPT_BYTES)
    if sha256(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256:
        raise RuntimeError("route predecessor transcript pin drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("route predecessor transcript is invalid JSON") from exc
    require_exact_keys(
        transcript,
        EXPECTED_RELABELLED_RESULT_KEYS,
        "route predecessor top-level transcript",
    )
    if raw != canonical_bytes(transcript):
        raise RuntimeError("route predecessor transcript is not canonical JSON")
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k573440_c32_q84_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "attempted_checkpoint_count": 84,
        "completed_checkpoint_count": 83,
        "failure_checkpoint_included": True,
        "horizon_reached_with_committed_checkpoint": False,
        "candidate_K_values": list(PREDECESSOR_M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_PREDECESSOR_POLICY_CAPS,
            "max_candidate_count": 32,
        },
        "kernel_capability_limits": EXPECTED_PREDECESSOR_KERNEL_CAPABILITY_LIMITS,
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256,
        "configuration_override_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
        ),
        "checkpoint_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if transcript.get(key) != value:
            raise RuntimeError(f"route predecessor transcript drift: {key}")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 84:
        raise RuntimeError("route predecessor record count drift")
    if type(history) is not list or len(history) != 83:
        raise RuntimeError("route predecessor history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("route predecessor records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("route predecessor history digest drift")
    if sha256(canonical_bytes(records[-1])) != EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256:
        raise RuntimeError("route predecessor failure digest drift")
    removed_rows = []
    for checkpoint_index, record in enumerate(records):
        expected_keys = (
            SUCCESS_RECORD_KEYS if checkpoint_index < 83 else FAILURE_RECORD_KEYS
        )
        require_exact_keys(
            record,
            expected_keys,
            f"route predecessor q{checkpoint_index + 1} record",
        )
        rows = record.get("candidate_records")
        if type(rows) is not list or len(rows) != 32:
            raise RuntimeError("route predecessor candidate row count drift")
        for candidate_index, (configured_K, row) in enumerate(
            zip(PREDECESSOR_M_CANDIDATES, rows)
        ):
            require_exact_keys(
                row,
                CANDIDATE_RECORD_KEYS,
                f"route predecessor q{checkpoint_index + 1} row {candidate_index}",
            )
            if (
                row.get("candidate_index") != candidate_index
                or row.get("configured_K") != configured_K
            ):
                raise RuntimeError("route predecessor candidate identity drift")
        removed = rows[0]
        if (
            removed.get("configured_K") != K65536
            or removed.get("feasible_under_current_prefix_cap") is not False
        ):
            raise RuntimeError("route predecessor K65536 feasibility evidence drift")
        removed_rows.append(removed)
    if K65536 in history:
        raise RuntimeError("route predecessor unexpectedly selected K65536")
    if sha256(canonical_bytes(removed_rows)) != EXPECTED_REMOVED_K65536_ROW_SET_SHA256:
        raise RuntimeError("route predecessor K65536 row-set digest drift")

    q83 = records[82]
    expected_q83 = {
        "checkpoint_number_one_based": 83,
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "selected_K": K573440,
        "selected_candidate_index": 31,
        "retained_expansion_count": K573440,
    }
    for key, value in expected_q83.items():
        if q83.get(key) != value:
            raise RuntimeError(f"route predecessor q83 drift: {key}")
    failure = records[83]
    expected_q84 = {
        "checkpoint_number_one_based": 84,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "input_expansion_count": K573440,
        "pretruncation_expansion_count": 694_130,
        "minimum_effective_K_to_meet_prefix": 586_381,
        "required_K_excess_over_policy_maximum": 12_941,
        "selected_K": None,
        "selected_candidate_index": None,
    }
    for key, value in expected_q84.items():
        if failure.get(key) != value:
            raise RuntimeError(f"route predecessor q84 drift: {key}")

    old_common = [
        {
            key: value for key, value in record.items()
            if key not in {"candidate_records", "selected_candidate_index"}
        }
        for record in records[:83]
    ]
    if sha256(canonical_bytes(old_common)) != EXPECTED_Q1_Q83_INDEX_INVARIANT_COMMON_SHA256:
        raise RuntimeError("route predecessor q1-q83 common-state digest drift")
    normalized_rows = []
    for record in records[:83]:
        checkpoint_rows = []
        for old_row in record["candidate_records"][1:]:
            normalized = dict(old_row)
            normalized["candidate_index"] -= 1
            checkpoint_rows.append(normalized)
        normalized_rows.append(checkpoint_rows)
    if sha256(canonical_bytes(normalized_rows)) != EXPECTED_Q1_Q83_NORMALIZED_ROWS_SHA256:
        raise RuntimeError("route predecessor q1-q83 normalized-row digest drift")

    reference = {
        "route_id": "magnetization_k573440_c32_q84_to_k589824_c32_q84_v1",
        "relationship": "trajectory_preserving_candidate_replacement",
        "screen": {
            "relative_path": ROUTE_PREDECESSOR_SCREEN_NAME,
            "source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
            "compiled": False,
            "executed": False,
            "execution_source_layer": False,
        },
        "canonical_transcript": {
            "relative_path": ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
            "failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256,
            "removed_K65536_row_set_sha256": (
                EXPECTED_REMOVED_K65536_ROW_SET_SHA256
            ),
            "loaded_before_replay_as_exact_reference": True,
            "used_only_after_replay_for_result_prefix_validation": True,
            "propagation_input": False,
            "checkpoint_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
    }
    return transcript, reference


def configure_parent_execution(
    parent: Any,
    configuration: Any,
    kernel_wrapper: Any,
) -> Dict[str, Any]:
    baseline = copy.deepcopy(parent.MODE_CONFIG)
    if baseline[MODE]["horizon_checkpoint_count"] != BASE_PARENT_HORIZON:
        raise RuntimeError("parent M horizon baseline drift")
    effective = copy.deepcopy(baseline)
    effective[MODE]["horizon_checkpoint_count"] = EXTENDED_HORIZON
    changed = []
    for mode, before_mode in baseline.items():
        for key, before_value in before_mode.items():
            if effective[mode].get(key) != before_value:
                changed.append(f"MODE_CONFIG.{mode}.{key}")
    expected_changed = [f"MODE_CONFIG.{MODE}.horizon_checkpoint_count"]
    if changed != expected_changed:
        raise RuntimeError("parent configuration changed outside M horizon")
    if effective["double_occupancy"] != baseline["double_occupancy"]:
        raise RuntimeError("parent double-occupancy configuration changed")
    parent.MODE_CONFIG = effective
    original_load_execution_sources = parent.load_execution_sources
    parent.load_v6_configuration = lambda _repo: configuration

    def load_wrapped_execution_sources(
        source_repo: Path,
        helper: Any,
        mode: str,
    ) -> Tuple[Any, Any, Dict[str, Any], Dict[str, str]]:
        base_kernel, root, modules, custody = original_load_execution_sources(
            source_repo, helper, mode
        )
        if base_kernel.RESOURCE_LIMITS != EXPECTED_V2_KERNEL_CAPABILITY_LIMITS:
            raise RuntimeError("v2 arithmetic capability limits drift")
        if kernel_wrapper.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS:
            raise RuntimeError("wrapped kernel capability limits drift")
        return kernel_wrapper, root, modules, custody

    parent.load_execution_sources = load_wrapped_execution_sources
    return {
        "override_id": "magnetization_parent_q84_horizon_override_v1",
        "parent_relative_path": CONTROL_FLOW_PARENT_NAME,
        "parent_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "parent_module_isolated": True,
        "parent_source_bytes_changed": False,
        "changed_fields": expected_changed,
        "semantic_delta": {
            expected_changed[0]: {
                "before": BASE_PARENT_HORIZON,
                "after": EXTENDED_HORIZON,
            },
        },
        "parent_mode_config_before": baseline,
        "parent_mode_config_before_sha256": sha256(canonical_bytes(baseline)),
        "parent_mode_config_after": effective,
        "parent_mode_config_after_sha256": sha256(canonical_bytes(effective)),
        "double_occupancy_configuration_unchanged": True,
    }


def is_canonical_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_q84_terminal_ledger(
    result: Mapping[str, Any],
    q83: Mapping[str, Any],
    q84: Mapping[str, Any],
    history: list[Any],
) -> None:
    require_exact_keys(q84, SUCCESS_RECORD_KEYS, "M q84 terminal record")
    if q84.get("checkpoint_index_zero_based") != 83:
        raise RuntimeError("M q84 terminal checkpoint index drift")
    if q84.get("checkpoint_number_one_based") != 84:
        raise RuntimeError("M q84 terminal checkpoint drift")
    for q84_key, q83_key in (
        ("input_expansion_count", "retained_expansion_count"),
        ("input_expansion_sha256", "retained_expansion_sha256"),
        ("E_before_ticks", "E_after_ticks"),
    ):
        if q84.get(q84_key) != q83.get(q83_key):
            raise RuntimeError(f"M q84 input continuity drift: {q84_key}")
    if not is_canonical_sha256(q84.get("input_expansion_sha256")):
        raise RuntimeError("M q84 input expansion digest drift")
    pre_count = q84.get("pretruncation_expansion_count")
    if type(pre_count) is not int or type(q84.get("input_expansion_count")) is not int:
        raise RuntimeError("M q84 expansion count type drift")
    try:
        E_before = int(q84["E_before_ticks"])
        prefix_cap = int(q84["budget_prefix_cap_ticks"])
        slack = int(q84["prefix_slack_before_selection_ticks"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("M q84 fixed-tick ledger field drift") from exc
    if slack != prefix_cap - E_before:
        raise RuntimeError("M q84 prefix slack recurrence drift")
    rows = q84.get("candidate_records")
    if type(rows) is not list or len(rows) != len(M_CANDIDATES):
        raise RuntimeError("M q84 candidate row count drift")
    feasible_indices = []
    for candidate_index, (configured_K, row) in enumerate(zip(M_CANDIDATES, rows)):
        require_exact_keys(
            row,
            CANDIDATE_RECORD_KEYS,
            f"M q84 candidate row {candidate_index}",
        )
        effective = min(configured_K, pre_count)
        expected = {
            "candidate_index": candidate_index,
            "configured_K": configured_K,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }
        for key, value in expected.items():
            if row.get(key) != value:
                raise RuntimeError(f"M q84 candidate row drift: {key}")
        try:
            drop = int(row["drop_ticks"])
            E_after = int(row["E_after_if_selected_ticks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("M q84 candidate fixed-tick field drift") from exc
        if drop < 0 or E_after != E_before + drop:
            raise RuntimeError("M q84 candidate E recurrence drift")
        feasible = E_after <= prefix_cap
        if row.get("feasible_under_current_prefix_cap") is not feasible:
            raise RuntimeError("M q84 candidate feasibility label drift")
        if feasible:
            feasible_indices.append(candidate_index)
    if result.get("horizon_checkpoint_attempted") is not True:
        raise RuntimeError("M q84 horizon-attempt flag drift")
    if feasible_indices != [31]:
        raise RuntimeError("M q84 K589824 row is not the unique first feasible candidate")
    if q84.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        raise RuntimeError("M q84 terminal status is not success")
    if any(key in q84 for key in FAILURE_ONLY_RECORD_KEYS):
        raise RuntimeError("M q84 success record contains failure-only fields")
    selected_index = 31
    selected_row = rows[31]
    expected_selection = {
        "selected_candidate_index": 31,
        "selected_K": K589824,
        "selected_effective_retained_count": selected_row["effective_retained_count"],
        "selected_dropped_term_count": selected_row["dropped_term_count"],
        "selected_drop_ticks": selected_row["drop_ticks"],
        "retained_expansion_count": selected_row["effective_retained_count"],
        "E_after_ticks": selected_row["E_after_if_selected_ticks"],
    }
    for key, value in expected_selection.items():
        if q84.get(key) != value:
            raise RuntimeError(f"M q84 success selection drift: {key}")
    if history[-1] != K589824:
        raise RuntimeError("M q84 success history selection drift")
    for key in ("selected_dropped_terms_sha256", "retained_expansion_sha256"):
        if not is_canonical_sha256(q84.get(key)):
            raise RuntimeError(f"M q84 success digest drift: {key}")
    for key in ("minimum_retained_abs_upper_ticks", "maximum_dropped_abs_upper_ticks"):
        try:
            if int(q84[key]) < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"M q84 success interval field drift: {key}") from exc
    if int(q84["E_after_ticks"]) > prefix_cap:
        raise RuntimeError("M q84 selected candidate violates prefix cap")
    expected_top = {
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_reached_with_committed_checkpoint": True,
        "last_committed_cumulative_drop_ticks": q84["E_after_ticks"],
    }
    for key, value in expected_top.items():
        if result.get(key) != value:
            raise RuntimeError(f"M q84 success summary drift: {key}")


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    require_handoff_top_level_keys(result)
    require_exact_keys(
        predecessor,
        EXPECTED_RELABELLED_RESULT_KEYS,
        "M route predecessor top-level transcript",
    )
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) != EXTENDED_HORIZON:
        raise RuntimeError("M q84 result did not attempt exactly through q84")
    if type(history) is not list or len(history) != 84:
        raise RuntimeError("M q84 selected history length drift")
    old_records = predecessor["records"]
    old_history = predecessor["selected_K_history"]
    if type(old_records) is not list or len(old_records) != 84:
        raise RuntimeError("M route predecessor record count drift")
    if type(old_history) is not list or len(old_history) != 83:
        raise RuntimeError("M route predecessor history count drift")
    if (
        predecessor.get("records_sha256")
        != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
        or sha256(canonical_bytes(old_records))
        != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
        or predecessor.get("selected_K_history_sha256")
        != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
        or sha256(canonical_bytes(old_history))
        != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
    ):
        raise RuntimeError("M route predecessor ledger digest drift")
    removed_rows = []
    for checkpoint_index, old_record in enumerate(old_records):
        require_exact_keys(
            old_record,
            SUCCESS_RECORD_KEYS if checkpoint_index < 83 else FAILURE_RECORD_KEYS,
            f"M route predecessor q{checkpoint_index + 1} record",
        )
        old_rows = old_record.get("candidate_records")
        if type(old_rows) is not list or len(old_rows) != 32:
            raise RuntimeError("M route predecessor candidate row count drift")
        removed = old_rows[0]
        require_exact_keys(
            removed,
            CANDIDATE_RECORD_KEYS,
            f"M route predecessor q{checkpoint_index + 1} removed row",
        )
        if (
            removed.get("candidate_index") != 0
            or removed.get("configured_K") != K65536
            or removed.get("feasible_under_current_prefix_cap") is not False
        ):
            raise RuntimeError("M route predecessor removed-K evidence drift")
        removed_rows.append(removed)
    if (
        K65536 in old_history
        or sha256(canonical_bytes(removed_rows))
        != EXPECTED_REMOVED_K65536_ROW_SET_SHA256
    ):
        raise RuntimeError("M route predecessor removed-K trajectory drift")
    if history[:83] != old_history or history[83] != K589824:
        raise RuntimeError("M replacement changed the q1-q83 selected-K trajectory")
    if sha256(canonical_bytes(history)) != EXPECTED_Q84_SUCCESS_HISTORY_SHA256:
        raise RuntimeError("M q84 expected selected-K history digest drift")

    common_records = []
    normalized_rows = []
    selected_indices = []
    for index in range(83):
        old = old_records[index]
        new = records[index]
        require_exact_keys(new, SUCCESS_RECORD_KEYS, f"M q{index + 1} record")
        old_common = {
            key: value for key, value in old.items()
            if key not in {"candidate_records", "selected_candidate_index"}
        }
        new_common = {
            key: value for key, value in new.items()
            if key not in {"candidate_records", "selected_candidate_index"}
        }
        if new_common != old_common:
            raise RuntimeError(
                f"M replacement changed q{index + 1} index-invariant state"
            )
        common_records.append(new_common)
        old_selected_index = old.get("selected_candidate_index")
        new_selected_index = new.get("selected_candidate_index")
        if (
            type(old_selected_index) is not int
            or old_selected_index <= 0
            or new_selected_index != old_selected_index - 1
        ):
            raise RuntimeError(f"M q{index + 1} selected-index shift drift")
        if (
            new.get("selected_K") != old.get("selected_K")
            or M_CANDIDATES[new_selected_index] != new.get("selected_K")
        ):
            raise RuntimeError(f"M q{index + 1} selected-K mapping drift")
        selected_indices.append(new_selected_index)
        old_rows = old["candidate_records"]
        new_rows = new.get("candidate_records")
        if type(new_rows) is not list or len(new_rows) != 32:
            raise RuntimeError(f"M q{index + 1} replacement row count drift")
        expected_normalized = []
        for new_index, (old_row, new_row) in enumerate(
            zip(old_rows[1:], new_rows[:31])
        ):
            require_exact_keys(
                new_row,
                CANDIDATE_RECORD_KEYS,
                f"M q{index + 1} mapped row {new_index}",
            )
            normalized_old = dict(old_row)
            normalized_old["candidate_index"] = new_index
            expected_normalized.append(normalized_old)
            if new_row != normalized_old:
                raise RuntimeError(
                    f"M q{index + 1} configured-K row mapping drift"
                )
        normalized_rows.append(new_rows[:31])
        appended = new_rows[31]
        require_exact_keys(
            appended,
            CANDIDATE_RECORD_KEYS,
            f"M q{index + 1} K589824 row",
        )
        pre_count = new.get("pretruncation_expansion_count")
        effective = min(K589824, pre_count)
        expected_appended = {
            "candidate_index": 31,
            "configured_K": K589824,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }
        for key, value in expected_appended.items():
            if appended.get(key) != value:
                raise RuntimeError(f"M q{index + 1} K589824 row drift: {key}")
        try:
            drop = int(appended["drop_ticks"])
            E_after = int(appended["E_after_if_selected_ticks"])
            E_before = int(new["E_before_ticks"])
            prefix_cap = int(new["budget_prefix_cap_ticks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("M K589824 row fixed-tick field drift") from exc
        if drop < 0 or E_after != E_before + drop:
            raise RuntimeError("M K589824 row E recurrence drift")
        if appended.get("feasible_under_current_prefix_cap") is not (
            E_after <= prefix_cap
        ):
            raise RuntimeError("M K589824 row feasibility-label drift")
        feasible = [
            row_index for row_index, row in enumerate(new_rows)
            if row["feasible_under_current_prefix_cap"] is True
        ]
        if not feasible or feasible[0] != new_selected_index:
            raise RuntimeError(f"M q{index + 1} first-feasible selection drift")

    if sha256(canonical_bytes(common_records)) != (
        EXPECTED_Q1_Q83_INDEX_INVARIANT_COMMON_SHA256
    ):
        raise RuntimeError("M q1-q83 index-invariant common digest drift")
    if sha256(canonical_bytes(normalized_rows)) != (
        EXPECTED_Q1_Q83_NORMALIZED_ROWS_SHA256
    ):
        raise RuntimeError("M q1-q83 normalized mapped-row digest drift")

    new_q83 = records[82]
    for key, value in {
        "selected_candidate_index": 30,
        "selected_K": K573440,
        "selected_effective_retained_count": K573440,
        "selected_dropped_term_count": 78_576,
        "retained_expansion_count": K573440,
    }.items():
        if new_q83.get(key) != value:
            raise RuntimeError(f"M q83 trajectory handoff drift: {key}")

    old_q84 = old_records[83]
    new_q84 = records[83]
    require_exact_keys(old_q84, FAILURE_RECORD_KEYS, "route predecessor q84 failure")
    require_exact_keys(new_q84, SUCCESS_RECORD_KEYS, "M q84 success")
    excluded = {
        "candidate_records",
        "status",
        "selected_candidate_index",
        "selected_K",
        *FAILURE_ONLY_RECORD_KEYS,
    }
    old_shared = {
        key: value for key, value in old_q84.items() if key not in excluded
    }
    if sha256(canonical_bytes(old_shared)) != EXPECTED_Q84_SHARED_PROPAGATION_SHA256:
        raise RuntimeError("route predecessor q84 shared-propagation digest drift")
    if {key: new_q84.get(key) for key in old_shared} != old_shared:
        raise RuntimeError("M replacement changed q84 shared propagation")
    old_q84_normalized = []
    for new_index, (old_row, new_row) in enumerate(
        zip(old_q84["candidate_records"][1:], new_q84["candidate_records"][:31])
    ):
        normalized_old = dict(old_row)
        normalized_old["candidate_index"] = new_index
        old_q84_normalized.append(normalized_old)
        if new_row != normalized_old:
            raise RuntimeError("M q84 normalized predecessor row mapping drift")
    if sha256(canonical_bytes(old_q84_normalized)) != (
        EXPECTED_Q84_NORMALIZED_PREDECESSOR_ROWS_SHA256
    ):
        raise RuntimeError("M q84 normalized predecessor row digest drift")
    appended_q84 = new_q84["candidate_records"][31]
    for key, value in {
        "candidate_index": 31,
        "configured_K": K589824,
        "effective_retained_count": K589824,
        "dropped_term_count": 104_306,
        "feasible_under_current_prefix_cap": True,
    }.items():
        if appended_q84.get(key) != value:
            raise RuntimeError(f"M q84 K589824 discriminator drift: {key}")
    if old_q84.get("minimum_effective_K_to_meet_prefix") != 586_381:
        raise RuntimeError("M q84 predecessor minimum-K discriminator drift")

    selected_indices.append(new_q84.get("selected_candidate_index"))
    if sha256(canonical_bytes(selected_indices)) != EXPECTED_SELECTED_INDEX_HISTORY_SHA256:
        raise RuntimeError("M selected-index history digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("M q84 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("M q84 selected history digest drift")
    if (
        result.get("attempted_checkpoint_count") != 84
        or result.get("completed_checkpoint_count") != 84
    ):
        raise RuntimeError("M q84 success count summary drift")
    validate_q84_terminal_ledger(result, new_q83, new_q84, history)
    return {
        "validation_id": "M_k589824_c32_q84_replacement_handoff_v1",
        "route_semantics": "selected_and_state_trajectory_preserving_replacement",
        "candidate_row_prefix_exact": False,
        "q1_through_q83_selected_K_history_exact": True,
        "q1_through_q83_index_invariant_state_and_commit_fields_exact": True,
        "q1_through_q83_old_indices_1_31_to_new_0_30_rows_exact": True,
        "selected_index_shift": "old_index_minus_one_through_q83",
        "removed_K": K65536,
        "removed_K_infeasible_checkpoint_count": 84,
        "removed_K_never_selected": True,
        "removed_K_row_set_sha256": EXPECTED_REMOVED_K65536_ROW_SET_SHA256,
        "q83_predecessor_selected_candidate_index": 31,
        "q83_selected_candidate_index": 30,
        "q83_selected_K": K573440,
        "q84_shared_propagation_fields_exact": True,
        "q84_old_indices_1_31_to_new_0_30_rows_exact": True,
        "q84_predecessor_minimum_effective_K": 586_381,
        "q84_K589824_headroom_over_predecessor_minimum_K": 3_443,
        "q84_selected_candidate_index": 31,
        "q84_selected_K": K589824,
        "selected_K_history_sha256": EXPECTED_Q84_SUCCESS_HISTORY_SHA256,
        "selected_index_history_sha256": EXPECTED_SELECTED_INDEX_HISTORY_SHA256,
        "q84_outcome_precommitted": False,
    }


def execution_components(
    parent_components: Any,
    self_sha: str,
    kernel_wrapper_sha: str,
) -> list[Dict[str, Any]]:
    if type(parent_components) is not list:
        raise RuntimeError("control-flow parent component list drift")
    if any(type(item) is not dict for item in parent_components):
        raise RuntimeError("control-flow parent component is not an exact dict")
    paths = [item.get("relative_path") for item in parent_components]
    if len(paths) != len(set(paths)):
        raise RuntimeError("duplicate parent execution component path")
    if parent_components != list(EXPECTED_PARENT_EXECUTION_COMPONENTS):
        raise RuntimeError("parent execution component schema drift")
    components = [{
        "relative_path": SELF_NAME,
        "role": "M_k589824_c32_q84_fresh_same_byte_screen",
        "sha256": self_sha,
    }]
    saw_parent = saw_v6 = saw_v2 = False
    forbidden_route_layers = {
        ROUTE_PREDECESSOR_SCREEN_NAME,
        ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
        "hubbard_l8_adaptive_k_arithmetic_k573440.py",
        "hubbard_l8_adaptive_k_arithmetic_k589824_c34.py",
    }
    for original in parent_components:
        if type(original) is not dict:
            raise RuntimeError("control-flow parent component is not a dict")
        item = dict(original)
        relative_path = item.get("relative_path")
        if relative_path in forbidden_route_layers:
            raise RuntimeError("route predecessor became an execution component")
        if relative_path == CONTROL_FLOW_PARENT_NAME:
            if item.get("sha256") != EXPECTED_CONTROL_FLOW_PARENT_SHA256:
                raise RuntimeError("control-flow parent component pin drift")
            item["role"] = "four_gate_control_flow_parent_private_entrypoint"
            saw_parent = True
        elif relative_path == V6_BASELINE_CONFIGURATION_NAME:
            if item.get("sha256") != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
                raise RuntimeError("v6 baseline component pin drift")
            item["role"] = "v6_baseline_configuration_before_declared_override"
            saw_v6 = True
        elif relative_path == V2_ARITHMETIC_NAME:
            if item.get("sha256") != EXPECTED_V2_ARITHMETIC_SHA256:
                raise RuntimeError("v2 arithmetic component pin drift")
            item["role"] = "v2_arithmetic_bytes_beneath_capability_wrapper"
            saw_v2 = True
        components.append(item)
        if relative_path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "k589824_capability_override_provider",
                "sha256": kernel_wrapper_sha,
            })
    if not (saw_parent and saw_v6 and saw_v2):
        raise RuntimeError("control-flow parent component set is incomplete")
    return components


def configuration_reference() -> Dict[str, Any]:
    return {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "source_sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "role": "v6_baseline_candidates_and_caps_before_direct_override",
        "baseline_M_candidate_K_values_sha256": EXPECTED_V6_M_CANDIDATE_SHA256,
        "baseline_D_candidate_K_values_sha256": EXPECTED_V6_D_CANDIDATE_SHA256,
        "baseline_policy_caps_sha256": EXPECTED_V6_POLICY_CAPS_SHA256,
        "compiled_from_verified_bytes": True,
        "module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }


def configuration_override(baseline_m: Tuple[int, ...]) -> Dict[str, Any]:
    if M_CANDIDATES != baseline_m[1:] + (
        K540672,
        K557056,
        K573440,
        K589824,
    ):
        raise RuntimeError("configuration override baseline M ladder drift")
    return {
        "override_id": "magnetization_k589824_c32_q84_configuration_override_v1",
        "diagnostic_ladder_precommitted_before_replay": True,
        "replacement_semantics": (
            "selected_and_state_trajectory_preserving_not_candidate_row_prefix_exact"
        ),
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": EXPECTED_V6_M_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 29, "after": 32},
            "candidate_ladder_added": [K540672, K557056, K573440, K589824],
            "candidate_ladder_removed": [K65536],
            "policy_cap_changes": {
                "max_candidate_K": {"before": 524_288, "after": K589824},
                "max_output_terms_if_successful": {"before": 524_288, "after": K589824},
            },
        },
        "incremental_route_override_from_k573440_c32_q84": {
            "predecessor_candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 32, "after": 32},
            "candidate_ladder_added": [K589824],
            "candidate_ladder_removed": [K65536],
            "policy_cap_changes": {
                "max_candidate_K": {"before": K573440, "after": K589824},
                "max_output_terms_if_successful": {"before": K573440, "after": K589824},
            },
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "derived_policy_cap": {
            "field": "max_candidate_count",
            "derivation": "len(candidate_K_values)",
            "before_on_route": 32,
            "after": 32,
        },
        "unchanged_policy_caps": {
            key: value for key, value in EXPECTED_V6_POLICY_CAPS.items()
            if key not in {"max_candidate_K", "max_output_terms_if_successful"}
        },
        "double_occupancy_candidate_configuration_unchanged": True,
        "overridden_fields": [
            f"MODE_CONFIG.{MODE}.candidates",
            "POLICY_CAPS_BASE.max_candidate_K",
            "POLICY_CAPS_BASE.max_output_terms_if_successful",
        ],
    }


def kernel_capability_override(
    wrapper_sha: str,
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "separate_k589824_capability_override_provider",
        "base_arithmetic_relative_path": V2_ARITHMETIC_NAME,
        "base_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "module_itself_is_extended_kernel": True,
        "verified_compilation_inputs": [
            "_VERIFIED_SELF_SOURCE_BYTES",
            "_VERIFIED_BASE_KERNEL_SOURCE_BYTES",
        ],
        "capability_manifest": dict(manifest),
        "capability_manifest_sha256": sha256(canonical_bytes(manifest)),
        "direct_capability_changes_from_v2": {
            "max_retained_K": {"before": 524_288, "after": K589824},
        },
        "incremental_route_changes_from_k573440": {
            "max_retained_K": {"before": K573440, "after": K589824},
        },
        "execution_source_layers": [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME],
        "route_predecessor_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def validate_and_relabel(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    predecessor_reference: Mapping[str, Any],
    baseline_m: Tuple[int, ...],
    kernel_wrapper_sha: str,
    kernel_manifest: Mapping[str, Any],
    horizon_override: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q84 relabel requires fresh same-byte self execution")
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "control-flow parent top-level result",
    )
    expected_parent_fields = {
        "schema_version": 1,
        "transcript_fingerprint": "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1",
        "screen_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "same_byte_self_execution": True,
        "v2_run_entrypoint_called": False,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "control_flow_owned_by_screen": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "candidate_K_values": list(M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(M_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_CAPABILITY_LIMITS,
    }
    for key, expected in expected_parent_fields.items():
        if result.get(key) != expected:
            raise RuntimeError(f"control-flow parent result drift: {key}")
    require_exact_source_custody(
        result.get("source_custody"),
        EXPECTED_PARENT_SOURCE_CUSTODY,
        "control-flow parent source custody",
    )
    handoff = validate_replay_handoff(result, predecessor)
    old_components = result.get("screen_execution_components")
    old_components_sha = result.get("screen_execution_components_sha256")
    if old_components_sha != sha256(canonical_bytes(old_components)):
        raise RuntimeError("control-flow parent component digest drift")
    old_configuration = result.get("configuration_reference")
    if (
        type(old_configuration) is not dict
        or result.get("configuration_reference_sha256")
        != sha256(canonical_bytes(old_configuration))
    ):
        raise RuntimeError("control-flow parent configuration digest drift")
    old_transform = result.get("checkpoint_transform")
    old_transform_sha = result.get("checkpoint_transform_sha256")
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("control-flow parent transform digest drift")

    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(old_components, self_sha, kernel_wrapper_sha)
    baseline_reference = configuration_reference()
    config_override = configuration_override(baseline_m)
    capability = kernel_capability_override(kernel_wrapper_sha, kernel_manifest)
    route_reference = dict(predecessor_reference)
    transform = {
        "transform_id": "magnetization_four_gate_k589824_c32_q84_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "route_predecessor_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q84_outcome_precommitted": False,
        "overridden_semantics": [
            "candidate_K_values",
            "policy_max_candidate_K",
            "policy_max_output_terms_if_successful",
            "kernel_max_retained_K",
            "magnetization_horizon_checkpoint_count",
        ],
    }
    custody = dict(result["source_custody"])
    for relative_path in (SELF_NAME, CONTROL_FLOW_PARENT_NAME, KERNEL_WRAPPER_NAME):
        if relative_path in custody:
            raise RuntimeError(f"unexpected preexisting custody entry: {relative_path}")
    custody[SELF_NAME] = self_sha
    custody[CONTROL_FLOW_PARENT_NAME] = EXPECTED_CONTROL_FLOW_PARENT_SHA256
    custody[KERNEL_WRAPPER_NAME] = kernel_wrapper_sha
    expected_final_custody = {
        **EXPECTED_PARENT_SOURCE_CUSTODY,
        SELF_NAME: self_sha,
        CONTROL_FLOW_PARENT_NAME: EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        KERNEL_WRAPPER_NAME: kernel_wrapper_sha,
    }
    require_exact_source_custody(
        custody,
        expected_final_custody,
        "relabelled M q84 source custody",
    )

    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k589824_c32_q84_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_relative_path": CONTROL_FLOW_PARENT_NAME,
        "control_flow_parent_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "control_flow_parent_compiled_from_verified_bytes": True,
        "control_flow_parent_module_isolated": True,
        "control_flow_parent_same_byte_execution": True,
        "control_flow_parent_private_entrypoint_called": True,
        "control_flow_parent_runtime_horizon_override_applied": True,
        "v6_configuration_source_used_as_baseline_only": True,
        "v6_runtime_configuration_override_applied": True,
        "v2_arithmetic_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "v2_arithmetic_compiled_from_verified_bytes": True,
        "arithmetic_kernel_commit_role": (
            "base_v2_arithmetic_implementation_commit_before_capability_override"
        ),
        "kernel_capability_wrapper_relative_path": KERNEL_WRAPPER_NAME,
        "kernel_capability_wrapper_source_sha256": kernel_wrapper_sha,
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": baseline_reference,
        "configuration_reference_sha256": sha256(canonical_bytes(baseline_reference)),
        "configuration_override": config_override,
        "configuration_override_sha256": sha256(canonical_bytes(config_override)),
        "kernel_capability_override": capability,
        "kernel_capability_override_sha256": sha256(canonical_bytes(capability)),
        "parent_horizon_override": dict(horizon_override),
        "parent_horizon_override_sha256": sha256(canonical_bytes(horizon_override)),
        "route_predecessor_reference": route_reference,
        "route_predecessor_reference_sha256": sha256(canonical_bytes(route_reference)),
        "predecessor_handoff_validation": handoff,
        "predecessor_handoff_validation_sha256": sha256(canonical_bytes(handoff)),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": sha256(canonical_bytes(transform)),
        "source_custody": custody,
        "diagnostic_candidate_ladder_precommitted_before_replay": True,
        "diagnostic_horizon_precommitted_before_replay": True,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    })
    require_exact_keys(
        result,
        EXPECTED_RELABELLED_RESULT_KEYS,
        "relabelled M q84 top-level result",
    )
    require_exact_source_custody(
        result.get("source_custody"),
        expected_final_custody,
        "relabelled M q84 source custody",
    )
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q84 screen requires fresh same-byte self execution")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_control_flow_parent(repo)
    configuration, baseline_m = load_configured_v6_baseline(repo)
    kernel_wrapper, kernel_wrapper_sha, kernel_manifest = load_kernel_wrapper(repo)
    predecessor, predecessor_reference = load_route_predecessor_reference(repo)
    horizon_override = configure_parent_execution(parent, configuration, kernel_wrapper)
    result = parent._run_verified(repo, MODE)
    return validate_and_relabel(
        result,
        predecessor,
        predecessor_reference,
        baseline_m,
        kernel_wrapper_sha,
        kernel_manifest,
        horizon_override,
    )


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_magnetization_k589824_c32_q84_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("M q84 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("M q84 transcript exceeds output byte cap")
    output = output.resolve()
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=output.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    result = run(args.repo)
    raw = canonical_bytes(result)
    output = args.output_dir / OUTPUT_NAME
    write_atomic_bounded(output, raw)
    final = result["records"][-1]
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "screen_terminal_condition": result["screen_terminal_condition"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "final_status": final["status"],
        "final_checkpoint": final["checkpoint_number_one_based"],
        "last_committed_cumulative_drop_ticks": result[
            "last_committed_cumulative_drop_ticks"
        ],
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_terminal_attempt"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
