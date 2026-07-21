#!/usr/bin/env python3
"""Source-pinned, diagnostic-only D K=606208/C=35 q70 screen.

The only execution parent is a fresh same-byte copy of the exact four-gate
control-flow screen.  The K589824/C34 q70 screen and failure transcript are
exact pre-run route references only; neither is compiled, executed, used for
propagation, or used for state resume.
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
    "k606208_c35_q70_screen.py"
)
CONTROL_FLOW_PARENT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k606208_c35.py"
ROUTE_PREDECESSOR_SCREEN_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k589824_c34_q70_screen.py"
)
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k589824_c34_q70_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
    "k606208_c35_q70_transcript.json"
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
    "34757028d695e2542cade50f4be5c214006dee6945e01afc2483e7338d6cb7dd"
)
EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256 = (
    "c55df50288334226a4d8ba37a257ca645d601967f8778f426a313773c1c73629"
)
EXPECTED_KERNEL_SOURCE_LAYERS_SHA256 = (
    "16871e933f66e58cbd892b8137d0a032559972966fc660b49d0567ddf25e325d"
)
EXPECTED_KERNEL_ROUTE_REFERENCE_SHA256 = (
    "a778ad33314c2086525b69673b148591c5e8b4b35580ac0d95899c0d155986af"
)
EXPECTED_ROUTE_KERNEL_SHA256 = (
    "7758cc1bf0cd71545a7135c92848059dc69e5d934c79f1d8c60ea61019459254"
)
EXPECTED_ROUTE_KERNEL_MANIFEST_SHA256 = (
    "36694fa3e72ad78fde91826c6a1ae81ae5a7f07e51db2d008769d97eabce5b1a"
)
EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256 = (
    "af4257d505bcebcafa80fa184bd83065fae1b5151fd9bdc28a5f5b9ccf9ecb32"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "65d6f5ba3e45b5b57b12d1b9e1daadb17064f8aece7dc914697191f822b3a8d7"
)
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "738ab268f6dc3f4a79ed17bcaf0c5400130a541bc823a8edbabfa42f34f09fb0"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "f41c9984a1f7d076f1f0148f2a37b2be3b7ba55fa9adff91a1e9753c7989daa0"
)
EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256 = (
    "5cbadf7fdfab27f651713dbd62b7d7497475bbdb9ebb7a03026330a6333b5a6e"
)
EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256 = (
    "f93f946e08a5189503ff970e944556db26cb0dfceb8d3fb76866b0255356bde9"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256 = (
    "088ec77c061a5fd87797245c3fe005462474e5c56ac1df3f52ba5cc17ff0810b"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_ROUTE_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "double_occupancy"
BASE_PARENT_HORIZON = 66
EXTENDED_HORIZON = 70
K540672 = 540_672
K573440 = 573_440
K589824 = 589_824
K606208 = 606_208

V6_D_CANDIDATES = (
    65_536, 73_728, 81_920, 90_112, 98_304, 106_496, 114_688,
    122_880, 131_072, 147_456, 163_840, 180_224, 196_608, 212_992,
    229_376, 245_760, 262_144, 278_528, 294_912, 311_296, 327_680,
    344_064, 360_448, 376_832, 393_216, 409_600, 425_984, 442_368,
    458_752, 475_136, 507_904, 524_288,
)
PREDECESSOR_D_CANDIDATES = (
    V6_D_CANDIDATES[1:] + (K540672, K573440, K589824)
)
D_CANDIDATES = PREDECESSOR_D_CANDIDATES + (K606208,)
EXPECTED_V6_D_CANDIDATE_SHA256 = (
    "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
)
EXPECTED_V6_M_CANDIDATE_SHA256 = (
    "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
)
EXPECTED_PREDECESSOR_CANDIDATE_SHA256 = (
    "a15306f3ca1f770baeac58bd8d3d48e64bb677e9fb10b6177c30be60bc735774"
)
EXPECTED_CANDIDATE_SHA256 = (
    "d69acf8cdc4e598e9734abe68a4d0a83cf7ea0618d38932b02c94c0aa8bfd161"
)
EXPECTED_Q69_SELECTED_HISTORY_SHA256 = (
    "f41c9984a1f7d076f1f0148f2a37b2be3b7ba55fa9adff91a1e9753c7989daa0"
)
EXPECTED_Q70_SELECTED_HISTORY_SHA256 = (
    "d57dfeffe7e5e0056ad1b0294a015852af7788fe23187aad9d4484683f8f1cba"
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
    "max_candidate_count": 34,
    "max_retained_K": K589824,
}
EXPECTED_WRAPPED_KERNEL_LIMITS = {
    **EXPECTED_V2_KERNEL_LIMITS,
    "max_candidate_count": 35,
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


def validate_local_configuration() -> None:
    if len(V6_D_CANDIDATES) != 32 or len(PREDECESSOR_D_CANDIDATES) != 34:
        raise RuntimeError("D predecessor candidate count drift")
    if len(D_CANDIDATES) != 35 or D_CANDIDATES != PREDECESSOR_D_CANDIDATES + (K606208,):
        raise RuntimeError("D K606208 route is not an exact append")
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


def load_control_flow_parent(repo: Path) -> Any:
    parent, _ = load_pinned_module(
        repo, CONTROL_FLOW_PARENT_NAME, EXPECTED_CONTROL_FLOW_PARENT_SHA256,
        "pinned_four_gate_parent_for_d_k606208_c35_q70",
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
    return parent


def load_configured_v6_baseline(repo: Path) -> Tuple[Any, Tuple[int, ...]]:
    configuration, _ = load_pinned_module(
        repo, V6_BASELINE_CONFIGURATION_NAME,
        EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "pinned_v6_baseline_for_d_k606208_c35_q70",
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
    wrapper = types.ModuleType("pinned_k606208_c35_arithmetic_wrapper")
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
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_double_occupancy_adaptive_k_four_gate_"
            "k589824_c34_q70_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_ROUTE_PREDECESSOR_SCREEN_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": 70,
        "screen_terminal_condition": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "attempted_checkpoint_count": 70,
        "completed_checkpoint_count": 69,
        "failure_checkpoint_included": True,
        "candidate_K_values": list(PREDECESSOR_D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
        "proposed_policy_caps": {
            **EXPECTED_PREDECESSOR_POLICY_CAPS,
            "max_candidate_count": len(PREDECESSOR_D_CANDIDATES),
        },
        "kernel_capability_limits": EXPECTED_ROUTE_KERNEL_LIMITS,
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
        "failure_record_sha256": EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256,
        "configuration_override_sha256": EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256,
        "checkpoint_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
    }
    for key, value in expected.items():
        if transcript.get(key) != value:
            raise RuntimeError(f"route predecessor transcript drift: {key}")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 70:
        raise RuntimeError("route record count drift")
    if type(history) is not list or len(history) != 69:
        raise RuntimeError("route history count drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("route records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("route history digest drift")
    if sha256(canonical_bytes(records[-1])) != EXPECTED_ROUTE_PREDECESSOR_FAILURE_SHA256:
        raise RuntimeError("route failure digest drift")
    q70 = records[-1]
    for key, value in {
        "checkpoint_number_one_based": 70,
        "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
        "pretruncation_expansion_count": 718_805,
        "minimum_effective_K_to_meet_prefix": 597_272,
        "required_K_excess_over_policy_maximum": 7_448,
        "selected_K": None,
        "selected_candidate_index": None,
    }.items():
        if q70.get(key) != value:
            raise RuntimeError(f"route predecessor q70 drift: {key}")
    if any(
        row.get("feasible_under_current_prefix_cap") is not False
        for row in q70.get("candidate_records", ())
    ):
        raise RuntimeError("route predecessor q70 failure feasibility drift")
    reference = {
        "route_id": "double_occupancy_k589824_c34_q70_to_k606208_c35_q70_v1",
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
            "loaded_before_replay_as_exact_reference": True,
            "used_only_after_replay_for_result_prefix_validation": True,
            "propagation_input": False,
            "checkpoint_69_state_loaded": False,
            "checkpoint_70_state_loaded": False,
            "state_resume_input": False,
            "execution_source_layer": False,
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
        "override_id": "double_occupancy_parent_q70_horizon_override_v1",
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


def is_canonical_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


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
        raise RuntimeError("D q70 result is not an exact dict")
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
            "D q70 top-level exact key-set drift: "
            f"missing={missing}, extra={extra}"
        )


def validate_q70_terminal_ledger(
    result: Mapping[str, Any],
    q69: Mapping[str, Any],
    q70: Mapping[str, Any],
    history: list[Any],
    expected_q70_keys: frozenset[str],
) -> None:
    require_exact_keys(q70, expected_q70_keys, "D q70 terminal record")
    if q70.get("checkpoint_index_zero_based") != 69:
        raise RuntimeError("D q70 terminal checkpoint index drift")
    if q70.get("checkpoint_number_one_based") != 70:
        raise RuntimeError("D q70 terminal checkpoint drift")
    for q70_key, q69_key in (
        ("input_expansion_count", "retained_expansion_count"),
        ("input_expansion_sha256", "retained_expansion_sha256"),
        ("E_before_ticks", "E_after_ticks"),
    ):
        if q70.get(q70_key) != q69.get(q69_key):
            raise RuntimeError(f"D q70 input continuity drift: {q70_key}")
    pre_count = q70.get("pretruncation_expansion_count")
    if type(pre_count) is not int or type(q70.get("input_expansion_count")) is not int:
        raise RuntimeError("D q70 expansion count type drift")
    try:
        E_before = int(q70["E_before_ticks"])
        prefix_cap = int(q70["budget_prefix_cap_ticks"])
        slack = int(q70["prefix_slack_before_selection_ticks"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("D q70 fixed-tick ledger field drift") from exc
    if slack != prefix_cap - E_before:
        raise RuntimeError("D q70 prefix slack recurrence drift")
    rows = q70.get("candidate_records")
    if type(rows) is not list or len(rows) != len(D_CANDIDATES):
        raise RuntimeError("D q70 candidate row count drift")
    feasible_indices = []
    for candidate_index, (configured_K, row) in enumerate(zip(D_CANDIDATES, rows)):
        require_exact_keys(
            row,
            CANDIDATE_RECORD_KEYS,
            f"D q70 candidate row {candidate_index}",
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
                raise RuntimeError(f"D q70 candidate row drift: {key}")
        try:
            drop = int(row["drop_ticks"])
            E_after = int(row["E_after_if_selected_ticks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("D q70 candidate fixed-tick field drift") from exc
        if drop < 0 or E_after != E_before + drop:
            raise RuntimeError("D q70 candidate E recurrence drift")
        feasible = E_after <= prefix_cap
        if row.get("feasible_under_current_prefix_cap") is not feasible:
            raise RuntimeError("D q70 candidate feasibility label drift")
        if feasible:
            feasible_indices.append(candidate_index)

    if feasible_indices != [34]:
        raise RuntimeError("D q70 K606208 row is not the unique first feasible candidate")
    failure_only = {
        "minimum_effective_K_to_meet_prefix",
        "required_K_excess_over_policy_maximum",
        "maximum_candidate_drop_excess_over_slack_ticks",
    }
    if q70.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED":
        raise RuntimeError("D q70 terminal status is not success")
    if any(key in q70 for key in failure_only):
        raise RuntimeError("D q70 success record contains failure-only fields")
    selected_row = rows[34]
    expected_selection = {
        "selected_candidate_index": 34,
        "selected_K": K606208,
        "selected_effective_retained_count": selected_row["effective_retained_count"],
        "selected_dropped_term_count": selected_row["dropped_term_count"],
        "selected_drop_ticks": selected_row["drop_ticks"],
        "retained_expansion_count": selected_row["effective_retained_count"],
        "E_after_ticks": selected_row["E_after_if_selected_ticks"],
    }
    for key, value in expected_selection.items():
        if q70.get(key) != value:
            raise RuntimeError(f"D q70 success selection drift: {key}")
    if (
        len(history) != 70
        or history[-1] != K606208
        or sha256(canonical_bytes(history)) != EXPECTED_Q70_SELECTED_HISTORY_SHA256
    ):
        raise RuntimeError("D q70 success history drift")
    for key in ("selected_dropped_terms_sha256", "retained_expansion_sha256"):
        if not is_canonical_sha256(q70.get(key)):
            raise RuntimeError(f"D q70 success digest drift: {key}")
    for key in ("minimum_retained_abs_upper_ticks", "maximum_dropped_abs_upper_ticks"):
        try:
            if int(q70[key]) < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"D q70 success interval field drift: {key}") from exc
    if int(q70["E_after_ticks"]) > prefix_cap:
        raise RuntimeError("D q70 selected candidate violates prefix cap")
    counterfactual = q70.get("removed_491520_counterfactual")
    require_exact_keys(
        counterfactual,
        REMOVED_COUNTERFACTUAL_KEYS,
        "D q70 removed-491520 counterfactual",
    )
    if counterfactual.get("actual_selected_K") != K606208:
        raise RuntimeError("D q70 counterfactual selection drift")
    expected_top = {
        "horizon_checkpoint_attempted": True,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "attempted_checkpoint_count": 70,
        "completed_checkpoint_count": 70,
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_reached_with_committed_checkpoint": True,
        "last_committed_cumulative_drop_ticks": q70["E_after_ticks"],
    }
    for key, value in expected_top.items():
        if result.get(key) != value:
            raise RuntimeError(f"D q70 success summary drift: {key}")


def validate_replay_handoff(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    require_handoff_top_level_keys(result)
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or len(records) != 70:
        raise RuntimeError("D q70 result did not attempt exactly through q70")
    if type(history) is not list or len(history) != 70:
        raise RuntimeError("D q70 selected history length drift")
    old_records = predecessor["records"]
    old_history = predecessor["selected_K_history"]
    if history[:69] != old_history:
        raise RuntimeError("D q70 changed q1-69 selected history")
    if sha256(canonical_bytes(history[:69])) != EXPECTED_Q69_SELECTED_HISTORY_SHA256:
        raise RuntimeError("D q69 selected history digest drift")

    for index in range(69):
        old, new = old_records[index], records[index]
        if {k: v for k, v in new.items() if k != "candidate_records"} != {
            k: v for k, v in old.items() if k != "candidate_records"
        }:
            raise RuntimeError(f"D q70 changed q{index + 1} common record state")
        rows = new.get("candidate_records")
        if (
            type(rows) is not list
            or len(rows) != 35
            or rows[:34] != old["candidate_records"]
        ):
            raise RuntimeError(f"D q70 changed q{index + 1} predecessor rows")
        appended = rows[34]
        require_exact_keys(
            appended,
            CANDIDATE_RECORD_KEYS,
            f"D q{index + 1} appended candidate row",
        )
        pre_count = new.get("pretruncation_expansion_count")
        effective = min(K606208, pre_count)
        expected = {
            "candidate_index": 34,
            "configured_K": K606208,
            "effective_retained_count": effective,
            "dropped_term_count": pre_count - effective,
        }
        for key, value in expected.items():
            if appended.get(key) != value:
                raise RuntimeError(f"D q{index + 1} appended candidate drift: {key}")
        try:
            E_after = int(appended["E_after_if_selected_ticks"])
            drop = int(appended["drop_ticks"])
            E_before = int(new["E_before_ticks"])
            prefix_cap = int(new["budget_prefix_cap_ticks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"D q{index + 1} appended fixed-tick drift") from exc
        if E_after != E_before + drop:
            raise RuntimeError(f"D q{index + 1} appended candidate E recurrence drift")
        if appended.get("feasible_under_current_prefix_cap") is not (
            E_after <= prefix_cap
        ):
            raise RuntimeError(f"D q{index + 1} appended feasibility label drift")

    old_q70, new_q70 = old_records[69], records[69]
    require_exact_keys(
        old_q70,
        Q70_FAILURE_RECORD_KEYS,
        "route predecessor q70 failure record",
    )
    expected_q70_keys = Q70_SUCCESS_RECORD_KEYS
    require_exact_keys(
        new_q70,
        expected_q70_keys,
        "D q70 transformed success record",
    )
    failure_only = Q70_FAILURE_ONLY_KEYS
    excluded = {
        "candidate_records",
        "status",
        "selected_candidate_index",
        "selected_K",
        "removed_491520_counterfactual",
        *failure_only,
    }
    old_shared = {k: v for k, v in old_q70.items() if k not in excluded}
    if any(key not in new_q70 for key in old_shared):
        raise RuntimeError("D q70 removed a shared propagation field")
    if {k: new_q70[k] for k in old_shared} != old_shared:
        raise RuntimeError("D q70 changed shared propagation fields")
    if any(key in new_q70 for key in failure_only):
        raise RuntimeError("D q70 retained predecessor failure-only fields")
    rows = new_q70.get("candidate_records")
    if (
        type(rows) is not list
        or len(rows) != 35
        or rows[:34] != old_q70["candidate_records"]
    ):
        raise RuntimeError("D q70 changed predecessor candidate rows")
    if any(
        row.get("feasible_under_current_prefix_cap") is not False
        for row in rows[:34]
    ):
        raise RuntimeError("route q70 unexpectedly had a feasible predecessor")
    appended = rows[34]
    for key, value in {
        "candidate_index": 34,
        "configured_K": K606208,
        "effective_retained_count": K606208,
        "dropped_term_count": 112_597,
        "feasible_under_current_prefix_cap": True,
    }.items():
        if appended.get(key) != value:
            raise RuntimeError(f"D q70 appended candidate drift: {key}")
    old_counterfactual = dict(old_q70["removed_491520_counterfactual"])
    new_counterfactual = dict(new_q70["removed_491520_counterfactual"])
    old_counterfactual.pop("actual_selected_K", None)
    new_counterfactual.pop("actual_selected_K", None)
    if new_counterfactual != old_counterfactual:
        raise RuntimeError("D q70 removed-491520 counterfactual drift")
    if new_q70["removed_491520_counterfactual"].get("actual_selected_K") != K606208:
        raise RuntimeError("D q70 counterfactual selected-K label drift")

    if result.get("records_sha256") != sha256(canonical_bytes(records)):
        raise RuntimeError("D q70 records digest drift")
    if result.get("selected_K_history_sha256") != sha256(canonical_bytes(history)):
        raise RuntimeError("D q70 history digest drift")
    validate_q70_terminal_ledger(
        result,
        records[68],
        new_q70,
        history,
        expected_q70_keys,
    )
    return {
        "validation_id": "D_k606208_c35_q70_predecessor_handoff_v1",
        "q1_through_q69_common_records_exact": True,
        "q1_through_q69_first_34_candidate_rows_exact": True,
        "q1_through_q69_selected_history_exact": True,
        "q69_selected_history_sha256": EXPECTED_Q69_SELECTED_HISTORY_SHA256,
        "q70_shared_propagation_fields_exact": True,
        "q70_first_34_candidate_rows_exact": True,
        "q70_appended_candidate_index": 34,
        "q70_appended_candidate_K": K606208,
        "q70_appended_candidate_is_first_feasible": True,
        "q70_terminal_success_validated_from_exact_ledger": True,
        "q70_selected_history_sha256": EXPECTED_Q70_SELECTED_HISTORY_SHA256,
        "q70_outcome_precommitted": False,
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
    components = [{"relative_path": SELF_NAME, "role": "D_k606208_c35_q70_fresh_same_byte_screen", "sha256": self_sha}]
    saw_parent = saw_v6 = saw_v2 = False
    forbidden = {
        ROUTE_PREDECESSOR_SCREEN_NAME,
        ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
        "hubbard_l8_adaptive_k_arithmetic_k589824_c34.py",
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
            components.append({"relative_path": KERNEL_WRAPPER_NAME, "role": "k606208_c35_capability_override_provider", "sha256": wrapper_sha})
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
    ):
        raise RuntimeError("configuration baseline construction drift")
    unchanged = {k: v for k, v in EXPECTED_V6_POLICY_CAPS.items() if k not in {"max_candidate_K", "max_output_terms_if_successful"}}
    return {
        "override_id": "double_occupancy_k606208_c35_q70_configuration_override_v1",
        "diagnostic_ladder_precommitted_before_replay": True,
        "direct_execution_override_from_v6": {
            "baseline_candidate_K_values_sha256": EXPECTED_V6_D_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 32, "after": 35},
            "candidate_ladder_added": [K540672, K573440, K589824, K606208],
            "candidate_ladder_removed": [65_536],
            "policy_cap_changes": {
                "max_candidate_K": {"before": 524_288, "after": K606208},
                "max_output_terms_if_successful": {"before": 524_288, "after": K606208},
            },
        },
        "incremental_route_override_from_k589824_c34_q70": {
            "predecessor_candidate_K_values_sha256": EXPECTED_PREDECESSOR_CANDIDATE_SHA256,
            "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
            "candidate_count": {"before": 34, "after": 35},
            "candidate_ladder_added": [K606208],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {
                "max_candidate_K": {"before": K589824, "after": K606208},
                "max_output_terms_if_successful": {"before": K589824, "after": K606208},
            },
            "predecessor_configuration_override_sha256": EXPECTED_ROUTE_PREDECESSOR_CONFIGURATION_OVERRIDE_SHA256,
        },
        "derived_policy_cap": {"field": "max_candidate_count", "derivation": "len(candidate_K_values)", "before_on_route": 34, "after": 35},
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
        "role": "separate_k606208_c35_capability_override_provider",
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
            "max_candidate_count": {"before": 32, "after": 35},
            "max_retained_K": {"before": 524_288, "after": K606208},
        },
        "incremental_route_changes_from_k589824_c34": {
            "max_candidate_count": {"before": 34, "after": 35},
            "max_retained_K": {"before": K589824, "after": K606208},
        },
        "execution_source_layers": [KERNEL_WRAPPER_NAME, V2_ARITHMETIC_NAME],
        "route_predecessor_is_execution_source": False,
        "v2_arithmetic_module_mutated_by_screen": False,
    }


def validate_and_relabel(result, predecessor, route_reference, baseline_d, wrapper_sha, manifest, horizon_override):
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q70 relabel requires fresh same-byte self execution")
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
        "screen_horizon_checkpoint_count": 70,
        "candidate_K_values": list(D_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {**POLICY_CAPS_BASE, "max_candidate_count": len(D_CANDIDATES)},
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_LIMITS,
    }
    for key, value in expected.items():
        if result.get(key) != value:
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
        "transform_id": "double_occupancy_four_gate_k606208_c35_q70_v1",
        "physical_four_gate_control_flow_parent_transform": old_transform,
        "physical_four_gate_control_flow_parent_transform_sha256": old_transform_sha,
        "route_predecessor_transform_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSFORM_SHA256,
        "configuration_capability_and_horizon_overrides_outside_parent_transform": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "q70_outcome_precommitted": False,
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
    custody = dict(result.get("source_custody", {}))
    for path in (SELF_NAME, CONTROL_FLOW_PARENT_NAME, KERNEL_WRAPPER_NAME):
        if path in custody:
            raise RuntimeError(f"unexpected custody entry: {path}")
    custody.update({SELF_NAME: self_sha, CONTROL_FLOW_PARENT_NAME: EXPECTED_CONTROL_FLOW_PARENT_SHA256, KERNEL_WRAPPER_NAME: wrapper_sha})
    result.update({
        "transcript_fingerprint": "hubbard_l8_double_occupancy_adaptive_k_four_gate_k606208_c35_q70_screen_v1",
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
        "D q70 relabelled top-level result",
    )
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("D q70 screen requires fresh same-byte self execution")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_control_flow_parent(repo)
    configuration, baseline_d = load_configured_v6_baseline(repo)
    wrapper, wrapper_sha, manifest = load_kernel_wrapper(repo)
    predecessor, route_reference = load_route_reference(repo)
    horizon = configure_parent_execution(parent, configuration, wrapper)
    result = parent._run_verified(repo, MODE)
    return validate_and_relabel(result, predecessor, route_reference, baseline_d, wrapper_sha, manifest, horizon)


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_double_occupancy_k606208_c35_q70_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("D q70 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("D q70 transcript exceeds output byte cap")
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
