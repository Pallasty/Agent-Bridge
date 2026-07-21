#!/usr/bin/env python3
"""Diagnostic-only M K606208/C33 q86 screen with a pinned raw parent."""

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
    "k606208_c33_q86_screen.py"
)
CONTROL_FLOW_PARENT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k606208_c33.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k589824_c32_q86_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k589824_c32_q86_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k606208_c33_q86_transcript.json"
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
EXPECTED_V2_HELPER_SHA256 = (
    "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "447cb116c2ca977cb2711b08e64e5795728907b8c4033bd1eb38211bf63cf558"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "116c8d37e11e2762a3a47d2d5844d059de0277dbd41724b5c65018b0b234b395"
)
EXPECTED_KERNEL_SOURCE_LAYERS_SHA256 = (
    "345b883e9dac2b657d30a629b4b0bb9339a96372deb05f7da2d769a6f5d2e1da"
)
EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256 = (
    "bd7d856617c0af68ba781da24d055c05301d022ece4a77af1f5c50431daf7492"
)
EXPECTED_KERNEL_CROSS_ROUTE_REFERENCE_SHA256 = (
    "221d37ef7f58799cf1fa908f6c81b1410a332bbdaac604d75df6f03695aa7343"
)
EXPECTED_ROUTE_KERNEL_SHA256 = (
    "9eded142673fcb548d585d0071f5c550970c48c24d50c5ef1fc43b6257b1775d"
)
EXPECTED_ROUTE_KERNEL_MANIFEST_SHA256 = (
    "6906e56af531063800742e95304682f9bcd123d0086806d59691e0b099772b1a"
)
EXPECTED_CROSS_ROUTE_KERNEL_SHA256 = (
    "34757028d695e2542cade50f4be5c214006dee6945e01afc2483e7338d6cb7dd"
)
EXPECTED_CROSS_ROUTE_KERNEL_MANIFEST_SHA256 = (
    "c55df50288334226a4d8ba37a257ca645d601967f8778f426a313773c1c73629"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "002cc87d5d1a8f1908a837e8612e3a9d4a4c5ebbf68e41f841ba4a5a639ff878"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "c24a665d543323a0e7f28ac4023fe5ae3d54b39c4e2991cba3e70e9371d0053d"
)
EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE = 758_536
# The predecessor has 85 records because q85 is its included failure attempt.
# The q1--84 prefix remains separately pinned below for the common replay ledger.
EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256 = (
    "aa3f493f3779da261261cef49bc12654fc8e8f44889cd14a979f5c77413336c0"
)
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "2e1c35996258d985ee4808e2e86235ce004de0e4d843043bec71a29fe12f8a32"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "ba0a38f3cdf13114aaa7e00f2889bc221ad7afa1b42d038cc4a4ed710a21df5c"
)
EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256 = (
    "ed97e80cc71f6738865abf849e7fc722f42429bb7acf6a5f93f1ec319cc291fa"
)
EXPECTED_ROUTE_PREDECESSOR_Q85_FAILURE_SHA256 = (
    "5c7f0315f858635b5784cc26a8f5bcd8171805ea957b7d782692cee0ae4e1235"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_SHA256 = (
    "a4d0b5a8736f2ffba7f83bf90685b5ce57920dee5028f9949159d5c3110a2138"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "b75d14b07fe59af899fb9d1cc289d58f04bd83cf91e5b10a4fbc6a762c52ea3b"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256 = (
    "a0e1f3e7750341a49732024034fa3853927d839e45b51a811e87df152b342d66"
)
EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256 = (
    "28acb72f3a225fe867961936044687d3ae5556d7be70d28c0c4e68074daf9a9e"
)
EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256 = (
    "4ea7baa4294bacb554d652da98b410239c64d5a585865564f8b813a155010527"
)
EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256 = (
    "69d5e3695fca27676a3b7b8db0e626f04a0b02c02e9d3eb086fa3494541e5c47"
)
EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256 = (
    "f8eddd7b546f0e8293290b9cabac6da6bcb39588b6452905657dd4293ddc8464"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "8ce85c741f471aef368a4eb35a564f25fce5345b0aaf9b93d1ec6af997f21e57"
)
EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256 = (
    "c2aa225b96c984618d0dd0454dba9cb20f20ae8749f3f2452d8982a399f07336"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_ROUTE_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "magnetization"
BASE_PARENT_HORIZON = 80
EXTENDED_HORIZON = 86
K540672 = 540_672
K557056 = 557_056
K573440 = 573_440
K589824 = 589_824
K606208 = 606_208

V6_M_CANDIDATES = (
    65_536, 81_920, 98_304, 114_688, 131_072, 147_456, 163_840,
    180_224, 196_608, 212_992, 229_376, 245_760, 262_144, 278_528,
    294_912, 311_296, 327_680, 344_064, 360_448, 376_832, 393_216,
    409_600, 425_984, 442_368, 458_752, 475_136, 491_520, 507_904,
    524_288,
)
PREDECESSOR_M_CANDIDATES = (
    V6_M_CANDIDATES[1:] + (K540672, K557056, K573440, K589824)
)
M_CANDIDATES = PREDECESSOR_M_CANDIDATES + (K606208,)
EXPECTED_V6_M_CANDIDATE_SHA256 = (
    "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
)
EXPECTED_PREDECESSOR_CANDIDATE_SHA256 = (
    "94c062a2f562b7ce9e095ce9585ac4087b7bfef2af492b45762ca5d732ae9b80"
)
EXPECTED_CANDIDATE_SHA256 = (
    "8c0105608be381ce3ecaeb6178d25c0eda50713e54aa22f734b964bbd5464f86"
)
EXPECTED_Q84_SELECTED_HISTORY_SHA256 = (
    "ba0a38f3cdf13114aaa7e00f2889bc221ad7afa1b42d038cc4a4ed710a21df5c"
)
EXPECTED_Q84_RETAINED_EXPANSION_SHA256 = (
    "35971741409db21c05aaffcda87ef034a5eebe2199f3ba4b03e62c12bbc24eba"
)
EXPECTED_Q84_E_AFTER_TICKS = "1700230728891281"
EXPECTED_Q85_PREFIX_CAP_TICKS = "1700381839070373"
EXPECTED_Q86_PREFIX_CAP_TICKS = "1700486370476045"
EXPECTED_Q85_MINIMUM_EFFECTIVE_K = 592_290
EXPECTED_Q85_NEW_POLICY_HEADROOM = 13_918
EXPECTED_EXTENSION_CHECKPOINT_ANCHORS = {
    85: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 28,
        "gate_batch_sha256": (
            "34a10608b11edb722a301d2fd60689a6b29389d1ba6dc76376cbb124ae32d77c"
        ),
    },
    86: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 29,
        "gate_batch_sha256": (
            "890f848373b624e1b7ebe230ef5d32d07a6e862c357317657e72c95ddda4d74f"
        ),
    },
}

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
    "max_candidate_K": K589824,
    "max_output_terms_if_successful": K589824,
}
POLICY_CAPS_BASE = {
    **EXPECTED_PREDECESSOR_POLICY_CAPS,
    "max_candidate_K": K606208,
    "max_output_terms_if_successful": K606208,
}

EXPECTED_V2_KERNEL_LIMITS = {
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
EXPECTED_ROUTE_KERNEL_LIMITS = {
    **EXPECTED_V2_KERNEL_LIMITS,
    "max_candidate_count": 32,
    "max_retained_K": K589824,
}
EXPECTED_WRAPPED_KERNEL_LIMITS = {
    **EXPECTED_V2_KERNEL_LIMITS,
    "max_candidate_count": 33,
    "max_retained_K": K606208,
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
        "relative_path": (
            "hubbard_l8_interval_checkpoints/"
            "staggered_magnetization_boundary_003.b85"
        ),
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
Q84_FAILURE_ONLY_KEYS = frozenset({
    "minimum_effective_K_to_meet_prefix",
    "required_K_excess_over_policy_maximum",
    "maximum_candidate_drop_excess_over_slack_ticks",
})
Q84_SUCCESS_ONLY_KEYS = frozenset({
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
Q84_FAILURE_RECORD_KEYS = frozenset({
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
Q84_SUCCESS_RECORD_KEYS = (
    Q84_FAILURE_RECORD_KEYS - Q84_FAILURE_ONLY_KEYS | Q84_SUCCESS_ONLY_KEYS
)
UPSTREAM_PARENT_RESULT_KEYS = frozenset({
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
RESOURCE_POLICY_ABORT_TOP_LEVEL_KEYS = frozenset({
    "resource_policy_abort",
    "resource_policy_abort_sha256",
})
RESOURCE_POLICY_ABORT_KEYS = frozenset({
    "schema_version",
    "abort_id",
    "abort_kind",
    "abort_frame_local_schema_id",
    "exception_type",
    "exception_message",
    "exception_args",
    "exception_source_role",
    "exception_chained_from_exact_parent_helper",
    "control_flow_parent_source_sha256",
    "helper_source_sha256",
    "kernel_source_sha256",
    "checkpoint_index_zero_based",
    "checkpoint_number_one_based",
    "stage_index",
    "stage_group",
    "batch_in_stage",
    "gate_occurrence_first_zero_based",
    "gate_occurrence_last_zero_based",
    "gate_batch_sha256",
    "input_expansion_count",
    "input_expansion_sha256",
    "pretruncation_expansion_count",
    "observed_term_count",
    "policy_max_single_expansion_terms",
    "kernel_max_single_expansion_terms",
    "enforced_term_cap",
    "observed_excess_terms",
    "policy_relation",
    "gate_batch_propagation_started",
    "gate_batch_propagation_completed",
    "policy_cap_check_reached",
    "kernel_cap_violation_triggered",
    "live_expansion_snapshot_available",
    "q86_pretruncation_digest_computed",
    "q86_ranking_performed",
    "q86_candidate_rows_constructed",
    "q86_selection_performed",
    "q86_commit_performed",
    "q86_checkpoint_record_constructed",
    "q86_partial_expansion_committed",
    "q85_committed_record_sha256",
    "peak_live_terms_this_checkpoint",
    "peak_live_terms_cumulative",
    "term_gate_visits_increment",
    "term_gate_visits_cumulative",
    "rounding_increment_scaled_ticks_squared",
    "rounding_cumulative_scaled_ticks_squared",
    "maximum_expansion_coefficient_tick_bits",
    "maximum_product_bits",
})
EXPECTED_PARENT_RESULT_KEYS = (
    UPSTREAM_PARENT_RESULT_KEYS | RESOURCE_POLICY_ABORT_TOP_LEVEL_KEYS
)
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
EXPECTED_ROUTE_PREDECESSOR_RESULT_KEYS = (
    UPSTREAM_PARENT_RESULT_KEYS | RELABELLED_ADDED_TOP_LEVEL_KEYS
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True,
        separators=(",", ":"), sort_keys=True,
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


def load_pinned_module(repo: Path, relative_path: str, expected: str, name: str):
    path = checked_repo_file(repo, relative_path)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != expected:
        raise RuntimeError(f"source pin drift for {relative_path}: {observed}")
    return compile_isolated(name, path, payload), payload


def changed_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def exact_value_equal(observed: Any, expected: Any) -> bool:

    if type(observed) is not type(expected):
        return False
    if type(expected) is dict:
        return (
            observed.keys() == expected.keys()
            and all(
                exact_value_equal(observed[key], expected[key])
                for key in expected
            )
        )
    if type(expected) in (list, tuple):
        return (
            len(observed) == len(expected)
            and all(
                exact_value_equal(left, right)
                for left, right in zip(observed, expected)
            )
        )
    return observed == expected


def validate_local_configuration() -> None:
    if len(V6_M_CANDIDATES) != 29 or len(PREDECESSOR_M_CANDIDATES) != 32:
        raise RuntimeError("M predecessor candidate count drift")
    if len(M_CANDIDATES) != 33 or M_CANDIDATES != PREDECESSOR_M_CANDIDATES + (K606208,):
        raise RuntimeError("M K606208 route is not an exact append")
    if any(left >= right for left, right in zip(M_CANDIDATES, M_CANDIDATES[1:])):
        raise RuntimeError("M candidate order drift")
    if sha256(canonical_bytes(list(PREDECESSOR_M_CANDIDATES))) != EXPECTED_PREDECESSOR_CANDIDATE_SHA256:
        raise RuntimeError("M predecessor candidate digest drift")
    if sha256(canonical_bytes(list(M_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("M candidate digest drift")
    expected = {"max_candidate_K", "max_output_terms_if_successful"}
    if changed_keys(EXPECTED_V6_POLICY_CAPS, POLICY_CAPS_BASE) != expected:
        raise RuntimeError("direct policy override changed a non-K field")
    if changed_keys(EXPECTED_PREDECESSOR_POLICY_CAPS, POLICY_CAPS_BASE) != expected:
        raise RuntimeError("route policy override changed a non-K field")
    if POLICY_CAPS_BASE["max_candidate_K"] != M_CANDIDATES[-1]:
        raise RuntimeError("policy maximum and M ladder disagree")
    schema_sizes = {
        "upstream_raw_top_level": len(UPSTREAM_PARENT_RESULT_KEYS),
        "raw_top_level": len(EXPECTED_PARENT_RESULT_KEYS),
        "final_top_level": len(EXPECTED_RELABELLED_RESULT_KEYS),
        "success_record": len(Q84_SUCCESS_RECORD_KEYS),
        "failure_record": len(Q84_FAILURE_RECORD_KEYS),
        "candidate_row": len(CANDIDATE_RECORD_KEYS),
        "resource_abort": len(RESOURCE_POLICY_ABORT_KEYS),
    }
    if schema_sizes != {
        "upstream_raw_top_level": 65,
        "raw_top_level": 67,
        "final_top_level": 96,
        "success_record": 37,
        "failure_record": 31,
        "candidate_row": 7,
        "resource_abort": 50,
    }:
        raise RuntimeError("M q86 closed schema size drift")


def load_control_flow_parent(repo: Path) -> Any:
    parent, _ = load_pinned_module(
        repo, CONTROL_FLOW_PARENT_NAME, EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_parent_for_m_k606208_c33_q86",
    )
    if parent.KERNEL_NAME != V2_ARITHMETIC_NAME:
        raise RuntimeError("control-flow parent kernel path drift")
    if parent.EXPECTED_KERNEL_SHA256 != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError("control-flow parent kernel pin drift")
    if parent.EXPECTED_V6_CONFIGURATION_SHA256 != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
        raise RuntimeError("control-flow parent v6 pin drift")
    horizons = {mode: cfg["horizon_checkpoint_count"] for mode, cfg in parent.MODE_CONFIG.items()}
    if horizons != {"magnetization": BASE_PARENT_HORIZON, "double_occupancy": 66}:
        raise RuntimeError("control-flow parent horizon drift")
    if (
        type(parent) is not types.ModuleType
        or type(parent.run_four_gate) is not types.FunctionType
        or parent.run_four_gate.__globals__ is not parent.__dict__
        or parent.run_four_gate.__module__ != parent.__name__
        or parent.run_four_gate.__code__.co_filename != parent.__file__
    ):
        raise RuntimeError("control-flow parent function authority drift")
    parent._M_K606208_EXACT_RUN_FOUR_GATE = parent.run_four_gate
    return parent


def load_configured_v6_baseline(repo: Path) -> Tuple[Any, Tuple[int, ...]]:
    configuration, _ = load_pinned_module(
        repo, V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_for_m_k606208_c33_q86",
    )
    if configuration.POLICY_CAPS_BASE != EXPECTED_V6_POLICY_CAPS:
        raise RuntimeError("v6 policy caps drift")
    if sha256(canonical_bytes(configuration.POLICY_CAPS_BASE)) != EXPECTED_V6_POLICY_CAPS_SHA256:
        raise RuntimeError("v6 policy digest drift")
    baseline_m = tuple(configuration.MODE_CONFIG["magnetization"]["candidates"])
    if sha256(canonical_bytes(list(baseline_m))) != EXPECTED_V6_M_CANDIDATE_SHA256:
        raise RuntimeError("v6 M candidate digest drift")
    if baseline_m != V6_M_CANDIDATES:
        raise RuntimeError("M direct construction from v6 drift")
    before_other = copy.deepcopy(configuration.MODE_CONFIG["double_occupancy"])
    effective = copy.deepcopy(configuration.MODE_CONFIG)
    effective[MODE]["candidates"] = tuple(M_CANDIDATES)
    configuration.MODE_CONFIG = effective
    configuration.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    if configuration.MODE_CONFIG["double_occupancy"] != before_other:
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
    wrapper = types.ModuleType("pinned_m_k606208_c33_arithmetic_wrapper")
    wrapper.__file__ = str(wrapper_path)
    wrapper.__package__ = ""
    wrapper.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = wrapper_payload
    wrapper.__dict__["_VERIFIED_BASE_KERNEL_SOURCE_BYTES"] = v2_payload
    exec(compile(wrapper_payload, wrapper.__file__, "exec"), wrapper.__dict__)
    if wrapper.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_LIMITS:
        raise RuntimeError("wrapped kernel effective limits drift")
    manifest = wrapper.capability_manifest()
    if sha256(canonical_bytes(manifest)) != EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256:
        raise RuntimeError("kernel capability manifest pin drift")
    if wrapper.capability_manifest_sha256() != EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256:
        raise RuntimeError("kernel capability manifest API drift")
    if [item.get("relative_path") for item in manifest.get("source_layers", ())] != [
        KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME,
    ]:
        raise RuntimeError("kernel execution source layers drift")
    if sha256(canonical_bytes(manifest["source_layers"])) != EXPECTED_KERNEL_SOURCE_LAYERS_SHA256:
        raise RuntimeError("kernel execution source-layer digest drift")
    route = manifest.get("route_predecessor_reference")
    if type(route) is not dict:
        raise RuntimeError("kernel route predecessor reference drift")
    if sha256(canonical_bytes(route)) != EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256:
        raise RuntimeError("kernel route predecessor reference digest drift")
    if route.get("source_sha256") != EXPECTED_ROUTE_KERNEL_SHA256:
        raise RuntimeError("kernel route source pin drift")
    if route.get("capability_manifest_sha256") != EXPECTED_ROUTE_KERNEL_MANIFEST_SHA256:
        raise RuntimeError("kernel route manifest pin drift")
    if any(route.get(key) is not False for key in ("compiled", "executed", "execution_source_layer")):
        raise RuntimeError("kernel route predecessor became an execution layer")
    cross_route = manifest.get("cross_route_reference")
    if type(cross_route) is not dict:
        raise RuntimeError("kernel cross-route reference drift")
    if sha256(canonical_bytes(cross_route)) != EXPECTED_KERNEL_CROSS_ROUTE_REFERENCE_SHA256:
        raise RuntimeError("kernel cross-route reference digest drift")
    if cross_route.get("source_sha256") != EXPECTED_CROSS_ROUTE_KERNEL_SHA256:
        raise RuntimeError("kernel cross-route source pin drift")
    if cross_route.get("capability_manifest_sha256") != EXPECTED_CROSS_ROUTE_KERNEL_MANIFEST_SHA256:
        raise RuntimeError("kernel cross-route manifest pin drift")
    if cross_route.get("relationship") != "same_retained_K_different_candidate_count":
        raise RuntimeError("kernel cross-route relationship drift")
    if any(cross_route.get(key) is not False for key in ("compiled", "executed", "execution_source_layer")):
        raise RuntimeError("kernel cross-route reference became an execution layer")
    return wrapper, wrapper_sha, manifest


def load_route_reference(repo: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:

    screen_raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_PREDECESSOR_SCREEN_NAME),
        MAX_PINNED_SOURCE_BYTES,
    )
    if sha256(screen_raw) != EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256:
        raise RuntimeError("route predecessor screen source pin drift")
    raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_PREDECESSOR_TRANSCRIPT_NAME),
        MAX_ROUTE_TRANSCRIPT_BYTES,
    )
    if len(raw) != EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE:
        raise RuntimeError("route predecessor transcript file-size drift")
    if sha256(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256:
        raise RuntimeError("route predecessor transcript pin drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("route predecessor transcript is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("route predecessor transcript is not canonical JSON")
    require_exact_keys(
        transcript,
        EXPECTED_ROUTE_PREDECESSOR_RESULT_KEYS,
        "route M K589824/C32 q86 canonical transcript",
    )
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k589824_c32_q86_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": 86,
        "screen_terminal_condition": (
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        ),
        "attempted_checkpoint_count": 85,
        "completed_checkpoint_count": 84,
        "horizon_checkpoint_attempted": False,
        "horizon_reached_with_committed_checkpoint": False,
        "failure_checkpoint_included": True,
        "failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q85_FAILURE_SHA256,
        "candidate_K_values": list(PREDECESSOR_M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_PREDECESSOR_POLICY_CAPS,
            "max_candidate_count": len(PREDECESSOR_M_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_ROUTE_KERNEL_LIMITS,
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "configuration_reference_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_SHA256
        ),
        "configuration_override_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
        ),
        "kernel_capability_override_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256
        ),
        "parent_horizon_override_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256
        ),
        "route_predecessor_reference_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256
        ),
        "predecessor_handoff_validation_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256
        ),
        "screen_execution_components_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256
        ),
        "checkpoint_transform_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256
        ),
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if not exact_value_equal(transcript.get(key), value):
            raise RuntimeError(f"route predecessor transcript drift: {key}")

    for value_key, digest_key in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("configuration_override", "configuration_override_sha256"),
        ("kernel_capability_override", "kernel_capability_override_sha256"),
        ("parent_horizon_override", "parent_horizon_override_sha256"),
        ("route_predecessor_reference", "route_predecessor_reference_sha256"),
        ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
    ):
        if transcript[digest_key] != sha256(canonical_bytes(transcript[value_key])):
            raise RuntimeError(
                f"route predecessor nested digest drift: {value_key}"
            )

    outer_transform = transcript["checkpoint_transform"]
    if type(outer_transform) is not dict:
        raise RuntimeError("route predecessor transform schema drift")
    raw_transform = outer_transform.get(
        "physical_four_gate_control_flow_parent_transform"
    )
    raw_transform_sha = outer_transform.get(
        "physical_four_gate_control_flow_parent_transform_sha256"
    )
    if raw_transform_sha != EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256:
        raise RuntimeError("route predecessor raw transform authority pin drift")
    if sha256(canonical_bytes(raw_transform)) != raw_transform_sha:
        raise RuntimeError("route predecessor raw transform digest drift")

    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 85:
        raise RuntimeError("route q86 record count drift")
    if type(history) is not list or len(history) != 84:
        raise RuntimeError("route q86 history count drift")
    if sha256(canonical_bytes(records)) != (
        EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256
    ):
        raise RuntimeError("route records digest drift")
    if sha256(canonical_bytes(records[:84])) != (
        EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
    ):
        raise RuntimeError("route q1-84 records digest drift")
    if sha256(canonical_bytes(history)) != (
        EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
    ):
        raise RuntimeError("route history digest drift")
    if sha256(canonical_bytes(records[83])) != (
        EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256
    ):
        raise RuntimeError("route q84 record digest drift")
    if sha256(canonical_bytes(records[84])) != (
        EXPECTED_ROUTE_PREDECESSOR_Q85_FAILURE_SHA256
    ):
        raise RuntimeError("route q85 failure digest drift")

    q84 = records[83]
    for key, value in {
        "checkpoint_number_one_based": 84,
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "pretruncation_expansion_count": 694_130,
        "selected_K": K589824,
        "selected_candidate_index": 31,
        "retained_expansion_count": K589824,
        "retained_expansion_sha256": EXPECTED_Q84_RETAINED_EXPANSION_SHA256,
        "E_after_ticks": EXPECTED_Q84_E_AFTER_TICKS,
    }.items():
        if not exact_value_equal(q84.get(key), value):
            raise RuntimeError(f"route predecessor q84 drift: {key}")

    q85 = records[84]
    require_exact_keys(q85, Q84_FAILURE_RECORD_KEYS, "route q85 failure record")
    q85_rows = q85.get("candidate_records")
    if type(q85_rows) is not list or len(q85_rows) != 32:
        raise RuntimeError("route q85 candidate row count drift")
    if not exact_value_equal(
        [row.get("configured_K") for row in q85_rows],
        list(PREDECESSOR_M_CANDIDATES),
    ):
        raise RuntimeError("route q85 candidate row order drift")
    if any(
        row.get("feasible_under_current_prefix_cap") is not False
        for row in q85_rows
    ):
        raise RuntimeError("route q85 unexpectedly contains a feasible row")
    for key, value in {
        "checkpoint_number_one_based": 85,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "input_expansion_count": K589824,
        "input_expansion_sha256": EXPECTED_Q84_RETAINED_EXPANSION_SHA256,
        "E_before_ticks": EXPECTED_Q84_E_AFTER_TICKS,
        "budget_prefix_cap_ticks": EXPECTED_Q85_PREFIX_CAP_TICKS,
        "pretruncation_expansion_count": 673_356,
        "minimum_effective_K_to_meet_prefix": (
            EXPECTED_Q85_MINIMUM_EFFECTIVE_K
        ),
        "required_K_excess_over_policy_maximum": 2_466,
        "selected_candidate_index": None,
        "selected_K": None,
    }.items():
        if not exact_value_equal(q85.get(key), value):
            raise RuntimeError(f"route predecessor q85 drift: {key}")
    if K606208 - q85["minimum_effective_K_to_meet_prefix"] != (
        EXPECTED_Q85_NEW_POLICY_HEADROOM
    ):
        raise RuntimeError("route q85 new-policy headroom drift")

    reference = {
        "route_id": (
            "magnetization_k589824_c32_q86_to_k606208_c33_q86_v1"
        ),
        "screen": {
            "relative_path": ROUTE_PREDECESSOR_SCREEN_NAME,
            "source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
            "compiled": False,
            "executed": False,
            "execution_source_layer": False,
        },
        "canonical_transcript": {
            "relative_path": ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "file_size_bytes": EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE,
            "file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
            "q1_through_q84_records_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
            ),
            "selected_K_history_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
            ),
            "q84_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256,
            "q85_failure_record_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_Q85_FAILURE_SHA256
            ),
            "compiled": False,
            "executed": False,
            "loaded_before_replay_as_exact_reference": False,
            "loaded_after_replay_as_exact_reference": True,
            "used_only_after_replay_for_result_prefix_validation": True,
            "post_replay_prefix_validation_input": True,
            "propagation_input": False,
            "checkpoint_84_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
        "incremental_semantic_delta": {
            "candidate_K_values_changed": True,
            "policy_caps_changed": True,
            "kernel_capability_limits_changed": True,
            "horizon_checkpoint_count": {"before": 86, "after": 86},
        },
    }
    return transcript, reference

def configure_parent_execution(parent: Any, configuration: Any, kernel: Any) -> Dict[str, Any]:
    before = copy.deepcopy(parent.MODE_CONFIG)
    after = copy.deepcopy(before)
    after[MODE]["horizon_checkpoint_count"] = EXTENDED_HORIZON
    changed = []
    for mode, before_mode in before.items():
        for key, value in before_mode.items():
            if after[mode].get(key) != value:
                changed.append(f"MODE_CONFIG.{mode}.{key}")
    expected = [f"MODE_CONFIG.{MODE}.horizon_checkpoint_count"]
    if changed != expected:
        raise RuntimeError("parent configuration changed outside M horizon")
    if after["double_occupancy"] != before["double_occupancy"]:
        raise RuntimeError("parent double-occupancy configuration changed")
    parent.MODE_CONFIG = after
    original = parent.load_execution_sources
    parent.load_v6_configuration = lambda _repo: configuration

    def wrapped(source_repo, helper, mode):
        base_kernel, root, modules, custody = original(source_repo, helper, mode)
        if base_kernel.RESOURCE_LIMITS != EXPECTED_V2_KERNEL_LIMITS:
            raise RuntimeError("v2 arithmetic limits drift")
        if kernel.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_LIMITS:
            raise RuntimeError("wrapped arithmetic limits drift")
        return kernel, root, modules, custody

    parent.load_execution_sources = wrapped
    return {
        "override_id": "magnetization_parent_q86_horizon_override_v1",
        "parent_relative_path": CONTROL_FLOW_PARENT_NAME,
        "parent_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "parent_module_isolated": True,
        "parent_source_bytes_changed": False,
        "changed_fields": expected,
        "semantic_delta": {expected[0]: {"before": BASE_PARENT_HORIZON, "after": EXTENDED_HORIZON}},
        "parent_mode_config_before": before,
        "parent_mode_config_before_sha256": sha256(canonical_bytes(before)),
        "parent_mode_config_after": after,
        "parent_mode_config_after_sha256": sha256(canonical_bytes(after)),
        "double_occupancy_configuration_unchanged": True,
    }


def normalize_completed_parent_result(result: Any) -> Dict[str, Any]:

    require_exact_keys(
        result,
        UPSTREAM_PARENT_RESULT_KEYS,
        "M q86 completed upstream parent result",
    )
    result = dict(result)
    result["resource_policy_abort"] = None
    result["resource_policy_abort_sha256"] = None
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "M q86 normalized parent result",
    )
    return result


def _traceback_items(exception: BaseException) -> list[Any]:
    items = []
    item = exception.__traceback__
    while item is not None:
        items.append(item)
        item = item.tb_next
    return items


def _require_abort_parent_authority(parent: Any) -> types.FunctionType:
    expected_run_four_gate = getattr(
        parent, "_M_K606208_EXACT_RUN_FOUR_GATE", None
    )
    if (
        type(parent) is not types.ModuleType
        or type(getattr(parent, "_VERIFIED_SELF_SOURCE_BYTES", None))
        is not bytes
        or sha256(parent._VERIFIED_SELF_SOURCE_BYTES)
        != EXPECTED_CONTROL_FLOW_PARENT_SHA256
        or type(expected_run_four_gate) is not types.FunctionType
        or parent.run_four_gate is not expected_run_four_gate
        or expected_run_four_gate.__globals__ is not parent.__dict__
        or expected_run_four_gate.__module__ != parent.__name__
        or expected_run_four_gate.__code__.co_filename != parent.__file__
    ):
        raise RuntimeError("M q86 abort parent same-byte identity drift")
    return expected_run_four_gate


def _exact_kernel_overflow_count(
    kernel: Any,
    counter: Any,
    traceback_items: list[Any],
) -> int:
    observe_count = kernel.PropagationCounterV2.observe_count
    expected_tail = [
        kernel.propagate_batch.__code__,
        kernel.propagate_gate.__code__,
        kernel.add_tick_term.__code__,
        observe_count.__code__,
    ]
    observed_tail = [item.tb_frame.f_code for item in traceback_items[-4:]]
    add_item = traceback_items[-2]
    deepest = traceback_items[-1]
    if (
        observed_tail != expected_tail
        or add_item.tb_lineno != 237
        or frozenset(add_item.tb_frame.f_locals)
        != frozenset({"output", "key", "value", "counter"})
        or deepest.tb_lineno != 162
        or frozenset(deepest.tb_frame.f_locals)
        != frozenset({"self", "count"})
    ):
        raise RuntimeError("M q86 kernel abort traceback/local schema drift")
    add_local = add_item.tb_frame.f_locals
    deepest_local = deepest.tb_frame.f_locals
    count = deepest_local["count"]
    if (
        deepest_local["self"] is not counter
        or type(count) is not int
        or add_local["counter"] is not counter
        or type(add_local["output"]) is not dict
        or len(add_local["output"]) != count
    ):
        raise RuntimeError("M q86 kernel abort counter identity drift")
    return count


def build_resource_abort_parent_result(
    parent: Any,
    kernel: Any,
    exception: BaseException,
) -> Dict[str, Any]:

    expected_run_four_gate = _require_abort_parent_authority(parent)
    traceback_items = _traceback_items(exception)
    run_items = [
        item
        for item in traceback_items
        if item.tb_frame.f_code is expected_run_four_gate.__code__
    ]
    if len(run_items) != 1:
        raise RuntimeError("M q86 abort parent traceback authority drift")
    run_item = run_items[0]
    local = run_item.tb_frame.f_locals
    required_locals = {
        "mode",
        "v6_configuration",
        "kernel",
        "root",
        "source_custody",
        "root_before",
        "boundary_custody",
        "sequence",
        "transform",
        "helper_config",
        "candidates",
        "caps",
        "counter",
        "E_input",
        "cumulative",
        "remaining_steps",
        "denominator",
        "horizon",
        "records",
        "selected_history",
        "failure",
        "horizon_reached",
        "gate_index",
        "stage_index",
        "stage",
        "batch_start",
        "checkpoint_index",
        "checkpoint_number",
        "batch",
        "input_count",
        "input_sha",
        "visits_before",
        "rounding_before",
    }
    if not required_locals <= set(local):
        raise RuntimeError("M q86 abort parent frame local schema drift")
    if local.get("kernel") is not kernel:
        raise RuntimeError("M q86 abort kernel identity drift")

    helper = local.get("helper")
    enforce_policy_caps = getattr(helper, "enforce_policy_caps", None)
    if (
        type(helper) is not types.ModuleType
        or type(getattr(helper, "_VERIFIED_SELF_SOURCE_BYTES", None))
        is not bytes
        or sha256(helper._VERIFIED_SELF_SOURCE_BYTES)
        != EXPECTED_V2_HELPER_SHA256
        or type(enforce_policy_caps) is not types.FunctionType
        or enforce_policy_caps.__globals__ is not helper.__dict__
        or enforce_policy_caps.__module__ != helper.__name__
        or enforce_policy_caps.__code__.co_filename != helper.__file__
    ):
        raise RuntimeError("M q86 abort helper authority drift")

    records = local["records"]
    history = local["selected_history"]
    candidates = local["candidates"]
    caps = local["caps"]
    counter = local["counter"]
    if local["mode"] != MODE:
        raise RuntimeError("M q86 abort mode drift")
    for label, value in {
        "checkpoint index": local["checkpoint_index"],
        "checkpoint number": local["checkpoint_number"],
        "input count": local["input_count"],
        "visits before": local["visits_before"],
        "rounding before": local["rounding_before"],
        "gate index": local["gate_index"],
    }.items():
        if type(value) is not int or value < 0:
            raise RuntimeError(f"M q86 abort {label} type drift")
    if (
        local["checkpoint_index"] != 85
        or local["checkpoint_number"] != 86
        or local["horizon"] != EXTENDED_HORIZON
        or type(records) is not list
        or len(records) != 85
        or type(history) is not list
        or len(history) != 85
        or local["failure"] is not None
        or local["horizon_reached"] is not False
        or local["gate_index"] != 340
    ):
        raise RuntimeError("M q86 abort checkpoint boundary drift")
    q85 = records[-1]
    require_exact_keys(q85, Q84_SUCCESS_RECORD_KEYS, "M q86 abort q85 success")
    if (
        q85.get("checkpoint_number_one_based") != 85
        or q85.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
        or type(q85.get("selected_candidate_index")) is not int
        or q85["selected_candidate_index"] != 32
        or type(q85.get("selected_K")) is not int
        or q85["selected_K"] != K606208
        or q85.get("retained_expansion_count") != K606208
        or history[-1] != K606208
    ):
        raise RuntimeError("M q86 abort q85 committed-success drift")
    if tuple(candidates) != M_CANDIDATES:
        raise RuntimeError("M q86 abort candidate ladder drift")
    expected_caps = {
        **POLICY_CAPS_BASE,
        "max_candidate_count": len(M_CANDIDATES),
    }
    if not exact_value_equal(caps, expected_caps):
        raise RuntimeError("M q86 abort policy caps drift")
    if kernel.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_LIMITS:
        raise RuntimeError("M q86 abort kernel limits drift")

    batch = local["batch"]
    stage = local["stage"]
    if type(batch) is not list or len(batch) != 4 or type(stage) is not dict:
        raise RuntimeError("M q86 abort gate batch schema drift")
    anchor = EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[86]
    observed_anchor = {
        "stage_index": local["stage_index"],
        "stage_group": stage.get("group"),
        "batch_in_stage": local["batch_start"] // 4,
        "gate_batch_sha256": helper.gate_batch_sha256(batch),
    }
    if not exact_value_equal(observed_anchor, anchor):
        raise RuntimeError("M q86 abort checkpoint anchor drift")
    if local["input_count"] != q85.get("retained_expansion_count"):
        raise RuntimeError("M q86 abort q85-to-q86 count continuity drift")
    if local["input_sha"] != q85.get("retained_expansion_sha256"):
        raise RuntimeError("M q86 abort q85-to-q86 digest continuity drift")

    policy_cap = caps["max_single_expansion_terms"]
    kernel_cap = kernel.RESOURCE_LIMITS["max_single_expansion_terms"]
    pre_count = None
    observed_count = None
    propagation_completed = None
    policy_check_reached = None
    kernel_violation_triggered = None
    snapshot_available = None
    exception_source_role = None
    chained_from_helper = None
    abort_kind = None
    local_schema_id = None
    policy_relation = None
    enforced_cap = None

    helper_messages = {
        "design policy live-term cap exceeded": (
            "final_live_terms",
            301,
            frozenset({"kernel", "counter", "term_count", "caps"}),
        ),
        "design policy transient live-term cap exceeded": (
            "transient_live_terms",
            313,
            frozenset({
                "kernel", "counter", "term_count", "caps",
                "checks", "key", "observed",
            }),
        ),
    }
    if type(exception) is RuntimeError and exception.args in (
        ("design policy live-term cap exceeded",),
        ("design policy transient live-term cap exceeded",),
    ):
        message = exception.args[0]
        abort_kind, helper_line, expected_helper_locals = helper_messages[message]
        helper_items = [
            item
            for item in traceback_items
            if item.tb_frame.f_code is enforce_policy_caps.__code__
        ]
        if (
            len(helper_items) != 1
            or traceback_items[-1] is not helper_items[0]
            or run_item.tb_lineno != 589
            or helper_items[0].tb_lineno != helper_line
            or frozenset(helper_items[0].tb_frame.f_locals)
            != expected_helper_locals
        ):
            raise RuntimeError("M q86 helper abort traceback/local schema drift")
        helper_local = helper_items[0].tb_frame.f_locals
        if (
            helper_local["kernel"] is not kernel
            or helper_local["counter"] is not counter
            or helper_local["caps"] is not caps
            or type(helper_local["term_count"]) is not int
            or helper_local["term_count"] < 0
        ):
            raise RuntimeError("M q86 helper abort argument identity drift")
        pre_count = helper_local["term_count"]
        if (
            type(local.get("pre_count")) is not int
            or local["pre_count"] != pre_count
            or type(local.get("expansion")) is not dict
            or len(local["expansion"]) != pre_count
        ):
            raise RuntimeError("M q86 helper abort pretruncation binding drift")
        propagation_completed = True
        policy_check_reached = True
        kernel_violation_triggered = False
        snapshot_available = True
        exception_source_role = "exact_parent_helper"
        chained_from_helper = True
        enforced_cap = policy_cap
        if abort_kind == "final_live_terms":
            observed_count = pre_count
            local_schema_id = "helper_final_live_terms_v1"
            policy_relation = (
                "pretruncation_expansion_count>"
                "policy_max_single_expansion_terms"
            )
            if not pre_count > policy_cap:
                raise RuntimeError("M q86 final-live abort cap relation drift")
        else:
            observed_count = counter.window_peak_live_terms
            local_schema_id = "helper_transient_live_terms_v1"
            policy_relation = (
                "peak_live_terms_this_checkpoint>"
                "policy_max_single_expansion_terms>="
                "pretruncation_expansion_count"
            )
            if not (
                pre_count <= policy_cap
                and observed_count > policy_cap
            ):
                raise RuntimeError("M q86 transient-live abort cap relation drift")
    elif (
        type(exception) is getattr(kernel, "SchemaError", None)
        and exception.args == ("v2 single-expansion term cap exceeded",)
    ):
        if run_item.tb_lineno != 587:
            raise RuntimeError("M q86 kernel abort parent line drift")
        observed_count = _exact_kernel_overflow_count(
            kernel,
            counter,
            traceback_items,
        )
        if observed_count <= kernel_cap:
            raise RuntimeError("M q86 kernel abort cap relation drift")
        if local.get("pre_count") != q85["pretruncation_expansion_count"]:
            raise RuntimeError("M q86 kernel abort stale pre_count binding drift")
        pre_count = None
        propagation_completed = False
        policy_check_reached = False
        kernel_violation_triggered = True
        snapshot_available = False
        exception_source_role = "exact_wrapped_v2_kernel"
        chained_from_helper = False
        abort_kind = "kernel_single_expansion_terms"
        local_schema_id = "kernel_observe_count_before_pre_count_assignment_v1"
        policy_relation = (
            "observed_term_count>kernel_max_single_expansion_terms_"
            "before_pretruncation_assignment"
        )
        enforced_cap = kernel_cap
    else:
        raise RuntimeError("M q86 resource abort exception identity drift")

    if (
        type(observed_count) is not int
        or observed_count <= enforced_cap
        or counter.peak_live_terms < observed_count
        or counter.window_peak_live_terms < observed_count
        or (
            abort_kind != "kernel_single_expansion_terms"
            and observed_count > kernel_cap
        )
    ):
        raise RuntimeError("M q86 abort observed live-term ledger drift")

    root_after = kernel.root_global_snapshot(local["root"])
    if not exact_value_equal(local["root_before"], root_after):
        raise RuntimeError("M q86 abort changed root arithmetic globals")
    q85_sha = sha256(canonical_bytes(q85))
    message = exception.args[0]
    abort = {
        "schema_version": 1,
        "abort_id": "M_k606208_c33_q86_policy_resource_abort_v1",
        "abort_kind": abort_kind,
        "abort_frame_local_schema_id": local_schema_id,
        "exception_type": type(exception).__name__,
        "exception_message": message,
        "exception_args": [message],
        "exception_source_role": exception_source_role,
        "exception_chained_from_exact_parent_helper": chained_from_helper,
        "control_flow_parent_source_sha256": (
            EXPECTED_CONTROL_FLOW_PARENT_SHA256
        ),
        "helper_source_sha256": EXPECTED_V2_HELPER_SHA256,
        "kernel_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "checkpoint_index_zero_based": 85,
        "checkpoint_number_one_based": 86,
        "stage_index": local["stage_index"],
        "stage_group": stage["group"],
        "batch_in_stage": local["batch_start"] // 4,
        "gate_occurrence_first_zero_based": local["gate_index"],
        "gate_occurrence_last_zero_based": local["gate_index"] + 3,
        "gate_batch_sha256": helper.gate_batch_sha256(batch),
        "input_expansion_count": local["input_count"],
        "input_expansion_sha256": local["input_sha"],
        "pretruncation_expansion_count": pre_count,
        "observed_term_count": observed_count,
        "policy_max_single_expansion_terms": policy_cap,
        "kernel_max_single_expansion_terms": kernel_cap,
        "enforced_term_cap": enforced_cap,
        "observed_excess_terms": observed_count - enforced_cap,
        "policy_relation": policy_relation,
        "gate_batch_propagation_started": True,
        "gate_batch_propagation_completed": propagation_completed,
        "policy_cap_check_reached": policy_check_reached,
        "kernel_cap_violation_triggered": kernel_violation_triggered,
        "live_expansion_snapshot_available": snapshot_available,
        "q86_pretruncation_digest_computed": False,
        "q86_ranking_performed": False,
        "q86_candidate_rows_constructed": False,
        "q86_selection_performed": False,
        "q86_commit_performed": False,
        "q86_checkpoint_record_constructed": False,
        "q86_partial_expansion_committed": False,
        "q85_committed_record_sha256": q85_sha,
        "peak_live_terms_this_checkpoint": counter.window_peak_live_terms,
        "peak_live_terms_cumulative": counter.peak_live_terms,
        "term_gate_visits_increment": (
            counter.term_gate_visits - local["visits_before"]
        ),
        "term_gate_visits_cumulative": counter.term_gate_visits,
        "rounding_increment_scaled_ticks_squared": str(
            counter.multiplication_rounding_l1_scaled_ticks_squared
            - local["rounding_before"]
        ),
        "rounding_cumulative_scaled_ticks_squared": str(
            counter.multiplication_rounding_l1_scaled_ticks_squared
        ),
        "maximum_expansion_coefficient_tick_bits": (
            counter.maximum_expansion_coefficient_tick_bits
        ),
        "maximum_product_bits": counter.maximum_product_bits,
    }
    require_exact_keys(
        abort,
        RESOURCE_POLICY_ABORT_KEYS,
        "M q86 resource-policy abort",
    )

    raw_parent_sha = sha256(parent._VERIFIED_SELF_SOURCE_BYTES)
    components = parent.execution_components(
        MODE,
        raw_parent_sha,
        local["source_custody"],
        local["boundary_custody"],
    )
    candidate_sha = sha256(canonical_bytes(list(candidates)))
    configuration_reference = {
        "relative_path": parent.V6_CONFIGURATION_NAME,
        "source_sha256": parent.EXPECTED_V6_CONFIGURATION_SHA256,
        "role": "candidates_and_caps_reference_only",
        "fields_adopted": [
            f"MODE_CONFIG.{MODE}.candidates",
            "POLICY_CAPS_BASE",
        ],
        "candidate_K_values_sha256": candidate_sha,
        "policy_caps_base_sha256": parent.EXPECTED_V6_CAPS_SHA256,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }
    records_copy = copy.deepcopy(records)
    history_copy = list(history)
    result = {
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
        "observable_id": local["helper_config"]["observable_id"],
        "input_step_index": local["helper_config"]["input_step_index"],
        "attempted_child_step_index": local["helper_config"][
            "child_step_index"
        ],
        "screen_source_sha256": raw_parent_sha,
        "same_byte_self_execution": True,
        "v2_helper_source_sha256": parent.EXPECTED_V2_HELPER_SHA256,
        "v2_helper_compiled_from_verified_bytes": True,
        "v2_helper_module_isolated": True,
        "v2_run_entrypoint_called": False,
        "v6_configuration_source_sha256": (
            parent.EXPECTED_V6_CONFIGURATION_SHA256
        ),
        "v6_configuration_compiled_from_verified_bytes": True,
        "v6_configuration_module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "control_flow_owned_by_screen": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(
            canonical_bytes(components)
        ),
        "configuration_reference": configuration_reference,
        "configuration_reference_sha256": sha256(
            canonical_bytes(configuration_reference)
        ),
        "checkpoint_transform": copy.deepcopy(local["transform"]),
        "checkpoint_transform_sha256": sha256(
            canonical_bytes(local["transform"])
        ),
        "arithmetic_kernel_commit": helper.KERNEL_COMMIT,
        "source_custody": {
            parent.V2_HELPER_NAME: parent.EXPECTED_V2_HELPER_SHA256,
            parent.V6_CONFIGURATION_NAME: (
                parent.EXPECTED_V6_CONFIGURATION_SHA256
            ),
            **local["source_custody"],
        },
        "parent_expected_witness_sha256": local["helper_config"][
            "parent_expected_witness_sha256"
        ],
        "input_boundary_custody": copy.deepcopy(local["boundary_custody"]),
        "input_cumulative_drop_ticks": str(local["E_input"]),
        "maximum_cumulative_drop_ticks": str(helper.MAXIMUM_DROP_TICKS),
        "remaining_mapped_steps_including_attempt": local["remaining_steps"],
        "future_checkpoint_denominator": local["denominator"],
        "prefix_cap_formula": (
            f"E{local['helper_config']['input_step_index']}+floor(q*(B-"
            f"E{local['helper_config']['input_step_index']})/("
            f"{local['remaining_steps']}*{parent.CHECKPOINTS_PER_MAPPED_STEP}))"
        ),
        "candidate_K_values": list(candidates),
        "candidate_K_values_sha256": candidate_sha,
        "candidate_policy_precommitted_at_probe_time": False,
        "selection_rule": (
            "first_candidate_whose_exact_ranked_suffix_drop_respects_"
            "current_prefix_cap"
        ),
        "single_propagation_and_single_ranking_per_checkpoint": True,
        "sequence": copy.deepcopy(local["sequence"]),
        "screen_horizon_checkpoint_count": local["horizon"],
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": False,
        "kernel_capability_limits": dict(kernel.RESOURCE_LIMITS),
        "proposed_policy_caps": dict(caps),
        "root_globals_before": copy.deepcopy(local["root_before"]),
        "root_globals_after": root_after,
        "root_globals_unchanged": True,
        "attempted_checkpoint_count": 86,
        "completed_checkpoint_count": 85,
        "failure_checkpoint_included": False,
        "selected_K_history": history_copy,
        "selected_K_history_sha256": sha256(canonical_bytes(history_copy)),
        "records": records_copy,
        "records_sha256": sha256(canonical_bytes(records_copy)),
        "failure_record_sha256": None,
        "last_committed_cumulative_drop_ticks": str(local["cumulative"]),
        "observed_peak_single_expansion_terms": (
            abort["peak_live_terms_cumulative"]
        ),
        "observed_term_gate_visits_including_terminal_attempt": (
            abort["term_gate_visits_cumulative"]
        ),
        "observed_maximum_expansion_coefficient_tick_bits": (
            abort["maximum_expansion_coefficient_tick_bits"]
        ),
        "observed_maximum_product_bits": abort["maximum_product_bits"],
        "observed_rounding_cumulative_scaled_ticks_squared": abort[
            "rounding_cumulative_scaled_ticks_squared"
        ],
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
        "runtime_RSS_host_timestamp_and_float_fields_excluded": True,
        "resource_policy_abort": abort,
        "resource_policy_abort_sha256": sha256(canonical_bytes(abort)),
    }
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "M q86 structured resource-abort parent result",
    )
    return result


def execute_parent_with_structured_abort(
    parent: Any,
    kernel: Any,
    repo: Path,
) -> Dict[str, Any]:

    try:
        return normalize_completed_parent_result(
            parent._run_verified(repo, MODE)
        )
    except RuntimeError as exception:
        if type(exception) is not RuntimeError or exception.args not in (
            ("design policy live-term cap exceeded",),
            ("design policy transient live-term cap exceeded",),
        ):
            raise
        return build_resource_abort_parent_result(parent, kernel, exception)
    except Exception as exception:
        if (
            type(exception) is not getattr(kernel, "SchemaError", None)
            or exception.args != ("v2 single-expansion term cap exceeded",)
        ):
            raise
        return build_resource_abort_parent_result(parent, kernel, exception)

def is_canonical_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def parse_canonical_nonnegative_decimal(value: Any, label: str) -> int:
    if type(value) is not str or not value:
        raise RuntimeError(f"{label} is not a canonical decimal string")
    if any(character not in "0123456789" for character in value):
        raise RuntimeError(f"{label} is not a canonical decimal string")
    if len(value) > 1 and value[0] == "0":
        raise RuntimeError(f"{label} is not a canonical decimal string")
    return int(value)


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


def validate_parent_source_custody(value: Any) -> Dict[str, str]:
    require_exact_keys(
        value,
        frozenset(EXPECTED_PARENT_SOURCE_CUSTODY),
        "M q86 raw parent source custody",
    )
    for path, expected_sha in EXPECTED_PARENT_SOURCE_CUSTODY.items():
        observed_sha = value.get(path)
        if observed_sha != expected_sha:
            raise RuntimeError(
                f"M q86 raw parent source custody hash drift: {path}"
            )
        if not is_canonical_sha256(observed_sha):
            raise RuntimeError(
                f"M q86 raw parent source custody digest schema drift: {path}"
            )
    return dict(value)


def expected_final_source_custody(
    self_sha: str,
    wrapper_sha: str,
) -> Dict[str, str]:
    if not is_canonical_sha256(self_sha):
        raise RuntimeError("M q86 self custody digest schema drift")
    if wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError("M q86 wrapper custody digest drift")
    return {
        **EXPECTED_PARENT_SOURCE_CUSTODY,
        SELF_NAME: self_sha,
        CONTROL_FLOW_PARENT_NAME: EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        KERNEL_WRAPPER_NAME: wrapper_sha,
    }


def validate_extended_record(
    record: Mapping[str, Any],
    previous: Mapping[str, Any],
    checkpoint: int,
) -> int | None:
    if type(record) is not dict or type(previous) is not dict:
        raise RuntimeError(f"M q{checkpoint} record continuity type drift")
    status = record.get("status")
    if status == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        expected_keys = Q84_SUCCESS_RECORD_KEYS
    elif status == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE":
        expected_keys = Q84_FAILURE_RECORD_KEYS
    else:
        raise RuntimeError(f"M q{checkpoint} status drift")
    require_exact_keys(record, expected_keys, f"M q{checkpoint} record")
    expected_scalars = {
        "checkpoint_index_zero_based": checkpoint - 1,
        "checkpoint_number_one_based": checkpoint,
        "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
        "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
        "input_expansion_count": previous["retained_expansion_count"],
        "input_expansion_sha256": previous["retained_expansion_sha256"],
        "E_before_ticks": previous["E_after_ticks"],
        "budget_prefix_cap_ticks": (
            EXPECTED_Q85_PREFIX_CAP_TICKS
            if checkpoint == 85
            else EXPECTED_Q86_PREFIX_CAP_TICKS
        ),
        **EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
    }
    for field, value in expected_scalars.items():
        if not exact_value_equal(record.get(field), value):
            raise RuntimeError(f"M q{checkpoint} exact ledger drift: {field}")
    for field in (
        "gate_batch_sha256",
        "input_expansion_sha256",
        "pretruncation_expansion_sha256",
        "ranked_suffix_sha256",
    ):
        if not is_canonical_sha256(record.get(field)):
            raise RuntimeError(f"M q{checkpoint} digest schema drift: {field}")
    integer_fields = (
        "input_expansion_count",
        "pretruncation_expansion_count",
        "peak_live_terms_this_checkpoint",
        "peak_live_terms_cumulative",
        "term_gate_visits_increment",
        "term_gate_visits_cumulative",
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    )
    for field in integer_fields:
        if type(record.get(field)) is not int or record[field] < 0:
            raise RuntimeError(f"M q{checkpoint} integer ledger drift: {field}")
    pre_count = record["pretruncation_expansion_count"]
    if pre_count > min(
        POLICY_CAPS_BASE["max_single_expansion_terms"],
        POLICY_CAPS_BASE["max_digest_terms"],
    ):
        raise RuntimeError(f"M q{checkpoint} pretruncation cap exceeded")
    if record["peak_live_terms_this_checkpoint"] < max(
        record["input_expansion_count"], pre_count
    ):
        raise RuntimeError(f"M q{checkpoint} checkpoint peak below live terms")
    if record["peak_live_terms_this_checkpoint"] > POLICY_CAPS_BASE[
        "max_single_expansion_terms"
    ]:
        raise RuntimeError(f"M q{checkpoint} checkpoint peak cap exceeded")
    if record["term_gate_visits_increment"] < record["input_expansion_count"]:
        raise RuntimeError(f"M q{checkpoint} visit increment below input")
    if record["term_gate_visits_cumulative"] > POLICY_CAPS_BASE[
        "max_term_gate_visits"
    ]:
        raise RuntimeError(f"M q{checkpoint} visit cap exceeded")

    E_before = parse_canonical_nonnegative_decimal(
        record["E_before_ticks"], f"M q{checkpoint} E-before"
    )
    prefix_cap = parse_canonical_nonnegative_decimal(
        record["budget_prefix_cap_ticks"], f"M q{checkpoint} prefix cap"
    )
    slack = parse_canonical_nonnegative_decimal(
        record["prefix_slack_before_selection_ticks"],
        f"M q{checkpoint} prefix slack",
    )
    if slack != prefix_cap - E_before:
        raise RuntimeError(f"M q{checkpoint} prefix slack recurrence drift")
    rounding_increment = parse_canonical_nonnegative_decimal(
        record["rounding_increment_scaled_ticks_squared"],
        f"M q{checkpoint} rounding increment",
    )
    rounding_cumulative = parse_canonical_nonnegative_decimal(
        record["rounding_cumulative_scaled_ticks_squared"],
        f"M q{checkpoint} rounding cumulative",
    )
    previous_rounding = parse_canonical_nonnegative_decimal(
        previous["rounding_cumulative_scaled_ticks_squared"],
        f"M q{checkpoint - 1} rounding cumulative",
    )
    if rounding_cumulative != previous_rounding + rounding_increment:
        raise RuntimeError(f"M q{checkpoint} rounding recurrence drift")
    if record["term_gate_visits_cumulative"] != (
        previous["term_gate_visits_cumulative"]
        + record["term_gate_visits_increment"]
    ):
        raise RuntimeError(f"M q{checkpoint} visit recurrence drift")
    if record["peak_live_terms_cumulative"] != max(
        previous["peak_live_terms_cumulative"],
        record["peak_live_terms_this_checkpoint"],
    ):
        raise RuntimeError(f"M q{checkpoint} peak recurrence drift")
    for field, policy_field in (
        (
            "maximum_expansion_coefficient_tick_bits",
            "max_expansion_coefficient_tick_bits",
        ),
        ("maximum_product_bits", "max_product_bits"),
    ):
        if record[field] < previous[field]:
            raise RuntimeError(f"M q{checkpoint} cumulative maximum decreased: {field}")
        if record[field] > POLICY_CAPS_BASE[policy_field]:
            raise RuntimeError(f"M q{checkpoint} cumulative maximum cap exceeded: {field}")

    rows = record.get("candidate_records")
    if type(rows) is not list or len(rows) != len(M_CANDIDATES):
        raise RuntimeError(f"M q{checkpoint} candidate row count drift")
    feasible_indices = []
    drops = []
    for candidate_index, (configured_K, row) in enumerate(
        zip(M_CANDIDATES, rows)
    ):
        require_exact_keys(
            row,
            CANDIDATE_RECORD_KEYS,
            f"M q{checkpoint} candidate row {candidate_index}",
        )
        effective = min(configured_K, pre_count)
        expected = {
            "candidate_index": candidate_index,
            "configured_K": configured_K,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }
        for field, value in expected.items():
            if not exact_value_equal(row.get(field), value):
                raise RuntimeError(
                    f"M q{checkpoint} candidate row drift: {field}"
                )
        drop = parse_canonical_nonnegative_decimal(
            row["drop_ticks"],
            f"M q{checkpoint} candidate {candidate_index} drop",
        )
        if (row["dropped_term_count"] == 0) is not (drop == 0):
            raise RuntimeError(
                f"M q{checkpoint} dropped-count/drop zero equivalence drift"
            )
        E_after = parse_canonical_nonnegative_decimal(
            row["E_after_if_selected_ticks"],
            f"M q{checkpoint} candidate {candidate_index} E-after",
        )
        if E_after != E_before + drop:
            raise RuntimeError(f"M q{checkpoint} candidate E recurrence drift")
        feasible = E_after <= prefix_cap
        if row.get("feasible_under_current_prefix_cap") is not feasible:
            raise RuntimeError(f"M q{checkpoint} candidate feasibility drift")
        drops.append(drop)
        if feasible:
            feasible_indices.append(candidate_index)
    if drops != sorted(drops, reverse=True):
        raise RuntimeError(f"M q{checkpoint} candidate drop ranking drift")

    if status == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        if not feasible_indices:
            raise RuntimeError(f"M q{checkpoint} success has no feasible row")
        selected_index = feasible_indices[0]
        if feasible_indices != list(range(selected_index, len(M_CANDIDATES))):
            raise RuntimeError(f"M q{checkpoint} feasible rows are not a suffix")
        selected_row = rows[selected_index]
        expected_selection = {
            "selected_candidate_index": selected_index,
            "selected_K": selected_row["configured_K"],
            "selected_effective_retained_count": selected_row[
                "effective_retained_count"
            ],
            "selected_dropped_term_count": selected_row["dropped_term_count"],
            "selected_drop_ticks": selected_row["drop_ticks"],
            "retained_expansion_count": selected_row["effective_retained_count"],
            "E_after_ticks": selected_row["E_after_if_selected_ticks"],
        }
        for field, value in expected_selection.items():
            if not exact_value_equal(record.get(field), value):
                raise RuntimeError(f"M q{checkpoint} first-feasible drift: {field}")
        for field in (
            "selected_dropped_terms_sha256",
            "retained_expansion_sha256",
        ):
            if not is_canonical_sha256(record.get(field)):
                raise RuntimeError(f"M q{checkpoint} success digest drift: {field}")
        minimum_retained = parse_canonical_nonnegative_decimal(
            record["minimum_retained_abs_upper_ticks"],
            f"M q{checkpoint} minimum retained",
        )
        maximum_dropped = parse_canonical_nonnegative_decimal(
            record["maximum_dropped_abs_upper_ticks"],
            f"M q{checkpoint} maximum dropped",
        )
        if minimum_retained < maximum_dropped:
            raise RuntimeError(f"M q{checkpoint} ranked boundary order drift")
        return record["selected_K"]

    if feasible_indices:
        raise RuntimeError(f"M q{checkpoint} failure contains a feasible row")
    if record.get("selected_candidate_index") is not None:
        raise RuntimeError(f"M q{checkpoint} failure selected an index")
    if record.get("selected_K") is not None:
        raise RuntimeError(f"M q{checkpoint} failure selected K")
    minimum_K = record.get("minimum_effective_K_to_meet_prefix")
    excess = record.get("required_K_excess_over_policy_maximum")
    if type(minimum_K) is not int or type(excess) is not int:
        raise RuntimeError(f"M q{checkpoint} failure minimum-K type drift")
    if (
        minimum_K <= K606208
        or minimum_K > pre_count
        or excess != minimum_K - K606208
    ):
        raise RuntimeError(f"M q{checkpoint} failure excess-K drift")
    maximum_excess = parse_canonical_nonnegative_decimal(
        record["maximum_candidate_drop_excess_over_slack_ticks"],
        f"M q{checkpoint} failure maximum excess",
    )
    if maximum_excess != drops[-1] - slack or maximum_excess <= 0:
        raise RuntimeError(f"M q{checkpoint} failure cap excess drift")
    return None



def validate_resource_policy_abort(
    result: Mapping[str, Any],
    q85: Mapping[str, Any],
) -> Dict[str, Any] | None:
    abort = result.get("resource_policy_abort")
    abort_sha = result.get("resource_policy_abort_sha256")
    if abort is None:
        if abort_sha is not None:
            raise RuntimeError("M q86 null resource abort has a digest")
        return None
    require_exact_keys(
        abort,
        RESOURCE_POLICY_ABORT_KEYS,
        "M q86 resource-policy abort",
    )
    if abort_sha != sha256(canonical_bytes(abort)):
        raise RuntimeError("M q86 resource-policy abort digest drift")
    require_exact_keys(q85, Q84_SUCCESS_RECORD_KEYS, "M q86 abort q85 success")
    expected = {
        "schema_version": 1,
        "abort_id": "M_k606208_c33_q86_policy_resource_abort_v1",
        "control_flow_parent_source_sha256": (
            EXPECTED_CONTROL_FLOW_PARENT_SHA256
        ),
        "helper_source_sha256": EXPECTED_V2_HELPER_SHA256,
        "kernel_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "checkpoint_index_zero_based": 85,
        "checkpoint_number_one_based": 86,
        "gate_occurrence_first_zero_based": 340,
        "gate_occurrence_last_zero_based": 343,
        **EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[86],
        "policy_max_single_expansion_terms": POLICY_CAPS_BASE[
            "max_single_expansion_terms"
        ],
        "kernel_max_single_expansion_terms": EXPECTED_WRAPPED_KERNEL_LIMITS[
            "max_single_expansion_terms"
        ],
        "gate_batch_propagation_started": True,
        "q86_pretruncation_digest_computed": False,
        "q86_ranking_performed": False,
        "q86_candidate_rows_constructed": False,
        "q86_selection_performed": False,
        "q86_commit_performed": False,
        "q86_checkpoint_record_constructed": False,
        "q86_partial_expansion_committed": False,
        "input_expansion_count": q85["retained_expansion_count"],
        "input_expansion_sha256": q85["retained_expansion_sha256"],
        "q85_committed_record_sha256": sha256(canonical_bytes(q85)),
    }
    for key, value in expected.items():
        if not exact_value_equal(abort.get(key), value):
            raise RuntimeError(f"M q86 resource abort exact drift: {key}")

    kind = abort.get("abort_kind")
    kinds = {
        "final_live_terms": {
            "exception_type": "RuntimeError",
            "exception_message": "design policy live-term cap exceeded",
            "exception_source_role": "exact_parent_helper",
            "exception_chained_from_exact_parent_helper": True,
            "abort_frame_local_schema_id": "helper_final_live_terms_v1",
            "gate_batch_propagation_completed": True,
            "policy_cap_check_reached": True,
            "kernel_cap_violation_triggered": False,
            "live_expansion_snapshot_available": True,
            "policy_relation": (
                "pretruncation_expansion_count>"
                "policy_max_single_expansion_terms"
            ),
            "cap": POLICY_CAPS_BASE["max_single_expansion_terms"],
        },
        "transient_live_terms": {
            "exception_type": "RuntimeError",
            "exception_message": (
                "design policy transient live-term cap exceeded"
            ),
            "exception_source_role": "exact_parent_helper",
            "exception_chained_from_exact_parent_helper": True,
            "abort_frame_local_schema_id": "helper_transient_live_terms_v1",
            "gate_batch_propagation_completed": True,
            "policy_cap_check_reached": True,
            "kernel_cap_violation_triggered": False,
            "live_expansion_snapshot_available": True,
            "policy_relation": (
                "peak_live_terms_this_checkpoint>"
                "policy_max_single_expansion_terms>="
                "pretruncation_expansion_count"
            ),
            "cap": POLICY_CAPS_BASE["max_single_expansion_terms"],
        },
        "kernel_single_expansion_terms": {
            "exception_type": "SchemaError",
            "exception_message": "v2 single-expansion term cap exceeded",
            "exception_source_role": "exact_wrapped_v2_kernel",
            "exception_chained_from_exact_parent_helper": False,
            "abort_frame_local_schema_id": (
                "kernel_observe_count_before_pre_count_assignment_v1"
            ),
            "gate_batch_propagation_completed": False,
            "policy_cap_check_reached": False,
            "kernel_cap_violation_triggered": True,
            "live_expansion_snapshot_available": False,
            "policy_relation": (
                "observed_term_count>kernel_max_single_expansion_terms_"
                "before_pretruncation_assignment"
            ),
            "cap": EXPECTED_WRAPPED_KERNEL_LIMITS[
                "max_single_expansion_terms"
            ],
        },
    }
    if type(kind) is not str or kind not in kinds:
        raise RuntimeError("M q86 resource abort kind drift")
    specification = kinds[kind]
    message = specification["exception_message"]
    branch_expected = {
        key: value
        for key, value in specification.items()
        if key != "cap"
    }
    branch_expected["exception_args"] = [message]
    branch_expected["enforced_term_cap"] = specification["cap"]
    for key, value in branch_expected.items():
        if not exact_value_equal(abort.get(key), value):
            raise RuntimeError(
                f"M q86 {kind} abort exact drift: {key}"
            )

    for key in (
        "observed_term_count",
        "observed_excess_terms",
        "peak_live_terms_this_checkpoint",
        "peak_live_terms_cumulative",
        "term_gate_visits_increment",
        "term_gate_visits_cumulative",
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    ):
        if type(abort.get(key)) is not int or abort[key] < 0:
            raise RuntimeError(f"M q86 resource abort integer drift: {key}")
    observed = abort["observed_term_count"]
    enforced = abort["enforced_term_cap"]
    if (
        observed <= enforced
        or abort["observed_excess_terms"] != observed - enforced
    ):
        raise RuntimeError("M q86 resource abort cap relation drift")
    pre_count = abort["pretruncation_expansion_count"]
    if kind == "final_live_terms":
        if type(pre_count) is not int or pre_count != observed:
            raise RuntimeError("M q86 final-live pretruncation drift")
    elif kind == "transient_live_terms":
        if (
            type(pre_count) is not int
            or pre_count < 0
            or pre_count > abort["policy_max_single_expansion_terms"]
            or abort["peak_live_terms_this_checkpoint"] != observed
        ):
            raise RuntimeError("M q86 transient-live relation drift")
    elif pre_count is not None:
        raise RuntimeError("M q86 kernel abort exposed stale pre_count")
    if (
        kind != "kernel_single_expansion_terms"
        and observed > abort["kernel_max_single_expansion_terms"]
    ):
        raise RuntimeError("M q86 helper abort bypassed kernel cap")

    if abort["peak_live_terms_this_checkpoint"] < observed:
        raise RuntimeError("M q86 resource abort peak below observed terms")
    if abort["peak_live_terms_cumulative"] != max(
        q85["peak_live_terms_cumulative"],
        abort["peak_live_terms_this_checkpoint"],
    ):
        raise RuntimeError("M q86 resource abort peak recurrence drift")
    if abort["term_gate_visits_increment"] < abort["input_expansion_count"]:
        raise RuntimeError("M q86 resource abort gate visits below input")
    if abort["term_gate_visits_cumulative"] != (
        q85["term_gate_visits_cumulative"]
        + abort["term_gate_visits_increment"]
    ):
        raise RuntimeError("M q86 resource abort visit recurrence drift")
    rounding_increment = parse_canonical_nonnegative_decimal(
        abort["rounding_increment_scaled_ticks_squared"],
        "M q86 resource abort rounding increment",
    )
    rounding_cumulative = parse_canonical_nonnegative_decimal(
        abort["rounding_cumulative_scaled_ticks_squared"],
        "M q86 resource abort rounding cumulative",
    )
    if rounding_cumulative != (
        int(q85["rounding_cumulative_scaled_ticks_squared"])
        + rounding_increment
    ):
        raise RuntimeError("M q86 resource abort rounding recurrence drift")
    for key in (
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    ):
        if abort[key] < q85[key]:
            raise RuntimeError(f"M q86 resource abort maximum drift: {key}")
    return dict(abort)

def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:

    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "M q86 raw parent top-level result",
    )
    require_exact_keys(
        predecessor,
        EXPECTED_ROUTE_PREDECESSOR_RESULT_KEYS,
        "M q86 route canonical",
    )
    expected_invariants = {
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": True,
        "v2_run_entrypoint_called": False,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "candidate_K_values": list(M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(M_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_LIMITS,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected_invariants.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"M q86 raw parent drift: {key}")

    validate_parent_source_custody(result.get("source_custody"))
    if not exact_value_equal(
        result.get("screen_execution_components"),
        list(EXPECTED_PARENT_EXECUTION_COMPONENTS),
    ):
        raise RuntimeError("M q86 raw component closure drift")
    for value_key, digest_key in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
    ):
        if result.get(digest_key) != sha256(
            canonical_bytes(result.get(value_key))
        ):
            raise RuntimeError(f"M q86 raw nested digest drift: {value_key}")
    expected_raw_configuration_reference = {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "source_sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "role": "candidates_and_caps_reference_only",
        "fields_adopted": [
            f"MODE_CONFIG.{MODE}.candidates",
            "POLICY_CAPS_BASE",
        ],
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "policy_caps_base_sha256": EXPECTED_V6_POLICY_CAPS_SHA256,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }
    if not exact_value_equal(
        result.get("configuration_reference"),
        expected_raw_configuration_reference,
    ):
        raise RuntimeError("M q86 raw configuration-reference authority drift")

    predecessor_transform = predecessor["checkpoint_transform"]
    if type(predecessor_transform) is not dict:
        raise RuntimeError("M q86 route transform schema drift")
    expected_raw_transform = predecessor_transform.get(
        "physical_four_gate_control_flow_parent_transform"
    )
    expected_raw_transform_sha = predecessor_transform.get(
        "physical_four_gate_control_flow_parent_transform_sha256"
    )
    if expected_raw_transform_sha != EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256:
        raise RuntimeError("M q86 route raw transform authority pin drift")
    if sha256(canonical_bytes(expected_raw_transform)) != (
        EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
    ):
        raise RuntimeError("M q86 route raw transform digest drift")
    if not exact_value_equal(
        result.get("checkpoint_transform"), expected_raw_transform
    ):
        raise RuntimeError("M q86 raw checkpoint transform authority drift")
    if result.get("checkpoint_transform_sha256") != (
        EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
    ):
        raise RuntimeError("M q86 raw checkpoint transform digest pin drift")

    dynamic_or_route_overridden_fields = {
        "transcript_fingerprint",
        "screen_terminal_condition",
        "screen_source_sha256",
        "control_flow_owned_by_screen",
        "screen_execution_components",
        "screen_execution_components_sha256",
        "configuration_reference",
        "configuration_reference_sha256",
        "checkpoint_transform",
        "checkpoint_transform_sha256",
        "source_custody",
        "candidate_K_values",
        "candidate_K_values_sha256",
        "kernel_capability_limits",
        "proposed_policy_caps",
        "horizon_checkpoint_attempted",
        "horizon_reached_with_committed_checkpoint",
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
    }
    for key in UPSTREAM_PARENT_RESULT_KEYS - dynamic_or_route_overridden_fields:
        if not exact_value_equal(result.get(key), predecessor.get(key)):
            raise RuntimeError(f"M q86 invariant top-level drift: {key}")

    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) not in (85, 86):
        raise RuntimeError("M q86 must attempt q85 and at most q86")
    if type(history) is not list:
        raise RuntimeError("M q86 selected history is not an exact list")
    old_records = predecessor.get("records")
    old_history = predecessor.get("selected_K_history")
    if type(old_records) is not list or len(old_records) != 85:
        raise RuntimeError("M q86 route predecessor record count drift")
    if type(old_history) is not list or len(old_history) != 84:
        raise RuntimeError("M q86 route predecessor history count drift")
    if not exact_value_equal(history[:84], old_history):
        raise RuntimeError("M q86 changed the exact q1-84 selected history")
    if sha256(canonical_bytes(old_records[:84])) != (
        EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
    ):
        raise RuntimeError("M q86 predecessor q1-84 digest drift")
    if sha256(canonical_bytes(history[:84])) != (
        EXPECTED_Q84_SELECTED_HISTORY_SHA256
    ):
        raise RuntimeError("M q86 q1-84 history prefix digest drift")

    def validate_appended_row(
        record: Mapping[str, Any],
        old_rows: Any,
        checkpoint: int,
    ) -> Dict[str, Any]:
        rows = record.get("candidate_records")
        if (
            type(old_rows) is not list
            or len(old_rows) != 32
            or type(rows) is not list
            or len(rows) != 33
            or not exact_value_equal(rows[:32], old_rows)
        ):
            raise RuntimeError(
                f"M q{checkpoint} changed predecessor candidate rows"
            )
        appended = rows[32]
        require_exact_keys(
            appended,
            CANDIDATE_RECORD_KEYS,
            f"M q{checkpoint} appended candidate row",
        )
        pre_count = record.get("pretruncation_expansion_count")
        if type(pre_count) is not int or pre_count < 0:
            raise RuntimeError(f"M q{checkpoint} pretruncation count drift")
        effective = min(K606208, pre_count)
        for key, value in {
            "candidate_index": 32,
            "configured_K": K606208,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }.items():
            if not exact_value_equal(appended.get(key), value):
                raise RuntimeError(
                    f"M q{checkpoint} appended candidate drift: {key}"
                )
        drop = parse_canonical_nonnegative_decimal(
            appended.get("drop_ticks"),
            f"M q{checkpoint} appended drop",
        )
        E_after = parse_canonical_nonnegative_decimal(
            appended.get("E_after_if_selected_ticks"),
            f"M q{checkpoint} appended E after",
        )
        E_before = parse_canonical_nonnegative_decimal(
            record.get("E_before_ticks"),
            f"M q{checkpoint} E before",
        )
        prefix_cap = parse_canonical_nonnegative_decimal(
            record.get("budget_prefix_cap_ticks"),
            f"M q{checkpoint} prefix cap",
        )
        if E_after != E_before + drop:
            raise RuntimeError(
                f"M q{checkpoint} appended candidate E recurrence drift"
            )
        predecessor_row = rows[31]
        predecessor_drop = parse_canonical_nonnegative_decimal(
            predecessor_row.get("drop_ticks"),
            f"M q{checkpoint} predecessor maximum-K drop",
        )
        predecessor_E_after = parse_canonical_nonnegative_decimal(
            predecessor_row.get("E_after_if_selected_ticks"),
            f"M q{checkpoint} predecessor maximum-K E after",
        )
        if (
            drop > predecessor_drop
            or E_after > predecessor_E_after
            or appended["effective_retained_count"]
            < predecessor_row["effective_retained_count"]
            or appended["dropped_term_count"]
            > predecessor_row["dropped_term_count"]
        ):
            raise RuntimeError(
                f"M q{checkpoint} appended candidate ranking drift"
            )
        if (appended["dropped_term_count"] == 0) is not (drop == 0):
            raise RuntimeError(
                f"M q{checkpoint} appended zero-drop arithmetic drift"
            )
        if appended.get("feasible_under_current_prefix_cap") is not (
            E_after <= prefix_cap
        ):
            raise RuntimeError(
                f"M q{checkpoint} appended candidate feasibility drift"
            )
        return appended

    for index in range(84):
        old = old_records[index]
        new = records[index]
        require_exact_keys(
            new,
            Q84_SUCCESS_RECORD_KEYS,
            f"M q{index + 1} extended success record",
        )
        old_common = {
            key: value
            for key, value in old.items()
            if key != "candidate_records"
        }
        new_common = {
            key: value
            for key, value in new.items()
            if key != "candidate_records"
        }
        if not exact_value_equal(new_common, old_common):
            raise RuntimeError(
                f"M q86 changed q{index + 1} common record state"
            )
        validate_appended_row(
            new,
            old.get("candidate_records"),
            index + 1,
        )

    q84 = records[83]
    if not exact_value_equal(q84.get("retained_expansion_count"), K589824):
        raise RuntimeError("M q86 q84 retained count anchor drift")
    if q84.get("retained_expansion_sha256") != (
        EXPECTED_Q84_RETAINED_EXPANSION_SHA256
    ):
        raise RuntimeError("M q86 q84 retained digest anchor drift")
    if q84.get("E_after_ticks") != EXPECTED_Q84_E_AFTER_TICKS:
        raise RuntimeError("M q86 q84 cumulative E anchor drift")

    old_q85 = old_records[84]
    new_q85 = records[84]
    excluded = {
        "candidate_records",
        "status",
        "selected_candidate_index",
        "selected_K",
        *Q84_FAILURE_ONLY_KEYS,
        *Q84_SUCCESS_ONLY_KEYS,
    }
    old_shared = {
        key: value for key, value in old_q85.items() if key not in excluded
    }
    if any(key not in new_q85 for key in old_shared):
        raise RuntimeError("M q85 removed a shared propagation field")
    if not exact_value_equal(
        {key: new_q85[key] for key in old_shared},
        old_shared,
    ):
        raise RuntimeError("M q85 changed shared propagation fields")
    appended_q85 = validate_appended_row(
        new_q85,
        old_q85.get("candidate_records"),
        85,
    )
    selected_q85 = validate_extended_record(new_q85, q84, 85)
    abort = validate_resource_policy_abort(result, new_q85)
    selected_after_q84 = []

    if selected_q85 is None:
        if abort is not None:
            raise RuntimeError("M q85 failure cannot carry a q86 resource abort")
        if len(records) != 85 or len(history) != 84:
            raise RuntimeError("M q85 failure must terminate before q86")
        branch = "Q85_FAILURE_Q86_NOT_ATTEMPTED"
        expected_summary = {
            "attempted_checkpoint_count": 85,
            "completed_checkpoint_count": 84,
            "horizon_checkpoint_attempted": False,
            "horizon_reached_with_committed_checkpoint": False,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "failure_checkpoint_included": True,
            "last_committed_cumulative_drop_ticks": EXPECTED_Q84_E_AFTER_TICKS,
        }
    else:
        if (
            selected_q85 != K606208
            or new_q85.get("selected_candidate_index") != 32
            or appended_q85.get("feasible_under_current_prefix_cap") is not True
        ):
            raise RuntimeError("M q85 did not select the appended M33 rung")
        selected_after_q84.append(selected_q85)
        if abort is not None:
            if len(records) != 85 or len(history) != 85:
                raise RuntimeError(
                    "M q86 resource abort must preserve exactly q1-q85"
                )
            branch = "Q85_SUCCESS_Q86_RESOURCE_ABORT"
            expected_summary = {
                "attempted_checkpoint_count": 86,
                "completed_checkpoint_count": 85,
                "horizon_checkpoint_attempted": True,
                "horizon_reached_with_committed_checkpoint": False,
                "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
                "failure_checkpoint_included": False,
                "last_committed_cumulative_drop_ticks": new_q85[
                    "E_after_ticks"
                ],
            }
        else:
            if len(records) != 86:
                raise RuntimeError("M q85 success must continue through q86")
            selected_q86 = validate_extended_record(
                records[85],
                records[84],
                86,
            )
            if selected_q86 is None:
                if len(history) != 85:
                    raise RuntimeError("M q86 failure history count drift")
                branch = "Q85_SUCCESS_Q86_FAILURE"
                expected_summary = {
                    "attempted_checkpoint_count": 86,
                    "completed_checkpoint_count": 85,
                    "horizon_checkpoint_attempted": True,
                    "horizon_reached_with_committed_checkpoint": False,
                    "screen_terminal_condition": (
                        "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                    ),
                    "failure_checkpoint_included": True,
                    "last_committed_cumulative_drop_ticks": new_q85[
                        "E_after_ticks"
                    ],
                }
            else:
                selected_after_q84.append(selected_q86)
                if len(history) != 86:
                    raise RuntimeError("M q86 success history count drift")
                branch = "Q85_AND_Q86_SUCCESS_HORIZON_REACHED"
                expected_summary = {
                    "attempted_checkpoint_count": 86,
                    "completed_checkpoint_count": 86,
                    "horizon_checkpoint_attempted": True,
                    "horizon_reached_with_committed_checkpoint": True,
                    "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
                    "failure_checkpoint_included": False,
                    "last_committed_cumulative_drop_ticks": records[85][
                        "E_after_ticks"
                    ],
                }

    if not exact_value_equal(
        history,
        list(old_history) + selected_after_q84,
    ):
        raise RuntimeError("M q86 selected history is not the exact replay ledger")
    for key, value in expected_summary.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"M q86 terminal summary drift: {key}")

    final = records[-1]
    failed = (
        abort is None
        and final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    )
    expected_failure_sha = sha256(canonical_bytes(final)) if failed else None
    if result.get("failure_record_sha256") != expected_failure_sha:
        raise RuntimeError("M q86 failure-record digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("M q86 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(
        canonical_bytes(history)
    ):
        raise RuntimeError("M q86 selected history digest drift")
    resource_source = abort if abort is not None else final
    observed = {
        "observed_peak_single_expansion_terms": resource_source[
            "peak_live_terms_cumulative"
        ],
        "observed_term_gate_visits_including_terminal_attempt": resource_source[
            "term_gate_visits_cumulative"
        ],
        "observed_maximum_expansion_coefficient_tick_bits": resource_source[
            "maximum_expansion_coefficient_tick_bits"
        ],
        "observed_maximum_product_bits": resource_source[
            "maximum_product_bits"
        ],
        "observed_rounding_cumulative_scaled_ticks_squared": resource_source[
            "rounding_cumulative_scaled_ticks_squared"
        ],
    }
    for key, value in observed.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"M q86 observed resource ledger drift: {key}")

    return {
        "validation_id": "M_k606208_c33_q86_predecessor_handoff_v1",
        "q1_through_q84_common_records_exact": True,
        "q1_through_q84_first_32_candidate_rows_exact": True,
        "q1_through_q84_appended_row_index": 32,
        "q1_through_q84_appended_row_K": K606208,
        "q1_through_q84_selected_history_exact": True,
        "q84_records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "q84_selected_history_sha256": EXPECTED_Q84_SELECTED_HISTORY_SHA256,
        "q84_terminal_record_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_Q84_RECORD_SHA256
        ),
        "q85_input_retained_count": K589824,
        "q85_input_retained_sha256": EXPECTED_Q84_RETAINED_EXPANSION_SHA256,
        "q85_input_E_before_ticks": EXPECTED_Q84_E_AFTER_TICKS,
        "q85_prefix_cap_ticks": EXPECTED_Q85_PREFIX_CAP_TICKS,
        "q85_shared_propagation_fields_exact": True,
        "q85_first_32_candidate_rows_exact": True,
        "q85_predecessor_failure_record_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_Q85_FAILURE_SHA256
        ),
        "q85_predecessor_minimum_effective_K": (
            EXPECTED_Q85_MINIMUM_EFFECTIVE_K
        ),
        "q85_new_policy_headroom": EXPECTED_Q85_NEW_POLICY_HEADROOM,
        "q85_appended_candidate_index": 32,
        "q85_appended_candidate_K": K606208,
        "q86_prefix_cap_ticks_if_attempted": EXPECTED_Q86_PREFIX_CAP_TICKS,
        "legal_terminal_branches": [
            "Q85_FAILURE_Q86_NOT_ATTEMPTED",
            "Q85_SUCCESS_Q86_FAILURE",
            "Q85_AND_Q86_SUCCESS_HORIZON_REACHED",
            "Q85_SUCCESS_Q86_RESOURCE_ABORT",
        ],
        "terminal_branch": branch,
        "q86_resource_policy_abort_structured": abort is not None,
        "q86_resource_policy_abort_kind": (
            abort["abort_kind"] if abort is not None else None
        ),
        "q86_checkpoint_record_constructed": len(records) == 86,
        "q86_resource_policy_abort_sha256": result[
            "resource_policy_abort_sha256"
        ],
        "q85_and_q86_outcomes_precommitted": False,
    }

def execution_components(
    parent_components: Any,
    self_sha: str,
    wrapper_sha: str,
) -> list[Dict[str, Any]]:
    if not exact_value_equal(
        parent_components,
        list(EXPECTED_PARENT_EXECUTION_COMPONENTS),
    ):
        raise RuntimeError("parent execution component schema drift")
    paths = [item["relative_path"] for item in parent_components]
    if len(paths) != len(set(paths)):
        raise RuntimeError("duplicate parent execution component path")
    components = [{
        "relative_path": SELF_NAME,
        "role": "M_k606208_c33_q86_fresh_same_byte_screen",
        "sha256": self_sha,
    }]
    saw_parent = saw_v6 = saw_v2 = False
    forbidden = {
        ROUTE_PREDECESSOR_SCREEN_NAME,
        ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
        "hubbard_l8_adaptive_k_arithmetic_k589824.py",
        "hubbard_l8_adaptive_k_arithmetic_k606208_c35.py",
    }
    for original in parent_components:
        item = dict(original)
        path = item.get("relative_path")
        if path in forbidden:
            raise RuntimeError("reference-only route became an execution component")
        if path == CONTROL_FLOW_PARENT_NAME:
            if item.get("sha256") != EXPECTED_CONTROL_FLOW_PARENT_SHA256:
                raise RuntimeError("control-flow parent component pin drift")
            item["role"] = "four_gate_control_flow_parent_private_entrypoint"
            saw_parent = True
        elif path == V6_BASELINE_CONFIGURATION_NAME:
            if item.get("sha256") != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
                raise RuntimeError("v6 baseline component pin drift")
            item["role"] = "v6_baseline_configuration_before_declared_override"
            saw_v6 = True
        elif path == V2_ARITHMETIC_NAME:
            if item.get("sha256") != EXPECTED_V2_ARITHMETIC_SHA256:
                raise RuntimeError("v2 arithmetic component pin drift")
            item["role"] = "v2_arithmetic_bytes_beneath_capability_wrapper"
            saw_v2 = True
        components.append(item)
        if path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "M_k606208_c33_capability_override_provider",
                "sha256": wrapper_sha,
            })
    if not (saw_parent and saw_v6 and saw_v2):
        raise RuntimeError("parent component set incomplete")
    final_paths = [item["relative_path"] for item in components]
    if len(final_paths) != 11 or len(final_paths) != len(set(final_paths)):
        raise RuntimeError("final execution component closure drift")
    return components


def configuration_reference() -> Dict[str, Any]:
    return {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "source_sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "role": "v6_baseline_candidates_and_caps_before_direct_override",
        "baseline_M_candidate_K_values_sha256": (
            EXPECTED_V6_M_CANDIDATE_SHA256
        ),
        "baseline_policy_caps_sha256": EXPECTED_V6_POLICY_CAPS_SHA256,
        "compiled_from_verified_bytes": True,
        "module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }


def configuration_override(
    baseline_m: Tuple[int, ...],
) -> Dict[str, Any]:
    expected_direct = baseline_m[1:] + (
        K540672,
        K557056,
        K573440,
        K589824,
        K606208,
    )
    if baseline_m != V6_M_CANDIDATES or M_CANDIDATES != expected_direct:
        raise RuntimeError("configuration baseline construction drift")
    unchanged = {
        key: value
        for key, value in EXPECTED_V6_POLICY_CAPS.items()
        if key not in {
            "max_candidate_K",
            "max_output_terms_if_successful",
        }
    }
    return {
        "override_id": (
            "magnetization_k606208_c33_q86_configuration_override_v1"
        ),
        "diagnostic_ladder_precommitted_before_replay": True,
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": (
                EXPECTED_V6_M_CANDIDATE_SHA256
            ),
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 29, "after": 33},
            "candidate_ladder_added": [
                K540672,
                K557056,
                K573440,
                K589824,
                K606208,
            ],
            "candidate_ladder_removed": [65_536],
            "policy_cap_changes": {
                "max_candidate_K": {
                    "before": 524_288,
                    "after": K606208,
                },
                "max_output_terms_if_successful": {
                    "before": 524_288,
                    "after": K606208,
                },
            },
        },
        "incremental_route_override_from_k589824_c32_q86": {
            "predecessor_candidate_K_values_sha256": (
                EXPECTED_PREDECESSOR_CANDIDATE_SHA256
            ),
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 32, "after": 33},
            "candidate_ladder_added": [K606208],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {
                    "before": K589824,
                    "after": K606208,
                },
                "max_output_terms_if_successful": {
                    "before": K589824,
                    "after": K606208,
                },
            },
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "derived_policy_cap": {
            "field": "max_candidate_count",
            "derivation": "len(candidate_K_values)",
            "before_on_route": 32,
            "after": 33,
        },
        "unchanged_policy_caps": unchanged,
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
    if (
        wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256
        or manifest.get("resource_limits_after_extension")
        != EXPECTED_WRAPPED_KERNEL_LIMITS
        or manifest.get("route_predecessor_resource_limits")
        != EXPECTED_ROUTE_KERNEL_LIMITS
        or manifest.get("cross_route_reference_resource_limits")
        != {
            **EXPECTED_WRAPPED_KERNEL_LIMITS,
            "max_candidate_count": 35,
        }
    ):
        raise RuntimeError("kernel capability manifest relationship drift")
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "separate_M_k606208_c33_capability_override_provider",
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
            "max_candidate_count": {"before": 32, "after": 33},
            "max_retained_K": {"before": 524_288, "after": K606208},
        },
        "incremental_route_changes_from_k589824_c32": {
            "max_candidate_count": {"before": 32, "after": 33},
            "max_retained_K": {"before": K589824, "after": K606208},
        },
        "same_K_cross_route_reference_to_D_k606208_c35": {
            "max_candidate_count": {"this_route": 33, "cross_route": 35},
            "max_retained_K": {
                "this_route": K606208,
                "cross_route": K606208,
            },
            "compiled": False,
            "executed": False,
            "execution_source_layer": False,
        },
        "execution_source_layers": [
            KERNEL_WRAPPER_NAME,
            V2_ARITHMETIC_NAME,
        ],
        "route_predecessor_is_execution_source": False,
        "cross_route_reference_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def validate_and_relabel(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    route_reference: Mapping[str, Any],
    baseline_m: Tuple[int, ...],
    wrapper_sha: str,
    manifest: Mapping[str, Any],
    horizon_override: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q86 relabel requires fresh same-byte self execution")
    if (
        horizon_override.get("changed_fields")
        != [f"MODE_CONFIG.{MODE}.horizon_checkpoint_count"]
        or horizon_override.get("semantic_delta")
        != {
            f"MODE_CONFIG.{MODE}.horizon_checkpoint_count": {
                "before": BASE_PARENT_HORIZON,
                "after": EXTENDED_HORIZON,
            }
        }
        or horizon_override.get(
            "double_occupancy_configuration_unchanged"
        ) is not True
    ):
        raise RuntimeError("M q86 parent horizon override drift")

    handoff = validate_replay_handoff(result, predecessor)
    old_components = result["screen_execution_components"]
    if result["screen_execution_components_sha256"] != sha256(
        canonical_bytes(old_components)
    ):
        raise RuntimeError("parent component digest drift")
    old_configuration_reference = result["configuration_reference"]
    if result["configuration_reference_sha256"] != sha256(
        canonical_bytes(old_configuration_reference)
    ):
        raise RuntimeError("parent configuration reference digest drift")
    old_transform = result["checkpoint_transform"]
    old_transform_sha = result["checkpoint_transform_sha256"]
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("parent transform digest drift")

    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(
        old_components,
        self_sha,
        wrapper_sha,
    )
    baseline_reference = configuration_reference()
    config = configuration_override(baseline_m)
    capability = kernel_capability_override(wrapper_sha, manifest)
    transform = {
        "transform_id": "magnetization_four_gate_k606208_c33_q86_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": (
            old_transform_sha
        ),
        "route_predecessor_transform_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256
        ),
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q85_and_q86_outcomes_precommitted": False,
        "incremental_route_semantic_delta": {
            "candidate_K_values_changed": True,
            "policy_caps_changed": True,
            "kernel_capability_limits_changed": True,
            "horizon_checkpoint_count": {"before": 86, "after": 86},
        },
        "overridden_semantics": [
            "candidate_K_values",
            "policy_max_candidate_K",
            "policy_max_output_terms_if_successful",
            "derived_policy_max_candidate_count",
            "kernel_max_retained_K",
            "kernel_max_candidate_count",
            "magnetization_horizon_checkpoint_count",
        ],
    }

    parent_custody = validate_parent_source_custody(result["source_custody"])
    custody = expected_final_source_custody(self_sha, wrapper_sha)
    if parent_custody != {
        path: custody[path] for path in EXPECTED_PARENT_SOURCE_CUSTODY
    }:
        raise RuntimeError("M q86 parent custody changed during relabel")
    if len(custody) != 10:
        raise RuntimeError("M q86 final source custody cardinality drift")
    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k606208_c33_q86_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_relative_path": CONTROL_FLOW_PARENT_NAME,
        "control_flow_parent_source_sha256": (
            EXPECTED_CONTROL_FLOW_PARENT_SHA256
        ),
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
            "base_v2_arithmetic_implementation_commit_before_"
            "capability_override"
        ),
        "kernel_capability_wrapper_relative_path": KERNEL_WRAPPER_NAME,
        "kernel_capability_wrapper_source_sha256": wrapper_sha,
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(
            canonical_bytes(components)
        ),
        "configuration_reference": baseline_reference,
        "configuration_reference_sha256": sha256(
            canonical_bytes(baseline_reference)
        ),
        "configuration_override": config,
        "configuration_override_sha256": sha256(canonical_bytes(config)),
        "kernel_capability_override": capability,
        "kernel_capability_override_sha256": sha256(
            canonical_bytes(capability)
        ),
        "parent_horizon_override": dict(horizon_override),
        "parent_horizon_override_sha256": sha256(
            canonical_bytes(horizon_override)
        ),
        "route_predecessor_reference": dict(route_reference),
        "route_predecessor_reference_sha256": sha256(
            canonical_bytes(route_reference)
        ),
        "predecessor_handoff_validation": handoff,
        "predecessor_handoff_validation_sha256": sha256(
            canonical_bytes(handoff)
        ),
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
        "M q86 relabelled top-level result",
    )
    if not exact_value_equal(
        result["source_custody"],
        expected_final_source_custody(self_sha, wrapper_sha),
    ):
        raise RuntimeError("M q86 final source custody closure drift")
    for value_key, digest_key in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("configuration_override", "configuration_override_sha256"),
        ("kernel_capability_override", "kernel_capability_override_sha256"),
        ("parent_horizon_override", "parent_horizon_override_sha256"),
        ("route_predecessor_reference", "route_predecessor_reference_sha256"),
        ("predecessor_handoff_validation", "predecessor_handoff_validation_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
        ("resource_policy_abort", "resource_policy_abort_sha256"),
    ):
        value = result[value_key]
        digest = result[digest_key]
        if value is None:
            if digest is not None:
                raise RuntimeError(f"M q86 null nested digest drift: {value_key}")
        elif digest != sha256(canonical_bytes(value)):
            raise RuntimeError(f"M q86 final nested digest drift: {value_key}")
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q86 screen requires fresh same-byte self execution")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_control_flow_parent(repo)
    configuration, baseline_m = load_configured_v6_baseline(repo)
    wrapper, wrapper_sha, manifest = load_kernel_wrapper(repo)
    horizon = configure_parent_execution(parent, configuration, wrapper)
    result = execute_parent_with_structured_abort(parent, wrapper, repo)
    predecessor, route_reference = load_route_reference(repo)
    return validate_and_relabel(
        result,
        predecessor,
        route_reference,
        baseline_m,
        wrapper_sha,
        manifest,
        horizon,
    )

def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_magnetization_k606208_c33_q86_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("M q86 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("M q86 transcript exceeds output byte cap")
    output = output.resolve()
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output.parent, prefix=output.name + ".", suffix=".tmp", delete=False) as handle:
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
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "final_status": final["status"],
        "final_checkpoint": final["checkpoint_number_one_based"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
