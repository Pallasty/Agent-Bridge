#!/usr/bin/env python3
"""Independent schedule/resource verifier and isolated replay harness for Majorana P2."""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import time
from typing import Any, Mapping, Sequence
import uuid


BASE = Path(__file__).resolve().parent
FIXTURE_NAME = "majorana_certificate_p2_fixture.json"
POLICY_NAME = "majorana_certificate_p2_policy.json"
RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"
PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p2_precommit_contract.json"
RESULT_CONTRACT_NAME = "majorana_certificate_p2_contract.json"
CERTIFICATE_NAME = "majorana_certificate_p2_certificate.json"
RESULT_TEST_NAME = "test_majorana_certificate_p2_result.py"
CHECKER_NAME = "majorana_certificate_p2_checker.py"
RUNNER_RELATIVE_PATH = "majorana_certificate_p2/majorana_p2_runner.jl"
PROJECT_DIRECTORY_NAME = "majorana_certificate_p0"
P0_CHECKER_NAME = "majorana_certificate_p0_checker.py"
P1_CHECKER_NAME = "majorana_certificate_p1_checker.py"
P1_CONTRACT_NAME = "majorana_certificate_p1_contract.json"
P1_CERTIFICATE_NAME = "majorana_certificate_p1_certificate.json"
P1_RESULT_TEST_NAME = "test_majorana_certificate_p1_result.py"
REQUIRED_PARENT_COMMIT = "2062c64a13b71189f01a0f2e9a11957534bf3a77"
P1_STATUS = (
    "VERIFIED_MAJORANA_P1_L2_L3_HUBBARD_SPARSE_ACTION_AND_CADENCE_"
    "CONFORMANCE_SUBCERTIFICATE"
)
MAXIMUM_STATUS = (
    "VERIFIED_MAJORANA_P2_L8_STAGGERED_MAGNETIZATION_ONE_STEP_BOUNDED_"
    "PREFIX_RESOURCE_FEASIBILITY_SUBCERTIFICATE"
)
CAP_STATUS = "VERIFIED_MAJORANA_P2_L8_ONE_STEP_PREFIX_POLICY_CAP_EXCEEDED_SUBCERTIFICATE"
RESULT_ARTIFACTS = (RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME)
FIXTURE_CANONICAL_SHA256 = "a8b0df9fd66bfaa5e1c1602fce4896de174b06e63a972f66f19fb1fe60fb3c01"
POLICY_CANONICAL_SHA256 = "b633637e9f06c22adc091fcae4aea3b6261e0a750aaf80bf391d798fdb15bec1"
STAGE_GROUPS = ("H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1")
MASK_HEX_RE = re.compile(r"[0-9a-f]{64}\Z")
FLOAT_BITS_RE = re.compile(r"[0-9a-f]{16}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


def _load_helper(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


P0 = _load_helper("majorana_p2_p0_helper", BASE / P0_CHECKER_NAME)
P1 = _load_helper("majorana_p2_p1_helper", BASE / P1_CHECKER_NAME)
SchemaError = P0.SchemaError
VerificationError = P0.VerificationError
canonical_bytes = P0.canonical_bytes
canonical_sha256 = P0.canonical_sha256
file_sha256 = P0.file_sha256
strict_json_loads = P0.strict_json_loads
load_json = P0.load_json
require_exact_keys = P0.require_exact_keys
require_sha256 = P0.require_sha256


class IndeterminateReplay(RuntimeError):
    """Raised only for host/sandbox resource failures with no negative authority."""


def _require_plain_int(value: Any, context: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise SchemaError(f"{context} must be an integer >= {minimum}")
    return value


def _format_q(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _float_bits_hex(value: float) -> str:
    return struct.pack(">d", value).hex()


def _mask_hex(mask: int) -> str:
    if type(mask) is not int or mask < 0 or mask.bit_length() > 256:
        raise VerificationError("Majorana mask is outside UInt256")
    return f"{mask:064x}"


def _term_stream_sha256(rows: Sequence[tuple[int, float]]) -> str:
    digest = hashlib.sha256()
    for mask, coefficient in rows:
        digest.update(_mask_hex(mask).encode("ascii"))
        digest.update(b"\t")
        digest.update(_float_bits_hex(coefficient).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _mask(*majorana_indices: int) -> int:
    output = 0
    for index in majorana_indices:
        if type(index) is not int or index < 1 or index > 256:
            raise VerificationError("invalid Majorana generator index")
        output |= 1 << (index - 1)
    return output


def _constructor_terms(symbol: str, sites: Sequence[int]) -> dict[int, Fraction]:
    if symbol == "nup":
        site = sites[0]
        return {_mask(4 * site - 3, 4 * site - 2): Fraction(1, 2), 0: Fraction(1, 2)}
    if symbol == "ndn":
        site = sites[0]
        return {_mask(4 * site - 1, 4 * site): Fraction(1, 2), 0: Fraction(1, 2)}
    if symbol == "nupndn":
        site = sites[0]
        up = _mask(4 * site - 3, 4 * site - 2)
        down = _mask(4 * site - 1, 4 * site)
        return {
            up: Fraction(1, 4),
            down: Fraction(1, 4),
            up | down: Fraction(-1, 4),
            0: Fraction(1, 4),
        }
    if symbol in ("hopup", "hopdn"):
        left, right = sorted(sites)
        if symbol == "hopup":
            return {
                _mask(4 * left - 3, 4 * right - 2): Fraction(1, 2),
                _mask(4 * left - 2, 4 * right - 3): Fraction(-1, 2),
            }
        return {
            _mask(4 * left - 1, 4 * right): Fraction(1, 2),
            _mask(4 * left, 4 * right - 1): Fraction(-1, 2),
        }
    raise VerificationError(f"unsupported constructor: {symbol}")


def _forward_group_specs(group: str) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    if group == "HU":
        for site0 in range(64):
            row, column = divmod(site0, 8)
            specs.append(
                {
                    "operator_id": f"HU_r{row}_c{column}",
                    "symbol": "nupndn",
                    "sites": [site0 + 1],
                    "multiplier": Fraction(8),
                }
            )
        return specs
    horizontal = group in ("H1", "H2")
    parity = 0 if group in ("H1", "H4") else 1
    if horizontal:
        for row in range(8):
            for column in range(parity, 7, 2):
                left = row * 8 + column + 1
                right = left + 1
                for spin, symbol in (("up", "hopup"), ("down", "hopdn")):
                    specs.append(
                        {
                            "operator_id": f"{group}_r{row}_c{column}_{spin}",
                            "symbol": symbol,
                            "sites": [left, right],
                            "multiplier": Fraction(-1),
                        }
                    )
    else:
        for row in range(parity, 7, 2):
            for column in range(8):
                top = row * 8 + column + 1
                bottom = top + 8
                for spin, symbol in (("up", "hopup"), ("down", "hopdn")):
                    specs.append(
                        {
                            "operator_id": f"{group}_r{row}_c{column}_{spin}",
                            "symbol": symbol,
                            "sites": [top, bottom],
                            "multiplier": Fraction(-1),
                        }
                    )
    return specs


def _majorana_commutes(left: int, right: int) -> bool:
    exponent = left.bit_count() * right.bit_count() - (left & right).bit_count()
    return exponent % 2 == 0


def expected_schedule() -> dict[str, Any]:
    composites: list[dict[str, Any]] = []
    commutation_rows: list[dict[str, Any]] = []
    theta_histogram: dict[str, int] = {}
    composite_index = 0
    constituent_index = 0
    boundary_index = 0
    for stage_index, group in enumerate(STAGE_GROUPS):
        duration = Fraction(1, 100) if group == "H4" else Fraction(1, 200)
        stage_masks: list[int] = []
        for occurrence_in_stage, spec in enumerate(reversed(_forward_group_specs(group))):
            terms = _constructor_terms(spec["symbol"], spec["sites"])
            terms.pop(0, None)
            truncate_each = spec["symbol"] == "nupndn"
            constituents: list[dict[str, Any]] = []
            sorted_terms = sorted(terms.items())
            for constituent_in_composite, (mask, constructor_coefficient) in enumerate(sorted_terms):
                physical_theta = duration * spec["multiplier"]
                applied = physical_theta * constructor_coefficient * 2
                applied_float = float(applied)
                key = _format_q(applied)
                theta_histogram[key] = theta_histogram.get(key, 0) + 1
                boundary_after = truncate_each or constituent_in_composite == len(sorted_terms) - 1
                constituents.append(
                    {
                        "constituent_index": constituent_index,
                        "constituent_in_composite": constituent_in_composite,
                        "mask_hex": _mask_hex(mask),
                        "constructor_coefficient": _format_q(constructor_coefficient),
                        "applied_angle": key,
                        "applied_angle_Float64_bits_hex": _float_bits_hex(applied_float),
                        "boundary_after": boundary_after,
                        "boundary_index_after": boundary_index if boundary_after else None,
                    }
                )
                stage_masks.append(mask)
                constituent_index += 1
                if boundary_after:
                    boundary_index += 1
            composites.append(
                {
                    "stage_index": stage_index,
                    "group": group,
                    "composite_index": composite_index,
                    "occurrence_in_stage": occurrence_in_stage,
                    "operator_id": spec["operator_id"],
                    "symbol": spec["symbol"],
                    "sites": spec["sites"],
                    "event_duration": _format_q(duration),
                    "physical_theta": _format_q(duration * spec["multiplier"]),
                    "truncate_after_each_constituent": truncate_each,
                    "constituents": constituents,
                }
            )
            composite_index += 1
        if len(set(stage_masks)) != len(stage_masks):
            raise VerificationError("independent schedule contains duplicate stage masks")
        for left_index, left in enumerate(stage_masks):
            for right in stage_masks[left_index + 1 :]:
                if not _majorana_commutes(left, right):
                    raise VerificationError("independent schedule stage does not commute")
        commutation_rows.append(
            {
                "stage_index": stage_index,
                "group": group,
                "generator_count": len(stage_masks),
                "unordered_pair_count": len(stage_masks) * (len(stage_masks) - 1) // 2,
                "masks_sha256": canonical_sha256([_mask_hex(mask) for mask in sorted(stage_masks)]),
                "all_pairs_commute": True,
            }
        )
    if (composite_index, constituent_index, boundary_index) != (512, 1152, 768):
        raise VerificationError("independent schedule total mismatch")
    expected_histogram = {
        "-1/100": 64,
        "-1/200": 320,
        "-1/50": 128,
        "1/100": 64,
        "1/200": 320,
        "1/50": 256,
    }
    if theta_histogram != expected_histogram:
        raise VerificationError("independent angle histogram mismatch")
    return {
        "stage_groups": list(STAGE_GROUPS),
        "stage_count": 9,
        "composite_count": 512,
        "constituent_count": 1152,
        "truncation_boundary_count": 768,
        "theta_histogram": theta_histogram,
        "composites": composites,
        "composites_sha256": canonical_sha256(composites),
        "stage_commutation": commutation_rows,
        "stage_commutation_sha256": canonical_sha256(commutation_rows),
        "central_H4_fused_before_execution": True,
        "raw_and_fused_exact_stage_unitary_equal_from_internal_commutation": True,
        "raw_and_fused_threshold_paths_identical": False,
    }


def expected_initial_observable() -> dict[str, Any]:
    rows: list[tuple[int, float]] = []
    for site0 in range(64):
        row, column = divmod(site0, 8)
        sign = 1.0 if (row + column) % 2 == 0 else -1.0
        site = site0 + 1
        rows.append((_mask(4 * site - 3, 4 * site - 2), sign / 128.0))
        rows.append((_mask(4 * site - 1, 4 * site), -sign / 128.0))
    rows.sort()
    return {
        "nonzero_term_count": 128,
        "initial_exact_zero_identity_prune_count": 1,
        "term_stream_sha256": _term_stream_sha256(rows),
    }


def validate_fixture(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError("P2 fixture must be an object")
    if canonical_sha256(value) != FIXTURE_CANONICAL_SHA256:
        raise SchemaError("P2 fixture differs from the frozen semantic object")
    if value.get("schema_version") != 1 or value.get("fixture_id") != (
        "MAJORANA-P2-L8-FUSED-ONE-STEP-RESOURCE-PREFIX-V1"
    ):
        raise SchemaError("unexpected P2 fixture identity")
    lattice = value["lattice_and_observable"]
    expected_lattice = {
        "linear_size": 8,
        "n_sites": 64,
        "n_modes": 128,
        "n_fermionic_modes": 128,
        "n_majorana_generators": 256,
        "mask_type": "UInt256",
        "boundary_condition": "square_open_boundary_no_wrap",
        "site_order": "row_major_zero_based_coordinates_exposed_as_one_based_Julia_sites",
        "mode_order": "site_major_spin_minor_q_equals_2_times_site_plus_up0_down1",
        "observable_id": "staggered_magnetization",
        "observable_definition": "(1/64)*sum_(-1)^(row+column)*(nup-ndn)",
        "observable_initial_nonzero_term_count": 128,
        "initial_exact_zero_identity_prune_count": 1,
        "initial_exact_zero_prune_is_outside_the_768_cadence_boundaries": True,
        "diagnostic_initial_state": "checkerboard_Neel_A_up_B_down_Nup32_Ndown32",
    }
    if lattice != expected_lattice:
        raise VerificationError("P2 lattice/observable fixture mismatch")
    prefix = value["heisenberg_prefix"]
    if (
        tuple(prefix["stage_order"]) != STAGE_GROUPS
        or prefix["stage_count"] != 9
        or prefix["planned_composite_count"] != 512
        or prefix["planned_constituent_count"] != 1152
        or prefix["planned_truncation_boundary_count"] != 768
    ):
        raise VerificationError("P2 prefix fixture mismatch")
    stage_counts = [
        ("H1", 64, 128, 64, "1/200"),
        ("H2", 48, 96, 48, "1/200"),
        ("HU", 64, 192, 192, "1/200"),
        ("H3", 48, 96, 48, "1/200"),
        ("H4", 64, 128, 64, "1/100"),
        ("H3", 48, 96, 48, "1/200"),
        ("HU", 64, 192, 192, "1/200"),
        ("H2", 48, 96, 48, "1/200"),
        ("H1", 64, 128, 64, "1/200"),
    ]
    for index, (group, composites, constituents, boundaries, duration) in enumerate(stage_counts):
        row = prefix["stages"][index]
        if row != {
            "stage_index": index,
            "group": group,
            "event_duration": duration,
            "composite_count": composites,
            "constituent_count": constituents,
            "truncation_boundary_count": boundaries,
        }:
            raise VerificationError(f"P2 stage fixture mismatch at {index}")
    execution = value["execution_semantics"]
    if (
        execution["coefficient_type"] != "Float64"
        or execution["threshold_rational"] != "1/17179869184"
        or execution["threshold_Float64_bits_hex"] != "3dd0000000000000"
        or execution["threshold_comparison"] != "strict_less_than"
    ):
        raise VerificationError("P2 threshold fixture mismatch")
    caps = value["deterministic_resource_caps"]
    expected_caps = {
        "maximum_boundary_retained_terms": 65_536,
        "maximum_current_terms_before_constituent": 65_536,
        "maximum_premerge_terms": 65_536,
        "maximum_cap_scan_term_visits": 33_554_432,
        "maximum_propagation_term_visits": 33_554_432,
        "maximum_truncation_term_visits": 16_777_216,
        "maximum_total_charged_term_visits": 67_108_864,
        "maximum_composites": 512,
        "maximum_constituents": 1152,
        "maximum_truncation_boundaries": 768,
    }
    if caps != expected_caps:
        raise VerificationError("P2 deterministic cap fixture mismatch")
    host = value["host_supervisor_caps"]
    if host != {
        "systemd_user_scope_cgroup_v2_required": True,
        "RuntimeMaxSec": "300s",
        "MemoryMax_bytes": 4_294_967_296,
        "subprocess_safety_timeout_seconds": 330,
        "maximum_stdout_bytes": 8_388_608,
        "maximum_stderr_bytes": 1_048_576,
        "host_cap_failure_branch": "INDETERMINATE",
    }:
        raise VerificationError("P2 host cap fixture mismatch")
    expected_schedule()
    return value


def validate_runtime_lock(value: Any) -> Mapping[str, Any]:
    return P0.validate_runtime_lock(value)


def validate_policy(
    policy: Any, runtime_lock: Mapping[str, Any], base: Path = BASE
) -> Mapping[str, Any]:
    if not isinstance(policy, dict):
        raise SchemaError("P2 policy must be an object")
    if canonical_sha256(policy) != POLICY_CANONICAL_SHA256:
        raise SchemaError("P2 policy differs from the frozen semantic object")
    if policy.get("schema_version") != 1 or policy.get("policy_id") != "MAJORANA-P2-S0":
        raise SchemaError("unexpected P2 policy identity")
    authority = policy.get("maximum_positive_authority")
    if not isinstance(authority, dict) or authority.get("status") != MAXIMUM_STATUS:
        raise SchemaError("P2 maximum authority mismatch")
    boundary = policy.get("precommit_boundary")
    if not isinstance(boundary, dict) or any(
        boundary.get(field) is not False
        for field in (
            "policy_contains_observed_replay_results",
            "policy_contains_witness_or_result_hashes",
            "policy_promises_a_terminal_branch",
        )
    ):
        raise SchemaError("P2 policy is not result-unpinned")
    encoded = canonical_bytes(policy).decode("utf-8")
    for forbidden in policy.get("forbidden_formal_result_pins", ()):
        if not isinstance(forbidden, str):
            raise SchemaError("P2 forbidden result pin names must be strings")
        if f'"{forbidden}":' in encoded:
            raise SchemaError(f"P2 policy contains forbidden result pin: {forbidden}")
    parent = policy.get("source_and_parent_custody")
    if (
        not isinstance(parent, dict)
        or parent.get("required_direct_parent_commit") != REQUIRED_PARENT_COMMIT
        or parent.get("required_parent_status") != P1_STATUS
    ):
        raise SchemaError("P2 parent custody policy mismatch")
    legal = policy.get("legal_terminal_branches")
    if not isinstance(legal, list) or [row.get("branch") for row in legal] != [
        "PREFIX_COMPLETED_UNDER_CAPS",
        "DETERMINISTIC_POLICY_CAP_EXCEEDED",
        "FAILED_CONFORMANCE",
        "INDETERMINATE",
        "INVALID_REPLAY",
    ]:
        raise SchemaError("P2 legal terminal branches mismatch")
    if legal[0].get("maximum_status") != MAXIMUM_STATUS or legal[1].get(
        "maximum_status"
    ) != CAP_STATUS:
        raise SchemaError("P2 legal status mapping mismatch")
    if policy["scope_boundary"].get("ready_gate_eligible") is not False:
        raise SchemaError("P2 policy improperly permits READY")
    validate_runtime_lock(runtime_lock)
    return policy


EXPECTED_SCOPE = {
    "maximum_positive_status": MAXIMUM_STATUS,
    "fixed_L8_first_fused_mapped_step_Float64_resource_feasibility_only": True,
    "binary64_coefficient_accuracy": "NOT_ASSESSED",
    "threshold_drop_is_a_certified_error_bound": False,
    "raw_1280_constituent_threshold_path": "NOT_EXECUTED",
    "existing_Python_topL1_route_result_equality": "NOT_CLAIMED",
    "double_occupancy": "NOT_ASSESSED",
    "remaining_99_mapped_steps": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
    "exact_time_evolution": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}


def _expected_runtime(runtime_lock: Mapping[str, Any]) -> dict[str, Any]:
    runtime = runtime_lock["julia_runtime"]
    project = runtime_lock["project_environment"]
    return {
        "julia_version": runtime["version"],
        "julia_commit": runtime["build_commit_short"],
        "machine": runtime["machine"],
        "threads": 1,
        "executable_sha256": runtime["executable"]["sha256"],
        "sysimage_sha256": runtime["sysimage"]["sha256"],
        "project_sha256": project["project"]["sha256"],
        "manifest_sha256": project["manifest"]["sha256"],
    }


def _expected_upstream(runtime_lock: Mapping[str, Any]) -> dict[str, Any]:
    packages = runtime_lock["direct_and_semantic_upstream_packages"]
    return {
        "majorana_propagation_version": packages["MajoranaPropagation"]["version"],
        "pauli_propagation_version": packages["PauliPropagation"]["version"],
        "majorana_source_closure": packages["MajoranaPropagation"]["installed_source_closure"],
        "pauli_source_closure": packages["PauliPropagation"]["installed_source_closure"],
    }


def _flatten_schedule(schedule: Mapping[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    flattened: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for composite in schedule["composites"]:
        for constituent in composite["constituents"]:
            flattened.append((composite, constituent))
    return flattened


def _neel_mask_hex() -> str:
    occupied = 0
    for site0 in range(64):
        row, column = divmod(site0, 8)
        site = site0 + 1
        if (row + column) % 2 == 0:
            occupied |= 1 << (4 * site - 4)
        else:
            occupied |= 1 << (4 * site - 2)
    return _mask_hex(occupied)


def _validate_resource_execution(
    execution: Any,
    final_state: Any,
    outcome: str,
    fixture: Mapping[str, Any],
    schedule: Mapping[str, Any],
) -> None:
    require_exact_keys(
        execution,
        (
            "completed_composite_count",
            "completed_constituent_count",
            "completed_truncation_boundary_count",
            "peak_premerge_contribution_count",
            "peak_postmerge_unique_term_count",
            "anticommuting_split_count",
            "threshold_dropped_term_count",
            "exact_zero_dropped_term_count",
            "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex",
            "counters",
            "transition_records",
            "transition_records_sha256",
            "boundary_records",
            "boundary_records_sha256",
            "stage_records",
            "stage_records_sha256",
            "cap_event",
        ),
        "P2 execution",
    )
    transitions = execution["transition_records"]
    boundaries = execution["boundary_records"]
    stages = execution["stage_records"]
    if not all(isinstance(rows, list) for rows in (transitions, boundaries, stages)):
        raise SchemaError("P2 resource ledgers must be arrays")
    if execution["transition_records_sha256"] != canonical_sha256(transitions):
        raise VerificationError("P2 transition ledger digest mismatch")
    if execution["boundary_records_sha256"] != canonical_sha256(boundaries):
        raise VerificationError("P2 boundary ledger digest mismatch")
    if execution["stage_records_sha256"] != canonical_sha256(stages):
        raise VerificationError("P2 stage ledger digest mismatch")
    expected_flat = _flatten_schedule(schedule)
    if len(transitions) > len(expected_flat):
        raise VerificationError("P2 transition ledger exceeds schedule")
    caps = fixture["deterministic_resource_caps"]
    boundary_by_index: dict[int, Mapping[str, Any]] = {}
    previous_output_count: int | None = 128
    input_sum = 0
    split_sum = 0
    peak_premerge = 128
    peak_postmerge = 128
    expected_boundary_count = 0
    for index, transition in enumerate(transitions):
        require_exact_keys(
            transition,
            (
                "constituent_index",
                "composite_index",
                "stage_index",
                "group",
                "mask_hex",
                "applied_angle",
                "input_term_count",
                "anticommuting_split_count",
                "premerge_contribution_count",
                "postmerge_unique_term_count",
                "boundary_index_after",
                "retained_term_count_after_boundary",
            ),
            f"P2 transition {index}",
        )
        composite, constituent = expected_flat[index]
        expected_static = {
            "constituent_index": constituent["constituent_index"],
            "composite_index": composite["composite_index"],
            "stage_index": composite["stage_index"],
            "group": composite["group"],
            "mask_hex": constituent["mask_hex"],
            "applied_angle": constituent["applied_angle"],
            "boundary_index_after": constituent["boundary_index_after"],
        }
        for field, expected_value in expected_static.items():
            if transition[field] != expected_value:
                raise VerificationError(f"P2 transition static mismatch at {index}: {field}")
        input_count = _require_plain_int(transition["input_term_count"], "input count")
        split_count = _require_plain_int(
            transition["anticommuting_split_count"], "split count"
        )
        premerge_count = _require_plain_int(
            transition["premerge_contribution_count"], "premerge count"
        )
        postmerge_count = _require_plain_int(
            transition["postmerge_unique_term_count"], "postmerge count"
        )
        if previous_output_count is not None and input_count != previous_output_count:
            raise VerificationError(f"P2 transition input recurrence mismatch at {index}")
        if split_count > input_count or premerge_count != input_count + split_count:
            raise VerificationError(f"P2 premerge recurrence mismatch at {index}")
        if postmerge_count > premerge_count:
            raise VerificationError(f"P2 merge cardinality mismatch at {index}")
        if input_count > caps["maximum_current_terms_before_constituent"]:
            raise VerificationError("P2 current-term cap exceeded in completed transition")
        if max(premerge_count, postmerge_count) > caps["maximum_premerge_terms"]:
            raise VerificationError("P2 premerge cap exceeded in completed transition")
        retained = transition["retained_term_count_after_boundary"]
        if constituent["boundary_after"]:
            if type(retained) is not int or retained < 0:
                raise SchemaError("P2 boundary transition lacks retained count")
            if retained > caps["maximum_boundary_retained_terms"]:
                raise VerificationError("P2 retained cap exceeded")
            previous_output_count = retained
            expected_boundary_count += 1
        else:
            if retained is not None:
                raise VerificationError("P2 non-boundary transition has retained count")
            previous_output_count = postmerge_count
        input_sum += input_count
        split_sum += split_count
        peak_premerge = max(peak_premerge, premerge_count)
        peak_postmerge = max(peak_postmerge, postmerge_count)

    dropped_sum = 0
    zero_sum = 0
    truncation_visits = 0
    if len(boundaries) != expected_boundary_count:
        raise VerificationError("P2 boundary count differs from completed transition prefix")
    for index, boundary in enumerate(boundaries):
        require_exact_keys(
            boundary,
            (
                "boundary_index",
                "stage_index",
                "group",
                "composite_index",
                "after_constituent_index",
                "boundary_kind",
                "postmerge_term_count",
                "retained_term_count",
                "threshold_dropped_term_count",
                "exact_zero_dropped_term_count",
                "dropped_term_stream_sha256",
                "dropped_abs_sum_Float64_diagnostic_bits_hex",
                "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex",
            ),
            f"P2 boundary {index}",
        )
        if boundary["boundary_index"] != index:
            raise VerificationError("P2 boundary indices are not contiguous")
        constituent_index = _require_plain_int(
            boundary["after_constituent_index"], "boundary constituent index"
        )
        if constituent_index >= len(transitions):
            raise VerificationError("P2 boundary references an incomplete transition")
        transition = transitions[constituent_index]
        if (
            transition["boundary_index_after"] != index
            or boundary["stage_index"] != transition["stage_index"]
            or boundary["group"] != transition["group"]
            or boundary["composite_index"] != transition["composite_index"]
            or boundary["postmerge_term_count"] != transition["postmerge_unique_term_count"]
            or boundary["retained_term_count"]
            != transition["retained_term_count_after_boundary"]
        ):
            raise VerificationError(f"P2 boundary/transition mismatch at {index}")
        postmerge = _require_plain_int(boundary["postmerge_term_count"], "boundary postmerge")
        retained = _require_plain_int(boundary["retained_term_count"], "boundary retained")
        dropped = _require_plain_int(
            boundary["threshold_dropped_term_count"], "boundary dropped"
        )
        zero = _require_plain_int(boundary["exact_zero_dropped_term_count"], "boundary zero")
        if retained + dropped != postmerge or zero > dropped:
            raise VerificationError(f"P2 threshold count recurrence mismatch at {index}")
        require_sha256(boundary["dropped_term_stream_sha256"], "P2 dropped digest")
        for field in (
            "dropped_abs_sum_Float64_diagnostic_bits_hex",
            "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex",
        ):
            if not isinstance(boundary[field], str) or FLOAT_BITS_RE.fullmatch(boundary[field]) is None:
                raise SchemaError(f"P2 boundary {field} is not Float64 bits")
        dropped_sum += dropped
        zero_sum += zero
        truncation_visits += postmerge
        boundary_by_index[index] = boundary

    counters = execution["counters"]
    require_exact_keys(
        counters,
        (
            "cap_scan_term_visits",
            "propagation_term_visits",
            "truncation_term_visits",
            "final_evaluation_term_visits",
            "total_charged_term_visits",
        ),
        "P2 resource counters",
    )
    counter_values = {
        field: _require_plain_int(value, f"P2 counter {field}")
        for field, value in counters.items()
    }
    if counter_values["total_charged_term_visits"] != sum(
        counter_values[field]
        for field in (
            "cap_scan_term_visits",
            "propagation_term_visits",
            "truncation_term_visits",
            "final_evaluation_term_visits",
        )
    ):
        raise VerificationError("P2 total charged visit recurrence mismatch")
    counter_caps = {
        "cap_scan_term_visits": caps["maximum_cap_scan_term_visits"],
        "propagation_term_visits": caps["maximum_propagation_term_visits"],
        "truncation_term_visits": caps["maximum_truncation_term_visits"],
        "total_charged_term_visits": caps["maximum_total_charged_term_visits"],
    }
    for field, limit in counter_caps.items():
        if counter_values[field] > limit:
            raise VerificationError(f"P2 completed resource counter exceeds cap: {field}")
    if outcome == "PREFIX_COMPLETED_UNDER_CAPS":
        if len(transitions) != 1152 or len(boundaries) != 768:
            raise VerificationError("P2 positive witness did not complete the full schedule")
        if execution["cap_event"] is not None:
            raise VerificationError("P2 positive witness contains a cap event")
        if counter_values["cap_scan_term_visits"] != input_sum or counter_values[
            "propagation_term_visits"
        ] != input_sum:
            raise VerificationError("P2 input visit counters differ from transition ledger")
        if counter_values["truncation_term_visits"] != truncation_visits:
            raise VerificationError("P2 truncation visits differ from boundary ledger")
        if not isinstance(final_state, dict):
            raise VerificationError("P2 positive witness lacks final state")
        require_exact_keys(
            final_state,
            (
                "retained_term_count",
                "term_stream_sha256",
                "checkerboard_Neel_occupied_mask_hex",
                "checkerboard_Neel_up_count",
                "checkerboard_Neel_down_count",
                "checkerboard_Neel_expectation_Float64_diagnostic_bits_hex",
                "checkerboard_Neel_contribution_stream_sha256",
                "expectation_is_diagnostic_not_scientific_authority",
            ),
            "P2 final state",
        )
        final_count = _require_plain_int(final_state["retained_term_count"], "final count")
        if final_count != previous_output_count or final_count > caps[
            "maximum_boundary_retained_terms"
        ]:
            raise VerificationError("P2 final term count mismatch")
        if counter_values["final_evaluation_term_visits"] != final_count:
            raise VerificationError("P2 final evaluation visit count mismatch")
        require_sha256(final_state["term_stream_sha256"], "P2 final term digest")
        require_sha256(
            final_state["checkerboard_Neel_contribution_stream_sha256"],
            "P2 Neel contribution digest",
        )
        if final_state["checkerboard_Neel_occupied_mask_hex"] != _neel_mask_hex():
            raise VerificationError("P2 checkerboard Neel mask mismatch")
        if (
            final_state["checkerboard_Neel_up_count"] != 32
            or final_state["checkerboard_Neel_down_count"] != 32
            or final_state["expectation_is_diagnostic_not_scientific_authority"] is not True
            or FLOAT_BITS_RE.fullmatch(
                final_state["checkerboard_Neel_expectation_Float64_diagnostic_bits_hex"]
            )
            is None
        ):
            raise VerificationError("P2 Neel diagnostic metadata mismatch")
    elif outcome == "DETERMINISTIC_POLICY_CAP_EXCEEDED":
        if final_state is not None or not isinstance(execution["cap_event"], dict):
            raise VerificationError("P2 cap witness has invalid terminal payload")
        cap_event = execution["cap_event"]
        require_exact_keys(
            cap_event,
            (
                "cap_name",
                "limit",
                "attempted",
                "context",
                "operation_was_not_executed_after_cap_detection",
            ),
            "P2 cap event",
        )
        if (
            type(cap_event["limit"]) is not int
            or type(cap_event["attempted"]) is not int
            or cap_event["attempted"] <= cap_event["limit"]
            or cap_event["operation_was_not_executed_after_cap_detection"] is not True
        ):
            raise VerificationError("P2 cap event does not prove an exceeded limit")
    else:
        raise VerificationError(f"unexpected P2 runner outcome: {outcome}")

    if execution["completed_constituent_count"] != len(transitions):
        raise VerificationError("P2 completed constituent count mismatch")
    if execution["completed_truncation_boundary_count"] != len(boundaries):
        raise VerificationError("P2 completed boundary count mismatch")
    if execution["peak_premerge_contribution_count"] != peak_premerge:
        raise VerificationError("P2 premerge peak mismatch")
    if execution["peak_postmerge_unique_term_count"] != peak_postmerge:
        raise VerificationError("P2 postmerge peak mismatch")
    if execution["anticommuting_split_count"] != split_sum:
        raise VerificationError("P2 split aggregate mismatch")
    if execution["threshold_dropped_term_count"] != dropped_sum:
        raise VerificationError("P2 threshold-drop aggregate mismatch")
    if execution["exact_zero_dropped_term_count"] != zero_sum:
        raise VerificationError("P2 zero-drop aggregate mismatch")
    if not isinstance(
        execution["cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex"], str
    ) or FLOAT_BITS_RE.fullmatch(
        execution["cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex"]
    ) is None:
        raise SchemaError("P2 cumulative diagnostic is not Float64 bits")
    if boundaries and execution[
        "cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex"
    ] != boundaries[-1]["cumulative_dropped_abs_sum_Float64_diagnostic_bits_hex"]:
        raise VerificationError("P2 cumulative diagnostic boundary mismatch")

    if outcome == "PREFIX_COMPLETED_UNDER_CAPS":
        if len(stages) != 9 or execution["completed_composite_count"] != 512:
            raise VerificationError("P2 stage/composite completion mismatch")
        for stage_index, stage in enumerate(stages):
            require_exact_keys(
                stage,
                (
                    "stage_index",
                    "group",
                    "input_term_count",
                    "final_retained_term_count",
                    "peak_premerge_contribution_count",
                    "peak_postmerge_unique_term_count",
                    "anticommuting_split_count",
                    "threshold_dropped_term_count",
                    "cap_scan_term_visits_increment",
                    "propagation_term_visits_increment",
                    "truncation_term_visits_increment",
                ),
                f"P2 stage {stage_index}",
            )
            stage_transitions = [
                row for row in transitions if row["stage_index"] == stage_index
            ]
            stage_boundaries = [row for row in boundaries if row["stage_index"] == stage_index]
            if (
                stage["stage_index"] != stage_index
                or stage["group"] != STAGE_GROUPS[stage_index]
                or stage["input_term_count"] != stage_transitions[0]["input_term_count"]
                or stage["final_retained_term_count"]
                != stage_transitions[-1]["retained_term_count_after_boundary"]
                or stage["peak_premerge_contribution_count"]
                != max(row["premerge_contribution_count"] for row in stage_transitions)
                or stage["peak_postmerge_unique_term_count"]
                != max(row["postmerge_unique_term_count"] for row in stage_transitions)
                or stage["anticommuting_split_count"]
                != sum(row["anticommuting_split_count"] for row in stage_transitions)
                or stage["threshold_dropped_term_count"]
                != sum(row["threshold_dropped_term_count"] for row in stage_boundaries)
                or stage["cap_scan_term_visits_increment"]
                != sum(row["input_term_count"] for row in stage_transitions)
                or stage["propagation_term_visits_increment"]
                != sum(row["input_term_count"] for row in stage_transitions)
                or stage["truncation_term_visits_increment"]
                != sum(row["postmerge_term_count"] for row in stage_boundaries)
            ):
                raise VerificationError(f"P2 stage aggregate mismatch at {stage_index}")


def validate_witness(
    witness: Any, fixture: Mapping[str, Any], runtime_lock: Mapping[str, Any]
) -> Mapping[str, Any]:
    require_exact_keys(
        witness,
        (
            "schema_version",
            "witness_type",
            "fixture_id",
            "fixture_sha256",
            "fixture_canonical_sha256",
            "outcome",
            "runtime",
            "upstream",
            "initial_observable",
            "schedule",
            "execution",
            "final_state",
            "scope",
        ),
        "P2 witness",
    )
    if (
        witness["schema_version"] != 1
        or witness["witness_type"]
        != "majorana_p2_L8_one_step_Float64_resource_feasibility_v1"
        or witness["fixture_id"] != fixture["fixture_id"]
    ):
        raise SchemaError("unexpected P2 witness identity")
    if witness["fixture_sha256"] != file_sha256(BASE / FIXTURE_NAME):
        raise VerificationError("P2 witness fixture raw digest mismatch")
    if witness["fixture_canonical_sha256"] != FIXTURE_CANONICAL_SHA256:
        raise VerificationError("P2 witness fixture canonical digest mismatch")
    if witness["runtime"] != _expected_runtime(runtime_lock):
        raise VerificationError("P2 runtime witness mismatch")
    if witness["upstream"] != _expected_upstream(runtime_lock):
        raise VerificationError("P2 upstream custody witness mismatch")
    if witness["initial_observable"] != expected_initial_observable():
        raise VerificationError("P2 initial observable witness mismatch")
    expected = expected_schedule()
    if witness["schedule"] != expected:
        raise VerificationError("P2 Julia schedule differs from independent L8 oracle")
    if witness["scope"] != EXPECTED_SCOPE:
        raise VerificationError("P2 witness scope mismatch")
    outcome = witness["outcome"]
    if outcome not in ("PREFIX_COMPLETED_UNDER_CAPS", "DETERMINISTIC_POLICY_CAP_EXCEEDED"):
        raise VerificationError("P2 runner emitted an illegal outcome")
    _validate_resource_execution(
        witness["execution"], witness["final_state"], outcome, fixture, expected
    )
    return witness


PRECOMMIT_SOURCE_PATHS = tuple(
    sorted(
        (
            CHECKER_NAME,
            FIXTURE_NAME,
            POLICY_NAME,
            RUNTIME_LOCK_NAME,
            P0_CHECKER_NAME,
            P1_CHECKER_NAME,
            "majorana_certificate_p1_fixture.json",
            "majorana_certificate_p1_policy.json",
            "majorana_certificate_p1_precommit_contract.json",
            P1_CONTRACT_NAME,
            P1_CERTIFICATE_NAME,
            P1_RESULT_TEST_NAME,
            "test_majorana_certificate_p2.py",
            "majorana_certificate_p1/majorana_p1_runner.jl",
            f"{PROJECT_DIRECTORY_NAME}/Project.toml",
            f"{PROJECT_DIRECTORY_NAME}/Manifest.toml",
            RUNNER_RELATIVE_PATH,
        )
    )
)


def validate_precommit_contract(
    contract: Any, base: Path = BASE
) -> Mapping[str, Any]:
    require_exact_keys(
        contract,
        (
            "schema_version",
            "contract_type",
            "self_relative_path",
            "required_parent_commit",
            "result_artifacts_required_absent",
            "source_files",
        ),
        "P2 precommit contract",
    )
    if (
        contract["schema_version"] != 1
        or contract["contract_type"]
        != "majorana_p2_result_unpinned_formal_replay_input_and_isolation_contract_v1"
        or contract["self_relative_path"] != PRECOMMIT_CONTRACT_NAME
        or contract["required_parent_commit"] != REQUIRED_PARENT_COMMIT
    ):
        raise SchemaError("unexpected P2 precommit contract identity")
    if tuple(contract["result_artifacts_required_absent"]) != RESULT_ARTIFACTS:
        raise SchemaError("P2 precommit result-artifact absence list mismatch")
    rows = contract["source_files"]
    if not isinstance(rows, list):
        raise SchemaError("P2 precommit source files must be an array")
    actual_paths: list[str] = []
    for index, row in enumerate(rows):
        require_exact_keys(
            row,
            ("relative_path", "size_bytes", "sha256"),
            f"P2 precommit source row {index}",
        )
        relative = row["relative_path"]
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise SchemaError("P2 precommit source path is unsafe")
        size = _require_plain_int(row["size_bytes"], "P2 precommit source size")
        require_sha256(row["sha256"], "P2 precommit source digest")
        path = base / relative
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"P2 precommit source is not regular: {relative}")
        body = path.read_bytes()
        if len(body) != size or hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise VerificationError(f"P2 precommit source bytes mismatch: {relative}")
        actual_paths.append(relative)
    if tuple(actual_paths) != PRECOMMIT_SOURCE_PATHS:
        raise SchemaError("P2 precommit source allowlist mismatch")
    if actual_paths != sorted(actual_paths):
        raise SchemaError("P2 precommit source rows must be path-sorted")
    return contract


def verify_parent_p1(base: Path = BASE) -> Mapping[str, Any]:
    summary = P1.verify_final(base)
    if summary.get("status") != P1_STATUS:
        raise VerificationError("P2 direct parent lacks the required P1 status")
    repo = Path(_run_git(base, "rev-parse", "--show-toplevel").stdout.decode().strip())
    parent_tree = _run_git(repo, "rev-parse", REQUIRED_PARENT_COMMIT).stdout.decode().strip()
    if parent_tree != REQUIRED_PARENT_COMMIT:
        raise VerificationError("P2 required parent commit is unavailable")
    for filename in (P1_CONTRACT_NAME, P1_CERTIFICATE_NAME, P1_RESULT_TEST_NAME):
        repo_relative = (base.resolve().relative_to(repo) / filename).as_posix()
        active = (base / filename).read_bytes()
        committed = _run_git(repo, "show", f"{REQUIRED_PARENT_COMMIT}:{repo_relative}").stdout
        if active != committed:
            raise VerificationError(f"P2 parent artifact differs from required parent: {filename}")
    return summary


def verify_precommit(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock, base)
    contract = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    parent = verify_parent_p1(base)
    for artifact in contract["result_artifacts_required_absent"]:
        if (base / artifact).exists():
            raise VerificationError(f"P2 result artifact must be absent before replay: {artifact}")
    schedule = expected_schedule()
    return {
        "policy_id": policy["policy_id"],
        "fixture_id": fixture["fixture_id"],
        "scope_ceiling": MAXIMUM_STATUS,
        "required_parent_commit": contract["required_parent_commit"],
        "required_parent_status": parent["status"],
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "schedule_sha256": canonical_sha256(schedule),
        "result_artifacts_absent": list(contract["result_artifacts_required_absent"]),
    }


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )


def _repo_and_base_relative(base: Path = BASE) -> tuple[Path, Path]:
    repo = Path(_run_git(base, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    try:
        relative = base.resolve().relative_to(repo)
    except ValueError as exc:
        raise VerificationError("P2 checker directory is outside the Git repository") from exc
    return repo, relative


def _verify_generation_git_state(
    precommit_commit: str, contract: Mapping[str, Any], base: Path = BASE
) -> tuple[Path, Path]:
    if not isinstance(precommit_commit, str) or COMMIT_RE.fullmatch(precommit_commit) is None:
        raise SchemaError("P2 precommit commit must be a full Git SHA-1")
    repo, base_relative = _repo_and_base_relative(base)
    head = _run_git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    if head != precommit_commit:
        raise VerificationError("P2 fresh replay requires HEAD equal to the precommit commit")
    if _run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("P2 fresh replay requires a completely clean worktree")
    parent = _run_git(repo, "show", "-s", "--format=%P", precommit_commit).stdout.decode().strip()
    if parent != contract["required_parent_commit"]:
        raise VerificationError("P2 precommit does not have the frozen direct parent")
    remote_contains = _run_git(repo, "branch", "-r", "--contains", precommit_commit).stdout.decode()
    if "origin/" not in remote_contains:
        raise VerificationError("P2 precommit must be pushed before formal replay")
    return repo, base_relative


def _git_blob(repo: Path, commit: str, repo_relative: str) -> tuple[str, str, bytes]:
    output = _run_git(repo, "ls-tree", "-z", commit, "--", repo_relative).stdout
    records = [record for record in output.split(b"\0") if record]
    if len(records) != 1:
        raise VerificationError(f"P2 Git input is missing or ambiguous: {repo_relative}")
    try:
        metadata, encoded_path = records[0].split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split(" ")
        decoded_path = encoded_path.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise VerificationError("malformed P2 git ls-tree record") from exc
    if decoded_path != repo_relative or mode != "100644" or object_type != "blob":
        raise VerificationError(f"non-regular P2 Git input: {repo_relative}")
    return mode, object_id, _run_git(repo, "cat-file", "blob", object_id).stdout


def _git_path_exists(repo: Path, commit: str, repo_relative: str) -> bool:
    return _run_git(repo, "cat-file", "-e", f"{commit}:{repo_relative}", check=False).returncode == 0


def _stage_precommit_tree(
    repo: Path,
    base_relative: Path,
    commit: str,
    contract: Mapping[str, Any],
    destination: Path,
) -> dict[str, Any]:
    rows_by_path = {row["relative_path"]: row for row in contract["source_files"]}
    allowlist = sorted([*rows_by_path, contract["self_relative_path"]])
    staged_rows: list[dict[str, Any]] = []
    for relative in allowlist:
        repo_relative = (base_relative / relative).as_posix()
        mode, object_id, body = _git_blob(repo, commit, repo_relative)
        if relative in rows_by_path:
            pin = rows_by_path[relative]
            if len(body) != pin["size_bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
                raise VerificationError(f"P2 Git blob differs from precommit pin: {relative}")
        elif body != (BASE / PRECOMMIT_CONTRACT_NAME).read_bytes():
            raise VerificationError("P2 Git precommit contract differs from active bytes")
        target = destination / repo_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        staged_rows.append(
            {
                "relative_path": repo_relative,
                "git_mode": mode,
                "git_blob": object_id,
                "size_bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    for artifact in contract["result_artifacts_required_absent"]:
        repo_relative = (base_relative / artifact).as_posix()
        if _git_path_exists(repo, commit, repo_relative):
            raise VerificationError(f"P2 result artifact exists in precommit: {artifact}")
    return {
        "files": staged_rows,
        "files_sha256": canonical_sha256(staged_rows),
        "file_count": len(staged_rows),
    }


def _kill_systemd_scope(unit_name: str, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(
        ["systemctl", "--user", "kill", "--signal=KILL", f"{unit_name}.scope"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if process.poll() is None:
        process.kill()


def _read_limited_stream(
    stream, cap: int, chunks: list[bytes], exceeded: threading.Event
) -> None:
    total = 0
    while True:
        block = stream.read(1 << 16)
        if not block:
            return
        total += len(block)
        if total <= cap:
            chunks.append(block)
        else:
            allowed = cap + 1 - sum(len(chunk) for chunk in chunks)
            if allowed > 0:
                chunks.append(block[:allowed])
            exceeded.set()


def _run_one_isolated_replay(
    staging_repo: Path,
    base_relative: Path,
    julia_executable: Path,
    depot: Path,
    run_root: Path,
    fixture: Mapping[str, Any],
) -> bytes:
    for executable in ("bwrap", "systemd-run", "systemctl"):
        if shutil.which(executable) is None:
            raise IndeterminateReplay(f"{executable} is required for P2 formal replay")
    if subprocess.run(
        ["stat", "-fc", "%T", "/sys/fs/cgroup"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    ).stdout.strip() != b"cgroup2fs":
        raise IndeterminateReplay("P2 formal replay requires cgroup v2")
    scratch = run_root / "scratch"
    depot_prefix = scratch / "depot"
    home = scratch / "home"
    tmp = scratch / "tmp"
    for path in (depot_prefix, home, tmp):
        path.mkdir(parents=True, exist_ok=False)
    staged_base = staging_repo / base_relative
    project = staged_base / PROJECT_DIRECTORY_NAME
    runner = staged_base / RUNNER_RELATIVE_PATH
    fixture_path = staged_base / FIXTURE_NAME
    host = fixture["host_supervisor_caps"]
    unit_name = f"majorana-p2-{uuid.uuid4().hex}"
    bwrap_command = [
        "bwrap",
        "--die-with-parent",
        "--unshare-net",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
        "--bind",
        str(scratch),
        str(scratch),
        "--clearenv",
        "--setenv",
        "HOME",
        str(home),
        "--setenv",
        "TMPDIR",
        str(tmp),
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--setenv",
        "LC_ALL",
        "C.UTF-8",
        "--setenv",
        "JULIA_DEPOT_PATH",
        f"{depot_prefix}:{depot}",
        "--setenv",
        "JULIA_LOAD_PATH",
        "@",
        "--setenv",
        "JULIA_NUM_THREADS",
        "1",
        "--setenv",
        "OPENBLAS_NUM_THREADS",
        "1",
        "--setenv",
        "JULIA_PKG_OFFLINE",
        "true",
        "--setenv",
        "JULIA_PKG_SERVER",
        "",
        "--chdir",
        str(staging_repo),
        str(julia_executable),
        "--startup-file=no",
        "--history-file=no",
        "--compiled-modules=no",
        f"--project={project}",
        str(runner),
        str(fixture_path),
    ]
    command = [
        "systemd-run",
        "--user",
        "--scope",
        "--quiet",
        f"--unit={unit_name}",
        "-p",
        f"MemoryMax={host['MemoryMax_bytes']}",
        "-p",
        f"RuntimeMaxSec={host['RuntimeMaxSec']}",
        "--",
        *bwrap_command,
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_exceeded = threading.Event()
    stderr_exceeded = threading.Event()
    readers = [
        threading.Thread(
            target=_read_limited_stream,
            args=(process.stdout, host["maximum_stdout_bytes"], stdout_chunks, stdout_exceeded),
            daemon=True,
        ),
        threading.Thread(
            target=_read_limited_stream,
            args=(process.stderr, host["maximum_stderr_bytes"], stderr_chunks, stderr_exceeded),
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + host["subprocess_safety_timeout_seconds"]
    reason: str | None = None
    while process.poll() is None:
        if stdout_exceeded.is_set():
            reason = "stdout byte cap"
            break
        if stderr_exceeded.is_set():
            reason = "stderr byte cap"
            break
        if time.monotonic() >= deadline:
            reason = "outer safety timeout"
            break
        time.sleep(0.01)
    if reason is not None:
        _kill_systemd_scope(unit_name, process)
    try:
        returncode = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _kill_systemd_scope(unit_name, process)
        returncode = process.wait(timeout=10)
        reason = reason or "scope termination failure"
    for reader in readers:
        reader.join(timeout=10)
    stdout = b"".join(stdout_chunks)
    stderr = b"".join(stderr_chunks)
    if reason is not None:
        raise IndeterminateReplay(f"P2 host resource abort: {reason}")
    if returncode != 0:
        diagnostic = stderr.decode("utf-8", errors="replace")[-4000:]
        raise IndeterminateReplay(
            f"P2 cgroup/bubblewrap replay exited {returncode}; host result is INDETERMINATE: {diagnostic}"
        )
    if stderr:
        raise IndeterminateReplay("P2 isolated replay emitted unexpected stderr")
    if len(stdout) > host["maximum_stdout_bytes"]:
        raise IndeterminateReplay("P2 isolated replay exceeded stdout cap")
    return stdout


def _status_for_outcome(outcome: str) -> str:
    if outcome == "PREFIX_COMPLETED_UNDER_CAPS":
        return MAXIMUM_STATUS
    if outcome == "DETERMINISTIC_POLICY_CAP_EXCEEDED":
        return CAP_STATUS
    raise VerificationError(f"illegal P2 outcome: {outcome}")


def fresh_replay(
    precommit_commit: str,
    julia_executable: Path,
    depot: Path,
    base: Path = BASE,
) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    validate_policy(load_json(base / POLICY_NAME), runtime_lock, base)
    contract = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    verify_parent_p1(base)
    repo, base_relative = _verify_generation_git_state(precommit_commit, contract, base)
    P0._verify_julia_runtime(julia_executable, runtime_lock)
    depot = depot.resolve()
    custody_before = P0._verify_depot_custody(depot, runtime_lock)
    with tempfile.TemporaryDirectory(prefix="majorana-p2-formal-") as temporary:
        root = Path(temporary)
        staging_repo = root / "staging"
        staging_repo.mkdir()
        manifest = _stage_precommit_tree(repo, base_relative, precommit_commit, contract, staging_repo)
        staging_before = P0._tree_digest(staging_repo)
        outputs: list[bytes] = []
        witnesses: list[Mapping[str, Any]] = []
        for index in range(2):
            run_root = root / f"run-{index + 1}"
            run_root.mkdir()
            output = _run_one_isolated_replay(
                staging_repo,
                base_relative,
                julia_executable.resolve(),
                depot,
                run_root,
                fixture,
            )
            witness = strict_json_loads(output, source=f"P2 Julia replay {index + 1} stdout")
            if output != canonical_bytes(witness) + b"\n":
                raise VerificationError("P2 Julia stdout is not canonical JSON plus newline")
            validate_witness(witness, fixture, runtime_lock)
            outputs.append(output)
            witnesses.append(witness)
        if outputs[0] != outputs[1]:
            raise VerificationError("two fresh P2 Julia stdout byte streams differ")
        if P0._tree_digest(staging_repo) != staging_before:
            raise VerificationError("P2 formal replay modified Git-object staging")
    custody_after = P0._verify_depot_custody(depot, runtime_lock)
    if custody_before != custody_after:
        raise VerificationError("P2 replay modified pinned depot custody")
    if _run_git(repo, "rev-parse", "HEAD").stdout.decode().strip() != precommit_commit:
        raise VerificationError("HEAD changed during P2 formal replay")
    if _run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("worktree changed during P2 formal replay")
    transcript = hashlib.sha256(outputs[0]).hexdigest()
    witness = witnesses[0]
    return {
        "schema_version": 1,
        "package_type": "majorana_p2_formal_fresh_replay_package_v1",
        "precommit_commit_sha": precommit_commit,
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "staging_manifest": manifest,
        "staging_tree_sha256": staging_before,
        "depot_custody": custody_after,
        "network_isolation": "bubblewrap_unshared_network_namespace",
        "host_resource_enforcement": {
            "cgroup_version": 2,
            "supervisor": "systemd_user_scope",
            "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
            "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
            "observed_runtime_or_memory_peak_in_canonical_package": False,
        },
        "fresh_process_count": 2,
        "stdout_byte_identical": True,
        "transcript_sha256_in_order": [transcript, transcript],
        "canonical_witness_sha256": canonical_sha256(witness),
        "witness": witness,
        "terminal_branch": witness["outcome"],
        "status": _status_for_outcome(witness["outcome"]),
    }


CERTIFICATE_CLAIMS = (
    "fixed_L8_square_OBC_staggered_magnetization_first_fused_mapped_step_execution",
    "independently_reconstructed_512_composite_1152_constituent_768_boundary_schedule",
    "unsigned_UInt256_constituent_sort_and_frozen_hopping_onsite_cadence",
    "strict_exactly_representable_binary64_2_pow_minus_34_threshold_execution",
    "predictive_preallocation_term_caps_and_charged_term_visit_caps",
    "kernel_enforced_cgroup_v2_MemoryMax_and_RuntimeMaxSec_for_each_fresh_replay",
    "two_byte_identical_network_isolated_fresh_process_transcripts",
)

CERTIFICATE_EXCLUSIONS = (
    "binary64_coefficient_or_threshold_drop_accuracy",
    "truncation_error_bound_or_uniform_scientific_budget",
    "raw_1280_constituent_threshold_path",
    "existing_Python_topL1_route_result_equality",
    "double_occupancy",
    "remaining_99_mapped_steps_or_full_R100",
    "product_formula_to_exact_Hubbard_error_or_exact_time_evolution",
    "physical_reference_qualification_or_READY",
    "native_unsorted_whole_circuit_vector_GPU_multithread_or_cross_host_performance",
)


def _validate_recorded_depot_custody(
    custody: Any, runtime_lock: Mapping[str, Any]
) -> None:
    packages = runtime_lock["direct_and_semantic_upstream_packages"]
    if not isinstance(custody, dict) or set(custody) != {"MajoranaPropagation", "PauliPropagation"}:
        raise SchemaError("P2 result depot custody package set mismatch")
    for package_name in ("MajoranaPropagation", "PauliPropagation"):
        row = custody[package_name]
        require_exact_keys(
            row,
            ("depot_relative_path", "file_count", "total_bytes", "closure_sha256"),
            f"P2 {package_name} depot custody",
        )
        expected = packages[package_name]["installed_source_closure"]
        if any(row[field] != expected[field] for field in ("file_count", "total_bytes", "closure_sha256")):
            raise VerificationError(f"P2 {package_name} depot custody mismatch")
        if not isinstance(row["depot_relative_path"], str):
            raise SchemaError("P2 depot relative path must be a string")


def _committed_precommit_evidence(
    precommit_commit: str,
    contract: Mapping[str, Any],
    base: Path = BASE,
) -> tuple[dict[str, Any], str]:
    if not isinstance(precommit_commit, str) or COMMIT_RE.fullmatch(precommit_commit) is None:
        raise SchemaError("P2 result precommit commit must be a full Git SHA-1")
    repo, base_relative = _repo_and_base_relative(base)
    if _run_git(repo, "cat-file", "-e", f"{precommit_commit}^{{commit}}", check=False).returncode:
        raise VerificationError("P2 result precommit commit does not exist")
    parent = _run_git(repo, "show", "-s", "--format=%P", precommit_commit).stdout.decode().strip()
    if parent != contract["required_parent_commit"]:
        raise VerificationError("P2 result precommit commit has the wrong direct parent")
    if _run_git(repo, "merge-base", "--is-ancestor", precommit_commit, "HEAD", check=False).returncode:
        raise VerificationError("P2 result precommit commit is not an ancestor of HEAD")
    if "origin/" not in _run_git(repo, "branch", "-r", "--contains", precommit_commit).stdout.decode():
        raise VerificationError("P2 result precommit commit lacks a pushed origin ref")
    for row in contract["source_files"]:
        relative = row["relative_path"]
        repo_relative = (base_relative / relative).as_posix()
        _mode, _object_id, body = _git_blob(repo, precommit_commit, repo_relative)
        if len(body) != row["size_bytes"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise VerificationError(f"P2 committed source differs from precommit pin: {relative}")
    contract_relative = (base_relative / PRECOMMIT_CONTRACT_NAME).as_posix()
    _mode, _object_id, contract_body = _git_blob(repo, precommit_commit, contract_relative)
    if contract_body != (base / PRECOMMIT_CONTRACT_NAME).read_bytes():
        raise VerificationError("P2 committed precommit contract differs from active bytes")
    for artifact in contract["result_artifacts_required_absent"]:
        if _git_path_exists(repo, precommit_commit, (base_relative / artifact).as_posix()):
            raise VerificationError(f"P2 result artifact exists in precommit commit: {artifact}")
    with tempfile.TemporaryDirectory(prefix="majorana-p2-evidence-") as temporary:
        staging = Path(temporary) / "staging"
        staging.mkdir()
        manifest = _stage_precommit_tree(
            repo, base_relative, precommit_commit, contract, staging
        )
        tree_sha256 = P0._tree_digest(staging)
    return manifest, tree_sha256


def _validate_replay_package(
    package: Any, base: Path = BASE
) -> Mapping[str, Any]:
    require_exact_keys(
        package,
        (
            "schema_version",
            "package_type",
            "precommit_commit_sha",
            "precommit_contract_sha256",
            "staging_manifest",
            "staging_tree_sha256",
            "depot_custody",
            "network_isolation",
            "host_resource_enforcement",
            "fresh_process_count",
            "stdout_byte_identical",
            "transcript_sha256_in_order",
            "canonical_witness_sha256",
            "witness",
            "terminal_branch",
            "status",
        ),
        "P2 replay package",
    )
    if package["schema_version"] != 1 or package["package_type"] != (
        "majorana_p2_formal_fresh_replay_package_v1"
    ):
        raise SchemaError("unexpected P2 replay package identity")
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    validate_witness(package["witness"], fixture, runtime_lock)
    if package["terminal_branch"] != package["witness"]["outcome"] or package[
        "status"
    ] != _status_for_outcome(package["terminal_branch"]):
        raise VerificationError("P2 replay terminal status mismatch")
    if package["fresh_process_count"] != 2 or package["stdout_byte_identical"] is not True:
        raise VerificationError("P2 replay freshness/equality evidence mismatch")
    transcripts = package["transcript_sha256_in_order"]
    if not isinstance(transcripts, list) or len(transcripts) != 2 or transcripts[0] != transcripts[1]:
        raise VerificationError("P2 replay transcript equality mismatch")
    witness_bytes = canonical_bytes(package["witness"])
    expected_transcript = hashlib.sha256(witness_bytes + b"\n").hexdigest()
    if transcripts != [expected_transcript, expected_transcript]:
        raise VerificationError("P2 replay transcript digest mismatch")
    if package["canonical_witness_sha256"] != hashlib.sha256(witness_bytes).hexdigest():
        raise VerificationError("P2 replay witness digest mismatch")
    if package["network_isolation"] != "bubblewrap_unshared_network_namespace":
        raise VerificationError("P2 replay network isolation mismatch")
    expected_host = {
        "cgroup_version": 2,
        "supervisor": "systemd_user_scope",
        "MemoryMax_bytes": fixture["host_supervisor_caps"]["MemoryMax_bytes"],
        "RuntimeMaxSec": fixture["host_supervisor_caps"]["RuntimeMaxSec"],
        "observed_runtime_or_memory_peak_in_canonical_package": False,
    }
    if package["host_resource_enforcement"] != expected_host:
        raise VerificationError("P2 replay host resource enforcement mismatch")
    _validate_recorded_depot_custody(package["depot_custody"], runtime_lock)
    for field in (
        "precommit_contract_sha256",
        "staging_tree_sha256",
        "canonical_witness_sha256",
    ):
        require_sha256(package[field], f"P2 replay {field}")
    return package


def materialize_result(
    replay_package: Mapping[str, Any], base: Path = BASE
) -> tuple[dict[str, Any], dict[str, Any]]:
    package = _validate_replay_package(replay_package, base)
    contract = {
        "schema_version": 1,
        "contract_type": "majorana_p2_formal_result_contract_v1",
        "precommit_commit_sha": package["precommit_commit_sha"],
        "precommit_contract_sha256": package["precommit_contract_sha256"],
        "replay_package_sha256": hashlib.sha256(canonical_bytes(package) + b"\n").hexdigest(),
        "staging_manifest_sha256": canonical_sha256(package["staging_manifest"]),
        "staging_tree_sha256": package["staging_tree_sha256"],
        "depot_custody": package["depot_custody"],
        "network_isolation": package["network_isolation"],
        "host_resource_enforcement": package["host_resource_enforcement"],
        "fresh_process_count": package["fresh_process_count"],
        "stdout_byte_identical": package["stdout_byte_identical"],
        "transcript_sha256_in_order": package["transcript_sha256_in_order"],
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "witness": package["witness"],
        "terminal_branch": package["terminal_branch"],
        "status": package["status"],
        "scope": package["witness"]["scope"],
    }
    certificate = {
        "schema_version": 1,
        "certificate_type": "majorana_p2_resource_feasibility_subcertificate_v1",
        "status": package["status"],
        "terminal_branch": package["terminal_branch"],
        "authority": "fixed_L8_first_fused_mapped_step_Float64_execution_resource_feasibility_only",
        "result_contract_sha256": hashlib.sha256(canonical_bytes(contract) + b"\n").hexdigest(),
        "precommit_commit_sha": package["precommit_commit_sha"],
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "runner_sha256": file_sha256(base / RUNNER_RELATIVE_PATH),
        "checker_sha256": file_sha256(base / CHECKER_NAME),
        "canonical_witness_sha256": package["canonical_witness_sha256"],
        "claims": list(CERTIFICATE_CLAIMS),
        "explicit_exclusions": list(CERTIFICATE_EXCLUSIONS),
        "ready_gate_eligible": False,
    }
    return contract, certificate


def verify_final(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock, base)
    precommit = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    verify_parent_p1(base)
    result = load_json(base / RESULT_CONTRACT_NAME)
    certificate = load_json(base / CERTIFICATE_NAME)
    require_exact_keys(
        result,
        (
            "schema_version",
            "contract_type",
            "precommit_commit_sha",
            "precommit_contract_sha256",
            "replay_package_sha256",
            "staging_manifest_sha256",
            "staging_tree_sha256",
            "depot_custody",
            "network_isolation",
            "host_resource_enforcement",
            "fresh_process_count",
            "stdout_byte_identical",
            "transcript_sha256_in_order",
            "canonical_witness_sha256",
            "witness",
            "terminal_branch",
            "status",
            "scope",
        ),
        "P2 result contract",
    )
    if result["schema_version"] != 1 or result["contract_type"] != (
        "majorana_p2_formal_result_contract_v1"
    ):
        raise SchemaError("unexpected P2 result contract identity")
    validate_witness(result["witness"], fixture, runtime_lock)
    if (
        result["terminal_branch"] != result["witness"]["outcome"]
        or result["status"] != _status_for_outcome(result["terminal_branch"])
        or result["scope"] != result["witness"]["scope"]
    ):
        raise VerificationError("P2 result terminal status/scope mismatch")
    witness_bytes = canonical_bytes(result["witness"])
    witness_sha = hashlib.sha256(witness_bytes).hexdigest()
    if result["canonical_witness_sha256"] != witness_sha:
        raise VerificationError("P2 result witness digest mismatch")
    transcript = hashlib.sha256(witness_bytes + b"\n").hexdigest()
    if result["transcript_sha256_in_order"] != [transcript, transcript]:
        raise VerificationError("P2 result transcript digest mismatch")
    if result["fresh_process_count"] != 2 or result["stdout_byte_identical"] is not True:
        raise VerificationError("P2 result fresh replay evidence mismatch")
    if result["precommit_contract_sha256"] != file_sha256(base / PRECOMMIT_CONTRACT_NAME):
        raise VerificationError("P2 result precommit contract digest mismatch")
    manifest, staging_tree_sha256 = _committed_precommit_evidence(
        result["precommit_commit_sha"], precommit, base
    )
    if result["staging_manifest_sha256"] != canonical_sha256(manifest):
        raise VerificationError("P2 result staging manifest digest mismatch")
    if result["staging_tree_sha256"] != staging_tree_sha256:
        raise VerificationError("P2 result staging tree digest mismatch")
    _validate_recorded_depot_custody(result["depot_custody"], runtime_lock)
    reconstructed_package = {
        "schema_version": 1,
        "package_type": "majorana_p2_formal_fresh_replay_package_v1",
        "precommit_commit_sha": result["precommit_commit_sha"],
        "precommit_contract_sha256": result["precommit_contract_sha256"],
        "staging_manifest": manifest,
        "staging_tree_sha256": result["staging_tree_sha256"],
        "depot_custody": result["depot_custody"],
        "network_isolation": result["network_isolation"],
        "host_resource_enforcement": result["host_resource_enforcement"],
        "fresh_process_count": result["fresh_process_count"],
        "stdout_byte_identical": result["stdout_byte_identical"],
        "transcript_sha256_in_order": result["transcript_sha256_in_order"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "witness": result["witness"],
        "terminal_branch": result["terminal_branch"],
        "status": result["status"],
    }
    if result["replay_package_sha256"] != hashlib.sha256(
        canonical_bytes(reconstructed_package) + b"\n"
    ).hexdigest():
        raise VerificationError("P2 replay package digest is not reconstructible")
    require_exact_keys(
        certificate,
        (
            "schema_version",
            "certificate_type",
            "status",
            "terminal_branch",
            "authority",
            "result_contract_sha256",
            "precommit_commit_sha",
            "policy_sha256",
            "runtime_lock_sha256",
            "fixture_sha256",
            "runner_sha256",
            "checker_sha256",
            "canonical_witness_sha256",
            "claims",
            "explicit_exclusions",
            "ready_gate_eligible",
        ),
        "P2 certificate",
    )
    if (
        certificate["schema_version"] != 1
        or certificate["certificate_type"]
        != "majorana_p2_resource_feasibility_subcertificate_v1"
        or certificate["status"] != result["status"]
        or certificate["terminal_branch"] != result["terminal_branch"]
        or certificate["authority"]
        != "fixed_L8_first_fused_mapped_step_Float64_execution_resource_feasibility_only"
        or certificate["result_contract_sha256"] != file_sha256(base / RESULT_CONTRACT_NAME)
        or certificate["precommit_commit_sha"] != result["precommit_commit_sha"]
        or certificate["canonical_witness_sha256"] != witness_sha
        or certificate["claims"] != list(CERTIFICATE_CLAIMS)
        or certificate["explicit_exclusions"] != list(CERTIFICATE_EXCLUSIONS)
        or certificate["ready_gate_eligible"] is not False
    ):
        raise VerificationError("P2 certificate content mismatch")
    expected_hashes = {
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "runner_sha256": file_sha256(base / RUNNER_RELATIVE_PATH),
        "checker_sha256": file_sha256(base / CHECKER_NAME),
    }
    for field, expected in expected_hashes.items():
        if certificate[field] != expected:
            raise VerificationError(f"P2 certificate {field} mismatch")
    return {
        "status": result["status"],
        "terminal_branch": result["terminal_branch"],
        "precommit_commit_sha": result["precommit_commit_sha"],
        "canonical_witness_sha256": witness_sha,
        "result_contract_sha256": file_sha256(base / RESULT_CONTRACT_NAME),
        "certificate_sha256": file_sha256(base / CERTIFICATE_NAME),
        "policy_id": policy["policy_id"],
    }


def _write_canonical_json(path: Path, value: Any) -> None:
    payload = canonical_bytes(value) + b"\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-precommit", action="store_true")
    parser.add_argument("--fresh-replay", action="store_true")
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--materialize-result", action="store_true")
    parser.add_argument("--precommit-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--replay-output", type=Path)
    parser.add_argument("--contract-output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    args = parser.parse_args(argv)
    selected = sum(
        int(flag)
        for flag in (
            args.verify_precommit,
            args.fresh_replay,
            args.verify_final,
            args.materialize_result,
        )
    )
    if selected != 1:
        parser.error("select exactly one operation")
    if args.verify_precommit:
        summary = verify_precommit()
    elif args.fresh_replay:
        if not all((args.precommit_commit, args.julia, args.depot, args.replay_output)):
            parser.error("fresh replay requires commit, Julia, depot, and replay output")
        package = fresh_replay(args.precommit_commit, args.julia, args.depot)
        _write_canonical_json(args.replay_output, package)
        summary = {
            "status": package["status"],
            "terminal_branch": package["terminal_branch"],
            "canonical_witness_sha256": package["canonical_witness_sha256"],
            "transcript_sha256_in_order": package["transcript_sha256_in_order"],
        }
    elif args.materialize_result:
        if not all((args.replay_output, args.contract_output, args.certificate_output)):
            parser.error("materialization requires replay, contract, and certificate paths")
        package = strict_json_loads(
            args.replay_output.read_bytes(), source="P2 replay package"
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
