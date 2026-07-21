#!/usr/bin/env python3
"""Fail-closed L=8 coefficient-L1 screen for alternative Strang groupings.

This checker answers one narrow feasibility question left by the fixed five-group
commutator certificate: can permutation alone, or an open-boundary adaptation of
the plaquette grouping of Schubert--Mendl, materially reduce the same fully merged
Pauli-coefficient-L1 Strang bound at R=100?

It source-pins and executes the already audited commutator checker, verifies its
positive contract/template, enumerates all 120 orders of the fixed five groups,
and enumerates all 24 orders of an exact L=8 OBC decomposition into two disjoint
bulk-plaquette groups, one disjoint boundary-residual group, and the onsite group.
Every candidate is checked to sum to the same nonidentity Hamiltonian before its
nested commutators are evaluated.

The plaquette candidate is only a grouping screen.  Its bulk group exponentials
contain noncommuting edges inside each plaquette and therefore are not the declared
individual-term benchmark circuit.  The paper's three-group construction assumes
periodic boundaries and simultaneous plaquette evolution; its printed numerical
spectral-norm bounds are not imported into this OBC certificate.  No physical L=8
initial state, observable-specific tightening, truncation composition, reference
qualification, or READY decision is made.  The CLI consequently always exits 1.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
import time
import types
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
CERTIFICATE_TYPE = "hubbard_strang_grouping_coefficient_l1_screen_v1"
CONTRACT_FINGERPRINT = "hubbard_strang_grouping_screen_contract_v1"
CHECKER_FINGERPRINT = "hubbard_strang_grouping_exact_permutation_screen_v1"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_STRANG_GROUPING_COEFFICIENT_L1_SCREEN"
BASE_POSITIVE_STATUS = "VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE"

LINEAR_SIZE = 8
TROTTER_STEPS = 100
OBSERVABLE_ALLOCATION = Fraction(1, 4000)
FIXED_GROUPS = ("H1", "H2", "HU", "H3", "H4")
PLAQUETTE_GROUPS = ("P0", "P1", "B", "HU")
FIXED_ORDER = FIXED_GROUPS

PRIMARY_SOURCE = {
    "authors": "Ansgar Schubert and Christian B. Mendl",
    "title": "Trotter error with commutator scaling for the Fermi-Hubbard model",
    "arxiv_version": "2306.10603v2",
    "doi": "10.1103/PhysRevB.108.195105",
    "formula": "Proposition 2 Equation 13",
    "plaquette_decomposition": "Section III.B Equation 19",
    "source_scope": (
        "paper uses even-L periodic boundaries and three groups; four hopping "
        "terms inside a plaquette are assumed simultaneously realizable"
    ),
    "use_in_this_checker": (
        "formula and grouping motivation only; printed decimal norm bounds are "
        "not used as certified OBC values"
    ),
}

SCREEN_POLICY = {
    "linear_size": LINEAR_SIZE,
    "boundary_condition": "square_open_boundary_no_wrap",
    "hamiltonian_convention": (
        "H=-sum_<ij>,sigma(cdag_i_sigma*c_j_sigma+cdag_j_sigma*c_i_sigma)"
        "+8*sum_i n_i_up*n_i_down_unshifted"
    ),
    "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
    "fixed_group_names": list(FIXED_GROUPS),
    "fixed_permutation_count": 120,
    "plaquette_candidate_group_names": list(PLAQUETTE_GROUPS),
    "plaquette_permutation_count": 24,
    "plaquette_bulk_anchors": {
        "P0": "even_row_even_column_lower_left",
        "P1": "odd_row_odd_column_lower_left_strictly_interior",
    },
    "boundary_residual": (
        "odd horizontal bonds on top/bottom plus odd vertical bonds on left/right"
    ),
    "bound": "Schubert_Mendl_Proposition_2_Eq_13_then_merged_Pauli_coefficient_L1",
    "observable_comparison": "generic_norm_at_most_one_factor_two",
    "trotter_steps": TROTTER_STEPS,
    "per_observable_allocation": "1/4000",
    "material_relative_C_reduction_threshold": "1/100",
}

RESOURCE_LIMITS = {
    "max_json_bytes": 262_144,
    "max_checker_source_bytes": 131_072,
    "max_pinned_source_bytes": 1_048_576,
    "max_fixed_permutations": 120,
    "max_plaquette_permutations": 24,
    "max_total_terms": 640,
    "max_commutator_pair_products_per_candidate": 2_000_000,
}

SOURCE_PINS = (
    {
        "relative_path": "hubbard_strang_commutator_checker.py",
        "role": "audited_exact_commutator_and_coefficient_L1_backend",
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
    "fixed_five_group_all_120_orders_exactly_screened": True,
    "OBC_plaquette_boundary_hamiltonian_cover_verified": True,
    "OBC_plaquette_boundary_all_24_orders_exactly_screened": True,
    "nested_commutators_merged_before_coefficient_L1": True,
    "R100_generic_observable_allocation_tested": True,
    "paper_periodic_plaquette_numerical_bound_imported": False,
    "candidate_group_exponentials_matched_to_benchmark_circuit": False,
    "observable_specific_or_locality_tightening": "NOT_ASSESSED",
    "truncation_certificate_composed": False,
    "physical_L8_instance_identity": "NOT_ASSESSED",
    "reference_error_budget_qualified": False,
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    key: (False if value is True else value) for key, value in SCOPE_CLAIMS.items()
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PauliKey = Tuple[int, int]
Expansion = Dict[PauliKey, Tuple[Fraction, Fraction]]


class SchemaError(ValueError):
    """Malformed input, source drift, or hard policy mismatch."""


class VerificationError(ValueError):
    """A well-shaped claim disagrees with exact recomputation."""


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
    module = types.ModuleType("verified_hubbard_strang_grouping_screen")
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


def _load_pinned_dependencies(source_pins: Any) -> Tuple[Any, Dict[str, bytes]]:
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
    module = types.ModuleType("pinned_hubbard_strang_commutator")
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
        raise VerificationError("pinned base commutator certificate is not positive")
    return module, sources


def _add_hopping_bond(
    backend: Any,
    expansion: Expansion,
    left: int,
    right: int,
) -> None:
    interior = ((1 << right) - 1) ^ ((1 << (left + 1)) - 1)
    endpoints = (1 << left) | (1 << right)
    for axis in ("X", "Y"):
        key = (endpoints, interior if axis == "X" else interior | endpoints)
        backend._add_term(expansion, key, (Fraction(-1, 2), Fraction(0)))


def _plaquette_boundary_groups(backend: Any) -> Tuple[Dict[str, Expansion], Dict[str, Any]]:
    groups: Dict[str, Expansion] = {name: {} for name in PLAQUETTE_GROUPS}
    spatial_records: List[Dict[str, Any]] = []
    expected_edges = set()
    for axis in ("horizontal", "vertical"):
        if axis == "horizontal":
            edges = (
                (row, column, row, column + 1)
                for row in range(LINEAR_SIZE)
                for column in range(LINEAR_SIZE - 1)
            )
        else:
            edges = (
                (row, column, row + 1, column)
                for row in range(LINEAR_SIZE - 1)
                for column in range(LINEAR_SIZE)
            )
        for row_a, col_a, row_b, col_b in edges:
            edge = (row_a, col_a, row_b, col_b)
            expected_edges.add(edge)
            if (axis == "horizontal" and col_a % 2 == 0) or (
                axis == "vertical" and row_a % 2 == 0
            ):
                group = "P0"
            elif (axis == "horizontal" and 0 < row_a < LINEAR_SIZE - 1) or (
                axis == "vertical" and 0 < col_a < LINEAR_SIZE - 1
            ):
                group = "P1"
            else:
                group = "B"
            spatial_records.append(
                {"axis": axis, "edge": list(edge), "group": group}
            )
            for spin in (0, 1):
                left = backend._mode(LINEAR_SIZE, row_a, col_a, spin)
                right = backend._mode(LINEAR_SIZE, row_b, col_b, spin)
                _add_hopping_bond(backend, groups[group], left, right)
    if len(expected_edges) != 2 * LINEAR_SIZE * (LINEAR_SIZE - 1):
        raise VerificationError("OBC spatial edge cardinality mismatch")
    if len(spatial_records) != len(expected_edges):
        raise VerificationError("OBC candidate does not cover every edge exactly once")
    assigned_edges = {
        name: {
            tuple(record["edge"])
            for record in spatial_records
            if record["group"] == name
        }
        for name in ("P0", "P1", "B")
    }

    def plaquette_edges(row: int, column: int) -> set[Tuple[int, int, int, int]]:
        return {
            (row, column, row, column + 1),
            (row + 1, column, row + 1, column + 1),
            (row, column, row + 1, column),
            (row, column + 1, row + 1, column + 1),
        }

    anchor_families = {
        "P0": [
            (row, column)
            for row in range(0, LINEAR_SIZE - 1, 2)
            for column in range(0, LINEAR_SIZE - 1, 2)
        ],
        "P1": [
            (row, column)
            for row in range(1, LINEAR_SIZE - 1, 2)
            for column in range(1, LINEAR_SIZE - 1, 2)
        ],
    }
    expected_bulk_edges: Dict[str, set[Tuple[int, int, int, int]]] = {}
    for name, anchors in anchor_families.items():
        vertices = set()
        family_edges = set()
        for row, column in anchors:
            plaquette_vertices = {
                (row, column),
                (row, column + 1),
                (row + 1, column),
                (row + 1, column + 1),
            }
            if vertices & plaquette_vertices:
                raise VerificationError(f"{name} plaquettes are not vertex-disjoint")
            vertices.update(plaquette_vertices)
            family_edges.update(plaquette_edges(row, column))
        expected_bulk_edges[name] = family_edges
        if assigned_edges[name] != family_edges:
            raise VerificationError(f"{name} assigned edges do not equal plaquette union")
    expected_boundary = expected_edges - expected_bulk_edges["P0"] - expected_bulk_edges["P1"]
    if assigned_edges["B"] != expected_boundary:
        raise VerificationError("boundary residual is not the exact plaquette complement")
    fixed = backend.canonical_group_expansions(LINEAR_SIZE)
    groups["HU"] = dict(fixed["HU"])
    if backend._merge_expansions(list(groups.values())) != backend._merge_expansions(
        list(fixed.values())
    ):
        raise VerificationError("OBC plaquette candidate does not equal fixed Hamiltonian")
    term_total = sum(len(value) for value in groups.values())
    if term_total != RESOURCE_LIMITS["max_total_terms"]:
        raise VerificationError("candidate total term count mismatch")
    bond_counts = {
        group: sum(1 for record in spatial_records if record["group"] == group)
        for group in ("P0", "P1", "B")
    }
    if bond_counts != {"P0": 64, "P1": 36, "B": 12}:
        raise VerificationError("candidate spatial bond counts mismatch")
    commutation = {}
    for name, expansion in groups.items():
        keys = list(expansion)
        commutation[name] = all(
            backend._pauli_commutes(left, right)
            for index, left in enumerate(keys)
            for right in keys[index + 1 :]
        )
    if commutation != {"P0": False, "P1": False, "B": True, "HU": True}:
        raise VerificationError("candidate internal commutation invariant mismatch")
    structure = {
        "spatial_bond_counts": bond_counts,
        "pauli_term_counts": {name: len(groups[name]) for name in PLAQUETTE_GROUPS},
        "P0_disjoint_plaquette_count": 16,
        "P1_disjoint_plaquette_count": 9,
        "boundary_residual_disjoint_bond_count": 12,
        "group_internal_pairwise_commutation": commutation,
        "bulk_group_exponentials_require_noncommuting_plaquette_cluster_evolution": True,
        "spatial_assignment_sha256": canonical_sha256(spatial_records),
        "hamiltonian_equality_verified": True,
    }
    return groups, structure


def _order_record(backend: Any, groups: Mapping[str, Expansion], order: Tuple[str, ...]) -> Dict[str, Any]:
    counter = backend.ComputationCounter()
    tail_sum = Fraction(0)
    self_sum = Fraction(0)
    for index, name in enumerate(order):
        tail = backend._merge_expansions([groups[item] for item in order[index + 1 :]])
        inner = backend.exact_commutator(tail, groups[name], counter)
        tail_nested = backend.exact_commutator(tail, inner, counter)
        self_nested = backend.exact_commutator(groups[name], inner, counter)
        tail_sum += backend._pure_axis_l1(tail_nested, "real")
        self_sum += backend._pure_axis_l1(self_nested, "real")
    if counter.commutator_pair_products > RESOURCE_LIMITS[
        "max_commutator_pair_products_per_candidate"
    ]:
        raise VerificationError("candidate pair-product cap exceeded")
    coefficient = tail_sum / 12 + self_sum / 24
    observable_bound = 2 * coefficient / TROTTER_STEPS**2
    return {
        "order": list(order),
        "tail_nested_l1_sum": backend.format_fraction(tail_sum),
        "self_nested_l1_sum": backend.format_fraction(self_sum),
        "coefficient_C": backend.format_fraction(coefficient),
        "generic_norm_one_observable_R100_bound": backend.format_fraction(observable_bound),
        "minimum_R_for_allocation": backend._minimum_steps_for_bound(coefficient, 2),
        "commutator_pair_products": counter.commutator_pair_products,
    }


def _screen_orders(
    backend: Any,
    groups: Mapping[str, Expansion],
    names: Tuple[str, ...],
    expected_count: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    records = [_order_record(backend, groups, order) for order in itertools.permutations(names)]
    if len(records) != expected_count:
        raise VerificationError("permutation count mismatch")
    records.sort(key=lambda item: (Fraction(item["coefficient_C"]), item["order"]))
    best_value = records[0]["coefficient_C"]
    best = [record for record in records if record["coefficient_C"] == best_value]
    return records, best


_SCREEN_CACHE_BYTES: bytes | None = None


def grouping_screen() -> Dict[str, Any]:
    global _SCREEN_CACHE_BYTES
    if _SCREEN_CACHE_BYTES is not None:
        return json.loads(_SCREEN_CACHE_BYTES.decode("ascii"))
    backend, _ = _load_pinned_dependencies(list(SOURCE_PINS))
    fixed = backend.canonical_group_expansions(LINEAR_SIZE)
    fixed_records, fixed_best = _screen_orders(
        backend, fixed, FIXED_GROUPS, RESOURCE_LIMITS["max_fixed_permutations"]
    )
    fixed_record = next(record for record in fixed_records if record["order"] == list(FIXED_ORDER))
    fixed_rank = fixed_records.index(fixed_record) + 1
    candidate, structure = _plaquette_boundary_groups(backend)
    plaquette_records, plaquette_best = _screen_orders(
        backend,
        candidate,
        PLAQUETTE_GROUPS,
        RESOURCE_LIMITS["max_plaquette_permutations"],
    )
    allocation_coefficient_ceiling = (
        OBSERVABLE_ALLOCATION * TROTTER_STEPS**2 / 2
    )
    fixed_coefficient = Fraction(fixed_record["coefficient_C"])
    best_fixed_coefficient = Fraction(fixed_best[0]["coefficient_C"])
    relative_fixed_reduction = (
        fixed_coefficient - best_fixed_coefficient
    ) / fixed_coefficient
    material_threshold = Fraction(SCREEN_POLICY["material_relative_C_reduction_threshold"])
    result = {
        "profile_id": "L8_OBC_U8_T1_R100_GROUPING_COEFFICIENT_L1_SCREEN",
        "allocation_coefficient_C_ceiling": backend.format_fraction(
            allocation_coefficient_ceiling
        ),
        "fixed_five_group_screen": {
            "permutation_count": len(fixed_records),
            "all_order_records_sha256": canonical_sha256(fixed_records),
            "maximum_candidate_commutator_pair_products": max(
                record["commutator_pair_products"] for record in fixed_records
            ),
            "fixed_declared_order": fixed_record,
            "fixed_declared_order_rank": fixed_rank,
            "best_order_count": len(fixed_best),
            "best_orders": fixed_best,
            "relative_C_reduction_from_declared_to_best": backend.format_fraction(
                relative_fixed_reduction
            ),
            "material_relative_C_reduction_threshold_satisfied": (
                relative_fixed_reduction >= material_threshold
            ),
            "best_meets_R100_allocation": (
                Fraction(fixed_best[0]["coefficient_C"]) <= allocation_coefficient_ceiling
            ),
        },
        "OBC_plaquette_boundary_screen": {
            "structure": structure,
            "permutation_count": len(plaquette_records),
            "all_order_records_sha256": canonical_sha256(plaquette_records),
            "maximum_candidate_commutator_pair_products": max(
                record["commutator_pair_products"] for record in plaquette_records
            ),
            "best_order_count": len(plaquette_best),
            "best_orders": plaquette_best,
            "best_meets_R100_allocation": (
                Fraction(plaquette_best[0]["coefficient_C"])
                <= allocation_coefficient_ceiling
            ),
            "matches_declared_individual_term_benchmark_circuit": False,
        },
        "decision": {
            "permutation_materially_improves_fixed_coefficient_L1_bound": (
                relative_fixed_reduction >= material_threshold
            ),
            "OBC_plaquette_regrouping_improves_fixed_declared_coefficient_L1_bound": False,
            "coefficient_L1_grouping_search_qualifies_reference_at_R100": False,
            "next_required_tightening": (
                "observable_or_locality_specific_norm_or_certified_cluster_spectral_norm"
            ),
        },
    }
    _SCREEN_CACHE_BYTES = json.dumps(
        result,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return json.loads(_SCREEN_CACHE_BYTES.decode("ascii"))


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
                "primary_source",
                "screen_policy",
                "resource_limits",
                "expected_screen_sha256",
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
            ("primary_source", PRIMARY_SOURCE),
            ("screen_policy", SCREEN_POLICY),
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
        recomputed = grouping_screen()
        if (
            type(item["expected_screen_sha256"]) is not str
            or not SHA256_RE.fullmatch(item["expected_screen_sha256"])
            or item["expected_screen_sha256"] != canonical_sha256(recomputed)
        ):
            raise SchemaError("contract.expected_screen_sha256 disagrees with recomputation")
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
                "primary_source",
                "screen_policy",
                "screen_claim",
                "scope_claims",
            ),
            "certificate",
        )
        if type(item["schema_version"]) is not int or item["schema_version"] != 1:
            raise SchemaError("certificate.schema_version must be integer 1")
        for field, expected in (
            ("certificate_type", CERTIFICATE_TYPE),
            ("contract_fingerprint", CONTRACT_FINGERPRINT),
            ("primary_source", PRIMARY_SOURCE),
            ("screen_policy", SCREEN_POLICY),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(item[field], expected):
                raise SchemaError(f"certificate.{field} does not match policy")
        recomputed = grouping_screen()
        if not _strict_equal(item["screen_claim"], recomputed):
            raise VerificationError("certificate.screen_claim disagrees with recomputation")
        if canonical_sha256(item["screen_claim"]) != contract["expected_screen_sha256"]:
            raise VerificationError("certificate.screen_claim disagrees with contract digest")
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
            "recomputed_screen": recomputed,
            "limitations": [
                "This is a coefficient-L1 grouping feasibility screen, not a physical reference.",
                "The OBC plaquette bulk exponentials do not match the individual-term benchmark circuit.",
                "The paper's PBC printed decimal norm bounds are not imported as OBC evidence.",
                "No observable/locality-specific norm, truncation composition, or L8 state identity is assessed.",
                "This screen cannot qualify a reference or READY gate.",
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
