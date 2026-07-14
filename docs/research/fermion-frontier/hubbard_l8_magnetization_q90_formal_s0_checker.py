#!/usr/bin/env python3
"""Two-commit formal replication checker for the M q90 fixed-policy screen.

The precommit phase validates an outcome-unpinned policy and checker.  A fresh
replay is then allowed only while HEAD is exactly that clean precommit commit.
The replay runs in a new 13-file allowlist tree that excludes every q90 result
artifact.  The old diagnostic q90 canonical is never read by this checker.

Only the branch in which q89 commits and all 34 q90 candidates are infeasible
has narrow negative authority.  Resource aborts are indeterminate; reaching the
q90 horizon does not create M4, a child boundary, or READY authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


if "_VERIFIED_SELF_SOURCE_BYTES" not in globals():
    _VERIFIED_SELF_SOURCE_BYTES: bytes | None = None

HERE = Path(__file__).resolve().parent
SELF_NAME = "hubbard_l8_magnetization_q90_formal_s0_checker.py"
POLICY_NAME = "hubbard_l8_magnetization_q90_formal_s0_policy.json"
PRECOMMIT_CONTRACT_NAME = (
    "hubbard_l8_magnetization_q90_formal_s0_precommit_contract.json"
)
FINAL_CONTRACT_NAME = "hubbard_l8_magnetization_q90_formal_s0_contract.json"
CERTIFICATE_NAME = "hubbard_l8_magnetization_q90_formal_s0_certificate.json"
POSTRUN_TEST_NAME = "test_hubbard_l8_magnetization_q90_formal_s0_result.py"

POLICY_FILE_SHA256 = (
    "8084ab612c6d3cefb8f779d4dfe24450cb5c7d612d14b485feabb7044ae7cab5"
)
POLICY_CANONICAL_SHA256 = (
    "c9c12105893b3b8ede1e3f55189631273771e09b1817863d65ce97cf6e308bbd"
)
POLICY_ID = "M-Q90-FORMAL-S0"
PRECOMMIT_CONTRACT_FINGERPRINT = (
    "hubbard_l8_magnetization_q90_formal_s0_precommit_v1"
)
FINAL_CONTRACT_FINGERPRINT = "hubbard_l8_magnetization_q90_formal_s0_contract_v1"
CHECKER_FINGERPRINT = "hubbard_l8_magnetization_q90_formal_s0_checker_v1"
CERTIFICATE_TYPE = "l8_magnetization_q90_fixed_policy_replication_v1"
MAXIMUM_POSITIVE_STATUS = (
    "VERIFIED_M_Q90_FIXED_POLICY_MAX_K_INFEASIBILITY_REPLICATION"
)

SUCCESS_STATUS = "DIAGNOSTIC_FIRST_FEASIBLE_SELECTED"
FAILURE_STATUS = "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
DIAGNOSTIC_STATUS = "DIAGNOSTIC_ONLY_NOT_A_CERTIFICATE_WITNESS"

LEGAL_BRANCHES = (
    "Q89_FAILURE_Q90_NOT_ATTEMPTED",
    "Q89_RESOURCE_ABORT_Q90_NOT_ATTEMPTED",
    "Q89_SUCCESS_Q90_FAILURE",
    "Q89_SUCCESS_Q90_RESOURCE_ABORT",
    "Q89_AND_Q90_SUCCESS_HORIZON_REACHED",
)

BRANCH_DECISIONS = {
    "Q89_FAILURE_Q90_NOT_ATTEMPTED": {
        "status": "VERIFIED_M_Q89_FIXED_POLICY_FAILURE_NO_Q90_AUTHORITY",
        "authority": "earlier_fixed_policy_failure_only_no_q90_inference",
        "scientific_negative_authority": False,
    },
    "Q89_RESOURCE_ABORT_Q90_NOT_ATTEMPTED": {
        "status": "INDETERMINATE_M_Q89_RESOURCE_ABORT",
        "authority": "indeterminate_resource_abort_no_infeasibility_inference",
        "scientific_negative_authority": False,
    },
    "Q89_SUCCESS_Q90_FAILURE": {
        "status": MAXIMUM_POSITIVE_STATUS,
        "authority": (
            "narrow_q90_fixed_policy_candidate_ceiling_infeasibility_replication"
        ),
        "scientific_negative_authority": True,
    },
    "Q89_SUCCESS_Q90_RESOURCE_ABORT": {
        "status": "INDETERMINATE_M_Q90_RESOURCE_ABORT",
        "authority": "indeterminate_resource_abort_no_infeasibility_inference",
        "scientific_negative_authority": False,
    },
    "Q89_AND_Q90_SUCCESS_HORIZON_REACHED": {
        "status": "VERIFIED_M_Q90_BOUNDED_HORIZON_PASS_NO_M4_AUTHORITY",
        "authority": "bounded_horizon_passed_without_M4_or_child_authority",
        "scientific_negative_authority": False,
    },
}

SOURCE_PIN_FACTS = (
    (
        "hubbard_l8_magnetization_adaptive_k_four_gate_k622592_c34_q90_screen.py",
        "f880e851bb16df5e659d7c0e6aa237d1836b17b4ad010d5676557ade2ba9140a",
        89_527,
    ),
    (
        "hubbard_l8_magnetization_adaptive_k_four_gate_k622592_c34_q88_screen.py",
        "6867dda2d6bd34ab2eed6b31d02a587e16762263a493e9890d0caa40f23a58a4",
        78_218,
    ),
    (
        "hubbard_l8_adaptive_k_four_gate_granularity_screen.py",
        "b483d9555a24dd07ea96292ed0a7ed51587259a79a2c5d69e3a8bf1408b4a614",
        35_616,
    ),
    (
        "hubbard_l8_magnetization_adaptive_k_four_gate_k622592_c34_q88_transcript.json",
        "0074b1eea5fa574378d5a9fae9e748e7145efaa0c96b622ddf50587a72a2551a",
        821_781,
    ),
    (
        "hubbard_l8_adaptive_k_v6_design_probe.py",
        "3e7f9ff0546addfaa23f351f3569b102d0c3ebb578dbc4873b042bac21070af2",
        26_538,
    ),
    (
        "hubbard_l8_adaptive_k_v2_design_probe.py",
        "01582da649f7df2a0e65dcf8ed251a341b72218eade72dcd3d69ffa627fe1ee3",
        25_517,
    ),
    (
        "hubbard_l8_adaptive_k_arithmetic_v2.py",
        "f4819f96bf92ac07a9ce5d0be646c8d187b04f37a64c7dccda68f665722d5998",
        23_931,
    ),
    (
        "hubbard_l8_adaptive_k_arithmetic_k622592_c34.py",
        "f4e676da40535903301181cf482119e051066b90921793e34152403b3b74b976",
        21_957,
    ),
    (
        "hubbard_l8_observable_interval_step_checker.py",
        "5c151a63cee86d362851629aae743600dd61fcfd534339376aca88fe030b1f1a",
        65_080,
    ),
    (
        "hubbard_l8_magnetization_interval_step3_checker.py",
        "4e471b6f22838b2e9621adeeb757e7fa8277e3d8c4985eee392b182530c0c717",
        56_874,
    ),
    (
        "hubbard_l8_magnetization_interval_step3_contract.json",
        "fb1d5e82819d39f217a8c1c7f4979a689f4d46b8d691a8f464cad9012c197387",
        6_930,
    ),
    (
        "hubbard_l8_magnetization_interval_step3_template.json",
        "b68544091be417eed5310d8579eb8dc4d1a51e1863ed1fb7a8cbfa1fc6004eb6",
        13_822,
    ),
    (
        "hubbard_l8_interval_checkpoints/staggered_magnetization_boundary_003.b85",
        "91aecef5a3b79279e394c8995072d19565f4898e0ba29ddd7685ea9e535d9c84",
        805_953,
    ),
)

RESOURCE_LIMITS = {
    "max_checker_source_bytes": 262_144,
    "max_json_bytes": 4_194_304,
    "max_pinned_file_bytes": 1_048_576,
    "max_staging_files": 13,
    "max_staging_total_bytes": 4_194_304,
    "max_replay_package_bytes": 8_388_608,
}

RESULT_ARTIFACTS = (FINAL_CONTRACT_NAME, CERTIFICATE_NAME, POSTRUN_TEST_NAME)

SCOPE_CEILING = {
    "retrospective_replication_only": True,
    "prospective_discovery_authority": False,
    "maximum_negative_authority": (
        "fixed_M3_input_four_gate_q1_to_q90_K_at_most_622592_C34_policy_only"
    ),
    "larger_K_other_cadences_and_other_algorithms": "NOT_ASSESSED",
    "certified_mapped_depth_before_and_after": 3,
    "M4_certification_allowed": False,
    "child_boundary_transition_or_sidecar_allowed": False,
    "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
    "physical_reference_qualified": False,
    "ready_gate_eligible": False,
}

CANDIDATE_RECORD_KEYS = frozenset({
    "candidate_index",
    "configured_K",
    "effective_retained_count",
    "dropped_term_count",
    "drop_ticks",
    "E_after_if_selected_ticks",
    "feasible_under_current_prefix_cap",
})


class SchemaError(ValueError):
    """Malformed JSON, policy, contract, certificate, or source closure."""


class VerificationError(ValueError):
    """A well-shaped object disagrees with deterministic verification."""


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SchemaError("value cannot be canonically encoded") from exc


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _strict_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            _strict_equal(left[key], right[key]) for key in left
        )
    if type(left) is list:
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
    if type(payload) is not bytes or len(payload) > RESOURCE_LIMITS["max_json_bytes"]:
        raise SchemaError(f"{name} exceeds the strict JSON byte cap")
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


def _regular_file_bytes(path: Path, maximum: int) -> bytes:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise SchemaError(f"required source is not a non-symlink regular file: {path}")
    with path.open("rb") as handle:
        payload = handle.read(maximum + 1)
    if len(payload) > maximum:
        raise SchemaError(f"source exceeds byte cap: {path.name}")
    return payload


def _self_source_bytes() -> bytes:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _VERIFIED_SELF_SOURCE_BYTES
    return _regular_file_bytes(HERE / SELF_NAME, RESOURCE_LIMITS["max_checker_source_bytes"])


def _execute_from_verified_self_source(method: str, *arguments: Any) -> Any:
    payload = _regular_file_bytes(
        HERE / SELF_NAME, RESOURCE_LIMITS["max_checker_source_bytes"]
    )
    if not arguments or type(arguments[0]) is not dict:
        raise SchemaError("verified self-execution requires a contract object")
    checker_pin = arguments[0].get("checker_source_sha256")
    if not _is_sha256(checker_pin):
        raise SchemaError("contract has no resolved checker source pin")
    if hashlib.sha256(payload).hexdigest() != checker_pin:
        raise SchemaError("checker source pin mismatch before compile/exec")
    module = types.ModuleType("verified_m_q90_formal_s0_checker")
    module.__file__ = str(HERE / SELF_NAME)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    target = getattr(module, method, None)
    if not callable(target):
        raise SchemaError("verified checker source lacks the requested entry point")
    return target(*arguments)


def _is_sha256(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _decimal(value: Any, name: str) -> int:
    if type(value) is not str or not value or not value.isdigit():
        raise SchemaError(f"{name} is not a canonical nonnegative decimal string")
    if len(value) > 1 and value[0] == "0":
        raise SchemaError(f"{name} has a redundant leading zero")
    return int(value)


def _validate_policy(policy: Any) -> Mapping[str, Any]:
    item = _exact_keys(
        policy,
        (
            "candidate_policy",
            "execution_engine",
            "forbidden_formal_result_pins",
            "historical_disclosure",
            "isolation_policy",
            "legal_terminal_branches",
            "operational_observation_policy",
            "parent_authority",
            "policy_fingerprint",
            "policy_id",
            "policy_role",
            "precommit_boundary",
            "resource_policy",
            "schema_version",
            "scope_boundary",
            "sequence_and_budget",
            "source_pins",
            "workload_identity",
            "wrapped_kernel_capability",
        ),
        "M q90 formal S0 policy",
    )
    if (
        item["schema_version"] != 1
        or item["policy_id"] != POLICY_ID
        or canonical_sha256(item) != POLICY_CANONICAL_SHA256
    ):
        raise VerificationError("policy identity or canonical semantic digest mismatch")

    expected_facts = [
        {"relative_path": path, "sha256": digest, "size_bytes": size}
        for path, digest, size in SOURCE_PIN_FACTS
    ]
    pins = item["source_pins"]
    if type(pins) is not list or len(pins) != RESOURCE_LIMITS["max_staging_files"]:
        raise VerificationError("policy source-pin cardinality mismatch")
    observed_facts = [
        {
            "relative_path": pin.get("relative_path") if type(pin) is dict else None,
            "sha256": pin.get("sha256") if type(pin) is dict else None,
            "size_bytes": pin.get("size_bytes") if type(pin) is dict else None,
        }
        for pin in pins
    ]
    if not _strict_equal(observed_facts, expected_facts):
        raise VerificationError("policy source-pin facts mismatch")
    if any(type(pin.get("role")) is not str or not pin["role"] for pin in pins):
        raise VerificationError("policy source-pin role is missing")
    paths = [pin["relative_path"] for pin in pins]
    if len(paths) != len(set(paths)) or any(Path(path).is_absolute() for path in paths):
        raise VerificationError("policy source paths are not unique relative paths")
    if any("_q90_transcript.json" in path or "_c33_" in path for path in paths):
        raise VerificationError("forbidden outcome or predecessor file entered source pins")

    candidates = item["candidate_policy"]
    expected_candidates = list(range(81_920, 622_592 + 1, 16_384))
    if (
        candidates.get("candidate_K_values_in_strict_ascending_order")
        != expected_candidates
        or candidates.get("configured_candidate_count") != 34
        or candidates.get("configured_maximum_K") != 622_592
        or canonical_sha256(expected_candidates)
        != candidates.get("candidate_K_values_sha256")
        or candidates.get("single_propagation_and_single_ranking_per_checkpoint")
        is not True
        or candidates.get("Neel_expectation_is_forbidden_as_a_K_selection_input")
        is not True
    ):
        raise VerificationError("candidate policy mismatch")

    budget = item["sequence_and_budget"]
    E3 = _decimal(budget.get("input_cumulative_drop_ticks"), "policy E3")
    B = _decimal(budget.get("maximum_cumulative_drop_ticks"), "policy B")
    denominator = budget.get("total_future_checkpoint_denominator")
    horizon = budget.get("horizon_checkpoint_count")
    if type(denominator) is not int or type(horizon) is not int:
        raise VerificationError("budget denominator or horizon has non-integer type")
    if (
        denominator != 97 * 288
        or horizon != 90
        or budget.get("four_gate_checkpoints_per_mapped_step") != 288
        or budget.get("four_gate_gates_per_checkpoint") != 4
        or budget.get("physical_gate_count_per_mapped_step") != 1152
        or budget.get("horizon_prefix_cap_ticks")
        != str(E3 + horizon * (B - E3) // denominator)
    ):
        raise VerificationError("four-gate budget policy mismatch")

    resource = item["resource_policy"]
    expected_resource = {
        "max_candidate_K": 622_592,
        "max_candidate_count": 34,
        "max_digest_terms": 786_432,
        "max_expansion_coefficient_tick_bits": 192,
        "max_output_terms_if_successful": 622_592,
        "max_product_bits": 384,
        "max_single_expansion_terms": 786_432,
        "max_suffix_accumulator_bits": 224,
        "max_term_gate_visits": 536_870_912,
        "max_trigonometric_tick_bits": 66,
        "resource_abort_action": (
            "indeterminate_fail_closed_without_scientific_negative_authority"
        ),
    }
    if not _strict_equal(resource, expected_resource):
        raise VerificationError("scientific resource policy mismatch")

    branches = item["legal_terminal_branches"]
    if type(branches) is not list or [branch.get("branch") for branch in branches] != list(
        LEGAL_BRANCHES
    ):
        raise VerificationError("legal terminal branch order or membership mismatch")
    for branch in branches:
        decision = BRANCH_DECISIONS[branch["branch"]]
        if (
            branch.get("authority") != decision["authority"]
            or branch.get("scientific_negative_authority")
            is not decision["scientific_negative_authority"]
            or branch.get("child_boundary_transition_or_sidecar_allowed") is not False
        ):
            raise VerificationError("legal terminal branch authority mismatch")

    precommit = item["precommit_boundary"]
    history = item["historical_disclosure"]
    isolation = item["isolation_policy"]
    premise = item["parent_authority"]
    if (
        precommit.get("formal_replay_started_before_this_policy_commit") is not False
        or precommit.get("policy_contains_formal_outcome_pins") is not False
        or precommit.get("policy_does_not_promise_any_terminal_branch") is not True
        or precommit.get(
            "formal_replay_must_start_only_after_policy_checker_and_precommit_contract_are_committed"
        )
        is not True
        or history.get("formal_replay_is_retrospective_replication_not_prospective_discovery")
        is not True
        or history.get("policy_was_selected_after_a_non_authoritative_diagnostic_observation")
        is not True
        or isolation.get("allowlist_staging_tree_required") is not True
        or isolation.get("old_q90_diagnostic_canonical_must_be_absent_from_staging_tree")
        is not True
        or isolation.get("old_q90_exact_result_test_must_be_absent_from_staging_tree")
        is not True
        or premise.get("certified_mapped_depth_before_and_after_screen") != 3
        or "not_reverified" not in premise.get("premise_role", "")
    ):
        raise VerificationError("precommit, disclosure, isolation, or premise boundary mismatch")

    scope = item["scope_boundary"]
    if (
        scope.get("M4_certified") is not False
        or scope.get("child_boundary_committed") is not False
        or scope.get("child_transition_committed") is not False
        or scope.get("positive_child_artifact_generated") is not False
        or scope.get("ready_gate_eligible") is not False
        or scope.get("exact_Hubbard_error") != "NOT_ASSESSED"
    ):
        raise VerificationError("policy scope boundary mismatch")
    return item


def _validate_precommit_contract(
    contract: Any, policy: Mapping[str, Any], self_sha256: str
) -> Mapping[str, Any]:
    item = _exact_keys(
        contract,
        (
            "schema_version",
            "contract_fingerprint",
            "phase",
            "checker_relative_path",
            "checker_source_sha256",
            "policy_relative_path",
            "policy_file_sha256",
            "policy_canonical_sha256",
            "source_pins",
            "legal_terminal_branches",
            "result_artifacts_absent_from_precommit_commit",
            "maximum_positive_status",
            "scope_ceiling",
        ),
        "M q90 formal S0 precommit contract",
    )
    if (
        item["schema_version"] != 1
        or item["contract_fingerprint"] != PRECOMMIT_CONTRACT_FINGERPRINT
        or item["phase"] != "PRECOMMIT_RESULT_UNPINNED"
        or item["checker_relative_path"] != SELF_NAME
        or item["checker_source_sha256"] != self_sha256
        or item["policy_relative_path"] != POLICY_NAME
        or item["policy_file_sha256"] != POLICY_FILE_SHA256
        or item["policy_canonical_sha256"] != POLICY_CANONICAL_SHA256
        or item["maximum_positive_status"] != MAXIMUM_POSITIVE_STATUS
    ):
        raise SchemaError("precommit contract identity or source pin mismatch")
    for key, expected in (
        ("source_pins", policy["source_pins"]),
        ("legal_terminal_branches", policy["legal_terminal_branches"]),
        ("result_artifacts_absent_from_precommit_commit", list(RESULT_ARTIFACTS)),
        ("scope_ceiling", SCOPE_CEILING),
    ):
        if not _strict_equal(item[key], expected):
            raise SchemaError(f"precommit contract {key} mismatch")
    return item


def _verify_precommit_impl(contract: Any, policy: Any) -> Dict[str, Any]:
    self_sha = hashlib.sha256(_self_source_bytes()).hexdigest()
    policy_item = _validate_policy(policy)
    _validate_precommit_contract(contract, policy_item, self_sha)
    return {
        "status": "VERIFIED_M_Q90_FORMAL_S0_RESULT_UNPINNED_PRECOMMIT",
        "verified": True,
        "checker_source_sha256": self_sha,
        "policy_file_sha256": POLICY_FILE_SHA256,
        "policy_canonical_sha256": POLICY_CANONICAL_SHA256,
        "source_pin_count": len(SOURCE_PIN_FACTS),
        "legal_terminal_branches": list(LEGAL_BRANCHES),
        "scope_ceiling": dict(SCOPE_CEILING),
    }


def verify_precommit(contract: Any, policy: Any) -> Dict[str, Any]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _verify_precommit_impl(contract, policy)
    return _execute_from_verified_self_source("_verify_precommit_impl", contract, policy)


def _read_pinned_sources(policy: Mapping[str, Any]) -> Dict[str, bytes]:
    output: Dict[str, bytes] = {}
    total = 0
    for pin in policy["source_pins"]:
        path = HERE / pin["relative_path"]
        resolved = path.resolve()
        try:
            resolved.relative_to(HERE.resolve())
        except ValueError as exc:
            raise SchemaError("source pin escapes the research directory") from exc
        payload = _regular_file_bytes(path, RESOURCE_LIMITS["max_pinned_file_bytes"])
        if len(payload) != pin["size_bytes"]:
            raise VerificationError(f"source size drift: {pin['relative_path']}")
        if hashlib.sha256(payload).hexdigest() != pin["sha256"]:
            raise VerificationError(f"source hash drift: {pin['relative_path']}")
        total += len(payload)
        output[pin["relative_path"]] = payload
    if len(output) != RESOURCE_LIMITS["max_staging_files"]:
        raise VerificationError("source closure cardinality drift")
    if total > RESOURCE_LIMITS["max_staging_total_bytes"]:
        raise VerificationError("source closure exceeds total byte cap")
    return output


def _tree_manifest(root: Path) -> list[Dict[str, Any]]:
    manifest = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        payload = _regular_file_bytes(path, RESOURCE_LIMITS["max_pinned_file_bytes"])
        manifest.append({
            "relative_path": relative,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        })
    return manifest


def _expected_staging_manifest(policy: Mapping[str, Any]) -> list[Dict[str, Any]]:
    return sorted(
        [
            {
                "relative_path": pin["relative_path"],
                "sha256": pin["sha256"],
                "size_bytes": pin["size_bytes"],
            }
            for pin in policy["source_pins"]
        ],
        key=lambda item: item["relative_path"],
    )


def _stage_sources(
    root: Path, policy: Mapping[str, Any], sources: Mapping[str, bytes]
) -> list[Dict[str, Any]]:
    if any(root.iterdir()):
        raise SchemaError("staging directory is not empty")
    for relative_path, payload in sources.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        os.chmod(target, 0o600)
    manifest = _tree_manifest(root)
    expected = _expected_staging_manifest(policy)
    if not _strict_equal(manifest, expected):
        raise VerificationError("staging tree differs from the exact 13-file allowlist")
    for entry in manifest:
        path = entry["relative_path"]
        if (
            "_q90_transcript.json" in path
            or (path.startswith("test_") and "q90" in path)
            or "_c33_" in path
        ):
            raise VerificationError("forbidden outcome or predecessor file entered staging")
    return manifest


def _compile_q90_engine(staging: Path, sources: Mapping[str, bytes]) -> Any:
    engine_name = SOURCE_PIN_FACTS[0][0]
    payload = sources[engine_name]
    module = types.ModuleType("verified_m_q90_outcome_unpinned_engine")
    module.__file__ = str(staging / engine_name)
    module.__package__ = ""
    module.__dict__["_VERIFIED_SELF_SOURCE_BYTES"] = payload
    exec(compile(payload, module.__file__, "exec"), module.__dict__)
    if (
        module.SELF_NAME != engine_name
        or module.EXTENDED_HORIZON != 90
        or tuple(module.M_CANDIDATES) != tuple(range(81_920, 622_592 + 1, 16_384))
        or not callable(getattr(module, "_run_verified", None))
    ):
        raise VerificationError("q90 execution-engine contract drift")
    return module


def _validate_candidate_matrix(
    record: Mapping[str, Any], candidates: Sequence[int], cumulative: int, cap: int
) -> list[int]:
    rows = record.get("candidate_records")
    pre_count = record.get("pretruncation_expansion_count")
    if type(pre_count) is not int or pre_count < 0:
        raise SchemaError("pretruncation expansion count is not a nonnegative integer")
    if type(rows) is not list or len(rows) != len(candidates):
        raise VerificationError("candidate matrix cardinality mismatch")
    feasible_indices = []
    previous_drop = None
    for index, (configured_K, row) in enumerate(zip(candidates, rows)):
        _exact_keys(row, CANDIDATE_RECORD_KEYS, "candidate record")
        effective = min(configured_K, pre_count)
        drop = _decimal(row["drop_ticks"], "candidate drop")
        expected_feasible = cumulative + drop <= cap
        if (
            type(row["candidate_index"]) is not int
            or row["candidate_index"] != index
            or type(row["configured_K"]) is not int
            or row["configured_K"] != configured_K
            or type(row["effective_retained_count"]) is not int
            or row["effective_retained_count"] != effective
            or type(row["dropped_term_count"]) is not int
            or row["dropped_term_count"] != pre_count - effective
            or row["E_after_if_selected_ticks"] != str(cumulative + drop)
            or row["feasible_under_current_prefix_cap"] is not expected_feasible
        ):
            raise VerificationError("candidate recurrence or feasibility mismatch")
        if previous_drop is not None and previous_drop < drop:
            raise VerificationError("ranked suffix drops are not monotone")
        previous_drop = drop
        if expected_feasible:
            feasible_indices.append(index)
    return feasible_indices


def derive_terminal_branch(statuses: Sequence[str], abort_checkpoint: int | None) -> str:
    if type(statuses) is not list or any(
        status not in (SUCCESS_STATUS, FAILURE_STATUS) for status in statuses
    ):
        raise VerificationError("record status sequence is malformed")
    if len(statuses) == 89 and statuses[:88] == [SUCCESS_STATUS] * 88:
        if statuses[88] == FAILURE_STATUS and abort_checkpoint is None:
            return "Q89_FAILURE_Q90_NOT_ATTEMPTED"
        if statuses[88] == SUCCESS_STATUS and abort_checkpoint == 90:
            return "Q89_SUCCESS_Q90_RESOURCE_ABORT"
    if len(statuses) == 88 and statuses == [SUCCESS_STATUS] * 88 and abort_checkpoint == 89:
        return "Q89_RESOURCE_ABORT_Q90_NOT_ATTEMPTED"
    if len(statuses) == 90 and statuses[:89] == [SUCCESS_STATUS] * 89:
        if statuses[89] == FAILURE_STATUS and abort_checkpoint is None:
            return "Q89_SUCCESS_Q90_FAILURE"
        if statuses[89] == SUCCESS_STATUS and abort_checkpoint is None:
            return "Q89_AND_Q90_SUCCESS_HORIZON_REACHED"
    raise VerificationError("record and abort shape does not match a legal terminal branch")


def classify_terminal_branch(branch: str) -> Dict[str, Any]:
    if branch not in BRANCH_DECISIONS:
        raise VerificationError("unknown terminal branch")
    return dict(BRANCH_DECISIONS[branch])


def _validate_formal_ledger(
    result: Mapping[str, Any], policy: Mapping[str, Any]
) -> Dict[str, Any]:
    records = result.get("records")
    history = result.get("selected_K_history")
    if type(records) is not list or type(history) is not list:
        raise SchemaError("fresh replay ledger or selected-K history is malformed")
    if result.get("records_sha256") != canonical_sha256(records):
        raise VerificationError("fresh replay ledger digest mismatch")
    if result.get("selected_K_history_sha256") != canonical_sha256(history):
        raise VerificationError("fresh replay selected-K history digest mismatch")

    candidates = policy["candidate_policy"][
        "candidate_K_values_in_strict_ascending_order"
    ]
    budget = policy["sequence_and_budget"]
    E3 = _decimal(budget["input_cumulative_drop_ticks"], "policy E3")
    B = _decimal(budget["maximum_cumulative_drop_ticks"], "policy B")
    denominator = budget["total_future_checkpoint_denominator"]
    cumulative = E3
    observed_history = []
    statuses: list[str] = []
    failure = None
    for checkpoint, record in enumerate(records, 1):
        if type(record) is not dict:
            raise SchemaError("fresh replay record is not an object")
        cap = E3 + checkpoint * (B - E3) // denominator
        if (
            type(record.get("checkpoint_number_one_based")) is not int
            or record.get("checkpoint_number_one_based") != checkpoint
            or type(record.get("checkpoint_index_zero_based")) is not int
            or record.get("checkpoint_index_zero_based") != checkpoint - 1
            or record.get("budget_prefix_cap_ticks") != str(cap)
            or record.get("E_before_ticks") != str(cumulative)
            or record.get("prefix_slack_before_selection_ticks")
            != str(cap - cumulative)
        ):
            raise VerificationError("checkpoint index or prefix-budget recurrence mismatch")
        feasible = _validate_candidate_matrix(record, candidates, cumulative, cap)
        status_value = record.get("status")
        if status_value == SUCCESS_STATUS:
            if not feasible:
                raise VerificationError("committed checkpoint has no feasible candidate")
            selected_index = feasible[0]
            selected = record["candidate_records"][selected_index]
            selected_drop = _decimal(selected["drop_ticks"], "selected drop")
            if (
                record.get("selected_candidate_index") != selected_index
                or record.get("selected_K") != candidates[selected_index]
                or record.get("selected_effective_retained_count")
                != selected["effective_retained_count"]
                or record.get("selected_dropped_term_count")
                != selected["dropped_term_count"]
                or record.get("selected_drop_ticks") != str(selected_drop)
                or record.get("E_after_ticks") != str(cumulative + selected_drop)
                or record.get("retained_expansion_count")
                != selected["effective_retained_count"]
            ):
                raise VerificationError("first-feasible selection or commit mismatch")
            cumulative += selected_drop
            observed_history.append(candidates[selected_index])
        elif status_value == FAILURE_STATUS:
            if feasible or failure is not None:
                raise VerificationError("terminal failure has a feasible candidate or repeats")
            if (
                record.get("selected_candidate_index") is not None
                or record.get("selected_K") is not None
            ):
                raise VerificationError("terminal failure selected a candidate")
            diagnostic_minimum = record.get("minimum_effective_K_to_meet_prefix")
            diagnostic_excess = record.get("required_K_excess_over_policy_maximum")
            if (
                type(diagnostic_minimum) is not int
                or type(diagnostic_excess) is not int
                or diagnostic_minimum <= candidates[-1]
                or diagnostic_excess != diagnostic_minimum - candidates[-1]
            ):
                raise VerificationError("non-authoritative minimum-K diagnostic is inconsistent")
            failure = record
        else:
            raise VerificationError("unknown checkpoint status")
        statuses.append(status_value)
        if failure is not None and checkpoint != len(records):
            raise VerificationError("record appears after terminal no-candidate failure")

        resource = policy["resource_policy"]
        resource_values = {
            "peak_live_terms_cumulative": resource["max_single_expansion_terms"],
            "term_gate_visits_cumulative": resource["max_term_gate_visits"],
            "maximum_expansion_coefficient_tick_bits": resource[
                "max_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": resource["max_product_bits"],
        }
        if any(
            type(record.get(key)) is not int or record[key] > maximum
            for key, maximum in resource_values.items()
        ):
            raise VerificationError("record exceeds the precommitted scientific resource policy")

    abort = result.get("resource_policy_abort")
    abort_digest = result.get("resource_policy_abort_sha256")
    if abort is None:
        if abort_digest is not None:
            raise VerificationError("null resource abort has a non-null digest")
        abort_checkpoint = None
    else:
        if type(abort) is not dict or abort_digest != canonical_sha256(abort):
            raise VerificationError("resource abort object or digest mismatch")
        abort_checkpoint = abort.get("checkpoint_number_one_based")
        if type(abort_checkpoint) is not int:
            raise VerificationError("resource abort checkpoint is malformed")
    branch = derive_terminal_branch(statuses, abort_checkpoint)
    handoff = result.get("predecessor_handoff_validation")
    if (
        type(handoff) is not dict
        or handoff.get("terminal_branch") != branch
        or handoff.get("legal_terminal_branches") != list(LEGAL_BRANCHES)
        or handoff.get("record_count") != len(records)
        or handoff.get("selected_history_count") != len(history)
        or handoff.get("candidate_row_count")
        != sum(len(record["candidate_records"]) for record in records)
        or handoff.get("resource_policy_abort_structured") is not (abort is not None)
    ):
        raise VerificationError("self-reported handoff disagrees with independently derived branch")
    if result.get("predecessor_handoff_validation_sha256") != canonical_sha256(handoff):
        raise VerificationError("handoff digest mismatch")
    if observed_history != history:
        raise VerificationError("selected-K history disagrees with committed records")
    if result.get("last_committed_cumulative_drop_ticks") != str(cumulative):
        raise VerificationError("last committed cumulative drop mismatch")
    expected_failure_digest = canonical_sha256(failure) if failure is not None else None
    if result.get("failure_record_sha256") != expected_failure_digest:
        raise VerificationError("failure record digest mismatch")

    branch_summary = {
        "Q89_FAILURE_Q90_NOT_ATTEMPTED": (
            89, 88, False, False, True, "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        ),
        "Q89_RESOURCE_ABORT_Q90_NOT_ATTEMPTED": (
            89, 88, False, False, False, "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
        ),
        "Q89_SUCCESS_Q90_FAILURE": (
            90, 89, True, False, True, "DIAGNOSTIC_NO_POLICY_CANDIDATE_FEASIBLE"
        ),
        "Q89_SUCCESS_Q90_RESOURCE_ABORT": (
            90, 89, True, False, False, "DIAGNOSTIC_RESOURCE_POLICY_ABORT"
        ),
        "Q89_AND_Q90_SUCCESS_HORIZON_REACHED": (
            90, 90, True, True, False, "DIAGNOSTIC_HORIZON_REACHED"
        ),
    }
    attempted, completed, horizon_attempted, horizon_reached, has_failure, terminal = (
        branch_summary[branch]
    )
    if (
        result.get("attempted_checkpoint_count") != attempted
        or result.get("completed_checkpoint_count") != completed
        or result.get("horizon_checkpoint_attempted") is not horizon_attempted
        or result.get("horizon_reached_with_committed_checkpoint") is not horizon_reached
        or result.get("failure_checkpoint_included") is not has_failure
        or result.get("screen_terminal_condition") != terminal
    ):
        raise VerificationError("top-level terminal summary disagrees with derived branch")
    resource_source = abort if abort is not None else records[-1]
    resource_fields = {
        "observed_peak_single_expansion_terms": "peak_live_terms_cumulative",
        "observed_term_gate_visits_including_terminal_attempt": (
            "term_gate_visits_cumulative"
        ),
        "observed_maximum_expansion_coefficient_tick_bits": (
            "maximum_expansion_coefficient_tick_bits"
        ),
        "observed_maximum_product_bits": "maximum_product_bits",
        "observed_rounding_cumulative_scaled_ticks_squared": (
            "rounding_cumulative_scaled_ticks_squared"
        ),
    }
    if any(
        result.get(output_key) != resource_source.get(source_key)
        for output_key, source_key in resource_fields.items()
    ):
        raise VerificationError("top-level resource summary disagrees with terminal source")
    return {
        "branch": branch,
        "records": records,
        "history": history,
        "failure": failure,
        "abort": abort,
        "last_committed_cumulative_drop_ticks": str(cumulative),
    }


def _validate_result_identity(
    result: Mapping[str, Any], policy: Mapping[str, Any]
) -> None:
    candidates = policy["candidate_policy"][
        "candidate_K_values_in_strict_ascending_order"
    ]
    resource = policy["resource_policy"]
    budget = policy["sequence_and_budget"]
    if (
        result.get("status") != DIAGNOSTIC_STATUS
        or result.get("observable_id") != "staggered_magnetization"
        or result.get("input_step_index") != 3
        or result.get("attempted_child_step_index") != 4
        or result.get("screen_horizon_checkpoint_count") != 90
        or result.get("candidate_K_values") != candidates
        or result.get("candidate_K_values_sha256")
        != policy["candidate_policy"]["candidate_K_values_sha256"]
        or result.get("proposed_policy_caps")
        != {key: resource[key] for key in resource if key != "resource_abort_action"}
        or result.get("input_cumulative_drop_ticks")
        != budget["input_cumulative_drop_ticks"]
        or result.get("maximum_cumulative_drop_ticks")
        != budget["maximum_cumulative_drop_ticks"]
        or result.get("future_checkpoint_denominator")
        != budget["total_future_checkpoint_denominator"]
        or result.get("prefix_cap_formula") != budget["prefix_cap_formula"]
        or result.get("kernel_capability_limits")
        != policy["wrapped_kernel_capability"]["limits"]
        or result.get("candidate_policy_precommitted_at_probe_time") is not False
        or result.get("diagnostic_candidate_ladder_precommitted_before_replay")
        is not True
        or result.get("diagnostic_horizon_precommitted_before_replay") is not True
        or result.get("root_globals_unchanged") is not True
        or result.get("child_boundary_committed") is not False
        or result.get("positive_artifact_generated") is not False
        or result.get("runtime_RSS_host_timestamp_and_float_fields_excluded") is not True
    ):
        raise VerificationError("fresh replay identity, policy, or fail-closed scope mismatch")

    sequence = result.get("sequence")
    if (
        type(sequence) is not dict
        or sequence.get("checkpoint_count") != 288
        or sequence.get("gate_count") != 1152
        or sequence.get("gates_per_checkpoint") != 4
        or sequence.get("baseline_checkpoint_count") != 144
        or sequence.get("baseline_gates_per_checkpoint") != 8
        or sequence.get("backprop_gate_records_sha256")
        != budget["backprop_gate_records_sha256"]
        or sequence.get("Neel_expectation_used_for_K_selection") is not False
    ):
        raise VerificationError("fresh replay four-gate sequence identity mismatch")

    pin_by_path = {pin["relative_path"]: pin for pin in policy["source_pins"]}
    expected_component_paths = [
        SOURCE_PIN_FACTS[index][0]
        for index in (0, 1, 5, 4, 6, 7, 8, 9, 10, 11, 12)
    ]
    components = result.get("screen_execution_components")
    if (
        type(components) is not list
        or [component.get("relative_path") for component in components]
        != expected_component_paths
        or any(
            component.get("sha256")
            != pin_by_path[component.get("relative_path", "")]["sha256"]
            for component in components
        )
        or result.get("screen_execution_components_sha256")
        != canonical_sha256(components)
    ):
        raise VerificationError("q90 outer execution-component report mismatch")
    expected_custody_paths = [
        SOURCE_PIN_FACTS[index][0] for index in (0, 1, 4, 5, 6, 7, 8, 9, 10, 11)
    ]
    expected_custody = {
        path: pin_by_path[path]["sha256"] for path in expected_custody_paths
    }
    if result.get("source_custody") != expected_custody:
        raise VerificationError("q90 source custody mismatch")
    if result.get("screen_source_sha256") != pin_by_path[SOURCE_PIN_FACTS[0][0]]["sha256"]:
        raise VerificationError("q90 same-byte self source mismatch")
    if (
        result.get("parent_expected_witness_sha256")
        != policy["parent_authority"]["expected_witness_sha256"]
        or result.get("input_boundary_custody", {}).get("encoded_sha256")
        != policy["parent_authority"]["encoded_boundary_sha256"]
    ):
        raise VerificationError("hash-pinned M3 premise custody mismatch")


def _record_summary(record: Mapping[str, Any]) -> Dict[str, Any]:
    summary = {
        "checkpoint_number_one_based": record["checkpoint_number_one_based"],
        "record_sha256": canonical_sha256(record),
        "status": record["status"],
        "pretruncation_expansion_count": record["pretruncation_expansion_count"],
        "budget_prefix_cap_ticks": record["budget_prefix_cap_ticks"],
        "E_before_ticks": record["E_before_ticks"],
        "prefix_slack_before_selection_ticks": record[
            "prefix_slack_before_selection_ticks"
        ],
        "selected_K": record.get("selected_K"),
    }
    if record["status"] == SUCCESS_STATUS:
        summary.update({
            "E_after_ticks": record["E_after_ticks"],
            "retained_expansion_count": record["retained_expansion_count"],
            "retained_expansion_sha256": record["retained_expansion_sha256"],
        })
    else:
        summary.update({
            "minimum_effective_K_diagnostic_only": record[
                "minimum_effective_K_to_meet_prefix"
            ],
            "required_K_excess_diagnostic_only": record[
                "required_K_excess_over_policy_maximum"
            ],
            "policy_max_K_candidate_drop_ticks": record["candidate_records"][-1][
                "drop_ticks"
            ],
        })
    return summary


def _scope_claims_for_branch(branch: str) -> Dict[str, Any]:
    decision = classify_terminal_branch(branch)
    return {
        "retrospective_replication_only": True,
        "prospective_discovery_authority": False,
        "fixed_policy_q90_candidate_ceiling_infeasibility_verified": (
            decision["scientific_negative_authority"]
        ),
        "larger_K_other_cadences_and_other_algorithms": "NOT_ASSESSED",
        "certified_mapped_depth": 3,
        "M4_certified": False,
        "child_boundary_transition_or_sidecar_generated": False,
        "product_formula_to_exact_Hubbard_error": "NOT_ASSESSED",
        "physical_reference_qualified": False,
        "ready_gate_eligible": False,
    }


def _build_witness(
    result: Mapping[str, Any],
    policy: Mapping[str, Any],
    staging_manifest: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    _validate_result_identity(result, policy)
    ledger = _validate_formal_ledger(result, policy)
    branch = ledger["branch"]
    decision = classify_terminal_branch(branch)
    records = ledger["records"]
    relevant_records = [
        _record_summary(record)
        for record in records
        if record["checkpoint_number_one_based"] in (89, 90)
    ]
    failure = ledger["failure"]
    failure_candidates = failure["candidate_records"] if failure is not None else None
    if branch == "Q89_SUCCESS_Q90_FAILURE":
        if (
            failure is None
            or failure["checkpoint_number_one_based"] != 90
            or any(row["feasible_under_current_prefix_cap"] is not False for row in failure_candidates)
            or ledger["abort"] is not None
        ):
            raise VerificationError("q90 negative-authority branch lacks all-34 infeasibility")

    return {
        "checker_fingerprint": CHECKER_FINGERPRINT,
        "policy_precommit": {
            "policy_id": POLICY_ID,
            "policy_file_sha256": POLICY_FILE_SHA256,
            "policy_canonical_sha256": POLICY_CANONICAL_SHA256,
            "outer_formal_policy_committed_before_replay": True,
            "inner_diagnostic_probe_historical_precommit_flag_preserved_as_false": True,
            "retrospective_replication_disclosed": True,
        },
        "execution_custody": {
            "allowlist_staging_manifest": list(staging_manifest),
            "allowlist_staging_manifest_sha256": canonical_sha256(staging_manifest),
            "allowlist_file_count": len(staging_manifest),
            "nested_four_gate_control_root_included": True,
            "q90_outer_component_report_hides_nested_control_root": True,
            "q88_canonical_loaded_post_replay_as_prefix_reference_only": True,
            "prior_q90_result_artifacts_read_or_staged": False,
            "C33_predecessor_files_read_or_staged": False,
            "same_byte_q90_engine_sha256": SOURCE_PIN_FACTS[0][1],
        },
        "parent_premise": {
            "status": policy["parent_authority"]["required_positive_status"],
            "expected_witness_sha256": policy["parent_authority"][
                "expected_witness_sha256"
            ],
            "encoded_boundary_sha256": policy["parent_authority"][
                "encoded_boundary_sha256"
            ],
            "certified_mapped_depth": 3,
            "role": policy["parent_authority"]["premise_role"],
        },
        "screen_result": {
            "terminal_branch": branch,
            "status": decision["status"],
            "authority": decision["authority"],
            "scientific_negative_authority": decision[
                "scientific_negative_authority"
            ],
            "record_count": len(records),
            "selected_K_history_count": len(ledger["history"]),
            "candidate_row_count": sum(
                len(record["candidate_records"]) for record in records
            ),
            "checkpoint_ledger_sha256": result["records_sha256"],
            "selected_K_history": ledger["history"],
            "selected_K_history_sha256": result["selected_K_history_sha256"],
            "failure_record_sha256": result["failure_record_sha256"],
            "last_committed_cumulative_drop_ticks": ledger[
                "last_committed_cumulative_drop_ticks"
            ],
            "q89_q90_record_summaries": relevant_records,
            "terminal_failure_candidate_evaluations": failure_candidates,
            "minimum_effective_K_is_diagnostic_not_required_for_negative_authority": True,
            "resource_policy_abort": ledger["abort"],
            "resource_policy_abort_sha256": result["resource_policy_abort_sha256"],
        },
        "resource_summary": {
            "peak_single_expansion_terms": result[
                "observed_peak_single_expansion_terms"
            ],
            "term_gate_visits_including_terminal_attempt": result[
                "observed_term_gate_visits_including_terminal_attempt"
            ],
            "maximum_expansion_coefficient_tick_bits": result[
                "observed_maximum_expansion_coefficient_tick_bits"
            ],
            "maximum_product_bits": result["observed_maximum_product_bits"],
            "rounding_cumulative_scaled_ticks_squared": result[
                "observed_rounding_cumulative_scaled_ticks_squared"
            ],
            "scientific_policy_caps": policy["resource_policy"],
            "host_runtime_RSS_timestamp_or_float_fields_included": False,
        },
        "decision": {
            "status": decision["status"],
            "fixed_policy_negative_authority": decision[
                "scientific_negative_authority"
            ],
            "certified_mapped_depth": 3,
            "M4_certified": False,
            "child_boundary_transition_or_sidecar_generated": False,
            "remaining_R100_steps_exact_Hubbard_error_reference_and_READY": (
                "NOT_ASSESSED"
            ),
        },
    }


def _git(arguments: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(HERE), *arguments],
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise VerificationError(
            f"git {' '.join(arguments)} failed: {result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result


def _repository_root() -> Path:
    return Path(_git(("rev-parse", "--show-toplevel")).stdout.decode().strip()).resolve()


def _research_relative_to_repo(filename: str) -> str:
    return ((HERE / filename).resolve().relative_to(_repository_root())).as_posix()


def _commit_blob(commit: str, filename: str) -> bytes:
    relative = _research_relative_to_repo(filename)
    tree = _git(
        ("ls-tree", commit, "--", f":(top){relative}")
    ).stdout.decode().strip().split()
    if len(tree) < 4 or tree[0] != "100644" or tree[1] != "blob":
        raise VerificationError(f"precommit path is absent or not a regular blob: {filename}")
    return _git(("show", f"{commit}:{relative}")).stdout


def _commit_lacks_path(commit: str, filename: str) -> None:
    relative = _research_relative_to_repo(filename)
    result = _git(("cat-file", "-e", f"{commit}:{relative}"), check=False)
    if result.returncode == 0:
        raise VerificationError(f"result artifact already existed in precommit: {filename}")


def _validate_commit_id(commit: Any) -> str:
    if type(commit) is not str or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise SchemaError("precommit commit must be a full lowercase 40-hex commit id")
    resolved = _git(("rev-parse", f"{commit}^{{commit}}")).stdout.decode().strip()
    if resolved != commit:
        raise VerificationError("precommit commit id did not resolve exactly")
    return commit


def _precommit_file_bytes() -> Dict[str, bytes]:
    return {
        POLICY_NAME: _regular_file_bytes(
            HERE / POLICY_NAME, RESOURCE_LIMITS["max_json_bytes"]
        ),
        SELF_NAME: _regular_file_bytes(
            HERE / SELF_NAME, RESOURCE_LIMITS["max_checker_source_bytes"]
        ),
        PRECOMMIT_CONTRACT_NAME: _regular_file_bytes(
            HERE / PRECOMMIT_CONTRACT_NAME, RESOURCE_LIMITS["max_json_bytes"]
        ),
    }


def _verify_generation_git_state(commit: Any) -> str:
    commit = _validate_commit_id(commit)
    head = _git(("rev-parse", "HEAD")).stdout.decode().strip()
    if head != commit:
        raise VerificationError("fresh replay requires HEAD to equal the precommit commit")
    status_output = _git(("status", "--porcelain=v1", "--untracked-files=all")).stdout
    if status_output:
        raise VerificationError("fresh replay requires a completely clean worktree and index")
    for filename, payload in _precommit_file_bytes().items():
        if _commit_blob(commit, filename) != payload:
            raise VerificationError(f"precommit blob differs from live bytes: {filename}")
    for filename in RESULT_ARTIFACTS:
        _commit_lacks_path(commit, filename)
    return commit


def _verify_precommit_history(commit: Any) -> str:
    commit = _validate_commit_id(commit)
    if _git(("merge-base", "--is-ancestor", commit, "HEAD"), check=False).returncode != 0:
        raise VerificationError("precommit commit is not an ancestor of current HEAD")
    for filename, payload in _precommit_file_bytes().items():
        if _commit_blob(commit, filename) != payload:
            raise VerificationError(f"precommit artifact changed after replay: {filename}")
    for filename in RESULT_ARTIFACTS:
        _commit_lacks_path(commit, filename)
    return commit


def _run_fresh_replay(
    policy: Mapping[str, Any]
) -> Tuple[Dict[str, Any], list[Dict[str, Any]]]:
    sources = _read_pinned_sources(policy)
    with tempfile.TemporaryDirectory(prefix="m-q90-formal-s0-") as directory:
        staging = Path(directory)
        before = _stage_sources(staging, policy, sources)
        engine = _compile_q90_engine(staging, sources)
        result = engine._run_verified(staging.resolve())
        after = _tree_manifest(staging)
        if not _strict_equal(after, before):
            raise VerificationError("fresh replay modified the allowlist staging tree")
    if type(result) is not dict:
        raise VerificationError("fresh replay did not return an exact result object")
    return result, before


def _fresh_replay_impl(
    contract: Any, policy: Any, precommit_commit: Any
) -> Dict[str, Any]:
    _verify_precommit_impl(contract, policy)
    commit = _verify_generation_git_state(precommit_commit)
    policy_item = _validate_policy(policy)
    result, staging_manifest = _run_fresh_replay(policy_item)
    _verify_generation_git_state(commit)
    witness = _build_witness(result, policy_item, staging_manifest)
    return {
        "schema_version": 1,
        "package_type": "m_q90_formal_s0_fresh_replay_package_v1",
        "precommit_commit_sha": commit,
        "checker_source_sha256": hashlib.sha256(_self_source_bytes()).hexdigest(),
        "policy_file_sha256": POLICY_FILE_SHA256,
        "precommit_contract_sha256": hashlib.sha256(
            _regular_file_bytes(
                HERE / PRECOMMIT_CONTRACT_NAME, RESOURCE_LIMITS["max_json_bytes"]
            )
        ).hexdigest(),
        "fresh_replay_result": result,
        "fresh_replay_result_sha256": canonical_sha256(result),
        "witness_claim": witness,
        "witness_sha256": canonical_sha256(witness),
        "scope_claims": _scope_claims_for_branch(
            witness["screen_result"]["terminal_branch"]
        ),
    }


def fresh_replay(contract: Any, policy: Any, precommit_commit: Any) -> Dict[str, Any]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _fresh_replay_impl(contract, policy, precommit_commit)
    return _execute_from_verified_self_source(
        "_fresh_replay_impl", contract, policy, precommit_commit
    )


def _validate_final_contract(
    contract: Any,
    precommit_contract: Mapping[str, Any],
    policy: Mapping[str, Any],
    self_sha256: str,
) -> Mapping[str, Any]:
    item = _exact_keys(
        contract,
        (
            "schema_version",
            "contract_fingerprint",
            "checker_relative_path",
            "checker_source_sha256",
            "policy_relative_path",
            "policy_file_sha256",
            "precommit_contract_relative_path",
            "precommit_contract_sha256",
            "precommit_commit_sha",
            "certificate_relative_path",
            "expected_fresh_replay_result_sha256",
            "expected_witness_sha256",
            "maximum_positive_status",
            "source_pins",
            "workload_identity",
            "scope_claims",
            "scope_ceiling",
        ),
        "M q90 formal S0 final contract",
    )
    if (
        item["schema_version"] != 1
        or item["contract_fingerprint"] != FINAL_CONTRACT_FINGERPRINT
        or item["checker_relative_path"] != SELF_NAME
        or item["checker_source_sha256"] != self_sha256
        or item["policy_relative_path"] != POLICY_NAME
        or item["policy_file_sha256"] != POLICY_FILE_SHA256
        or item["precommit_contract_relative_path"] != PRECOMMIT_CONTRACT_NAME
        or item["precommit_contract_sha256"]
        != hashlib.sha256(
            _regular_file_bytes(
                HERE / PRECOMMIT_CONTRACT_NAME, RESOURCE_LIMITS["max_json_bytes"]
            )
        ).hexdigest()
        or item["certificate_relative_path"] != CERTIFICATE_NAME
        or item["maximum_positive_status"] != MAXIMUM_POSITIVE_STATUS
        or not _is_sha256(item["expected_fresh_replay_result_sha256"])
        or not _is_sha256(item["expected_witness_sha256"])
    ):
        raise SchemaError("final contract identity, source, or result pin mismatch")
    if (
        precommit_contract["checker_source_sha256"] != self_sha256
        or not _strict_equal(item["source_pins"], policy["source_pins"])
        or not _strict_equal(item["workload_identity"], policy["workload_identity"])
        or not _strict_equal(item["scope_ceiling"], SCOPE_CEILING)
    ):
        raise SchemaError("final contract disagrees with precommit artifacts")
    _verify_precommit_history(item["precommit_commit_sha"])
    return item


def _verify_certificate_impl(
    contract: Any, certificate: Any, precommit_contract: Any, policy: Any
) -> Dict[str, Any]:
    self_sha = hashlib.sha256(_self_source_bytes()).hexdigest()
    policy_item = _validate_policy(policy)
    precommit_item = _validate_precommit_contract(
        precommit_contract, policy_item, self_sha
    )
    final_item = _validate_final_contract(
        contract, precommit_item, policy_item, self_sha
    )
    certificate_item = _exact_keys(
        certificate,
        (
            "schema_version",
            "certificate_type",
            "contract_fingerprint",
            "workload_identity",
            "scope_claims",
            "witness_claim",
        ),
        "M q90 formal S0 certificate",
    )
    if (
        certificate_item["schema_version"] != 1
        or certificate_item["certificate_type"] != CERTIFICATE_TYPE
        or certificate_item["contract_fingerprint"] != FINAL_CONTRACT_FINGERPRINT
        or not _strict_equal(
            certificate_item["workload_identity"], policy_item["workload_identity"]
        )
    ):
        raise SchemaError("certificate identity or workload mismatch")

    result, staging_manifest = _run_fresh_replay(policy_item)
    witness = _build_witness(result, policy_item, staging_manifest)
    scope = _scope_claims_for_branch(witness["screen_result"]["terminal_branch"])
    if (
        canonical_sha256(result) != final_item["expected_fresh_replay_result_sha256"]
        or canonical_sha256(witness) != final_item["expected_witness_sha256"]
        or not _strict_equal(certificate_item["witness_claim"], witness)
        or not _strict_equal(certificate_item["scope_claims"], scope)
        or not _strict_equal(final_item["scope_claims"], scope)
    ):
        raise VerificationError("certificate disagrees with fresh isolated replay")
    return {
        "status": witness["decision"]["status"],
        "verified": True,
        "checker_source_sha256": self_sha,
        "precommit_commit_sha": final_item["precommit_commit_sha"],
        "fresh_replay_result_sha256": canonical_sha256(result),
        "expected_witness_sha256": canonical_sha256(witness),
        "recomputed_witness": witness,
        "scope_claims": scope,
    }


def verify_certificate(
    contract: Any, certificate: Any, precommit_contract: Any, policy: Any
) -> Dict[str, Any]:
    if _VERIFIED_SELF_SOURCE_BYTES is not None:
        return _verify_certificate_impl(
            contract, certificate, precommit_contract, policy
        )
    return _execute_from_verified_self_source(
        "_verify_certificate_impl",
        contract,
        certificate,
        precommit_contract,
        policy,
    )


def _write_atomic(path: Path, payload: bytes) -> None:
    if len(payload) > RESOURCE_LIMITS["max_replay_package_bytes"]:
        raise SchemaError("replay package exceeds output byte cap")
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--precommit-contract", type=Path, default=HERE / PRECOMMIT_CONTRACT_NAME
    )
    parser.add_argument("--policy", type=Path, default=HERE / POLICY_NAME)
    parser.add_argument("--fresh-replay", action="store_true")
    parser.add_argument("--precommit-commit")
    parser.add_argument("--replay-output", type=Path)
    parser.add_argument("--verify-final", action="store_true")
    parser.add_argument("--final-contract", type=Path, default=HERE / FINAL_CONTRACT_NAME)
    parser.add_argument("--certificate", type=Path, default=HERE / CERTIFICATE_NAME)
    args = parser.parse_args(argv)
    try:
        precommit_contract = load_strict_json(args.precommit_contract)
        policy = load_strict_json(args.policy)
        policy_raw = _regular_file_bytes(args.policy, RESOURCE_LIMITS["max_json_bytes"])
        if hashlib.sha256(policy_raw).hexdigest() != POLICY_FILE_SHA256:
            raise VerificationError("policy file-byte hash mismatch")
        if args.fresh_replay and args.verify_final:
            raise SchemaError("choose at most one replay mode")
        if args.fresh_replay:
            if args.precommit_commit is None or args.replay_output is None:
                raise SchemaError("fresh replay requires --precommit-commit and --replay-output")
            package = fresh_replay(
                precommit_contract, policy, args.precommit_commit
            )
            raw = canonical_bytes(package)
            _write_atomic(args.replay_output, raw)
            result = {
                "status": package["witness_claim"]["decision"]["status"],
                "verified": True,
                "replay_output": str(args.replay_output.resolve()),
                "fresh_replay_result_sha256": package[
                    "fresh_replay_result_sha256"
                ],
                "witness_sha256": package["witness_sha256"],
                "precommit_commit_sha": package["precommit_commit_sha"],
            }
            exit_code = 0
        elif args.verify_final:
            result = verify_certificate(
                load_strict_json(args.final_contract),
                load_strict_json(args.certificate),
                precommit_contract,
                policy,
            )
            exit_code = 1
        else:
            result = verify_precommit(precommit_contract, policy)
            exit_code = 0
    except (
        OSError,
        SchemaError,
        VerificationError,
        RuntimeError,
        KeyError,
        TypeError,
        ValueError,
        RecursionError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            json.dumps(
                {"status": "FAILED", "verified": False, "error": str(exc)},
                allow_nan=False,
                ensure_ascii=True,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, allow_nan=False, ensure_ascii=True, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
