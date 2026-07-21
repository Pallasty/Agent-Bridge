#!/usr/bin/env python3
"""Source-pinned, diagnostic-only M K622592/C34 horizon-q90 screen.

The exact q88 screen is compiled from pinned same bytes and its private entry
point owns a fresh replay from checkpoint one.  Its internal C33 reference
loader and q88 relabel are suppressed during execution.  The q88 canonical is
loaded only after replay as exact q1--q88 evidence; it is never an execution,
propagation, state, or resume input.  This screen creates no authority.
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
    "k622592_c34_q90_screen.py"
)
EXECUTION_PARENT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k622592_c34_q88_screen.py"
)
CONTROL_FLOW_ROOT_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V6_BASELINE_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
V2_HELPER_NAME = "hubbard_l8_adaptive_k_v2_design_probe.py"
V2_ARITHMETIC_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
KERNEL_WRAPPER_NAME = "hubbard_l8_adaptive_k_arithmetic_k622592_c34.py"
ROUTE_PREDECESSOR_TRANSCRIPT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k622592_c34_q88_transcript.json"
)
OUTPUT_NAME = (
    "hubbard_l8_magnetization_adaptive_k_four_gate_"
    "k622592_c34_q90_transcript.json"
)

EXPECTED_EXECUTION_PARENT_SHA256 = (
    "6867dda2d6bd34ab2eed6b31d02a587e16762263a493e9890d0caa40f23a58a4"
)
EXPECTED_EXECUTION_PARENT_FILE_SIZE = 78_218
EXPECTED_CONTROL_FLOW_ROOT_SHA256 = (
    "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614"
)
EXPECTED_V6_BASELINE_CONFIGURATION_SHA256 = (
    "3e7f9ff0546addfaa23f351f3569b102d0c3ebb578dbc4873b042bac21070af2"
)
EXPECTED_V2_HELPER_SHA256 = (
    "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
)
EXPECTED_V2_ARITHMETIC_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_KERNEL_WRAPPER_SHA256 = (
    "f4e676da40535903301181cf482119e051066b90921793e34152403b3b74b976"
)
EXPECTED_KERNEL_MANIFEST_SHA256 = (
    "3c2b66149d524cc63a4d04838b3eec47fb69677466fe1f208e226df92bf0dac3"
)
EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256 = (
    "0074b1eea5fa574378d5a9fae9e748e7145efaa0c96b622ddf50587a72a2551a"
)
EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE = 821_781
EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256 = (
    "8832c0fd7c61146f2aa3c5e9a3a827972c459a126c2d371b5a5c41bac700c804"
)
EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256 = (
    "58cd214e13f4c122f710aad62ac0e52ead1aed0fa7d8a7e2498ea6013c7f4726"
)
EXPECTED_ROUTE_PREDECESSOR_Q88_RECORD_SHA256 = (
    "aa0c1f25c2957f1f0dbe9d71ad67fa14e217ecbec20e3badbad1cd3d465f9461"
)
EXPECTED_ROUTE_PREDECESSOR_Q88_ROWS_SHA256 = (
    "bec83189ac3f784e82342aa94d1ef0b257a0b1fba0bd38a82e7ee84a5511c8d9"
)
EXPECTED_ROUTE_CONFIGURATION_REFERENCE_SHA256 = (
    "e421d9c9c57e5dc3f7d5aa3500e9e9776f588bfb65df1a03ccd9292df404e5f2"
)
EXPECTED_ROUTE_CONFIGURATION_OVERRIDE_SHA256 = (
    "836107afb82a7c377c1d5b7e768d6c69fc238292d1c84316fce2dcd96fa41c6a"
)
EXPECTED_ROUTE_KERNEL_OVERRIDE_SHA256 = (
    "36e24d5b0f615862042a79093059c1a7a00c7be6e97dae30f69a1d723b08c866"
)
EXPECTED_ROUTE_PARENT_HORIZON_OVERRIDE_SHA256 = (
    "f4b28e1ffdbc72dffdc70af3c796a2808b3a9ed3e024d4f1183b6650fbf0fce3"
)
EXPECTED_ROUTE_REFERENCE_SHA256 = (
    "c8c392bd124d7bea65c998ef821e5226c83ce256c8350a75d992cf27e29f815f"
)
EXPECTED_ROUTE_HANDOFF_SHA256 = (
    "af84dcc4ceafb293d144f8a4d3a7c426854527c32d46cf5d0d0d75bfd777c915"
)
EXPECTED_ROUTE_TRANSFORM_SHA256 = (
    "3c1d764768df6ff87b22ca9738a7f55cc4c991da40a22b72114d09241bdc64b8"
)
EXPECTED_ROUTE_COMPONENTS_SHA256 = (
    "27c5d848da8c8651fea8935ba58b817264ee1846d5f7d4aa40d4a4e224afae99"
)
EXPECTED_ROUTE_CUSTODY_SHA256 = (
    "14c88e017bc16aeb1406c31aae41e04cabf50dffcce6aa2de9253f6d7323564e"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_ROUTE_TRANSCRIPT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

MODE = "magnetization"
BASE_PARENT_HORIZON = 88
EXTENDED_HORIZON = 90
K622592 = 622_592
M_CANDIDATES = tuple(range(81_920, K622592 + 1, 16_384))
EXPECTED_CANDIDATE_SHA256 = (
    "4de63e9494a84e9603fccfa0bbf6d5e03da1be4aee08927728e8f575ad516d01"
)
POLICY_CAPS_BASE = {
    "max_candidate_K": 622_592,
    "max_output_terms_if_successful": 622_592,
    "max_single_expansion_terms": 786_432,
    "max_digest_terms": 786_432,
    "max_term_gate_visits": 536_870_912,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_suffix_accumulator_bits": 224,
}
EXPECTED_WRAPPED_KERNEL_LIMITS = {
    "max_candidate_count": 34,
    "max_digest_terms": 1_048_576,
    "max_expansion_coefficient_tick_bits": 192,
    "max_product_bits": 384,
    "max_retained_K": 622_592,
    "max_single_expansion_terms": 1_048_576,
    "max_source_bytes": 196_608,
    "max_suffix_accumulator_bits": 224,
    "max_term_gate_visits": 1_000_000_000,
    "max_trigonometric_tick_bits": 66,
}
EXPECTED_Q88_E_AFTER_TICKS = "1700535038508063"
EXPECTED_Q88_RETAINED_COUNT = 622_592
EXPECTED_Q88_RETAINED_SHA256 = (
    "8afaf7ce7e55c64f6c89e43929bb2df7d3c9229ccbf0193b171519c703829561"
)
EXPECTED_EXTENSION_CHECKPOINT_ANCHORS = {
    89: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 32,
        "gate_batch_sha256": (
            "c08d8485b35b6ab2b1df14e8d1c60d57836e263fee5649a4095052e42f6fbbab"
        ),
        "budget_prefix_cap_ticks": "1700799964693059",
    },
    90: {
        "stage_index": 2,
        "stage_group": "HU",
        "batch_in_stage": 33,
        "gate_batch_sha256": (
            "ec44bb3afa96f4d843a813f612af51c5478148a2e323a9601861b4ffa88acb8c"
        ),
        "budget_prefix_cap_ticks": "1700904496098731",
    },
}

CANDIDATE_RECORD_KEYS = frozenset({
    "candidate_index", "configured_K", "effective_retained_count",
    "dropped_term_count", "drop_ticks", "E_after_if_selected_ticks",
    "feasible_under_current_prefix_cap",
})
RECORD_FAILURE_ONLY_KEYS = frozenset({
    "minimum_effective_K_to_meet_prefix",
    "required_K_excess_over_policy_maximum",
    "maximum_candidate_drop_excess_over_slack_ticks",
})
RECORD_SUCCESS_ONLY_KEYS = frozenset({
    "selected_effective_retained_count", "selected_dropped_term_count",
    "selected_drop_ticks", "selected_dropped_terms_sha256",
    "retained_expansion_count", "retained_expansion_sha256",
    "minimum_retained_abs_upper_ticks", "maximum_dropped_abs_upper_ticks",
    "E_after_ticks",
})
RECORD_FAILURE_RECORD_KEYS = frozenset({
    "E_before_ticks", "batch_in_stage", "budget_prefix_cap_ticks",
    "candidate_records", "checkpoint_index_zero_based",
    "checkpoint_number_one_based", "gate_batch_sha256",
    "gate_occurrence_first_zero_based", "gate_occurrence_last_zero_based",
    "input_expansion_count", "input_expansion_sha256",
    "maximum_candidate_drop_excess_over_slack_ticks",
    "maximum_expansion_coefficient_tick_bits", "maximum_product_bits",
    "minimum_effective_K_to_meet_prefix", "peak_live_terms_cumulative",
    "peak_live_terms_this_checkpoint", "prefix_slack_before_selection_ticks",
    "pretruncation_expansion_count", "pretruncation_expansion_sha256",
    "ranked_suffix_sha256", "required_K_excess_over_policy_maximum",
    "rounding_cumulative_scaled_ticks_squared",
    "rounding_increment_scaled_ticks_squared", "selected_K",
    "selected_candidate_index", "stage_group", "stage_index", "status",
    "term_gate_visits_cumulative", "term_gate_visits_increment",
})
RECORD_SUCCESS_RECORD_KEYS = (
    RECORD_FAILURE_RECORD_KEYS - RECORD_FAILURE_ONLY_KEYS
    | RECORD_SUCCESS_ONLY_KEYS
)
UPSTREAM_PARENT_RESULT_KEYS = frozenset({
    "schema_version", "transcript_fingerprint", "status",
    "screen_terminal_condition", "observable_id", "input_step_index",
    "attempted_child_step_index", "screen_source_sha256",
    "same_byte_self_execution", "v2_helper_source_sha256",
    "v2_helper_compiled_from_verified_bytes", "v2_helper_module_isolated",
    "v2_run_entrypoint_called", "v6_configuration_source_sha256",
    "v6_configuration_compiled_from_verified_bytes",
    "v6_configuration_module_isolated", "v6_execution_invoked",
    "v6_same_byte_execution_parent", "control_flow_owned_by_screen",
    "screen_execution_components", "screen_execution_components_sha256",
    "configuration_reference", "configuration_reference_sha256",
    "checkpoint_transform", "checkpoint_transform_sha256",
    "arithmetic_kernel_commit", "source_custody",
    "parent_expected_witness_sha256", "input_boundary_custody",
    "input_cumulative_drop_ticks", "maximum_cumulative_drop_ticks",
    "remaining_mapped_steps_including_attempt", "future_checkpoint_denominator",
    "prefix_cap_formula", "candidate_K_values", "candidate_K_values_sha256",
    "candidate_policy_precommitted_at_probe_time", "selection_rule",
    "single_propagation_and_single_ranking_per_checkpoint", "sequence",
    "screen_horizon_checkpoint_count", "horizon_checkpoint_attempted",
    "horizon_reached_with_committed_checkpoint", "kernel_capability_limits",
    "proposed_policy_caps", "root_globals_before", "root_globals_after",
    "root_globals_unchanged", "attempted_checkpoint_count",
    "completed_checkpoint_count", "failure_checkpoint_included",
    "selected_K_history", "selected_K_history_sha256", "records",
    "records_sha256", "failure_record_sha256",
    "last_committed_cumulative_drop_ticks",
    "observed_peak_single_expansion_terms",
    "observed_term_gate_visits_including_terminal_attempt",
    "observed_maximum_expansion_coefficient_tick_bits",
    "observed_maximum_product_bits",
    "observed_rounding_cumulative_scaled_ticks_squared",
    "child_boundary_committed", "positive_artifact_generated",
    "runtime_RSS_host_timestamp_and_float_fields_excluded",
})
RESOURCE_POLICY_ABORT_TOP_LEVEL_KEYS = frozenset({
    "resource_policy_abort", "resource_policy_abort_sha256",
})
RESOURCE_POLICY_ABORT_KEYS = frozenset({
    "schema_version", "abort_id", "abort_kind", "abort_frame_local_schema_id",
    "exception_type", "exception_message", "exception_args",
    "exception_source_role", "exception_chained_from_exact_parent_helper",
    "control_flow_parent_source_sha256", "helper_source_sha256",
    "kernel_source_sha256", "checkpoint_index_zero_based",
    "checkpoint_number_one_based", "stage_index", "stage_group",
    "batch_in_stage", "gate_occurrence_first_zero_based",
    "gate_occurrence_last_zero_based", "gate_batch_sha256",
    "input_expansion_count", "input_expansion_sha256",
    "pretruncation_expansion_count", "observed_term_count",
    "policy_max_single_expansion_terms", "kernel_max_single_expansion_terms",
    "enforced_term_cap", "observed_excess_terms", "policy_relation",
    "gate_batch_propagation_started", "gate_batch_propagation_completed",
    "policy_cap_check_reached", "kernel_cap_violation_triggered",
    "live_expansion_snapshot_available",
    "attempted_checkpoint_pretruncation_digest_computed",
    "attempted_checkpoint_ranking_performed",
    "attempted_checkpoint_candidate_rows_constructed",
    "attempted_checkpoint_selection_performed",
    "attempted_checkpoint_commit_performed",
    "attempted_checkpoint_record_constructed",
    "attempted_checkpoint_partial_expansion_committed",
    "last_committed_record_sha256", "peak_live_terms_this_checkpoint",
    "peak_live_terms_cumulative", "term_gate_visits_increment",
    "term_gate_visits_cumulative", "rounding_increment_scaled_ticks_squared",
    "rounding_cumulative_scaled_ticks_squared",
    "maximum_expansion_coefficient_tick_bits", "maximum_product_bits",
})
EXPECTED_PARENT_RESULT_KEYS = (
    UPSTREAM_PARENT_RESULT_KEYS | RESOURCE_POLICY_ABORT_TOP_LEVEL_KEYS
)
RELABELLED_ADDED_TOP_LEVEL_KEYS = frozenset({
    "arithmetic_kernel_commit_role", "configuration_override",
    "configuration_override_sha256", "control_flow_owned_by_verified_parent",
    "control_flow_parent_compiled_from_verified_bytes",
    "control_flow_parent_module_isolated",
    "control_flow_parent_private_entrypoint_called",
    "control_flow_parent_relative_path",
    "control_flow_parent_runtime_horizon_override_applied",
    "control_flow_parent_same_byte_execution", "control_flow_parent_source_sha256",
    "diagnostic_candidate_ladder_precommitted_before_replay",
    "diagnostic_horizon_precommitted_before_replay",
    "kernel_capability_override", "kernel_capability_override_sha256",
    "kernel_capability_wrapper_compiled_from_verified_bytes",
    "kernel_capability_wrapper_module_isolated",
    "kernel_capability_wrapper_relative_path",
    "kernel_capability_wrapper_source_sha256", "parent_horizon_override",
    "parent_horizon_override_sha256", "predecessor_handoff_validation",
    "predecessor_handoff_validation_sha256", "route_predecessor_reference",
    "route_predecessor_reference_sha256", "v2_arithmetic_compiled_from_verified_bytes",
    "v2_arithmetic_source_sha256", "v6_configuration_source_used_as_baseline_only",
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


def exact_value_equal(left: Any, right: Any) -> bool:
    try:
        return canonical_bytes(left) == canonical_bytes(right)
    except (TypeError, ValueError):
        return False


def bounded_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"byte cap exceeded: {path.name}")
    return payload


def checked_repo_file(repo: Path, relative_path: str) -> Path:
    if type(relative_path) is not str or not relative_path:
        raise RuntimeError("invalid relative path")
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("unsafe relative path")
    root = repo.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("path escapes repository") from exc
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"required regular file missing: {relative_path}")
    return path


def compile_isolated(name: str, path: Path, payload: bytes) -> Any:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, str(path), "exec"), module.__dict__)
    return module


def require_exact_keys(value: Any, expected: frozenset[str], label: str) -> None:
    if type(value) is not dict or frozenset(value) != expected:
        raise RuntimeError(f"{label} schema drift")


def parse_decimal(value: Any, label: str) -> int:
    if type(value) is not str or not value or not value.isdigit():
        raise RuntimeError(f"{label} is not a canonical decimal")
    if len(value) > 1 and value[0] == "0":
        raise RuntimeError(f"{label} is not minimally encoded")
    return int(value)


def is_sha256(value: Any) -> bool:
    return (
        type(value) is str and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_local_configuration() -> None:
    if BASE_PARENT_HORIZON != 88 or EXTENDED_HORIZON != 90:
        raise RuntimeError("M q90 horizon contract drift")
    if len(M_CANDIDATES) != 34 or M_CANDIDATES[-1] != K622592:
        raise RuntimeError("M q90 candidate ladder drift")
    if sha256(canonical_bytes(list(M_CANDIDATES))) != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError("M q90 candidate digest drift")
    if POLICY_CAPS_BASE["max_candidate_K"] != K622592:
        raise RuntimeError("M q90 policy maximum drift")
    if EXPECTED_WRAPPED_KERNEL_LIMITS["max_retained_K"] != K622592:
        raise RuntimeError("M q90 kernel retained maximum drift")
    sizes = {
        "raw": len(EXPECTED_PARENT_RESULT_KEYS),
        "final": len(EXPECTED_RELABELLED_RESULT_KEYS),
        "success": len(RECORD_SUCCESS_RECORD_KEYS),
        "failure": len(RECORD_FAILURE_RECORD_KEYS),
        "row": len(CANDIDATE_RECORD_KEYS),
        "abort": len(RESOURCE_POLICY_ABORT_KEYS),
    }
    if sizes != {
        "raw": 67, "final": 96, "success": 37,
        "failure": 31, "row": 7, "abort": 50,
    }:
        raise RuntimeError("M q90 closed schema size drift")


def load_execution_parent(repo: Path) -> Any:
    path = checked_repo_file(repo, EXECUTION_PARENT_NAME)
    payload = bounded_bytes(path, MAX_PINNED_SOURCE_BYTES)
    if len(payload) != EXPECTED_EXECUTION_PARENT_FILE_SIZE:
        raise RuntimeError("M q88 execution-parent size drift")
    if sha256(payload) != EXPECTED_EXECUTION_PARENT_SHA256:
        raise RuntimeError("M q88 execution-parent source drift")
    parent = compile_isolated("pinned_m_k622592_c34_q88_parent_for_q90", path, payload)
    expected = {
        "SELF_NAME": EXECUTION_PARENT_NAME,
        "CONTROL_FLOW_PARENT_NAME": CONTROL_FLOW_ROOT_NAME,
        "KERNEL_WRAPPER_NAME": KERNEL_WRAPPER_NAME,
        "EXPECTED_CONTROL_FLOW_PARENT_SHA256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "EXPECTED_KERNEL_WRAPPER_SHA256": EXPECTED_KERNEL_WRAPPER_SHA256,
        "EXPECTED_KERNEL_CAPABILITY_MANIFEST_SHA256": EXPECTED_KERNEL_MANIFEST_SHA256,
        "EXTENDED_HORIZON": BASE_PARENT_HORIZON,
        "M_CANDIDATES": M_CANDIDATES,
        "POLICY_CAPS_BASE": POLICY_CAPS_BASE,
        "EXPECTED_WRAPPED_KERNEL_LIMITS": EXPECTED_WRAPPED_KERNEL_LIMITS,
    }
    for field, value in expected.items():
        if getattr(parent, field, None) != value:
            raise RuntimeError(f"M q88 execution-parent contract drift: {field}")
    if frozenset(parent.EXPECTED_PARENT_RESULT_KEYS) != EXPECTED_PARENT_RESULT_KEYS:
        raise RuntimeError("M q88 raw schema drift")
    if frozenset(parent.EXPECTED_RELABELLED_RESULT_KEYS) != EXPECTED_RELABELLED_RESULT_KEYS:
        raise RuntimeError("M q88 final schema drift")
    parent.validate_local_configuration()
    return parent


def _traceback_items(exception: BaseException) -> list[Any]:
    items = []
    item = exception.__traceback__
    while item is not None:
        items.append(item)
        item = item.tb_next
    return items


def _require_abort_parent_authority(parent: Any) -> types.FunctionType:
    expected_run = getattr(parent, "_M_K622592_Q90_EXACT_RUN_FOUR_GATE", None)
    if (
        type(parent) is not types.ModuleType
        or type(getattr(parent, "_VERIFIED_SELF_SOURCE_BYTES", None)) is not bytes
        or sha256(parent._VERIFIED_SELF_SOURCE_BYTES)
        != EXPECTED_CONTROL_FLOW_ROOT_SHA256
        or type(expected_run) is not types.FunctionType
        or parent.run_four_gate is not expected_run
        or expected_run.__globals__ is not parent.__dict__
        or expected_run.__module__ != parent.__name__
        or expected_run.__code__.co_filename != parent.__file__
    ):
        raise RuntimeError("M q90 abort parent same-byte identity drift")
    return expected_run


def _exact_kernel_overflow_count(
    kernel: Any,
    counter: Any,
    traceback_items: list[Any],
) -> int:
    observe_count = kernel.PropagationCounterV2.observe_count
    expected_tail = [
        kernel.propagate_batch.__code__, kernel.propagate_gate.__code__,
        kernel.add_tick_term.__code__, observe_count.__code__,
    ]
    if [item.tb_frame.f_code for item in traceback_items[-4:]] != expected_tail:
        raise RuntimeError("M q90 kernel abort traceback authority drift")
    add_item, deepest = traceback_items[-2], traceback_items[-1]
    if (
        add_item.tb_lineno != 237 or deepest.tb_lineno != 162
        or frozenset(add_item.tb_frame.f_locals)
        != frozenset({"output", "key", "value", "counter"})
        or frozenset(deepest.tb_frame.f_locals) != frozenset({"self", "count"})
    ):
        raise RuntimeError("M q90 kernel abort local schema drift")
    add_local = add_item.tb_frame.f_locals
    deepest_local = deepest.tb_frame.f_locals
    count = deepest_local["count"]
    if (
        deepest_local["self"] is not counter
        or add_local["counter"] is not counter
        or type(count) is not int
        or type(add_local["output"]) is not dict
        or len(add_local["output"]) != count
    ):
        raise RuntimeError("M q90 kernel abort counter identity drift")
    return count


def build_resource_abort_parent_result(
    execution_parent: Any,
    control_parent: Any,
    kernel: Any,
    exception: BaseException,
) -> Dict[str, Any]:
    """Close an exact q89/q90 resource exception from the raw parent frame."""

    expected_run = _require_abort_parent_authority(control_parent)
    traceback_items = _traceback_items(exception)
    run_items = [
        item for item in traceback_items
        if item.tb_frame.f_code is expected_run.__code__
    ]
    if len(run_items) != 1:
        raise RuntimeError("M q90 abort parent traceback authority drift")
    run_item = run_items[0]
    local = run_item.tb_frame.f_locals
    required_locals = {
        "mode", "helper", "v6_configuration", "kernel", "root",
        "source_custody", "root_before", "boundary_custody", "sequence",
        "transform", "helper_config", "candidates", "caps", "counter",
        "E_input", "cumulative", "remaining_steps", "denominator", "horizon",
        "records", "selected_history", "failure", "horizon_reached",
        "gate_index", "stage_index", "stage", "batch_start",
        "checkpoint_index", "checkpoint_number", "batch", "input_count",
        "input_sha", "visits_before", "rounding_before",
    }
    if not required_locals <= set(local):
        raise RuntimeError("M q90 abort parent frame local schema drift")
    if local["kernel"] is not kernel:
        raise RuntimeError("M q90 abort kernel identity drift")

    helper = local["helper"]
    enforce = getattr(helper, "enforce_policy_caps", None)
    if (
        type(helper) is not types.ModuleType
        or type(getattr(helper, "_VERIFIED_SELF_SOURCE_BYTES", None)) is not bytes
        or sha256(helper._VERIFIED_SELF_SOURCE_BYTES) != EXPECTED_V2_HELPER_SHA256
        or type(enforce) is not types.FunctionType
        or enforce.__globals__ is not helper.__dict__
        or enforce.__module__ != helper.__name__
        or enforce.__code__.co_filename != helper.__file__
    ):
        raise RuntimeError("M q90 abort helper authority drift")

    records = local["records"]
    history = local["selected_history"]
    candidates = local["candidates"]
    caps = local["caps"]
    counter = local["counter"]
    checkpoint = local["checkpoint_number"]
    if type(checkpoint) is not int or checkpoint not in (89, 90):
        raise RuntimeError("M q90 abort checkpoint drift")
    checkpoint_index = checkpoint - 1
    expected_gate_index = 4 * checkpoint_index
    if (
        local["mode"] != MODE or type(records) is not list
        or len(records) != checkpoint_index or type(history) is not list
        or len(history) != checkpoint_index
        or local["checkpoint_index"] != checkpoint_index
        or local["horizon"] != EXTENDED_HORIZON
        or local["failure"] is not None or local["horizon_reached"] is not False
        or local["gate_index"] != expected_gate_index
    ):
        raise RuntimeError("M q90 abort checkpoint boundary drift")
    previous = records[-1]
    require_exact_keys(previous, RECORD_SUCCESS_RECORD_KEYS, "abort previous record")
    if (
        previous.get("checkpoint_number_one_based") != checkpoint - 1
        or previous.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
        or previous.get("retained_expansion_count")
        != previous.get("selected_effective_retained_count")
        or history[-1] != previous.get("selected_K")
    ):
        raise RuntimeError("M q90 abort previous commit drift")
    if tuple(candidates) != M_CANDIDATES:
        raise RuntimeError("M q90 abort candidate ladder drift")
    expected_caps = {**POLICY_CAPS_BASE, "max_candidate_count": 34}
    if not exact_value_equal(caps, expected_caps):
        raise RuntimeError("M q90 abort policy caps drift")
    if kernel.RESOURCE_LIMITS != EXPECTED_WRAPPED_KERNEL_LIMITS:
        raise RuntimeError("M q90 abort kernel limits drift")

    batch = local["batch"]
    stage = local["stage"]
    if type(batch) is not list or len(batch) != 4 or type(stage) is not dict:
        raise RuntimeError("M q90 abort gate batch schema drift")
    anchor = {
        "stage_index": local["stage_index"],
        "stage_group": stage.get("group"),
        "batch_in_stage": local["batch_start"] // 4,
        "gate_batch_sha256": helper.gate_batch_sha256(batch),
    }
    expected_anchor = dict(EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint])
    expected_anchor.pop("budget_prefix_cap_ticks")
    if not exact_value_equal(anchor, expected_anchor):
        raise RuntimeError("M q90 abort checkpoint anchor drift")
    if (
        local["input_count"] != previous.get("retained_expansion_count")
        or local["input_sha"] != previous.get("retained_expansion_sha256")
    ):
        raise RuntimeError("M q90 abort input continuity drift")

    policy_cap = caps["max_single_expansion_terms"]
    kernel_cap = kernel.RESOURCE_LIMITS["max_single_expansion_terms"]
    pre_count = observed_count = None
    propagation_completed = policy_check_reached = None
    kernel_violation = snapshot_available = None
    source_role = chained = abort_kind = local_schema = relation = enforced = None
    helper_messages = {
        "design policy live-term cap exceeded": (
            "final_live_terms", 301,
            frozenset({"kernel", "counter", "term_count", "caps"}),
        ),
        "design policy transient live-term cap exceeded": (
            "transient_live_terms", 313,
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
        abort_kind, helper_line, helper_locals = helper_messages[message]
        helper_items = [
            item for item in traceback_items
            if item.tb_frame.f_code is enforce.__code__
        ]
        if (
            len(helper_items) != 1 or traceback_items[-1] is not helper_items[0]
            or run_item.tb_lineno != 589 or helper_items[0].tb_lineno != helper_line
            or frozenset(helper_items[0].tb_frame.f_locals) != helper_locals
        ):
            raise RuntimeError("M q90 helper abort traceback/local schema drift")
        helper_local = helper_items[0].tb_frame.f_locals
        if (
            helper_local["kernel"] is not kernel
            or helper_local["counter"] is not counter
            or helper_local["caps"] is not caps
            or type(helper_local["term_count"]) is not int
        ):
            raise RuntimeError("M q90 helper abort argument identity drift")
        pre_count = helper_local["term_count"]
        if (
            local.get("pre_count") != pre_count
            or type(local.get("expansion")) is not dict
            or len(local["expansion"]) != pre_count
        ):
            raise RuntimeError("M q90 helper abort pre-count binding drift")
        propagation_completed = policy_check_reached = snapshot_available = True
        kernel_violation = False
        source_role = "exact_parent_helper"
        chained = True
        enforced = policy_cap
        if abort_kind == "final_live_terms":
            observed_count = pre_count
            local_schema = "helper_final_live_terms_v1"
            relation = "pretruncation_expansion_count>policy_max_single_expansion_terms"
            if pre_count <= policy_cap:
                raise RuntimeError("M q90 final-live cap relation drift")
        else:
            observed_count = counter.window_peak_live_terms
            local_schema = "helper_transient_live_terms_v1"
            relation = (
                "peak_live_terms_this_checkpoint>"
                "policy_max_single_expansion_terms>=pretruncation_expansion_count"
            )
            if not pre_count <= policy_cap < observed_count:
                raise RuntimeError("M q90 transient-live cap relation drift")
    elif (
        type(exception) is getattr(kernel, "SchemaError", None)
        and exception.args == ("v2 single-expansion term cap exceeded",)
    ):
        if run_item.tb_lineno != 587:
            raise RuntimeError("M q90 kernel abort parent line drift")
        observed_count = _exact_kernel_overflow_count(kernel, counter, traceback_items)
        if observed_count <= kernel_cap:
            raise RuntimeError("M q90 kernel cap relation drift")
        if local.get("pre_count") != previous["pretruncation_expansion_count"]:
            raise RuntimeError("M q90 kernel abort stale pre-count drift")
        propagation_completed = policy_check_reached = snapshot_available = False
        kernel_violation = True
        source_role = "exact_wrapped_v2_kernel"
        chained = False
        abort_kind = "kernel_single_expansion_terms"
        local_schema = "kernel_observe_count_before_pre_count_assignment_v1"
        relation = (
            "observed_term_count>kernel_max_single_expansion_terms_"
            "before_pretruncation_assignment"
        )
        enforced = kernel_cap
    else:
        raise RuntimeError("M q90 resource exception identity drift")

    if (
        type(observed_count) is not int or observed_count <= enforced
        or counter.peak_live_terms < observed_count
        or counter.window_peak_live_terms < observed_count
    ):
        raise RuntimeError("M q90 abort resource ledger drift")
    root_after = kernel.root_global_snapshot(local["root"])
    if not exact_value_equal(local["root_before"], root_after):
        raise RuntimeError("M q90 abort changed root globals")
    message = exception.args[0]
    abort = {
        "schema_version": 1,
        "abort_id": "M_k622592_c34_q90_policy_resource_abort_v1",
        "abort_kind": abort_kind,
        "abort_frame_local_schema_id": local_schema,
        "exception_type": type(exception).__name__,
        "exception_message": message,
        "exception_args": [message],
        "exception_source_role": source_role,
        "exception_chained_from_exact_parent_helper": chained,
        "control_flow_parent_source_sha256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "helper_source_sha256": EXPECTED_V2_HELPER_SHA256,
        "kernel_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "checkpoint_index_zero_based": checkpoint_index,
        "checkpoint_number_one_based": checkpoint,
        **anchor,
        "gate_occurrence_first_zero_based": expected_gate_index,
        "gate_occurrence_last_zero_based": expected_gate_index + 3,
        "input_expansion_count": local["input_count"],
        "input_expansion_sha256": local["input_sha"],
        "pretruncation_expansion_count": pre_count,
        "observed_term_count": observed_count,
        "policy_max_single_expansion_terms": policy_cap,
        "kernel_max_single_expansion_terms": kernel_cap,
        "enforced_term_cap": enforced,
        "observed_excess_terms": observed_count - enforced,
        "policy_relation": relation,
        "gate_batch_propagation_started": True,
        "gate_batch_propagation_completed": propagation_completed,
        "policy_cap_check_reached": policy_check_reached,
        "kernel_cap_violation_triggered": kernel_violation,
        "live_expansion_snapshot_available": snapshot_available,
        "attempted_checkpoint_pretruncation_digest_computed": False,
        "attempted_checkpoint_ranking_performed": False,
        "attempted_checkpoint_candidate_rows_constructed": False,
        "attempted_checkpoint_selection_performed": False,
        "attempted_checkpoint_commit_performed": False,
        "attempted_checkpoint_record_constructed": False,
        "attempted_checkpoint_partial_expansion_committed": False,
        "last_committed_record_sha256": sha256(canonical_bytes(previous)),
        "peak_live_terms_this_checkpoint": counter.window_peak_live_terms,
        "peak_live_terms_cumulative": counter.peak_live_terms,
        "term_gate_visits_increment": counter.term_gate_visits - local["visits_before"],
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
    require_exact_keys(abort, RESOURCE_POLICY_ABORT_KEYS, "M q90 resource abort")

    raw_parent_sha = sha256(control_parent._VERIFIED_SELF_SOURCE_BYTES)
    components = control_parent.execution_components(
        MODE, raw_parent_sha, local["source_custody"], local["boundary_custody"]
    )
    candidate_sha = sha256(canonical_bytes(list(candidates)))
    configuration_reference = {
        "relative_path": control_parent.V6_CONFIGURATION_NAME,
        "source_sha256": control_parent.EXPECTED_V6_CONFIGURATION_SHA256,
        "role": "candidates_and_caps_reference_only",
        "fields_adopted": [
            f"MODE_CONFIG.{MODE}.candidates", "POLICY_CAPS_BASE",
        ],
        "candidate_K_values_sha256": candidate_sha,
        "policy_caps_base_sha256": control_parent.EXPECTED_V6_CAPS_SHA256,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }
    records_copy = copy.deepcopy(records)
    history_copy = list(history)
    result = {
        "schema_version": 1,
        "transcript_fingerprint": "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1",
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": "DIAGNOSTIC_RESOURCE_POLICY_ABORT",
        "observable_id": local["helper_config"]["observable_id"],
        "input_step_index": local["helper_config"]["input_step_index"],
        "attempted_child_step_index": local["helper_config"]["child_step_index"],
        "screen_source_sha256": raw_parent_sha,
        "same_byte_self_execution": True,
        "v2_helper_source_sha256": EXPECTED_V2_HELPER_SHA256,
        "v2_helper_compiled_from_verified_bytes": True,
        "v2_helper_module_isolated": True,
        "v2_run_entrypoint_called": False,
        "v6_configuration_source_sha256": EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
        "v6_configuration_compiled_from_verified_bytes": True,
        "v6_configuration_module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "control_flow_owned_by_screen": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": configuration_reference,
        "configuration_reference_sha256": sha256(canonical_bytes(configuration_reference)),
        "checkpoint_transform": copy.deepcopy(local["transform"]),
        "checkpoint_transform_sha256": sha256(canonical_bytes(local["transform"])),
        "arithmetic_kernel_commit": helper.KERNEL_COMMIT,
        "source_custody": {
            V2_HELPER_NAME: EXPECTED_V2_HELPER_SHA256,
            V6_BASELINE_CONFIGURATION_NAME: EXPECTED_V6_BASELINE_CONFIGURATION_SHA256,
            **local["source_custody"],
        },
        "parent_expected_witness_sha256": local["helper_config"]["parent_expected_witness_sha256"],
        "input_boundary_custody": copy.deepcopy(local["boundary_custody"]),
        "input_cumulative_drop_ticks": str(local["E_input"]),
        "maximum_cumulative_drop_ticks": str(helper.MAXIMUM_DROP_TICKS),
        "remaining_mapped_steps_including_attempt": local["remaining_steps"],
        "future_checkpoint_denominator": local["denominator"],
        "prefix_cap_formula": (
            f"E{local['helper_config']['input_step_index']}+floor(q*(B-"
            f"E{local['helper_config']['input_step_index']})/("
            f"{local['remaining_steps']}*{control_parent.CHECKPOINTS_PER_MAPPED_STEP}))"
        ),
        "candidate_K_values": list(candidates),
        "candidate_K_values_sha256": candidate_sha,
        "candidate_policy_precommitted_at_probe_time": False,
        "selection_rule": (
            "first_candidate_whose_exact_ranked_suffix_drop_respects_current_prefix_cap"
        ),
        "single_propagation_and_single_ranking_per_checkpoint": True,
        "sequence": copy.deepcopy(local["sequence"]),
        "screen_horizon_checkpoint_count": local["horizon"],
        "horizon_checkpoint_attempted": checkpoint == EXTENDED_HORIZON,
        "horizon_reached_with_committed_checkpoint": False,
        "kernel_capability_limits": dict(kernel.RESOURCE_LIMITS),
        "proposed_policy_caps": dict(caps),
        "root_globals_before": copy.deepcopy(local["root_before"]),
        "root_globals_after": root_after,
        "root_globals_unchanged": True,
        "attempted_checkpoint_count": checkpoint,
        "completed_checkpoint_count": checkpoint - 1,
        "failure_checkpoint_included": False,
        "selected_K_history": history_copy,
        "selected_K_history_sha256": sha256(canonical_bytes(history_copy)),
        "records": records_copy,
        "records_sha256": sha256(canonical_bytes(records_copy)),
        "failure_record_sha256": None,
        "last_committed_cumulative_drop_ticks": str(local["cumulative"]),
        "observed_peak_single_expansion_terms": abort["peak_live_terms_cumulative"],
        "observed_term_gate_visits_including_terminal_attempt": abort["term_gate_visits_cumulative"],
        "observed_maximum_expansion_coefficient_tick_bits": abort["maximum_expansion_coefficient_tick_bits"],
        "observed_maximum_product_bits": abort["maximum_product_bits"],
        "observed_rounding_cumulative_scaled_ticks_squared": abort["rounding_cumulative_scaled_ticks_squared"],
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
        "runtime_RSS_host_timestamp_and_float_fields_excluded": True,
        "resource_policy_abort": abort,
        "resource_policy_abort_sha256": sha256(canonical_bytes(abort)),
    }
    require_exact_keys(result, EXPECTED_PARENT_RESULT_KEYS, "structured raw result")
    return result


def execute_control_parent_with_structured_abort(
    execution_parent: Any,
    control_parent: Any,
    kernel: Any,
    repo: Path,
) -> Dict[str, Any]:
    try:
        return execution_parent.normalize_completed_parent_result(
            control_parent._run_verified(repo, MODE)
        )
    except RuntimeError as exception:
        if type(exception) is not RuntimeError or exception.args not in (
            ("design policy live-term cap exceeded",),
            ("design policy transient live-term cap exceeded",),
        ):
            raise
        return build_resource_abort_parent_result(
            execution_parent, control_parent, kernel, exception
        )
    except Exception as exception:
        if (
            type(exception) is not getattr(kernel, "SchemaError", None)
            or exception.args != ("v2 single-expansion term cap exceeded",)
        ):
            raise
        return build_resource_abort_parent_result(
            execution_parent, control_parent, kernel, exception
        )


def execute_parent_replay(parent: Any, repo: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute the exact q88 private entrypoint with only horizon semantics changed."""

    if type(parent) is not types.ModuleType:
        raise RuntimeError("M q90 execution parent is not isolated")
    parent.validate_local_configuration()
    originals = {
        "EXTENDED_HORIZON": parent.EXTENDED_HORIZON,
        "validate_local_configuration": parent.validate_local_configuration,
        "load_configured_v6_baseline": parent.load_configured_v6_baseline,
        "load_kernel_wrapper": parent.load_kernel_wrapper,
        "load_route_reference": parent.load_route_reference,
        "configure_parent_execution": parent.configure_parent_execution,
        "execute_parent_fail_closed": parent.execute_parent_fail_closed,
        "validate_and_relabel": parent.validate_and_relabel,
    }
    context: Dict[str, Any] = {
        "execution_parent_private_entrypoint_called": False,
        "raw_replay_completed": False,
        "q88_internal_c33_loader_suppressed": False,
        "q88_internal_relabel_suppressed": False,
        "execution_parent_abort_adapter_installed": False,
    }

    def capture_configuration(source_repo):
        configuration, baseline_m = originals["load_configured_v6_baseline"](source_repo)
        context["baseline_m"] = tuple(baseline_m)
        return configuration, baseline_m

    def capture_wrapper(source_repo):
        wrapper, wrapper_sha, manifest = originals["load_kernel_wrapper"](source_repo)
        context.update({
            "kernel": wrapper,
            "wrapper_sha": wrapper_sha,
            "wrapper_manifest": copy.deepcopy(manifest),
        })
        return wrapper, wrapper_sha, manifest

    def suppress_c33_loader(_source_repo):
        if context["raw_replay_completed"] is not True:
            raise RuntimeError("M q90 internal route suppression order drift")
        context["q88_internal_c33_loader_suppressed"] = True
        return {}, {}

    def capture_horizon(control_parent, configuration, wrapper):
        control_parent._M_K622592_Q90_EXACT_RUN_FOUR_GATE = control_parent.run_four_gate
        horizon = originals["configure_parent_execution"](
            control_parent, configuration, wrapper
        )
        context["raw_control_flow_horizon_override"] = copy.deepcopy(horizon)
        return horizon

    def execute_q90(control_parent, source_repo):
        context["execution_parent_abort_adapter_installed"] = True
        result = execute_control_parent_with_structured_abort(
            parent, control_parent, context["kernel"], source_repo
        )
        context["raw_replay_completed"] = True
        return result

    def return_raw(result, *_args):
        context["q88_internal_relabel_suppressed"] = True
        return result

    try:
        parent.EXTENDED_HORIZON = EXTENDED_HORIZON
        parent.validate_local_configuration = lambda: None
        parent.load_configured_v6_baseline = capture_configuration
        parent.load_kernel_wrapper = capture_wrapper
        parent.load_route_reference = suppress_c33_loader
        parent.configure_parent_execution = capture_horizon
        parent.execute_parent_fail_closed = execute_q90
        parent.validate_and_relabel = return_raw
        context["execution_parent_private_entrypoint_called"] = True
        result = parent._run_verified(repo.resolve())
    finally:
        for field, value in originals.items():
            setattr(parent, field, value)
    if type(result) is not dict:
        raise RuntimeError("M q90 execution parent returned non-dict")
    required = {
        "baseline_m", "kernel", "wrapper_sha", "wrapper_manifest",
        "raw_control_flow_horizon_override",
    }
    if not required <= context.keys():
        raise RuntimeError("M q90 execution adapter context incomplete")
    for key in (
        "raw_replay_completed", "q88_internal_c33_loader_suppressed",
        "q88_internal_relabel_suppressed", "execution_parent_abort_adapter_installed",
    ):
        if context[key] is not True:
            raise RuntimeError(f"M q90 execution adapter evidence drift: {key}")
    if context["wrapper_sha"] != EXPECTED_KERNEL_WRAPPER_SHA256:
        raise RuntimeError("M q90 captured wrapper drift")
    return result, context


def _nested_digest_pair(value: Mapping[str, Any], key: str, digest_key: str) -> None:
    nested = value.get(key)
    digest = value.get(digest_key)
    if nested is None:
        if digest is not None:
            raise RuntimeError(f"null nested digest drift: {key}")
    elif digest != sha256(canonical_bytes(nested)):
        raise RuntimeError(f"nested digest drift: {key}")


def load_route_reference(
    repo: Path,
    execution_parent: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    parent_raw = bounded_bytes(
        checked_repo_file(repo, EXECUTION_PARENT_NAME), MAX_PINNED_SOURCE_BYTES
    )
    if (
        len(parent_raw) != EXPECTED_EXECUTION_PARENT_FILE_SIZE
        or sha256(parent_raw) != EXPECTED_EXECUTION_PARENT_SHA256
    ):
        raise RuntimeError("M q88 execution-parent post-reference drift")
    raw = bounded_bytes(
        checked_repo_file(repo, ROUTE_PREDECESSOR_TRANSCRIPT_NAME),
        MAX_ROUTE_TRANSCRIPT_BYTES,
    )
    if (
        len(raw) != EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE
        or sha256(raw) != EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256
    ):
        raise RuntimeError("M q88 canonical exact-byte drift")
    try:
        transcript = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("M q88 canonical is invalid JSON") from exc
    if type(transcript) is not dict or raw != canonical_bytes(transcript):
        raise RuntimeError("M q88 transcript is not canonical JSON")
    require_exact_keys(
        transcript,
        frozenset(execution_parent.EXPECTED_RELABELLED_RESULT_KEYS),
        "M q88 canonical top level",
    )
    expected = {
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k622592_c34_q88_screen_v1"
        ),
        "screen_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_horizon_checkpoint_count": 88,
        "screen_terminal_condition": "DIAGNOSTIC_HORIZON_REACHED",
        "attempted_checkpoint_count": 88,
        "completed_checkpoint_count": 88,
        "failure_checkpoint_included": False,
        "failure_record_sha256": None,
        "horizon_checkpoint_attempted": True,
        "horizon_reached_with_committed_checkpoint": True,
        "resource_policy_abort": None,
        "resource_policy_abort_sha256": None,
        "candidate_K_values": list(M_CANDIDATES),
        "candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "proposed_policy_caps": {**POLICY_CAPS_BASE, "max_candidate_count": 34},
        "kernel_capability_limits": EXPECTED_WRAPPED_KERNEL_LIMITS,
        "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
        "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
    }
    for key, value in expected.items():
        if not exact_value_equal(transcript.get(key), value):
            raise RuntimeError(f"M q88 canonical field drift: {key}")
    digest_pins = {
        "configuration_reference_sha256": EXPECTED_ROUTE_CONFIGURATION_REFERENCE_SHA256,
        "configuration_override_sha256": EXPECTED_ROUTE_CONFIGURATION_OVERRIDE_SHA256,
        "kernel_capability_override_sha256": EXPECTED_ROUTE_KERNEL_OVERRIDE_SHA256,
        "parent_horizon_override_sha256": EXPECTED_ROUTE_PARENT_HORIZON_OVERRIDE_SHA256,
        "route_predecessor_reference_sha256": EXPECTED_ROUTE_REFERENCE_SHA256,
        "predecessor_handoff_validation_sha256": EXPECTED_ROUTE_HANDOFF_SHA256,
        "checkpoint_transform_sha256": EXPECTED_ROUTE_TRANSFORM_SHA256,
        "screen_execution_components_sha256": EXPECTED_ROUTE_COMPONENTS_SHA256,
    }
    for key, digest in digest_pins.items():
        if transcript.get(key) != digest:
            raise RuntimeError(f"M q88 nested authority pin drift: {key}")
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
        _nested_digest_pair(transcript, value_key, digest_key)
    if sha256(canonical_bytes(transcript["source_custody"])) != EXPECTED_ROUTE_CUSTODY_SHA256:
        raise RuntimeError("M q88 source custody drift")
    records = transcript.get("records")
    history = transcript.get("selected_K_history")
    if type(records) is not list or len(records) != 88:
        raise RuntimeError("M q88 record ledger drift")
    if type(history) is not list or len(history) != 88:
        raise RuntimeError("M q88 history ledger drift")
    if sha256(canonical_bytes(records)) != EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256:
        raise RuntimeError("M q88 records digest drift")
    if sha256(canonical_bytes(history)) != EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256:
        raise RuntimeError("M q88 history digest drift")
    q88 = records[-1]
    if sha256(canonical_bytes(q88)) != EXPECTED_ROUTE_PREDECESSOR_Q88_RECORD_SHA256:
        raise RuntimeError("M q88 record anchor drift")
    if sha256(canonical_bytes(q88["candidate_records"])) != EXPECTED_ROUTE_PREDECESSOR_Q88_ROWS_SHA256:
        raise RuntimeError("M q88 row anchor drift")
    if (
        q88.get("E_after_ticks") != EXPECTED_Q88_E_AFTER_TICKS
        or q88.get("retained_expansion_count") != EXPECTED_Q88_RETAINED_COUNT
        or q88.get("retained_expansion_sha256") != EXPECTED_Q88_RETAINED_SHA256
    ):
        raise RuntimeError("M q88 committed state drift")
    reference = {
        "route_id": "M_k622592_c34_q88_to_same_cap_q90_v1",
        "execution_parent": {
            "relative_path": EXECUTION_PARENT_NAME,
            "source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
            "file_size_bytes": EXPECTED_EXECUTION_PARENT_FILE_SIZE,
            "compiled_from_verified_bytes": True,
            "private_entrypoint_called": True,
            "same_byte_execution": True,
        },
        "canonical_transcript": {
            "relative_path": ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
            "semantic_and_file_sha256": EXPECTED_ROUTE_PREDECESSOR_TRANSCRIPT_SHA256,
            "file_size_bytes": EXPECTED_ROUTE_PREDECESSOR_FILE_SIZE,
            "records_sha256": EXPECTED_ROUTE_PREDECESSOR_RECORDS_SHA256,
            "selected_K_history_sha256": EXPECTED_ROUTE_PREDECESSOR_HISTORY_SHA256,
            "loaded_before_replay": False,
            "loaded_after_full_replay_as_exact_reference": True,
            "compiled": False,
            "executed": False,
            "propagation_input": False,
            "state_resume_input": False,
            "execution_source_layer": False,
        },
        "K607993_evidence_scope": (
            "fixed_M_C33_q88_predecessor_state_prefix_only_no_q89_q90_extrapolation"
        ),
        "q89_and_q90_outcomes_precommitted": False,
        "incremental_semantic_delta": {
            "candidate_K_values_changed": False,
            "policy_caps_changed": False,
            "kernel_capability_limits_changed": False,
            "horizon_checkpoint_count": {"before": 88, "after": 90},
        },
    }
    return transcript, reference


def _validate_row(
    row: Any,
    index: int,
    configured_K: int,
    pre_count: int,
    E_before: int,
    slack: int,
) -> Dict[str, Any]:
    require_exact_keys(row, CANDIDATE_RECORD_KEYS, "candidate row")
    effective = min(configured_K, pre_count)
    if (
        row.get("candidate_index") != index
        or row.get("configured_K") != configured_K
        or row.get("effective_retained_count") != effective
        or row.get("dropped_term_count") != pre_count - effective
    ):
        raise RuntimeError("candidate row index/count drift")
    drop = parse_decimal(row.get("drop_ticks"), "candidate drop")
    after = parse_decimal(row.get("E_after_if_selected_ticks"), "candidate E after")
    if after != E_before + drop:
        raise RuntimeError("candidate energy recurrence drift")
    if row.get("feasible_under_current_prefix_cap") is not (drop <= slack):
        raise RuntimeError("candidate feasibility drift")
    return dict(row)


def _validate_extension_record(
    record: Any,
    previous: Mapping[str, Any],
    checkpoint: int,
) -> str:
    status = record.get("status") if type(record) is dict else None
    success = status == "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
    failure = status == "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
    if not (success or failure):
        raise RuntimeError(f"M q{checkpoint} status drift")
    require_exact_keys(
        record,
        RECORD_SUCCESS_RECORD_KEYS if success else RECORD_FAILURE_RECORD_KEYS,
        f"M q{checkpoint} record",
    )
    anchor = EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
    expected_gate = 4 * (checkpoint - 1)
    if (
        record["checkpoint_index_zero_based"] != checkpoint - 1
        or record["checkpoint_number_one_based"] != checkpoint
        or record["stage_index"] != anchor["stage_index"]
        or record["stage_group"] != anchor["stage_group"]
        or record["batch_in_stage"] != anchor["batch_in_stage"]
        or record["gate_occurrence_first_zero_based"] != expected_gate
        or record["gate_occurrence_last_zero_based"] != expected_gate + 3
        or record["gate_batch_sha256"] != anchor["gate_batch_sha256"]
        or record["budget_prefix_cap_ticks"] != anchor["budget_prefix_cap_ticks"]
    ):
        raise RuntimeError(f"M q{checkpoint} checkpoint anchor drift")
    if (
        record["E_before_ticks"] != previous["E_after_ticks"]
        or record["input_expansion_count"] != previous["retained_expansion_count"]
        or record["input_expansion_sha256"] != previous["retained_expansion_sha256"]
    ):
        raise RuntimeError(f"M q{checkpoint} input continuity drift")
    pre_count = record["pretruncation_expansion_count"]
    if type(pre_count) is not int or pre_count < 0:
        raise RuntimeError(f"M q{checkpoint} pre-count drift")
    for key in ("pretruncation_expansion_sha256", "ranked_suffix_sha256"):
        if not is_sha256(record[key]):
            raise RuntimeError(f"M q{checkpoint} digest drift: {key}")
    E_before = parse_decimal(record["E_before_ticks"], "record E before")
    prefix = parse_decimal(record["budget_prefix_cap_ticks"], "record prefix")
    slack = parse_decimal(record["prefix_slack_before_selection_ticks"], "record slack")
    if slack != prefix - E_before:
        raise RuntimeError(f"M q{checkpoint} prefix slack drift")
    rows = record["candidate_records"]
    if type(rows) is not list or len(rows) != len(M_CANDIDATES):
        raise RuntimeError(f"M q{checkpoint} candidate matrix drift")
    validated = [
        _validate_row(row, index, configured_K, pre_count, E_before, slack)
        for index, (row, configured_K) in enumerate(zip(rows, M_CANDIDATES))
    ]
    drops = [parse_decimal(row["drop_ticks"], "row drop") for row in validated]
    if any(left < right for left, right in zip(drops, drops[1:])):
        raise RuntimeError(f"M q{checkpoint} candidate drop monotonicity drift")
    feasible = [index for index, row in enumerate(validated) if row["feasible_under_current_prefix_cap"]]
    if success:
        if not feasible or record["selected_candidate_index"] != feasible[0]:
            raise RuntimeError(f"M q{checkpoint} first-feasible selection drift")
        index = feasible[0]
        row = validated[index]
        if (
            record["selected_K"] != M_CANDIDATES[index]
            or record["selected_effective_retained_count"] != row["effective_retained_count"]
            or record["selected_dropped_term_count"] != row["dropped_term_count"]
            or record["selected_drop_ticks"] != row["drop_ticks"]
            or record["E_after_ticks"] != row["E_after_if_selected_ticks"]
            or record["retained_expansion_count"] != row["effective_retained_count"]
        ):
            raise RuntimeError(f"M q{checkpoint} selected-row recurrence drift")
        for key in ("selected_dropped_terms_sha256", "retained_expansion_sha256"):
            if not is_sha256(record[key]):
                raise RuntimeError(f"M q{checkpoint} selected digest drift")
        minimum = parse_decimal(record["minimum_retained_abs_upper_ticks"], "minimum retained")
        maximum = parse_decimal(record["maximum_dropped_abs_upper_ticks"], "maximum dropped")
        if minimum < maximum:
            raise RuntimeError(f"M q{checkpoint} ranking boundary drift")
        return "success"
    if feasible or record["selected_candidate_index"] is not None or record["selected_K"] is not None:
        raise RuntimeError(f"M q{checkpoint} failure selection drift")
    minimum_K = record["minimum_effective_K_to_meet_prefix"]
    if (
        type(minimum_K) is not int or minimum_K <= K622592
        or record["required_K_excess_over_policy_maximum"] != minimum_K - K622592
        or parse_decimal(
            record["maximum_candidate_drop_excess_over_slack_ticks"],
            "maximum candidate excess",
        ) != drops[-1] - slack
    ):
        raise RuntimeError(f"M q{checkpoint} failure arithmetic drift")
    return "failure"


def validate_resource_policy_abort(
    result: Mapping[str, Any],
    previous: Mapping[str, Any],
    checkpoint: int,
) -> Dict[str, Any] | None:
    abort = result.get("resource_policy_abort")
    digest = result.get("resource_policy_abort_sha256")
    if abort is None:
        if digest is not None:
            raise RuntimeError("null resource abort digest drift")
        return None
    require_exact_keys(abort, RESOURCE_POLICY_ABORT_KEYS, "resource abort")
    if digest != sha256(canonical_bytes(abort)):
        raise RuntimeError("resource abort digest drift")
    anchor = EXPECTED_EXTENSION_CHECKPOINT_ANCHORS[checkpoint]
    expected = {
        "schema_version": 1,
        "abort_id": "M_k622592_c34_q90_policy_resource_abort_v1",
        "control_flow_parent_source_sha256": EXPECTED_CONTROL_FLOW_ROOT_SHA256,
        "helper_source_sha256": EXPECTED_V2_HELPER_SHA256,
        "kernel_source_sha256": EXPECTED_V2_ARITHMETIC_SHA256,
        "checkpoint_index_zero_based": checkpoint - 1,
        "checkpoint_number_one_based": checkpoint,
        "stage_index": anchor["stage_index"],
        "stage_group": anchor["stage_group"],
        "batch_in_stage": anchor["batch_in_stage"],
        "gate_occurrence_first_zero_based": 4 * (checkpoint - 1),
        "gate_occurrence_last_zero_based": 4 * (checkpoint - 1) + 3,
        "gate_batch_sha256": anchor["gate_batch_sha256"],
        "input_expansion_count": previous["retained_expansion_count"],
        "input_expansion_sha256": previous["retained_expansion_sha256"],
        "policy_max_single_expansion_terms": 786_432,
        "kernel_max_single_expansion_terms": 1_048_576,
        "gate_batch_propagation_started": True,
        "attempted_checkpoint_pretruncation_digest_computed": False,
        "attempted_checkpoint_ranking_performed": False,
        "attempted_checkpoint_candidate_rows_constructed": False,
        "attempted_checkpoint_selection_performed": False,
        "attempted_checkpoint_commit_performed": False,
        "attempted_checkpoint_record_constructed": False,
        "attempted_checkpoint_partial_expansion_committed": False,
        "last_committed_record_sha256": sha256(canonical_bytes(previous)),
    }
    for key, value in expected.items():
        if not exact_value_equal(abort.get(key), value):
            raise RuntimeError(f"M q{checkpoint} resource abort drift: {key}")
    kind = abort.get("abort_kind")
    kind_expected = {
        "final_live_terms": {
            "exception_type": "RuntimeError",
            "exception_message": "design policy live-term cap exceeded",
            "abort_frame_local_schema_id": "helper_final_live_terms_v1",
            "exception_source_role": "exact_parent_helper",
            "exception_chained_from_exact_parent_helper": True,
            "gate_batch_propagation_completed": True,
            "policy_cap_check_reached": True,
            "kernel_cap_violation_triggered": False,
            "live_expansion_snapshot_available": True,
            "enforced_term_cap": 786_432,
        },
        "transient_live_terms": {
            "exception_type": "RuntimeError",
            "exception_message": "design policy transient live-term cap exceeded",
            "abort_frame_local_schema_id": "helper_transient_live_terms_v1",
            "exception_source_role": "exact_parent_helper",
            "exception_chained_from_exact_parent_helper": True,
            "gate_batch_propagation_completed": True,
            "policy_cap_check_reached": True,
            "kernel_cap_violation_triggered": False,
            "live_expansion_snapshot_available": True,
            "enforced_term_cap": 786_432,
        },
        "kernel_single_expansion_terms": {
            "exception_type": "SchemaError",
            "exception_message": "v2 single-expansion term cap exceeded",
            "abort_frame_local_schema_id": "kernel_observe_count_before_pre_count_assignment_v1",
            "exception_source_role": "exact_wrapped_v2_kernel",
            "exception_chained_from_exact_parent_helper": False,
            "gate_batch_propagation_completed": False,
            "policy_cap_check_reached": False,
            "kernel_cap_violation_triggered": True,
            "live_expansion_snapshot_available": False,
            "enforced_term_cap": 1_048_576,
        },
    }
    if kind not in kind_expected:
        raise RuntimeError("resource abort kind drift")
    for key, value in kind_expected[kind].items():
        if not exact_value_equal(abort.get(key), value):
            raise RuntimeError(f"resource abort kind field drift: {key}")
    if abort.get("exception_args") != [abort["exception_message"]]:
        raise RuntimeError("resource abort exception args drift")
    observed = abort.get("observed_term_count")
    enforced = abort.get("enforced_term_cap")
    if (
        type(observed) is not int or observed <= enforced
        or abort.get("observed_excess_terms") != observed - enforced
    ):
        raise RuntimeError("resource abort cap relation drift")
    pre_count = abort.get("pretruncation_expansion_count")
    if kind == "final_live_terms" and pre_count != observed:
        raise RuntimeError("final-live pre-count drift")
    if kind == "transient_live_terms" and (
        type(pre_count) is not int or pre_count > 786_432
        or abort["peak_live_terms_this_checkpoint"] != observed
    ):
        raise RuntimeError("transient-live relation drift")
    if kind == "kernel_single_expansion_terms" and pre_count is not None:
        raise RuntimeError("kernel abort exposed pre-count")
    for key in (
        "peak_live_terms_this_checkpoint", "peak_live_terms_cumulative",
        "term_gate_visits_increment", "term_gate_visits_cumulative",
        "maximum_expansion_coefficient_tick_bits", "maximum_product_bits",
    ):
        if type(abort.get(key)) is not int or abort[key] < 0:
            raise RuntimeError(f"resource abort integer drift: {key}")
    for key in (
        "rounding_increment_scaled_ticks_squared",
        "rounding_cumulative_scaled_ticks_squared",
    ):
        parse_decimal(abort.get(key), key)
    return dict(abort)


def validate_replay_handoff(
    result: Mapping[str, Any],
    predecessor: Mapping[str, Any],
) -> Dict[str, Any]:
    require_exact_keys(result, EXPECTED_PARENT_RESULT_KEYS, "M q90 raw result")
    require_exact_keys(predecessor, EXPECTED_RELABELLED_RESULT_KEYS, "M q88 predecessor")
    if (
        result.get("candidate_K_values") != list(M_CANDIDATES)
        or result.get("candidate_K_values_sha256") != EXPECTED_CANDIDATE_SHA256
        or result.get("proposed_policy_caps")
        != {**POLICY_CAPS_BASE, "max_candidate_count": 34}
        or result.get("kernel_capability_limits") != EXPECTED_WRAPPED_KERNEL_LIMITS
    ):
        raise RuntimeError("M q90 ladder/capability drift")
    records = result.get("records")
    history = result.get("selected_K_history")
    old_records = predecessor.get("records")
    old_history = predecessor.get("selected_K_history")
    if (
        type(records) is not list or not 88 <= len(records) <= 90
        or type(history) is not list or not 88 <= len(history) <= 90
        or type(old_records) is not list or len(old_records) != 88
        or type(old_history) is not list or len(old_history) != 88
    ):
        raise RuntimeError("M q90 ledger length drift")
    if not exact_value_equal(records[:88], old_records):
        raise RuntimeError("M q1-q88 record prefix drift")
    if not exact_value_equal(history[:88], old_history):
        raise RuntimeError("M q1-q88 history prefix drift")
    for checkpoint, record in enumerate(records[:88], 1):
        require_exact_keys(record, RECORD_SUCCESS_RECORD_KEYS, f"M q{checkpoint} prefix")
        rows = record.get("candidate_records")
        if type(rows) is not list or len(rows) != 34:
            raise RuntimeError(f"M q{checkpoint} prefix row drift")
        for row in rows:
            require_exact_keys(row, CANDIDATE_RECORD_KEYS, "prefix candidate row")
    q88 = records[87]
    if (
        q88.get("E_after_ticks") != EXPECTED_Q88_E_AFTER_TICKS
        or q88.get("retained_expansion_count") != EXPECTED_Q88_RETAINED_COUNT
        or q88.get("retained_expansion_sha256") != EXPECTED_Q88_RETAINED_SHA256
    ):
        raise RuntimeError("M q88 state handoff drift")

    abort = result.get("resource_policy_abort")
    branch = None
    terminal = None
    failure = None
    final_success = q88
    if abort is not None:
        checkpoint = abort.get("checkpoint_number_one_based") if type(abort) is dict else None
        if checkpoint == 89 and len(records) == 88 and len(history) == 88:
            validate_resource_policy_abort(result, q88, 89)
            branch = "Q89_RESOURCE_ABORT_Q90_NOT_ATTEMPTED"
            terminal = "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
        elif checkpoint == 90 and len(records) == 89 and len(history) == 89:
            if _validate_extension_record(records[88], q88, 89) != "success":
                raise RuntimeError("M q90 abort lacks q89 success")
            if history[-1] != records[88]["selected_K"]:
                raise RuntimeError("M q89 history drift")
            final_success = records[88]
            validate_resource_policy_abort(result, final_success, 90)
            branch = "Q89_SUCCESS_Q90_RESOURCE_ABORT"
            terminal = "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
        else:
            raise RuntimeError("M q90 resource branch ledger drift")
    else:
        if result.get("resource_policy_abort_sha256") is not None:
            raise RuntimeError("M q90 null resource digest drift")
        if len(records) == 89 and len(history) == 88:
            if _validate_extension_record(records[88], q88, 89) != "failure":
                raise RuntimeError("M q89 terminal record is not failure")
            failure = records[88]
            branch = "Q89_FAILURE_Q90_NOT_ATTEMPTED"
            terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        elif len(records) == 90:
            if _validate_extension_record(records[88], q88, 89) != "success":
                raise RuntimeError("M q90 path lacks q89 success")
            if history[88] != records[88]["selected_K"]:
                raise RuntimeError("M q89 selected history drift")
            final_success = records[88]
            q90_status = _validate_extension_record(records[89], final_success, 90)
            if q90_status == "failure" and len(history) == 89:
                failure = records[89]
                branch = "Q89_SUCCESS_Q90_FAILURE"
                terminal = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
            elif q90_status == "success" and len(history) == 90:
                if history[89] != records[89]["selected_K"]:
                    raise RuntimeError("M q90 selected history drift")
                final_success = records[89]
                branch = "Q89_AND_Q90_SUCCESS_HORIZON_REACHED"
                terminal = "DIAGNOSTIC_HORIZON_REACHED"
            else:
                raise RuntimeError("M q90 terminal history drift")
        else:
            raise RuntimeError("M q90 non-resource branch ledger drift")

    branch_summary = {
        "Q89_FAILURE_Q90_NOT_ATTEMPTED": (89, 88, False, False),
        "Q89_RESOURCE_ABORT_Q90_NOT_ATTEMPTED": (89, 88, False, False),
        "Q89_SUCCESS_Q90_FAILURE": (90, 89, True, False),
        "Q89_SUCCESS_Q90_RESOURCE_ABORT": (90, 89, True, False),
        "Q89_AND_Q90_SUCCESS_HORIZON_REACHED": (90, 90, True, True),
    }
    attempted, completed, horizon_attempted, horizon_reached = branch_summary[branch]
    expected_failure_sha = sha256(canonical_bytes(failure)) if failure is not None else None
    expected_top = {
        "screen_horizon_checkpoint_count": 90,
        "attempted_checkpoint_count": attempted,
        "completed_checkpoint_count": completed,
        "horizon_checkpoint_attempted": horizon_attempted,
        "horizon_reached_with_committed_checkpoint": horizon_reached,
        "screen_terminal_condition": terminal,
        "failure_checkpoint_included": failure is not None,
        "failure_record_sha256": expected_failure_sha,
        "last_committed_cumulative_drop_ticks": final_success["E_after_ticks"],
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
        "root_globals_unchanged": True,
    }
    for key, value in expected_top.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"M q90 terminal summary drift: {key}")
    if (
        result.get("records_sha256") != sha256(canonical_bytes(records))
        or result.get("selected_K_history_sha256") != sha256(canonical_bytes(history))
    ):
        raise RuntimeError("M q90 ledger digest drift")
    resource_source = abort if abort is not None else records[-1]
    observed = {
        "observed_peak_single_expansion_terms": resource_source["peak_live_terms_cumulative"],
        "observed_term_gate_visits_including_terminal_attempt": resource_source["term_gate_visits_cumulative"],
        "observed_maximum_expansion_coefficient_tick_bits": resource_source["maximum_expansion_coefficient_tick_bits"],
        "observed_maximum_product_bits": resource_source["maximum_product_bits"],
        "observed_rounding_cumulative_scaled_ticks_squared": resource_source["rounding_cumulative_scaled_ticks_squared"],
    }
    for key, value in observed.items():
        if not exact_value_equal(result.get(key), value):
            raise RuntimeError(f"M q90 observed resource drift: {key}")
    row_count = sum(len(record["candidate_records"]) for record in records)
    expected_counts = {
        "Q89_FAILURE_Q90_NOT_ATTEMPTED": (89, 88, 3_026),
        "Q89_RESOURCE_ABORT_Q90_NOT_ATTEMPTED": (88, 88, 2_992),
        "Q89_SUCCESS_Q90_FAILURE": (90, 89, 3_060),
        "Q89_SUCCESS_Q90_RESOURCE_ABORT": (89, 89, 3_026),
        "Q89_AND_Q90_SUCCESS_HORIZON_REACHED": (90, 90, 3_060),
    }
    if (len(records), len(history), row_count) != expected_counts[branch]:
        raise RuntimeError("M q90 branch ledger count drift")
    return {
        "validation_id": "M_k622592_c34_q90_post_replay_handoff_v1",
        "fresh_replay_checkpoint_range": [1, attempted],
        "q1_through_q88_records_exact": True,
        "q1_through_q88_selected_history_exact": True,
        "q1_through_q88_all_34_candidate_rows_exact": True,
        "q88_committed_state_exact": True,
        "q89_and_q90_outcomes_precommitted": False,
        "K607993_execution_row_constructed": False,
        "K607993_q89_q90_extrapolation_permitted": False,
        "legal_terminal_branches": list(branch_summary),
        "terminal_branch": branch,
        "resource_policy_abort_structured": abort is not None,
        "resource_policy_abort_checkpoint": (
            abort["checkpoint_number_one_based"] if abort is not None else None
        ),
        "resource_policy_abort_kind": abort["abort_kind"] if abort is not None else None,
        "resource_policy_abort_sha256": result.get("resource_policy_abort_sha256"),
        "record_count": len(records),
        "selected_history_count": len(history),
        "candidate_row_count": row_count,
    }


def execution_components(
    raw_components: Any,
    execution_parent: Any,
    self_sha: str,
    wrapper_sha: str,
) -> list[Dict[str, Any]]:
    if not exact_value_equal(raw_components, list(execution_parent.EXPECTED_PARENT_EXECUTION_COMPONENTS)):
        raise RuntimeError("M q90 raw component closure drift")
    components = [{
        "relative_path": SELF_NAME,
        "role": "M_k622592_c34_q90_fresh_same_byte_screen",
        "sha256": self_sha,
    }]
    saw_root = saw_v2 = False
    for original in raw_components:
        item = dict(original)
        path = item.get("relative_path")
        if path == CONTROL_FLOW_ROOT_NAME:
            item = {
                "relative_path": EXECUTION_PARENT_NAME,
                "role": "M_k622592_c34_q88_same_byte_private_execution_parent",
                "sha256": EXPECTED_EXECUTION_PARENT_SHA256,
            }
            saw_root = True
        elif path == V6_BASELINE_CONFIGURATION_NAME:
            item["role"] = "v6_baseline_configuration_before_q88_parent_override"
        elif path == V2_ARITHMETIC_NAME:
            item["role"] = "v2_arithmetic_bytes_beneath_k622592_c34_wrapper"
            saw_v2 = True
        components.append(item)
        if path == V2_ARITHMETIC_NAME:
            components.append({
                "relative_path": KERNEL_WRAPPER_NAME,
                "role": "M_k622592_c34_capability_override_provider",
                "sha256": wrapper_sha,
            })
    paths = [item["relative_path"] for item in components]
    if not saw_root or not saw_v2 or len(paths) != 11 or len(paths) != len(set(paths)):
        raise RuntimeError("M q90 final component closure drift")
    forbidden = {
        CONTROL_FLOW_ROOT_NAME, ROUTE_PREDECESSOR_TRANSCRIPT_NAME,
        "hubbard_l8_magnetization_adaptive_k_four_gate_k606208_c33_q88_screen.py",
        "hubbard_l8_magnetization_adaptive_k_four_gate_k606208_c33_q88_transcript.json",
    }
    if forbidden & set(paths):
        raise RuntimeError("M q90 reference-only source became a component")
    return components


def final_source_custody(
    raw_custody: Any,
    execution_parent: Any,
    self_sha: str,
    wrapper_sha: str,
) -> Dict[str, str]:
    if type(raw_custody) is not dict:
        raise RuntimeError("M q90 raw custody schema drift")
    expected_raw = dict(execution_parent.EXPECTED_PARENT_SOURCE_CUSTODY)
    if raw_custody != expected_raw:
        raise RuntimeError("M q90 raw custody drift")
    custody = {
        SELF_NAME: self_sha,
        EXECUTION_PARENT_NAME: EXPECTED_EXECUTION_PARENT_SHA256,
        KERNEL_WRAPPER_NAME: wrapper_sha,
        **raw_custody,
    }
    if len(custody) != 10 or CONTROL_FLOW_ROOT_NAME in custody:
        raise RuntimeError("M q90 final custody cardinality drift")
    if ROUTE_PREDECESSOR_TRANSCRIPT_NAME in custody:
        raise RuntimeError("M q88 canonical became source custody")
    return custody


def validate_and_relabel(
    result: Dict[str, Any],
    predecessor: Mapping[str, Any],
    route_reference: Mapping[str, Any],
    execution_parent: Any,
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q90 relabel requires fresh same-byte self execution")
    if (
        context.get("execution_parent_private_entrypoint_called") is not True
        or context.get("raw_replay_completed") is not True
        or context.get("q88_internal_c33_loader_suppressed") is not True
        or context.get("q88_internal_relabel_suppressed") is not True
        or context.get("execution_parent_abort_adapter_installed") is not True
    ):
        raise RuntimeError("M q90 execution-parent context drift")
    raw_horizon = context.get("raw_control_flow_horizon_override")
    if type(raw_horizon) is not dict or raw_horizon.get("semantic_delta") != {
        "MODE_CONFIG.magnetization.horizon_checkpoint_count": {
            "before": 80, "after": 90,
        }
    }:
        raise RuntimeError("M q90 nested raw horizon override drift")
    if (
        context.get("wrapper_sha") != EXPECTED_KERNEL_WRAPPER_SHA256
        or sha256(canonical_bytes(context.get("wrapper_manifest")))
        != EXPECTED_KERNEL_MANIFEST_SHA256
    ):
        raise RuntimeError("M q90 wrapper capture drift")
    handoff = validate_replay_handoff(result, predecessor)
    for key, digest_key in (
        ("screen_execution_components", "screen_execution_components_sha256"),
        ("configuration_reference", "configuration_reference_sha256"),
        ("checkpoint_transform", "checkpoint_transform_sha256"),
        ("resource_policy_abort", "resource_policy_abort_sha256"),
    ):
        _nested_digest_pair(result, key, digest_key)
    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(
        result["screen_execution_components"], execution_parent,
        self_sha, context["wrapper_sha"],
    )
    custody = final_source_custody(
        result["source_custody"], execution_parent,
        self_sha, context["wrapper_sha"],
    )
    configuration_reference = copy.deepcopy(predecessor["configuration_reference"])
    if (
        predecessor["configuration_reference_sha256"]
        != EXPECTED_ROUTE_CONFIGURATION_REFERENCE_SHA256
        or sha256(canonical_bytes(configuration_reference))
        != EXPECTED_ROUTE_CONFIGURATION_REFERENCE_SHA256
    ):
        raise RuntimeError("M q90 configuration-reference drift")
    configuration_override = {
        "override_id": "magnetization_k622592_c34_q90_configuration_override_v1",
        "candidate_policy_and_kernel_capability_unchanged_on_route": True,
        "effective_candidate_K_values": list(M_CANDIDATES),
        "effective_candidate_K_values_sha256": EXPECTED_CANDIDATE_SHA256,
        "effective_policy_caps": {**POLICY_CAPS_BASE, "max_candidate_count": 34},
        "incremental_route_override_from_k622592_c34_q88": {
            "candidate_K_values_changed": False,
            "candidate_count": {"before": 34, "after": 34},
            "candidate_ladder_added": [],
            "candidate_ladder_removed": [],
            "policy_cap_changes": {},
            "kernel_capability_limit_changes": {},
            "horizon_checkpoint_count": {"before": 88, "after": 90},
            "predecessor_configuration_override_sha256": (
                EXPECTED_ROUTE_CONFIGURATION_OVERRIDE_SHA256
            ),
        },
        "overridden_fields_on_incremental_route": ["screen_horizon_checkpoint_count"],
    }
    kernel_override = copy.deepcopy(predecessor["kernel_capability_override"])
    if (
        predecessor["kernel_capability_override_sha256"]
        != EXPECTED_ROUTE_KERNEL_OVERRIDE_SHA256
        or sha256(canonical_bytes(kernel_override)) != EXPECTED_ROUTE_KERNEL_OVERRIDE_SHA256
    ):
        raise RuntimeError("M q90 unchanged kernel override drift")
    parent_horizon_override = {
        "override_id": "magnetization_q88_parent_to_q90_horizon_override_v1",
        "execution_parent_relative_path": EXECUTION_PARENT_NAME,
        "execution_parent_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
        "execution_parent_source_bytes_changed": False,
        "execution_parent_module_isolated": True,
        "execution_parent_private_entrypoint_called": True,
        "changed_fields": ["screen_horizon_checkpoint_count"],
        "semantic_delta": {
            "screen_horizon_checkpoint_count": {"before": 88, "after": 90},
        },
        "raw_control_flow_horizon_override": copy.deepcopy(raw_horizon),
        "raw_control_flow_horizon_override_sha256": sha256(canonical_bytes(raw_horizon)),
        "temporary_parent_attribute_count": 8,
        "temporary_parent_attributes_restored_in_finally": True,
        "q88_internal_c33_loader_suppressed": True,
        "q88_internal_relabel_suppressed": True,
        "structured_abort_adapter_installed": True,
    }
    predecessor_transform = copy.deepcopy(predecessor["checkpoint_transform"])
    if (
        predecessor["checkpoint_transform_sha256"] != EXPECTED_ROUTE_TRANSFORM_SHA256
        or sha256(canonical_bytes(predecessor_transform)) != EXPECTED_ROUTE_TRANSFORM_SHA256
    ):
        raise RuntimeError("M q90 predecessor transform drift")
    transform = {
        "transform_id": "magnetization_four_gate_k622592_c34_q90_v1",
        "execution_parent_q88_transform": predecessor_transform,
        "execution_parent_q88_transform_sha256": EXPECTED_ROUTE_TRANSFORM_SHA256,
        "nested_raw_control_flow_horizon_override": copy.deepcopy(raw_horizon),
        "nested_raw_control_flow_horizon_override_sha256": sha256(canonical_bytes(raw_horizon)),
        "q88_execution_parent_replaces_raw_root_component_at_outer_boundary": True,
        "physical_gate_sequence_changed": False,
        "checkpoint_cadence_changed": False,
        "candidate_K_values_changed": False,
        "policy_caps_changed": False,
        "kernel_capability_limits_changed": False,
        "horizon_checkpoint_count": {"before": 88, "after": 90},
        "q89_and_q90_outcomes_precommitted": False,
        "overridden_semantics": ["screen_horizon_checkpoint_count"],
    }
    result.update({
        "transcript_fingerprint": (
            "hubbard_l8_magnetization_adaptive_k_four_gate_"
            "k622592_c34_q90_screen_v1"
        ),
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "control_flow_owned_by_screen": False,
        "control_flow_owned_by_verified_parent": True,
        "control_flow_parent_relative_path": EXECUTION_PARENT_NAME,
        "control_flow_parent_source_sha256": EXPECTED_EXECUTION_PARENT_SHA256,
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
        "kernel_capability_wrapper_source_sha256": context["wrapper_sha"],
        "kernel_capability_wrapper_compiled_from_verified_bytes": True,
        "kernel_capability_wrapper_module_isolated": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": configuration_reference,
        "configuration_reference_sha256": sha256(canonical_bytes(configuration_reference)),
        "configuration_override": configuration_override,
        "configuration_override_sha256": sha256(canonical_bytes(configuration_override)),
        "kernel_capability_override": kernel_override,
        "kernel_capability_override_sha256": sha256(canonical_bytes(kernel_override)),
        "parent_horizon_override": parent_horizon_override,
        "parent_horizon_override_sha256": sha256(canonical_bytes(parent_horizon_override)),
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
    require_exact_keys(result, EXPECTED_RELABELLED_RESULT_KEYS, "M q90 final result")
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
        _nested_digest_pair(result, value_key, digest_key)
    return result


def _run_verified(repo: Path) -> Dict[str, Any]:
    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("M q90 screen requires fresh same-byte self execution")
    validate_local_configuration()
    repo = repo.resolve()
    parent = load_execution_parent(repo)
    result, context = execute_parent_replay(parent, repo)
    predecessor, route_reference = load_route_reference(repo, parent)
    return validate_and_relabel(
        result, predecessor, route_reference, parent, context
    )


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_magnetization_k622592_c34_q90_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path) -> Dict[str, Any]:
    return fresh_self_module()._run_verified(repo)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("M q90 transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("M q90 transcript exceeds output byte cap")
    output = output.resolve()
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=output.parent, prefix=output.name + ".",
            suffix=".tmp", delete=False,
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
        "selected_K_history_sha256": result["selected_K_history_sha256"],
        "terminal_branch": result["predecessor_handoff_validation"]["terminal_branch"],
        "final_checkpoint": final["checkpoint_number_one_based"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_terminal_attempt"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
