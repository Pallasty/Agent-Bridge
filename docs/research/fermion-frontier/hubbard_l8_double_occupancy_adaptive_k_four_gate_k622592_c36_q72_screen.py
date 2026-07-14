#!/usr/bin/env python3
"""Source-pinned, diagnostic-only D K=622592/C=36 q72 screen.

The only execution parent is a fresh same-byte copy of the exact four-gate
control-flow screen, which owns a complete replay from checkpoint one.  The
K606208/C35 q72 screen and canonical transcript are exact post-replay route
references for q1--70 and q71 shared-ledger validation; neither is compiled,
executed, used for propagation, or used for state resume.
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
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_q72_screen.py"
)
CONTROL_FLOW_PARENT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k622592_c36.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k606208_c35_q72_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k606208_c35_q72_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_q72_transcript.json"
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
    "7ac6c87f3d789ad62540cbc96e81f0a092594b0524eec3f9b05e7ffec2124838"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "fc82c41b1a1dd82fbb34e205ea347b0ba41b08c5fd2ebed6a599593fe95c1b34"
)
EXPECTED_KERNEL_SOURCE_LAYERS_SHA256 = (
    "4ce34099fe9df61ed76f3e601fec2f5a69b3615940560675005f7108b991aa8f"
)
EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256 = (
    "3a519ce616393b62722f9779a4d38a30d97850c83628d8cbe94189f183a22f7f"
)
EXPECTED_ROUTE_KERNEL_SHA256 = (
    "34757028d695e2542cade50f4be5c214006dee6945e01afc2483e7338d6cb7dd"
)
EXPECTED_ROUTE_KERNEL_MANIFEST_SHA256 = (
    "c55df50288334226a4d8ba37a257ca645d601967f8778f426a313773c1c73629"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "54601418ab5aa2b6c887d928ad6c87fa0cff558c0558d106961201d291cc33fe"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "f21288cf0c37dc86fedc9ac195f4efe390dcc913640caa7ca79f02e6297d20f8"
)
# The predecessor has 71 records because q71 is its included failure attempt.
# The q1--70 prefix remains separately pinned below for the common replay ledger.
EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256 = (
    "d1a76c90065cead72388d0ce0712273fe3184dd06d25ecbea24c7b03f04d165f"
)
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "9c22797b82cba9e41edbc117593e2cb364f3c6dd274c99c369a7f29ebbc95c39"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "d57dfeffe7e5e0056ad1b0294a015852af7788fe23187aad9d4484683f8f1cba"
)
EXPECTED_ROUTE_PREDECESSOR_Q70_RECORD_SHA256 = (
    "d26ffa65831304b1d668a6d4221bc8244e9b581da10babb98a9d9949f4aed685"
)
EXPECTED_ROUTE_PREDECESSOR_Q71_FAILURE_SHA256 = (
    "ca1558715a87ca8d728bf511cce4a3d63c06828572d835f6005214d0ae021749"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "b2b55b96b9f29a2731e60625ca6c40ffc254901740f8ef66aaf7b3e906411e35"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256 = (
    "41be637814a62b1b8f122aa113ce2be575f00cf21322b9d137e292d186e461a7"
)
EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256 = (
    "6260d69cff7e23c4f725e81f1db2d2edd057a2a2b73bbf2b5fc99382003db6b7"
)
EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256 = (
    "f661416c9751b50f6bd9753fca8c1b4d57e743ee9b4556a103d296417fffc861"
)
EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256 = (
    "2b218fd138d85c06a59b94736ecd3a1b093fef7d729e8409e7daa55a060f05c2"
)
EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256 = (
    "420da6713b0b837d25b54275724810054a12d3e3680f64398805b7c6e267ae22"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "7767fa4b9bc3c1e9de5fa898d0c46bcb65fa26598678e3c8234f6f08ee61278e"
)
EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256 = (
    "c2aa225b96c984618d0dd0454dba9cb20f20ae8749f3f2452d8982a399f07336"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_ROUTE_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "double_occupancy"
BASE_PARENT_HORIZON = 66
EXTENDED_HORIZON = 72
K540672 = 540_672
K573440 = 573_440
K589824 = 589_824
K606208 = 606_208
K622592 = 622_592

V6_D_CANDIDATES = (
    65_536, 73_728, 81_920, 90_112, 98_304, 106_496, 114_688,
    122_880, 131_072, 147_456, 163_840, 180_224, 196_608, 212_992,
    229_376, 245_760, 262_144, 278_528, 294_912, 311_296, 327_680,
    344_064, 360_448, 376_832, 393_216, 409_600, 425_984, 442_368,
    458_752, 475_136, 507_904, 524_288,
)
PREDECESSOR_D_CANDIDATES = (
    V6_D_CANDIDATES[1:] + (K540672, K573440, K589824, K606208)
)
D_CANDIDATES = PREDECESSOR_D_CANDIDATES + (K622592,)
EXPECTED_V6_D_CANDIDATE_SHA256 = (
    "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
)
EXPECTED_V6_M_CANDIDATE_SHA256 = (
    "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
)
EXPECTED_PREDECESSOR_CANDIDATE_SHA256 = (
    "d69acf8cdc4e598e9734abe68a4d0a83cf7ea0618d38932b02c94c0aa8bfd161"
)
EXPECTED_CANDIDATE_SHA256 = (
    "5ab222cdcd073227d6d5e23f881ce94511dab86c35b6aab53c72de9f403367fc"
)
EXPECTED_Q70_SELECTED_HISTORY_SHA256 = (
    "d57dfeffe7e5e0056ad1b0294a015852af7788fe23187aad9d4484683f8f1cba"
)
EXPECTED_Q70_RETAINED_EXPANSION_SHA256 = (
    "4cb4888523ed5d1ffb5571573d017c2e44720def1f61a4b3bcaf1c68ac668dc4"
)
EXPECTED_Q70_E_AFTER_TICKS = "2288871542213247"
EXPECTED_Q71_PREFIX_CAP_TICKS = "2289007495823880"
EXPECTED_Q72_PREFIX_CAP_TICKS = "2289089997813814"
EXPECTED_EXTENSION_CHECKPOINT_ANCHORS = {
    71: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 14,
        "gate_batch_sha256": (
            "0d8e35335ccbe016a37dbaebad3206f556f6990ebe6dd49774a71088ab178530"
        ),
    },
    72: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 15,
        "gate_batch_sha256": (
            "18438c6e92238d37c833e1df5a341bbc17ec0a129a735e11719a586b2b74a4a3"
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
    "max_candidate_K": K606208,
    "max_output_terms_if_successful": K606208,
}
POLICY_CAPS_BASE = {
    **EXPECTED_PREDECESSOR_POLICY_CAPS,
    "max_candidate_K": K622592,
    "max_output_terms_if_successful": K622592,
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
    "max_candidate_count": 35,
    "max_retained_K": K606208,
}
EXPECTED_WRAPPED_KERNEL_LIMITS = {
    **EXPECTED_V2_KERNEL_LIMITS,
    "max_candidate_count": 36,
    "max_retained_K": K622592,
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
        "relative_path": "hubbard_l8_observable_interval_two_step_checker.py",
        "role": "double_occupancy_boundary_parent_source",
        "sha256": "a562055fa361b3b31d24cd9613c38d09ddc176791454a8612eb12ac2ad06c232",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_contract.json",
        "role": "double_occupancy_boundary_parent_source",
        "sha256": "09d4233cad211bb31e5e779156af2574ed966921168e9b4baf490691301b4e45",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_template.json",
        "role": "double_occupancy_boundary_parent_source",
        "sha256": "4ac0a0b3cbabb595a5872ae39bd182ab561fafaa51733625575d6bfc3f627ba1",
    },
    {
        "relative_path": "hubbard_l8_interval_checkpoints/double_occupancy_boundary_002.b85",
        "role": "double_occupancy_encoded_input_boundary",
        "sha256": "f92d5eadc01e1d9ebef86328b9eed92d867a2dd79b8bb2ba0baa821fe3b037ab",
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
    "hubbard_l8_observable_interval_two_step_checker.py": (
        "a562055fa361b3b31d24cd9613c38d09ddc176791454a8612eb12ac2ad06c232"
    ),
    "hubbard_l8_observable_interval_two_step_contract.json": (
        "09d4233cad211bb31e5e779156af2574ed966921168e9b4baf490691301b4e45"
    ),
    "hubbard_l8_observable_interval_two_step_template.json": (
        "4ac0a0b3cbabb595a5872ae39bd182ab561fafaa51733625575d6bfc3f627ba1"
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
REMOVED_COUNTERFACTUAL_KEYS = frozenset({
    "configured_K",
    "effective_retained_count",
    "dropped_term_count",
    "drop_ticks",
    "E_after_if_selected_ticks",
    "feasible_under_current_prefix_cap",
    "actual_selected_K",
    "would_precede_selected",
    "would_be_selected_if_inserted",
})
Q70_FAILURE_ONLY_KEYS = frozenset({
    "minimum_effective_K_to_meet_prefix",
    "required_K_excess_over_policy_maximum",
    "maximum_candidate_drop_excess_over_slack_ticks",
})
Q70_SUCCESS_ONLY_KEYS = frozenset({
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
Q70_FAILURE_RECORD_KEYS = frozenset({
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
    "removed_491520_counterfactual",
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
Q70_SUCCESS_RECORD_KEYS = (
    Q70_FAILURE_RECORD_KEYS - Q70_FAILURE_ONLY_KEYS | Q70_SUCCESS_ONLY_KEYS
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
    "exception_type",
    "exception_message",
    "exception_args",
    "exception_chained_from_exact_parent_helper",
    "control_flow_parent_source_sha256",
    "helper_source_sha256",
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
    "max_single_expansion_terms",
    "observed_excess_terms",
    "policy_relation",
    "attempted_gate_batch_propagated",
    "policy_cap_check_reached",
    "q72_pretruncation_digest_computed",
    "q72_ranking_performed",
    "q72_candidate_rows_constructed",
    "q72_selection_performed",
    "q72_commit_performed",
    "q72_checkpoint_record_constructed",
    "q72_partial_expansion_committed",
    "q71_committed_record_sha256",
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
    """Compare JSON-shaped values without Python's bool/int equivalence."""

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
    if len(V6_D_CANDIDATES) != 32 or len(PREDECESSOR_D_CANDIDATES) != 35:
        raise RuntimeError("D predecessor candidate count drift")
    if len(D_CANDIDATES) != 36 or D_CANDIDATES != PREDECESSOR_D_CANDIDATES + (K622592,):
        raise RuntimeError("D K622592 route is not an exact append")
    if any(left >= right for left, right in zip(D_CANDIDATES, D_CANDIDATES[1:])):
        raise RuntimeError("D candidate order drift")
    if sha256(canonical_bytes(list(PREDECESSOR_D_CANDIDATES))) != EXPECTED_PREDECESSOR_CANDIDATE_SHA256:
        raise RuntimeError("D predecessor candidate digest drift")
    if sha256(canonical_bytes(list(D_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("D candidate digest drift")
    expected = {"max_candidate_K", "max_output_terms_if_successful"}
    if changed_keys(EXPECTED_V6_POLICY_CAPS, POLICY_CAPS_BASE) != expected:
        raise RuntimeError("direct policy override changed a non-K field")
    if changed_keys(EXPECTED_PREDECESSOR_POLICY_CAPS, POLICY_CAPS_BASE) != expected:
        raise RuntimeError("route policy override changed a non-K field")
    if POLICY_CAPS_BASE["max_candidate_K"] != D_CANDIDATES[-1]:
        raise RuntimeError("policy maximum and D ladder disagree")
    schema_sizes = {
        "upstream_raw_top_level": len(UPSTREAM_PARENT_RESULT_KEYS),
        "raw_top_level": len(EXPECTED_PARENT_RESULT_KEYS),
        "final_top_level": len(EXPECTED_RELABELLED_RESULT_KEYS),
        "success_record": len(Q70_SUCCESS_RECORD_KEYS),
        "failure_record": len(Q70_FAILURE_RECORD_KEYS),
        "candidate_row": len(CANDIDATE_RECORD_KEYS),
        "removed_counterfactual": len(REMOVED_COUNTERFACTUAL_KEYS),
    }
    if schema_sizes != {
        "upstream_raw_top_level": 65,
        "raw_top_level": 67,
        "final_top_level": 96,
        "success_record": 38,
        "failure_record": 32,
        "candidate_row": 7,
        "removed_counterfactual": 9,
    }:
        raise RuntimeError("D q72 closed schema size drift")


def load_control_flow_parent(repo: Path) -> Any:
    parent, _ = load_pinned_module(
        repo, CONTROL_FLOW_PARENT_NAME, EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_parent_for_d_k622592_c36_q72",
    )
    if parent.KERNEL_NAME != V2_ARITHMETIC_NAME:
        raise RuntimeError("control-flow parent kernel path drift")
    if parent.EXPECTED_KERNEL_SHA256 != EXPECTED_V2_ARITHMETIC_SHA256:
        raise RuntimeError("control-flow parent kernel pin drift")
    if parent.EXPECTED_V6_CONFIGURATION_SHA256 != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
        raise RuntimeError("control-flow parent v6 pin drift")
    horizons = {mode: cfg["horizon_checkpoint_count"] for mode, cfg in parent.MODE_CONFIG.items()}
    if horizons != {"magnetization": 80, MODE: BASE_PARENT_HORIZON}:
        raise RuntimeError("control-flow parent horizon drift")
    if (
        type(parent) is not types.ModuleType
        or type(parent.run_four_gate) is not types.FunctionType
        or parent.run_four_gate.__globals__ is not parent.__dict__
        or parent.run_four_gate.__module__ != parent.__name__
        or parent.run_four_gate.__code__.co_filename != parent.__file__
    ):
        raise RuntimeError("control-flow parent function authority drift")
    parent._D_K622592_EXACT_RUN_FOUR_GATE = parent.run_four_gate
    return parent


def load_configured_v6_baseline(repo: Path) -> Tuple[Any, Tuple[int, ...]]:
    configuration, _ = load_pinned_module(
        repo, V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_for_d_k622592_c36_q72",
    )
    if configuration.POLICY_CAPS_BASE != EXPECTED_V6_POLICY_CAPS:
        raise RuntimeError("v6 policy caps drift")
    if sha256(canonical_bytes(configuration.POLICY_CAPS_BASE)) != EXPECTED_V6_POLICY_CAPS_SHA256:
        raise RuntimeError("v6 policy digest drift")
    baseline_d = tuple(configuration.MODE_CONFIG[MODE]["candidates"])
    baseline_m = tuple(configuration.MODE_CONFIG["magnetization"]["candidates"])
    if sha256(canonical_bytes(list(baseline_d))) != EXPECTED_V6_D_CANDIDATE_SHA256:
        raise RuntimeError("v6 D candidate digest drift")
    if sha256(canonical_bytes(list(baseline_m))) != EXPECTED_V6_M_CANDIDATE_SHA256:
        raise RuntimeError("v6 M candidate digest drift")
    if baseline_d != V6_D_CANDIDATES:
        raise RuntimeError("D direct construction from v6 drift")
    before_m = copy.deepcopy(configuration.MODE_CONFIG["magnetization"])
    effective = copy.deepcopy(configuration.MODE_CONFIG)
    effective[MODE]["candidates"] = tuple(D_CANDIDATES)
    configuration.MODE_CONFIG = effective
    configuration.POLICY_CAPS_BASE = dict(POLICY_CAPS_BASE)
    if configuration.MODE_CONFIG["magnetization"] != before_m:
        raise RuntimeError("configured v6 changed magnetization")
    return configuration, baseline_d


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
    wrapper = types.ModuleType("pinned_k622592_c36_arithmetic_wrapper")
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
        "route q72 canonical top-level transcript",
    )
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k606208_c35_q72_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": 72,
        "screen_terminal_condition": (
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        ),
        "attempted_checkpoint_count": 71,
        "completed_checkpoint_count": 70,
        "horizon_checkpoint_attempted": False,
        "horizon_reached_with_committed_checkpoint": False,
        "failure_checkpoint_included": True,
        "failure_record_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_Q71_FAILURE_SHA256
        ),
        "candidate_K_values": list(PREDECESSOR_D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_PREDECESSOR_POLICY_CAPS,
            "max_candidate_count": len(PREDECESSOR_D_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_ROUTE_KERNEL_LIMITS,
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
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
        "checkpoint_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if not exact_value_equal(transcript.get(key), value):
            raise RuntimeError(f"route predecessor transcript drift: {key}")
    outer_transform = transcript.get("checkpoint_transform")
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
    if type(records) is not list or len(records) != 71:
        raise RuntimeError("route q72 record count drift")
    if type(history) is not list or len(history) != 70:
        raise RuntimeError("route q72 history count drift")
    if sha256(canonical_bytes(records)) != (
        EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256
    ):
        raise RuntimeError("route records digest drift")
    if sha256(canonical_bytes(records[:70])) != (
        EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
    ):
        raise RuntimeError("route q1-70 records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("route history digest drift")
    if sha256(canonical_bytes(records[69])) != (
        EXPECTED_ROUTE_PREDECESSOR_Q70_RECORD_SHA256
    ):
        raise RuntimeError("route q70 record digest drift")
    if sha256(canonical_bytes(records[70])) != (
        EXPECTED_ROUTE_PREDECESSOR_Q71_FAILURE_SHA256
    ):
        raise RuntimeError("route q71 failure digest drift")
    q70 = records[69]
    for key, value in {
        "checkpoint_number_one_based": 70,
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "pretruncation_expansion_count": 718_805,
        "selected_K": K606208,
        "selected_candidate_index": 34,
        "retained_expansion_count": K606208,
        "retained_expansion_sha256": EXPECTED_Q70_RETAINED_EXPANSION_SHA256,
        "E_after_ticks": EXPECTED_Q70_E_AFTER_TICKS,
    }.items():
        if not exact_value_equal(q70.get(key), value):
            raise RuntimeError(f"route predecessor q70 drift: {key}")
    require_exact_keys(q70, Q70_SUCCESS_RECORD_KEYS, "route q70 success record")
    rows = q70.get("candidate_records")
    if type(rows) is not list or len(rows) != len(PREDECESSOR_D_CANDIDATES):
        raise RuntimeError("route q70 candidate row count drift")
    if not exact_value_equal(
        [row.get("configured_K") for row in rows],
        list(PREDECESSOR_D_CANDIDATES),
    ):
        raise RuntimeError("route q70 candidate row order drift")
    if [
        index for index, row in enumerate(rows)
        if row.get("feasible_under_current_prefix_cap") is True
    ] != [34]:
        raise RuntimeError("route q70 first-feasible selection drift")

    q71 = records[70]
    require_exact_keys(q71, Q70_FAILURE_RECORD_KEYS, "route q71 failure record")
    q71_rows = q71.get("candidate_records")
    if type(q71_rows) is not list or len(q71_rows) != 35:
        raise RuntimeError("route q71 candidate row count drift")
    if not exact_value_equal(
        [row.get("configured_K") for row in q71_rows],
        list(PREDECESSOR_D_CANDIDATES),
    ):
        raise RuntimeError("route q71 candidate row order drift")
    if any(
        row.get("feasible_under_current_prefix_cap") is not False
        for row in q71_rows
    ):
        raise RuntimeError("route q71 unexpectedly contains a feasible row")
    for key, value in {
        "checkpoint_number_one_based": 71,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "input_expansion_count": K606208,
        "input_expansion_sha256": EXPECTED_Q70_RETAINED_EXPANSION_SHA256,
        "E_before_ticks": EXPECTED_Q70_E_AFTER_TICKS,
        "budget_prefix_cap_ticks": EXPECTED_Q71_PREFIX_CAP_TICKS,
        "pretruncation_expansion_count": 761_190,
        "selected_candidate_index": None,
        "selected_K": None,
    }.items():
        if not exact_value_equal(q71.get(key), value):
            raise RuntimeError(f"route predecessor q71 drift: {key}")
    reference = {
        "route_id": (
            "double_occupancy_k606208_c35_q72_to_k622592_c36_q72_v1"
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
            "file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
            "q1_through_q70_records_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
            ),
            "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
            "q70_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q70_RECORD_SHA256,
            "q71_failure_record_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_Q71_FAILURE_SHA256
            ),
            "compiled": False,
            "executed": False,
            "loaded_before_replay_as_exact_reference": False,
            "loaded_after_replay_as_exact_reference": True,
            "used_only_after_replay_for_result_prefix_validation": True,
            "post_replay_prefix_validation_input": True,
            "propagation_input": False,
            "checkpoint_70_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
        "incremental_semantic_delta": {
            "candidate_K_values_changed": True,
            "policy_caps_changed": True,
            "kernel_capability_limits_changed": True,
            "horizon_checkpoint_count": {"before": 72, "after": 72},
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
        raise RuntimeError("parent configuration changed outside D horizon")
    if after["magnetization"] != before["magnetization"]:
        raise RuntimeError("parent magnetization configuration changed")
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
        "override_id": "double_occupancy_parent_q72_horizon_override_v1",
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
        "magnetization_configuration_unchanged": True,
    }


def normalize_completed_parent_result(result: Any) -> Dict[str, Any]:
    """Attach the closed non-abort fields to an ordinary parent result."""

    require_exact_keys(
        result,
        UPSTREAM_PARENT_RESULT_KEYS,
        "D q72 completed upstream parent result",
    )
    result = dict(result)
    result["resource_policy_abort"] = None
    result["resource_policy_abort_sha256"] = None
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "D q72 normalized parent result",
    )
    return result


def build_live_term_abort_parent_result(
    parent: Any,
    exception: RuntimeError,
) -> Dict[str, Any]:
    """Close the exact q72 live-term abort from the verified parent frame."""

    if type(exception) is not RuntimeError or exception.args != (
        "design policy live-term cap exceeded",
    ):
        raise RuntimeError("D q72 resource abort exception identity drift")
    expected_run_four_gate = getattr(
        parent, "_D_K622592_EXACT_RUN_FOUR_GATE", None
    )
    if (
        type(parent) is not types.ModuleType
        or type(parent._VERIFIED_SELF_SOURCE_BYTES) is not bytes
        or sha256(parent._VERIFIED_SELF_SOURCE_BYTES)
        != EXPECTED_CONTROL_FLOW_PARENT_SHA256
        or type(expected_run_four_gate) is not types.FunctionType
        or parent.run_four_gate is not expected_run_four_gate
        or expected_run_four_gate.__globals__ is not parent.__dict__
        or expected_run_four_gate.__module__ != parent.__name__
        or expected_run_four_gate.__code__.co_filename != parent.__file__
    ):
        raise RuntimeError("D q72 abort parent same-byte identity drift")

    traceback_frames = []
    traceback_item = exception.__traceback__
    while traceback_item is not None:
        traceback_frames.append(traceback_item.tb_frame)
        traceback_item = traceback_item.tb_next
    run_frames = [
        frame
        for frame in traceback_frames
        if frame.f_code is expected_run_four_gate.__code__
    ]
    if len(run_frames) != 1:
        raise RuntimeError("D q72 abort parent traceback authority drift")
    frame = run_frames[0]
    local = frame.f_locals
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
        raise RuntimeError("D q72 abort helper frame authority drift")
    helper_frames = [
        item
        for item in traceback_frames
        if item.f_code is enforce_policy_caps.__code__
    ]
    if len(helper_frames) != 1 or traceback_frames[-1] is not helper_frames[0]:
        raise RuntimeError("D q72 abort helper traceback identity drift")
    helper_local = helper_frames[0].f_locals

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
        "pre_count",
    }
    if not required_locals <= set(local):
        raise RuntimeError("D q72 abort parent frame local schema drift")

    records = local["records"]
    history = local["selected_history"]
    candidates = local["candidates"]
    caps = local["caps"]
    counter = local["counter"]
    pre_count = local["pre_count"]
    if local["mode"] != MODE:
        raise RuntimeError("D q72 abort mode drift")
    for label, value in {
        "checkpoint index": local["checkpoint_index"],
        "checkpoint number": local["checkpoint_number"],
        "pretruncation count": pre_count,
        "input count": local["input_count"],
        "visits before": local["visits_before"],
        "rounding before": local["rounding_before"],
    }.items():
        if type(value) is not int or value < 0:
            raise RuntimeError(f"D q72 abort {label} type drift")
    if (
        local["checkpoint_index"] != 71
        or local["checkpoint_number"] != 72
        or local["horizon"] != EXTENDED_HORIZON
        or type(records) is not list
        or len(records) != 71
        or type(history) is not list
        or len(history) != 71
        or local["failure"] is not None
        or local["horizon_reached"] is not False
    ):
        raise RuntimeError("D q72 abort checkpoint boundary drift")
    q71 = records[-1]
    if (
        type(q71) is not dict
        or q71.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
        or type(q71.get("selected_candidate_index")) is not int
        or q71.get("selected_candidate_index") != 35
        or type(q71.get("selected_K")) is not int
        or q71.get("selected_K") != K622592
    ):
        raise RuntimeError("D q72 abort q71 committed-success drift")
    if tuple(candidates) != D_CANDIDATES:
        raise RuntimeError("D q72 abort candidate ladder drift")
    cap = caps.get("max_single_expansion_terms")
    if type(cap) is not int or cap != POLICY_CAPS_BASE[
        "max_single_expansion_terms"
    ]:
        raise RuntimeError("D q72 abort live-term cap drift")
    if pre_count <= cap:
        raise RuntimeError("D q72 abort did not exceed the live-term cap")
    if (
        helper_local.get("term_count") != pre_count
        or helper_local.get("caps") is not caps
        or helper_local.get("counter") is not counter
        or helper_local.get("kernel") is not local["kernel"]
    ):
        raise RuntimeError("D q72 abort helper argument identity drift")

    batch = local["batch"]
    if type(batch) is not list or len(batch) != 4:
        raise RuntimeError("D q72 abort gate batch drift")
    if local["input_count"] != q71.get("retained_expansion_count"):
        raise RuntimeError("D q72 abort q71-to-q72 count continuity drift")
    if local["input_sha"] != q71.get("retained_expansion_sha256"):
        raise RuntimeError("D q72 abort q71-to-q72 digest continuity drift")

    root_after = local["kernel"].root_global_snapshot(local["root"])
    if not exact_value_equal(local["root_before"], root_after):
        raise RuntimeError("D q72 abort changed root arithmetic globals")
    q71_sha = sha256(canonical_bytes(q71))
    abort = {
        "schema_version": 1,
        "abort_id": "D_k622592_c36_q72_live_term_policy_abort_v1",
        "exception_type": "RuntimeError",
        "exception_message": "design policy live-term cap exceeded",
        "exception_args": ["design policy live-term cap exceeded"],
        "exception_chained_from_exact_parent_helper": True,
        "control_flow_parent_source_sha256": (
            EXPECTED_CONTROL_FLOW_PARENT_SHA256
        ),
        "helper_source_sha256": EXPECTED_V2_HELPER_SHA256,
        "checkpoint_index_zero_based": 71,
        "checkpoint_number_one_based": 72,
        "stage_index": local["stage_index"],
        "stage_group": local["stage"]["group"],
        "batch_in_stage": local["batch_start"] // 4,
        "gate_occurrence_first_zero_based": local["gate_index"],
        "gate_occurrence_last_zero_based": local["gate_index"] + 3,
        "gate_batch_sha256": helper.gate_batch_sha256(batch),
        "input_expansion_count": local["input_count"],
        "input_expansion_sha256": local["input_sha"],
        "pretruncation_expansion_count": pre_count,
        "max_single_expansion_terms": cap,
        "observed_excess_terms": pre_count - cap,
        "policy_relation": (
            "pretruncation_expansion_count>max_single_expansion_terms"
        ),
        "attempted_gate_batch_propagated": True,
        "policy_cap_check_reached": True,
        "q72_pretruncation_digest_computed": False,
        "q72_ranking_performed": False,
        "q72_candidate_rows_constructed": False,
        "q72_selection_performed": False,
        "q72_commit_performed": False,
        "q72_checkpoint_record_constructed": False,
        "q72_partial_expansion_committed": False,
        "q71_committed_record_sha256": q71_sha,
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
        "D q72 resource-policy abort",
    )

    self_sha = sha256(parent._VERIFIED_SELF_SOURCE_BYTES)
    components = parent.execution_components(
        MODE,
        self_sha,
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
    records = copy.deepcopy(records)
    history = list(history)
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
        "screen_source_sha256": self_sha,
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
        "kernel_capability_limits": dict(local["kernel"].RESOURCE_LIMITS),
        "proposed_policy_caps": dict(caps),
        "root_globals_before": copy.deepcopy(local["root_before"]),
        "root_globals_after": root_after,
        "root_globals_unchanged": True,
        "attempted_checkpoint_count": 72,
        "completed_checkpoint_count": 71,
        "failure_checkpoint_included": False,
        "selected_K_history": history,
        "selected_K_history_sha256": sha256(canonical_bytes(history)),
        "records": records,
        "records_sha256": sha256(canonical_bytes(records)),
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
        "D q72 structured resource-abort parent result",
    )
    return result


def execute_parent_with_structured_abort(
    parent: Any,
    repo: Path,
) -> Dict[str, Any]:
    """Execute once, structuring only the exact q72 live-term policy abort."""

    try:
        return normalize_completed_parent_result(
            parent._run_verified(repo, MODE)
        )
    except RuntimeError as exception:
        if type(exception) is not RuntimeError or exception.args != (
            "design policy live-term cap exceeded",
        ):
            raise
        return build_live_term_abort_parent_result(parent, exception)


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


def require_handoff_top_level_keys(result: Any) -> None:
    if type(result) is not dict:
        raise RuntimeError("D q72 result is not an exact dict")
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
            "D q72 top-level exact key-set drift: "
            f"missing={missing}, extra={extra}"
        )


def validate_parent_source_custody(value: Any) -> Dict[str, str]:
    require_exact_keys(
        value,
        frozenset(EXPECTED_PARENT_SOURCE_CUSTODY),
        "D q72 raw parent source custody",
    )
    for path, expected_sha in EXPECTED_PARENT_SOURCE_CUSTODY.items():
        observed_sha = value.get(path)
        if observed_sha != expected_sha:
            raise RuntimeError(
                f"D q72 raw parent source custody hash drift: {path}"
            )
        if not is_canonical_sha256(observed_sha):
            raise RuntimeError(
                f"D q72 raw parent source custody digest schema drift: {path}"
            )
    return dict(value)


def expected_final_source_custody(
    self_sha: str,
    wrapper_sha: str,
) -> Dict[str, str]:
    if not is_canonical_sha256(self_sha):
        raise RuntimeError("D q72 self custody digest schema drift")
    if wrapper_sha != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError("D q72 wrapper custody digest drift")
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
    """Validate one exact q71/q72 success or failure ledger record."""

    if type(record) is not dict or type(previous) is not dict:
        raise RuntimeError(f"D q{checkpoint} record continuity type drift")
    status = record.get("status")
    if status == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        expected_keys = Q70_SUCCESS_RECORD_KEYS
    elif status == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE":
        expected_keys = Q70_FAILURE_RECORD_KEYS
    else:
        raise RuntimeError(f"D q{checkpoint} terminal status drift")
    require_exact_keys(record, expected_keys, f"D q{checkpoint} record")

    expected_scalars = {
        "checkpoint_index_zero_based": checkpoint - 1,
        "checkpoint_number_one_based": checkpoint,
        "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
        "gate_occurrence_last_zero_based": 4 * checkpoint - 1,
        "input_expansion_count": previous["retained_expansion_count"],
        "input_expansion_sha256": previous["retained_expansion_sha256"],
        "E_before_ticks": previous["E_after_ticks"],
        "budget_prefix_cap_ticks": (
            EXPECTED_Q71_PREFIX_CAP_TICKS
            if checkpoint == 71
            else EXPECTED_Q72_PREFIX_CAP_TICKS
        ),
        **EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint],
    }
    for key, value in expected_scalars.items():
        if not exact_value_equal(record.get(key), value):
            raise RuntimeError(f"D q{checkpoint} exact ledger drift: {key}")
    for key in (
        "gate_batch_sha256",
        "input_expansion_sha256",
        "pretruncation_expansion_sha256",
        "ranked_suffix_sha256",
    ):
        if not is_canonical_sha256(record.get(key)):
            raise RuntimeError(f"D q{checkpoint} digest schema drift: {key}")
    for key in (
        "input_expansion_count",
        "pretruncation_expansion_count",
        "peak_live_terms_this_checkpoint",
        "peak_live_terms_cumulative",
        "term_gate_visits_increment",
        "term_gate_visits_cumulative",
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    ):
        if type(record.get(key)) is not int or record[key] < 0:
            raise RuntimeError(f"D q{checkpoint} integer ledger drift: {key}")
    minimum_peak = max(
        record["input_expansion_count"],
        record["pretruncation_expansion_count"],
    )
    if record["peak_live_terms_this_checkpoint"] < minimum_peak:
        raise RuntimeError(f"D q{checkpoint} checkpoint peak below live terms")
    if record["term_gate_visits_increment"] < record["input_expansion_count"]:
        raise RuntimeError(f"D q{checkpoint} gate visits below first-gate input")
    pretruncation_cap = min(
        POLICY_CAPS_BASE["max_single_expansion_terms"],
        POLICY_CAPS_BASE["max_digest_terms"],
    )
    if record["pretruncation_expansion_count"] > pretruncation_cap:
        raise RuntimeError(f"D q{checkpoint} pretruncation exceeds policy cap")
    if record["peak_live_terms_this_checkpoint"] > (
        POLICY_CAPS_BASE["max_single_expansion_terms"]
    ):
        raise RuntimeError(f"D q{checkpoint} checkpoint peak exceeds policy cap")
    if record["term_gate_visits_cumulative"] > (
        POLICY_CAPS_BASE["max_term_gate_visits"]
    ):
        raise RuntimeError(f"D q{checkpoint} cumulative visits exceed policy cap")

    E_before = parse_canonical_nonnegative_decimal(
        record["E_before_ticks"],
        f"D q{checkpoint} E-before",
    )
    prefix_cap = parse_canonical_nonnegative_decimal(
        record["budget_prefix_cap_ticks"],
        f"D q{checkpoint} prefix cap",
    )
    slack = parse_canonical_nonnegative_decimal(
        record["prefix_slack_before_selection_ticks"],
        f"D q{checkpoint} prefix slack",
    )
    rounding_increment = parse_canonical_nonnegative_decimal(
        record["rounding_increment_scaled_ticks_squared"],
        f"D q{checkpoint} rounding increment",
    )
    rounding_cumulative = parse_canonical_nonnegative_decimal(
        record["rounding_cumulative_scaled_ticks_squared"],
        f"D q{checkpoint} rounding cumulative",
    )
    previous_rounding = parse_canonical_nonnegative_decimal(
        previous["rounding_cumulative_scaled_ticks_squared"],
        f"D q{checkpoint - 1} rounding cumulative",
    )
    if slack != prefix_cap - E_before:
        raise RuntimeError(f"D q{checkpoint} prefix slack recurrence drift")
    if rounding_increment < 0 or rounding_cumulative != (
        previous_rounding + rounding_increment
    ):
        raise RuntimeError(f"D q{checkpoint} rounding recurrence drift")
    if record["term_gate_visits_cumulative"] != (
        previous["term_gate_visits_cumulative"]
        + record["term_gate_visits_increment"]
    ):
        raise RuntimeError(f"D q{checkpoint} visit recurrence drift")
    if record["peak_live_terms_cumulative"] != max(
        previous["peak_live_terms_cumulative"],
        record["peak_live_terms_this_checkpoint"],
    ):
        raise RuntimeError(f"D q{checkpoint} peak recurrence drift")
    for key, policy_key in (
        (
            "maximum_expansion_coefficient_tick_bits",
            "max_expansion_coefficient_tick_bits",
        ),
        ("maximum_product_bits", "max_product_bits"),
    ):
        if record[key] < previous[key]:
            raise RuntimeError(f"D q{checkpoint} cumulative maximum decreased: {key}")
        if record[key] > POLICY_CAPS_BASE[policy_key]:
            raise RuntimeError(f"D q{checkpoint} cumulative maximum exceeds cap: {key}")

    pre_count = record["pretruncation_expansion_count"]
    rows = record.get("candidate_records")
    if type(rows) is not list or len(rows) != len(D_CANDIDATES):
        raise RuntimeError(f"D q{checkpoint} candidate row count drift")
    feasible_indices = []
    drops = []
    for candidate_index, (configured_K, row) in enumerate(
        zip(D_CANDIDATES, rows)
    ):
        require_exact_keys(
            row,
            CANDIDATE_RECORD_KEYS,
            f"D q{checkpoint} candidate row {candidate_index}",
        )
        effective = min(configured_K, pre_count)
        expected = {
            "candidate_index": candidate_index,
            "configured_K": configured_K,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }
        for key, value in expected.items():
            if not exact_value_equal(row.get(key), value):
                raise RuntimeError(
                    f"D q{checkpoint} candidate row drift: {key}"
                )
        drop = parse_canonical_nonnegative_decimal(
            row["drop_ticks"],
            f"D q{checkpoint} candidate {candidate_index} drop",
        )
        E_after = parse_canonical_nonnegative_decimal(
            row["E_after_if_selected_ticks"],
            f"D q{checkpoint} candidate {candidate_index} E-after",
        )
        if drop < 0 or E_after != E_before + drop:
            raise RuntimeError(f"D q{checkpoint} candidate E recurrence drift")
        if row["dropped_term_count"] == 0 and drop != 0:
            raise RuntimeError(
                f"D q{checkpoint} zero-drop candidate arithmetic drift"
            )
        feasible = E_after <= prefix_cap
        if row.get("feasible_under_current_prefix_cap") is not feasible:
            raise RuntimeError(
                f"D q{checkpoint} candidate feasibility label drift"
            )
        drops.append(drop)
        if feasible:
            feasible_indices.append(candidate_index)
    if drops != sorted(drops, reverse=True):
        raise RuntimeError(f"D q{checkpoint} candidate ranking drift")

    counterfactual = record.get("removed_491520_counterfactual")
    require_exact_keys(
        counterfactual,
        REMOVED_COUNTERFACTUAL_KEYS,
        f"D q{checkpoint} removed-491520 counterfactual",
    )
    expected_effective = min(491_520, pre_count)
    if not exact_value_equal(counterfactual.get("configured_K"), 491_520):
        raise RuntimeError(f"D q{checkpoint} counterfactual K drift")
    if not exact_value_equal(
        counterfactual.get("effective_retained_count"), expected_effective
    ):
        raise RuntimeError(f"D q{checkpoint} counterfactual effective-K drift")
    if not exact_value_equal(
        counterfactual.get("dropped_term_count"),
        pre_count - expected_effective,
    ):
        raise RuntimeError(f"D q{checkpoint} counterfactual drop-count drift")
    counterfactual_drop = parse_canonical_nonnegative_decimal(
        counterfactual["drop_ticks"],
        f"D q{checkpoint} counterfactual drop",
    )
    counterfactual_E_after = parse_canonical_nonnegative_decimal(
        counterfactual["E_after_if_selected_ticks"],
        f"D q{checkpoint} counterfactual E-after",
    )
    if counterfactual_drop < 0 or counterfactual_E_after != (
        E_before + counterfactual_drop
    ):
        raise RuntimeError(f"D q{checkpoint} counterfactual E recurrence drift")
    counterfactual_feasible = counterfactual_E_after <= prefix_cap
    if counterfactual.get("feasible_under_current_prefix_cap") is not (
        counterfactual_feasible
    ):
        raise RuntimeError(f"D q{checkpoint} counterfactual feasibility drift")
    lower_index = 28
    upper_index = 29
    if (
        D_CANDIDATES[lower_index] != 475_136
        or D_CANDIDATES[upper_index] != 507_904
    ):
        raise RuntimeError("D counterfactual adjacency index drift")
    lower_row = rows[lower_index]
    upper_row = rows[upper_index]
    lower_drop = int(lower_row["drop_ticks"])
    upper_drop = int(upper_row["drop_ticks"])
    lower_E_after = int(lower_row["E_after_if_selected_ticks"])
    upper_E_after = int(upper_row["E_after_if_selected_ticks"])
    counterfactual_dropped = counterfactual["dropped_term_count"]
    if not lower_drop >= counterfactual_drop >= upper_drop:
        raise RuntimeError(f"D q{checkpoint} counterfactual drop adjacency drift")
    if not lower_E_after >= counterfactual_E_after >= upper_E_after:
        raise RuntimeError(f"D q{checkpoint} counterfactual E adjacency drift")
    if not (
        lower_row["dropped_term_count"]
        >= counterfactual_dropped
        >= upper_row["dropped_term_count"]
    ):
        raise RuntimeError(
            f"D q{checkpoint} counterfactual dropped-count adjacency drift"
        )

    if status == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        if not feasible_indices:
            raise RuntimeError(f"D q{checkpoint} success has no feasible row")
        selected_index = feasible_indices[0]
        selected_row = rows[selected_index]
        selected_K = D_CANDIDATES[selected_index]
        expected_selection = {
            "selected_candidate_index": selected_index,
            "selected_K": selected_K,
            "selected_effective_retained_count": (
                selected_row["effective_retained_count"]
            ),
            "selected_dropped_term_count": selected_row["dropped_term_count"],
            "selected_drop_ticks": selected_row["drop_ticks"],
            "retained_expansion_count": selected_row["effective_retained_count"],
            "E_after_ticks": selected_row["E_after_if_selected_ticks"],
        }
        for key, value in expected_selection.items():
            if not exact_value_equal(record.get(key), value):
                raise RuntimeError(f"D q{checkpoint} first-feasible drift: {key}")
        for key in (
            "selected_dropped_terms_sha256",
            "retained_expansion_sha256",
        ):
            if not is_canonical_sha256(record.get(key)):
                raise RuntimeError(f"D q{checkpoint} success digest drift: {key}")
        for key in (
            "minimum_retained_abs_upper_ticks",
            "maximum_dropped_abs_upper_ticks",
        ):
            parse_canonical_nonnegative_decimal(
                record[key],
                f"D q{checkpoint} success interval {key}",
            )
        if not exact_value_equal(
            counterfactual.get("actual_selected_K"), selected_K
        ):
            raise RuntimeError(f"D q{checkpoint} counterfactual selection drift")
        expected_would_precede = (
            counterfactual_feasible and 491_520 < selected_K
        )
        expected_would_be_selected = (
            counterfactual_feasible
            and (selected_K is None or 491_520 < selected_K)
        )
        if counterfactual.get("would_precede_selected") is not (
            expected_would_precede
        ):
            raise RuntimeError(f"D q{checkpoint} counterfactual order drift")
        if counterfactual.get("would_be_selected_if_inserted") is not (
            expected_would_be_selected
        ):
            raise RuntimeError(f"D q{checkpoint} counterfactual choice drift")
        return selected_K

    if feasible_indices:
        raise RuntimeError(f"D q{checkpoint} failure contains a feasible row")
    if record.get("selected_candidate_index") is not None:
        raise RuntimeError(f"D q{checkpoint} failure selected an index")
    if record.get("selected_K") is not None:
        raise RuntimeError(f"D q{checkpoint} failure selected K")
    if counterfactual.get("actual_selected_K") is not None:
        raise RuntimeError(f"D q{checkpoint} failure counterfactual selected K")
    expected_would_precede = False
    expected_would_be_selected = counterfactual_feasible
    if counterfactual.get("would_precede_selected") is not (
        expected_would_precede
    ):
        raise RuntimeError(f"D q{checkpoint} failure counterfactual order drift")
    if counterfactual.get("would_be_selected_if_inserted") is not (
        expected_would_be_selected
    ):
        raise RuntimeError(f"D q{checkpoint} failure counterfactual choice drift")
    if counterfactual_feasible:
        raise RuntimeError(
            f"D q{checkpoint} failure counterfactual is unexpectedly feasible"
        )
    minimum_K = record.get("minimum_effective_K_to_meet_prefix")
    excess = record.get("required_K_excess_over_policy_maximum")
    if type(minimum_K) is not int or type(excess) is not int:
        raise RuntimeError(f"D q{checkpoint} failure minimum-K type drift")
    if (
        minimum_K <= K622592
        or minimum_K > pre_count
        or excess != minimum_K - K622592
    ):
        raise RuntimeError(f"D q{checkpoint} failure excess-K drift")
    maximum_excess = parse_canonical_nonnegative_decimal(
        record["maximum_candidate_drop_excess_over_slack_ticks"],
        f"D q{checkpoint} failure maximum excess",
    )
    if maximum_excess != drops[-1] - slack or maximum_excess <= 0:
        raise RuntimeError(f"D q{checkpoint} failure cap excess drift")
    return None


def validate_resource_policy_abort(
    result: Mapping[str, Any],
    q71: Mapping[str, Any],
) -> Dict[str, Any] | None:
    abort = result.get("resource_policy_abort")
    abort_sha = result.get("resource_policy_abort_sha256")
    if abort is None:
        if abort_sha is not None:
            raise RuntimeError("D q72 null resource abort has a digest")
        return None
    require_exact_keys(
        abort,
        RESOURCE_POLICY_ABORT_KEYS,
        "D q72 resource-policy abort",
    )
    if abort_sha != sha256(canonical_bytes(abort)):
        raise RuntimeError("D q72 resource-policy abort digest drift")
    if not Q70_SUCCESS_ONLY_KEYS <= frozenset(q71):
        raise RuntimeError("D q72 resource abort lacks a committed q71 success")
    expected = {
        "schema_version": 1,
        "abort_id": "D_k622592_c36_q72_live_term_policy_abort_v1",
        "exception_type": "RuntimeError",
        "exception_message": "design policy live-term cap exceeded",
        "exception_args": ["design policy live-term cap exceeded"],
        "exception_chained_from_exact_parent_helper": True,
        "control_flow_parent_source_sha256": (
            EXPECTED_CONTROL_FLOW_PARENT_SHA256
        ),
        "helper_source_sha256": EXPECTED_V2_HELPER_SHA256,
        "checkpoint_index_zero_based": 71,
        "checkpoint_number_one_based": 72,
        "gate_occurrence_first_zero_based": 284,
        "gate_occurrence_last_zero_based": 287,
        **EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[72],
        "max_single_expansion_terms": POLICY_CAPS_BASE[
            "max_single_expansion_terms"
        ],
        "policy_relation": (
            "pretruncation_expansion_count>max_single_expansion_terms"
        ),
        "attempted_gate_batch_propagated": True,
        "policy_cap_check_reached": True,
        "q72_pretruncation_digest_computed": False,
        "q72_ranking_performed": False,
        "q72_candidate_rows_constructed": False,
        "q72_selection_performed": False,
        "q72_commit_performed": False,
        "q72_checkpoint_record_constructed": False,
        "q72_partial_expansion_committed": False,
        "input_expansion_count": q71["retained_expansion_count"],
        "input_expansion_sha256": q71["retained_expansion_sha256"],
        "q71_committed_record_sha256": sha256(canonical_bytes(q71)),
    }
    for key, value in expected.items():
        if not exact_value_equal(abort.get(key), value):
            raise RuntimeError(f"D q72 resource abort exact drift: {key}")
    for key in (
        "pretruncation_expansion_count",
        "observed_excess_terms",
        "peak_live_terms_this_checkpoint",
        "peak_live_terms_cumulative",
        "term_gate_visits_increment",
        "term_gate_visits_cumulative",
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    ):
        if type(abort.get(key)) is not int or abort[key] < 0:
            raise RuntimeError(f"D q72 resource abort integer drift: {key}")
    pre_count = abort["pretruncation_expansion_count"]
    cap = abort["max_single_expansion_terms"]
    if pre_count <= cap or abort["observed_excess_terms"] != pre_count - cap:
        raise RuntimeError("D q72 resource abort cap relation drift")
    if abort["peak_live_terms_this_checkpoint"] < pre_count:
        raise RuntimeError("D q72 resource abort peak below live terms")
    if abort["peak_live_terms_cumulative"] != max(
        q71["peak_live_terms_cumulative"],
        abort["peak_live_terms_this_checkpoint"],
    ):
        raise RuntimeError("D q72 resource abort peak recurrence drift")
    if abort["term_gate_visits_increment"] < abort["input_expansion_count"]:
        raise RuntimeError("D q72 resource abort gate visits below input")
    if abort["term_gate_visits_cumulative"] != (
        q71["term_gate_visits_cumulative"]
        + abort["term_gate_visits_increment"]
    ):
        raise RuntimeError("D q72 resource abort visit recurrence drift")
    rounding_increment = parse_canonical_nonnegative_decimal(
        abort["rounding_increment_scaled_ticks_squared"],
        "D q72 resource abort rounding increment",
    )
    rounding_cumulative = parse_canonical_nonnegative_decimal(
        abort["rounding_cumulative_scaled_ticks_squared"],
        "D q72 resource abort rounding cumulative",
    )
    if rounding_cumulative != (
        int(q71["rounding_cumulative_scaled_ticks_squared"])
        + rounding_increment
    ):
        raise RuntimeError("D q72 resource abort rounding recurrence drift")
    for key in (
        "maximum_expansion_coefficient_tick_bits",
        "maximum_product_bits",
    ):
        if abort[key] < q71[key]:
            raise RuntimeError(f"D q72 resource abort maximum drift: {key}")
    return dict(abort)


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate exact q1--70 replay plus exactly one legal q72 terminal branch."""

    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "D q72 raw parent top-level result",
    )
    require_exact_keys(
        predecessor,
        EXPECTED_ROUTE_PREDECESSOR_RESULT_KEYS,
        "D q72 route canonical",
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
        "candidate_K_values": list(D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **POLICY_CAPS_BASE,
            "max_candidate_count": len(D_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_LIMITS,
        "candidate_policy_precommitted_at_probe_time": False,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected_invariants.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"D q72 raw parent drift: {key}")

    validate_parent_source_custody(result.get("source_custody"))
    if not exact_value_equal(
        result.get("screen_execution_components"),
        list(EXPECTED_PARENT_EXECUTION_COMPONENTS),
    ):
        raise RuntimeError("D q72 raw component closure drift")
    for value_key, digest_key in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
    ):
        if result.get(digest_key) != sha256(
            canonical_bytes(result.get(value_key))
        ):
            raise RuntimeError(f"D q72 raw nested digest drift: {value_key}")
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
        raise RuntimeError("D q72 raw configuration-reference authority drift")
    predecessor_transform = predecessor["checkpoint_transform"]
    if type(predecessor_transform) is not dict:
        raise RuntimeError("D q72 route transform schema drift")
    expected_raw_transform = predecessor_transform.get(
        "physical_four_gate_control_flow_parent_transform"
    )
    expected_raw_transform_sha = predecessor_transform.get(
        "physical_four_gate_control_flow_parent_transform_sha256"
    )
    if expected_raw_transform_sha != EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256:
        raise RuntimeError("D q72 route raw transform authority pin drift")
    if sha256(canonical_bytes(expected_raw_transform)) != (
        EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
    ):
        raise RuntimeError("D q72 route raw transform digest drift")
    if not exact_value_equal(
        result.get("checkpoint_transform"), expected_raw_transform
    ):
        raise RuntimeError("D q72 raw checkpoint transform authority drift")
    if result.get("checkpoint_transform_sha256") != (
        EXPECTED_RAW_CONTROL_FLOW_TRANSFORM_SHA256
    ):
        raise RuntimeError("D q72 raw checkpoint transform digest pin drift")
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
            raise RuntimeError(f"D q72 invariant top-level drift: {key}")

    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) not in (71, 72):
        raise RuntimeError("D q72 must attempt q71 and at most q72")
    if type(history) is not list:
        raise RuntimeError("D q72 selected history is not an exact list")
    old_records = predecessor.get("records")
    old_history = predecessor.get("selected_K_history")
    if type(old_records) is not list or len(old_records) != 71:
        raise RuntimeError("D q72 route predecessor record count drift")
    if type(old_history) is not list or len(old_history) != 70:
        raise RuntimeError("D q72 route predecessor history count drift")
    if not exact_value_equal(history[:70], old_history):
        raise RuntimeError("D q72 changed the exact q1-70 selected history")
    if sha256(canonical_bytes(old_records[:70])) != (
        EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
    ):
        raise RuntimeError("D q72 predecessor q1-70 digest drift")
    if sha256(canonical_bytes(history[:70])) != (
        EXPECTED_Q70_SELECTED_HISTORY_SHA256
    ):
        raise RuntimeError("D q72 q1-70 history prefix digest drift")

    for index in range(70):
        old = old_records[index]
        new = records[index]
        require_exact_keys(
            new,
            frozenset(old),
            f"D q{index + 1} extended record",
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
                f"D q72 changed q{index + 1} common record state"
            )
        rows = new.get("candidate_records")
        if (
            type(rows) is not list
            or len(rows) != 36
            or not exact_value_equal(
                rows[:35], old.get("candidate_records")
            )
        ):
            raise RuntimeError(
                f"D q72 changed q{index + 1} predecessor candidate rows"
            )
        appended = rows[35]
        require_exact_keys(
            appended,
            CANDIDATE_RECORD_KEYS,
            f"D q{index + 1} appended candidate row",
        )
        pre_count = new.get("pretruncation_expansion_count")
        if type(pre_count) is not int or pre_count < 0:
            raise RuntimeError(
                f"D q{index + 1} pretruncation count drift"
            )
        effective = min(K622592, pre_count)
        for key, value in {
            "candidate_index": 35,
            "configured_K": K622592,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }.items():
            if not exact_value_equal(appended.get(key), value):
                raise RuntimeError(
                    f"D q{index + 1} appended candidate drift: {key}"
                )
        drop = parse_canonical_nonnegative_decimal(
            appended.get("drop_ticks"),
            f"D q{index + 1} appended drop",
        )
        E_after = parse_canonical_nonnegative_decimal(
            appended.get("E_after_if_selected_ticks"),
            f"D q{index + 1} appended E after",
        )
        E_before = parse_canonical_nonnegative_decimal(
            new.get("E_before_ticks"),
            f"D q{index + 1} E before",
        )
        prefix_cap = parse_canonical_nonnegative_decimal(
            new.get("budget_prefix_cap_ticks"),
            f"D q{index + 1} prefix cap",
        )
        if E_after != E_before + drop:
            raise RuntimeError(
                f"D q{index + 1} appended candidate E recurrence drift"
            )
        predecessor_drop = parse_canonical_nonnegative_decimal(
            rows[34].get("drop_ticks"),
            f"D q{index + 1} predecessor maximum-K drop",
        )
        predecessor_E_after = parse_canonical_nonnegative_decimal(
            rows[34].get("E_after_if_selected_ticks"),
            f"D q{index + 1} predecessor maximum-K E after",
        )
        if (
            drop > predecessor_drop
            or E_after > predecessor_E_after
            or appended["effective_retained_count"]
            < rows[34]["effective_retained_count"]
            or appended["dropped_term_count"]
            > rows[34]["dropped_term_count"]
        ):
            raise RuntimeError(
                f"D q{index + 1} appended candidate ranking drift"
            )
        if appended["dropped_term_count"] == 0 and drop != 0:
            raise RuntimeError(
                f"D q{index + 1} appended zero-drop arithmetic drift"
            )
        if appended.get("feasible_under_current_prefix_cap") is not (
            E_after <= prefix_cap
        ):
            raise RuntimeError(
                f"D q{index + 1} appended candidate feasibility drift"
            )

    q70 = records[69]
    if not exact_value_equal(q70.get("retained_expansion_count"), K606208):
        raise RuntimeError("D q72 q70 retained count anchor drift")
    if q70.get("retained_expansion_sha256") != (
        EXPECTED_Q70_RETAINED_EXPANSION_SHA256
    ):
        raise RuntimeError("D q72 q70 retained digest anchor drift")
    if q70.get("E_after_ticks") != EXPECTED_Q70_E_AFTER_TICKS:
        raise RuntimeError("D q72 q70 cumulative E anchor drift")

    old_q71 = old_records[70]
    new_q71 = records[70]
    excluded = {
        "candidate_records",
        "removed_491520_counterfactual",
        "status",
        "selected_candidate_index",
        "selected_K",
        *Q70_FAILURE_ONLY_KEYS,
        *Q70_SUCCESS_ONLY_KEYS,
    }
    old_shared = {
        key: value for key, value in old_q71.items() if key not in excluded
    }
    if any(key not in new_q71 for key in old_shared):
        raise RuntimeError("D q71 removed a shared propagation field")
    if not exact_value_equal(
        {key: new_q71[key] for key in old_shared}, old_shared
    ):
        raise RuntimeError("D q71 changed shared propagation fields")
    q71_rows = new_q71.get("candidate_records")
    if (
        type(q71_rows) is not list
        or len(q71_rows) != 36
        or not exact_value_equal(
            q71_rows[:35], old_q71.get("candidate_records")
        )
    ):
        raise RuntimeError("D q71 changed predecessor candidate rows")
    appended_q71 = q71_rows[35]
    require_exact_keys(
        appended_q71,
        CANDIDATE_RECORD_KEYS,
        "D q71 appended candidate row",
    )
    pre_count = new_q71.get("pretruncation_expansion_count")
    effective = min(K622592, pre_count)
    for key, value in {
        "candidate_index": 35,
        "configured_K": K622592,
        "effective_retained_count": effective,
        "dropped_term_count": pre_count - effective,
    }.items():
        if not exact_value_equal(appended_q71.get(key), value):
            raise RuntimeError(f"D q71 appended candidate drift: {key}")
    old_counterfactual = old_q71.get("removed_491520_counterfactual")
    new_counterfactual = new_q71.get("removed_491520_counterfactual")
    require_exact_keys(
        new_counterfactual,
        REMOVED_COUNTERFACTUAL_KEYS,
        "D q71 removed-491520 counterfactual",
    )
    choice_keys = {
        "actual_selected_K",
        "would_precede_selected",
        "would_be_selected_if_inserted",
    }
    if not exact_value_equal(
        {
            key: value
            for key, value in new_counterfactual.items()
            if key not in choice_keys
        },
        {
            key: value
            for key, value in old_counterfactual.items()
            if key not in choice_keys
        },
    ):
        raise RuntimeError("D q71 counterfactual arithmetic drift")

    selected_q71 = validate_extended_record(new_q71, q70, 71)
    abort = validate_resource_policy_abort(result, new_q71)
    selected_after_q70 = []
    if selected_q71 is None:
        if abort is not None:
            raise RuntimeError("D q71 failure cannot carry a q72 resource abort")
        if len(records) != 71 or len(history) != 70:
            raise RuntimeError("D q71 failure must terminate before q72")
        branch = "Q71_FAILURE_Q72_NOT_ATTEMPTED"
        expected_summary = {
            "attempted_checkpoint_count": 71,
            "completed_checkpoint_count": 70,
            "horizon_checkpoint_attempted": False,
            "horizon_reached_with_committed_checkpoint": False,
            "screen_terminal_condition": (
                "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            ),
            "failure_checkpoint_included": True,
            "last_committed_cumulative_drop_ticks": EXPECTED_Q70_E_AFTER_TICKS,
        }
    else:
        selected_after_q70.append(selected_q71)
        if abort is not None:
            if len(records) != 71 or len(history) != 71:
                raise RuntimeError(
                    "D q72 resource abort must preserve exactly q1-q71"
                )
            branch = "Q71_SUCCESS_Q72_LIVE_TERM_POLICY_ABORT"
            expected_summary = {
                "attempted_checkpoint_count": 72,
                "completed_checkpoint_count": 71,
                "horizon_checkpoint_attempted": True,
                "horizon_reached_with_committed_checkpoint": False,
                "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
                "failure_checkpoint_included": False,
                "last_committed_cumulative_drop_ticks": records[70][
                    "E_after_ticks"
                ],
            }
        else:
            if len(records) != 72:
                raise RuntimeError("D q71 success must continue through q72")
            selected_q72 = validate_extended_record(records[71], records[70], 72)
            if selected_q72 is None:
                if len(history) != 71:
                    raise RuntimeError("D q72 failure history count drift")
                branch = "Q71_SUCCESS_Q72_FAILURE"
                expected_summary = {
                    "attempted_checkpoint_count": 72,
                    "completed_checkpoint_count": 71,
                    "horizon_checkpoint_attempted": True,
                    "horizon_reached_with_committed_checkpoint": False,
                    "screen_terminal_condition": (
                        "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                    ),
                    "failure_checkpoint_included": True,
                    "last_committed_cumulative_drop_ticks": records[70][
                        "E_after_ticks"
                    ],
                }
            else:
                selected_after_q70.append(selected_q72)
                if len(history) != 72:
                    raise RuntimeError("D q72 success history count drift")
                branch = "Q71_AND_Q72_SUCCESS_HORIZON_REACHED"
                expected_summary = {
                    "attempted_checkpoint_count": 72,
                    "completed_checkpoint_count": 72,
                    "horizon_checkpoint_attempted": True,
                    "horizon_reached_with_committed_checkpoint": True,
                    "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
                    "failure_checkpoint_included": False,
                    "last_committed_cumulative_drop_ticks": records[71][
                        "E_after_ticks"
                    ],
                }
    if not exact_value_equal(
        history, list(old_history) + selected_after_q70
    ):
        raise RuntimeError("D q72 selected history is not the exact replay ledger")
    for key, value in expected_summary.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"D q72 terminal summary drift: {key}")

    final = records[-1]
    failed = (
        abort is None
        and final["status"] == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    )
    expected_failure_sha = sha256(canonical_bytes(final)) if failed else None
    if result.get("failure_record_sha256") != expected_failure_sha:
        raise RuntimeError("D q72 failure-record digest drift")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("D q72 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(
        canonical_bytes(history)
    ):
        raise RuntimeError("D q72 selected history digest drift")
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
            raise RuntimeError(f"D q72 observed resource ledger drift: {key}")
    return {
        "validation_id": "D_k622592_c36_q72_predecessor_handoff_v1",
        "q1_through_q70_common_records_exact": True,
        "q1_through_q70_first_35_candidate_rows_exact": True,
        "q1_through_q70_selected_history_exact": True,
        "q70_records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "q70_selected_history_sha256": EXPECTED_Q70_SELECTED_HISTORY_SHA256,
        "q70_terminal_record_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_Q70_RECORD_SHA256
        ),
        "q71_input_retained_count": K606208,
        "q71_input_retained_sha256": EXPECTED_Q70_RETAINED_EXPANSION_SHA256,
        "q71_input_E_before_ticks": EXPECTED_Q70_E_AFTER_TICKS,
        "q71_prefix_cap_ticks": EXPECTED_Q71_PREFIX_CAP_TICKS,
        "q71_shared_propagation_fields_exact": True,
        "q71_first_35_candidate_rows_exact": True,
        "q71_predecessor_failure_record_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_Q71_FAILURE_SHA256
        ),
        "q71_appended_candidate_index": 35,
        "q71_appended_candidate_K": K622592,
        "q72_prefix_cap_ticks_if_attempted": EXPECTED_Q72_PREFIX_CAP_TICKS,
        "terminal_branch": branch,
        "q72_resource_policy_abort_structured": abort is not None,
        "q72_checkpoint_record_constructed": len(records) == 72,
        "q72_resource_policy_abort_sha256": result[
            "resource_policy_abort_sha256"
        ],
        "q71_and_q72_outcomes_precommitted": False,
    }


def execution_components(parent_components, self_sha, wrapper_sha):
    if type(parent_components) is not list:
        raise RuntimeError("parent component list drift")
    if any(type(item) is not dict for item in parent_components):
        raise RuntimeError("parent component entry is not an exact dict")
    if parent_components != list(EXPECTED_PARENT_EXECUTION_COMPONENTS):
        raise RuntimeError("parent execution component schema drift")
    paths = [item["relative_path"] for item in parent_components]
    if len(paths) != len(set(paths)):
        raise RuntimeError("duplicate parent execution component path")
    components = [{"relative_path": SELF_NAME, "role": "D_k622592_c36_q72_fresh_same_byte_screen", "sha256": self_sha}]
    saw_parent = saw_v6 = saw_v2 = False
    forbidden = {
        ROUTE_PREDECESSOR_SCREEN_NAME,
        ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
        "hubbard_l8_adaptive_k_arithmetic_k606208_c35.py",
    }
    for original in parent_components:
        item = dict(original)
        path = item.get("relative_path")
        if path in forbidden:
            raise RuntimeError("route predecessor became an execution component")
        if path == CONTROL_FLOW_PARENT_NAME:
            if item.get("sha256") != EXPECTED_CONTROL_FLOW_PARENT_SHA256:
                raise RuntimeError("control-flow parent component pin drift")
            item["role"] = "four_gate_control_flow_parent_private_entrypoint"
            saw_parent = True
        elif path == V6_BASELINE_CONFIGURATION_NAME:
            if item.get("sha256") != EXPECTED_V6_BASELINE_CONFIGURATION_SHA256:
                raise RuntimeError("v6 baseline component pin drift")
            saw_v6 = True
            item["role"] = "v6_baseline_configuration_before_declared_override"
        elif path == V2_ARITHMETIC_NAME:
            if item.get("sha256") != EXPECTED_V2_ARITHMETIC_SHA256:
                raise RuntimeError("v2 arithmetic component pin drift")
            saw_v2 = True
            item["role"] = "v2_arithmetic_bytes_beneath_capability_wrapper"
        components.append(item)
        if path == V2_ARITHMETIC_NAME:
            components.append({"relative_path": KERNEL_WRAPPER_NAME, "role": "k622592_c36_capability_override_provider", "sha256": wrapper_sha})
    if not (saw_parent and saw_v6 and saw_v2):
        raise RuntimeError("parent component set incomplete")
    return components


def configuration_reference() -> Dict[str, Any]:
    return {
        "relative_path": V6_BASELINE_CONFIGURATION_NAME,
        "source_sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "role": "v6_baseline_candidates_and_caps_before_direct_override",
        "baseline_D_candidate_K_values_sha256": EXPECTED_V6_D_CANDIDATE_SHA256,
        "baseline_policy_caps_sha256": EXPECTED_V6_POLICY_CAPS_SHA256,
        "compiled_from_verified_bytes": True,
        "module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }


def configuration_override(baseline_d):
    if D_CANDIDATES != baseline_d[1:] + (
        K540672,
        K573440,
        K589824,
        K606208,
        K622592,
    ):
        raise RuntimeError("configuration baseline construction drift")
    unchanged = {k: v for k, v in EXPECTED_V6_POLICY_CAPS.items() if k not in {"max_candidate_K", "max_output_terms_if_successful"}}
    return {
        "override_id": "double_occupancy_k622592_c36_q72_configuration_override_v1",
        "diagnostic_ladder_precommitted_before_replay": True,
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": EXPECTED_V6_D_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 32, "after": 36},
            "candidate_ladder_added": [
                K540672, K573440, K589824, K606208, K622592,
            ],
            "candidate_ladder_removed": [65_536],
            "policy_cap_changes": {
                "max_candidate_K": {"before": 524_288, "after": K622592},
                "max_output_terms_if_successful": {"before": 524_288, "after": K622592},
            },
        },
        "incremental_route_override_from_k606208_c35_q72": {
            "predecessor_candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 35, "after": 36},
            "candidate_ladder_added": [K622592],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {"before": K606208, "after": K622592},
                "max_output_terms_if_successful": {
                    "before": K606208,
                    "after": K622592,
                },
            },
            "predecessor_configuration_override_sha256": EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256,
        },
        "derived_policy_cap": {"field": "max_candidate_count", "derivation": "len(candidate_K_values)", "before_on_route": 35, "after": 36},
        "unchanged_policy_caps": unchanged,
        "magnetization_candidate_configuration_unchanged": True,
        "overridden_fields": [f"MODE_CONFIG.{MODE}.candidates", "POLICY_CAPS_BASE.max_candidate_K", "POLICY_CAPS_BASE.max_output_terms_if_successful"],
    }


def kernel_capability_override(
    wrapper_sha: str,
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "separate_k622592_c36_capability_override_provider",
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
            "max_candidate_count": {"before": 32, "after": 36},
            "max_retained_K": {"before": 524_288, "after": K622592},
        },
        "incremental_route_changes_from_k606208_c35": {
            "max_candidate_count": {"before": 35, "after": 36},
            "max_retained_K": {"before": K606208, "after": K622592},
        },
        "execution_source_layers": [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME],
        "route_predecessor_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def validate_and_relabel(result, predecessor, route_reference, baseline_d, wrapper_sha, manifest, horizon_override):
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q72 relabel requires fresh same-byte self execution")
    require_exact_keys(
        result,
        EXPECTED_PARENT_RESULT_KEYS,
        "control-flow parent top-level result",
    )
    expected = {
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
        "screen_horizon_checkpoint_count": 72,
        "candidate_K_values": list(D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {**POLICY_CAPS_BASE, "max_candidate_count": len(D_CANDIDATES)},
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_LIMITS,
    }
    for key, value in expected.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"control-flow parent result drift: {key}")
    handoff = validate_replay_handoff(result, predecessor)
    old_components = result.get("screen_execution_components")
    if result.get("screen_execution_components_sha256") != sha256(canonical_bytes(old_components)):
        raise RuntimeError("parent component digest drift")
    old_configuration_reference = result.get("configuration_reference")
    if (
        type(old_configuration_reference) is not dict
        or result.get("configuration_reference_sha256")
        != sha256(canonical_bytes(old_configuration_reference))
    ):
        raise RuntimeError("parent configuration reference digest drift")
    old_transform = result.get("checkpoint_transform")
    old_transform_sha = result.get("checkpoint_transform_sha256")
    if old_transform_sha != sha256(canonical_bytes(old_transform)):
        raise RuntimeError("parent transform digest drift")
    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(old_components, self_sha, wrapper_sha)
    baseline_reference = configuration_reference()
    config = configuration_override(baseline_d)
    capability = kernel_capability_override(wrapper_sha, manifest)
    transform = {
        "transform_id": "double_occupancy_four_gate_k622592_c36_q72_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "route_predecessor_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q71_and_q72_outcomes_precommitted": False,
        "incremental_route_semantic_delta": {
            "candidate_K_values_changed": True,
            "policy_caps_changed": True,
            "kernel_capability_limits_changed": True,
            "horizon_checkpoint_count": {"before": 72, "after": 72},
        },
        "overridden_semantics": [
            "candidate_K_values",
            "policy_max_candidate_K",
            "policy_max_output_terms_if_successful",
            "derived_policy_max_candidate_count",
            "kernel_max_retained_K",
            "kernel_max_candidate_count",
            "double_occupancy_horizon_checkpoint_count",
        ],
    }
    parent_custody = validate_parent_source_custody(result.get("source_custody"))
    custody = expected_final_source_custody(self_sha, wrapper_sha)
    if parent_custody != {
        path: custody[path] for path in EXPECTED_PARENT_SOURCE_CUSTODY
    }:
        raise RuntimeError("D q72 parent custody changed during relabel")
    if len(custody) != 10:
        raise RuntimeError("D q72 final source custody cardinality drift")
    result.update({
        "transcript_fingerprint": "hubbard_l8_double_occupancy_adaptive_k_four_gate_k622592_c36_q72_screen_v1",
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
        "kernel_capability_wrapper_source_sha256": wrapper_sha,
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": baseline_reference,
        "configuration_reference_sha256": sha256(canonical_bytes(baseline_reference)),
        "configuration_override": config,
        "configuration_override_sha256": sha256(canonical_bytes(config)),
        "kernel_capability_override": capability,
        "kernel_capability_override_sha256": sha256(canonical_bytes(capability)),
        "parent_horizon_override": dict(horizon_override),
        "parent_horizon_override_sha256": sha256(canonical_bytes(horizon_override)),
        "route_predecessor_reference": dict(route_reference),
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
        "D q72 relabelled top-level result",
    )
    if result.get("source_custody") != expected_final_source_custody(
        self_sha,
        wrapper_sha,
    ):
        raise RuntimeError("D q72 final source custody closure drift")
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q72 screen requires fresh same-byte self execution")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_control_flow_parent(repo)
    configuration, baseline_d = load_configured_v6_baseline(repo)
    wrapper, wrapper_sha, manifest = load_kernel_wrapper(repo)
    horizon = configure_parent_execution(parent, configuration, wrapper)
    result = execute_parent_with_structured_abort(parent, repo)
    predecessor, route_reference = load_route_reference(repo)
    return validate_and_relabel(result, predecessor, route_reference, baseline_d, wrapper_sha, manifest, horizon)


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_double_occupancy_k622592_c36_q72_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("D q72 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("D q72 transcript exceeds output byte cap")
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
