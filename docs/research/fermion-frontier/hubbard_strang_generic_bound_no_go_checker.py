#!/usr/bin/env python3
"""Exact infeasibility witness for the fixed L=8 generic Strang norm bound.

For the declared five-group order, Schubert--Mendl Proposition 2 defines a
nonnegative sum of nested-commutator norms.  R=100 and the per-observable allocation
1/4000 would require that coefficient C to satisfy C <= 5/4.

This checker selects just one summand,

    ||[K_1,[K_1,H_1]]|| / 12,

and lower-bounds its true spectral norm by applying the exact nested operator to one
normalized L=8 checkerboard-Neel computational-basis vector.  The exact squared
action norm is 295200, so the squared selected contribution is at least 2050,
strictly larger than (5/4)^2 = 25/16.  Since every other term in C is nonnegative,
even globally exact cluster spectral norms cannot make this fixed generic theorem
bound qualify at R=100.

This is a no-go for the *generic operator-norm bound expression*, not a lower bound
on actual product-formula error and not an observable-specific no-go.  It does not
compose truncation, a physical reference, or READY.  The CLI always exits 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import types
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
CERTIFICATE_TYPE = "hubbard_strang_fixed_generic_bound_infeasibility_witness_v1"
CONTRACT_FINGERPRINT = "hubbard_strang_generic_bound_no_go_contract_v1"
CHECKER_FINGERPRINT = "hubbard_strang_exact_basis_action_no_go_v1"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_GENERIC_STRANG_BOUND_INFEASIBILITY_WITNESS"
BASE_POSITIVE_STATUS = "VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE"

LINEAR_SIZE = 8
N_QUBITS = 128
GROUPS = ("H1", "H2", "HU", "H3", "H4")
TROTTER_STEPS = 100
OBSERVABLE_ALLOCATION = Fraction(1, 4000)
THEOREM_TERM_WEIGHT = Fraction(1, 12)

BOUND_SOURCE = {
    "authors": "Ansgar Schubert and Christian B. Mendl",
    "title": "Trotter error with commutator scaling for the Fermi-Hubbard model",
    "arxiv_version": "2306.10603v2",
    "doi": "10.1103/PhysRevB.108.195105",
    "result": "Proposition 2 Equation 13",
    "fixed_coefficient": (
        "C=sum_gamma(norm([K_gamma,[K_gamma,H_gamma]])/12"
        "+norm([H_gamma,[K_gamma,H_gamma]])/24)"
    ),
    "generic_observable_bound": "2*C*T^3/R^2 for norm(O)<=1",
}

UPSTREAM_CLUSTER_CONTEXT = {
    "official_repository": "https://github.com/qc-tum/fermi_hubbard_commutators",
    "paper_time_commit": "859bef092675957ae126e9d3b09dc3c63b213859",
    "hamiltonian_ops_relative_path": "fh_comm/hamiltonian_ops.py",
    "hamiltonian_ops_sha256": "c8fd4425f573d57823ac6857c66a7b8464db9d84bbe562241c9730c86350c9ea",
    "maximum_dense_Fock_modes_in_upstream_code": 14,
    "upstream_spectral_numerics": "NumPy_dense_binary64_SVD_without_directed_rounding",
    "executed_or_imported_by_this_checker": False,
    "logical_role": (
        "the no-go remains valid even if every cluster approximation is replaced "
        "by the globally exact spectral norm"
    ),
}

WITNESS_POLICY = {
    "profile_id": "L8_OBC_U8_T1_R100_FIXED_FIVE_GROUP_GENERIC_BOUND_NO_GO",
    "linear_size": LINEAR_SIZE,
    "n_qubits": N_QUBITS,
    "boundary_condition": "square_open_boundary_no_wrap",
    "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
    "hamiltonian_convention": (
        "H=-sum_<ij>,sigma(cdag_i_sigma*c_j_sigma+cdag_j_sigma*c_i_sigma)"
        "+8*sum_i n_i_up*n_i_down_unshifted"
    ),
    "group_order": list(GROUPS),
    "selected_gamma": 1,
    "selected_group": "H1",
    "selected_tail_groups": ["H2", "HU", "H3", "H4"],
    "selected_family": "tail_nested_[K1_[K1_H1]]",
    "selected_theorem_weight": "1/12",
    "witness_vector": "checkerboard_Neel_computational_basis_A_up_B_down_q0_first",
    "witness_sector": "N_up=32_N_down=32_half_filled_zero_spin",
    "trotter_steps": TROTTER_STEPS,
    "per_observable_allocation": "1/4000",
    "required_coefficient_C_ceiling": "5/4",
    "proof_rule": (
        "norm(A)^2>=norm(A|psi>)^2 for normalized psi; all theorem norm summands nonnegative"
    ),
}

RESOURCE_LIMITS = {
    "max_json_bytes": 262_144,
    "max_checker_source_bytes": 131_072,
    "max_pinned_source_bytes": 1_048_576,
    "max_qubits": N_QUBITS,
    "max_selected_nested_terms": 4_096,
    "max_action_outputs": 2_048,
    "max_rational_digits": 64,
}

SOURCE_PINS = (
    {
        "relative_path": "hubbard_strang_commutator_checker.py",
        "role": "audited_exact_nested_commutator_and_basis_action_backend",
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

SCOPE_CLAIMS = {
    "checker_execution_from_contract_pinned_source_bytes_verified": True,
    "base_commutator_subcertificate_source_pinned_and_verified": True,
    "fixed_L8_selected_nested_operator_exactly_recomputed": True,
    "normalized_computational_basis_witness_verified": True,
    "half_filled_zero_spin_sector_witness_verified": True,
    "exact_nested_operator_basis_action_recomputed": True,
    "spectral_norm_lower_bound_from_basis_action_verified": True,
    "generic_R100_coefficient_ceiling_infeasibility_verified": True,
    "exact_cluster_spectral_norm_required_for_decision": False,
    "upstream_binary64_spectral_norm_imported": False,
    "actual_product_formula_error_lower_bounded": False,
    "observable_specific_or_locality_tightening": "NOT_ASSESSED",
    "alternative_grouping_or_higher_order_formula": "NOT_ASSESSED",
    "truncation_certificate_composed": False,
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    key: (False if value is True else value) for key, value in SCOPE_CLAIMS.items()
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
Gaussian = Tuple[Fraction, Fraction]


class SchemaError(ValueError):
    """Malformed input, source drift, or hard policy mismatch."""


class VerificationError(ValueError):
    """A well-shaped claim or exact invariant disagrees with recomputation."""


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
    if type(value) is not dict:
        raise SchemaError(f"{name} must be an exact object")
    expected = set(keys)
    if set(value) != expected:
        raise SchemaError(f"{name} keys must exactly equal {sorted(expected)}")
    return value


def canonical_sha256(value: Any) -> str:
    try:
        payload = json.dumps(
            value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("value cannot be canonically hashed") from exc
    return hashlib.sha256(payload).hexdigest()


def _format_fraction(backend: Any, value: Fraction) -> str:
    if (
        len(str(abs(value.numerator))) > RESOURCE_LIMITS["max_rational_digits"]
        or len(str(value.denominator)) > RESOURCE_LIMITS["max_rational_digits"]
    ):
        raise VerificationError("witness rational exceeds digit cap")
    return backend.format_fraction(value)


def _read_checker_source_bytes() -> bytes:
    with Path(__file__).open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_checker_source_bytes"] + 1)
    if len(payload) > RESOURCE_LIMITS["max_checker_source_bytes"]:
        raise SchemaError("checker source exceeds byte cap")
    return payload


def checker_source_sha256() -> str:
    payload = _VERIFIED_SELF_SOURCE_BYTES
    if payload is None:
        payload = _read_checker_source_bytes()
    return hashlib.sha256(payload).hexdigest()


def _execute_from_verified_self_source(method: str, *arguments: Any) -> Any:
    payload = _read_checker_source_bytes()
    if not arguments or type(arguments[0]) is not dict:
        raise SchemaError("outer self-exec preflight requires an exact contract object")
    checker_pin = arguments[0].get("checker_source_sha256")
    if type(checker_pin) is not str or not SHA256_RE.fullmatch(checker_pin):
        raise SchemaError("outer self-exec preflight requires canonical checker_source_sha256")
    if hashlib.sha256(payload).hexdigest() != checker_pin:
        raise SchemaError("checker source pin mismatch before compile/exec")
    path = Path(__file__).resolve()
    module = types.ModuleType("verified_hubbard_strang_generic_bound_no_go")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, str(path), "exec"), module.__dict__)
    target = getattr(module, method, None)
    if not callable(target):
        raise SchemaError("verified checker source lacks required entry point")
    return target(*arguments)


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _strict_json_bytes(payload: bytes, name: str) -> Any:
    if len(payload) > RESOURCE_LIMITS["max_json_bytes"]:
        raise SchemaError(f"{name} exceeds JSON byte cap")
    try:
        return json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant: {value}")
            ),
        )
    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        raise SchemaError(f"{name} is not strict JSON: {exc}") from exc


def load_strict_json(path: Path) -> Any:
    with path.open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_json_bytes"] + 1)
    return _strict_json_bytes(payload, str(path))


def _load_base_backend(source_pins: Any) -> Any:
    if not _strict_equal(source_pins, list(SOURCE_PINS)):
        raise SchemaError("contract.source_pins do not match checker policy")
    sources: Dict[str, bytes] = {}
    for pin in SOURCE_PINS:
        path = HERE / pin["relative_path"]
        with path.open("rb") as handle:
            payload = handle.read(RESOURCE_LIMITS["max_pinned_source_bytes"] + 1)
        if len(payload) > RESOURCE_LIMITS["max_pinned_source_bytes"]:
            raise SchemaError(f"pinned source exceeds byte cap: {pin['relative_path']}")
        if hashlib.sha256(payload).hexdigest() != pin["sha256"]:
            raise SchemaError(f"source pin drift: {pin['relative_path']}")
        sources[pin["relative_path"]] = payload
    source = sources["hubbard_strang_commutator_checker.py"]
    backend = types.ModuleType("pinned_hubbard_strang_commutator_for_no_go")
    backend.__file__ = str(HERE / "hubbard_strang_commutator_checker.py")
    backend.__package__ = ""
    backend.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = source
    exec(compile(source, backend.__file__, "exec"), backend.__dict__)
    base_contract = _strict_json_bytes(
        sources["hubbard_strang_commutator_contract.json"], "base contract"
    )
    base_certificate = _strict_json_bytes(
        sources["hubbard_strang_commutator_template.json"], "base certificate"
    )
    result = backend.verify_certificate(base_contract, base_certificate)
    if result.get("status") != BASE_POSITIVE_STATUS or result.get("verified") is not True:
        raise VerificationError("pinned base commutator certificate is not positive")
    return backend


def _neel_bits_q0_first() -> str:
    bits = "".join(
        "10" if (row + column) % 2 == 0 else "01"
        for row in range(LINEAR_SIZE)
        for column in range(LINEAR_SIZE)
    )
    if len(bits) != N_QUBITS or bits.count("1") != LINEAR_SIZE**2:
        raise VerificationError("checkerboard-Neel witness construction failed")
    return bits


def _apply_expansion_to_basis(
    backend: Any, expansion: Mapping[Tuple[int, int], Gaussian], source: int
) -> Dict[int, Gaussian]:
    output: Dict[int, Gaussian] = {}
    for key, coefficient in expansion.items():
        target, phase = backend._basis_pauli_action(key, source)
        contribution = backend._g_mul(coefficient, phase)
        output[target] = backend._g_add(
            output.get(target, (Fraction(0), Fraction(0))), contribution
        )
    return {basis: value for basis, value in output.items() if value != (0, 0)}


_WITNESS_CACHE_BYTES: bytes | None = None


def recompute_witness() -> Dict[str, Any]:
    global _WITNESS_CACHE_BYTES
    if _WITNESS_CACHE_BYTES is not None:
        return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))
    backend = _load_base_backend(list(SOURCE_PINS))
    groups = backend.canonical_group_expansions(LINEAR_SIZE)
    tail = backend._merge_expansions([groups[name] for name in GROUPS[1:]])
    counter = backend.ComputationCounter()
    inner = backend.exact_commutator(tail, groups["H1"], counter)
    selected = backend.exact_commutator(tail, inner, counter)
    if len(selected) > RESOURCE_LIMITS["max_selected_nested_terms"]:
        raise VerificationError("selected nested operator exceeds term cap")
    bits = _neel_bits_q0_first()
    source = sum((character == "1") << index for index, character in enumerate(bits))
    action = _apply_expansion_to_basis(backend, selected, source)
    if len(action) > RESOURCE_LIMITS["max_action_outputs"]:
        raise VerificationError("basis action exceeds output cap")
    for basis in action:
        spin_up = sum((basis >> (2 * site)) & 1 for site in range(64))
        spin_down = sum((basis >> (2 * site + 1)) & 1 for site in range(64))
        if spin_up != 32 or spin_down != 32:
            raise VerificationError("basis action escaped the N_up=32,N_down=32 sector")
    action_records = [
        {
            "basis": hex(basis),
            "real": _format_fraction(backend, action[basis][0]),
            "imag": _format_fraction(backend, action[basis][1]),
        }
        for basis in sorted(action)
    ]
    action_norm_squared = sum(
        real * real + imaginary * imaginary for real, imaginary in action.values()
    )
    if any(imaginary != 0 for _, imaginary in action.values()):
        raise VerificationError("selected witness action unexpectedly has imaginary amplitude")
    amplitude_histogram: Dict[str, int] = {}
    for real, _ in action.values():
        key = _format_fraction(backend, real)
        amplitude_histogram[key] = amplitude_histogram.get(key, 0) + 1
    expected_histogram = {
        "-66/1": 16,
        "-65/1": 16,
        "-8/1": 160,
        "-2/1": 16,
        "2/1": 16,
        "8/1": 160,
        "65/1": 16,
        "66/1": 16,
    }
    if amplitude_histogram != expected_histogram:
        raise VerificationError("selected witness amplitude histogram mismatch")
    contribution_lower_squared = THEOREM_TERM_WEIGHT**2 * action_norm_squared
    coefficient_ceiling = OBSERVABLE_ALLOCATION * TROTTER_STEPS**2 / 2
    coefficient_ceiling_squared = coefficient_ceiling**2
    generic_bound_lower_squared = (
        Fraction(2, TROTTER_STEPS**2) ** 2 * contribution_lower_squared
    )
    allocation_squared = OBSERVABLE_ALLOCATION**2
    if not contribution_lower_squared > coefficient_ceiling_squared:
        raise VerificationError("selected norm witness does not prove infeasibility")
    if generic_bound_lower_squared / allocation_squared != 1312:
        raise VerificationError("exact squared margin invariant failed")
    necessary_R_fourth_power_threshold_exact = (
        4 * contribution_lower_squared / allocation_squared
    )
    if necessary_R_fourth_power_threshold_exact.denominator != 1:
        raise VerificationError("necessary-R fourth-power threshold is not integral")
    necessary_R_fourth_power_threshold = necessary_R_fourth_power_threshold_exact.numerator
    if not 601**4 < necessary_R_fourth_power_threshold <= 602**4:
        raise VerificationError("necessary-R boundary invariant failed")
    result = {
        "profile_id": WITNESS_POLICY["profile_id"],
        "selected_operator": {
            "group": "H1",
            "tail_groups": list(GROUPS[1:]),
            "inner_term_count": len(inner),
            "nested_term_count": len(selected),
            "nested_expansion_sha256": backend._expansion_sha256(selected),
            "theorem_weight": "1/12",
            "commutator_pair_products": counter.commutator_pair_products,
        },
        "normalized_basis_witness": {
            "bits_q0_first": bits,
            "basis_integer_hex": hex(source),
            "particle_count": source.bit_count(),
            "spin_up_particle_count": sum((source >> (2 * site)) & 1 for site in range(64)),
            "spin_down_particle_count": sum((source >> (2 * site + 1)) & 1 for site in range(64)),
            "normalization_squared": "1/1",
            "matches_half_filled_zero_spin_sector": True,
        },
        "exact_action": {
            "nonzero_output_count": len(action),
            "action_records_sha256": canonical_sha256(action_records),
            "action_norm_squared": _format_fraction(backend, action_norm_squared),
            "real_amplitude_histogram": amplitude_histogram,
            "all_outputs_remain_in_N_up32_N_down32_sector": True,
        },
        "infeasibility_proof": {
            "required_total_coefficient_C_ceiling": _format_fraction(
                backend, coefficient_ceiling
            ),
            "required_total_coefficient_C_ceiling_squared": _format_fraction(
                backend, coefficient_ceiling_squared
            ),
            "selected_single_contribution_lower_bound_squared": _format_fraction(
                backend, contribution_lower_squared
            ),
            "selected_contribution_strictly_exceeds_total_ceiling": True,
            "R100_generic_bound_lower_bound_squared": _format_fraction(
                backend, generic_bound_lower_squared
            ),
            "allocation_squared": _format_fraction(backend, allocation_squared),
            "squared_margin_ratio": _format_fraction(
                backend, generic_bound_lower_squared / allocation_squared
            ),
            "minimum_R_not_ruled_out_by_single_witness": 602,
            "R601_fourth_power": 601**4,
            "R602_fourth_power": 602**4,
            "necessary_R_fourth_power_threshold": necessary_R_fourth_power_threshold,
            "fixed_generic_bound_cannot_qualify_at_R100": True,
            "globally_exact_cluster_spectral_norm_cannot_change_decision": True,
            "sector_restricted_exact_spectral_norm_cannot_change_decision": True,
        },
        "decision": {
            "continue_fixed_generic_cluster_spectral_tightening": False,
            "next_required_route": (
                "observable_locality_specific_bound_or_alternative_grouping_or_higher_order_formula"
            ),
        },
    }
    _WITNESS_CACHE_BYTES = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))


def _validate_contract_impl(contract: Any) -> list[str]:
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
                "upstream_cluster_context",
                "witness_policy",
                "resource_limits",
                "expected_witness_sha256",
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
            ("source_pins", list(SOURCE_PINS)),
            ("bound_source", BOUND_SOURCE),
            ("upstream_cluster_context", UPSTREAM_CLUSTER_CONTEXT),
            ("witness_policy", WITNESS_POLICY),
            ("resource_limits", RESOURCE_LIMITS),
            ("maximum_positive_status", MAXIMUM_POSITIVE_STATUS),
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
        recomputed = recompute_witness()
        if (
            type(item["expected_witness_sha256"]) is not str
            or not SHA256_RE.fullmatch(item["expected_witness_sha256"])
            or item["expected_witness_sha256"] != canonical_sha256(recomputed)
        ):
            raise SchemaError("contract.expected_witness_sha256 disagrees with recomputation")
    except (
        SchemaError,
        VerificationError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
    ) as exc:
        return [str(exc)]
    return []


def validate_contract(contract: Any) -> list[str]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _validate_contract_impl(contract)
    try:
        return _execute_from_verified_self_source("_validate_contract_impl", contract)
    except (
        SchemaError,
        VerificationError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
    ) as exc:
        return [str(exc)]


def _verify_certificate_impl(contract: Any, certificate: Any) -> Dict[str, Any]:
    started = time.monotonic()
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
        result["verification_runtime_seconds"] = time.monotonic() - started
        return result
    try:
        item = _exact_keys(
            certificate,
            (
                "schema_version",
                "certificate_type",
                "contract_fingerprint",
                "bound_source",
                "upstream_cluster_context",
                "witness_policy",
                "witness_claim",
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
            ("upstream_cluster_context", UPSTREAM_CLUSTER_CONTEXT),
            ("witness_policy", WITNESS_POLICY),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(item[field], expected):
                raise SchemaError(f"certificate.{field} does not match policy")
        recomputed = recompute_witness()
        if not _strict_equal(item["witness_claim"], recomputed):
            raise VerificationError("certificate.witness_claim disagrees with recomputation")
        if canonical_sha256(item["witness_claim"]) != contract["expected_witness_sha256"]:
            raise VerificationError("certificate.witness_claim disagrees with contract digest")
    except SchemaError as exc:
        result["errors"] = [str(exc)]
        result["verification_runtime_seconds"] = time.monotonic() - started
        return result
    except (
        VerificationError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
    ) as exc:
        result["status"] = "VERIFICATION_FAILED"
        result["errors"] = [str(exc)]
        result["verification_runtime_seconds"] = time.monotonic() - started
        return result
    result.update(
        {
            "status": MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "ready_gate_eligible": False,
            "scope_claims": dict(SCOPE_CLAIMS),
            "checker_executed_source_bytes_sha256_verified": True,
            "recomputed_witness": recomputed,
            "limitations": [
                "This proves infeasibility of the fixed generic theorem bound, not large actual error.",
                "It does not rule out observable/locality-specific cancellation.",
                "It does not assess an alternative grouping or higher-order product formula.",
                "No upstream binary64 spectral norm is imported as certified evidence.",
                "No truncation, physical reference, or READY state is composed.",
            ],
            "verification_runtime_seconds": time.monotonic() - started,
            "errors": [],
        }
    )
    return result


def verify_certificate(contract: Any, certificate: Any) -> Dict[str, Any]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _verify_certificate_impl(contract, certificate)
    started = time.monotonic()
    try:
        return _execute_from_verified_self_source(
            "_verify_certificate_impl", contract, certificate
        )
    except (
        SchemaError,
        VerificationError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
    ) as exc:
        return {
            "status": "INVALID_SCHEMA",
            "verified": False,
            "ready_gate_eligible": False,
            "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
            "verification_runtime_seconds": time.monotonic() - started,
            "errors": [str(exc)],
        }


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
    return 1


if __name__ == "__main__":
    sys.exit(main())
