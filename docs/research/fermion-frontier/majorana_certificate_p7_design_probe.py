#!/usr/bin/env python3
"""Run and verify the non-authoritative Majorana P7 D0 resource probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping, Sequence
import uuid


BASE = Path(__file__).resolve().parent
POLICY_NAME = "majorana_certificate_p7_design_probe_policy.json"
FIXTURE_NAME = "majorana_certificate_p7_design_probe_fixture.json"
REPORT_NAME = "majorana_certificate_p7_design_probe_report.json"
RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"
RUNTIME_LOCK_ID = "MAJORANA-P0-JULIA-1.11.9-LINUX-X86_64-V1"
RUNTIME_LOCK_SHA256 = (
    "d54b68d9960cc9912f09a8a20b337804e198c61d5c68852db985cc4b537a1e17"
)
JULIA_EXECUTABLE_SHA256 = (
    "2976d17aba35be5d546e8e315e521bd9be3e58c2e64abfd588f186696e807b7d"
)
MAJORANA_SOURCE_TREE_CLOSURE = {
    "file_count": 42,
    "total_bytes": 1875632,
    "closure_sha256": (
        "744e743d88d7bc62da1ba11cef02909539de626bd4b0a5533b0b65d8aae309b5"
    ),
}
PAULI_SOURCE_TREE_CLOSURE = {
    "file_count": 119,
    "total_bytes": 7736347,
    "closure_sha256": (
        "ce1e6cac1b09573962136fce0f315fabbf8556c9075c4aa3545c41c6ee4c3783"
    ),
}
FINALIZER_PRIVACY = {
    "complete_formal_finalizer_execution_role": (
        "future_S0_resource_path_equivalence_only"
    ),
    "complete_formal_finalizer_has_scientific_authority": False,
    "transient_private_values": [
        "term_digest", "checkerboard_Neel_value", "exact_center",
        "declared_interval", "operator_error_ticks",
    ],
    "D0_driver_reads_transient_private_values": False,
    "D0_driver_serializes_transient_private_values": False,
    "D0_driver_compares_transient_private_values": False,
    "only_public_finalizer_resource_fields": [
        "final_retained_term_count",
        "P2_resource_counters.final_evaluation_term_visits",
    ],
    "public_finalizer_fields_are_resource_counts_only": True,
    "public_finalizer_fields_do_not_form_a_scientific_assessment_or_expand_"
    "authority": True,
}
CHECKERBOARD_NEEL_SCOPE = (
    "TRANSIENTLY_COMPUTED_AND_INTERNAL_CONSISTENCY_CHECKED_BY_THE_FROZEN_"
    "FINALIZER_FOR_FUTURE_S0_RESOURCE_PATH_EQUIVALENCE_BUT_NEVER_EXPORTED_"
    "DECODED_COMPARED_OR_USED_AS_D0_EVIDENCE"
)
INVALID_D0_PROBE_EXIT_CODE = 66
JULIA_RUNTIME_FAILURE_EXIT_CODE = 70
PROBE_DRIVER = (
    "majorana_certificate_p7_design_probe/"
    "majorana_p7_step3_resource_probe.jl"
)
P6_RUNNER = "majorana_certificate_p6/majorana_p6_runner.jl"
STAGED_PATHS = (
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p4/majorana_p4_runner.jl",
    P6_RUNNER,
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3_fixture.json",
    "majorana_certificate_p4_fixture.json",
    "majorana_certificate_p5_fixture.json",
    "majorana_certificate_p6_fixture.json",
    FIXTURE_NAME,
    PROBE_DRIVER,
)
PREPROBE_CHANGED_PATHS = frozenset({
    f"docs/research/fermion-frontier/{POLICY_NAME}",
    f"docs/research/fermion-frontier/{FIXTURE_NAME}",
    f"docs/research/fermion-frontier/{Path(__file__).name}",
    f"docs/research/fermion-frontier/{PROBE_DRIVER}",
    "docs/research/fermion-frontier/test_majorana_certificate_p7_design_probe.py",
})
RESULT_ARTIFACTS = (
    REPORT_NAME,
    "majorana_certificate_p7_fixture.json",
    "majorana_certificate_p7_policy.json",
    "majorana_certificate_p7_precommit_contract.json",
    "majorana_certificate_p7_contract.json",
    "majorana_certificate_p7_certificate.json",
    "test_majorana_certificate_p7_result.py",
)

POLICY_ID = "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D0-V1"
POLICY_SEMANTIC_SHA256 = (
    "0a7db26fed1d6f66aca0641fa1c09676038749529b1aac691b3001c544a147c9"
)
FIXTURE_ID = "MAJORANA-P7-STEP3-E768-MAX-LAZY37-D0-V1"
REPORT_TYPE = "majorana_p7_step3_e768_max_lazy37_resource_report_d0_v1"
PROBE_TYPE = "majorana_p7_step3_e768_max_lazy37_resource_probe_d0_v1"
DIRECT_PARENT = "254f893dc5e40c27f6c4fb17dfd1c07ab749c2e4"
PROBE_MODE = "E768_MAX_LAZY37_STEP3_V1"
CANDIDATE_ID = "E768-MAX-LAZY37-STEP3-V1"
MODE_ORDER = (PROBE_MODE,)

P2_COUNTER_KEYS = {
    "cap_scan_term_visits", "propagation_term_visits",
    "truncation_term_visits", "final_evaluation_term_visits",
    "total_charged_term_visits",
}
ACCURACY_COUNTER_KEYS = {
    "product_defect_event_count", "merge_defect_event_count",
    "drop_defect_event_count", "anticommuting_event_count",
    "accuracy_charged_event_count",
}
RESOURCE_SUMMARY_KEYS = {
    "completed_composite_count", "completed_constituent_count",
    "completed_truncation_boundary_count",
    "peak_premerge_contribution_count", "peak_postmerge_unique_term_count",
    "anticommuting_split_count", "threshold_dropped_term_count",
    "exact_zero_dropped_term_count", "P2_resource_counters",
    "accuracy_event_counters", "total_P2_plus_accuracy_charged_event_count",
    "final_retained_term_count", "cap_event",
}
SELECTION_RESOURCE_KEYS = {
    "total_ranking_scan_term_visits", "total_sort_work_items",
    "total_tick_evaluations", "total_selected_membership_insertions",
    "peak_ranking_buffer_terms", "total_selection_work_units",
    "completed_selection_boundary_count",
}
CAP_CONTEXT_KEYS = {
    "stage_index", "group", "composite_index", "constituent_index",
    "boundary_index", "mapped_step_index", "operation",
}
CAP_EVENT_NAMES = frozenset({
    "cap_scan_term_visits",
    "final_evaluation_term_visits",
    "maximum_BigInt_bit_length",
    "maximum_accuracy_charged_events",
    "maximum_anticommuting_events",
    "maximum_boundary_retained_terms",
    "maximum_cap_scan_term_visits",
    "maximum_current_terms_before_constituent",
    "maximum_drop_defect_events",
    "maximum_final_evaluation_term_visits",
    "maximum_merge_defect_events",
    "maximum_peak_ranking_buffer_terms",
    "maximum_premerge_terms",
    "maximum_product_defect_events",
    "maximum_propagation_term_visits",
    "maximum_ranking_scan_term_visits",
    "maximum_selected_membership_insertions",
    "maximum_sort_input_items",
    "maximum_tick_evaluations",
    "maximum_total_P2_plus_accuracy_charged_events",
    "maximum_total_charged_term_visits",
    "maximum_total_selection_work_units",
    "maximum_truncation_term_visits",
    "propagation_term_visits",
    "total_charged_term_visits",
    "truncation_term_visits",
})
PUBLIC_RESOURCE_IDENTITIES = (
    "P2_total_equals_cap_scan_plus_propagation_plus_truncation_plus_final_evaluation",
    "accuracy_total_equals_product_plus_merge_plus_drop",
    "product_defect_events_equal_twice_anticommuting_events",
    "completed_execution_anticommuting_split_count_equals_anticommuting_event_count",
    "completed_execution_threshold_dropped_term_count_equals_drop_defect_event_count",
    "combined_total_equals_P2_total_plus_accuracy_total",
    "completed_final_retained_count_equals_final_evaluation_term_visits",
    "uncapped_adaptive_selection_boundaries_equal_completed_step3_"
    "truncation_boundaries",
    "capped_progress_aggregates_never_exceed_their_precharged_event_counts",
    "every_public_count_is_within_its_frozen_D0_probe_cap_or_schedule_bound",
)
TIME_DIAGNOSTIC_KEYS = {
    "user_time_seconds", "system_time_seconds", "elapsed_wall_clock",
    "maximum_resident_set_size_KiB", "minor_page_faults",
    "major_page_faults",
}
PUBLIC_EXCLUSIONS = [
    "scientific_local_or_cumulative_error_values",
    "allocation_assessment_or_candidate_selection",
    "term_or_drop_stream_commitments",
    "checkerboard_observable_center_or_interval",
    "adaptive_execution_branch_as_scientific_evidence",
    "scientific_witness_result_contract_certificate_or_READY_authority",
]

RUNTIME_CUSTODY_KEYS = {
    "runtime_lock_id", "runtime_lock_relative_path", "runtime_lock_sha256",
    "julia_executable_sha256", "JULIA_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "compiled_modules", "network_or_package_resolution_required",
    "Float64_rounding_mode", "locale", "timezone",
    "MajoranaPropagation_source_tree_closure",
    "PauliPropagation_source_tree_closure",
    "runtime_lock_bytes_verified_by_preprobe_checker",
}

STEP3_NUMERIC_CAP_KEYS = {
    "maximum_BigInt_bit_length", "maximum_trig_table_entries",
    "maximum_step3_accuracy_charged_events",
    "maximum_step3_anticommuting_events",
    "maximum_step3_boundary_retained_terms",
    "maximum_step3_cap_scan_term_visits",
    "maximum_step3_current_terms_before_constituent",
    "maximum_step3_drop_defect_events",
    "maximum_step3_final_retained_terms",
    "maximum_step3_merge_defect_events", "maximum_step3_premerge_terms",
    "maximum_step3_product_defect_events",
    "maximum_step3_propagation_term_visits",
    "maximum_step3_total_P2_charged_term_visits",
    "maximum_step3_total_P2_plus_accuracy_charged_events",
    "maximum_step3_truncation_term_visits",
}
SELECTION_NUMERIC_CAP_KEYS = {
    "maximum_peak_ranking_buffer_terms",
    "maximum_ranking_scan_term_visits",
    "maximum_selected_membership_insertions", "maximum_sort_input_items",
    "maximum_tick_evaluations", "maximum_total_selection_work_units",
}


class ProbeError(RuntimeError):
    """Fail-closed P7 D0 validation error."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def loads_json(payload: str | bytes, context: str = "JSON") -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProbeError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload, object_pairs_hook=unique_object)
    except UnicodeDecodeError as error:
        raise ProbeError(f"invalid UTF-8 JSON: {context}") from error
    except json.JSONDecodeError as error:
        raise ProbeError(f"invalid JSON: {context}") from error


def load_json(path: Path) -> Any:
    path = Path(path)
    return loads_json(path.read_bytes(), str(path))


def write_canonical_json(path: Path, value: Any) -> None:
    Path(path).write_bytes(canonical_bytes(value) + b"\n")


def _run_git(*args: str, check: bool = True) -> str:
    process = subprocess.run(
        ["git", *args], cwd=BASE, check=check, capture_output=True,
    )
    return process.stdout.decode("utf-8").strip()


def _source_pins(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = policy.get("source_files")
    if not isinstance(rows, list) or not rows:
        raise ProbeError("P7 D0 source_files is empty or malformed")
    pins: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "size_bytes", "sha256",
        }:
            raise ProbeError("malformed P7 D0 source pin")
        relative = row["relative_path"]
        if not isinstance(relative, str) or relative in pins:
            raise ProbeError("duplicate or invalid P7 D0 source pin")
        pins[relative] = row
    return pins


def _positive_cap_subset(
    value: Any, required: set[str], context: str,
) -> dict[str, int]:
    if not isinstance(value, dict) or not required <= set(value):
        raise ProbeError(f"malformed {context}")
    result: dict[str, int] = {}
    for key in required:
        item = value[key]
        if not isinstance(item, int) or isinstance(item, bool) or item <= 0:
            raise ProbeError(f"invalid {context}: {key}")
        result[key] = item
    return result


def _step_cap_limits_from_fixture(fixture: Mapping[str, Any]) -> dict[str, int]:
    return _positive_cap_subset(
        fixture.get("deterministic_step3_probe_caps"),
        STEP3_NUMERIC_CAP_KEYS, "P7 D0 step-3 cap",
    )


def _selection_cap_limits_from_fixture(
    fixture: Mapping[str, Any],
) -> dict[str, int]:
    return _positive_cap_subset(
        fixture.get("deterministic_step3_selection_probe_caps"),
        SELECTION_NUMERIC_CAP_KEYS, "P7 D0 selection cap",
    )


def _validate_source_tree_closure(
    value: Any, expected: Mapping[str, Any], context: str,
) -> None:
    if not isinstance(value, dict) or set(value) != {
        "file_count", "total_bytes", "closure_sha256",
    }:
        raise ProbeError(f"malformed {context} source-tree closure")
    for key in ("file_count", "total_bytes"):
        if type(value[key]) is not int or value[key] <= 0:
            raise ProbeError(f"invalid {context} source-tree closure: {key}")
    digest = value["closure_sha256"]
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ProbeError(f"invalid {context} source-tree closure digest")
    if value != expected:
        raise ProbeError(f"unexpected {context} source-tree closure")


def _validate_runtime_custody_shape(runtime: Any, context: str) -> None:
    if not isinstance(runtime, dict) or set(runtime) != RUNTIME_CUSTODY_KEYS:
        raise ProbeError(f"{context} runtime custody key drift")
    if (
        runtime["runtime_lock_id"] != RUNTIME_LOCK_ID
        or runtime["runtime_lock_relative_path"] != RUNTIME_LOCK_NAME
        or runtime["runtime_lock_sha256"] != RUNTIME_LOCK_SHA256
        or runtime["julia_executable_sha256"] != JULIA_EXECUTABLE_SHA256
        or runtime["JULIA_NUM_THREADS"] != "1"
        or runtime["OPENBLAS_NUM_THREADS"] != "1"
        or runtime["compiled_modules"] is not False
        or runtime["network_or_package_resolution_required"] is not False
        or runtime["Float64_rounding_mode"] != "RoundNearest"
        or runtime["locale"] != "C"
        or runtime["timezone"] != "UTC"
        or runtime["runtime_lock_bytes_verified_by_preprobe_checker"] is not True
    ):
        raise ProbeError(f"{context} runtime custody drift")
    _validate_source_tree_closure(
        runtime["MajoranaPropagation_source_tree_closure"],
        MAJORANA_SOURCE_TREE_CLOSURE, "MajoranaPropagation",
    )
    _validate_source_tree_closure(
        runtime["PauliPropagation_source_tree_closure"],
        PAULI_SOURCE_TREE_CLOSURE, "PauliPropagation",
    )


def _validate_runtime_lock_bytes(runtime: Mapping[str, Any]) -> None:
    """Bind the declared runtime and source closures to the P0 lock bytes."""
    _validate_runtime_custody_shape(runtime, "P7 D0 policy")
    path = BASE / RUNTIME_LOCK_NAME
    if not path.is_file() or path.is_symlink():
        raise ProbeError("P7 D0 runtime lock is missing or nonregular")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != RUNTIME_LOCK_SHA256:
        raise ProbeError("P7 D0 runtime-lock bytes SHA-256 mismatch")
    lock = loads_json(body, str(path))
    if (
        not isinstance(lock, dict)
        or lock.get("schema_version") != 1
        or lock.get("runtime_lock_id") != RUNTIME_LOCK_ID
    ):
        raise ProbeError("P7 D0 runtime-lock identity drift")
    try:
        executable_sha256 = lock["julia_runtime"]["executable"]["sha256"]
        packages = lock["direct_and_semantic_upstream_packages"]
        majorana_closure = packages["MajoranaPropagation"][
            "installed_source_closure"
        ]
        pauli_closure = packages["PauliPropagation"][
            "installed_source_closure"
        ]
    except (KeyError, TypeError) as error:
        raise ProbeError("P7 D0 runtime-lock closure custody is malformed") from error
    if executable_sha256 != runtime["julia_executable_sha256"]:
        raise ProbeError("P7 D0 runtime-lock Julia executable drift")
    if majorana_closure != runtime["MajoranaPropagation_source_tree_closure"]:
        raise ProbeError("P7 D0 MajoranaPropagation closure custody drift")
    if pauli_closure != runtime["PauliPropagation_source_tree_closure"]:
        raise ProbeError("P7 D0 PauliPropagation closure custody drift")


def _validate_fixture(fixture: Any) -> Mapping[str, Any]:
    if (not isinstance(fixture, dict)
            or type(fixture.get("schema_version")) is not int
            or fixture.get("schema_version") != 1):
        raise ProbeError("malformed P7 D0 fixture")
    if set(fixture) != {
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible", "scope",
        "candidate_design", "frozen_P6_prefix", "step3_adaptive_rule",
        "exact_lazy_implementation", "outward_arithmetic",
        "deterministic_step3_probe_caps",
        "deterministic_step3_selection_probe_caps", "host_supervisor_caps",
        "runtime_custody", "required_base_fixture_sha256",
        "expected_P6_prefix_resource_projection",
    }:
        raise ProbeError("P7 D0 fixture top-level key drift")
    if fixture.get("fixture_id") != FIXTURE_ID:
        raise ProbeError("unexpected P7 D0 fixture identity")
    if fixture.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise ProbeError("unexpected P7 D0 fixture parent")
    if fixture.get("scientific_authority") != "NONE":
        raise ProbeError("P7 D0 fixture claims scientific authority")
    if fixture.get("certificate_eligible") is not False:
        raise ProbeError("P7 D0 fixture is certificate eligible")
    scope = fixture.get("scope")
    if (
        not isinstance(scope, dict)
        or scope.get("D0_formal_finalizer_privacy") != FINALIZER_PRIVACY
        or scope.get("checkerboard_Neel_expectation")
        != CHECKERBOARD_NEEL_SCOPE
    ):
        raise ProbeError("P7 D0 finalizer-privacy disclosure drift")
    design = fixture.get("candidate_design", {})
    if design.get("probe_mode_order") != [PROBE_MODE]:
        raise ProbeError("P7 D0 fixture mode order drift")
    if design.get("formal_candidates") != [CANDIDATE_ID]:
        raise ProbeError("P7 D0 fixture formal candidate drift")
    if design.get("formal_candidate_count") != 1:
        raise ProbeError("P7 D0 fixture does not freeze one candidate")
    if (
        design.get("candidate_id") != CANDIDATE_ID
        or design.get("probe_mode") != PROBE_MODE
        or design.get("algorithm_id")
        != "MAJORANA-P7-E768-MAX-LAZY37-STEP3-V1"
        or design.get("control_candidate") is not None
    ):
        raise ProbeError("P7 D0 fixture unexpectedly defines a control")
    if design.get("design_disclosure") != "P6_INFORMED_P7_RESULT_UNPINNED":
        raise ProbeError("P7 D0 fixture hindsight disclosure drift")
    if (
        design.get("fresh_D0_process_count") != 1
        or design.get("required_future_S0_fresh_process_count") != 2
        or design.get("all_three_steps_execute_in_one_process") is not True
        or design.get("step1_to_step2_uses_a_live_deepcopy") is not True
        or design.get("step2_to_step3_uses_a_live_deepcopy") is not True
        or design.get(
            "checkpoint_serialization_or_cross_process_resume_forbidden"
        ) is not True
        or design.get("candidate_or_budget_grid_forbidden") is not True
        or design.get("formal_candidate_is_frozen_before_any_P7_probe_output")
        is not True
        or design.get(
            "P6_observed_local_slack_is_not_a_step3_budget_input"
        ) is not True
    ):
        raise ProbeError("P7 D0 fixture candidate custody drift")
    rule = fixture.get("step3_adaptive_rule", {})
    grid = 1 << 128
    strict_max = (grid - 1) // 400000
    cumulative_max = (3 * grid - 1) // 400000
    if rule.get("grid_denominator") != str(grid):
        raise ProbeError("P7 D0 grid drift")
    if rule.get("maximum_strictly_legal_local_ticks") != str(strict_max):
        raise ProbeError("P7 D0 strict local maximum drift")
    if rule.get("local_raw_boundary_indices") != "0_through_767":
        raise ProbeError("P7 D0 raw boundary domain drift")
    if rule.get("local_released_prefix_number_q") != (
        "local_raw_boundary_index_plus_one_in_1_through_768"
    ):
        raise ProbeError("P7 D0 released-prefix mapping drift")
    if (
        rule.get("mapped_step_index") != 3
        or rule.get("local_allocation_denominator") != 400000
        or rule.get("local_allocation") != "1/400000"
        or rule.get("local_boundary_count") != 768
        or rule.get("global_raw_boundary_indices") != "1536_through_2303"
        or rule.get("global_raw_boundary_index_formula")
        != "1536_plus_local_raw_boundary_index"
        or rule.get("prefix_target_formula")
        != "floor((q*maximum_strictly_legal_local_ticks)/768)"
        or rule.get("prefix_target_uses_local_q_not_the_global_boundary_index")
        is not True
        or rule.get(
            "step3_local_ledger_resets_exactly_once_at_the_step2_to_step3_"
            "mapped_step_boundary"
        ) is not True
        or rule.get("step2_unused_local_slack_is_not_carried_into_step3")
        is not True
        or rule.get("future_step4_budget_cannot_be_borrowed") is not True
        or rule.get("future_S0_three_step_cumulative_allocation") != "3/400000"
        or rule.get("future_S0_maximum_strictly_legal_cumulative_ticks")
        != str(cumulative_max)
        or rule.get("future_S0_maximum_strictly_legal_cumulative_ticks_formula")
        != "floor((3*2^128-1)/400000)"
        or rule.get("allocation_equality_is_failure") is not True
        or rule.get("D0_does_not_compare_the_completed_local_ledger_to_the_allocation")
        is not True
    ):
        raise ProbeError("P7 D0 step-3 authority boundary drift")
    lazy = fixture.get("exact_lazy_implementation", {})
    if lazy.get("split_threshold_exponent") != 37:
        raise ProbeError("P7 D0 lazy split drift")
    if (
        lazy.get("split_threshold_Float64_bits_hex")
        != "3da0000000000000"
        or lazy.get("tier1_is_a_provable_initial_segment_of_the_full_ranking")
        is not True
        or lazy.get(
            "if_tier1_is_fully_selected_with_positive_remainder_rescan_the_"
            "same_unmodified_snapshot"
        ) is not True
        or lazy.get(
            "tier2_collects_every_nonpool_row_whose_exact_cost_is_at_most_"
            "the_current_remainder"
        ) is not True
        or lazy.get("hard_K37_eligibility_gate_is_forbidden") is not True
        or lazy.get(
            "step2_and_step3_lazy_state_counters_membership_and_snapshots_are_"
            "disjoint"
        ) is not True
    ):
        raise ProbeError("P7 D0 fixture permits a hard K37 gate")
    _step_cap_limits_from_fixture(fixture)
    _selection_cap_limits_from_fixture(fixture)
    host = fixture.get("host_supervisor_caps")
    if not isinstance(host, dict) or {
        key: host.get(key) for key in (
            "MemoryMax_bytes", "MemorySwapMax_bytes", "RuntimeMaxSec",
            "outer_safety_timeout_seconds", "maximum_stdout_bytes",
            "maximum_stderr_bytes",
        )
    } != {
        "MemoryMax_bytes": 2147483648,
        "MemorySwapMax_bytes": 0,
        "RuntimeMaxSec": "1800s",
        "outer_safety_timeout_seconds": 1830,
        "maximum_stdout_bytes": 1048576,
        "maximum_stderr_bytes": 1048576,
    }:
        raise ProbeError("P7 D0 fixture host admission drift")
    runtime = fixture.get("runtime_custody")
    _validate_runtime_custody_shape(runtime, "P7 D0 fixture")
    base_pins = fixture.get("required_base_fixture_sha256")
    expected_pin_paths = {
        "P2": "majorana_certificate_p2_fixture.json",
        "P3": "majorana_certificate_p3_fixture.json",
        "P4": "majorana_certificate_p4_fixture.json",
        "P5": "majorana_certificate_p5_fixture.json",
        "P6": "majorana_certificate_p6_fixture.json",
    }
    if not isinstance(base_pins, dict) or set(base_pins) != set(
        expected_pin_paths
    ):
        raise ProbeError("P7 D0 base fixture pin set drift")
    for label, relative in expected_pin_paths.items():
        if base_pins[label] != file_sha256(BASE / relative):
            raise ProbeError(f"P7 D0 base fixture pin drift: {label}")
    expected = fixture.get("expected_P6_prefix_resource_projection")
    if not isinstance(expected, dict) or set(expected) != {
        "step1", "step2", "step_link", "selection_resources",
    }:
        raise ProbeError("malformed P7 D0 inline P6 prefix projection")
    return fixture


def validate_policy(
    policy: Any, *, require_report_absent: bool,
) -> Mapping[str, Any]:
    if (not isinstance(policy, dict)
            or type(policy.get("schema_version")) is not int
            or policy.get("schema_version") != 1):
        raise ProbeError("malformed P7 D0 policy")
    if set(policy) != {
        "schema_version", "policy_id", "policy_fingerprint", "policy_role",
        "required_direct_parent_commit", "required_fixture_relative_path",
        "probe_driver_relative_path", "scientific_authority",
        "certificate_eligible", "hindsight_firewall", "candidate_design",
        "P6_prefix_reproduction", "scientific_algorithm",
        "D0_observation_contract", "D0_deterministic_resource_caps",
        "D0_host_supervisor_caps", "fixed_admission_rule",
        "fixed_formal_admission_schema", "stop_rules", "runtime",
        "state_custody_and_runner_visibility", "staged_source_custody",
        "stage_and_artifact_exclusions", "D0_to_S0_lifecycle",
        "future_S0_terminal_truth_requirements",
        "adversarial_mutations_required", "authority_exclusions",
        "source_files",
    }:
        raise ProbeError("P7 D0 policy top-level key drift")
    semantic_policy = {
        key: value for key, value in policy.items() if key != "source_files"
    }
    if canonical_sha256(semantic_policy) != POLICY_SEMANTIC_SHA256:
        raise ProbeError("P7 D0 policy semantic object drift")
    if policy.get("policy_id") != POLICY_ID:
        raise ProbeError("unexpected P7 D0 policy identity")
    if (
        policy.get("policy_fingerprint")
        != "majorana_p7_p6_informed_result_unpinned_fixed_admission_step3_"
        "e768_max_lazy37_resource_probe_v1"
        or policy.get("policy_role")
        != "result_unpinned_non_authoritative_resource_probe_for_one_adjacent_"
        "step3_continuation_after_a_fresh_resource_conforming_P6_prefix"
        or policy.get("required_fixture_relative_path") != FIXTURE_NAME
        or policy.get("probe_driver_relative_path") != PROBE_DRIVER
    ):
        raise ProbeError("P7 D0 policy role or source path drift")
    if policy.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise ProbeError("unexpected P7 D0 direct parent")
    if policy.get("scientific_authority") != "NONE":
        raise ProbeError("P7 D0 policy claims scientific authority")
    if policy.get("certificate_eligible") is not False:
        raise ProbeError("P7 D0 policy is certificate eligible")
    design = policy.get("candidate_design", {})
    if design.get("probe_mode_order") != [PROBE_MODE]:
        raise ProbeError("P7 D0 policy mode order drift")
    if design.get("formal_candidate_order_is_frozen_before_any_D0_output") != [
        CANDIDATE_ID
    ]:
        raise ProbeError("P7 D0 formal candidate set drift")
    formal = design.get("formal_candidates")
    if not isinstance(formal, list) or len(formal) != 1:
        raise ProbeError("P7 D0 does not have exactly one formal candidate")
    if formal[0].get("probe_mode") != PROBE_MODE:
        raise ProbeError("P7 D0 formal candidate mode drift")
    if formal[0].get("candidate_id") != CANDIDATE_ID:
        raise ProbeError("P7 D0 formal candidate identity drift")
    if (
        design.get("candidate_execution_order") != [CANDIDATE_ID]
        or design.get("exactly_one_formal_candidate") is not True
        or design.get("control_candidate") is not None
        or design.get("there_is_no_multi_candidate_selector") is not True
        or design.get(
            "candidate_CLI_environment_or_runtime_selection_is_forbidden"
        ) is not True
    ):
        raise ProbeError("P7 D0 candidate-design firewall drift")
    expected_formal_candidate = {
        "candidate_id": CANDIDATE_ID,
        "probe_mode": PROBE_MODE,
        "algorithm_id": "MAJORANA-P7-E768-MAX-LAZY37-STEP3-V1",
        "prefix_path": (
            "fresh_O0_then_P3_2^-34_step1_then_P6_E768_MAX_LAZY37_V1_step2"
        ),
        "step3_path": (
            "full_postmerge_domain_maximal_affordable_prefix_under_a_new_"
            "step3_local_error_escrow"
        ),
        "implementation_strategy": (
            "exact_lazy_initial_segment_acceleration_anchored_at_strict_"
            "2_pow_minus_37"
        ),
        "fresh_D0_process_count": 1,
        "required_future_S0_fresh_process_count": 2,
        "selectable": True,
    }
    if formal[0] != expected_formal_candidate:
        raise ProbeError("P7 D0 formal candidate definition drift")
    algorithm = policy.get("scientific_algorithm", {})
    if algorithm.get("strict_local_maximum_formula") != (
        "floor((2^128-1)/400000)"
    ):
        raise ProbeError("P7 D0 local budget formula drift")
    if (
        algorithm.get("common_grid_denominator") != str(1 << 128)
        or algorithm.get("step3_local_allocation") != "1/400000"
        or algorithm.get("strict_local_maximum_ticks")
        != str(((1 << 128) - 1) // 400000)
        or algorithm.get("allocation_equality_is_failure") is not True
    ):
        raise ProbeError("P7 D0 scientific-algorithm allocation drift")
    boundary_design = algorithm.get("step3_boundary_design", {})
    if (
        boundary_design.get("boundary_count") != 768
        or boundary_design.get("local_raw_boundary_index_domain")
        != "0_through_767"
        or boundary_design.get("global_raw_boundary_index_domain")
        != "1536_through_2303"
        or boundary_design.get("global_raw_boundary_index_formula")
        != "1536_plus_local_raw_boundary_index"
        or boundary_design.get(
            "prefix_uses_local_q_and_never_the_global_boundary_index"
        ) is not True
        or boundary_design.get(
            "local_ledger_resets_exactly_once_at_the_step2_to_step3_boundary"
        ) is not True
    ):
        raise ProbeError("P7 D0 policy boundary schedule drift")
    if algorithm.get("lazy_k37_accelerator", {}).get(
        "hard_K37_pool_only_stopping_with_positive_remaining_ticks_is_forbidden"
    ) is not True:
        raise ProbeError("P7 D0 policy permits a hard K37 gate")
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    policy_caps = policy.get("D0_deterministic_resource_caps", {})
    expected_policy_caps = {
        **fixture["deterministic_step3_probe_caps"],
        **fixture["deterministic_step3_selection_probe_caps"],
    }
    if policy_caps != expected_policy_caps:
        raise ProbeError("P7 D0 deterministic cap envelope drift")
    host = policy.get("D0_host_supervisor_caps", {})
    if host != fixture["host_supervisor_caps"]:
        raise ProbeError("P7 D0 host caps drift")
    runtime = policy.get("runtime", {})
    if runtime != fixture["runtime_custody"]:
        raise ProbeError("P7 D0 runtime custody drift")
    _validate_runtime_lock_bytes(runtime)
    observation_contract = policy.get("D0_observation_contract", {})
    if observation_contract.get("public_cap_event_name_allowlist") != sorted(
        CAP_EVENT_NAMES
    ):
        raise ProbeError("P7 D0 public cap-event allowlist drift")
    if observation_contract.get("public_resource_identities") != list(
        PUBLIC_RESOURCE_IDENTITIES
    ):
        raise ProbeError("P7 D0 public resource identities drift")
    if observation_contract.get("public_witness_exact_top_level_fields") != [
        "schema_version", "probe_type", "fixture_id", "fixture_sha256",
        "fixture_canonical_sha256", "scientific_authority",
        "certificate_eligible", "result_contract_eligible",
        "resource_observations_only", "candidate", "runtime_custody",
        "step1", "step2", "step3", "step1_to_step2_link",
        "step2_to_step3_link", "step2_selection_resources",
        "step3_selection_resources",
        "P6_prefix_resource_projection_conformed", "step3_started",
        "explicit_exclusions",
    ]:
        raise ProbeError("P7 D0 public witness schema drift")
    if observation_contract.get("public_candidate_exact_fields") != [
        "candidate_id", "probe_mode", "identity", "formal_candidate",
        "step1_path", "step2_path", "step3_path",
    ]:
        raise ProbeError("P7 D0 public candidate schema drift")
    if observation_contract.get("public_link_exact_fields") != [
        "same_process", "checkpoint_or_serialized_state_used",
        "previous_step_final_term_count", "next_step_input_term_count",
    ]:
        raise ProbeError("P7 D0 public link schema drift")
    if observation_contract.get("public_explicit_exclusions") != (
        PUBLIC_EXCLUSIONS
    ):
        raise ProbeError("P7 D0 public exclusions schema drift")
    if observation_contract.get("formal_finalizer_privacy") != FINALIZER_PRIVACY:
        raise ProbeError("P7 D0 policy finalizer-privacy disclosure drift")
    admission = policy.get("fixed_admission_rule", policy.get(
        "formal_cap_derivation_rule", {},
    ))
    if not isinstance(admission, dict):
        raise ProbeError("missing P7 D0 fixed admission rule")
    admission_text = json.dumps(admission, sort_keys=True)
    if "2147483648" not in admission_text or "1800" not in admission_text:
        raise ProbeError("P7 D0 fixed admission envelope drift")
    if "two_times" in admission_text or "2_times" in admission_text:
        raise ProbeError("P7 D0 retains the forbidden observation-times-two rule")
    formal_schema = policy.get("fixed_formal_admission_schema", {})
    if (
        formal_schema.get("report_field_name") != "fixed_formal_admission"
        or formal_schema.get("exact_fields") != [
            "status", "formal_step3_caps",
            "formal_step3_selection_caps", "formal_host_caps",
            "derived_from_observation", "same_as_D0_admission",
        ]
        or formal_schema.get("established_status")
        != "ESTABLISHED_FOR_FUTURE_S0_PRECOMMIT"
        or formal_schema.get("prefix_mismatch_status")
        != "NOT_ESTABLISHED_INVALID_PREFIX_RESOURCE_CONFORMANCE"
        or formal_schema.get("step1_cap_status")
        != "NOT_ESTABLISHED_DETERMINISTIC_STEP1_CAP"
        or formal_schema.get("step2_cap_status")
        != "NOT_ESTABLISHED_DETERMINISTIC_STEP2_CAP"
        or formal_schema.get("step3_cap_status")
        != "NOT_ESTABLISHED_DETERMINISTIC_STEP3_CAP"
        or formal_schema.get("host_failure_status")
        != "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
        or formal_schema.get("derived_from_observation") is not False
        or formal_schema.get("same_as_D0_admission") is not True
    ):
        raise ProbeError("P7 D0 fixed formal admission schema drift")

    staged_custody = policy.get("staged_source_custody", {})
    if (
        staged_custody.get("staged_path_order") != list(STAGED_PATHS)
        or staged_custody.get("exact_staged_path_count") != 13
        or staged_custody.get(
            "every_staged_file_is_regular_and_not_a_symlink"
        ) is not True
        or staged_custody.get(
            "staged_sha256_must_equal_repository_sha256_for_every_path"
        ) is not True
        or staged_custody.get(
            "candidate_algorithm_transform_applied_is_false_for_every_path"
        ) is not True
        or staged_custody.get(
            "string_source_AST_or_runtime_transform_is_forbidden"
        ) is not True
        or staged_custody.get(
            "Python_orchestrator_is_source_pinned_but_not_runner_staged"
        ) is not True
    ):
        raise ProbeError("P7 D0 staged-source custody drift")
    artifact_exclusions = policy.get("stage_and_artifact_exclusions", {})
    if artifact_exclusions.get(
        "future_P7_result_artifacts_must_be_absent_at_D0_precommit"
    ) != list(RESULT_ARTIFACTS):
        raise ProbeError("P7 D0 future-artifact exclusion drift")

    pins = _source_pins(policy)
    expected_paths = set((*STAGED_PATHS, Path(__file__).name))
    if set(pins) != expected_paths:
        raise ProbeError("P7 D0 source pin allowlist drift")
    for relative, row in pins.items():
        path = BASE / relative
        if not path.is_file() or path.is_symlink():
            raise ProbeError(f"missing or nonregular P7 D0 source: {relative}")
        body = path.read_bytes()
        if row.get("size_bytes") != len(body):
            raise ProbeError(f"P7 D0 source size drift: {relative}")
        if row.get("sha256") != hashlib.sha256(body).hexdigest():
            raise ProbeError(f"P7 D0 source hash drift: {relative}")
    if require_report_absent:
        if (BASE / REPORT_NAME).exists():
            raise ProbeError("P7 D0 report exists before the probe commit")
        for relative in RESULT_ARTIFACTS[1:]:
            if (BASE / relative).exists():
                raise ProbeError(f"future P7 artifact exists before D0: {relative}")
    return policy


def stage_probe_tree(
    destination: Path, policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    pins = _source_pins(policy)
    rows: list[dict[str, Any]] = []
    for relative in STAGED_PATHS:
        body = (BASE / relative).read_bytes()
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        rows.append({
            "relative_path": relative,
            "repository_sha256": pins[relative]["sha256"],
            "staged_size_bytes": len(body),
            "staged_sha256": hashlib.sha256(body).hexdigest(),
            "byte_identical_to_repository": True,
        })
    return rows


def _step_cap_limits(label: str) -> dict[str, int]:
    if label == "step1":
        p2 = load_json(BASE / "majorana_certificate_p2_fixture.json")[
            "deterministic_resource_caps"
        ]
        p3_fixture = load_json(BASE / "majorana_certificate_p3_fixture.json")
        p3 = p3_fixture["deterministic_resource_caps"]
        return {
            "maximum_current_terms_before_constituent":
                p2["maximum_current_terms_before_constituent"],
            "maximum_premerge_terms": p2["maximum_premerge_terms"],
            "maximum_boundary_retained_terms":
                p2["maximum_boundary_retained_terms"],
            "cap_scan_term_visits": p2["maximum_cap_scan_term_visits"],
            "propagation_term_visits":
                p2["maximum_propagation_term_visits"],
            "truncation_term_visits":
                p2["maximum_truncation_term_visits"],
            "final_evaluation_term_visits":
                p2["maximum_boundary_retained_terms"],
            "total_charged_term_visits":
                p2["maximum_total_charged_term_visits"],
            "maximum_anticommuting_events":
                p3["maximum_anticommuting_events"],
            "maximum_product_defect_events":
                p3["maximum_product_defect_events"],
            "maximum_merge_defect_events":
                p3["maximum_merge_defect_events"],
            "maximum_drop_defect_events":
                p3["maximum_drop_defect_events"],
            "maximum_accuracy_charged_events":
                p3["maximum_accuracy_charged_events"],
            "maximum_total_P2_plus_accuracy_charged_events":
                p3["maximum_total_P2_plus_accuracy_charged_events"],
            "maximum_BigInt_bit_length":
                p3_fixture["outward_arithmetic"]["maximum_BigInt_bit_length"],
        }
    if label == "step2":
        p6_fixture = load_json(BASE / "majorana_certificate_p6_fixture.json")
        step = p6_fixture["deterministic_resource_caps"]
        selection = p6_fixture["deterministic_selection_caps"]
        prefix = "maximum_step2_"
        maximum_bits = step["maximum_BigInt_bit_length"]
    elif label == "step3":
        fixture = load_json(BASE / FIXTURE_NAME)
        step = fixture["deterministic_step3_probe_caps"]
        selection = fixture["deterministic_step3_selection_probe_caps"]
        prefix = "maximum_step3_"
        maximum_bits = fixture["outward_arithmetic"][
            "maximum_BigInt_bit_length"
        ]
    else:
        raise ProbeError(f"unexpected P7 D0 resource-summary label: {label}")
    return {
        "maximum_current_terms_before_constituent":
            step[prefix + "current_terms_before_constituent"],
        "maximum_premerge_terms": step[prefix + "premerge_terms"],
        "maximum_boundary_retained_terms":
            step[prefix + "boundary_retained_terms"],
        "maximum_cap_scan_term_visits":
            step[prefix + "cap_scan_term_visits"],
        "maximum_propagation_term_visits":
            step[prefix + "propagation_term_visits"],
        "maximum_truncation_term_visits":
            step[prefix + "truncation_term_visits"],
        "maximum_final_evaluation_term_visits":
            step[prefix + "final_retained_terms"],
        "maximum_total_charged_term_visits":
            step[prefix + "total_P2_charged_term_visits"],
        "maximum_anticommuting_events":
            step[prefix + "anticommuting_events"],
        "maximum_product_defect_events":
            step[prefix + "product_defect_events"],
        "maximum_merge_defect_events":
            step[prefix + "merge_defect_events"],
        "maximum_drop_defect_events":
            step[prefix + "drop_defect_events"],
        "maximum_accuracy_charged_events":
            step[prefix + "accuracy_charged_events"],
        "maximum_total_P2_plus_accuracy_charged_events":
            step[prefix + "total_P2_plus_accuracy_charged_events"],
        "maximum_BigInt_bit_length": maximum_bits,
        "maximum_ranking_scan_term_visits":
            selection["maximum_ranking_scan_term_visits"],
        "maximum_sort_input_items": selection["maximum_sort_input_items"],
        "maximum_tick_evaluations": selection["maximum_tick_evaluations"],
        "maximum_selected_membership_insertions":
            selection["maximum_selected_membership_insertions"],
        "maximum_peak_ranking_buffer_terms":
            selection["maximum_peak_ranking_buffer_terms"],
        "maximum_total_selection_work_units":
            selection["maximum_total_selection_work_units"],
    }


def _validate_cap_event(
    value: Any, cap_limits: Mapping[str, int], label: str,
) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {
        "cap_name", "limit", "attempted", "context",
        "rejected_operation_was_not_executed_after_cap_detection",
    }:
        raise ProbeError("malformed P7 D0 cap event")
    if value["rejected_operation_was_not_executed_after_cap_detection"] is not True:
        raise ProbeError("P7 D0 cap executed the rejected operation")
    if value["cap_name"] not in cap_limits:
        raise ProbeError("P7 D0 cap name is outside the frozen allowlist")
    for key in ("limit", "attempted"):
        if (not isinstance(value[key], int) or isinstance(value[key], bool)
                or value[key] < 0):
            raise ProbeError(f"invalid P7 D0 cap value: {key}")
    if value["attempted"] <= value["limit"]:
        raise ProbeError("P7 D0 cap attempted value does not exceed its limit")
    if value["limit"] != cap_limits[value["cap_name"]]:
        raise ProbeError("P7 D0 cap limit differs from the frozen limit")
    context = value["context"]
    if (not isinstance(context, dict) or not set(context) <= CAP_CONTEXT_KEYS
            or "operation" not in context):
        raise ProbeError("malformed P7 D0 sanitized cap context")
    if context["operation"] != "resource_cap_precheck":
        raise ProbeError("P7 D0 cap context exposes an unfrozen operation")
    if label == "step3" and context.get("mapped_step_index") != 3:
        raise ProbeError("P7 D0 step-3 cap lacks its mapped-step identity")
    if "mapped_step_index" in context and context["mapped_step_index"] not in {
        1, 2, 3,
    }:
        raise ProbeError("P7 D0 cap context has an invalid mapped-step index")
    if "group" in context and (
        not isinstance(context["group"], str) or not context["group"]
    ):
        raise ProbeError("invalid P7 D0 cap context group")
    for key in CAP_CONTEXT_KEYS - {"group", "operation"}:
        if key in context and (
            not isinstance(context[key], int) or isinstance(context[key], bool)
            or context[key] < 0
        ):
            raise ProbeError(f"invalid P7 D0 cap context index: {key}")


def _validate_resource_summary(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != RESOURCE_SUMMARY_KEYS:
        raise ProbeError(f"malformed P7 D0 {label} resource summary")
    if (not isinstance(value["P2_resource_counters"], dict)
            or set(value["P2_resource_counters"]) != P2_COUNTER_KEYS):
        raise ProbeError(f"malformed P7 D0 {label} P2 counters")
    if (not isinstance(value["accuracy_event_counters"], dict)
            or set(value["accuracy_event_counters"]) != ACCURACY_COUNTER_KEYS):
        raise ProbeError(f"malformed P7 D0 {label} accuracy counters")
    for key, item in value.items():
        if key in {
            "P2_resource_counters", "accuracy_event_counters", "cap_event",
            "final_retained_term_count",
        }:
            continue
        if (not isinstance(item, int) or isinstance(item, bool) or item < 0):
            raise ProbeError(f"invalid P7 D0 {label} resource count: {key}")
    for group in (value["P2_resource_counters"], value["accuracy_event_counters"]):
        if any(
            not isinstance(item, int) or isinstance(item, bool) or item < 0
            for item in group.values()
        ):
            raise ProbeError(f"invalid P7 D0 {label} nested resource count")
    cap_limits = _step_cap_limits(label)
    _validate_cap_event(value["cap_event"], cap_limits, label)
    p2 = value["P2_resource_counters"]
    accuracy = value["accuracy_event_counters"]
    if p2["total_charged_term_visits"] != (
        p2["cap_scan_term_visits"]
        + p2["propagation_term_visits"]
        + p2["truncation_term_visits"]
        + p2["final_evaluation_term_visits"]
    ):
        raise ProbeError(f"P7 D0 {label} P2 resource identity mismatch")
    if accuracy["accuracy_charged_event_count"] != (
        accuracy["product_defect_event_count"]
        + accuracy["merge_defect_event_count"]
        + accuracy["drop_defect_event_count"]
    ):
        raise ProbeError(f"P7 D0 {label} accuracy resource identity mismatch")
    if accuracy["product_defect_event_count"] != (
        2 * accuracy["anticommuting_event_count"]
    ):
        raise ProbeError(f"P7 D0 {label} product/anticommuting identity mismatch")
    if value["cap_event"] is None:
        if value["anticommuting_split_count"] != accuracy[
            "anticommuting_event_count"
        ]:
            raise ProbeError(
                f"P7 D0 {label} split/anticommuting identity mismatch"
            )
        if value["threshold_dropped_term_count"] != accuracy[
            "drop_defect_event_count"
        ]:
            raise ProbeError(f"P7 D0 {label} drop-event identity mismatch")
    elif (
        value["anticommuting_split_count"]
        > accuracy["anticommuting_event_count"]
        or value["threshold_dropped_term_count"]
        > accuracy["drop_defect_event_count"]
    ):
        raise ProbeError(f"P7 D0 {label} capped progress exceeds charged events")
    if value["total_P2_plus_accuracy_charged_event_count"] != (
        p2["total_charged_term_visits"]
        + accuracy["accuracy_charged_event_count"]
    ):
        raise ProbeError(f"P7 D0 {label} combined resource identity mismatch")
    if (
        value["completed_composite_count"] > 512
        or value["completed_constituent_count"] > 1152
        or value["completed_truncation_boundary_count"] > 768
    ):
        raise ProbeError(f"P7 D0 {label} completed-count bound exceeded")
    prefix = "" if label == "step1" else "maximum_"
    observed_limits = {
        "cap_scan_term_visits": f"{prefix}cap_scan_term_visits",
        "propagation_term_visits": f"{prefix}propagation_term_visits",
        "truncation_term_visits": f"{prefix}truncation_term_visits",
        "final_evaluation_term_visits": f"{prefix}final_evaluation_term_visits",
        "total_charged_term_visits":
            "total_charged_term_visits" if label == "step1"
            else "maximum_total_charged_term_visits",
    }
    for field, cap_name in observed_limits.items():
        if p2[field] > cap_limits[cap_name]:
            raise ProbeError(f"P7 D0 {label} P2 count exceeds its probe cap")
    accuracy_limits = {
        "anticommuting_event_count": "maximum_anticommuting_events",
        "product_defect_event_count": "maximum_product_defect_events",
        "merge_defect_event_count": "maximum_merge_defect_events",
        "drop_defect_event_count": "maximum_drop_defect_events",
        "accuracy_charged_event_count": "maximum_accuracy_charged_events",
    }
    for field, cap_name in accuracy_limits.items():
        if accuracy[field] > cap_limits[cap_name]:
            raise ProbeError(f"P7 D0 {label} accuracy count exceeds its probe cap")
    if value["total_P2_plus_accuracy_charged_event_count"] > cap_limits[
        "maximum_total_P2_plus_accuracy_charged_events"
    ]:
        raise ProbeError(f"P7 D0 {label} combined count exceeds its probe cap")
    premerge_cap = cap_limits["maximum_premerge_terms"]
    if (
        value["peak_premerge_contribution_count"] > premerge_cap
        or value["peak_postmerge_unique_term_count"] > premerge_cap
    ):
        raise ProbeError(f"P7 D0 {label} peak term count exceeds its probe cap")
    final_count = value["final_retained_term_count"]
    if value["cap_event"] is None:
        if (not isinstance(final_count, int) or isinstance(final_count, bool)
                or final_count < 0):
            raise ProbeError(f"missing P7 D0 {label} completed final count")
        final_cap_name = (
            "final_evaluation_term_visits" if label == "step1"
            else "maximum_final_evaluation_term_visits"
        )
        if final_count > cap_limits[final_cap_name]:
            raise ProbeError(f"P7 D0 {label} final count exceeds its probe cap")
        if final_count != p2["final_evaluation_term_visits"]:
            raise ProbeError(f"P7 D0 {label} final-evaluation identity mismatch")
    elif final_count is not None:
        raise ProbeError(f"capped P7 D0 {label} exposes a final count")
    elif p2["final_evaluation_term_visits"] != 0:
        raise ProbeError(f"capped P7 D0 {label} exposes final-evaluation work")


def _reject_public_scientific_vocabulary(value: Any, path: str = "$") -> None:
    forbidden = (
        "budget", "slack", "cutoff", "winner", "fallback", "neel",
        "coefficient_bits", "mask_hex", "drop_rows", "term_stream",
        "allocation_pass", "operator_error_ticks", "product_defect_ticks",
        "merge_defect_ticks", "drop_defect_ticks",
    )
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()
            if any(fragment in lower for fragment in forbidden):
                raise ProbeError(f"forbidden P7 D0 public key at {path}.{key}")
            _reject_public_scientific_vocabulary(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_public_scientific_vocabulary(item, f"{path}[{index}]")
    elif isinstance(value, str):
        lower = value.lower()
        if any(fragment in lower for fragment in forbidden):
            raise ProbeError(f"forbidden P7 D0 public string at {path}")


def _selection_caps(label: str) -> Mapping[str, int]:
    if label == "step2":
        return load_json(
            BASE / "majorana_certificate_p6_fixture.json"
        )["deterministic_selection_caps"]
    if label == "step3":
        return _selection_cap_limits_from_fixture(
            load_json(BASE / FIXTURE_NAME)
        )
    raise ProbeError(f"unexpected P7 D0 selection label: {label}")


def _validate_selection_resources(
    value: Any, label: str, summary: Mapping[str, Any],
) -> None:
    if not isinstance(value, dict) or set(value) != SELECTION_RESOURCE_KEYS:
        raise ProbeError(f"malformed P7 D0 {label} selection resources")
    if any(
        not isinstance(item, int) or isinstance(item, bool) or item < 0
        for item in value.values()
    ):
        raise ProbeError(f"invalid P7 D0 {label} selection resource count")
    expected_total = (
        value["total_ranking_scan_term_visits"]
        + value["total_sort_work_items"]
        + value["total_tick_evaluations"]
        + value["total_selected_membership_insertions"]
    )
    if value["total_selection_work_units"] != expected_total:
        raise ProbeError(f"P7 D0 {label} selection work identity mismatch")
    caps = _selection_caps(label)
    limits = {
        "total_ranking_scan_term_visits": "maximum_ranking_scan_term_visits",
        "total_sort_work_items": "maximum_sort_input_items",
        "total_tick_evaluations": "maximum_tick_evaluations",
        "total_selected_membership_insertions":
            "maximum_selected_membership_insertions",
        "peak_ranking_buffer_terms": "maximum_peak_ranking_buffer_terms",
        "total_selection_work_units": "maximum_total_selection_work_units",
    }
    for field, cap_name in limits.items():
        if value[field] > caps[cap_name]:
            raise ProbeError(
                f"P7 D0 {label} selection resource exceeds its cap: {field}"
            )
    boundaries = value["completed_selection_boundary_count"]
    completed = summary["completed_truncation_boundary_count"]
    if boundaries > 768:
        raise ProbeError(f"P7 D0 {label} selection boundary count exceeds schedule")
    if summary["cap_event"] is None:
        if boundaries != completed or boundaries != 768:
            raise ProbeError(
                f"P7 D0 completed {label} selection/boundary identity mismatch"
            )
    elif boundaries not in {completed, completed + 1}:
        raise ProbeError(f"P7 D0 capped {label} selection progress mismatch")


def _validate_step_link(
    value: Any, previous: Mapping[str, Any], next_step: Mapping[str, Any],
    context: str,
) -> None:
    expected = {
        "same_process", "checkpoint_or_serialized_state_used",
        "previous_step_final_term_count", "next_step_input_term_count",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ProbeError(f"malformed P7 D0 {context} link")
    if (
        value["same_process"] is not True
        or value["checkpoint_or_serialized_state_used"] is not False
    ):
        raise ProbeError(f"P7 D0 {context} link violates live-process custody")
    for key in (
        "previous_step_final_term_count", "next_step_input_term_count",
    ):
        item = value[key]
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ProbeError(f"invalid P7 D0 {context} link count")
    if (
        value["previous_step_final_term_count"]
        != value["next_step_input_term_count"]
        or value["previous_step_final_term_count"]
        != previous["final_retained_term_count"]
    ):
        raise ProbeError(f"P7 D0 {context} term-count link mismatch")
    if next_step["completed_constituent_count"] > 0 and (
        value["next_step_input_term_count"] <= 0
    ):
        raise ProbeError(f"P7 D0 {context} has an empty executed input")


def validate_public_witness(
    witness: Any, *, mode: str = PROBE_MODE,
) -> Mapping[str, Any]:
    expected_top = {
        "schema_version", "probe_type", "fixture_id", "fixture_sha256",
        "fixture_canonical_sha256", "scientific_authority",
        "certificate_eligible", "result_contract_eligible",
        "resource_observations_only", "candidate", "runtime_custody",
        "step1", "step2", "step3", "step1_to_step2_link",
        "step2_to_step3_link", "step2_selection_resources",
        "step3_selection_resources",
        "P6_prefix_resource_projection_conformed", "step3_started",
        "explicit_exclusions",
    }
    if mode != PROBE_MODE:
        raise ProbeError("P7 D0 public witness mode is not frozen")
    if not isinstance(witness, dict) or set(witness) != expected_top:
        raise ProbeError("malformed P7 D0 public witness")
    fixture_path = BASE / FIXTURE_NAME
    fixture = _validate_fixture(load_json(fixture_path))
    if (
        type(witness["schema_version"]) is not int
        or witness["schema_version"] != 1
        or witness["probe_type"] != PROBE_TYPE
        or witness["fixture_id"] != FIXTURE_ID
        or witness["fixture_sha256"] != file_sha256(fixture_path)
        or witness["fixture_canonical_sha256"] != canonical_sha256(fixture)
    ):
        raise ProbeError("unexpected P7 D0 witness identity or fixture custody")
    if witness["scientific_authority"] != "NONE":
        raise ProbeError("P7 D0 witness claims scientific authority")
    for key in ("certificate_eligible", "result_contract_eligible"):
        if witness[key] is not False:
            raise ProbeError(f"P7 D0 witness enables {key}")
    if witness["resource_observations_only"] is not True:
        raise ProbeError("P7 D0 witness is not resource-only")

    candidate = witness["candidate"]
    if not isinstance(candidate, dict) or set(candidate) != {
        "candidate_id", "probe_mode", "identity", "formal_candidate",
        "step1_path", "step2_path", "step3_path",
    }:
        raise ProbeError("malformed P7 D0 candidate identity")
    if (
        candidate["candidate_id"] != CANDIDATE_ID
        or candidate["probe_mode"] != PROBE_MODE
        or candidate["identity"] != PROBE_MODE
        or candidate["formal_candidate"] is not True
        or candidate["step1_path"] != "fixed_P3_2^-34"
        or candidate["step2_path"] != "frozen_P6_E768_MAX_LAZY37_V1"
        or candidate["step3_path"] != "full_domain_E768_MAX_LAZY37_STEP3_V1"
    ):
        raise ProbeError("P7 D0 candidate execution identity drift")
    if witness["runtime_custody"] != fixture["runtime_custody"]:
        raise ProbeError("P7 D0 runtime custody drift")
    if witness["explicit_exclusions"] != PUBLIC_EXCLUSIONS:
        raise ProbeError("P7 D0 public exclusions drift")
    for key in (
        "P6_prefix_resource_projection_conformed", "step3_started",
    ):
        if not isinstance(witness[key], bool):
            raise ProbeError(f"P7 D0 witness {key} is not boolean")

    step1 = witness["step1"]
    _validate_resource_summary(step1, "step1")
    step2 = witness["step2"]
    step3 = witness["step3"]
    link12 = witness["step1_to_step2_link"]
    link23 = witness["step2_to_step3_link"]
    selection2 = witness["step2_selection_resources"]
    selection3 = witness["step3_selection_resources"]

    if step1["cap_event"] is not None:
        if any(item is not None for item in (
            step2, step3, link12, link23, selection2, selection3,
        )):
            raise ProbeError("P7 D0 attempted work after a capped step 1")
        if (
            witness["P6_prefix_resource_projection_conformed"]
            or witness["step3_started"]
        ):
            raise ProbeError("P7 D0 capped step 1 has positive lifecycle flags")
    else:
        if (
            step1["completed_composite_count"] != 512
            or step1["completed_constituent_count"] != 1152
            or step1["completed_truncation_boundary_count"] != 768
            or step2 is None or link12 is None or selection2 is None
        ):
            raise ProbeError("P7 D0 completed step 1 lacks its step-2 continuation")
        _validate_resource_summary(step2, "step2")
        _validate_selection_resources(selection2, "step2", step2)
        _validate_step_link(link12, step1, step2, "step1-to-step2")
        if step2["cap_event"] is not None:
            if any(item is not None for item in (step3, link23, selection3)):
                raise ProbeError("P7 D0 attempted step 3 after a capped step 2")
            if (
                witness["P6_prefix_resource_projection_conformed"]
                or witness["step3_started"]
            ):
                raise ProbeError("P7 D0 capped step 2 has positive lifecycle flags")
        else:
            if (
                step2["completed_composite_count"] != 512
                or step2["completed_constituent_count"] != 1152
                or step2["completed_truncation_boundary_count"] != 768
            ):
                raise ProbeError("P7 D0 uncapped step 2 is incomplete")
            projection = {
                "step1": step1,
                "step2": step2,
                "step_link": {
                    "same_process": link12["same_process"],
                    "checkpoint_or_serialized_state_used":
                        link12["checkpoint_or_serialized_state_used"],
                    "step1_final_term_count":
                        link12["previous_step_final_term_count"],
                    "step2_input_term_count":
                        link12["next_step_input_term_count"],
                },
                "selection_resources": selection2,
            }
            prefix_matches = (
                projection == fixture["expected_P6_prefix_resource_projection"]
            )
            if not prefix_matches:
                if (
                    witness["P6_prefix_resource_projection_conformed"]
                    or witness["step3_started"]
                    or any(item is not None for item in (
                        step3, link23, selection3,
                    ))
                ):
                    raise ProbeError(
                        "P7 D0 invalid prefix conformance attempted step 3"
                    )
            else:
                if (
                    witness["P6_prefix_resource_projection_conformed"] is not True
                    or witness["step3_started"] is not True
                    or step3 is None or link23 is None or selection3 is None
                ):
                    raise ProbeError("P7 D0 conforming P6 prefix lacks step 3")
                _validate_resource_summary(step3, "step3")
                _validate_selection_resources(selection3, "step3", step3)
                _validate_step_link(link23, step2, step3, "step2-to-step3")
                if step3["cap_event"] is None and (
                    step3["completed_composite_count"] != 512
                    or step3["completed_constituent_count"] != 1152
                    or step3["completed_truncation_boundary_count"] != 768
                ):
                    raise ProbeError("P7 D0 uncapped step 3 is incomplete")

    _reject_public_scientific_vocabulary(witness)
    return witness


def _parse_time_stderr(stderr: bytes) -> dict[str, Any]:
    text = stderr.decode("utf-8", errors="replace")
    values: dict[str, Any] = {}
    keys = {
        "User time (seconds)": "user_time_seconds",
        "System time (seconds)": "system_time_seconds",
        "Elapsed (wall clock) time (h:mm:ss or m:ss)": "elapsed_wall_clock",
        "Maximum resident set size (kbytes)": "maximum_resident_set_size_KiB",
        "Minor (reclaiming a frame) page faults": "minor_page_faults",
        "Major (requiring I/O) page faults": "major_page_faults",
    }
    for line in text.splitlines():
        stripped = line.strip()
        for source, target in keys.items():
            prefix = source + ": "
            if stripped.startswith(prefix):
                raw = stripped[len(prefix):]
                values[target] = int(raw) if raw.isdigit() else raw
                break
    return values


def _terminate_scope(unit: str, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ["systemctl", "--user", "kill", "--kill-who=all", f"{unit}.scope"],
        check=False, capture_output=True,
    )
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _candidate_process_status(
    *, returncode: int | None, timed_out: bool, stdout_bytes: int,
    stderr_bytes: int, host: Mapping[str, Any],
) -> str:
    """Classify only the frozen exit protocol; never inspect child stderr."""
    if (
        timed_out
        or stdout_bytes > host["maximum_stdout_bytes"]
        or stderr_bytes > host["maximum_stderr_bytes"]
    ):
        return "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
    if returncode == INVALID_D0_PROBE_EXIT_CODE:
        return "INVALID_D0_PROBE"
    if returncode != 0:
        return "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
    return "COMPLETED_RESOURCE_OBSERVATION"


def _run_candidate(
    staging: Path, julia: Path, depot: Path,
    host: Mapping[str, Any], scratch_root: Path,
) -> dict[str, Any]:
    scratch = scratch_root / "candidate"
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    unit = (
        "majorana-p7-d0-step3-"
        + PROBE_MODE.lower().replace("_", "-")
        + "-"
        + uuid.uuid4().hex
    )
    julia_command = [
        "/usr/bin/time", "-v", str(julia), "--startup-file=no",
        "--history-file=no", "--compiled-modules=no",
        f"--project={staging / 'majorana_certificate_p0'}",
        str(staging / PROBE_DRIVER),
        str(staging / FIXTURE_NAME),
        str(staging / "majorana_certificate_p6_fixture.json"),
        str(staging / "majorana_certificate_p5_fixture.json"),
        str(staging / "majorana_certificate_p4_fixture.json"),
        str(staging / "majorana_certificate_p3_fixture.json"),
        str(staging / "majorana_certificate_p2_fixture.json"),
        PROBE_MODE,
    ]
    command = [
        "systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
        "-p", f"MemoryMax={host['MemoryMax_bytes']}",
        "-p", f"MemorySwapMax={host['MemorySwapMax_bytes']}",
        "-p", f"RuntimeMaxSec={host['RuntimeMaxSec']}",
        "--", *julia_command,
    ]
    environment = os.environ.copy()
    environment.update({
        "HOME": str(scratch / "home"),
        "TMPDIR": str(scratch / "tmp"),
        "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
        "JULIA_DEPOT_PATH": f"{scratch / 'depot'}:{depot}",
        "JULIA_LOAD_PATH": "@", "JULIA_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1", "JULIA_PKG_OFFLINE": "true",
        "JULIA_PKG_SERVER": "",
    })
    started_ns = time.monotonic_ns()
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=environment,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(
            timeout=host["outer_safety_timeout_seconds"],
        )
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_scope(unit, process)
        stdout, stderr = process.communicate()
    process_status = _candidate_process_status(
        returncode=process.returncode,
        timed_out=timed_out,
        stdout_bytes=len(stdout),
        stderr_bytes=len(stderr),
        host=host,
    )
    if process_status == "INVALID_D0_PROBE":
        raise ProbeError(
            "INVALID_D0_PROBE: frozen Julia runner rejected custody, schema, "
            "or public-output discipline"
        )
    observation: dict[str, Any] = {
        "probe_mode": PROBE_MODE,
        "candidate_id": CANDIDATE_ID,
        "process_returncode": process.returncode,
        "outer_timeout_triggered": timed_out,
        "stdout_bytes": len(stdout),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "outer_monotonic_elapsed_ns": time.monotonic_ns() - started_ns,
        "time_diagnostics": _parse_time_stderr(stderr),
        "host_failure_has_no_mathematical_authority": True,
    }
    if process_status == "INDETERMINATE_HOST_OR_RUNTIME_FAILURE":
        observation["status"] = process_status
        observation["resource_witness"] = None
        return observation
    witness = loads_json(stdout, "P7 D0 candidate stdout")
    if stdout != canonical_bytes(witness) + b"\n":
        raise ProbeError("P7 D0 candidate stdout is not canonical JSON")
    validate_public_witness(witness)
    observation["status"] = "COMPLETED_RESOURCE_OBSERVATION"
    observation["resource_witness"] = witness
    observation["resource_witness_sha256"] = canonical_sha256(witness)
    return observation


def _fixed_formal_admission(
    observation: Mapping[str, Any], policy: Mapping[str, Any],
) -> dict[str, Any]:
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    result = {
        "formal_step3_caps": fixture["deterministic_step3_probe_caps"],
        "formal_step3_selection_caps":
            fixture["deterministic_step3_selection_probe_caps"],
        "formal_host_caps": fixture["host_supervisor_caps"],
        "derived_from_observation": False,
        "same_as_D0_admission": True,
    }
    if observation.get("status") != "COMPLETED_RESOURCE_OBSERVATION":
        result["status"] = (
            "NOT_ESTABLISHED_INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
        )
        return result
    witness = observation.get("resource_witness")
    if not isinstance(witness, dict):
        raise ProbeError("completed P7 D0 observation lacks a witness")
    if witness["step1"]["cap_event"] is not None:
        result["status"] = "NOT_ESTABLISHED_DETERMINISTIC_STEP1_CAP"
    elif witness["step2"]["cap_event"] is not None:
        result["status"] = "NOT_ESTABLISHED_DETERMINISTIC_STEP2_CAP"
    elif witness["P6_prefix_resource_projection_conformed"] is not True:
        result["status"] = (
            "NOT_ESTABLISHED_INVALID_PREFIX_RESOURCE_CONFORMANCE"
        )
    elif witness["step3"]["cap_event"] is not None:
        result["status"] = "NOT_ESTABLISHED_DETERMINISTIC_STEP3_CAP"
    elif (
        witness["P6_prefix_resource_projection_conformed"] is True
        and witness["step3_started"] is True
    ):
        result["status"] = "ESTABLISHED_FOR_FUTURE_S0_PRECOMMIT"
    else:
        raise ProbeError("P7 D0 completed witness has an invalid admission truth state")
    return result


def _validate_preprobe_commit_identity(preprobe_commit: Any) -> None:
    if (
        not isinstance(preprobe_commit, str)
        or len(preprobe_commit) != 40
        or any(
            character not in "0123456789abcdef"
            for character in preprobe_commit
        )
    ):
        raise ProbeError("P7 D0 preprobe commit is not a full lowercase SHA-1")
    try:
        ancestry = _run_git("rev-list", "--parents", "-n", "1", preprobe_commit)
    except subprocess.CalledProcessError as error:
        raise ProbeError("P7 D0 preprobe commit is not present") from error
    if ancestry.split() != [preprobe_commit, DIRECT_PARENT]:
        raise ProbeError("P7 D0 preprobe commit has the wrong direct parent")
    changed = set(filter(None, _run_git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", preprobe_commit,
    ).splitlines()))
    if changed != PREPROBE_CHANGED_PATHS:
        raise ProbeError("P7 D0 preprobe changed-path allowlist drift")
    artifact = f"{preprobe_commit}:docs/research/fermion-frontier/{REPORT_NAME}"
    if subprocess.run(
        ["git", "cat-file", "-e", artifact], cwd=BASE,
        check=False, capture_output=True,
    ).returncode == 0:
        raise ProbeError("P7 D0 report exists in the preprobe commit")


def _validate_preprobe_commit(preprobe_commit: str) -> None:
    _validate_preprobe_commit_identity(preprobe_commit)
    if _run_git("rev-parse", "HEAD") != preprobe_commit:
        raise ProbeError("P7 D0 HEAD differs from requested preprobe commit")
    if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ProbeError("P7 D0 worktree is not clean before execution")


def run_probe(
    preprobe_commit: str, julia: Path, depot: Path, output: Path,
) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=True)
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    _validate_preprobe_commit(preprobe_commit)
    julia = Path(julia).resolve()
    depot = Path(depot).resolve()
    if (
        not julia.is_file()
        or file_sha256(julia)
        != fixture["runtime_custody"]["julia_executable_sha256"]
    ):
        raise ProbeError("P7 D0 Julia executable custody mismatch")
    if not depot.is_dir():
        raise ProbeError("P7 D0 depot is missing")
    for executable in ("systemd-run", "systemctl", "/usr/bin/time"):
        if shutil.which(executable) is None:
            raise ProbeError(f"P7 D0 missing required executable: {executable}")

    with tempfile.TemporaryDirectory(prefix="majorana-p7-d0-") as temporary:
        root = Path(temporary)
        staging = root / "staging"
        staging.mkdir()
        staging_manifest = stage_probe_tree(staging, policy)
        scratch = root / "scratch"
        scratch.mkdir()
        observation = _run_candidate(
            staging, julia, depot, fixture["host_supervisor_caps"], scratch,
        )

    admission = _fixed_formal_admission(observation, policy)
    report = {
        "schema_version": 1,
        "report_type": REPORT_TYPE,
        "policy_id": policy["policy_id"],
        "policy_sha256": file_sha256(BASE / POLICY_NAME),
        "fixture_id": FIXTURE_ID,
        "fixture_sha256": file_sha256(BASE / FIXTURE_NAME),
        "fixture_canonical_sha256": canonical_sha256(fixture),
        "preprobe_commit_sha": preprobe_commit,
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "formal_candidate_was_frozen_before_probe": CANDIDATE_ID,
        "staging_manifest": staging_manifest,
        "staging_manifest_sha256": canonical_sha256(staging_manifest),
        "host_caps": fixture["host_supervisor_caps"],
        "observations": [observation],
        "fixed_formal_admission": admission,
        "authority_exclusions": policy["authority_exclusions"],
    }
    validate_report(report)
    write_canonical_json(output, report)
    return report


def _validate_staging_manifest(
    rows: Any, policy: Mapping[str, Any], expected_sha256: Any,
) -> None:
    if not isinstance(rows, list) or len(rows) != 13:
        raise ProbeError("P7 D0 staging manifest must contain exactly 13 paths")
    if any(not isinstance(row, dict) for row in rows):
        raise ProbeError("malformed P7 D0 staging row")
    if [row.get("relative_path") for row in rows] != list(STAGED_PATHS):
        raise ProbeError("P7 D0 staging manifest order drift")
    pins = _source_pins(policy)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "repository_sha256", "staged_size_bytes",
            "staged_sha256", "byte_identical_to_repository",
        }:
            raise ProbeError("malformed P7 D0 staging row")
        relative = row["relative_path"]
        if (
            not isinstance(row["staged_size_bytes"], int)
            or isinstance(row["staged_size_bytes"], bool)
            or row["staged_size_bytes"] < 0
        ):
            raise ProbeError("invalid P7 D0 staged size")
        for key in ("repository_sha256", "staged_sha256"):
            if (
                not isinstance(row[key], str)
                or len(row[key]) != 64
                or any(character not in "0123456789abcdef" for character in row[key])
            ):
                raise ProbeError("invalid P7 D0 staging digest")
        body = (BASE / relative).read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        if (
            row["repository_sha256"] != pins[relative]["sha256"]
            or row["staged_size_bytes"] != len(body)
            or row["staged_sha256"] != digest
            or row["staged_sha256"] != row["repository_sha256"]
            or row["byte_identical_to_repository"] is not True
        ):
            raise ProbeError("P7 D0 staging is not byte-identical")
    if expected_sha256 != canonical_sha256(rows):
        raise ProbeError("P7 D0 staging manifest hash mismatch")


def _validate_time_diagnostics(value: Any, *, completed: bool) -> None:
    if (not isinstance(value, dict) or not set(value) <= TIME_DIAGNOSTIC_KEYS
            or (completed and set(value) != TIME_DIAGNOSTIC_KEYS)):
        raise ProbeError("malformed P7 D0 time diagnostics")
    for key, item in value.items():
        if key in {
            "maximum_resident_set_size_KiB", "minor_page_faults",
            "major_page_faults",
        }:
            if (not isinstance(item, int) or isinstance(item, bool) or item < 0):
                raise ProbeError(f"invalid P7 D0 time diagnostic: {key}")
        elif not isinstance(item, str) or not item:
            raise ProbeError(f"invalid P7 D0 time diagnostic: {key}")
        elif key in {"user_time_seconds", "system_time_seconds"} and not (
            re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", item)
        ):
            raise ProbeError(f"invalid P7 D0 time diagnostic format: {key}")
        elif key == "elapsed_wall_clock" and not re.fullmatch(
            r"(?:[0-9]+:)?[0-9]+:[0-5][0-9](?:\.[0-9]+)?", item,
        ):
            raise ProbeError("invalid P7 D0 elapsed-wall-clock format")
    _reject_public_scientific_vocabulary(value, "$.time_diagnostics")


def _validate_observation(
    row: Any, host: Mapping[str, Any],
) -> None:
    common = {
        "probe_mode", "candidate_id", "process_returncode",
        "outer_timeout_triggered", "stdout_bytes", "stdout_sha256",
        "stderr_bytes", "stderr_sha256", "outer_monotonic_elapsed_ns",
        "time_diagnostics", "host_failure_has_no_mathematical_authority",
        "status", "resource_witness",
    }
    completed = (
        isinstance(row, dict)
        and row.get("status") == "COMPLETED_RESOURCE_OBSERVATION"
    )
    expected = common | ({"resource_witness_sha256"} if completed else set())
    if not isinstance(row, dict) or set(row) != expected:
        raise ProbeError("malformed P7 D0 observation")
    if (
        row["probe_mode"] != PROBE_MODE
        or row["candidate_id"] != CANDIDATE_ID
    ):
        raise ProbeError("P7 D0 observation identity drift")
    if row["host_failure_has_no_mathematical_authority"] is not True:
        raise ProbeError("P7 D0 host failure claims authority")
    if (not isinstance(row["process_returncode"], int)
            or isinstance(row["process_returncode"], bool)):
        raise ProbeError("invalid P7 D0 process return code")
    if not isinstance(row["outer_timeout_triggered"], bool):
        raise ProbeError("invalid P7 D0 timeout flag")
    for key in (
        "stdout_bytes", "stderr_bytes", "outer_monotonic_elapsed_ns",
    ):
        if (not isinstance(row[key], int) or isinstance(row[key], bool)
                or row[key] < 0):
            raise ProbeError("invalid P7 D0 observation resource value")
    if row["outer_monotonic_elapsed_ns"] <= 0:
        raise ProbeError("invalid P7 D0 nonpositive elapsed time")
    for key in ("stdout_sha256", "stderr_sha256"):
        if (not isinstance(row[key], str) or len(row[key]) != 64
                or any(character not in "0123456789abcdef" for character in row[key])):
            raise ProbeError("invalid P7 D0 observation digest")
    _validate_time_diagnostics(row["time_diagnostics"], completed=completed)
    host_failed = (
        row["outer_timeout_triggered"]
        or row["process_returncode"] != 0
        or row["stdout_bytes"] > host["maximum_stdout_bytes"]
        or row["stderr_bytes"] > host["maximum_stderr_bytes"]
        or row["outer_monotonic_elapsed_ns"] > (
            host["outer_safety_timeout_seconds"] * 1_000_000_000
        )
    )
    if completed:
        witness = validate_public_witness(row["resource_witness"])
        if row["resource_witness_sha256"] != canonical_sha256(witness):
            raise ProbeError("P7 D0 resource witness hash mismatch")
        stdout = canonical_bytes(witness) + b"\n"
        if (row["stdout_bytes"] != len(stdout)
                or row["stdout_sha256"] != hashlib.sha256(stdout).hexdigest()):
            raise ProbeError("P7 D0 stdout/resource witness custody mismatch")
        if host_failed:
            raise ProbeError("completed P7 D0 observation has host failure")
    elif row["status"] == "INDETERMINATE_HOST_OR_RUNTIME_FAILURE":
        if row["resource_witness"] is not None:
            raise ProbeError("indeterminate P7 D0 observation retained a witness")
        if not host_failed:
            raise ProbeError("P7 D0 host-failure status has no host failure")
    else:
        raise ProbeError("unexpected P7 D0 observation status")


def validate_report(report: Any) -> Mapping[str, Any]:
    policy = validate_policy(
        load_json(BASE / POLICY_NAME), require_report_absent=False,
    )
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    expected_top = {
        "schema_version", "report_type", "policy_id", "policy_sha256",
        "fixture_id", "fixture_sha256", "fixture_canonical_sha256",
        "preprobe_commit_sha", "scientific_authority", "certificate_eligible",
        "formal_candidate_was_frozen_before_probe", "staging_manifest",
        "staging_manifest_sha256", "host_caps", "observations",
        "fixed_formal_admission", "authority_exclusions",
    }
    if not isinstance(report, dict) or set(report) != expected_top:
        raise ProbeError("malformed P7 D0 report")
    if (
        type(report.get("schema_version")) is not int
        or report["schema_version"] != 1
        or report["report_type"] != REPORT_TYPE
        or report["policy_id"] != POLICY_ID
        or report["fixture_id"] != FIXTURE_ID
    ):
        raise ProbeError("unexpected P7 D0 report identity")
    if (
        report["policy_sha256"] != file_sha256(BASE / POLICY_NAME)
        or report["fixture_sha256"] != file_sha256(BASE / FIXTURE_NAME)
        or report["fixture_canonical_sha256"] != canonical_sha256(fixture)
    ):
        raise ProbeError("P7 D0 report source custody mismatch")
    if (
        report["scientific_authority"] != "NONE"
        or report["certificate_eligible"] is not False
    ):
        raise ProbeError("P7 D0 report exceeds resource-only authority")
    _validate_preprobe_commit_identity(report["preprobe_commit_sha"])
    if report["host_caps"] != fixture["host_supervisor_caps"]:
        raise ProbeError("P7 D0 report host admission drift")
    _validate_staging_manifest(
        report["staging_manifest"], policy,
        report["staging_manifest_sha256"],
    )
    observations = report["observations"]
    if (
        not isinstance(observations, list)
        or len(observations) != 1
        or observations[0].get("probe_mode") != PROBE_MODE
    ):
        raise ProbeError("P7 D0 report must contain the sole frozen observation")
    _validate_observation(observations[0], fixture["host_supervisor_caps"])
    expected_admission = _fixed_formal_admission(observations[0], policy)
    if report["fixed_formal_admission"] != expected_admission:
        raise ProbeError("P7 D0 fixed formal admission drift")
    if (
        report["fixed_formal_admission"]["formal_host_caps"]
        != fixture["host_supervisor_caps"]
        or report["fixed_formal_admission"]["derived_from_observation"] is not False
        or report["fixed_formal_admission"]["same_as_D0_admission"] is not True
    ):
        raise ProbeError("P7 D0 admission is observation-derived")
    if report["authority_exclusions"] != policy["authority_exclusions"]:
        raise ProbeError("P7 D0 report authority exclusions drift")
    if report["formal_candidate_was_frozen_before_probe"] != CANDIDATE_ID:
        raise ProbeError("P7 D0 report formal candidate drift")
    return report


def lazy_reference_select(
    rows: Sequence[Mapping[str, int]], available: int,
) -> list[Mapping[str, int]]:
    """Small-model reference for the exact lazy/full-domain prefix identity."""
    if available < 0:
        raise ProbeError("negative lazy-reference amount")
    threshold_bits = 0x3DA0000000000000
    key = lambda row: (
        int(row["point_abs_ticks"]), int(row["abs_bits"]), int(row["mask"]),
    )
    tier1 = sorted(
        (row for row in rows if int(row["abs_bits"]) < threshold_bits),
        key=key,
    )
    selected: list[Mapping[str, int]] = []
    remaining = available
    for row in tier1:
        cost = int(row["point_abs_ticks"])
        if cost > remaining:
            return selected
        selected.append(row)
        remaining -= cost
    if remaining == 0:
        return selected
    tier2 = sorted(
        (
            row for row in rows
            if int(row["abs_bits"]) >= threshold_bits
            and int(row["point_abs_ticks"]) <= remaining
        ),
        key=key,
    )
    for row in tier2:
        cost = int(row["point_abs_ticks"])
        if cost > remaining:
            break
        selected.append(row)
        remaining -= cost
    return selected


def brute_force_reference_select(
    rows: Sequence[Mapping[str, int]], available: int,
) -> list[Mapping[str, int]]:
    if available < 0:
        raise ProbeError("negative brute-force amount")
    ordered = sorted(rows, key=lambda row: (
        int(row["point_abs_ticks"]), int(row["abs_bits"]), int(row["mask"]),
    ))
    result: list[Mapping[str, int]] = []
    remaining = available
    for row in ordered:
        cost = int(row["point_abs_ticks"])
        if cost > remaining:
            break
        result.append(row)
        remaining -= cost
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-preprobe", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--verify-report", action="store_true")
    parser.add_argument("--preprobe-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--output", type=Path, default=BASE / REPORT_NAME)
    args = parser.parse_args(argv)
    selected = sum(map(int, (args.verify_preprobe, args.run, args.verify_report)))
    if selected != 1:
        parser.error("select exactly one operation")
    if args.verify_preprobe:
        policy = validate_policy(
            load_json(BASE / POLICY_NAME), require_report_absent=True,
        )
        summary = {
            "status": "VERIFIED_P7_D0_PREPROBE",
            "policy_id": policy["policy_id"],
        }
    elif args.run:
        if not all((args.preprobe_commit, args.julia, args.depot)):
            parser.error("run requires preprobe commit, Julia, and depot")
        report = run_probe(args.preprobe_commit, args.julia, args.depot, args.output)
        summary = {
            "status": "COMPLETED_P7_D0_RESOURCE_PROBE",
            "report_sha256": file_sha256(args.output),
            "observation_statuses": [row["status"] for row in report["observations"]],
            "fixed_formal_admission_status":
                report["fixed_formal_admission"]["status"],
        }
    else:
        report = validate_report(load_json(args.output))
        if args.output.read_bytes() != canonical_bytes(report) + b"\n":
            raise ProbeError("P7 D0 report is not canonical JSON plus newline")
        summary = {
            "status": "VERIFIED_P7_D0_RESOURCE_REPORT",
            "report_sha256": file_sha256(args.output),
            "fixed_formal_admission_status":
                report["fixed_formal_admission"]["status"],
        }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
