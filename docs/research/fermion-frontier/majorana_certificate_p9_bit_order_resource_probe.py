#!/usr/bin/env python3
"""Run and verify the non-authoritative Majorana P9 D0 resource probe."""

from __future__ import annotations

import argparse
import ast
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
POLICY_NAME = "majorana_certificate_p9_bit_order_resource_probe_policy.json"
FIXTURE_NAME = "majorana_certificate_p9_bit_order_resource_probe_fixture.json"
REPORT_NAME = "majorana_certificate_p9_bit_order_resource_probe_report.json"
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
    "majorana_certificate_p9_bit_order_resource_probe/"
    "majorana_p9_bit_order_step3_resource_probe.jl"
)
TEST_NAME = "test_majorana_certificate_p9_bit_order_resource_probe.py"
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
    "docs/research/fermion-frontier/test_majorana_certificate_p9_bit_order_resource_probe.py",
})
RESULT_ARTIFACTS = (
    REPORT_NAME,
    "majorana_certificate_p9_fixture.json",
    "majorana_certificate_p9_policy.json",
    "majorana_certificate_p9_precommit_contract.json",
    "majorana_certificate_p9_contract.json",
    "majorana_certificate_p9_certificate.json",
    "test_majorana_certificate_p9_result.py",
)

POLICY_ID = "MAJORANA-P9-STEP3-E768-BITORDER-D0-V1"
POLICY_SEMANTIC_SHA256 = (
    "f6e28904d836a625f1383daf98598b9ff9936865b11511d9293f1ef43efa0569"
)
FIXTURE_ID = "MAJORANA-P9-STEP3-E768-BITORDER-D0-V1"
REPORT_TYPE = "majorana_p9_step3_e768_bitorder_resource_report_d0_v1"
PROBE_TYPE = "majorana_p9_step3_e768_bitorder_resource_probe_d0_v1"
DIRECT_PARENT = "5dcb03990037e47dd48c8166712df9855c91ed67"
PROBE_MODE = "E768_BITORDER_STEP3_V1"
CANDIDATE_ID = "E768-BITORDER-STEP3-V1"
MODE_ORDER = (PROBE_MODE,)
P8_A_RESULT_COMMIT = "5cf53d73c4e375d9c8159cb7a742b4c22edd9622"
P8_A_REPORT_PATH = (
    "docs/research/fermion-frontier/"
    "majorana_certificate_p8_selector_equivalence_report.json"
)
P8_A_REPORT_SHA256 = (
    "014148df4be0f1c234456a5d0a09fb84dc7cb25d91d6d67e0d7f5ff66e3bb97a"
)
P8_A_REPORT_SIZE_BYTES = 3668
P8_B_RESULT_COMMIT = DIRECT_PARENT
P8_B_REPORT_PATH = (
    "docs/research/fermion-frontier/"
    "majorana_certificate_p8_selector_equivalence_independent_audit_report.json"
)
P8_B_REPORT_SHA256 = (
    "b47b8379f88deb2507df89996e113df10faff795e9eb814c254065ba66ef7828"
)
P8_B_REPORT_SIZE_BYTES = 2619
D4_RESULT_COMMIT = "c82e2443dfae07af17cb9108ccb344c2f0cbebba"
D4_REPORT_PATH = (
    "docs/research/fermion-frontier/"
    "majorana_certificate_p7_d4_e_per_composite_probe_report.json"
)
D4_REPORT_SHA256 = (
    "269e74dd23c33b0e2d1943d7f25e44ebcd897bdde1a96645a80eba4cf4e5da19"
)
D4_REPORT_SIZE_BYTES = 11822

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
P6_SELECTION_RESOURCE_KEYS = {
    "total_ranking_scan_term_visits", "total_sort_work_items",
    "total_tick_evaluations", "total_selected_membership_insertions",
    "peak_ranking_buffer_terms", "total_selection_work_units",
    "completed_selection_boundary_count",
}
P9_SELECTION_RESOURCE_KEYS = {
    "total_snapshot_scan_term_visits",
    "total_bit_order_sort_input_items",
    "total_lazy_tick_evaluations",
    "total_selected_membership_insertions",
    "peak_bit_order_sort_input_terms",
    "total_bit_order_selection_work_units",
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
    "maximum_snapshot_scan_term_visits",
    "maximum_bit_order_sort_input_items",
    "maximum_lazy_tick_evaluations",
    "maximum_peak_bit_order_sort_input_terms",
    "maximum_total_bit_order_selection_work_units",
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
P9_SELECTION_NUMERIC_CAP_KEYS = {
    "maximum_snapshot_scan_term_visits",
    "maximum_bit_order_sort_input_items",
    "maximum_lazy_tick_evaluations",
    "maximum_selected_membership_insertions",
    "maximum_peak_bit_order_sort_input_terms",
    "maximum_total_bit_order_selection_work_units",
}


class ProbeError(RuntimeError):
    """Fail-closed P9 D0 validation error."""


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


def _read_fixed_git_object(
    commit: str, relative_path: str, expected_sha256: str,
    expected_size_bytes: int, label: str,
) -> Any:
    """Read one declared historical input directly from its Git object."""
    process = subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=BASE, check=False, capture_output=True,
    )
    if process.returncode != 0:
        raise ProbeError(f"P9 missing fixed {label} Git object")
    body = process.stdout
    if (
        len(body) != expected_size_bytes
        or hashlib.sha256(body).hexdigest() != expected_sha256
    ):
        raise ProbeError(f"P9 fixed {label} Git-object custody drift")
    return loads_json(body, f"{label} Git object")


def _validate_fixed_upstream_custody() -> None:
    """Accept only the minimal P8/D4 projections declared by the P9 fixture."""
    p8_a = _read_fixed_git_object(
        P8_A_RESULT_COMMIT, P8_A_REPORT_PATH, P8_A_REPORT_SHA256,
        P8_A_REPORT_SIZE_BYTES, "P8-A report",
    )
    try:
        p8_a_projection = {
            "report_type": p8_a["report_type"],
            "scientific_authority": p8_a["scientific_authority"],
            "certificate_eligible": p8_a["certificate_eligible"],
            "result_contract_eligible": p8_a["result_contract_eligible"],
            "status": p8_a["status"],
            "assumptions": p8_a["proof"]["assumptions"],
            "selector_lemma": p8_a["proof"]["lemma"][
                "bit_order_and_full_domain_successful_selection_"
                "membership_and_cost_total_are_equal"
            ],
            "nonclaims": p8_a["proof"]["nonclaims"],
        }
    except (KeyError, TypeError) as error:
        raise ProbeError("P9 fixed P8-A projection is malformed") from error
    if p8_a_projection != {
        "report_type": "majorana_p8_a_selector_bit_order_equivalence_report_v2",
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "result_contract_eligible": False,
        "status": "VERIFIED_CONDITIONAL_P8_A_SELECTOR_EQUIVALENCE",
        "assumptions": [
            "finite_immutable_snapshot_with_unique_unsigned_masks",
            "P3_exact_point_abs_ticks_and_no_BigInt_cap_exception",
            "same_nonnegative_BigInt_available_budget_and_same_P6_K37_threshold",
            "P6_rank_key_is_point_cost_then_abs_bits_then_unsigned_mask",
            "tier2_rescans_the_same_snapshot_and_includes_every_cost_not_exceeding_tier1_remaining_budget",
        ],
        "selector_lemma": True,
        "nonclaims": [
            "no_resource_consumption_equivalence",
            "no_cap_path_equivalence",
            "no_host_or_performance_claim",
            "no_D4_interruption_cause_inference",
            "no_S0_or_step3_scientific_claim",
        ],
    }:
        raise ProbeError("P9 fixed P8-A proof-scope projection drift")

    p8_b = _read_fixed_git_object(
        P8_B_RESULT_COMMIT, P8_B_REPORT_PATH, P8_B_REPORT_SHA256,
        P8_B_REPORT_SIZE_BYTES, "P8-B report",
    )
    try:
        p8_b_projection = {
            "report_type": p8_b["report_type"],
            "scientific_authority": p8_b["scientific_authority"],
            "certificate_eligible": p8_b["certificate_eligible"],
            "result_contract_eligible": p8_b["result_contract_eligible"],
            "status": p8_b["status"],
            "selector_semantics": p8_b["independent_verification"][
                "selector_semantics"
            ],
            "proof_scope": p8_b["proof_scope"],
        }
    except (KeyError, TypeError) as error:
        raise ProbeError("P9 fixed P8-B projection is malformed") from error
    if p8_b_projection != {
        "report_type": "majorana_p8_b_independent_selector_audit_report_v1",
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "result_contract_eligible": False,
        "status": "VERIFIED_INDEPENDENT_P8_A_SELECTOR_EQUIVALENCE_AUDIT",
        "selector_semantics": "membership_and_selected_cost_total_only",
        "proof_scope": {
            "P8_B_compares_only_selector_membership_and_selected_cost_total": True,
            "P8_B_does_not_establish_a_D4_cause_S0_step3_or_physical_result": True,
            "P8_B_does_not_establish_resource_cap_host_or_performance_equivalence": True,
            "P8_B_does_not_execute_or_change_the_P7_candidate": True,
            "P8_B_does_not_import_or_execute_the_P8_A_producer": True,
            "P8_B_is_an_independent_Git_object_only_audit": True,
        },
    }:
        raise ProbeError("P9 fixed P8-B proof-scope projection drift")

    d4 = _read_fixed_git_object(
        D4_RESULT_COMMIT, D4_REPORT_PATH, D4_REPORT_SHA256,
        D4_REPORT_SIZE_BYTES, "D4 report",
    )
    try:
        d4_projection = {
            "report_type": d4["report_type"],
            "scientific_authority": d4["scientific_authority"],
            "certificate_eligible": d4["certificate_eligible"],
            "result_contract_eligible": d4["result_contract_eligible"],
            "instrumented_kernel_custody": {
                "frozen_P6_function_slice_sha256":
                    d4["instrumented_kernel_custody"][
                        "frozen_P6_function_slice_sha256"
                    ],
                "frozen_P6_runner_sha256":
                    d4["instrumented_kernel_custody"][
                        "frozen_P6_runner_sha256"
                    ],
            },
        }
    except (KeyError, TypeError) as error:
        raise ProbeError("P9 fixed D4 projection is malformed") from error
    if d4_projection != {
        "report_type": "majorana_p7_step3_e768_max_lazy37_e_per_composite_report_d4_v2",
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "result_contract_eligible": False,
        "instrumented_kernel_custody": {
            "frozen_P6_function_slice_sha256": (
                "a0a7f956540c602ea3f33424eee0b89189e35eb3f7a12941e556143576693f25"
            ),
            "frozen_P6_runner_sha256": (
                "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c"
            ),
        },
    }:
        raise ProbeError("P9 fixed D4 custody projection drift")


def _source_pins(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = policy.get("source_files")
    if not isinstance(rows, list) or not rows:
        raise ProbeError("P9 D0 source_files is empty or malformed")
    pins: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "size_bytes", "sha256",
        }:
            raise ProbeError("malformed P9 D0 source pin")
        relative = row["relative_path"]
        if not isinstance(relative, str) or relative in pins:
            raise ProbeError("duplicate or invalid P9 D0 source pin")
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
        STEP3_NUMERIC_CAP_KEYS, "P9 D0 step-3 cap",
    )


def _selection_cap_limits_from_fixture(
    fixture: Mapping[str, Any],
) -> dict[str, int]:
    return _positive_cap_subset(
        fixture.get("deterministic_step3_bit_order_selection_probe_caps"),
        P9_SELECTION_NUMERIC_CAP_KEYS, "P9 D0 bit-order selection cap",
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
    _validate_runtime_custody_shape(runtime, "P9 D0 policy")
    path = BASE / RUNTIME_LOCK_NAME
    if not path.is_file() or path.is_symlink():
        raise ProbeError("P9 D0 runtime lock is missing or nonregular")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != RUNTIME_LOCK_SHA256:
        raise ProbeError("P9 D0 runtime-lock bytes SHA-256 mismatch")
    lock = loads_json(body, str(path))
    if (
        not isinstance(lock, dict)
        or lock.get("schema_version") != 1
        or lock.get("runtime_lock_id") != RUNTIME_LOCK_ID
    ):
        raise ProbeError("P9 D0 runtime-lock identity drift")
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
        raise ProbeError("P9 D0 runtime-lock closure custody is malformed") from error
    if executable_sha256 != runtime["julia_executable_sha256"]:
        raise ProbeError("P9 D0 runtime-lock Julia executable drift")
    if majorana_closure != runtime["MajoranaPropagation_source_tree_closure"]:
        raise ProbeError("P9 D0 MajoranaPropagation closure custody drift")
    if pauli_closure != runtime["PauliPropagation_source_tree_closure"]:
        raise ProbeError("P9 D0 PauliPropagation closure custody drift")


def _require_exact_keys(value: Any, expected: set[str], context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ProbeError(f"{context} key set drift")
    return value


def _validate_fixture(fixture: Any) -> Mapping[str, Any]:
    expected_keys = {
        "schema_version", "fixture_id", "required_direct_parent_commit",
        "scientific_authority", "certificate_eligible",
        "result_contract_eligible", "scope", "candidate_design",
        "frozen_P6_prefix", "step3_adaptive_rule", "bit_order_selector",
        "outward_arithmetic", "deterministic_step3_probe_caps",
        "deterministic_step3_bit_order_selection_probe_caps",
        "host_supervisor_caps", "runtime_custody",
        "required_base_fixture_sha256",
        "expected_P6_prefix_resource_projection",
        "P8_selector_semantics_custody", "D4_route_custody",
    }
    _require_exact_keys(fixture, expected_keys, "P9 D0 fixture")
    if (
        fixture["schema_version"] != 1
        or fixture["fixture_id"] != FIXTURE_ID
        or fixture["required_direct_parent_commit"] != DIRECT_PARENT
        or fixture["scientific_authority"] != "NONE"
        or fixture["certificate_eligible"] is not False
        or fixture["result_contract_eligible"] is not False
    ):
        raise ProbeError("P9 D0 fixture identity or authority drift")

    scope = fixture["scope"]
    if (
        not isinstance(scope, dict)
        or scope.get("D0_formal_finalizer_privacy") != FINALIZER_PRIVACY
        or scope.get("checkerboard_Neel_expectation")
        != CHECKERBOARD_NEEL_SCOPE
        or scope.get("P9_is_a_new_step3_candidate_not_a_P7_modification")
        is not True
        or scope.get(
            "P9_preserves_the_frozen_P6_step1_step2_resource_projection_before_step3"
        ) is not True
        or scope.get(
            "P8_selector_semantics_does_not_authorize_resource_or_scientific_claims"
        ) is not True
        or scope.get(
            "P9_step3_resource_result_does_not_establish_S0_or_a_physical_result"
        ) is not True
    ):
        raise ProbeError("P9 D0 scope firewall drift")

    design = fixture["candidate_design"]
    if not isinstance(design, dict) or (
        design.get("probe_mode_order") != [PROBE_MODE]
        or design.get("formal_candidates") != [CANDIDATE_ID]
        or design.get("formal_candidate_count") != 1
        or design.get("candidate_id") != CANDIDATE_ID
        or design.get("probe_mode") != PROBE_MODE
        or design.get("algorithm_id")
        != "MAJORANA-P9-E768-BITORDER-STEP3-V1"
        or design.get("control_candidate") is not None
        or design.get("design_disclosure")
        != "P8_A_AND_P8_B_PROOF_SCOPE_INFORMED_P9_RESULT_UNPINNED"
        or design.get(
            "fixed_execution_chain"
        ) != (
            "O0_then_P3_2^-34_step1_then_frozen_P6_E768_MAX_LAZY37_step2_"
            "then_live_deepcopy_then_E768_BITORDER_step3"
        )
    ):
        raise ProbeError("P9 D0 fixture candidate identity drift")
    for key in (
        "all_three_steps_execute_in_one_process",
        "step1_to_step2_uses_a_live_deepcopy",
        "step2_to_step3_uses_a_live_deepcopy",
        "checkpoint_serialization_or_cross_process_resume_forbidden",
        "candidate_or_budget_grid_forbidden",
        "formal_candidate_is_frozen_before_any_P9_probe_output",
        "P6_observed_local_slack_is_not_a_step3_budget_input",
    ):
        if design.get(key) is not True:
            raise ProbeError(f"P9 D0 fixture candidate custody drift: {key}")
    if design.get("allowed_P8_design_inputs") != [
        "P8_A_successful_selector_membership_and_selected_cost_total_lemma_under_its_explicit_preconditions",
        "P8_B_independent_Git_object_bound_selector_semantics_audit_scope",
    ]:
        raise ProbeError("P9 D0 P8 design-input allowlist drift")
    forbidden_design = design.get("forbidden_P9_design_inputs")
    if (
        not isinstance(forbidden_design, list)
        or "any_P8_resource_cap_host_or_performance_claim" not in forbidden_design
        or "any_D4_phase_event_timing_return_code_memory_or_causal_interpretation"
        not in forbidden_design
    ):
        raise ProbeError("P9 D0 design firewall permits P8/D4 overreach")

    rule = fixture["step3_adaptive_rule"]
    grid = 1 << 128
    strict_max = (grid - 1) // 400000
    cumulative_max = (3 * grid - 1) // 400000
    if not isinstance(rule, dict) or (
        rule.get("algorithm_id") != "MAJORANA-P9-E768-BITORDER-STEP3-V1"
        or rule.get("mapped_step_index") != 3
        or rule.get("grid_denominator") != str(grid)
        or rule.get("local_allocation_denominator") != 400000
        or rule.get("local_allocation") != "1/400000"
        or rule.get("maximum_strictly_legal_local_ticks") != str(strict_max)
        or rule.get("local_boundary_count") != 768
        or rule.get("local_raw_boundary_indices") != "0_through_767"
        or rule.get("global_raw_boundary_indices") != "1536_through_2303"
        or rule.get("prefix_target_formula")
        != "floor((q*maximum_strictly_legal_local_ticks)/768)"
        or rule.get("future_S0_maximum_strictly_legal_cumulative_ticks")
        != str(cumulative_max)
        or rule.get("allocation_equality_is_failure") is not True
        or rule.get(
            "P8_conditional_semantics_is_not_a_resource_or_host_equivalence_claim"
        ) is not True
    ):
        raise ProbeError("P9 D0 step-3 rule drift")
    if rule.get("ranking_key") != [
        "sign_cleared_binary64_magnitude_bits_ascending",
        "unsigned_majorana_mask_ascending",
    ] or rule.get("semantic_reference_rank_key") != [
        "exact_point_abs_ticks_ascending",
        "sign_cleared_binary64_magnitude_bits_ascending",
        "unsigned_majorana_mask_ascending",
    ]:
        raise ProbeError("P9 D0 bit-order/reference rank contract drift")

    selector = fixture["bit_order_selector"]
    if not isinstance(selector, dict) or (
        selector.get("selector_order")
        != "(sign_cleared_binary64_magnitude_bits,unsigned_majorana_mask)"
        or selector.get("exact_point_cost")
        != "ceil(2^128*abs(exact_finite_Float64))"
    ):
        raise ProbeError("P9 D0 bit-order selector identity drift")
    for key in (
        "finite_Float64_snapshot_required",
        "immutable_unique_unsigned_mask_snapshot_required",
        "first_unaffordable_positive_cost_stops_without_skipping",
        "zero_cost_rows_are_selected_at_zero_available_ticks",
        "P6_K37_is_a_frozen_callback_anchor_only_not_a_selector_tier",
        "callback_only_tests_precomputed_membership",
        "callback_iteration_order_cannot_consume_budget",
        "callback_revalidates_selected_coefficient_bits",
        "prepare_helper_reads_but_never_mutates_live_merged_main_or_authoritative_ticks",
        "all_deletions_are_performed_only_by_the_existing_truncate_callback",
        "existing_drop_ledger_is_the_only_authoritative_drop_charge",
        "existing_drop_ledger_recomputes_and_must_equal_the_selection_cost",
        "P8_does_not_establish_Julia_resource_cap_or_host_equivalence",
    ):
        if selector.get(key) is not True:
            raise ProbeError(f"P9 D0 bit-order selector drift: {key}")

    _step_cap_limits_from_fixture(fixture)
    selection_caps = _selection_cap_limits_from_fixture(fixture)
    if selection_caps != {
        "maximum_snapshot_scan_term_visits": 1073741824,
        "maximum_bit_order_sort_input_items": 1073741824,
        "maximum_lazy_tick_evaluations": 1073741824,
        "maximum_selected_membership_insertions": 1073741824,
        "maximum_peak_bit_order_sort_input_terms": 1048576,
        "maximum_total_bit_order_selection_work_units": 4294967296,
    }:
        raise ProbeError("P9 D0 static bit-order cap envelope drift")
    cap_object = fixture["deterministic_step3_bit_order_selection_probe_caps"]
    if (
        cap_object.get("static_per_component_upper_bound")
        != "1048576_rows_times_768_boundaries_is_805306368"
        or cap_object.get("static_combined_upper_bound")
        != "four_times_805306368_is_3221225472_strictly_below_4294967296"
        or cap_object.get(
            "peak_cap_counts_one_sort_input_buffer_not_total_live_process_memory"
        ) is not True
        or cap_object.get(
            "caps_are_precommitted_not_derived_from_D0_to_D4_or_P8_observations"
        ) is not True
        or cap_object.get(
            "each_component_and_combined_total_are_checked_before_the_corresponding_operation"
        ) is not True
    ):
        raise ProbeError("P9 D0 static cap-derivation disclosure drift")

    host = fixture["host_supervisor_caps"]
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
        raise ProbeError("P9 D0 fixture host admission drift")
    _validate_runtime_custody_shape(fixture["runtime_custody"], "P9 D0 fixture")

    expected_pins = {
        "P2": "majorana_certificate_p2_fixture.json",
        "P3": "majorana_certificate_p3_fixture.json",
        "P4": "majorana_certificate_p4_fixture.json",
        "P5": "majorana_certificate_p5_fixture.json",
        "P6": "majorana_certificate_p6_fixture.json",
    }
    base_pins = fixture["required_base_fixture_sha256"]
    if not isinstance(base_pins, dict) or set(base_pins) != set(expected_pins):
        raise ProbeError("P9 D0 base fixture pin set drift")
    for label, relative in expected_pins.items():
        if base_pins[label] != file_sha256(BASE / relative):
            raise ProbeError(f"P9 D0 base fixture pin drift: {label}")

    expected_p8 = {
        "P8_A_result_commit": P8_A_RESULT_COMMIT,
        "P8_A_report_sha256": P8_A_REPORT_SHA256,
        "P8_B_result_commit": P8_B_RESULT_COMMIT,
        "P8_B_report_sha256": P8_B_REPORT_SHA256,
        "allowed_P8_A_claim": (
            "successful_selector_membership_and_selected_cost_total_only"
        ),
        "allowed_P8_B_claim": (
            "independent_Git_object_bound_selector_semantics_only"
        ),
        "P8_resource_cap_host_performance_and_runtime_equivalence_are_not_claimed": True,
    }
    if fixture["P8_selector_semantics_custody"] != expected_p8:
        raise ProbeError("P9 D0 P8 custody projection drift")
    expected_d4 = {
        "D4_result_commit": D4_RESULT_COMMIT,
        "D4_report_sha256": D4_REPORT_SHA256,
        "P9_does_not_use_D4_phase_timing_or_host_observations_as_an_algorithm_input": True,
    }
    if fixture["D4_route_custody"] != expected_d4:
        raise ProbeError("P9 D0 D4 route custody drift")
    projection = fixture["expected_P6_prefix_resource_projection"]
    if not isinstance(projection, dict) or set(projection) != {
        "step1", "step2", "step_link", "selection_resources",
    }:
        raise ProbeError("malformed P9 D0 inline P6 prefix projection")
    return fixture


def _extract_function_slice(
    body: bytes, opening: bytes, following: bytes, context: str,
) -> bytes:
    start = body.find(opening)
    end = body.find(following, start)
    if start < 0 or end < 0:
        raise ProbeError(f"missing {context} source slice")
    return body[start:end]


def _validate_static_source_contract(policy: Mapping[str, Any]) -> None:
    p6_path = BASE / P6_RUNNER
    p9_path = BASE / PROBE_DRIVER
    p7_path = (
        BASE / "majorana_certificate_p7_design_probe/"
        "majorana_p7_step3_resource_probe.jl"
    )
    for path, label in (
        (p6_path, "P6 runner"), (p9_path, "P9 driver"),
        (p7_path, "P7 D0 driver"),
    ):
        if not path.is_file() or path.is_symlink():
            raise ProbeError(f"P9 static contract missing nonregular {label}")
    p6 = p6_path.read_bytes()
    p9 = p9_path.read_bytes()
    p7 = p7_path.read_bytes()
    p6_custody = policy["P6_execute_slice_custody"]
    expected_p6_custody = {
        "P6_runner_sha256": (
            "b63143c066d3d258594e27ee4062632632030e9962a0fcd127fcd5000ff9cc1c"
        ),
        "P6_execute_p6_step2_slice_sha256": (
            "a0a7f956540c602ea3f33424eee0b89189e35eb3f7a12941e556143576693f25"
        ),
        "P9_static_copy_permitted_deltas": (
            "function_name_and_three_selector_hook_callees_only"
        ),
        "P9_static_reverse_normalization_must_equal_the_frozen_P6_slice": True,
        "runtime_source_AST_eval_or_monkey_patch_is_forbidden": True,
    }
    if p6_custody != expected_p6_custody:
        raise ProbeError("P9 P6 execute-slice custody declaration drift")
    if hashlib.sha256(p6).hexdigest() != p6_custody["P6_runner_sha256"]:
        raise ProbeError("P9 frozen P6 runner bytes drift")
    p6_slice = _extract_function_slice(
        p6, b"function execute_p6_step2(", b"\nfunction main_p6()",
        "frozen P6 execute",
    )
    if hashlib.sha256(p6_slice).hexdigest() != (
        p6_custody["P6_execute_p6_step2_slice_sha256"]
    ):
        raise ProbeError("P9 frozen P6 execute slice drift")
    p9_slice = _extract_function_slice(
        p9, b"function execute_p9_step3_bitorder(",
        b"\nfunction main_p9_d0()", "P9 bit-order execute",
    )
    normalized = (
        p9_slice
        .replace(b"execute_p9_step3_bitorder", b"execute_p6_step2")
        .replace(b"p9_prepare_boundary_drop!", b"p6_prepare_boundary_drop!")
        .replace(b"p9_should_drop", b"p6_should_drop")
        .replace(
            b"p9_validate_selected_drop_ticks!",
            b"p6_validate_selected_drop_ticks!",
        )
    )
    if normalized != p6_slice:
        raise ProbeError("P9 execute slice has an unauthorized delta from P6")

    expected_p7_custody = {
        "P7_D0_driver_sha256": (
            "12b3883309e64e49baa6b05c9d42ef6b311fa3c692daeccb90ab52849845723c"
        ),
        "P7_D0_driver_size_bytes": 33680,
        "P9_prefix_helpers_are_static_renamed_copies_of_the_frozen_P7_D0_helpers": True,
        "P9_executes_the_byte_identical_frozen_P6_runner_for_step2": True,
    }
    if policy["P7_prefix_source_custody"] != expected_p7_custody:
        raise ProbeError("P9 P7-prefix custody declaration drift")
    if (
        len(p7) != expected_p7_custody["P7_D0_driver_size_bytes"]
        or hashlib.sha256(p7).hexdigest()
        != expected_p7_custody["P7_D0_driver_sha256"]
    ):
        raise ProbeError("P9 frozen P7 helper source drift")
    p9_adaptive = _extract_function_slice(
        p9, b"function p9_execute_adaptive_step(",
        b"\nfunction p9_execute_bit_order_step(", "P9 frozen-prefix adaptive",
    )
    p7_adaptive = _extract_function_slice(
        p7, b"function p7_execute_adaptive_step(",
        b"\nfunction p7_execute_prefix(", "P7 adaptive",
    )
    if p9_adaptive.replace(b"p9_", b"p7_").replace(b"P9", b"P7") != p7_adaptive:
        raise ProbeError("P9 frozen-prefix adaptive helper drift")
    p9_prefix = _extract_function_slice(
        p9, b"function p9_execute_prefix(",
        b"\nfunction p9_assert_public_vocabulary", "P9 frozen-prefix executor",
    )
    p7_prefix = _extract_function_slice(
        p7, b"function p7_execute_prefix(",
        b"\nfunction p7_assert_public_vocabulary", "P7 prefix executor",
    )
    if p9_prefix.replace(b"p9_", b"p7_").replace(b"P9", b"P7") != p7_prefix:
        raise ProbeError("P9 frozen-prefix executor drift")
    for forbidden in (b"include_string", b"Meta.parse", b"eval(", b"run("):
        if forbidden in p9:
            raise ProbeError("P9 driver contains a forbidden runtime transform")
    source = (BASE / Path(__file__).name).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(BASE / Path(__file__).name))
    forbidden_modules = {"runpy", "importlib"}
    forbidden_calls = {"exec", "eval"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name.split(".")[0] in forbidden_modules for alias in node.names
        ):
            raise ProbeError("P9 Python verifier imports a forbidden execution route")
        if isinstance(node, ast.ImportFrom) and (
            node.module or ""
        ).split(".")[0] in forbidden_modules:
            raise ProbeError("P9 Python verifier imports a forbidden execution route")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in forbidden_calls
        ):
            raise ProbeError("P9 Python verifier invokes a forbidden execution route")


def _validate_current_source_pins(policy: Mapping[str, Any]) -> None:
    pins = _source_pins(policy)
    expected_paths = set((*STAGED_PATHS, Path(__file__).name, TEST_NAME))
    if set(pins) != expected_paths:
        raise ProbeError("P9 D0 source pin allowlist drift")
    for relative, row in pins.items():
        path = BASE / relative
        if not path.is_file() or path.is_symlink():
            raise ProbeError(f"missing or nonregular P9 D0 source: {relative}")
        body = path.read_bytes()
        if (
            row.get("size_bytes") != len(body)
            or row.get("sha256") != hashlib.sha256(body).hexdigest()
        ):
            raise ProbeError(f"P9 D0 source pin drift: {relative}")


def validate_policy(
    policy: Any, *, require_report_absent: bool,
) -> Mapping[str, Any]:
    expected_keys = {
        "schema_version", "policy_id", "policy_fingerprint", "policy_role",
        "required_direct_parent_commit", "required_fixture_relative_path",
        "probe_driver_relative_path", "scientific_authority",
        "certificate_eligible", "result_contract_eligible",
        "hindsight_firewall", "candidate_design", "P6_prefix_reproduction",
        "scientific_algorithm", "P8_selector_semantics_custody",
        "D4_route_custody", "P6_execute_slice_custody",
        "P7_prefix_source_custody", "D0_observation_contract",
        "D0_deterministic_resource_caps", "D0_host_supervisor_caps",
        "fixed_admission_rule", "fixed_formal_admission_schema",
        "stop_rules", "runtime", "state_custody_and_runner_visibility",
        "staged_source_custody", "stage_and_artifact_exclusions",
        "D0_to_S0_lifecycle", "future_S0_terminal_truth_requirements",
        "adversarial_mutations_required", "authority_exclusions",
        "source_files",
    }
    _require_exact_keys(policy, expected_keys, "P9 D0 policy")
    semantic_policy = {
        key: value for key, value in policy.items() if key != "source_files"
    }
    if POLICY_SEMANTIC_SHA256 == "P9_POLICY_SEMANTIC_SHA256_UNSET":
        raise ProbeError("P9 D0 policy semantic SHA is unset")
    if canonical_sha256(semantic_policy) != POLICY_SEMANTIC_SHA256:
        raise ProbeError("P9 D0 policy semantic object drift")
    if (
        policy["schema_version"] != 1
        or policy["policy_id"] != POLICY_ID
        or policy["policy_fingerprint"]
        != "majorana_p9_bit_order_step3_resource_probe_v1"
        or policy["policy_role"]
        != (
            "result_unpinned_non_authoritative_resource_probe_for_one_new_"
            "bit_order_step3_candidate_after_a_byte_identical_frozen_P6_prefix"
        )
        or policy["required_direct_parent_commit"] != DIRECT_PARENT
        or policy["required_fixture_relative_path"] != FIXTURE_NAME
        or policy["probe_driver_relative_path"] != PROBE_DRIVER
        or policy["scientific_authority"] != "NONE"
        or policy["certificate_eligible"] is not False
        or policy["result_contract_eligible"] is not False
    ):
        raise ProbeError("P9 D0 policy identity or authority drift")

    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    if (
        policy["P8_selector_semantics_custody"]
        != fixture["P8_selector_semantics_custody"]
        or policy["D4_route_custody"] != fixture["D4_route_custody"]
    ):
        raise ProbeError("P9 policy/fixture upstream-custody drift")
    _validate_fixed_upstream_custody()
    design = policy["candidate_design"]
    formal = design.get("formal_candidates")
    if (
        design.get("probe_mode_order") != [PROBE_MODE]
        or design.get("candidate_execution_order") != [CANDIDATE_ID]
        or design.get("formal_candidate_order_is_frozen_before_any_D0_output")
        != [CANDIDATE_ID]
        or not isinstance(formal, list)
        or len(formal) != 1
        or design.get("exactly_one_formal_candidate") is not True
        or design.get("control_candidate") is not None
        or design.get(
            "P8_does_not_authorize_resource_cap_host_or_performance_equivalence"
        ) is not True
        or design.get(
            "P9_step3_selector_is_not_applied_to_the_frozen_P6_prefix"
        ) is not True
    ):
        raise ProbeError("P9 D0 policy candidate firewall drift")
    expected_formal = {
        "candidate_id": CANDIDATE_ID,
        "probe_mode": PROBE_MODE,
        "algorithm_id": "MAJORANA-P9-E768-BITORDER-STEP3-V1",
        "prefix_path": (
            "fresh_O0_then_P3_2^-34_step1_then_byte_identical_frozen_P6_"
            "E768_MAX_LAZY37_V1_step2"
        ),
        "step3_path": (
            "full_postmerge_bit_order_prefix_with_lazy_exact_point_costs_"
            "under_a_new_step3_local_error_escrow"
        ),
        "implementation_strategy": (
            "static_P6_execute_slice_copy_with_three_P9_selector_hooks_and_"
            "no_runtime_transform"
        ),
        "fresh_D0_process_count": 1,
        "required_future_S0_fresh_process_count": 2,
        "selectable": True,
    }
    if formal[0] != expected_formal:
        raise ProbeError("P9 D0 formal candidate definition drift")

    algorithm = policy["scientific_algorithm"]
    if (
        algorithm.get("algorithm_id") != "MAJORANA-P9-E768-BITORDER-STEP3-V1"
        or algorithm.get("common_grid_denominator") != str(1 << 128)
        or algorithm.get("step3_local_allocation") != "1/400000"
        or algorithm.get("strict_local_maximum_ticks")
        != str(((1 << 128) - 1) // 400000)
        or algorithm.get("allocation_equality_is_failure") is not True
    ):
        raise ProbeError("P9 D0 algorithm identity drift")
    order = algorithm.get("full_domain_order")
    if not isinstance(order, dict) or (
        order.get("execution_key") != [
            "raw_binary64_absolute_magnitude_bits_as_UInt64_ascending",
            "unsigned_Majorana_mask_ascending",
        ]
        or order.get("semantic_reference_rank_key") != [
            "drop_row_cost_BigInt_ascending",
            "raw_binary64_absolute_magnitude_bits_as_UInt64_ascending",
            "unsigned_Majorana_mask_ascending",
        ]
        or order.get(
            "P8_conditional_membership_and_cost_total_lemma_is_not_a_resource_or_host_claim"
        ) is not True
    ):
        raise ProbeError("P9 D0 policy bit-order contract drift")
    selector = algorithm.get("bit_order_selector")
    if not isinstance(selector, dict) or any(
        selector.get(key) is not True for key in (
            "finite_Float64_immutable_unique_unsigned_mask_snapshot_required",
            "P6_K37_is_callback_anchor_only_not_a_tier",
            "one_snapshot_scan_and_one_bit_order_sort_per_boundary",
            "lazy_costs_stop_at_the_first_unaffordable_positive_cost",
            "callback_only_tests_precomputed_membership",
            "existing_drop_ledger_recomputes_and_must_equal_selected_cost_total",
            "runtime_source_AST_eval_or_monkey_patch_is_forbidden",
        )
    ):
        raise ProbeError("P9 D0 policy bit-order selector firewall drift")

    expected_caps = {
        **fixture["deterministic_step3_probe_caps"],
        **fixture["deterministic_step3_bit_order_selection_probe_caps"],
    }
    if policy["D0_deterministic_resource_caps"] != expected_caps:
        raise ProbeError("P9 D0 deterministic cap envelope drift")
    if policy["D0_host_supervisor_caps"] != fixture["host_supervisor_caps"]:
        raise ProbeError("P9 D0 host cap drift")
    if policy["runtime"] != fixture["runtime_custody"]:
        raise ProbeError("P9 D0 runtime custody drift")
    _validate_runtime_lock_bytes(policy["runtime"])

    observation = policy["D0_observation_contract"]
    expected_witness_fields = [
        "schema_version", "probe_type", "fixture_id", "fixture_sha256",
        "fixture_canonical_sha256", "scientific_authority",
        "certificate_eligible", "result_contract_eligible",
        "resource_observations_only", "candidate", "runtime_custody",
        "step1", "step2", "step3", "step1_to_step2_link",
        "step2_to_step3_link", "step2_selection_resources",
        "step3_bit_order_selection_resources",
        "P6_prefix_resource_projection_conformed", "step3_started",
        "explicit_exclusions",
    ]
    if (
        observation.get("public_witness_exact_top_level_fields")
        != expected_witness_fields
        or observation.get("public_candidate_exact_fields") != [
            "candidate_id", "probe_mode", "identity", "formal_candidate",
            "step1_path", "step2_path", "step3_path",
        ]
        or observation.get("public_explicit_exclusions") != PUBLIC_EXCLUSIONS
        or observation.get("formal_finalizer_privacy") != FINALIZER_PRIVACY
        or observation.get("public_cap_event_name_allowlist") != sorted(
            CAP_EVENT_NAMES
        )
        or observation.get("public_resource_identities") != list(
            PUBLIC_RESOURCE_IDENTITIES
        )
    ):
        raise ProbeError("P9 D0 public-observation contract drift")

    formal_schema = policy["fixed_formal_admission_schema"]
    if formal_schema.get("exact_fields") != [
        "status", "formal_step3_caps",
        "formal_step3_bit_order_selection_caps", "formal_host_caps",
        "derived_from_observation", "same_as_D0_admission",
    ]:
        raise ProbeError("P9 D0 formal-admission schema drift")
    staged = policy["staged_source_custody"]
    if (
        staged.get("staged_path_order") != list(STAGED_PATHS)
        or staged.get("exact_staged_path_count") != len(STAGED_PATHS)
        or staged.get("every_staged_file_is_regular_and_not_a_symlink") is not True
        or staged.get(
            "staged_sha256_must_equal_repository_sha256_for_every_path"
        ) is not True
        or staged.get("candidate_algorithm_transform_applied_is_false_for_every_path")
        is not True
        or staged.get("string_source_AST_or_runtime_transform_is_forbidden")
        is not True
        or staged.get("P9_new_step3_adapter_is_a_committed_static_source_file")
        is not True
        or staged.get("P6_prefix_runner_is_byte_identical_and_unmodified")
        is not True
    ):
        raise ProbeError("P9 D0 staged-source custody drift")
    artifacts = policy["stage_and_artifact_exclusions"]
    if artifacts.get(
        "future_P9_result_artifacts_must_be_absent_at_D0_precommit"
    ) != list(RESULT_ARTIFACTS):
        raise ProbeError("P9 D0 future-artifact exclusion drift")
    _validate_static_source_contract(policy)
    _validate_current_source_pins(policy)
    if require_report_absent:
        if (BASE / REPORT_NAME).exists() or (BASE / REPORT_NAME).is_symlink():
            raise ProbeError("P9 D0 report exists before the probe commit")
        for relative in RESULT_ARTIFACTS[1:]:
            if (BASE / relative).exists() or (BASE / relative).is_symlink():
                raise ProbeError(f"future P9 artifact exists before D0: {relative}")
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
        selection = fixture[
            "deterministic_step3_bit_order_selection_probe_caps"
        ]
        prefix = "maximum_step3_"
        maximum_bits = fixture["outward_arithmetic"][
            "maximum_BigInt_bit_length"
        ]
    else:
        raise ProbeError(f"unexpected P9 D0 resource-summary label: {label}")
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
        **(
            {
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
            if label == "step2" else {
                "maximum_snapshot_scan_term_visits":
                    selection["maximum_snapshot_scan_term_visits"],
                "maximum_bit_order_sort_input_items":
                    selection["maximum_bit_order_sort_input_items"],
                "maximum_lazy_tick_evaluations":
                    selection["maximum_lazy_tick_evaluations"],
                "maximum_selected_membership_insertions":
                    selection["maximum_selected_membership_insertions"],
                "maximum_peak_bit_order_sort_input_terms":
                    selection["maximum_peak_bit_order_sort_input_terms"],
                "maximum_total_bit_order_selection_work_units":
                    selection["maximum_total_bit_order_selection_work_units"],
            }
        ),
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
        raise ProbeError("malformed P9 D0 cap event")
    if value["rejected_operation_was_not_executed_after_cap_detection"] is not True:
        raise ProbeError("P9 D0 cap executed the rejected operation")
    if value["cap_name"] not in cap_limits:
        raise ProbeError("P9 D0 cap name is outside the frozen allowlist")
    for key in ("limit", "attempted"):
        if (not isinstance(value[key], int) or isinstance(value[key], bool)
                or value[key] < 0):
            raise ProbeError(f"invalid P9 D0 cap value: {key}")
    if value["attempted"] <= value["limit"]:
        raise ProbeError("P9 D0 cap attempted value does not exceed its limit")
    if value["limit"] != cap_limits[value["cap_name"]]:
        raise ProbeError("P9 D0 cap limit differs from the frozen limit")
    context = value["context"]
    if (not isinstance(context, dict) or not set(context) <= CAP_CONTEXT_KEYS
            or "operation" not in context):
        raise ProbeError("malformed P9 D0 sanitized cap context")
    if context["operation"] != "resource_cap_precheck":
        raise ProbeError("P9 D0 cap context exposes an unfrozen operation")
    if label == "step3" and context.get("mapped_step_index") != 3:
        raise ProbeError("P9 D0 step-3 cap lacks its mapped-step identity")
    if "mapped_step_index" in context and context["mapped_step_index"] not in {
        1, 2, 3,
    }:
        raise ProbeError("P9 D0 cap context has an invalid mapped-step index")
    if "group" in context and (
        not isinstance(context["group"], str) or not context["group"]
    ):
        raise ProbeError("invalid P9 D0 cap context group")
    for key in CAP_CONTEXT_KEYS - {"group", "operation"}:
        if key in context and (
            not isinstance(context[key], int) or isinstance(context[key], bool)
            or context[key] < 0
        ):
            raise ProbeError(f"invalid P9 D0 cap context index: {key}")


def _validate_resource_summary(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != RESOURCE_SUMMARY_KEYS:
        raise ProbeError(f"malformed P9 D0 {label} resource summary")
    if (not isinstance(value["P2_resource_counters"], dict)
            or set(value["P2_resource_counters"]) != P2_COUNTER_KEYS):
        raise ProbeError(f"malformed P9 D0 {label} P2 counters")
    if (not isinstance(value["accuracy_event_counters"], dict)
            or set(value["accuracy_event_counters"]) != ACCURACY_COUNTER_KEYS):
        raise ProbeError(f"malformed P9 D0 {label} accuracy counters")
    for key, item in value.items():
        if key in {
            "P2_resource_counters", "accuracy_event_counters", "cap_event",
            "final_retained_term_count",
        }:
            continue
        if (not isinstance(item, int) or isinstance(item, bool) or item < 0):
            raise ProbeError(f"invalid P9 D0 {label} resource count: {key}")
    for group in (value["P2_resource_counters"], value["accuracy_event_counters"]):
        if any(
            not isinstance(item, int) or isinstance(item, bool) or item < 0
            for item in group.values()
        ):
            raise ProbeError(f"invalid P9 D0 {label} nested resource count")
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
        raise ProbeError(f"P9 D0 {label} P2 resource identity mismatch")
    if accuracy["accuracy_charged_event_count"] != (
        accuracy["product_defect_event_count"]
        + accuracy["merge_defect_event_count"]
        + accuracy["drop_defect_event_count"]
    ):
        raise ProbeError(f"P9 D0 {label} accuracy resource identity mismatch")
    if accuracy["product_defect_event_count"] != (
        2 * accuracy["anticommuting_event_count"]
    ):
        raise ProbeError(f"P9 D0 {label} product/anticommuting identity mismatch")
    if value["cap_event"] is None:
        if value["anticommuting_split_count"] != accuracy[
            "anticommuting_event_count"
        ]:
            raise ProbeError(
                f"P9 D0 {label} split/anticommuting identity mismatch"
            )
        if value["threshold_dropped_term_count"] != accuracy[
            "drop_defect_event_count"
        ]:
            raise ProbeError(f"P9 D0 {label} drop-event identity mismatch")
    elif (
        value["anticommuting_split_count"]
        > accuracy["anticommuting_event_count"]
        or value["threshold_dropped_term_count"]
        > accuracy["drop_defect_event_count"]
    ):
        raise ProbeError(f"P9 D0 {label} capped progress exceeds charged events")
    if value["total_P2_plus_accuracy_charged_event_count"] != (
        p2["total_charged_term_visits"]
        + accuracy["accuracy_charged_event_count"]
    ):
        raise ProbeError(f"P9 D0 {label} combined resource identity mismatch")
    if (
        value["completed_composite_count"] > 512
        or value["completed_constituent_count"] > 1152
        or value["completed_truncation_boundary_count"] > 768
    ):
        raise ProbeError(f"P9 D0 {label} completed-count bound exceeded")
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
            raise ProbeError(f"P9 D0 {label} P2 count exceeds its probe cap")
    accuracy_limits = {
        "anticommuting_event_count": "maximum_anticommuting_events",
        "product_defect_event_count": "maximum_product_defect_events",
        "merge_defect_event_count": "maximum_merge_defect_events",
        "drop_defect_event_count": "maximum_drop_defect_events",
        "accuracy_charged_event_count": "maximum_accuracy_charged_events",
    }
    for field, cap_name in accuracy_limits.items():
        if accuracy[field] > cap_limits[cap_name]:
            raise ProbeError(f"P9 D0 {label} accuracy count exceeds its probe cap")
    if value["total_P2_plus_accuracy_charged_event_count"] > cap_limits[
        "maximum_total_P2_plus_accuracy_charged_events"
    ]:
        raise ProbeError(f"P9 D0 {label} combined count exceeds its probe cap")
    premerge_cap = cap_limits["maximum_premerge_terms"]
    if (
        value["peak_premerge_contribution_count"] > premerge_cap
        or value["peak_postmerge_unique_term_count"] > premerge_cap
    ):
        raise ProbeError(f"P9 D0 {label} peak term count exceeds its probe cap")
    final_count = value["final_retained_term_count"]
    if value["cap_event"] is None:
        if (not isinstance(final_count, int) or isinstance(final_count, bool)
                or final_count < 0):
            raise ProbeError(f"missing P9 D0 {label} completed final count")
        final_cap_name = (
            "final_evaluation_term_visits" if label == "step1"
            else "maximum_final_evaluation_term_visits"
        )
        if final_count > cap_limits[final_cap_name]:
            raise ProbeError(f"P9 D0 {label} final count exceeds its probe cap")
        if final_count != p2["final_evaluation_term_visits"]:
            raise ProbeError(f"P9 D0 {label} final-evaluation identity mismatch")
    elif final_count is not None:
        raise ProbeError(f"capped P9 D0 {label} exposes a final count")
    elif p2["final_evaluation_term_visits"] != 0:
        raise ProbeError(f"capped P9 D0 {label} exposes final-evaluation work")


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
                raise ProbeError(f"forbidden P9 D0 public key at {path}.{key}")
            _reject_public_scientific_vocabulary(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_public_scientific_vocabulary(item, f"{path}[{index}]")
    elif isinstance(value, str):
        lower = value.lower()
        if any(fragment in lower for fragment in forbidden):
            raise ProbeError(f"forbidden P9 D0 public string at {path}")


def _selection_caps(label: str) -> Mapping[str, int]:
    if label == "step2":
        return load_json(
            BASE / "majorana_certificate_p6_fixture.json"
        )["deterministic_selection_caps"]
    if label == "step3":
        return _selection_cap_limits_from_fixture(
            load_json(BASE / FIXTURE_NAME)
        )
    raise ProbeError(f"unexpected P9 D0 selection label: {label}")


def _validate_selection_resources(
    value: Any, label: str, summary: Mapping[str, Any],
) -> None:
    if label == "step2":
        resource_keys = P6_SELECTION_RESOURCE_KEYS
        work_fields = (
            "total_ranking_scan_term_visits", "total_sort_work_items",
            "total_tick_evaluations", "total_selected_membership_insertions",
        )
        work_total = "total_selection_work_units"
        limits = {
            "total_ranking_scan_term_visits": "maximum_ranking_scan_term_visits",
            "total_sort_work_items": "maximum_sort_input_items",
            "total_tick_evaluations": "maximum_tick_evaluations",
            "total_selected_membership_insertions":
                "maximum_selected_membership_insertions",
            "peak_ranking_buffer_terms": "maximum_peak_ranking_buffer_terms",
            "total_selection_work_units": "maximum_total_selection_work_units",
        }
    elif label == "step3":
        resource_keys = P9_SELECTION_RESOURCE_KEYS
        work_fields = (
            "total_snapshot_scan_term_visits",
            "total_bit_order_sort_input_items",
            "total_lazy_tick_evaluations",
            "total_selected_membership_insertions",
        )
        work_total = "total_bit_order_selection_work_units"
        limits = {
            "total_snapshot_scan_term_visits":
                "maximum_snapshot_scan_term_visits",
            "total_bit_order_sort_input_items":
                "maximum_bit_order_sort_input_items",
            "total_lazy_tick_evaluations": "maximum_lazy_tick_evaluations",
            "total_selected_membership_insertions":
                "maximum_selected_membership_insertions",
            "peak_bit_order_sort_input_terms":
                "maximum_peak_bit_order_sort_input_terms",
            "total_bit_order_selection_work_units":
                "maximum_total_bit_order_selection_work_units",
        }
    else:
        raise ProbeError(f"unexpected P9 D0 selection label: {label}")
    if not isinstance(value, dict) or set(value) != resource_keys:
        raise ProbeError(f"malformed P9 D0 {label} selection resources")
    if any(
        not isinstance(item, int) or isinstance(item, bool) or item < 0
        for item in value.values()
    ):
        raise ProbeError(f"invalid P9 D0 {label} selection resource count")
    expected_total = sum(value[field] for field in work_fields)
    if value[work_total] != expected_total:
        raise ProbeError(f"P9 D0 {label} selection work identity mismatch")
    caps = _selection_caps(label)
    for field, cap_name in limits.items():
        if value[field] > caps[cap_name]:
            raise ProbeError(
                f"P9 D0 {label} selection resource exceeds its cap: {field}"
            )
    boundaries = value["completed_selection_boundary_count"]
    completed = summary["completed_truncation_boundary_count"]
    if boundaries > 768:
        raise ProbeError(f"P9 D0 {label} selection boundary count exceeds schedule")
    if summary["cap_event"] is None:
        if boundaries != completed or boundaries != 768:
            raise ProbeError(
                f"P9 D0 completed {label} selection/boundary identity mismatch"
            )
    elif boundaries not in {completed, completed + 1}:
        raise ProbeError(f"P9 D0 capped {label} selection progress mismatch")


def _validate_step_link(
    value: Any, previous: Mapping[str, Any], next_step: Mapping[str, Any],
    context: str,
) -> None:
    expected = {
        "same_process", "checkpoint_or_serialized_state_used",
        "previous_step_final_term_count", "next_step_input_term_count",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ProbeError(f"malformed P9 D0 {context} link")
    if (
        value["same_process"] is not True
        or value["checkpoint_or_serialized_state_used"] is not False
    ):
        raise ProbeError(f"P9 D0 {context} link violates live-process custody")
    for key in (
        "previous_step_final_term_count", "next_step_input_term_count",
    ):
        item = value[key]
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ProbeError(f"invalid P9 D0 {context} link count")
    if (
        value["previous_step_final_term_count"]
        != value["next_step_input_term_count"]
        or value["previous_step_final_term_count"]
        != previous["final_retained_term_count"]
    ):
        raise ProbeError(f"P9 D0 {context} term-count link mismatch")
    if next_step["completed_constituent_count"] > 0 and (
        value["next_step_input_term_count"] <= 0
    ):
        raise ProbeError(f"P9 D0 {context} has an empty executed input")


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
        "step3_bit_order_selection_resources",
        "P6_prefix_resource_projection_conformed", "step3_started",
        "explicit_exclusions",
    }
    if mode != PROBE_MODE:
        raise ProbeError("P9 D0 public witness mode is not frozen")
    if not isinstance(witness, dict) or set(witness) != expected_top:
        raise ProbeError("malformed P9 D0 public witness")
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
        raise ProbeError("unexpected P9 D0 witness identity or fixture custody")
    if witness["scientific_authority"] != "NONE":
        raise ProbeError("P9 D0 witness claims scientific authority")
    for key in ("certificate_eligible", "result_contract_eligible"):
        if witness[key] is not False:
            raise ProbeError(f"P9 D0 witness enables {key}")
    if witness["resource_observations_only"] is not True:
        raise ProbeError("P9 D0 witness is not resource-only")

    candidate = witness["candidate"]
    if not isinstance(candidate, dict) or set(candidate) != {
        "candidate_id", "probe_mode", "identity", "formal_candidate",
        "step1_path", "step2_path", "step3_path",
    }:
        raise ProbeError("malformed P9 D0 candidate identity")
    if (
        candidate["candidate_id"] != CANDIDATE_ID
        or candidate["probe_mode"] != PROBE_MODE
        or candidate["identity"] != PROBE_MODE
        or candidate["formal_candidate"] is not True
        or candidate["step1_path"] != "fixed_P3_2^-34"
        or candidate["step2_path"] != "frozen_P6_E768_MAX_LAZY37_V1"
        or candidate["step3_path"] != "full_domain_bit_order_E768_STEP3_V1"
    ):
        raise ProbeError("P9 D0 candidate execution identity drift")
    if witness["runtime_custody"] != fixture["runtime_custody"]:
        raise ProbeError("P9 D0 runtime custody drift")
    if witness["explicit_exclusions"] != PUBLIC_EXCLUSIONS:
        raise ProbeError("P9 D0 public exclusions drift")
    for key in (
        "P6_prefix_resource_projection_conformed", "step3_started",
    ):
        if not isinstance(witness[key], bool):
            raise ProbeError(f"P9 D0 witness {key} is not boolean")

    step1 = witness["step1"]
    _validate_resource_summary(step1, "step1")
    step2 = witness["step2"]
    step3 = witness["step3"]
    link12 = witness["step1_to_step2_link"]
    link23 = witness["step2_to_step3_link"]
    selection2 = witness["step2_selection_resources"]
    selection3 = witness["step3_bit_order_selection_resources"]

    if step1["cap_event"] is not None:
        if any(item is not None for item in (
            step2, step3, link12, link23, selection2, selection3,
        )):
            raise ProbeError("P9 D0 attempted work after a capped step 1")
        if (
            witness["P6_prefix_resource_projection_conformed"]
            or witness["step3_started"]
        ):
            raise ProbeError("P9 D0 capped step 1 has positive lifecycle flags")
    else:
        if (
            step1["completed_composite_count"] != 512
            or step1["completed_constituent_count"] != 1152
            or step1["completed_truncation_boundary_count"] != 768
            or step2 is None or link12 is None or selection2 is None
        ):
            raise ProbeError("P9 D0 completed step 1 lacks its step-2 continuation")
        _validate_resource_summary(step2, "step2")
        _validate_selection_resources(selection2, "step2", step2)
        _validate_step_link(link12, step1, step2, "step1-to-step2")
        if step2["cap_event"] is not None:
            if any(item is not None for item in (step3, link23, selection3)):
                raise ProbeError("P9 D0 attempted step 3 after a capped step 2")
            if (
                witness["P6_prefix_resource_projection_conformed"]
                or witness["step3_started"]
            ):
                raise ProbeError("P9 D0 capped step 2 has positive lifecycle flags")
        else:
            if (
                step2["completed_composite_count"] != 512
                or step2["completed_constituent_count"] != 1152
                or step2["completed_truncation_boundary_count"] != 768
            ):
                raise ProbeError("P9 D0 uncapped step 2 is incomplete")
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
                        "P9 D0 invalid prefix conformance attempted step 3"
                    )
            else:
                if (
                    witness["P6_prefix_resource_projection_conformed"] is not True
                    or witness["step3_started"] is not True
                    or step3 is None or link23 is None or selection3 is None
                ):
                    raise ProbeError("P9 D0 conforming P6 prefix lacks step 3")
                _validate_resource_summary(step3, "step3")
                _validate_selection_resources(selection3, "step3", step3)
                _validate_step_link(link23, step2, step3, "step2-to-step3")
                if step3["cap_event"] is None and (
                    step3["completed_composite_count"] != 512
                    or step3["completed_constituent_count"] != 1152
                    or step3["completed_truncation_boundary_count"] != 768
                ):
                    raise ProbeError("P9 D0 uncapped step 3 is incomplete")

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
        "majorana-p9-d0-step3-"
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
    witness = loads_json(stdout, "P9 D0 candidate stdout")
    if stdout != canonical_bytes(witness) + b"\n":
        raise ProbeError("P9 D0 candidate stdout is not canonical JSON")
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
        "formal_step3_bit_order_selection_caps":
            fixture["deterministic_step3_bit_order_selection_probe_caps"],
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
        raise ProbeError("completed P9 D0 observation lacks a witness")
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
        raise ProbeError("P9 D0 completed witness has an invalid admission truth state")
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
        raise ProbeError("P9 D0 preprobe commit is not a full lowercase SHA-1")
    try:
        ancestry = _run_git("rev-list", "--parents", "-n", "1", preprobe_commit)
    except subprocess.CalledProcessError as error:
        raise ProbeError("P9 D0 preprobe commit is not present") from error
    if ancestry.split() != [preprobe_commit, DIRECT_PARENT]:
        raise ProbeError("P9 D0 preprobe commit has the wrong direct parent")
    changed = set(filter(None, _run_git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", preprobe_commit,
    ).splitlines()))
    if changed != PREPROBE_CHANGED_PATHS:
        raise ProbeError("P9 D0 preprobe changed-path allowlist drift")
    raw_rows = _run_git(
        "diff-tree", "--no-commit-id", "--raw", "--no-renames", "-r",
        preprobe_commit,
    ).splitlines()
    if len(raw_rows) != len(PREPROBE_CHANGED_PATHS):
        raise ProbeError("P9 D0 preprobe raw-diff cardinality drift")
    source_prefix = "docs/research/fermion-frontier/"
    for row in raw_rows:
        try:
            metadata, relative = row.split("\t", 1)
            old_mode, new_mode, old_blob, new_blob, status = metadata.split()
        except ValueError as error:
            raise ProbeError("malformed P9 D0 preprobe raw-diff row") from error
        if (
            relative not in PREPROBE_CHANGED_PATHS
            or old_mode != ":000000"
            or new_mode != "100644"
            or old_blob != "0" * 40
            or len(new_blob) != 40
            or any(character not in "0123456789abcdef" for character in new_blob)
            or status != "A"
            or not relative.startswith(source_prefix)
        ):
            raise ProbeError("P9 D0 preprobe path is not a new regular blob")
        worktree_path = BASE / relative.removeprefix(source_prefix)
        if not worktree_path.is_file() or worktree_path.is_symlink():
            raise ProbeError("P9 D0 preprobe path is missing or nonregular")
        blob = subprocess.run(
            ["git", "show", f"{preprobe_commit}:{relative}"], cwd=BASE,
            check=False, capture_output=True,
        )
        if blob.returncode != 0 or blob.stdout != worktree_path.read_bytes():
            raise ProbeError("P9 D0 preprobe Git blob/disk byte mismatch")
    artifact = f"{preprobe_commit}:docs/research/fermion-frontier/{REPORT_NAME}"
    if subprocess.run(
        ["git", "cat-file", "-e", artifact], cwd=BASE,
        check=False, capture_output=True,
    ).returncode == 0:
        raise ProbeError("P9 D0 report exists in the preprobe commit")


def _validate_preprobe_commit(preprobe_commit: str) -> None:
    _validate_preprobe_commit_identity(preprobe_commit)
    if _run_git("rev-parse", "HEAD") != preprobe_commit:
        raise ProbeError("P9 D0 HEAD differs from requested preprobe commit")
    if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ProbeError("P9 D0 worktree is not clean before execution")


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
        raise ProbeError("P9 D0 Julia executable custody mismatch")
    if not depot.is_dir():
        raise ProbeError("P9 D0 depot is missing")
    for executable in ("systemd-run", "systemctl", "/usr/bin/time"):
        if shutil.which(executable) is None:
            raise ProbeError(f"P9 D0 missing required executable: {executable}")

    with tempfile.TemporaryDirectory(prefix="majorana-p9-d0-") as temporary:
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
        "result_contract_eligible": False,
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
        raise ProbeError("P9 D0 staging manifest must contain exactly 13 paths")
    if any(not isinstance(row, dict) for row in rows):
        raise ProbeError("malformed P9 D0 staging row")
    if [row.get("relative_path") for row in rows] != list(STAGED_PATHS):
        raise ProbeError("P9 D0 staging manifest order drift")
    pins = _source_pins(policy)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "repository_sha256", "staged_size_bytes",
            "staged_sha256", "byte_identical_to_repository",
        }:
            raise ProbeError("malformed P9 D0 staging row")
        relative = row["relative_path"]
        if (
            not isinstance(row["staged_size_bytes"], int)
            or isinstance(row["staged_size_bytes"], bool)
            or row["staged_size_bytes"] < 0
        ):
            raise ProbeError("invalid P9 D0 staged size")
        for key in ("repository_sha256", "staged_sha256"):
            if (
                not isinstance(row[key], str)
                or len(row[key]) != 64
                or any(character not in "0123456789abcdef" for character in row[key])
            ):
                raise ProbeError("invalid P9 D0 staging digest")
        body = (BASE / relative).read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        if (
            row["repository_sha256"] != pins[relative]["sha256"]
            or row["staged_size_bytes"] != len(body)
            or row["staged_sha256"] != digest
            or row["staged_sha256"] != row["repository_sha256"]
            or row["byte_identical_to_repository"] is not True
        ):
            raise ProbeError("P9 D0 staging is not byte-identical")
    if expected_sha256 != canonical_sha256(rows):
        raise ProbeError("P9 D0 staging manifest hash mismatch")


def _validate_time_diagnostics(value: Any, *, completed: bool) -> None:
    if (not isinstance(value, dict) or not set(value) <= TIME_DIAGNOSTIC_KEYS
            or (completed and set(value) != TIME_DIAGNOSTIC_KEYS)):
        raise ProbeError("malformed P9 D0 time diagnostics")
    for key, item in value.items():
        if key in {
            "maximum_resident_set_size_KiB", "minor_page_faults",
            "major_page_faults",
        }:
            if (not isinstance(item, int) or isinstance(item, bool) or item < 0):
                raise ProbeError(f"invalid P9 D0 time diagnostic: {key}")
        elif not isinstance(item, str) or not item:
            raise ProbeError(f"invalid P9 D0 time diagnostic: {key}")
        elif key in {"user_time_seconds", "system_time_seconds"} and not (
            re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", item)
        ):
            raise ProbeError(f"invalid P9 D0 time diagnostic format: {key}")
        elif key == "elapsed_wall_clock" and not re.fullmatch(
            r"(?:[0-9]+:)?[0-9]+:[0-5][0-9](?:\.[0-9]+)?", item,
        ):
            raise ProbeError("invalid P9 D0 elapsed-wall-clock format")
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
        raise ProbeError("malformed P9 D0 observation")
    if (
        row["probe_mode"] != PROBE_MODE
        or row["candidate_id"] != CANDIDATE_ID
    ):
        raise ProbeError("P9 D0 observation identity drift")
    if row["host_failure_has_no_mathematical_authority"] is not True:
        raise ProbeError("P9 D0 host failure claims authority")
    if (not isinstance(row["process_returncode"], int)
            or isinstance(row["process_returncode"], bool)):
        raise ProbeError("invalid P9 D0 process return code")
    if not isinstance(row["outer_timeout_triggered"], bool):
        raise ProbeError("invalid P9 D0 timeout flag")
    for key in (
        "stdout_bytes", "stderr_bytes", "outer_monotonic_elapsed_ns",
    ):
        if (not isinstance(row[key], int) or isinstance(row[key], bool)
                or row[key] < 0):
            raise ProbeError("invalid P9 D0 observation resource value")
    if row["outer_monotonic_elapsed_ns"] <= 0:
        raise ProbeError("invalid P9 D0 nonpositive elapsed time")
    for key in ("stdout_sha256", "stderr_sha256"):
        if (not isinstance(row[key], str) or len(row[key]) != 64
                or any(character not in "0123456789abcdef" for character in row[key])):
            raise ProbeError("invalid P9 D0 observation digest")
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
            raise ProbeError("P9 D0 resource witness hash mismatch")
        stdout = canonical_bytes(witness) + b"\n"
        if (row["stdout_bytes"] != len(stdout)
                or row["stdout_sha256"] != hashlib.sha256(stdout).hexdigest()):
            raise ProbeError("P9 D0 stdout/resource witness custody mismatch")
        if host_failed:
            raise ProbeError("completed P9 D0 observation has host failure")
    elif row["status"] == "INDETERMINATE_HOST_OR_RUNTIME_FAILURE":
        if row["resource_witness"] is not None:
            raise ProbeError("indeterminate P9 D0 observation retained a witness")
        if not host_failed:
            raise ProbeError("P9 D0 host-failure status has no host failure")
    else:
        raise ProbeError("unexpected P9 D0 observation status")


def validate_report(report: Any) -> Mapping[str, Any]:
    policy = validate_policy(
        load_json(BASE / POLICY_NAME), require_report_absent=False,
    )
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    expected_top = {
        "schema_version", "report_type", "policy_id", "policy_sha256",
        "fixture_id", "fixture_sha256", "fixture_canonical_sha256",
        "preprobe_commit_sha", "scientific_authority", "certificate_eligible",
        "result_contract_eligible",
        "formal_candidate_was_frozen_before_probe", "staging_manifest",
        "staging_manifest_sha256", "host_caps", "observations",
        "fixed_formal_admission", "authority_exclusions",
    }
    if not isinstance(report, dict) or set(report) != expected_top:
        raise ProbeError("malformed P9 D0 report")
    if (
        type(report.get("schema_version")) is not int
        or report["schema_version"] != 1
        or report["report_type"] != REPORT_TYPE
        or report["policy_id"] != POLICY_ID
        or report["fixture_id"] != FIXTURE_ID
    ):
        raise ProbeError("unexpected P9 D0 report identity")
    if (
        report["policy_sha256"] != file_sha256(BASE / POLICY_NAME)
        or report["fixture_sha256"] != file_sha256(BASE / FIXTURE_NAME)
        or report["fixture_canonical_sha256"] != canonical_sha256(fixture)
    ):
        raise ProbeError("P9 D0 report source custody mismatch")
    if (
        report["scientific_authority"] != "NONE"
        or report["certificate_eligible"] is not False
        or report["result_contract_eligible"] is not False
    ):
        raise ProbeError("P9 D0 report exceeds resource-only authority")
    _validate_preprobe_commit_identity(report["preprobe_commit_sha"])
    if report["host_caps"] != fixture["host_supervisor_caps"]:
        raise ProbeError("P9 D0 report host admission drift")
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
        raise ProbeError("P9 D0 report must contain the sole frozen observation")
    _validate_observation(observations[0], fixture["host_supervisor_caps"])
    expected_admission = _fixed_formal_admission(observations[0], policy)
    if report["fixed_formal_admission"] != expected_admission:
        raise ProbeError("P9 D0 fixed formal admission drift")
    if (
        report["fixed_formal_admission"]["formal_host_caps"]
        != fixture["host_supervisor_caps"]
        or report["fixed_formal_admission"]["derived_from_observation"] is not False
        or report["fixed_formal_admission"]["same_as_D0_admission"] is not True
    ):
        raise ProbeError("P9 D0 admission is observation-derived")
    if report["authority_exclusions"] != policy["authority_exclusions"]:
        raise ProbeError("P9 D0 report authority exclusions drift")
    if report["formal_candidate_was_frozen_before_probe"] != CANDIDATE_ID:
        raise ProbeError("P9 D0 report formal candidate drift")
    return report


def lazy_reference_select(
    rows: Sequence[Mapping[str, int]], available: int,
) -> list[Mapping[str, int]]:
    """Small-model reference for P9's lazy bit-order initial prefix."""
    if available < 0:
        raise ProbeError("negative lazy-reference amount")
    ordered = sorted(
        rows, key=lambda row: (int(row["abs_bits"]), int(row["mask"])),
    )
    selected: list[Mapping[str, int]] = []
    remaining = available
    for row in ordered:
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
            "status": "VERIFIED_P9_D0_PREPROBE",
            "policy_id": policy["policy_id"],
        }
    elif args.run:
        if not all((args.preprobe_commit, args.julia, args.depot)):
            parser.error("run requires preprobe commit, Julia, and depot")
        report = run_probe(args.preprobe_commit, args.julia, args.depot, args.output)
        summary = {
            "status": "COMPLETED_P9_D0_RESOURCE_PROBE",
            "report_sha256": file_sha256(args.output),
            "observation_statuses": [row["status"] for row in report["observations"]],
            "fixed_formal_admission_status":
                report["fixed_formal_admission"]["status"],
        }
    else:
        report = validate_report(load_json(args.output))
        if args.output.read_bytes() != canonical_bytes(report) + b"\n":
            raise ProbeError("P9 D0 report is not canonical JSON plus newline")
        summary = {
            "status": "VERIFIED_P9_D0_RESOURCE_REPORT",
            "report_sha256": file_sha256(args.output),
            "fixed_formal_admission_status":
                report["fixed_formal_admission"]["status"],
        }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
