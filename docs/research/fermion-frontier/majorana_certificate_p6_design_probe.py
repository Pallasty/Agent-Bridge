#!/usr/bin/env python3
"""Run and verify the non-authoritative Majorana P6 D0 resource probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
POLICY_NAME = "majorana_certificate_p6_design_probe_policy.json"
FIXTURE_NAME = "majorana_certificate_p6_design_probe_fixture.json"
REPORT_NAME = "majorana_certificate_p6_design_probe_report.json"
PROBE_DRIVER = (
    "majorana_certificate_p6_design_probe/"
    "majorana_p6_adaptive_drop_resource_probe.jl"
)
P5_RUNNER = "majorana_certificate_p5/majorana_p5_runner.jl"
STAGED_PATHS = (
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    "majorana_certificate_p3/majorana_p3_runner.jl",
    "majorana_certificate_p4/majorana_p4_runner.jl",
    P5_RUNNER,
    "majorana_certificate_p2_fixture.json",
    "majorana_certificate_p3_fixture.json",
    "majorana_certificate_p4_fixture.json",
    "majorana_certificate_p5_fixture.json",
    FIXTURE_NAME,
    PROBE_DRIVER,
)
PREPROBE_CHANGED_PATHS = frozenset({
    f"docs/research/fermion-frontier/{POLICY_NAME}",
    f"docs/research/fermion-frontier/{FIXTURE_NAME}",
    f"docs/research/fermion-frontier/{Path(__file__).name}",
    f"docs/research/fermion-frontier/{PROBE_DRIVER}",
    "docs/research/fermion-frontier/test_majorana_certificate_p6_design_probe.py",
})
RESULT_ARTIFACTS = (
    REPORT_NAME,
    "majorana_certificate_p6_fixture.json",
    "majorana_certificate_p6_policy.json",
    "majorana_certificate_p6_precommit_contract.json",
    "majorana_certificate_p6_contract.json",
    "majorana_certificate_p6_certificate.json",
    "test_majorana_certificate_p6_result.py",
)

POLICY_ID = "MAJORANA-P6-E768-MAX-LAZY37-D0-V1"
FIXTURE_ID = "MAJORANA-P6-E768-MAX-LAZY37-D0-V1"
REPORT_TYPE = "majorana_p6_e768_max_lazy37_resource_report_d0_v1"
PROBE_TYPE = "majorana_p6_e768_max_lazy37_resource_probe_d0_v1"
DIRECT_PARENT = "39100195cfd04bb4de086f127e8a75da0a7548ce"
CONTROL_MODE = "P5_K37_RESOURCE_CONTROL"
ADAPTIVE_MODE = "E768_MAX_LAZY37_V1"
MODE_ORDER = (CONTROL_MODE, ADAPTIVE_MODE)
CANDIDATE_IDS = {
    CONTROL_MODE: "P5-K37-RESOURCE-CONTROL",
    ADAPTIVE_MODE: "E768-MAX-LAZY37-V1",
}

PREPARE_NEEDLE = (
    "                        dropped = "
    "Tuple{typeof(constituent.rotation.ms_int),Float64}[]\n"
)
PREPARE_REPLACEMENT = (
    "                        p6_drop_decision = p6_prepare_boundary_drop!(\n"
    "                            merged_main, ticks, "
    "Int(public.boundary_index_after),\n"
    "                            maximum_bits, merge(context, (\n"
    "                                operation=\"p6_drop_selection\",\n"
    "                            )),\n"
    "                        )\n"
    + PREPARE_NEEDLE
)
CALLBACK_NEEDLE = (
    "                            should_drop = abs(coefficient) < threshold\n"
)
CALLBACK_REPLACEMENT = (
    "                            should_drop = p6_should_drop(\n"
    "                                p6_drop_decision, mask, coefficient, "
    "threshold,\n"
    "                            )\n"
)
VALIDATION_NEEDLE = (
    "                        drop_rows_digest = "
    "finish_canonical_array!(drop_hasher)\n"
)
VALIDATION_REPLACEMENT = (
    "                        p6_validate_selected_drop_ticks!(\n"
    "                            p6_drop_decision, transition_drop_ticks, "
    "dropped,\n"
    "                        )\n"
    + VALIDATION_NEEDLE
)

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
    "boundary_index", "operation",
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
    "uncapped_adaptive_selection_boundaries_equal_completed_step2_truncation_boundaries",
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
STEP2_CAP_OBSERVATION = {
    "maximum_step2_accuracy_charged_events":
        ("accuracy_event_counters", "accuracy_charged_event_count"),
    "maximum_step2_anticommuting_events":
        ("accuracy_event_counters", "anticommuting_event_count"),
    "maximum_step2_boundary_retained_terms":
        (None, "peak_postmerge_unique_term_count"),
    "maximum_step2_cap_scan_term_visits":
        ("P2_resource_counters", "cap_scan_term_visits"),
    "maximum_step2_current_terms_before_constituent":
        (None, "peak_postmerge_unique_term_count"),
    "maximum_step2_drop_defect_events":
        ("accuracy_event_counters", "drop_defect_event_count"),
    "maximum_step2_final_retained_terms":
        (None, "final_retained_term_count"),
    "maximum_step2_merge_defect_events":
        ("accuracy_event_counters", "merge_defect_event_count"),
    "maximum_step2_premerge_terms":
        (None, "peak_premerge_contribution_count"),
    "maximum_step2_product_defect_events":
        ("accuracy_event_counters", "product_defect_event_count"),
    "maximum_step2_propagation_term_visits":
        ("P2_resource_counters", "propagation_term_visits"),
    "maximum_step2_total_P2_charged_term_visits":
        ("P2_resource_counters", "total_charged_term_visits"),
    "maximum_step2_total_P2_plus_accuracy_charged_events":
        (None, "total_P2_plus_accuracy_charged_event_count"),
    "maximum_step2_truncation_term_visits":
        ("P2_resource_counters", "truncation_term_visits"),
}
SELECTION_CAP_OBSERVATION = {
    "maximum_ranking_scan_term_visits": "total_ranking_scan_term_visits",
    "maximum_sort_input_items": "total_sort_work_items",
    "maximum_tick_evaluations": "total_tick_evaluations",
    "maximum_selected_membership_insertions":
        "total_selected_membership_insertions",
    "maximum_peak_ranking_buffer_terms": "peak_ranking_buffer_terms",
    "maximum_total_selection_work_units": "total_selection_work_units",
}


class ProbeError(RuntimeError):
    """Fail-closed P6 D0 validation error."""


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


def load_json(path: Path) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProbeError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
        )
    except json.JSONDecodeError as error:
        raise ProbeError(f"invalid JSON: {path}") from error


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
        raise ProbeError("P6 D0 source_files is empty or malformed")
    pins: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "size_bytes", "sha256",
        }:
            raise ProbeError("malformed P6 D0 source pin")
        relative = row["relative_path"]
        if not isinstance(relative, str) or relative in pins:
            raise ProbeError("duplicate or invalid P6 D0 source pin")
        pins[relative] = row
    return pins


def _validate_transform(policy: Mapping[str, Any]) -> None:
    transform = policy.get("staged_instrumentation_transform")
    if not isinstance(transform, dict):
        raise ProbeError("missing P6 D0 staged transform")
    expected = {
        "source_relative_path": P5_RUNNER,
        "selection_prepare_needle": PREPARE_NEEDLE,
        "selection_prepare_replacement": PREPARE_REPLACEMENT,
        "callback_needle": CALLBACK_NEEDLE,
        "callback_replacement": CALLBACK_REPLACEMENT,
        "selection_validation_needle": VALIDATION_NEEDLE,
        "selection_validation_replacement": VALIDATION_REPLACEMENT,
        "each_needle_must_have_exactly_one_occurrence": True,
        "repository_source_is_not_modified": True,
    }
    for key, value in expected.items():
        if transform.get(key) != value:
            raise ProbeError(f"P6 D0 staged transform drift: {key}")
    for key in (
        "control_mode_prepare_returns_a_noop_sentinel_callback_retains_the_original_strict_K37_rule_and_all_selection_counters_remain_zero",
        "formal_mode_threshold_argument_only_revalidates_the_2^-37_lazy_anchor_bits_and_never_creates_pool_only_scientific_eligibility",
        "prepare_helper_is_read_only_over_merged_main_and_authoritative_ticks",
        "all_deletion_and_the_only_authoritative_drop_charge_remain_on_the_existing_callback_and_drop_ledger_path",
    ):
        if transform.get(key) is not True:
            raise ProbeError(f"P6 D0 transform semantic guard drift: {key}")


def _instrument_p5(body: bytes, policy: Mapping[str, Any]) -> bytes:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProbeError("P5 runner is not UTF-8") from error
    transform = policy["staged_instrumentation_transform"]
    pairs = (
        (transform["selection_prepare_needle"],
         transform["selection_prepare_replacement"]),
        (transform["callback_needle"], transform["callback_replacement"]),
        (transform["selection_validation_needle"],
         transform["selection_validation_replacement"]),
    )
    for needle, replacement in pairs:
        if text.count(needle) != 1:
            raise ProbeError("P5 transform needle occurrence count is not one")
        if replacement in text:
            raise ProbeError("repository P5 runner is already transformed")
        text = text.replace(needle, replacement, 1)
    for _needle, replacement in pairs:
        if text.count(replacement) != 1:
            raise ProbeError("P5 staged transform did not close")
    if text.count(CALLBACK_NEEDLE) != 0:
        raise ProbeError("P5 callback transform left the original decision")
    return text.encode("utf-8")


def _validate_fixture(fixture: Any) -> Mapping[str, Any]:
    if (not isinstance(fixture, dict)
            or type(fixture.get("schema_version")) is not int
            or fixture.get("schema_version") != 1):
        raise ProbeError("malformed P6 D0 fixture")
    if fixture.get("fixture_id") != FIXTURE_ID:
        raise ProbeError("unexpected P6 D0 fixture identity")
    if fixture.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise ProbeError("unexpected P6 D0 fixture parent")
    if fixture.get("scientific_authority") != "NONE":
        raise ProbeError("P6 D0 fixture claims scientific authority")
    if fixture.get("certificate_eligible") is not False:
        raise ProbeError("P6 D0 fixture is certificate eligible")
    design = fixture.get("candidate_design", {})
    if design.get("probe_order") != list(MODE_ORDER):
        raise ProbeError("P6 D0 fixture mode order drift")
    if design.get("formal_candidates") != [ADAPTIVE_MODE]:
        raise ProbeError("P6 D0 fixture formal candidate drift")
    if design.get("control_candidate") != CONTROL_MODE:
        raise ProbeError("P6 D0 fixture control drift")
    rule = fixture.get("full_domain_adaptive_rule", {})
    grid = 1 << 128
    strict_max = (grid - 1) // 400000
    if rule.get("grid_denominator") != str(grid):
        raise ProbeError("P6 D0 grid drift")
    if rule.get("maximum_strictly_legal_local_ticks") != str(strict_max):
        raise ProbeError("P6 D0 strict local maximum drift")
    if rule.get("raw_boundary_indices") != "0_through_767":
        raise ProbeError("P6 D0 raw boundary domain drift")
    if rule.get("released_prefix_number_q") != (
        "raw_boundary_index_plus_one_in_1_through_768"
    ):
        raise ProbeError("P6 D0 released-prefix mapping drift")
    lazy = fixture.get("exact_lazy_implementation", {})
    if lazy.get("split_threshold_exponent") != 37:
        raise ProbeError("P6 D0 lazy split drift")
    if lazy.get("hard_K37_eligibility_gate_is_forbidden") is not True:
        raise ProbeError("P6 D0 fixture permits a hard K37 gate")
    return fixture


def validate_policy(
    policy: Any, *, require_report_absent: bool,
) -> Mapping[str, Any]:
    if (not isinstance(policy, dict)
            or type(policy.get("schema_version")) is not int
            or policy.get("schema_version") != 1):
        raise ProbeError("malformed P6 D0 policy")
    if policy.get("policy_id") != POLICY_ID:
        raise ProbeError("unexpected P6 D0 policy identity")
    if policy.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise ProbeError("unexpected P6 D0 direct parent")
    if policy.get("scientific_authority") != "NONE":
        raise ProbeError("P6 D0 policy claims scientific authority")
    if policy.get("certificate_eligible") is not False:
        raise ProbeError("P6 D0 policy is certificate eligible")
    design = policy.get("candidate_design", {})
    if design.get("probe_mode_order") != list(MODE_ORDER):
        raise ProbeError("P6 D0 policy mode order drift")
    if design.get("formal_candidate_order_is_frozen_before_any_D0_output") != [
        CANDIDATE_IDS[ADAPTIVE_MODE]
    ]:
        raise ProbeError("P6 D0 formal candidate set drift")
    formal = design.get("formal_candidates")
    if not isinstance(formal, list) or len(formal) != 1:
        raise ProbeError("P6 D0 does not have exactly one formal candidate")
    if formal[0].get("probe_mode") != ADAPTIVE_MODE:
        raise ProbeError("P6 D0 formal candidate mode drift")
    if formal[0].get("candidate_id") != CANDIDATE_IDS[ADAPTIVE_MODE]:
        raise ProbeError("P6 D0 formal candidate identity drift")
    algorithm = policy.get("scientific_algorithm", {})
    if algorithm.get("strict_local_maximum_formula") != (
        "floor((2^128-1)/400000)"
    ):
        raise ProbeError("P6 D0 local budget formula drift")
    if algorithm.get("lazy_k37_accelerator", {}).get(
        "hard_K37_pool_only_stopping_with_positive_remaining_ticks_is_forbidden"
    ) is not True:
        raise ProbeError("P6 D0 policy permits a hard K37 gate")
    _validate_transform(policy)
    fixture = _validate_fixture(load_json(BASE / FIXTURE_NAME))
    policy_caps = policy.get("D0_deterministic_resource_caps", {})
    for section in (
        "deterministic_step2_probe_caps",
        "deterministic_selection_probe_caps",
    ):
        for key, value in fixture[section].items():
            if policy_caps.get(key) != value:
                raise ProbeError(f"P6 D0 cap drift: {key}")
    host = policy.get("D0_host_supervisor_caps", {})
    if {
        key: host.get(key) for key in (
            "MemoryMax_bytes", "MemorySwapMax_bytes", "RuntimeMaxSec",
            "outer_safety_timeout_seconds", "maximum_stdout_bytes",
            "maximum_stderr_bytes",
        )
    } != {
        "MemoryMax_bytes": 4294967296,
        "MemorySwapMax_bytes": 0,
        "RuntimeMaxSec": "1800s",
        "outer_safety_timeout_seconds": 1830,
        "maximum_stdout_bytes": 1048576,
        "maximum_stderr_bytes": 1048576,
    }:
        raise ProbeError("P6 D0 host caps drift")
    runtime = policy.get("runtime", {})
    if runtime.get("julia_executable_sha256") != (
        "2976d17aba35be5d546e8e315e521bd9be3e58c2e64abfd588f186696e807b7d"
    ):
        raise ProbeError("P6 D0 Julia runtime drift")
    if runtime.get("JULIA_NUM_THREADS") != "1":
        raise ProbeError("P6 D0 Julia thread drift")
    observation_contract = policy.get("D0_observation_contract", {})
    if observation_contract.get("public_cap_event_name_allowlist") != sorted(
        CAP_EVENT_NAMES
    ):
        raise ProbeError("P6 D0 public cap-event allowlist drift")
    if observation_contract.get("public_resource_identities") != list(
        PUBLIC_RESOURCE_IDENTITIES
    ):
        raise ProbeError("P6 D0 public resource identities drift")
    stop_rules = policy.get("stop_rules", {})
    for key in (
        "control_host_failure_terminates_before_candidate_and_report_as_"
        "INDETERMINATE_without_authority",
        "control_deterministic_cap_terminates_before_candidate_and_report_as_"
        "D0_RESOURCE_ENVELOPE_NOT_ESTABLISHED_without_authority",
    ):
        if stop_rules.get(key) is not True:
            raise ProbeError(f"P6 D0 control stop-rule drift: {key}")

    pins = _source_pins(policy)
    expected_paths = set((*STAGED_PATHS, Path(__file__).name))
    if set(pins) != expected_paths:
        raise ProbeError("P6 D0 source pin allowlist drift")
    for relative, row in pins.items():
        path = BASE / relative
        if not path.is_file() or path.is_symlink():
            raise ProbeError(f"missing or nonregular P6 D0 source: {relative}")
        body = path.read_bytes()
        if row.get("size_bytes") != len(body):
            raise ProbeError(f"P6 D0 source size drift: {relative}")
        if row.get("sha256") != hashlib.sha256(body).hexdigest():
            raise ProbeError(f"P6 D0 source hash drift: {relative}")
    _instrument_p5((BASE / P5_RUNNER).read_bytes(), policy)
    if require_report_absent:
        if (BASE / REPORT_NAME).exists():
            raise ProbeError("P6 D0 report exists before the probe commit")
        for relative in RESULT_ARTIFACTS[1:]:
            if (BASE / relative).exists():
                raise ProbeError(f"future P6 artifact exists before D0: {relative}")
    return policy


def stage_probe_tree(
    destination: Path, policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    pins = _source_pins(policy)
    rows: list[dict[str, Any]] = []
    for relative in STAGED_PATHS:
        body = (BASE / relative).read_bytes()
        instrumented = relative == P5_RUNNER
        if instrumented:
            body = _instrument_p5(body, policy)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        rows.append({
            "relative_path": relative,
            "repository_sha256": pins[relative]["sha256"],
            "staged_size_bytes": len(body),
            "staged_sha256": hashlib.sha256(body).hexdigest(),
            "candidate_algorithm_transform_applied": instrumented,
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
    if label != "step2":
        raise ProbeError(f"unexpected P6 D0 resource-summary label: {label}")
    fixture = load_json(BASE / FIXTURE_NAME)
    step2 = fixture["deterministic_step2_probe_caps"]
    selection = fixture["deterministic_selection_probe_caps"]
    return {
        "maximum_current_terms_before_constituent":
            step2["maximum_step2_current_terms_before_constituent"],
        "maximum_premerge_terms": step2["maximum_step2_premerge_terms"],
        "maximum_boundary_retained_terms":
            step2["maximum_step2_boundary_retained_terms"],
        "maximum_cap_scan_term_visits":
            step2["maximum_step2_cap_scan_term_visits"],
        "maximum_propagation_term_visits":
            step2["maximum_step2_propagation_term_visits"],
        "maximum_truncation_term_visits":
            step2["maximum_step2_truncation_term_visits"],
        "maximum_final_evaluation_term_visits":
            step2["maximum_step2_final_retained_terms"],
        "maximum_total_charged_term_visits":
            step2["maximum_step2_total_P2_charged_term_visits"],
        "maximum_anticommuting_events":
            step2["maximum_step2_anticommuting_events"],
        "maximum_product_defect_events":
            step2["maximum_step2_product_defect_events"],
        "maximum_merge_defect_events":
            step2["maximum_step2_merge_defect_events"],
        "maximum_drop_defect_events":
            step2["maximum_step2_drop_defect_events"],
        "maximum_accuracy_charged_events":
            step2["maximum_step2_accuracy_charged_events"],
        "maximum_total_P2_plus_accuracy_charged_events":
            step2["maximum_step2_total_P2_plus_accuracy_charged_events"],
        "maximum_BigInt_bit_length":
            fixture["outward_arithmetic"]["maximum_BigInt_bit_length"],
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


def _validate_cap_event(value: Any, cap_limits: Mapping[str, int]) -> None:
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {
        "cap_name", "limit", "attempted", "context",
        "rejected_operation_was_not_executed_after_cap_detection",
    }:
        raise ProbeError("malformed P6 D0 cap event")
    if value["rejected_operation_was_not_executed_after_cap_detection"] is not True:
        raise ProbeError("P6 D0 cap executed the rejected operation")
    if value["cap_name"] not in cap_limits:
        raise ProbeError("P6 D0 cap name is outside the frozen allowlist")
    for key in ("limit", "attempted"):
        if (not isinstance(value[key], int) or isinstance(value[key], bool)
                or value[key] < 0):
            raise ProbeError(f"invalid P6 D0 cap value: {key}")
    if value["attempted"] <= value["limit"]:
        raise ProbeError("P6 D0 cap attempted value does not exceed its limit")
    if value["limit"] != cap_limits[value["cap_name"]]:
        raise ProbeError("P6 D0 cap limit differs from the frozen limit")
    context = value["context"]
    if (not isinstance(context, dict) or not set(context) <= CAP_CONTEXT_KEYS
            or "operation" not in context):
        raise ProbeError("malformed P6 D0 sanitized cap context")
    if context["operation"] != "resource_cap_precheck":
        raise ProbeError("P6 D0 cap context exposes an unfrozen operation")
    if "group" in context and (
        not isinstance(context["group"], str) or not context["group"]
    ):
        raise ProbeError("invalid P6 D0 cap context group")
    for key in CAP_CONTEXT_KEYS - {"group", "operation"}:
        if key in context and (
            not isinstance(context[key], int) or isinstance(context[key], bool)
            or context[key] < 0
        ):
            raise ProbeError(f"invalid P6 D0 cap context index: {key}")


def _validate_resource_summary(value: Any, label: str) -> None:
    if not isinstance(value, dict) or set(value) != RESOURCE_SUMMARY_KEYS:
        raise ProbeError(f"malformed P6 D0 {label} resource summary")
    if (not isinstance(value["P2_resource_counters"], dict)
            or set(value["P2_resource_counters"]) != P2_COUNTER_KEYS):
        raise ProbeError(f"malformed P6 D0 {label} P2 counters")
    if (not isinstance(value["accuracy_event_counters"], dict)
            or set(value["accuracy_event_counters"]) != ACCURACY_COUNTER_KEYS):
        raise ProbeError(f"malformed P6 D0 {label} accuracy counters")
    for key, item in value.items():
        if key in {
            "P2_resource_counters", "accuracy_event_counters", "cap_event",
            "final_retained_term_count",
        }:
            continue
        if (not isinstance(item, int) or isinstance(item, bool) or item < 0):
            raise ProbeError(f"invalid P6 D0 {label} resource count: {key}")
    for group in (value["P2_resource_counters"], value["accuracy_event_counters"]):
        if any(
            not isinstance(item, int) or isinstance(item, bool) or item < 0
            for item in group.values()
        ):
            raise ProbeError(f"invalid P6 D0 {label} nested resource count")
    cap_limits = _step_cap_limits(label)
    _validate_cap_event(value["cap_event"], cap_limits)
    p2 = value["P2_resource_counters"]
    accuracy = value["accuracy_event_counters"]
    if p2["total_charged_term_visits"] != (
        p2["cap_scan_term_visits"]
        + p2["propagation_term_visits"]
        + p2["truncation_term_visits"]
        + p2["final_evaluation_term_visits"]
    ):
        raise ProbeError(f"P6 D0 {label} P2 resource identity mismatch")
    if accuracy["accuracy_charged_event_count"] != (
        accuracy["product_defect_event_count"]
        + accuracy["merge_defect_event_count"]
        + accuracy["drop_defect_event_count"]
    ):
        raise ProbeError(f"P6 D0 {label} accuracy resource identity mismatch")
    if accuracy["product_defect_event_count"] != (
        2 * accuracy["anticommuting_event_count"]
    ):
        raise ProbeError(f"P6 D0 {label} product/anticommuting identity mismatch")
    if value["cap_event"] is None:
        if value["anticommuting_split_count"] != accuracy[
            "anticommuting_event_count"
        ]:
            raise ProbeError(
                f"P6 D0 {label} split/anticommuting identity mismatch"
            )
        if value["threshold_dropped_term_count"] != accuracy[
            "drop_defect_event_count"
        ]:
            raise ProbeError(f"P6 D0 {label} drop-event identity mismatch")
    elif (
        value["anticommuting_split_count"]
        > accuracy["anticommuting_event_count"]
        or value["threshold_dropped_term_count"]
        > accuracy["drop_defect_event_count"]
    ):
        raise ProbeError(f"P6 D0 {label} capped progress exceeds charged events")
    if value["total_P2_plus_accuracy_charged_event_count"] != (
        p2["total_charged_term_visits"]
        + accuracy["accuracy_charged_event_count"]
    ):
        raise ProbeError(f"P6 D0 {label} combined resource identity mismatch")
    if (
        value["completed_composite_count"] > 512
        or value["completed_constituent_count"] > 1152
        or value["completed_truncation_boundary_count"] > 768
    ):
        raise ProbeError(f"P6 D0 {label} completed-count bound exceeded")
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
            raise ProbeError(f"P6 D0 {label} P2 count exceeds its probe cap")
    accuracy_limits = {
        "anticommuting_event_count": "maximum_anticommuting_events",
        "product_defect_event_count": "maximum_product_defect_events",
        "merge_defect_event_count": "maximum_merge_defect_events",
        "drop_defect_event_count": "maximum_drop_defect_events",
        "accuracy_charged_event_count": "maximum_accuracy_charged_events",
    }
    for field, cap_name in accuracy_limits.items():
        if accuracy[field] > cap_limits[cap_name]:
            raise ProbeError(f"P6 D0 {label} accuracy count exceeds its probe cap")
    if value["total_P2_plus_accuracy_charged_event_count"] > cap_limits[
        "maximum_total_P2_plus_accuracy_charged_events"
    ]:
        raise ProbeError(f"P6 D0 {label} combined count exceeds its probe cap")
    premerge_cap = cap_limits["maximum_premerge_terms"]
    if (
        value["peak_premerge_contribution_count"] > premerge_cap
        or value["peak_postmerge_unique_term_count"] > premerge_cap
    ):
        raise ProbeError(f"P6 D0 {label} peak term count exceeds its probe cap")
    final_count = value["final_retained_term_count"]
    if value["cap_event"] is None:
        if (not isinstance(final_count, int) or isinstance(final_count, bool)
                or final_count < 0):
            raise ProbeError(f"missing P6 D0 {label} completed final count")
        final_cap_name = (
            "final_evaluation_term_visits" if label == "step1"
            else "maximum_final_evaluation_term_visits"
        )
        if final_count > cap_limits[final_cap_name]:
            raise ProbeError(f"P6 D0 {label} final count exceeds its probe cap")
        if final_count != p2["final_evaluation_term_visits"]:
            raise ProbeError(f"P6 D0 {label} final-evaluation identity mismatch")
    elif final_count is not None:
        raise ProbeError(f"capped P6 D0 {label} exposes a final count")
    elif p2["final_evaluation_term_visits"] != 0:
        raise ProbeError(f"capped P6 D0 {label} exposes final-evaluation work")


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
                raise ProbeError(f"forbidden P6 D0 public key at {path}.{key}")
            _reject_public_scientific_vocabulary(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_public_scientific_vocabulary(item, f"{path}[{index}]")
    elif isinstance(value, str):
        lower = value.lower()
        if any(fragment in lower for fragment in forbidden):
            raise ProbeError(f"forbidden P6 D0 public string at {path}")


def validate_public_witness(witness: Any, *, mode: str) -> Mapping[str, Any]:
    expected_top = {
        "schema_version", "probe_type", "scientific_authority",
        "certificate_eligible", "result_contract_eligible",
        "resource_observations_only", "candidate", "step1", "step2",
        "step_link", "selection_resources", "explicit_exclusions",
    }
    if not isinstance(witness, dict) or set(witness) != expected_top:
        raise ProbeError(f"malformed P6 D0 witness for {mode}")
    if (type(witness["schema_version"]) is not int
            or witness["schema_version"] != 1
            or witness["probe_type"] != PROBE_TYPE):
        raise ProbeError("unexpected P6 D0 witness identity")
    if witness["scientific_authority"] != "NONE":
        raise ProbeError("P6 D0 witness claims scientific authority")
    for key in ("certificate_eligible", "result_contract_eligible"):
        if witness[key] is not False:
            raise ProbeError(f"P6 D0 witness enables {key}")
    if witness["resource_observations_only"] is not True:
        raise ProbeError("P6 D0 witness is not resource-only")
    candidate = witness["candidate"]
    if not isinstance(candidate, dict) or set(candidate) != {
        "candidate_id", "probe_mode", "identity", "control_candidate",
        "formal_candidate", "step1_path", "step2_path",
    }:
        raise ProbeError("malformed P6 D0 candidate identity")
    if candidate["probe_mode"] != mode or candidate["identity"] != mode:
        raise ProbeError("P6 D0 candidate mode drift")
    if candidate["candidate_id"] != CANDIDATE_IDS[mode]:
        raise ProbeError("P6 D0 candidate ID drift")
    if candidate["control_candidate"] is not (mode == CONTROL_MODE):
        raise ProbeError("P6 D0 control truth drift")
    if candidate["formal_candidate"] is not (mode == ADAPTIVE_MODE):
        raise ProbeError("P6 D0 formal truth drift")
    expected_step2_path = (
        "fixed_P5_K37_resource_control" if mode == CONTROL_MODE
        else "full_domain_E768_MAX_LAZY37_V1"
    )
    if candidate["step1_path"] != "fixed_P3_2^-34":
        raise ProbeError("P6 D0 step-1 identity drift")
    if candidate["step2_path"] != expected_step2_path:
        raise ProbeError("P6 D0 step-2 identity drift")
    _validate_resource_summary(witness["step1"], "step1")
    if witness["step1"]["cap_event"] is None:
        if (
            witness["step1"]["completed_composite_count"] != 512
            or witness["step1"]["completed_constituent_count"] != 1152
            or witness["step1"]["completed_truncation_boundary_count"] != 768
            or witness["step1"]["final_retained_term_count"] == 0
        ):
            raise ProbeError("P6 D0 completed step 1 has incomplete resources")
    step2 = witness["step2"]
    if step2 is not None:
        _validate_resource_summary(step2, "step2")
        if step2["cap_event"] is None and (
            step2["completed_composite_count"] != 512
            or step2["completed_constituent_count"] != 1152
            or step2["completed_truncation_boundary_count"] != 768
            or step2["final_retained_term_count"] == 0
        ):
            raise ProbeError("P6 D0 completed step 2 has incomplete resources")
    link = witness["step_link"]
    if step2 is None:
        if link is not None or witness["step1"]["cap_event"] is None:
            raise ProbeError("P6 D0 missing step 2 without a step-1 cap")
    else:
        if link is None or witness["step1"]["cap_event"] is not None:
            raise ProbeError("P6 D0 step-link/step-2 lifecycle mismatch")
        if not isinstance(link, dict) or set(link) != {
            "same_process", "checkpoint_or_serialized_state_used",
            "step1_final_term_count", "step2_input_term_count",
        }:
            raise ProbeError("malformed P6 D0 step link")
        if link["same_process"] is not True:
            raise ProbeError("P6 D0 step link is not same-process")
        if link["checkpoint_or_serialized_state_used"] is not False:
            raise ProbeError("P6 D0 step link used a checkpoint")
        for key in ("step1_final_term_count", "step2_input_term_count"):
            if (not isinstance(link[key], int) or isinstance(link[key], bool)
                    or link[key] < 0):
                raise ProbeError("invalid P6 D0 step-link term count")
        if link["step1_final_term_count"] != link["step2_input_term_count"]:
            raise ProbeError("P6 D0 step-link term count mismatch")
        if link["step1_final_term_count"] != witness["step1"][
            "final_retained_term_count"
        ]:
            raise ProbeError("P6 D0 step link differs from the step-1 final state")
    selection = witness["selection_resources"]
    if not isinstance(selection, dict) or set(selection) != SELECTION_RESOURCE_KEYS:
        raise ProbeError("malformed P6 D0 selection resources")
    if any(
        not isinstance(item, int) or isinstance(item, bool) or item < 0
        for item in selection.values()
    ):
        raise ProbeError("invalid P6 D0 selection resource count")
    expected_total = (
        selection["total_ranking_scan_term_visits"]
        + selection["total_sort_work_items"]
        + selection["total_tick_evaluations"]
        + selection["total_selected_membership_insertions"]
    )
    if selection["total_selection_work_units"] != expected_total:
        raise ProbeError("P6 D0 selection work identity mismatch")
    selection_caps = load_json(BASE / FIXTURE_NAME)[
        "deterministic_selection_probe_caps"
    ]
    selection_limits = {
        "total_ranking_scan_term_visits": "maximum_ranking_scan_term_visits",
        "total_sort_work_items": "maximum_sort_input_items",
        "total_tick_evaluations": "maximum_tick_evaluations",
        "total_selected_membership_insertions":
            "maximum_selected_membership_insertions",
        "peak_ranking_buffer_terms": "maximum_peak_ranking_buffer_terms",
        "total_selection_work_units": "maximum_total_selection_work_units",
    }
    for field, cap_name in selection_limits.items():
        if selection[field] > selection_caps[cap_name]:
            raise ProbeError("P6 D0 selection resource count exceeds its probe cap")
    if selection["completed_selection_boundary_count"] > 768:
        raise ProbeError("P6 D0 selection boundary count exceeds the schedule")
    if mode == CONTROL_MODE and any(selection.values()):
        raise ProbeError("P6 D0 control accumulated adaptive work")
    if step2 is None and any(selection.values()):
        raise ProbeError("P6 D0 accumulated selection work without step 2")
    if mode == ADAPTIVE_MODE and step2 is not None:
        selection_boundaries = selection["completed_selection_boundary_count"]
        step2_boundaries = step2["completed_truncation_boundary_count"]
        if step2["cap_event"] is None:
            if selection_boundaries != step2_boundaries:
                raise ProbeError("P6 D0 selection/step-2 boundary identity mismatch")
        elif selection_boundaries not in {
            step2_boundaries, step2_boundaries + 1,
        }:
            raise ProbeError("P6 D0 capped selection boundary progress mismatch")
    if (
        mode == ADAPTIVE_MODE and step2 is not None
        and step2["cap_event"] is None
        and selection["completed_selection_boundary_count"] != 768
    ):
        raise ProbeError("P6 D0 completed adaptive selection has wrong boundary count")
    if witness["explicit_exclusions"] != PUBLIC_EXCLUSIONS:
        raise ProbeError("P6 D0 public exclusions drift")
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


def _run_candidate(
    staging: Path, mode: str, julia: Path, depot: Path,
    host: Mapping[str, Any], scratch_root: Path,
) -> dict[str, Any]:
    scratch = scratch_root / mode.lower()
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    unit = f"majorana-p6-d0-{mode.lower().replace('_', '-')}-{uuid.uuid4().hex}"
    julia_command = [
        "/usr/bin/time", "-v", str(julia), "--startup-file=no",
        "--history-file=no", "--compiled-modules=no",
        f"--project={staging / 'majorana_certificate_p0'}",
        str(staging / PROBE_DRIVER),
        str(staging / FIXTURE_NAME),
        str(staging / "majorana_certificate_p5_fixture.json"),
        str(staging / "majorana_certificate_p4_fixture.json"),
        str(staging / "majorana_certificate_p3_fixture.json"),
        str(staging / "majorana_certificate_p2_fixture.json"),
        mode,
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
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
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
    observation: dict[str, Any] = {
        "probe_mode": mode,
        "candidate_id": CANDIDATE_IDS[mode],
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
    failed = (
        timed_out
        or len(stdout) > host["maximum_stdout_bytes"]
        or len(stderr) > host["maximum_stderr_bytes"]
        or process.returncode != 0
    )
    if failed:
        observation["status"] = "INDETERMINATE_HOST_OR_RUNTIME_FAILURE"
        observation["resource_witness"] = None
        return observation
    try:
        witness = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise ProbeError(f"P6 D0 {mode} stdout is not JSON") from error
    if stdout != canonical_bytes(witness) + b"\n":
        raise ProbeError(f"P6 D0 {mode} stdout is not canonical JSON")
    validate_public_witness(witness, mode=mode)
    observation["status"] = "COMPLETED_RESOURCE_OBSERVATION"
    observation["resource_witness"] = witness
    observation["resource_witness_sha256"] = canonical_sha256(witness)
    return observation


def _control_projection(witness: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "step1": witness["step1"],
        "step2": witness["step2"],
        "step_link": witness["step_link"],
        "selection_resources": witness["selection_resources"],
    }


def _validate_control(
    observation: Mapping[str, Any], policy: Mapping[str, Any],
) -> None:
    if observation.get("status") == "INDETERMINATE_HOST_OR_RUNTIME_FAILURE":
        raise ProbeError(
            "P6_D0_CONTROL_INDETERMINATE: control host/runtime failure; "
            "candidate and report were not executed or materialized"
        )
    if observation.get("status") != "COMPLETED_RESOURCE_OBSERVATION":
        raise ProbeError("P6 D0 control has an invalid observation status")
    witness = observation.get("resource_witness")
    if (
        not isinstance(witness, dict)
        or witness["step1"]["cap_event"] is not None
        or witness["step2"] is None
        or witness["step2"]["cap_event"] is not None
    ):
        raise ProbeError(
            "P6_D0_RESOURCE_ENVELOPE_NOT_ESTABLISHED: control deterministic "
            "cap; candidate and report were not executed or materialized"
        )
    actual = _control_projection(witness)
    expected = policy["expected_P5_K37_control_resource_projection"]
    if actual != expected:
        raise ProbeError(
            "P6_D0_INVALID_CONTROL_PROJECTION: control differs from the "
            "frozen P5 K37 resource projection; candidate and report were "
            "not executed or materialized"
        )


def _ceil_power_of_two(value: int) -> int:
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def _derive_formal_resource_envelope(
    observations: Sequence[Mapping[str, Any]], policy: Mapping[str, Any],
) -> dict[str, Any]:
    if len(observations) != 2 or any(
        row.get("status") != "COMPLETED_RESOURCE_OBSERVATION"
        for row in observations
    ):
        return {
            "status": "NOT_ESTABLISHED_INCOMPLETE_OR_HOST_FAILURE",
            "formal_step2_caps": None,
            "formal_selection_caps": None,
            "formal_host_caps": None,
        }
    witnesses = [row.get("resource_witness") for row in observations]
    if any(not isinstance(row, dict) for row in witnesses):
        return {
            "status": "NOT_ESTABLISHED_INCOMPLETE_OR_HOST_FAILURE",
            "formal_step2_caps": None,
            "formal_selection_caps": None,
            "formal_host_caps": None,
        }
    if any(
        row["step1"]["cap_event"] is not None
        or row["step2"] is None
        or row["step2"]["cap_event"] is not None
        for row in witnesses
    ):
        return {
            "status": "NOT_ESTABLISHED_DETERMINISTIC_CAP",
            "formal_step2_caps": None,
            "formal_selection_caps": None,
            "formal_host_caps": None,
        }
    step2_caps: dict[str, int] = {}
    for cap_name, (group, field) in STEP2_CAP_OBSERVATION.items():
        values = [
            int(witness["step2"][field] if group is None
                else witness["step2"][group][field])
            for witness in witnesses
        ]
        step2_caps[cap_name] = _ceil_power_of_two(2 * max(values))
    selection_caps: dict[str, int] = {}
    for cap_name, field in SELECTION_CAP_OBSERVATION.items():
        values = [int(witness["selection_resources"][field]) for witness in witnesses]
        selection_caps[cap_name] = _ceil_power_of_two(2 * max(values))
    rss_values = [
        row.get("time_diagnostics", {}).get("maximum_resident_set_size_KiB")
        for row in observations
    ]
    if any(not isinstance(value, int) or value <= 0 for value in rss_values):
        return {
            "status": "NOT_ESTABLISHED_MISSING_HOST_DIAGNOSTICS",
            "formal_step2_caps": None,
            "formal_selection_caps": None,
            "formal_host_caps": None,
        }
    memory = _ceil_power_of_two(2 * max(rss_values) * 1024)
    elapsed_seconds = max(
        int(math.ceil(row["outer_monotonic_elapsed_ns"] / 1_000_000_000))
        for row in observations
    )
    runtime = int(math.ceil((2 * elapsed_seconds) / 60.0) * 60)
    stderr_cap = _ceil_power_of_two(
        2 * max(row["stderr_bytes"] for row in observations)
    )
    if memory > 4294967296 or runtime > 1800:
        return {
            "status": "NOT_ESTABLISHED_FORMAL_HOST_CEILING",
            "formal_step2_caps": None,
            "formal_selection_caps": None,
            "formal_host_caps": None,
        }
    return {
        "status": "ESTABLISHED_FOR_FUTURE_S0_PRECOMMIT",
        "formal_step2_caps": step2_caps,
        "formal_selection_caps": selection_caps,
        "formal_host_caps": {
            "MemoryMax_bytes": memory,
            "MemorySwapMax_bytes": 0,
            "RuntimeMaxSec": f"{runtime}s",
            "maximum_stderr_bytes": stderr_cap,
        },
    }


def _validate_preprobe_commit_identity(preprobe_commit: Any) -> None:
    if (not isinstance(preprobe_commit, str) or len(preprobe_commit) != 40
            or any(character not in "0123456789abcdef" for character in preprobe_commit)):
        raise ProbeError("P6 D0 preprobe commit is not a full lowercase SHA-1")
    try:
        ancestry = _run_git("rev-list", "--parents", "-n", "1", preprobe_commit)
    except subprocess.CalledProcessError as error:
        raise ProbeError("P6 D0 preprobe commit is not present") from error
    if ancestry.split() != [preprobe_commit, DIRECT_PARENT]:
        raise ProbeError("P6 D0 preprobe commit has the wrong direct parent")
    changed = set(filter(None, _run_git(
        "diff-tree", "--no-commit-id", "--name-only", "-r", preprobe_commit,
    ).splitlines()))
    if changed != PREPROBE_CHANGED_PATHS:
        raise ProbeError("P6 D0 preprobe changed-path allowlist drift")
    artifact = f"{preprobe_commit}:docs/research/fermion-frontier/{REPORT_NAME}"
    if subprocess.run(
        ["git", "cat-file", "-e", artifact], cwd=BASE,
        check=False, capture_output=True,
    ).returncode == 0:
        raise ProbeError("P6 D0 report exists in the preprobe commit")


def _validate_preprobe_commit(preprobe_commit: str) -> None:
    _validate_preprobe_commit_identity(preprobe_commit)
    if _run_git("rev-parse", "HEAD") != preprobe_commit:
        raise ProbeError("P6 D0 HEAD differs from requested preprobe commit")
    if _run_git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ProbeError("P6 D0 worktree is not clean before execution")


def run_probe(
    preprobe_commit: str, julia: Path, depot: Path, output: Path,
) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=True)
    _validate_preprobe_commit(preprobe_commit)
    julia = Path(julia).resolve()
    depot = Path(depot).resolve()
    if not julia.is_file() or file_sha256(julia) != policy["runtime"][
        "julia_executable_sha256"
    ]:
        raise ProbeError("P6 D0 Julia executable custody mismatch")
    if not depot.is_dir():
        raise ProbeError("P6 D0 depot is missing")
    for executable in ("systemd-run", "systemctl", "/usr/bin/time"):
        if shutil.which(executable) is None:
            raise ProbeError(f"P6 D0 missing required executable: {executable}")

    with tempfile.TemporaryDirectory(prefix="majorana-p6-d0-") as temporary:
        root = Path(temporary)
        staging = root / "staging"
        staging.mkdir()
        staging_manifest = stage_probe_tree(staging, policy)
        scratch = root / "scratch"
        scratch.mkdir()
        observations: list[dict[str, Any]] = []
        control = _run_candidate(
            staging, CONTROL_MODE, julia, depot,
            policy["D0_host_supervisor_caps"], scratch,
        )
        observations.append(control)
        _validate_control(control, policy)
        observations.append(_run_candidate(
            staging, ADAPTIVE_MODE, julia, depot,
            policy["D0_host_supervisor_caps"], scratch,
        ))

    envelope = _derive_formal_resource_envelope(observations, policy)
    report = {
        "schema_version": 1,
        "report_type": REPORT_TYPE,
        "policy_id": policy["policy_id"],
        "policy_sha256": file_sha256(BASE / POLICY_NAME),
        "fixture_id": FIXTURE_ID,
        "fixture_sha256": file_sha256(BASE / FIXTURE_NAME),
        "fixture_canonical_sha256": canonical_sha256(load_json(BASE / FIXTURE_NAME)),
        "preprobe_commit_sha": preprobe_commit,
        "scientific_authority": "NONE",
        "certificate_eligible": False,
        "formal_candidate_was_frozen_before_probe": CANDIDATE_IDS[ADAPTIVE_MODE],
        "control_is_not_selectable": True,
        "staging_manifest": staging_manifest,
        "staging_manifest_sha256": canonical_sha256(staging_manifest),
        "host_caps": policy["D0_host_supervisor_caps"],
        "observations": observations,
        "formal_resource_envelope": envelope,
        "authority_exclusions": policy["authority_exclusions"],
    }
    validate_report(report)
    write_canonical_json(output, report)
    return report


def _validate_staging_manifest(
    rows: Any, policy: Mapping[str, Any], expected_sha256: Any,
) -> None:
    if not isinstance(rows, list) or len(rows) != len(STAGED_PATHS):
        raise ProbeError("P6 D0 staging manifest length drift")
    if any(not isinstance(row, dict) for row in rows):
        raise ProbeError("malformed P6 D0 staging row")
    if [row.get("relative_path") for row in rows] != list(STAGED_PATHS):
        raise ProbeError("P6 D0 staging manifest order drift")
    pins = _source_pins(policy)
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "relative_path", "repository_sha256", "staged_size_bytes",
            "staged_sha256", "candidate_algorithm_transform_applied",
        }:
            raise ProbeError("malformed P6 D0 staging row")
        relative = row["relative_path"]
        if (not isinstance(row["staged_size_bytes"], int)
                or isinstance(row["staged_size_bytes"], bool)
                or row["staged_size_bytes"] < 0):
            raise ProbeError("invalid P6 D0 staged size")
        for key in ("repository_sha256", "staged_sha256"):
            if (not isinstance(row[key], str) or len(row[key]) != 64
                    or any(character not in "0123456789abcdef" for character in row[key])):
                raise ProbeError("invalid P6 D0 staging digest")
        if row["repository_sha256"] != pins[relative]["sha256"]:
            raise ProbeError("P6 D0 staging repository hash drift")
        expected_body = (BASE / relative).read_bytes()
        transformed = relative == P5_RUNNER
        if transformed:
            expected_body = _instrument_p5(expected_body, policy)
        if row["candidate_algorithm_transform_applied"] is not transformed:
            raise ProbeError("P6 D0 staging transform flag drift")
        if row["staged_size_bytes"] != len(expected_body):
            raise ProbeError("P6 D0 staged size drift")
        if row["staged_sha256"] != hashlib.sha256(expected_body).hexdigest():
            raise ProbeError("P6 D0 staged hash drift")
    if expected_sha256 != canonical_sha256(rows):
        raise ProbeError("P6 D0 staging manifest hash mismatch")


def _validate_time_diagnostics(value: Any, *, completed: bool) -> None:
    if (not isinstance(value, dict) or not set(value) <= TIME_DIAGNOSTIC_KEYS
            or (completed and set(value) != TIME_DIAGNOSTIC_KEYS)):
        raise ProbeError("malformed P6 D0 time diagnostics")
    for key, item in value.items():
        if key in {
            "maximum_resident_set_size_KiB", "minor_page_faults",
            "major_page_faults",
        }:
            if (not isinstance(item, int) or isinstance(item, bool) or item < 0):
                raise ProbeError(f"invalid P6 D0 time diagnostic: {key}")
        elif not isinstance(item, str) or not item:
            raise ProbeError(f"invalid P6 D0 time diagnostic: {key}")
        elif key in {"user_time_seconds", "system_time_seconds"} and not (
            re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", item)
        ):
            raise ProbeError(f"invalid P6 D0 time diagnostic format: {key}")
        elif key == "elapsed_wall_clock" and not re.fullmatch(
            r"(?:[0-9]+:)?[0-9]+:[0-5][0-9](?:\.[0-9]+)?", item,
        ):
            raise ProbeError("invalid P6 D0 elapsed-wall-clock format")
    _reject_public_scientific_vocabulary(value, "$.time_diagnostics")


def _validate_observation(
    row: Any, mode: str, host: Mapping[str, Any],
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
        raise ProbeError("malformed P6 D0 observation")
    if row["probe_mode"] != mode or row["candidate_id"] != CANDIDATE_IDS[mode]:
        raise ProbeError("P6 D0 observation identity drift")
    if row["host_failure_has_no_mathematical_authority"] is not True:
        raise ProbeError("P6 D0 host failure claims authority")
    if (not isinstance(row["process_returncode"], int)
            or isinstance(row["process_returncode"], bool)):
        raise ProbeError("invalid P6 D0 process return code")
    if not isinstance(row["outer_timeout_triggered"], bool):
        raise ProbeError("invalid P6 D0 timeout flag")
    for key in (
        "stdout_bytes", "stderr_bytes", "outer_monotonic_elapsed_ns",
    ):
        if (not isinstance(row[key], int) or isinstance(row[key], bool)
                or row[key] < 0):
            raise ProbeError("invalid P6 D0 observation resource value")
    if row["outer_monotonic_elapsed_ns"] <= 0:
        raise ProbeError("invalid P6 D0 nonpositive elapsed time")
    for key in ("stdout_sha256", "stderr_sha256"):
        if (not isinstance(row[key], str) or len(row[key]) != 64
                or any(character not in "0123456789abcdef" for character in row[key])):
            raise ProbeError("invalid P6 D0 observation digest")
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
        witness = validate_public_witness(row["resource_witness"], mode=mode)
        if row["resource_witness_sha256"] != canonical_sha256(witness):
            raise ProbeError("P6 D0 resource witness hash mismatch")
        stdout = canonical_bytes(witness) + b"\n"
        if (row["stdout_bytes"] != len(stdout)
                or row["stdout_sha256"] != hashlib.sha256(stdout).hexdigest()):
            raise ProbeError("P6 D0 stdout/resource witness custody mismatch")
        if host_failed:
            raise ProbeError("completed P6 D0 observation has host failure")
    elif row["status"] == "INDETERMINATE_HOST_OR_RUNTIME_FAILURE":
        if row["resource_witness"] is not None:
            raise ProbeError("indeterminate P6 D0 observation retained a witness")
        if not host_failed:
            raise ProbeError("P6 D0 host-failure status has no host failure")
    else:
        raise ProbeError("unexpected P6 D0 observation status")


def validate_report(report: Any) -> Mapping[str, Any]:
    policy = validate_policy(load_json(BASE / POLICY_NAME), require_report_absent=False)
    expected_top = {
        "schema_version", "report_type", "policy_id", "policy_sha256",
        "fixture_id", "fixture_sha256", "fixture_canonical_sha256",
        "preprobe_commit_sha", "scientific_authority", "certificate_eligible",
        "formal_candidate_was_frozen_before_probe", "control_is_not_selectable",
        "staging_manifest", "staging_manifest_sha256", "host_caps",
        "observations", "formal_resource_envelope", "authority_exclusions",
    }
    if not isinstance(report, dict) or set(report) != expected_top:
        raise ProbeError("malformed P6 D0 report")
    if type(report.get("schema_version")) is not int or report.get(
        "schema_version"
    ) != 1:
        raise ProbeError("unexpected P6 D0 report schema")
    if report.get("report_type") != REPORT_TYPE:
        raise ProbeError("unexpected P6 D0 report identity")
    if report.get("policy_id") != POLICY_ID:
        raise ProbeError("P6 D0 report policy identity drift")
    if report.get("policy_sha256") != file_sha256(BASE / POLICY_NAME):
        raise ProbeError("P6 D0 report policy hash mismatch")
    if report.get("fixture_sha256") != file_sha256(BASE / FIXTURE_NAME):
        raise ProbeError("P6 D0 report fixture hash mismatch")
    if report.get("fixture_canonical_sha256") != canonical_sha256(
        load_json(BASE / FIXTURE_NAME)
    ):
        raise ProbeError("P6 D0 report fixture semantic hash mismatch")
    if report.get("scientific_authority") != "NONE":
        raise ProbeError("P6 D0 report claims scientific authority")
    if report.get("certificate_eligible") is not False:
        raise ProbeError("P6 D0 report is certificate eligible")
    if report.get("fixture_id") != FIXTURE_ID:
        raise ProbeError("P6 D0 report fixture identity drift")
    _validate_preprobe_commit_identity(report.get("preprobe_commit_sha"))
    if report.get("host_caps") != policy["D0_host_supervisor_caps"]:
        raise ProbeError("P6 D0 report host cap drift")
    _validate_staging_manifest(
        report.get("staging_manifest"), policy,
        report.get("staging_manifest_sha256"),
    )
    observations = report.get("observations")
    if not isinstance(observations, list) or len(observations) != 2:
        raise ProbeError("P6 D0 report observation count drift")
    if [row.get("probe_mode") for row in observations] != list(MODE_ORDER):
        raise ProbeError("P6 D0 report mode order drift")
    for row, mode in zip(observations, MODE_ORDER):
        _validate_observation(row, mode, policy["D0_host_supervisor_caps"])
    _validate_control(observations[0], policy)
    if (
        observations[1]["resource_witness"] is not None
        and observations[1]["resource_witness"]["step1"]
        != observations[0]["resource_witness"]["step1"]
    ):
        raise ProbeError("P6 D0 fresh step-1 resource projection drift")
    expected_envelope = _derive_formal_resource_envelope(observations, policy)
    if report.get("formal_resource_envelope") != expected_envelope:
        raise ProbeError("P6 D0 formal envelope derivation drift")
    if report.get("authority_exclusions") != policy["authority_exclusions"]:
        raise ProbeError("P6 D0 report authority exclusions drift")
    if report.get("formal_candidate_was_frozen_before_probe") != (
        CANDIDATE_IDS[ADAPTIVE_MODE]
    ):
        raise ProbeError("P6 D0 report formal candidate drift")
    if report.get("control_is_not_selectable") is not True:
        raise ProbeError("P6 D0 report makes the control selectable")
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
        summary = {"status": "VERIFIED_P6_D0_PREPROBE", "policy_id": policy["policy_id"]}
    elif args.run:
        if not all((args.preprobe_commit, args.julia, args.depot)):
            parser.error("run requires preprobe commit, Julia, and depot")
        report = run_probe(args.preprobe_commit, args.julia, args.depot, args.output)
        summary = {
            "status": "COMPLETED_P6_D0_RESOURCE_PROBE",
            "report_sha256": file_sha256(args.output),
            "observation_statuses": [row["status"] for row in report["observations"]],
            "formal_resource_envelope_status":
                report["formal_resource_envelope"]["status"],
        }
    else:
        report = validate_report(load_json(args.output))
        if args.output.read_bytes() != canonical_bytes(report) + b"\n":
            raise ProbeError("P6 D0 report is not canonical JSON plus newline")
        summary = {
            "status": "VERIFIED_P6_D0_RESOURCE_REPORT",
            "report_sha256": file_sha256(args.output),
            "formal_resource_envelope_status":
                report["formal_resource_envelope"]["status"],
        }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
