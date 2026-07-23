#!/usr/bin/env python3
"""D21 fail-closed readiness review for the D20 full-run plan.

No scientific action is performed.  The checker distinguishes a declarative
protocol plan from an executable consumer and prevents resource authorization
from being inferred from bounded D18-C observations.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CHECKER = "docs/research/fermion-frontier/fh_l8_full_resource_readiness_d21_checker.py"
TEST = "docs/research/fermion-frontier/test_fh_l8_full_resource_readiness_d21.py"
CONTRACT = "docs/research/fermion-frontier/fh_l8_full_resource_readiness_d21_contract.json"
RESULT = "docs/research/fermion-frontier/fh_l8_full_resource_readiness_d21_result.json"
D20_RUNNER = "fh_l8_full_consumer_d20.py"
D20_CONTRACT = "fh_l8_full_consumer_d20_contract.json"
D20_RESULT = "fh_l8_full_consumer_d20_result.json"
STATUS = "NO_GO_D21_FULL_53_RESOURCE_AUTHORIZATION_EXECUTABLE_IMPLEMENTATION_ABSENT"
NEXT_GATE = "FULL_53_SHARD_EXECUTABLE_CONSUMER_AND_TINY_FIXTURE_RECOVERY_VALIDATION"


class VerificationError(RuntimeError):
    pass


def _reject_float(token: str) -> Any:
    raise VerificationError(f"floating-point JSON forbidden: {token}")


def _reject_constant(token: str) -> Any:
    raise VerificationError(f"non-finite JSON forbidden: {token}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise VerificationError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_json(path: Path, maximum: int = 1_048_576) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"cannot read {path}: {exc}") from exc
    if not raw or len(raw) > maximum:
        raise VerificationError(f"JSON size outside bound: {path}")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"top-level object required: {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _exact(value: dict[str, Any], keys: set[str], label: str) -> None:
    _require(set(value) == keys, f"{label} key drift")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode:
        raise VerificationError(
            f"git {' '.join(args)} failed: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc


def _git_text(*args: str) -> str:
    return _git(*args).stdout.decode("utf-8").strip()


def _commit(value: Any, label: str) -> str:
    _require(
        isinstance(value, str)
        and len(value) == 40
        and all(ch in "0123456789abcdef" for ch in value),
        f"{label} must be full commit",
    )
    return value


def _diff(parent: str, child: str) -> list[tuple[str, str]]:
    text = _git_text("diff", "--name-status", "--no-renames", parent, child)
    return [tuple(line.split("\t", 1)) for line in text.splitlines()] if text else []


def _chronology(contract: dict[str, Any]) -> None:
    value = contract["chronology"]
    _exact(
        value,
        {
            "baseline",
            "checker_freeze",
            "checker_path",
            "test_path",
            "contract_path",
            "result_path",
            "result_absent_at_contract_freeze",
        },
        "chronology",
    )
    baseline = _commit(value["baseline"], "baseline")
    c1 = _commit(value["checker_freeze"], "checker_freeze")
    _require(value["checker_path"] == CHECKER, "checker path drift")
    _require(value["test_path"] == TEST, "test path drift")
    _require(value["contract_path"] == CONTRACT, "contract path drift")
    _require(value["result_path"] == RESULT, "result path drift")
    _require(value["result_absent_at_contract_freeze"] is True, "result absence required")
    _require(_git_text("rev-parse", f"{c1}^") == baseline, "C1 parent drift")
    _require(_diff(baseline, c1) == [("M", CHECKER)], "checker refreeze content drift")
    c2 = _git_text("log", "--diff-filter=A", "-1", "--format=%H", "--", CONTRACT)
    _require(bool(c2), "contract freeze commit absent")
    _require(_git_text("rev-parse", f"{c2}^") == c1, "C2 parent drift")
    _require(_diff(c1, c2) == [("A", CONTRACT)], "C2 content drift")
    _require(
        _git("cat-file", "-e", f"{c2}:{RESULT}", check=False).returncode != 0,
        "result existed at contract freeze",
    )


def _analyze_d20_source(raw: bytes) -> dict[str, Any]:
    try:
        tree = ast.parse(raw.decode("utf-8"))
    except (UnicodeError, SyntaxError) as exc:
        raise VerificationError(f"cannot parse D20 runner: {exc}") from exc
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    _require("run" in functions, "D20 run entrypoint absent")
    run = functions["run"]
    _require(isinstance(run, ast.FunctionDef), "D20 run must be synchronous")
    _require(len(run.body) == 2, "D20 run body drift")
    first, second = run.body
    _require(
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Call)
        and isinstance(first.value.func, ast.Name)
        and first.value.func.id == "build_plan",
        "D20 run must validate plan first",
    )
    _require(isinstance(second, ast.Raise), "D20 run is not unconditional reject")
    _require(
        isinstance(second.exc, ast.Call)
        and isinstance(second.exc.func, ast.Name)
        and second.exc.func.id == "ConsumerError",
        "D20 run rejection type drift",
    )
    loops = sum(isinstance(node, (ast.For, ast.AsyncFor, ast.While)) for node in ast.walk(tree))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    return {
        "run_unconditionally_rejects_after_plan_validation": True,
        "loop_nodes": loops,
        "scientific_kernel_reference_present": "_reduced_column" in names
        or "_reduced_column" in attributes,
        "filesystem_write_reference_present": bool(
            {"write", "pwrite", "replace", "link", "fsync"} & attributes
        ),
        "manifest_merge_reference_present": bool(
            {"heapq", "merge", "merge_complete"} & (names | attributes)
        ),
    }


def _ceil_mul_div(value: int, numerator: int, denominator: int) -> int:
    _require(type(value) is int and value >= 0, "projection value invalid")
    return (value * numerator + denominator - 1) // denominator


def recompute(contract: dict[str, Any]) -> dict[str, Any]:
    _exact(
        contract,
        {
            "schema_version",
            "contract_id",
            "analysis_class",
            "chronology",
            "source_pins",
            "d20_static_findings",
            "d18c_bounded_observation",
            "planning_projection",
            "authorization_rule",
            "authority_ceiling",
            "limitations",
        },
        "contract",
    )
    _require(contract["schema_version"] == 1, "schema drift")
    _require(contract["contract_id"] == "FH-L8-INDEPENDENT-REFERENCE-D21-READINESS-V1", "contract id drift")
    _require(
        contract["analysis_class"]
        == "FULL_53_RESOURCE_READINESS_REVIEW_NO_SCIENTIFIC_ACTION",
        "analysis class drift",
    )
    _chronology(contract)

    pins = contract["source_pins"]
    _require(isinstance(pins, list) and len(pins) == 3, "three D20 pins required")
    expected_names = [D20_RUNNER, D20_CONTRACT, D20_RESULT]
    for entry, name in zip(pins, expected_names):
        _exact(entry, {"path", "sha256", "bytes"}, "source pin")
        _require(entry["path"] == name, "source pin order/path drift")
        path = HERE / name
        raw = path.read_bytes()
        _require(len(raw) == entry["bytes"], f"D20 bytes drift: {name}")
        _require(hashlib.sha256(raw).hexdigest() == entry["sha256"], f"D20 SHA drift: {name}")

    d20_contract = load_json(HERE / D20_CONTRACT)
    d20_result = load_json(HERE / D20_RESULT)
    _require(
        d20_result["status"]
        == "VERIFIED_D20_FULL_53_CONSUMER_IMPLEMENTATION_FROZEN_NO_EXECUTION",
        "D20 status drift",
    )
    _require(d20_result["execution_authorized"] is False, "D20 unexpectedly authorized")
    _require(
        d20_contract["execution_authorization"]
        == {
            "full_53_shard_execution_authorized": False,
            "q3_rows_authorized": 0,
            "kernel_evaluations_authorized": 0,
        },
        "D20 authorization drift",
    )
    source_findings = _analyze_d20_source((HERE / D20_RUNNER).read_bytes())
    expected_findings = {
        "declarative_protocol_plan_present": True,
        "action_entrypoint_implemented": False,
        "scientific_kernel_invocation_implemented": False,
        "exact_53_shard_iteration_implemented": False,
        "per_shard_spill_publication_implemented": False,
        "resume_frontier_validation_implemented": False,
        "manifest_only_full_merge_implemented": False,
        "atomic_full_target_publication_implemented": False,
        "terminal_resource_receipt_implemented": False,
        "tiny_fixture_recovery_tests_present": False,
        "run_unconditionally_rejects_after_plan_validation": True,
    }
    _require(contract["d20_static_findings"] == expected_findings, "D20 finding contract drift")
    _require(source_findings["run_unconditionally_rejects_after_plan_validation"], "D20 rejection drift")
    _require(source_findings["loop_nodes"] == 0, "D20 unexpectedly contains action loop")
    _require(not source_findings["scientific_kernel_reference_present"], "D20 unexpectedly references kernel")
    _require(not source_findings["filesystem_write_reference_present"], "D20 unexpectedly writes action files")
    _require(not source_findings["manifest_merge_reference_present"], "D20 unexpectedly implements merge")

    observation = contract["d18c_bounded_observation"]
    expected_observation = {
        "source_records": 213099,
        "bounded_rows": 4096,
        "spill_bytes": 27801152,
        "target_bytes": 13589824,
        "elapsed_monotonic_ns": 57941070334,
        "memory_peak_bytes": 224747520,
        "process_peak_rss_bytes": 193392640,
        "zero_swap": True,
        "memory_event_failures": 0,
        "same_kernel_replay_only": True,
        "external_evidence_location_bound": True,
    }
    _require(observation == expected_observation, "D18-C observation drift")

    projection = contract["planning_projection"]
    _exact(
        projection,
        {
            "role",
            "scale_numerator",
            "scale_denominator",
            "linear_spill_bytes_ceiling",
            "linear_target_bytes_ceiling",
            "linear_elapsed_ns_ceiling",
            "margin_numerator",
            "margin_denominator",
            "margin_spill_bytes_ceiling",
            "margin_target_bytes_ceiling",
            "margin_elapsed_ns_ceiling",
            "combined_margin_spill_and_target_bytes",
            "authoritative_worst_case_disk_bound",
            "authoritative_full_runtime_bound",
            "authoritative_full_memory_bound",
        },
        "planning_projection",
    )
    n, d = observation["source_records"], observation["bounded_rows"]
    _require((projection["scale_numerator"], projection["scale_denominator"]) == (n, d), "scale drift")
    linear_spill = _ceil_mul_div(observation["spill_bytes"], n, d)
    linear_target = _ceil_mul_div(observation["target_bytes"], n, d)
    linear_elapsed = _ceil_mul_div(observation["elapsed_monotonic_ns"], n, d)
    _require(projection["linear_spill_bytes_ceiling"] == linear_spill, "spill projection drift")
    _require(projection["linear_target_bytes_ceiling"] == linear_target, "target projection drift")
    _require(projection["linear_elapsed_ns_ceiling"] == linear_elapsed, "elapsed projection drift")
    _require((projection["margin_numerator"], projection["margin_denominator"]) == (5, 4), "margin drift")
    margin_spill = _ceil_mul_div(linear_spill, 5, 4)
    margin_target = _ceil_mul_div(linear_target, 5, 4)
    margin_elapsed = _ceil_mul_div(linear_elapsed, 5, 4)
    _require(projection["margin_spill_bytes_ceiling"] == margin_spill, "spill margin drift")
    _require(projection["margin_target_bytes_ceiling"] == margin_target, "target margin drift")
    _require(projection["margin_elapsed_ns_ceiling"] == margin_elapsed, "elapsed margin drift")
    _require(
        projection["combined_margin_spill_and_target_bytes"] == margin_spill + margin_target,
        "combined planning bytes drift",
    )
    _require(projection["role"] == "NON_AUTHORITATIVE_SAMPLE_LINEAR_PLANNING_ONLY", "projection role drift")
    for key in (
        "authoritative_worst_case_disk_bound",
        "authoritative_full_runtime_bound",
        "authoritative_full_memory_bound",
    ):
        _require(projection[key] is False, f"{key} must remain false")

    rule = contract["authorization_rule"]
    expected_rule = {
        "executable_consumer_required": True,
        "tiny_fixture_success_and_resume_fault_matrix_required": True,
        "worst_case_disk_file_runtime_bounds_required": True,
        "bounded_sample_linear_projection_sufficient": False,
        "full_53_shard_execution_authorized": False,
        "scientific_action_calls": 0,
        "no_go_status": STATUS,
        "next_gate": NEXT_GATE,
    }
    _require(rule == expected_rule, "authorization rule drift")

    ceiling = contract["authority_ceiling"]
    expected_ceiling = {
        "d20_protocol_plan_admitted": True,
        "d20_executable_consumer_admitted": False,
        "full_53_resource_envelope_admitted": False,
        "full_53_shard_execution_authorized": False,
        "full_53_shard_executed": False,
        "full_q4_target_materialized": False,
        "bounded_output_admissible_as_q4_operand": False,
        "q5_executed": False,
        "degree6_remainder_bounded": False,
        "two_step_cumulative_error_bounded": False,
        "full_R100_error_bounded": False,
        "physical_reference_qualified": False,
        "hardware_result_available": False,
        "quantum_advantage_claimed": False,
        "ready_gate_eligible": False,
    }
    _require(ceiling == expected_ceiling, "authority ceiling drift")
    limitations = contract["limitations"]
    _require(isinstance(limitations, list) and len(limitations) == 6, "six limitations required")
    _require(all(isinstance(item, str) and item for item in limitations), "limitation drift")

    return {
        "schema_version": 1,
        "contract_id": contract["contract_id"],
        "status": STATUS,
        "verified": True,
        "scientific_action_calls": 0,
        "d20_static_findings": expected_findings,
        "planning_projection": dict(projection),
        "decision": {
            "d20_protocol_plan_admitted": True,
            "d20_executable_consumer_admitted": False,
            "full_53_resource_preflight_passed": False,
            "full_53_shard_execution_authorized": False,
        },
        "authority": dict(ceiling),
        "limitations": list(limitations),
        "next_gate": NEXT_GATE,
    }


def verify(contract: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = recompute(contract)
    _require(result == expected, "result differs from deterministic review")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("contract", "result"), required=True)
    args = parser.parse_args()
    try:
        contract = load_json(HERE / Path(CONTRACT).name)
        if args.mode == "contract":
            evidence = recompute(contract)
            evidence["status"] = "D21_CONTRACT_VERIFIED_NO_SCIENTIFIC_ACTION"
            evidence["verified"] = False
        else:
            evidence = verify(contract, load_json(HERE / Path(RESULT).name))
    except (OSError, VerificationError, KeyError, TypeError) as exc:
        print(
            json.dumps(
                {"status": "D21_VERIFICATION_FAILED", "verified": False, "error": str(exc)},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
