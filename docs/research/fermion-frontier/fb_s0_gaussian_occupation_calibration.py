#!/usr/bin/env python3
"""FB-S0 calibration for fermionic-Gaussian occupation data versus HOI Q2.

This is an interpretation counterexample, not a non-Gaussianity detector.  It
constructs two valid gauge-invariant quasifree mixed-state correlation kernels
with identical one- and two-mode occupation margins but different three-mode
occupation tables.  It then compares each table with the classical pairwise
maximum-entropy distribution Q2.

A separate fixed L=2, U=0 quadratic-circuit control scans all 56 mode triplets.
That fixture is deliberately a negative control and does not weaken the analytic
counterexample.  Nothing in this module reads BGL data or participates in the
L=8 resource-evidence gate.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import platform
import sys
import types
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


HERE = Path(__file__).resolve().parent
DEFAULT_CONTRACT = HERE / "fb_s0_gaussian_occupation_contract.json"
PILOT_PATH = HERE / "fermi_hubbard_l2_pilot.py"
FIBRE_DIRECTION = tuple(
    1 if cell.bit_count() % 2 == 0 else -1 for cell in range(8)
)


class CalibrationError(ValueError):
    """Raised when the frozen calibration contract or a check fails."""


def _exact_keys(value: Mapping[str, Any], keys: Iterable[str], name: str) -> None:
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        raise CalibrationError(
            f"{name} keys must exactly equal {sorted(expected)}; got {sorted(actual)}"
        )


def _fraction(value: Any, name: str) -> Fraction:
    if not isinstance(value, str) or not value:
        raise CalibrationError(f"{name} must be a non-empty rational string")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise CalibrationError(f"{name} is not a valid rational") from exc
    return result


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationError(f"{name} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise CalibrationError(f"{name} must be finite")
    return result


def load_contract(path: Path = DEFAULT_CONTRACT) -> Mapping[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, Mapping):
        raise CalibrationError("contract must be a JSON object")
    return value


def _validate_contract(contract: Mapping[str, Any]) -> None:
    _exact_keys(
        contract,
        (
            "schema_version",
            "calibration_id",
            "checker_sha256",
            "analytic_kernels",
            "expected_shared_single_inclusions",
            "expected_shared_pair_inclusions",
            "expected_q2_cells",
            "minimum_c3_bits",
            "l2_negative_control",
            "resource_limits",
            "fixed_claims",
        ),
        "contract",
    )
    if contract["schema_version"] != 1:
        raise CalibrationError("contract schema_version must be 1")
    if contract["calibration_id"] != "FB-S0_GAUSSIAN_OCCUPATION_Q2_INTERPRETATION_V1":
        raise CalibrationError("unexpected calibration_id")
    if not isinstance(contract["checker_sha256"], str) or len(contract["checker_sha256"]) != 64:
        raise CalibrationError("checker_sha256 must be a 64-character string")

    kernels = contract["analytic_kernels"]
    if not isinstance(kernels, Mapping):
        raise CalibrationError("analytic_kernels must be an object")
    _exact_keys(kernels, ("positive_loop", "negative_loop"), "analytic_kernels")
    for kernel_id, record in kernels.items():
        if not isinstance(record, Mapping):
            raise CalibrationError(f"analytic_kernels.{kernel_id} must be an object")
        _exact_keys(
            record,
            ("matrix", "expected_eigenvalues", "expected_triple_inclusion"),
            f"analytic_kernels.{kernel_id}",
        )
        matrix = record["matrix"]
        if not isinstance(matrix, list) or len(matrix) != 3:
            raise CalibrationError(f"analytic_kernels.{kernel_id}.matrix must be 3x3")
        for row_index, row in enumerate(matrix):
            if not isinstance(row, list) or len(row) != 3:
                raise CalibrationError(
                    f"analytic_kernels.{kernel_id}.matrix[{row_index}] must have length 3"
                )
            for column_index, item in enumerate(row):
                _fraction(item, f"{kernel_id}.matrix[{row_index}][{column_index}]")
        eigenvalues = record["expected_eigenvalues"]
        if not isinstance(eigenvalues, list) or len(eigenvalues) != 3:
            raise CalibrationError(f"{kernel_id}.expected_eigenvalues must have length 3")
        parsed_eigenvalues = [
            _fraction(item, f"{kernel_id}.expected_eigenvalues") for item in eigenvalues
        ]
        if any(item < 0 or item > 1 for item in parsed_eigenvalues):
            raise CalibrationError(f"{kernel_id} eigenvalues must lie in [0,1]")
        _fraction(record["expected_triple_inclusion"], f"{kernel_id}.triple")

    singles = contract["expected_shared_single_inclusions"]
    if not isinstance(singles, list) or len(singles) != 3:
        raise CalibrationError("expected_shared_single_inclusions must have length 3")
    for item in singles:
        _fraction(item, "expected_shared_single_inclusions")
    pairs = contract["expected_shared_pair_inclusions"]
    if not isinstance(pairs, Mapping):
        raise CalibrationError("expected_shared_pair_inclusions must be an object")
    _exact_keys(pairs, ("0,1", "0,2", "1,2"), "expected_shared_pair_inclusions")
    for item in pairs.values():
        _fraction(item, "expected_shared_pair_inclusions")
    q2_cells = contract["expected_q2_cells"]
    if not isinstance(q2_cells, list) or len(q2_cells) != 8:
        raise CalibrationError("expected_q2_cells must have length 8")
    if sum((_fraction(item, "expected_q2_cells") for item in q2_cells), Fraction()) != 1:
        raise CalibrationError("expected_q2_cells must sum exactly to one")
    if not 0 < _finite(contract["minimum_c3_bits"], "minimum_c3_bits") < 1:
        raise CalibrationError("minimum_c3_bits must lie in (0,1)")

    negative = contract["l2_negative_control"]
    if not isinstance(negative, Mapping):
        raise CalibrationError("l2_negative_control must be an object")
    _exact_keys(
        negative,
        (
            "pilot_sha256",
            "linear_size",
            "u_over_hopping",
            "total_time",
            "trotter_steps",
            "expected_modes",
            "expected_particles",
            "expected_triplets",
            "max_projection_residual",
            "max_inclusion_determinant_residual",
            "max_c3_bits",
        ),
        "l2_negative_control",
    )
    if not isinstance(negative["pilot_sha256"], str) or len(negative["pilot_sha256"]) != 64:
        raise CalibrationError("pilot_sha256 must be a 64-character string")
    if negative["linear_size"] != 2 or negative["expected_modes"] != 8:
        raise CalibrationError("the negative control must remain the fixed L=2/eight-mode fixture")
    if negative["expected_particles"] != 4 or negative["expected_triplets"] != 56:
        raise CalibrationError("the negative-control particle/triplet counts are frozen")
    if negative["u_over_hopping"] != 0.0:
        raise CalibrationError("the negative control must remain quadratic at U=0")
    if negative["total_time"] != 1.0 or negative["trotter_steps"] != 8:
        raise CalibrationError("the negative-control time and Trotter-step count are frozen")
    for key in (
        "max_projection_residual",
        "max_inclusion_determinant_residual",
        "max_c3_bits",
    ):
        if not 0 < _finite(negative[key], f"l2_negative_control.{key}") <= 1e-9:
            raise CalibrationError(f"l2_negative_control.{key} is outside the calibration cap")

    resources = contract["resource_limits"]
    claims = contract["fixed_claims"]
    if resources != {
        "max_logical_state_dimension": 256,
        "max_kernel_dimension": 8,
        "max_triplets_processed": 56,
        "max_table_cells_processed": 448,
    }:
        raise CalibrationError("resource_limits drifted")
    expected_claims = {
        "calibration_only": True,
        "fermionic_non_gaussianity_assessed": False,
        "hoi_application_claim": False,
        "physical_l8_instance_assessed": False,
        "ready_gate_eligible": False,
        "bgl_accessed": False,
        "runtime_authority": False,
        "mainline_parameter_influence": False,
        "portable_receipt_byte_identity": False,
    }
    if claims != expected_claims:
        raise CalibrationError("fixed_claims drifted")


def _matrix(record: Mapping[str, Any], name: str) -> List[List[Fraction]]:
    return [
        [_fraction(item, f"{name}.matrix") for item in row]
        for row in record["matrix"]
    ]


def _determinant_fraction(matrix: Sequence[Sequence[Fraction]]) -> Fraction:
    size = len(matrix)
    if size == 0:
        return Fraction(1)
    if size == 1:
        return matrix[0][0]
    if size == 2:
        return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    if size == 3:
        return (
            matrix[0][0] * matrix[1][1] * matrix[2][2]
            + matrix[0][1] * matrix[1][2] * matrix[2][0]
            + matrix[0][2] * matrix[1][0] * matrix[2][1]
            - matrix[0][2] * matrix[1][1] * matrix[2][0]
            - matrix[0][1] * matrix[1][0] * matrix[2][2]
            - matrix[0][0] * matrix[1][2] * matrix[2][1]
        )
    raise CalibrationError("only determinants through size three are required")


def _principal_fraction(
    matrix: Sequence[Sequence[Fraction]], subset: Sequence[int]
) -> Fraction:
    return _determinant_fraction([[matrix[i][j] for j in subset] for i in subset])


def _characteristic_invariants(
    matrix: Sequence[Sequence[Fraction]], eigenvalues: Sequence[Fraction]
) -> bool:
    trace = sum((matrix[index][index] for index in range(3)), Fraction())
    pair_sum = sum(
        (_principal_fraction(matrix, pair) for pair in itertools.combinations(range(3), 2)),
        Fraction(),
    )
    determinant = _determinant_fraction(matrix)
    expected_pair_sum = sum(
        (left * right for left, right in itertools.combinations(eigenvalues, 2)),
        Fraction(),
    )
    expected_determinant = eigenvalues[0] * eigenvalues[1] * eigenvalues[2]
    return (
        trace == sum(eigenvalues, Fraction())
        and pair_sum == expected_pair_sum
        and determinant == expected_determinant
    )


def _occupation_table_from_kernel(
    matrix: Sequence[Sequence[Fraction]], modes: Sequence[int] = (0, 1, 2)
) -> List[Fraction]:
    table: List[Fraction] = []
    all_modes = set(modes)
    for cell in range(1 << len(modes)):
        occupied = {modes[index] for index in range(len(modes)) if cell & (1 << index)}
        empty = sorted(all_modes - occupied)
        probability = Fraction()
        for extra_size in range(len(empty) + 1):
            for extra in itertools.combinations(empty, extra_size):
                subset = sorted(occupied | set(extra))
                probability += ((-1) ** extra_size) * _principal_fraction(matrix, subset)
        table.append(probability)
    if any(item < 0 for item in table) or sum(table, Fraction()) != 1:
        raise CalibrationError("kernel produced an invalid occupation table")
    return table


def _margins_fraction(table: Sequence[Fraction]) -> Dict[str, Any]:
    singles = [
        sum((table[cell] for cell in range(8) if cell & (1 << index)), Fraction())
        for index in range(3)
    ]
    pairs = {
        f"{left},{right}": sum(
            (
                table[cell]
                for cell in range(8)
                if cell & (1 << left) and cell & (1 << right)
            ),
            Fraction(),
        )
        for left, right in itertools.combinations(range(3), 2)
    }
    return {"singles": singles, "pairs": pairs}


def _margins_float(table: Sequence[float]) -> Tuple[List[float], Dict[str, float]]:
    singles = [sum(table[cell] for cell in range(8) if cell & (1 << index)) for index in range(3)]
    pairs = {
        f"{left},{right}": sum(
            table[cell]
            for cell in range(8)
            if cell & (1 << left) and cell & (1 << right)
        )
        for left, right in itertools.combinations(range(3), 2)
    }
    return singles, pairs


def pairwise_maximum_entropy(table: Sequence[float]) -> List[float]:
    """Return Q2 on the one-dimensional 2x2x2 fixed-pair-margin fibre."""

    if len(table) != 8 or any(not math.isfinite(item) or item < 0 for item in table):
        raise CalibrationError("Q2 input must be eight finite non-negative cells")
    if not math.isclose(sum(table), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise CalibrationError("Q2 input must sum to one")
    lower = max(
        -table[cell] for cell, direction in enumerate(FIBRE_DIRECTION) if direction > 0
    )
    upper = min(
        table[cell] for cell, direction in enumerate(FIBRE_DIRECTION) if direction < 0
    )
    if upper < lower:
        raise CalibrationError("Q2 fibre is empty")
    if upper == lower:
        return list(table)

    # On the open fibre, maximum entropy is the unique root of the absent
    # three-way log-linear interaction.  Bisection is more accurate than
    # comparing nearly equal entropy values close to the optimum.
    left = math.nextafter(lower, upper)
    right = math.nextafter(upper, lower)
    if not left < right:
        # There is no representable floating-point interior.  Select the
        # higher-entropy endpoint without changing any positive probability.
        candidates = []
        for delta in (lower, upper):
            values = [
                table[cell] + delta * FIBRE_DIRECTION[cell] for cell in range(8)
            ]
            entropy = -sum(value * math.log(value) for value in values if value > 0)
            candidates.append((entropy, values))
        return max(candidates, key=lambda item: item[0])[1]

    def score(delta: float) -> float:
        candidate = [
            table[cell] + delta * FIBRE_DIRECTION[cell] for cell in range(8)
        ]
        zero_directions = {
            FIBRE_DIRECTION[cell] for cell in range(8) if candidate[cell] == 0
        }
        if any(value < 0 for value in candidate):
            raise CalibrationError("Q2 score reached a negative cell")
        if zero_directions == {1}:
            return -math.inf
        if zero_directions == {-1}:
            return math.inf
        if zero_directions:
            raise CalibrationError("Q2 score reached both fibre boundaries")
        return sum(
            FIBRE_DIRECTION[cell] * math.log(candidate[cell]) for cell in range(8)
        )

    left_score = score(left)
    right_score = score(right)
    if left_score >= 0:
        delta = lower
    elif right_score <= 0:
        delta = upper
    else:
        for _ in range(192):
            midpoint = (left + right) / 2.0
            if midpoint == left or midpoint == right:
                break
            midpoint_score = score(midpoint)
            if midpoint_score < 0:
                left = midpoint
            else:
                right = midpoint
        delta = (left + right) / 2.0
    result = [table[cell] + delta * FIBRE_DIRECTION[cell] for cell in range(8)]
    if any(item < 0 for item in result):
        raise CalibrationError("Q2 result contains a negative cell")
    if not math.isclose(sum(result), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise CalibrationError("Q2 result does not sum to one")

    before_singles, before_pairs = _margins_float(table)
    after_singles, after_pairs = _margins_float(result)
    residuals = [
        abs(left_value - right_value)
        for left_value, right_value in zip(before_singles, after_singles)
    ] + [
        abs(before_pairs[key] - after_pairs[key]) for key in sorted(before_pairs)
    ]
    if max(residuals, default=0.0) > 1e-12:
        raise CalibrationError("Q2 failed to preserve the declared pairwise margins")
    return result


def c3_bits(table: Sequence[float], q2: Sequence[float]) -> float:
    if len(table) != len(q2):
        raise CalibrationError("C3 inputs must have the same length")
    value = 0.0
    for observed, expected in zip(table, q2):
        if observed < 0 or expected < 0:
            raise CalibrationError("C3 inputs must be non-negative")
        if observed == 0:
            continue
        if expected == 0:
            return math.inf
        value += observed * math.log2(observed / expected)
    return 0.0 if abs(value) < 1e-14 else value


def _load_pilot(expected_sha256: str) -> Any:
    source_bytes = PILOT_PATH.read_bytes()
    actual_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise CalibrationError("the pinned L2 pilot source hash does not match")
    module = types.ModuleType("fb_s0_l2_pilot")
    module.__file__ = str(PILOT_PATH)
    compiled = compile(source_bytes, str(PILOT_PATH), "exec")
    exec(compiled, module.__dict__)
    return module


def _one_body_kernel(state: Sequence[complex], pilot: Any) -> List[List[complex]]:
    modes = 8
    kernel = [[0j for _ in range(modes)] for _ in range(modes)]
    for left in range(modes):
        for right in range(modes):
            if left == right:
                kernel[left][right] = sum(
                    abs(amplitude) ** 2
                    for basis, amplitude in enumerate(state)
                    if basis & (1 << left)
                )
                continue
            value = 0j
            for source, amplitude in enumerate(state):
                if amplitude == 0 or source & (1 << left) or not source & (1 << right):
                    continue
                target = source ^ (1 << left) ^ (1 << right)
                value += (
                    state[target].conjugate()
                    * pilot._hop_sign(source, left, right)
                    * amplitude
                )
            kernel[left][right] = value
    return kernel


def _determinant_complex(matrix: Sequence[Sequence[complex]]) -> complex:
    size = len(matrix)
    if size == 0:
        return 1.0 + 0j
    if size == 1:
        return matrix[0][0]
    if size == 2:
        return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    if size == 3:
        return (
            matrix[0][0] * matrix[1][1] * matrix[2][2]
            + matrix[0][1] * matrix[1][2] * matrix[2][0]
            + matrix[0][2] * matrix[1][0] * matrix[2][1]
            - matrix[0][2] * matrix[1][1] * matrix[2][0]
            - matrix[0][1] * matrix[1][0] * matrix[2][2]
            - matrix[0][0] * matrix[1][2] * matrix[2][1]
        )
    raise CalibrationError("only complex determinants through size three are required")


def _principal_complex(
    matrix: Sequence[Sequence[complex]], subset: Sequence[int]
) -> complex:
    return _determinant_complex([[matrix[i][j] for j in subset] for i in subset])


def _occupation_inclusion(state: Sequence[complex], subset: Sequence[int]) -> float:
    return sum(
        abs(amplitude) ** 2
        for basis, amplitude in enumerate(state)
        if all(basis & (1 << mode) for mode in subset)
    )


def _occupation_table_from_state(
    state: Sequence[complex], triplet: Sequence[int]
) -> List[float]:
    table = [0.0] * 8
    for basis, amplitude in enumerate(state):
        cell = sum(
            ((basis >> mode) & 1) << local_index
            for local_index, mode in enumerate(triplet)
        )
        table[cell] += abs(amplitude) ** 2
    return table


def _projection_residual(kernel: Sequence[Sequence[complex]]) -> float:
    size = len(kernel)
    maximum = 0.0
    for row in range(size):
        for column in range(size):
            squared = sum(kernel[row][inner] * kernel[inner][column] for inner in range(size))
            maximum = max(maximum, abs(squared - kernel[row][column]))
    return maximum


def _l2_negative_control(contract: Mapping[str, Any]) -> Dict[str, Any]:
    negative = contract["l2_negative_control"]
    pilot = _load_pilot(negative["pilot_sha256"])
    state = pilot.trotter_evolution(
        pilot.neel_state(negative["linear_size"]),
        negative["linear_size"],
        negative["u_over_hopping"],
        negative["total_time"],
        negative["trotter_steps"],
    )
    if len(state) > contract["resource_limits"]["max_logical_state_dimension"]:
        raise CalibrationError("the negative-control state exceeds its resource cap")
    norm_residual = abs(pilot._norm(state) - 1.0)
    kernel = _one_body_kernel(state, pilot)
    hermitian_residual = max(
        abs(kernel[row][column] - kernel[column][row].conjugate())
        for row in range(8)
        for column in range(8)
    )
    trace_residual = abs(sum(kernel[index][index].real for index in range(8)) - 4.0)
    projection_residual = _projection_residual(kernel)

    maximum_inclusion_residual = 0.0
    for size in (1, 2, 3):
        for subset in itertools.combinations(range(8), size):
            observed = _occupation_inclusion(state, subset)
            predicted = _principal_complex(kernel, subset)
            maximum_inclusion_residual = max(
                maximum_inclusion_residual,
                abs(observed - predicted.real),
                abs(predicted.imag),
            )

    triplet_rows: List[Dict[str, Any]] = []
    for triplet in itertools.combinations(range(8), 3):
        table = _occupation_table_from_state(state, triplet)
        q2 = pairwise_maximum_entropy(table)
        triplet_rows.append(
            {"triplet": list(triplet), "c3_bits": c3_bits(table, q2)}
        )
    maximum_c3 = max((row["c3_bits"] for row in triplet_rows), default=0.0)
    positive_triplets = sum(row["c3_bits"] > negative["max_c3_bits"] for row in triplet_rows)
    checks = {
        "norm_within_tolerance": norm_residual <= 1e-12,
        "kernel_hermitian": hermitian_residual <= 1e-12,
        "particle_trace_is_four": trace_residual <= 1e-12,
        "kernel_is_projection": projection_residual <= negative["max_projection_residual"],
        "wick_determinant_moments_match": (
            maximum_inclusion_residual <= negative["max_inclusion_determinant_residual"]
        ),
        "all_triplets_scanned": len(triplet_rows) == negative["expected_triplets"],
        "no_q2_divergence_in_fixed_fixture": maximum_c3 <= negative["max_c3_bits"],
    }
    if not all(checks.values()):
        raise CalibrationError("the fixed L2 Gaussian negative control failed")
    return {
        "status": "NO_DIVERGENCE_IN_FIXED_L2_FIXTURE",
        "fixture": {
            "linear_size": negative["linear_size"],
            "modes": negative["expected_modes"],
            "particles": negative["expected_particles"],
            "u_over_hopping": negative["u_over_hopping"],
            "total_time": negative["total_time"],
            "trotter_steps": negative["trotter_steps"],
            "pilot_sha256": negative["pilot_sha256"],
            "quadratic_product_preserves_gaussianity": True,
        },
        "checks": checks,
        "norm_residual": norm_residual,
        "kernel_hermitian_residual": hermitian_residual,
        "kernel_trace_residual": trace_residual,
        "kernel_projection_residual": projection_residual,
        "maximum_inclusion_determinant_residual": maximum_inclusion_residual,
        "triplets_scanned": len(triplet_rows),
        "positive_triplets": positive_triplets,
        "maximum_c3_bits": maximum_c3,
    }


def build_calibration(
    contract: Mapping[str, Any], contract_source_bytes: bytes | None = None
) -> Dict[str, Any]:
    _validate_contract(contract)
    checker_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if checker_sha256 != contract["checker_sha256"]:
        raise CalibrationError("the checker source hash does not match the contract")
    if contract_source_bytes is None:
        contract_source_bytes = json.dumps(
            contract, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        contract_hash_basis = "canonical_json_semantics"
    else:
        try:
            bound_contract = json.loads(contract_source_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CalibrationError("contract source bytes are not valid JSON") from exc
        if bound_contract != contract:
            raise CalibrationError("contract object differs from its bound source bytes")
        contract_hash_basis = "source_bytes"
    contract_sha256 = hashlib.sha256(contract_source_bytes).hexdigest()
    analytic_rows: Dict[str, Any] = {}
    common_margins: Dict[str, Any] | None = None
    common_q2: List[float] | None = None
    triple_values: List[Fraction] = []

    for kernel_id, record in contract["analytic_kernels"].items():
        matrix = _matrix(record, kernel_id)
        if matrix != [list(row) for row in zip(*matrix)]:
            raise CalibrationError(f"{kernel_id} kernel must be symmetric")
        eigenvalues = [
            _fraction(item, f"{kernel_id}.expected_eigenvalues")
            for item in record["expected_eigenvalues"]
        ]
        if not _characteristic_invariants(matrix, eigenvalues):
            raise CalibrationError(f"{kernel_id} characteristic invariants do not match")
        table = _occupation_table_from_kernel(matrix)
        margins = _margins_fraction(table)
        expected_singles = [
            _fraction(item, "expected_shared_single_inclusions")
            for item in contract["expected_shared_single_inclusions"]
        ]
        expected_pairs = {
            key: _fraction(item, "expected_shared_pair_inclusions")
            for key, item in contract["expected_shared_pair_inclusions"].items()
        }
        if margins != {"singles": expected_singles, "pairs": expected_pairs}:
            raise CalibrationError(f"{kernel_id} pairwise margins drifted")
        if common_margins is None:
            common_margins = margins
        elif margins != common_margins:
            raise CalibrationError("analytic kernels do not share pairwise margins")
        triple = _principal_fraction(matrix, (0, 1, 2))
        expected_triple = _fraction(record["expected_triple_inclusion"], f"{kernel_id}.triple")
        if triple != expected_triple or table[7] != triple:
            raise CalibrationError(f"{kernel_id} triple inclusion drifted")
        triple_values.append(triple)

        q2 = pairwise_maximum_entropy([float(item) for item in table])
        expected_q2 = [float(_fraction(item, "expected_q2_cells")) for item in contract["expected_q2_cells"]]
        maximum_q2_error = max(abs(left - right) for left, right in zip(q2, expected_q2))
        if maximum_q2_error > 1e-12:
            raise CalibrationError(f"{kernel_id} Q2 differs from the frozen solution")
        if common_q2 is None:
            common_q2 = q2
        elif max(abs(left - right) for left, right in zip(q2, common_q2)) > 1e-12:
            raise CalibrationError("shared pairwise margins did not produce a shared Q2")
        divergence = c3_bits([float(item) for item in table], q2)
        if divergence < contract["minimum_c3_bits"]:
            raise CalibrationError(f"{kernel_id} did not clear the C3 calibration floor")
        analytic_rows[kernel_id] = {
            "valid_gauge_invariant_quasifree_mixed_state_kernel": True,
            "fixed_particle_number_pure_state": False,
            "eigenvalues": [str(item) for item in eigenvalues],
            "one_mode_inclusions": [str(item) for item in margins["singles"]],
            "two_mode_inclusions": {
                key: str(item) for key, item in margins["pairs"].items()
            },
            "three_mode_inclusion": str(triple),
            "occupation_table": [str(item) for item in table],
            "q2_cells": q2,
            "maximum_q2_cell_error": maximum_q2_error,
            "c3_bits": divergence,
        }

    if len(set(triple_values)) != 2:
        raise CalibrationError("analytic kernels must differ in their three-mode inclusion")
    l2_control = _l2_negative_control(contract)
    report = {
        "schema_version": 1,
        "calibration_id": contract["calibration_id"],
        "status": "ANALYTIC_GAUSSIAN_Q2_COUNTEREXAMPLE_VERIFIED",
        "interpretation": {
            "supported": (
                "C3 measures order-3 irreducibility relative to the declared classical "
                "binary pairwise-maximum-entropy family"
            ),
            "refuted": (
                "C3 greater than zero is a sufficient witness of fermionic non-Gaussianity, "
                "beyond-Wick structure, or a three-body Hamiltonian"
            ),
            "converse_not_assessed": "C3 equal to zero does not establish fermionic Gaussianity",
        },
        "analytic_counterexample": {
            "shared_pairwise_margins": True,
            "different_three_mode_inclusions": True,
            "shared_q2": True,
            "kernels": analytic_rows,
        },
        "l2_negative_control": l2_control,
        "logical_resource_counts": {
            "logical_state_dimension": 256,
            "maximum_kernel_dimension": 8,
            "triplets_processed": 56,
            "table_cells_processed": 448,
            "python_peak_rss_measured": False,
            "rng_used": False,
            "external_corpus_data_read": False,
            "local_pinned_source_imported": True,
        },
        "provenance": {
            "checker_sha256": checker_sha256,
            "contract_sha256": contract_sha256,
            "contract_hash_basis": contract_hash_basis,
            "pilot_sha256": contract["l2_negative_control"]["pilot_sha256"],
            "pilot_execution": "compiled_and_executed_from_one_verified_byte_buffer",
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "libc": list(platform.libc_ver()),
        },
        "claims": dict(contract["fixed_claims"]),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    contract_source_bytes = args.contract.read_bytes()
    try:
        contract = json.loads(contract_source_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CalibrationError("contract source bytes are not valid JSON") from exc
    if not isinstance(contract, Mapping):
        raise CalibrationError("contract must be a JSON object")
    report = build_calibration(contract, contract_source_bytes)
    if args.format == "markdown":
        rows = report["analytic_counterexample"]["kernels"]
        print(f"# FB-S0 Gaussian occupation calibration: {report['status']}\n")
        for kernel_id, row in rows.items():
            print(f"- `{kernel_id}`: C3 = `{row['c3_bits']:.12g}` bits")
        print(
            "- fixed L=2 control maximum C3: "
            f"`{report['l2_negative_control']['maximum_c3_bits']:.12g}` bits"
        )
        print("\nThis is calibration only and does not assess fermionic non-Gaussianity.")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
