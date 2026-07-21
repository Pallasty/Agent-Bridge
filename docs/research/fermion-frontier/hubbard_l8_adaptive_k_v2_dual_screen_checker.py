#!/usr/bin/env python3
"""Formal dual infeasibility screens for the precommitted L8 adaptive-K v2 routes.

The checker executes the source-pinned positive magnetization step-3 parent.  That
parent same-byte executes the positive two-step chain, which is also the immediate
parent required by the double-occupancy policy.  It then independently replays one
new attempted step for each observable through the source-pinned v2 arithmetic
kernel.  Diagnostic transcript records are never loaded as result evidence.

Both precommitted K ladders fail before checkpoint 144, so no child boundary,
transition, sidecar, or depth increment is issued.  A verified screen is a positive
narrow infeasibility result, but the CLI deliberately exits 1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
SELF_NAME = "hubbard_l8_adaptive_k_v2_dual_screen_checker.py"
CONTRACT_NAME = "hubbard_l8_adaptive_k_v2_dual_screen_contract.json"
CERTIFICATE_NAME = "hubbard_l8_adaptive_k_v2_dual_screen_template.json"
CERTIFICATE_TYPE = "l8_adaptive_k_v2_dual_infeasibility_screens_v1"
CONTRACT_FINGERPRINT = "hubbard_l8_adaptive_k_v2_dual_screen_contract_v1"
CHECKER_FINGERPRINT = "hubbard_l8_adaptive_k_v2_dual_screen_checker_v1"
MAXIMUM_POSITIVE_STATUS = "VERIFIED_L8_ADAPTIVE_K_V2_DUAL_INFEASIBILITY_SCREENS"
M_PARENT_STATUS = "VERIFIED_L8_MAGNETIZATION_STEP3_MAPPED_INTERVAL_CHILD_SUBCERTIFICATE"
D_PARENT_STATUS = "VERIFIED_L8_TWO_STEP_MAPPED_INTERVAL_CHILD_CHAIN_SUBCERTIFICATE"

SOURCE_PINS = (
    {
        "relative_path": "hubbard_l8_adaptive_k_v2_design_probe.py",
        "role": "deterministic_replay_driver_without_certificate_authority",
        "sha256": "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3",
    },
    {
        "relative_path": "hubbard_l8_adaptive_k_arithmetic_v2.py",
        "role": "formal_new_step_fixed_tick_arithmetic_kernel",
        "sha256": "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_step_checker.py",
        "role": "source_pinned_sequence_trigonometry_and_Neel_oracle",
        "sha256": "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a",
    },
    {
        "relative_path": "hubbard_l8_magnetization_adaptive_k_policy_v2.json",
        "role": "precommitted_magnetization_step4_policy",
        "sha256": "c1300af91ed28c69b309e19ffdb0e772e3e256432b08e1b17adfcea58700dd16",
    },
    {
        "relative_path": "hubbard_l8_double_occupancy_adaptive_k_policy_v2.json",
        "role": "precommitted_double_occupancy_step3_policy",
        "sha256": "5099b6e29e52c1dc4ff26b9b4fd408fbd4483e7e4b7a554aa718226336e9c07b",
    },
    {
        "relative_path": "hubbard_l8_magnetization_adaptive_k_v2_design_transcript.json",
        "role": "non_normative_magnetization_design_provenance_bytes_only",
        "sha256": "aaed027aa212f60a40eea93c0826c45cfe5ffa23ef94b0b616213d794e83fd12",
    },
    {
        "relative_path": "hubbard_l8_double_occupancy_adaptive_k_v2_design_transcript.json",
        "role": "non_normative_double_occupancy_design_provenance_bytes_only",
        "sha256": "4223155009f7dc4c8fe883a75ac71116ddaff82492e1e1602685e893c4c2368c",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_checker.py",
        "role": "same_byte_positive_magnetization_step3_parent_checker",
        "sha256": "4e471b6f22838b2e9621adeeb757e7fa8277e3d8c4985eee392b182530c0c717",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_contract.json",
        "role": "positive_magnetization_step3_parent_contract",
        "sha256": "fb1d5e82819d39f217a8c1c7f4979a689f4d46b8d691a8f464cad9012c197387",
    },
    {
        "relative_path": "hubbard_l8_magnetization_interval_step3_template.json",
        "role": "positive_magnetization_step3_parent_certificate",
        "sha256": "b68544091be417eed5310d8579eb8dc4d1a51e1863ed1fb7a8cbfa1fc6004eb6",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_checker.py",
        "role": "transitive_same_byte_positive_two_step_parent_checker",
        "sha256": "a562055fa361b3b31d24cd9613c38d09ddc176791454a8612eb12ac2ad06c232",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_contract.json",
        "role": "transitive_positive_two_step_parent_contract",
        "sha256": "09d4233cad211bb31e5e779156af2574ed966921168e9b4baf490691301b4e45",
    },
    {
        "relative_path": "hubbard_l8_observable_interval_two_step_template.json",
        "role": "transitive_positive_two_step_parent_certificate",
        "sha256": "4ac0a0b3cbabb595a5872ae39bd182ab561fafaa51733625575d6bfc3f627ba1",
    },
)

RESOURCE_LIMITS = {
    "max_json_bytes": 4_194_304,
    "max_checker_source_bytes": 262_144,
    "max_pinned_source_bytes": 4_194_304,
    "max_dependency_files": 13,
    "max_witness_records": 2,
    "max_candidate_count": 21,
}

WORKLOAD_IDENTITY = {
    "profile_id": "L8_OBC_U8_T1_R100_NEEL_ADAPTIVE_K_V2_DUAL_SCREEN",
    "linear_size": 8,
    "n_sites": 64,
    "n_qubits": 128,
    "boundary_condition": "square_open_boundary_no_wrap",
    "initial_state": "checkerboard_Neel_A_up_B_down_Nup32_Ndown32",
    "step_duration": "1/100",
    "trotter_steps": 100,
    "observables": ["staggered_magnetization", "double_occupancy"],
    "attempted_adjacent_transitions": ["3_to_4", "2_to_3"],
}

SCREEN_POLICY = {
    "magnetization_policy_id": "hubbard_l8_magnetization_step4_adaptive_k_v2",
    "magnetization_policy_sha256": SOURCE_PINS[3]["sha256"],
    "double_occupancy_policy_id": "hubbard_l8_double_occupancy_step3_adaptive_k_v2",
    "double_occupancy_policy_sha256": SOURCE_PINS[4]["sha256"],
    "formal_replay_uses_design_transcript_records": False,
    "new_step_arithmetic_kernel_sha256": SOURCE_PINS[1]["sha256"],
    "no_candidate_action": "fail_closed_without_child_boundary_transition_or_depth_increment",
}

SCOPE_CLAIMS = {
    "same_byte_positive_magnetization_step3_parent_chain_verified": True,
    "transitive_same_byte_positive_two_step_parent_chain_verified": True,
    "both_v2_policies_were_committed_before_formal_replay": True,
    "formal_new_step_arithmetic_used_only_the_v2_kernel": True,
    "design_transcript_records_were_not_parsed_or_used_as_result_evidence": True,
    "magnetization_step4_candidate_ceiling_infeasibility_verified": True,
    "double_occupancy_step3_candidate_ceiling_infeasibility_verified": True,
    "magnetization_certified_mapped_depth": 3,
    "double_occupancy_certified_mapped_depth": 2,
    "child_boundary_or_transition_committed": False,
    "remaining_mapped_steps": "NOT_ASSESSED",
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}

EXPECTED = {
    "magnetization": {
        "observable_id": "staggered_magnetization",
        "input_step_index": 3,
        "attempted_child_step_index": 4,
        "policy_id": SCREEN_POLICY["magnetization_policy_id"],
        "policy_sha256": SCREEN_POLICY["magnetization_policy_sha256"],
        "policy_canonical_sha256": "9dc39b20225220439a2bc6d660835a754d8f1d8cdb3744a399087c6349aacb0a",
        "parent_status": M_PARENT_STATUS,
        "parent_depth": 3,
        "completed_checkpoint_count": 28,
        "failure_checkpoint_number_one_based": 29,
        "minimum_effective_K": 333_983,
        "required_K_excess": 6_303,
        "records_sha256": "30c538ed5faee21fe92a547ead1e3e2f1726f9ebebaad6f7fa815b64f36ca6fa",
        "failure_record_sha256": "1a8ec75243bc2e3134c1df4586ebcbbbc4f12b9d5b286d5bb0801f37f5702894",
        "selected_K_history_sha256": "da62d62c4f71baec52aefc94965dccdf185067e98fe54d95ff4361e1dbe465aa",
        "last_committed_cumulative_drop_ticks": "1697274762053234",
        "peak": 397_526,
        "visits": 48_646_721,
        "coefficient_bits": 57,
        "product_bits": 121,
        "rounding": "58214000484856634216120234",
    },
    "double_occupancy": {
        "observable_id": "double_occupancy",
        "input_step_index": 2,
        "attempted_child_step_index": 3,
        "policy_id": SCREEN_POLICY["double_occupancy_policy_id"],
        "policy_sha256": SCREEN_POLICY["double_occupancy_policy_sha256"],
        "policy_canonical_sha256": "f6f216ee8d7d245faeadb4934787b4384a115501f976979fdedbb8514b06a6b4",
        "parent_status": D_PARENT_STATUS,
        "parent_depth": 2,
        "completed_checkpoint_count": 21,
        "failure_checkpoint_number_one_based": 22,
        "minimum_effective_K": 350_604,
        "required_K_excess": 22_924,
        "records_sha256": "504964a8ab8cb0d68ccf203f8c70876bbf21b5bd631d621bdaef8500c479b051",
        "failure_record_sha256": "f3e78409683eb88c21861a0ae4b1029b8247629d458eb836b30edeaeb2e50820",
        "selected_K_history_sha256": "fdcd6561c7174e40fb42d1dda17dc1630cc445057d97ec6094ac27418ab7c8b8",
        "last_committed_cumulative_drop_ticks": "2286550711700036",
        "peak": 501_254,
        "visits": 37_271_764,
        "coefficient_bits": 63,
        "product_bits": 120,
        "rounding": "52895966859009042364436135",
    },
}


class SchemaError(ValueError):
    """Malformed source, JSON, policy, contract, or certificate."""


class VerificationError(ValueError):
    """A well-shaped exact claim disagrees with deterministic recomputation."""


def canonical_sha256(value: Any) -> str:
    try:
        payload = json.dumps(
            value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("value cannot be canonically hashed") from exc
    return hashlib.sha256(payload).hexdigest()


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


def _reject_duplicate_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _reject_nonfinite(value: str) -> Any:
    raise ValueError(f"non-finite JSON constant: {value}")


def strict_json_bytes(payload: bytes, name: str) -> Any:
    if len(payload) > RESOURCE_LIMITS["max_json_bytes"]:
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
    return strict_json_bytes(payload, path.name)


def _self_source_bytes() -> bytes:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _VERIFIED_SELF_SOURCE_BYTES
    with (HERE / SELF_NAME).open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_checker_source_bytes"] + 1)
    if len(payload) > RESOURCE_LIMITS["max_checker_source_bytes"]:
        raise SchemaError("checker source exceeds cap")
    return payload


def _execute_from_verified_self_source(method: str, *arguments: Any) -> Any:
    with (HERE / SELF_NAME).open("rb") as handle:
        payload = handle.read(RESOURCE_LIMITS["max_checker_source_bytes"] + 1)
    if len(payload) > RESOURCE_LIMITS["max_checker_source_bytes"]:
        raise SchemaError("checker source exceeds cap")
    if not arguments or type(arguments[0]) is not dict:
        raise SchemaError("outer self-exec requires an exact contract object")
    checker_pin = arguments[0].get("checker_source_sha256")
    if type(checker_pin) is not str or len(checker_pin) != 64:
        raise SchemaError("outer self-exec requires checker_source_sha256")
    if hashlib.sha256(payload).hexdigest() != checker_pin:
        raise SchemaError("checker source pin mismatch before compile/exec")
    module = types.ModuleType("verified_l8_adaptive_k_v2_dual_screen_checker")
    module.__file__ = str(HERE / SELF_NAME)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    target = getattr(module, method, None)
    if not callable(target):
        raise SchemaError("verified checker source lacks required entry point")
    return target(*arguments)


def _read_pinned_sources() -> Dict[str, bytes]:
    if len(SOURCE_PINS) != RESOURCE_LIMITS["max_dependency_files"]:
        raise VerificationError("dependency count drift")
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


def _compile_module(name: str, filename: str, source: bytes, *, self_bytes: bool = False) -> Any:
    module = types.ModuleType(name)
    module.__file__ = str(HERE / filename)
    module.__package__ = ""
    if self_bytes:
        module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = source
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def _validate_policy(policy: Any, mode: str, probe: Any, sources: Mapping[str, bytes]) -> Mapping[str, Any]:
    expected = EXPECTED[mode]
    item = _exact_keys(
        policy,
        (
            "schema_version", "policy_id", "policy_fingerprint", "policy_role",
            "workload_identity", "precommit_boundary", "immediate_parent",
            "arithmetic_kernel", "design_transcript", "sequence_and_arithmetic",
            "truncation_budget", "candidate_policy", "resource_limits",
            "output_schema_policy", "required_checkpoint_ledger_bindings",
            "forbidden_output_pins", "scope_boundary",
        ),
        f"{mode} policy",
    )
    if item["schema_version"] != 2 or item["policy_id"] != expected["policy_id"]:
        raise VerificationError(f"{mode} policy identity mismatch")
    if canonical_sha256(item) != expected["policy_canonical_sha256"]:
        raise VerificationError(f"{mode} policy canonical semantic digest mismatch")
    boundary = item["precommit_boundary"]
    if (
        boundary.get("formal_v2_attempt_started_before_this_policy_commit") is not False
        or boundary.get("policy_contains_formal_child_output_pins") is not False
        or boundary.get("formal_v2_attempt_must_start_only_after_this_policy_is_committed") is not True
        or boundary.get("policy_does_not_promise_success") is not True
    ):
        raise VerificationError(f"{mode} precommit boundary mismatch")
    kernel = item["arithmetic_kernel"]
    if (
        kernel.get("sha256") != SOURCE_PINS[1]["sha256"]
        or kernel.get("certificate_authority") != "NONE"
        or kernel.get("root_globals_may_be_monkeypatched") is not False
    ):
        raise VerificationError(f"{mode} kernel policy mismatch")
    transcript = item["design_transcript"]
    transcript_name = probe.CONFIG[mode]["output_name"]
    if (
        transcript.get("relative_path") != transcript_name
        or transcript.get("diagnostic_only") is not True
        or transcript.get("formal_checker_must_independently_replay") is not True
        or transcript.get("not_accepted_as_a_certificate_witness_sidecar_or_transition") is not True
        or hashlib.sha256(sources[transcript_name]).hexdigest() != transcript.get("sha256")
    ):
        raise VerificationError(f"{mode} design provenance mismatch")
    candidates = item["candidate_policy"]["candidate_K_values_in_strict_ascending_order"]
    if candidates != list(probe.CONFIG[mode]["candidates"]):
        raise VerificationError(f"{mode} candidate ladder mismatch")
    if canonical_sha256(candidates) != item["candidate_policy"]["candidate_K_values_sha256"]:
        raise VerificationError(f"{mode} candidate digest mismatch")
    caps = dict(probe.POLICY_CAPS_BASE)
    caps["max_candidate_count"] = len(candidates)
    limits = item["resource_limits"]
    for key, value in caps.items():
        policy_key = {
            "max_output_terms_if_successful": "max_output_sidecar_terms_if_successful"
        }.get(key, key)
        if limits.get(policy_key) != value:
            raise VerificationError(f"{mode} policy cap mismatch: {policy_key}")
    budget = item["truncation_budget"]
    E_input = probe.CONFIG[mode]["input_cumulative_drop_ticks"]
    remaining = 100 - probe.CONFIG[mode]["input_step_index"]
    B = probe.MAXIMUM_DROP_TICKS
    denominator = remaining * 144
    if (
        budget.get("input_cumulative_drop_ticks") != E_input
        or budget.get("maximum_cumulative_drop_ticks") != B
        or budget.get("remaining_checkpoint_count") != denominator
        or budget.get("child_final_prefix_cap_ticks")
        != E_input + 144 * (B - E_input) // denominator
    ):
        raise VerificationError(f"{mode} budget mismatch")
    parent = item["immediate_parent"]
    parent_names = {
        "magnetization": SOURCE_PINS[7:10],
        "double_occupancy": SOURCE_PINS[10:13],
    }[mode]
    for key, pin in zip(
        ("checker_sha256", "contract_sha256", "certificate_sha256"), parent_names
    ):
        if parent.get(key) != pin["sha256"]:
            raise VerificationError(f"{mode} immediate parent pin mismatch: {key}")
    if parent.get("required_positive_status") != expected["parent_status"]:
        raise VerificationError(f"{mode} parent status mismatch")
    if parent.get("required_certified_depth") != expected["parent_depth"]:
        raise VerificationError(f"{mode} parent depth mismatch")
    cfg = probe.CONFIG[mode]
    boundary = parent.get("boundary")
    if type(boundary) is not dict:
        raise VerificationError(f"{mode} input boundary policy is malformed")
    boundary_expected = {
        "state_sha256": cfg["input_state_sha256"],
        "expansion_sha256": cfg["input_expansion_sha256"],
        "cumulative_dropped_l1_ticks": cfg["input_cumulative_drop_ticks"],
        "input_transition_sha256": cfg["input_transition_sha256"],
        "previous_transition_recorded_inside_state_sha256": cfg[
            "state_previous_transition_sha256"
        ],
    }
    if any(boundary.get(key) != value for key, value in boundary_expected.items()):
        raise VerificationError(f"{mode} input boundary ancestry mismatch")
    if item["scope_boundary"].get("policy_itself_has_no_child_transition_authority") is not True:
        raise VerificationError(f"{mode} policy authority scope mismatch")
    return item


def _verify_parent_chain(sources: Mapping[str, bytes], policies: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    checker_name = SOURCE_PINS[7]["relative_path"]
    parent = _compile_module(
        "pinned_magnetization_step3_parent_for_v2_dual_screen",
        checker_name,
        sources[checker_name],
        self_bytes=True,
    )
    contract = strict_json_bytes(
        sources[SOURCE_PINS[8]["relative_path"]], "magnetization step3 parent contract"
    )
    certificate = strict_json_bytes(
        sources[SOURCE_PINS[9]["relative_path"]], "magnetization step3 parent certificate"
    )
    result = parent.verify_certificate(contract, certificate)
    if result.get("status") != M_PARENT_STATUS or result.get("verified") is not True:
        raise VerificationError("same-byte magnetization step3 parent is not positive")
    witness = result.get("recomputed_witness")
    if type(witness) is not dict or not _strict_equal(witness, certificate.get("witness_claim")):
        raise VerificationError("magnetization step3 parent witness mismatch")
    if canonical_sha256(witness) != contract.get("expected_witness_sha256"):
        raise VerificationError("magnetization step3 expected-witness mismatch")
    if contract.get("expected_witness_sha256") != policies["magnetization"]["immediate_parent"]["expected_witness_sha256"]:
        raise VerificationError("magnetization parent policy witness mismatch")
    m_boundary = policies["magnetization"]["immediate_parent"]["boundary"]
    m_output_expected = {
        "output_state_sha256": m_boundary["state_sha256"],
        "output_expansion_sha256": m_boundary["expansion_sha256"],
        "output_cumulative_dropped_l1_ticks": str(
            m_boundary["cumulative_dropped_l1_ticks"]
        ),
        "transition_sha256": m_boundary["input_transition_sha256"],
    }
    if any(witness.get(key) != value for key, value in m_output_expected.items()):
        raise VerificationError("magnetization input boundary disagrees with positive parent")
    immediate = witness.get("immediate_parent")
    d_parent = policies["double_occupancy"]["immediate_parent"]
    if (
        type(immediate) is not dict
        or immediate.get("verified") is not True
        or immediate.get("status") != D_PARENT_STATUS
        or immediate.get("checker_source_sha256") != d_parent["checker_sha256"]
        or immediate.get("contract_sha256") != d_parent["contract_sha256"]
        or immediate.get("certificate_sha256") != d_parent["certificate_sha256"]
        or immediate.get("expected_witness_sha256") != d_parent["expected_witness_sha256"]
    ):
        raise VerificationError("transitive same-byte two-step parent custody mismatch")
    d_contract = strict_json_bytes(
        sources[SOURCE_PINS[11]["relative_path"]], "two-step parent contract"
    )
    d_certificate = strict_json_bytes(
        sources[SOURCE_PINS[12]["relative_path"]], "two-step parent certificate"
    )
    if (
        d_contract.get("expected_witness_sha256") != d_parent["expected_witness_sha256"]
        or canonical_sha256(d_certificate.get("witness_claim"))
        != d_parent["expected_witness_sha256"]
    ):
        raise VerificationError("two-step parent stored witness custody mismatch")
    d_claims = [
        claim for claim in d_certificate["witness_claim"].get("child_witnesses", [])
        if type(claim) is dict and claim.get("observable_id") == "double_occupancy"
    ]
    if len(d_claims) != 1:
        raise VerificationError("two-step parent double-occupancy claim is not unique")
    d_boundary = d_parent["boundary"]
    d_output_expected = {
        "output_state_sha256": d_boundary["state_sha256"],
        "output_expansion_sha256": d_boundary["expansion_sha256"],
        "output_cumulative_dropped_l1_ticks": str(
            d_boundary["cumulative_dropped_l1_ticks"]
        ),
        "transition_sha256": d_boundary["input_transition_sha256"],
    }
    if any(d_claims[0].get(key) != value for key, value in d_output_expected.items()):
        raise VerificationError("double-occupancy input boundary disagrees with positive parent")
    return {
        "same_byte_magnetization_step3_status": result["status"],
        "magnetization_step3_expected_witness_sha256": contract["expected_witness_sha256"],
        "transitive_same_byte_two_step_status": immediate["status"],
        "two_step_expected_witness_sha256": immediate["expected_witness_sha256"],
        "two_step_execution_verified_inside_step3_parent": True,
    }


def _validate_formal_records(
    mode: str,
    formal: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> Tuple[Mapping[str, Any], Sequence[Mapping[str, Any]]]:
    expected = EXPECTED[mode]
    records = formal.get("records")
    if type(records) is not list or len(records) != expected["completed_checkpoint_count"] + 1:
        raise VerificationError(f"{mode} formal replay record count mismatch")
    if canonical_sha256(records) != expected["records_sha256"]:
        raise VerificationError(f"{mode} formal records digest mismatch")
    failure = records[-1]
    if canonical_sha256(failure) != expected["failure_record_sha256"]:
        raise VerificationError(f"{mode} formal failure digest mismatch")
    history = formal.get("selected_K_history")
    if type(history) is not list or canonical_sha256(history) != expected[
        "selected_K_history_sha256"
    ]:
        raise VerificationError(f"{mode} selected-K history digest mismatch")
    candidates = policy["candidate_policy"]["candidate_K_values_in_strict_ascending_order"]
    budget = policy["truncation_budget"]
    E_input = budget["input_cumulative_drop_ticks"]
    B = budget["maximum_cumulative_drop_ticks"]
    denominator = budget["remaining_checkpoint_count"]
    cumulative = E_input
    observed_history = []
    for checkpoint_number, record in enumerate(records, 1):
        if (
            type(record) is not dict
            or record.get("checkpoint_number_one_based") != checkpoint_number
            or record.get("checkpoint_index_zero_based") != checkpoint_number - 1
        ):
            raise VerificationError(f"{mode} checkpoint index mismatch")
        cap = E_input + checkpoint_number * (B - E_input) // denominator
        if (
            record.get("budget_prefix_cap_ticks") != str(cap)
            or record.get("E_before_ticks") != str(cumulative)
            or record.get("prefix_slack_before_selection_ticks") != str(cap - cumulative)
        ):
            raise VerificationError(f"{mode} checkpoint budget recurrence mismatch")
        candidate_records = record.get("candidate_records")
        if type(candidate_records) is not list or len(candidate_records) != len(candidates):
            raise VerificationError(f"{mode} checkpoint candidate count mismatch")
        feasible_indices = []
        for index, (configured_K, candidate) in enumerate(zip(candidates, candidate_records)):
            if type(candidate) is not dict:
                raise VerificationError(f"{mode} candidate record is malformed")
            drop = int(candidate.get("drop_ticks"))
            feasible = cumulative + drop <= cap
            if (
                candidate.get("candidate_index") != index
                or candidate.get("configured_K") != configured_K
                or candidate.get("effective_retained_count")
                != min(configured_K, record["pretruncation_expansion_count"])
                or candidate.get("E_after_if_selected_ticks") != str(cumulative + drop)
                or candidate.get("feasible_under_current_prefix_cap") is not feasible
            ):
                raise VerificationError(f"{mode} candidate feasibility mismatch")
            if feasible:
                feasible_indices.append(index)
        if checkpoint_number <= expected["completed_checkpoint_count"]:
            if not feasible_indices:
                raise VerificationError(f"{mode} committed checkpoint has no feasible K")
            selected_index = feasible_indices[0]
            selected = candidate_records[selected_index]
            selected_drop = int(selected["drop_ticks"])
            if (
                record.get("status") != "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
                or record.get("selected_candidate_index") != selected_index
                or record.get("selected_K") != candidates[selected_index]
                or record.get("selected_drop_ticks") != str(selected_drop)
                or record.get("E_after_ticks") != str(cumulative + selected_drop)
            ):
                raise VerificationError(f"{mode} first-feasible commit mismatch")
            cumulative += selected_drop
            observed_history.append(candidates[selected_index])
        else:
            if (
                feasible_indices
                or record.get("status") != "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
                or record.get("selected_candidate_index") is not None
                or record.get("selected_K") is not None
            ):
                raise VerificationError(f"{mode} terminal no-candidate result mismatch")
    if observed_history != history or str(cumulative) != formal.get(
        "last_committed_cumulative_drop_ticks"
    ):
        raise VerificationError(f"{mode} selected history or cumulative drop mismatch")
    return failure, failure["candidate_records"]


def _route_witness(mode: str, formal: Mapping[str, Any], policy: Mapping[str, Any]) -> Dict[str, Any]:
    expected = EXPECTED[mode]
    failure, candidate_records = _validate_formal_records(mode, formal, policy)
    checks = {
        "observable_id": formal.get("observable_id"),
        "input_step_index": formal.get("input_step_index"),
        "attempted_child_step_index": formal.get("attempted_child_step_index"),
        "completed_checkpoint_count": formal.get("completed_checkpoint_count"),
        "failure_checkpoint_number_one_based": failure.get("checkpoint_number_one_based"),
        "minimum_effective_K": failure.get("minimum_effective_K_to_meet_prefix"),
        "required_K_excess": failure.get("required_K_excess_over_policy_maximum"),
        "records_sha256": formal.get("records_sha256"),
        "failure_record_sha256": formal.get("failure_record_sha256"),
        "selected_K_history_sha256": formal.get("selected_K_history_sha256"),
        "last_committed_cumulative_drop_ticks": formal.get("last_committed_cumulative_drop_ticks"),
        "peak": formal.get("observed_peak_single_expansion_terms"),
        "visits": formal.get("observed_term_gate_visits_including_failure"),
        "coefficient_bits": formal.get("observed_maximum_expansion_coefficient_tick_bits"),
        "product_bits": formal.get("observed_maximum_product_bits"),
        "rounding": formal.get("observed_rounding_cumulative_scaled_ticks_squared"),
    }
    for key, observed in checks.items():
        if observed != expected[key]:
            raise VerificationError(f"{mode} formal exact result mismatch: {key}")
    if (
        failure.get("status") != "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        or formal.get("failure_checkpoint_included") is not True
        or formal.get("root_globals_unchanged") is not True
        or formal.get("child_boundary_committed") is not False
        or formal.get("positive_artifact_generated") is not False
    ):
        raise VerificationError(f"{mode} fail-closed result mismatch")
    candidates = policy["candidate_policy"]["candidate_K_values_in_strict_ascending_order"]
    if any(record.get("feasible_under_current_prefix_cap") is not False for record in candidate_records):
        raise VerificationError(f"{mode} failure contains a feasible candidate")
    return {
        "screen_status": "VERIFIED_POLICY_MAX_K_INFEASIBILITY",
        "observable_id": expected["observable_id"],
        "input_step_index": expected["input_step_index"],
        "attempted_child_step_index": expected["attempted_child_step_index"],
        "certified_mapped_depth_after_screen": expected["parent_depth"],
        "parent_positive_status": expected["parent_status"],
        "policy_id": expected["policy_id"],
        "policy_sha256": expected["policy_sha256"],
        "configured_candidate_count": len(candidates),
        "configured_maximum_K": candidates[-1],
        "completed_checkpoint_count": expected["completed_checkpoint_count"],
        "failure_checkpoint_number_one_based": expected["failure_checkpoint_number_one_based"],
        "failure_pretruncation_expansion_count": failure["pretruncation_expansion_count"],
        "failure_budget_prefix_cap_ticks": failure["budget_prefix_cap_ticks"],
        "failure_E_before_ticks": failure["E_before_ticks"],
        "failure_prefix_slack_ticks": failure["prefix_slack_before_selection_ticks"],
        "failure_policy_max_K_candidate_drop_ticks": candidate_records[-1]["drop_ticks"],
        "failure_maximum_candidate_drop_excess_over_slack_ticks": failure[
            "maximum_candidate_drop_excess_over_slack_ticks"
        ],
        "minimum_effective_K_to_meet_prefix": expected["minimum_effective_K"],
        "required_K_excess_over_policy_maximum": expected["required_K_excess"],
        "selected_K_history": formal["selected_K_history"],
        "selected_K_history_sha256": expected["selected_K_history_sha256"],
        "checkpoint_ledger_sha256": expected["records_sha256"],
        "failure_record_sha256": expected["failure_record_sha256"],
        "last_committed_cumulative_drop_ticks": expected[
            "last_committed_cumulative_drop_ticks"
        ],
        "resource_summary": {
            "peak_single_expansion_terms": expected["peak"],
            "term_gate_visits_including_failure": expected["visits"],
            "maximum_expansion_coefficient_tick_bits": expected["coefficient_bits"],
            "maximum_product_bits": expected["product_bits"],
            "rounding_cumulative_scaled_ticks_squared": expected["rounding"],
        },
        "failure_candidate_evaluations": candidate_records,
        "root_arithmetic_globals_unchanged": True,
        "design_transcript_records_used_as_result_input": False,
        "child_boundary_committed": False,
        "child_transition_committed": False,
        "positive_child_artifact_generated": False,
    }


def _install_verified_replay_loader(probe: Any, sources: Mapping[str, bytes]) -> None:
    """Make probe.run execute the exact dependency bytes verified by this checker."""

    module_sources = {
        "hubbard_l8_adaptive_k_arithmetic_v2.py": SOURCE_PINS[1],
        "hubbard_l8_observable_interval_step_checker.py": SOURCE_PINS[2],
        "hubbard_l8_magnetization_interval_step3_checker.py": SOURCE_PINS[7],
        "hubbard_l8_observable_interval_two_step_checker.py": SOURCE_PINS[10],
    }
    verified_modules = {
        filename: _compile_module(
            "verified_dual_screen_" + filename.replace(".", "_"),
            filename,
            sources[pin["relative_path"]],
            self_bytes=filename.endswith("_checker.py"),
        )
        for filename, pin in module_sources.items()
    }

    verified_parent = HERE.resolve()

    def verified_load_module(name: str, path: Path) -> Any:
        del name
        if not isinstance(path, Path) or path.resolve().parent != verified_parent:
            raise SchemaError("formal replay module path escapes the verified repository")
        filename = path.name
        if filename not in verified_modules:
            raise SchemaError(f"formal replay attempted an unverified module load: {filename}")
        return verified_modules[filename]

    probe.load_module = verified_load_module


def recompute_witness() -> Dict[str, Any]:
    sources = _read_pinned_sources()
    probe = _compile_module(
        "pinned_l8_adaptive_k_v2_formal_replay_driver",
        SOURCE_PINS[0]["relative_path"],
        sources[SOURCE_PINS[0]["relative_path"]],
    )
    if probe.EXPECTED_KERNEL_SHA256 != SOURCE_PINS[1]["sha256"]:
        raise VerificationError("formal replay driver kernel pin mismatch")
    _install_verified_replay_loader(probe, sources)
    policies = {
        "magnetization": _validate_policy(
            strict_json_bytes(sources[SOURCE_PINS[3]["relative_path"]], "magnetization v2 policy"),
            "magnetization", probe, sources,
        ),
        "double_occupancy": _validate_policy(
            strict_json_bytes(sources[SOURCE_PINS[4]["relative_path"]], "double occupancy v2 policy"),
            "double_occupancy", probe, sources,
        ),
    }
    parent_chain = _verify_parent_chain(sources, policies)
    route_results = []
    for mode in ("magnetization", "double_occupancy"):
        formal = probe.run(HERE, mode)
        route_results.append(_route_witness(mode, formal, policies[mode]))
    if len(route_results) != RESOURCE_LIMITS["max_witness_records"]:
        raise VerificationError("dual screen result count mismatch")
    return {
        "checker_fingerprint": CHECKER_FINGERPRINT,
        "parent_chain": parent_chain,
        "policy_precommit": {
            "magnetization_policy_sha256": SOURCE_PINS[3]["sha256"],
            "double_occupancy_policy_sha256": SOURCE_PINS[4]["sha256"],
            "policies_committed_before_formal_replay": True,
            "formal_output_pins_absent_from_policies": True,
        },
        "arithmetic_custody": {
            "v2_kernel_sha256": SOURCE_PINS[1]["sha256"],
            "replay_driver_sha256": SOURCE_PINS[0]["sha256"],
            "root_new_step_arithmetic_helpers_used": False,
            "root_globals_monkeypatched": False,
            "design_transcript_records_parsed_or_used_as_result_input": False,
        },
        "screen_results": route_results,
        "decision": {
            "both_candidate_ceiling_infeasibility_screens_verified": True,
            "magnetization_certified_mapped_depth": 3,
            "double_occupancy_certified_mapped_depth": 2,
            "child_boundary_transition_or_sidecar_generated": False,
            "remaining_R100_steps_exact_Hubbard_error_reference_and_READY": "NOT_ASSESSED",
        },
    }


def _validate_contract(contract: Any, self_sha256: str) -> Mapping[str, Any]:
    item = _exact_keys(
        contract,
        (
            "schema_version", "contract_fingerprint", "checker_relative_path",
            "checker_source_sha256", "expected_witness_sha256",
            "maximum_positive_status", "source_pins", "workload_identity",
            "screen_policy", "scope_claims",
        ),
        "dual screen contract",
    )
    if item["schema_version"] != 1 or item["contract_fingerprint"] != CONTRACT_FINGERPRINT:
        raise SchemaError("contract identity mismatch")
    if item["checker_relative_path"] != SELF_NAME or item["checker_source_sha256"] != self_sha256:
        raise SchemaError("contract checker source pin mismatch")
    if item["maximum_positive_status"] != MAXIMUM_POSITIVE_STATUS:
        raise SchemaError("contract maximum status mismatch")
    for key, expected in (
        ("source_pins", list(SOURCE_PINS)),
        ("workload_identity", WORKLOAD_IDENTITY),
        ("screen_policy", SCREEN_POLICY),
        ("scope_claims", SCOPE_CLAIMS),
    ):
        if not _strict_equal(item[key], expected):
            raise SchemaError(f"contract {key} mismatch")
    expected_witness = item["expected_witness_sha256"]
    if type(expected_witness) is not str or len(expected_witness) != 64:
        raise SchemaError("contract expected witness sha256 is unresolved")
    return item


def _verify_certificate_impl(contract: Any, certificate: Any) -> Dict[str, Any]:
    self_sha = hashlib.sha256(_self_source_bytes()).hexdigest()
    contract_item = _validate_contract(contract, self_sha)
    item = _exact_keys(
        certificate,
        (
            "schema_version", "certificate_type", "contract_fingerprint",
            "workload_identity", "screen_policy", "scope_claims", "witness_claim",
        ),
        "dual screen certificate",
    )
    if (
        item["schema_version"] != 1
        or item["certificate_type"] != CERTIFICATE_TYPE
        or item["contract_fingerprint"] != CONTRACT_FINGERPRINT
    ):
        raise SchemaError("certificate identity mismatch")
    for key, expected in (
        ("workload_identity", WORKLOAD_IDENTITY),
        ("screen_policy", SCREEN_POLICY),
        ("scope_claims", SCOPE_CLAIMS),
    ):
        if not _strict_equal(item[key], expected):
            raise SchemaError(f"certificate {key} mismatch")
    recomputed = recompute_witness()
    if not _strict_equal(item["witness_claim"], recomputed):
        raise VerificationError("certificate witness disagrees with formal replay")
    witness_sha = canonical_sha256(recomputed)
    if witness_sha != contract_item["expected_witness_sha256"]:
        raise VerificationError("formal witness digest disagrees with contract")
    return {
        "status": MAXIMUM_POSITIVE_STATUS,
        "verified": True,
        "checker_source_sha256": self_sha,
        "expected_witness_sha256": witness_sha,
        "recomputed_witness": recomputed,
        "scope_claims": dict(SCOPE_CLAIMS),
    }


def verify_certificate(contract: Any, certificate: Any) -> Dict[str, Any]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _verify_certificate_impl(contract, certificate)
    return _execute_from_verified_self_source(
        "_verify_certificate_impl", contract, certificate
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=HERE / CONTRACT_NAME)
    parser.add_argument("--certificate", type=Path, default=HERE / CERTIFICATE_NAME)
    args = parser.parse_args(argv)
    try:
        result = verify_certificate(
            load_strict_json(args.contract), load_strict_json(args.certificate)
        )
    except (
        OSError,
        SchemaError,
        VerificationError,
        RuntimeError,
        KeyError,
        TypeError,
        ValueError,
        RecursionError,
    ) as exc:
        print(json.dumps({"status": "FAILED", "verified": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, allow_nan=False, ensure_ascii=True, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
