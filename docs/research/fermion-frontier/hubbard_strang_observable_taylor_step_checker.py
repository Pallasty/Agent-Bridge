#!/usr/bin/env python3
"""Exact one-step observable Taylor-L1 subcertificate for fixed Hubbard Strang.

The checker specializes the iterated integral-Taylor remainder of Fang--Qu,
Eq. (3.9), to the fixed nine-stage L2/L3/L8 OBC Hubbard Strang step.  It
verifies the formal degree-zero through degree-two cancellation, exactly merges
the degree-three Heisenberg defect D3, and enumerates all 495 degree-four weak
compositions.  Pauli coefficient L1 then gives a rigorous operator-norm upper
bound for *one* step of duration 1/100 acting on each initial observable.

This is intentionally not a full R=100 error certificate.  Correct telescoping
applies the one-step defect to evolved observables O_k.  Multiplying the initial
O bound by 100 is not an error bound; it is only a lower floor on a proposed
uniform-supremum certificate architecture because that supremum includes k=0.
The CLI always exits 1 and never qualifies a reference or READY state.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
import types
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


HERE = Path(__file__).resolve().parent
MAXIMUM_POSITIVE_STATUS = "VERIFIED_ONE_STEP_OBSERVABLE_TAYLOR_L1_SUBCERTIFICATE"
BASE_POSITIVE_STATUS = "VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE"
CHECKER_FINGERPRINT = "hubbard_strang_observable_taylor_step_checker_v1"

GROUPS = ("H1", "H2", "HU", "H3", "H4")
STAGES = (
    ("H1", Fraction(1, 2)),
    ("H2", Fraction(1, 2)),
    ("HU", Fraction(1, 2)),
    ("H3", Fraction(1, 2)),
    ("H4", Fraction(1, 1)),
    ("H3", Fraction(1, 2)),
    ("HU", Fraction(1, 2)),
    ("H2", Fraction(1, 2)),
    ("H1", Fraction(1, 2)),
)
PROFILE_SIZES = (2, 3, 8)
OBSERVABLES = ("staggered_magnetization", "double_occupancy")
STEP_DURATION = Fraction(1, 100)
TROTTER_STEPS = 100
OBSERVABLE_ALLOCATION = Fraction(1, 4000)
UNIFORM_LEADING_COEFFICIENT_CEILING = OBSERVABLE_ALLOCATION * TROTTER_STEPS**2

BOUND_SOURCE = {
    "authors": "Di Fang and Conrad Qu",
    "title": (
        "Uniform Semiclassical Observable Error Bound of Trotter-Suzuki "
        "Splitting: A Simple Algebraic Proof"
    ),
    "journal": "SIAM Journal on Numerical Analysis 64 (2026)",
    "doi": "10.1137/25M1777098",
    "arxiv_version": "2507.02783v2",
    "result": "Proposition 2.5 and iterated integral-Taylor remainder Equation 3.9",
    "audited_pdf_sha256": (
        "c1afaae4a944ba5c32bb5c86e421986bbcd89c14dae959d73560db979e668806"
    ),
    "specialization": (
        "explicit positive coefficients for the fixed nine-stage five-group "
        "Strang Heisenberg map; all hidden constants are replaced by exact "
        "degree-three and degree-four Fraction ledgers"
    ),
}

SOURCE_PINS = (
    {
        "relative_path": "hubbard_strang_commutator_checker.py",
        "role": "exact_Pauli_Hubbard_backend_and_positive_base_checker",
        "sha256": "e3144590c0e00bb2bd69bc50b1bdf3d7d6c3043c8697d5050202404590138fa7",
    },
    {
        "relative_path": "hubbard_strang_commutator_contract.json",
        "role": "positive_base_contract",
        "sha256": "44bc15474b7964d94db6cd79fb7bce3255d1c8f9bb181ddada8dc294cdb428c1",
    },
    {
        "relative_path": "hubbard_strang_commutator_template.json",
        "role": "positive_base_certificate",
        "sha256": "ba42851a7bad6fa117df8bfa4d8f6f7c261f11175a6df4bb673614b5cdbba572",
    },
)

RESOURCE_LIMITS = {
    "max_pinned_source_bytes": 1_048_576,
    "max_qubits": 128,
    "max_pair_products": 180_000_000,
    "max_expansion_terms": 200_000,
    "max_cached_prefixes": 256,
    "max_action_outputs": 20_000,
    "max_rational_digits": 256,
}

SCOPE_CLAIMS = {
    "base_commutator_subcertificate_source_pinned_and_verified": True,
    "fixed_L2_L3_L8_observable_definitions_exactly_generated": True,
    "fixed_nine_stage_Strang_composition_verified": True,
    "formal_degree_zero_one_two_residuals_exactly_zero": True,
    "degree_three_observable_defect_exactly_recomputed": True,
    "all_495_degree_four_product_remainder_paths_exactly_enumerated": True,
    "initial_observable_single_step_operator_error_upper_bound_verified": True,
    "initial_Neel_single_step_expectation_error_upper_bound_verified": True,
    "L8_degree_three_Neel_sector_action_verified": True,
    "uniform_supremum_Pauli_L1_Taylor_architecture_infeasible_at_R100_verified": True,
    "checker_self_source_same_byte_contract_pinned": False,
    "paper_pdf_bytes_loaded_by_checker": False,
    "full_R100_observable_error_upper_bound": (
        "NOT_ASSESSED_EVOLVED_OBSERVABLE_UNIFORMITY_REQUIRED"
    ),
    "actual_R100_observable_error_lower_bounded": False,
    "per_step_evolved_observable_ledger": "NOT_ASSESSED",
    "cross_step_cancellation": "NOT_ASSESSED",
    "fermionic_Lieb_Robinson_adaptation": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}

Gaussian = Tuple[Fraction, Fraction]
PauliKey = Tuple[int, int]
Expansion = Dict[PauliKey, Gaussian]


class VerificationError(ValueError):
    """Exact invariant, source pin, or resource policy failed."""


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _read_pinned(path: Path, expected_sha256: str) -> bytes:
    with path.open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_pinned_source_bytes"] + 1)
    if len(payload) > RESOURCE_LIMITS["max_pinned_source_bytes"]:
        raise VerificationError(f"pinned source exceeds byte cap: {path.name}")
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise VerificationError(f"source pin drift: {path.name}")
    return payload


def _load_backend() -> Any:
    sources = _verify_source_pins()
    source = sources["hubbard_strang_commutator_checker.py"]
    backend = types.ModuleType("pinned_hubbard_strang_for_observable_taylor")
    backend.__file__ = str(HERE / "hubbard_strang_commutator_checker.py")
    backend.__package__ = ""
    backend.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = source
    exec(compile(source, backend.__file__, "exec"), backend.__dict__)
    contract = json.loads(sources["hubbard_strang_commutator_contract.json"])
    certificate = json.loads(sources["hubbard_strang_commutator_template.json"])
    result = backend.verify_certificate(contract, certificate)
    if result.get("status") != BASE_POSITIVE_STATUS or result.get("verified") is not True:
        raise VerificationError("pinned base commutator certificate is not positive")
    return backend


def _verify_source_pins() -> Dict[str, bytes]:
    return {
        pin["relative_path"]: _read_pinned(HERE / pin["relative_path"], pin["sha256"])
        for pin in SOURCE_PINS
    }


def _verify_stage_binding(backend: Any) -> Dict[str, Any]:
    collapsed: list[Tuple[str, Fraction]] = []
    for group_name in backend.RAW_S2_ORDER:
        if collapsed and collapsed[-1][0] == group_name:
            previous_group, previous_coefficient = collapsed[-1]
            collapsed[-1] = (previous_group, previous_coefficient + Fraction(1, 2))
        else:
            collapsed.append((group_name, Fraction(1, 2)))
    if tuple(collapsed) != STAGES:
        raise VerificationError("nine-stage composition does not bind pinned raw S2 order")
    records = [
        {"group": group, "coefficient": f"{coefficient.numerator}/{coefficient.denominator}"}
        for group, coefficient in collapsed
    ]
    return {
        "pinned_raw_event_order": list(backend.RAW_S2_ORDER),
        "collapsed_nine_stage_records_sha256": canonical_sha256(records),
        "consecutive_central_H4_half_steps_exactly_combined": True,
    }


class ComputationCounter:
    def __init__(self) -> None:
        self.pair_products = 0
        self.peak_terms = 0

    def reserve_pairs(self, pairs: int) -> None:
        self.pair_products += pairs
        if self.pair_products > RESOURCE_LIMITS["max_pair_products"]:
            raise VerificationError("commutator pair-product cap exceeded")

    def observe_terms(self, terms: int) -> None:
        self.peak_terms = max(self.peak_terms, terms)
        if terms > RESOURCE_LIMITS["max_expansion_terms"]:
            raise VerificationError("commutator expansion-term cap exceeded")


def _commutator(
    backend: Any, left: Mapping[PauliKey, Gaussian], right: Mapping[PauliKey, Gaussian],
    counter: ComputationCounter,
) -> Expansion:
    counter.reserve_pairs(len(left) * len(right))
    output: Expansion = {}
    for left_key, left_coefficient in left.items():
        for right_key, right_coefficient in right.items():
            if backend._pauli_commutes(left_key, right_key):
                continue
            phase, key = backend._pauli_multiply(left_key, right_key)
            coefficient = backend._g_scale(
                backend._g_i_power(
                    backend._g_mul(left_coefficient, right_coefficient), phase
                ),
                Fraction(2),
            )
            backend._add_term(output, key, coefficient)
        counter.observe_terms(len(output))
    counter.observe_terms(len(output))
    return output


def _repeated_ad(
    backend: Any, operator: Mapping[PauliKey, Gaussian], observable: Expansion,
    power: int, counter: ComputationCounter,
) -> Expansion:
    output = dict(observable)
    for _ in range(power):
        output = _commutator(backend, operator, output, counter)
    return output


def _add_scaled(
    backend: Any, destination: Expansion, source: Mapping[PauliKey, Gaussian],
    scalar: Gaussian,
) -> None:
    for key, coefficient in source.items():
        backend._add_term(destination, key, backend._g_mul(coefficient, scalar))


def _i_scalar(backend: Any, power: int, value: Fraction) -> Gaussian:
    return backend._g_i_power((value, Fraction(0)), power)


def _l1(expansion: Mapping[PauliKey, Gaussian]) -> Fraction:
    return sum((abs(real) + abs(imaginary) for real, imaginary in expansion.values()), Fraction(0))


def _format_fraction(backend: Any, value: Fraction) -> str:
    if (
        len(str(abs(value.numerator))) > RESOURCE_LIMITS["max_rational_digits"]
        or len(str(value.denominator)) > RESOURCE_LIMITS["max_rational_digits"]
    ):
        raise VerificationError("rational digit cap exceeded")
    return backend.format_fraction(value)


def _observable_expansion(
    backend: Any, linear_size: int, observable_id: str
) -> Tuple[Expansion, Dict[str, Any]]:
    n_sites = linear_size * linear_size
    n_qubits = 2 * n_sites
    if n_qubits > RESOURCE_LIMITS["max_qubits"]:
        raise VerificationError("observable qubit cap exceeded")
    output: Expansion = {}
    if observable_id == "staggered_magnetization":
        for site in range(n_sites):
            row, column = divmod(site, linear_size)
            sign = 1 if (row + column) % 2 == 0 else -1
            backend._add_term(
                output, (0, 1 << (2 * site)),
                (Fraction(-sign, 2 * n_sites), Fraction(0)),
            )
            backend._add_term(
                output, (0, 1 << (2 * site + 1)),
                (Fraction(sign, 2 * n_sites), Fraction(0)),
            )
        identity = Fraction(0)
        definition = "(1/N)*sum_(-1)^(r+c)*(n_up-n_down)"
    elif observable_id == "double_occupancy":
        for site in range(n_sites):
            backend._add_term(
                output, (0, 1 << (2 * site)),
                (Fraction(-1, 4 * n_sites), Fraction(0)),
            )
            backend._add_term(
                output, (0, 1 << (2 * site + 1)),
                (Fraction(-1, 4 * n_sites), Fraction(0)),
            )
            backend._add_term(
                output, (0, (1 << (2 * site)) | (1 << (2 * site + 1))),
                (Fraction(1, 4 * n_sites), Fraction(0)),
            )
        identity = Fraction(1, 4)
        definition = "(1/N)*sum_n_up*n_down"
    else:
        raise VerificationError("unknown observable")
    full_l1 = _l1(output) + abs(identity)
    if full_l1 != 1:
        raise VerificationError("normalized observable Pauli L1 must equal one")
    ledger = {
        "observable_id": observable_id,
        "definition": definition,
        "n_sites": n_sites,
        "nonidentity_term_count": len(output),
        "omitted_commuting_identity_coefficient": _format_fraction(backend, identity),
        "full_observable_Pauli_L1": _format_fraction(backend, full_l1),
        "nonidentity_expansion_sha256": backend._expansion_sha256(output),
    }
    return output, ledger


def _formal_product_coefficients(
    backend: Any, groups: Mapping[str, Expansion], observable: Expansion,
    counter: ComputationCounter,
) -> list[Expansion]:
    polynomial: list[Expansion] = [dict(observable), {}, {}, {}]
    for group_name, stage_coefficient in STAGES:
        updated: list[Expansion] = [{}, {}, {}, {}]
        for degree, expansion in enumerate(polynomial):
            nested = dict(expansion)
            for power in range(4 - degree):
                if power:
                    nested = _commutator(
                        backend, groups[group_name], nested, counter
                    )
                scalar = _i_scalar(
                    backend,
                    power,
                    stage_coefficient**power / math.factorial(power),
                )
                _add_scaled(backend, updated[degree + power], nested, scalar)
        polynomial = updated
    return polynomial


def _ideal_coefficients(
    backend: Any, hamiltonian: Expansion, observable: Expansion,
    counter: ComputationCounter,
) -> list[Expansion]:
    output: list[Expansion] = []
    nested = dict(observable)
    for degree in range(4):
        if degree:
            nested = _commutator(backend, hamiltonian, nested, counter)
        coefficient = _i_scalar(backend, degree, Fraction(1, math.factorial(degree)))
        scaled: Expansion = {}
        _add_scaled(backend, scaled, nested, coefficient)
        output.append(scaled)
    return output


def _subtract(backend: Any, left: Expansion, right: Expansion) -> Expansion:
    output = dict(left)
    _add_scaled(backend, output, right, (Fraction(-1), Fraction(0)))
    return output


def _product_fourth_remainder(
    backend: Any, groups: Mapping[str, Expansion], observable: Expansion,
    counter: ComputationCounter,
) -> Tuple[Fraction, Dict[str, Any]]:
    cache: Dict[Tuple[int, ...], Expansion] = {(): dict(observable)}
    total = Fraction(0)
    records: list[Dict[str, Any]] = []
    maximum_path_terms = 0
    for sequence in itertools.combinations_with_replacement(range(len(STAGES)), 4):
        prefix: Tuple[int, ...] = ()
        final: Expansion | None = None
        for stage_index in sequence:
            next_prefix = prefix + (stage_index,)
            if len(next_prefix) < 4:
                if next_prefix not in cache:
                    if len(cache) >= RESOURCE_LIMITS["max_cached_prefixes"]:
                        raise VerificationError("fourth-order prefix-cache cap exceeded")
                    cache[next_prefix] = _commutator(
                        backend,
                        groups[STAGES[stage_index][0]],
                        cache[prefix],
                        counter,
                    )
                final = cache[next_prefix]
            else:
                final = _commutator(
                    backend,
                    groups[STAGES[stage_index][0]],
                    cache[prefix],
                    counter,
                )
            prefix = next_prefix
        if final is None:
            raise VerificationError("empty fourth-order path")
        multiplicities = Counter(sequence)
        weight = Fraction(1)
        for stage_index, multiplicity in multiplicities.items():
            weight *= STAGES[stage_index][1] ** multiplicity
            weight /= math.factorial(multiplicity)
        path_l1 = _l1(final)
        weighted = weight * path_l1
        total += weighted
        maximum_path_terms = max(maximum_path_terms, len(final))
        records.append(
            {
                "stage_indices": list(sequence),
                "weight": _format_fraction(backend, weight),
                "nested_term_count": len(final),
                "nested_L1": _format_fraction(backend, path_l1),
                "weighted_L1": _format_fraction(backend, weighted),
            }
        )
    if len(cache) > RESOURCE_LIMITS["max_cached_prefixes"]:
        raise VerificationError("fourth-order prefix-cache cap exceeded")
    if len(records) != math.comb(12, 8):
        raise VerificationError("fourth-order weak-composition count mismatch")
    return total, {
        "weak_composition_count": len(records),
        "path_records_sha256": canonical_sha256(records),
        "cached_prefix_count": len(cache),
        "maximum_path_term_count": maximum_path_terms,
    }


def _neel_basis(linear_size: int) -> int:
    source = 0
    for row in range(linear_size):
        for column in range(linear_size):
            site = row * linear_size + column
            spin = 0 if (row + column) % 2 == 0 else 1
            source |= 1 << (2 * site + spin)
    return source


def _action_record(
    backend: Any, operator: Expansion, source: int, linear_size: int
) -> Dict[str, Any]:
    action: Dict[int, Gaussian] = {}
    for key, coefficient in operator.items():
        target, phase = backend._basis_pauli_action(key, source)
        contribution = backend._g_mul(coefficient, phase)
        action[target] = backend._g_add(
            action.get(target, (Fraction(0), Fraction(0))), contribution
        )
    action = {basis: amplitude for basis, amplitude in action.items() if amplitude != (0, 0)}
    if len(action) > RESOURCE_LIMITS["max_action_outputs"]:
        raise VerificationError("basis-action output cap exceeded")
    n_sites = linear_size * linear_size
    expected_up = sum((source >> (2 * site)) & 1 for site in range(n_sites))
    expected_down = sum((source >> (2 * site + 1)) & 1 for site in range(n_sites))
    for basis in action:
        up = sum((basis >> (2 * site)) & 1 for site in range(n_sites))
        down = sum((basis >> (2 * site + 1)) & 1 for site in range(n_sites))
        if up != expected_up or down != expected_down:
            raise VerificationError("D3 action escaped the fixed particle-spin sector")
    records = [
        {
            "basis": hex(basis),
            "real": _format_fraction(backend, amplitude[0]),
            "imag": _format_fraction(backend, amplitude[1]),
        }
        for basis, amplitude in sorted(action.items())
    ]
    norm_squared = sum(
        (real * real + imaginary * imaginary for real, imaginary in action.values()),
        Fraction(0),
    )
    expectation = action.get(source, (Fraction(0), Fraction(0)))
    if expectation[1] != 0:
        raise VerificationError("Hermitian D3 has non-real basis expectation")
    ceiling_squared = UNIFORM_LEADING_COEFFICIENT_CEILING**2
    return {
        "basis_integer_hex": hex(source),
        "particle_count": source.bit_count(),
        "spin_up_particle_count": expected_up,
        "spin_down_particle_count": expected_down,
        "nonzero_output_count": len(action),
        "action_records_sha256": canonical_sha256(records),
        "action_norm_squared": _format_fraction(backend, norm_squared),
        "basis_expectation": _format_fraction(backend, expectation[0]),
        "all_outputs_remain_in_fixed_particle_spin_sector": True,
        "uniform_leading_coefficient_ceiling_squared": _format_fraction(
            backend, ceiling_squared
        ),
        "action_norm_squared_to_ceiling_squared_ratio": _format_fraction(
            backend, norm_squared / ceiling_squared
        ),
        "exact_action_witness_exceeds_uniform_leading_ceiling": (
            norm_squared > ceiling_squared
        ),
    }


def _observable_record(
    backend: Any, linear_size: int, observable_id: str,
    groups: Mapping[str, Expansion], hamiltonian: Expansion,
    counter: ComputationCounter,
) -> Dict[str, Any]:
    observable, identity = _observable_expansion(backend, linear_size, observable_id)
    product = _formal_product_coefficients(backend, groups, observable, counter)
    ideal = _ideal_coefficients(backend, hamiltonian, observable, counter)
    residuals = [_subtract(backend, product[d], ideal[d]) for d in range(4)]
    if any(residuals[degree] for degree in range(3)):
        raise VerificationError("fixed Strang formal residual below degree three is nonzero")
    d3 = residuals[3]
    if any(imaginary != 0 for _, imaginary in d3.values()):
        raise VerificationError("degree-three Heisenberg defect is not Hermitian-real Pauli")
    d3_l1 = _l1(d3)
    ideal_fourth = _repeated_ad(backend, hamiltonian, observable, 4, counter)
    ideal_e4 = _l1(ideal_fourth) / 24
    product_p4, product_ledger = _product_fourth_remainder(
        backend, groups, observable, counter
    )
    remainder_fourth = ideal_e4 + product_p4
    single_step_operator_bound = (
        STEP_DURATION**3 * d3_l1 + STEP_DURATION**4 * remainder_fourth
    )
    action = _action_record(backend, d3, _neel_basis(linear_size), linear_size)
    expectation_numerator, expectation_denominator = action["basis_expectation"].split("/")
    expectation_value = Fraction(
        int(expectation_numerator), int(expectation_denominator)
    )
    initial_expectation_bound = (
        STEP_DURATION**3 * abs(expectation_value)
        + STEP_DURATION**4 * remainder_fourth
    )
    uniform_floor = TROTTER_STEPS * single_step_operator_bound
    return {
        "observable_identity": identity,
        "formal_residuals": [
            {
                "degree": degree,
                "term_count": len(residuals[degree]),
                "expansion_sha256": backend._expansion_sha256(residuals[degree]),
            }
            for degree in range(3)
        ],
        "degree_three_defect": {
            "term_count": len(d3),
            "coefficient_L1_operator_norm_upper_bound": _format_fraction(
                backend, d3_l1
            ),
            "expansion_sha256": backend._expansion_sha256(d3),
        },
        "degree_four_remainder": {
            "ideal_ad_H4_term_count": len(ideal_fourth),
            "ideal_E4_L1": _format_fraction(backend, ideal_e4),
            "ideal_ad_H4_expansion_sha256": backend._expansion_sha256(ideal_fourth),
            "product_P4_L1": _format_fraction(backend, product_p4),
            "total_E4_plus_P4_L1": _format_fraction(backend, remainder_fourth),
            **product_ledger,
        },
        "one_step_certificate": {
            "step_duration": _format_fraction(backend, STEP_DURATION),
            "operator_error_upper_bound": _format_fraction(
                backend, single_step_operator_bound
            ),
            "initial_Neel_expectation_error_upper_bound": _format_fraction(
                backend, initial_expectation_bound
            ),
            "per_observable_full_time_allocation": _format_fraction(
                backend, OBSERVABLE_ALLOCATION
            ),
            "one_step_bound_below_full_time_allocation": (
                single_step_operator_bound <= OBSERVABLE_ALLOCATION
            ),
            "does_not_certify_full_R100_error": True,
        },
        "uniform_supremum_architecture": {
            "required_evolved_observables": "O_k=exact_Heisenberg_step^k(O)",
            "initial_k0_floor_after_R_factor": _format_fraction(
                backend, uniform_floor
            ),
            "floor_to_allocation_ratio": _format_fraction(
                backend, uniform_floor / OBSERVABLE_ALLOCATION
            ),
            "uniform_supremum_Pauli_L1_architecture_cannot_qualify_at_R100": (
                uniform_floor > OBSERVABLE_ALLOCATION
            ),
            "used_as_actual_R100_error_bound": False,
        },
        "Neel_sector_degree_three_action": action,
    }


_EVIDENCE_CACHE_BYTES: bytes | None = None


def recompute_evidence() -> Dict[str, Any]:
    global _EVIDENCE_CACHE_BYTES
    if _EVIDENCE_CACHE_BYTES is not None:
        _verify_source_pins()
        return json.loads(_EVIDENCE_CACHE_BYTES.decode("ascii"))
    backend = _load_backend()
    stage_binding = _verify_stage_binding(backend)
    profiles: list[Dict[str, Any]] = []
    total_counter = ComputationCounter()
    for linear_size in PROFILE_SIZES:
        groups = backend.canonical_group_expansions(linear_size)
        hamiltonian = backend._merge_expansions([groups[name] for name in GROUPS])
        observables = [
            _observable_record(
                backend,
                linear_size,
                observable_id,
                groups,
                hamiltonian,
                total_counter,
            )
            for observable_id in OBSERVABLES
        ]
        profiles.append(
            {
                "profile_id": f"L{linear_size}_OBC_U8_delta_1_over_100",
                "linear_size": linear_size,
                "n_qubits": 2 * linear_size * linear_size,
                "group_order": list(GROUPS),
                "nine_stage_composition": [
                    {"group": group, "coefficient": _format_fraction(backend, coefficient)}
                    for group, coefficient in STAGES
                ],
                "observables": observables,
            }
        )
    result = {
        "checker_fingerprint": CHECKER_FINGERPRINT,
        "status": MAXIMUM_POSITIVE_STATUS,
        "verified": True,
        "ready_gate_eligible": False,
        "bound_source": BOUND_SOURCE,
        "source_pins": list(SOURCE_PINS),
        "stage_binding": stage_binding,
        "scope_claims": SCOPE_CLAIMS,
        "profiles": profiles,
        "resource_usage": {
            "commutator_pair_products": total_counter.pair_products,
            "peak_expansion_terms": total_counter.peak_terms,
        },
        "limitations": [
            "Only one step acting on each initial observable is upper-bounded.",
            "Full R=100 telescoping requires exact- or PF-evolved observables O_k.",
            "The uniform-supremum result is an architecture floor, not an actual-error lower bound.",
            "The paper PDF SHA is external audit metadata; PDF bytes are not loaded by this checker.",
            "This minimal checker pins its backend trio but does not yet have a same-byte self contract.",
            "No cross-step cancellation, locality adaptation, physical reference, or READY state is certified.",
        ],
    }
    _EVIDENCE_CACHE_BYTES = json.dumps(
        result, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return json.loads(_EVIDENCE_CACHE_BYTES.decode("ascii"))


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    try:
        result = recompute_evidence()
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        result = {
            "checker_fingerprint": CHECKER_FINGERPRINT,
            "status": "VERIFICATION_FAILED",
            "verified": False,
            "ready_gate_eligible": False,
            "scope_claims": {
                key: (False if value is True else value)
                for key, value in SCOPE_CLAIMS.items()
            },
            "errors": [str(exc)],
        }
    print(json.dumps(result, allow_nan=False, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    sys.exit(main())
