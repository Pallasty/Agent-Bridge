#!/usr/bin/env python3
"""Independent two-step checker for the Majorana P4 adjacent-step certificate.

The Julia runner is deliberately result-blind: its raw witness contains only a
fresh in-process execution of mapped steps one and two.  This outer checker
first checks that raw witness with an integer-only binary64 RNE oracle.  Only
after that check succeeds does it read the certified P3 result, compare the
fresh step-one projection field by field, and compose P3's operator-error upper
exactly once with the newly replayed step-two local-defect ledger.

P3 supplies the frozen schedule, exact rational trigonometric enclosure,
binary64 helpers, Git helpers, and replay-environment custody helpers.  No P4
fixture or policy is loaded at module-import time, so this module remains
importable while the result-unpinned P4 inputs are being assembled.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Iterable, Mapping, MutableMapping, Sequence
import uuid


BASE = Path(__file__).resolve().parent
FIXTURE_NAME = "majorana_certificate_p4_fixture.json"
POLICY_NAME = "majorana_certificate_p4_policy.json"
PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p4_precommit_contract.json"
RESULT_CONTRACT_NAME = "majorana_certificate_p4_contract.json"
CERTIFICATE_NAME = "majorana_certificate_p4_certificate.json"
RESULT_TEST_NAME = "test_majorana_certificate_p4_result.py"
PRECOMMIT_TEST_NAME = "test_majorana_certificate_p4.py"
CHECKER_NAME = "majorana_certificate_p4_checker.py"
RUNNER_RELATIVE_PATH = "majorana_certificate_p4/majorana_p4_runner.jl"
P3_CHECKER_NAME = "majorana_certificate_p3_checker.py"
P3_RESULT_CONTRACT_NAME = "majorana_certificate_p3_contract.json"
P3_CERTIFICATE_NAME = "majorana_certificate_p3_certificate.json"
P3_RESULT_TEST_NAME = "test_majorana_certificate_p3_result.py"
P3_PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p3_precommit_contract.json"
P3_FIXTURE_NAME = "majorana_certificate_p3_fixture.json"
P2_FIXTURE_NAME = "majorana_certificate_p2_fixture.json"
RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"

REQUIRED_PARENT_COMMIT = "d5b63abe941ff0a723dd7c15a61b9ab8298286ab"
FAILED_V1_PRECOMMIT_COMMIT = "b38b273d64ff9c12f6dc20a5d02b9b422f0a45c5"
FAILED_V1_CHECKER_SHA256 = (
    "e4ea5d6aef906ed2d00d335ada71bc8b56c3e064edfc97e2665282ebd1673cbb"
)

MAXIMUM_STATUS = (
    "VERIFIED_MAJORANA_P4_L8_STAGGERED_MAGNETIZATION_TWO_FUSED_STEPS_"
    "LOCAL_DEFECT_AND_TRUNCATION_OPERATOR_AND_NEEL_EXPECTATION_BOUND_SUBCERTIFICATE"
)
STEP2_EXCEEDS_STATUS = (
    "VERIFIED_MAJORANA_P4_L8_SECOND_STEP_ERROR_BOUND_EXCEEDS_INCREMENT_"
    "ALLOCATION_SUBCERTIFICATE"
)
EXCEEDS_STATUS = (
    "VERIFIED_MAJORANA_P4_L8_TWO_STEP_CUMULATIVE_ERROR_BOUND_EXCEEDS_"
    "ALLOCATION_SUBCERTIFICATE"
)
STEP1_CAP_STATUS = (
    "VERIFIED_MAJORANA_P4_L8_STEP1_RECONSTRUCTION_POLICY_CAP_EXCEEDED_"
    "SUBCERTIFICATE"
)
STEP2_CAP_STATUS = (
    "VERIFIED_MAJORANA_P4_L8_SECOND_STEP_POLICY_CAP_EXCEEDED_SUBCERTIFICATE"
)
FAILED_CONFORMANCE_STATUS = "FAILED_MAJORANA_P4_STEP1_P3_POST_REPLAY_CONFORMANCE"
INDETERMINATE_STATUS = "INDETERMINATE_MAJORANA_P4_REPLAY"
INVALID_STATUS = "INVALID_MAJORANA_P4_REPLAY"

STEP2_ALLOCATION = Fraction(1, 400000)
CUMULATIVE_ALLOCATION = Fraction(1, 200000)


def _load_helper(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P3 = _load_helper("majorana_p4_p3_helper", BASE / P3_CHECKER_NAME)
P2 = P3.P2
P0 = P3.P0
SchemaError = P3.SchemaError
VerificationError = P3.VerificationError
IndeterminateReplay = P3.IndeterminateReplay
canonical_bytes = P3.canonical_bytes
canonical_sha256 = P3.canonical_sha256
file_sha256 = P3.file_sha256
require_exact_keys = P3.require_exact_keys
require_sha256 = P3.require_sha256

GRID = P3.GRID
GRID_BITS = P3.GRID_BITS
SIGN_MASK = P3.SIGN_MASK
EPSILON_BITS = P3.EPSILON_BITS
STAGE_GROUPS = P3.STAGE_GROUPS
REPLAY_ENVIRONMENT_TARGETS = P3.REPLAY_ENVIRONMENT_TARGETS
PARENT_STATUS = P3.MAXIMUM_STATUS

RUNNER_STAGED_PATHS = (
    "majorana_certificate_p0/Manifest.toml",
    "majorana_certificate_p0/Project.toml",
    "majorana_certificate_p2/majorana_p2_runner.jl",
    P2_FIXTURE_NAME,
    "majorana_certificate_p3/majorana_p3_runner.jl",
    P3_FIXTURE_NAME,
    RUNNER_RELATIVE_PATH,
    FIXTURE_NAME,
)

RUNNER_FORBIDDEN_PATHS = (
    "majorana_certificate_p2_contract.json",
    "majorana_certificate_p2_certificate.json",
    "test_majorana_certificate_p2_result.py",
    P3_RESULT_CONTRACT_NAME,
    P3_CERTIFICATE_NAME,
    P3_RESULT_TEST_NAME,
    RESULT_CONTRACT_NAME,
    CERTIFICATE_NAME,
    RESULT_TEST_NAME,
)

# P4's outer checker sees the complete P3 custody/result closure.  The Julia
# stage above is an exact, much smaller allowlist and contains no result bytes.
PRECOMMIT_SOURCE_PATHS = tuple(sorted(set(P3.PRECOMMIT_SOURCE_PATHS) | {
    P3_PRECOMMIT_CONTRACT_NAME,
    P3_RESULT_CONTRACT_NAME,
    P3_CERTIFICATE_NAME,
    P3_RESULT_TEST_NAME,
    RUNNER_RELATIVE_PATH,
    CHECKER_NAME,
    FIXTURE_NAME,
    POLICY_NAME,
    PRECOMMIT_TEST_NAME,
}))

RAW_SCOPE = {
    "fixed_L8_two_adjacent_fused_mapped_steps_execution_only": True,
    "fresh_process_started_from_initial_observable": True,
    "step1_and_step2_same_process_in_memory": True,
    "checkpoint_or_serialized_state_used": False,
    "P3_result_available_to_runner": False,
    "scientific_authority_claimed_by_raw_witness": False,
}

EXPECTED_SCOPE = {
    "maximum_positive_status": MAXIMUM_STATUS,
    "fixed_L8_first_two_adjacent_fused_mapped_steps_exact_prefix_only": True,
    "freshly_executed_Float64_threshold_path": "ASSESSED_BY_LOCAL_DEFECT_AND_DROP_BOUND",
    "operator_norm_error_enclosure": "ASSESSED",
    "checkerboard_Neel_expectation_enclosure": "ASSESSED",
    "parent_step1_error_propagation_factor": 1,
    "global_coefficientwise_interval_state": "NOT_CLAIMED",
    "exact_arithmetic_threshold_drop_set": "NOT_CLAIMED_EQUAL",
    "raw_1280_constituent_threshold_path": "NOT_EXECUTED",
    "double_occupancy": "NOT_ASSESSED",
    "remaining_98_mapped_steps_or_full_R100": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}


def load_json(path: Path) -> Any:
    return P3.load_json(path)


def _format_q(value: Fraction) -> str:
    return P3._format_q(value)


def _positive_int(value: Any, context: str) -> int:
    if type(value) is not int or value <= 0:
        raise SchemaError(f"{context} must be a positive integer")
    return value


_STEP_CAP_KEYS = (
    "maximum_current_terms_before_constituent",
    "maximum_premerge_terms",
    "maximum_boundary_retained_terms",
    "maximum_cap_scan_term_visits",
    "maximum_propagation_term_visits",
    "maximum_truncation_term_visits",
    "maximum_final_evaluation_term_visits",
    "maximum_total_charged_term_visits",
    "maximum_anticommuting_events",
    "maximum_product_defect_events",
    "maximum_merge_defect_events",
    "maximum_drop_defect_events",
    "maximum_accuracy_charged_events",
    "maximum_total_P2_plus_accuracy_charged_events",
    "maximum_composites",
    "maximum_constituents",
    "maximum_truncation_boundaries",
)

_CUMULATIVE_CAP_KEYS = (
    "maximum_current_terms_before_constituent",
    "maximum_premerge_terms",
    "maximum_boundary_retained_terms",
    "maximum_cap_scan_term_visits",
    "maximum_propagation_term_visits",
    "maximum_truncation_term_visits",
    "maximum_final_evaluation_term_visits",
    "maximum_total_charged_term_visits",
    "maximum_anticommuting_events",
    "maximum_product_defect_events",
    "maximum_merge_defect_events",
    "maximum_drop_defect_events",
    "maximum_accuracy_charged_events",
    "maximum_total_P2_plus_accuracy_charged_events",
    "maximum_composites",
    "maximum_constituents",
    "maximum_truncation_boundaries",
)


def _validate_cap_map(value: Any, keys: Sequence[str], context: str) -> Mapping[str, int]:
    if not isinstance(value, dict):
        raise SchemaError(f"{context} must be an object")
    require_exact_keys(value, keys, context)
    for key in keys:
        _positive_int(value[key], f"{context}.{key}")
    return value


def _resource_cap_sections(
    fixture: Mapping[str, Any], base: Path = BASE,
) -> tuple[
    Mapping[str, int], Mapping[str, int], Mapping[str, int], int
]:
    """Return normalized per-step and derived cumulative cap maps.

    Step one is required to use the staged P2/P3 cap objects byte-for-byte.
    Step two uses P4's flat, probe-disclosed cap object.  A cumulative guard is
    derived only from those frozen caps (sum for charged counters/topology and
    max for instantaneous term cardinalities); no observed P4 quantity enters
    this normalization.
    """

    root = fixture.get("deterministic_resource_caps")
    if not isinstance(root, dict):
        raise SchemaError("P4 deterministic_resource_caps must be an object")
    p2_fixture = load_json(base / P2_FIXTURE_NAME)
    p3_fixture = load_json(base / P3_FIXTURE_NAME)
    P2.validate_fixture(p2_fixture)
    P3.validate_fixture(p3_fixture)
    p2_caps = p2_fixture["deterministic_resource_caps"]
    p3_caps = p3_fixture["deterministic_resource_caps"]
    step1 = {
        "maximum_current_terms_before_constituent": p2_caps["maximum_current_terms_before_constituent"],
        "maximum_premerge_terms": p2_caps["maximum_premerge_terms"],
        "maximum_boundary_retained_terms": p2_caps["maximum_boundary_retained_terms"],
        "maximum_cap_scan_term_visits": p2_caps["maximum_cap_scan_term_visits"],
        "maximum_propagation_term_visits": p2_caps["maximum_propagation_term_visits"],
        "maximum_truncation_term_visits": p2_caps["maximum_truncation_term_visits"],
        "maximum_final_evaluation_term_visits": p2_caps["maximum_boundary_retained_terms"],
        "maximum_total_charged_term_visits": p2_caps["maximum_total_charged_term_visits"],
        "maximum_anticommuting_events": p3_caps["maximum_anticommuting_events"],
        "maximum_product_defect_events": p3_caps["maximum_product_defect_events"],
        "maximum_merge_defect_events": p3_caps["maximum_merge_defect_events"],
        "maximum_drop_defect_events": p3_caps["maximum_drop_defect_events"],
        "maximum_accuracy_charged_events": p3_caps["maximum_accuracy_charged_events"],
        "maximum_total_P2_plus_accuracy_charged_events": p3_caps[
            "maximum_total_P2_plus_accuracy_charged_events"
        ],
        "maximum_composites": p2_caps["maximum_composites"],
        "maximum_constituents": p2_caps["maximum_constituents"],
        "maximum_truncation_boundaries": p2_caps["maximum_truncation_boundaries"],
    }
    step2 = {
        "maximum_current_terms_before_constituent": root[
            "maximum_step2_current_terms_before_constituent"
        ],
        "maximum_premerge_terms": root["maximum_step2_premerge_terms"],
        "maximum_boundary_retained_terms": root["maximum_step2_boundary_retained_terms"],
        "maximum_cap_scan_term_visits": root["maximum_step2_cap_scan_term_visits"],
        "maximum_propagation_term_visits": root["maximum_step2_propagation_term_visits"],
        "maximum_truncation_term_visits": root["maximum_step2_truncation_term_visits"],
        "maximum_final_evaluation_term_visits": root["maximum_step2_final_retained_terms"],
        "maximum_total_charged_term_visits": root[
            "maximum_step2_total_P2_charged_term_visits"
        ],
        "maximum_anticommuting_events": root["maximum_step2_anticommuting_events"],
        "maximum_product_defect_events": root["maximum_step2_product_defect_events"],
        "maximum_merge_defect_events": root["maximum_step2_merge_defect_events"],
        "maximum_drop_defect_events": root["maximum_step2_drop_defect_events"],
        "maximum_accuracy_charged_events": root["maximum_step2_accuracy_charged_events"],
        "maximum_total_P2_plus_accuracy_charged_events": root[
            "maximum_step2_total_P2_plus_accuracy_charged_events"
        ],
        "maximum_composites": fixture["frozen_execution_relation"][
            "composite_count_per_step"
        ],
        "maximum_constituents": fixture["frozen_execution_relation"][
            "constituent_count_per_step"
        ],
        "maximum_truncation_boundaries": fixture["frozen_execution_relation"][
            "truncation_boundary_count_per_step"
        ],
    }
    _validate_cap_map(step1, _STEP_CAP_KEYS, "normalized P4 step1 caps")
    _validate_cap_map(step2, _STEP_CAP_KEYS, "normalized P4 step2 caps")
    instantaneous = {
        "maximum_current_terms_before_constituent",
        "maximum_premerge_terms", "maximum_boundary_retained_terms",
    }
    cumulative = {
        key: max(step1[key], step2[key]) if key in instantaneous
        else step1[key] + step2[key]
        for key in _CUMULATIVE_CAP_KEYS
    }
    explicit_cumulative = {
        "maximum_total_charged_term_visits": root.get(
            "maximum_two_step_total_P2_charged_term_visits"
        ),
        "maximum_accuracy_charged_events": root.get(
            "maximum_two_step_accuracy_charged_events"
        ),
        "maximum_total_P2_plus_accuracy_charged_events": root.get(
            "maximum_two_step_total_P2_plus_accuracy_charged_events"
        ),
    }
    for key, value in explicit_cumulative.items():
        _positive_int(value, f"P4 cumulative cap {key}")
        if value != cumulative[key]:
            raise VerificationError(
                f"P4 explicit cumulative cap is not the sum of frozen step caps: {key}"
            )
        cumulative[key] = value
    maximum_trig = _positive_int(
        root["maximum_trig_table_entries"], "P4 maximum_trig_table_entries",
    )
    if maximum_trig != len(P3.ALLOWED_ANGLES):
        raise VerificationError("P4 trigonometric table cap must equal the frozen table size")
    return step1, step2, cumulative, maximum_trig


def validate_fixture(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P4 fixture must be an object")
    if value.get("schema_version") != 1 or value.get("fixture_id") != (
        "MAJORANA-P4-L8-FUSED-TWO-STEP-LOCAL-DEFECT-V2"
    ):
        raise SchemaError("unexpected P4 fixture identity")
    parent = value.get("required_parent_P3")
    if not isinstance(parent, dict):
        raise SchemaError("P4 required_parent_P3 must be an object")
    for field in (
        "result_contract_sha256", "certificate_sha256", "fixture_sha256",
        "policy_sha256", "runner_sha256", "checker_sha256",
        "precommit_contract_sha256", "exact_result_test_sha256",
    ):
        require_sha256(parent.get(field), f"P4 parent {field}")
    if (
        parent.get("direct_parent_commit") != REQUIRED_PARENT_COMMIT
        or parent.get("status") != PARENT_STATUS
    ):
        raise VerificationError("P4 direct-parent anchor mismatch")
    if any(key in parent for key in (
        "operator_error_ticks", "total_operator_error_ticks", "E1_ticks",
    )):
        raise VerificationError("P4 fixture exposes the P3 numeric result to the runner")
    failed_v1 = value.get("failed_formal_replay_disclosure", {})
    if (
        failed_v1.get("failed_precommit_commit") != FAILED_V1_PRECOMMIT_COMMIT
        or failed_v1.get("failed_checker_sha256") != FAILED_V1_CHECKER_SHA256
        or failed_v1.get("fresh_raw_processes_completed") != 2
        or failed_v1.get("raw_stdout_was_byte_identical") is not True
        or failed_v1.get("outer_oracle_failed_closed_before_package_materialization")
        is not True
        or failed_v1.get("authoritative_P4_result_generated") is not False
        or failed_v1.get("failed_raw_bytes_are_forbidden_as_v2_replay_inputs")
        is not True
    ):
        raise VerificationError("P4 failed-v1 formal replay disclosure mismatch")
    relation = value["frozen_execution_relation"]
    if (
        relation.get("mapped_step_indices") != [1, 2]
        or relation.get("composite_count_per_step") != 512
        or relation.get("constituent_count_per_step") != 1152
        or relation.get("truncation_boundary_count_per_step") != 768
        or relation.get("total_composite_count_if_completed") != 1024
        or relation.get("total_constituent_count_if_completed") != 2304
        or relation.get("total_truncation_boundary_count_if_completed") != 1536
        or relation.get("threshold_Float64_bits_hex") != P3._bits_hex(EPSILON_BITS)
        or relation.get("P4_must_freshly_execute_both_steps") is not True
        or relation.get(
            "P3_result_is_post_replay_conformance_and_error_inheritance_evidence_not_a_runner_input"
        ) is not True
    ):
        raise VerificationError("P4 frozen execution relation mismatch")
    arithmetic = value["outward_arithmetic"]
    if (
        arithmetic.get("taylor_order") != 7
        or int(arithmetic.get("trig_grid_denominator", 0)) != GRID
        or int(arithmetic.get("defect_grid_denominator", 0)) != GRID
        or _positive_int(
            arithmetic.get("maximum_BigInt_bit_length"),
            "P4 maximum_BigInt_bit_length",
        ) < GRID_BITS
    ):
        raise VerificationError("P4 outward arithmetic mismatch")
    allocation = value["allocation"]
    if (
        Fraction(allocation.get("step2_local_increment_allocation")) != STEP2_ALLOCATION
        or Fraction(allocation.get("two_step_cumulative_allocation"))
        != CUMULATIVE_ALLOCATION
    ):
        raise VerificationError("P4 campaign allocation mismatch")
    _resource_cap_sections(value)
    continuity = value.get("same_process_fresh_two_step_replay", {})
    if (
        continuity.get("fresh_process_starts_from_O0") is not True
        or continuity.get("step1_and_step2_execute_in_the_same_Julia_process") is not True
        or continuity.get(
            "checkpoint_resume_serialization_and_cross_process_step_link_are_forbidden"
        ) is not True
        or continuity.get(
            "step2_input_is_a_deepcopy_of_the_in_memory_step1_retained_mainsum"
        ) is not True
        or continuity.get("step2_local_resource_and_accuracy_counters_start_at_zero") is not True
        or continuity.get(
            "raw_runner_step2_error_counter_contains_local_ticks_only_and_starts_at_zero"
        ) is not True
    ):
        raise VerificationError("P4 same-process fresh replay relation mismatch")
    local_ledger = value.get("step2_local_ledger", {})
    if (
        local_ledger.get(
            "raw_records_must_not_carry_parent_E1_or_any_two_step_cumulative_numeric_bound"
        ) is not True
        or local_ledger.get("each_record_carries_step2_local_ticks_starting_at_zero") is not True
    ):
        raise VerificationError("P4 raw-local ledger causality mismatch")
    host = value["host_supervisor_caps"]
    for field in (
        "MemoryMax_bytes", "subprocess_safety_timeout_seconds",
        "maximum_stdout_bytes", "maximum_stderr_bytes",
    ):
        _positive_int(host.get(field), f"P4 host cap {field}")
    if (
        host.get("systemd_user_scope_cgroup_v2_required") is not True
        or not isinstance(host.get("RuntimeMaxSec"), str)
        or host.get("host_cap_failure_branch") != "INDETERMINATE"
    ):
        raise VerificationError("P4 host-supervisor policy mismatch")
    return value


_BRANCH_STATUS_DEFAULTS = {
    "STEP2_AND_TWO_STEP_BOUND_WITHIN_ALLOCATIONS": MAXIMUM_STATUS,
    "STEP2_BOUND_EXCEEDS_INCREMENT_ALLOCATION_BUT_TWO_STEP_BOUND_WITHIN_CUMULATIVE_ALLOCATION": STEP2_EXCEEDS_STATUS,
    "TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION": EXCEEDS_STATUS,
    "STEP1_P3_DETERMINISTIC_POLICY_CAP_EXCEEDED": STEP1_CAP_STATUS,
    "STEP2_DETERMINISTIC_POLICY_CAP_EXCEEDED": STEP2_CAP_STATUS,
    "FAILED_P3_POST_REPLAY_CONFORMANCE": FAILED_CONFORMANCE_STATUS,
    "INDETERMINATE": INDETERMINATE_STATUS,
    "INVALID_REPLAY": INVALID_STATUS,
}


def validate_policy(value: Any, runtime_lock: Any = None) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P4 policy must be an object")
    if value.get("schema_version") != 1 or value.get("policy_id") != "MAJORANA-P4-S0V2":
        raise SchemaError("unexpected P4 policy identity")
    if value.get("maximum_positive_authority", {}).get("status") != MAXIMUM_STATUS:
        raise VerificationError("P4 maximum authority mismatch")
    branches = {
        row.get("branch"): row.get("maximum_status")
        for row in value.get("legal_terminal_branches", [])
        if isinstance(row, dict)
    }
    if branches != _BRANCH_STATUS_DEFAULTS:
        raise VerificationError("P4 terminal branch/status map mismatch")
    scope = value.get("scope_boundary", {})
    if scope.get("physical_reference_qualified") or scope.get("ready_gate_eligible"):
        raise VerificationError("P4 policy promotes reference or READY")
    visibility = value.get("runner_parent_visibility_policy", {})
    if (
        visibility.get(
            "runner_staging_must_exclude_numeric_parent_E1_and_equivalent_numeric_bounds"
        ) is not True
        or visibility.get("outer_checker_may_read_the_pinned_P3_result_only_after_both_runner_processes_finish") is not True
    ):
        raise VerificationError("P4 runner/parent visibility policy mismatch")
    disclosure = value.get("design_probe_disclosure", {})
    if disclosure.get("authoritative_P4_result_generated") is not False:
        raise VerificationError("P4 policy falsely claims an authoritative result exists")
    failed_v1 = value.get("failed_formal_replay_disclosure", {})
    if (
        failed_v1.get("failed_precommit_commit") != FAILED_V1_PRECOMMIT_COMMIT
        or failed_v1.get("failed_checker_sha256") != FAILED_V1_CHECKER_SHA256
        or failed_v1.get("outer_oracle_failed_closed_before_package_materialization")
        is not True
        or failed_v1.get("diagnostic_checker_fix_requires_a_new_precommit_and_fresh_replays")
        is not True
        or failed_v1.get("scientific_workload_allocations_and_caps_changed") is not False
        or failed_v1.get("authoritative_P4_result_generated") is not False
    ):
        raise VerificationError("P4 policy failed-v1 replay disclosure mismatch")
    environment = value.get("replay_environment_custody", {})
    if (
        environment.get("exact_sandbox_regular_file_target_count") != 18
        or environment.get("only_writable_host_backed_bind_mount_target") != "/scratch"
        or environment.get("private_kernel_virtual_mount_targets") != ["/dev", "/proc"]
        or environment.get("canonical_witness_excludes_replay_environment_custody") is not True
        or environment.get("PID_namespace_unshared") is not True
    ):
        raise VerificationError("P4 replay environment custody policy mismatch")
    if runtime_lock is not None:
        P0.validate_runtime_lock(runtime_lock)
    return value


def validate_precommit_contract(
    value: Any, base: Path = BASE, *, verify_source_files: bool = True,
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P4 precommit contract must be an object")
    require_exact_keys(
        value,
        (
            "schema_version", "contract_type", "self_relative_path",
            "required_parent_commit", "result_artifacts_required_absent",
            "forbidden_formal_result_pins", "source_files",
            "runner_staged_files", "runner_forbidden_paths",
        ),
        "P4 precommit contract",
    )
    if (
        value["schema_version"] != 1
        or value["contract_type"]
        != "majorana_p4_result_unpinned_adjacent_step_replay_input_and_isolation_contract_v2"
        or value["self_relative_path"] != PRECOMMIT_CONTRACT_NAME
        or value["required_parent_commit"] != REQUIRED_PARENT_COMMIT
    ):
        raise VerificationError("P4 precommit identity or parent mismatch")
    policy = validate_policy(load_json(base / POLICY_NAME))
    if value["forbidden_formal_result_pins"] != policy.get("forbidden_formal_result_pins"):
        raise VerificationError("P4 forbidden result pins mismatch")
    if tuple(value["result_artifacts_required_absent"]) != (
        RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME,
    ):
        raise VerificationError("P4 result artifact absence set mismatch")
    if tuple(value["runner_staged_files"]) != RUNNER_STAGED_PATHS:
        raise VerificationError("P4 runner staging allowlist mismatch")
    if tuple(value["runner_forbidden_paths"]) != RUNNER_FORBIDDEN_PATHS:
        raise VerificationError("P4 runner forbidden path set mismatch")
    rows = value["source_files"]
    if not isinstance(rows, list):
        raise SchemaError("P4 source_files must be an array")
    paths: list[str] = []
    for row in rows:
        require_exact_keys(row, ("relative_path", "size_bytes", "sha256"), "P4 source row")
        relative = row["relative_path"]
        if (
            not isinstance(relative, str) or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise SchemaError("invalid P4 source relative path")
        if type(row["size_bytes"]) is not int or row["size_bytes"] < 0:
            raise SchemaError("invalid P4 source size")
        require_sha256(row["sha256"], f"P4 source hash {relative}")
        if verify_source_files:
            path = base / relative
            if path.is_symlink() or not path.is_file():
                raise VerificationError(f"P4 source is not a regular file: {relative}")
            if path.stat().st_size != row["size_bytes"] or file_sha256(path) != row["sha256"]:
                raise VerificationError(f"P4 source custody mismatch: {relative}")
        paths.append(relative)
    if tuple(paths) != PRECOMMIT_SOURCE_PATHS:
        raise VerificationError("P4 source custody allowlist mismatch")
    if not set(RUNNER_STAGED_PATHS).issubset(paths):
        raise VerificationError("P4 runner stage is outside source custody")
    if set(RUNNER_STAGED_PATHS) & set(RUNNER_FORBIDDEN_PATHS):
        raise VerificationError("P4 runner stage exposes a forbidden result")
    return value


class _CapExceeded(Exception):
    def __init__(
        self, *, step_index: int, cap_name: str, cap_scope: str,
        limit: int, attempted: int, context: Mapping[str, Any],
    ) -> None:
        super().__init__(f"{cap_scope} {cap_name}: {attempted} > {limit}")
        clean_context = {
            key: value for key, value in context.items() if key != "step_index"
        }
        self.event = {
            "cap_name": cap_name,
            "cap_scope": cap_scope,
            "limit": limit,
            "attempted": attempted,
            "context": clean_context,
            "rejected_operation_was_not_executed_after_cap_detection": True,
        }


def _p3_compatible_cap_event(error: _CapExceeded) -> dict[str, Any]:
    return {
        key: value for key, value in error.event.items() if key != "cap_scope"
    }


def _check_cap(
    step_index: int, cap_name: str, attempted: int, caps: Mapping[str, int],
    cap_scope: str, context: Mapping[str, Any],
) -> None:
    limit = caps[cap_name]
    if attempted > limit:
        raise _CapExceeded(
            step_index=step_index, cap_name=cap_name, cap_scope=cap_scope,
            limit=limit, attempted=attempted, context=context,
        )


def _check_bigint(
    value: int, maximum_bits: int, step_index: int, context: Mapping[str, Any],
) -> None:
    attempted = abs(value).bit_length()
    if attempted > maximum_bits:
        raise _CapExceeded(
            step_index=step_index, cap_name="maximum_BigInt_bit_length",
            cap_scope="step", limit=maximum_bits, attempted=attempted, context=context,
        )


def _p2_total(counters: Mapping[str, int]) -> int:
    return sum(counters.values())


def _accuracy_total(counters: Mapping[str, int]) -> int:
    return counters["product"] + counters["merge"] + counters["drop"]


def _charge_p2(
    *, step_index: int, field: str, cap_name: str, amount: int,
    local: MutableMapping[str, int], cumulative: MutableMapping[str, int],
    step_caps: Mapping[str, int], cumulative_caps: Mapping[str, int],
    accuracy_local: Mapping[str, int], accuracy_cumulative: Mapping[str, int],
    context: Mapping[str, Any],
) -> None:
    attempted_local = local[field] + amount
    attempted_cumulative = cumulative[field] + amount
    _check_cap(step_index, cap_name, attempted_local, step_caps, "step", context)
    _check_cap(
        step_index, cap_name, attempted_cumulative, cumulative_caps, "cumulative", context,
    )
    _check_cap(
        step_index, "maximum_total_charged_term_visits",
        _p2_total(local) + amount, step_caps, "step", context,
    )
    _check_cap(
        step_index, "maximum_total_charged_term_visits",
        _p2_total(cumulative) + amount, cumulative_caps, "cumulative", context,
    )
    _check_cap(
        step_index, "maximum_total_P2_plus_accuracy_charged_events",
        _p2_total(local) + amount + _accuracy_total(accuracy_local),
        step_caps, "step", context,
    )
    _check_cap(
        step_index, "maximum_total_P2_plus_accuracy_charged_events",
        _p2_total(cumulative) + amount + _accuracy_total(accuracy_cumulative),
        cumulative_caps, "cumulative", context,
    )
    local[field] = attempted_local
    cumulative[field] = attempted_cumulative


def _charge_accuracy(
    *, step_index: int, field: str, cap_name: str, amount: int,
    local: MutableMapping[str, int], cumulative: MutableMapping[str, int],
    step_caps: Mapping[str, int], cumulative_caps: Mapping[str, int],
    p2_local: Mapping[str, int], p2_cumulative: Mapping[str, int],
    context: Mapping[str, Any],
) -> None:
    attempted_local = local[field] + amount
    attempted_cumulative = cumulative[field] + amount
    _check_cap(step_index, cap_name, attempted_local, step_caps, "step", context)
    _check_cap(
        step_index, cap_name, attempted_cumulative, cumulative_caps, "cumulative", context,
    )
    if field != "anticommuting":
        _check_cap(
            step_index, "maximum_accuracy_charged_events",
            _accuracy_total(local) + amount, step_caps, "step", context,
        )
        _check_cap(
            step_index, "maximum_accuracy_charged_events",
            _accuracy_total(cumulative) + amount, cumulative_caps, "cumulative", context,
        )
        _check_cap(
            step_index, "maximum_total_P2_plus_accuracy_charged_events",
            _p2_total(p2_local) + _accuracy_total(local) + amount,
            step_caps, "step", context,
        )
        _check_cap(
            step_index, "maximum_total_P2_plus_accuracy_charged_events",
            _p2_total(p2_cumulative) + _accuracy_total(cumulative) + amount,
            cumulative_caps, "cumulative", context,
        )
    local[field] = attempted_local
    cumulative[field] = attempted_cumulative


def _charge_product_pair(
    *, step_index: int, anticommuting: int,
    local: MutableMapping[str, int], cumulative: MutableMapping[str, int],
    step_caps: Mapping[str, int], cumulative_caps: Mapping[str, int],
    p2_local: Mapping[str, int], p2_cumulative: Mapping[str, int],
    context: Mapping[str, Any],
) -> None:
    product = 2 * anticommuting
    attempted_local_anti = local["anticommuting"] + anticommuting
    attempted_cumulative_anti = cumulative["anticommuting"] + anticommuting
    attempted_local_product = local["product"] + product
    attempted_cumulative_product = cumulative["product"] + product
    _check_cap(
        step_index, "maximum_anticommuting_events", attempted_local_anti,
        step_caps, "step", context,
    )
    _check_cap(
        step_index, "maximum_anticommuting_events", attempted_cumulative_anti,
        cumulative_caps, "cumulative", context,
    )
    _check_cap(
        step_index, "maximum_product_defect_events", attempted_local_product,
        step_caps, "step", context,
    )
    _check_cap(
        step_index, "maximum_product_defect_events", attempted_cumulative_product,
        cumulative_caps, "cumulative", context,
    )
    _check_cap(
        step_index, "maximum_accuracy_charged_events",
        _accuracy_total(local) + product, step_caps, "step", context,
    )
    _check_cap(
        step_index, "maximum_accuracy_charged_events",
        _accuracy_total(cumulative) + product,
        cumulative_caps, "cumulative", context,
    )
    _check_cap(
        step_index, "maximum_total_P2_plus_accuracy_charged_events",
        _p2_total(p2_local) + _accuracy_total(local) + product,
        step_caps, "step", context,
    )
    _check_cap(
        step_index, "maximum_total_P2_plus_accuracy_charged_events",
        _p2_total(p2_cumulative) + _accuracy_total(cumulative) + product,
        cumulative_caps, "cumulative", context,
    )
    local["anticommuting"] = attempted_local_anti
    cumulative["anticommuting"] = attempted_cumulative_anti
    local["product"] = attempted_local_product
    cumulative["product"] = attempted_cumulative_product


def _state_descriptor(state: Mapping[int, int]) -> dict[str, Any]:
    rows = sorted(state.items())
    return {
        "term_count": len(rows),
        "term_stream_sha256": P3._raw_term_digest(rows),
    }


def _empty_cumulative_counters() -> dict[str, Any]:
    return {
        "p2": {"cap_scan": 0, "propagation": 0, "truncation": 0, "final": 0},
        "accuracy": {"anticommuting": 0, "product": 0, "merge": 0, "drop": 0},
        "composites": 0,
        "constituents": 0,
        "boundaries": 0,
    }


def _complex_mul_bits(
    left: tuple[int, int], right: tuple[int, int],
) -> tuple[int, int]:
    """Reproduce Base's ordered ComplexF64 multiplication with integer RNE."""

    left_real, left_imag = left
    right_real, right_imag = right
    real = P3._rne_add_bits(
        P3._rne_mul_bits(left_real, right_real),
        P3._negate_bits(P3._rne_mul_bits(left_imag, right_imag)),
    )
    imag = P3._rne_add_bits(
        P3._rne_mul_bits(left_real, right_imag),
        P3._rne_mul_bits(left_imag, right_real),
    )
    return real, imag


_UNIT_POSITIVE_ONE_BITS = 0x3FF0000000000000
_UNIT_NEGATIVE_ONE_BITS = 0xBFF0000000000000
_COMPLEX_UNIT_STATES = (
    (_UNIT_POSITIVE_ONE_BITS, 0),
    (_UNIT_POSITIVE_ONE_BITS, SIGN_MASK),
    (_UNIT_NEGATIVE_ONE_BITS, 0),
    (_UNIT_NEGATIVE_ONE_BITS, SIGN_MASK),
    (0, _UNIT_POSITIVE_ONE_BITS),
    (SIGN_MASK, _UNIT_POSITIVE_ONE_BITS),
    (0, _UNIT_NEGATIVE_ONE_BITS),
    (SIGN_MASK, _UNIT_NEGATIVE_ONE_BITS),
)
_COMPLEX_UNIT_FACTORS = (
    (_UNIT_POSITIVE_ONE_BITS, 0),
    (0, _UNIT_POSITIVE_ONE_BITS),
    (0, _UNIT_NEGATIVE_ONE_BITS),
)
_COMPLEX_UNIT_STATE_INDEX = {
    state: index for index, state in enumerate(_COMPLEX_UNIT_STATES)
}
_COMPLEX_UNIT_TRANSITIONS = tuple(
    tuple(
        _COMPLEX_UNIT_STATE_INDEX[_complex_mul_bits(state, factor)]
        for factor in _COMPLEX_UNIT_FACTORS
    )
    for state in _COMPLEX_UNIT_STATES
)


def _upstream_fock_real_bits(mask: int, occupied_mask: int) -> int:
    """Reproduce the frozen upstream Fock loop, including signed-zero history.

    ``omega_L_mult`` returns a Float64 exponent in the pinned upstream release,
    so the accumulator starts as ComplexF64.  The loop then multiplies that
    accumulator by a Complex{Int64} unit even when a Majorana pair is absent.
    Those mathematically inert multiplications change IEEE-754 zero signs.
    Tracking only the phase modulo four is therefore insufficient for the
    diagnostic contribution-stream digest, although it is sufficient for the
    authoritative exact dyadic center.
    """

    state = 0 if P3._omega_self(mask) == 0 else 4
    for fermion0 in range(128):
        first = (mask >> (2 * fermion0)) & 1
        second = (mask >> (2 * fermion0 + 1)) & 1
        if first != second:
            # Upstream executes ``res *= 0.`` and then returns real(res).
            return _COMPLEX_UNIT_STATES[state][0] & SIGN_MASK
        if first:
            occupied = (occupied_mask >> (2 * fermion0)) & 1
            factor = 2 if occupied else 1
        else:
            # Upstream still evaluates and multiplies by (±im)^0 == 1 + 0im.
            factor = 0
        state = _COMPLEX_UNIT_TRANSITIONS[state][factor]

    element = P3._fock_diagonal_mask(mask, occupied_mask)
    value = _COMPLEX_UNIT_STATES[state]
    expected_real = _UNIT_NEGATIVE_ONE_BITS if element < 0 else _UNIT_POSITIVE_ONE_BITS
    if value[0] != expected_real or value[1] & ~SIGN_MASK:
        raise VerificationError("P4 upstream Fock unit-phase reconstruction failed")
    return value[0]


def _final_state_from_rows(
    rows: Sequence[tuple[int, int]], total_ticks: int,
) -> dict[str, Any]:
    occupied_mask = P3._neel_gamma_mask()
    exact_center = Fraction(0)
    float_expectation_bits = 0
    float_stream = hashlib.sha256()
    exact_rows = P3.CanonicalArrayDigest()
    for mask, coefficient in rows:
        element = P3._fock_diagonal_mask(mask, occupied_mask)
        exact_contribution = P3.decode_binary64_bits(coefficient) * element
        exact_center += exact_contribution
        multiplier = _upstream_fock_real_bits(mask, occupied_mask)
        float_contribution = P3._rne_mul_bits(coefficient, multiplier)
        float_expectation_bits = P3._rne_add_bits(
            float_expectation_bits, float_contribution,
        )
        float_stream.update(P3._mask_hex(mask).encode("ascii"))
        float_stream.update(b"\t")
        float_stream.update(P3._bits_hex(float_contribution).encode("ascii"))
        float_stream.update(b"\n")
        exact_rows.add({
            "mask_hex": P3._mask_hex(mask),
            "coefficient_Float64_bits_hex": P3._bits_hex(coefficient),
            "fock_diagonal_element": element,
            "exact_dyadic_contribution": _format_q(exact_contribution),
        })
    center_lower = P3._floor_scaled(exact_center, GRID)
    center_upper = P3._ceil_scaled(exact_center, GRID)
    declared_lower = center_lower - total_ticks
    declared_upper = center_upper + total_ticks
    return {
        "retained_term_count": len(rows),
        "term_stream_sha256": P3._raw_term_digest(rows),
        "checkerboard_Neel_occupied_mask_hex": P3._mask_hex(occupied_mask),
        "checkerboard_Neel_independent_occupied_gamma_mask_hex": P3._mask_hex(occupied_mask),
        "checkerboard_Neel_up_count": 32,
        "checkerboard_Neel_down_count": 32,
        "checkerboard_Neel_expectation_Float64_diagnostic_bits_hex": P3._bits_hex(
            float_expectation_bits
        ),
        "checkerboard_Neel_contribution_stream_sha256": float_stream.hexdigest(),
        "checkerboard_Neel_expectation_rows_sha256": exact_rows.hexdigest(),
        "checkerboard_Neel_exact_dyadic_center": _format_q(exact_center),
        "center_lower_ticks": str(center_lower),
        "center_upper_ticks": str(center_upper),
        "declared_expectation_lower_ticks": str(declared_lower),
        "declared_expectation_upper_ticks": str(declared_upper),
        "declared_expectation_interval": {
            "lower": _format_q(Fraction(declared_lower, GRID)),
            "upper": _format_q(Fraction(declared_upper, GRID)),
        },
        "Float64_reduction_is_diagnostic_only": True,
        "exact_dyadic_center_and_declared_interval_are_authoritative": True,
    }


def _build_execution(
    *, completed_composites: int, completed_constituents: int,
    completed_boundaries: int, peak_premerge: int, peak_postmerge: int,
    total_splits: int, total_drops: int, total_zero_drops: int,
    cumulative_drop_bits: int, p2: Mapping[str, int],
    accuracy: Mapping[str, int], transitions: list[dict[str, Any]],
    boundaries: list[dict[str, Any]], stages: list[dict[str, Any]],
    p2_transition_digest: P3.CanonicalArrayDigest,
    p2_boundary_digest: P3.CanonicalArrayDigest,
    p2_stage_digest: P3.CanonicalArrayDigest,
    cap_event: Mapping[str, Any] | None,
) -> dict[str, Any]:
    p2_public = P3._public_p2_counters(p2)
    accuracy_public = P3._public_accuracy_counters(accuracy)
    return {
        "completed_composite_count": completed_composites,
        "completed_constituent_count": completed_constituents,
        "completed_truncation_boundary_count": completed_boundaries,
        "peak_premerge_contribution_count": peak_premerge,
        "peak_postmerge_unique_term_count": peak_postmerge,
        "anticommuting_split_count": total_splits,
        "threshold_dropped_term_count": total_drops,
        "exact_zero_dropped_term_count": total_zero_drops,
        "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex": P3._bits_hex(
            cumulative_drop_bits
        ),
        "P2_resource_counters": p2_public,
        "accuracy_counters": accuracy_public,
        "total_P2_plus_accuracy_charged_event_count": (
            p2_public["total_charged_term_visits"]
            + accuracy_public["accuracy_charged_event_count"]
        ),
        "P2_transition_records_sha256": p2_transition_digest.hexdigest(),
        "P2_boundary_records_sha256": p2_boundary_digest.hexdigest(),
        "P2_stage_records_sha256": p2_stage_digest.hexdigest(),
        "transition_records": transitions,
        "transition_records_sha256": canonical_sha256(transitions),
        "boundary_records": boundaries,
        "boundary_records_sha256": canonical_sha256(boundaries),
        "stage_records": stages,
        "stage_records_sha256": canonical_sha256(stages),
        "cap_event": cap_event,
    }


def _build_local_ledger(
    accuracy: Mapping[str, int], ticks: Mapping[str, int], cap_event: Any,
) -> dict[str, Any]:
    public = P3._public_accuracy_counters(accuracy)
    total = sum(ticks.values())
    public.update({
        "product_defect_ticks": str(ticks["product"]),
        "merge_defect_ticks": str(ticks["merge"]),
        "drop_defect_ticks": str(ticks["drop"]),
        "total_operator_error_ticks": str(total),
        "grid_denominator": str(GRID),
        "allocation_rational": "1/400000",
        "allocation_grid_ceiling_ticks_diagnostic_only": str((GRID + 399999) // 400000),
        "strictly_within_allocation": None if cap_event is not None else total * 400000 < GRID,
        "strict_comparison": (
            "total_operator_error_ticks_times_400000_strictly_less_than_2_pow_128"
        ),
        "outward_widening_is_absorbed_in_each_local_upper_not_added_again": True,
        "coefficient_L1_bounds_operator_norm": True,
        "no_future_L1_amplification_from_exact_unitary_conjugation": True,
    })
    return public


def _run_step_oracle(
    *, step_index: int, state: dict[int, int], trig: Mapping[str, Any],
    schedule: Mapping[str, Any], step_caps: Mapping[str, int],
    cumulative_caps: Mapping[str, int], cumulative: MutableMapping[str, Any],
    maximum_bits: int, input_state: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[int, int]]:
    transitions: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []
    p2_transition_digest = P3.CanonicalArrayDigest()
    p2_boundary_digest = P3.CanonicalArrayDigest()
    p2_stage_digest = P3.CanonicalArrayDigest()
    p2 = {"cap_scan": 0, "propagation": 0, "truncation": 0, "final": 0}
    accuracy = {"anticommuting": 0, "product": 0, "merge": 0, "drop": 0}
    ticks = {"product": 0, "merge": 0, "drop": 0}
    peak_premerge = len(state)
    peak_postmerge = len(state)
    total_splits = total_drops = total_zero_drops = 0
    cumulative_drop_bits = 0
    completed_composites = completed_constituents = completed_boundaries = 0
    cap_event: Mapping[str, Any] | None = None

    try:
        for stage_index, group in enumerate(STAGE_GROUPS):
            stage_composites = [
                row for row in schedule["composites"]
                if row["stage_index"] == stage_index
            ]
            stage_input = len(state)
            stage_peak_pre = stage_peak_post = stage_input
            splits_before, drops_before = total_splits, total_drops
            p2_before = dict(p2)
            accuracy_before = dict(accuracy)
            ticks_before = dict(ticks)
            for composite in stage_composites:
                composite_context = {
                    "step_index": step_index,
                    "stage_index": stage_index,
                    "group": group,
                    "composite_index": composite["composite_index"],
                    "operation": "begin_composite",
                }
                _check_cap(
                    step_index, "maximum_composites", completed_composites + 1,
                    step_caps, "step", composite_context,
                )
                _check_cap(
                    step_index, "maximum_composites", cumulative["composites"] + 1,
                    cumulative_caps, "cumulative", composite_context,
                )
                for public in composite["constituents"]:
                    context = {
                        "step_index": step_index,
                        "stage_index": stage_index,
                        "group": group,
                        "composite_index": composite["composite_index"],
                        "constituent_index": public["constituent_index"],
                    }
                    _check_cap(
                        step_index, "maximum_constituents", completed_constituents + 1,
                        step_caps, "step", {**context, "operation": "begin_constituent"},
                    )
                    _check_cap(
                        step_index, "maximum_constituents", cumulative["constituents"] + 1,
                        cumulative_caps, "cumulative",
                        {**context, "operation": "begin_constituent"},
                    )
                    gate = int(public["mask_hex"], 16)
                    input_count = len(state)
                    _check_cap(
                        step_index, "maximum_current_terms_before_constituent",
                        input_count, step_caps, "step",
                        {**context, "operation": "predictive_anticommutation_scan"},
                    )
                    _check_cap(
                        step_index, "maximum_current_terms_before_constituent",
                        input_count, cumulative_caps, "cumulative",
                        {**context, "operation": "predictive_anticommutation_scan"},
                    )
                    _charge_p2(
                        step_index=step_index, field="cap_scan",
                        cap_name="maximum_cap_scan_term_visits", amount=input_count,
                        local=p2, cumulative=cumulative["p2"], step_caps=step_caps,
                        cumulative_caps=cumulative_caps, accuracy_local=accuracy,
                        accuracy_cumulative=cumulative["accuracy"],
                        context={**context, "operation": "predictive_anticommutation_scan"},
                    )
                    source_masks = sorted(
                        mask for mask in state if not P3._majorana_commutes(gate, mask)
                    )
                    anti_count = len(source_masks)
                    premerge_count = input_count + anti_count
                    _check_cap(
                        step_index, "maximum_premerge_terms", premerge_count,
                        step_caps, "step", {**context, "operation": "applytoall"},
                    )
                    _check_cap(
                        step_index, "maximum_premerge_terms", premerge_count,
                        cumulative_caps, "cumulative", {**context, "operation": "applytoall"},
                    )
                    _charge_product_pair(
                        step_index=step_index, anticommuting=anti_count,
                        local=accuracy, cumulative=cumulative["accuracy"],
                        step_caps=step_caps, cumulative_caps=cumulative_caps,
                        p2_local=p2, p2_cumulative=cumulative["p2"],
                        context={**context, "operation": "product_defects"},
                    )
                    _charge_p2(
                        step_index=step_index, field="propagation",
                        cap_name="maximum_propagation_term_visits", amount=input_count,
                        local=p2, cumulative=cumulative["p2"], step_caps=step_caps,
                        cumulative_caps=cumulative_caps, accuracy_local=accuracy,
                        accuracy_cumulative=cumulative["accuracy"],
                        context={**context, "operation": "upstream_applytoall"},
                    )

                    angle = trig[public["applied_angle"]]
                    main = dict(state)
                    aux: dict[int, int] = {}
                    contribution_digest = P3.CanonicalArrayDigest()
                    transition_product_ticks = 0
                    for source in source_masks:
                        coefficient = state[source]
                        target, sign = P3._majorana_product_target_sign(gate, source)
                        cosine_output = P3._rne_mul_bits(coefficient, angle["cosine_bits"])
                        signed_sine = (
                            angle["sine_bits"] if sign > 0
                            else P3._negate_bits(angle["sine_bits"])
                        )
                        sine_output = P3._rne_mul_bits(coefficient, signed_sine)
                        cosine_ticks = P3._point_interval_defect(
                            cosine_output, coefficient, angle["cosine_interval"], 1,
                        )
                        sine_ticks = P3._point_interval_defect(
                            sine_output, coefficient, angle["sine_interval"], sign,
                        )
                        _check_bigint(
                            cosine_ticks, maximum_bits, step_index,
                            {**context, "operation": "cosine_product_defect"},
                        )
                        _check_bigint(
                            sine_ticks, maximum_bits, step_index,
                            {**context, "operation": "sine_product_defect"},
                        )
                        increment = cosine_ticks + sine_ticks
                        transition_product_ticks += increment
                        ticks["product"] += increment
                        _check_bigint(
                            transition_product_ticks, maximum_bits, step_index,
                            {**context, "operation": "transition_product_accumulate"},
                        )
                        _check_bigint(
                            ticks["product"], maximum_bits, step_index,
                            {**context, "operation": "product_defect_accumulate"},
                        )
                        contribution_digest.add({
                            "source_mask_hex": P3._mask_hex(source),
                            "target_mask_hex": P3._mask_hex(target),
                            "branch_sign": sign,
                            "input_coefficient_Float64_bits_hex": P3._bits_hex(coefficient),
                            "cosine_output_Float64_bits_hex": P3._bits_hex(cosine_output),
                            "sine_output_Float64_bits_hex": P3._bits_hex(sine_output),
                            "cosine_product_defect_ticks": str(cosine_ticks),
                            "sine_product_defect_ticks": str(sine_ticks),
                        })
                        main[source] = cosine_output
                        if target in aux:
                            raise VerificationError(
                                "independent Majorana target map is not injective"
                            )
                        aux[target] = sine_output
                    total_splits += anti_count
                    peak_premerge = max(peak_premerge, premerge_count)
                    stage_peak_pre = max(stage_peak_pre, premerge_count)

                    collision_masks = sorted(set(main).intersection(aux))
                    _charge_accuracy(
                        step_index=step_index, field="merge",
                        cap_name="maximum_merge_defect_events",
                        amount=len(collision_masks), local=accuracy,
                        cumulative=cumulative["accuracy"], step_caps=step_caps,
                        cumulative_caps=cumulative_caps, p2_local=p2,
                        p2_cumulative=cumulative["p2"],
                        context={**context, "operation": "merge_defects"},
                    )
                    merge_digest = P3.CanonicalArrayDigest()
                    transition_merge_ticks = 0
                    for mask in collision_masks:
                        left, right = main[mask], aux[mask]
                        merged = P3._rne_add_bits(left, right)
                        defect = P3._ceil_grid(abs(
                            P3.decode_binary64_bits(merged)
                            - P3.decode_binary64_bits(left)
                            - P3.decode_binary64_bits(right)
                        ))
                        transition_merge_ticks += defect
                        ticks["merge"] += defect
                        _check_bigint(
                            transition_merge_ticks, maximum_bits, step_index,
                            {**context, "operation": "transition_merge_accumulate"},
                        )
                        _check_bigint(
                            ticks["merge"], maximum_bits, step_index,
                            {**context, "operation": "merge_defect_accumulate"},
                        )
                        merge_digest.add({
                            "mask_hex": P3._mask_hex(mask),
                            "main_premerge_coefficient_Float64_bits_hex": P3._bits_hex(left),
                            "aux_premerge_coefficient_Float64_bits_hex": P3._bits_hex(right),
                            "merged_coefficient_Float64_bits_hex": P3._bits_hex(merged),
                            "merge_defect_ticks": str(defect),
                        })
                        main[mask] = merged
                    for mask, coefficient in aux.items():
                        if mask not in main:
                            main[mask] = coefficient
                    state = main
                    postmerge_count = len(state)
                    peak_postmerge = max(peak_postmerge, postmerge_count)
                    stage_peak_post = max(stage_peak_post, postmerge_count)

                    transition_drop_ticks = 0
                    transition_drop_events = 0
                    boundary_record = None
                    if public["boundary_after"]:
                        boundary_context = {**context, "operation": "threshold_callback_scan"}
                        _check_cap(
                            step_index, "maximum_truncation_boundaries",
                            completed_boundaries + 1, step_caps, "step", boundary_context,
                        )
                        _check_cap(
                            step_index, "maximum_truncation_boundaries",
                            cumulative["boundaries"] + 1,
                            cumulative_caps, "cumulative", boundary_context,
                        )
                        _charge_p2(
                            step_index=step_index, field="truncation",
                            cap_name="maximum_truncation_term_visits",
                            amount=postmerge_count, local=p2,
                            cumulative=cumulative["p2"], step_caps=step_caps,
                            cumulative_caps=cumulative_caps, accuracy_local=accuracy,
                            accuracy_cumulative=cumulative["accuracy"],
                            context=boundary_context,
                        )
                        dropped = sorted(
                            (mask, bits) for mask, bits in state.items()
                            if (bits & ~SIGN_MASK) < EPSILON_BITS
                        )
                        transition_drop_events = len(dropped)
                        _charge_accuracy(
                            step_index=step_index, field="drop",
                            cap_name="maximum_drop_defect_events",
                            amount=transition_drop_events, local=accuracy,
                            cumulative=cumulative["accuracy"], step_caps=step_caps,
                            cumulative_caps=cumulative_caps, p2_local=p2,
                            p2_cumulative=cumulative["p2"],
                            context={**context, "operation": "drop_defects"},
                        )
                        retained_count = postmerge_count - transition_drop_events
                        _check_cap(
                            step_index, "maximum_boundary_retained_terms", retained_count,
                            step_caps, "step",
                            {**context, "operation": "post_threshold_retained_state"},
                        )
                        _check_cap(
                            step_index, "maximum_boundary_retained_terms", retained_count,
                            cumulative_caps, "cumulative",
                            {**context, "operation": "post_threshold_retained_state"},
                        )
                        drop_digest = P3.CanonicalArrayDigest()
                        diagnostic_increment_bits = 0
                        zero_count = 0
                        for mask, bits in dropped:
                            defect = P3.drop_defect_upper_ticks(bits)
                            transition_drop_ticks += defect
                            ticks["drop"] += defect
                            _check_bigint(
                                transition_drop_ticks, maximum_bits, step_index,
                                {**context, "operation": "transition_drop_accumulate"},
                            )
                            _check_bigint(
                                ticks["drop"], maximum_bits, step_index,
                                {**context, "operation": "drop_defect_accumulate"},
                            )
                            drop_digest.add({
                                "mask_hex": P3._mask_hex(mask),
                                "coefficient_Float64_bits_hex": P3._bits_hex(bits),
                                "drop_defect_ticks": str(defect),
                            })
                            magnitude = bits & ~SIGN_MASK
                            zero_count += magnitude == 0
                            diagnostic_increment_bits = P3._rne_add_bits(
                                diagnostic_increment_bits, magnitude,
                            )
                        cumulative_drop_bits = P3._rne_add_bits(
                            cumulative_drop_bits, diagnostic_increment_bits,
                        )
                        for mask, _bits in dropped:
                            del state[mask]
                        total_drops += transition_drop_events
                        total_zero_drops += zero_count
                        p2_boundary = {
                            "boundary_index": public["boundary_index_after"],
                            "stage_index": stage_index,
                            "group": group,
                            "composite_index": composite["composite_index"],
                            "after_constituent_index": public["constituent_index"],
                            "boundary_kind": (
                                "after_constituent"
                                if composite["truncate_after_each_constituent"]
                                else "after_complete_composite"
                            ),
                            "postmerge_term_count": postmerge_count,
                            "retained_term_count": retained_count,
                            "threshold_dropped_term_count": transition_drop_events,
                            "exact_zero_dropped_term_count": zero_count,
                            "dropped_term_stream_sha256": P3._raw_term_digest(dropped),
                            "dropped_abs_sum_Float64_diagnostic_bits_hex": P3._bits_hex(
                                diagnostic_increment_bits
                            ),
                            "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex": P3._bits_hex(
                                cumulative_drop_bits
                            ),
                        }
                        p2_boundary_digest.add(p2_boundary)
                        boundary_record = dict(p2_boundary)
                        boundary_record.update({
                            "drop_defect_event_count": transition_drop_events,
                            "drop_defect_ticks": str(transition_drop_ticks),
                            "drop_rows_sha256": drop_digest.hexdigest(),
                            "cumulative_product_defect_ticks": str(ticks["product"]),
                            "cumulative_merge_defect_ticks": str(ticks["merge"]),
                            "cumulative_drop_defect_ticks": str(ticks["drop"]),
                            "cumulative_total_operator_error_ticks": str(sum(ticks.values())),
                            "cumulative_accuracy_charged_event_count": _accuracy_total(accuracy),
                        })
                        boundaries.append(boundary_record)
                        completed_boundaries += 1
                        cumulative["boundaries"] += 1

                    p2_transition = {
                        "constituent_index": public["constituent_index"],
                        "composite_index": composite["composite_index"],
                        "stage_index": stage_index,
                        "group": group,
                        "mask_hex": public["mask_hex"],
                        "applied_angle": public["applied_angle"],
                        "input_term_count": input_count,
                        "anticommuting_split_count": anti_count,
                        "premerge_contribution_count": premerge_count,
                        "postmerge_unique_term_count": postmerge_count,
                        "boundary_index_after": public["boundary_index_after"],
                        "retained_term_count_after_boundary": (
                            None if boundary_record is None
                            else boundary_record["retained_term_count"]
                        ),
                    }
                    p2_transition_digest.add(p2_transition)
                    transition = dict(p2_transition)
                    transition.update({
                        "product_defect_event_count": 2 * anti_count,
                        "product_defect_ticks": str(transition_product_ticks),
                        "product_contribution_rows_sha256": contribution_digest.hexdigest(),
                        "merge_defect_event_count": len(collision_masks),
                        "merge_defect_ticks": str(transition_merge_ticks),
                        "merge_collision_rows_sha256": merge_digest.hexdigest(),
                        "drop_defect_event_count": transition_drop_events,
                        "drop_defect_ticks": str(transition_drop_ticks),
                        "cumulative_product_defect_ticks": str(ticks["product"]),
                        "cumulative_merge_defect_ticks": str(ticks["merge"]),
                        "cumulative_drop_defect_ticks": str(ticks["drop"]),
                        "cumulative_total_operator_error_ticks": str(sum(ticks.values())),
                        "accuracy_charged_event_count_increment": (
                            2 * anti_count + len(collision_masks) + transition_drop_events
                        ),
                        "cumulative_accuracy_charged_event_count": _accuracy_total(accuracy),
                    })
                    transitions.append(transition)
                    completed_constituents += 1
                    cumulative["constituents"] += 1
                completed_composites += 1
                cumulative["composites"] += 1

            p2_stage = {
                "stage_index": stage_index,
                "group": group,
                "input_term_count": stage_input,
                "final_retained_term_count": len(state),
                "peak_premerge_contribution_count": stage_peak_pre,
                "peak_postmerge_unique_term_count": stage_peak_post,
                "anticommuting_split_count": total_splits - splits_before,
                "threshold_dropped_term_count": total_drops - drops_before,
                "cap_scan_term_visits_increment": p2["cap_scan"] - p2_before["cap_scan"],
                "propagation_term_visits_increment": p2["propagation"] - p2_before["propagation"],
                "truncation_term_visits_increment": p2["truncation"] - p2_before["truncation"],
            }
            p2_stage_digest.add(p2_stage)
            stage_row = dict(p2_stage)
            stage_row.update({
                "product_defect_event_count_increment": accuracy["product"] - accuracy_before["product"],
                "product_defect_ticks_increment": str(ticks["product"] - ticks_before["product"]),
                "merge_defect_event_count_increment": accuracy["merge"] - accuracy_before["merge"],
                "merge_defect_ticks_increment": str(ticks["merge"] - ticks_before["merge"]),
                "drop_defect_event_count_increment": accuracy["drop"] - accuracy_before["drop"],
                "drop_defect_ticks_increment": str(ticks["drop"] - ticks_before["drop"]),
                "total_operator_error_ticks_increment": str(sum(
                    ticks[key] - ticks_before[key] for key in ticks
                )),
                "cumulative_total_operator_error_ticks": str(sum(ticks.values())),
                "accuracy_charged_event_count_increment": sum(
                    accuracy[key] - accuracy_before[key]
                    for key in ("product", "merge", "drop")
                ),
                "cumulative_accuracy_charged_event_count": _accuracy_total(accuracy),
            })
            stages.append(stage_row)
    except _CapExceeded as error:
        cap_event = _p3_compatible_cap_event(error)

    final_state = None
    if cap_event is None:
        final_rows = sorted(state.items())
        try:
            _charge_p2(
                step_index=step_index, field="final",
                cap_name="maximum_final_evaluation_term_visits",
                amount=len(final_rows), local=p2, cumulative=cumulative["p2"],
                step_caps=step_caps, cumulative_caps=cumulative_caps,
                accuracy_local=accuracy, accuracy_cumulative=cumulative["accuracy"],
                context={
                    "step_index": step_index,
                    "operation": "sorted_final_digest_and_exact_Neel_center",
                },
            )
            final_state = _final_state_from_rows(final_rows, sum(ticks.values()))
            if step_index == 2:
                final_state["exact_dyadic_center_and_declared_interval_are_authoritative"] = False
                final_state["exact_dyadic_center_is_authoritative_execution_fact"] = True
                final_state["local_only_interval_is_not_two_step_authority"] = True
        except _CapExceeded as error:
            cap_event = _p3_compatible_cap_event(error)

    execution = _build_execution(
        completed_composites=completed_composites,
        completed_constituents=completed_constituents,
        completed_boundaries=completed_boundaries,
        peak_premerge=peak_premerge, peak_postmerge=peak_postmerge,
        total_splits=total_splits, total_drops=total_drops,
        total_zero_drops=total_zero_drops, cumulative_drop_bits=cumulative_drop_bits,
        p2=p2, accuracy=accuracy, transitions=transitions, boundaries=boundaries,
        stages=stages, p2_transition_digest=p2_transition_digest,
        p2_boundary_digest=p2_boundary_digest, p2_stage_digest=p2_stage_digest,
        cap_event=cap_event,
    )
    return ({
        "step_index": step_index,
        "input_state": dict(input_state),
        "execution": execution,
        "accuracy_ledger": _build_local_ledger(accuracy, ticks, cap_event),
        "final_state": final_state,
    }, state)


def replay_two_step_oracle(
    trig_table: Mapping[str, Any], fixture: Mapping[str, Any], base: Path = BASE,
) -> dict[str, Any]:
    """Independently execute the two adjacent steps using integer binary64 RNE."""

    trig = P3._validate_trig_table(trig_table)
    schedule = P3.expected_schedule()
    step1_caps, step2_caps, cumulative_caps, maximum_trig = _resource_cap_sections(
        fixture, base,
    )
    if len(trig) != maximum_trig:
        raise VerificationError("P4 raw trigonometric table exceeds its frozen cap")
    maximum_bits = fixture["outward_arithmetic"]["maximum_BigInt_bit_length"]
    state = P3._initial_state()
    initial_descriptor = _state_descriptor(state)
    p3_fixture_path = base / P3_FIXTURE_NAME
    p3_fixture = load_json(p3_fixture_path)
    step1_input = {
        "P3_fixture_id": p3_fixture["fixture_id"],
        "P3_fixture_sha256": file_sha256(p3_fixture_path),
        "P3_fixture_canonical_sha256": canonical_sha256(p3_fixture),
        **initial_descriptor,
    }
    cumulative = _empty_cumulative_counters()
    step1, state = _run_step_oracle(
        step_index=1, state=state, trig=trig, schedule=schedule,
        step_caps=step1_caps, cumulative_caps=cumulative_caps,
        cumulative=cumulative, maximum_bits=maximum_bits,
        input_state=step1_input,
    )
    steps = [step1]
    if step1["execution"]["cap_event"] is not None:
        return {"steps": steps, "step_boundary_link": None}

    if step1["final_state"] is None:
        raise VerificationError("completed P4 step1 lacks a final state")
    step2_input = _state_descriptor(state)
    if (
        step2_input["term_count"] != step1["final_state"]["retained_term_count"]
        or step2_input["term_stream_sha256"]
        != step1["final_state"]["term_stream_sha256"]
    ):
        raise VerificationError("oracle step1 output does not link to step2 input")
    # The actual runner uses a fresh in-process deepcopy of the retained main
    # sum.  The independent oracle mirrors that boundary without serialization.
    state = dict(state)
    step2, state = _run_step_oracle(
        step_index=2, state=state, trig=trig, schedule=schedule,
        step_caps=step2_caps, cumulative_caps=cumulative_caps,
        cumulative=cumulative, maximum_bits=maximum_bits,
        input_state=step2_input,
    )
    steps.append(step2)
    link = {
        "same_process": True,
        "no_serialization": True,
        "step1_output_term_count": step1["final_state"]["retained_term_count"],
        "step1_output_term_stream_sha256": step1["final_state"]["term_stream_sha256"],
        "step2_input_term_count": step2_input["term_count"],
        "step2_input_term_stream_sha256": step2_input["term_stream_sha256"],
    }
    return {"steps": steps, "step_boundary_link": link}


def _assert_fieldwise_equal(actual: Any, expected: Any, context: str) -> None:
    """Report the first canonical field mismatch, rather than comparing a digest only."""

    if type(actual) is not type(expected):
        raise VerificationError(f"{context}: type mismatch")
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            raise VerificationError(
                f"{context}: key mismatch (missing={missing}, extra={extra})"
            )
        for key in sorted(expected):
            _assert_fieldwise_equal(actual[key], expected[key], f"{context}.{key}")
        return
    if isinstance(expected, list):
        if len(actual) != len(expected):
            raise VerificationError(f"{context}: array length mismatch")
        for index, (actual_row, expected_row) in enumerate(zip(actual, expected)):
            _assert_fieldwise_equal(actual_row, expected_row, f"{context}[{index}]")
        return
    if actual != expected:
        raise VerificationError(f"{context}: value mismatch")


def validate_raw_witness(
    witness: Any, fixture: Mapping[str, Any], runtime_lock: Mapping[str, Any],
    base: Path = BASE,
) -> Mapping[str, Any]:
    """Validate runner-only evidence without opening any P3 result artifact."""

    require_exact_keys(
        witness,
        (
            "schema_version", "witness_type", "fixture_id", "fixture_sha256",
            "fixture_canonical_sha256", "inherited_P2_fixture_sha256",
            "inherited_P2_fixture_canonical_sha256", "runtime", "upstream",
            "initial_observable", "schedule", "trig_table", "steps",
            "step_boundary_link", "scope",
        ),
        "P4 raw witness",
    )
    if (
        witness["schema_version"] != 1
        or witness["witness_type"] != "majorana_p4_L8_two_fused_steps_execution_raw_v2"
        or witness["fixture_id"] != fixture["fixture_id"]
    ):
        raise SchemaError("unexpected P4 raw witness identity")
    fixture_path = base / FIXTURE_NAME
    if (
        witness["fixture_sha256"] != file_sha256(fixture_path)
        or witness["fixture_canonical_sha256"] != canonical_sha256(fixture)
    ):
        raise VerificationError("P4 raw fixture custody mismatch")
    p2_path = base / P2_FIXTURE_NAME
    p2_fixture = load_json(p2_path)
    P2.validate_fixture(p2_fixture)
    if (
        witness["inherited_P2_fixture_sha256"] != file_sha256(p2_path)
        or witness["inherited_P2_fixture_canonical_sha256"]
        != canonical_sha256(p2_fixture)
    ):
        raise VerificationError("P4 raw inherited P2 fixture custody mismatch")
    if witness["runtime"] != P2._expected_runtime(runtime_lock):
        raise VerificationError("P4 raw runtime custody mismatch")
    if witness["upstream"] != P2._expected_upstream(runtime_lock):
        raise VerificationError("P4 raw upstream custody mismatch")
    if witness["initial_observable"] != P2.expected_initial_observable():
        raise VerificationError("P4 raw initial observable mismatch")
    if witness["schedule"] != P3.expected_schedule():
        raise VerificationError("P4 raw schedule mismatch")
    if witness["scope"] != RAW_SCOPE:
        raise VerificationError("P4 raw scope must contain execution facts only")

    oracle = replay_two_step_oracle(witness["trig_table"], fixture, base)
    _assert_fieldwise_equal(witness["steps"], oracle["steps"], "P4 raw steps")
    _assert_fieldwise_equal(
        witness["step_boundary_link"], oracle["step_boundary_link"],
        "P4 raw step boundary link",
    )
    steps = witness["steps"]
    if not isinstance(steps, list) or len(steps) not in (1, 2):
        raise SchemaError("P4 raw steps must contain one capped step or two attempted steps")
    if len(steps) == 1:
        if (
            steps[0]["execution"]["cap_event"] is None
            or witness["step_boundary_link"] is not None
        ):
            raise VerificationError("P4 one-row raw witness is not a step1 cap prefix")
    else:
        link = witness["step_boundary_link"]
        require_exact_keys(
            link,
            (
                "same_process", "no_serialization", "step1_output_term_count",
                "step1_output_term_stream_sha256", "step2_input_term_count",
                "step2_input_term_stream_sha256",
            ),
            "P4 step boundary link",
        )
        if (
            link["same_process"] is not True or link["no_serialization"] is not True
            or link["step1_output_term_count"] != link["step2_input_term_count"]
            or link["step1_output_term_stream_sha256"]
            != link["step2_input_term_stream_sha256"]
        ):
            raise VerificationError("P4 raw step boundary is not same-process linked")
    return witness


def _verify_parent_p3(
    fixture: Mapping[str, Any], base: Path = BASE,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    """Verify the exact direct-parent P3 result and every fixture pin."""

    summary = P3.verify_final(base)
    if summary["status"] != PARENT_STATUS:
        raise VerificationError("P4 direct parent lacks the required P3 authority")
    pins = fixture["required_parent_P3"]
    parent_paths = {
        "result_contract_sha256": P3_RESULT_CONTRACT_NAME,
        "certificate_sha256": P3_CERTIFICATE_NAME,
        "fixture_sha256": P3_FIXTURE_NAME,
        "policy_sha256": "majorana_certificate_p3_policy.json",
        "runner_sha256": "majorana_certificate_p3/majorana_p3_runner.jl",
        "checker_sha256": P3_CHECKER_NAME,
        "precommit_contract_sha256": P3_PRECOMMIT_CONTRACT_NAME,
        "exact_result_test_sha256": P3_RESULT_TEST_NAME,
    }
    repo, base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", REQUIRED_PARENT_COMMIT).stdout.decode().strip()
    if resolved != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P4 direct-parent commit does not resolve exactly")
    for field, relative in parent_paths.items():
        path = base / relative
        if pins[field] != file_sha256(path):
            raise VerificationError(f"P4 fixture P3 pin mismatch: {field}")
        committed = P2._run_git(
            repo, "show", f"{REQUIRED_PARENT_COMMIT}:{(base_relative / relative).as_posix()}"
        ).stdout
        if committed != path.read_bytes():
            raise VerificationError(f"P4 direct-parent bytes drifted: {relative}")
    result = load_json(base / P3_RESULT_CONTRACT_NAME)
    parent_witness = result["witness"]
    if (
        result["canonical_witness_sha256"] != pins["canonical_witness_sha256"]
        or canonical_sha256(parent_witness) != pins["canonical_witness_sha256"]
        or canonical_sha256(parent_witness["accuracy_ledger"])
        != pins["accuracy_ledger_sha256"]
        or result["transcript_sha256_in_order"] != [
            pins["canonical_transcript_sha256"], pins["canonical_transcript_sha256"]
        ]
        or result["status"] != pins["status"]
        or result["terminal_branch"] != pins["terminal_branch"]
    ):
        raise VerificationError("P4 published P3 semantic pins mismatch")
    return summary, result, parent_witness


def _step1_p3_projection(
    raw: Mapping[str, Any], base: Path = BASE,
) -> dict[str, Any]:
    if len(raw["steps"]) < 1:
        raise VerificationError("P4 raw witness lacks step1")
    step = raw["steps"][0]
    if step["execution"]["cap_event"] is not None or step["final_state"] is None:
        raise VerificationError("capped P4 step1 has no complete P3 projection")
    input_state = step["input_state"]
    require_exact_keys(
        input_state,
        (
            "P3_fixture_id", "P3_fixture_sha256", "P3_fixture_canonical_sha256",
            "term_count", "term_stream_sha256",
        ),
        "P4 step1 input state",
    )
    p3_fixture_path = base / P3_FIXTURE_NAME
    p3_fixture = load_json(p3_fixture_path)
    if (
        input_state["P3_fixture_id"] != p3_fixture["fixture_id"]
        or input_state["P3_fixture_sha256"] != file_sha256(p3_fixture_path)
        or input_state["P3_fixture_canonical_sha256"] != canonical_sha256(p3_fixture)
    ):
        raise VerificationError("P4 raw step1 P3 fixture custody mismatch")
    return {
        "schema_version": 1,
        "witness_type": "majorana_p3_L8_one_fused_step_local_defect_v1",
        "fixture_id": input_state["P3_fixture_id"],
        "fixture_sha256": input_state["P3_fixture_sha256"],
        "fixture_canonical_sha256": input_state["P3_fixture_canonical_sha256"],
        "inherited_P2_fixture_sha256": raw["inherited_P2_fixture_sha256"],
        "inherited_P2_fixture_canonical_sha256": raw[
            "inherited_P2_fixture_canonical_sha256"
        ],
        "terminal_branch": "BOUND_WITHIN_PREFIX_ALLOCATION",
        "status": PARENT_STATUS,
        "runtime": raw["runtime"],
        "upstream": raw["upstream"],
        "initial_observable": raw["initial_observable"],
        "schedule": raw["schedule"],
        "trig_table": raw["trig_table"],
        "execution": step["execution"],
        "accuracy_ledger": step["accuracy_ledger"],
        "final_state": step["final_state"],
        "scope": P3.EXPECTED_SCOPE,
    }


def _authoritative_final_state(
    raw_step2_final: Mapping[str, Any], cumulative_ticks: int,
) -> dict[str, Any]:
    final = dict(raw_step2_final)
    final.pop("exact_dyadic_center_is_authoritative_execution_fact", None)
    final.pop("local_only_interval_is_not_two_step_authority", None)
    center_lower = int(final["center_lower_ticks"])
    center_upper = int(final["center_upper_ticks"])
    lower = center_lower - cumulative_ticks
    upper = center_upper + cumulative_ticks
    final["declared_expectation_lower_ticks"] = str(lower)
    final["declared_expectation_upper_ticks"] = str(upper)
    final["declared_expectation_interval"] = {
        "lower": _format_q(Fraction(lower, GRID)),
        "upper": _format_q(Fraction(upper, GRID)),
    }
    final["exact_dyadic_center_and_declared_interval_are_authoritative"] = True
    final["two_step_cumulative_operator_error_ticks"] = str(cumulative_ticks)
    final["declared_interval_uses_parent_E1_once_plus_step2_local_increment"] = True
    return final


def _status_for_terminal_branch(policy: Mapping[str, Any], branch: str) -> str:
    statuses = {
        row["branch"]: row["maximum_status"]
        for row in policy["legal_terminal_branches"]
    }
    if branch not in statuses:
        raise VerificationError("illegal P4 terminal branch")
    return statuses[branch]


def _compose_authoritative_witness(
    raw: Mapping[str, Any], fixture: Mapping[str, Any],
    policy: Mapping[str, Any], base: Path = BASE,
) -> dict[str, Any]:
    """Read P3 only now, then compose its error exactly once with step two."""

    parent_summary, parent_result, parent_witness = _verify_parent_p3(fixture, base)
    step1 = raw["steps"][0]
    step1_capped = step1["execution"]["cap_event"] is not None
    conformance = False
    projection_sha: str | None = None
    if not step1_capped:
        projection = _step1_p3_projection(raw, base)
        _assert_fieldwise_equal(
            projection, parent_witness, "P4 fresh step1 P3 conformance",
        )
        projection_sha = canonical_sha256(projection)
        conformance = True

    step2_capped = (
        len(raw["steps"]) == 2
        and raw["steps"][1]["execution"]["cap_event"] is not None
    )
    completed = (
        conformance and len(raw["steps"]) == 2 and not step2_capped
        and raw["steps"][1]["final_state"] is not None
    )
    parent_ticks: int | None = None
    step2_ticks: int | None = None
    cumulative_ticks: int | None = None
    telescoping: dict[str, Any] | None = None
    final_state: dict[str, Any] | None = None
    if step1_capped:
        branch = "STEP1_P3_DETERMINISTIC_POLICY_CAP_EXCEEDED"
    elif step2_capped:
        branch = "STEP2_DETERMINISTIC_POLICY_CAP_EXCEEDED"
    elif not completed:
        raise VerificationError("P4 raw witness is neither capped nor a complete two-step replay")
    else:
        parent_ledger = parent_witness["accuracy_ledger"]
        step2_ledger = raw["steps"][1]["accuracy_ledger"]
        if parent_ledger["grid_denominator"] != str(GRID) or step2_ledger[
            "grid_denominator"
        ] != str(GRID):
            raise VerificationError("P4 parent/step2 defect grids differ")
        parent_ticks = int(parent_ledger["total_operator_error_ticks"])
        replayed_step1_ticks = int(step1["accuracy_ledger"]["total_operator_error_ticks"])
        if replayed_step1_ticks != parent_ticks:
            raise VerificationError("P4 fresh step1 ticks differ from the P3 parent")
        step2_ticks = int(step2_ledger["total_operator_error_ticks"])
        cumulative_ticks = parent_ticks + step2_ticks
        step2_within = step2_ticks * 400000 < GRID
        cumulative_within = cumulative_ticks * 200000 < GRID
        if step2_within and not cumulative_within:
            raise VerificationError("P4 allocation truth combination is impossible after P3 conformance")
        if not cumulative_within:
            branch = "TWO_STEP_CUMULATIVE_BOUND_EXCEEDS_ALLOCATION"
        elif not step2_within:
            branch = (
                "STEP2_BOUND_EXCEEDS_INCREMENT_ALLOCATION_BUT_TWO_STEP_BOUND_WITHIN_"
                "CUMULATIVE_ALLOCATION"
            )
        else:
            branch = "STEP2_AND_TWO_STEP_BOUND_WITHIN_ALLOCATIONS"
        telescoping = {
            "grid_denominator": str(GRID),
            "parent_P3_operator_error_ticks": str(parent_ticks),
            "fresh_step1_recomputed_operator_error_ticks": str(replayed_step1_ticks),
            "fresh_step1_recomputed_ticks_equal_parent": True,
            "fresh_step1_recomputation_is_conformance_not_a_second_charge": True,
            "parent_step1_error_charge_multiplicity": 1,
            "exact_unitary_parent_error_propagation_factor": 1,
            "step2_product_defect_ticks": step2_ledger["product_defect_ticks"],
            "step2_merge_defect_ticks": step2_ledger["merge_defect_ticks"],
            "step2_drop_defect_ticks": step2_ledger["drop_defect_ticks"],
            "step2_local_increment_ticks": str(step2_ticks),
            "cumulative_two_step_operator_error_ticks": str(cumulative_ticks),
            "composition_identity": "parent_E1_once_plus_step2_local_increment",
            "parent_ticks_not_requantized_rounded_or_widened_again": True,
            "outward_widening_not_double_counted": True,
            "step2_local_allocation": "1/400000",
            "step2_strictly_within_allocation": step2_within,
            "step2_strict_integer_comparison": (
                "step2_local_increment_ticks_times_400000_less_than_grid_denominator"
            ),
            "two_step_cumulative_allocation": "1/200000",
            "two_step_strictly_within_allocation": cumulative_within,
            "two_step_strict_integer_comparison": (
                "cumulative_two_step_ticks_times_200000_less_than_grid_denominator"
            ),
        }
        final_state = _authoritative_final_state(
            raw["steps"][1]["final_state"], cumulative_ticks,
        )

    status = _status_for_terminal_branch(policy, branch)
    parent = {
        "direct_parent_commit": REQUIRED_PARENT_COMMIT,
        "status": parent_summary["status"],
        "terminal_branch": parent_result["terminal_branch"],
        "result_contract_sha256": file_sha256(base / P3_RESULT_CONTRACT_NAME),
        "certificate_sha256": file_sha256(base / P3_CERTIFICATE_NAME),
        "canonical_witness_sha256": parent_result["canonical_witness_sha256"],
        "accuracy_ledger_sha256": canonical_sha256(parent_witness["accuracy_ledger"]),
        "canonical_transcript_sha256": parent_result["transcript_sha256_in_order"][0],
        "fresh_step1_projection_sha256": projection_sha,
        "fresh_step1_fieldwise_conformance": conformance,
        "operator_error_inheritance_applied": completed,
        "operator_error_charge_multiplicity": 1 if completed else 0,
    }
    return {
        "schema_version": 1,
        "witness_type": "majorana_p4_L8_two_step_composed_authoritative_witness_v2",
        "fixture_id": fixture["fixture_id"],
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "fixture_canonical_sha256": canonical_sha256(fixture),
        "raw_witness_sha256": canonical_sha256(raw),
        "raw_witness": raw,
        "parent_P3": parent,
        "telescoping_ledger": telescoping,
        "authoritative_two_step_final_state": final_state,
        "terminal_branch": branch,
        "status": status,
        "scope": {
            "maximum_positive_status": MAXIMUM_STATUS,
            **policy["scope_boundary"],
        },
    }


def validate_composed_witness(
    witness: Any, fixture: Mapping[str, Any], policy: Mapping[str, Any],
    runtime_lock: Mapping[str, Any], base: Path = BASE,
) -> Mapping[str, Any]:
    require_exact_keys(
        witness,
        (
            "schema_version", "witness_type", "fixture_id", "fixture_sha256",
            "fixture_canonical_sha256", "raw_witness_sha256", "raw_witness",
            "parent_P3", "telescoping_ledger", "authoritative_two_step_final_state",
            "terminal_branch", "status", "scope",
        ),
        "P4 composed witness",
    )
    raw = validate_raw_witness(witness["raw_witness"], fixture, runtime_lock, base)
    expected = _compose_authoritative_witness(raw, fixture, policy, base)
    _assert_fieldwise_equal(witness, expected, "P4 composed witness")
    return witness


def verify_precommit(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime)
    contract = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
    )
    parent_summary, _parent_result, _parent_witness = _verify_parent_p3(fixture, base)
    disclosure = fixture.get("design_probe_disclosure", {})
    if disclosure.get("status") == "DESIGN_PROBE_IN_PROGRESS":
        raise VerificationError("P4 design probe is still in progress")
    if disclosure.get("authoritative_P4_result_generated") is not False:
        raise VerificationError("P4 precommit fixture claims an authoritative result already exists")
    for artifact in contract["result_artifacts_required_absent"]:
        if (base / artifact).exists():
            raise VerificationError(f"P4 result artifact exists at precommit: {artifact}")
    return {
        "scope_ceiling": MAXIMUM_STATUS,
        "required_parent_commit": REQUIRED_PARENT_COMMIT,
        "required_parent_status": parent_summary["status"],
        "parent_result_contract_sha256": file_sha256(base / P3_RESULT_CONTRACT_NAME),
        "fixture_id": fixture["fixture_id"],
        "policy_id": policy["policy_id"],
    }


def _outer_commit_closure(
    repo: Path, base_relative: Path, commit: str, contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    pins = {row["relative_path"]: row for row in contract["source_files"]}
    rows: list[dict[str, Any]] = []
    for relative in (*PRECOMMIT_SOURCE_PATHS, PRECOMMIT_CONTRACT_NAME):
        mode, blob, body = P2._git_blob(
            repo, commit, (base_relative / relative).as_posix(),
        )
        if relative in pins:
            pin = pins[relative]
            if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
                raise VerificationError(f"P4 committed outer input differs from pin: {relative}")
        elif body != (BASE / PRECOMMIT_CONTRACT_NAME).read_bytes():
            raise VerificationError("P4 committed precommit contract differs from active bytes")
        rows.append({
            "relative_path": relative,
            "git_mode": mode,
            "git_blob": blob,
            "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
    for relative in contract["result_artifacts_required_absent"]:
        if P2._git_path_exists(repo, commit, (base_relative / relative).as_posix()):
            raise VerificationError(f"P4 result artifact exists in precommit: {relative}")
    return rows


def _stage_runner_tree(
    repo: Path, base_relative: Path, commit: str,
    contract: Mapping[str, Any], destination: Path,
) -> list[dict[str, Any]]:
    pins = {row["relative_path"]: row for row in contract["source_files"]}
    if tuple(contract["runner_staged_files"]) != RUNNER_STAGED_PATHS:
        raise VerificationError("P4 runner staging allowlist drift")
    rows: list[dict[str, Any]] = []
    for relative in RUNNER_STAGED_PATHS:
        mode, blob, body = P2._git_blob(
            repo, commit, (base_relative / relative).as_posix(),
        )
        pin = pins[relative]
        if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
            raise VerificationError(f"P4 staged Git blob differs from pin: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        rows.append({
            "relative_path": relative,
            "git_mode": mode,
            "git_blob": blob,
            "size_bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
    if any((destination / relative).exists() for relative in RUNNER_FORBIDDEN_PATHS):
        raise VerificationError("P4 runner staging exposes a P2/P3/P4 result artifact")
    return rows


def _run_one_isolated_replay(
    staging: Path, julia_executable: Path, depot: Path, run_root: Path,
    fixture: Mapping[str, Any], abi_mounts: Sequence[tuple[Path, str]],
) -> bytes:
    for executable in ("bwrap", "systemd-run", "systemctl"):
        if shutil.which(executable) is None:
            raise IndeterminateReplay(f"{executable} is required for P4 formal replay")
    cgroup = subprocess.run(
        ["stat", "-fc", "%T", "/sys/fs/cgroup"], capture_output=True, check=False,
    )
    if cgroup.stdout.strip() != b"cgroup2fs":
        raise IndeterminateReplay("P4 formal replay requires cgroup v2")
    scratch = run_root / "scratch"
    for relative in ("depot", "home", "tmp"):
        (scratch / relative).mkdir(parents=True, exist_ok=False)
    verified_julia = julia_executable.resolve()
    runtime_root = verified_julia.parent.parent
    if verified_julia != (runtime_root / "bin" / "julia").resolve():
        raise IndeterminateReplay("P4 Julia executable differs from runtime_root/bin/julia")
    bwrap = [
        "bwrap", "--die-with-parent", "--unshare-net", "--unshare-pid",
        "--ro-bind", str(staging), "/repo",
        "--ro-bind", str(runtime_root), "/runtime",
        "--ro-bind", str(depot), "/depot-ro",
        "--bind", str(scratch), "/scratch",
        "--proc", "/proc", "--dev", "/dev",
        "--dir", "/lib64", "--dir", "/usr", "--dir", "/usr/lib",
        "--dir", "/usr/lib/x86_64-linux-gnu", "--dir", "/usr/lib/locale",
        "--dir", "/usr/lib/locale/C.utf8",
        "--dir", "/usr/lib/locale/C.utf8/LC_MESSAGES",
    ]
    for source, destination in abi_mounts:
        bwrap.extend(("--ro-bind", str(source), destination))
    bwrap.extend((
        "--clearenv", "--setenv", "HOME", "/scratch/home",
        "--setenv", "TMPDIR", "/scratch/tmp", "--setenv", "LANG", "C.UTF-8",
        "--setenv", "LC_ALL", "C.UTF-8", "--setenv", "JULIA_DEPOT_PATH",
        "/scratch/depot:/depot-ro", "--setenv", "JULIA_LOAD_PATH", "@",
        "--setenv", "JULIA_NUM_THREADS", "1", "--setenv", "OPENBLAS_NUM_THREADS", "1",
        "--setenv", "JULIA_PKG_OFFLINE", "true", "--setenv", "JULIA_PKG_SERVER", "",
        "--chdir", "/repo", "/runtime/bin/julia", "--startup-file=no",
        "--history-file=no", "--compiled-modules=no",
        "--project=/repo/majorana_certificate_p0",
        "/repo/majorana_certificate_p4/majorana_p4_runner.jl",
        "/repo/majorana_certificate_p4_fixture.json",
        "/repo/majorana_certificate_p3_fixture.json",
        "/repo/majorana_certificate_p2_fixture.json",
    ))
    host = fixture["host_supervisor_caps"]
    unit = f"majorana-p4-{uuid.uuid4().hex}"
    command = [
        "systemd-run", "--user", "--scope", "--quiet", f"--unit={unit}",
        "-p", f"MemoryMax={host['MemoryMax_bytes']}",
        "-p", f"RuntimeMaxSec={host['RuntimeMaxSec']}", "--", *bwrap,
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_exceeded, stderr_exceeded = threading.Event(), threading.Event()
    readers = (
        threading.Thread(
            target=P2._read_limited_stream,
            args=(process.stdout, host["maximum_stdout_bytes"], stdout_chunks, stdout_exceeded),
            daemon=True,
        ),
        threading.Thread(
            target=P2._read_limited_stream,
            args=(process.stderr, host["maximum_stderr_bytes"], stderr_chunks, stderr_exceeded),
            daemon=True,
        ),
    )
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + host["subprocess_safety_timeout_seconds"]
    reason = None
    while process.poll() is None:
        if stdout_exceeded.is_set() or stderr_exceeded.is_set():
            reason = "stdout/stderr byte cap"
            break
        if time.monotonic() >= deadline:
            reason = "outer safety timeout"
            break
        time.sleep(0.01)
    if reason:
        P2._kill_systemd_scope(unit, process)
    try:
        returncode = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        P2._kill_systemd_scope(unit, process)
        try:
            returncode = process.wait(timeout=10)
        except subprocess.TimeoutExpired as error:
            raise IndeterminateReplay("P4 scope termination failure") from error
    for reader in readers:
        reader.join(timeout=10)
    stdout, stderr = b"".join(stdout_chunks), b"".join(stderr_chunks)
    if reason:
        raise IndeterminateReplay(f"P4 host resource abort: {reason}")
    if stdout_exceeded.is_set() or len(stdout) > host["maximum_stdout_bytes"]:
        raise IndeterminateReplay("P4 isolated replay exceeded stdout cap")
    if stderr_exceeded.is_set() or len(stderr) > host["maximum_stderr_bytes"]:
        raise IndeterminateReplay("P4 isolated replay exceeded stderr cap")
    if returncode != 0 or stderr:
        diagnostic = stderr.decode("utf-8", errors="replace")[-4000:]
        raise IndeterminateReplay(f"P4 isolated replay failed ({returncode}): {diagnostic}")
    return stdout


def fresh_replay(
    precommit_commit: str, julia_executable: Path, depot: Path, base: Path = BASE,
) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock)
    # This preflight checks P4 contract shape and pins but deliberately does not
    # open the P3 result-bearing source rows.  P3 is opened only after both raw
    # runner processes have exited and their stdout caps/canonical form pass.
    contract = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base, verify_source_files=False,
    )
    repo, base_relative = P2._verify_generation_git_state(
        precommit_commit, contract, base,
    )
    P0._verify_julia_runtime(Path(julia_executable), runtime_lock)
    depot = Path(depot).resolve()
    depot_before = P0._verify_depot_custody(depot, runtime_lock)
    _live_mounts, abi_before = P3._host_abi_mounts_and_custody()
    expected_environment_sha = fixture["required_parent_P3"][
        "host_abi_and_locale_custody_sha256"
    ]
    if canonical_sha256(abi_before) != expected_environment_sha:
        raise IndeterminateReplay("P4 host ABI/locale differs from the frozen P3 custody")

    with tempfile.TemporaryDirectory(prefix="majorana-p4-formal-") as temporary:
        root = Path(temporary)
        environment_snapshot = root / "environment-snapshot"
        environment_snapshot.mkdir()
        abi_mounts, abi_snapshot = P3._host_abi_mounts_and_custody(environment_snapshot)
        if abi_snapshot != abi_before:
            raise IndeterminateReplay("P4 host environment changed while taking snapshot")
        environment_snapshot_digest = P0._tree_digest(environment_snapshot)
        staging = root / "runner-staging"
        staging.mkdir()
        runner_manifest = _stage_runner_tree(
            repo, base_relative, precommit_commit, contract, staging,
        )
        staging_before = P0._tree_digest(staging)
        outputs: list[bytes] = []
        raws: list[Mapping[str, Any]] = []
        for index in range(2):
            run_root = root / f"run-{index + 1}"
            run_root.mkdir()
            output = _run_one_isolated_replay(
                staging, Path(julia_executable), depot, run_root, fixture, abi_mounts,
            )
            raw = P3.strict_json_loads(
                output, source=f"P4 Julia raw replay {index + 1} stdout",
            )
            if output != canonical_bytes(raw) + b"\n":
                raise VerificationError("P4 Julia stdout is not canonical JSON plus newline")
            outputs.append(output)
            raws.append(raw)
        if outputs[0] != outputs[1]:
            raise VerificationError("two fresh P4 Julia stdout byte streams differ")
        # Both raw outputs and their byte equality are established before this
        # independent oracle, and especially before the later P3 result read.
        raw = validate_raw_witness(raws[0], fixture, runtime_lock, base)
        if raws[1] != raw:
            raise VerificationError("second P4 raw witness differs despite transcript equality")
        composed = _compose_authoritative_witness(raw, fixture, policy, base)
        # Only now may the complete outer closure (which contains P3 result
        # artifacts) be read and bound into the replay package.
        validate_precommit_contract(
            load_json(base / PRECOMMIT_CONTRACT_NAME), base, verify_source_files=True,
        )
        outer_manifest = _outer_commit_closure(
            repo, base_relative, precommit_commit, contract,
        )
        if P0._tree_digest(staging) != staging_before:
            raise VerificationError("P4 runner staging was modified")
        if P0._tree_digest(environment_snapshot) != environment_snapshot_digest:
            raise IndeterminateReplay("P4 captured environment changed during replay")

    if P0._verify_depot_custody(depot, runtime_lock) != depot_before:
        raise VerificationError("P4 replay modified pinned depot custody")
    _mounts_after, abi_after = P3._host_abi_mounts_and_custody()
    if abi_after != abi_before:
        raise IndeterminateReplay("P4 host environment changed during replay")
    if P2._run_git(repo, "rev-parse", "HEAD").stdout.decode().strip() != precommit_commit:
        raise VerificationError("HEAD changed during P4 replay")
    if P2._run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("worktree changed during P4 replay")

    raw_transcript = hashlib.sha256(outputs[0]).hexdigest()
    return {
        "schema_version": 1,
        "package_type": "majorana_p4_formal_fresh_two_step_replay_package_v2",
        "precommit_commit_sha": precommit_commit,
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "outer_custody_manifest": outer_manifest,
        "outer_custody_manifest_sha256": canonical_sha256(outer_manifest),
        "runner_staging_manifest": runner_manifest,
        "runner_staging_manifest_sha256": canonical_sha256(runner_manifest),
        "runner_staging_tree_sha256": staging_before,
        "depot_custody": depot_before,
        "host_abi_and_locale_custody": abi_after,
        "host_abi_and_locale_custody_sha256": canonical_sha256(abi_after),
        "network_isolation": "bubblewrap_unshared_network_namespace",
        "PID_isolation": "bubblewrap_unshared_PID_namespace",
        "mount_isolation": (
            "eight_file_runner_stage_plus_runtime_depot_scratch_18_file_host_"
            "environment_and_private_proc_dev_only"
        ),
        "host_resource_enforcement": {
            "cgroup_version": 2,
            "supervisor": "systemd_user_scope",
            "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
            "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
            "observed_runtime_or_memory_peak_in_canonical_package": False,
        },
        "fresh_process_count": 2,
        "each_process_executes_step1_then_step2_same_process": True,
        "stdout_byte_identical": True,
        "raw_transcript_sha256_in_order": [raw_transcript, raw_transcript],
        "raw_witness_sha256": canonical_sha256(raw),
        "canonical_witness_sha256": canonical_sha256(composed),
        "witness": composed,
        "terminal_branch": composed["terminal_branch"],
        "status": composed["status"],
    }


def _committed_replay_evidence(
    commit: str, contract: Mapping[str, Any], base: Path = BASE,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    if (
        not isinstance(commit, str) or len(commit) != 40
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        raise SchemaError("P4 precommit commit must be a full lowercase Git SHA-1")
    repo, base_relative = P2._repo_and_base_relative(base)
    resolved = P2._run_git(repo, "rev-parse", commit).stdout.decode().strip()
    object_type = P2._run_git(repo, "cat-file", "-t", commit).stdout.decode().strip()
    if resolved != commit or object_type != "commit":
        raise VerificationError("P4 precommit commit does not resolve exactly")
    parent = P2._run_git(repo, "show", "-s", "--format=%P", commit).stdout.decode().strip()
    if parent != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P4 replay commit lacks the frozen direct parent")
    if P2._run_git(
        repo, "merge-base", "--is-ancestor", commit, "HEAD", check=False,
    ).returncode != 0:
        raise VerificationError("P4 replay commit is not an ancestor of current HEAD")
    remote_contains = P2._run_git(repo, "branch", "-r", "--contains", commit).stdout.decode()
    if "origin/" not in remote_contains:
        raise VerificationError("P4 replay commit was not pushed to an origin remote branch")
    outer = _outer_commit_closure(repo, base_relative, commit, contract)
    with tempfile.TemporaryDirectory(prefix="majorana-p4-evidence-") as temporary:
        staging = Path(temporary) / "stage"
        staging.mkdir()
        runner = _stage_runner_tree(repo, base_relative, commit, contract, staging)
        tree_digest = P0._tree_digest(staging)
    return outer, runner, tree_digest


def _validate_replay_package(
    package: Any, base: Path = BASE,
) -> Mapping[str, Any]:
    require_exact_keys(
        package,
        (
            "schema_version", "package_type", "precommit_commit_sha",
            "precommit_contract_sha256", "outer_custody_manifest",
            "outer_custody_manifest_sha256", "runner_staging_manifest",
            "runner_staging_manifest_sha256", "runner_staging_tree_sha256",
            "depot_custody", "host_abi_and_locale_custody",
            "host_abi_and_locale_custody_sha256", "network_isolation",
            "PID_isolation", "mount_isolation", "host_resource_enforcement",
            "fresh_process_count", "each_process_executes_step1_then_step2_same_process",
            "stdout_byte_identical", "raw_transcript_sha256_in_order",
            "raw_witness_sha256", "canonical_witness_sha256", "witness",
            "terminal_branch", "status",
        ),
        "P4 replay package",
    )
    if (
        package["schema_version"] != 1
        or package["package_type"]
        != "majorana_p4_formal_fresh_two_step_replay_package_v2"
    ):
        raise SchemaError("unexpected P4 replay package identity")
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock)
    precommit = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
    )
    witness = validate_composed_witness(
        package["witness"], fixture, policy, runtime_lock, base,
    )
    if (
        package["terminal_branch"] != witness["terminal_branch"]
        or package["status"] != witness["status"]
    ):
        raise VerificationError("P4 replay terminal branch/status mismatch")
    if (
        package["fresh_process_count"] != 2
        or package["each_process_executes_step1_then_step2_same_process"] is not True
        or package["stdout_byte_identical"] is not True
    ):
        raise VerificationError("P4 replay freshness/same-process evidence mismatch")
    raw = witness["raw_witness"]
    raw_bytes = canonical_bytes(raw)
    raw_sha = hashlib.sha256(raw_bytes).hexdigest()
    transcript = hashlib.sha256(raw_bytes + b"\n").hexdigest()
    if package["raw_witness_sha256"] != raw_sha:
        raise VerificationError("P4 raw witness digest mismatch")
    if package["raw_transcript_sha256_in_order"] != [transcript, transcript]:
        raise VerificationError("P4 raw transcript digest mismatch")
    if package["canonical_witness_sha256"] != canonical_sha256(witness):
        raise VerificationError("P4 composed witness digest mismatch")
    if package["precommit_contract_sha256"] != file_sha256(base / PRECOMMIT_CONTRACT_NAME):
        raise VerificationError("P4 replay precommit contract digest mismatch")
    if (
        package["network_isolation"] != "bubblewrap_unshared_network_namespace"
        or package["PID_isolation"] != "bubblewrap_unshared_PID_namespace"
        or package["mount_isolation"] != (
            "eight_file_runner_stage_plus_runtime_depot_scratch_18_file_host_"
            "environment_and_private_proc_dev_only"
        )
    ):
        raise VerificationError("P4 replay isolation declaration mismatch")
    expected_host = {
        "cgroup_version": 2,
        "supervisor": "systemd_user_scope",
        "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
        "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
        "observed_runtime_or_memory_peak_in_canonical_package": False,
    }
    if package["host_resource_enforcement"] != expected_host:
        raise VerificationError("P4 replay host resource declaration mismatch")
    environment = P3._validate_environment_manifest(
        package["host_abi_and_locale_custody"]
    )
    if (
        package["host_abi_and_locale_custody_sha256"] != canonical_sha256(environment)
        or package["host_abi_and_locale_custody_sha256"]
        != fixture["required_parent_P3"]["host_abi_and_locale_custody_sha256"]
    ):
        raise VerificationError("P4 replay environment custody mismatch")
    P2._validate_recorded_depot_custody(package["depot_custody"], runtime_lock)
    outer, runner, tree_digest = _committed_replay_evidence(
        package["precommit_commit_sha"], precommit, base,
    )
    if (
        package["outer_custody_manifest"] != outer
        or package["outer_custody_manifest_sha256"] != canonical_sha256(outer)
    ):
        raise VerificationError("P4 outer custody evidence mismatch")
    if (
        package["runner_staging_manifest"] != runner
        or package["runner_staging_manifest_sha256"] != canonical_sha256(runner)
        or package["runner_staging_tree_sha256"] != tree_digest
    ):
        raise VerificationError("P4 runner staging evidence mismatch")
    for field in (
        "precommit_contract_sha256", "outer_custody_manifest_sha256",
        "runner_staging_manifest_sha256", "runner_staging_tree_sha256",
        "host_abi_and_locale_custody_sha256", "raw_witness_sha256",
        "canonical_witness_sha256",
    ):
        require_sha256(package[field], f"P4 replay {field}")
    return package


CERTIFICATE_CLAIMS = (
    "fixed_L8_first_two_adjacent_fused_mapped_steps_fresh_same_process_execution",
    "independent_integer_binary64_RNE_replay_of_both_1152_constituent_steps",
    "complete_step2_product_merge_and_executed_drop_local_defect_ledger",
    "post_replay_fieldwise_conformance_of_fresh_step1_to_certified_P3",
    "parent_P3_operator_error_inherited_exactly_once_with_unit_propagation_factor",
    "exact_dyadic_step2_Neel_center_and_cumulative_two_step_expectation_interval",
    "strict_step2_one_over_400000_and_cumulative_one_over_200000_comparisons",
    "two_byte_identical_network_isolated_cgroup_limited_fresh_transcripts",
    "eight_file_result_blind_runner_stage_and_18_file_environment_custody",
)

CERTIFICATE_EXCLUSIONS = (
    "global_coefficientwise_interval_state",
    "equality_of_executed_and_exact_arithmetic_threshold_drop_sets",
    "raw_unfused_constituent_threshold_path",
    "double_occupancy",
    "remaining_98_mapped_steps_or_full_R100",
    "product_formula_to_exact_Hubbard_error_or_exact_time_evolution",
    "physical_reference_qualification_or_READY",
    "host_runtime_RSS_paths_timestamps_inodes_or_process_identifiers",
)


def materialize_result(
    replay_package: Mapping[str, Any], base: Path = BASE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    package = _validate_replay_package(replay_package, base)
    contract = {
        "schema_version": 1,
        "contract_type": "majorana_p4_formal_two_step_result_contract_v2",
        "precommit_commit_sha": package["precommit_commit_sha"],
        "precommit_contract_sha256": package["precommit_contract_sha256"],
        "replay_package_sha256": hashlib.sha256(
            canonical_bytes(package) + b"\n"
        ).hexdigest(),
        "outer_custody_manifest_sha256": package["outer_custody_manifest_sha256"],
        "runner_staging_manifest_sha256": package["runner_staging_manifest_sha256"],
        "runner_staging_tree_sha256": package["runner_staging_tree_sha256"],
        "depot_custody": package["depot_custody"],
        "host_abi_and_locale_custody": package["host_abi_and_locale_custody"],
        "host_abi_and_locale_custody_sha256": package[
            "host_abi_and_locale_custody_sha256"
        ],
        "network_isolation": package["network_isolation"],
        "PID_isolation": package["PID_isolation"],
        "mount_isolation": package["mount_isolation"],
        "host_resource_enforcement": package["host_resource_enforcement"],
        "fresh_process_count": package["fresh_process_count"],
        "each_process_executes_step1_then_step2_same_process": package[
            "each_process_executes_step1_then_step2_same_process"
        ],
        "stdout_byte_identical": package["stdout_byte_identical"],
        "raw_transcript_sha256_in_order": package["raw_transcript_sha256_in_order"],
        "raw_witness_sha256": package["raw_witness_sha256"],
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "witness": package["witness"],
        "terminal_branch": package["terminal_branch"],
        "status": package["status"],
        "scope": package["witness"]["scope"],
    }
    certificate = {
        "schema_version": 1,
        "certificate_type": "majorana_p4_adjacent_two_step_local_defect_bound_subcertificate_v2",
        "status": package["status"],
        "terminal_branch": package["terminal_branch"],
        "authority": (
            "fixed_L8_first_two_adjacent_fused_product_formula_steps_operator_and_"
            "checkerboard_Neel_expectation_enclosure_only"
        ),
        "result_contract_sha256": hashlib.sha256(
            canonical_bytes(contract) + b"\n"
        ).hexdigest(),
        "precommit_commit_sha": package["precommit_commit_sha"],
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "runner_sha256": file_sha256(base / RUNNER_RELATIVE_PATH),
        "checker_sha256": file_sha256(base / CHECKER_NAME),
        "parent_P3_result_contract_sha256": file_sha256(base / P3_RESULT_CONTRACT_NAME),
        "parent_P3_certificate_sha256": file_sha256(base / P3_CERTIFICATE_NAME),
        "raw_witness_sha256": package["raw_witness_sha256"],
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "telescoping_ledger_sha256": canonical_sha256(
            package["witness"]["telescoping_ledger"]
        ),
        "claims": list(CERTIFICATE_CLAIMS),
        "explicit_exclusions": list(CERTIFICATE_EXCLUSIONS),
        "ready_gate_eligible": False,
    }
    return contract, certificate


def _package_from_result(
    result: Mapping[str, Any], precommit: Mapping[str, Any], base: Path,
) -> dict[str, Any]:
    outer, runner, tree_digest = _committed_replay_evidence(
        result["precommit_commit_sha"], precommit, base,
    )
    if result["outer_custody_manifest_sha256"] != canonical_sha256(outer):
        raise VerificationError("P4 result outer custody digest mismatch")
    if result["runner_staging_manifest_sha256"] != canonical_sha256(runner):
        raise VerificationError("P4 result runner staging digest mismatch")
    if result["runner_staging_tree_sha256"] != tree_digest:
        raise VerificationError("P4 result runner staging tree digest mismatch")
    return {
        "schema_version": 1,
        "package_type": "majorana_p4_formal_fresh_two_step_replay_package_v2",
        "precommit_commit_sha": result["precommit_commit_sha"],
        "precommit_contract_sha256": result["precommit_contract_sha256"],
        "outer_custody_manifest": outer,
        "outer_custody_manifest_sha256": result["outer_custody_manifest_sha256"],
        "runner_staging_manifest": runner,
        "runner_staging_manifest_sha256": result["runner_staging_manifest_sha256"],
        "runner_staging_tree_sha256": result["runner_staging_tree_sha256"],
        "depot_custody": result["depot_custody"],
        "host_abi_and_locale_custody": result["host_abi_and_locale_custody"],
        "host_abi_and_locale_custody_sha256": result[
            "host_abi_and_locale_custody_sha256"
        ],
        "network_isolation": result["network_isolation"],
        "PID_isolation": result["PID_isolation"],
        "mount_isolation": result["mount_isolation"],
        "host_resource_enforcement": result["host_resource_enforcement"],
        "fresh_process_count": result["fresh_process_count"],
        "each_process_executes_step1_then_step2_same_process": result[
            "each_process_executes_step1_then_step2_same_process"
        ],
        "stdout_byte_identical": result["stdout_byte_identical"],
        "raw_transcript_sha256_in_order": result["raw_transcript_sha256_in_order"],
        "raw_witness_sha256": result["raw_witness_sha256"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "witness": result["witness"],
        "terminal_branch": result["terminal_branch"],
        "status": result["status"],
    }


def verify_final(base: Path = BASE) -> dict[str, Any]:
    validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = P0.validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock)
    precommit = validate_precommit_contract(
        load_json(base / PRECOMMIT_CONTRACT_NAME), base,
    )
    result_path = base / RESULT_CONTRACT_NAME
    certificate_path = base / CERTIFICATE_NAME
    result = load_json(result_path)
    certificate = load_json(certificate_path)
    require_exact_keys(
        result,
        (
            "schema_version", "contract_type", "precommit_commit_sha",
            "precommit_contract_sha256", "replay_package_sha256",
            "outer_custody_manifest_sha256", "runner_staging_manifest_sha256",
            "runner_staging_tree_sha256", "depot_custody",
            "host_abi_and_locale_custody", "host_abi_and_locale_custody_sha256",
            "network_isolation", "PID_isolation", "mount_isolation",
            "host_resource_enforcement", "fresh_process_count",
            "each_process_executes_step1_then_step2_same_process",
            "stdout_byte_identical", "raw_transcript_sha256_in_order",
            "raw_witness_sha256", "canonical_witness_sha256", "witness",
            "terminal_branch", "status", "scope",
        ),
        "P4 result contract",
    )
    if (
        result["schema_version"] != 1
        or result["contract_type"] != "majorana_p4_formal_two_step_result_contract_v2"
    ):
        raise SchemaError("unexpected P4 result contract identity")
    if result_path.read_bytes() != canonical_bytes(result) + b"\n":
        raise VerificationError("P4 result contract is not canonical JSON plus newline")
    package = _package_from_result(result, precommit, base)
    _validate_replay_package(package, base)
    if result["replay_package_sha256"] != hashlib.sha256(
        canonical_bytes(package) + b"\n"
    ).hexdigest():
        raise VerificationError("P4 replay package digest is not reconstructible")
    if result["scope"] != result["witness"]["scope"]:
        raise VerificationError("P4 result scope mismatch")
    expected_contract, expected_certificate = materialize_result(package, base)
    if result != expected_contract:
        raise VerificationError("P4 result contract content mismatch")
    if certificate_path.read_bytes() != canonical_bytes(certificate) + b"\n":
        raise VerificationError("P4 certificate is not canonical JSON plus newline")
    if certificate != expected_certificate:
        raise VerificationError("P4 certificate content mismatch")
    return {
        "status": result["status"],
        "terminal_branch": result["terminal_branch"],
        "precommit_commit_sha": result["precommit_commit_sha"],
        "raw_witness_sha256": result["raw_witness_sha256"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "result_contract_sha256": file_sha256(result_path),
        "certificate_sha256": file_sha256(certificate_path),
        "policy_id": policy["policy_id"],
    }


def _write_canonical_json(path: Path, value: Any) -> None:
    path = Path(path)
    payload = canonical_bytes(value) + b"\n"
    temporary = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-precommit", action="store_true")
    parser.add_argument("--fresh-replay", action="store_true")
    parser.add_argument("--materialize-result", action="store_true")
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--precommit-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--replay-output", type=Path)
    parser.add_argument("--contract-output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    args = parser.parse_args(argv)
    selected = sum(map(int, (
        args.verify_precommit, args.fresh_replay, args.materialize_result,
        args.verify_final,
    )))
    if selected != 1:
        parser.error("select exactly one operation")
    if args.verify_precommit:
        summary = verify_precommit()
    elif args.fresh_replay:
        if not all((args.precommit_commit, args.julia, args.depot, args.replay_output)):
            parser.error("fresh replay requires commit, Julia, depot, and replay output")
        try:
            package = fresh_replay(
                args.precommit_commit, args.julia, args.depot,
            )
        except IndeterminateReplay as error:
            print(json.dumps(
                {"status": "INDETERMINATE", "reason": str(error)},
                sort_keys=True, separators=(",", ":"),
            ))
            return 2
        _write_canonical_json(args.replay_output, package)
        summary = {
            "status": package["status"],
            "terminal_branch": package["terminal_branch"],
            "raw_witness_sha256": package["raw_witness_sha256"],
            "canonical_witness_sha256": package["canonical_witness_sha256"],
            "raw_transcript_sha256_in_order": package[
                "raw_transcript_sha256_in_order"
            ],
        }
    elif args.materialize_result:
        if not all((args.replay_output, args.contract_output, args.certificate_output)):
            parser.error("materialization requires replay, contract, and certificate paths")
        package = P3.strict_json_loads(
            args.replay_output.read_bytes(), source="P4 replay package",
        )
        contract, certificate = materialize_result(package)
        _write_canonical_json(args.contract_output, contract)
        _write_canonical_json(args.certificate_output, certificate)
        summary = {
            "status": contract["status"],
            "terminal_branch": contract["terminal_branch"],
            "result_contract_sha256": file_sha256(args.contract_output),
            "certificate_sha256": file_sha256(args.certificate_output),
        }
    else:
        summary = verify_final()
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
