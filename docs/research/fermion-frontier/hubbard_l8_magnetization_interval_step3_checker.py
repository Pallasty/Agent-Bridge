#!/usr/bin/env python3
"""Fail-closed fixed-K magnetization transition from mapped step 2 to step 3.

This checker source-pins and same-byte executes the immediate positive two-step
checker, contract, and certificate.  It selects only the staggered-
magnetization depth-2 parent claim, loads that parent's canonical boundary-2
sidecar, independently applies one complete nine-stage / 1,152-gate / 144-
checkpoint fused mapped step, and compares the exact retained expansion with a
canonical boundary-3 sidecar.  No H1 half stages are fused across the retained
step boundary.  Its scalar ledger is exactly E3 = E2 + d3.

The dependency graph is deliberately one edge deep: this checker pins only the
immediate two-step checker family.  The immediate parent remains responsible
for its own one-step/root custody.  This checker certifies no double-occupancy
transition, no remaining mapped steps, no product-formula-to-exact-Hubbard
error, no physical reference, and no READY state.  The CLI always exits 1.

The boundary-3 transport, expansion, state, dropped-L1 and adjacent-transition
identities are all frozen.  Every public verification path checks these pins
before executing the expensive parent and child replays.
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
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
SELF_NAME = Path(__file__).name

CERTIFICATE_TYPE = "l8_magnetization_step3_fixed_k_interval_child_subcertificate_v1"
CONTRACT_FINGERPRINT = "hubbard_l8_magnetization_interval_step3_contract_v1"
CHECKER_FINGERPRINT = "hubbard_l8_magnetization_interval_step3_child_v1"
MAXIMUM_POSITIVE_STATUS = (
    "VERIFIED_L8_MAGNETIZATION_STEP3_MAPPED_INTERVAL_CHILD_SUBCERTIFICATE"
)
IMMEDIATE_PARENT_POSITIVE_STATUS = (
    "VERIFIED_L8_TWO_STEP_MAPPED_INTERVAL_CHILD_CHAIN_SUBCERTIFICATE"
)
IMMEDIATE_PARENT_CHECKER_FINGERPRINT = "hubbard_l8_two_step_interval_child_v1"
IMMEDIATE_PARENT_EXPECTED_WITNESS_SHA256 = (
    "b63bcf3b6b8b920630e639215281cd04c065e5226aa430dd417a5515df8ad623"
)
ROOT_EXPECTED_WITNESS_SHA256 = (
    "2e9a414c7e6df53a46363518a9e46d764306837be6772d4bb228456a61b5e0f2"
)
EXPECTED_PREVIOUS_TRANSITION_SHA256 = (
    "019b813fcd2ff64b419d091785b78a9cb57dc3ccd4c35140059fc5e0279fed27"
)

CHECKPOINT_FORMAT = "l8_fixed_tick_expansion_checkpoint_v1"
STATE_FINGERPRINT = "hubbard_l8_mapped_observable_interval_child_state_v2"
TRANSITION_FINGERPRINT = "l8_fixed_tick_interval_adjacent_child_transition_v2"
HEISENBERG_DIRECTION = "repeat_fixed_fused_step_backpropagation_no_cross_step_fusion"
OBSERVABLE_ID = "staggered_magnetization"
INPUT_STEP_INDEX = 2
OUTPUT_STEP_INDEX = 3
N_QUBITS = 128
TICK_DENOMINATOR = 1 << 64
TAYLOR_ORDER = 5
RETAINED_TERM_CAP = 65_536
EXPECTED_STAGE_COUNT = 9
EXPECTED_GATE_COUNT = 1_152
EXPECTED_CHECKPOINT_COUNT = 144
GATES_PER_CHECKPOINT = 8
CANONICAL_B85_LINE_LENGTH = 100

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INTEGER_RE = re.compile(r"^(?:0|-?[1-9][0-9]*)$")
PLACEHOLDER_RE = re.compile(r"^__PLACEHOLDER_[A-Z0-9_]+__$")

RESOURCE_LIMITS = {
    "max_json_bytes": 1_048_576,
    "max_checker_source_bytes": 196_608,
    "max_pinned_source_bytes": 1_048_576,
    "max_dependency_files": 3,
    "max_checkpoint_sidecars": 2,
    "max_sidecar_encoded_bytes": 4_194_304,
    "max_sidecar_compressed_bytes": 4_194_304,
    "max_sidecar_raw_bytes": 16_777_216,
    "max_total_sidecar_encoded_bytes": 8_388_608,
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
        "relative_path": "hubbard_l8_observable_interval_two_step_checker.py",
        "role": "immediate_positive_two_step_parent_checker",
        "sha256": "a562055fa361b3b31d24cd9613c38d09ddc176791454a8612eb12ac2ad06c232",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_contract.json",
        "role": "immediate_positive_two_step_parent_contract",
        "sha256": "09d4233cad211bb31e5e779156af2574ed966921168e9b4baf490691301b4e45",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_template.json",
        "role": "immediate_positive_two_step_parent_certificate",
        "sha256": "4ac0a0b3cbabb595a5872ae39bd182ab561fafaa51733625575d6bfc3f627ba1",
    },
)

OUTPUT_CHECKPOINT_SPEC = {
    "relative_path": (
        "hubbard_l8_interval_checkpoints/"
        "staggered_magnetization_boundary_003.b85"
    ),
    "observable_id": OBSERVABLE_ID,
    "step_index": OUTPUT_STEP_INDEX,
    "encoded_sha256": "91aecef5a3b79279e394c8995072d19565f4898e0ba29ddd7685ea9e535d9c84",
    "compressed_sha256": "b235497f28f79aaed6e2266a5d45e11539893bcbf0aebc495ca30cab9558867f",
    "raw_sha256": "61fc4fb5d65c18ae64134ff829f6de184786a8f86671760b78433e54a542137a",
}

EXPECTED_STEP3_EXACT = {
    "expansion_sha256": "3ce27ae55f05b8c2a71577a99f47af8b50563aaf7221f9f4e48b551d902e86ff",
    "state_sha256": "093e4ccd1df0170afa357a93fd64656ff98e978192f9dc1dc35ef6a4d1a26add",
    "child_dropped_l1_ticks": "1479500890039114",
    "transition_sha256": "a02d636d4e511f2399ddaa069ba443225bb8259dd8a9e3e5203ca2e21aa7a73d",
}

TRANSITION_POLICY = {
    "backprop_gate_records_sha256": (
        "8504eae718b7a670fa71b79c789691e70a59365f0876f8acfdd4ea8dceee2df5"
    ),
    "coefficient_box_widening_is_not_added_to_scalar_drop_ledger": True,
    "cross_step_H1_half_stage_fusion": False,
    "drop_ledger_recurrence": "E3_ticks=E2_ticks+d3_ticks",
    "final_expectation_rule": (
        "boundary3_retained_Neel_interval_expanded_by_plus_minus_E3_ticks"
    ),
    "fixed_checkpoint_count": EXPECTED_CHECKPOINT_COUNT,
    "fixed_fused_stage_count": EXPECTED_STAGE_COUNT,
    "fixed_gate_count": EXPECTED_GATE_COUNT,
    "gates_per_checkpoint": GATES_PER_CHECKPOINT,
    "immediate_parent_positive_status": IMMEDIATE_PARENT_POSITIVE_STATUS,
    "input_step_index": INPUT_STEP_INDEX,
    "merge_policy": "merge_equal_Pauli_keys_before_truncation",
    "observable_id": OBSERVABLE_ID,
    "output_step_index": OUTPUT_STEP_INDEX,
    "policy_fingerprint": (
        "l8_magnetization_fixed_k_adjacent_step3_transition_policy_v1"
    ),
    "ranking_policy": (
        "descending_max_abs_interval_endpoint_then_numeric_x_then_numeric_z"
    ),
    "retained_term_cap": RETAINED_TERM_CAP,
    "root_arithmetic_checker_sha256": (
        "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a"
    ),
    "taylor_order": TAYLOR_ORDER,
    "tick_denominator": TICK_DENOMINATOR,
}
TRANSITION_POLICY_SHA256 = (
    "f1c3eae027ba376be98040b4f1632c18dd87f51f08d132be0fb4451a90f33bbb"
)

WORKLOAD_IDENTITY = {
    "profile_id": "L8_OBC_U8_T1_R100_NEEL_MAGNETIZATION_FIXED_K_STEP3_CHILD",
    "immediate_parent_profile_id": (
        "L8_OBC_U8_T1_R100_NEEL_FUSED_STRANG_TWO_STEP_CHILD_CHAIN"
    ),
    "root_profile_id": "L8_OBC_U8_T1_R100_NEEL_FUSED_STRANG_ONE_STEP",
    "linear_size": 8,
    "n_sites": 64,
    "n_qubits": N_QUBITS,
    "boundary_condition": "square_open_boundary_no_wrap",
    "mode_order": "site-major_spin-minor_q=2*(r*L+c)+spin_up0_down1",
    "observable_id": OBSERVABLE_ID,
    "input_step_index": INPUT_STEP_INDEX,
    "output_step_index": OUTPUT_STEP_INDEX,
    "certified_repeated_step_count": OUTPUT_STEP_INDEX,
    "total_time": "1/1",
    "trotter_steps": 100,
    "step_duration": "1/100",
    "initial_state": "checkerboard_Neel_A_up_B_down_Nup32_Ndown32",
    "heisenberg_direction": HEISENBERG_DIRECTION,
}

PROPAGATION_POLICY = {
    "immediate_parent_positive_status": IMMEDIATE_PARENT_POSITIVE_STATUS,
    "immediate_parent_same_byte_checker_contract_certificate_required": True,
    "observable_id": OBSERVABLE_ID,
    "input_step_index": INPUT_STEP_INDEX,
    "output_step_index": OUTPUT_STEP_INDEX,
    "fixed_fused_stage_count": EXPECTED_STAGE_COUNT,
    "fixed_gate_count": EXPECTED_GATE_COUNT,
    "fixed_checkpoint_count": EXPECTED_CHECKPOINT_COUNT,
    "gates_per_checkpoint": GATES_PER_CHECKPOINT,
    "tick_denominator": TICK_DENOMINATOR,
    "taylor_order": TAYLOR_ORDER,
    "retained_term_cap": RETAINED_TERM_CAP,
    "cross_step_H1_half_stage_fusion": False,
    "drop_ledger_recurrence": "E3_ticks=E2_ticks+d3_ticks",
    "transition_policy_sha256": TRANSITION_POLICY_SHA256,
    "state_fingerprint": STATE_FINGERPRINT,
    "transition_fingerprint": TRANSITION_FINGERPRINT,
    "sidecar_format": CHECKPOINT_FORMAT,
}

SCOPE_CLAIMS = {
    "checker_execution_from_contract_pinned_source_bytes_verified": True,
    "immediate_two_step_parent_same_byte_positive_verified": True,
    "parent_dependency_DAG_has_no_step3_self_cycle_verified": True,
    "staggered_magnetization_depth_two_parent_selected_exclusively": True,
    "canonical_boundary_two_and_three_sidecar_custody_verified": True,
    "boundary_two_equals_immediate_parent_output_verified": True,
    "fixed_K_65536_step_three_1152_gate_144_checkpoint_transition_verified": True,
    "no_cross_step_fusion_verified": True,
    "boundary_three_exact_expansion_equality_verified": True,
    "drop_recurrence_E3_equals_E2_plus_d3_verified": True,
    "step_three_mapped_circuit_expectation_interval_verified": True,
    "double_occupancy_step_three": "NOT_ASSESSED",
    "remaining_97_mapped_steps": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
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
    """Malformed input, unresolved pin, custody drift, or resource failure."""


class VerificationError(ValueError):
    """A well-shaped exact claim disagrees with deterministic recomputation."""


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


def _require_resolved_sha256(value: Any, name: str) -> str:
    if type(value) is not str:
        raise SchemaError(f"{name} must be a string")
    if PLACEHOLDER_RE.fullmatch(value):
        raise SchemaError(f"{name} is an unresolved placeholder")
    if not SHA256_RE.fullmatch(value):
        raise SchemaError(f"{name} must be lowercase sha256")
    return value


def _canonical_integer(value: Any, name: str, *, nonnegative: bool = False) -> int:
    if type(value) is not str:
        raise SchemaError(f"{name} must be a canonical decimal integer string")
    if PLACEHOLDER_RE.fullmatch(value):
        raise SchemaError(f"{name} is an unresolved placeholder")
    if not INTEGER_RE.fullmatch(value):
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


def _preflight_resolved_pins() -> None:
    if canonical_sha256(TRANSITION_POLICY) != TRANSITION_POLICY_SHA256:
        raise SchemaError("transition policy digest drift")
    if len(SOURCE_PINS) != RESOURCE_LIMITS["max_dependency_files"]:
        raise SchemaError("immediate-parent dependency count mismatch")
    relative_paths = [pin["relative_path"] for pin in SOURCE_PINS]
    if len(set(relative_paths)) != len(relative_paths):
        raise SchemaError("immediate-parent source pins repeat a path")
    if SELF_NAME in relative_paths:
        raise SchemaError("step-three checker dependency graph contains a self-cycle")
    for pin in SOURCE_PINS:
        _require_resolved_sha256(pin["sha256"], f"source pin {pin['relative_path']}")
    for field in ("encoded_sha256", "compressed_sha256", "raw_sha256"):
        _require_resolved_sha256(
            OUTPUT_CHECKPOINT_SPEC[field], f"boundary-three {field}"
        )
    _require_resolved_sha256(
        EXPECTED_STEP3_EXACT["expansion_sha256"], "expected step-three expansion_sha256"
    )
    _require_resolved_sha256(
        EXPECTED_STEP3_EXACT["state_sha256"], "expected step-three state_sha256"
    )
    _canonical_integer(
        EXPECTED_STEP3_EXACT["child_dropped_l1_ticks"],
        "expected step-three child_dropped_l1_ticks",
        nonnegative=True,
    )
    _require_resolved_sha256(
        EXPECTED_STEP3_EXACT["transition_sha256"],
        "expected step-three transition_sha256",
    )


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
    _preflight_resolved_pins()
    payload = _read_checker_source_bytes()
    if not arguments or type(arguments[0]) is not dict:
        raise SchemaError("outer self-exec preflight requires an exact contract object")
    checker_pin = arguments[0].get("checker_source_sha256")
    if type(checker_pin) is not str or not SHA256_RE.fullmatch(checker_pin):
        raise SchemaError("outer self-exec preflight requires checker_source_sha256")
    if hashlib.sha256(payload).hexdigest() != checker_pin:
        raise SchemaError("checker source pin mismatch before compile/exec")
    path = Path(__file__).resolve()
    module = types.ModuleType("verified_hubbard_l8_magnetization_step3")
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
            raise SchemaError(f"pinned dependency exceeds cap: {path.name}")
        if hashlib.sha256(payload).hexdigest() != pin["sha256"]:
            raise SchemaError(f"immediate-parent source pin drift: {path.name}")
        output[pin["relative_path"]] = payload
    return output


def _compile_immediate_parent(sources: Mapping[str, bytes]) -> Any:
    checker_name = "hubbard_l8_observable_interval_two_step_checker.py"
    source = sources[checker_name]
    module = types.ModuleType("pinned_hubbard_l8_two_step_immediate_parent")
    module.__file__ = str(HERE / checker_name)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = source
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    if module.CHECKER_FINGERPRINT != IMMEDIATE_PARENT_CHECKER_FINGERPRINT:
        raise VerificationError("immediate parent checker fingerprint mismatch")
    if module.CHECKER_FINGERPRINT == CHECKER_FINGERPRINT:
        raise VerificationError("immediate parent aliases the child checker")
    if any(pin["relative_path"] == SELF_NAME for pin in module.SOURCE_PINS):
        raise VerificationError("immediate parent dependency DAG points back to step three")
    if module.WORKLOAD_IDENTITY.get("certified_repeated_step_count") != INPUT_STEP_INDEX:
        raise VerificationError("immediate parent is not exactly depth two")
    return module


def _preflight_checkpoint_files(immediate: Any | None = None) -> Dict[str, int]:
    """Rehash parent custody and both adjacent encoded sidecars.

    The immediate parent checks all four sidecars in its own certificate.  This
    child additionally accounts the exact boundary-2 input and boundary-3
    output bytes against its narrower two-sidecar transport cap.  It is called
    on cold and warm witness paths.
    """

    if immediate is None:
        _preflight_resolved_pins()
        immediate = _compile_immediate_parent(_read_pinned_sources())
    immediate._preflight_checkpoint_files()
    input_specs = [
        spec
        for spec in immediate.CHECKPOINT_SPECS
        if spec["observable_id"] == OBSERVABLE_ID
        and spec["step_index"] == INPUT_STEP_INDEX
    ]
    if len(input_specs) != 1:
        raise VerificationError("immediate parent boundary-two spec is not unique")
    files = (
        (input_specs[0], "input"),
        (OUTPUT_CHECKPOINT_SPEC, "output"),
    )
    if len(files) != RESOURCE_LIMITS["max_checkpoint_sidecars"]:
        raise SchemaError("adjacent sidecar count disagrees with local cap")
    usage: Dict[str, int] = {}
    total = 0
    for spec, role in files:
        path = HERE / spec["relative_path"]
        with path.open("rb") as handle:
            encoded = handle.read(RESOURCE_LIMITS["max_sidecar_encoded_bytes"] + 1)
        if len(encoded) > RESOURCE_LIMITS["max_sidecar_encoded_bytes"]:
            raise SchemaError(f"{role} encoded sidecar exceeds local cap")
        if hashlib.sha256(encoded).hexdigest() != spec["encoded_sha256"]:
            raise SchemaError(f"{role} encoded sidecar hash mismatch")
        usage[f"{role}_encoded_bytes"] = len(encoded)
        total += len(encoded)
    if total > RESOURCE_LIMITS["max_total_sidecar_encoded_bytes"]:
        raise SchemaError("adjacent encoded sidecars exceed aggregate byte cap")
    usage["aggregate_encoded_bytes"] = total
    return usage


def _load_immediate_parent(
    sources: Mapping[str, bytes], immediate: Any | None = None,
) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    checker_name = "hubbard_l8_observable_interval_two_step_checker.py"
    contract_name = "hubbard_l8_observable_interval_two_step_contract.json"
    certificate_name = "hubbard_l8_observable_interval_two_step_template.json"
    module = _compile_immediate_parent(sources) if immediate is None else immediate
    contract = _strict_json_bytes(sources[contract_name], "immediate parent contract")
    certificate = _strict_json_bytes(
        sources[certificate_name], "immediate parent certificate"
    )
    result = module.verify_certificate(contract, certificate)
    if (
        result.get("status") != IMMEDIATE_PARENT_POSITIVE_STATUS
        or result.get("verified") is not True
    ):
        raise VerificationError("same-byte immediate two-step parent is not positive")
    witness = result.get("recomputed_witness")
    if type(witness) is not dict or not _strict_equal(
        certificate.get("witness_claim"), witness
    ):
        raise VerificationError("immediate parent did not return its exact witness")
    if canonical_sha256(witness) != contract.get("expected_witness_sha256"):
        raise VerificationError("immediate parent expected-witness pin mismatch")
    if contract.get("expected_witness_sha256") != IMMEDIATE_PARENT_EXPECTED_WITNESS_SHA256:
        raise VerificationError("immediate parent expected-witness custody drift")
    return module, contract, witness


def _select_parent_magnetization_claim(parent_witness: Mapping[str, Any]) -> Mapping[str, Any]:
    claims = parent_witness.get("child_witnesses")
    if type(claims) is not list:
        raise VerificationError("immediate parent child-witness list is malformed")
    selected = [claim for claim in claims if claim.get("observable_id") == OBSERVABLE_ID]
    if len(selected) != 1 or type(selected[0]) is not dict:
        raise VerificationError("immediate parent magnetization claim is not unique")
    claim = selected[0]
    if claim.get("child_step_index") != INPUT_STEP_INDEX:
        raise VerificationError("immediate parent magnetization claim has wrong depth")
    transition = claim.get("transition_record")
    if type(transition) is not dict:
        raise VerificationError("immediate parent transition record is malformed")
    if (
        transition.get("observable_id") != OBSERVABLE_ID
        or transition.get("output_step_index") != INPUT_STEP_INDEX
        or transition.get("cross_step_fusion_used") is not False
        or canonical_sha256(transition) != claim.get("transition_sha256")
    ):
        raise VerificationError("immediate parent transition anchor is inconsistent")
    return claim


def _load_root_arithmetic_and_sequence(
    immediate: Any,
) -> Tuple[Any, Dict[str, Any], Dict[str, Any], Any, Any, str]:
    root_sources = immediate._read_pinned_sources()
    root, root_contract, root_witness = immediate._load_positive_parent(root_sources)
    root_sha = immediate.SOURCE_PINS[0]["sha256"]
    if root_sha != TRANSITION_POLICY["root_arithmetic_checker_sha256"]:
        raise VerificationError("root arithmetic source disagrees with transition policy")
    if root_contract.get("expected_witness_sha256") != ROOT_EXPECTED_WITNESS_SHA256:
        raise VerificationError("root arithmetic expected-witness custody drift")
    if (
        root.RETAINED_TERM_CAP != RETAINED_TERM_CAP
        or root.GATES_PER_CHECKPOINT != GATES_PER_CHECKPOINT
        or root.TAYLOR_ORDER != TAYLOR_ORDER
        or root.TICK_DENOMINATOR != TICK_DENOMINATOR
        or root.RESOURCE_LIMITS["max_single_expansion_terms"]
        != RESOURCE_LIMITS["max_single_expansion_terms"]
        or root.RESOURCE_LIMITS["max_term_gate_visits"]
        != RESOURCE_LIMITS["max_term_gate_visits_per_child"]
    ):
        raise VerificationError("root arithmetic resources disagree with step-three policy")
    backprop_stages, trig_cache, backprop_digest = immediate._build_parent_sequence(
        root, root_witness
    )
    if backprop_digest != TRANSITION_POLICY["backprop_gate_records_sha256"]:
        raise VerificationError("step-three backprop sequence digest mismatch")
    expected_groups = ["H1", "H2", "HU", "H3", "H4", "H3", "HU", "H2", "H1"]
    if (
        len(backprop_stages) != EXPECTED_STAGE_COUNT
        or [stage["group"] for stage in backprop_stages] != expected_groups
        or sum(stage["gate_count"] for stage in backprop_stages)
        != EXPECTED_GATE_COUNT
        or sum(stage["gate_count"] // GATES_PER_CHECKPOINT for stage in backprop_stages)
        != EXPECTED_CHECKPOINT_COUNT
        or any(stage["gate_count"] % GATES_PER_CHECKPOINT for stage in backprop_stages)
    ):
        raise VerificationError("step-three sequence is not the complete fixed fused step")
    return root, root_contract, root_witness, backprop_stages, trig_cache, backprop_digest


def _load_boundary_two(
    immediate: Any,
    root: Any,
    root_contract: Mapping[str, Any],
    backprop_digest: str,
    parent_claim: Mapping[str, Any],
) -> Dict[str, Any]:
    specs = [
        spec
        for spec in immediate.CHECKPOINT_SPECS
        if spec["observable_id"] == OBSERVABLE_ID
        and spec["step_index"] == INPUT_STEP_INDEX
    ]
    if len(specs) != 1:
        raise VerificationError("immediate parent boundary-two spec is not unique")
    checkpoint = immediate._load_checkpoint(
        specs[0],
        parent=root,
        parent_source_sha256=immediate.SOURCE_PINS[0]["sha256"],
        parent_expected_witness_sha256=root_contract["expected_witness_sha256"],
        backprop_gate_records_sha256=backprop_digest,
    )
    expected = {
        "state_sha256": parent_claim["output_state_sha256"],
        "expansion_sha256": parent_claim["output_expansion_sha256"],
        "cumulative_dropped_l1_ticks": parent_claim[
            "output_cumulative_dropped_l1_ticks"
        ],
        "retained_Neel_expectation_lower_ticks": parent_claim[
            "final_retained_Neel_expectation_interval"
        ]["lower_ticks"],
        "retained_Neel_expectation_upper_ticks": parent_claim[
            "final_retained_Neel_expectation_interval"
        ]["upper_ticks"],
    }
    observed = {
        "state_sha256": checkpoint["state_sha256"],
        "expansion_sha256": checkpoint["state"]["expansion_sha256"],
        "cumulative_dropped_l1_ticks": checkpoint["state"][
            "cumulative_dropped_l1_ticks"
        ],
        "retained_Neel_expectation_lower_ticks": checkpoint["state"][
            "retained_Neel_expectation_lower_ticks"
        ],
        "retained_Neel_expectation_upper_ticks": checkpoint["state"][
            "retained_Neel_expectation_upper_ticks"
        ],
    }
    if not _strict_equal(observed, expected):
        raise VerificationError("boundary two disagrees with immediate parent output")
    if checkpoint["spec"]["encoded_sha256"] != parent_claim["transition_record"][
        "output_encoded_file_sha256"
    ]:
        raise VerificationError("boundary-two transport pin disagrees with parent transition")
    return checkpoint


def _propagate_step_three(
    root: Any,
    input_expansion: TickExpansion,
    backprop_stages: Sequence[Mapping[str, Any]],
    trig_cache: Mapping[Fraction, Tuple[TickInterval, TickInterval]],
) -> Dict[str, Any]:
    expansion = dict(input_expansion)
    counter = root.PropagationCounter()
    counter.observe(expansion)
    for interval in expansion.values():
        counter.observe_interval(interval)
    child_drop_ticks = 0
    checkpoint_records: List[Dict[str, Any]] = []
    stage_records: List[Dict[str, Any]] = []
    checkpoint_index = 0
    for stage in backprop_stages:
        gates = stage["gates"]
        stage_start_terms = len(expansion)
        stage_peak = len(expansion)
        stage_drop_ticks = 0
        stage_dropped_count = 0
        stage_rounding_start = counter.multiplication_rounding_l1_scaled_ticks_squared
        for batch_start in range(0, len(gates), GATES_PER_CHECKPOINT):
            batch = gates[batch_start : batch_start + GATES_PER_CHECKPOINT]
            input_digest = root._tick_digest(expansion)
            rounding_start = counter.multiplication_rounding_l1_scaled_ticks_squared
            counter.begin_window(expansion)
            for generator, theta in batch:
                sine, cosine = trig_cache[theta]
                expansion = root._propagate_gate(
                    expansion, generator, sine, cosine, counter
                )
            peak_before_truncation = counter.window_peak_live_terms
            post_propagation_count = len(expansion)
            pretruncate_digest = root._tick_digest(expansion)
            expansion, dropped = root._truncate(expansion)
            dropped_ticks = dropped["dropped_l1_ticks"]
            child_drop_ticks += dropped_ticks
            stage_drop_ticks += dropped_ticks
            stage_dropped_count += dropped["dropped_term_count"]
            stage_peak = max(stage_peak, peak_before_truncation)
            checkpoint_records.append(
                {
                    "checkpoint_index": checkpoint_index,
                    "child_step_index": OUTPUT_STEP_INDEX,
                    "backprop_stage_index": stage["backprop_stage_index"],
                    "forward_stage_index": stage["forward_stage_index"],
                    "group": stage["group"],
                    "batch_in_stage": batch_start // GATES_PER_CHECKPOINT,
                    "gate_count": len(batch),
                    "input_expansion_sha256": input_digest,
                    "post_propagation_expansion_sha256": pretruncate_digest,
                    "post_propagation_term_count": post_propagation_count,
                    "peak_single_expansion_term_count": peak_before_truncation,
                    "retained_term_count": len(expansion),
                    "retained_expansion_sha256": root._tick_digest(expansion),
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
                        - rounding_start
                    ),
                    "checkpoint_status": root.CHECKPOINT_STATUS,
                }
            )
            checkpoint_index += 1
        stage_records.append(
            {
                "child_step_index": OUTPUT_STEP_INDEX,
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
                "retained_expansion_sha256": root._tick_digest(expansion),
            }
        )
    if checkpoint_index != EXPECTED_CHECKPOINT_COUNT:
        raise VerificationError("step three did not produce exactly 144 checkpoints")
    if len(expansion) != RETAINED_TERM_CAP:
        raise VerificationError("step-three retained expansion is not fixed K=65536")
    if counter.term_gate_visits > RESOURCE_LIMITS["max_term_gate_visits_per_child"]:
        raise SchemaError("step-three term-gate visits exceed local cap")
    if counter.peak_live_terms > RESOURCE_LIMITS["max_single_expansion_terms"]:
        raise SchemaError("step-three single-expansion peak exceeds local cap")
    retained_expectation = root._expectation_ticks(expansion, root._neel_basis())
    return {
        "expansion": expansion,
        "expansion_sha256": root._tick_digest(expansion),
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
    root_source_sha256: str,
    root_expected_witness_sha256: str,
    immediate_parent_source_sha256: str,
    immediate_parent_expected_witness_sha256: str,
    previous_transition_sha256: str,
    backprop_gate_records_sha256: str,
    expansion_sha256: str,
    cumulative_dropped_l1_ticks: int,
    retained_expectation: TickInterval,
) -> Dict[str, Any]:
    return {
        "schema_version": 2,
        "state_fingerprint": STATE_FINGERPRINT,
        "profile_id": WORKLOAD_IDENTITY["root_profile_id"],
        "observable_id": OBSERVABLE_ID,
        "step_index": OUTPUT_STEP_INDEX,
        "heisenberg_direction": HEISENBERG_DIRECTION,
        "producer_fingerprint": CHECKER_FINGERPRINT,
        "root_checker_source_sha256": root_source_sha256,
        "root_expected_witness_sha256": root_expected_witness_sha256,
        "backprop_gate_records_sha256": backprop_gate_records_sha256,
        "tick_denominator": str(TICK_DENOMINATOR),
        "term_count": RETAINED_TERM_CAP,
        "expansion_sha256": expansion_sha256,
        "cumulative_dropped_l1_ticks": str(cumulative_dropped_l1_ticks),
        "retained_Neel_expectation_lower_ticks": str(retained_expectation[0]),
        "retained_Neel_expectation_upper_ticks": str(retained_expectation[1]),
        "immediate_parent_checker_source_sha256": immediate_parent_source_sha256,
        "immediate_parent_expected_witness_sha256": (
            immediate_parent_expected_witness_sha256
        ),
        "previous_transition_sha256": previous_transition_sha256,
        "transition_policy_sha256": TRANSITION_POLICY_SHA256,
    }


def _load_boundary_three(
    immediate: Any,
    root: Any,
    expected_state: Mapping[str, Any],
) -> Dict[str, Any]:
    spec = OUTPUT_CHECKPOINT_SPEC
    path = HERE / spec["relative_path"]
    with path.open("rb") as handle:
        encoded = handle.read(RESOURCE_LIMITS["max_sidecar_encoded_bytes"] + 1)
    if len(encoded) > RESOURCE_LIMITS["max_sidecar_encoded_bytes"]:
        raise SchemaError("boundary-three encoded sidecar exceeds cap")
    if hashlib.sha256(encoded).hexdigest() != spec["encoded_sha256"]:
        raise SchemaError("boundary-three encoded sidecar hash mismatch")
    compressed = immediate._canonical_b85_decode(encoded, path.name)
    if hashlib.sha256(compressed).hexdigest() != spec["compressed_sha256"]:
        raise SchemaError("boundary-three compressed sidecar hash mismatch")
    raw = immediate._bounded_zlib_decompress(compressed, path.name)
    if hashlib.sha256(raw).hexdigest() != spec["raw_sha256"]:
        raise SchemaError("boundary-three raw sidecar hash mismatch")
    payload = immediate._strict_json_bytes(
        raw, path.name, RESOURCE_LIMITS["max_sidecar_raw_bytes"]
    )
    if immediate._canonical_bytes(payload) != raw:
        raise SchemaError("boundary-three payload is not canonical JSON")
    outer = _exact_keys(payload, ("format", "state", "state_sha256", "terms"), path.name)
    if outer["format"] != CHECKPOINT_FORMAT or type(outer["format"]) is not str:
        raise SchemaError("boundary-three checkpoint format mismatch")
    if not _strict_equal(outer["state"], expected_state):
        raise VerificationError("boundary-three state metadata mismatch")
    state_sha = _require_resolved_sha256(outer["state_sha256"], "boundary-three state_sha256")
    if canonical_sha256(outer["state"]) != state_sha:
        raise VerificationError("boundary-three state digest mismatch")
    if state_sha != EXPECTED_STEP3_EXACT["state_sha256"]:
        raise VerificationError("boundary-three state does not match exact pin")
    terms = outer["terms"]
    if type(terms) is not list or len(terms) != RETAINED_TERM_CAP:
        raise SchemaError("boundary-three sidecar must contain exactly 65536 terms")
    expansion: TickExpansion = {}
    previous: PauliKey | None = None
    for index, record in enumerate(terms):
        name = f"{path.name}.terms[{index}]"
        if type(record) is not list or len(record) != 4:
            raise SchemaError(f"{name} must be an exact four-string array")
        x_mask = immediate._canonical_mask(record[0], f"{name}[0]")
        z_mask = immediate._canonical_mask(record[1], f"{name}[1]")
        lower = immediate._canonical_integer(record[2], f"{name}[2]")
        upper = immediate._canonical_integer(record[3], f"{name}[3]")
        key = x_mask, z_mask
        if previous is not None and key <= previous:
            raise SchemaError(f"{name} violates strict numeric (x,z) order")
        if lower > upper:
            raise SchemaError(f"{name} interval is reversed")
        if lower == 0 and upper == 0:
            raise SchemaError(f"{name} exact zero is forbidden in sparse form")
        expansion[key] = lower, upper
        previous = key
    expansion_sha = root._tick_digest(expansion)
    if expansion_sha != expected_state["expansion_sha256"]:
        raise VerificationError("boundary-three semantic expansion digest mismatch")
    if expansion_sha != EXPECTED_STEP3_EXACT["expansion_sha256"]:
        raise VerificationError("boundary-three expansion does not match exact pin")
    expectation = root._expectation_ticks(expansion, root._neel_basis())
    stated_expectation = (
        int(expected_state["retained_Neel_expectation_lower_ticks"]),
        int(expected_state["retained_Neel_expectation_upper_ticks"]),
    )
    if expectation != stated_expectation:
        raise VerificationError("boundary-three retained Neel expectation mismatch")
    return {
        "spec": dict(spec),
        "encoded_bytes": len(encoded),
        "compressed_bytes": len(compressed),
        "raw_bytes": len(raw),
        "state": dict(expected_state),
        "state_sha256": state_sha,
        "expansion": expansion,
        "retained_Neel_expectation_ticks": expectation,
    }


def _transition_record(
    *,
    immediate_parent_source_sha256: str,
    immediate_parent_expected_witness_sha256: str,
    previous_transition_sha256: str,
    input_checkpoint: Mapping[str, Any],
    output_checkpoint: Mapping[str, Any],
    child: Mapping[str, Any],
    inherited_drop_ticks: int,
    output_drop_ticks: int,
    backprop_gate_records_sha256: str,
) -> Dict[str, Any]:
    return {
        "schema_version": 2,
        "transition_fingerprint": TRANSITION_FINGERPRINT,
        "observable_id": OBSERVABLE_ID,
        "child_step_index": OUTPUT_STEP_INDEX,
        "input_step_index": INPUT_STEP_INDEX,
        "output_step_index": OUTPUT_STEP_INDEX,
        "immediate_parent_checker_source_sha256": immediate_parent_source_sha256,
        "immediate_parent_expected_witness_sha256": (
            immediate_parent_expected_witness_sha256
        ),
        "previous_transition_sha256": previous_transition_sha256,
        "transition_policy_sha256": TRANSITION_POLICY_SHA256,
        "input_state_sha256": input_checkpoint["state_sha256"],
        "output_state_sha256": output_checkpoint["state_sha256"],
        "input_encoded_file_sha256": input_checkpoint["spec"]["encoded_sha256"],
        "output_encoded_file_sha256": output_checkpoint["spec"]["encoded_sha256"],
        "input_expansion_sha256": input_checkpoint["state"]["expansion_sha256"],
        "output_expansion_sha256": output_checkpoint["state"]["expansion_sha256"],
        "backprop_gate_records_sha256": backprop_gate_records_sha256,
        "gate_count": EXPECTED_GATE_COUNT,
        "checkpoint_count": child["checkpoint_count"],
        "checkpoint_ledger_sha256": child["checkpoint_ledger_sha256"],
        "input_cumulative_dropped_l1_ticks": str(inherited_drop_ticks),
        "child_dropped_l1_ticks": str(child["child_dropped_l1_ticks"]),
        "output_cumulative_dropped_l1_ticks": str(output_drop_ticks),
        "cross_step_fusion_used": False,
    }


_WITNESS_CACHE_BYTES: bytes | None = None


def recompute_witness() -> Dict[str, Any]:
    global _WITNESS_CACHE_BYTES
    _preflight_resolved_pins()
    sources = _read_pinned_sources()
    preflight_immediate = _compile_immediate_parent(sources)
    sidecar_transport_usage = _preflight_checkpoint_files(preflight_immediate)
    if _WITNESS_CACHE_BYTES is not None:
        return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))
    immediate, immediate_contract, immediate_witness = _load_immediate_parent(
        sources, preflight_immediate
    )
    parent_claim = _select_parent_magnetization_claim(immediate_witness)
    previous_transition_sha256 = _require_resolved_sha256(
        parent_claim["transition_sha256"], "immediate parent transition anchor"
    )
    if previous_transition_sha256 != EXPECTED_PREVIOUS_TRANSITION_SHA256:
        raise VerificationError("immediate parent transition anchor custody drift")
    (
        root,
        root_contract,
        _root_witness,
        backprop_stages,
        trig_cache,
        backprop_digest,
    ) = _load_root_arithmetic_and_sequence(immediate)
    del _root_witness
    boundary_two = _load_boundary_two(
        immediate, root, root_contract, backprop_digest, parent_claim
    )
    child = _propagate_step_three(
        root, boundary_two["expansion"], backprop_stages, trig_cache
    )
    inherited_drop = _canonical_integer(
        boundary_two["state"]["cumulative_dropped_l1_ticks"],
        "boundary-two inherited drop",
        nonnegative=True,
    )
    output_drop = inherited_drop + child["child_dropped_l1_ticks"]
    immediate_parent_source_sha256 = SOURCE_PINS[0]["sha256"]
    immediate_parent_expected_witness_sha256 = immediate_contract[
        "expected_witness_sha256"
    ]
    expected_state = _state_record(
        root_source_sha256=TRANSITION_POLICY["root_arithmetic_checker_sha256"],
        root_expected_witness_sha256=root_contract["expected_witness_sha256"],
        immediate_parent_source_sha256=immediate_parent_source_sha256,
        immediate_parent_expected_witness_sha256=(
            immediate_parent_expected_witness_sha256
        ),
        previous_transition_sha256=previous_transition_sha256,
        backprop_gate_records_sha256=backprop_digest,
        expansion_sha256=child["expansion_sha256"],
        cumulative_dropped_l1_ticks=output_drop,
        retained_expectation=child["retained_Neel_expectation_ticks"],
    )
    boundary_three = _load_boundary_three(immediate, root, expected_state)
    if child["expansion"] != boundary_three["expansion"]:
        raise VerificationError("boundary three is not exact step-three child output")
    transition = _transition_record(
        immediate_parent_source_sha256=immediate_parent_source_sha256,
        immediate_parent_expected_witness_sha256=(
            immediate_parent_expected_witness_sha256
        ),
        previous_transition_sha256=previous_transition_sha256,
        input_checkpoint=boundary_two,
        output_checkpoint=boundary_three,
        child=child,
        inherited_drop_ticks=inherited_drop,
        output_drop_ticks=output_drop,
        backprop_gate_records_sha256=backprop_digest,
    )
    transition_sha256 = canonical_sha256(transition)
    observed_exact = {
        "expansion_sha256": child["expansion_sha256"],
        "state_sha256": boundary_three["state_sha256"],
        "child_dropped_l1_ticks": str(child["child_dropped_l1_ticks"]),
        "transition_sha256": transition_sha256,
    }
    if not _strict_equal(observed_exact, EXPECTED_STEP3_EXACT):
        raise VerificationError("exact step-three output pins disagree")
    retained = child["retained_Neel_expectation_ticks"]
    declared = retained[0] - output_drop, retained[1] + output_drop
    witness = {
        "profile_id": WORKLOAD_IDENTITY["profile_id"],
        "observable_id": OBSERVABLE_ID,
        "input_step_index": INPUT_STEP_INDEX,
        "output_step_index": OUTPUT_STEP_INDEX,
        "immediate_parent": {
            "status": IMMEDIATE_PARENT_POSITIVE_STATUS,
            "verified": True,
            "checker_source_sha256": immediate_parent_source_sha256,
            "contract_sha256": SOURCE_PINS[1]["sha256"],
            "certificate_sha256": SOURCE_PINS[2]["sha256"],
            "expected_witness_sha256": immediate_parent_expected_witness_sha256,
            "previous_transition_sha256": previous_transition_sha256,
            "selected_parent_observable_id": OBSERVABLE_ID,
            "selected_parent_depth": INPUT_STEP_INDEX,
        },
        "transition_policy_sha256": TRANSITION_POLICY_SHA256,
        "input_state_sha256": boundary_two["state_sha256"],
        "output_state_sha256": boundary_three["state_sha256"],
        "input_expansion_sha256": boundary_two["state"]["expansion_sha256"],
        "output_expansion_sha256": child["expansion_sha256"],
        "input_cumulative_dropped_l1_ticks": str(inherited_drop),
        "child_dropped_l1_ticks": str(child["child_dropped_l1_ticks"]),
        "output_cumulative_dropped_l1_ticks": str(output_drop),
        "drop_recurrence_E3_equals_E2_plus_d3": True,
        "checkpoint_count": child["checkpoint_count"],
        "checkpoint_ledger_sha256": child["checkpoint_ledger_sha256"],
        "stage_records": child["stage_records"],
        "final_retained_Neel_expectation_interval": {
            "lower_ticks": str(retained[0]),
            "upper_ticks": str(retained[1]),
        },
        "declared_three_step_untruncated_mapped_circuit_Neel_expectation_interval": {
            "lower_ticks": str(declared[0]),
            "upper_ticks": str(declared[1]),
        },
        "transition_record": transition,
        "transition_sha256": transition_sha256,
        "resource_usage": child["resource_usage"],
        "boundary_sidecar_custody": {
            "input_relative_path": boundary_two["spec"]["relative_path"],
            "input_raw_sha256": boundary_two["spec"]["raw_sha256"],
            "output_relative_path": boundary_three["spec"]["relative_path"],
            "output_raw_sha256": boundary_three["spec"]["raw_sha256"],
            **sidecar_transport_usage,
        },
        "decision": {
            "magnetization_step3_fixed_K_child_closed": True,
            "double_occupancy_step3_certified": False,
            "remaining_97_steps_certified": False,
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
        "source_pins": [dict(pin) for pin in SOURCE_PINS],
        "output_checkpoint_spec": dict(OUTPUT_CHECKPOINT_SPEC),
        "expected_step3_exact": dict(EXPECTED_STEP3_EXACT),
        "transition_policy": dict(TRANSITION_POLICY),
        "transition_policy_sha256": TRANSITION_POLICY_SHA256,
        "workload_identity": dict(WORKLOAD_IDENTITY),
        "propagation_policy": dict(PROPAGATION_POLICY),
        "resource_limits": dict(RESOURCE_LIMITS),
        "maximum_positive_status": MAXIMUM_POSITIVE_STATUS,
        "scope_claims": dict(SCOPE_CLAIMS),
    }


def _validate_contract_raise(contract: Any) -> None:
    _preflight_resolved_pins()
    item = _exact_keys(
        contract,
        (
            "schema_version",
            "contract_fingerprint",
            "certificate_type",
            "checker_fingerprint",
            "checker_source_sha256",
            "source_pins",
            "output_checkpoint_spec",
            "expected_step3_exact",
            "transition_policy",
            "transition_policy_sha256",
            "workload_identity",
            "propagation_policy",
            "resource_limits",
            "expected_witness_sha256",
            "maximum_positive_status",
            "scope_claims",
        ),
        "contract",
    )
    if item["checker_source_sha256"] != checker_source_sha256():
        raise SchemaError("contract does not pin this checker source")
    expected = expected_contract_body()
    observed = {
        key: value
        for key, value in item.items()
        if key not in ("checker_source_sha256", "expected_witness_sha256")
    }
    if not _strict_equal(observed, expected):
        raise SchemaError("contract does not match fixed step-three policy")
    _require_resolved_sha256(item["expected_witness_sha256"], "expected_witness_sha256")
    _read_pinned_sources()


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
    try:
        _preflight_resolved_pins()
        if _VERIFIED_SELF_SOURCE_BYTES is not None:
            return _validate_contract_impl(contract)
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
                raise SchemaError(f"certificate.{field} does not match fixed policy")
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
                "Only staggered magnetization mapped step 2 to step 3 is certified.",
                "No cross-step gate fusion is used at the retained boundary.",
                "Only dropped-L1 is added to the scalar ledger; interval widening remains boxed.",
                "Double occupancy, remaining steps, exact-Hubbard error, references, and READY are not certified.",
            ],
            "errors": [],
        }
    )
    return base


def verify_certificate(contract: Any, certificate: Any) -> Dict[str, Any]:
    try:
        _preflight_resolved_pins()
        if _VERIFIED_SELF_SOURCE_BYTES is not None:
            return _verify_certificate_impl(contract, certificate)
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
    try:
        _preflight_resolved_pins()
    except (SchemaError, ValueError, TypeError, RecursionError) as exc:
        print(
            json.dumps(
                {
                    "status": "INVALID_SCHEMA",
                    "verified": False,
                    "ready_gate_eligible": False,
                    "scope_claims": dict(UNVERIFIED_SCOPE_CLAIMS),
                    "errors": [str(exc)],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
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
