#!/usr/bin/env python3
"""Fail-closed checker for fixed L=2/L=3 Hubbard-to-JW mappings.

The checker independently constructs the OBC lattice bonds, the unshifted
``U n_up n_down`` Pauli expansion, and the raw (unfused) Strang term events.
For every spin-resolved hopping bond it also selects eight computational-basis
inputs and compares the fermionic CAR action with the proposed JW Pauli-pair
action exactly over rational Gaussian coefficients.

This is only a canonical mapping subcertificate.  It does not assess a
product-formula error, exact Hamiltonian evolution, L=8, or any READY gate.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


CERTIFICATE_TYPE = "hubbard_jw_mapping_subcertificate_v1"
CONTRACT_FINGERPRINT = "hubbard_jw_mapping_contract_v1"
CHECKER_FINGERPRINT = "hubbard_jw_mapping_validator_exact_car_v1"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE"
GROUP_ORDER = ("H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1")
UNIQUE_GROUP_ORDER = ("H1", "H2", "HU", "H3", "H4")
PROFILE_IDS = ("L2_OBC", "L3_OBC")
LINEAR_SIZES = (2, 3)
U_OVER_T = Fraction(8)
TOTAL_TIME = Fraction(1)
TROTTER_STEPS = 2
MODE_ORDER = "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1"
BOUNDARY = "square_open_boundary_no_wrap"
HAMILTONIAN_CONVENTION = (
    "H=-sum_<ij>,sigma(cdag_i_sigma*c_j_sigma+cdag_j_sigma*c_i_sigma)"
    "+8*sum_i n_i_up*n_i_down_unshifted"
)
JW_CONVENTION = (
    "n_q=(I-Z_q)/2; hopping=-1/2*(X_p Z_(p+1:q) X_q"
    "+Y_p Z_(p+1:q) Y_q),p<q;q0-first"
)
ROTATION_CONVENTION = "G_P(theta)=exp(-i*theta*P/2)"
SIGN_WITNESS_POLICY = (
    "each_spin_resolved_bond: right_even,right_odd,left_even,left_odd,"
    "right_even_external_spectator,left_odd_external_spectator,"
    "empty_endpoints_odd,both_endpoints_odd; first interior mode toggles odd parity;"
    "external spectator is prefix when available and suffix otherwise"
)
RATIONAL_ENCODING = "reduced_numerator_slash_positive_denominator"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RATIONAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)/[1-9][0-9]*$")
RESOURCE_LIMITS = {
    "max_json_bytes": 524_288,
    "max_linear_size": 3,
    "max_qubits": 18,
    "max_spin_resolved_bonds": 24,
    "max_canonical_terms": 84,
    "max_raw_events": 20,
    "max_raw_term_rotations": 336,
    "max_sign_witnesses": 192,
    "max_onsite_basis_witnesses": 36,
}
SOURCE_PINS = (
    {
        "relative_path": "fermi_hubbard_l2_pilot.py",
        "role": "direct_CAR_and_group_partition_conformance_source",
        "sha256": "9474ffb478dd14854e95c36430ecf500b0e44b5b2342b5dfcbe395032bee96c6",
    },
    {
        "relative_path": "term_order_contract.json",
        "role": "raw_Strang_group_order_source",
        "sha256": "fc11e0d626b7e89ea2d00cebb2f64a4f87075d3916c4ad6aaabd69a1f39525ef",
    },
    {
        "relative_path": "operator_propagation_l2_witness.py",
        "role": "L2_R2_nonidentity_gate_sequence_cross_check_source",
        "sha256": "575124ffcb90619b804bd017118b4ed45551b2d56c99b6c056c4d928111e4332",
    },
    {
        "relative_path": "operator_propagation_certificate_checker.py",
        "role": "pinned_dependency_of_L2_gate_sequence_source",
        "sha256": "ade384b1b2258bc5cb3a296d9f7f4c0c85ee374293c2b1a5e4332f4ecba938d4",
    },
)

PROFILE_POLICY = {
    "profile_ids": list(PROFILE_IDS),
    "linear_sizes": list(LINEAR_SIZES),
    "boundary_condition": BOUNDARY,
    "mode_order": MODE_ORDER,
    "hamiltonian_convention": HAMILTONIAN_CONVENTION,
    "jw_convention": JW_CONVENTION,
    "rotation_convention": ROTATION_CONVENTION,
    "u_over_t": "8/1",
    "total_time": "1/1",
    "trotter_steps": TROTTER_STEPS,
    "raw_group_order": list(GROUP_ORDER),
    "raw_events_unfused": True,
    "onsite_identity_retained": True,
    "sign_witness_policy": SIGN_WITNESS_POLICY,
}
SCOPE_CLAIMS = {
    "fixed_L2_L3_OBC_profiles_verified": True,
    "source_pinned_L2_witness_gate_sequence_verified": True,
    "canonical_spin_resolved_bonds_verified": True,
    "canonical_JW_hopping_selected_basis_actions_verified": True,
    "unshifted_onsite_mapping_verified": True,
    "raw_strang_term_expansion_verified": True,
    "product_formula_to_exact_hamiltonian": "NOT_ASSESSED",
    "physical_L8_instance_identity": "NOT_ASSESSED",
    "reference_error_budget": "NOT_ASSESSED",
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    **SCOPE_CLAIMS,
    "fixed_L2_L3_OBC_profiles_verified": False,
    "source_pinned_L2_witness_gate_sequence_verified": False,
    "canonical_spin_resolved_bonds_verified": False,
    "canonical_JW_hopping_selected_basis_actions_verified": False,
    "unshifted_onsite_mapping_verified": False,
    "raw_strang_term_expansion_verified": False,
}

Gaussian = Tuple[Fraction, Fraction]
Action = Dict[int, Gaussian]


class SchemaError(ValueError):
    """Certificate or contract shape/policy error."""


class VerificationError(ValueError):
    """Well-shaped claim that disagrees with independent recomputation."""


def checker_source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def parse_fraction(value: Any, name: str = "rational") -> Fraction:
    if not isinstance(value, str) or not RATIONAL_RE.fullmatch(value):
        raise SchemaError(f"{name} must be a canonical rational string")
    numerator, denominator = value.split("/", 1)
    if len(numerator.lstrip("-")) > 64 or len(denominator) > 64:
        raise SchemaError(f"{name} exceeds rational digit limit")
    result = Fraction(int(numerator), int(denominator))
    if value != format_fraction(result):
        raise SchemaError(f"{name} must be reduced and canonical")
    return result


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise SchemaError(f"{name} must be in [{minimum}, {maximum}]")
    return value


def _exact_keys(value: Any, keys: Iterable[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{name} must be an object")
    expected = set(keys)
    if set(value) != expected:
        raise SchemaError(f"{name} keys must exactly equal {sorted(expected)}")
    return value


def _strict_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _strict_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _strict_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def canonical_sha256(value: Any) -> str:
    try:
        payload = json.dumps(
            value, allow_nan=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("value cannot be canonicalized") from exc
    return hashlib.sha256(payload).hexdigest()


def _pauli_string(n_qubits: int, assignments: Mapping[int, str]) -> str:
    result = ["I"] * n_qubits
    for qubit, operator in assignments.items():
        if (
            isinstance(qubit, bool)
            or not isinstance(qubit, int)
            or not 0 <= qubit < n_qubits
            or operator not in "XYZ"
        ):
            raise SchemaError("invalid Pauli assignment")
        result[qubit] = operator
    return "".join(result)


def _mode(linear_size: int, row: int, column: int, spin: int) -> int:
    return 2 * (row * linear_size + column) + spin


def canonical_bonds(linear_size: int) -> List[Dict[str, Any]]:
    """Generate fixed spin-resolved OBC matchings without trusting claims."""

    linear_size = _integer(
        linear_size, "linear_size", 2, RESOURCE_LIMITS["max_linear_size"]
    )
    bonds: List[Dict[str, Any]] = []
    for group in ("H1", "H2", "H3", "H4"):
        if group in ("H1", "H2"):
            parity = 0 if group == "H1" else 1
            endpoints = (
                ((row, column), (row, column + 1))
                for row in range(linear_size)
                for column in range(parity, linear_size - 1, 2)
            )
            orientation = "horizontal"
        else:
            parity = 1 if group == "H3" else 0
            endpoints = (
                ((row, column), (row + 1, column))
                for row in range(parity, linear_size - 1, 2)
                for column in range(linear_size)
            )
            orientation = "vertical"
        for (row_a, column_a), (row_b, column_b) in endpoints:
            for spin, spin_name in ((0, "up"), (1, "down")):
                left = _mode(linear_size, row_a, column_a, spin)
                right = _mode(linear_size, row_b, column_b, spin)
                if not left < right:
                    raise VerificationError("canonical bond modes must ascend")
                bonds.append(
                    {
                        "bond_id": f"{group}_r{row_a}_c{column_a}_{spin_name}",
                        "group": group,
                        "orientation": orientation,
                        "parity": parity,
                        "spin": spin_name,
                        "left_site": [row_a, column_a],
                        "right_site": [row_b, column_b],
                        "modes": [left, right],
                    }
                )
    if len(bonds) > RESOURCE_LIMITS["max_spin_resolved_bonds"]:
        raise SchemaError("spin-resolved bond cap exceeded")
    return bonds


def _hopping_terms(linear_size: int, bond: Mapping[str, Any]) -> List[Dict[str, Any]]:
    n_qubits = 2 * linear_size * linear_size
    left, right = bond["modes"]
    parity = {qubit: "Z" for qubit in range(left + 1, right)}
    return [
        {
            "term_id": f"{bond['bond_id']}_{axis}{axis}",
            "group": bond["group"],
            "kind": "hopping",
            "bond_id": bond["bond_id"],
            "pauli": _pauli_string(
                n_qubits, {**parity, left: axis, right: axis}
            ),
            "coefficient": "-1/2",
        }
        for axis in ("X", "Y")
    ]


def _onsite_terms(linear_size: int) -> List[Dict[str, Any]]:
    n_qubits = 2 * linear_size * linear_size
    coefficient = U_OVER_T / 4
    output: List[Dict[str, Any]] = []
    for row in range(linear_size):
        for column in range(linear_size):
            site = row * linear_size + column
            up, down = 2 * site, 2 * site + 1
            components = (
                ("I", {}, coefficient),
                ("Zup", {up: "Z"}, -coefficient),
                ("Zdown", {down: "Z"}, -coefficient),
                ("ZZ", {up: "Z", down: "Z"}, coefficient),
            )
            for component, assignments, value in components:
                output.append(
                    {
                        "term_id": f"HU_r{row}_c{column}_{component}",
                        "group": "HU",
                        "kind": "onsite",
                        "site": [row, column],
                        "component": component,
                        "pauli": _pauli_string(n_qubits, assignments),
                        "coefficient": format_fraction(value),
                    }
                )
    return output


def canonical_terms(linear_size: int) -> List[Dict[str, Any]]:
    bonds = canonical_bonds(linear_size)
    terms: List[Dict[str, Any]] = []
    for group in UNIQUE_GROUP_ORDER:
        if group == "HU":
            terms.extend(_onsite_terms(linear_size))
        else:
            for bond in bonds:
                if bond["group"] == group:
                    terms.extend(_hopping_terms(linear_size, bond))
    if len(terms) > RESOURCE_LIMITS["max_canonical_terms"]:
        raise SchemaError("canonical term cap exceeded")
    return terms


def raw_strang_events(linear_size: int) -> List[Dict[str, Any]]:
    """Generate the exact raw, unfused R=2 term-event sequence."""

    terms = canonical_terms(linear_size)
    by_group = {
        group: [term for term in terms if term["group"] == group]
        for group in UNIQUE_GROUP_ORDER
    }
    step_duration = TOTAL_TIME / TROTTER_STEPS
    event_duration = step_duration / 2
    events: List[Dict[str, Any]] = []
    raw_term_index = 0
    for step_index in range(TROTTER_STEPS):
        for event_in_step, group in enumerate(GROUP_ORDER):
            raw_terms = []
            for term_in_event, term in enumerate(by_group[group]):
                coefficient = parse_fraction(term["coefficient"])
                raw_terms.append(
                    {
                        "raw_term_index": raw_term_index,
                        "term_in_event": term_in_event,
                        "term_id": term["term_id"],
                        "pauli": term["pauli"],
                        "hamiltonian_coefficient": term["coefficient"],
                        "rotation_theta": format_fraction(
                            2 * event_duration * coefficient
                        ),
                    }
                )
                raw_term_index += 1
            events.append(
                {
                    "raw_event_index": len(events),
                    "step_index": step_index,
                    "event_in_step": event_in_step,
                    "group": group,
                    "duration": format_fraction(event_duration),
                    "terms": raw_terms,
                }
            )
    if len(events) > RESOURCE_LIMITS["max_raw_events"]:
        raise SchemaError("raw event cap exceeded")
    if raw_term_index > RESOURCE_LIMITS["max_raw_term_rotations"]:
        raise SchemaError("raw term-rotation cap exceeded")
    return events


def canonical_nonidentity_gate_sequence(linear_size: int) -> List[Dict[str, Any]]:
    """Return the raw gates with identity phases removed but explicitly ledgered.

    For L=2 this record shape and order exactly match
    ``operator_propagation_l2_witness.build_forward_gate_sequence()``.  The
    identity rotations remain present in :func:`raw_strang_events`; this view
    exists only for the cross-source circuit comparison.
    """

    gates: List[Dict[str, Any]] = []
    for event in raw_strang_events(linear_size):
        nonidentity = [
            term
            for term in event["terms"]
            if set(term["pauli"]) != {"I"}
        ]
        for gate_in_event, term in enumerate(nonidentity):
            gates.append(
                {
                    "step": event["step_index"],
                    "group": event["group"],
                    "group_event_index": event["raw_event_index"],
                    "gate_in_event": gate_in_event,
                    "pauli": term["pauli"],
                    "theta": term["rotation_theta"],
                }
            )
    return gates


def _bitstring(bits: int, n_qubits: int) -> str:
    return "".join("1" if bits & (1 << qubit) else "0" for qubit in range(n_qubits))


def _gaussian_add(left: Gaussian, right: Gaussian) -> Gaussian:
    return left[0] + right[0], left[1] + right[1]


def _gaussian_scale(value: Gaussian, scale: Fraction) -> Gaussian:
    return value[0] * scale, value[1] * scale


def _clean_action(action: Action) -> Action:
    return {target: value for target, value in action.items() if value != (0, 0)}


def _apply_creation_annihilation(
    source: int, create: int, annihilate: int
) -> Tuple[int, int] | None:
    if not source & (1 << annihilate) or source & (1 << create):
        return None
    annihilation_sign = -1 if (source & ((1 << annihilate) - 1)).bit_count() % 2 else 1
    intermediate = source ^ (1 << annihilate)
    creation_sign = -1 if (intermediate & ((1 << create) - 1)).bit_count() % 2 else 1
    return intermediate | (1 << create), annihilation_sign * creation_sign


def car_hopping_action(source: int, n_qubits: int, left: int, right: int) -> Action:
    """Action of ``-(c†_left c_right + c†_right c_left)``."""

    if (
        isinstance(source, bool)
        or not isinstance(source, int)
        or not 0 <= source < (1 << n_qubits)
        or not 0 <= left < right < n_qubits
    ):
        raise SchemaError("invalid CAR action input")
    result: Action = {}
    for create, annihilate in ((left, right), (right, left)):
        branch = _apply_creation_annihilation(source, create, annihilate)
        if branch is not None:
            target, sign = branch
            result[target] = _gaussian_add(
                result.get(target, (Fraction(0), Fraction(0))),
                (Fraction(-sign), Fraction(0)),
            )
    return _clean_action(result)


def pauli_basis_action(pauli: str, source: int) -> Tuple[int, Gaussian]:
    if (
        not isinstance(pauli, str)
        or not pauli
        or set(pauli) - set("IXYZ")
        or isinstance(source, bool)
        or not isinstance(source, int)
        or not 0 <= source < (1 << len(pauli))
    ):
        raise SchemaError("invalid Pauli basis action input")
    target = source
    phase: Gaussian = (Fraction(1), Fraction(0))
    for qubit, operator in enumerate(pauli):
        occupied = bool(source & (1 << qubit))
        if operator == "Z" and occupied:
            phase = _gaussian_scale(phase, Fraction(-1))
        elif operator == "X":
            target ^= 1 << qubit
        elif operator == "Y":
            target ^= 1 << qubit
            # Y|0>=i|1>, Y|1>=-i|0>.
            phase = (-phase[1], phase[0]) if not occupied else (phase[1], -phase[0])
    return target, phase


def jw_pauli_hopping_action(
    source: int, n_qubits: int, left: int, right: int
) -> Action:
    if not 0 <= left < right < n_qubits:
        raise SchemaError("invalid JW hopping endpoints")
    parity = {qubit: "Z" for qubit in range(left + 1, right)}
    result: Action = {}
    for axis in ("X", "Y"):
        pauli = _pauli_string(
            n_qubits, {**parity, left: axis, right: axis}
        )
        target, phase = pauli_basis_action(pauli, source)
        result[target] = _gaussian_add(
            result.get(target, (Fraction(0), Fraction(0))),
            _gaussian_scale(phase, Fraction(-1, 2)),
        )
    return _clean_action(result)


def jw_term_record_hopping_action(
    source: int, n_qubits: int, terms: Any
) -> Action:
    """Apply the generated hopping term records to one basis state exactly."""

    if not isinstance(terms, list) or len(terms) != 2:
        raise SchemaError("a canonical hopping bond must have exactly two terms")
    result: Action = {}
    for index, term in enumerate(terms):
        if not isinstance(term, Mapping):
            raise SchemaError(f"hopping term {index} must be an object")
        try:
            pauli = term["pauli"]
            coefficient = parse_fraction(
                term["coefficient"], f"hopping term {index}.coefficient"
            )
        except KeyError as exc:
            raise SchemaError(f"hopping term {index} is incomplete") from exc
        if not isinstance(pauli, str) or len(pauli) != n_qubits:
            raise SchemaError(f"hopping term {index}.pauli has the wrong width")
        target, phase = pauli_basis_action(pauli, source)
        result[target] = _gaussian_add(
            result.get(target, (Fraction(0), Fraction(0))),
            _gaussian_scale(phase, coefficient),
        )
    return _clean_action(result)


def _action_json(action: Action, n_qubits: int) -> List[Dict[str, Any]]:
    return [
        {
            "target_bits_q0_first": _bitstring(target, n_qubits),
            "amplitude": {
                "real": format_fraction(action[target][0]),
                "imag": format_fraction(action[target][1]),
            },
        }
        for target in sorted(action)
    ]


def selected_sign_witnesses(linear_size: int) -> List[Dict[str, Any]]:
    """Independently select and exactly compare eight inputs per hopping bond."""

    n_qubits = 2 * linear_size * linear_size
    witnesses: List[Dict[str, Any]] = []
    for bond in canonical_bonds(linear_size):
        left, right = bond["modes"]
        generated_terms = _hopping_terms(linear_size, bond)
        first_interior = left + 1
        if not first_interior < right:
            raise VerificationError("same-spin square-lattice bond lacks a JW interior mode")
        odd = 1 << first_interior
        spectator = 0 if left > 0 else right + 1
        if not 0 <= spectator < n_qubits or left <= spectator <= right:
            raise VerificationError("no external spectator available for fixed bond")
        spectator_bit = 1 << spectator
        cases = (
            ("right_even", 1 << right),
            ("right_odd", (1 << right) | odd),
            ("left_even", 1 << left),
            ("left_odd", (1 << left) | odd),
            ("right_even_external_spectator", (1 << right) | spectator_bit),
            ("left_odd_external_spectator", (1 << left) | odd | spectator_bit),
            ("empty_endpoints_odd", odd),
            ("both_endpoints_odd", (1 << left) | (1 << right) | odd),
        )
        for case, source in cases:
            car = car_hopping_action(source, n_qubits, left, right)
            pauli = jw_term_record_hopping_action(
                source, n_qubits, generated_terms
            )
            if car != pauli:
                raise VerificationError(
                    f"CAR/JW action mismatch for {bond['bond_id']} {case}"
                )
            witnesses.append(
                {
                    "bond_id": bond["bond_id"],
                    "case": case,
                    "source_bits_q0_first": _bitstring(source, n_qubits),
                    "car_action": _action_json(car, n_qubits),
                    "jw_pauli_action": _action_json(pauli, n_qubits),
                }
            )
    if len(witnesses) > RESOURCE_LIMITS["max_sign_witnesses"]:
        raise SchemaError("sign-witness cap exceeded")
    return witnesses


def onsite_basis_witnesses(linear_size: int) -> List[Dict[str, Any]]:
    """Check the onsite I/Z/Z/ZZ sum on all four local occupations."""

    n_qubits = 2 * linear_size * linear_size
    terms = _onsite_terms(linear_size)
    witnesses: List[Dict[str, Any]] = []
    cases = (
        ("empty", 0, Fraction(0)),
        ("up_only", 1, Fraction(0)),
        ("down_only", 2, Fraction(0)),
        ("double", 3, U_OVER_T),
    )
    for row in range(linear_size):
        for column in range(linear_size):
            site = row * linear_size + column
            up, down = 2 * site, 2 * site + 1
            site_terms = [term for term in terms if term["site"] == [row, column]]
            if [term["component"] for term in site_terms] != ["I", "Zup", "Zdown", "ZZ"]:
                raise VerificationError("onsite term components are incomplete or misordered")
            for case, local_bits, expected in cases:
                source = (
                    ((local_bits & 1) << up)
                    | (((local_bits >> 1) & 1) << down)
                )
                energy = Fraction(0)
                for term in site_terms:
                    target, phase = pauli_basis_action(term["pauli"], source)
                    if target != source or phase[1] != 0:
                        raise VerificationError("onsite Pauli term is unexpectedly non-diagonal")
                    energy += parse_fraction(term["coefficient"]) * phase[0]
                if energy != expected:
                    raise VerificationError(
                        f"onsite occupation energy mismatch at r{row} c{column} {case}"
                    )
                witnesses.append(
                    {
                        "site": [row, column],
                        "case": case,
                        "source_bits_q0_first": _bitstring(source, n_qubits),
                        "recomputed_energy": format_fraction(energy),
                        "expected_energy": format_fraction(expected),
                    }
                )
    if len(witnesses) > RESOURCE_LIMITS["max_onsite_basis_witnesses"]:
        raise SchemaError("onsite-basis witness cap exceeded")
    return witnesses


def _profile_summary(linear_size: int) -> Dict[str, Any]:
    profile_id = f"L{linear_size}_OBC"
    bonds = canonical_bonds(linear_size)
    terms = canonical_terms(linear_size)
    events = raw_strang_events(linear_size)
    witnesses = selected_sign_witnesses(linear_size)
    onsite_witnesses = onsite_basis_witnesses(linear_size)
    matching_sizes = {
        group: sum(1 for bond in bonds if bond["group"] == group)
        for group in ("H1", "H2", "H3", "H4")
    }
    raw_rotations = sum(len(event["terms"]) for event in events)
    identity_terms = [
        term
        for event in events
        for term in event["terms"]
        if set(term["pauli"]) == {"I"}
    ]
    raw_nonidentity = raw_rotations - len(identity_terms)
    identity_theta_sum = sum(
        (parse_fraction(term["rotation_theta"]) for term in identity_terms),
        Fraction(0),
    )
    nonidentity_gates = canonical_nonidentity_gate_sequence(linear_size)
    summary = {
        "profile_id": profile_id,
        "linear_size": linear_size,
        "n_qubits": 2 * linear_size * linear_size,
        "matching_sizes": matching_sizes,
        "spin_resolved_hopping_bond_count": len(bonds),
        "canonical_hopping_pauli_term_count": sum(
            term["kind"] == "hopping" for term in terms
        ),
        "onsite_pauli_term_count_including_identity": sum(
            term["kind"] == "onsite" for term in terms
        ),
        "canonical_term_count": len(terms),
        "raw_strang_event_count": len(events),
        "raw_term_rotation_count_including_identity": raw_rotations,
        "raw_nonidentity_rotation_count": raw_nonidentity,
        "raw_identity_rotation_count": len(identity_terms),
        "global_phase_ledger": {
            "identity_rotation_theta_sum": format_fraction(identity_theta_sum),
            "phase_exponent_in_exp_minus_i_x": format_fraction(identity_theta_sum / 2),
            "status": "IDENTITY_RETAINED_IN_RAW_EVENTS_NONIDENTITY_VIEW_ONLY_OMITS_GLOBAL_PHASE",
        },
        "selected_sign_witness_count": len(witnesses),
        "onsite_basis_witness_count": len(onsite_witnesses),
        "canonical_bonds_sha256": canonical_sha256(bonds),
        "canonical_terms_sha256": canonical_sha256(terms),
        "raw_strang_events_sha256": canonical_sha256(events),
        "nonidentity_gate_sequence_sha256": canonical_sha256(nonidentity_gates),
        "selected_sign_witnesses_sha256": canonical_sha256(witnesses),
        "onsite_basis_witnesses_sha256": canonical_sha256(onsite_witnesses),
    }
    return summary


def expected_profile_summaries() -> List[Dict[str, Any]]:
    summaries = [_profile_summary(linear_size) for linear_size in LINEAR_SIZES]
    l2, l3 = summaries
    if l2["matching_sizes"]["H2"] != 0 or l2["matching_sizes"]["H3"] != 0:
        raise VerificationError("fixed L2 odd-parity matchings must be empty")
    if l3["matching_sizes"]["H2"] <= 0 or l3["matching_sizes"]["H3"] <= 0:
        raise VerificationError("fixed L3 H2/H3 matchings must be nonempty")
    return summaries


def _verified_source_bytes() -> Dict[str, bytes]:
    """Read each dependency once and return only bytes matching its hard pin."""

    here = Path(__file__).resolve().parent
    verified: Dict[str, bytes] = {}
    for index, pin in enumerate(SOURCE_PINS):
        path = here / pin["relative_path"]
        try:
            source = path.read_bytes()
        except OSError as exc:
            raise SchemaError(f"source pin {index} cannot be read") from exc
        digest = hashlib.sha256(source).hexdigest()
        if digest != pin["sha256"]:
            raise SchemaError(f"source pin {index} byte hash mismatch")
        verified[pin["relative_path"]] = source
    return verified


def _validate_source_pins(source_pins: Any) -> None:
    if not _strict_equal(source_pins, list(SOURCE_PINS)):
        raise SchemaError("contract.source_pins do not match checker pins")
    _verified_source_bytes()


def _execute_pinned_l2_gate_builder(source: bytes, path: Path) -> Any:
    """Execute only the gate-builder AST taken from the exact verified bytes.

    Loading by filesystem import after hashing would leave a source/pyc race.  The
    selected constants and functions are instead compiled directly from the bytes
    whose digest was checked.  The builder needs only canonical Fraction formatting;
    no dependency module is imported or executed here.
    """

    constant_names = {"N_QUBITS", "GROUP_ORDER", "H1_MODE_PAIRS", "H4_MODE_PAIRS"}
    function_names = {
        "_pauli_string", "_hopping_group", "_onsite_group",
        "build_forward_gate_sequence",
    }
    try:
        tree = ast.parse(source, filename=str(path))
        selected: List[ast.stmt] = []
        found_constants = set()
        found_functions = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                selected.append(node)
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in constant_names
            ):
                name = node.targets[0].id
                if name in found_constants:
                    raise SchemaError(f"duplicate pinned L2 constant {name}")
                found_constants.add(name)
                selected.append(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in function_names:
                if node.name in found_functions:
                    raise SchemaError(f"duplicate pinned L2 function {node.name}")
                found_functions.add(node.name)
                selected.append(node)
        if found_constants != constant_names or found_functions != function_names:
            raise SchemaError("pinned L2 gate-builder structure is incomplete")

        class FractionFormatter:
            format_fraction = staticmethod(format_fraction)

        namespace: Dict[str, Any] = {
            "__name__": "hubbard_jw_pinned_l2_gate_builder",
            "CHECKER": FractionFormatter,
            "Fraction": Fraction,
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "Mapping": Mapping,
            "Sequence": Sequence,
            "Tuple": Tuple,
        }
        selected_tree = ast.Module(body=selected, type_ignores=[])
        exec(compile(selected_tree, str(path), "exec"), namespace)
        return namespace["build_forward_gate_sequence"]()
    except Exception as exc:
        if isinstance(exc, (SchemaError, VerificationError)):
            raise
        raise SchemaError("pinned L2 gate-sequence source could not execute") from exc


def verify_pinned_l2_witness_sequence() -> str:
    """Execute the exact hash-pinned L2 builder and require gate equality."""

    relative_path = "operator_propagation_l2_witness.py"
    sources = _verified_source_bytes()
    path = Path(__file__).resolve().parent / relative_path
    actual = _execute_pinned_l2_gate_builder(sources[relative_path], path)
    expected = canonical_nonidentity_gate_sequence(2)
    if not _strict_equal(actual, expected):
        raise VerificationError(
            "pinned L2 witness gate sequence disagrees with canonical mapping"
        )
    digest = canonical_sha256(actual)
    expected_digest = _profile_summary(2)["nonidentity_gate_sequence_sha256"]
    if digest != expected_digest:
        raise VerificationError("pinned L2 witness gate digest mismatch")
    return digest


def validate_contract(contract: Any) -> List[str]:
    try:
        item = _exact_keys(
            contract,
            (
                "schema_version", "contract_fingerprint", "certificate_type",
                "checker_fingerprint", "checker_source_sha256", "source_pins",
                "profile_policy", "expected_profiles", "rational_encoding",
                "resource_limits", "maximum_positive_status", "scope_claims",
            ),
            "contract",
        )
        if type(item["schema_version"]) is not int or item["schema_version"] != 1:
            raise SchemaError("contract.schema_version must be integer 1")
        expected_scalars = {
            "contract_fingerprint": CONTRACT_FINGERPRINT,
            "certificate_type": CERTIFICATE_TYPE,
            "checker_fingerprint": CHECKER_FINGERPRINT,
            "rational_encoding": RATIONAL_ENCODING,
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
        _validate_source_pins(item["source_pins"])
        verify_pinned_l2_witness_sequence()
        if not _strict_equal(item["profile_policy"], PROFILE_POLICY):
            raise SchemaError("contract.profile_policy does not match fixed profiles")
        if not _strict_equal(item["resource_limits"], RESOURCE_LIMITS):
            raise SchemaError("contract.resource_limits does not match hard caps")
        if not _strict_equal(item["scope_claims"], SCOPE_CLAIMS):
            raise SchemaError("contract.scope_claims does not match fail-closed scope")
        expected_profiles = expected_profile_summaries()
        if not _strict_equal(item["expected_profiles"], expected_profiles):
            raise SchemaError("contract.expected_profiles do not match recomputation")
    except (
        SchemaError, VerificationError, KeyError, TypeError, OSError,
        RecursionError,
    ) as exc:
        return [str(exc)]
    return []


def _validate_profile_claim_shape(value: Any, index: int) -> Mapping[str, Any]:
    item = _exact_keys(
        value,
        (
            "profile_id", "linear_size", "n_qubits", "matching_sizes",
            "spin_resolved_hopping_bond_count",
            "canonical_hopping_pauli_term_count",
            "onsite_pauli_term_count_including_identity", "canonical_term_count",
            "raw_strang_event_count", "raw_term_rotation_count_including_identity",
            "raw_nonidentity_rotation_count", "raw_identity_rotation_count",
            "global_phase_ledger", "selected_sign_witness_count",
            "onsite_basis_witness_count",
            "canonical_bonds_sha256", "canonical_terms_sha256",
            "raw_strang_events_sha256", "nonidentity_gate_sequence_sha256",
            "selected_sign_witnesses_sha256", "onsite_basis_witnesses_sha256",
        ),
        f"certificate.profile_claims[{index}]",
    )
    if item["profile_id"] not in PROFILE_IDS:
        raise SchemaError(f"certificate.profile_claims[{index}].profile_id is unknown")
    _integer(item["linear_size"], f"profile[{index}].linear_size", 2, 3)
    _integer(item["n_qubits"], f"profile[{index}].n_qubits", 1, RESOURCE_LIMITS["max_qubits"])
    matching = _exact_keys(
        item["matching_sizes"], ("H1", "H2", "H3", "H4"),
        f"profile[{index}].matching_sizes",
    )
    for group in ("H1", "H2", "H3", "H4"):
        _integer(matching[group], f"profile[{index}].matching_sizes.{group}", 0, RESOURCE_LIMITS["max_spin_resolved_bonds"])
    count_limits = {
        "spin_resolved_hopping_bond_count": RESOURCE_LIMITS["max_spin_resolved_bonds"],
        "canonical_hopping_pauli_term_count": RESOURCE_LIMITS["max_canonical_terms"],
        "onsite_pauli_term_count_including_identity": RESOURCE_LIMITS["max_canonical_terms"],
        "canonical_term_count": RESOURCE_LIMITS["max_canonical_terms"],
        "raw_strang_event_count": RESOURCE_LIMITS["max_raw_events"],
        "raw_term_rotation_count_including_identity": RESOURCE_LIMITS["max_raw_term_rotations"],
        "raw_nonidentity_rotation_count": RESOURCE_LIMITS["max_raw_term_rotations"],
        "raw_identity_rotation_count": RESOURCE_LIMITS["max_raw_term_rotations"],
        "selected_sign_witness_count": RESOURCE_LIMITS["max_sign_witnesses"],
        "onsite_basis_witness_count": RESOURCE_LIMITS["max_onsite_basis_witnesses"],
    }
    for field, maximum in count_limits.items():
        _integer(item[field], f"profile[{index}].{field}", 0, maximum)
    ledger = _exact_keys(
        item["global_phase_ledger"],
        ("identity_rotation_theta_sum", "phase_exponent_in_exp_minus_i_x", "status"),
        f"profile[{index}].global_phase_ledger",
    )
    parse_fraction(ledger["identity_rotation_theta_sum"], f"profile[{index}].global_phase_ledger.identity_rotation_theta_sum")
    parse_fraction(ledger["phase_exponent_in_exp_minus_i_x"], f"profile[{index}].global_phase_ledger.phase_exponent_in_exp_minus_i_x")
    if ledger["status"] != "IDENTITY_RETAINED_IN_RAW_EVENTS_NONIDENTITY_VIEW_ONLY_OMITS_GLOBAL_PHASE":
        raise SchemaError(f"profile[{index}].global_phase_ledger.status does not match policy")
    for field in (
        "canonical_bonds_sha256", "canonical_terms_sha256",
        "raw_strang_events_sha256", "nonidentity_gate_sequence_sha256",
        "selected_sign_witnesses_sha256", "onsite_basis_witnesses_sha256",
    ):
        if not isinstance(item[field], str) or not SHA256_RE.fullmatch(item[field]):
            raise SchemaError(f"profile[{index}].{field} must be lowercase sha256")
    return item


def verify_certificate(contract: Any, certificate: Any) -> Dict[str, Any]:
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
                "profile_policy", "profile_claims", "scope_claims",
            ),
            "certificate",
        )
        if type(cert["schema_version"]) is not int or cert["schema_version"] != 1:
            raise SchemaError("certificate.schema_version must be integer 1")
        for field, expected in (
            ("certificate_type", CERTIFICATE_TYPE),
            ("contract_fingerprint", CONTRACT_FINGERPRINT),
            ("profile_policy", PROFILE_POLICY),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(cert[field], expected):
                raise SchemaError(f"certificate.{field} does not match contract")
        claims = cert["profile_claims"]
        if not isinstance(claims, list) or len(claims) != len(PROFILE_IDS):
            raise SchemaError("certificate.profile_claims must contain exactly L2 and L3")
        parsed = [_validate_profile_claim_shape(value, index) for index, value in enumerate(claims)]
        if [item["profile_id"] for item in parsed] != list(PROFILE_IDS):
            raise SchemaError("certificate.profile_claims must be ordered L2_OBC,L3_OBC")
        recomputed = expected_profile_summaries()
        if not _strict_equal(parsed, recomputed):
            raise VerificationError("profile claims disagree with independent recomputation")
        if not _strict_equal(parsed, contract["expected_profiles"]):
            raise VerificationError("profile claims disagree with contract pins")
        pinned_l2_digest = verify_pinned_l2_witness_sequence()
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
            "source_pins_verified": True,
            "source_pinned_L2_witness_gate_sequence_verified": True,
            "source_pinned_L2_witness_gate_sequence_sha256": pinned_l2_digest,
            "profile_count": len(recomputed),
            "recomputed_profiles": recomputed,
            "limitations": [
                "Only the contract-pinned L=2 and L=3 OBC profiles are verified.",
                "Generated JW hopping records are checked on fixed selected basis inputs, not arbitrary superpositions as a separate theorem object.",
                "Raw Strang events are reconstructed but no product-formula error is assessed.",
                "No exact-Hamiltonian evolution or reference error budget is assessed.",
                "No result is transferred to L=8 or any READY gate.",
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


def load_strict_json(path: Path, maximum_bytes: int = RESOURCE_LIMITS["max_json_bytes"]) -> Any:
    if (
        isinstance(maximum_bytes, bool)
        or not isinstance(maximum_bytes, int)
        or not 1 <= maximum_bytes <= RESOURCE_LIMITS["max_json_bytes"]
    ):
        raise ValueError("JSON byte cap is invalid")
    with path.open("rb") as handle:
        payload = handle.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise ValueError("JSON file exceeds byte cap")
    return json.loads(
        payload.decode("utf-8", errors="strict"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON constant: {value}")
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("certificate", type=Path)
    args = parser.parse_args(argv)
    try:
        contract = load_strict_json(args.contract)
        certificate = load_strict_json(args.certificate)
        result = verify_certificate(contract, certificate)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        result = {
            "status": "INVALID_SCHEMA",
            "verified": False,
            "ready_gate_eligible": False,
            "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
            "errors": [str(exc)],
        }
    print(json.dumps(result, allow_nan=False, indent=2, sort_keys=True))
    # Mapping alone cannot qualify a physical reference or READY condition.
    return 1


if __name__ == "__main__":
    sys.exit(main())
