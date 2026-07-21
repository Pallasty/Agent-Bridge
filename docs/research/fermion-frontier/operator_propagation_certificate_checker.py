#!/usr/bin/env python3
"""Fail-closed checker for an abstract Pauli circuit-truncation certificate.

This kernel proves only interval propagation through the *declared* Pauli
rotation sequence, its dropped-L1 ledger, and evaluation on a contract-pinned
computational-basis bitstring.  It deliberately does not prove a
product-formula bound to exact Hamiltonian evolution, a fermion-to-qubit
mapping, the physical L=8 instance identity, or any READY condition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


CERTIFICATE_TYPE = "abstract_pauli_circuit_truncation_subcertificate_v1"
CONTRACT_FINGERPRINT = "operator_propagation_certificate_contract_v1"
CHECKER_FINGERPRINT = "operator_propagation_certificate_checker_fraction_interval_v1"
CONVENTION = "G_P(theta)=exp(-i*theta*P/2); Heisenberg G_P(theta)^dagger O G_P(theta)"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_CIRCUIT_TRUNCATION_SUBCERTIFICATE"
EXPECTED_N_QUBITS = 2
EXPECTED_GENERATOR_COUNT = 2
EXPECTED_GENERATOR_SEQUENCE_SHA256 = (
    "88673b8e5864d527b2c41b74e081e0560e8e13040153587effd4962251160146"
)
EXPECTED_INITIAL_TERMS_SHA256 = (
    "b8bb280653d2c6128a093a6d236cb28083b5c11b829dd42a96a9ea86181e3d58"
)
EXPECTED_COMPUTATIONAL_BASIS_BITS = "00"
RATIONAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)/[1-9][0-9]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RESOURCE_LIMITS = {
    "max_certificate_bytes": 1_048_576,
    "max_qubits": 16,
    "max_initial_terms": 256,
    "max_slices": 64,
    "max_gates_per_slice": 256,
    "max_live_terms": 65_536,
    "max_taylor_order": 32,
    "max_rational_digits": 128,
}

WORKLOAD_IDENTITY = {
    "workload_fingerprint": "abstract_two_qubit_pauli_conformance_v1",
    "initial_state_fingerprint": "computational_basis_00_v1",
    "evolution_fingerprint": "declared_pauli_rotation_sequence_v1",
    "boundary_condition_fingerprint": "not_applicable_abstract_conformance",
    "hamiltonian_convention_fingerprint": "not_assessed_declared_gate_sequence",
    "reference_target": "supplied_product_formula_gate_sequence",
}
SCOPE_CLAIMS = {
    "declared_pauli_sequence_arithmetic_verified": True,
    "declared_sequence_truncation_l1_verified": True,
    "contract_pinned_computational_basis_evaluation_verified": True,
    "product_formula_to_exact_hamiltonian": "NOT_ASSESSED",
    "fermion_to_qubit_mapping_identity": "NOT_ASSESSED",
    "physical_L8_instance_identity": "NOT_ASSESSED",
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    **SCOPE_CLAIMS,
    "declared_pauli_sequence_arithmetic_verified": False,
    "declared_sequence_truncation_l1_verified": False,
    "contract_pinned_computational_basis_evaluation_verified": False,
}

Interval = Tuple[Fraction, Fraction]
Expansion = Dict[str, Interval]


class SchemaError(ValueError):
    pass


class VerificationError(ValueError):
    pass


def checker_source_sha256() -> str:
    """Hash the exact checker source bytes pinned by the contract."""

    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _exact_keys(value: Any, keys: Iterable[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{name} must be an object")
    expected = set(keys)
    if set(value) != expected:
        raise SchemaError(f"{name} keys must exactly equal {sorted(expected)}")
    return value


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise SchemaError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def parse_fraction(value: Any, name: str = "rational", max_digits: int = 64) -> Fraction:
    """Parse a reduced, canonical ``numerator/positive-denominator`` string."""

    if not isinstance(value, str) or not RATIONAL_RE.fullmatch(value):
        raise SchemaError(f"{name} must be a canonical rational string")
    numerator_text, denominator_text = value.split("/", 1)
    if len(numerator_text.lstrip("-")) > max_digits or len(denominator_text) > max_digits:
        raise SchemaError(f"{name} exceeds rational digit limit")
    result = Fraction(int(numerator_text), int(denominator_text))
    if value != format_fraction(result):
        raise SchemaError(f"{name} must be reduced and canonical")
    return result


def format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def interval_add(left: Interval, right: Interval) -> Interval:
    return left[0] + right[0], left[1] + right[1]


def interval_multiply(left: Interval, right: Interval) -> Interval:
    """Exact four-corner interval multiplication."""

    corners = (
        left[0] * right[0],
        left[0] * right[1],
        left[1] * right[0],
        left[1] * right[1],
    )
    return min(corners), max(corners)


def interval_scale(value: Interval, scale: Fraction) -> Interval:
    return interval_multiply(value, (scale, scale))


def interval_abs_upper(value: Interval) -> Fraction:
    return max(abs(value[0]), abs(value[1]))


def taylor_sin_cos_interval(theta: Fraction, order: int) -> Tuple[Interval, Interval]:
    """Return rigorous rational Taylor enclosures for |theta| <= 1.

    ``order=N`` retains sine through degree ``2N+1`` and cosine through
    degree ``2N``.  The next non-zero Taylor term bounds each remainder on
    [-1, 1].
    """

    if not isinstance(theta, Fraction):
        raise SchemaError("theta must be Fraction")
    if (
        isinstance(order, bool)
        or not isinstance(order, int)
        or not 0 <= order <= RESOURCE_LIMITS["max_taylor_order"]
    ):
        raise SchemaError("Taylor order must be within the hard checker cap")
    if abs(theta) > 1:
        raise SchemaError("|theta| must be <= 1")
    sine = Fraction(0)
    cosine = Fraction(0)
    for k in range(order + 1):
        sine += Fraction((-1) ** k, math.factorial(2 * k + 1)) * theta ** (2 * k + 1)
        cosine += Fraction((-1) ** k, math.factorial(2 * k)) * theta ** (2 * k)
    sine_radius = abs(theta) ** (2 * order + 3) / math.factorial(2 * order + 3)
    cosine_radius = abs(theta) ** (2 * order + 2) / math.factorial(2 * order + 2)
    return (
        (sine - sine_radius, sine + sine_radius),
        (cosine - cosine_radius, cosine + cosine_radius),
    )


_PAULI_PRODUCT = {
    ("I", "I"): (0, "I"), ("I", "X"): (0, "X"),
    ("I", "Y"): (0, "Y"), ("I", "Z"): (0, "Z"),
    ("X", "I"): (0, "X"), ("Y", "I"): (0, "Y"),
    ("Z", "I"): (0, "Z"), ("X", "X"): (0, "I"),
    ("Y", "Y"): (0, "I"), ("Z", "Z"): (0, "I"),
    ("X", "Y"): (1, "Z"), ("Y", "X"): (3, "Z"),
    ("Y", "Z"): (1, "X"), ("Z", "Y"): (3, "X"),
    ("Z", "X"): (1, "Y"), ("X", "Z"): (3, "Y"),
}


def pauli_multiply(left: str, right: str) -> Tuple[int, str]:
    """Return ``(phase_power, string)`` for left*right, phase=i**power."""

    if len(left) != len(right) or not left or set(left + right) - set("IXYZ"):
        raise SchemaError("Pauli strings must be equal-length non-empty IXYZ strings")
    phase = 0
    output: List[str] = []
    for a, b in zip(left, right):
        local_phase, local_output = _PAULI_PRODUCT[(a, b)]
        phase = (phase + local_phase) % 4
        output.append(local_output)
    return phase, "".join(output)


def pauli_commutes(left: str, right: str) -> bool:
    phase_lr, _ = pauli_multiply(left, right)
    phase_rl, _ = pauli_multiply(right, left)
    return phase_lr == phase_rl


def anticommuting_branch(generator: str, operator: str) -> Tuple[int, str]:
    """Return sign/string for i*generator*operator (which is Hermitian)."""

    if pauli_commutes(generator, operator):
        raise SchemaError("anticommuting_branch requires anticommuting strings")
    phase, output = pauli_multiply(generator, operator)
    combined = (phase + 1) % 4
    if combined == 0:
        return 1, output
    if combined == 2:
        return -1, output
    raise VerificationError("i*P*Q was unexpectedly non-Hermitian")


def computational_basis_pauli_expectation(pauli: str, bits: str) -> Fraction:
    """Return the exact expectation on |bits>, with q0 stored first."""

    if (
        not isinstance(bits, str)
        or len(bits) != len(pauli)
        or set(bits) - set("01")
    ):
        raise SchemaError("computational basis bits must match the Pauli width")
    if "X" in pauli or "Y" in pauli:
        return Fraction(0)
    sign = 1
    for operator, bit in zip(pauli, bits):
        if operator == "Z" and bit == "1":
            sign *= -1
    return Fraction(sign)


def _pauli(value: Any, n_qubits: int, name: str) -> str:
    if not isinstance(value, str) or len(value) != n_qubits or set(value) - set("IXYZ"):
        raise SchemaError(f"{name} must be an {n_qubits}-character IXYZ string")
    return value


def _interval_json(value: Interval) -> Dict[str, str]:
    return {"lower": format_fraction(value[0]), "upper": format_fraction(value[1])}


def _parse_interval(value: Any, name: str, digits: int) -> Interval:
    item = _exact_keys(value, ("lower", "upper"), name)
    result = (
        parse_fraction(item["lower"], f"{name}.lower", digits),
        parse_fraction(item["upper"], f"{name}.upper", digits),
    )
    if result[0] > result[1]:
        raise SchemaError(f"{name} lower must not exceed upper")
    return result


def _parse_terms(
    value: Any,
    name: str,
    n_qubits: int,
    digits: int,
    maximum: int,
    *,
    intervals: bool,
    require_sorted_unique: bool,
) -> Expansion:
    if not isinstance(value, list) or len(value) > maximum:
        raise SchemaError(f"{name} must be a list within the term limit")
    result: Expansion = {}
    seen: List[str] = []
    for index, raw in enumerate(value):
        keys = ("pauli", "coefficient_interval") if intervals else ("pauli", "coefficient")
        item = _exact_keys(raw, keys, f"{name}[{index}]")
        pauli = _pauli(item["pauli"], n_qubits, f"{name}[{index}].pauli")
        coefficient = (
            _parse_interval(item["coefficient_interval"], f"{name}[{index}].coefficient_interval", digits)
            if intervals
            else (lambda x: (x, x))(parse_fraction(item["coefficient"], f"{name}[{index}].coefficient", digits))
        )
        if coefficient == (Fraction(0), Fraction(0)):
            raise SchemaError(f"{name}[{index}] coefficient must be nonzero")
        if require_sorted_unique and pauli in result:
            raise SchemaError(f"{name} must contain unique Pauli strings")
        result[pauli] = interval_add(result.get(pauli, (Fraction(0), Fraction(0))), coefficient)
        seen.append(pauli)
    if require_sorted_unique and seen != sorted(seen):
        raise SchemaError(f"{name} must be sorted by Pauli string")
    return {key: val for key, val in result.items() if val != (Fraction(0), Fraction(0))}


def _terms_json(expansion: Expansion) -> List[Dict[str, Any]]:
    return [
        {"pauli": pauli, "coefficient_interval": _interval_json(expansion[pauli])}
        for pauli in sorted(expansion)
    ]


def _strict_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(_strict_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_strict_equal(a, b) for a, b in zip(left, right))
    return left == right


def canonical_generator_sequence_sha256(certificate: Mapping[str, Any]) -> str:
    slices = certificate.get("backprop_slices")
    if not isinstance(slices, list):
        raise SchemaError("certificate.backprop_slices must be a list")
    canonical_slices = []
    for index, raw_slice in enumerate(slices):
        if not isinstance(raw_slice, Mapping) or not isinstance(raw_slice.get("gates"), list):
            raise SchemaError(f"certificate.backprop_slices[{index}] is malformed")
        canonical_slices.append(
            {
                "slice_index": raw_slice.get("slice_index"),
                "gates": [
                    {"pauli": gate.get("pauli"), "theta": gate.get("theta")}
                    for gate in raw_slice["gates"]
                    if isinstance(gate, Mapping)
                ],
            }
        )
        if len(canonical_slices[-1]["gates"]) != len(raw_slice["gates"]):
            raise SchemaError(f"certificate.backprop_slices[{index}].gates is malformed")
    payload = {
        "schema_version": 1,
        "n_qubits": certificate.get("n_qubits"),
        "heisenberg_convention": certificate.get("heisenberg_convention"),
        "backprop_slices": canonical_slices,
    }
    try:
        encoded = json.dumps(
            payload,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("certificate generator sequence cannot be canonicalized") from exc
    return hashlib.sha256(encoded).hexdigest()


def canonical_initial_terms_sha256(certificate: Mapping[str, Any]) -> str:
    """Hash the exact raw observable term list pinned by the contract."""

    terms = certificate.get("initial_terms")
    if not isinstance(terms, list):
        raise SchemaError("certificate.initial_terms must be a list")
    payload = {
        "schema_version": 1,
        "n_qubits": certificate.get("n_qubits"),
        "initial_terms": terms,
    }
    try:
        encoded = json.dumps(
            payload,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("certificate.initial_terms cannot be canonicalized") from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_contract(contract: Any) -> List[str]:
    try:
        item = _exact_keys(
            contract,
            (
                "schema_version", "contract_fingerprint", "certificate_type",
                "checker_fingerprint", "checker_source_sha256", "workload_identity", "n_qubits",
                "expected_generator_count", "expected_generator_sequence_sha256",
                "expected_initial_terms_sha256", "expected_computational_basis_bits",
                "heisenberg_convention", "rational_encoding", "taylor_policy",
                "merge_drop_policy", "sequence_order_semantics", "resource_limits", "maximum_positive_status",
                "scope_claims",
            ),
            "contract",
        )
        if item["schema_version"] != 1 or isinstance(item["schema_version"], bool):
            raise SchemaError("contract.schema_version must be integer 1")
        expected_scalars = {
            "contract_fingerprint": CONTRACT_FINGERPRINT,
            "certificate_type": CERTIFICATE_TYPE,
            "checker_fingerprint": CHECKER_FINGERPRINT,
            "heisenberg_convention": CONVENTION,
            "rational_encoding": "reduced_numerator_slash_positive_denominator",
            "taylor_policy": "sin_through_2Nplus1_cos_through_2N_next_term_interval_abs_theta_le_1",
            "merge_drop_policy": "provided_backprop_order_all_slice_gates_then_merge_then_explicit_drop_upper_abs_l1",
            "sequence_order_semantics": "apply_backprop_slices_and_gates_left_to_right_to_observable; producer_must_reverse_forward_circuit",
            "maximum_positive_status": MAXIMUM_POSITIVE_STATUS,
        }
        for field, expected in expected_scalars.items():
            if item[field] != expected:
                raise SchemaError(f"contract.{field} does not match checker policy")
        if (
            not isinstance(item["checker_source_sha256"], str)
            or not SHA256_RE.fullmatch(item["checker_source_sha256"])
            or item["checker_source_sha256"] != checker_source_sha256()
        ):
            raise SchemaError("contract.checker_source_sha256 does not pin this checker")
        if not _strict_equal(item["workload_identity"], WORKLOAD_IDENTITY):
            raise SchemaError("contract.workload_identity does not match fixed workload metadata")
        if not _strict_equal(item["scope_claims"], SCOPE_CLAIMS):
            raise SchemaError("contract.scope_claims does not match fail-closed scope")
        limits = _exact_keys(
            item["resource_limits"],
            ("max_certificate_bytes", "max_qubits", "max_initial_terms", "max_slices", "max_gates_per_slice", "max_live_terms", "max_taylor_order", "max_rational_digits"),
            "contract.resource_limits",
        )
        if not _strict_equal(limits, RESOURCE_LIMITS):
            raise SchemaError("contract.resource_limits does not match hard checker caps")
        n_qubits = _integer(item["n_qubits"], "contract.n_qubits", 1, limits["max_qubits"])
        if n_qubits != EXPECTED_N_QUBITS:
            raise SchemaError("contract.n_qubits does not match the fixed conformance profile")
        generator_count = _integer(
            item["expected_generator_count"],
            "contract.expected_generator_count",
            1,
            limits["max_slices"] * limits["max_gates_per_slice"],
        )
        if generator_count != EXPECTED_GENERATOR_COUNT:
            raise SchemaError("contract.expected_generator_count does not match the fixed profile")
        if item["expected_generator_sequence_sha256"] != EXPECTED_GENERATOR_SEQUENCE_SHA256:
            raise SchemaError("contract generator-sequence pin does not match the fixed profile")
        if item["expected_initial_terms_sha256"] != EXPECTED_INITIAL_TERMS_SHA256:
            raise SchemaError("contract initial-terms pin does not match the fixed profile")
        basis_bits = item["expected_computational_basis_bits"]
        if (
            not isinstance(basis_bits, str)
            or len(basis_bits) != item["n_qubits"]
            or set(basis_bits) - set("01")
        ):
            raise SchemaError(
                "contract.expected_computational_basis_bits must be an n-qubit 01 string"
            )
        if basis_bits != EXPECTED_COMPUTATIONAL_BASIS_BITS:
            raise SchemaError("contract basis bits do not match the fixed conformance profile")
    except (SchemaError, KeyError, TypeError, RecursionError) as exc:
        return [str(exc)]
    return []


def _propagate_gate(expansion: Expansion, generator: str, sine: Interval, cosine: Interval, live_limit: int) -> Expansion:
    if len(expansion) * 2 > live_limit * 2:
        raise SchemaError("live-term resource cap exceeded")
    output: Expansion = {}
    zero = (Fraction(0), Fraction(0))
    for operator, coefficient in expansion.items():
        if pauli_commutes(generator, operator):
            output[operator] = interval_add(output.get(operator, zero), coefficient)
        else:
            sign, branch = anticommuting_branch(generator, operator)
            cos_coefficient = interval_multiply(coefficient, cosine)
            sin_coefficient = interval_scale(interval_multiply(coefficient, sine), Fraction(sign))
            output[operator] = interval_add(output.get(operator, zero), cos_coefficient)
            output[branch] = interval_add(output.get(branch, zero), sin_coefficient)
    output = {key: value for key, value in output.items() if value != zero}
    if len(output) > live_limit:
        raise SchemaError("live-term resource cap exceeded")
    return output


def verify_certificate(contract: Any, certificate: Any) -> Dict[str, Any]:
    """Validate and independently recompute a circuit-truncation subcertificate."""

    base = {
        "status": "INVALID_SCHEMA",
        "verified": False,
        "ready_gate_eligible": False,
        "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
        "errors": [],
    }
    contract_errors = validate_contract(contract)
    if contract_errors:
        base["errors"] = contract_errors
        return base
    try:
        cert = _exact_keys(
            certificate,
            (
                "schema_version", "certificate_type", "contract_fingerprint",
                "workload_identity", "n_qubits", "heisenberg_convention",
                "generator_sequence_sha256", "initial_terms", "initial_merged_terms",
                "initial_terms_sha256", "backprop_slices", "computational_basis_bits",
                "claimed_final_retained_terms", "claimed_cumulative_dropped_l1",
                "claimed_final_retained_expectation_interval", "scope_claims",
            ),
            "certificate",
        )
        if cert["schema_version"] != 1 or isinstance(cert["schema_version"], bool):
            raise SchemaError("certificate.schema_version must be integer 1")
        for field, expected in (
            ("certificate_type", CERTIFICATE_TYPE),
            ("contract_fingerprint", CONTRACT_FINGERPRINT),
            ("workload_identity", contract["workload_identity"]),
            ("n_qubits", contract["n_qubits"]),
            ("heisenberg_convention", CONVENTION),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(cert[field], expected):
                raise SchemaError(f"certificate.{field} does not match contract")
        limits = contract["resource_limits"]
        digits = limits["max_rational_digits"]
        n_qubits = contract["n_qubits"]
        if not isinstance(cert["generator_sequence_sha256"], str) or not SHA256_RE.fullmatch(cert["generator_sequence_sha256"]):
            raise SchemaError("certificate.generator_sequence_sha256 must be lowercase sha256")
        recomputed_hash = canonical_generator_sequence_sha256(cert)
        if cert["generator_sequence_sha256"] != recomputed_hash:
            raise VerificationError("declared generator sequence hash does not match certificate sequence")
        if recomputed_hash != contract["expected_generator_sequence_sha256"]:
            raise VerificationError("generator sequence hash does not match contract pin")

        if not isinstance(cert["initial_terms_sha256"], str) or not SHA256_RE.fullmatch(
            cert["initial_terms_sha256"]
        ):
            raise SchemaError("certificate.initial_terms_sha256 must be lowercase sha256")
        initial_terms_hash = canonical_initial_terms_sha256(cert)
        if cert["initial_terms_sha256"] != initial_terms_hash:
            raise VerificationError("declared initial-terms hash does not match certificate")
        if initial_terms_hash != contract["expected_initial_terms_sha256"]:
            raise VerificationError("initial-terms hash does not match contract pin")
        if cert["computational_basis_bits"] != contract["expected_computational_basis_bits"]:
            raise VerificationError("computational-basis bitstring does not match contract pin")

        expansion = _parse_terms(cert["initial_terms"], "certificate.initial_terms", n_qubits, digits, limits["max_initial_terms"], intervals=False, require_sorted_unique=False)
        claimed_initial = _parse_terms(cert["initial_merged_terms"], "certificate.initial_merged_terms", n_qubits, digits, limits["max_live_terms"], intervals=True, require_sorted_unique=True)
        if expansion != claimed_initial:
            raise VerificationError("initial_merged_terms does not match deduplicated initial_terms")

        slices = cert["backprop_slices"]
        if not isinstance(slices, list) or not 1 <= len(slices) <= limits["max_slices"]:
            raise SchemaError("certificate.backprop_slices must be a non-empty list within cap")
        if [item.get("slice_index") if isinstance(item, Mapping) else None for item in slices] != list(range(len(slices))):
            raise SchemaError("backprop slice_index values must be contiguous ascending integers")
        generator_count = 0
        cumulative_dropped = Fraction(0)
        for slice_position in range(len(slices)):
            raw_slice = _exact_keys(
                slices[slice_position],
                ("slice_index", "gates", "dropped_strings", "claimed_post_merge_terms", "claimed_dropped_l1_increment", "claimed_cumulative_dropped_l1", "claimed_retained_terms"),
                f"certificate.backprop_slices[{slice_position}]",
            )
            _integer(raw_slice["slice_index"], f"slice[{slice_position}].slice_index", slice_position, slice_position)
            gates = raw_slice["gates"]
            if not isinstance(gates, list) or not 1 <= len(gates) <= limits["max_gates_per_slice"]:
                raise SchemaError(f"slice[{slice_position}].gates must be non-empty within cap")
            generator_count += len(gates)
            for gate_position in range(len(gates)):
                gate = _exact_keys(gates[gate_position], ("pauli", "theta", "taylor_order"), f"slice[{slice_position}].gates[{gate_position}]")
                generator = _pauli(gate["pauli"], n_qubits, f"slice[{slice_position}].gates[{gate_position}].pauli")
                theta = parse_fraction(gate["theta"], f"slice[{slice_position}].gates[{gate_position}].theta", digits)
                if abs(theta) > 1:
                    raise SchemaError("gate |theta| must be <= 1")
                order = _integer(gate["taylor_order"], f"slice[{slice_position}].gates[{gate_position}].taylor_order", 0, limits["max_taylor_order"])
                sine, cosine = taylor_sin_cos_interval(theta, order)
                expansion = _propagate_gate(expansion, generator, sine, cosine, limits["max_live_terms"])

            claimed_post = _parse_terms(raw_slice["claimed_post_merge_terms"], f"slice[{slice_position}].claimed_post_merge_terms", n_qubits, digits, limits["max_live_terms"], intervals=True, require_sorted_unique=True)
            if expansion != claimed_post:
                raise VerificationError(f"slice {slice_position} post-merge expansion mismatch")
            dropped = raw_slice["dropped_strings"]
            if not isinstance(dropped, list) or any(not isinstance(x, str) for x in dropped) or dropped != sorted(set(dropped)):
                raise SchemaError(f"slice[{slice_position}].dropped_strings must be sorted unique strings")
            for index, pauli in enumerate(dropped):
                _pauli(pauli, n_qubits, f"slice[{slice_position}].dropped_strings[{index}]")
                if pauli not in expansion:
                    raise VerificationError(f"slice {slice_position} drops absent/zero string {pauli}")
            increment = sum((interval_abs_upper(expansion[pauli]) for pauli in dropped), Fraction(0))
            cumulative_dropped += increment
            claimed_increment = parse_fraction(raw_slice["claimed_dropped_l1_increment"], f"slice[{slice_position}].claimed_dropped_l1_increment", digits)
            claimed_cumulative = parse_fraction(raw_slice["claimed_cumulative_dropped_l1"], f"slice[{slice_position}].claimed_cumulative_dropped_l1", digits)
            if claimed_increment != increment or claimed_cumulative != cumulative_dropped:
                raise VerificationError(f"slice {slice_position} dropped-L1 ledger mismatch")
            for pauli in dropped:
                del expansion[pauli]
            claimed_retained = _parse_terms(raw_slice["claimed_retained_terms"], f"slice[{slice_position}].claimed_retained_terms", n_qubits, digits, limits["max_live_terms"], intervals=True, require_sorted_unique=True)
            if expansion != claimed_retained:
                raise VerificationError(f"slice {slice_position} retained expansion mismatch")

        if generator_count != contract["expected_generator_count"]:
            raise VerificationError("generator count does not match contract pin")
        final_claim = _parse_terms(cert["claimed_final_retained_terms"], "certificate.claimed_final_retained_terms", n_qubits, digits, limits["max_live_terms"], intervals=True, require_sorted_unique=True)
        if expansion != final_claim:
            raise VerificationError("final retained expansion mismatch")
        claimed_dropped = parse_fraction(cert["claimed_cumulative_dropped_l1"], "certificate.claimed_cumulative_dropped_l1", digits)
        if claimed_dropped != cumulative_dropped:
            raise VerificationError("final cumulative dropped-L1 mismatch")

        retained_interval = (Fraction(0), Fraction(0))
        basis_bits = cert["computational_basis_bits"]
        for pauli in sorted(expansion):
            expectation = computational_basis_pauli_expectation(pauli, basis_bits)
            retained_interval = interval_add(
                retained_interval,
                interval_scale(expansion[pauli], expectation),
            )
        claimed_expectation = _parse_interval(cert["claimed_final_retained_expectation_interval"], "certificate.claimed_final_retained_expectation_interval", digits)
        if retained_interval != claimed_expectation:
            raise VerificationError("final retained expectation interval mismatch")
    except (SchemaError, RecursionError) as exc:
        base["errors"] = [str(exc)]
        return base
    except (VerificationError, KeyError, TypeError) as exc:
        base["status"] = "VERIFICATION_FAILED"
        base["errors"] = [str(exc)]
        return base

    base.update(
        {
            "status": MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "scope_claims": dict(SCOPE_CLAIMS),
            "checker_source_sha256_verified": True,
            "generator_sequence_sha256_verified": True,
            "initial_terms_sha256_verified": True,
            "computational_basis_bits_verified": True,
            "recomputed_cumulative_dropped_l1": format_fraction(cumulative_dropped),
            "recomputed_final_retained_expectation_interval": _interval_json(retained_interval),
            "recomputed_declared_circuit_expectation_interval": _interval_json(
                (
                    retained_interval[0] - cumulative_dropped,
                    retained_interval[1] + cumulative_dropped,
                )
            ),
            "retained_expectation_interval_width": format_fraction(retained_interval[1] - retained_interval[0]),
            "truncation_error_budget_adequacy": "NOT_ASSESSED",
            "limitations": [
                "Only the contract-pinned declared Pauli sequence is propagated.",
                "No truncation tolerance or error-budget acceptance is assessed.",
                "The declared-circuit expectation interval is retained interval plus/minus cumulative dropped L1.",
                "Fermion-to-qubit mapping and physical L=8 identity are not assessed.",
                "Product-formula error relative to exact Hamiltonian evolution is not assessed.",
                "This subcertificate is never eligible for a reference or benchmark READY gate.",
            ],
            "errors": [],
        }
    )
    return base


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_strict_json(path: Path, maximum_bytes: int = 1_048_576) -> Any:
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or not 1 <= maximum_bytes <= RESOURCE_LIMITS["max_certificate_bytes"]
    ):
        raise ValueError("JSON byte cap is invalid")
    with path.open("rb") as handle:
        payload = handle.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise ValueError("JSON file exceeds byte cap")
    return json.loads(
        payload.decode("utf-8", errors="strict"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON constant: {value}")),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("certificate", type=Path)
    args = parser.parse_args(argv)
    try:
        contract = load_strict_json(args.contract)
        maximum = contract.get("resource_limits", {}).get("max_certificate_bytes", 1_048_576) if isinstance(contract, Mapping) else 1_048_576
        if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 1_048_576:
            maximum = 1_048_576
        certificate = load_strict_json(args.certificate, maximum)
        result = verify_certificate(contract, certificate)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        result = {"status": "INVALID_SCHEMA", "verified": False, "ready_gate_eligible": False, "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS), "errors": [str(exc)]}
    print(json.dumps(result, allow_nan=False, indent=2, sort_keys=True))
    # A verified arithmetic subcertificate is deliberately not reference
    # qualification.  Exit zero is reserved for a future full machine-checked
    # reference state that also closes mapping and product-formula error.
    return 1


if __name__ == "__main__":
    sys.exit(main())
