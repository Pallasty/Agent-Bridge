#!/usr/bin/env python3
"""Fail-closed L=2 checkpointed bitset/Fraction propagation checker.

This checker closes one deliberately narrow gap: it propagates two fixed L=2
Hubbard observables through all 112 non-identity rotations of the source-pinned
R=2 mapped circuit.  Every raw group event is a checkpoint boundary.  Exact
``Fraction`` Taylor intervals are rounded *outward* to a fixed rational grid,
then a deterministic top-L1 rule retains at most the full 8-qubit Pauli space
(65,536 terms).  The positive fixture therefore has zero dropped terms, while
the dropped-L1 rule remains explicit and fail-closed.  The checker
independently recomputes every checkpoint digest, quantization-widening record,
and cumulative dropped-L1 ledger.

The result is only a mapped-circuit truncation subcertificate.  In particular,
it does not bound product-formula error relative to exact Hubbard evolution,
does not identify an L=8 workload, and is never READY-gate eligible.
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
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


# Public CLI/API entry points re-execute one bounded source read only after its
# SHA-256 matches the contract pin.  A fresh module receives the exact bytes
# here before ``exec``, excluding stale pyc/import and second-read drift.
if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None


HERE = Path(__file__).resolve().parent

CERTIFICATE_TYPE = "l2_checkpointed_bitset_fraction_propagation_subcertificate_v1"
CONTRACT_FINGERPRINT = "operator_propagation_checkpointed_l2_contract_v1"
CHECKER_FINGERPRINT = "operator_propagation_checkpointed_l2_bitset_fraction_v1"
MAXIMUM_POSITIVE_STATUS = (
    "VERIFIED_L2_MAPPED_CIRCUIT_TRUNCATION_SUBCERTIFICATE"
)
MAPPING_POSITIVE_STATUS = "VERIFIED_CANONICAL_JW_MAPPING_SUBCERTIFICATE"
CHECKPOINT_STATUS = "OUTWARD_QUANTIZED_DETERMINISTIC_TOP_L1_TRUNCATION"
DIAGNOSTIC_STATUS = "APPROXIMATE_FLOAT_STATEVECTOR_DIAGNOSTIC_NOT_PROOF"

N_QUBITS = 8
LINEAR_SIZE = 2
TROTTER_STEPS = 2
TOTAL_TIME = Fraction(1)
U_OVER_T = Fraction(8)
NEEL_BITS_Q0_FIRST = "10010110"
EXPECTED_FORWARD_GATE_COUNT = 112
EXPECTED_RAW_SLICE_COUNT = 20
EXPECTED_FORWARD_GATE_SEQUENCE_SHA256 = (
    "3b3a7979593463681cc24a90c8d042053a433aec22e705b5ac50f614cb2bc5ad"
)
TAYLOR_ORDER = 5
QUANTIZATION_DENOMINATOR = 1 << 32
RETAINED_TERM_CAP = 65_536

RATIONAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)/[1-9][0-9]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DECIMAL_RE = re.compile(
    r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$"
)

RESOURCE_LIMITS = {
    "max_json_bytes": 262_144,
    "max_source_bytes_per_file": 1_048_576,
    "max_qubits": 8,
    "max_observables": 2,
    "max_initial_terms": 16,
    "max_raw_slices": 20,
    "max_gates_per_slice": 12,
    "max_gate_count": 112,
    "max_live_terms": 65_536,
    "retained_term_cap": RETAINED_TERM_CAP,
    "max_taylor_order": TAYLOR_ORDER,
    "max_rational_digits": 256,
    "quantization_denominator": QUANTIZATION_DENOMINATOR,
    "max_checkpoint_bytes": 16_777_216,
}

SOURCE_PINS = (
    {
        "relative_path": "hubbard_jw_mapping_validator.py",
        "role": "positive_mapping_subcertificate_checker_and_gate_builder",
        "sha256": "21ada33e0a45ec2ede6cc75872e17c8292eac6b17b747fc902a5bb1a135c8be6",
    },
    {
        "relative_path": "hubbard_jw_mapping_contract.json",
        "role": "mapping_contract",
        "sha256": "8d1af7c7b17dfd2b92d5c9fae9a1a6dd71e17d3e78b6e8d4fc5aba2123463e01",
    },
    {
        "relative_path": "hubbard_jw_mapping_template.json",
        "role": "positive_mapping_certificate",
        "sha256": "ecd9b2f98483280f3072e2077c83a6d8c115328968226de3c5e7c6f00a75fdaf",
    },
    {
        "relative_path": "pauli_bitset_backend.py",
        "role": "exact_bitset_Pauli_arithmetic_and_checkpoint_serialization",
        "sha256": "6f968e30b9809894dc6a5585c80a29feb4f3cc8dab6da8300473763a90c7a8a5",
    },
    {
        "relative_path": "operator_propagation_certificate_checker.py",
        "role": "exact_Taylor_interval_and_rotation_semantics",
        "sha256": "ade384b1b2258bc5cb3a296d9f7f4c0c85ee374293c2b1a5e4332f4ecba938d4",
    },
    {
        "relative_path": "operator_propagation_l2_witness.py",
        "role": "L2_112_gate_and_float_statevector_diagnostic_source",
        "sha256": "575124ffcb90619b804bd017118b4ed45551b2d56c99b6c056c4d928111e4332",
    },
)

WORKLOAD_IDENTITY = {
    "profile_id": "L2_OBC_U8_tT1_R2_NEEL",
    "linear_size": LINEAR_SIZE,
    "n_qubits": N_QUBITS,
    "boundary_condition": "square_open_boundary_no_wrap",
    "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
    "hamiltonian_convention": (
        "H=-sum_<ij>,sigma(cdag_i_sigma*c_j_sigma+cdag_j_sigma*c_i_sigma)"
        "+8*sum_i n_i_up*n_i_down_unshifted"
    ),
    "rotation_convention": "G_P(theta)=exp(-i*theta*P/2)",
    "heisenberg_order": (
        "reverse_forward_raw_events_and_reverse_gates_within_each_event"
    ),
    "u_over_t": "8/1",
    "total_time": "1/1",
    "trotter_steps": TROTTER_STEPS,
    "neel_bits_q0_first": NEEL_BITS_Q0_FIRST,
    "forward_identity_rotations_omitted_as_global_phase_only": True,
}

PROPAGATION_POLICY = {
    "taylor_order": TAYLOR_ORDER,
    "taylor_interval": (
        "sin_through_2Nplus1_cos_through_2N_next_term_remainder_abs_theta_le_1"
    ),
    "checkpoint_boundary": "after_each_of_20_reversed_raw_group_events",
    "outward_quantization": (
        "lower=floor(lower*D)/D;upper=ceil(upper*D)/D"
    ),
    "quantization_denominator": QUANTIZATION_DENOMINATOR,
    "quantization_widening_l1": (
        "sum_over_terms_max(pre_lower-quant_lower,quant_upper-pre_upper)"
    ),
    "retained_term_cap": RETAINED_TERM_CAP,
    "truncation_order": (
        "descending_interval_abs_upper_then_ascending_numeric_x_mask_z_mask"
    ),
    "dropped_l1": "sum_over_dropped_max(abs(lower),abs(upper))_after_quantization",
    "checkpoint_digest": "source_pinned_pauli_bitset_fraction_interval_checkpoint_v1",
}

SCOPE_CLAIMS = {
    "checker_execution_from_contract_pinned_source_bytes_verified": True,
    "source_pinned_mapping_subcertificate_verified": True,
    "source_pinned_112_gate_sequence_verified": True,
    "fixed_L2_observable_initializations_verified": True,
    "bitset_fraction_interval_propagation_verified": True,
    "outward_quantization_and_widening_ledger_verified": True,
    "deterministic_truncation_dropped_l1_verified": True,
    "canonical_checkpoint_digests_verified": True,
    "product_formula_to_exact_hamiltonian": "NOT_ASSESSED",
    "physical_L8_instance_identity": "NOT_ASSESSED",
    "reference_error_budget": "NOT_ASSESSED",
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    **SCOPE_CLAIMS,
    "checker_execution_from_contract_pinned_source_bytes_verified": False,
    "source_pinned_mapping_subcertificate_verified": False,
    "source_pinned_112_gate_sequence_verified": False,
    "fixed_L2_observable_initializations_verified": False,
    "bitset_fraction_interval_propagation_verified": False,
    "outward_quantization_and_widening_ledger_verified": False,
    "deterministic_truncation_dropped_l1_verified": False,
    "canonical_checkpoint_digests_verified": False,
}

PauliKey = Tuple[int, int]
Interval = Tuple[Fraction, Fraction]
Expansion = Dict[PauliKey, Interval]


class SchemaError(ValueError):
    """Malformed contract/certificate or hard resource-cap violation."""


class VerificationError(ValueError):
    """A well-shaped claim disagrees with independent recomputation."""


def _read_checker_source_bytes() -> bytes:
    maximum = RESOURCE_LIMITS["max_source_bytes_per_file"]
    with Path(__file__).open("rb") as handle:
        source = handle.read(maximum + 1)
    if len(source) > maximum:
        raise SchemaError("checker source exceeds byte cap")
    return source


def checker_source_sha256() -> str:
    source = _VERIFIED_SELF_SOURCE_BYTES
    if source is None:
        source = _read_checker_source_bytes()
    return hashlib.sha256(source).hexdigest()


def _execute_from_verified_self_source(method: str, *arguments: Any) -> Any:
    """Preflight the contract pin, then execute exactly the hashed source."""

    source = _read_checker_source_bytes()
    if not arguments or type(arguments[0]) is not dict:
        raise SchemaError("outer self-exec preflight requires an exact contract object")
    checker_pin = arguments[0].get("checker_source_sha256")
    if type(checker_pin) is not str or not SHA256_RE.fullmatch(checker_pin):
        raise SchemaError("outer self-exec preflight requires canonical checker_source_sha256")
    if hashlib.sha256(source).hexdigest() != checker_pin:
        raise SchemaError("checker source pin mismatch before compile/exec")
    path = Path(__file__).resolve()
    module = types.ModuleType("verified_operator_propagation_checkpointed_l2")
    module.__file__ = str(path)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = source
    exec(compile(source, str(path), "exec"), module.__dict__)
    target = getattr(module, method, None)
    if not callable(target):
        raise SchemaError("verified checker source lacks required entry point")
    return target(*arguments)


def format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def parse_fraction(value: Any, name: str = "rational") -> Fraction:
    if not isinstance(value, str) or not RATIONAL_RE.fullmatch(value):
        raise SchemaError(f"{name} must be a canonical rational string")
    numerator, denominator = value.split("/", 1)
    limit = RESOURCE_LIMITS["max_rational_digits"]
    if len(numerator.lstrip("-")) > limit or len(denominator) > limit:
        raise SchemaError(f"{name} exceeds rational digit cap")
    result = Fraction(int(numerator), int(denominator))
    if value != format_fraction(result):
        raise SchemaError(f"{name} must be reduced and canonical")
    return result


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise SchemaError(f"{name} must be an integer in [{minimum}, {maximum}]")
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


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json_bytes(payload: bytes, name: str, maximum: int) -> Any:
    if len(payload) > maximum:
        raise SchemaError(f"{name} exceeds byte cap")
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


def load_strict_json(
    path: Path, maximum_bytes: int = RESOURCE_LIMITS["max_json_bytes"]
) -> Any:
    if (
        type(maximum_bytes) is not int
        or not 1 <= maximum_bytes <= RESOURCE_LIMITS["max_json_bytes"]
    ):
        raise ValueError("JSON byte cap is invalid")
    with path.open("rb") as handle:
        payload = handle.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise ValueError("JSON file exceeds byte cap")
    return _strict_json_bytes(payload, str(path), maximum_bytes)


def _verified_source_bytes() -> Dict[str, bytes]:
    verified: Dict[str, bytes] = {}
    maximum = RESOURCE_LIMITS["max_source_bytes_per_file"]
    for index, pin in enumerate(SOURCE_PINS):
        path = HERE / pin["relative_path"]
        try:
            with path.open("rb") as handle:
                source = handle.read(maximum + 1)
        except OSError as exc:
            raise SchemaError(f"source pin {index} cannot be read") from exc
        if len(source) > maximum:
            raise SchemaError(f"source pin {index} exceeds byte cap")
        if hashlib.sha256(source).hexdigest() != pin["sha256"]:
            raise SchemaError(f"source pin {index} byte hash mismatch")
        verified[pin["relative_path"]] = source
    return verified


def _module_from_verified_bytes(name: str, filename: str, source: bytes) -> Any:
    path = HERE / filename
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    try:
        exec(compile(source, str(path), "exec"), module.__dict__)
    except Exception as exc:
        raise SchemaError(f"source-pinned module {filename} could not execute") from exc
    return module


def _runtime_dependencies() -> Tuple[Any, Any, Any, Dict[str, bytes], Dict[str, Any]]:
    """Load exact hash-checked dependencies and require positive mapping status."""

    sources = _verified_source_bytes()
    mapping = _module_from_verified_bytes(
        "checkpointed_l2_mapping",
        "hubbard_jw_mapping_validator.py",
        sources["hubbard_jw_mapping_validator.py"],
    )
    # Bind the mapping checker's self-pin to the exact bytes compiled above.
    # Its contract validation therefore cannot select different source bytes
    # between our hash check and execution.
    mapping.checker_source_sha256 = lambda: hashlib.sha256(
        sources["hubbard_jw_mapping_validator.py"]
    ).hexdigest()
    bitset = _module_from_verified_bytes(
        "checkpointed_l2_bitset",
        "pauli_bitset_backend.py",
        sources["pauli_bitset_backend.py"],
    )
    fraction_checker = _module_from_verified_bytes(
        "checkpointed_l2_fraction_checker",
        "operator_propagation_certificate_checker.py",
        sources["operator_propagation_certificate_checker.py"],
    )
    mapping_contract = _strict_json_bytes(
        sources["hubbard_jw_mapping_contract.json"],
        "source-pinned mapping contract",
        RESOURCE_LIMITS["max_json_bytes"],
    )
    mapping_certificate = _strict_json_bytes(
        sources["hubbard_jw_mapping_template.json"],
        "source-pinned mapping certificate",
        RESOURCE_LIMITS["max_json_bytes"],
    )
    mapping_result = mapping.verify_certificate(mapping_contract, mapping_certificate)
    if (
        type(mapping_result) is not dict
        or mapping_result.get("status") != MAPPING_POSITIVE_STATUS
        or mapping_result.get("verified") is not True
        or mapping_result.get("ready_gate_eligible") is not False
    ):
        raise VerificationError("source-pinned mapping subcertificate is not positive")
    digest = mapping_result.get(
        "source_pinned_L2_witness_gate_sequence_sha256"
    )
    if digest != EXPECTED_FORWARD_GATE_SEQUENCE_SHA256:
        raise VerificationError("positive mapping result has the wrong L2 gate digest")
    return mapping, bitset, fraction_checker, sources, mapping_result


def _pauli_string(assignments: Mapping[int, str]) -> str:
    result = ["I"] * N_QUBITS
    for qubit, operator in assignments.items():
        result[qubit] = operator
    return "".join(result)


def initial_observable_terms() -> List[Dict[str, Any]]:
    """Return the two fixed normalized L=2 observables as exact Pauli sums."""

    magnetization: Dict[str, Fraction] = {}
    site_signs = (1, -1, -1, 1)
    for site, sign in enumerate(site_signs):
        magnetization[_pauli_string({2 * site: "Z"})] = Fraction(-sign, 8)
        magnetization[_pauli_string({2 * site + 1: "Z"})] = Fraction(sign, 8)

    occupancy: Dict[str, Fraction] = {"I" * N_QUBITS: Fraction(1, 4)}
    for site in range(4):
        occupancy[_pauli_string({2 * site: "Z"})] = Fraction(-1, 16)
        occupancy[_pauli_string({2 * site + 1: "Z"})] = Fraction(-1, 16)
        occupancy[_pauli_string({2 * site: "Z", 2 * site + 1: "Z"})] = Fraction(1, 16)

    definitions = (
        (
            "staggered_magnetization",
            "(1/4)*sum_(r,c)(-1)^(r+c)*(n_up-n_down)",
            magnetization,
        ),
        (
            "double_occupancy",
            "(1/4)*sum_(r,c)n_up*n_down",
            occupancy,
        ),
    )
    return [
        {
            "observable_id": observable_id,
            "normalization": normalization,
            "terms": [
                {"pauli": pauli, "coefficient": format_fraction(expansion[pauli])}
                for pauli in sorted(expansion)
            ],
        }
        for observable_id, normalization, expansion in definitions
    ]


def expected_observable_profiles() -> List[Dict[str, Any]]:
    return [
        {
            "observable_id": item["observable_id"],
            "normalization": item["normalization"],
            "initial_term_count": len(item["terms"]),
            "initial_terms_sha256": canonical_sha256(item["terms"]),
        }
        for item in initial_observable_terms()
    ]


def _forward_and_backprop_slices(mapping: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    forward = mapping.canonical_nonidentity_gate_sequence(LINEAR_SIZE)
    if not isinstance(forward, list) or len(forward) != EXPECTED_FORWARD_GATE_COUNT:
        raise VerificationError("mapping did not generate exactly 112 nonidentity gates")
    digest = mapping.canonical_sha256(forward)
    if digest != EXPECTED_FORWARD_GATE_SEQUENCE_SHA256:
        raise VerificationError("mapping L2 forward gate sequence digest mismatch")

    raw_events = mapping.raw_strang_events(LINEAR_SIZE)
    if not isinstance(raw_events, list) or len(raw_events) != EXPECTED_RAW_SLICE_COUNT:
        raise VerificationError("mapping did not generate exactly 20 raw events")
    gates_by_event: Dict[int, List[Dict[str, Any]]] = {
        index: [] for index in range(EXPECTED_RAW_SLICE_COUNT)
    }
    for gate in forward:
        event_index = gate.get("group_event_index") if isinstance(gate, Mapping) else None
        if type(event_index) is not int or event_index not in gates_by_event:
            raise VerificationError("forward gate has invalid raw event index")
        gates_by_event[event_index].append(dict(gate))

    backprop: List[Dict[str, Any]] = []
    for slice_index, forward_event_index in enumerate(
        reversed(range(EXPECTED_RAW_SLICE_COUNT))
    ):
        event = raw_events[forward_event_index]
        gates = [
            {"pauli": gate["pauli"], "theta": gate["theta"]}
            for gate in reversed(gates_by_event[forward_event_index])
        ]
        if len(gates) > RESOURCE_LIMITS["max_gates_per_slice"]:
            raise SchemaError("gates-per-slice cap exceeded")
        backprop.append(
            {
                "slice_index": slice_index,
                "forward_event_index": forward_event_index,
                "step_index": event["step_index"],
                "event_in_step": event["event_in_step"],
                "group": event["group"],
                "gates": gates,
            }
        )
    if sum(len(item["gates"]) for item in backprop) != EXPECTED_FORWARD_GATE_COUNT:
        raise VerificationError("backprop slices do not contain exactly 112 gates")
    return forward, backprop, digest


def expected_backprop_sequence_sha256(mapping: Any) -> str:
    _, slices, _ = _forward_and_backprop_slices(mapping)
    return canonical_sha256(slices)


def _apply_pauli_float(state: Sequence[complex], pauli: str) -> List[complex]:
    """Apply a q0-first Pauli string for a non-proof float diagnostic."""

    if len(state) != 1 << N_QUBITS or len(pauli) != N_QUBITS or set(pauli) - set("IXYZ"):
        raise VerificationError("float statevector diagnostic received malformed Pauli")
    output = [0j] * len(state)
    for source, amplitude in enumerate(state):
        if amplitude == 0:
            continue
        target = source
        phase = 1 + 0j
        for qubit, operator in enumerate(pauli):
            occupied = (source >> qubit) & 1
            if operator == "Z":
                phase *= -1 if occupied else 1
            elif operator == "X":
                target ^= 1 << qubit
            elif operator == "Y":
                target ^= 1 << qubit
                phase *= -1j if occupied else 1j
        output[target] += phase * amplitude
    return output


def _mapped_statevector_observables(
    forward: Sequence[Mapping[str, Any]], fraction_checker: Any
) -> Dict[str, float]:
    """Independently replay the pinned mapped circuit using ordinary floats.

    This comparison is explicitly diagnostic.  No float enters any interval,
    truncation, quantization, or checkpoint proof calculation.
    """

    occupied = sum(
        1 << qubit for qubit, bit in enumerate(NEEL_BITS_Q0_FIRST) if bit == "1"
    )
    state = [0j] * (1 << N_QUBITS)
    state[occupied] = 1 + 0j
    for gate in forward:
        theta = fraction_checker.parse_fraction(gate["theta"])
        transformed = _apply_pauli_float(state, gate["pauli"])
        cosine = math.cos(float(theta) / 2)
        sine_factor = -1j * math.sin(float(theta) / 2)
        state = [
            cosine * amplitude + sine_factor * branch
            for amplitude, branch in zip(state, transformed)
        ]

    magnetization = 0.0
    occupancy_value = 0.0
    site_signs = (1, -1, -1, 1)
    for bits, amplitude in enumerate(state):
        probability = abs(amplitude) ** 2
        local_magnetization = 0
        double_count = 0
        for site, sign in enumerate(site_signs):
            up = 1 if bits & (1 << (2 * site)) else 0
            down = 1 if bits & (1 << (2 * site + 1)) else 0
            local_magnetization += sign * (up - down)
            double_count += up * down
        magnetization += probability * local_magnetization / 4
        occupancy_value += probability * double_count / 4
    result = {
        "staggered_magnetization": magnetization,
        "double_occupancy": occupancy_value,
    }
    if any(not math.isfinite(value) for value in result.values()):
        raise VerificationError("float statevector diagnostic is non-finite")
    return result


def expected_contract_body(mapping: Any) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "certificate_type": CERTIFICATE_TYPE,
        "checker_fingerprint": CHECKER_FINGERPRINT,
        "source_pins": list(SOURCE_PINS),
        "workload_identity": dict(WORKLOAD_IDENTITY),
        "propagation_policy": dict(PROPAGATION_POLICY),
        "expected_forward_gate_count": EXPECTED_FORWARD_GATE_COUNT,
        "expected_forward_gate_sequence_sha256": EXPECTED_FORWARD_GATE_SEQUENCE_SHA256,
        "expected_backprop_gate_sequence_sha256": expected_backprop_sequence_sha256(mapping),
        "expected_observables": expected_observable_profiles(),
        "resource_limits": dict(RESOURCE_LIMITS),
        "maximum_positive_status": MAXIMUM_POSITIVE_STATUS,
        "scope_claims": dict(SCOPE_CLAIMS),
    }


def _validate_contract_raise(contract: Any) -> Tuple[Any, Any, Any, Dict[str, bytes], Dict[str, Any]]:
    item = _exact_keys(
        contract,
        (
            "schema_version", "contract_fingerprint", "certificate_type",
            "checker_fingerprint", "checker_source_sha256", "source_pins",
            "workload_identity", "propagation_policy", "expected_forward_gate_count",
            "expected_forward_gate_sequence_sha256",
            "expected_backprop_gate_sequence_sha256", "expected_observables",
            "resource_limits", "maximum_positive_status", "scope_claims",
        ),
        "contract",
    )
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise SchemaError("contract.schema_version must be integer 1")
    if (
        not isinstance(item["checker_source_sha256"], str)
        or not SHA256_RE.fullmatch(item["checker_source_sha256"])
        or item["checker_source_sha256"] != checker_source_sha256()
    ):
        raise SchemaError("contract.checker_source_sha256 does not pin this checker")
    runtime = _runtime_dependencies()
    mapping = runtime[0]
    expected = expected_contract_body(mapping)
    observed_without_checker_hash = {
        key: value for key, value in item.items() if key != "checker_source_sha256"
    }
    if not _strict_equal(observed_without_checker_hash, expected):
        raise SchemaError("contract does not match the fixed checker policy")
    return runtime


def _validate_contract_impl(contract: Any) -> List[str]:
    try:
        _validate_contract_raise(contract)
    except (
        SchemaError, VerificationError, KeyError, TypeError, ValueError, OSError,
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
        SchemaError, VerificationError, KeyError, TypeError, ValueError, OSError,
        RecursionError,
    ) as exc:
        return [str(exc)]


def _fraction_digits(value: Fraction) -> int:
    return max(len(str(abs(value.numerator))), len(str(value.denominator)))


def maximum_expansion_digits(expansion: Expansion) -> int:
    if type(expansion) is not dict or not expansion:
        return 0
    return max(_fraction_digits(endpoint) for interval in expansion.values() for endpoint in interval)


def interval_abs_upper(value: Interval) -> Fraction:
    return max(abs(value[0]), abs(value[1]))


def quantize_interval_outward(value: Interval, denominator: int) -> Interval:
    denominator = _integer(
        denominator,
        "quantization denominator",
        1,
        RESOURCE_LIMITS["quantization_denominator"],
    )
    lower, upper = value
    if type(lower) is not Fraction or type(upper) is not Fraction or lower > upper:
        raise SchemaError("quantize_interval_outward requires a valid Fraction interval")
    lower_tick = (lower.numerator * denominator) // lower.denominator
    upper_tick = -((-upper.numerator * denominator) // upper.denominator)
    return Fraction(lower_tick, denominator), Fraction(upper_tick, denominator)


def quantize_expansion_outward(expansion: Expansion) -> Tuple[Expansion, Fraction]:
    output: Expansion = {}
    widening = Fraction(0)
    for key, interval in expansion.items():
        quantized = quantize_interval_outward(interval, QUANTIZATION_DENOMINATOR)
        if not quantized[0] <= interval[0] <= interval[1] <= quantized[1]:
            raise VerificationError("outward quantization failed containment")
        widening += max(
            interval[0] - quantized[0], quantized[1] - interval[1]
        )
        if quantized != (Fraction(0), Fraction(0)):
            output[key] = quantized
    return output, widening


def truncate_deterministically(expansion: Expansion) -> Tuple[Expansion, Fraction, int]:
    if len(expansion) <= RETAINED_TERM_CAP:
        return dict(expansion), Fraction(0), 0
    ranked = sorted(
        expansion,
        key=lambda key: (
            -interval_abs_upper(expansion[key]), key[0], key[1]
        ),
    )
    retained_keys = ranked[:RETAINED_TERM_CAP]
    dropped_keys = ranked[RETAINED_TERM_CAP:]
    dropped_l1 = sum(
        (interval_abs_upper(expansion[key]) for key in dropped_keys),
        Fraction(0),
    )
    return {key: expansion[key] for key in retained_keys}, dropped_l1, len(dropped_keys)


def computational_basis_expectation(expansion: Expansion) -> Interval:
    occupied_mask = sum(
        1 << qubit for qubit, bit in enumerate(NEEL_BITS_Q0_FIRST) if bit == "1"
    )
    lower = Fraction(0)
    upper = Fraction(0)
    for (x_mask, z_mask), interval in expansion.items():
        if x_mask:
            continue
        sign = -1 if (z_mask & occupied_mask).bit_count() & 1 else 1
        if sign == 1:
            lower += interval[0]
            upper += interval[1]
        else:
            lower -= interval[1]
            upper -= interval[0]
    return lower, upper


def _interval_json(value: Interval) -> Dict[str, str]:
    return {"lower": format_fraction(value[0]), "upper": format_fraction(value[1])}


def _initial_expansion(bitset: Any, observable: Mapping[str, Any]) -> Expansion:
    output: Expansion = {}
    for term in observable["terms"]:
        key = bitset.pauli_string_to_masks(term["pauli"])
        coefficient = parse_fraction(term["coefficient"])
        if key in output:
            raise VerificationError("fixed initial observable contains duplicate key")
        output[key] = (coefficient, coefficient)
    if not 1 <= len(output) <= RESOURCE_LIMITS["max_initial_terms"]:
        raise SchemaError("initial term-count cap exceeded")
    return output


def _checkpoint_claim(
    bitset: Any,
    slice_record: Mapping[str, Any],
    expansion: Expansion,
    post_count: int,
    peak_count: int,
    dropped_count: int,
    dropped_increment: Fraction,
    cumulative_dropped: Fraction,
    widening_increment: Fraction,
    cumulative_widening: Fraction,
    max_digits_slice: int,
) -> Dict[str, Any]:
    digest = bitset.checkpoint_sha256(
        N_QUBITS,
        bitset.expansion_term_records(expansion),
        max_qubits=N_QUBITS,
        max_terms=RETAINED_TERM_CAP,
        max_rational_digits=RESOURCE_LIMITS["max_rational_digits"],
        max_bytes=RESOURCE_LIMITS["max_checkpoint_bytes"],
    )
    return {
        "slice_index": slice_record["slice_index"],
        "forward_event_index": slice_record["forward_event_index"],
        "step_index": slice_record["step_index"],
        "event_in_step": slice_record["event_in_step"],
        "group": slice_record["group"],
        "gate_count": len(slice_record["gates"]),
        "post_propagation_term_count": post_count,
        "peak_live_term_count": peak_count,
        "retained_term_count": len(expansion),
        "dropped_term_count": dropped_count,
        "maximum_rational_digits_in_slice": max_digits_slice,
        "maximum_rational_digits_retained": maximum_expansion_digits(expansion),
        "quantization_l1_widening_increment": format_fraction(widening_increment),
        "cumulative_quantization_l1_widening": format_fraction(cumulative_widening),
        "dropped_l1_increment": format_fraction(dropped_increment),
        "cumulative_dropped_l1": format_fraction(cumulative_dropped),
        "checkpoint_sha256": digest,
        "checkpoint_status": CHECKPOINT_STATUS,
    }


def _propagate_observable(
    bitset: Any,
    fraction_checker: Any,
    observable: Mapping[str, Any],
    slices: Sequence[Mapping[str, Any]],
    direct_value: float,
) -> Dict[str, Any]:
    expansion = _initial_expansion(bitset, observable)
    initial_digest = canonical_sha256(observable["terms"])
    checkpoints: List[Dict[str, Any]] = []
    cumulative_dropped = Fraction(0)
    cumulative_widening = Fraction(0)
    peak_global = len(expansion)
    max_digits_global = maximum_expansion_digits(expansion)

    for slice_record in slices:
        peak_slice = len(expansion)
        max_digits_slice = maximum_expansion_digits(expansion)
        for gate in slice_record["gates"]:
            theta = fraction_checker.parse_fraction(gate["theta"])
            if abs(theta) > 1:
                raise SchemaError("source-pinned gate has |theta| > 1")
            sine, cosine = fraction_checker.taylor_sin_cos_interval(
                theta, TAYLOR_ORDER
            )
            expansion = bitset.propagate_gate(
                expansion,
                bitset.pauli_string_to_masks(gate["pauli"]),
                sine,
                cosine,
                N_QUBITS,
                max_live_terms=RESOURCE_LIMITS["max_live_terms"],
                max_rational_digits=RESOURCE_LIMITS["max_rational_digits"],
            )
            peak_slice = max(peak_slice, len(expansion))
            max_digits_slice = max(
                max_digits_slice, maximum_expansion_digits(expansion)
            )
        post_count = len(expansion)
        quantized, widening_increment = quantize_expansion_outward(expansion)
        retained, dropped_increment, dropped_count = truncate_deterministically(
            quantized
        )
        cumulative_widening += widening_increment
        cumulative_dropped += dropped_increment
        expansion = retained
        peak_global = max(peak_global, peak_slice)
        max_digits_global = max(max_digits_global, max_digits_slice)
        checkpoints.append(
            _checkpoint_claim(
                bitset, slice_record, expansion, post_count, peak_slice,
                dropped_count, dropped_increment, cumulative_dropped,
                widening_increment, cumulative_widening, max_digits_slice,
            )
        )

    retained_interval = computational_basis_expectation(expansion)
    declared_interval = (
        retained_interval[0] - cumulative_dropped,
        retained_interval[1] + cumulative_dropped,
    )
    diagnostic_value = format(direct_value, ".17g")
    contains = float(declared_interval[0]) <= direct_value <= float(declared_interval[1])
    return {
        "observable_id": observable["observable_id"],
        "initial_terms_sha256": initial_digest,
        "initial_term_count": len(observable["terms"]),
        "checkpoint_count": len(checkpoints),
        "checkpoints": checkpoints,
        "final_checkpoint_sha256": checkpoints[-1]["checkpoint_sha256"],
        "final_retained_term_count": len(expansion),
        "peak_live_term_count": peak_global,
        "maximum_rational_digits_observed": max_digits_global,
        "final_retained_expectation_interval": _interval_json(retained_interval),
        "cumulative_quantization_l1_widening": format_fraction(cumulative_widening),
        "cumulative_dropped_l1": format_fraction(cumulative_dropped),
        "declared_mapped_circuit_expectation_interval": _interval_json(declared_interval),
        "statevector_product_formula_diagnostic": {
            "decimal_value": diagnostic_value,
            "contained_in_declared_interval": contains,
            "status": DIAGNOSTIC_STATUS,
            "used_as_proof": False,
        },
    }


def recompute_certificate_claims(runtime: Tuple[Any, Any, Any, Dict[str, bytes], Dict[str, Any]]) -> Dict[str, Any]:
    mapping, bitset, fraction_checker, sources, mapping_result = runtime
    forward, slices, forward_digest = _forward_and_backprop_slices(mapping)
    direct_values = _mapped_statevector_observables(forward, fraction_checker)

    observables = initial_observable_terms()
    observable_claims = [
        _propagate_observable(
            bitset,
            fraction_checker,
            observable,
            slices,
            direct_values[observable["observable_id"]],
        )
        for observable in observables
    ]
    return {
        "source_pinned_mapping": {
            "status": mapping_result["status"],
            "verified": True,
            "contract_sha256": hashlib.sha256(
                sources["hubbard_jw_mapping_contract.json"]
            ).hexdigest(),
            "certificate_sha256": hashlib.sha256(
                sources["hubbard_jw_mapping_template.json"]
            ).hexdigest(),
            "forward_gate_sequence_sha256": forward_digest,
        },
        "forward_gate_count": EXPECTED_FORWARD_GATE_COUNT,
        "forward_gate_sequence_sha256": forward_digest,
        "backprop_gate_sequence_sha256": canonical_sha256(slices),
        "raw_slice_count": len(slices),
        "observable_claims": observable_claims,
    }


def build_template() -> Dict[str, Any]:
    runtime = _runtime_dependencies()
    claims = recompute_certificate_claims(runtime)
    return {
        "schema_version": 1,
        "certificate_type": CERTIFICATE_TYPE,
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "workload_identity": dict(WORKLOAD_IDENTITY),
        "propagation_policy": dict(PROPAGATION_POLICY),
        **claims,
        "scope_claims": dict(SCOPE_CLAIMS),
    }


def _parse_interval_claim(value: Any, name: str) -> None:
    item = _exact_keys(value, ("lower", "upper"), name)
    lower = parse_fraction(item["lower"], f"{name}.lower")
    upper = parse_fraction(item["upper"], f"{name}.upper")
    if lower > upper:
        raise SchemaError(f"{name}.lower exceeds upper")


def _validate_checkpoint_shape(value: Any, observable_index: int, slice_index: int) -> None:
    name = f"certificate.observable_claims[{observable_index}].checkpoints[{slice_index}]"
    item = _exact_keys(
        value,
        (
            "slice_index", "forward_event_index", "step_index", "event_in_step",
            "group", "gate_count", "post_propagation_term_count",
            "peak_live_term_count", "retained_term_count", "dropped_term_count",
            "maximum_rational_digits_in_slice", "maximum_rational_digits_retained",
            "quantization_l1_widening_increment",
            "cumulative_quantization_l1_widening", "dropped_l1_increment",
            "cumulative_dropped_l1", "checkpoint_sha256", "checkpoint_status",
        ),
        name,
    )
    _integer(item["slice_index"], f"{name}.slice_index", slice_index, slice_index)
    _integer(item["forward_event_index"], f"{name}.forward_event_index", 0, 19)
    _integer(item["step_index"], f"{name}.step_index", 0, 1)
    _integer(item["event_in_step"], f"{name}.event_in_step", 0, 9)
    if item["group"] not in {"H1", "H2", "HU", "H3", "H4"}:
        raise SchemaError(f"{name}.group is invalid")
    _integer(item["gate_count"], f"{name}.gate_count", 0, RESOURCE_LIMITS["max_gates_per_slice"])
    for field in (
        "post_propagation_term_count", "peak_live_term_count",
    ):
        _integer(item[field], f"{name}.{field}", 0, RESOURCE_LIMITS["max_live_terms"])
    _integer(item["retained_term_count"], f"{name}.retained_term_count", 0, RETAINED_TERM_CAP)
    _integer(item["dropped_term_count"], f"{name}.dropped_term_count", 0, RESOURCE_LIMITS["max_live_terms"])
    for field in (
        "maximum_rational_digits_in_slice", "maximum_rational_digits_retained"
    ):
        _integer(item[field], f"{name}.{field}", 0, RESOURCE_LIMITS["max_rational_digits"])
    for field in (
        "quantization_l1_widening_increment",
        "cumulative_quantization_l1_widening", "dropped_l1_increment",
        "cumulative_dropped_l1",
    ):
        if parse_fraction(item[field], f"{name}.{field}") < 0:
            raise SchemaError(f"{name}.{field} must be nonnegative")
    if not isinstance(item["checkpoint_sha256"], str) or not SHA256_RE.fullmatch(item["checkpoint_sha256"]):
        raise SchemaError(f"{name}.checkpoint_sha256 must be lowercase sha256")
    if item["checkpoint_status"] != CHECKPOINT_STATUS:
        raise SchemaError(f"{name}.checkpoint_status does not match policy")


def _validate_observable_claim_shape(value: Any, index: int) -> None:
    name = f"certificate.observable_claims[{index}]"
    item = _exact_keys(
        value,
        (
            "observable_id", "initial_terms_sha256", "initial_term_count",
            "checkpoint_count", "checkpoints", "final_checkpoint_sha256",
            "final_retained_term_count", "peak_live_term_count",
            "maximum_rational_digits_observed",
            "final_retained_expectation_interval",
            "cumulative_quantization_l1_widening", "cumulative_dropped_l1",
            "declared_mapped_circuit_expectation_interval",
            "statevector_product_formula_diagnostic",
        ),
        name,
    )
    if item["observable_id"] not in {
        "staggered_magnetization", "double_occupancy"
    }:
        raise SchemaError(f"{name}.observable_id is invalid")
    for field in ("initial_terms_sha256", "final_checkpoint_sha256"):
        if not isinstance(item[field], str) or not SHA256_RE.fullmatch(item[field]):
            raise SchemaError(f"{name}.{field} must be lowercase sha256")
    _integer(item["initial_term_count"], f"{name}.initial_term_count", 1, RESOURCE_LIMITS["max_initial_terms"])
    _integer(item["checkpoint_count"], f"{name}.checkpoint_count", EXPECTED_RAW_SLICE_COUNT, EXPECTED_RAW_SLICE_COUNT)
    checkpoints = item["checkpoints"]
    if not isinstance(checkpoints, list) or len(checkpoints) != EXPECTED_RAW_SLICE_COUNT:
        raise SchemaError(f"{name}.checkpoints must contain exactly 20 entries")
    for slice_index, checkpoint in enumerate(checkpoints):
        _validate_checkpoint_shape(checkpoint, index, slice_index)
    _integer(item["final_retained_term_count"], f"{name}.final_retained_term_count", 0, RETAINED_TERM_CAP)
    _integer(item["peak_live_term_count"], f"{name}.peak_live_term_count", 0, RESOURCE_LIMITS["max_live_terms"])
    _integer(item["maximum_rational_digits_observed"], f"{name}.maximum_rational_digits_observed", 0, RESOURCE_LIMITS["max_rational_digits"])
    _parse_interval_claim(item["final_retained_expectation_interval"], f"{name}.final_retained_expectation_interval")
    _parse_interval_claim(item["declared_mapped_circuit_expectation_interval"], f"{name}.declared_mapped_circuit_expectation_interval")
    for field in ("cumulative_quantization_l1_widening", "cumulative_dropped_l1"):
        if parse_fraction(item[field], f"{name}.{field}") < 0:
            raise SchemaError(f"{name}.{field} must be nonnegative")
    diagnostic = _exact_keys(
        item["statevector_product_formula_diagnostic"],
        ("decimal_value", "contained_in_declared_interval", "status", "used_as_proof"),
        f"{name}.statevector_product_formula_diagnostic",
    )
    if not isinstance(diagnostic["decimal_value"], str) or not DECIMAL_RE.fullmatch(diagnostic["decimal_value"]):
        raise SchemaError(f"{name} diagnostic decimal_value is invalid")
    if not math.isfinite(float(diagnostic["decimal_value"])):
        raise SchemaError(f"{name} diagnostic decimal_value must be finite")
    if type(diagnostic["contained_in_declared_interval"]) is not bool:
        raise SchemaError(f"{name} diagnostic containment must be bool")
    if diagnostic["status"] != DIAGNOSTIC_STATUS or diagnostic["used_as_proof"] is not False:
        raise SchemaError(f"{name} diagnostic status must remain non-proof")


def _validate_certificate_shape(certificate: Any, contract: Mapping[str, Any]) -> Mapping[str, Any]:
    cert = _exact_keys(
        certificate,
        (
            "schema_version", "certificate_type", "contract_fingerprint",
            "workload_identity", "propagation_policy", "source_pinned_mapping",
            "forward_gate_count", "forward_gate_sequence_sha256",
            "backprop_gate_sequence_sha256", "raw_slice_count",
            "observable_claims", "scope_claims",
        ),
        "certificate",
    )
    if type(cert["schema_version"]) is not int or cert["schema_version"] != 1:
        raise SchemaError("certificate.schema_version must be integer 1")
    for field, expected in (
        ("certificate_type", CERTIFICATE_TYPE),
        ("contract_fingerprint", CONTRACT_FINGERPRINT),
        ("workload_identity", WORKLOAD_IDENTITY),
        ("propagation_policy", PROPAGATION_POLICY),
        ("scope_claims", SCOPE_CLAIMS),
    ):
        if not _strict_equal(cert[field], expected):
            raise SchemaError(f"certificate.{field} does not match contract policy")
    mapping_claim = _exact_keys(
        cert["source_pinned_mapping"],
        (
            "status", "verified", "contract_sha256", "certificate_sha256",
            "forward_gate_sequence_sha256",
        ),
        "certificate.source_pinned_mapping",
    )
    if mapping_claim["status"] != MAPPING_POSITIVE_STATUS or mapping_claim["verified"] is not True:
        raise SchemaError("certificate.source_pinned_mapping is not positive")
    for field in ("contract_sha256", "certificate_sha256", "forward_gate_sequence_sha256"):
        if not isinstance(mapping_claim[field], str) or not SHA256_RE.fullmatch(mapping_claim[field]):
            raise SchemaError(f"certificate.source_pinned_mapping.{field} must be sha256")
    _integer(cert["forward_gate_count"], "certificate.forward_gate_count", EXPECTED_FORWARD_GATE_COUNT, EXPECTED_FORWARD_GATE_COUNT)
    _integer(cert["raw_slice_count"], "certificate.raw_slice_count", EXPECTED_RAW_SLICE_COUNT, EXPECTED_RAW_SLICE_COUNT)
    for field in ("forward_gate_sequence_sha256", "backprop_gate_sequence_sha256"):
        if not isinstance(cert[field], str) or not SHA256_RE.fullmatch(cert[field]):
            raise SchemaError(f"certificate.{field} must be lowercase sha256")
    claims = cert["observable_claims"]
    if not isinstance(claims, list) or len(claims) != 2:
        raise SchemaError("certificate.observable_claims must contain exactly two entries")
    for index, claim in enumerate(claims):
        _validate_observable_claim_shape(claim, index)
    if [claim["observable_id"] for claim in claims] != [
        "staggered_magnetization", "double_occupancy"
    ]:
        raise SchemaError("certificate observables must be in canonical order")
    return cert


def _verify_certificate_impl(contract: Any, certificate: Any) -> Dict[str, Any]:
    started = time.monotonic()
    base = {
        "status": "INVALID_SCHEMA",
        "verified": False,
        "ready_gate_eligible": False,
        "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
        "errors": [],
    }
    try:
        runtime = _validate_contract_raise(contract)
        cert = _validate_certificate_shape(certificate, contract)
        if cert["forward_gate_sequence_sha256"] != contract["expected_forward_gate_sequence_sha256"]:
            raise VerificationError("certificate forward gate digest disagrees with contract pin")
        if cert["backprop_gate_sequence_sha256"] != contract["expected_backprop_gate_sequence_sha256"]:
            raise VerificationError("certificate backprop gate digest disagrees with contract pin")
        recomputed = recompute_certificate_claims(runtime)
        for field in (
            "source_pinned_mapping", "forward_gate_count",
            "forward_gate_sequence_sha256", "backprop_gate_sequence_sha256",
            "raw_slice_count", "observable_claims",
        ):
            if not _strict_equal(cert[field], recomputed[field]):
                raise VerificationError(f"certificate.{field} disagrees with recomputation")
    except (SchemaError, RecursionError) as exc:
        base["errors"] = [str(exc)]
        base["verification_runtime_seconds"] = time.monotonic() - started
        return base
    except (VerificationError, KeyError, TypeError, ValueError, OSError) as exc:
        base["status"] = "VERIFICATION_FAILED"
        base["errors"] = [str(exc)]
        base["verification_runtime_seconds"] = time.monotonic() - started
        return base

    base.update(
        {
            "status": MAXIMUM_POSITIVE_STATUS,
            "verified": True,
            "scope_claims": dict(SCOPE_CLAIMS),
            "checker_executed_source_bytes_sha256_verified": True,
            "source_pins_verified": True,
            "mapping_subcertificate_verified": True,
            "forward_gate_sequence_verified": True,
            "recomputed_claims": recomputed,
            "verification_runtime_seconds": time.monotonic() - started,
            "limitations": [
                "Only the fixed source-pinned L=2 mapped R=2 circuit is propagated.",
                "Taylor and quantization intervals are rigorous for that declared circuit; the float statevector comparison is diagnostic only.",
                "The cumulative dropped-L1 interval is reported even when too loose for a useful accuracy target.",
                "No product-formula error relative to exact Hubbard evolution is assessed.",
                "No L=8 workload identity or reference-error budget is assessed.",
                "This subcertificate is never eligible for a READY gate.",
            ],
            "errors": [],
        }
    )
    return base


def verify_certificate(contract: Any, certificate: Any) -> Dict[str, Any]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _verify_certificate_impl(contract, certificate)
    started = time.monotonic()
    try:
        return _execute_from_verified_self_source(
            "_verify_certificate_impl", contract, certificate
        )
    except (
        SchemaError, VerificationError, KeyError, TypeError, ValueError, OSError,
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
    # This intentionally narrow subcertificate can never qualify READY.
    return 1


if __name__ == "__main__":
    sys.exit(main())
