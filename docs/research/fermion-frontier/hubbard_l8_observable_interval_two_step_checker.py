#!/usr/bin/env python3
"""Fail-closed parent--child custody for two fused L=8 mapped steps.

This checker deliberately extends the source-pinned one-step interval checker
by exactly one child transition.  It verifies canonical compressed boundary-1
and boundary-2 fixed-tick expansions for both observables, proves boundary 1 is
the exact retained output and inherited dropped-L1 ledger of the positive
parent certificate, and applies the parent's pinned arithmetic primitives for
one further 1,152-gate fused step with 144 fresh checkpoints.

There is an explicit truncation boundary between the two steps.  In
particular, the final H1 half-stage of one repeated step and the initial H1
half-stage of the next are not fused across that boundary.  The cumulative
dropped-L1 ledger is E2 = E1 + d2.  The final expectation interval is the
retained boundary-2 interval enlarged by +/-E2.

This is only a two-step mapped product-formula subcertificate.  It does not
bound product-formula error to exact Hubbard evolution, certify the remaining
98 steps, qualify a physical reference, or enable READY.  The CLI always
exits 1.

All transport, semantic, state, and transition identities are contract-bound.
Any unresolved development placeholder fails closed before reading a sidecar.
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
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
CERTIFICATE_TYPE = "l8_two_step_fixed_point_interval_child_chain_subcertificate_v1"
CONTRACT_FINGERPRINT = "hubbard_l8_observable_interval_two_step_contract_v1"
CHECKER_FINGERPRINT = "hubbard_l8_two_step_interval_child_v1"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_L8_TWO_STEP_MAPPED_INTERVAL_CHILD_CHAIN_SUBCERTIFICATE"
PARENT_POSITIVE_STATUS = "VERIFIED_L8_ONE_STEP_MAPPED_INTERVAL_TRUNCATION_SUBCERTIFICATE"

CHECKPOINT_FORMAT = "l8_fixed_tick_expansion_checkpoint_v1"
STATE_FINGERPRINT = "hubbard_l8_mapped_observable_interval_state_v1"
TRANSITION_FINGERPRINT = "l8_fixed_tick_interval_child_transition_v1"
HEISENBERG_DIRECTION = "repeat_fixed_fused_step_backpropagation_no_cross_step_fusion"
OBSERVABLES = ("staggered_magnetization", "double_occupancy")
N_QUBITS = 128
TICK_DENOMINATOR = 1 << 64
RETAINED_TERM_CAP = 65_536
GATES_PER_CHECKPOINT = 8
EXPECTED_GATE_COUNT = 1_152
EXPECTED_CHECKPOINT_COUNT = 144
BOUNDARY_STEPS = (1, 2)
CANONICAL_B85_LINE_LENGTH = 100

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MASK_RE = re.compile(r"^0x(?:0|[1-9a-f][0-9a-f]*)$")
INTEGER_RE = re.compile(r"^(?:0|-?[1-9][0-9]*)$")
PLACEHOLDER_RE = re.compile(r"^__PLACEHOLDER_[A-Z0-9_]+__$")

RESOURCE_LIMITS = {
    "max_json_bytes": 1_048_576,
    "max_checker_source_bytes": 196_608,
    "max_pinned_source_bytes": 1_048_576,
    "max_checkpoint_sidecars": 4,
    "max_sidecar_encoded_bytes": 4_194_304,
    "max_sidecar_compressed_bytes": 4_194_304,
    "max_sidecar_raw_bytes": 16_777_216,
    "max_total_sidecar_encoded_bytes": 16_777_216,
    "max_terms_per_sidecar": RETAINED_TERM_CAP,
    "max_tick_integer_digits": 64,
    "max_tick_integer_bits": 192,
    "max_mask_bits": N_QUBITS,
    "max_gate_count_per_child": EXPECTED_GATE_COUNT,
    "max_checkpoints_per_child": EXPECTED_CHECKPOINT_COUNT,
    "max_single_expansion_terms": 262_144,
    "max_term_gate_visits_per_child": 200_000_000,
}

SOURCE_PINS = (
    {
        "relative_path": "hubbard_l8_observable_interval_step_checker.py",
        "role": "positive_one_step_checker_and_fixed_tick_propagation_primitives",
        "sha256": "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_step_contract.json",
        "role": "positive_one_step_contract",
        "sha256": "b187de82cb9448aec25e657e1d6a8b1c144a8a2a61559237eebe322ead34552b",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_step_template.json",
        "role": "positive_one_step_certificate",
        "sha256": "22f7c7a6903a88524b06999f7ae74acfeb59ed5b5bf56ab6a09e0914ad9f2ab3",
    },
)


# Frozen after canonical sidecar generation.  Keep this assignment explicit so
# review can compare every transport-layer pin directly with the sidecar
# manifest without executing helper code.
CHECKPOINT_SPECS = (
    {
        "relative_path": "hubbard_l8_interval_checkpoints/staggered_magnetization_boundary_001.b85",
        "observable_id": "staggered_magnetization",
        "step_index": 1,
        "encoded_sha256": "97e02e5530880f73abc905f2de8bcfd9eaf32f21fec077aa2978158afb78d7e9",
        "compressed_sha256": "3f22eac9ccc3697a3711014a54a370d9174dd4635fa1e9a3a6b3f5ff44d23034",
        "raw_sha256": "cd7fdf1b6d15eb13ba816db0868bd275b59374bd862ddddc077e5962e4298e15",
    },
    {
        "relative_path": "hubbard_l8_interval_checkpoints/staggered_magnetization_boundary_002.b85",
        "observable_id": "staggered_magnetization",
        "step_index": 2,
        "encoded_sha256": "ba21b10983c878c59d345bffff9cbee83eef3ac58b2e74b6eee9e93be2446aea",
        "compressed_sha256": "c430a2e6f0e1ad584fc68d65fcc0f06b42cc3be53cc291ead408df14679a997c",
        "raw_sha256": "c29f3d2cc7a1e903fc1b45a21c56b0aa4a3d4f7005a775aecb353afdf8f509c9",
    },
    {
        "relative_path": "hubbard_l8_interval_checkpoints/double_occupancy_boundary_001.b85",
        "observable_id": "double_occupancy",
        "step_index": 1,
        "encoded_sha256": "05f58417e16a2d65803c5ab7c0ca6d809b2775553f5facf544846b57352621b9",
        "compressed_sha256": "0cf1b997ac312e63ac40b23bd00b3f49c6db362a7c53c3b6c3c04ff58cbc7b81",
        "raw_sha256": "4f5a1c018d4f0caad0ebddce4aa7545405b4f602c212f958a0e6b0aa6ea2bd73",
    },
    {
        "relative_path": "hubbard_l8_interval_checkpoints/double_occupancy_boundary_002.b85",
        "observable_id": "double_occupancy",
        "step_index": 2,
        "encoded_sha256": "f92d5eadc01e1d9ebef86328b9eed92d867a2dd79b8bb2ba0baa821fe3b037ab",
        "compressed_sha256": "8054077eade80f8d57d0ee5c4ed378c4ac38dee40d4e9d083dfa31d2340697b7",
        "raw_sha256": "fd06c71e8e86ed0a79a9accc7f0b0267395a400591372fa436e4c856c5703239",
    },
)

# These redundant exact outputs make accidental regeneration under a changed
# policy fail before a new contract can be issued.  The contract's full
# expected-witness digest remains the final aggregate pin.
EXPECTED_STEP2_EXACT = {
    "staggered_magnetization": {
        "expansion_sha256": "c4d66ec8137b3fafb57817fe128c7ae91abed9dab1183cf4b9faff30224bc366",
        "state_sha256": "ae3fe69120963d954b1c82a5adb4d142958341670f9b67acf0f18204f771048e",
        "child_dropped_l1_ticks": "207375793741436",
        "transition_sha256": "019b813fcd2ff64b419d091785b78a9cb57dc3ccd4c35140059fc5e0279fed27",
    },
    "double_occupancy": {
        "expansion_sha256": "9376e6a4e2229ec0d995e36dbcf2a509a5dbf2f9bb276154458cb6ebcb91ff80",
        "state_sha256": "8a3477bd3c145e95853e411ccdf60f6c23ce674dffa02fa0a1933c578a36979b",
        "child_dropped_l1_ticks": "2152392847533726",
        "transition_sha256": "57b8396e446f01ee6467ea2dee54a25af8bc257dea58ee5ed2b5abe77647fb71",
    },
}

WORKLOAD_IDENTITY = {
    "profile_id": "L8_OBC_U8_T1_R100_NEEL_FUSED_STRANG_TWO_STEP_CHILD_CHAIN",
    "root_profile_id": "L8_OBC_U8_T1_R100_NEEL_FUSED_STRANG_ONE_STEP",
    "linear_size": 8,
    "n_sites": 64,
    "n_qubits": N_QUBITS,
    "boundary_condition": "square_open_boundary_no_wrap",
    "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
    "hamiltonian_convention": (
        "H=-sum_<ij>,sigma(cdag_i_sigma*c_j_sigma+cdag_j_sigma*c_i_sigma)"
        "+8*sum_i n_i_up*n_i_down_unshifted"
    ),
    "rotation_convention": "G_P(theta)=exp(-i*theta*P/2)",
    "heisenberg_direction": HEISENBERG_DIRECTION,
    "total_time": "1/1",
    "trotter_steps": 100,
    "certified_repeated_step_count": 2,
    "step_duration": "1/100",
    "initial_state": "checkerboard_Neel_A_up_B_down_Nup32_Ndown32",
}

PROPAGATION_POLICY = {
    "root_parent_positive_status": PARENT_POSITIVE_STATUS,
    "fixed_fused_stage_count_per_step": 9,
    "fixed_gate_count_per_step": EXPECTED_GATE_COUNT,
    "fixed_checkpoint_count_per_step": EXPECTED_CHECKPOINT_COUNT,
    "gates_per_checkpoint": GATES_PER_CHECKPOINT,
    "tick_denominator": TICK_DENOMINATOR,
    "retained_term_cap": RETAINED_TERM_CAP,
    "parent_fixed_tick_primitives_reused_from_pinned_source_bytes": True,
    "boundary_one_equals_positive_parent_retained_output": True,
    "step_two_starts_from_canonical_boundary_one_sidecar": True,
    "cross_step_H1_half_stage_fusion": False,
    "drop_ledger_recurrence": "E2_ticks=E1_ticks+d2_ticks",
    "final_expectation_rule": (
        "boundary2_retained_Neel_interval_expanded_by_plus_minus_E2_ticks"
    ),
    "sidecar_transport": "canonical_100_column_LF_base85_of_single_zlib_stream",
    "sidecar_payload": "canonical_compact_sorted_key_JSON",
    "sidecar_format": CHECKPOINT_FORMAT,
    "state_fingerprint": STATE_FINGERPRINT,
    "transition_fingerprint": TRANSITION_FINGERPRINT,
}

SCOPE_CLAIMS = {
    "checker_execution_from_contract_pinned_source_bytes_verified": True,
    "same_byte_parent_checker_contract_certificate_verified": True,
    "positive_parent_one_step_certificate_verified": True,
    "canonical_compressed_boundary_sidecar_custody_verified": True,
    "boundary_one_exactly_matches_parent_retained_state_verified": True,
    "step_two_uses_parent_pinned_fixed_tick_primitives_verified": True,
    "step_two_1152_gate_144_checkpoint_transition_verified": True,
    "no_cross_step_fusion_verified": True,
    "boundary_two_exact_expansion_equality_verified": True,
    "two_step_cumulative_dropped_L1_recurrence_verified": True,
    "two_step_mapped_circuit_expectation_intervals_verified": True,
    "remaining_98_mapped_steps": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
    "interval_box_optimality": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    key: (False if value is True else value) for key, value in SCOPE_CLAIMS.items()
}

PauliKey = Tuple[int, int]
TickInterval = Tuple[int, int]
TickExpansion = Dict[PauliKey, TickInterval]


class SchemaError(ValueError):
    """Malformed input, unresolved pin, source drift, or resource failure."""


class VerificationError(ValueError):
    """A well-shaped exact claim disagrees with recomputation."""


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


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("value cannot be canonically serialized") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


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
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise SchemaError(f"{name} is not strict JSON: {exc}") from exc


def load_strict_json(path: Path) -> Any:
    with path.open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_json_bytes"] + 1)
    return _strict_json_bytes(payload, path.name)


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
    module = types.ModuleType("verified_hubbard_l8_interval_two_step")
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


def _preflight_checkpoint_files() -> None:
    total = 0
    for spec in CHECKPOINT_SPECS:
        path = HERE / spec["relative_path"]
        with path.open("rb") as handle:
            payload = handle.read(RESOURCE_LIMITS["max_sidecar_encoded_bytes"] + 1)
        if len(payload) > RESOURCE_LIMITS["max_sidecar_encoded_bytes"]:
            raise SchemaError(f"encoded checkpoint exceeds cap: {path.name}")
        if hashlib.sha256(payload).hexdigest() != spec["encoded_sha256"]:
            raise SchemaError(f"encoded checkpoint hash mismatch: {path.name}")
        total += len(payload)
    if total > RESOURCE_LIMITS["max_total_sidecar_encoded_bytes"]:
        raise SchemaError("aggregate sidecar encoded-byte cap exceeded")


def _load_positive_parent(sources: Mapping[str, bytes]) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    source = sources["hubbard_l8_observable_interval_step_checker.py"]
    module = types.ModuleType("pinned_hubbard_l8_observable_interval_parent")
    module.__file__ = str(HERE / "hubbard_l8_observable_interval_step_checker.py")
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = source
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    contract = _strict_json_bytes(
        sources["hubbard_l8_observable_interval_step_contract.json"],
        "parent contract",
    )
    certificate = _strict_json_bytes(
        sources["hubbard_l8_observable_interval_step_template.json"],
        "parent certificate",
    )
    result = module.verify_certificate(contract, certificate)
    if result.get("status") != PARENT_POSITIVE_STATUS or result.get("verified") is not True:
        raise VerificationError("same-byte source-pinned parent certificate is not positive")
    witness = result.get("recomputed_witness")
    if type(witness) is not dict or not _strict_equal(certificate.get("witness_claim"), witness):
        raise VerificationError("positive parent did not return its exact certificate witness")
    if canonical_sha256(witness) != contract.get("expected_witness_sha256"):
        raise VerificationError("parent expected-witness pin mismatch")
    return module, contract, witness


def _require_resolved_sha256(value: Any, name: str) -> str:
    if type(value) is not str:
        raise SchemaError(f"{name} must be a string")
    if PLACEHOLDER_RE.fullmatch(value):
        raise SchemaError(f"{name} is an unresolved placeholder")
    if not SHA256_RE.fullmatch(value):
        raise SchemaError(f"{name} must be lowercase sha256")
    return value


def _canonical_integer(value: Any, name: str, *, nonnegative: bool = False) -> int:
    if type(value) is not str or not INTEGER_RE.fullmatch(value):
        raise SchemaError(f"{name} must be a canonical decimal integer string")
    digits = value[1:] if value.startswith("-") else value
    if len(digits) > RESOURCE_LIMITS["max_tick_integer_digits"]:
        raise SchemaError(f"{name} exceeds decimal digit cap")
    result = int(value)
    if abs(result).bit_length() > RESOURCE_LIMITS["max_tick_integer_bits"]:
        raise SchemaError(f"{name} exceeds integer bit cap")
    if nonnegative and result < 0:
        raise SchemaError(f"{name} must be nonnegative")
    return result


def _canonical_mask(value: Any, name: str) -> int:
    if type(value) is not str or not MASK_RE.fullmatch(value):
        raise SchemaError(f"{name} must be canonical lowercase hexadecimal")
    result = int(value, 16)
    if result.bit_length() > RESOURCE_LIMITS["max_mask_bits"]:
        raise SchemaError(f"{name} exceeds Pauli mask width")
    if hex(result) != value:
        raise SchemaError(f"{name} is not canonical hex() spelling")
    return result


def _canonical_b85_decode(encoded: bytes, name: str) -> bytes:
    if not encoded or len(encoded) > RESOURCE_LIMITS["max_sidecar_encoded_bytes"]:
        raise SchemaError(f"{name} encoded size is outside cap")
    if not encoded.endswith(b"\n"):
        raise SchemaError(f"{name} must end with one canonical LF")
    body = encoded[:-1]
    if not body or body.endswith(b"\n") or b"\r" in body:
        raise SchemaError(f"{name} has noncanonical Base85 wrapping")
    lines = body.split(b"\n")
    if any(len(line) != CANONICAL_B85_LINE_LENGTH for line in lines[:-1]):
        raise SchemaError(f"{name} nonfinal Base85 lines must have 100 columns")
    if not 1 <= len(lines[-1]) <= CANONICAL_B85_LINE_LENGTH:
        raise SchemaError(f"{name} final Base85 line length is invalid")
    compact = b"".join(lines)
    try:
        compact.decode("ascii")
        compressed = base64.b85decode(compact)
    except (UnicodeDecodeError, ValueError) as exc:
        raise SchemaError(f"{name} Base85 decoding failed") from exc
    if len(compressed) > RESOURCE_LIMITS["max_sidecar_compressed_bytes"]:
        raise SchemaError(f"{name} compressed bytes exceed cap")
    if base64.b85encode(compressed) != compact:
        raise SchemaError(f"{name} Base85 payload is not canonical")
    return compressed


def _bounded_zlib_decompress(compressed: bytes, name: str) -> bytes:
    maximum = RESOURCE_LIMITS["max_sidecar_raw_bytes"]
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, maximum + 1)
        if len(raw) > maximum or decoder.unconsumed_tail:
            raise SchemaError(f"{name} decompressed bytes exceed cap")
        raw += decoder.flush(maximum + 1 - len(raw))
    except zlib.error as exc:
        raise SchemaError(f"{name} zlib decoding failed") from exc
    if len(raw) > maximum:
        raise SchemaError(f"{name} decompressed bytes exceed cap")
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise SchemaError(f"{name} must contain exactly one complete zlib stream")
    return raw


def _validate_state_shape(
    state: Any,
    *,
    observable_id: str,
    step_index: int,
    parent_source_sha256: str,
    parent_expected_witness_sha256: str,
    backprop_gate_records_sha256: str,
) -> Mapping[str, Any]:
    item = _exact_keys(
        state,
        (
            "schema_version",
            "state_fingerprint",
            "profile_id",
            "observable_id",
            "step_index",
            "heisenberg_direction",
            "producer_fingerprint",
            "root_checker_source_sha256",
            "root_expected_witness_sha256",
            "backprop_gate_records_sha256",
            "tick_denominator",
            "term_count",
            "expansion_sha256",
            "cumulative_dropped_l1_ticks",
            "retained_Neel_expectation_lower_ticks",
            "retained_Neel_expectation_upper_ticks",
        ),
        "checkpoint.state",
    )
    expected_producer = (
        "hubbard_l8_fixed_tick_interval_step_v1"
        if step_index == 1
        else CHECKER_FINGERPRINT
    )
    fixed = {
        "schema_version": 1,
        "state_fingerprint": STATE_FINGERPRINT,
        "profile_id": WORKLOAD_IDENTITY["root_profile_id"],
        "observable_id": observable_id,
        "step_index": step_index,
        "heisenberg_direction": HEISENBERG_DIRECTION,
        "producer_fingerprint": expected_producer,
        "root_checker_source_sha256": parent_source_sha256,
        "root_expected_witness_sha256": parent_expected_witness_sha256,
        "backprop_gate_records_sha256": backprop_gate_records_sha256,
        "tick_denominator": str(TICK_DENOMINATOR),
        "term_count": RETAINED_TERM_CAP,
    }
    for key, expected in fixed.items():
        if type(item[key]) is not type(expected) or item[key] != expected:
            raise SchemaError(f"checkpoint.state.{key} does not match fixed custody")
    _require_resolved_sha256(item["expansion_sha256"], "checkpoint.state.expansion_sha256")
    lower = _canonical_integer(
        item["retained_Neel_expectation_lower_ticks"],
        "checkpoint.state.retained_Neel_expectation_lower_ticks",
    )
    upper = _canonical_integer(
        item["retained_Neel_expectation_upper_ticks"],
        "checkpoint.state.retained_Neel_expectation_upper_ticks",
    )
    if lower > upper:
        raise SchemaError("checkpoint retained Neel interval is reversed")
    _canonical_integer(
        item["cumulative_dropped_l1_ticks"],
        "checkpoint.state.cumulative_dropped_l1_ticks",
        nonnegative=True,
    )
    return item


def _load_checkpoint(
    spec: Mapping[str, Any],
    *,
    parent: Any,
    parent_source_sha256: str,
    parent_expected_witness_sha256: str,
    backprop_gate_records_sha256: str,
) -> Dict[str, Any]:
    expected_keys = (
        "relative_path",
        "observable_id",
        "step_index",
        "encoded_sha256",
        "compressed_sha256",
        "raw_sha256",
    )
    item = _exact_keys(spec, expected_keys, "checkpoint spec")
    observable_id = item["observable_id"]
    step_index = item["step_index"]
    if observable_id not in OBSERVABLES or type(observable_id) is not str:
        raise SchemaError("checkpoint spec observable_id is invalid")
    if step_index not in BOUNDARY_STEPS or type(step_index) is not int:
        raise SchemaError("checkpoint spec step_index is invalid")
    expected_path = (
        f"hubbard_l8_interval_checkpoints/"
        f"{observable_id}_boundary_{step_index:03d}.b85"
    )
    if item["relative_path"] != expected_path:
        raise SchemaError("checkpoint spec path is not canonical")
    encoded_sha256 = _require_resolved_sha256(
        item["encoded_sha256"], "checkpoint spec encoded_sha256"
    )
    compressed_sha256 = _require_resolved_sha256(
        item["compressed_sha256"], "checkpoint spec compressed_sha256"
    )
    raw_sha256 = _require_resolved_sha256(item["raw_sha256"], "checkpoint spec raw_sha256")
    path = HERE / expected_path
    with path.open("rb") as handle:
        encoded = handle.read(RESOURCE_LIMITS["max_sidecar_encoded_bytes"] + 1)
    if hashlib.sha256(encoded).hexdigest() != encoded_sha256:
        raise SchemaError(f"encoded checkpoint hash mismatch: {path.name}")
    compressed = _canonical_b85_decode(encoded, path.name)
    if hashlib.sha256(compressed).hexdigest() != compressed_sha256:
        raise SchemaError(f"compressed checkpoint hash mismatch: {path.name}")
    raw = _bounded_zlib_decompress(compressed, path.name)
    if hashlib.sha256(raw).hexdigest() != raw_sha256:
        raise SchemaError(f"raw checkpoint hash mismatch: {path.name}")
    payload = _strict_json_bytes(
        raw, path.name, RESOURCE_LIMITS["max_sidecar_raw_bytes"]
    )
    if _canonical_bytes(payload) != raw:
        raise SchemaError(f"{path.name} is not canonical compact sorted-key JSON")
    outer = _exact_keys(payload, ("format", "state", "state_sha256", "terms"), path.name)
    if outer["format"] != CHECKPOINT_FORMAT or type(outer["format"]) is not str:
        raise SchemaError(f"{path.name} checkpoint format mismatch")
    state = _validate_state_shape(
        outer["state"],
        observable_id=observable_id,
        step_index=step_index,
        parent_source_sha256=parent_source_sha256,
        parent_expected_witness_sha256=parent_expected_witness_sha256,
        backprop_gate_records_sha256=backprop_gate_records_sha256,
    )
    state_sha256 = _require_resolved_sha256(outer["state_sha256"], "checkpoint.state_sha256")
    if canonical_sha256(state) != state_sha256:
        raise VerificationError(f"{path.name} state digest mismatch")
    terms = outer["terms"]
    if type(terms) is not list or len(terms) != RETAINED_TERM_CAP:
        raise SchemaError(f"{path.name} must contain exactly 65536 terms")
    expansion: TickExpansion = {}
    previous: PauliKey | None = None
    for index, record in enumerate(terms):
        name = f"{path.name}.terms[{index}]"
        if type(record) is not list or len(record) != 4:
            raise SchemaError(f"{name} must be an exact four-string array")
        x_mask = _canonical_mask(record[0], f"{name}[0]")
        z_mask = _canonical_mask(record[1], f"{name}[1]")
        lower = _canonical_integer(record[2], f"{name}[2]")
        upper = _canonical_integer(record[3], f"{name}[3]")
        key = x_mask, z_mask
        if previous is not None and key <= previous:
            raise SchemaError(f"{name} violates strict numeric (x,z) order")
        if lower > upper:
            raise SchemaError(f"{name} interval is reversed")
        if lower == 0 and upper == 0:
            raise SchemaError(f"{name} exact zero is forbidden in sparse form")
        expansion[key] = lower, upper
        previous = key
    if parent._tick_digest(expansion) != state["expansion_sha256"]:
        raise VerificationError(f"{path.name} semantic expansion digest mismatch")
    neel = parent._neel_basis()
    expectation = parent._expectation_ticks(expansion, neel)
    stated_expectation = (
        int(state["retained_Neel_expectation_lower_ticks"]),
        int(state["retained_Neel_expectation_upper_ticks"]),
    )
    if expectation != stated_expectation:
        raise VerificationError(f"{path.name} retained Neel expectation mismatch")
    return {
        "spec": dict(spec),
        "encoded_bytes": len(encoded),
        "compressed_bytes": len(compressed),
        "raw_bytes": len(raw),
        "state": dict(state),
        "state_sha256": state_sha256,
        "expansion": expansion,
        "retained_Neel_expectation_ticks": expectation,
    }


def _parent_claim_by_observable(parent_witness: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    claims = parent_witness.get("observable_claims")
    if type(claims) is not list or len(claims) != len(OBSERVABLES):
        raise VerificationError("parent witness observable claims are malformed")
    output: Dict[str, Mapping[str, Any]] = {}
    for claim in claims:
        if type(claim) is not dict or claim.get("observable_id") not in OBSERVABLES:
            raise VerificationError("parent witness observable identity is malformed")
        if claim["observable_id"] in output:
            raise VerificationError("parent witness repeats an observable")
        output[claim["observable_id"]] = claim
    if set(output) != set(OBSERVABLES):
        raise VerificationError("parent witness omits an observable")
    return output


def _verify_boundary_one(
    checkpoint: Mapping[str, Any], parent_claim: Mapping[str, Any]
) -> None:
    state = checkpoint["state"]
    expected = {
        "term_count": parent_claim["final_retained_term_count"],
        "expansion_sha256": parent_claim["final_retained_expansion_sha256"],
        "cumulative_dropped_l1_ticks": parent_claim["cumulative_dropped_l1_ticks"],
        "retained_Neel_expectation_lower_ticks": parent_claim[
            "final_retained_Neel_expectation_interval"
        ]["lower_ticks"],
        "retained_Neel_expectation_upper_ticks": parent_claim[
            "final_retained_Neel_expectation_interval"
        ]["upper_ticks"],
    }
    for key, value in expected.items():
        if type(state[key]) is not type(value) or state[key] != value:
            raise VerificationError(f"boundary one disagrees with parent field {key}")


def _build_parent_sequence(parent: Any, parent_witness: Mapping[str, Any]) -> Tuple[Any, Any, str]:
    if (
        parent.RETAINED_TERM_CAP != RETAINED_TERM_CAP
        or parent.GATES_PER_CHECKPOINT != GATES_PER_CHECKPOINT
        or parent.EXPECTED_GATE_COUNT != EXPECTED_GATE_COUNT
        or parent.EXPECTED_CHECKPOINT_COUNT != EXPECTED_CHECKPOINT_COUNT
        or parent.RESOURCE_LIMITS["max_single_expansion_terms"]
        != RESOURCE_LIMITS["max_single_expansion_terms"]
        or parent.RESOURCE_LIMITS["max_term_gate_visits"]
        != RESOURCE_LIMITS["max_term_gate_visits_per_child"]
    ):
        raise VerificationError("local child resources disagree with pinned parent policy")
    groups = parent._independent_groups(parent._independent_bonds())
    _forward_stages, _forward_gates, backprop_stages, sequence_claim = parent._sequence_records(groups)
    del _forward_stages, _forward_gates
    expected_digest = parent_witness["sequence_identity"]["backprop_gate_records_sha256"]
    if sequence_claim["backprop_gate_records_sha256"] != expected_digest:
        raise VerificationError("parent primitive sequence disagrees with positive parent witness")
    if sum(stage["gate_count"] for stage in backprop_stages) != EXPECTED_GATE_COUNT:
        raise VerificationError("step-two parent sequence gate count mismatch")
    if EXPECTED_GATE_COUNT > RESOURCE_LIMITS["max_gate_count_per_child"]:
        raise SchemaError("step-two gate count exceeds local child cap")
    unique_thetas = sorted(
        {theta for stage in backprop_stages for _, theta in stage["gates"]}
    )
    trig_cache: Dict[Fraction, Tuple[TickInterval, TickInterval]] = {}
    for theta in unique_thetas:
        sine, cosine, _record = parent._taylor_trig_record(theta)
        trig_cache[theta] = sine, cosine
    return backprop_stages, trig_cache, expected_digest


def _propagate_child(
    parent: Any,
    observable_id: str,
    input_expansion: TickExpansion,
    backprop_stages: Sequence[Mapping[str, Any]],
    trig_cache: Mapping[Fraction, Tuple[TickInterval, TickInterval]],
) -> Dict[str, Any]:
    expansion = dict(input_expansion)
    counter = parent.PropagationCounter()
    counter.observe(expansion)
    for interval in expansion.values():
        counter.observe_interval(interval)
    child_drop_ticks = 0
    checkpoint_records: List[Dict[str, Any]] = []
    stage_records: List[Dict[str, Any]] = []
    checkpoint_index = 0
    for stage in backprop_stages:
        gates = stage["gates"]
        if len(gates) % GATES_PER_CHECKPOINT:
            raise VerificationError("parent stage is not divisible into fixed checkpoints")
        stage_start_terms = len(expansion)
        stage_peak = len(expansion)
        stage_drop_ticks = 0
        stage_dropped_count = 0
        stage_rounding_start = counter.multiplication_rounding_l1_scaled_ticks_squared
        for batch_start in range(0, len(gates), GATES_PER_CHECKPOINT):
            batch = gates[batch_start : batch_start + GATES_PER_CHECKPOINT]
            checkpoint_rounding_start = counter.multiplication_rounding_l1_scaled_ticks_squared
            counter.begin_window(expansion)
            for generator, theta in batch:
                sine, cosine = trig_cache[theta]
                expansion = parent._propagate_gate(
                    expansion, generator, sine, cosine, counter
                )
            peak_before_truncation = counter.window_peak_live_terms
            post_propagation_count = len(expansion)
            expansion, dropped = parent._truncate(expansion)
            dropped_ticks = dropped["dropped_l1_ticks"]
            child_drop_ticks += dropped_ticks
            stage_drop_ticks += dropped_ticks
            stage_dropped_count += dropped["dropped_term_count"]
            stage_peak = max(stage_peak, peak_before_truncation)
            checkpoint_records.append(
                {
                    "checkpoint_index": checkpoint_index,
                    "child_step_index": 2,
                    "backprop_stage_index": stage["backprop_stage_index"],
                    "forward_stage_index": stage["forward_stage_index"],
                    "group": stage["group"],
                    "batch_in_stage": batch_start // GATES_PER_CHECKPOINT,
                    "gate_count": len(batch),
                    "post_propagation_term_count": post_propagation_count,
                    "peak_single_expansion_term_count": peak_before_truncation,
                    "retained_term_count": len(expansion),
                    "dropped_term_count": dropped["dropped_term_count"],
                    "dropped_l1_ticks": str(dropped_ticks),
                    "child_cumulative_dropped_l1_ticks": str(child_drop_ticks),
                    "dropped_terms_sha256": dropped["dropped_terms_sha256"],
                    "minimum_retained_abs_upper_ticks": str(
                        dropped["minimum_retained_abs_upper_ticks"]
                    ),
                    "maximum_dropped_abs_upper_ticks": str(
                        dropped["maximum_dropped_abs_upper_ticks"]
                    ),
                    "multiplication_grid_rounding_L1_upper_increment_scaled_ticks_squared": str(
                        counter.multiplication_rounding_l1_scaled_ticks_squared
                        - checkpoint_rounding_start
                    ),
                    "multiplication_grid_rounding_L1_upper_child_cumulative_scaled_ticks_squared": str(
                        counter.multiplication_rounding_l1_scaled_ticks_squared
                    ),
                    "checkpoint_status": parent.CHECKPOINT_STATUS,
                }
            )
            checkpoint_index += 1
        stage_records.append(
            {
                "child_step_index": 2,
                "backprop_stage_index": stage["backprop_stage_index"],
                "forward_stage_index": stage["forward_stage_index"],
                "group": stage["group"],
                "start_term_count": stage_start_terms,
                "end_retained_term_count": len(expansion),
                "peak_single_expansion_term_count": stage_peak,
                "dropped_term_count": stage_dropped_count,
                "dropped_l1_ticks": str(stage_drop_ticks),
                "child_cumulative_dropped_l1_ticks": str(child_drop_ticks),
                "multiplication_grid_rounding_L1_upper_increment_scaled_ticks_squared": str(
                    counter.multiplication_rounding_l1_scaled_ticks_squared
                    - stage_rounding_start
                ),
                "retained_expansion_sha256": parent._tick_digest(expansion),
            }
        )
    if checkpoint_index != EXPECTED_CHECKPOINT_COUNT:
        raise VerificationError("step two did not produce exactly 144 checkpoints")
    if checkpoint_index > RESOURCE_LIMITS["max_checkpoints_per_child"]:
        raise SchemaError("step-two checkpoint count exceeds local child cap")
    if len(expansion) != RETAINED_TERM_CAP:
        raise VerificationError("step-two retained expansion is not exactly fixed K")
    if len(expansion) > RESOURCE_LIMITS["max_terms_per_sidecar"]:
        raise SchemaError("step-two retained expansion exceeds local sidecar term cap")
    neel = parent._neel_basis()
    retained_expectation = parent._expectation_ticks(expansion, neel)
    if counter.term_gate_visits > RESOURCE_LIMITS["max_term_gate_visits_per_child"]:
        raise SchemaError("step-two term-gate visits exceed local child cap")
    if counter.peak_live_terms > RESOURCE_LIMITS["max_single_expansion_terms"]:
        raise SchemaError("step-two single-expansion peak exceeds local child cap")
    return {
        "observable_id": observable_id,
        "expansion": expansion,
        "expansion_sha256": parent._tick_digest(expansion),
        "retained_Neel_expectation_ticks": retained_expectation,
        "child_dropped_l1_ticks": child_drop_ticks,
        "checkpoint_count": len(checkpoint_records),
        "checkpoint_ledger_sha256": canonical_sha256(checkpoint_records),
        "stage_records": stage_records,
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
        },
    }


def _state_record(
    *,
    observable_id: str,
    step_index: int,
    producer_fingerprint: str,
    parent_source_sha256: str,
    parent_expected_witness_sha256: str,
    backprop_gate_records_sha256: str,
    expansion_sha256: str,
    cumulative_dropped_l1_ticks: int,
    retained_expectation: TickInterval,
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "state_fingerprint": STATE_FINGERPRINT,
        "profile_id": WORKLOAD_IDENTITY["root_profile_id"],
        "observable_id": observable_id,
        "step_index": step_index,
        "heisenberg_direction": HEISENBERG_DIRECTION,
        "producer_fingerprint": producer_fingerprint,
        "root_checker_source_sha256": parent_source_sha256,
        "root_expected_witness_sha256": parent_expected_witness_sha256,
        "backprop_gate_records_sha256": backprop_gate_records_sha256,
        "tick_denominator": str(TICK_DENOMINATOR),
        "term_count": RETAINED_TERM_CAP,
        "expansion_sha256": expansion_sha256,
        "cumulative_dropped_l1_ticks": str(cumulative_dropped_l1_ticks),
        "retained_Neel_expectation_lower_ticks": str(retained_expectation[0]),
        "retained_Neel_expectation_upper_ticks": str(retained_expectation[1]),
    }


def _transition_record(
    *,
    observable_id: str,
    input_checkpoint: Mapping[str, Any],
    output_checkpoint: Mapping[str, Any],
    child: Mapping[str, Any],
    parent_claim: Mapping[str, Any],
    input_cumulative_drop: int,
    output_cumulative_drop: int,
    backprop_gate_records_sha256: str,
) -> Dict[str, Any]:
    previous_anchor = canonical_sha256(
        {
            "anchor_fingerprint": "positive_one_step_parent_observable_claim_v1",
            "root_expected_witness_sha256": input_checkpoint["state"][
                "root_expected_witness_sha256"
            ],
            "observable_claim_sha256": canonical_sha256(parent_claim),
        }
    )
    transition_policy_sha256 = canonical_sha256(
        {
            "policy_fingerprint": "l8_two_step_transition_policy_v1",
            "workload_identity": WORKLOAD_IDENTITY,
            "propagation_policy": PROPAGATION_POLICY,
            "resource_limits": RESOURCE_LIMITS,
        }
    )
    return {
        "schema_version": 1,
        "transition_fingerprint": TRANSITION_FINGERPRINT,
        "observable_id": observable_id,
        "child_step_index": 2,
        "input_step_index": 1,
        "output_step_index": 2,
        "input_state_sha256": input_checkpoint["state_sha256"],
        "output_state_sha256": output_checkpoint["state_sha256"],
        "previous_transition_anchor_sha256": previous_anchor,
        "transition_policy_sha256": transition_policy_sha256,
        "input_encoded_file_sha256": input_checkpoint["spec"]["encoded_sha256"],
        "output_encoded_file_sha256": output_checkpoint["spec"]["encoded_sha256"],
        "input_expansion_sha256": input_checkpoint["state"]["expansion_sha256"],
        "output_expansion_sha256": output_checkpoint["state"]["expansion_sha256"],
        "backprop_gate_records_sha256": backprop_gate_records_sha256,
        "gate_count": EXPECTED_GATE_COUNT,
        "checkpoint_count": child["checkpoint_count"],
        "checkpoint_ledger_sha256": child["checkpoint_ledger_sha256"],
        "input_cumulative_dropped_l1_ticks": str(input_cumulative_drop),
        "child_dropped_l1_ticks": str(child["child_dropped_l1_ticks"]),
        "output_cumulative_dropped_l1_ticks": str(output_cumulative_drop),
        "cross_step_fusion_used": False,
    }


_WITNESS_CACHE_BYTES: bytes | None = None


def recompute_witness() -> Dict[str, Any]:
    global _WITNESS_CACHE_BYTES
    if _WITNESS_CACHE_BYTES is not None:
        _read_pinned_sources()
        _preflight_checkpoint_files()
        return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))
    if len(CHECKPOINT_SPECS) != RESOURCE_LIMITS["max_checkpoint_sidecars"]:
        raise SchemaError("checkpoint sidecar count disagrees with fixed local cap")
    for spec in CHECKPOINT_SPECS:
        for field in ("encoded_sha256", "compressed_sha256", "raw_sha256"):
            _require_resolved_sha256(spec[field], f"checkpoint spec {field}")
    for observable_id, expected in EXPECTED_STEP2_EXACT.items():
        _require_resolved_sha256(
            expected["expansion_sha256"], f"{observable_id} expected expansion_sha256"
        )
        _require_resolved_sha256(
            expected["state_sha256"], f"{observable_id} expected state_sha256"
        )
        _require_resolved_sha256(
            expected["transition_sha256"], f"{observable_id} expected transition_sha256"
        )
        _canonical_integer(
            expected["child_dropped_l1_ticks"],
            f"{observable_id} expected child_dropped_l1_ticks",
            nonnegative=True,
        )
    _preflight_checkpoint_files()
    sources = _read_pinned_sources()
    parent, parent_contract, parent_witness = _load_positive_parent(sources)
    parent_source_sha256 = SOURCE_PINS[0]["sha256"]
    parent_expected_witness_sha256 = parent_contract["expected_witness_sha256"]
    backprop_stages, trig_cache, backprop_digest = _build_parent_sequence(
        parent, parent_witness
    )
    parent_claims = _parent_claim_by_observable(parent_witness)
    checkpoints: Dict[Tuple[str, int], Dict[str, Any]] = {}
    total_encoded = 0
    for spec in CHECKPOINT_SPECS:
        key = spec["observable_id"], spec["step_index"]
        if key in checkpoints:
            raise SchemaError("checkpoint specs repeat an observable boundary")
        checkpoint = _load_checkpoint(
            spec,
            parent=parent,
            parent_source_sha256=parent_source_sha256,
            parent_expected_witness_sha256=parent_expected_witness_sha256,
            backprop_gate_records_sha256=backprop_digest,
        )
        total_encoded += checkpoint["encoded_bytes"]
        if total_encoded > RESOURCE_LIMITS["max_total_sidecar_encoded_bytes"]:
            raise SchemaError("aggregate sidecar encoded-byte cap exceeded")
        checkpoints[key] = checkpoint
    expected_keys = {(observable_id, step) for observable_id in OBSERVABLES for step in BOUNDARY_STEPS}
    if set(checkpoints) != expected_keys:
        raise SchemaError("checkpoint specs do not provide all four fixed boundaries")
    child_witnesses: List[Dict[str, Any]] = []
    for observable_id in OBSERVABLES:
        boundary_one = checkpoints[(observable_id, 1)]
        boundary_two = checkpoints[(observable_id, 2)]
        parent_claim = parent_claims[observable_id]
        _verify_boundary_one(boundary_one, parent_claim)
        child = _propagate_child(
            parent,
            observable_id,
            boundary_one["expansion"],
            backprop_stages,
            trig_cache,
        )
        if child["expansion"] != boundary_two["expansion"]:
            raise VerificationError(f"{observable_id} boundary two is not the exact child output")
        inherited_drop = int(parent_claim["cumulative_dropped_l1_ticks"])
        cumulative_drop = inherited_drop + child["child_dropped_l1_ticks"]
        expected_state_two = _state_record(
            observable_id=observable_id,
            step_index=2,
            producer_fingerprint=CHECKER_FINGERPRINT,
            parent_source_sha256=parent_source_sha256,
            parent_expected_witness_sha256=parent_expected_witness_sha256,
            backprop_gate_records_sha256=backprop_digest,
            expansion_sha256=child["expansion_sha256"],
            cumulative_dropped_l1_ticks=cumulative_drop,
            retained_expectation=child["retained_Neel_expectation_ticks"],
        )
        if not _strict_equal(boundary_two["state"], expected_state_two):
            raise VerificationError(f"{observable_id} boundary two state metadata mismatch")
        if boundary_two["state_sha256"] != canonical_sha256(expected_state_two):
            raise VerificationError(f"{observable_id} boundary two state digest mismatch")
        retained = child["retained_Neel_expectation_ticks"]
        declared = retained[0] - cumulative_drop, retained[1] + cumulative_drop
        transition = _transition_record(
            observable_id=observable_id,
            input_checkpoint=boundary_one,
            output_checkpoint=boundary_two,
            child=child,
            parent_claim=parent_claim,
            input_cumulative_drop=inherited_drop,
            output_cumulative_drop=cumulative_drop,
            backprop_gate_records_sha256=backprop_digest,
        )
        transition_sha256 = canonical_sha256(transition)
        expected_exact = EXPECTED_STEP2_EXACT[observable_id]
        observed_exact = {
            "expansion_sha256": child["expansion_sha256"],
            "state_sha256": boundary_two["state_sha256"],
            "child_dropped_l1_ticks": str(child["child_dropped_l1_ticks"]),
            "transition_sha256": transition_sha256,
        }
        if not _strict_equal(observed_exact, expected_exact):
            raise VerificationError(f"{observable_id} exact step-two pins disagree")
        child_witnesses.append(
            {
                "observable_id": observable_id,
                "child_step_index": 2,
                "input_state_sha256": boundary_one["state_sha256"],
                "output_state_sha256": boundary_two["state_sha256"],
                "input_expansion_sha256": boundary_one["state"]["expansion_sha256"],
                "output_expansion_sha256": child["expansion_sha256"],
                "input_cumulative_dropped_l1_ticks": str(inherited_drop),
                "child_dropped_l1_ticks": str(child["child_dropped_l1_ticks"]),
                "output_cumulative_dropped_l1_ticks": str(cumulative_drop),
                "drop_recurrence_E2_equals_E1_plus_d2": True,
                "checkpoint_count": child["checkpoint_count"],
                "checkpoint_ledger_sha256": child["checkpoint_ledger_sha256"],
                "stage_records": child["stage_records"],
                "final_retained_Neel_expectation_interval": {
                    "lower_ticks": str(retained[0]),
                    "upper_ticks": str(retained[1]),
                },
                "declared_two_step_untruncated_mapped_circuit_Neel_expectation_interval": {
                    "lower_ticks": str(declared[0]),
                    "upper_ticks": str(declared[1]),
                },
                "transition_record": transition,
                "transition_sha256": transition_sha256,
                "resource_usage": child["resource_usage"],
                "boundary_sidecar_custody": {
                    "input_relative_path": boundary_one["spec"]["relative_path"],
                    "output_relative_path": boundary_two["spec"]["relative_path"],
                    "input_raw_sha256": boundary_one["spec"]["raw_sha256"],
                    "output_raw_sha256": boundary_two["spec"]["raw_sha256"],
                },
            }
        )
    witness = {
        "profile_id": WORKLOAD_IDENTITY["profile_id"],
        "root_parent": {
            "status": PARENT_POSITIVE_STATUS,
            "verified": True,
            "checker_source_sha256": parent_source_sha256,
            "contract_sha256": SOURCE_PINS[1]["sha256"],
            "certificate_sha256": SOURCE_PINS[2]["sha256"],
            "expected_witness_sha256": parent_expected_witness_sha256,
            "backprop_gate_records_sha256": backprop_digest,
        },
        "checkpoint_codec": {
            "format": CHECKPOINT_FORMAT,
            "state_fingerprint": STATE_FINGERPRINT,
            "canonical_b85_line_length": CANONICAL_B85_LINE_LENGTH,
            "checkpoint_count": len(checkpoints),
            "aggregate_encoded_bytes": total_encoded,
            "all_encoded_compressed_raw_state_and_expansion_hashes_verified": True,
            "strict_numeric_x_then_z_term_order_verified": True,
        },
        "child_witnesses": child_witnesses,
        "decision": {
            "two_step_mapped_child_chain_closed": True,
            "continue_magnetization_fixed_K_step3_resource_probe": True,
            "double_occupancy_requires_cap_or_adaptive_policy_before_step3": True,
            "remaining_98_parent_child_transitions_certified": False,
            "full_R100_or_exact_Hubbard_error_certified": False,
        },
    }
    _WITNESS_CACHE_BYTES = _canonical_bytes(witness)
    return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))


def expected_contract_body() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "certificate_type": CERTIFICATE_TYPE,
        "checker_fingerprint": CHECKER_FINGERPRINT,
        "source_pins": list(SOURCE_PINS),
        "checkpoint_specs": [dict(spec) for spec in CHECKPOINT_SPECS],
        "expected_step2_exact": {
            key: dict(value) for key, value in EXPECTED_STEP2_EXACT.items()
        },
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
            "schema_version",
            "contract_fingerprint",
            "certificate_type",
            "checker_fingerprint",
            "checker_source_sha256",
            "source_pins",
            "checkpoint_specs",
            "expected_step2_exact",
            "workload_identity",
            "propagation_policy",
            "resource_limits",
            "expected_witness_sha256",
            "maximum_positive_status",
            "scope_claims",
        ),
        "contract",
    )
    if type(item["checker_source_sha256"]) is not str or not SHA256_RE.fullmatch(
        item["checker_source_sha256"]
    ):
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
    _require_resolved_sha256(item["expected_witness_sha256"], "expected_witness_sha256")
    _read_pinned_sources()
    for spec in CHECKPOINT_SPECS:
        for field in ("encoded_sha256", "compressed_sha256", "raw_sha256"):
            _require_resolved_sha256(spec[field], f"checkpoint spec {field}")
    _preflight_checkpoint_files()


def _validate_contract_impl(contract: Any) -> List[str]:
    try:
        _validate_contract_raise(contract)
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
                "schema_version",
                "certificate_type",
                "contract_fingerprint",
                "workload_identity",
                "propagation_policy",
                "witness_claim",
                "scope_claims",
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
            raise VerificationError("certificate witness disagrees with recomputation")
    except SchemaError as exc:
        base["errors"] = [str(exc)]
        base["verification_runtime_seconds"] = time.monotonic() - started
        return base
    except (
        VerificationError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        RecursionError,
    ) as exc:
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
                "Only two repeated fused L8 mapped product-formula steps are certified.",
                "No gate fusion is performed across the retained/truncated step boundary.",
                "The scalar ledger adds only dropped-L1; fixed-point and Taylor enlargement remains inside coefficient boxes.",
                "No exact-Hubbard product-formula error, remaining 98 steps, physical reference, or READY state is certified.",
            ],
            "errors": [],
        }
    )
    return base


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
        ValueError,
        OSError,
        RecursionError,
    ) as exc:
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
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    sys.exit(main())
