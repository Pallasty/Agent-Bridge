#!/usr/bin/env python3
"""Certified fixed-point interval propagation for one fused L=8 Strang step.

This checker closes one deliberately narrow L=8 gap.  It independently rebuilds
the 8x8 OBC Hubbard Jordan--Wigner groups, cross-checks them against a
source-pinned positive commutator backend, verifies CAR/onsite witnesses, and
binds a fused nine-stage one-step circuit with 1,152 nonidentity Pauli
rotations.  Both fixed observables are then back-propagated through that single
mapped product-formula step.

Coefficients are closed integer intervals on a 2**64 grid.  Taylor truncation
index N=5 (sin degree 11, cos degree 10) with alternating next-term radii is
quantized outward once; every gate
multiply rounds outward with integer floor/ceil.  After each fixed batch of
eight gates, equal Pauli keys are already merged and a deterministic top-65,536
rule drops the rest.  The sum of interval absolute upper bounds of all dropped
terms is a rigorous operator-norm error ledger relative to the *untruncated
mapped one-step circuit*.

This is not an exact-Hubbard or full R=100 certificate.  The central H4 halves
are fused before truncation, so the exact unitary equals the raw ten-event step
but the truncation path is intentionally different.  Product-formula error,
Majorana runtime custody, reference qualification, and READY remain
unassessed.  The CLI always exits 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
import types
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
CERTIFICATE_TYPE = "l8_one_step_fixed_point_interval_truncation_subcertificate_v1"
CONTRACT_FINGERPRINT = "hubbard_l8_observable_interval_step_contract_v1"
CHECKER_FINGERPRINT = "hubbard_l8_fixed_tick_interval_step_v1"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_L8_ONE_STEP_MAPPED_INTERVAL_TRUNCATION_SUBCERTIFICATE"
BASE_POSITIVE_STATUS = "VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE"

LINEAR_SIZE = 8
N_SITES = 64
N_QUBITS = 128
U_OVER_T = Fraction(8)
STEP_DURATION = Fraction(1, 100)
TROTTER_STEPS = 100
TICK_DENOMINATOR = 1 << 64
TAYLOR_ORDER = 5
GATES_PER_CHECKPOINT = 8
RETAINED_TERM_CAP = 65_536
EXPECTED_GATE_COUNT = 1_152
EXPECTED_CHECKPOINT_COUNT = 144
GROUPS = ("H1", "H2", "HU", "H3", "H4")
FORWARD_STAGES = (
    ("H1", Fraction(1, 2)),
    ("H2", Fraction(1, 2)),
    ("HU", Fraction(1, 2)),
    ("H3", Fraction(1, 2)),
    ("H4", Fraction(1)),
    ("H3", Fraction(1, 2)),
    ("HU", Fraction(1, 2)),
    ("H2", Fraction(1, 2)),
    ("H1", Fraction(1, 2)),
)
RAW_FORWARD_STAGES = (
    ("H1", Fraction(1, 2)),
    ("H2", Fraction(1, 2)),
    ("HU", Fraction(1, 2)),
    ("H3", Fraction(1, 2)),
    ("H4", Fraction(1, 2)),
    ("H4", Fraction(1, 2)),
    ("H3", Fraction(1, 2)),
    ("HU", Fraction(1, 2)),
    ("H2", Fraction(1, 2)),
    ("H1", Fraction(1, 2)),
)
OBSERVABLES = ("staggered_magnetization", "double_occupancy")
CHECKPOINT_STATUS = "OUTWARD_FIXED_TICK_MERGE_THEN_DETERMINISTIC_TOP_L1"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RATIONAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)/[1-9][0-9]*$")

RESOURCE_LIMITS = {
    "max_json_bytes": 1_048_576,
    "max_checker_source_bytes": 131_072,
    "max_pinned_source_bytes": 1_048_576,
    "max_qubits": N_QUBITS,
    "max_spin_resolved_bonds": 224,
    "max_car_action_witnesses": 3_584,
    "max_onsite_witnesses": 256,
    "max_group_terms": 192,
    "max_gate_count": EXPECTED_GATE_COUNT,
    "max_checkpoints": EXPECTED_CHECKPOINT_COUNT,
    "max_single_expansion_terms": 262_144,
    "retained_term_cap": RETAINED_TERM_CAP,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
    "max_term_gate_visits": 200_000_000,
    "max_digest_terms": 262_144,
    "max_rational_digits": 256,
}

SOURCE_PINS = (
    {
        "relative_path": "hubbard_strang_commutator_checker.py",
        "role": "positive_L2_L3_L8_Hubbard_group_oracle_and_exact_Pauli_backend",
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

WORKLOAD_IDENTITY = {
    "profile_id": "L8_OBC_U8_T1_R100_NEEL_FUSED_STRANG_ONE_STEP",
    "linear_size": LINEAR_SIZE,
    "n_sites": N_SITES,
    "n_qubits": N_QUBITS,
    "boundary_condition": "square_open_boundary_no_wrap",
    "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
    "hamiltonian_convention": (
        "H=-sum_<ij>,sigma(cdag_i_sigma*c_j_sigma+cdag_j_sigma*c_i_sigma)"
        "+8*sum_i n_i_up*n_i_down_unshifted"
    ),
    "rotation_convention": "G_P(theta)=exp(-i*theta*P/2)",
    "heisenberg_convention": "backpropagate_G_dagger_O_G_in_reverse_forward_occurrence_order",
    "u_over_t": "8/1",
    "total_time": "1/1",
    "trotter_steps": TROTTER_STEPS,
    "step_duration": "1/100",
    "initial_state": "checkerboard_Neel_A_up_B_down_Nup32_Ndown32",
}

PROPAGATION_POLICY = {
    "forward_stages": [f"{name}:{coefficient.numerator}/{coefficient.denominator}" for name, coefficient in FORWARD_STAGES],
    "raw_group_event_count": 10,
    "fused_stage_count": 9,
    "central_H4_half_events_fused_before_any_truncation": True,
    "fused_gate_count": EXPECTED_GATE_COUNT,
    "raw_nonidentity_gate_count": 1_280,
    "generator_order_within_stage": "ascending_numeric_x_mask_then_z_mask",
    "backpropagation_order": "reverse_stages_and_reverse_gates_within_each_stage",
    "taylor_order": TAYLOR_ORDER,
    "taylor_rule": "sin_through_2Nplus1_cos_through_2N_symmetric_next_term_radius_abs_theta_le_1",
    "tick_denominator": TICK_DENOMINATOR,
    "outward_multiply": "floor_or_ceil_of_four_integer_tick_products_divided_by_tick_denominator",
    "multiplication_rounding_diagnostic": (
        "sum_per_product_max_lower_or_upper_grid_extension_over_tick_denominator_squared_"
        "already_contained_not_additive_error"
    ),
    "gates_per_checkpoint": GATES_PER_CHECKPOINT,
    "checkpoint_count": EXPECTED_CHECKPOINT_COUNT,
    "retained_term_cap": RETAINED_TERM_CAP,
    "ranking": "descending_max_abs_interval_endpoint_then_ascending_numeric_x_mask_z_mask",
    "drop_bound": "sum_max_abs_interval_endpoint_over_dropped_terms_divided_by_tick_denominator",
    "checkpoint_status": CHECKPOINT_STATUS,
}

SCOPE_CLAIMS = {
    "checker_execution_from_contract_pinned_source_bytes_verified": True,
    "positive_base_commutator_subcertificate_verified": True,
    "independent_L8_OBC_geometry_and_JW_groups_verified": True,
    "independent_CAR_hopping_action_witnesses_verified": True,
    "independent_onsite_occupation_energies_verified": True,
    "all_five_group_internal_commutation_verified": True,
    "fused_nine_stage_1152_gate_occurrence_identity_verified": True,
    "raw_to_fused_exact_unitary_equivalence_verified": True,
    "omitted_identity_global_phase_ledger_verified": True,
    "fixed_two_observable_and_Neel_initializations_verified": True,
    "fixed_tick_Taylor_interval_propagation_verified": True,
    "multiplication_grid_rounding_L1_upper_diagnostic_verified": True,
    "merge_before_deterministic_top_L1_truncation_verified": True,
    "per_checkpoint_dropped_L1_ledger_with_nonzero_total_verified": True,
    "final_one_step_mapped_circuit_expectation_intervals_verified": True,
    "raw_1280_occurrence_truncation_path_identical": False,
    "interval_box_optimality": "NOT_ASSESSED",
    "separate_rounding_error_budget": "NOT_ASSESSED_CONTAINED_IN_RETAINED_INTERVAL_BOX",
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
    "full_R100_observable_propagation": "NOT_ASSESSED",
    "MajoranaPropagation_runtime_or_Manifest_custody": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    key: (False if value is True else value) for key, value in SCOPE_CLAIMS.items()
}

PauliKey = Tuple[int, int]
Gaussian = Tuple[Fraction, Fraction]
TickInterval = Tuple[int, int]
TickExpansion = Dict[PauliKey, TickInterval]


class SchemaError(ValueError):
    """Malformed input, source drift, or hard resource-policy failure."""


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


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _reject_nonfinite(value: str) -> Any:
    raise ValueError(f"non-finite JSON constant: {value}")


def _strict_json_bytes(payload: bytes, name: str) -> Any:
    if len(payload) > RESOURCE_LIMITS["max_json_bytes"]:
        raise SchemaError(f"{name} exceeds JSON byte cap")
    try:
        return json.loads(
            payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise SchemaError(f"{name} is not strict JSON: {exc}") from exc


def load_strict_json(path: Path) -> Any:
    with path.open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_json_bytes"] + 1)
    return _strict_json_bytes(payload, path.name)


def _format_fraction(value: Fraction) -> str:
    if max(len(str(abs(value.numerator))), len(str(value.denominator))) > RESOURCE_LIMITS["max_rational_digits"]:
        raise VerificationError("rational digit cap exceeded")
    return f"{value.numerator}/{value.denominator}"


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
        raise SchemaError("outer self-exec preflight requires checker_source_sha256")
    if hashlib.sha256(payload).hexdigest() != checker_pin:
        raise SchemaError("checker source pin mismatch before compile/exec")
    path = Path(__file__).resolve()
    module = types.ModuleType("verified_hubbard_l8_observable_interval_step")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, str(path), "exec"), module.__dict__)
    target = getattr(module, method, None)
    if not callable(target):
        raise SchemaError("verified checker source lacks required entry point")
    return target(*arguments)


def _read_pinned_sources() -> Dict[str, bytes]:
    output: Dict[str, bytes] = {}
    for pin in SOURCE_PINS:
        path = HERE / pin["relative_path"]
        with path.open("rb") as handle:
            payload = handle.read(RESOURCE_LIMITS["max_pinned_source_bytes"] + 1)
        if len(payload) > RESOURCE_LIMITS["max_pinned_source_bytes"]:
            raise SchemaError(f"pinned source exceeds cap: {path.name}")
        if hashlib.sha256(payload).hexdigest() != pin["sha256"]:
            raise SchemaError(f"source pin drift: {path.name}")
        output[pin["relative_path"]] = payload
    return output


def _load_base(sources: Mapping[str, bytes]) -> Any:
    source = sources["hubbard_strang_commutator_checker.py"]
    module = types.ModuleType("pinned_hubbard_strang_for_l8_interval_step")
    module.__file__ = str(HERE / "hubbard_strang_commutator_checker.py")
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = source
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    contract = _strict_json_bytes(
        sources["hubbard_strang_commutator_contract.json"], "base contract"
    )
    certificate = _strict_json_bytes(
        sources["hubbard_strang_commutator_template.json"], "base certificate"
    )
    result = module.verify_certificate(contract, certificate)
    if result.get("status") != BASE_POSITIVE_STATUS or result.get("verified") is not True:
        raise VerificationError("source-pinned base commutator certificate is not positive")
    return module


def _mode(row: int, column: int, spin: int) -> int:
    return 2 * (row * LINEAR_SIZE + column) + spin


def _independent_bonds() -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    used_geometric: set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()
    for group in ("H1", "H2", "H3", "H4"):
        if group in ("H1", "H2"):
            parity = 0 if group == "H1" else 1
            endpoints = (
                ((row, column), (row, column + 1))
                for row in range(LINEAR_SIZE)
                for column in range(parity, LINEAR_SIZE - 1, 2)
            )
            orientation = "horizontal"
        else:
            parity = 1 if group == "H3" else 0
            endpoints = (
                ((row, column), (row + 1, column))
                for row in range(parity, LINEAR_SIZE - 1, 2)
                for column in range(LINEAR_SIZE)
            )
            orientation = "vertical"
        for left_site, right_site in endpoints:
            if not (0 <= left_site[0] < LINEAR_SIZE and 0 <= left_site[1] < LINEAR_SIZE):
                raise VerificationError("left OBC endpoint is outside lattice")
            if not (0 <= right_site[0] < LINEAR_SIZE and 0 <= right_site[1] < LINEAR_SIZE):
                raise VerificationError("right OBC endpoint is outside lattice")
            if abs(left_site[0] - right_site[0]) + abs(left_site[1] - right_site[1]) != 1:
                raise VerificationError("generated bond is not nearest-neighbour OBC")
            geometric = (left_site, right_site)
            used_geometric.add(geometric)
            for spin, spin_name in ((0, "up"), (1, "down")):
                left = _mode(*left_site, spin)
                right = _mode(*right_site, spin)
                if not left < right:
                    raise VerificationError("spin-resolved bond modes must ascend")
                output.append(
                    {
                        "group": group,
                        "orientation": orientation,
                        "parity": parity,
                        "spin": spin_name,
                        "left_site": list(left_site),
                        "right_site": list(right_site),
                        "left_mode": left,
                        "right_mode": right,
                    }
                )
    if len(output) != 224 or len(used_geometric) != 112:
        raise VerificationError("L8 OBC bond cardinality mismatch")
    for group in ("H1", "H2", "H3", "H4"):
        modes: List[int] = []
        for bond in output:
            if bond["group"] == group:
                modes.extend((bond["left_mode"], bond["right_mode"]))
        if len(modes) != len(set(modes)):
            raise VerificationError(f"{group} is not a disjoint spin-mode matching")
    return output


def _add_exact_term(
    expansion: MutableMapping[PauliKey, Fraction], key: PauliKey, coefficient: Fraction
) -> None:
    value = expansion.get(key, Fraction(0)) + coefficient
    if value:
        expansion[key] = value
    else:
        expansion.pop(key, None)


def _independent_groups(bonds: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[PauliKey, Fraction]]:
    output: Dict[str, Dict[PauliKey, Fraction]] = {group: {} for group in GROUPS}
    for bond in bonds:
        left, right = bond["left_mode"], bond["right_mode"]
        interior = ((1 << right) - 1) ^ ((1 << (left + 1)) - 1)
        endpoints = (1 << left) | (1 << right)
        _add_exact_term(output[bond["group"]], (endpoints, interior), Fraction(-1, 2))
        _add_exact_term(
            output[bond["group"]], (endpoints, interior | endpoints), Fraction(-1, 2)
        )
    for site in range(N_SITES):
        up, down = 2 * site, 2 * site + 1
        for key, coefficient in (
            ((0, 1 << up), Fraction(-2)),
            ((0, 1 << down), Fraction(-2)),
            ((0, (1 << up) | (1 << down)), Fraction(2)),
        ):
            _add_exact_term(output["HU"], key, coefficient)
    expected = {"H1": 128, "H2": 96, "HU": 192, "H3": 96, "H4": 128}
    if {group: len(output[group]) for group in GROUPS} != expected:
        raise VerificationError("independent L8 group term counts mismatch")
    return output


def _g_add(left: Gaussian, right: Gaussian) -> Gaussian:
    return left[0] + right[0], left[1] + right[1]


def _g_mul(left: Gaussian, right: Gaussian) -> Gaussian:
    return left[0] * right[0] - left[1] * right[1], left[0] * right[1] + left[1] * right[0]


def _g_i_power(value: Gaussian, power: int) -> Gaussian:
    for _ in range(power % 4):
        value = -value[1], value[0]
    return value


def _basis_pauli_action(key: PauliKey, source: int) -> Tuple[int, Gaussian]:
    x_mask, z_mask = key
    phase = (x_mask & z_mask).bit_count() % 4
    if (z_mask & source).bit_count() & 1:
        phase = (phase + 2) % 4
    return source ^ x_mask, _g_i_power((Fraction(1), Fraction(0)), phase)


def _apply_creation_annihilation(source: int, create: int, annihilate: int) -> Tuple[int, int] | None:
    if not source & (1 << annihilate) or source & (1 << create):
        return None
    annihilation_sign = -1 if (source & ((1 << annihilate) - 1)).bit_count() & 1 else 1
    intermediate = source ^ (1 << annihilate)
    creation_sign = -1 if (intermediate & ((1 << create) - 1)).bit_count() & 1 else 1
    return intermediate | (1 << create), annihilation_sign * creation_sign


def _direct_hopping_action(source: int, left: int, right: int) -> Dict[int, Gaussian]:
    output: Dict[int, Gaussian] = {}
    for create, annihilate in ((left, right), (right, left)):
        result = _apply_creation_annihilation(source, create, annihilate)
        if result is not None:
            target, sign = result
            output[target] = _g_add(
                output.get(target, (Fraction(0), Fraction(0))),
                (Fraction(-sign), Fraction(0)),
            )
    return {key: value for key, value in output.items() if value != (0, 0)}


def _jw_hopping_action(source: int, left: int, right: int) -> Dict[int, Gaussian]:
    interior = ((1 << right) - 1) ^ ((1 << (left + 1)) - 1)
    endpoints = (1 << left) | (1 << right)
    output: Dict[int, Gaussian] = {}
    for key in ((endpoints, interior), (endpoints, interior | endpoints)):
        target, phase = _basis_pauli_action(key, source)
        contribution = (-phase[0] / 2, -phase[1] / 2)
        output[target] = _g_add(output.get(target, (Fraction(0), Fraction(0))), contribution)
    return {key: value for key, value in output.items() if value != (0, 0)}


def _action_records(action: Mapping[int, Gaussian]) -> List[Dict[str, str]]:
    return [
        {
            "target": hex(target),
            "real": _format_fraction(action[target][0]),
            "imag": _format_fraction(action[target][1]),
        }
        for target in sorted(action)
    ]


def _mapping_oracles(
    backend: Any,
) -> Tuple[Dict[str, Dict[PauliKey, Fraction]], Dict[str, Any]]:
    bonds = _independent_bonds()
    independent = _independent_groups(bonds)
    source_groups = backend.canonical_group_expansions(LINEAR_SIZE)
    group_records: List[Dict[str, Any]] = []
    pair_counts: Dict[str, int] = {}
    for group in GROUPS:
        expected = {
            key: (coefficient, Fraction(0)) for key, coefficient in independent[group].items()
        }
        if source_groups[group] != expected:
            raise VerificationError(f"independent {group} expansion disagrees with pinned backend")
        keys = sorted(independent[group])
        comparisons = 0
        for offset, left in enumerate(keys):
            for right in keys[offset + 1 :]:
                comparisons += 1
                if ((left[0] & right[1]).bit_count() + (left[1] & right[0]).bit_count()) & 1:
                    raise VerificationError(f"{group} contains noncommuting generators")
        pair_counts[group] = comparisons
        group_records.append(
            {
                "group": group,
                "term_count": len(keys),
                "expansion_sha256": backend._expansion_sha256(expected),
                "internal_pair_commutation_count": comparisons,
            }
        )
    car_records: List[Dict[str, Any]] = []
    for bond_index, bond in enumerate(bonds):
        left, right = bond["left_mode"], bond["right_mode"]
        odd_bit = 1 << (left + 1)
        spectator = left - 1 if left > 0 else right + 1
        if not 0 <= spectator < N_QUBITS or left <= spectator <= right:
            raise VerificationError("CAR witness lacks external spectator")
        for endpoint_bits in range(4):
            for odd_parity in (0, 1):
                for external in (0, 1):
                    source = (
                        ((endpoint_bits & 1) << left)
                        | (((endpoint_bits >> 1) & 1) << right)
                        | (odd_parity * odd_bit)
                        | (external << spectator)
                    )
                    direct = _direct_hopping_action(source, left, right)
                    mapped = _jw_hopping_action(source, left, right)
                    if direct != mapped:
                        raise VerificationError("direct CAR and JW hopping actions disagree")
                    car_records.append(
                        {
                            "bond_index": bond_index,
                            "endpoint_bits": endpoint_bits,
                            "interior_parity": odd_parity,
                            "external_spectator": external,
                            "source": hex(source),
                            "action": _action_records(direct),
                        }
                    )
    if len(car_records) != RESOURCE_LIMITS["max_car_action_witnesses"]:
        raise VerificationError("CAR witness count mismatch")
    onsite_records: List[Dict[str, Any]] = []
    for site in range(N_SITES):
        up, down = 2 * site, 2 * site + 1
        for local_bits in range(4):
            source = ((local_bits & 1) << up) | (((local_bits >> 1) & 1) << down)
            z_up = -1 if source & (1 << up) else 1
            z_down = -1 if source & (1 << down) else 1
            energy = 2 * (1 - z_up - z_down + z_up * z_down)
            expected = 8 if local_bits == 3 else 0
            if energy != expected:
                raise VerificationError("onsite occupation energy mismatch")
            onsite_records.append(
                {"site": site, "local_bits": local_bits, "energy": energy}
            )
    if len(onsite_records) != RESOURCE_LIMITS["max_onsite_witnesses"]:
        raise VerificationError("onsite witness count mismatch")
    return independent, {
        "spin_resolved_bond_count": len(bonds),
        "geometric_bond_count": len(bonds) // 2,
        "group_spin_resolved_bond_counts": {
            group: sum(bond["group"] == group for bond in bonds)
            for group in ("H1", "H2", "H3", "H4")
        },
        "group_records": group_records,
        "group_internal_pair_counts": pair_counts,
        "CAR_action_witness_count": len(car_records),
        "CAR_action_witnesses_sha256": canonical_sha256(car_records),
        "onsite_occupation_witness_count": len(onsite_records),
        "onsite_occupation_witnesses_sha256": canonical_sha256(onsite_records),
        "all_groups_match_source_pinned_backend": True,
        "CAR_representative_equivalence_classes_per_bond": 16,
        "all_representative_hopping_CAR_equivalence_classes_match_JW": True,
        "all_onsite_energies_match_unshifted_U_nup_ndown": True,
        "all_group_generators_internally_commute": True,
    }


def _sequence_records(
    groups: Mapping[str, Mapping[PauliKey, Fraction]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    def build_forward(
        stages: Sequence[Tuple[str, Fraction]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        stage_records: List[Dict[str, Any]] = []
        gate_records: List[Dict[str, Any]] = []
        occurrence = 0
        for stage_index, (group, stage_coefficient) in enumerate(stages):
            duration = stage_coefficient * STEP_DURATION
            start = occurrence
            for gate_in_stage, key in enumerate(sorted(groups[group])):
                coefficient = groups[group][key]
                theta = 2 * duration * coefficient
                gate_records.append(
                    {
                        "occurrence_index": occurrence,
                        "stage_index": stage_index,
                        "gate_in_stage": gate_in_stage,
                        "group": group,
                        "x_mask": hex(key[0]),
                        "z_mask": hex(key[1]),
                        "hamiltonian_coefficient": _format_fraction(coefficient),
                        "duration": _format_fraction(duration),
                        "rotation_theta": _format_fraction(theta),
                    }
                )
                occurrence += 1
            stage_records.append(
                {
                    "stage_index": stage_index,
                    "group": group,
                    "duration": _format_fraction(duration),
                    "term_count": len(groups[group]),
                    "occurrence_start": start,
                    "occurrence_stop_exclusive": occurrence,
                }
            )
        return stage_records, gate_records

    forward_stages, forward_gates = build_forward(FORWARD_STAGES)
    raw_forward_stages, raw_forward_gates = build_forward(RAW_FORWARD_STAGES)
    analytically_fused_stages = (
        RAW_FORWARD_STAGES[:4]
        + (("H4", RAW_FORWARD_STAGES[4][1] + RAW_FORWARD_STAGES[5][1]),)
        + RAW_FORWARD_STAGES[6:]
    )
    if analytically_fused_stages != FORWARD_STAGES:
        raise VerificationError("raw and fused outer stage identities mismatch")
    occurrence = len(forward_gates)
    if occurrence != EXPECTED_GATE_COUNT:
        raise VerificationError("fused forward gate count mismatch")
    if len(raw_forward_gates) != 1_280:
        raise VerificationError("raw forward gate count mismatch")

    raw_halves = (
        [gate for gate in raw_forward_gates if gate["stage_index"] == 4],
        [gate for gate in raw_forward_gates if gate["stage_index"] == 5],
    )
    fused_central = [gate for gate in forward_gates if gate["stage_index"] == 4]
    if not (len(raw_halves[0]) == len(raw_halves[1]) == len(fused_central)):
        raise VerificationError("central H4 fusion term counts mismatch")
    fusion_witnesses: List[Dict[str, Any]] = []
    for first, second, fused in zip(raw_halves[0], raw_halves[1], fused_central):
        key = first["x_mask"], first["z_mask"]
        if key != (second["x_mask"], second["z_mask"]) or key != (
            fused["x_mask"], fused["z_mask"]
        ):
            raise VerificationError("central H4 fusion generator ordering mismatch")
        if Fraction(first["rotation_theta"]) + Fraction(second["rotation_theta"]) != Fraction(
            fused["rotation_theta"]
        ):
            raise VerificationError("central H4 half angles do not sum to fused angle")
        fusion_witnesses.append(
            {
                "x_mask": key[0],
                "z_mask": key[1],
                "first_half_theta": first["rotation_theta"],
                "second_half_theta": second["rotation_theta"],
                "fused_theta": fused["rotation_theta"],
            }
        )
    h4_keys = sorted(groups["H4"])
    central_pair_count = 0
    for offset, left in enumerate(h4_keys):
        for right in h4_keys[offset + 1 :]:
            central_pair_count += 1
            if ((left[0] & right[1]).bit_count() + (left[1] & right[0]).bit_count()) & 1:
                raise VerificationError("central H4 fusion requires commuting generators")
    backprop_gates: List[Dict[str, Any]] = []
    backprop_stages: List[Dict[str, Any]] = []
    back_index = 0
    for back_stage_index, forward_stage_index in enumerate(reversed(range(len(FORWARD_STAGES)))):
        forward_stage = forward_stages[forward_stage_index]
        selected = [
            gate for gate in forward_gates if gate["stage_index"] == forward_stage_index
        ]
        stage_gates: List[Tuple[PauliKey, Fraction]] = []
        for gate_in_back_stage, gate in enumerate(reversed(selected)):
            record = {
                "backprop_occurrence_index": back_index,
                "forward_occurrence_index": gate["occurrence_index"],
                "backprop_stage_index": back_stage_index,
                "forward_stage_index": forward_stage_index,
                "gate_in_backprop_stage": gate_in_back_stage,
                "group": gate["group"],
                "x_mask": gate["x_mask"],
                "z_mask": gate["z_mask"],
                "theta": gate["rotation_theta"],
            }
            backprop_gates.append(record)
            stage_gates.append(
                (
                    (int(gate["x_mask"], 16), int(gate["z_mask"], 16)),
                    Fraction(gate["rotation_theta"]),
                )
            )
            back_index += 1
        backprop_stages.append(
            {
                "backprop_stage_index": back_stage_index,
                "forward_stage_index": forward_stage_index,
                "group": forward_stage["group"],
                "gate_count": len(stage_gates),
                "gates": stage_gates,
            }
        )
    theta_histogram = Counter(gate["rotation_theta"] for gate in forward_gates)
    expected_histogram = {"-1/200": 640, "-1/100": 128, "-1/50": 256, "1/50": 128}
    if dict(sorted(theta_histogram.items())) != expected_histogram:
        raise VerificationError("fused gate theta histogram mismatch")
    onsite_identity_coefficient = N_SITES * U_OVER_T / 4
    hu_half_duration = STEP_DURATION / 2
    phase_exponent_per_HU_half = onsite_identity_coefficient * hu_half_duration
    phase_exponent_per_step = 2 * phase_exponent_per_HU_half
    identity_rotation_theta_sum_per_step = 2 * phase_exponent_per_step
    identity_rotation_theta_sum_R100 = TROTTER_STEPS * identity_rotation_theta_sum_per_step
    if (
        onsite_identity_coefficient != 128
        or phase_exponent_per_HU_half != Fraction(16, 25)
        or phase_exponent_per_step != Fraction(32, 25)
        or identity_rotation_theta_sum_per_step != Fraction(64, 25)
        or identity_rotation_theta_sum_R100 != 256
    ):
        raise VerificationError("omitted onsite identity phase mismatch")
    sequence_claim = {
        "fused_stage_count": len(forward_stages),
        "fused_forward_gate_count": len(forward_gates),
        "backprop_gate_count": len(backprop_gates),
        "forward_stage_records_sha256": canonical_sha256(forward_stages),
        "forward_gate_records_sha256": canonical_sha256(forward_gates),
        "raw_forward_stage_records_sha256": canonical_sha256(raw_forward_stages),
        "raw_forward_gate_records_sha256": canonical_sha256(raw_forward_gates),
        "backprop_gate_records_sha256": canonical_sha256(backprop_gates),
        "theta_histogram": dict(sorted(theta_histogram.items())),
        "raw_nonidentity_gate_count": len(raw_forward_gates),
        "central_H4_half_events_fused_before_truncation": True,
        "central_H4_fused_generator_count": len(fusion_witnesses),
        "central_H4_internal_commutation_pair_count": central_pair_count,
        "central_H4_fusion_witnesses_sha256": canonical_sha256(fusion_witnesses),
        "raw_and_fused_exact_unitaries_equal_from_internal_commutation": True,
        "raw_and_fused_truncation_paths_identical": False,
        "omitted_global_phase": {
            "HU_identity_Hamiltonian_coefficient": _format_fraction(
                onsite_identity_coefficient
            ),
            "phase_exponent_per_HU_half_stage": _format_fraction(phase_exponent_per_HU_half),
            "phase_exponent_per_step": _format_fraction(phase_exponent_per_step),
            "phase_exponent_R100": _format_fraction(phase_exponent_per_step * 100),
            "identity_rotation_theta_sum_per_step": _format_fraction(
                identity_rotation_theta_sum_per_step
            ),
            "identity_rotation_theta_sum_R100": _format_fraction(
                identity_rotation_theta_sum_R100
            ),
            "cancels_from_Heisenberg_observable_conjugation": True,
        },
    }
    return forward_stages, forward_gates, backprop_stages, sequence_claim


def _tick_digest(expansion: Mapping[PauliKey, TickInterval], keys: Sequence[PauliKey] | None = None) -> str:
    selected = sorted(expansion) if keys is None else sorted(keys)
    if len(selected) > RESOURCE_LIMITS["max_digest_terms"]:
        raise SchemaError("tick digest term cap exceeded")
    digest = hashlib.sha256()
    digest.update(b"l8_fixed_tick_interval_expansion_v1\n")
    for key in selected:
        lower, upper = expansion[key]
        digest.update(
            f"{hex(key[0])},{hex(key[1])},{lower},{upper}\n".encode("ascii")
        )
    return digest.hexdigest()


def _initial_observable(observable_id: str) -> Tuple[TickExpansion, Dict[str, Any]]:
    output: TickExpansion = {}
    if observable_id == "double_occupancy":
        output[(0, 0)] = (TICK_DENOMINATOR // 4, TICK_DENOMINATOR // 4)
    for site in range(N_SITES):
        row, column = divmod(site, LINEAR_SIZE)
        up, down = 2 * site, 2 * site + 1
        if observable_id == "staggered_magnetization":
            sign = 1 if (row + column) % 2 == 0 else -1
            coefficients = (
                ((0, 1 << up), Fraction(-sign, 128)),
                ((0, 1 << down), Fraction(sign, 128)),
            )
        elif observable_id == "double_occupancy":
            coefficients = (
                ((0, 1 << up), Fraction(-1, 256)),
                ((0, 1 << down), Fraction(-1, 256)),
                ((0, (1 << up) | (1 << down)), Fraction(1, 256)),
            )
        else:
            raise VerificationError("unknown observable")
        for key, coefficient in coefficients:
            ticks = coefficient * TICK_DENOMINATOR
            if ticks.denominator != 1 or key in output:
                raise VerificationError("initial observable is not exactly tick representable")
            output[key] = (ticks.numerator, ticks.numerator)
    l1_ticks = sum(max(abs(value[0]), abs(value[1])) for value in output.values())
    if l1_ticks != TICK_DENOMINATOR:
        raise VerificationError("normalized observable tick L1 must equal one")
    return output, {
        "observable_id": observable_id,
        "initial_term_count": len(output),
        "initial_tick_expansion_sha256": _tick_digest(output),
        "initial_coefficient_L1": "1/1",
    }


def _neel_basis() -> int:
    state = 0
    for site in range(N_SITES):
        row, column = divmod(site, LINEAR_SIZE)
        spin = 0 if (row + column) % 2 == 0 else 1
        state |= 1 << (2 * site + spin)
    spin_up_count = sum(bool(state & (1 << mode)) for mode in range(0, N_QUBITS, 2))
    spin_down_count = sum(bool(state & (1 << mode)) for mode in range(1, N_QUBITS, 2))
    if state.bit_count() != 64 or spin_up_count != 32 or spin_down_count != 32:
        raise VerificationError("Neel state particle count mismatch")
    return state


def _floor_tick(value: Fraction) -> int:
    return value.numerator * TICK_DENOMINATOR // value.denominator


def _ceil_tick(value: Fraction) -> int:
    return -((-value.numerator * TICK_DENOMINATOR) // value.denominator)


def _taylor_trig_record(theta: Fraction) -> Tuple[TickInterval, TickInterval, Dict[str, Any]]:
    if abs(theta) > 1:
        raise SchemaError("gate theta exceeds Taylor policy")
    sine = sum(
        (
            Fraction((-1) ** k, math.factorial(2 * k + 1))
            * theta ** (2 * k + 1)
            for k in range(TAYLOR_ORDER + 1)
        ),
        Fraction(0),
    )
    cosine = sum(
        (
            Fraction((-1) ** k, math.factorial(2 * k)) * theta ** (2 * k)
            for k in range(TAYLOR_ORDER + 1)
        ),
        Fraction(0),
    )
    sine_radius = abs(theta) ** (2 * TAYLOR_ORDER + 3) / math.factorial(2 * TAYLOR_ORDER + 3)
    cosine_radius = abs(theta) ** (2 * TAYLOR_ORDER + 2) / math.factorial(2 * TAYLOR_ORDER + 2)
    sine_fraction = (sine - sine_radius, sine + sine_radius)
    cosine_fraction = (cosine - cosine_radius, cosine + cosine_radius)
    sine_ticks = (_floor_tick(sine_fraction[0]), _ceil_tick(sine_fraction[1]))
    cosine_ticks = (_floor_tick(cosine_fraction[0]), _ceil_tick(cosine_fraction[1]))
    return sine_ticks, cosine_ticks, {
        "theta": _format_fraction(theta),
        "sine_fraction_interval": {
            "lower": _format_fraction(sine_fraction[0]),
            "upper": _format_fraction(sine_fraction[1]),
        },
        "cosine_fraction_interval": {
            "lower": _format_fraction(cosine_fraction[0]),
            "upper": _format_fraction(cosine_fraction[1]),
        },
        "sine_tick_interval": {"lower": str(sine_ticks[0]), "upper": str(sine_ticks[1])},
        "cosine_tick_interval": {"lower": str(cosine_ticks[0]), "upper": str(cosine_ticks[1])},
    }


class PropagationCounter:
    def __init__(self) -> None:
        self.term_gate_visits = 0
        self.peak_live_terms = 0
        self.maximum_expansion_coefficient_tick_bits = 0
        self.maximum_product_bits = 0
        self.multiplication_rounding_l1_scaled_ticks_squared = 0
        self.window_peak_live_terms = 0

    def visit(self, count: int) -> None:
        self.term_gate_visits += count
        if self.term_gate_visits > RESOURCE_LIMITS["max_term_gate_visits"]:
            raise SchemaError("term-gate visit cap exceeded")

    def observe(self, expansion: Mapping[PauliKey, TickInterval]) -> None:
        count = len(expansion)
        self.peak_live_terms = max(self.peak_live_terms, count)
        self.window_peak_live_terms = max(self.window_peak_live_terms, count)
        if count > RESOURCE_LIMITS["max_single_expansion_terms"]:
            raise SchemaError("single-expansion term cap exceeded")

    def begin_window(self, expansion: Mapping[PauliKey, TickInterval]) -> None:
        self.window_peak_live_terms = len(expansion)
        self.observe(expansion)

    def observe_interval(self, value: TickInterval) -> None:
        bits = max(abs(value[0]).bit_length(), abs(value[1]).bit_length())
        self.maximum_expansion_coefficient_tick_bits = max(
            self.maximum_expansion_coefficient_tick_bits, bits
        )
        if bits > RESOURCE_LIMITS["max_expansion_coefficient_tick_bits"]:
            raise SchemaError("expansion coefficient tick integer bit cap exceeded")


def _multiply_ticks(left: TickInterval, right: TickInterval, counter: PropagationCounter) -> TickInterval:
    products = (
        left[0] * right[0],
        left[0] * right[1],
        left[1] * right[0],
        left[1] * right[1],
    )
    product_bits = max(abs(value).bit_length() for value in products)
    counter.maximum_product_bits = max(counter.maximum_product_bits, product_bits)
    if product_bits > RESOURCE_LIMITS["max_product_bits"]:
        raise SchemaError("tick product integer bit cap exceeded")
    minimum = min(products)
    maximum = max(products)
    lower = minimum // TICK_DENOMINATOR
    upper = -((-maximum) // TICK_DENOMINATOR)
    counter.multiplication_rounding_l1_scaled_ticks_squared += max(
        minimum - lower * TICK_DENOMINATOR,
        upper * TICK_DENOMINATOR - maximum,
    )
    return lower, upper


def _add_tick_term(
    output: TickExpansion,
    key: PauliKey,
    value: TickInterval,
    counter: PropagationCounter,
) -> None:
    if key in output:
        previous = output[key]
        value = previous[0] + value[0], previous[1] + value[1]
    if value == (0, 0):
        output.pop(key, None)
    else:
        output[key] = value
        counter.observe_interval(value)
    live_terms = len(output)
    if live_terms > counter.window_peak_live_terms:
        counter.window_peak_live_terms = live_terms
        if live_terms > counter.peak_live_terms:
            counter.peak_live_terms = live_terms
        if live_terms > RESOURCE_LIMITS["max_single_expansion_terms"]:
            raise SchemaError("single-expansion term cap exceeded")


def _anticommuting_branch(generator: PauliKey, operator: PauliKey) -> Tuple[int, PauliKey]:
    gx, gz = generator
    ox, oz = operator
    output = gx ^ ox, gz ^ oz
    phase = (
        (gx & gz).bit_count()
        + (ox & oz).bit_count()
        + 2 * (gz & ox).bit_count()
        - (output[0] & output[1]).bit_count()
    ) % 4
    combined = (phase + 1) % 4
    if combined == 0:
        return 1, output
    if combined == 2:
        return -1, output
    raise VerificationError("anticommuting Pauli branch is unexpectedly non-Hermitian")


def _propagate_gate(
    expansion: TickExpansion,
    generator: PauliKey,
    sine: TickInterval,
    cosine: TickInterval,
    counter: PropagationCounter,
) -> TickExpansion:
    counter.visit(len(expansion))
    output: TickExpansion = {}
    gx, gz = generator
    for operator, coefficient in expansion.items():
        ox, oz = operator
        if (((gx & oz).bit_count() + (gz & ox).bit_count()) & 1) == 0:
            _add_tick_term(output, operator, coefficient, counter)
        else:
            _add_tick_term(
                output,
                operator,
                _multiply_ticks(coefficient, cosine, counter),
                counter,
            )
            sign, branch = _anticommuting_branch(generator, operator)
            value = _multiply_ticks(coefficient, sine, counter)
            if sign == -1:
                value = -value[1], -value[0]
            _add_tick_term(output, branch, value, counter)
        if len(output) > RESOURCE_LIMITS["max_single_expansion_terms"]:
            raise SchemaError("intermediate gate output exceeds single-expansion term cap")
    counter.observe(output)
    return output


def _abs_upper(value: TickInterval) -> int:
    return max(abs(value[0]), abs(value[1]))


def _truncate(expansion: TickExpansion) -> Tuple[TickExpansion, Dict[str, Any]]:
    if len(expansion) <= RETAINED_TERM_CAP:
        empty_digest = _tick_digest({}, [])
        return dict(expansion), {
            "dropped_term_count": 0,
            "dropped_l1_ticks": 0,
            "dropped_terms_sha256": empty_digest,
            "minimum_retained_abs_upper_ticks": min(
                (_abs_upper(value) for value in expansion.values()), default=0
            ),
            "maximum_dropped_abs_upper_ticks": 0,
        }
    ranked = sorted(
        expansion,
        key=lambda key: (-_abs_upper(expansion[key]), key[0], key[1]),
    )
    retained_keys = ranked[:RETAINED_TERM_CAP]
    dropped_keys = ranked[RETAINED_TERM_CAP:]
    minimum_retained = min(_abs_upper(expansion[key]) for key in retained_keys)
    maximum_dropped = max(_abs_upper(expansion[key]) for key in dropped_keys)
    if minimum_retained < maximum_dropped:
        raise VerificationError("deterministic top-L1 ordering invariant failed")
    return {key: expansion[key] for key in retained_keys}, {
        "dropped_term_count": len(dropped_keys),
        "dropped_l1_ticks": sum(_abs_upper(expansion[key]) for key in dropped_keys),
        "dropped_terms_sha256": _tick_digest(expansion, dropped_keys),
        "minimum_retained_abs_upper_ticks": minimum_retained,
        "maximum_dropped_abs_upper_ticks": maximum_dropped,
    }


def _expectation_ticks(expansion: Mapping[PauliKey, TickInterval], basis: int) -> TickInterval:
    lower = 0
    upper = 0
    for (x_mask, z_mask), interval in expansion.items():
        if x_mask:
            continue
        if (z_mask & basis).bit_count() & 1:
            lower -= interval[1]
            upper -= interval[0]
        else:
            lower += interval[0]
            upper += interval[1]
    return lower, upper


def _tick_interval_record(value: TickInterval) -> Dict[str, Any]:
    return {
        "lower_ticks": str(value[0]),
        "upper_ticks": str(value[1]),
        "lower": _format_fraction(Fraction(value[0], TICK_DENOMINATOR)),
        "upper": _format_fraction(Fraction(value[1], TICK_DENOMINATOR)),
    }


def _propagate_observable(
    observable_id: str,
    backprop_stages: Sequence[Mapping[str, Any]],
    trig_cache: Mapping[Fraction, Tuple[TickInterval, TickInterval]],
    neel: int,
) -> Dict[str, Any]:
    expansion, initial_record = _initial_observable(observable_id)
    initial_expectation = _expectation_ticks(expansion, neel)
    expected_initial = (TICK_DENOMINATOR, TICK_DENOMINATOR) if observable_id == "staggered_magnetization" else (0, 0)
    if initial_expectation != expected_initial:
        raise VerificationError("initial Neel observable expectation mismatch")
    counter = PropagationCounter()
    counter.observe(expansion)
    for interval in expansion.values():
        counter.observe_interval(interval)
    cumulative_drop_ticks = 0
    checkpoint_records: List[Dict[str, Any]] = []
    stage_records: List[Dict[str, Any]] = []
    checkpoint_index = 0
    for stage in backprop_stages:
        gates = stage["gates"]
        if len(gates) % GATES_PER_CHECKPOINT:
            raise VerificationError("stage gate count is not divisible by checkpoint batch")
        stage_start_terms = len(expansion)
        stage_peak = len(expansion)
        stage_drop_ticks = 0
        stage_dropped_count = 0
        stage_rounding_start = counter.multiplication_rounding_l1_scaled_ticks_squared
        for batch_index in range(0, len(gates), GATES_PER_CHECKPOINT):
            batch = gates[batch_index : batch_index + GATES_PER_CHECKPOINT]
            checkpoint_rounding_start = counter.multiplication_rounding_l1_scaled_ticks_squared
            counter.begin_window(expansion)
            for generator, theta in batch:
                sine, cosine = trig_cache[theta]
                expansion = _propagate_gate(expansion, generator, sine, cosine, counter)
            peak_before_truncation = counter.window_peak_live_terms
            post_propagation_count = len(expansion)
            expansion, dropped = _truncate(expansion)
            dropped_ticks = dropped["dropped_l1_ticks"]
            cumulative_drop_ticks += dropped_ticks
            stage_drop_ticks += dropped_ticks
            stage_dropped_count += dropped["dropped_term_count"]
            stage_peak = max(stage_peak, peak_before_truncation)
            checkpoint_records.append(
                {
                    "checkpoint_index": checkpoint_index,
                    "backprop_stage_index": stage["backprop_stage_index"],
                    "forward_stage_index": stage["forward_stage_index"],
                    "group": stage["group"],
                    "batch_in_stage": batch_index // GATES_PER_CHECKPOINT,
                    "gate_count": len(batch),
                    "post_propagation_term_count": post_propagation_count,
                    "peak_single_expansion_term_count": peak_before_truncation,
                    "retained_term_count": len(expansion),
                    "dropped_term_count": dropped["dropped_term_count"],
                    "dropped_l1_ticks": str(dropped_ticks),
                    "dropped_l1": _format_fraction(Fraction(dropped_ticks, TICK_DENOMINATOR)),
                    "cumulative_dropped_l1_ticks": str(cumulative_drop_ticks),
                    "cumulative_dropped_l1": _format_fraction(Fraction(cumulative_drop_ticks, TICK_DENOMINATOR)),
                    "dropped_terms_sha256": dropped["dropped_terms_sha256"],
                    "minimum_retained_abs_upper_ticks": str(dropped["minimum_retained_abs_upper_ticks"]),
                    "maximum_dropped_abs_upper_ticks": str(dropped["maximum_dropped_abs_upper_ticks"]),
                    "multiplication_grid_rounding_L1_upper_increment_scaled_ticks_squared": str(
                        counter.multiplication_rounding_l1_scaled_ticks_squared
                        - checkpoint_rounding_start
                    ),
                    "multiplication_grid_rounding_L1_upper_cumulative_scaled_ticks_squared": str(
                        counter.multiplication_rounding_l1_scaled_ticks_squared
                    ),
                    "checkpoint_status": CHECKPOINT_STATUS,
                }
            )
            checkpoint_index += 1
        stage_records.append(
            {
                "backprop_stage_index": stage["backprop_stage_index"],
                "forward_stage_index": stage["forward_stage_index"],
                "group": stage["group"],
                "start_term_count": stage_start_terms,
                "end_retained_term_count": len(expansion),
                "peak_single_expansion_term_count": stage_peak,
                "dropped_term_count": stage_dropped_count,
                "dropped_l1_ticks": str(stage_drop_ticks),
                "dropped_l1": _format_fraction(Fraction(stage_drop_ticks, TICK_DENOMINATOR)),
                "cumulative_dropped_l1": _format_fraction(Fraction(cumulative_drop_ticks, TICK_DENOMINATOR)),
                "multiplication_grid_rounding_L1_upper_increment": _format_fraction(
                    Fraction(
                        counter.multiplication_rounding_l1_scaled_ticks_squared
                        - stage_rounding_start,
                        TICK_DENOMINATOR * TICK_DENOMINATOR,
                    )
                ),
                "multiplication_grid_rounding_L1_upper_cumulative": _format_fraction(
                    Fraction(
                        counter.multiplication_rounding_l1_scaled_ticks_squared,
                        TICK_DENOMINATOR * TICK_DENOMINATOR,
                    )
                ),
                "retained_expansion_sha256": _tick_digest(expansion),
            }
        )
    if checkpoint_index != EXPECTED_CHECKPOINT_COUNT:
        raise VerificationError("checkpoint count mismatch")
    if cumulative_drop_ticks <= 0:
        raise VerificationError("positive L8 fixture did not exercise nonzero truncation")
    retained_expectation = _expectation_ticks(expansion, neel)
    declared_expectation = (
        retained_expectation[0] - cumulative_drop_ticks,
        retained_expectation[1] + cumulative_drop_ticks,
    )
    return {
        **initial_record,
        "initial_Neel_expectation_interval": _tick_interval_record(initial_expectation),
        "checkpoint_count": len(checkpoint_records),
        "nonzero_checkpoint_count": sum(
            record["dropped_l1_ticks"] != "0" for record in checkpoint_records
        ),
        "maximum_checkpoint_dropped_l1_ticks": str(
            max(int(record["dropped_l1_ticks"]) for record in checkpoint_records)
        ),
        "checkpoint_ledger_sha256": canonical_sha256(checkpoint_records),
        "stage_records": stage_records,
        "final_retained_term_count": len(expansion),
        "final_retained_expansion_sha256": _tick_digest(expansion),
        "cumulative_dropped_l1_ticks": str(cumulative_drop_ticks),
        "cumulative_dropped_l1": _format_fraction(Fraction(cumulative_drop_ticks, TICK_DENOMINATOR)),
        "final_retained_Neel_expectation_interval": _tick_interval_record(retained_expectation),
        "declared_untruncated_mapped_step_Neel_expectation_interval": _tick_interval_record(declared_expectation),
        "nonzero_truncation_exercised": True,
        "resource_usage": {
            "term_gate_visits": counter.term_gate_visits,
            "peak_single_expansion_term_count": counter.peak_live_terms,
            "maximum_expansion_coefficient_tick_bits": (
                counter.maximum_expansion_coefficient_tick_bits
            ),
            "maximum_product_bits": counter.maximum_product_bits,
            "multiplication_grid_rounding_L1_upper_scaled_ticks_squared": str(
                counter.multiplication_rounding_l1_scaled_ticks_squared
            ),
            "multiplication_grid_rounding_L1_upper": _format_fraction(
                Fraction(
                    counter.multiplication_rounding_l1_scaled_ticks_squared,
                    TICK_DENOMINATOR * TICK_DENOMINATOR,
                )
            ),
            "multiplication_grid_rounding_already_contained_not_additive_error": True,
        },
    }


_WITNESS_CACHE_BYTES: bytes | None = None


def recompute_witness() -> Dict[str, Any]:
    global _WITNESS_CACHE_BYTES
    if _WITNESS_CACHE_BYTES is not None:
        _read_pinned_sources()
        return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))
    sources = _read_pinned_sources()
    backend = _load_base(sources)
    groups, mapping_claim = _mapping_oracles(backend)
    forward_stages, forward_gates, backprop_stages, sequence_claim = _sequence_records(groups)
    del forward_stages, forward_gates
    unique_thetas = sorted(
        {theta for stage in backprop_stages for _, theta in stage["gates"]}
    )
    trig_cache: Dict[Fraction, Tuple[TickInterval, TickInterval]] = {}
    trig_records: List[Dict[str, Any]] = []
    for theta in unique_thetas:
        sine, cosine, record = _taylor_trig_record(theta)
        trig_cache[theta] = sine, cosine
        trig_records.append(record)
    maximum_trigonometric_tick_bits = max(
        abs(value).bit_length()
        for intervals in trig_cache.values()
        for interval in intervals
        for value in interval
    )
    if maximum_trigonometric_tick_bits > RESOURCE_LIMITS["max_trigonometric_tick_bits"]:
        raise SchemaError("trigonometric tick integer bit cap exceeded")
    neel = _neel_basis()
    observable_claims = [
        _propagate_observable(observable_id, backprop_stages, trig_cache, neel)
        for observable_id in OBSERVABLES
    ]
    witness = {
        "profile_id": WORKLOAD_IDENTITY["profile_id"],
        "source_pinned_base": {
            "status": BASE_POSITIVE_STATUS,
            "verified": True,
            "checker_sha256": hashlib.sha256(
                sources["hubbard_strang_commutator_checker.py"]
            ).hexdigest(),
        },
        "mapping_oracles": mapping_claim,
        "sequence_identity": sequence_claim,
        "fixed_point_trigonometric_intervals": {
            "unique_theta_count": len(unique_thetas),
            "maximum_trigonometric_tick_bits": maximum_trigonometric_tick_bits,
            "records": trig_records,
            "records_sha256": canonical_sha256(trig_records),
        },
        "initial_Neel_state": {
            "basis_integer_hex": hex(neel),
            "particle_count": neel.bit_count(),
            "spin_up_particle_count": sum(bool(neel & (1 << mode)) for mode in range(0, N_QUBITS, 2)),
            "spin_down_particle_count": sum(bool(neel & (1 << mode)) for mode in range(1, N_QUBITS, 2)),
        },
        "observable_claims": observable_claims,
        "decision": {
            "one_step_nonzero_truncation_ledger_closed": True,
            "continue_to_repeated_step_parent_child_checkpoint_chain": True,
            "full_R100_or_exact_Hubbard_error_certified": False,
        },
    }
    _WITNESS_CACHE_BYTES = json.dumps(
        witness, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("ascii")
    return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))


def expected_contract_body() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "certificate_type": CERTIFICATE_TYPE,
        "checker_fingerprint": CHECKER_FINGERPRINT,
        "source_pins": list(SOURCE_PINS),
        "workload_identity": dict(WORKLOAD_IDENTITY),
        "propagation_policy": dict(PROPAGATION_POLICY),
        "resource_limits": dict(RESOURCE_LIMITS),
        "maximum_positive_status": MAXIMUM_POSITIVE_STATUS,
        "scope_claims": dict(SCOPE_CLAIMS),
    }


def _validate_contract_raise(contract: Any) -> None:
    item = _exact_keys(
        contract,
        (
            "schema_version", "contract_fingerprint", "certificate_type",
            "checker_fingerprint", "checker_source_sha256", "source_pins",
            "workload_identity", "propagation_policy", "resource_limits",
            "expected_witness_sha256", "maximum_positive_status", "scope_claims",
        ),
        "contract",
    )
    if type(item["checker_source_sha256"]) is not str or not SHA256_RE.fullmatch(item["checker_source_sha256"]):
        raise SchemaError("contract checker source hash is malformed")
    if item["checker_source_sha256"] != checker_source_sha256():
        raise SchemaError("contract does not pin this checker source")
    expected = expected_contract_body()
    observed = {
        key: value
        for key, value in item.items()
        if key not in ("checker_source_sha256", "expected_witness_sha256")
    }
    if not _strict_equal(observed, expected):
        raise SchemaError("contract does not match fixed checker policy")
    if type(item["expected_witness_sha256"]) is not str or not SHA256_RE.fullmatch(item["expected_witness_sha256"]):
        raise SchemaError("contract expected witness hash is malformed")
    _read_pinned_sources()


def _validate_contract_impl(contract: Any) -> List[str]:
    try:
        _validate_contract_raise(contract)
    except (SchemaError, VerificationError, KeyError, TypeError, ValueError, OSError, RecursionError) as exc:
        return [str(exc)]
    return []


def validate_contract(contract: Any) -> List[str]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _validate_contract_impl(contract)
    try:
        return _execute_from_verified_self_source("_validate_contract_impl", contract)
    except (SchemaError, VerificationError, KeyError, TypeError, ValueError, OSError, RecursionError) as exc:
        return [str(exc)]


def _verify_certificate_impl(contract: Any, certificate: Any) -> Dict[str, Any]:
    started = time.monotonic()
    base = {
        "status": "INVALID_SCHEMA",
        "verified": False,
        "ready_gate_eligible": False,
        "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
        "verification_runtime_seconds": 0.0,
        "errors": [],
    }
    try:
        _validate_contract_raise(contract)
        cert = _exact_keys(
            certificate,
            (
                "schema_version", "certificate_type", "contract_fingerprint",
                "workload_identity", "propagation_policy", "witness_claim", "scope_claims",
            ),
            "certificate",
        )
        for field, expected in (
            ("schema_version", 1),
            ("certificate_type", CERTIFICATE_TYPE),
            ("contract_fingerprint", CONTRACT_FINGERPRINT),
            ("workload_identity", WORKLOAD_IDENTITY),
            ("propagation_policy", PROPAGATION_POLICY),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(cert[field], expected):
                raise SchemaError(f"certificate.{field} does not match contract policy")
        witness = recompute_witness()
        if canonical_sha256(witness) != contract["expected_witness_sha256"]:
            raise VerificationError("recomputed witness digest disagrees with contract")
        if not _strict_equal(cert["witness_claim"], witness):
            raise VerificationError("certificate.witness_claim disagrees with recomputation")
    except SchemaError as exc:
        base["errors"] = [str(exc)]
        base["verification_runtime_seconds"] = time.monotonic() - started
        return base
    except (VerificationError, KeyError, TypeError, ValueError, OSError, RecursionError) as exc:
        base["status"] = "VERIFICATION_FAILED"
        base["errors"] = [str(exc)]
        base["verification_runtime_seconds"] = time.monotonic() - started
        return base
    base.update(
        {
            "status": MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "ready_gate_eligible": False,
            "scope_claims": dict(SCOPE_CLAIMS),
            "recomputed_witness": witness,
            "checker_executed_source_bytes_sha256_verified": True,
            "verification_runtime_seconds": time.monotonic() - started,
            "limitations": [
                "Only one fused L8 product-formula step is interval-propagated.",
                "The exact fused unitary equals the raw ten-event step, but their truncation paths are not identical.",
                "The retained coefficient box contains all fixed-point/Taylor rounding enlargement; it is not claimed optimal.",
                "Cumulative dropped-L1 bounds truncation relative to the untruncated mapped step only.",
                "No product-formula error to exact Hubbard evolution, full R=100 chain, physical reference, or READY state is certified.",
            ],
            "errors": [],
        }
    )
    return base


def verify_certificate(contract: Any, certificate: Any) -> Dict[str, Any]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _verify_certificate_impl(contract, certificate)
    try:
        return _execute_from_verified_self_source("_verify_certificate_impl", contract, certificate)
    except (SchemaError, VerificationError, KeyError, TypeError, ValueError, OSError, RecursionError) as exc:
        return {
            "status": "INVALID_SCHEMA",
            "verified": False,
            "ready_gate_eligible": False,
            "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
            "verification_runtime_seconds": 0.0,
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
    except (SchemaError, OSError, ValueError, TypeError, RecursionError) as exc:
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
