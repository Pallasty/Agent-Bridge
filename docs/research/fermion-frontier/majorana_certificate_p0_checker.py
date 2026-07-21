#!/usr/bin/env python3
"""Independent verifier and isolated replay harness for the Majorana P0 certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
from fractions import Fraction
from typing import Any, Iterable, Mapping, Sequence


BASE = Path(__file__).resolve().parent
FIXTURE_NAME = "majorana_certificate_p0_fixture.json"
POLICY_NAME = "majorana_certificate_p0_policy.json"
RUNTIME_LOCK_NAME = "majorana_certificate_p0_runtime_lock.json"
PRECOMMIT_CONTRACT_NAME = "majorana_certificate_p0_precommit_contract.json"
RESULT_CONTRACT_NAME = "majorana_certificate_p0_contract.json"
CERTIFICATE_NAME = "majorana_certificate_p0_certificate.json"
RESULT_TEST_NAME = "test_majorana_certificate_p0_result.py"
PROJECT_DIRECTORY_NAME = "majorana_certificate_p0"
RUNNER_NAME = "majorana_p0_runner.jl"
MAX_JSON_BYTES = 2_000_000
MAX_STDOUT_BYTES = 1_000_000
REPLAY_TIMEOUT_SECONDS = 600
MAXIMUM_STATUS = (
    "VERIFIED_MAJORANA_P0_DETERMINISTIC_INTERVAL_LEDGER_"
    "CONFORMANCE_SUBCERTIFICATE"
)
RESULT_ARTIFACTS = (RESULT_CONTRACT_NAME, CERTIFICATE_NAME, RESULT_TEST_NAME)
CANONICAL_RATIONAL_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class SchemaError(ValueError):
    """Raised when an artifact is malformed or non-canonical."""


class VerificationError(RuntimeError):
    """Raised when well-formed evidence does not satisfy the fixed contract."""


def canonical_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SchemaError(f"value is not canonical JSON: {exc}") from exc
    return text.encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SchemaError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_int(text: str) -> int:
    if text == "-0":
        raise SchemaError("negative-zero JSON integer is forbidden")
    value = int(text)
    if value.bit_length() > 4096:
        raise SchemaError("JSON integer exceeds the 4096-bit input limit")
    return value


def _reject_float(text: str) -> Any:
    raise SchemaError(f"JSON floating-point token is forbidden: {text}")


def _reject_constant(text: str) -> Any:
    raise SchemaError(f"non-finite JSON constant is forbidden: {text}")


def strict_json_loads(payload: bytes, *, source: str = "JSON input") -> Any:
    if len(payload) > MAX_JSON_BYTES:
        raise SchemaError(f"{source} exceeds the {MAX_JSON_BYTES}-byte cap")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SchemaError(f"{source} is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_int=_parse_int,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except SchemaError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SchemaError(f"invalid {source}: {exc}") from exc


def load_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise SchemaError(f"required regular file is missing: {path}")
    return strict_json_loads(path.read_bytes(), source=str(path))


def require_exact_keys(value: Any, keys: Iterable[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{label} must be an object")
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        raise SchemaError(
            f"{label} keys mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return value


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise SchemaError(f"{label} must be a lowercase SHA-256 digest")
    return value


def parse_q(value: Any, label: str = "rational") -> Fraction:
    if not isinstance(value, str) or CANONICAL_RATIONAL_RE.fullmatch(value) is None:
        raise SchemaError(f"{label} is not a canonical rational string")
    result = Fraction(value)
    if format_q(result) != value:
        raise SchemaError(f"{label} is not reduced canonical rational text")
    return result


def format_q(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


Interval = tuple[Fraction, Fraction]


def interval_json(value: Interval) -> dict[str, str]:
    return {"lower": format_q(value[0]), "upper": format_q(value[1])}


def quantize_outward(value: Interval, denominator_grid: int) -> tuple[Interval, Fraction]:
    lower, upper = value
    if lower > upper or denominator_grid <= 0:
        raise VerificationError("invalid interval quantization input")
    lower_tick = (lower.numerator * denominator_grid) // lower.denominator
    scaled_upper_numerator = upper.numerator * denominator_grid
    upper_tick = -((-scaled_upper_numerator) // upper.denominator)
    rounded = (
        Fraction(lower_tick, denominator_grid),
        Fraction(upper_tick, denominator_grid),
    )
    widening = lower - rounded[0] + rounded[1] - upper
    if widening < 0:
        raise VerificationError("interval quantization rounded inward")
    return rounded, widening


def interval_add(left: Interval, right: Interval) -> Interval:
    return left[0] + right[0], left[1] + right[1]


def interval_multiply(left: Interval, right: Interval) -> Interval:
    corners = (
        left[0] * right[0],
        left[0] * right[1],
        left[1] * right[0],
        left[1] * right[1],
    )
    return min(corners), max(corners)


def interval_scale(value: Interval, scale: Fraction) -> Interval:
    if scale >= 0:
        return value[0] * scale, value[1] * scale
    return value[1] * scale, value[0] * scale


def interval_abs_upper(value: Interval) -> Fraction:
    return max(abs(value[0]), abs(value[1]))


def taylor_sin_cos(
    theta: Fraction, order: int, denominator_grid: int
) -> tuple[Interval, Interval, Fraction]:
    if abs(theta) > 1:
        raise VerificationError("Taylor fixture angle exceeds one")
    sin_point = Fraction(0)
    cos_point = Fraction(0)
    for k in range(order + 1):
        sin_point += Fraction((-1) ** k * theta ** (2 * k + 1), math.factorial(2 * k + 1))
        cos_point += Fraction((-1) ** k * theta ** (2 * k), math.factorial(2 * k))
    sin_remainder = Fraction(abs(theta) ** (2 * order + 3), math.factorial(2 * order + 3))
    cos_remainder = Fraction(abs(theta) ** (2 * order + 2), math.factorial(2 * order + 2))
    sine, sine_widening = quantize_outward(
        (sin_point - sin_remainder, sin_point + sin_remainder), denominator_grid
    )
    cosine, cosine_widening = quantize_outward(
        (cos_point - cos_remainder, cos_point + cos_remainder), denominator_grid
    )
    return sine, cosine, sine_widening + cosine_widening


def omega_l(left: int, right: int, nbits: int) -> int:
    parity = 0
    for i in range(nbits):
        if (left >> i) & 1:
            for j in range(i):
                parity ^= (right >> j) & 1
    return parity


def omega_l_self(value: int) -> int:
    weight = value.bit_count()
    return ((weight * weight - weight) // 2) % 2


def omega(left: int, right: int) -> int:
    return (left.bit_count() * right.bit_count() - (left & right).bit_count()) % 2


def independent_multiply(left: int, right: int, nfermions: int) -> tuple[str, int]:
    result = left ^ right
    crossing = omega(left, right)
    exponent = (
        omega_l_self(left) * omega_l_self(right)
        + crossing * (omega_l_self(left) + omega_l_self(right) + 1)
    )
    sign = -1 if (omega_l(left, right, 2 * nfermions) + exponent) % 2 else 1
    if crossing:
        return ("i" if sign == 1 else "-i"), result
    return ("1" if sign == 1 else "-1"), result


def branch_sign(phase: str) -> int:
    if phase == "i":
        return -1
    if phase == "-i":
        return 1
    raise VerificationError("anticommuting branch has a real phase")


def term_rows(expansion: Mapping[int, Interval]) -> list[dict[str, Any]]:
    return [
        {"mask": mask, "coefficient_interval": interval_json(expansion[mask])}
        for mask in sorted(expansion)
    ]


def terms_sha256(expansion: Mapping[int, Interval]) -> str:
    return canonical_sha256(term_rows(expansion))


def primitive_algebra_oracle(fixture: Mapping[str, Any]) -> dict[str, Any]:
    primitive = fixture["primitive_conformance"]
    nfermions = primitive["n_fermions"]
    minimum = primitive["mask_minimum"]
    maximum = primitive["mask_maximum"]
    rows: list[dict[str, Any]] = []
    for left in range(minimum, maximum + 1):
        for right in range(minimum, maximum + 1):
            phase, result = independent_multiply(left, right, nfermions)
            rows.append(
                {
                    "left": left,
                    "right": right,
                    "result": result,
                    "phase": phase,
                    "commutes": omega(left, right) == 0,
                }
            )
    return {"pair_count": len(rows), "records_sha256": canonical_sha256(rows)}


def primitive_rotations_oracle(fixture: Mapping[str, Any]) -> dict[str, Any]:
    primitive = fixture["primitive_conformance"]
    interval_policy = fixture["interval_policy"]
    nfermions = primitive["n_fermions"]
    minimum = primitive["mask_minimum"]
    maximum = primitive["mask_maximum"]
    order = interval_policy["taylor_order"]
    denominator_grid = int(interval_policy["outward_quantization_denominator"])
    rows: list[dict[str, Any]] = []
    for gate in range(minimum, maximum + 1):
        if gate == 0 or gate.bit_count() % 2:
            continue
        for operator in range(minimum, maximum + 1):
            commutes = omega(gate, operator) == 0
            phase, result = independent_multiply(gate, operator, nfermions)
            for theta_text in primitive["angles_in_order"]:
                theta = parse_q(theta_text, "primitive angle")
                sine, cosine, _ = taylor_sin_cos(theta, order, denominator_grid)
                rows.append(
                    {
                        "gate": gate,
                        "operator": operator,
                        "theta": theta_text,
                        "commutes": commutes,
                        "result": result,
                        "branch_sign": 0 if commutes else branch_sign(phase),
                        "sine": interval_json(sine),
                        "cosine": interval_json(cosine),
                    }
                )
    return {"case_count": len(rows), "records_sha256": canonical_sha256(rows)}


def apply_rotation_oracle(
    expansion: Mapping[int, Interval],
    gate_mask: int,
    theta: Fraction,
    nfermions: int,
    order: int,
    denominator_grid: int,
    rounding: dict[str, Any],
) -> tuple[dict[int, Interval], dict[str, Any]]:
    sine, cosine, widening = taylor_sin_cos(theta, order, denominator_grid)
    rounding["widening"] += widening
    rounding["events"] += 2
    contributions: list[tuple[int, int, int, Interval]] = []
    for source_mask in sorted(expansion):
        coefficient = expansion[source_mask]
        if omega(gate_mask, source_mask) == 0:
            contributions.append((source_mask, source_mask, 0, coefficient))
            continue
        cosine_product, widening = quantize_outward(
            interval_multiply(coefficient, cosine), denominator_grid
        )
        rounding["widening"] += widening
        rounding["events"] += 1
        phase, target_mask = independent_multiply(gate_mask, source_mask, nfermions)
        sine_product, widening = quantize_outward(
            interval_scale(
                interval_multiply(coefficient, sine), Fraction(branch_sign(phase))
            ),
            denominator_grid,
        )
        rounding["widening"] += widening
        rounding["events"] += 1
        contributions.append((source_mask, source_mask, 0, cosine_product))
        contributions.append((target_mask, source_mask, 1, sine_product))
    contributions.sort(key=lambda row: (row[0], row[1], row[2]))
    premerge_rows = [
        {
            "mask": mask,
            "source_mask": source,
            "branch": branch,
            "coefficient_interval": interval_json(value),
        }
        for mask, source, branch, value in contributions
    ]
    merged: dict[int, Interval] = {}
    zero_pruned = 0
    index = 0
    while index < len(contributions):
        mask = contributions[index][0]
        accumulator: Interval = (Fraction(0), Fraction(0))
        while index < len(contributions) and contributions[index][0] == mask:
            accumulator = interval_add(accumulator, contributions[index][3])
            index += 1
        accumulator, widening = quantize_outward(accumulator, denominator_grid)
        rounding["widening"] += widening
        rounding["events"] += 1
        if accumulator == (Fraction(0), Fraction(0)):
            zero_pruned += 1
        else:
            merged[mask] = accumulator
    return merged, {
        "gate_mask": gate_mask,
        "theta": format_q(theta),
        "input_term_count": len(expansion),
        "premerge_term_count": len(contributions),
        "postmerge_term_count": len(merged),
        "exact_zero_pruned_count": zero_pruned,
        "premerge_sha256": canonical_sha256(premerge_rows),
        "postmerge_sha256": terms_sha256(merged),
    }


def drop_threshold_oracle(
    expansion: Mapping[int, Interval],
    epsilon: Fraction,
    cumulative_before: Fraction,
    occurrence_index: int,
    schrodinger_index: int,
    symbol: str,
    boundary_kind: str,
    constituent_index: int | None,
) -> tuple[dict[int, Interval], dict[str, Any], Fraction]:
    dropped_masks = [
        mask
        for mask in sorted(expansion)
        if interval_abs_upper(expansion[mask]) < epsilon
    ]
    dropped_rows = [
        {
            "mask": mask,
            "coefficient_interval": interval_json(expansion[mask]),
            "abs_upper": format_q(interval_abs_upper(expansion[mask])),
            "reason": "strict_interval_abs_upper_below_threshold",
        }
        for mask in dropped_masks
    ]
    increment = sum(
        (interval_abs_upper(expansion[mask]) for mask in dropped_masks), Fraction(0)
    )
    dropped_set = set(dropped_masks)
    retained = {
        mask: expansion[mask] for mask in sorted(expansion) if mask not in dropped_set
    }
    return retained, {
        "occurrence_index": occurrence_index,
        "schrodinger_index": schrodinger_index,
        "gate_symbol": symbol,
        "boundary_kind": boundary_kind,
        "constituent_index": constituent_index,
        "postmerge_term_count": len(expansion),
        "retained_term_count": len(retained),
        "dropped_term_count": len(dropped_masks),
        "postmerge_sha256": terms_sha256(expansion),
        "dropped_terms": dropped_rows,
        "dropped_terms_sha256": canonical_sha256(dropped_rows),
        "retained_sha256": terms_sha256(retained),
        "dropped_l1_increment": format_q(increment),
        "cumulative_dropped_l1_before": format_q(cumulative_before),
        "cumulative_dropped_l1_after": format_q(cumulative_before + increment),
    }, increment


def fock_expectation(mask: int, occupied_fermions: Sequence[int], nfermions: int) -> int:
    for fermion in range(1, nfermions + 1):
        first_bit = (mask >> (2 * fermion - 2)) & 1
        second_bit = (mask >> (2 * fermion - 1)) & 1
        if first_bit != second_bit:
            return 0
    occupied_mask = 0
    for fermion in occupied_fermions:
        occupied_mask |= 1 << (2 * fermion - 2)
    exponent = (omega_l_self(mask) + mask.bit_count() // 2) % 4
    if exponent not in (0, 2):
        raise VerificationError("independent Fock oracle produced a non-real phase")
    phase = 1 if exponent == 0 else -1
    return phase * (-1 if (mask & occupied_mask).bit_count() % 2 else 1)


def expansion_expectation(
    expansion: Mapping[int, Interval],
    occupied_fermions: Sequence[int],
    nfermions: int,
    denominator_grid: int,
) -> Interval:
    result: Interval = (Fraction(0), Fraction(0))
    for mask in sorted(expansion):
        expectation = fock_expectation(mask, occupied_fermions, nfermions)
        if expectation:
            result = interval_add(
                result, interval_scale(expansion[mask], Fraction(expectation))
            )
    return quantize_outward(result, denominator_grid)[0]


def _fixed_constituents(symbol: str, sites: Sequence[int]) -> tuple[list[tuple[int, Fraction]], bool]:
    key = (symbol, tuple(sites))
    fixtures: dict[tuple[str, tuple[int, ...]], tuple[list[tuple[int, Fraction]], bool]] = {
        ("hopup", (1, 2)): ([(18, Fraction(-1, 2)), (33, Fraction(1, 2))], False),
        ("hopdn", (1, 2)): ([(72, Fraction(-1, 2)), (132, Fraction(1, 2))], False),
        ("nupndn", (2,)): (
            [(48, Fraction(1, 4)), (192, Fraction(1, 4)), (240, Fraction(-1, 4))],
            True,
        ),
    }
    try:
        return fixtures[key]
    except KeyError as exc:
        raise SchemaError(f"composite fixture is outside the fixed P0 oracle: {key}") from exc


def composite_oracle(fixture: Mapping[str, Any]) -> dict[str, Any]:
    composite = fixture["composite_conformance"]
    interval_policy = fixture["interval_policy"]
    nsites = composite["n_sites"]
    nfermions = 2 * nsites
    order = interval_policy["taylor_order"]
    denominator_grid = int(interval_policy["outward_quantization_denominator"])
    epsilon = parse_q(interval_policy["threshold_epsilon"], "threshold epsilon")
    observable = composite["observable"]
    if observable != {"symbol": "nupndn", "sites": [1]}:
        raise SchemaError("P0 oracle accepts only the frozen nupndn site-1 observable")
    expansion: dict[int, Interval] = {
        0: (Fraction(1, 4), Fraction(1, 4)),
        3: (Fraction(1, 4), Fraction(1, 4)),
        12: (Fraction(1, 4), Fraction(1, 4)),
        15: (Fraction(-1, 4), Fraction(-1, 4)),
    }
    initial_rows = term_rows(expansion)
    schrodinger = [
        {
            "schrodinger_index": index,
            "symbol": gate["symbol"],
            "sites": gate["sites"],
            "theta": gate["theta"],
        }
        for index, gate in enumerate(composite["schrodinger_gates_in_order"], 1)
    ]
    occurrence_rows: list[dict[str, Any]] = []
    stage_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    cumulative_dropped = Fraction(0)
    rounding: dict[str, Any] = {"widening": Fraction(0), "events": 0}
    reversed_gates = list(enumerate(composite["schrodinger_gates_in_order"], 1))[::-1]
    for occurrence_index, (schrodinger_index, gate) in enumerate(reversed_gates, 1):
        symbol = gate["symbol"]
        sites = gate["sites"]
        theta = parse_q(gate["theta"], "composite theta")
        constituents, truncate_after_each = _fixed_constituents(symbol, sites)
        constituents = sorted(constituents)
        constituent_rows = [
            {"mask": mask, "coefficient": format_q(coefficient)}
            for mask, coefficient in constituents
        ]
        occurrence_rows.append(
            {
                "occurrence_index": occurrence_index,
                "schrodinger_index": schrodinger_index,
                "symbol": symbol,
                "sites": sites,
                "theta": format_q(theta),
                "truncate_after_each_constituent": truncate_after_each,
                "constituents": constituent_rows,
                "constituents_sha256": canonical_sha256(constituent_rows),
            }
        )
        stage_input_sha256 = terms_sha256(expansion)
        merge_rows: list[dict[str, Any]] = []
        stage_drop_start = cumulative_dropped
        for constituent_index, (gate_mask, coefficient) in enumerate(constituents, 1):
            expansion, merge_row = apply_rotation_oracle(
                expansion,
                gate_mask,
                theta * coefficient * 2,
                nfermions,
                order,
                denominator_grid,
                rounding,
            )
            merge_rows.append(merge_row)
            if truncate_after_each:
                expansion, ledger_row, increment = drop_threshold_oracle(
                    expansion,
                    epsilon,
                    cumulative_dropped,
                    occurrence_index,
                    schrodinger_index,
                    symbol,
                    "after_constituent",
                    constituent_index,
                )
                cumulative_dropped += increment
                ledger_rows.append(ledger_row)
        if not truncate_after_each:
            expansion, ledger_row, increment = drop_threshold_oracle(
                expansion,
                epsilon,
                cumulative_dropped,
                occurrence_index,
                schrodinger_index,
                symbol,
                "after_complete_composite",
                None,
            )
            cumulative_dropped += increment
            ledger_rows.append(ledger_row)
        stage_rows.append(
            {
                "occurrence_index": occurrence_index,
                "schrodinger_index": schrodinger_index,
                "gate_symbol": symbol,
                "input_sha256": stage_input_sha256,
                "merge_steps": merge_rows,
                "ledger_event_count": len(constituents) if truncate_after_each else 1,
                "dropped_l1_increment": format_q(cumulative_dropped - stage_drop_start),
                "cumulative_dropped_l1": format_q(cumulative_dropped),
                "output_sha256": terms_sha256(expansion),
            }
        )
    fock = composite["fock_state"]
    occupied_fermions = sorted(
        [2 * site - 1 for site in fock["up_occupied_sites"]]
        + [2 * site for site in fock["down_occupied_sites"]]
    )
    retained_expectation = expansion_expectation(
        expansion, occupied_fermions, nfermions, denominator_grid
    )
    declared_expectation, widening = quantize_outward(
        (
            retained_expectation[0] - cumulative_dropped,
            retained_expectation[1] + cumulative_dropped,
        ),
        denominator_grid,
    )
    rounding["widening"] += widening
    rounding["events"] += 1
    return {
        "schrodinger_occurrences": schrodinger,
        "schrodinger_occurrences_sha256": canonical_sha256(schrodinger),
        "heisenberg_occurrences": occurrence_rows,
        "heisenberg_occurrences_sha256": canonical_sha256(occurrence_rows),
        "initial_terms": initial_rows,
        "initial_terms_sha256": canonical_sha256(initial_rows),
        "stages": stage_rows,
        "ledger_events": ledger_rows,
        "ledger_events_sha256": canonical_sha256(ledger_rows),
        "final_retained_terms": term_rows(expansion),
        "final_retained_terms_sha256": terms_sha256(expansion),
        "cumulative_dropped_l1": format_q(cumulative_dropped),
        "retained_expectation_interval": interval_json(retained_expectation),
        "declared_circuit_expectation_interval": interval_json(declared_expectation),
        "rounding_endpoint_widening_diagnostic": format_q(rounding["widening"]),
        "rounding_quantization_event_count": rounding["events"],
        "rounding_accounting": "absorbed_in_coefficient_boxes_not_added_again_as_scalar",
    }


def validate_fixture(fixture: Any) -> Mapping[str, Any]:
    require_exact_keys(
        fixture,
        (
            "schema_version",
            "fixture_id",
            "primitive_conformance",
            "interval_policy",
            "composite_conformance",
            "scope_ceiling",
        ),
        "fixture",
    )
    if fixture["schema_version"] != 1 or fixture["fixture_id"] != "MAJORANA-P0-SMALL-FIXTURE-V1":
        raise SchemaError("unexpected fixture identity")
    expected_primitive = {
        "n_fermions": 3,
        "mask_minimum": 0,
        "mask_maximum": 63,
        "even_nonidentity_gate_masks_only": True,
        "angles_in_order": ["0", "1/8", "-1/8", "1/3", "-1/3", "1/2", "-1/2", "1", "-1"],
    }
    if fixture["primitive_conformance"] != expected_primitive:
        raise SchemaError("primitive fixture differs from the frozen P0 input")
    interval_policy = fixture["interval_policy"]
    for field in ("maximum_absolute_angle", "threshold_epsilon"):
        parse_q(interval_policy[field], field)
    if interval_policy != {
        "coefficient_domain": "real_hermitian_rational_interval_only",
        "taylor_order": 5,
        "maximum_absolute_angle": "1",
        "outward_quantization_denominator": "18446744073709551616",
        "quantization_schedule": "each_rotation_product_then_global_postmerge",
        "rounding_accounting": "absorbed_in_coefficient_boxes_not_added_again_as_scalar",
        "threshold_epsilon": "1/100",
        "threshold_rule": "drop_only_if_interval_abs_upper_is_strictly_less_than_epsilon",
        "equal_or_crossing_threshold_action": "retain",
    }:
        raise SchemaError("interval policy differs from the frozen P0 input")
    if fixture["scope_ceiling"].get("L8_full_propagation") != "NOT_ASSESSED":
        raise SchemaError("fixture exceeds the P0 L8 scope ceiling")
    if fixture["scope_ceiling"].get("physical_reference_qualified") is not False:
        raise SchemaError("fixture improperly claims physical-reference authority")
    if fixture["scope_ceiling"].get("ready_gate_eligible") is not False:
        raise SchemaError("fixture improperly claims READY authority")
    composite_oracle(fixture)
    return fixture


def validate_runtime_lock(runtime_lock: Any) -> Mapping[str, Any]:
    if not isinstance(runtime_lock, dict) or runtime_lock.get("schema_version") != 1:
        raise SchemaError("invalid runtime lock schema")
    if runtime_lock.get("runtime_lock_id") != "MAJORANA-P0-JULIA-1.11.9-LINUX-X86_64-V1":
        raise SchemaError("unexpected runtime lock identity")
    julia = runtime_lock["julia_runtime"]
    if (julia["version"], julia["build_commit_short"], julia["machine"]) != (
        "1.11.9",
        "53a02c0720c",
        "x86_64-linux-gnu",
    ):
        raise VerificationError("runtime identity lock mismatch")
    for item in (julia["official_archive"], julia["executable"], julia["sysimage"]):
        require_sha256(item["sha256"], "runtime lock digest")
        if not isinstance(item["size_bytes"], int) or item["size_bytes"] <= 0:
            raise SchemaError("runtime lock size must be a positive integer")
    environment = runtime_lock["project_environment"]
    for name in ("project", "manifest"):
        require_sha256(environment[name]["sha256"], f"{name} digest")
    packages = runtime_lock["direct_and_semantic_upstream_packages"]
    expected_packages = {
        "MajoranaPropagation": (
            "0.3.0",
            "d62823f20677593ff5e256e5f8bc316dd7aecd7a",
            "744e743d88d7bc62da1ba11cef02909539de626bd4b0a5533b0b65d8aae309b5",
        ),
        "PauliPropagation": (
            "0.7.3",
            "757b43af3c247d9fad953dd056d3df76fe6e6a08",
            "ce1e6cac1b09573962136fce0f315fabbf8556c9075c4aa3545c41c6ee4c3783",
        ),
    }
    for name, (version, tree, closure) in expected_packages.items():
        item = packages[name]
        if item["version"] != version or item["manifest_git_tree_sha1"] != tree:
            raise VerificationError(f"{name} version/tree lock mismatch")
        if item["installed_source_closure"]["closure_sha256"] != closure:
            raise VerificationError(f"{name} installed source closure lock mismatch")
    if runtime_lock["scope_boundary"] != {
        "lock_certifies_runtime_custody_only": True,
        "runtime_lock_is_not_a_conformance_result": True,
        "runtime_lock_is_not_a_physical_reference": True,
        "ready_gate_eligible": False,
    }:
        raise SchemaError("runtime lock scope boundary mismatch")
    return runtime_lock


def validate_project_environment(runtime_lock: Mapping[str, Any], base: Path = BASE) -> None:
    project_path = base / PROJECT_DIRECTORY_NAME / "Project.toml"
    manifest_path = base / PROJECT_DIRECTORY_NAME / "Manifest.toml"
    project_pin = runtime_lock["project_environment"]["project"]
    manifest_pin = runtime_lock["project_environment"]["manifest"]
    for path, pin, label in (
        (project_path, project_pin, "Project.toml"),
        (manifest_path, manifest_pin, "Manifest.toml"),
    ):
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"{label} is not a regular file")
        if path.stat().st_size != pin["size_bytes"] or file_sha256(path) != pin["sha256"]:
            raise VerificationError(f"{label} byte lock mismatch")
    with project_path.open("rb") as handle:
        project = tomllib.load(handle)
    if project.get("deps") != {
        "JSON": "682c06a0-de6a-54ab-a142-c8b1cf79cde6",
        "MajoranaPropagation": "c1ba0b60-2606-4ffc-8aea-7c4a0f2726e4",
        "SHA": "ea8e919c-243c-51af-8825-aaa63cd721ce",
    }:
        raise VerificationError("Project.toml dependency set mismatch")
    if project.get("compat") != {
        "JSON": "=0.21.4",
        "MajoranaPropagation": "=0.3.0",
        "julia": "=1.11.9",
    }:
        raise VerificationError("Project.toml exact compat mismatch")
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    manifest_lock = runtime_lock["project_environment"]["manifest"]
    if str(manifest.get("julia_version")) != manifest_lock["julia_version"]:
        raise VerificationError("Manifest Julia version mismatch")
    if str(manifest.get("manifest_format")) != manifest_lock["manifest_format"]:
        raise VerificationError("Manifest format mismatch")
    if manifest.get("project_hash") != manifest_lock["project_hash"]:
        raise VerificationError("Manifest project hash mismatch")
    for package_name in ("MajoranaPropagation", "PauliPropagation"):
        entries = manifest.get("deps", {}).get(package_name)
        if not isinstance(entries, list) or len(entries) != 1:
            raise VerificationError(f"Manifest {package_name} entry is not unique")
        entry = entries[0]
        lock = runtime_lock["direct_and_semantic_upstream_packages"][package_name]
        if entry.get("version") != lock["version"] or entry.get("git-tree-sha1") != lock["manifest_git_tree_sha1"]:
            raise VerificationError(f"Manifest {package_name} version/tree mismatch")


def validate_policy(policy: Any, runtime_lock: Mapping[str, Any], base: Path = BASE) -> Mapping[str, Any]:
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise SchemaError("invalid policy schema")
    if policy.get("policy_id") != "MAJORANA-P0-S0":
        raise SchemaError("unexpected policy identity")
    authority = policy.get("maximum_positive_authority", {})
    if authority.get("status") != MAXIMUM_STATUS:
        raise VerificationError("policy authority ceiling mismatch")
    boundary = policy.get("precommit_boundary", {})
    required_false = (
        "policy_contains_observed_replay_results",
        "policy_contains_witness_or_result_hashes",
        "policy_promises_a_terminal_branch",
    )
    if any(boundary.get(field) is not False for field in required_false):
        raise VerificationError("policy is not result-unpinned")
    scope = policy.get("scope_boundary", {})
    if scope.get("L8_full_propagation") != "NOT_ASSESSED":
        raise VerificationError("policy exceeds the L8 scope ceiling")
    if scope.get("physical_reference_qualified") is not False or scope.get("ready_gate_eligible") is not False:
        raise VerificationError("policy improperly claims reference or READY authority")
    if tuple(policy.get("precommit_forbidden_paths", ())) != RESULT_ARTIFACTS:
        raise SchemaError("policy result-artifact denylist mismatch")
    pins = policy.get("source_pins")
    if not isinstance(pins, list) or not pins:
        raise SchemaError("policy source pins are missing")
    seen: set[str] = set()
    for pin in pins:
        require_exact_keys(pin, ("relative_path", "role", "size_bytes", "sha256"), "policy source pin")
        relative = pin["relative_path"]
        if not isinstance(relative, str) or relative in seen or relative.startswith("/") or ".." in Path(relative).parts:
            raise SchemaError("invalid or duplicate policy source path")
        seen.add(relative)
        path = base / relative
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"pinned source is not a regular file: {relative}")
        if path.stat().st_size != pin["size_bytes"] or file_sha256(path) != pin["sha256"]:
            raise VerificationError(f"pinned source byte mismatch: {relative}")
    runtime_pin = next((item for item in pins if item["relative_path"] == RUNTIME_LOCK_NAME), None)
    if runtime_pin is None or runtime_pin["sha256"] != file_sha256(base / RUNTIME_LOCK_NAME):
        raise VerificationError("policy does not pin the active runtime lock")
    validate_project_environment(runtime_lock, base)
    return policy


def expected_witness(fixture: Mapping[str, Any], runtime_lock: Mapping[str, Any]) -> dict[str, Any]:
    julia = runtime_lock["julia_runtime"]
    environment = runtime_lock["project_environment"]
    packages = runtime_lock["direct_and_semantic_upstream_packages"]
    return {
        "schema_version": 1,
        "witness_type": "majorana_p0_small_fixture_deterministic_interval_ledger_v1",
        "fixture_id": fixture["fixture_id"],
        "runtime": {
            "julia_version": julia["version"],
            "julia_commit": julia["build_commit_short"],
            "machine": julia["machine"],
            "threads": 1,
            "executable_sha256": julia["executable"]["sha256"],
            "sysimage_sha256": julia["sysimage"]["sha256"],
            "project_sha256": environment["project"]["sha256"],
            "manifest_sha256": environment["manifest"]["sha256"],
        },
        "upstream": {
            "majorana_propagation_version": packages["MajoranaPropagation"]["version"],
            "pauli_propagation_version": packages["PauliPropagation"]["version"],
            "majorana_source_closure": packages["MajoranaPropagation"]["installed_source_closure"],
            "pauli_source_closure": packages["PauliPropagation"]["installed_source_closure"],
        },
        "primitive_algebra": primitive_algebra_oracle(fixture),
        "primitive_rotations": primitive_rotations_oracle(fixture),
        "composite": composite_oracle(fixture),
        "scope": {
            "maximum_positive_status": MAXIMUM_STATUS,
            "small_fixture_conformance_only": True,
            "L8_full_propagation": "NOT_ASSESSED",
            "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
            "physical_reference_qualified": False,
            "ready_gate_eligible": False,
        },
    }


def validate_witness(
    witness: Any, fixture: Mapping[str, Any], runtime_lock: Mapping[str, Any]
) -> dict[str, Any]:
    expected = expected_witness(fixture, runtime_lock)
    if witness != expected:
        expected_digest = canonical_sha256(expected)
        actual_digest = canonical_sha256(witness)
        raise VerificationError(
            "Julia witness differs from the independent oracle: "
            f"expected={expected_digest}, actual={actual_digest}"
        )
    return expected


def validate_precommit_contract(contract: Any, base: Path = BASE) -> Mapping[str, Any]:
    require_exact_keys(
        contract,
        (
            "schema_version",
            "contract_id",
            "contract_role",
            "required_parent_commit",
            "self_relative_path",
            "source_files",
            "result_artifacts_required_absent",
            "formal_replay",
        ),
        "precommit contract",
    )
    if contract["schema_version"] != 1 or contract["contract_id"] != "MAJORANA-P0-PRECOMMIT-S0":
        raise SchemaError("unexpected precommit contract identity")
    if contract["self_relative_path"] != PRECOMMIT_CONTRACT_NAME:
        raise SchemaError("precommit contract self path mismatch")
    if tuple(contract["result_artifacts_required_absent"]) != RESULT_ARTIFACTS:
        raise SchemaError("precommit result denylist mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", contract["required_parent_commit"]):
        raise SchemaError("required parent commit must be a full Git SHA-1")
    replay = contract["formal_replay"]
    if replay != {
        "process_count": 2,
        "fresh_scratch_and_depot_per_process": True,
        "network_namespace_isolated": True,
        "canonical_stdout_must_be_byte_identical": True,
        "independent_python_oracle_required": True,
    }:
        raise SchemaError("formal replay contract mismatch")
    rows = contract["source_files"]
    if not isinstance(rows, list) or not rows:
        raise SchemaError("precommit source file manifest is missing")
    paths: list[str] = []
    for row in rows:
        require_exact_keys(row, ("relative_path", "mode", "size_bytes", "sha256"), "precommit source row")
        relative = row["relative_path"]
        if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
            raise SchemaError("invalid precommit source path")
        if relative in paths:
            raise SchemaError("duplicate precommit source path")
        paths.append(relative)
        if row["mode"] != "100644":
            raise SchemaError("precommit inputs must be non-executable regular files")
        require_sha256(row["sha256"], "precommit source digest")
        path = base / relative
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"precommit source is not a regular file: {relative}")
        if path.stat().st_size != row["size_bytes"] or file_sha256(path) != row["sha256"]:
            raise VerificationError(f"precommit source bytes mismatch: {relative}")
    required_paths = {
        FIXTURE_NAME,
        POLICY_NAME,
        RUNTIME_LOCK_NAME,
        "majorana_certificate_p0/Project.toml",
        "majorana_certificate_p0/Manifest.toml",
        "majorana_certificate_p0/majorana_p0_runner.jl",
        "majorana_certificate_p0_checker.py",
        "test_majorana_certificate_p0.py",
    }
    if set(paths) != required_paths:
        raise SchemaError("precommit source file allowlist mismatch")
    return contract


def verify_precommit(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock, base)
    contract = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
    for artifact in RESULT_ARTIFACTS:
        if (base / artifact).exists():
            raise VerificationError(f"result artifact must be absent before replay: {artifact}")
    expected = expected_witness(fixture, runtime_lock)
    return {
        "status": "VERIFIED_MAJORANA_P0_RESULT_UNPINNED_PRECOMMIT_INPUTS",
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "independent_expected_witness_sha256": canonical_sha256(expected),
        "scope_ceiling": MAXIMUM_STATUS,
        "result_artifacts_absent": list(contract["result_artifacts_required_absent"]),
        "policy_id": policy["policy_id"],
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
        raise VerificationError("checker directory is outside the Git repository") from exc
    return repo, relative


def _verify_generation_git_state(
    precommit_commit: str, contract: Mapping[str, Any], base: Path = BASE
) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9a-f]{40}", precommit_commit):
        raise SchemaError("precommit commit must be a full Git SHA-1")
    repo, base_relative = _repo_and_base_relative(base)
    head = _run_git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    if head != precommit_commit:
        raise VerificationError("fresh replay requires HEAD to equal the precommit commit")
    status_output = _run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout
    if status_output:
        raise VerificationError("fresh replay requires a completely clean worktree and index")
    parent = _run_git(repo, "show", "-s", "--format=%P", precommit_commit).stdout.decode().strip()
    if parent != contract["required_parent_commit"]:
        raise VerificationError("precommit commit does not have the frozen direct parent")
    remote_contains = _run_git(repo, "branch", "-r", "--contains", precommit_commit).stdout.decode()
    if "origin/" not in remote_contains:
        raise VerificationError("precommit commit must be pushed before formal replay")
    return repo, base_relative


def _git_blob(repo: Path, commit: str, repo_relative: str) -> tuple[str, str, bytes]:
    output = _run_git(repo, "ls-tree", "-z", commit, "--", repo_relative).stdout
    records = [record for record in output.split(b"\0") if record]
    if len(records) != 1:
        raise VerificationError(f"Git input path is missing or ambiguous: {repo_relative}")
    try:
        metadata, encoded_path = records[0].split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split(" ")
        decoded_path = encoded_path.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise VerificationError("malformed git ls-tree record") from exc
    if decoded_path != repo_relative or mode != "100644" or object_type != "blob":
        raise VerificationError(f"non-regular or mode-mismatched Git input: {repo_relative}")
    body = _run_git(repo, "cat-file", "blob", object_id).stdout
    return mode, object_id, body


def _git_path_exists(repo: Path, commit: str, repo_relative: str) -> bool:
    result = _run_git(repo, "cat-file", "-e", f"{commit}:{repo_relative}", check=False)
    return result.returncode == 0


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
                raise VerificationError(f"Git blob differs from precommit pin: {relative}")
        elif body != (BASE / PRECOMMIT_CONTRACT_NAME).read_bytes():
            raise VerificationError("Git precommit contract differs from active contract bytes")
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
            raise VerificationError(f"result artifact exists in the precommit commit: {artifact}")
    for directory, _directories, files in os.walk(destination, topdown=False):
        for filename in files:
            path = Path(directory) / filename
            if path.is_symlink() or not path.is_file():
                raise VerificationError("staging tree contains a non-regular file")
    return {
        "files": staged_rows,
        "files_sha256": canonical_sha256(staged_rows),
        "file_count": len(staged_rows),
    }


def _tree_digest(root: Path) -> str:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise VerificationError("staging tree gained a symlink")
        if path.is_dir():
            continue
        if not path.is_file():
            raise VerificationError("staging tree gained a non-regular entry")
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return canonical_sha256(rows)


def source_tree_closure(root: Path) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise VerificationError(f"package root is not a regular directory: {root}")
    rows: list[dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise VerificationError(f"package closure contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise VerificationError(f"package closure contains a non-regular entry: {path}")
        body = path.read_bytes()
        total_bytes += len(body)
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "mode": stat.S_IMODE(path.stat().st_mode),
                "size": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    return {
        "file_count": len(rows),
        "total_bytes": total_bytes,
        "closure_sha256": canonical_sha256(rows),
    }


def _verify_depot_custody(depot: Path, runtime_lock: Mapping[str, Any]) -> dict[str, Any]:
    registry = runtime_lock["registry_snapshot"]
    for field, filename in (("registry_pointer", "General.toml"), ("registry_archive", "General.tar.gz")):
        path = depot / "registries" / filename
        pin = registry[field]
        if not path.is_file() or path.is_symlink():
            raise VerificationError(f"pinned registry file is missing: {filename}")
        if path.stat().st_size != pin["size_bytes"] or file_sha256(path) != pin["sha256"]:
            raise VerificationError(f"pinned registry file mismatch: {filename}")
    closures: dict[str, Any] = {}
    for package_name in ("MajoranaPropagation", "PauliPropagation"):
        package_parent = depot / "packages" / package_name
        candidates = sorted(path for path in package_parent.iterdir() if path.is_dir() and not path.is_symlink())
        expected = runtime_lock["direct_and_semantic_upstream_packages"][package_name]["installed_source_closure"]
        matches: list[tuple[Path, dict[str, Any]]] = []
        for candidate in candidates:
            closure = source_tree_closure(candidate)
            if closure == expected:
                matches.append((candidate, closure))
        if len(matches) != 1:
            raise VerificationError(f"pinned {package_name} source closure is not unique in depot")
        closures[package_name] = {
            "depot_relative_path": matches[0][0].relative_to(depot).as_posix(),
            **matches[0][1],
        }
    return closures


def _verify_julia_runtime(julia_executable: Path, runtime_lock: Mapping[str, Any]) -> None:
    julia_executable = julia_executable.resolve()
    pin = runtime_lock["julia_runtime"]
    if not julia_executable.is_file() or julia_executable.is_symlink():
        raise VerificationError("Julia executable is not a regular resolved file")
    if julia_executable.stat().st_size != pin["executable"]["size_bytes"] or file_sha256(julia_executable) != pin["executable"]["sha256"]:
        raise VerificationError("Julia executable byte lock mismatch")
    sysimage = julia_executable.parent.parent / "lib" / "julia" / "sys.so"
    if not sysimage.is_file() or sysimage.is_symlink():
        raise VerificationError("Julia sysimage is missing")
    if sysimage.stat().st_size != pin["sysimage"]["size_bytes"] or file_sha256(sysimage) != pin["sysimage"]["sha256"]:
        raise VerificationError("Julia sysimage byte lock mismatch")


def _run_one_isolated_replay(
    staging_repo: Path,
    base_relative: Path,
    julia_executable: Path,
    depot: Path,
    run_root: Path,
) -> bytes:
    if shutil.which("bwrap") is None:
        raise VerificationError("bubblewrap is required for network-isolated formal replay")
    scratch = run_root / "scratch"
    depot_prefix = scratch / "depot"
    home = scratch / "home"
    tmp = scratch / "tmp"
    for path in (depot_prefix, home, tmp):
        path.mkdir(parents=True, exist_ok=False)
    staged_base = staging_repo / base_relative
    project = staged_base / PROJECT_DIRECTORY_NAME
    runner = project / RUNNER_NAME
    fixture = staged_base / FIXTURE_NAME
    command = [
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
        str(fixture),
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=REPLAY_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VerificationError("formal replay is INDETERMINATE after timeout") from exc
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[-4000:]
        raise VerificationError(f"isolated Julia replay failed with {result.returncode}: {stderr}")
    if result.stderr:
        raise VerificationError("isolated Julia replay emitted unexpected stderr")
    if len(result.stdout) > MAX_STDOUT_BYTES:
        raise VerificationError("isolated Julia replay exceeded the stdout byte cap")
    return result.stdout


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
    repo, base_relative = _verify_generation_git_state(precommit_commit, contract, base)
    _verify_julia_runtime(julia_executable, runtime_lock)
    depot = depot.resolve()
    custody_before = _verify_depot_custody(depot, runtime_lock)
    with tempfile.TemporaryDirectory(prefix="majorana-p0-formal-") as temporary:
        temporary_path = Path(temporary)
        staging_repo = temporary_path / "staging"
        staging_repo.mkdir()
        staging_manifest = _stage_precommit_tree(
            repo, base_relative, precommit_commit, contract, staging_repo
        )
        staging_before = _tree_digest(staging_repo)
        outputs: list[bytes] = []
        witnesses: list[dict[str, Any]] = []
        for index in range(2):
            run_root = temporary_path / f"run-{index + 1}"
            run_root.mkdir()
            output = _run_one_isolated_replay(
                staging_repo,
                base_relative,
                julia_executable.resolve(),
                depot,
                run_root,
            )
            witness = strict_json_loads(output, source=f"Julia replay {index + 1} stdout")
            canonical_output = canonical_bytes(witness) + b"\n"
            if output != canonical_output:
                raise VerificationError("Julia replay stdout is not exact canonical JSON plus newline")
            validate_witness(witness, fixture, runtime_lock)
            outputs.append(output)
            witnesses.append(witness)
        if outputs[0] != outputs[1]:
            raise VerificationError("two fresh Julia replay stdout byte streams differ")
        if staging_before != _tree_digest(staging_repo):
            raise VerificationError("formal replay modified the Git-object staging tree")
    custody_after = _verify_depot_custody(depot, runtime_lock)
    if custody_before != custody_after:
        raise VerificationError("formal replay modified pinned depot custody inputs")
    if _run_git(repo, "rev-parse", "HEAD").stdout.decode().strip() != precommit_commit:
        raise VerificationError("HEAD changed during formal replay")
    if _run_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout:
        raise VerificationError("worktree or index changed during formal replay")
    transcript_sha = hashlib.sha256(outputs[0]).hexdigest()
    witness_sha = canonical_sha256(witnesses[0])
    return {
        "schema_version": 1,
        "package_type": "majorana_p0_formal_fresh_replay_package_v1",
        "precommit_commit_sha": precommit_commit,
        "precommit_contract_sha256": file_sha256(base / PRECOMMIT_CONTRACT_NAME),
        "staging_manifest": staging_manifest,
        "staging_tree_sha256": staging_before,
        "depot_custody": custody_after,
        "network_isolation": "bubblewrap_unshared_network_namespace",
        "fresh_process_count": 2,
        "stdout_byte_identical": True,
        "transcript_sha256_in_order": [transcript_sha, transcript_sha],
        "canonical_witness_sha256": witness_sha,
        "witness": witnesses[0],
        "status": MAXIMUM_STATUS,
    }


def verify_final(base: Path = BASE) -> dict[str, Any]:
    fixture = validate_fixture(load_json(base / FIXTURE_NAME))
    runtime_lock = validate_runtime_lock(load_json(base / RUNTIME_LOCK_NAME))
    policy = validate_policy(load_json(base / POLICY_NAME), runtime_lock, base)
    precommit = validate_precommit_contract(load_json(base / PRECOMMIT_CONTRACT_NAME), base)
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
            "fresh_process_count",
            "stdout_byte_identical",
            "transcript_sha256_in_order",
            "canonical_witness_sha256",
            "witness",
            "status",
            "scope",
        ),
        "result contract",
    )
    if result["schema_version"] != 1 or result["contract_type"] != "majorana_p0_formal_result_contract_v1":
        raise SchemaError("unexpected result contract identity")
    if result["status"] != MAXIMUM_STATUS or result["fresh_process_count"] != 2:
        raise VerificationError("result status or process count mismatch")
    transcripts = result["transcript_sha256_in_order"]
    if not isinstance(transcripts, list) or len(transcripts) != 2 or transcripts[0] != transcripts[1]:
        raise VerificationError("result transcript equality evidence mismatch")
    for digest in transcripts:
        require_sha256(digest, "transcript digest")
    if result["stdout_byte_identical"] is not True:
        raise VerificationError("result does not attest byte-identical replay")
    validate_witness(result["witness"], fixture, runtime_lock)
    if canonical_sha256(result["witness"]) != result["canonical_witness_sha256"]:
        raise VerificationError("result witness digest mismatch")
    if result["precommit_contract_sha256"] != file_sha256(base / PRECOMMIT_CONTRACT_NAME):
        raise VerificationError("result precommit-contract digest mismatch")
    if result["scope"] != result["witness"]["scope"]:
        raise VerificationError("result scope differs from witness scope")
    require_exact_keys(
        certificate,
        (
            "schema_version",
            "certificate_type",
            "status",
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
        "certificate",
    )
    if certificate["schema_version"] != 1 or certificate["certificate_type"] != "majorana_p0_subcertificate_v1":
        raise SchemaError("unexpected certificate identity")
    if certificate["status"] != MAXIMUM_STATUS or certificate["authority"] != "fixed_small_fixture_subcertificate_only":
        raise VerificationError("certificate authority mismatch")
    if certificate["result_contract_sha256"] != file_sha256(base / RESULT_CONTRACT_NAME):
        raise VerificationError("certificate result-contract digest mismatch")
    if certificate["precommit_commit_sha"] != result["precommit_commit_sha"]:
        raise VerificationError("certificate precommit commit mismatch")
    expected_hashes = {
        "policy_sha256": file_sha256(base / POLICY_NAME),
        "runtime_lock_sha256": file_sha256(base / RUNTIME_LOCK_NAME),
        "fixture_sha256": file_sha256(base / FIXTURE_NAME),
        "runner_sha256": file_sha256(base / PROJECT_DIRECTORY_NAME / RUNNER_NAME),
        "checker_sha256": file_sha256(base / "majorana_certificate_p0_checker.py"),
        "canonical_witness_sha256": result["canonical_witness_sha256"],
    }
    for field, expected in expected_hashes.items():
        if certificate[field] != expected:
            raise VerificationError(f"certificate {field} mismatch")
    if certificate["ready_gate_eligible"] is not False:
        raise VerificationError("certificate improperly claims READY authority")
    if "L8_full_propagation" not in certificate["explicit_exclusions"]:
        raise VerificationError("certificate does not explicitly exclude L8")
    return {
        "status": MAXIMUM_STATUS,
        "precommit_commit_sha": result["precommit_commit_sha"],
        "canonical_witness_sha256": result["canonical_witness_sha256"],
        "result_contract_sha256": file_sha256(base / RESULT_CONTRACT_NAME),
        "certificate_sha256": file_sha256(base / CERTIFICATE_NAME),
        "policy_id": policy["policy_id"],
        "required_parent_commit": precommit["required_parent_commit"],
    }


def _write_canonical_json(path: Path, value: Any) -> None:
    payload = canonical_bytes(value) + b"\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-replay", action="store_true")
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--precommit-commit")
    parser.add_argument("--julia", type=Path)
    parser.add_argument("--depot", type=Path)
    parser.add_argument("--replay-output", type=Path)
    args = parser.parse_args(argv)
    if args.fresh_replay and args.verify_final:
        raise SchemaError("--fresh-replay and --verify-final are mutually exclusive")
    if args.fresh_replay:
        if not all((args.precommit_commit, args.julia, args.depot, args.replay_output)):
            raise SchemaError(
                "fresh replay requires --precommit-commit, --julia, --depot, and --replay-output"
            )
        package = fresh_replay(args.precommit_commit, args.julia, args.depot)
        _write_canonical_json(args.replay_output, package)
        summary = {
            "status": package["status"],
            "precommit_commit_sha": package["precommit_commit_sha"],
            "canonical_witness_sha256": package["canonical_witness_sha256"],
            "transcript_sha256_in_order": package["transcript_sha256_in_order"],
            "replay_package_sha256": file_sha256(args.replay_output),
        }
    elif args.verify_final:
        summary = verify_final()
    else:
        summary = verify_precommit()
    print(canonical_bytes(summary).decode("utf-8"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SchemaError, VerificationError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        raise SystemExit(1)
