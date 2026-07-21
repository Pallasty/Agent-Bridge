#!/usr/bin/env python3
"""Exact no-go witness for one fixed double-occupancy D3 cluster route.

The L=8 double-occupancy leading observable defect is reconstructed twice:
once by the source-pinned Pauli/Fraction Taylor checker and once from a compact
fixture of simplified physical-fermion terms.  The latter is mapped through
Jordan--Wigner exactly and must equal the former term by term.

The physical terms are then partitioned with a fixture-defined deterministic
14-mode greedy rule matching the externally audited ``fh_comm`` policy.  The
checker proves the fixture's total operator identity, but does not regenerate
its decomposition/order from upstream source.  For each of the first 30
clusters, a matrix element obtained by acting directly on the global
checkerboard Neel state lower-bounds that cluster's exact spectral norm.  The
30 nonnegative lower bounds sum
to 1945/768 > 5/2.  Consequently, even exact cluster norms followed by the
triangle inequality cannot make this fixed k=0 partition bound seed an R=100
*uniform-supremum* leading certificate.  A per-k triangle ledger remains open:
the k=0 term by itself is divided by R**3 rather than multiplied by a uniform
R factor.

This is not a lower bound on the norm of the globally merged D3 operator:
cross-cluster cancellation, a different partition, and a direct global-sector
method remain open.  It is not a product-formula error or reference
certificate.  The CLI always exits 1.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
import types
import zlib
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
CERTIFICATE_TYPE = "hubbard_d3_double_occupancy_cluster_uniform_sup_no_go_v1"
CONTRACT_FINGERPRINT = "hubbard_d3_double_occupancy_cluster_uniform_sup_no_go_contract_v1"
CHECKER_FINGERPRINT = "hubbard_d3_exact_cluster_uniform_sup_no_go_v1"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_D3_DOUBLE_OCCUPANCY_CLUSTER_UNIFORM_SUP_NO_GO"
BASE_POSITIVE_STATUS = "VERIFIED_STRANG_COMMUTATOR_L1_SUBCERTIFICATE"

LINEAR_SIZE = 8
N_QUBITS = 128
CLUSTER_MODE_CAP = 14
EXPECTED_SYMBOLIC_TERM_COUNT = 2_748
EXPECTED_FIELD_TERM_COUNT = 18_544
EXPECTED_PAULI_TERM_COUNT = 8_928
EXPECTED_CLUSTER_COUNT = 43
PARTIAL_CLUSTER_COUNT = 30
LEADING_COEFFICIENT_CEILING = Fraction(5, 2)
EXPECTED_PARTIAL_LOWER_BOUND = Fraction(1945, 768)
FIXTURE_RAW_SHA256 = "107cd7945811370216da25876934256101a315d0853d383f523fbb04e591f793"
DIRECT_D3_SHA256 = "069f0d7d28804d2981081b84393e88696a55628814da625ff82df0beaa262aba"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RATIONAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)/[1-9][0-9]*$")

RESOURCE_LIMITS = {
    "max_json_bytes": 1_048_576,
    "max_checker_source_bytes": 131_072,
    "max_pinned_source_bytes": 1_048_576,
    "max_fixture_encoded_bytes": 65_536,
    "max_fixture_raw_bytes": 1_048_576,
    "max_fixture_nodes": 32_768,
    "max_fixture_depth": 8,
    "max_symbolic_terms": EXPECTED_SYMBOLIC_TERM_COUNT,
    "max_field_terms": 25_000,
    "max_pauli_terms": 20_000,
    "max_clusters": 64,
    "max_cluster_modes": CLUSTER_MODE_CAP,
    "max_cluster_action_outputs": 16_384,
    "max_rational_digits": 128,
}

SOURCE_PINS = (
    {
        "relative_path": "hubbard_strang_observable_taylor_step_checker.py",
        "role": "exact_L8_double_occupancy_D3_Pauli_oracle_and_base_custody",
        "sha256": "c0cf77034d97f713c47ae666f015729d4595f445df5b58a36b61adb6274b98b5",
    },
    {
        "relative_path": "hubbard_d3_double_occupancy_symbolic_terms.b85",
        "role": "compressed_fh_comm_simplified_physical_fermion_term_fixture",
        "sha256": "a4f5ba58be3c5fe11c560698cea6ae10970b79c83f7fd94d935da981bc8efa00",
    },
)

UPSTREAM_CONTEXT = {
    "official_repository": "https://github.com/qc-tum/fermi_hubbard_commutators",
    "audited_commit": "859bef092675957ae126e9d3b09dc3c63b213859",
    "hamiltonian_ops_relative_path": "fh_comm/hamiltonian_ops.py",
    "hamiltonian_ops_sha256": "c8fd4425f573d57823ac6857c66a7b8464db9d84bbe562241c9730c86350c9ea",
    "fixture_generation_role": (
        "simplified symbolic term order and recursive operator records only; "
        "the checker independently expands every record and proves its full "
        "Jordan-Wigner Pauli sum equals the source-pinned D3 oracle"
    ),
    "fixture_decomposition_and_order_recomputed_from_upstream_source_by_checker": False,
    "upstream_code_executed_or_imported_by_checker": False,
    "upstream_binary64_spectral_norm_imported": False,
}

WITNESS_POLICY = {
    "profile_id": "L8_OBC_U8_T1_R100_DOUBLE_OCCUPANCY_D3_GREEDY14_UNIFORM_SUP_NO_GO",
    "linear_size": LINEAR_SIZE,
    "n_qubits": N_QUBITS,
    "boundary_condition": "square_open_boundary_no_wrap",
    "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
    "observable": "D=(1/64)*sum_i n_i_up*n_i_down",
    "fixed_group_order": ["H1", "H2", "HU", "H3", "H4"],
    "fixed_nine_stage_Strang": ["H1/2", "H2/2", "HU/2", "H3/2", "H4", "H3/2", "HU/2", "H2/2", "H1/2"],
    "leading_defect_identity": "D3=-i*[B3,D]",
    "cluster_partition": (
        "fixture-defined order externally audited against fh_comm; reverse term "
        "order; seed_first_remaining; repeatedly choose "
        "first minimum support addition while union_modes<=14"
    ),
    "cluster_norm_lower_witness": (
        "maximum absolute matrix element from each cluster acting directly on "
        "the global 128-mode checkerboard Neel basis state"
    ),
    "trotter_steps": 100,
    "per_observable_allocation": "1/4000",
    "required_uniform_supremum_D3_coefficient_ceiling": "5/2",
    "partial_cluster_count": PARTIAL_CLUSTER_COUNT,
}

SCOPE_CLAIMS = {
    "checker_execution_from_contract_pinned_source_bytes_verified": True,
    "source_pinned_observable_taylor_backend_verified": True,
    "fixture_decompressed_and_exact_schema_verified": True,
    "physical_fermion_fixture_JW_equals_exact_Pauli_D3_verified": True,
    "fixture_decomposition_and_order_provenance_to_upstream_machine_verified": False,
    "fixture_support_graph_single_component_verified": True,
    "fixed_greedy_14_mode_partition_exactly_recomputed": True,
    "cluster_field_transition_equals_independent_JW_action_verified": True,
    "global_Neel_matrix_element_cluster_norm_lower_bounds_verified": True,
    "global_half_filled_spin_balanced_sector_action_verified": True,
    "fixed_k0_cluster_triangle_uniform_supremum_infeasible_verified": True,
    "binary64_cluster_spectral_norm_used": False,
    "global_D3_norm_lower_bounded_by_cluster_sum": False,
    "cross_cluster_cancellation": "NOT_ASSESSED",
    "alternative_partition": "NOT_ASSESSED",
    "direct_global_half_sector_norm": "NOT_ASSESSED",
    "per_step_evolved_cluster_triangle_ledger": "NOT_ASSESSED_STILL_OPEN",
    "actual_R100_product_formula_error_lower_bounded": False,
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    key: (False if value is True else value) for key, value in SCOPE_CLAIMS.items()
}

Gaussian = Tuple[Fraction, Fraction]
PauliKey = Tuple[int, int]
FieldOperator = Tuple[int, int]
FieldTerm = Tuple[Fraction, Tuple[FieldOperator, ...]]


class SchemaError(ValueError):
    """Malformed input, source drift, or resource-policy failure."""


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


def _strict_json_bytes(payload: bytes, name: str, maximum: int | None = None) -> Any:
    limit = RESOURCE_LIMITS["max_json_bytes"] if maximum is None else maximum
    if len(payload) > limit:
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


def _parse_fraction(value: Any, name: str) -> Fraction:
    if type(value) is not str or not RATIONAL_RE.fullmatch(value):
        raise SchemaError(f"{name} must be canonical numerator/denominator")
    numerator, denominator = value.split("/")
    result = Fraction(int(numerator), int(denominator))
    if f"{result.numerator}/{result.denominator}" != value:
        raise SchemaError(f"{name} must be reduced and canonical")
    if max(len(str(abs(result.numerator))), len(str(result.denominator))) > RESOURCE_LIMITS["max_rational_digits"]:
        raise SchemaError(f"{name} exceeds rational digit cap")
    return result


def _format_fraction(value: Fraction) -> str:
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
    module = types.ModuleType("verified_hubbard_d3_double_occupancy_cluster_no_go")
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


def _load_observable_runtime(source: bytes) -> Tuple[Any, Any]:
    module = types.ModuleType("pinned_observable_taylor_for_d3_cluster")
    module.__file__ = str(HERE / SOURCE_PINS[0]["relative_path"])
    module.__package__ = ""
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    backend = module._load_backend()
    return module, backend


def _decompress_fixture(encoded: bytes) -> Any:
    if len(encoded) > RESOURCE_LIMITS["max_fixture_encoded_bytes"]:
        raise SchemaError("encoded fixture exceeds cap")
    try:
        compressed = base64.b85decode(b"".join(encoded.split()))
        decoder = zlib.decompressobj()
        maximum = RESOURCE_LIMITS["max_fixture_raw_bytes"]
        raw = decoder.decompress(compressed, maximum + 1)
        if len(raw) > maximum or decoder.unconsumed_tail:
            raise SchemaError("decompressed fixture exceeds cap")
        raw += decoder.flush(maximum + 1 - len(raw))
        if len(raw) > maximum or not decoder.eof or decoder.unused_data:
            raise SchemaError("fixture compression stream is non-canonical")
    except (ValueError, zlib.error) as exc:
        raise SchemaError("fixture base85/zlib decoding failed") from exc
    if hashlib.sha256(raw).hexdigest() != FIXTURE_RAW_SHA256:
        raise SchemaError("decompressed fixture raw hash mismatch")
    return _strict_json_bytes(raw, "decompressed symbolic fixture", maximum)


def _mode(value: Any, name: str) -> int:
    if type(value) is not int or not 0 <= value < N_QUBITS:
        raise SchemaError(f"{name} must be an integer mode in [0,127]")
    return value


def _validate_node(node: Any, name: str, counter: List[int], depth: int = 0) -> None:
    counter[0] += 1
    if counter[0] > RESOURCE_LIMITS["max_fixture_nodes"]:
        raise SchemaError("fixture node cap exceeded")
    if depth > RESOURCE_LIMITS["max_fixture_depth"]:
        raise SchemaError("fixture depth cap exceeded")
    if type(node) is not dict or type(node.get("t")) is not str:
        raise SchemaError(f"{name} must be a tagged exact object")
    tag = node["t"]
    if tag == "n":
        item = _exact_keys(node, ("t", "c", "i"), name)
        _parse_fraction(item["c"], f"{name}.c")
        _mode(item["i"], f"{name}.i")
    elif tag in ("h", "a"):
        item = _exact_keys(node, ("t", "c", "i", "j"), name)
        _parse_fraction(item["c"], f"{name}.c")
        left, right = _mode(item["i"], f"{name}.i"), _mode(item["j"], f"{name}.j")
        if left == right or left % 2 != right % 2:
            raise SchemaError(f"{name} hopping modes must be distinct and same-spin")
    elif tag in ("p", "s"):
        keys = ("t", "c", "o") if tag == "p" else ("t", "o")
        item = _exact_keys(node, keys, name)
        if tag == "p":
            _parse_fraction(item["c"], f"{name}.c")
        children = item["o"]
        maximum = 3 if tag == "p" else 6
        if type(children) is not list or not 1 <= len(children) <= maximum:
            raise SchemaError(f"{name}.o must be a bounded non-empty list")
        for index, child in enumerate(children):
            _validate_node(child, f"{name}.o[{index}]", counter, depth + 1)
    else:
        raise SchemaError(f"{name}.t is unknown")


def _validated_fixture(encoded: bytes) -> List[Mapping[str, Any]]:
    fixture = _decompress_fixture(encoded)
    item = _exact_keys(
        fixture, ("schema_version", "representation", "linear_size", "terms"), "fixture"
    )
    if item["schema_version"] != 1 or type(item["schema_version"]) is not int:
        raise SchemaError("fixture.schema_version must be integer 1")
    if item["representation"] != "fh_comm_simplified_symbolic_v1":
        raise SchemaError("fixture representation mismatch")
    if item["linear_size"] != LINEAR_SIZE or type(item["linear_size"]) is not int:
        raise SchemaError("fixture linear size mismatch")
    terms = item["terms"]
    if type(terms) is not list or len(terms) != EXPECTED_SYMBOLIC_TERM_COUNT:
        raise SchemaError("fixture must contain exactly 2748 symbolic terms")
    counter = [0]
    for index, node in enumerate(terms):
        _validate_node(node, f"fixture.terms[{index}]", counter)
    return terms


def _node_support(node: Mapping[str, Any]) -> frozenset[int]:
    tag = node["t"]
    if tag == "n":
        return frozenset((node["i"],))
    if tag in ("h", "a"):
        return frozenset((node["i"], node["j"]))
    output: set[int] = set()
    for child in node["o"]:
        output.update(_node_support(child))
    return frozenset(output)


def _field_terms(node: Mapping[str, Any]) -> List[FieldTerm]:
    tag = node["t"]
    if tag == "n":
        return [(_parse_fraction(node["c"], "number coefficient"), ((2, node["i"]),))]
    if tag in ("h", "a"):
        coefficient = _parse_fraction(node["c"], "hopping coefficient")
        second = coefficient if tag == "h" else -coefficient
        return [
            (coefficient, ((0, node["i"]), (1, node["j"]))),
            (second, ((0, node["j"]), (1, node["i"]))),
        ]
    if tag == "s":
        output: List[FieldTerm] = []
        for child in node["o"]:
            output.extend(_field_terms(child))
        return output
    if tag == "p":
        output: List[FieldTerm] = [(_parse_fraction(node["c"], "product coefficient"), ())]
        for child in node["o"]:
            factors = _field_terms(child)
            output = [
                (left_coefficient * right_coefficient, left_ops + right_ops)
                for left_coefficient, left_ops in output
                for right_coefficient, right_ops in factors
            ]
            if len(output) > RESOURCE_LIMITS["max_field_terms"]:
                raise SchemaError("single symbolic field expansion exceeds cap")
        return output
    raise AssertionError(tag)


def _elementary_pauli(kind: int, mode: int) -> List[Tuple[PauliKey, Gaussian]]:
    bit = 1 << mode
    if kind == 2:
        return [((0, 0), (Fraction(1, 2), Fraction(0))), ((0, bit), (Fraction(-1, 2), Fraction(0)))]
    prefix = bit - 1
    imaginary = Fraction(-1, 2) if kind == 0 else Fraction(1, 2)
    return [
        ((bit, prefix), (Fraction(1, 2), Fraction(0))),
        ((bit, prefix | bit), (Fraction(0), imaginary)),
    ]


def _field_pauli_expansion(
    backend: Any, field_items: Sequence[FieldTerm]
) -> Dict[PauliKey, Gaussian]:
    output: Dict[PauliKey, Gaussian] = {}
    for field_coefficient, operators in field_items:
        expansion: Dict[PauliKey, Gaussian] = {
            (0, 0): (field_coefficient, Fraction(0))
        }
        for kind, mode in operators:
            updated: Dict[PauliKey, Gaussian] = {}
            for left_key, left_coefficient in expansion.items():
                for right_key, right_coefficient in _elementary_pauli(kind, mode):
                    phase, key = backend._pauli_multiply(left_key, right_key)
                    coefficient = backend._g_i_power(
                        backend._g_mul(left_coefficient, right_coefficient), phase
                    )
                    backend._add_term(updated, key, coefficient)
            expansion = updated
        for key, coefficient in expansion.items():
            backend._add_term(output, key, coefficient)
        if len(output) > RESOURCE_LIMITS["max_pauli_terms"]:
            raise SchemaError("field JW Pauli expansion exceeds cap")
    # The physical fixture is [B3,D]; D3=-i[B3,D].
    return {key: (value[1], -value[0]) for key, value in output.items()}


def _fixture_pauli_expansion(
    backend: Any, field_by_term: Sequence[Sequence[FieldTerm]]
) -> Dict[PauliKey, Gaussian]:
    total_field_terms = sum(len(items) for items in field_by_term)
    if total_field_terms != EXPECTED_FIELD_TERM_COUNT:
        raise VerificationError("fixture field-term count mismatch")
    return _field_pauli_expansion(
        backend, [item for items in field_by_term for item in items]
    )


def _direct_d3(module: Any, backend: Any) -> Tuple[Dict[PauliKey, Gaussian], Dict[str, int]]:
    counter = module.ComputationCounter()
    groups = backend.canonical_group_expansions(LINEAR_SIZE)
    hamiltonian = backend._merge_expansions([groups[name] for name in module.GROUPS])
    observable, _ = module._observable_expansion(backend, LINEAR_SIZE, "double_occupancy")
    product = module._formal_product_coefficients(backend, groups, observable, counter)
    ideal = module._ideal_coefficients(backend, hamiltonian, observable, counter)
    d3 = module._subtract(backend, product[3], ideal[3])
    if len(d3) != EXPECTED_PAULI_TERM_COUNT:
        raise VerificationError("direct D3 Pauli term count mismatch")
    if backend._expansion_sha256(d3) != DIRECT_D3_SHA256:
        raise VerificationError("direct D3 Pauli digest mismatch")
    return d3, {
        "commutator_pair_products": counter.pair_products,
        "peak_expansion_terms": counter.peak_terms,
    }


def _partition_greedy(terms: Sequence[Mapping[str, Any]]) -> Tuple[List[List[int]], List[frozenset[int]]]:
    supports = [_node_support(term) for term in terms]
    adjacency: Dict[int, set[int]] = {}
    for support in supports:
        for mode in support:
            adjacency.setdefault(mode, set()).update(support - {mode})
    remaining_modes = set(adjacency)
    component_count = 0
    while remaining_modes:
        component_count += 1
        stack = [remaining_modes.pop()]
        while stack:
            neighbours = adjacency[stack.pop()] & remaining_modes
            remaining_modes.difference_update(neighbours)
            stack.extend(neighbours)
    if set(adjacency) != set(range(N_QUBITS)) or component_count != 1:
        raise VerificationError("fixture support graph must be one connected 128-mode component")
    remaining = list(reversed(range(len(terms))))
    clusters: List[List[int]] = []
    cluster_supports: List[frozenset[int]] = []
    while remaining:
        seed = remaining.pop(0)
        selected = [seed]
        support = set(supports[seed])
        if len(support) > CLUSTER_MODE_CAP:
            raise VerificationError("individual symbolic term exceeds cluster cap")
        while remaining:
            additions = [len(supports[index] - support) for index in remaining]
            minimum = min(additions)
            if len(support) + minimum > CLUSTER_MODE_CAP:
                break
            offset = additions.index(minimum)
            picked = remaining.pop(offset)
            selected.append(picked)
            support.update(supports[picked])
        clusters.append(selected)
        cluster_supports.append(frozenset(support))
        if len(clusters) > RESOURCE_LIMITS["max_clusters"]:
            raise SchemaError("cluster count exceeds cap")
    if len(clusters) != EXPECTED_CLUSTER_COUNT:
        raise VerificationError("greedy partition cluster count mismatch")
    return clusters, cluster_supports


def _neel_occupied(global_mode: int) -> bool:
    site, spin = divmod(global_mode, 2)
    row, column = divmod(site, LINEAR_SIZE)
    return spin == (0 if (row + column) % 2 == 0 else 1)


def _transition(coefficient: Fraction, operators: Sequence[FieldOperator], state: int) -> Tuple[int, Fraction] | None:
    value = coefficient
    for kind, mode in reversed(operators):
        bit = 1 << mode
        if kind == 2:
            if not state & bit:
                return None
        elif kind == 1:
            if not state & bit:
                return None
            if (state >> (mode + 1)).bit_count() & 1:
                value = -value
            state ^= bit
        elif kind == 0:
            if state & bit:
                return None
            if (state >> (mode + 1)).bit_count() & 1:
                value = -value
            state ^= bit
        else:
            raise AssertionError(kind)
    return state, value


def _spin_counts(state: int, support: Sequence[int]) -> Tuple[int, int]:
    up = sum(bool(state & (1 << local)) for local, mode in enumerate(support) if mode % 2 == 0)
    down = sum(bool(state & (1 << local)) for local, mode in enumerate(support) if mode % 2 == 1)
    return up, down


def _global_spin_counts(state: int) -> Tuple[int, int]:
    return (
        sum(bool(state & (1 << mode)) for mode in range(0, N_QUBITS, 2)),
        sum(bool(state & (1 << mode)) for mode in range(1, N_QUBITS, 2)),
    )


def _cluster_witness(
    backend: Any,
    cluster_index: int,
    selected: Sequence[int],
    support_set: frozenset[int],
    terms: Sequence[Mapping[str, Any]],
    field_by_term: Sequence[Sequence[FieldTerm]],
    cumulative: Fraction,
) -> Tuple[Dict[str, Any], Fraction]:
    support = sorted(support_set)
    if not 1 <= len(support) <= CLUSTER_MODE_CAP:
        raise VerificationError("cluster support violates mode cap")
    local_index = {mode: index for index, mode in enumerate(support)}
    local_source = sum(1 << local_index[mode] for mode in support if _neel_occupied(mode))
    local_source_counts = _spin_counts(local_source, support)
    source = sum(1 << mode for mode in range(N_QUBITS) if _neel_occupied(mode))
    source_counts = _global_spin_counts(source)
    if source_counts != (32, 32):
        raise VerificationError("global Neel witness is not Nup32/Ndown32")
    amplitudes: Dict[int, Fraction] = {}
    field_count = 0
    for term_index in selected:
        for coefficient, operators in field_by_term[term_index]:
            field_count += 1
            result = _transition(coefficient, operators, source)
            if result is not None:
                target, value = result
                amplitudes[target] = amplitudes.get(target, Fraction(0)) + value
    amplitudes = {state: value for state, value in amplitudes.items() if value}
    if len(amplitudes) > RESOURCE_LIMITS["max_cluster_action_outputs"]:
        raise SchemaError("cluster action output cap exceeded")
    if any(_global_spin_counts(state) != source_counts for state in amplitudes):
        raise VerificationError("cluster action escaped global spin-number sector")
    selected_field_items = [
        item for term_index in selected for item in field_by_term[term_index]
    ]
    cluster_pauli = _field_pauli_expansion(backend, selected_field_items)
    pauli_action: Dict[int, Gaussian] = {}
    for key, coefficient in cluster_pauli.items():
        target, phase = backend._basis_pauli_action(key, source)
        contribution = backend._g_mul(coefficient, phase)
        pauli_action[target] = backend._g_add(
            pauli_action.get(target, (Fraction(0), Fraction(0))), contribution
        )
    pauli_action = {
        state: value for state, value in pauli_action.items() if value != (0, 0)
    }
    scaled_field_action = {
        state: (Fraction(0), -value) for state, value in amplitudes.items()
    }
    if pauli_action != scaled_field_action:
        raise VerificationError("cluster field transition disagrees with exact JW Pauli action")
    lower = max((abs(value) for value in amplitudes.values()), default=Fraction(0))
    cumulative += lower
    action_records = [
        {"target_hex": hex(state), "amplitude": _format_fraction(value)}
        for state, value in sorted(amplitudes.items())
    ]
    record = {
        "cluster_index": cluster_index,
        "symbolic_term_count": len(selected),
        "symbolic_term_indices_sha256": canonical_sha256(list(selected)),
        "symbolic_terms_sha256": canonical_sha256([terms[index] for index in selected]),
        "support_mode_count": len(support),
        "support_global_modes": support,
        "field_term_count": field_count,
        "exact_JW_Pauli_term_count": len(cluster_pauli),
        "exact_JW_Pauli_expansion_sha256": backend._expansion_sha256(cluster_pauli),
        "local_Neel_state_hex": hex(local_source),
        "local_spin_up_particle_count": local_source_counts[0],
        "local_spin_down_particle_count": local_source_counts[1],
        "global_Neel_state_hex": hex(source),
        "global_spin_up_particle_count": source_counts[0],
        "global_spin_down_particle_count": source_counts[1],
        "nonzero_action_output_count": len(amplitudes),
        "action_records_sha256": canonical_sha256(action_records),
        "maximum_absolute_matrix_element_lower_bound": _format_fraction(lower),
        "cumulative_cluster_norm_lower_bound": _format_fraction(cumulative),
        "all_outputs_preserve_global_spin_numbers": True,
        "witness_is_direct_global_Nup32_Ndown32_basis_state": True,
        "field_transition_equals_exact_JW_Pauli_action": True,
    }
    return record, cumulative


_WITNESS_CACHE_BYTES: bytes | None = None


def recompute_witness() -> Dict[str, Any]:
    global _WITNESS_CACHE_BYTES
    if _WITNESS_CACHE_BYTES is not None:
        _read_pinned_sources()
        return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))
    sources = _read_pinned_sources()
    module, backend = _load_observable_runtime(sources[SOURCE_PINS[0]["relative_path"]])
    terms = _validated_fixture(sources[SOURCE_PINS[1]["relative_path"]])
    field_by_term = [_field_terms(term) for term in terms]
    direct, direct_resources = _direct_d3(module, backend)
    fixture_pauli = _fixture_pauli_expansion(backend, field_by_term)
    if fixture_pauli != direct:
        raise VerificationError("physical-fermion fixture JW expansion does not equal exact D3")
    clusters, supports = _partition_greedy(terms)
    cumulative = Fraction(0)
    records: List[Dict[str, Any]] = []
    for index in range(PARTIAL_CLUSTER_COUNT):
        record, cumulative = _cluster_witness(
            backend, index, clusters[index], supports[index], terms, field_by_term,
            cumulative,
        )
        records.append(record)
    if cumulative != EXPECTED_PARTIAL_LOWER_BOUND:
        raise VerificationError("partial cluster norm lower-bound sum mismatch")
    if cumulative <= LEADING_COEFFICIENT_CEILING:
        raise VerificationError("partial cluster lower bound does not exceed ceiling")
    witness = {
        "profile_id": WITNESS_POLICY["profile_id"],
        "D3_identity": {
            "fixture_symbolic_term_count": len(terms),
            "fixture_expanded_field_term_count": sum(len(items) for items in field_by_term),
            "exact_Pauli_term_count": len(direct),
            "exact_Pauli_coefficient_L1": _format_fraction(module._l1(direct)),
            "exact_Pauli_expansion_sha256": backend._expansion_sha256(direct),
            "fixture_JW_expansion_sha256": backend._expansion_sha256(fixture_pauli),
            "physical_fermion_fixture_JW_equals_exact_Pauli_D3": True,
            "fixture_support_mode_count": N_QUBITS,
            "fixture_support_component_count": 1,
        },
        "greedy_partition": {
            "mode_cap": CLUSTER_MODE_CAP,
            "cluster_count": len(clusters),
            "cluster_symbolic_term_counts": [len(cluster) for cluster in clusters],
            "cluster_support_mode_counts": [len(support) for support in supports],
            "partition_term_indices_sha256": canonical_sha256(clusters),
            "first_30_cluster_witnesses": records,
        },
        "uniform_supremum_architecture_infeasibility_proof": {
            "required_uniform_supremum_D3_coefficient_ceiling": _format_fraction(LEADING_COEFFICIENT_CEILING),
            "partial_cluster_count": PARTIAL_CLUSTER_COUNT,
            "k0_partial_sum_of_cluster_norm_lower_bounds": _format_fraction(cumulative),
            "strict_margin_over_ceiling": _format_fraction(cumulative - LEADING_COEFFICIENT_CEILING),
            "k0_partial_lower_bound_exceeds_uniform_ceiling": True,
            "even_exact_norms_for_fixed_43_clusters_cannot_seed_uniform_supremum_certificate": True,
            "k0_leading_contribution_at_R100_from_partial_floor": _format_fraction(
                cumulative / 100**3
            ),
            "per_step_evolved_cluster_triangle_ledger_ruled_out": False,
            "used_as_lower_bound_on_globally_merged_D3_norm": False,
        },
        "decision": {
            "use_fixed_greedy14_cluster_triangle_as_uniform_supremum_bound": False,
            "continue_per_step_evolved_cluster_triangle_ledger": "NOT_ASSESSED_STILL_OPEN",
            "next_required_route": (
                "direct_evolved_observable_interval_propagation_with_dropped_L1_ledger_"
                "or_cross_cluster_cancellation_aware_global_method"
            ),
        },
        "resource_usage": {
            **direct_resources,
            "fixture_node_cap": RESOURCE_LIMITS["max_fixture_nodes"],
            "field_term_count": sum(len(items) for items in field_by_term),
            "cluster_action_witness_count": len(records),
            "cluster_exact_JW_action_cross_check_count": len(records),
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
        "fixture_raw_sha256": FIXTURE_RAW_SHA256,
        "upstream_context": dict(UPSTREAM_CONTEXT),
        "witness_policy": dict(WITNESS_POLICY),
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
            "fixture_raw_sha256", "upstream_context", "witness_policy",
            "resource_limits", "expected_witness_sha256",
            "maximum_positive_status", "scope_claims",
        ),
        "contract",
    )
    if type(item["checker_source_sha256"]) is not str or not SHA256_RE.fullmatch(item["checker_source_sha256"]):
        raise SchemaError("contract checker source hash is malformed")
    if item["checker_source_sha256"] != checker_source_sha256():
        raise SchemaError("contract does not pin this checker source")
    expected = expected_contract_body()
    observed = {key: value for key, value in item.items() if key not in ("checker_source_sha256", "expected_witness_sha256")}
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
                "upstream_context", "witness_policy", "witness_claim", "scope_claims",
            ),
            "certificate",
        )
        for field, expected in (
            ("schema_version", 1),
            ("certificate_type", CERTIFICATE_TYPE),
            ("contract_fingerprint", CONTRACT_FINGERPRINT),
            ("upstream_context", UPSTREAM_CONTEXT),
            ("witness_policy", WITNESS_POLICY),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(cert[field], expected):
                raise SchemaError(f"certificate.{field} does not match contract policy")
        witness = recompute_witness()
        if canonical_sha256(witness) != contract["expected_witness_sha256"]:
            raise VerificationError("recomputed witness digest disagrees with contract")
        if not _strict_equal(cert["witness_claim"], witness):
            raise VerificationError("certificate.witness_claim disagrees with exact recomputation")
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
                "The no-go applies only to using the fixed k=0 greedy14 cluster triangle bound as an R=100 uniform supremum.",
                "A per-step evolved cluster triangle ledger is not ruled out; the k=0 term is weighted by 1/R^3 there.",
                "The cluster-norm lower bounds are not added as a lower bound on the globally merged D3 norm.",
                "Cross-cluster cancellation, alternative partitions, and a direct global half-sector norm remain open.",
                "No actual R=100 product-formula error, truncation budget, physical reference, or READY state is certified.",
                "The upstream symbolic package is not imported; fixture identity is closed by exact JW equality to the pinned Pauli D3 oracle.",
                "The fixture decomposition/order provenance to upstream simplify is external audit metadata, not machine-recomputed by this checker.",
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
