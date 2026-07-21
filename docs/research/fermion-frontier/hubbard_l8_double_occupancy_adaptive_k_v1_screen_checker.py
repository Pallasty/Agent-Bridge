#!/usr/bin/env python3
"""Fail-closed infeasibility screen for the precommitted L=8 adaptive-K v1.

The checker re-executes the source-pinned positive two-step parent from its
exact checker, contract, and certificate bytes.  It then loads the certified
double-occupancy boundary-2 expansion and follows the separately precommitted
adaptive-K policy through one and only one propagation path.  Six checkpoints
commit a first-feasible K; at checkpoint seven all nine allowed candidates
exceed the contemporaneous prefix envelope.  That failure is the positive,
narrow result certified here.

No step-3 child boundary is committed.  Double-occupancy mapped depth remains
two, and neither R=100, exact-Hubbard error, a physical reference, nor READY is
certified.  The CLI always exits 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import types
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
CERTIFICATE_TYPE = "l8_double_occupancy_adaptive_k_v1_infeasibility_screen_v1"
CONTRACT_FINGERPRINT = "hubbard_l8_double_occupancy_adaptive_k_v1_screen_contract_v1"
CHECKER_FINGERPRINT = "hubbard_l8_double_occupancy_adaptive_k_v1_screen_v1"
MAXIMUM_POSITIVE_STATUS = (
    "VERIFIED_L8_DOUBLE_OCCUPANCY_ADAPTIVE_K_V1_INFEASIBILITY_SCREEN"
)
PARENT_POSITIVE_STATUS = (
    "VERIFIED_L8_TWO_STEP_MAPPED_INTERVAL_CHILD_CHAIN_SUBCERTIFICATE"
)
POLICY_ID = "hubbard_l8_double_occupancy_step3_adaptive_k_v1"
OBSERVABLE_ID = "double_occupancy"
BOUNDARY_RELATIVE_PATH = (
    "hubbard_l8_interval_checkpoints/double_occupancy_boundary_002.b85"
)
BOUNDARY_ENCODED_SHA256 = (
    "f92d5eadc01e1d9ebef86328b9eed92d867a2dd79b8bb2ba0baa821fe3b037ab"
)
BOUNDARY_STATE_SHA256 = (
    "8a3477bd3c145e95853e411ccdf60f6c23ce674dffa02fa0a1933c578a36979b"
)
BOUNDARY_EXPANSION_SHA256 = (
    "9376e6a4e2229ec0d995e36dbcf2a509a5dbf2f9bb276154458cb6ebcb91ff80"
)
BACKPROP_GATE_RECORDS_SHA256 = (
    "8504eae718b7a670fa71b79c789691e70a59365f0876f8acfdd4ea8dceee2df5"
)
TICK_DENOMINATOR = 1 << 64
CANDIDATE_K_VALUES = (
    65_536, 73_728, 81_920, 90_112, 98_304,
    106_496, 114_688, 122_880, 131_072,
)
EXPECTED_SELECTED_K_HISTORY = (73_728, 81_920, 90_112, 98_304, 114_688, 122_880)
EXPECTED_SELECTED_K_HISTORY_SHA256 = (
    "8e294855dd978a15a7ec8aac2b9f5a1e6844c2690d83bb85cbea9246f2ba2d37"
)
EXPECTED_CHECKPOINT_LEDGER_SHA256 = (
    "f1210e3bdd2d505195b93029fcd9ec3a05e29a5ee99ab854e910c7726d2ad9bb"
)
EXPECTED_FAILURE_CHECKPOINT_SHA256 = (
    "8d8aff7ab17148df346857cb9d86b07c9a031cb3a1ffec5945b3183938f0e5cd"
)
EXPECTED_COMMITTED_CHECKPOINTS = (
    (0, 73_728, "3023600994", "2283152878139582", "1b42ad8a17b05f0a09da91100b139239113d16d10237941644d35fbe2b3d7686"),
    (1, 81_920, "4141509858", "2283157019649440", "4d1e5855f9c76fb71a2a66ccab27fca5fd846457075cb8da188f6bb51b126ac7"),
    (2, 90_112, "216398869638", "2283373418519078", "83c61f37d0dbc9515840bc005618b8c4621a11a57aaed41e0afcccd8626fc47c"),
    (3, 98_304, "326858945750", "2283700277464828", "13cfde44486b161f0785b198557b873b636c9f0558839f6559ea2c1ddc027ce7"),
    (4, 114_688, "53740545959", "2283754018010787", "cb09b81f1f1b95a4ef9572833b7dc56f8dbb151c33d05bec4f3aab772ab6c98a"),
    (5, 122_880, "372996329093", "2284127014339880", "74af3f21e53666b381a4e6819f56e9fbe6905471973231825fc2b2ad2d49639f"),
)
EXPECTED_FAILURE_CANDIDATES = (
    (65_536, "161821144224452", "2445948158564332"),
    (73_728, "96060341555712", "2380187355895592"),
    (81_920, "41981074519431", "2326108088859311"),
    (90_112, "13439258743743", "2297566273083623"),
    (98_304, "6134951976745", "2290261966316625"),
    (106_496, "3721955700635", "2287848970040515"),
    (114_688, "2125723908602", "2286252738248482"),
    (122_880, "1084977840089", "2285211992179969"),
    (131_072, "429299248198", "2284556313588078"),
)
EXPECTED_RESOURCES = {
    "term_gate_visits_including_failed_checkpoint": 5_944_785,
    "peak_single_expansion_terms": 173_236,
    "maximum_expansion_coefficient_tick_bits": 63,
    "maximum_product_bits": 120,
    "multiplication_rounding_cumulative_scaled_ticks_squared": (
        "9816784588163813615680486"
    ),
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SOURCE_PINS = (
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_checker.py",
        "role": "positive_two_step_parent_checker",
        "sha256": "a562055fa361b3b31d24cd9613c38d09ddc176791454a8612eb12ac2ad06c232",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_contract.json",
        "role": "positive_two_step_parent_contract",
        "sha256": "09d4233cad211bb31e5e779156af2574ed966921168e9b4baf490691301b4e45",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_template.json",
        "role": "positive_two_step_parent_certificate",
        "sha256": "4ac0a0b3cbabb595a5872ae39bd182ab561fafaa51733625575d6bfc3f627ba1",
    },
    {
        "relative_path": "hubbard_l8_double_occupancy_adaptive_k_policy_v1.json",
        "role": "output_independent_adaptive_K_v1_precommit",
        "sha256": "319c0905d78cf42de2973b5e82e762cec26fd929c86bc770a00bbd1b6cb8b372",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_step_checker.py",
        "role": "root_fixed_tick_arithmetic_and_sequence_implementation",
        "sha256": "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a",
    },
)

RESOURCE_LIMITS = {
    "max_json_bytes": 1_048_576,
    "max_checker_source_bytes": 196_608,
    "max_pinned_source_bytes": 1_048_576,
    "max_boundary_encoded_bytes": 4_194_304,
    "max_candidate_count": 9,
    "max_candidate_K": 131_072,
    "max_single_expansion_terms": 262_144,
    "max_term_gate_visits": 200_000_000,
    "max_expansion_coefficient_tick_bits": 192,
    "max_trigonometric_tick_bits": 66,
    "max_product_bits": 384,
}

WORKLOAD_IDENTITY = {
    "profile_id": "L8_OBC_U8_T1_R100_NEEL_DOUBLE_OCCUPANCY_ADAPTIVE_K_V1_SCREEN",
    "observable_id": OBSERVABLE_ID,
    "root_parent_profile_id": "L8_OBC_U8_T1_R100_NEEL_FUSED_STRANG_TWO_STEP_CHILD_CHAIN",
    "boundary_input_step_index": 2,
    "attempted_child_step_index": 3,
    "certified_mapped_depth_after_screen": 2,
    "boundary_condition": "square_open_boundary_no_wrap",
    "n_qubits": 128,
    "step_duration": "1/100",
}

SCREEN_POLICY = {
    "policy_id": POLICY_ID,
    "candidate_K_values": list(CANDIDATE_K_VALUES),
    "selection_rule": "first_candidate_whose_exact_suffix_drop_respects_current_prefix_cap",
    "selection_time": "after_each_eight_gate_merge_before_truncation",
    "single_propagation_and_single_ranking_per_checkpoint": True,
    "prefix_cap_formula": "E2+floor(q*(B-E2)/(98*144))",
    "cross_step_fusion_used": False,
    "parent_globals_may_be_monkeypatched": False,
    "successful_child_boundary_required_for_depth_increment": True,
    "no_candidate_action": "fail_closed_without_committing_child_boundary",
}

SCOPE_CLAIMS = {
    "checker_execution_from_contract_pinned_source_bytes_verified": True,
    "same_byte_positive_two_step_parent_execution_verified": True,
    "adaptive_K_v1_precommit_source_pin_verified": True,
    "double_occupancy_boundary_2_custody_verified": True,
    "root_parent_arithmetic_globals_unchanged_verified": True,
    "single_propagation_single_ranking_suffix_sum_policy_verified": True,
    "first_six_first_feasible_candidate_commits_verified": True,
    "checkpoint_seven_all_nine_candidates_infeasible_verified": True,
    "fail_closed_without_step_3_child_boundary_verified": True,
    "double_occupancy_certified_mapped_depth": 2,
    "adaptive_step_3_child_boundary_committed": False,
    "remaining_97_mapped_steps": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}
UNVERIFIED_SCOPE_CLAIMS = {
    key: (False if value is True else value) for key, value in SCOPE_CLAIMS.items()
}
UNVERIFIED_SCOPE_CLAIMS["double_occupancy_certified_mapped_depth"] = "NOT_VERIFIED"


class SchemaError(ValueError):
    """Malformed input, source drift, unresolved custody, or resource failure."""


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
            value, allow_nan=False, ensure_ascii=True,
            separators=(",", ":"), sort_keys=True,
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
    module = types.ModuleType("verified_hubbard_l8_adaptive_k_v1_screen")
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


def _preflight_boundary_sidecar() -> None:
    path = HERE / BOUNDARY_RELATIVE_PATH
    with path.open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_boundary_encoded_bytes"] + 1)
    if len(payload) > RESOURCE_LIMITS["max_boundary_encoded_bytes"]:
        raise SchemaError("boundary-2 encoded sidecar exceeds cap")
    if hashlib.sha256(payload).hexdigest() != BOUNDARY_ENCODED_SHA256:
        raise SchemaError("boundary-2 encoded sidecar hash mismatch")


def _load_module_from_pinned_source(
    source: bytes, *, module_name: str, filename: str
) -> Any:
    module = types.ModuleType(module_name)
    module.__file__ = str(HERE / filename)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = source
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def _validate_policy(policy: Any) -> Mapping[str, Any]:
    item = _exact_keys(
        policy,
        (
            "schema_version", "policy_id", "policy_role", "observable_id",
            "child_step_index", "immediate_parent", "arithmetic_and_sequence",
            "candidate_policy", "precommit_boundary",
            "required_checkpoint_ledger_bindings", "resource_limits",
            "truncation_budget", "scope_boundary",
        ),
        "adaptive policy",
    )
    fixed = {
        "schema_version": 1,
        "policy_id": POLICY_ID,
        "observable_id": OBSERVABLE_ID,
        "child_step_index": 3,
    }
    for key, expected in fixed.items():
        if type(item[key]) is not type(expected) or item[key] != expected:
            raise SchemaError(f"adaptive policy {key} mismatch")
    parent = item["immediate_parent"]
    expected_parent = {
        "checker_relative_path": SOURCE_PINS[0]["relative_path"],
        "checker_sha256": SOURCE_PINS[0]["sha256"],
        "contract_relative_path": SOURCE_PINS[1]["relative_path"],
        "contract_sha256": SOURCE_PINS[1]["sha256"],
        "certificate_relative_path": SOURCE_PINS[2]["relative_path"],
        "certificate_sha256": SOURCE_PINS[2]["sha256"],
        "boundary_2_relative_path": BOUNDARY_RELATIVE_PATH,
        "boundary_2_encoded_sha256": BOUNDARY_ENCODED_SHA256,
        "boundary_2_state_sha256": BOUNDARY_STATE_SHA256,
        "boundary_2_expansion_sha256": BOUNDARY_EXPANSION_SHA256,
        "required_positive_status": PARENT_POSITIVE_STATUS,
        "required_certified_depth": 2,
    }
    for key, expected in expected_parent.items():
        if parent.get(key) != expected or type(parent.get(key)) is not type(expected):
            raise SchemaError(f"adaptive policy immediate_parent.{key} mismatch")
    arithmetic = item["arithmetic_and_sequence"]
    expected_arithmetic = {
        "root_arithmetic_checker_relative_path": SOURCE_PINS[4]["relative_path"],
        "root_arithmetic_checker_sha256": SOURCE_PINS[4]["sha256"],
        "backprop_gate_records_sha256": BACKPROP_GATE_RECORDS_SHA256,
        "fixed_checkpoint_count": 144,
        "fixed_gate_count": 1_152,
        "gates_per_checkpoint": 8,
        "tick_denominator": TICK_DENOMINATOR,
        "cross_step_H1_half_stage_fusion": False,
        "Neel_expectation_is_forbidden_as_a_K_selection_input": True,
        "future_gates_and_final_interval_are_forbidden_as_K_selection_inputs": True,
    }
    for key, expected in expected_arithmetic.items():
        if arithmetic.get(key) != expected or type(arithmetic.get(key)) is not type(expected):
            raise SchemaError(f"adaptive policy arithmetic_and_sequence.{key} mismatch")
    candidate = item["candidate_policy"]
    if candidate.get("candidate_K_values_in_strict_ascending_order") != list(
        CANDIDATE_K_VALUES
    ):
        raise SchemaError("adaptive policy candidate K list mismatch")
    expected_candidate = {
        "all_candidate_drop_values_derived_from_one_ranked_suffix_sum": True,
        "all_smaller_candidates_must_be_recorded_infeasible": True,
        "single_propagation_and_single_ranking_per_checkpoint": True,
        "no_candidate_is_feasible": (
            "fail_closed_without_committing_a_child_boundary"
        ),
    }
    for key, expected in expected_candidate.items():
        if candidate.get(key) != expected:
            raise SchemaError(f"adaptive policy candidate_policy.{key} mismatch")
    limits = item["resource_limits"]
    for key in (
        "max_candidate_count", "max_candidate_K", "max_single_expansion_terms",
        "max_term_gate_visits", "max_expansion_coefficient_tick_bits",
        "max_trigonometric_tick_bits", "max_product_bits",
    ):
        if limits.get(key) != RESOURCE_LIMITS[key]:
            raise SchemaError(f"adaptive policy resource_limits.{key} mismatch")
    budget = item["truncation_budget"]
    expected_budget = {
        "tick_denominator": TICK_DENOMINATOR,
        "input_cumulative_drop_ticks": 2_283_149_854_538_588,
        "maximum_cumulative_drop_ticks": 4_611_686_018_427_387,
        "remaining_checkpoint_count": 14_112,
        "checkpoints_per_step": 144,
        "prefix_cap_ticks_formula": "E2+floor(q*(B-E2)/(98*144))",
        "slack_carries_forward_but_may_not_be_borrowed_from_future_prefixes": True,
    }
    for key, expected in expected_budget.items():
        if budget.get(key) != expected or type(budget.get(key)) is not type(expected):
            raise SchemaError(f"adaptive policy truncation_budget.{key} mismatch")
    return item


def _load_positive_parent_and_boundary(
    sources: Mapping[str, bytes], policy: Mapping[str, Any]
) -> Tuple[Any, Any, Mapping[str, Any], Mapping[str, Any]]:
    two_step = _load_module_from_pinned_source(
        sources[SOURCE_PINS[0]["relative_path"]],
        module_name="pinned_positive_two_step_parent",
        filename=SOURCE_PINS[0]["relative_path"],
    )
    parent_contract = _strict_json_bytes(
        sources[SOURCE_PINS[1]["relative_path"]], "positive parent contract"
    )
    parent_certificate = _strict_json_bytes(
        sources[SOURCE_PINS[2]["relative_path"]], "positive parent certificate"
    )
    parent_result = two_step.verify_certificate(parent_contract, parent_certificate)
    if (
        parent_result.get("status") != PARENT_POSITIVE_STATUS
        or parent_result.get("verified") is not True
    ):
        raise VerificationError("same-byte two-step parent execution is not positive")
    parent_witness = parent_result.get("recomputed_witness")
    if type(parent_witness) is not dict:
        raise VerificationError("positive parent omitted recomputed witness")
    if not _strict_equal(parent_witness, parent_certificate.get("witness_claim")):
        raise VerificationError("positive parent witness differs from certificate")
    if canonical_sha256(parent_witness) != parent_contract.get(
        "expected_witness_sha256"
    ):
        raise VerificationError("positive parent expected-witness pin mismatch")
    root = _load_module_from_pinned_source(
        sources[SOURCE_PINS[4]["relative_path"]],
        module_name="pinned_root_fixed_tick_arithmetic",
        filename=SOURCE_PINS[4]["relative_path"],
    )
    for key in (
        "max_single_expansion_terms", "max_term_gate_visits",
        "max_expansion_coefficient_tick_bits", "max_trigonometric_tick_bits",
        "max_product_bits",
    ):
        if root.RESOURCE_LIMITS.get(key) != RESOURCE_LIMITS[key]:
            raise VerificationError(f"root arithmetic global resource cap drift: {key}")
    if root.RETAINED_TERM_CAP != 65_536:
        raise VerificationError("root arithmetic retained cap global was modified")
    child_claims = {
        claim["observable_id"]: claim
        for claim in parent_witness.get("child_witnesses", [])
        if type(claim) is dict and "observable_id" in claim
    }
    double_claim = child_claims.get(OBSERVABLE_ID)
    if type(double_claim) is not dict:
        raise VerificationError("positive parent lacks double-occupancy child claim")
    if double_claim.get("transition_sha256") != policy["immediate_parent"].get(
        "boundary_2_transition_sha256"
    ):
        raise VerificationError("positive parent boundary-2 transition pin mismatch")
    root_parent = parent_witness.get("root_parent")
    if type(root_parent) is not dict:
        raise VerificationError("positive parent root custody is malformed")
    checkpoint_spec = next(
        (
            spec for spec in two_step.CHECKPOINT_SPECS
            if spec.get("observable_id") == OBSERVABLE_ID
            and spec.get("step_index") == 2
        ),
        None,
    )
    if type(checkpoint_spec) is not dict:
        raise VerificationError("positive parent lacks boundary-2 checkpoint spec")
    if (
        checkpoint_spec.get("relative_path") != BOUNDARY_RELATIVE_PATH
        or checkpoint_spec.get("encoded_sha256") != BOUNDARY_ENCODED_SHA256
    ):
        raise VerificationError("positive parent boundary-2 checkpoint spec drift")
    boundary = two_step._load_checkpoint(
        checkpoint_spec,
        parent=root,
        parent_source_sha256=two_step.SOURCE_PINS[0]["sha256"],
        parent_expected_witness_sha256=root_parent["expected_witness_sha256"],
        backprop_gate_records_sha256=root_parent["backprop_gate_records_sha256"],
    )
    if boundary["state_sha256"] != BOUNDARY_STATE_SHA256:
        raise VerificationError("boundary-2 state digest mismatch")
    if boundary["state"].get("expansion_sha256") != BOUNDARY_EXPANSION_SHA256:
        raise VerificationError("boundary-2 expansion digest mismatch")
    return two_step, root, parent_witness, boundary


def _run_adaptive_screen(
    two_step: Any,
    root: Any,
    policy: Mapping[str, Any],
    parent_witness: Mapping[str, Any],
    boundary: Mapping[str, Any],
) -> Dict[str, Any]:
    retained_cap_before = root.RETAINED_TERM_CAP
    resource_limits_before = dict(root.RESOURCE_LIMITS)
    groups = root._independent_groups(root._independent_bonds())
    _forward_stages, _forward_gates, stages, sequence = root._sequence_records(groups)
    del _forward_stages, _forward_gates
    if sequence["backprop_gate_records_sha256"] != BACKPROP_GATE_RECORDS_SHA256:
        raise VerificationError("root backpropagation sequence digest mismatch")
    if sum(stage["gate_count"] for stage in stages) != 1_152:
        raise VerificationError("root backpropagation sequence gate count mismatch")
    trig = {}
    for theta in sorted({theta for stage in stages for _, theta in stage["gates"]}):
        sine, cosine, _record = root._taylor_trig_record(theta)
        trig[theta] = sine, cosine
    expansion = dict(boundary["expansion"])
    budget = policy["truncation_budget"]
    E2 = budget["input_cumulative_drop_ticks"]
    B = budget["maximum_cumulative_drop_ticks"]
    denominator = budget["remaining_checkpoint_count"]
    if int(boundary["state"]["cumulative_dropped_l1_ticks"]) != E2:
        raise VerificationError("boundary-2 cumulative drop disagrees with policy")
    cumulative = E2
    counter = root.PropagationCounter()
    counter.observe(expansion)
    for interval in expansion.values():
        counter.observe_interval(interval)
    ledger: List[Dict[str, Any]] = []
    selected_history: List[int] = []
    global_gate_index = 0
    failure: Dict[str, Any] | None = None
    for stage in stages:
        gates = stage["gates"]
        for batch_start in range(0, len(gates), 8):
            checkpoint_index = len(ledger)
            checkpoint_number = checkpoint_index + 1
            batch = gates[batch_start : batch_start + 8]
            if len(batch) != 8:
                raise VerificationError("adaptive checkpoint batch is not exactly eight gates")
            input_digest = root._tick_digest(expansion)
            input_count = len(expansion)
            gate_records = [
                {
                    "gate_occurrence_index": global_gate_index + offset,
                    "generator_x_hex": hex(generator[0]),
                    "generator_z_hex": hex(generator[1]),
                    "theta": root._format_fraction(theta),
                }
                for offset, (generator, theta) in enumerate(batch)
            ]
            rounding_before = counter.multiplication_rounding_l1_scaled_ticks_squared
            visits_before = counter.term_gate_visits
            counter.begin_window(expansion)
            for generator, theta in batch:
                sine, cosine = trig[theta]
                expansion = root._propagate_gate(
                    expansion, generator, sine, cosine, counter
                )
            pretruncation_count = len(expansion)
            pretruncation_digest = root._tick_digest(expansion)
            ranked = sorted(
                expansion,
                key=lambda key: (
                    -root._abs_upper(expansion[key]), key[0], key[1]
                ),
            )
            suffix = [0] * (len(ranked) + 1)
            for index in range(len(ranked) - 1, -1, -1):
                suffix[index] = suffix[index + 1] + root._abs_upper(
                    expansion[ranked[index]]
                )
            prefix_cap = E2 + checkpoint_number * (B - E2) // denominator
            prefix_slack = prefix_cap - cumulative
            candidate_records: List[Dict[str, Any]] = []
            selected_index: int | None = None
            for index, candidate_K in enumerate(CANDIDATE_K_VALUES):
                effective = min(candidate_K, pretruncation_count)
                candidate_drop = suffix[effective]
                feasible = cumulative + candidate_drop <= prefix_cap
                candidate_records.append(
                    {
                        "candidate_index": index,
                        "K": candidate_K,
                        "effective_retained_count": effective,
                        "dropped_term_count": pretruncation_count - effective,
                        "drop_ticks": str(candidate_drop),
                        "E_after_if_selected_ticks": str(cumulative + candidate_drop),
                        "feasible_under_current_prefix_cap": feasible,
                    }
                )
                if selected_index is None and feasible:
                    selected_index = index
            base_record = {
                "step_index": 3,
                "checkpoint_index_zero_based": checkpoint_index,
                "checkpoint_number_one_based": checkpoint_number,
                "backprop_stage_index": stage["backprop_stage_index"],
                "forward_stage_index": stage["forward_stage_index"],
                "group": stage["group"],
                "batch_in_stage": batch_start // 8,
                "input_expansion_count": input_count,
                "input_expansion_sha256": input_digest,
                "gate_occurrence_first": global_gate_index,
                "gate_occurrence_last": global_gate_index + 7,
                "eight_gate_occurrences_sha256": canonical_sha256(gate_records),
                "pretruncation_expansion_count": pretruncation_count,
                "pretruncation_expansion_sha256": pretruncation_digest,
                "budget_prefix_cap_ticks": str(prefix_cap),
                "E_before_ticks": str(cumulative),
                "prefix_slack_before_selection_ticks": str(prefix_slack),
                "candidate_records": candidate_records,
                "rounding_widening_increment_scaled_ticks_squared": str(
                    counter.multiplication_rounding_l1_scaled_ticks_squared
                    - rounding_before
                ),
                "rounding_widening_cumulative_scaled_ticks_squared": str(
                    counter.multiplication_rounding_l1_scaled_ticks_squared
                ),
                "term_gate_visits_increment": counter.term_gate_visits - visits_before,
                "term_gate_visits_cumulative": counter.term_gate_visits,
                "peak_single_expansion_terms_this_checkpoint": (
                    counter.window_peak_live_terms
                ),
                "peak_single_expansion_terms_cumulative": counter.peak_live_terms,
                "maximum_expansion_coefficient_tick_bits": (
                    counter.maximum_expansion_coefficient_tick_bits
                ),
                "maximum_product_bits": counter.maximum_product_bits,
            }
            global_gate_index += 8
            if selected_index is None:
                failure = {
                    **base_record,
                    "checkpoint_status": (
                        "NO_CANDIDATE_FEASIBLE_CHILD_BOUNDARY_NOT_COMMITTED"
                    ),
                    "selected_candidate_index": None,
                    "selected_K": None,
                    "selected_effective_retained_count": None,
                    "selected_checkpoint_drop_ticks": None,
                    "selected_dropped_term_count": None,
                    "selected_dropped_terms_sha256": None,
                    "retained_expansion_count": None,
                    "retained_expansion_sha256": None,
                    "E_after_ticks": None,
                    "minimum_retained_abs_upper_ticks": None,
                    "maximum_dropped_abs_upper_ticks": None,
                    "smallest_excess_at_max_K_ticks": str(
                        cumulative
                        + int(candidate_records[-1]["drop_ticks"])
                        - prefix_cap
                    ),
                }
                ledger.append(failure)
                break
            selected = candidate_records[selected_index]
            effective = selected["effective_retained_count"]
            retained_keys = ranked[:effective]
            dropped_keys = ranked[effective:]
            checkpoint_drop = int(selected["drop_ticks"])
            retained = {key: expansion[key] for key in retained_keys}
            selected_record = {
                **base_record,
                "checkpoint_status": (
                    "SELECTED_FIRST_FEASIBLE_CANDIDATE_AND_COMMITTED"
                ),
                "selected_candidate_index": selected_index,
                "selected_K": selected["K"],
                "selected_effective_retained_count": effective,
                "selected_checkpoint_drop_ticks": str(checkpoint_drop),
                "selected_dropped_term_count": len(dropped_keys),
                "selected_dropped_terms_sha256": root._tick_digest(
                    expansion, dropped_keys
                ),
                "retained_expansion_count": len(retained),
                "retained_expansion_sha256": root._tick_digest(retained),
                "E_after_ticks": str(cumulative + checkpoint_drop),
                "minimum_retained_abs_upper_ticks": str(
                    min(
                        (root._abs_upper(retained[key]) for key in retained),
                        default=0,
                    )
                ),
                "maximum_dropped_abs_upper_ticks": str(
                    max(
                        (root._abs_upper(expansion[key]) for key in dropped_keys),
                        default=0,
                    )
                ),
            }
            ledger.append(selected_record)
            selected_history.append(selected["K"])
            cumulative += checkpoint_drop
            expansion = retained
        if failure is not None:
            break
    if failure is None:
        raise VerificationError("adaptive fixture unexpectedly committed a child boundary")
    if root.RETAINED_TERM_CAP != retained_cap_before:
        raise VerificationError("root retained-term global changed during adaptive screen")
    if not _strict_equal(root.RESOURCE_LIMITS, resource_limits_before):
        raise VerificationError("root resource-limit globals changed during adaptive screen")
    ledger_sha256 = canonical_sha256(ledger)
    failure_sha256 = canonical_sha256(failure)
    history_sha256 = canonical_sha256(selected_history)
    if tuple(selected_history) != EXPECTED_SELECTED_K_HISTORY:
        raise VerificationError("adaptive selected-K history mismatch")
    if history_sha256 != EXPECTED_SELECTED_K_HISTORY_SHA256:
        raise VerificationError("adaptive selected-K history digest mismatch")
    if ledger_sha256 != EXPECTED_CHECKPOINT_LEDGER_SHA256:
        raise VerificationError("adaptive checkpoint ledger digest mismatch")
    if failure_sha256 != EXPECTED_FAILURE_CHECKPOINT_SHA256:
        raise VerificationError("adaptive failure checkpoint digest mismatch")
    for observed, expected in zip(ledger[:6], EXPECTED_COMMITTED_CHECKPOINTS):
        checkpoint_index, selected_K, drop_ticks, E_after, retained_sha256 = expected
        exact = (
            observed["checkpoint_index_zero_based"],
            observed["selected_K"],
            observed["selected_checkpoint_drop_ticks"],
            observed["E_after_ticks"],
            observed["retained_expansion_sha256"],
        )
        if exact != expected:
            raise VerificationError(
                f"adaptive committed checkpoint {checkpoint_index} exact pin mismatch"
            )
    observed_failure_candidates = tuple(
        (record["K"], record["drop_ticks"], record["E_after_if_selected_ticks"])
        for record in failure["candidate_records"]
    )
    if observed_failure_candidates != EXPECTED_FAILURE_CANDIDATES:
        raise VerificationError("adaptive failure candidate evaluations mismatch")
    resources = {
        "term_gate_visits_including_failed_checkpoint": counter.term_gate_visits,
        "peak_single_expansion_terms": counter.peak_live_terms,
        "maximum_expansion_coefficient_tick_bits": (
            counter.maximum_expansion_coefficient_tick_bits
        ),
        "maximum_product_bits": counter.maximum_product_bits,
        "multiplication_rounding_cumulative_scaled_ticks_squared": str(
            counter.multiplication_rounding_l1_scaled_ticks_squared
        ),
    }
    if not _strict_equal(resources, EXPECTED_RESOURCES):
        raise VerificationError("adaptive deterministic resource record mismatch")
    if failure["checkpoint_index_zero_based"] != 6:
        raise VerificationError("adaptive failure checkpoint index mismatch")
    if failure["budget_prefix_cap_ticks"] != "2284304882397659":
        raise VerificationError("adaptive failure prefix cap mismatch")
    if failure["E_before_ticks"] != "2284127014339880":
        raise VerificationError("adaptive failure E-before mismatch")
    if failure["prefix_slack_before_selection_ticks"] != "177868057779":
        raise VerificationError("adaptive failure prefix slack mismatch")
    if failure["smallest_excess_at_max_K_ticks"] != "251431190419":
        raise VerificationError("adaptive failure smallest excess mismatch")
    parent_double_claim = next(
        (
            claim
            for claim in parent_witness["child_witnesses"]
            if claim["observable_id"] == OBSERVABLE_ID
        ),
        None,
    )
    if type(parent_double_claim) is not dict:
        raise VerificationError("positive parent double-occupancy claim disappeared")
    return {
        "attempt_status": "INFEASIBLE_AT_CHECKPOINT_7_NO_CHILD_BOUNDARY",
        "input_certified_mapped_depth": 2,
        "output_certified_mapped_depth": 2,
        "attempted_child_step_index": 3,
        "child_boundary_committed": False,
        "completed_checkpoint_count": 6,
        "failure_checkpoint_included_in_ledger": True,
        "failure_checkpoint_index_zero_based": 6,
        "failure_checkpoint_number_one_based": 7,
        "input_boundary_state_sha256": boundary["state_sha256"],
        "input_boundary_expansion_sha256": boundary["state"]["expansion_sha256"],
        "input_parent_transition_sha256": parent_double_claim["transition_sha256"],
        "selected_K_history": selected_history,
        "selected_K_history_sha256": history_sha256,
        "checkpoint_ledger": ledger,
        "checkpoint_ledger_sha256": ledger_sha256,
        "failure_checkpoint_sha256": failure_sha256,
        "last_committed_cumulative_drop_ticks": str(cumulative),
        "failure_prefix_cap_ticks": failure["budget_prefix_cap_ticks"],
        "failure_prefix_slack_ticks": failure[
            "prefix_slack_before_selection_ticks"
        ],
        "failure_smallest_excess_at_max_K_ticks": failure[
            "smallest_excess_at_max_K_ticks"
        ],
        "resources": resources,
        "execution_invariants": {
            "same_positive_parent_boundary_used": True,
            "root_globals_monkeypatched": False,
            "single_propagation_per_checkpoint": True,
            "single_ranking_and_suffix_sum_per_checkpoint": True,
            "first_feasible_candidate_selected": True,
            "all_smaller_candidates_recorded_infeasible": True,
            "Neel_expectation_used_for_selection": False,
            "future_gate_or_final_interval_used_for_selection": False,
            "cross_step_fusion_used": False,
            "failed_checkpoint_committed": False,
        },
    }


_WITNESS_CACHE_BYTES: bytes | None = None


def recompute_witness() -> Dict[str, Any]:
    global _WITNESS_CACHE_BYTES
    if _WITNESS_CACHE_BYTES is not None:
        _read_pinned_sources()
        _preflight_boundary_sidecar()
        return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))
    sources = _read_pinned_sources()
    policy = _validate_policy(
        _strict_json_bytes(
            sources[SOURCE_PINS[3]["relative_path"]], "adaptive policy"
        )
    )
    _preflight_boundary_sidecar()
    two_step, root, parent_witness, boundary = _load_positive_parent_and_boundary(
        sources, policy
    )
    attempt = _run_adaptive_screen(
        two_step, root, policy, parent_witness, boundary
    )
    witness = {
        "profile_id": WORKLOAD_IDENTITY["profile_id"],
        "source_pinned_positive_parent": {
            "status": PARENT_POSITIVE_STATUS,
            "verified": True,
            "same_byte_checker_contract_certificate_executed": True,
            "checker_sha256": SOURCE_PINS[0]["sha256"],
            "contract_sha256": SOURCE_PINS[1]["sha256"],
            "certificate_sha256": SOURCE_PINS[2]["sha256"],
            "expected_witness_sha256": canonical_sha256(parent_witness),
        },
        "adaptive_policy_precommit": {
            "policy_id": POLICY_ID,
            "policy_sha256": SOURCE_PINS[3]["sha256"],
            "output_pins_absent_from_policy": True,
            "candidate_K_values": list(CANDIDATE_K_VALUES),
        },
        "boundary_2_custody": {
            "relative_path": BOUNDARY_RELATIVE_PATH,
            "encoded_sha256": BOUNDARY_ENCODED_SHA256,
            "state_sha256": BOUNDARY_STATE_SHA256,
            "expansion_sha256": BOUNDARY_EXPANSION_SHA256,
            "semantic_expansion_loaded_and_verified": True,
        },
        "adaptive_infeasibility_attempt": attempt,
        "decision": {
            "adaptive_K_v1_infeasibility_screen_closed": True,
            "step_3_child_boundary_committed": False,
            "double_occupancy_certified_mapped_depth": 2,
            "new_policy_version_required_for_any_relaxation": True,
            "remaining_97_steps_certified": False,
            "full_R100_or_exact_Hubbard_error_certified": False,
            "physical_reference_qualified": False,
            "ready_gate_eligible": False,
        },
    }
    _WITNESS_CACHE_BYTES = _canonical_bytes(witness)
    return json.loads(_WITNESS_CACHE_BYTES.decode("ascii"))


def _expected_screen_exact() -> Dict[str, Any]:
    return {
        "selected_K_history": list(EXPECTED_SELECTED_K_HISTORY),
        "selected_K_history_sha256": EXPECTED_SELECTED_K_HISTORY_SHA256,
        "checkpoint_ledger_sha256": EXPECTED_CHECKPOINT_LEDGER_SHA256,
        "failure_checkpoint_sha256": EXPECTED_FAILURE_CHECKPOINT_SHA256,
        "completed_checkpoint_count": 6,
        "failure_checkpoint_index_zero_based": 6,
        "last_committed_cumulative_drop_ticks": "2284127014339880",
        "failure_prefix_cap_ticks": "2284304882397659",
        "failure_prefix_slack_ticks": "177868057779",
        "failure_smallest_excess_at_max_K_ticks": "251431190419",
        "committed_checkpoint_exact_pins": [
            {
                "checkpoint_index_zero_based": item[0],
                "selected_K": item[1],
                "drop_ticks": item[2],
                "E_after_ticks": item[3],
                "retained_expansion_sha256": item[4],
            }
            for item in EXPECTED_COMMITTED_CHECKPOINTS
        ],
        "failure_candidate_evaluations": [
            {"K": item[0], "drop_ticks": item[1], "E_after_ticks": item[2]}
            for item in EXPECTED_FAILURE_CANDIDATES
        ],
        "resources": dict(EXPECTED_RESOURCES),
    }


def expected_contract_body() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "contract_fingerprint": CONTRACT_FINGERPRINT,
        "certificate_type": CERTIFICATE_TYPE,
        "checker_fingerprint": CHECKER_FINGERPRINT,
        "source_pins": list(SOURCE_PINS),
        "workload_identity": dict(WORKLOAD_IDENTITY),
        "screen_policy": dict(SCREEN_POLICY),
        "resource_limits": dict(RESOURCE_LIMITS),
        "expected_screen_exact": _expected_screen_exact(),
        "maximum_positive_status": MAXIMUM_POSITIVE_STATUS,
        "scope_claims": dict(SCOPE_CLAIMS),
    }


def _validate_contract_raise(contract: Any) -> None:
    item = _exact_keys(
        contract,
        (
            "schema_version", "contract_fingerprint", "certificate_type",
            "checker_fingerprint", "checker_source_sha256", "source_pins",
            "workload_identity", "screen_policy", "resource_limits",
            "expected_screen_exact", "expected_witness_sha256",
            "maximum_positive_status", "scope_claims",
        ),
        "contract",
    )
    checker_pin = item["checker_source_sha256"]
    if type(checker_pin) is not str or not SHA256_RE.fullmatch(checker_pin):
        raise SchemaError("contract checker source hash is malformed")
    if checker_pin != checker_source_sha256():
        raise SchemaError("contract does not pin this checker source")
    expected = expected_contract_body()
    observed = {
        key: value
        for key, value in item.items()
        if key not in ("checker_source_sha256", "expected_witness_sha256")
    }
    if not _strict_equal(observed, expected):
        raise SchemaError("contract does not match fixed checker policy")
    witness_pin = item["expected_witness_sha256"]
    if type(witness_pin) is not str or not SHA256_RE.fullmatch(witness_pin):
        raise SchemaError("contract expected-witness hash is malformed")
    _read_pinned_sources()
    _preflight_boundary_sidecar()


def _validate_contract_impl(contract: Any) -> List[str]:
    try:
        _validate_contract_raise(contract)
    except (
        SchemaError, VerificationError, KeyError, TypeError, ValueError,
        OSError, RecursionError,
    ) as exc:
        return [str(exc)]
    return []


def validate_contract(contract: Any) -> List[str]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _validate_contract_impl(contract)
    try:
        return _execute_from_verified_self_source("_validate_contract_impl", contract)
    except (
        SchemaError, VerificationError, KeyError, TypeError, ValueError,
        OSError, RecursionError,
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
                "schema_version", "certificate_type", "contract_fingerprint",
                "workload_identity", "screen_policy", "witness_claim",
                "scope_claims",
            ),
            "certificate",
        )
        for field, expected in (
            ("schema_version", 1),
            ("certificate_type", CERTIFICATE_TYPE),
            ("contract_fingerprint", CONTRACT_FINGERPRINT),
            ("workload_identity", WORKLOAD_IDENTITY),
            ("screen_policy", SCREEN_POLICY),
            ("scope_claims", SCOPE_CLAIMS),
        ):
            if not _strict_equal(cert[field], expected):
                raise SchemaError(f"certificate.{field} does not match policy")
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
        VerificationError, KeyError, TypeError, ValueError, OSError,
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
                "The positive result is only adaptive-K v1 infeasibility at checkpoint seven.",
                "No step-3 child boundary is committed; double-occupancy mapped depth remains two.",
                "Any larger K, looser prefix envelope, or resource relaxation requires a new precommit.",
                "R=100, exact-Hubbard error, physical reference qualification, and READY are not certified.",
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
        SchemaError, VerificationError, KeyError, TypeError, ValueError,
        OSError, RecursionError,
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
