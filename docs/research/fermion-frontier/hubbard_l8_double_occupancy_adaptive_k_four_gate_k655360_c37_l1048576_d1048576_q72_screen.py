#!/usr/bin/env python3
"""Source-pinned D K=655360/C=37, live/digest=1048576 q72 screen.

The only execution parent is a fresh same-byte copy of the exact four-gate
control-flow screen, which owns a complete replay from checkpoint one.  The
K622592/C36 live/digest=1048576 screen and canonical transcript are read only
after replay as exact comparison evidence for q1--q72; neither is compiled,
executed, used for propagation, or used for state resume.

K=638976 is deliberately not an execution candidate.  Its only authority is
the fixed four-gate q72 predecessor-state/prefix threshold evidence recorded
in ``EXCLUDED_K638976_EVIDENCE``; no candidate row or drop value is asserted.
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
    "k655360_c37_l1048576_d1048576_q72_screen.py"
)
CONTROL_FLOW_PARENT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k655360_c37.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_l1048576_d1048576_q72_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k622592_c36_l1048576_d1048576_q72_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k655360_c37_l1048576_d1048576_q72_transcript.json"
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
    "2acf8f8329376ab06ad4c079af633d23bcc6a32fa20af654e5c3dbbb32093d54"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "62c889baf0676150344f06ccf5d48132e121ade399c77dd1b85727f5002dd6e5"
)
EXPECTED_KERNEL_SOURCE_LAYERS_SHA256 = (
    "38332356b52aededd8d1385e71d9a217b950305b26d96f9b2aa33b6d115c4443"
)
EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256 = (
    "24051ef0d1df6ce984c12ee65819e3ae9fdd4f9cdc2ce47a3bd86ab13bf90c0c"
)
EXPECTED_ROUTE_KERNEL_SHA256 = (
    "7ac6c87f3d789ad62540cbc96e81f0a092594b0524eec3f9b05e7ffec2124838"
)
EXPECTED_ROUTE_KERNEL_MANIFEST_SHA256 = (
    "fc82c41b1a1dd82fbb34e205ea347b0ba41b08c5fd2ebed6a599593fe95c1b34"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "57a68b3086cd2ed2d484d0f835a190dc768b12bbb2b8d6a3c99c86f6ea6bda8d"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "4bdc16622a52a57ab6d43da04d77c6c67defdb36c2630a9d51178b65ac1e6ddd"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SIZE = 739_189
EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256 = (
    "21d7ff35dc1a6dc725eda9b16ecde3e64dd8b683c0a830fbc7e75e8d146733be"
)
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "6bd9a1a5e6599efd78dda59025281af2d8a030beb02c3f145d9f3e055ed18d22"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "18e76e6b8a2eb970bf5930c79901f97d24e9e5cfed865d5a8c8e27bee5bec807"
)
EXPECTED_ROUTE_PREDECESSOR_Q71_RECORD_SHA256 = (
    "bb5fffe2871aefed25755423d43b0689d48df7e954bb524e3041268a9fc22ad2"
)
EXPECTED_ROUTE_PREDECESSOR_Q72_FAILURE_SHA256 = (
    "caeeb5a3854abdfb4fe2100ce0d5df20cc757dc6e153b5099efa8bd25ee648c7"
)
EXPECTED_ROUTE_PREDECESSOR_Q72_ROWS_SHA256 = (
    "8ec5b4b4ab3bc981f81cefb8f8ba4e8b86394918242f21cddc18861db369ddd9"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "5ab17c2bb62a5b86ef55bbea54353d21b023f03497d590f73775e3edaddd522d"
)
EXPECTED_ROUTE_PREDECESSOR_KERNEL_OVERRIDE_SHA256 = (
    "3fb44fe999a8f5745b0eb8aa9a326d4bafda499ed9e576fe0a118571e998b3ea"
)
EXPECTED_ROUTE_PREDECESSOR_PARENT_HORIZON_OVERRIDE_SHA256 = (
    "927db7ca5d269edc666f97d7fca6a0bc3b02933c98a55e5a8994c9efbb49e589"
)
EXPECTED_ROUTE_PREDECESSOR_ROUTE_REFERENCE_SHA256 = (
    "038150c686da0a3eb2615ebcc02e44d0c2c1c7f6e0fabaa5d0fa62b8e5629dc0"
)
EXPECTED_ROUTE_PREDECESSOR_HANDOFF_SHA256 = (
    "1a555b346b9b719cf206de929a155aa03694cce6b1dd36b295c8ae37c8ef020d"
)
EXPECTED_ROUTE_PREDECESSOR_COMPONENTS_SHA256 = (
    "c944b2a5949a8277368fa77661c62d44a16633acc662fde360bbee001c148ca3"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "9a28d63449e1f870a1c0c4f1b9e6a78de5e7176c3cc99074aa42011787614ac2"
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
K638976 = 638_976
K655360 = 655_360
LIVE_AND_DIGEST_CAP = 1_048_576

V6_D_CANDIDATES = (
    65_536, 73_728, 81_920, 90_112, 98_304, 106_496, 114_688,
    122_880, 131_072, 147_456, 163_840, 180_224, 196_608, 212_992,
    229_376, 245_760, 262_144, 278_528, 294_912, 311_296, 327_680,
    344_064, 360_448, 376_832, 393_216, 409_600, 425_984, 442_368,
    458_752, 475_136, 507_904, 524_288,
)
PREDECESSOR_D_CANDIDATES = (
    V6_D_CANDIDATES[1:] + (
        K540672, K573440, K589824, K606208, K622592,
    )
)
D_CANDIDATES = PREDECESSOR_D_CANDIDATES + (K655360,)
EXPECTED_V6_D_CANDIDATE_SHA256 = (
    "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
)
EXPECTED_V6_M_CANDIDATE_SHA256 = (
    "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
)
EXPECTED_PREDECESSOR_CANDIDATE_SHA256 = (
    "5ab222cdcd073227d6d5e23f881ce94511dab86c35b6aab53c72de9f403367fc"
)
EXPECTED_CANDIDATE_SHA256 = (
    "66076fbdd8558ff2da161fae605ad594392cff569c3d523abc8524d666ae3dd8"
)
EXPECTED_Q71_RETAINED_EXPANSION_SHA256 = (
    "50969113d522dadfedced0960548674551acd1ddf56024bb673ce4ee1272b0f4"
)
EXPECTED_Q71_E_AFTER_TICKS = "2288967389826722"
EXPECTED_Q71_PREFIX_CAP_TICKS = "2289007495823880"
EXPECTED_Q72_PREFIX_CAP_TICKS = "2289089997813814"
EXPECTED_Q72_RANKED_SUFFIX_SHA256 = (
    "9e9bbc7b188fe28962229358a07b68c5e38c0f9f15921e3505f4e3a27a1fe7a4"
)
EXPECTED_Q72_PRETRUNCATION_EXPANSION_SHA256 = (
    "c9a791a2fd9eb9caf971b87917973afe300d1839b0a2bb0b01e315f8b6d06f96"
)
EXPECTED_Q72_MINIMUM_EFFECTIVE_K = 642_206
EXCLUDED_K638976_EVIDENCE = {
    "configured_K": K638976,
    "minimum_effective_K_to_meet_prefix": EXPECTED_Q72_MINIMUM_EFFECTIVE_K,
    "shortfall": EXPECTED_Q72_MINIMUM_EFFECTIVE_K - K638976,
    "evidence_scope": "fixed_four_gate_q72_predecessor_state_prefix_only",
    "execution_candidate": False,
    "candidate_row_constructed": False,
    "exact_drop_ticks_asserted": False,
}
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
    "max_candidate_K": K622592,
    "max_output_terms_if_successful": K622592,
    "max_single_expansion_terms": LIVE_AND_DIGEST_CAP,
    "max_digest_terms": LIVE_AND_DIGEST_CAP,
}
POLICY_CAPS_BASE = {
    **EXPECTED_PREDECESSOR_POLICY_CAPS,
    "max_candidate_K": K655360,
    "max_output_terms_if_successful": K655360,
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
    "max_candidate_count": 36,
    "max_retained_K": K622592,
}
EXPECTED_WRAPPED_KERNEL_LIMITS = {
    **EXPECTED_V2_KERNEL_LIMITS,
    "max_candidate_count": 37,
    "max_retained_K": K655360,
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
    EXPECTED_RELABELLED_RESULT_KEYS
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
    if len(V6_D_CANDIDATES) != 32 or len(PREDECESSOR_D_CANDIDATES) != 36:
        raise RuntimeError("D predecessor candidate count drift")
    if (
        len(D_CANDIDATES) != 37
        or D_CANDIDATES != PREDECESSOR_D_CANDIDATES + (K655360,)
    ):
        raise RuntimeError("D K655360 route is not an exact append")
    if any(left >= right for left, right in zip(D_CANDIDATES, D_CANDIDATES[1:])):
        raise RuntimeError("D candidate order drift")
    if sha256(canonical_bytes(list(PREDECESSOR_D_CANDIDATES))) != EXPECTED_PREDECESSOR_CANDIDATE_SHA256:
        raise RuntimeError("D predecessor candidate digest drift")
    if sha256(canonical_bytes(list(D_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("D candidate digest drift")
    direct_expected = {
        "max_candidate_K",
        "max_output_terms_if_successful",
        "max_single_expansion_terms",
        "max_digest_terms",
    }
    route_expected = {"max_candidate_K", "max_output_terms_if_successful"}
    if changed_keys(EXPECTED_V6_POLICY_CAPS, POLICY_CAPS_BASE) != direct_expected:
        raise RuntimeError("direct policy override field drift")
    if (
        changed_keys(EXPECTED_PREDECESSOR_POLICY_CAPS, POLICY_CAPS_BASE)
        != route_expected
    ):
        raise RuntimeError("route policy override changed a non-K field")
    if POLICY_CAPS_BASE["max_candidate_K"] != D_CANDIDATES[-1]:
        raise RuntimeError("policy maximum and D ladder disagree")
    if EXCLUDED_K638976_EVIDENCE != {
        "configured_K": K638976,
        "minimum_effective_K_to_meet_prefix": 642_206,
        "shortfall": 3_230,
        "evidence_scope": "fixed_four_gate_q72_predecessor_state_prefix_only",
        "execution_candidate": False,
        "candidate_row_constructed": False,
        "exact_drop_ticks_asserted": False,
    }:
        raise RuntimeError("excluded K638976 evidence drift")
    if K638976 in D_CANDIDATES:
        raise RuntimeError("excluded K638976 became an execution candidate")
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
        "pinned_four_gate_parent_for_d_k655360_c37_q72",
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
    return parent


def load_configured_v6_baseline(repo: Path) -> Tuple[Any, Tuple[int, ...]]:
    configuration, _ = load_pinned_module(
        repo, V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_for_d_k655360_c37_q72",
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
    wrapper = types.ModuleType("pinned_k655360_c37_arithmetic_wrapper")
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


def load_route_reference(
    repo: Path,
    *,
    replay_completed: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load the current policy screen/canonical as post-replay evidence only."""

    if replay_completed is not True:
        raise RuntimeError("route evidence cannot be loaded before replay")
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
    if len(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SIZE:
        raise RuntimeError("route predecessor transcript size drift")
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
            "k622592_c36_l1048576_d1048576_q72_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": EXTENDED_HORIZON,
        "screen_terminal_condition": (
            "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        ),
        "attempted_checkpoint_count": 72,
        "completed_checkpoint_count": 71,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": False,
        "failure_checkpoint_included": True,
        "failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q72_FAILURE_SHA256,
        "candidate_K_values": list(PREDECESSOR_D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_PREDECESSOR_POLICY_CAPS,
            "max_candidate_count": len(PREDECESSOR_D_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_ROUTE_KERNEL_LIMITS,
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "resource_policy_abort": None,
        "resource_policy_abort_sha256": None,
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
    if type(records) is not list or len(records) != 72:
        raise RuntimeError("route q72 record count drift")
    if type(history) is not list or len(history) != 71:
        raise RuntimeError("route q72 history count drift")
    if sha256(canonical_bytes(records)) != (
        EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256
    ):
        raise RuntimeError("route records digest drift")
    if sha256(canonical_bytes(records[:71])) != (
        EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
    ):
        raise RuntimeError("route q1-q71 records digest drift")
    if sha256(canonical_bytes(history)) != (
        EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
    ):
        raise RuntimeError("route history digest drift")
    q71 = records[70]
    q72 = records[71]
    if sha256(canonical_bytes(q71)) != (
        EXPECTED_ROUTE_PREDECESSOR_Q71_RECORD_SHA256
    ):
        raise RuntimeError("route q71 record digest drift")
    if sha256(canonical_bytes(q72)) != (
        EXPECTED_ROUTE_PREDECESSOR_Q72_FAILURE_SHA256
    ):
        raise RuntimeError("route q72 failure digest drift")
    if sha256(canonical_bytes(q72.get("candidate_records"))) != (
        EXPECTED_ROUTE_PREDECESSOR_Q72_ROWS_SHA256
    ):
        raise RuntimeError("route q72 candidate-row digest drift")

    require_exact_keys(q71, Q70_SUCCESS_RECORD_KEYS, "route q71 success record")
    for key, value in {
        "checkpoint_number_one_based": 71,
        "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
        "selected_candidate_index": 35,
        "selected_K": K622592,
        "retained_expansion_count": K622592,
        "retained_expansion_sha256": EXPECTED_Q71_RETAINED_EXPANSION_SHA256,
        "E_after_ticks": EXPECTED_Q71_E_AFTER_TICKS,
    }.items():
        if not exact_value_equal(q71.get(key), value):
            raise RuntimeError(f"route predecessor q71 drift: {key}")

    require_exact_keys(q72, Q70_FAILURE_RECORD_KEYS, "route q72 failure record")
    q72_rows = q72.get("candidate_records")
    if type(q72_rows) is not list or len(q72_rows) != 36:
        raise RuntimeError("route q72 candidate row count drift")
    if not exact_value_equal(
        [row.get("configured_K") for row in q72_rows],
        list(PREDECESSOR_D_CANDIDATES),
    ):
        raise RuntimeError("route q72 candidate row order drift")
    if any(
        row.get("feasible_under_current_prefix_cap") is not False
        for row in q72_rows
    ):
        raise RuntimeError("route q72 unexpectedly contains a feasible row")
    for key, value in {
        "checkpoint_number_one_based": 72,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "input_expansion_count": K622592,
        "input_expansion_sha256": EXPECTED_Q71_RETAINED_EXPANSION_SHA256,
        "E_before_ticks": EXPECTED_Q71_E_AFTER_TICKS,
        "budget_prefix_cap_ticks": EXPECTED_Q72_PREFIX_CAP_TICKS,
        "pretruncation_expansion_count": 799_279,
        "pretruncation_expansion_sha256": (
            EXPECTED_Q72_PRETRUNCATION_EXPANSION_SHA256
        ),
        "ranked_suffix_sha256": EXPECTED_Q72_RANKED_SUFFIX_SHA256,
        "minimum_effective_K_to_meet_prefix": (
            EXPECTED_Q72_MINIMUM_EFFECTIVE_K
        ),
        "required_K_excess_over_policy_maximum": 19_614,
        "selected_candidate_index": None,
        "selected_K": None,
    }.items():
        if not exact_value_equal(q72.get(key), value):
            raise RuntimeError(f"route predecessor q72 drift: {key}")

    # This subtraction is threshold evidence only.  It must never be extended
    # into a synthetic candidate row or a claimed drop value.
    if (
        EXPECTED_Q72_MINIMUM_EFFECTIVE_K - K638976
        != EXCLUDED_K638976_EVIDENCE["shortfall"]
        or EXCLUDED_K638976_EVIDENCE["shortfall"] != 3_230
    ):
        raise RuntimeError("excluded K638976 threshold evidence drift")

    reference = {
        "route_id": (
            "double_occupancy_k622592_c36_l1048576_d1048576_q72_"
            "to_k655360_c37_l1048576_d1048576_q72_v1"
        ),
        "screen": {
            "relative_path": ROUTE_PREDECESSOR_SCREEN_NAME,
            "source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
            "compiled": False,
            "executed": False,
            "private_entrypoint_called": False,
            "execution_source_layer": False,
            "loaded_after_replay_as_exact_reference": True,
            "used_only_for_post_replay_comparison": True,
        },
        "canonical_transcript": {
            "relative_path": ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "file_size_bytes": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SIZE,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_FULL_RECORDS_SHA256,
            "q1_through_q71_records_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
            ),
            "selected_K_history_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
            ),
            "q71_record_sha256": EXPECTED_ROUTE_PREDECESSOR_Q71_RECORD_SHA256,
            "q72_failure_record_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_Q72_FAILURE_SHA256
            ),
            "q72_candidate_rows_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_Q72_ROWS_SHA256
            ),
            "compiled": False,
            "executed": False,
            "loaded_before_replay_as_exact_reference": False,
            "loaded_after_replay_as_exact_reference": True,
            "used_only_after_replay_for_result_comparison": True,
            "post_replay_comparison_input": True,
            "propagation_input": False,
            "checkpoint_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
            "source_custody_layer": False,
        },
        "excluded_candidate_threshold_evidence": dict(
            EXCLUDED_K638976_EVIDENCE
        ),
        "incremental_semantic_delta": {
            "candidate_K_values_changed": True,
            "candidate_ladder_added": [K655360],
            "candidate_ladder_removed": [],
            "policy_caps_changed": True,
            "policy_cap_changes": {
                "max_candidate_K": {
                    "before": K622592,
                    "after": K655360,
                },
                "max_output_terms_if_successful": {
                    "before": K622592,
                    "after": K655360,
                },
            },
            "live_and_digest_caps_changed": False,
            "kernel_capability_limits_changed": True,
            "horizon_checkpoint_count": {"before": 72, "after": 72},
        },
        "terminal_contract": {
            "expected_branch": "Q72_INDEX36_FIRST_FEASIBLE_SUCCESS",
            "resource_exceptions_fail_closed_without_artifact": True,
            "resource_exception_artifact_generated": False,
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


def execute_parent_fail_closed(
    parent: Any,
    repo: Path,
) -> Dict[str, Any]:
    """Execute once; every schema/resource exception propagates unchanged."""

    return normalize_completed_parent_result(parent._run_verified(repo, MODE))


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
        minimum_K <= K655360
        or minimum_K > pre_count
        or excess != minimum_K - K655360
    ):
        raise RuntimeError(f"D q{checkpoint} failure excess-K drift")
    maximum_excess = parse_canonical_nonnegative_decimal(
        record["maximum_candidate_drop_excess_over_slack_ticks"],
        f"D q{checkpoint} failure maximum excess",
    )
    if maximum_excess != drops[-1] - slack or maximum_excess <= 0:
        raise RuntimeError(f"D q{checkpoint} failure cap excess drift")
    return None


def require_no_resource_policy_abort(result: Mapping[str, Any]) -> None:
    """Require the artifact branch to be resource-abort free."""

    if (
        result.get("resource_policy_abort") is not None
        or result.get("resource_policy_abort_sha256") is not None
    ):
        raise RuntimeError(
            "D q72 resource/schema exceptions fail closed without an artifact"
        )
    return None
def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    """Validate fresh q1--q72 replay against post-replay C36 evidence."""

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

    predecessor_transform = predecessor.get("checkpoint_transform")
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

    require_no_resource_policy_abort(result)
    records = result.get("records")
    history = result.get("selected_K_history")
    old_records = predecessor.get("records")
    old_history = predecessor.get("selected_K_history")
    if type(records) is not list or len(records) != 72:
        raise RuntimeError("D route must freshly replay q1 through q72")
    if type(history) is not list or len(history) != 72:
        raise RuntimeError("D route must commit q1 through q72")
    if type(old_records) is not list or len(old_records) != 72:
        raise RuntimeError("D route predecessor record count drift")
    if type(old_history) is not list or len(old_history) != 71:
        raise RuntimeError("D route predecessor history count drift")
    if sha256(canonical_bytes(old_records[:71])) != (
        EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
    ):
        raise RuntimeError("D predecessor q1-q71 digest drift")
    if not exact_value_equal(history[:71], old_history):
        raise RuntimeError("D route changed exact q1-q71 selected history")

    def validate_appended_row(
        record: Mapping[str, Any],
        old_rows: Any,
        checkpoint: int,
    ) -> Mapping[str, Any]:
        rows = record.get("candidate_records")
        if (
            type(old_rows) is not list
            or len(old_rows) != 36
            or type(rows) is not list
            or len(rows) != 37
            or not exact_value_equal(rows[:36], old_rows)
        ):
            raise RuntimeError(
                f"D q{checkpoint} changed predecessor candidate rows"
            )
        if any(
            row.get("configured_K") == K638976
            for row in rows
            if type(row) is dict
        ):
            raise RuntimeError(
                f"D q{checkpoint} constructed excluded K638976 row"
            )
        appended = rows[36]
        require_exact_keys(
            appended,
            CANDIDATE_RECORD_KEYS,
            f"D q{checkpoint} appended candidate row",
        )
        pre_count = record.get("pretruncation_expansion_count")
        if type(pre_count) is not int or pre_count < 0:
            raise RuntimeError(f"D q{checkpoint} pretruncation count drift")
        effective = min(K655360, pre_count)
        for key, value in {
            "candidate_index": 36,
            "configured_K": K655360,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }.items():
            if not exact_value_equal(appended.get(key), value):
                raise RuntimeError(
                    f"D q{checkpoint} appended candidate drift: {key}"
                )
        drop = parse_canonical_nonnegative_decimal(
            appended.get("drop_ticks"),
            f"D q{checkpoint} appended drop",
        )
        E_after = parse_canonical_nonnegative_decimal(
            appended.get("E_after_if_selected_ticks"),
            f"D q{checkpoint} appended E after",
        )
        E_before = parse_canonical_nonnegative_decimal(
            record.get("E_before_ticks"),
            f"D q{checkpoint} E before",
        )
        prefix_cap = parse_canonical_nonnegative_decimal(
            record.get("budget_prefix_cap_ticks"),
            f"D q{checkpoint} prefix cap",
        )
        if E_after != E_before + drop:
            raise RuntimeError(
                f"D q{checkpoint} appended candidate E recurrence drift"
            )
        predecessor_row = rows[35]
        predecessor_drop = parse_canonical_nonnegative_decimal(
            predecessor_row.get("drop_ticks"),
            f"D q{checkpoint} predecessor maximum-K drop",
        )
        predecessor_E_after = parse_canonical_nonnegative_decimal(
            predecessor_row.get("E_after_if_selected_ticks"),
            f"D q{checkpoint} predecessor maximum-K E after",
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
                f"D q{checkpoint} appended candidate ranking drift"
            )
        if appended["dropped_term_count"] == 0 and drop != 0:
            raise RuntimeError(
                f"D q{checkpoint} appended zero-drop arithmetic drift"
            )
        if appended.get("feasible_under_current_prefix_cap") is not (
            E_after <= prefix_cap
        ):
            raise RuntimeError(
                f"D q{checkpoint} appended candidate feasibility drift"
            )
        return appended

    for index in range(71):
        old = old_records[index]
        new = records[index]
        require_exact_keys(new, frozenset(old), f"D q{index + 1} record")
        old_common = {
            key: value for key, value in old.items()
            if key != "candidate_records"
        }
        new_common = {
            key: value for key, value in new.items()
            if key != "candidate_records"
        }
        if not exact_value_equal(new_common, old_common):
            raise RuntimeError(
                f"D q{index + 1} changed common replay state"
            )
        validate_appended_row(
            new,
            old.get("candidate_records"),
            index + 1,
        )

    q71 = records[70]
    q72 = records[71]
    old_q72 = old_records[71]
    if sha256(canonical_bytes(old_q72)) != (
        EXPECTED_ROUTE_PREDECESSOR_Q72_FAILURE_SHA256
    ):
        raise RuntimeError("D q72 predecessor failure digest drift")
    if sha256(canonical_bytes(old_q72["candidate_records"])) != (
        EXPECTED_ROUTE_PREDECESSOR_Q72_ROWS_SHA256
    ):
        raise RuntimeError("D q72 predecessor row digest drift")

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
        key: value for key, value in old_q72.items() if key not in excluded
    }
    if any(key not in q72 for key in old_shared):
        raise RuntimeError("D q72 removed a propagation/ranking field")
    if not exact_value_equal(
        {key: q72[key] for key in old_shared},
        old_shared,
    ):
        raise RuntimeError("D q72 propagation/ranking evidence drift")

    old_counterfactual = old_q72.get("removed_491520_counterfactual")
    new_counterfactual = q72.get("removed_491520_counterfactual")
    require_exact_keys(
        new_counterfactual,
        REMOVED_COUNTERFACTUAL_KEYS,
        "D q72 removed-491520 counterfactual",
    )
    choice_keys = {
        "actual_selected_K",
        "would_precede_selected",
        "would_be_selected_if_inserted",
    }
    if not exact_value_equal(
        {
            key: value for key, value in new_counterfactual.items()
            if key not in choice_keys
        },
        {
            key: value for key, value in old_counterfactual.items()
            if key not in choice_keys
        },
    ):
        raise RuntimeError("D q72 counterfactual arithmetic drift")

    appended_q72 = validate_appended_row(
        q72,
        old_q72.get("candidate_records"),
        72,
    )
    if (
        old_q72.get("minimum_effective_K_to_meet_prefix")
        != EXPECTED_Q72_MINIMUM_EFFECTIVE_K
        or not K638976 < EXPECTED_Q72_MINIMUM_EFFECTIVE_K <= K655360
        or EXCLUDED_K638976_EVIDENCE["shortfall"] != 3_230
    ):
        raise RuntimeError("D q72 excluded-threshold evidence drift")
    if appended_q72.get("feasible_under_current_prefix_cap") is not True:
        raise RuntimeError("D q72 K655360 must be feasible")
    if any(
        row.get("feasible_under_current_prefix_cap") is not False
        for row in q72["candidate_records"][:36]
    ):
        raise RuntimeError("D q72 old C36 rows must remain infeasible")

    selected_q71 = validate_extended_record(q71, records[69], 71)
    selected_q72 = validate_extended_record(q72, q71, 72)
    if selected_q71 != K622592:
        raise RuntimeError("D q71 predecessor selection drift")
    if (
        selected_q72 != K655360
        or q72.get("selected_candidate_index") != 36
        or q72.get("selected_K") != K655360
    ):
        raise RuntimeError("D q72 appended row is not first-feasible")
    if not exact_value_equal(history, list(old_history) + [K655360]):
        raise RuntimeError("D q72 selected history drift")

    expected_summary = {
        "attempted_checkpoint_count": 72,
        "completed_checkpoint_count": 72,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": True,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "last_committed_cumulative_drop_ticks": q72["E_after_ticks"],
    }
    for key, value in expected_summary.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"D q72 terminal summary drift: {key}")
    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("D q72 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(
        canonical_bytes(history)
    ):
        raise RuntimeError("D q72 selected history digest drift")
    observed = {
        "observed_peak_single_expansion_terms": q72[
            "peak_live_terms_cumulative"
        ],
        "observed_term_gate_visits_including_terminal_attempt": q72[
            "term_gate_visits_cumulative"
        ],
        "observed_maximum_expansion_coefficient_tick_bits": q72[
            "maximum_expansion_coefficient_tick_bits"
        ],
        "observed_maximum_product_bits": q72["maximum_product_bits"],
        "observed_rounding_cumulative_scaled_ticks_squared": q72[
            "rounding_cumulative_scaled_ticks_squared"
        ],
    }
    for key, value in observed.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"D q72 observed resource ledger drift: {key}")

    return {
        "validation_id": (
            "D_k655360_c37_l1048576_d1048576_q72_"
            "post_replay_handoff_v1"
        ),
        "fresh_replay_checkpoint_range": [1, 72],
        "q1_through_q71_common_records_exact": True,
        "q1_through_q71_first_36_candidate_rows_exact": True,
        "q1_through_q71_selected_history_exact": True,
        "q1_through_q71_predecessor_records_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256
        ),
        "q1_through_q71_predecessor_history_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256
        ),
        "q72_propagation_and_ranking_exact": True,
        "q72_first_36_candidate_rows_exact": True,
        "q72_predecessor_failure_record_sha256": (
            EXPECTED_ROUTE_PREDECESSOR_Q72_FAILURE_SHA256
        ),
        "q72_appended_candidate_index": 36,
        "q72_appended_candidate_K": K655360,
        "q72_appended_candidate_first_feasible": True,
        "q72_terminal_branch": "Q72_INDEX36_FIRST_FEASIBLE_SUCCESS",
        "excluded_K638976_threshold_evidence": dict(
            EXCLUDED_K638976_EVIDENCE
        ),
        "K638976_execution_row_constructed": False,
        "K638976_drop_ticks_asserted": False,
        "resource_exceptions_fail_closed_without_artifact": True,
        "route_screen_private_entrypoint_called": False,
        "route_screen_compiled_or_executed": False,
        "route_canonical_used_as_state_or_resume_input": False,
        "q72_outcome_precommitted": False,
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
    components = [{
        "relative_path": SELF_NAME,
        "role": "D_k655360_c37_fresh_same_byte_direct_control_flow_screen",
        "sha256": self_sha,
    }]
    saw_parent = saw_v6 = saw_v2 = False
    forbidden = {
        ROUTE_PREDECESSOR_SCREEN_NAME,
        ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
        "hubbard_l8_adaptive_k_arithmetic_k622592_c36.py",
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
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "k655360_c37_capability_override_provider",
                "sha256": wrapper_sha,
            })
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
        K655360,
    ):
        raise RuntimeError("configuration baseline construction drift")
    direct_changed = {
        "max_candidate_K",
        "max_output_terms_if_successful",
        "max_single_expansion_terms",
        "max_digest_terms",
    }
    unchanged = {
        key: value for key, value in EXPECTED_V6_POLICY_CAPS.items()
        if key not in direct_changed
    }
    return {
        "override_id": (
            "double_occupancy_k655360_c37_l1048576_d1048576_"
            "q72_configuration_override_v1"
        ),
        "diagnostic_ladder_precommitted_before_replay": True,
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": (
                EXPECTED_V6_D_CANDIDATE_SHA256
            ),
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 32, "after": 37},
            "candidate_ladder_added": [
                K540672,
                K573440,
                K589824,
                K606208,
                K622592,
                K655360,
            ],
            "candidate_ladder_removed": [65_536],
            "policy_cap_changes": {
                "max_candidate_K": {
                    "before": 524_288,
                    "after": K655360,
                },
                "max_output_terms_if_successful": {
                    "before": 524_288,
                    "after": K655360,
                },
                "max_single_expansion_terms": {
                    "before": 786_432,
                    "after": LIVE_AND_DIGEST_CAP,
                },
                "max_digest_terms": {
                    "before": 786_432,
                    "after": LIVE_AND_DIGEST_CAP,
                },
            },
        },
        "incremental_route_override_from_k622592_c36_policy_q72": {
            "predecessor_candidate_K_values_sha256": (
                EXPECTED_PREDECESSOR_CANDIDATE_SHA256
            ),
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 36, "after": 37},
            "candidate_ladder_added": [K655360],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {
                    "before": K622592,
                    "after": K655360,
                },
                "max_output_terms_if_successful": {
                    "before": K622592,
                    "after": K655360,
                },
            },
            "live_and_digest_caps_unchanged": {
                "max_single_expansion_terms": LIVE_AND_DIGEST_CAP,
                "max_digest_terms": LIVE_AND_DIGEST_CAP,
            },
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "excluded_candidate_threshold_evidence": dict(
            EXCLUDED_K638976_EVIDENCE
        ),
        "derived_policy_cap": {
            "field": "max_candidate_count",
            "derivation": "len(candidate_K_values)",
            "before_on_route": 36,
            "after": 37,
        },
        "unchanged_policy_caps": unchanged,
        "magnetization_candidate_configuration_unchanged": True,
        "overridden_fields": [
            f"MODE_CONFIG.{MODE}.candidates",
            "POLICY_CAPS_BASE.max_candidate_K",
            "POLICY_CAPS_BASE.max_output_terms_if_successful",
            "POLICY_CAPS_BASE.max_single_expansion_terms",
            "POLICY_CAPS_BASE.max_digest_terms",
        ],
    }


def kernel_capability_override(
    wrapper_sha: str,
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "relative_path": KERNEL_WRAPPER_NAME,
        "source_sha256": wrapper_sha,
        "role": "separate_k655360_c37_capability_override_provider",
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
            "max_candidate_count": {"before": 32, "after": 37},
            "max_retained_K": {"before": 524_288, "after": K655360},
        },
        "incremental_route_changes_from_k622592_c36": {
            "max_candidate_count": {"before": 36, "after": 37},
            "max_retained_K": {"before": K622592, "after": K655360},
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
        "transform_id": (
            "double_occupancy_four_gate_k655360_c37_"
            "l1048576_d1048576_q72_v1"
        ),
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "route_predecessor_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q72_outcome_precommitted": False,
        "incremental_route_semantic_delta": {
            "candidate_K_values_changed": True,
            "candidate_ladder_added": [K655360],
            "candidate_ladder_removed": [],
            "policy_caps_changed": True,
            "policy_cap_changes": {
                "max_candidate_K": {
                    "before": K622592,
                    "after": K655360,
                },
                "max_output_terms_if_successful": {
                    "before": K622592,
                    "after": K655360,
                },
            },
            "live_and_digest_caps_changed": False,
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
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k655360_c37_l1048576_d1048576_q72_screen_v1"
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
            "base_v2_arithmetic_implementation_commit_before_"
            "k655360_c37_capability_override"
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
    result = execute_parent_fail_closed(parent, repo)
    predecessor, route_reference = load_route_reference(
        repo,
        replay_completed=True,
    )
    return validate_and_relabel(result, predecessor, route_reference, baseline_d, wrapper_sha, manifest, horizon)


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType(
        "verified_double_occupancy_k655360_c37_policy_q72_screen"
    )
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
