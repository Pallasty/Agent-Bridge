#!/usr/bin/env python3
"""Fail-closed exact L1 commutator bound for three fixed Hubbard profiles.

This checker independently regenerates the nonidentity Jordan--Wigner Pauli
expansions of the five OBC groups ``H1,H2,HU,H3,H4`` at L=2,3,8.  It then
aggregates every Pauli string in the two nested-commutator families of the
tight second-order Suzuki bound before applying the coefficient L1 norm.

The pinned theorem is Proposition 2, Eq. (13), of Schubert and Mendl,
arXiv:2306.10603v2 / Phys. Rev. B 108, 195105 (2023).  With

    K_gamma = sum_{j>gamma} H_j,

its one-step coefficient is exactly

    C = sum_gamma ( ||[K_gamma,[K_gamma,H_gamma]]|| / 12
                    + ||[H_gamma,[K_gamma,H_gamma]]|| / 24 ).

The checker upper-bounds each spectral norm by the L1 norm of its fully
merged Pauli coefficients and telescopes R unitary steps, giving
``C*T**3/R**2``.  A generic norm-one observable expectation bound is twice
that value.  This is only a Strang commutator-L1 subcertificate: it does not
compose a mapping certificate, prove an observable-specific norm or
tightening, certify truncation, identify a physical L=8 workload, or qualify
any reference/READY gate.  Consequently the CLI always exits nonzero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import types
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


# A public CLI/API call re-executes the checker from one bounded source read.
# The fresh module receives those exact bytes here before ``exec``.  This
# avoids binding a path hash to stale imported bytecode or to a second read.
if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None


CERTIFICATE_TYPE = "hubbard_strang_commutator_l1_subcertificate_v1"
CONTRACT_FINGERPRINT = "hubbard_strang_commutator_contract_v1"
CHECKER_FINGERPRINT = "hubbard_strang_exact_pauli_l1_checker_v1"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE"

GROUPS = ("H1", "H2", "HU", "H3", "H4")
RAW_S2_ORDER = ("H1", "H2", "HU", "H3", "H4", "H4", "H3", "HU", "H2", "H1")
PROFILE_SIZES = (2, 3, 8)
PROFILE_IDS = ("L2_OBC_R100", "L3_OBC_R100", "L8_OBC_R100")
U_OVER_T = Fraction(8)
TOTAL_TIME = Fraction(1)
TROTTER_STEPS = 100
OBSERVABLE_ALLOCATION = Fraction(1, 4000)

BOUND_SOURCE = {
    "authors": "Ansgar Schubert and Christian B. Mendl",
    "title": "Trotter error with commutator scaling for the Fermi-Hubbard model",
    "arxiv_version": "2306.10603v2",
    "doi": "10.1103/PhysRevB.108.195105",
    "result": "Proposition 2, Equation (13), citing Childs-et-al Proposition 10",
    "formula": (
        "K_gamma=sum_{j>gamma}H_j; "
        "C=sum_gamma(norm([K_gamma,[K_gamma,H_gamma]])/12"
        "+norm([H_gamma,[K_gamma,H_gamma]])/24); "
        "R_step_error<=C*T^3/R^2"
    ),
    "group_index_order": list(GROUPS),
    "norm_substitution": (
        "each nested commutator is independently Pauli-merged, then "
        "operator norm is upper-bounded by coefficient L1"
    ),
}

PROFILE_POLICY = {
    "profile_ids": list(PROFILE_IDS),
    "linear_sizes": list(PROFILE_SIZES),
    "boundary_condition": "square_open_boundary_no_wrap",
    "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
    "hamiltonian_convention": (
        "H=-sum_<ij>,sigma(cdag_i_sigma*c_j_sigma+cdag_j_sigma*c_i_sigma)"
        "+8*sum_i n_i_up*n_i_down_unshifted"
    ),
    "group_order": list(GROUPS),
    "raw_symmetric_s2_order": list(RAW_S2_ORDER),
    "total_time": "1/1",
    "trotter_steps": TROTTER_STEPS,
    "single_step_duration": "1/100",
    "onsite_identity_policy": "omit_common_identity_with_explicit_phase_ledger",
    "observable_allocation": "1/4000",
    "observable_comparison_policy": "generic_norm_at_most_one_factor_two_only",
}

RESOURCE_LIMITS = {
    "max_json_bytes": 1_048_576,
    "max_linear_size": 8,
    "max_qubits": 128,
    "max_group_terms": 192,
    "max_total_terms": 640,
    "max_commutator_pair_products": 20_000_000,
    "max_commutator_output_terms": 20_000,
    "max_action_basis_states": 256,
    "max_action_term_applications": 80_000_000,
    "max_rational_digits": 128,
    "max_checker_source_bytes": 131_072,
    "max_pinned_source_bytes": 1_048_576,
}

SOURCE_PINS = (
    {
        "relative_path": "hubbard_jw_mapping_validator.py",
        "role": "L2_L3_canonical_mapping_cross_check_source",
        "sha256": "21ada33e0a45ec2ede6cc75872e17c8292eac6b17b747fc902a5bb1a135c8be6",
    },
    {
        "relative_path": "hubbard_jw_mapping_contract.json",
        "role": "L2_L3_mapping_contract_cross_check_source",
        "sha256": "8d1af7c7b17dfd2b92d5c9fae9a1a6dd71e17d3e78b6e8d4fc5aba2123463e01",
    },
    {
        "relative_path": "hubbard_jw_mapping_template.json",
        "role": "L2_L3_positive_mapping_template_cross_check_source",
        "sha256": "ecd9b2f98483280f3072e2077c83a6d8c115328968226de3c5e7c6f00a75fdaf",
    },
    {
        "relative_path": "pauli_bitset_backend.py",
        "role": "independent_bitset_arithmetic_cross_check_source",
        "sha256": "6f968e30b9809894dc6a5585c80a29feb4f3cc8dab6da8300473763a90c7a8a5",
    },
)

SCOPE_CLAIMS = {
    "checker_execution_from_contract_pinned_source_bytes_verified": True,
    "fixed_L2_L3_L8_OBC_commutator_profiles_verified": True,
    "source_pins_verified": True,
    "canonical_nonidentity_group_expansions_recomputed": True,
    "group_internal_pairwise_commutation_verified": True,
    "raw_S2_palindrome_and_commuting_term_product_binding_verified": True,
    "nested_commutators_exactly_aggregated": True,
    "coefficient_L1_operator_norm_upper_bounds_verified": True,
    "pinned_strang_bound_and_R_step_telescoping_verified": True,
    "L2_full_basis_sparse_action_oracle_verified": True,
    "L3_selected_basis_sparse_action_oracle_verified": True,
    "mapping_certificate_composed": False,
    "observable_specific_tightening": "NOT_ASSESSED",
    "truncation_certificate_composed": False,
    "physical_L8_instance_identity": "NOT_ASSESSED",
    "reference_error_budget_qualified": False,
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    key: (False if value is True else value) for key, value in SCOPE_CLAIMS.items()
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RATIONAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)/[1-9][0-9]*$")

PauliKey = Tuple[int, int]
Gaussian = Tuple[Fraction, Fraction]
Expansion = Dict[PauliKey, Gaussian]
State = Dict[int, Gaussian]
_PROFILE_CACHE_BYTES: bytes | None = None


class SchemaError(ValueError):
    """Malformed input or contract-policy mismatch."""


class VerificationError(ValueError):
    """Well-shaped claim or independent oracle mismatch."""


class ResourceLimitError(VerificationError):
    """A deterministic hard computation cap was exceeded."""


def format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def parse_fraction(value: Any, name: str = "rational") -> Fraction:
    if type(value) is not str or not RATIONAL_RE.fullmatch(value):
        raise SchemaError(f"{name} must be a canonical rational string")
    numerator, denominator = value.split("/", 1)
    if (
        len(numerator.lstrip("-")) > RESOURCE_LIMITS["max_rational_digits"]
        or len(denominator) > RESOURCE_LIMITS["max_rational_digits"]
    ):
        raise SchemaError(f"{name} exceeds rational digit cap")
    result = Fraction(int(numerator), int(denominator))
    if format_fraction(result) != value:
        raise SchemaError(f"{name} must be reduced and canonical")
    return result


def _check_fraction(value: Fraction, name: str) -> Fraction:
    if type(value) is not Fraction:
        raise VerificationError(f"{name} is not an exact Fraction")
    if (
        len(str(abs(value.numerator))) > RESOURCE_LIMITS["max_rational_digits"]
        or len(str(value.denominator)) > RESOURCE_LIMITS["max_rational_digits"]
    ):
        raise ResourceLimitError(f"{name} exceeds rational digit cap")
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


def _exact_keys(value: Any, keys: Iterable[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{name} must be an object")
    expected = set(keys)
    if set(value) != expected:
        raise SchemaError(f"{name} keys must exactly equal {sorted(expected)}")
    return value


def canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(
            value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("value cannot be canonically hashed") from exc
    return hashlib.sha256(encoded).hexdigest()


def _read_checker_source_bytes() -> bytes:
    with Path(__file__).open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_checker_source_bytes"] + 1)
    if len(payload) > RESOURCE_LIMITS["max_checker_source_bytes"]:
        raise SchemaError("checker source exceeds its byte cap")
    return payload


def checker_source_sha256() -> str:
    payload = _VERIFIED_SELF_SOURCE_BYTES
    if payload is None:
        payload = _read_checker_source_bytes()
    return hashlib.sha256(payload).hexdigest()


def _execute_from_verified_self_source(method: str, *arguments: Any) -> Any:
    """Execute ``method`` in a module compiled from the exact hashed bytes."""

    payload = _read_checker_source_bytes()
    if not arguments or type(arguments[0]) is not dict:
        raise SchemaError("outer self-exec preflight requires an exact contract object")
    checker_pin = arguments[0].get("checker_source_sha256")
    if type(checker_pin) is not str or not SHA256_RE.fullmatch(checker_pin):
        raise SchemaError("outer self-exec preflight requires canonical checker_source_sha256")
    if hashlib.sha256(payload).hexdigest() != checker_pin:
        raise SchemaError("checker source pin mismatch before compile/exec")
    path = Path(__file__).resolve()
    module = types.ModuleType("verified_hubbard_strang_commutator_checker")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, str(path), "exec"), module.__dict__)
    target = getattr(module, method, None)
    if not callable(target):
        raise SchemaError("verified checker source lacks required entry point")
    return target(*arguments)


def _pauli_multiply(left: PauliKey, right: PauliKey) -> Tuple[int, PauliKey]:
    lx, lz = left
    rx, rz = right
    output = lx ^ rx, lz ^ rz
    phase = (
        (lx & lz).bit_count()
        + (rx & rz).bit_count()
        + 2 * (lz & rx).bit_count()
        - (output[0] & output[1]).bit_count()
    ) % 4
    return phase, output


def _pauli_commutes(left: PauliKey, right: PauliKey) -> bool:
    lx, lz = left
    rx, rz = right
    return (((lx & rz).bit_count() + (lz & rx).bit_count()) & 1) == 0


def _string_to_masks(pauli: str) -> PauliKey:
    if type(pauli) is not str or not pauli or set(pauli) - set("IXYZ"):
        raise SchemaError("invalid Pauli string")
    x_mask = 0
    z_mask = 0
    for qubit, symbol in enumerate(pauli):
        if symbol in "XY":
            x_mask |= 1 << qubit
        if symbol in "YZ":
            z_mask |= 1 << qubit
    return x_mask, z_mask


def _masks_to_string(key: PauliKey, n_qubits: int) -> str:
    x_mask, z_mask = key
    symbols = ("I", "X", "Z", "Y")
    return "".join(
        symbols[2 * ((z_mask >> q) & 1) + ((x_mask >> q) & 1)]
        for q in range(n_qubits)
    )


def _g_add(left: Gaussian, right: Gaussian) -> Gaussian:
    return left[0] + right[0], left[1] + right[1]


def _g_neg(value: Gaussian) -> Gaussian:
    return -value[0], -value[1]


def _g_mul(left: Gaussian, right: Gaussian) -> Gaussian:
    return (
        left[0] * right[0] - left[1] * right[1],
        left[0] * right[1] + left[1] * right[0],
    )


def _g_scale(value: Gaussian, scale: Fraction) -> Gaussian:
    return value[0] * scale, value[1] * scale


def _g_i_power(value: Gaussian, power: int) -> Gaussian:
    power %= 4
    if power == 0:
        return value
    if power == 1:
        return -value[1], value[0]
    if power == 2:
        return -value[0], -value[1]
    return value[1], -value[0]


def _clean(values: MutableMapping[Any, Gaussian]) -> None:
    for key in [key for key, value in values.items() if value == (0, 0)]:
        del values[key]


def _add_term(expansion: Expansion, key: PauliKey, coefficient: Gaussian) -> None:
    value = _g_add(expansion.get(key, (Fraction(0), Fraction(0))), coefficient)
    _check_fraction(value[0], "commutator real coefficient")
    _check_fraction(value[1], "commutator imaginary coefficient")
    if value == (0, 0):
        expansion.pop(key, None)
    else:
        expansion[key] = value


def _mode(linear_size: int, row: int, column: int, spin: int) -> int:
    return 2 * (row * linear_size + column) + spin


def _hopping_bonds(linear_size: int, group: str) -> List[Tuple[int, int]]:
    bonds: List[Tuple[int, int]] = []
    if group in ("H1", "H2"):
        parity = 0 if group == "H1" else 1
        endpoints = (
            ((row, column), (row, column + 1))
            for row in range(linear_size)
            for column in range(parity, linear_size - 1, 2)
        )
    elif group in ("H3", "H4"):
        parity = 1 if group == "H3" else 0
        endpoints = (
            ((row, column), (row + 1, column))
            for row in range(parity, linear_size - 1, 2)
            for column in range(linear_size)
        )
    else:
        raise SchemaError("hopping bonds require H1,H2,H3,H4")
    for (row_a, col_a), (row_b, col_b) in endpoints:
        for spin in (0, 1):
            left = _mode(linear_size, row_a, col_a, spin)
            right = _mode(linear_size, row_b, col_b, spin)
            if not left < right:
                raise VerificationError("generated hopping modes are not ascending")
            bonds.append((left, right))
    return bonds


def canonical_group_expansions(linear_size: int) -> Dict[str, Expansion]:
    """Generate nonidentity group Hamiltonians without importing pinned mapping code."""

    if type(linear_size) is not int or linear_size not in PROFILE_SIZES:
        raise SchemaError("linear_size must be one of the three fixed profiles")
    n_qubits = 2 * linear_size * linear_size
    if n_qubits > RESOURCE_LIMITS["max_qubits"]:
        raise ResourceLimitError("qubit cap exceeded")
    output: Dict[str, Expansion] = {group: {} for group in GROUPS}
    for group in ("H1", "H2", "H3", "H4"):
        for left, right in _hopping_bonds(linear_size, group):
            interior = ((1 << right) - 1) ^ ((1 << (left + 1)) - 1)
            for axis in ("X", "Y"):
                endpoints = (1 << left) | (1 << right)
                key = (
                    endpoints,
                    interior if axis == "X" else interior | endpoints,
                )
                _add_term(output[group], key, (Fraction(-1, 2), Fraction(0)))
    for site in range(linear_size * linear_size):
        up = 2 * site
        down = up + 1
        onsite_component = U_OVER_T / 4
        for key, coefficient in (
            ((0, 1 << up), -onsite_component),
            ((0, 1 << down), -onsite_component),
            ((0, (1 << up) | (1 << down)), onsite_component),
        ):
            _add_term(output["HU"], key, (coefficient, Fraction(0)))
    total = 0
    for group, expansion in output.items():
        if len(expansion) > RESOURCE_LIMITS["max_group_terms"]:
            raise ResourceLimitError(f"{group} term cap exceeded")
        total += len(expansion)
    if total > RESOURCE_LIMITS["max_total_terms"]:
        raise ResourceLimitError("total term cap exceeded")
    return output


def _expansion_records(expansion: Expansion) -> List[Dict[str, str]]:
    return [
        {
            "x_mask": hex(key[0]),
            "z_mask": hex(key[1]),
            "real": format_fraction(expansion[key][0]),
            "imag": format_fraction(expansion[key][1]),
        }
        for key in sorted(expansion)
    ]


def _expansion_sha256(expansion: Expansion) -> str:
    return canonical_sha256(_expansion_records(expansion))


def _raw_s2_binding_records(groups: Mapping[str, Expansion]) -> Dict[str, Any]:
    """Bind the theorem's group exponentials to the raw commuting term products."""

    group_events: List[Dict[str, Any]] = []
    term_events: List[Dict[str, Any]] = []
    raw_term_index = 0
    for event_index, group in enumerate(RAW_S2_ORDER):
        expansion = groups[group]
        group_events.append(
            {
                "event_index": event_index,
                "group": group,
                "duration": "1/200",
                "term_count": len(expansion),
                "group_expansion_sha256": _expansion_sha256(expansion),
            }
        )
        for term_in_event, key in enumerate(sorted(expansion)):
            coefficient = expansion[key]
            if coefficient[1] != 0:
                raise VerificationError("Hamiltonian group coefficient is not real")
            term_events.append(
                {
                    "raw_term_index": raw_term_index,
                    "event_index": event_index,
                    "term_in_event": term_in_event,
                    "group": group,
                    "x_mask": hex(key[0]),
                    "z_mask": hex(key[1]),
                    "hamiltonian_coefficient": format_fraction(coefficient[0]),
                    "duration": "1/200",
                }
            )
            raw_term_index += 1
    if [record["group"] for record in group_events] != list(RAW_S2_ORDER):
        raise VerificationError("raw S2 group palindrome mismatch")
    return {
        "raw_group_event_count_per_step": len(group_events),
        "raw_nonidentity_term_event_count_per_step": len(term_events),
        "raw_group_events_sha256": canonical_sha256(group_events),
        "raw_nonidentity_term_events_sha256": canonical_sha256(term_events),
        "status": "VERIFIED_RAW_PALINDROME_AND_COMMUTING_TERM_PRODUCT_BINDING",
    }


def _merge_expansions(expansions: Sequence[Expansion]) -> Expansion:
    output: Expansion = {}
    for expansion in expansions:
        for key, coefficient in expansion.items():
            _add_term(output, key, coefficient)
    return output


def _verify_internal_commutation(groups: Mapping[str, Expansion]) -> Dict[str, int]:
    pair_counts: Dict[str, int] = {}
    for group in GROUPS:
        keys = list(groups[group])
        pair_counts[group] = len(keys) * (len(keys) - 1) // 2
        for index, left in enumerate(keys):
            for right in keys[index + 1 :]:
                if not _pauli_commutes(left, right):
                    raise VerificationError(f"{group} contains noncommuting Pauli terms")
    return pair_counts


class ComputationCounter:
    def __init__(self) -> None:
        self.commutator_pair_products = 0
        self.action_term_applications = 0

    def add_pairs(self, count: int) -> None:
        self.commutator_pair_products += count
        if (
            self.commutator_pair_products
            > RESOURCE_LIMITS["max_commutator_pair_products"]
        ):
            raise ResourceLimitError("commutator pair-product cap exceeded")

    def add_actions(self, count: int) -> None:
        self.action_term_applications += count
        if (
            self.action_term_applications
            > RESOURCE_LIMITS["max_action_term_applications"]
        ):
            raise ResourceLimitError("sparse-action term-application cap exceeded")


def exact_commutator(
    left: Expansion, right: Expansion, counter: ComputationCounter
) -> Expansion:
    """Return ``[left,right]`` with all identical Pauli keys exactly merged."""

    counter.add_pairs(len(left) * len(right))
    output: Expansion = {}
    for left_key, left_coefficient in left.items():
        for right_key, right_coefficient in right.items():
            if _pauli_commutes(left_key, right_key):
                continue
            phase, key = _pauli_multiply(left_key, right_key)
            coefficient = _g_scale(
                _g_i_power(_g_mul(left_coefficient, right_coefficient), phase),
                Fraction(2),
            )
            _add_term(output, key, coefficient)
    if len(output) > RESOURCE_LIMITS["max_commutator_output_terms"]:
        raise ResourceLimitError("commutator output-term cap exceeded")
    return output


def _pure_axis_l1(expansion: Expansion, expected_axis: str) -> Fraction:
    total = Fraction(0)
    for real, imag in expansion.values():
        if expected_axis == "real":
            if imag != 0:
                raise VerificationError("nested commutator has unexpected imaginary coefficient")
            total += abs(real)
        elif expected_axis == "imag":
            if real != 0:
                raise VerificationError("commutator has unexpected real coefficient")
            total += abs(imag)
        else:
            raise AssertionError("unknown Gaussian axis")
    return _check_fraction(total, "coefficient L1")


def _basis_pauli_action(key: PauliKey, source: int) -> Tuple[int, Gaussian]:
    """Independent action oracle for P=i^popcount(x&z) X^x Z^z."""

    x_mask, z_mask = key
    phase = (x_mask & z_mask).bit_count() % 4
    if (z_mask & source).bit_count() & 1:
        phase = (phase + 2) % 4
    return source ^ x_mask, _g_i_power((Fraction(1), Fraction(0)), phase)


def _apply_operator(
    operator: Expansion, state: State, counter: ComputationCounter
) -> State:
    counter.add_actions(len(operator) * len(state))
    output: State = {}
    for source, amplitude in state.items():
        for key, coefficient in operator.items():
            target, phase = _basis_pauli_action(key, source)
            contribution = _g_mul(amplitude, _g_mul(coefficient, phase))
            output[target] = _g_add(
                output.get(target, (Fraction(0), Fraction(0))), contribution
            )
    _clean(output)
    return output


def _state_subtract(left: State, right: State) -> State:
    output = dict(left)
    for basis, value in right.items():
        output[basis] = _g_add(output.get(basis, (Fraction(0), Fraction(0))), _g_neg(value))
    _clean(output)
    return output


def _direct_inner_action(
    tail: Expansion, group: Expansion, state: State, counter: ComputationCounter
) -> State:
    return _state_subtract(
        _apply_operator(tail, _apply_operator(group, state, counter), counter),
        _apply_operator(group, _apply_operator(tail, state, counter), counter),
    )


def _direct_outer_action(
    outer: Expansion,
    tail: Expansion,
    group: Expansion,
    state: State,
    counter: ComputationCounter,
) -> State:
    inner_state = _direct_inner_action(tail, group, state, counter)
    first = _apply_operator(outer, inner_state, counter)
    outer_state = _apply_operator(outer, state, counter)
    second = _direct_inner_action(tail, group, outer_state, counter)
    return _state_subtract(first, second)


def _action_record(state: State) -> List[Dict[str, str]]:
    return [
        {
            "basis": hex(basis),
            "real": format_fraction(state[basis][0]),
            "imag": format_fraction(state[basis][1]),
        }
        for basis in sorted(state)
    ]


def _selected_l3_basis_states(n_qubits: int) -> List[int]:
    limit = 1 << n_qubits
    seeds = [
        0,
        limit - 1,
        int("10" * (n_qubits // 2), 2),
        int("01" * (n_qubits // 2), 2),
        (1 << (n_qubits // 2)) - 1,
        ((1 << n_qubits) - 1) ^ ((1 << (n_qubits // 2)) - 1),
    ]
    value = 0x2D5A5
    while len(seeds) < 16:
        value ^= value << 7
        value ^= value >> 9
        value ^= value << 8
        candidate = value & (limit - 1)
        if candidate not in seeds:
            seeds.append(candidate)
    return seeds


def _verify_action_oracle(
    linear_size: int,
    groups: Mapping[str, Expansion],
    commutators: Sequence[Tuple[Expansion, Expansion, Expansion]],
    counter: ComputationCounter,
) -> Dict[str, Any]:
    n_qubits = 2 * linear_size * linear_size
    if linear_size == 2:
        sources = list(range(1 << n_qubits))
        coverage = "ALL_COMPUTATIONAL_BASIS_STATES"
    elif linear_size == 3:
        sources = _selected_l3_basis_states(n_qubits)
        coverage = "FIXED_16_COMPUTATIONAL_BASIS_STATES"
    else:
        return {
            "status": "NOT_RUN_L8_ACTION_ORACLE_RESOURCE_LIMIT",
            "coverage": "NONE",
            "basis_state_count": 0,
            "operator_action_comparison_count": 0,
            "action_records_sha256": canonical_sha256([]),
        }
    if len(sources) > RESOURCE_LIMITS["max_action_basis_states"]:
        raise ResourceLimitError("action basis-state cap exceeded")
    records: List[Dict[str, Any]] = []
    for gamma, group_name in enumerate(GROUPS):
        tail = _merge_expansions([groups[name] for name in GROUPS[gamma + 1 :]])
        group = groups[group_name]
        inner, outer_tail, outer_self = commutators[gamma]
        for source in sources:
            state = {source: (Fraction(1), Fraction(0))}
            direct_inner = _direct_inner_action(tail, group, state, counter)
            direct_tail = _direct_outer_action(tail, tail, group, state, counter)
            direct_self = _direct_outer_action(group, tail, group, state, counter)
            expansion_actions = (
                _apply_operator(inner, state, counter),
                _apply_operator(outer_tail, state, counter),
                _apply_operator(outer_self, state, counter),
            )
            direct_actions = (direct_inner, direct_tail, direct_self)
            for family, direct, expanded in zip(
                ("inner", "tail_nested", "self_nested"),
                direct_actions,
                expansion_actions,
            ):
                if direct != expanded:
                    raise VerificationError(
                        f"L{linear_size} sparse-action oracle mismatch for {group_name} {family}"
                    )
                records.append(
                    {
                        "group": group_name,
                        "family": family,
                        "source": hex(source),
                        "action_sha256": canonical_sha256(_action_record(expanded)),
                    }
                )
    return {
        "status": "VERIFIED_INDEPENDENT_SPARSE_ACTION_ORACLE",
        "coverage": coverage,
        "basis_state_count": len(sources),
        "operator_action_comparison_count": len(records),
        "action_records_sha256": canonical_sha256(records),
    }


def _minimum_steps_for_bound(coefficient: Fraction, multiplier: int) -> int:
    """Least R with ``multiplier*C/R^2 <= allocation``, using integers."""

    if type(multiplier) is not int or multiplier not in (1, 2):
        raise SchemaError("bound multiplier must be integer 1 or 2")
    numerator = multiplier * coefficient.numerator * OBSERVABLE_ALLOCATION.denominator
    denominator = coefficient.denominator * OBSERVABLE_ALLOCATION.numerator
    candidate = math.isqrt((numerator + denominator - 1) // denominator)
    while multiplier * coefficient / (candidate * candidate) > OBSERVABLE_ALLOCATION:
        candidate += 1
    while candidate > 1 and multiplier * coefficient / ((candidate - 1) ** 2) <= OBSERVABLE_ALLOCATION:
        candidate -= 1
    return candidate


def _profile_summary(linear_size: int) -> Dict[str, Any]:
    groups = canonical_group_expansions(linear_size)
    pair_counts = _verify_internal_commutation(groups)
    counter = ComputationCounter()
    records: List[Dict[str, Any]] = []
    commutators: List[Tuple[Expansion, Expansion, Expansion]] = []
    tail_l1_sum = Fraction(0)
    self_l1_sum = Fraction(0)
    for gamma, group_name in enumerate(GROUPS):
        tail_names = GROUPS[gamma + 1 :]
        tail = _merge_expansions([groups[name] for name in tail_names])
        inner = exact_commutator(tail, groups[group_name], counter)
        outer_tail = exact_commutator(tail, inner, counter)
        outer_self = exact_commutator(groups[group_name], inner, counter)
        _pure_axis_l1(inner, "imag")
        tail_l1 = _pure_axis_l1(outer_tail, "real")
        self_l1 = _pure_axis_l1(outer_self, "real")
        tail_l1_sum += tail_l1
        self_l1_sum += self_l1
        commutators.append((inner, outer_tail, outer_self))
        records.append(
            {
                "group": group_name,
                "tail_groups": list(tail_names),
                "tail_term_count": len(tail),
                "inner_term_count": len(inner),
                "tail_nested_term_count": len(outer_tail),
                "self_nested_term_count": len(outer_self),
                "tail_nested_l1": format_fraction(tail_l1),
                "self_nested_l1": format_fraction(self_l1),
                "inner_sha256": _expansion_sha256(inner),
                "tail_nested_sha256": _expansion_sha256(outer_tail),
                "self_nested_sha256": _expansion_sha256(outer_self),
            }
        )
    coefficient = tail_l1_sum / 12 + self_l1_sum / 24
    unitary_bound = coefficient * TOTAL_TIME**3 / TROTTER_STEPS**2
    generic_observable_bound = 2 * unitary_bound
    action_oracle = _verify_action_oracle(
        linear_size, groups, commutators, counter
    )
    minimum_unitary_steps = _minimum_steps_for_bound(coefficient, 1)
    minimum_observable_steps = _minimum_steps_for_bound(coefficient, 2)
    group_records = {
        group: {
            "term_count": len(groups[group]),
            "pairwise_commutation_pair_count": pair_counts[group],
            "expansion_sha256": _expansion_sha256(groups[group]),
        }
        for group in GROUPS
    }
    raw_s2_binding = _raw_s2_binding_records(groups)
    identity_coefficient = U_OVER_T / 4 * linear_size * linear_size
    return {
        "profile_id": f"L{linear_size}_OBC_R100",
        "linear_size": linear_size,
        "n_qubits": 2 * linear_size * linear_size,
        "total_time": "1/1",
        "trotter_steps": TROTTER_STEPS,
        "group_records": group_records,
        "total_nonidentity_term_count": sum(len(value) for value in groups.values()),
        "group_internal_pairwise_commutation_verified": True,
        "raw_s2_binding": raw_s2_binding,
        "identity_phase_ledger": {
            "omitted_HU_identity_coefficient": format_fraction(identity_coefficient),
            "full_time_common_phase_exponent": format_fraction(
                TOTAL_TIME * identity_coefficient
            ),
            "status": (
                "FULL_AND_NONIDENTITY_REDUCED_EXACT_AND_S2_EVOLUTIONS_SHARE_"
                "THE_SAME_IDENTITY_PHASE_SO_OPERATOR_NORM_DIFFERENCE_IS_UNCHANGED"
            ),
        },
        "commutator_records": records,
        "tail_nested_l1_sum": format_fraction(tail_l1_sum),
        "self_nested_l1_sum": format_fraction(self_l1_sum),
        "one_step_commutator_coefficient_C": format_fraction(coefficient),
        "single_step_unitary_error_bound": format_fraction(
            coefficient / TROTTER_STEPS**3
        ),
        "R_step_unitary_error_bound": format_fraction(unitary_bound),
        "generic_norm_one_observable_error_bound": format_fraction(
            generic_observable_bound
        ),
        "per_observable_allocation": format_fraction(OBSERVABLE_ALLOCATION),
        "per_observable_allocation_satisfied_at_R100": (
            generic_observable_bound <= OBSERVABLE_ALLOCATION
        ),
        "minimum_R_for_unitary_error_allocation": minimum_unitary_steps,
        "minimum_R_for_generic_norm_one_observable_allocation": minimum_observable_steps,
        "action_oracle": action_oracle,
        "resource_usage": {
            "commutator_pair_products": counter.commutator_pair_products,
            "action_term_applications": counter.action_term_applications,
        },
    }


def expected_profile_summaries() -> List[Dict[str, Any]]:
    global _PROFILE_CACHE_BYTES
    if _PROFILE_CACHE_BYTES is not None:
        # Decode a fresh copy so callers cannot mutate the cached evidence.
        return json.loads(_PROFILE_CACHE_BYTES.decode("ascii"))
    summaries = [_profile_summary(linear_size) for linear_size in PROFILE_SIZES]
    expected_counts = {
        2: {"H1": 8, "H2": 0, "HU": 12, "H3": 0, "H4": 8},
        3: {"H1": 12, "H2": 12, "HU": 27, "H3": 12, "H4": 12},
        8: {"H1": 128, "H2": 96, "HU": 192, "H3": 96, "H4": 128},
    }
    for summary in summaries:
        counts = {
            group: summary["group_records"][group]["term_count"] for group in GROUPS
        }
        if counts != expected_counts[summary["linear_size"]]:
            raise VerificationError("fixed group term-count invariant failed")
    _PROFILE_CACHE_BYTES = json.dumps(
        summaries,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return json.loads(_PROFILE_CACHE_BYTES.decode("ascii"))


def _matmul(left: Sequence[Sequence[complex]], right: Sequence[Sequence[complex]]) -> List[List[complex]]:
    return [
        [sum(left[i][k] * right[k][j] for k in range(2)) for j in range(2)]
        for i in range(2)
    ]


def _pauli_exponential(pauli: Sequence[Sequence[complex]], time: float) -> List[List[complex]]:
    cosine = math.cos(time)
    sine = math.sin(time)
    return [
        [((1 if i == j else 0) * cosine - 1j * sine * pauli[i][j]) for j in range(2)]
        for i in range(2)
    ]


def _spectral_norm_2x2(matrix: Sequence[Sequence[complex]]) -> float:
    a = sum(abs(matrix[row][0]) ** 2 for row in range(2))
    d = sum(abs(matrix[row][1]) ** 2 for row in range(2))
    b = sum(matrix[row][0].conjugate() * matrix[row][1] for row in range(2))
    largest = (a + d + math.sqrt(max(0.0, (a - d) ** 2 + 4 * abs(b) ** 2))) / 2
    return math.sqrt(max(0.0, largest))


def numerical_formula_oracle() -> Dict[str, Any]:
    """Independent direct 2x2 X/Z S2 error check at t=0.1."""

    x = [[0j, 1 + 0j], [1 + 0j, 0j]]
    z = [[1 + 0j, 0j], [0j, -1 + 0j]]
    time = 0.1
    s2 = _matmul(
        _matmul(_pauli_exponential(x, time / 2), _pauli_exponential(z, time)),
        _pauli_exponential(x, time / 2),
    )
    norm = math.sqrt(2.0)
    exact = [
        [
            (1 if i == j else 0) * math.cos(norm * time)
            - 1j * math.sin(norm * time) / norm * (x[i][j] + z[i][j])
            for j in range(2)
        ]
        for i in range(2)
    ]
    difference = [[s2[i][j] - exact[i][j] for j in range(2)] for i in range(2)]
    actual = _spectral_norm_2x2(difference)
    bound = 0.0005  # (4/12 + 4/24) * (1/10)^3.
    if not actual < bound:
        raise VerificationError("independent two-by-two Strang formula oracle failed")
    return {
        "status": "VERIFIED_DIRECT_2X2_NUMERICAL_ORACLE",
        "hamiltonians": "H1=X,H2=Z",
        "step_duration": "1/10",
        "nested_norms": {"tail_family": "4/1", "self_family": "4/1"},
        "theorem_bound": "1/2000",
        "direct_spectral_error_decimal": format(actual, ".17g"),
        "direct_error_strictly_below_bound": True,
        "floating_point_role": "ORACLE_ONLY_NOT_USED_IN_CERTIFIED_EXACT_BOUNDS",
    }


def _load_module_from_verified_bytes(payload: bytes, path: Path, name: str) -> Any:
    """Compile exactly the bytes that were hashed; never consult a pyc."""

    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    exec(compile(payload, str(path), "exec"), module.__dict__)
    return module


def _strict_json_from_verified_bytes(payload: bytes, name: str) -> Any:
    if len(payload) > RESOURCE_LIMITS["max_json_bytes"]:
        raise SchemaError(f"pinned {name} exceeds JSON byte cap")
    try:
        return json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant: {value}")
            ),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        raise SchemaError(f"pinned {name} is not strict JSON") from exc


def _verified_source_bytes(source_pins: Any) -> Dict[str, bytes]:
    if not isinstance(source_pins, list) or len(source_pins) != len(SOURCE_PINS):
        raise SchemaError("contract.source_pins must contain the exact pinned list")
    if not _strict_equal(source_pins, list(SOURCE_PINS)):
        raise SchemaError("contract.source_pins do not match checker policy")
    directory = Path(__file__).resolve().parent
    output: Dict[str, bytes] = {}
    for pin in SOURCE_PINS:
        path = directory / pin["relative_path"]
        with path.open("rb") as handle:
            payload = handle.read(RESOURCE_LIMITS["max_pinned_source_bytes"] + 1)
        if len(payload) > RESOURCE_LIMITS["max_pinned_source_bytes"]:
            raise SchemaError(f"pinned source exceeds byte cap: {pin['relative_path']}")
        if hashlib.sha256(payload).hexdigest() != pin["sha256"]:
            raise SchemaError(f"source pin drift: {pin['relative_path']}")
        output[pin["relative_path"]] = payload
    return output


def verify_pinned_cross_sources(source_pins: Any) -> Dict[str, Any]:
    """Hash first, then execute narrow cross-checks against pinned sources."""

    sources = _verified_source_bytes(source_pins)
    directory = Path(__file__).resolve().parent
    mapping_path = directory / "hubbard_jw_mapping_validator.py"
    mapping_source = sources["hubbard_jw_mapping_validator.py"]
    mapping = _load_module_from_verified_bytes(
        mapping_source, mapping_path, "pinned_hubbard_mapping"
    )
    # Its self-source pin must refer to the already verified bytes, not a second read.
    mapping.checker_source_sha256 = lambda: hashlib.sha256(mapping_source).hexdigest()
    mapping_contract = _strict_json_from_verified_bytes(
        sources["hubbard_jw_mapping_contract.json"], "mapping contract"
    )
    mapping_template = _strict_json_from_verified_bytes(
        sources["hubbard_jw_mapping_template.json"], "mapping template"
    )
    if mapping.validate_contract(mapping_contract):
        raise VerificationError("pinned mapping contract no longer verifies")
    mapping_result = mapping.verify_certificate(mapping_contract, mapping_template)
    if mapping_result.get("status") != "VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE":
        raise VerificationError("pinned mapping template no longer verifies")
    mapping_digests: Dict[str, str] = {}
    for linear_size in (2, 3):
        expected = canonical_group_expansions(linear_size)
        actual: Dict[str, Expansion] = {group: {} for group in GROUPS}
        for term in mapping.canonical_terms(linear_size):
            if set(term["pauli"]) == {"I"}:
                continue
            key = _string_to_masks(term["pauli"])
            coefficient = mapping.parse_fraction(term["coefficient"])
            _add_term(actual[term["group"]], key, (coefficient, Fraction(0)))
        if actual != expected:
            raise VerificationError(f"pinned mapping disagrees at L={linear_size}")
        mapping_digests[f"L{linear_size}"] = canonical_sha256(
            {group: _expansion_records(actual[group]) for group in GROUPS}
        )

    bitset = _load_module_from_verified_bytes(
        sources["pauli_bitset_backend.py"],
        directory / "pauli_bitset_backend.py",
        "pinned_pauli_bitset",
    )
    symbols = "IXYZ"
    for left_symbol in symbols:
        for right_symbol in symbols:
            left = _string_to_masks(left_symbol)
            right = _string_to_masks(right_symbol)
            if bitset.pauli_string_to_masks(left_symbol) != left:
                raise VerificationError("pinned bitset conversion disagrees")
            if bitset.pauli_multiply(left, right, 1) != _pauli_multiply(left, right):
                raise VerificationError("pinned bitset multiplication disagrees")
            if bitset.pauli_commutes(left, right, 1) != _pauli_commutes(left, right):
                raise VerificationError("pinned bitset commutation disagrees")
    return {
        "status": "VERIFIED_HASHED_CROSS_SOURCE_CONFORMANCE",
        "mapping_template_status": mapping_result["status"],
        "mapping_group_expansion_digests": mapping_digests,
        "bitset_single_qubit_product_checks": 16,
    }


def _validate_contract_impl(contract: Any) -> List[str]:
    try:
        item = _exact_keys(
            contract,
            (
                "schema_version",
                "contract_fingerprint",
                "certificate_type",
                "checker_fingerprint",
                "checker_source_sha256",
                "source_pins",
                "bound_source",
                "profile_policy",
                "expected_profiles",
                "numerical_formula_oracle",
                "resource_limits",
                "maximum_positive_status",
                "scope_claims",
            ),
            "contract",
        )
        if type(item["schema_version"]) is not int or item["schema_version"] != 1:
            raise SchemaError("contract.schema_version must be integer 1")
        for field, expected in (
            ("contract_fingerprint", CONTRACT_FINGERPRINT),
            ("certificate_type", CERTIFICATE_TYPE),
            ("checker_fingerprint", CHECKER_FINGERPRINT),
            ("maximum_positive_status", MAXIMUM_POSITIVE_STATUS),
            ("bound_source", BOUND_SOURCE),
            ("profile_policy", PROFILE_POLICY),
            ("resource_limits", RESOURCE_LIMITS),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(item[field], expected):
                raise SchemaError(f"contract.{field} does not match checker policy")
        if (
            type(item["checker_source_sha256"]) is not str
            or not SHA256_RE.fullmatch(item["checker_source_sha256"])
            or item["checker_source_sha256"] != checker_source_sha256()
        ):
            raise SchemaError("contract.checker_source_sha256 does not pin this checker")
        verify_pinned_cross_sources(item["source_pins"])
        expected_profiles = expected_profile_summaries()
        if not _strict_equal(item["expected_profiles"], expected_profiles):
            raise SchemaError("contract.expected_profiles disagree with recomputation")
        oracle = numerical_formula_oracle()
        if not _strict_equal(item["numerical_formula_oracle"], oracle):
            raise SchemaError("contract.numerical_formula_oracle disagrees with recomputation")
    except (
        SchemaError,
        VerificationError,
        KeyError,
        TypeError,
        OSError,
        ValueError,
        RecursionError,
    ) as exc:
        return [str(exc)]
    return []


def validate_contract(contract: Any) -> List[str]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _validate_contract_impl(contract)
    try:
        return _execute_from_verified_self_source("_validate_contract_impl", contract)
    except (
        SchemaError,
        VerificationError,
        KeyError,
        TypeError,
        OSError,
        ValueError,
        RecursionError,
    ) as exc:
        return [str(exc)]


def _verify_certificate_impl(contract: Any, certificate: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "status": "INVALID_SCHEMA",
        "verified": False,
        "ready_gate_eligible": False,
        "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
        "errors": [],
    }
    contract_errors = _validate_contract_impl(contract)
    if contract_errors:
        result["errors"] = contract_errors
        return result
    try:
        item = _exact_keys(
            certificate,
            (
                "schema_version",
                "certificate_type",
                "contract_fingerprint",
                "bound_source",
                "profile_policy",
                "profile_claims",
                "numerical_formula_oracle",
                "scope_claims",
            ),
            "certificate",
        )
        if type(item["schema_version"]) is not int or item["schema_version"] != 1:
            raise SchemaError("certificate.schema_version must be integer 1")
        for field, expected in (
            ("certificate_type", CERTIFICATE_TYPE),
            ("contract_fingerprint", CONTRACT_FINGERPRINT),
            ("bound_source", BOUND_SOURCE),
            ("profile_policy", PROFILE_POLICY),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(item[field], expected):
                raise SchemaError(f"certificate.{field} does not match contract policy")
        if not isinstance(item["profile_claims"], list) or len(item["profile_claims"]) != 3:
            raise SchemaError("certificate.profile_claims must contain exactly L2,L3,L8")
        recomputed = expected_profile_summaries()
        if not _strict_equal(item["profile_claims"], recomputed):
            raise VerificationError("certificate.profile_claims disagree with recomputation")
        if not _strict_equal(item["profile_claims"], contract["expected_profiles"]):
            raise VerificationError("certificate.profile_claims disagree with contract pins")
        oracle = numerical_formula_oracle()
        if not _strict_equal(item["numerical_formula_oracle"], oracle):
            raise VerificationError("certificate numerical oracle disagrees")
        if not _strict_equal(item["numerical_formula_oracle"], contract["numerical_formula_oracle"]):
            raise VerificationError("certificate numerical oracle disagrees with contract")
        cross_sources = verify_pinned_cross_sources(contract["source_pins"])
    except SchemaError as exc:
        result["errors"] = [str(exc)]
        return result
    except (
        VerificationError,
        ResourceLimitError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
    ) as exc:
        result["status"] = "VERIFICATION_FAILED"
        result["errors"] = [str(exc)]
        return result
    result.update(
        {
            "status": MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "scope_claims": dict(SCOPE_CLAIMS),
            "checker_executed_source_bytes_sha256_verified": True,
            "cross_source_conformance": cross_sources,
            "recomputed_profiles": recomputed,
            "numerical_formula_oracle": oracle,
            "limitations": [
                "The exact results are coefficient-L1 upper bounds, not exact spectral norms.",
                "The mapping subcertificate is cross-checked but not composed into this status.",
                "The observable comparison uses only the generic 2*unitary-error factor for norm at most one.",
                "No observable-specific cancellation or tightening is assessed.",
                "No truncation certificate or physical L=8 identity is composed.",
                "Failure to meet the allocation cannot qualify a reference or READY gate.",
            ],
            "errors": [],
        }
    )
    return result


def verify_certificate(contract: Any, certificate: Any) -> Dict[str, Any]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _verify_certificate_impl(contract, certificate)
    try:
        return _execute_from_verified_self_source(
            "_verify_certificate_impl", contract, certificate
        )
    except (
        SchemaError,
        VerificationError,
        KeyError,
        TypeError,
        OSError,
        ValueError,
        RecursionError,
    ) as exc:
        return {
            "status": "INVALID_SCHEMA",
            "verified": False,
            "ready_gate_eligible": False,
            "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
            "errors": [str(exc)],
        }


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def load_strict_json(path: Path, maximum_bytes: int = RESOURCE_LIMITS["max_json_bytes"]) -> Any:
    if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= RESOURCE_LIMITS["max_json_bytes"]:
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
    # This narrow subcertificate can never qualify a physical reference/READY gate.
    return 1


if __name__ == "__main__":
    sys.exit(main())
