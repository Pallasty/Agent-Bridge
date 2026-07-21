#!/usr/bin/env python3
"""Deterministic, non-authoritative four-gate granularity screen for L8."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple


SELF_NAME = "hubbard_l8_adaptive_k_four_gate_granularity_screen.py"
V2_HELPER_NAME = "hubbard_l8_adaptive_k_v2_design_probe.py"
V6_CONFIGURATION_NAME = "hubbard_l8_adaptive_k_v6_design_probe.py"
KERNEL_NAME = "hubbard_l8_adaptive_k_arithmetic_v2.py"
ROOT_NAME = "hubbard_l8_observable_interval_step_checker.py"

EXPECTED_V2_HELPER_SHA256 = (
    "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3"
)
EXPECTED_V6_CONFIGURATION_SHA256 = (
    "3e7f9ff0546addfaa23f351f3569b102d0c3ebb578dbc4873b042bac21070af2"
)
EXPECTED_KERNEL_SHA256 = (
    "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998"
)
EXPECTED_ROOT_SHA256 = (
    "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a"
)
EXPECTED_BACKPROP_GATE_RECORDS_SHA256 = (
    "8504eae718b7a670fa71b79c789691e70a59365f0876f8acfdd4ea8dceee2df5"
)
EXPECTED_V6_CANDIDATE_SHA256 = {
    "magnetization": (
        "44a7cf505d4d7db6ade441ee15f5b47aba18b45ce6f2a243042adcc155a418cc"
    ),
    "double_occupancy": (
        "df55613f1fbd691f42319976d4722e614b25a8c985cdae5df9797f2e49660160"
    ),
}
EXPECTED_V6_CAPS_SHA256 = (
    "32a0619246b07e67e6d4f237f808fc5c5163c1149c50230bf962ab1851a6f25a"
)

MAX_SELF_SOURCE_BYTES = 131_072
MAX_PINNED_SOURCE_BYTES = 262_144
MAX_BOUNDARY_ENCODED_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 4_194_304
_VERIFIED_SELF_SOURCE_BYTES = globals().get("_VERIFIED_SELF_SOURCE_BYTES")

BASELINE_GATES_PER_CHECKPOINT = 8
BASELINE_CHECKPOINTS_PER_MAPPED_STEP = 144
GATES_PER_CHECKPOINT = 4
CHECKPOINTS_PER_MAPPED_STEP = 288
EXPECTED_STAGE_COUNT = 9
EXPECTED_GATE_COUNT = 1_152
REMOVED_D_CANDIDATE_K = 491_520

EXPECTED_V6_CAPS = {
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

MODE_CONFIG = {
    "magnetization": {
        "horizon_checkpoint_count": 80,
        "output_name": (
            "hubbard_l8_magnetization_adaptive_k_"
            "four_gate_granularity_transcript.json"
        ),
    },
    "double_occupancy": {
        "horizon_checkpoint_count": 66,
        "output_name": (
            "hubbard_l8_double_occupancy_adaptive_k_"
            "four_gate_granularity_transcript.json"
        ),
    },
}

CHECKPOINT_TRANSFORM = {
    "transform_id": "l8_adaptive_k_8_gate_to_4_gate_granularity_screen_v1",
    "baseline_geometry": {
        "stage_count": EXPECTED_STAGE_COUNT,
        "gate_count": EXPECTED_GATE_COUNT,
        "gates_per_checkpoint": BASELINE_GATES_PER_CHECKPOINT,
        "checkpoints_per_mapped_step": BASELINE_CHECKPOINTS_PER_MAPPED_STEP,
    },
    "screen_geometry": {
        "stage_count": EXPECTED_STAGE_COUNT,
        "gate_count": EXPECTED_GATE_COUNT,
        "gates_per_checkpoint": GATES_PER_CHECKPOINT,
        "checkpoints_per_mapped_step": CHECKPOINTS_PER_MAPPED_STEP,
    },
    "budget_invariant": {
        "denominator_before": "remaining_mapped_steps_including_attempt*144",
        "denominator_after": "remaining_mapped_steps_including_attempt*288",
        "corresponding_boundary_relation": "screen_q=2*baseline_q",
        "mapped_step_total_budget_unchanged": True,
    },
    "control_flow_changes": [
        {
            "field": "sequence.checkpoint_count_divisor",
            "before": 8,
            "after": 4,
        },
        {
            "field": "sequence.gates_per_checkpoint",
            "before": 8,
            "after": 4,
        },
        {
            "field": "sequence.fixed_checkpoint_count",
            "before": 144,
            "after": 288,
        },
        {
            "field": "run.future_checkpoint_denominator_multiplier",
            "before": 144,
            "after": 288,
        },
        {"field": "run.batch_loop_stride", "before": 8, "after": 4},
        {"field": "run.batch_slice_width", "before": 8, "after": 4},
        {"field": "run.batch_length_requirement", "before": 8, "after": 4},
        {"field": "record.batch_in_stage_divisor", "before": 8, "after": 4},
        {
            "field": "record.gate_occurrence_last_offset",
            "before": 7,
            "after": 3,
        },
        {"field": "run.gate_index_increment", "before": 8, "after": 4},
        {
            "field": "transcript.prefix_cap_formula_multiplier",
            "before": 144,
            "after": 288,
        },
        {
            "field": "run.selection_frequency",
            "before": "once_after_8_gates",
            "after": "once_after_4_gates",
        },
        {
            "field": "run.commit_frequency",
            "before": "once_after_8_gates",
            "after": "once_after_4_gates",
        },
        {
            "field": "run.horizon",
            "before": "until_terminal_condition",
            "after": "bounded_mode_specific_checkpoint_horizon",
        },
    ],
    "unchanged_semantics": [
        "boundary_state",
        "backprop_gate_order",
        "fixed_tick_interval_arithmetic",
        "ranked_suffix_order",
        "first_feasible_candidate_selection",
        "candidate_commit",
        "v6_candidate_values",
        "v6_resource_caps",
    ],
}


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


def bounded_source_bytes(path: Path, maximum: int) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise RuntimeError(f"source byte cap exceeded: {path.name}")
    return payload


def checked_repo_file(repo: Path, relative_path: str) -> Path:
    if type(relative_path) is not str or not relative_path:
        raise RuntimeError("source relative path is not a nonempty string")
    candidate = (repo / relative_path).resolve()
    try:
        candidate.relative_to(repo)
    except ValueError as exc:
        raise RuntimeError("source path escapes the repository") from exc
    return candidate


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
    payload = bounded_source_bytes(path, MAX_PINNED_SOURCE_BYTES)
    observed = sha256(payload)
    if observed != expected_sha:
        raise RuntimeError(f"source pin drift for {relative_path}: {observed}")
    return compile_isolated(module_name, path, payload), payload


def load_v2_helper(repo: Path) -> Any:
    helper, _payload = load_pinned_module(
        repo,
        V2_HELPER_NAME,
        EXPECTED_V2_HELPER_SHA256,
        "pinned_hubbard_l8_adaptive_k_v2_helper_for_four_gate_screen",
    )
    if helper.KERNEL_NAME != KERNEL_NAME:
        raise RuntimeError("v2 helper kernel path drift")
    if helper.ROOT_NAME != ROOT_NAME:
        raise RuntimeError("v2 helper root path drift")
    if helper.EXPECTED_KERNEL_SHA256 != EXPECTED_KERNEL_SHA256:
        raise RuntimeError("v2 helper kernel pin drift")
    if helper.EXPECTED_ROOT_SHA256 != EXPECTED_ROOT_SHA256:
        raise RuntimeError("v2 helper root pin drift")
    return helper


def load_v6_configuration(repo: Path) -> Any:
    configuration, _payload = load_pinned_module(
        repo,
        V6_CONFIGURATION_NAME,
        EXPECTED_V6_CONFIGURATION_SHA256,
        "pinned_hubbard_l8_adaptive_k_v6_configuration_only",
    )
    if configuration.POLICY_CAPS_BASE != EXPECTED_V6_CAPS:
        raise RuntimeError("v6 configuration resource caps drift")
    if sha256(canonical_bytes(configuration.POLICY_CAPS_BASE)) != (
        EXPECTED_V6_CAPS_SHA256
    ):
        raise RuntimeError("v6 configuration resource cap digest drift")
    for mode in MODE_CONFIG:
        candidates = configuration.MODE_CONFIG[mode]["candidates"]
        if type(candidates) is not tuple:
            raise RuntimeError(f"v6 candidate ladder type drift: {mode}")
        if sha256(canonical_bytes(list(candidates))) != (
            EXPECTED_V6_CANDIDATE_SHA256[mode]
        ):
            raise RuntimeError(f"v6 candidate ladder digest drift: {mode}")
        if any(type(value) is not int or value <= 0 for value in candidates):
            raise RuntimeError(f"v6 candidate ladder value drift: {mode}")
        if any(left >= right for left, right in zip(candidates, candidates[1:])):
            raise RuntimeError(f"v6 candidate ladder order drift: {mode}")
        if candidates[-1] != 524_288:
            raise RuntimeError(f"v6 candidate ladder maximum drift: {mode}")
    if len(configuration.MODE_CONFIG["magnetization"]["candidates"]) != 29:
        raise RuntimeError("v6 magnetization candidate count drift")
    double_candidates = configuration.MODE_CONFIG["double_occupancy"]["candidates"]
    if len(double_candidates) != 32:
        raise RuntimeError("v6 double-occupancy candidate count drift")
    if REMOVED_D_CANDIDATE_K in double_candidates:
        raise RuntimeError("v6 double-occupancy ladder unexpectedly contains 491520")
    return configuration


def load_execution_sources(
    repo: Path,
    helper: Any,
    mode: str,
) -> Tuple[Any, Any, Dict[str, Any], Dict[str, str]]:
    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    helper_config = helper.CONFIG[mode]
    pins = {
        KERNEL_NAME: EXPECTED_KERNEL_SHA256,
        ROOT_NAME: EXPECTED_ROOT_SHA256,
        **helper_config["parent_sources"],
    }
    payloads: Dict[str, bytes] = {}
    source_custody: Dict[str, str] = {}
    for relative_path, expected in pins.items():
        path = checked_repo_file(repo, relative_path)
        payload = bounded_source_bytes(path, MAX_PINNED_SOURCE_BYTES)
        observed = sha256(payload)
        if observed != expected:
            raise RuntimeError(f"dependency source pin drift for {relative_path}: {observed}")
        payloads[relative_path] = payload
        source_custody[relative_path] = observed

    kernel = compile_isolated(
        "pinned_four_gate_screen_kernel",
        checked_repo_file(repo, KERNEL_NAME),
        payloads[KERNEL_NAME],
    )
    root = compile_isolated(
        "pinned_four_gate_screen_root",
        checked_repo_file(repo, ROOT_NAME),
        payloads[ROOT_NAME],
    )
    modules = {
        relative_path: compile_isolated(
            "pinned_four_gate_screen_" + relative_path.replace(".", "_"),
            checked_repo_file(repo, relative_path),
            payload,
        )
        for relative_path, payload in payloads.items()
        if relative_path in helper_config["parent_sources"]
        and relative_path.endswith(".py")
    }
    return kernel, root, modules, source_custody


class FrozenBoundaryPath:
    """Expose one already-bounded boundary payload to the exact v2 loader."""

    def __init__(self, payload: bytes) -> None:
        if type(payload) is not bytes:
            raise RuntimeError("frozen boundary payload must be exact bytes")
        self._payload = payload

    def read_bytes(self) -> bytes:
        return self._payload


class FrozenBoundaryRepo:
    """Reject every v2 boundary read except the single verified relative path."""

    def __init__(self, relative_path: str, payload: bytes) -> None:
        self._relative_path = relative_path
        self._path = FrozenBoundaryPath(payload)

    def __truediv__(self, relative_path: str) -> FrozenBoundaryPath:
        if relative_path != self._relative_path:
            raise RuntimeError("exact v2 helper requested an unverified boundary path")
        return self._path


def load_exact_boundary(
    repo: Path,
    helper: Any,
    mode: str,
    modules: Mapping[str, Any],
    kernel: Any,
    root: Any,
) -> Tuple[Dict[Any, Any], Mapping[str, Any], Dict[str, Any]]:
    spec = helper.boundary_spec(mode, modules)
    boundary_path = checked_repo_file(repo, spec["relative_path"])
    encoded = bounded_source_bytes(boundary_path, MAX_BOUNDARY_ENCODED_BYTES)
    if sha256(encoded) != spec["encoded_sha256"]:
        raise RuntimeError("bounded boundary source pin drift")
    frozen_repo = FrozenBoundaryRepo(spec["relative_path"], encoded)
    expansion, state, custody = helper.load_boundary(
        frozen_repo,
        mode,
        modules,
        kernel,
        root,
    )
    if custody["relative_path"] != spec["relative_path"]:
        raise RuntimeError("boundary custody path drift")
    if custody["encoded_sha256"] != sha256(encoded):
        raise RuntimeError("boundary custody digest drift")
    return expansion, state, custody


def build_four_gate_sequence(
    helper: Any,
    root: Any,
    kernel: Any,
) -> Tuple[Any, Any, Dict[str, Any], Dict[str, Any]]:
    stages, trig, baseline = helper.build_sequence(root, kernel)
    if baseline != {
        **baseline,
        "stage_count": EXPECTED_STAGE_COUNT,
        "gate_count": EXPECTED_GATE_COUNT,
        "checkpoint_count": BASELINE_CHECKPOINTS_PER_MAPPED_STEP,
        "gates_per_checkpoint": BASELINE_GATES_PER_CHECKPOINT,
        "backprop_gate_records_sha256": EXPECTED_BACKPROP_GATE_RECORDS_SHA256,
    }:
        raise RuntimeError("baseline sequence geometry drift")
    for stage in stages:
        if len(stage["gates"]) % GATES_PER_CHECKPOINT:
            raise RuntimeError("stage is not divisible into four-gate checkpoints")
    checkpoint_count = sum(
        len(stage["gates"]) // GATES_PER_CHECKPOINT for stage in stages
    )
    if checkpoint_count != CHECKPOINTS_PER_MAPPED_STEP:
        raise RuntimeError("four-gate checkpoint geometry drift")
    sequence = {
        **baseline,
        "checkpoint_count": checkpoint_count,
        "gates_per_checkpoint": GATES_PER_CHECKPOINT,
        "baseline_checkpoint_count": BASELINE_CHECKPOINTS_PER_MAPPED_STEP,
        "baseline_gates_per_checkpoint": BASELINE_GATES_PER_CHECKPOINT,
    }
    transform = {
        **CHECKPOINT_TRANSFORM,
        "baseline_sequence_sha256": sha256(canonical_bytes(baseline)),
        "screen_sequence_sha256": sha256(canonical_bytes(sequence)),
        "backprop_gate_records_sha256": baseline[
            "backprop_gate_records_sha256"
        ],
    }
    return stages, trig, sequence, transform


def execution_components(
    mode: str,
    self_sha: str,
    source_custody: Mapping[str, str],
    boundary_custody: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    components: list[Dict[str, Any]] = [
        {
            "relative_path": SELF_NAME,
            "role": "four_gate_screen_execution_source",
            "sha256": self_sha,
        },
        {
            "relative_path": V2_HELPER_NAME,
            "role": "v2_helper_provider_not_run_entrypoint",
            "sha256": EXPECTED_V2_HELPER_SHA256,
        },
        {
            "relative_path": V6_CONFIGURATION_NAME,
            "role": "v6_candidates_and_caps_reference_only",
            "sha256": EXPECTED_V6_CONFIGURATION_SHA256,
        },
    ]
    helper_sources = [KERNEL_NAME, ROOT_NAME]
    helper_sources.extend(
        sorted(name for name in source_custody if name not in helper_sources)
    )
    roles = {
        KERNEL_NAME: "v2_arithmetic_kernel",
        ROOT_NAME: "root_sequence_and_trigonometry_source",
    }
    for relative_path in helper_sources:
        components.append({
            "relative_path": relative_path,
            "role": roles.get(relative_path, f"{mode}_boundary_parent_source"),
            "sha256": source_custody[relative_path],
        })
    components.append({
        "relative_path": boundary_custody["relative_path"],
        "role": f"{mode}_encoded_input_boundary",
        "sha256": boundary_custody["encoded_sha256"],
    })
    return components


def removed_candidate_counterfactual(
    pretruncation_count: int,
    suffix: Sequence[int],
    cumulative: int,
    prefix_cap: int,
    selected_K: int | None,
) -> Dict[str, Any]:
    effective = min(REMOVED_D_CANDIDATE_K, pretruncation_count)
    drop = suffix[effective]
    feasible = cumulative + drop <= prefix_cap
    would_precede = (
        selected_K is not None
        and feasible
        and REMOVED_D_CANDIDATE_K < selected_K
    )
    return {
        "configured_K": REMOVED_D_CANDIDATE_K,
        "effective_retained_count": effective,
        "dropped_term_count": pretruncation_count - effective,
        "drop_ticks": str(drop),
        "E_after_if_selected_ticks": str(cumulative + drop),
        "feasible_under_current_prefix_cap": feasible,
        "actual_selected_K": selected_K,
        "would_precede_selected": would_precede,
        "would_be_selected_if_inserted": (
            feasible
            and (selected_K is None or REMOVED_D_CANDIDATE_K < selected_K)
        ),
    }


def run_four_gate(repo: Path, mode: str) -> Dict[str, Any]:
    """Execute the independent four-gate screen from exact pinned components."""

    if type(_VERIFIED_SELF_SOURCE_BYTES) is not bytes:
        raise RuntimeError("four-gate screen requires fresh same-byte self execution")
    if mode not in MODE_CONFIG:
        raise RuntimeError(f"unknown mode: {mode}")
    repo = repo.resolve()
    helper = load_v2_helper(repo)
    v6_configuration = load_v6_configuration(repo)
    kernel, root, modules, source_custody = load_execution_sources(
        repo,
        helper,
        mode,
    )
    root_before = kernel.root_global_snapshot(root)
    expansion, _state, boundary_custody = load_exact_boundary(
        repo,
        helper,
        mode,
        modules,
        kernel,
        root,
    )
    stages, trig, sequence, transform = build_four_gate_sequence(
        helper,
        root,
        kernel,
    )

    helper_config = helper.CONFIG[mode]
    candidates = tuple(v6_configuration.MODE_CONFIG[mode]["candidates"])
    caps = dict(v6_configuration.POLICY_CAPS_BASE)
    caps["max_candidate_count"] = len(candidates)
    helper.enforce_policy_caps(
        kernel,
        kernel.PropagationCounterV2(),
        len(expansion),
        caps,
    )
    counter = kernel.PropagationCounterV2()
    counter.observe(expansion)
    for interval in expansion.values():
        counter.observe_interval(interval)

    E_input = helper_config["input_cumulative_drop_ticks"]
    cumulative = E_input
    remaining_steps = 100 - helper_config["input_step_index"]
    denominator = remaining_steps * CHECKPOINTS_PER_MAPPED_STEP
    horizon = MODE_CONFIG[mode]["horizon_checkpoint_count"]
    if horizon <= 0 or horizon > sequence["checkpoint_count"]:
        raise RuntimeError("screen horizon is outside the fixed sequence")

    records = []
    selected_history = []
    failure = None
    horizon_reached = False
    gate_index = 0
    for stage_index, stage in enumerate(stages):
        for batch_start in range(
            0,
            len(stage["gates"]),
            GATES_PER_CHECKPOINT,
        ):
            checkpoint_index = len(records)
            checkpoint_number = checkpoint_index + 1
            if checkpoint_number > horizon:
                raise RuntimeError("screen attempted to pass its fixed horizon")
            batch = stage["gates"][
                batch_start:batch_start + GATES_PER_CHECKPOINT
            ]
            if len(batch) != GATES_PER_CHECKPOINT:
                raise RuntimeError("partial four-gate checkpoint batch")

            input_count = len(expansion)
            input_sha = kernel.tick_digest(expansion)
            visits_before = counter.term_gate_visits
            rounding_before = (
                counter.multiplication_rounding_l1_scaled_ticks_squared
            )
            expansion = kernel.propagate_batch(expansion, batch, trig, counter)
            pre_count = len(expansion)
            helper.enforce_policy_caps(kernel, counter, pre_count, caps)
            pre_sha = kernel.tick_digest(expansion)
            ranked, suffix = kernel.rank_with_suffix(expansion)
            prefix_cap = (
                E_input
                + checkpoint_number * (helper.MAXIMUM_DROP_TICKS - E_input)
                // denominator
            )
            slack = prefix_cap - cumulative
            candidate_records, selected_index = kernel.evaluate_candidates(
                pre_count,
                suffix,
                candidates,
                cumulative,
                prefix_cap,
            )
            selected_K_if_any = (
                candidate_records[selected_index]["configured_K"]
                if selected_index is not None
                else None
            )
            base = {
                "checkpoint_index_zero_based": checkpoint_index,
                "checkpoint_number_one_based": checkpoint_number,
                "stage_index": stage_index,
                "stage_group": stage["group"],
                "batch_in_stage": batch_start // GATES_PER_CHECKPOINT,
                "gate_occurrence_first_zero_based": gate_index,
                "gate_occurrence_last_zero_based": gate_index + len(batch) - 1,
                "gate_batch_sha256": helper.gate_batch_sha256(batch),
                "input_expansion_count": input_count,
                "input_expansion_sha256": input_sha,
                "pretruncation_expansion_count": pre_count,
                "pretruncation_expansion_sha256": pre_sha,
                "ranked_suffix_sha256": helper.ranked_suffix_sha256(
                    expansion,
                    ranked,
                    suffix,
                ),
                "budget_prefix_cap_ticks": str(prefix_cap),
                "E_before_ticks": str(cumulative),
                "prefix_slack_before_selection_ticks": str(slack),
                "candidate_records": candidate_records,
                "peak_live_terms_this_checkpoint": counter.window_peak_live_terms,
                "peak_live_terms_cumulative": counter.peak_live_terms,
                "term_gate_visits_increment": counter.term_gate_visits - visits_before,
                "term_gate_visits_cumulative": counter.term_gate_visits,
                "rounding_increment_scaled_ticks_squared": str(
                    counter.multiplication_rounding_l1_scaled_ticks_squared
                    - rounding_before
                ),
                "rounding_cumulative_scaled_ticks_squared": str(
                    counter.multiplication_rounding_l1_scaled_ticks_squared
                ),
                "maximum_expansion_coefficient_tick_bits": (
                    counter.maximum_expansion_coefficient_tick_bits
                ),
                "maximum_product_bits": counter.maximum_product_bits,
            }
            if mode == "double_occupancy":
                base["removed_491520_counterfactual"] = (
                    removed_candidate_counterfactual(
                        pre_count,
                        suffix,
                        cumulative,
                        prefix_cap,
                        selected_K_if_any,
                    )
                )
            gate_index += len(batch)

            if selected_index is None:
                minimum_K = helper.minimum_effective_k(suffix, slack)
                failure = {
                    **base,
                    "status": "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE",
                    "selected_candidate_index": None,
                    "selected_K": None,
                    "minimum_effective_K_to_meet_prefix": minimum_K,
                    "required_K_excess_over_policy_maximum": max(
                        0,
                        minimum_K - candidates[-1],
                    ),
                    "maximum_candidate_drop_excess_over_slack_ticks": str(
                        int(candidate_records[-1]["drop_ticks"]) - slack
                    ),
                }
                records.append(failure)
                break

            retained, truncation = kernel.commit_candidate(
                expansion,
                ranked,
                suffix,
                candidates,
                cumulative,
                prefix_cap,
                selected_index,
            )
            selected_K = candidate_records[selected_index]["configured_K"]
            drop = truncation["dropped_l1_ticks"]
            record = {
                **base,
                "status": "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED",
                "selected_candidate_index": selected_index,
                "selected_K": selected_K,
                "selected_effective_retained_count": truncation[
                    "effective_retained_count"
                ],
                "selected_dropped_term_count": truncation["dropped_term_count"],
                "selected_drop_ticks": str(drop),
                "selected_dropped_terms_sha256": truncation[
                    "dropped_terms_sha256"
                ],
                "retained_expansion_count": len(retained),
                "retained_expansion_sha256": truncation[
                    "retained_expansion_sha256"
                ],
                "minimum_retained_abs_upper_ticks": str(
                    truncation["minimum_retained_abs_upper_ticks"]
                ),
                "maximum_dropped_abs_upper_ticks": str(
                    truncation["maximum_dropped_abs_upper_ticks"]
                ),
                "E_after_ticks": str(cumulative + drop),
            }
            records.append(record)
            selected_history.append(selected_K)
            cumulative += drop
            expansion = retained
            if checkpoint_number == horizon:
                horizon_reached = True
                break
        if failure is not None or horizon_reached:
            break

    if failure is None and not horizon_reached:
        raise RuntimeError("screen ended without a declared terminal condition")
    root_after = kernel.root_global_snapshot(root)
    if root_before != root_after:
        raise RuntimeError("root arithmetic globals changed")

    self_sha = sha256(_VERIFIED_SELF_SOURCE_BYTES)
    components = execution_components(
        mode,
        self_sha,
        source_custody,
        boundary_custody,
    )
    candidate_sha = sha256(canonical_bytes(list(candidates)))
    selected_history_sha = kernel.canonical_sha256(selected_history)
    records_sha = kernel.canonical_sha256(records)
    terminal_condition = (
        "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        if failure is not None
        else "DIAGNOSTIC_HORIZON_REACHED"
    )
    configuration_reference = {
        "relative_path": V6_CONFIGURATION_NAME,
        "source_sha256": EXPECTED_V6_CONFIGURATION_SHA256,
        "role": "candidates_and_caps_reference_only",
        "fields_adopted": [
            f"MODE_CONFIG.{mode}.candidates",
            "POLICY_CAPS_BASE",
        ],
        "candidate_K_values_sha256": candidate_sha,
        "policy_caps_base_sha256": EXPECTED_V6_CAPS_SHA256,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
    }
    transcript = {
        "schema_version": 1,
        "transcript_fingerprint": (
            "hubbard_l8_adaptive_k_four_gate_granularity_screen_v1"
        ),
        "status": "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS",
        "screen_terminal_condition": terminal_condition,
        "observable_id": helper_config["observable_id"],
        "input_step_index": helper_config["input_step_index"],
        "attempted_child_step_index": helper_config["child_step_index"],
        "screen_source_sha256": self_sha,
        "same_byte_self_execution": True,
        "v2_helper_source_sha256": EXPECTED_V2_HELPER_SHA256,
        "v2_helper_compiled_from_verified_bytes": True,
        "v2_helper_module_isolated": True,
        "v2_run_entrypoint_called": False,
        "v6_configuration_source_sha256": EXPECTED_V6_CONFIGURATION_SHA256,
        "v6_configuration_compiled_from_verified_bytes": True,
        "v6_configuration_module_isolated": True,
        "v6_execution_invoked": False,
        "v6_same_byte_execution_parent": False,
        "control_flow_owned_by_screen": True,
        "screen_execution_components": components,
        "screen_execution_components_sha256": sha256(canonical_bytes(components)),
        "configuration_reference": configuration_reference,
        "configuration_reference_sha256": sha256(
            canonical_bytes(configuration_reference)
        ),
        "checkpoint_transform": transform,
        "checkpoint_transform_sha256": sha256(canonical_bytes(transform)),
        "arithmetic_kernel_commit": helper.KERNEL_COMMIT,
        "source_custody": {
            V2_HELPER_NAME: EXPECTED_V2_HELPER_SHA256,
            V6_CONFIGURATION_NAME: EXPECTED_V6_CONFIGURATION_SHA256,
            **source_custody,
        },
        "parent_expected_witness_sha256": helper_config[
            "parent_expected_witness_sha256"
        ],
        "input_boundary_custody": boundary_custody,
        "input_cumulative_drop_ticks": str(E_input),
        "maximum_cumulative_drop_ticks": str(helper.MAXIMUM_DROP_TICKS),
        "remaining_mapped_steps_including_attempt": remaining_steps,
        "future_checkpoint_denominator": denominator,
        "prefix_cap_formula": (
            f"E{helper_config['input_step_index']}+floor(q*(B-"
            f"E{helper_config['input_step_index']})/({remaining_steps}*"
            f"{CHECKPOINTS_PER_MAPPED_STEP}))"
        ),
        "candidate_K_values": list(candidates),
        "candidate_K_values_sha256": candidate_sha,
        "candidate_policy_precommitted_at_probe_time": False,
        "selection_rule": (
            "first_candidate_whose_exact_ranked_suffix_drop_respects_"
            "current_prefix_cap"
        ),
        "single_propagation_and_single_ranking_per_checkpoint": True,
        "sequence": sequence,
        "screen_horizon_checkpoint_count": horizon,
        "horizon_checkpoint_attempted": len(records) >= horizon,
        "horizon_reached_with_committed_checkpoint": horizon_reached,
        "kernel_capability_limits": dict(kernel.RESOURCE_LIMITS),
        "proposed_policy_caps": caps,
        "root_globals_before": root_before,
        "root_globals_after": root_after,
        "root_globals_unchanged": True,
        "attempted_checkpoint_count": len(records),
        "completed_checkpoint_count": len(records) - (1 if failure is not None else 0),
        "failure_checkpoint_included": failure is not None,
        "selected_K_history": selected_history,
        "selected_K_history_sha256": selected_history_sha,
        "records": records,
        "records_sha256": records_sha,
        "failure_record_sha256": (
            kernel.canonical_sha256(failure) if failure is not None else None
        ),
        "last_committed_cumulative_drop_ticks": str(cumulative),
        "observed_peak_single_expansion_terms": counter.peak_live_terms,
        "observed_term_gate_visits_including_terminal_attempt": (
            counter.term_gate_visits
        ),
        "observed_maximum_expansion_coefficient_tick_bits": (
            counter.maximum_expansion_coefficient_tick_bits
        ),
        "observed_maximum_product_bits": counter.maximum_product_bits,
        "observed_rounding_cumulative_scaled_ticks_squared": str(
            counter.multiplication_rounding_l1_scaled_ticks_squared
        ),
        "child_boundary_committed": False,
        "positive_artifact_generated": False,
        "runtime_RSS_host_timestamp_and_float_fields_excluded": True,
    }
    return transcript


def _run_verified(repo: Path, mode: str) -> Dict[str, Any]:
    """Private same-byte entry point for the independent screen."""

    return run_four_gate(repo, mode)


def fresh_self_module() -> Any:
    path = Path(__file__).resolve()
    payload = bounded_source_bytes(path, MAX_SELF_SOURCE_BYTES)
    module = types.ModuleType("verified_hubbard_l8_four_gate_granularity_screen")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    return module


def run(repo: Path, mode: str) -> Dict[str, Any]:
    """Public fresh-self entry point for one four-gate screen."""

    return fresh_self_module()._run_verified(repo, mode)


def write_atomic_bounded(output: Path, raw: bytes) -> None:
    if type(raw) is not bytes:
        raise RuntimeError("transcript payload must be exact bytes")
    if len(raw) > MAX_OUTPUT_BYTES:
        raise RuntimeError("screen transcript exceeds output byte cap")
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
    parser.add_argument("mode", choices=tuple(MODE_CONFIG))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    args = parser.parse_args()
    result = run(args.repo, args.mode)
    raw = canonical_bytes(result)
    output = args.output_dir / MODE_CONFIG[args.mode]["output_name"]
    write_atomic_bounded(output, raw)
    final_record = result["records"][-1] if result["records"] else None
    print(json.dumps({
        "output": output.name,
        "semantic_and_file_sha256": sha256(raw),
        "records_sha256": result["records_sha256"],
        "screen_terminal_condition": result["screen_terminal_condition"],
        "completed_checkpoint_count": result["completed_checkpoint_count"],
        "attempted_checkpoint_count": result["attempted_checkpoint_count"],
        "selected_K_history": result["selected_K_history"],
        "final_status": final_record["status"] if final_record else None,
        "final_checkpoint": (
            final_record.get("checkpoint_number_one_based") if final_record else None
        ),
        "last_committed_cumulative_drop_ticks": (
            result["last_committed_cumulative_drop_ticks"]
        ),
        "peak": result["observed_peak_single_expansion_terms"],
        "visits": result["observed_term_gate_visits_including_terminal_attempt"],
    }, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
