#!/usr/bin/env python3
"""Independent D22 static identity plus live tiny-fixture verifier."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNNER_PATH = "docs/research/fermion-frontier/fh_l8_tiny_recovery_d22_runner.py"
CHECKER_PATH = "docs/research/fermion-frontier/fh_l8_tiny_recovery_d22_checker.py"
TEST_PATH = "docs/research/fermion-frontier/test_fh_l8_tiny_recovery_d22.py"
CONTRACT_PATH = "docs/research/fermion-frontier/fh_l8_tiny_recovery_d22_contract.json"
RESULT_PATH = "docs/research/fermion-frontier/fh_l8_tiny_recovery_d22_result.json"
D21_RESULT = "docs/research/fermion-frontier/fh_l8_full_resource_readiness_d21_result.json"

SPEC = importlib.util.spec_from_file_location(
    "fh_l8_d22_runner", HERE / Path(RUNNER_PATH).name
)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class VerificationError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise VerificationError(message)


def _reject_float(token: str) -> Any:
    _fail(f"floating-point JSON forbidden: {token}")


def _reject_constant(token: str) -> Any:
    _fail(f"non-finite JSON forbidden: {token}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            _fail(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_json(path: Path, maximum: int = 1_048_576) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _fail(f"cannot read {path}: {exc}")
    if not raw or len(raw) > maximum:
        _fail(f"JSON size outside bound: {path}")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_float=_reject_float,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs,
        )
    except VerificationError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"invalid JSON {path}: {exc}")
    if not isinstance(value, dict):
        _fail(f"top-level object required: {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


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
        _fail(
            f"git {' '.join(args)} failed: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return proc


def _git_text(*args: str) -> str:
    return _git(*args).stdout.decode("utf-8").strip()


def _diff(parent: str, child: str) -> list[tuple[str, str]]:
    text = _git_text("diff", "--name-status", "--no-renames", parent, child)
    return [tuple(line.split("\t", 1)) for line in text.splitlines()] if text else []


def _verify_chronology(contract: dict[str, Any]) -> None:
    chronology = contract["chronology"]
    expected_keys = {
        "evidence_baseline",
        "scaffold",
        "implementation_freeze",
        "runner_path",
        "checker_path",
        "test_path",
        "contract_path",
        "result_path",
        "result_absent_at_contract_freeze",
    }
    _require(set(chronology) == expected_keys, "chronology key drift")
    evidence_baseline = chronology["evidence_baseline"]
    scaffold = chronology["scaffold"]
    c1 = chronology["implementation_freeze"]
    for value in (evidence_baseline, scaffold, c1):
        _require(
            isinstance(value, str)
            and len(value) == 40
            and all(ch in "0123456789abcdef" for ch in value),
            "full commit id required",
        )
    _require(chronology["runner_path"] == RUNNER_PATH, "runner path drift")
    _require(chronology["checker_path"] == CHECKER_PATH, "checker path drift")
    _require(chronology["test_path"] == TEST_PATH, "test path drift")
    _require(chronology["contract_path"] == CONTRACT_PATH, "contract path drift")
    _require(chronology["result_path"] == RESULT_PATH, "result path drift")
    _require(
        chronology["result_absent_at_contract_freeze"] is True,
        "result absence required",
    )
    _require(
        _git_text("rev-parse", f"{scaffold}^") == evidence_baseline,
        "scaffold parent drift",
    )
    _require(
        _diff(evidence_baseline, scaffold)
        == [("A", CHECKER_PATH), ("A", RUNNER_PATH), ("A", TEST_PATH)],
        "scaffold must add runner/checker/test only",
    )
    _require(_git_text("rev-parse", f"{c1}^") == scaffold, "C1 parent drift")
    _require(
        _diff(scaffold, c1) == [("M", CHECKER_PATH), ("M", RUNNER_PATH)],
        "C1 refreeze must modify checker/runner only",
    )
    c2 = _git_text("log", "--diff-filter=A", "-1", "--format=%H", "--", CONTRACT_PATH)
    _require(bool(c2), "contract freeze absent")
    _require(_git_text("rev-parse", f"{c2}^") == c1, "C2 parent drift")
    _require(_diff(c1, c2) == [("A", CONTRACT_PATH)], "C2 must add contract only")
    _require(
        _git("cat-file", "-e", f"{c2}:{RESULT_PATH}", check=False).returncode
        != 0,
        "result existed at contract freeze",
    )


def _verify_implementation(contract: dict[str, Any]) -> None:
    implementation = contract["implementation"]
    _require(
        isinstance(implementation, list) and len(implementation) == 3,
        "three implementation pins required",
    )
    expected_paths = [
        Path(RUNNER_PATH).name,
        Path(CHECKER_PATH).name,
        Path(TEST_PATH).name,
    ]
    for entry, name in zip(implementation, expected_paths):
        _require(set(entry) == {"path", "bytes", "sha256"}, "pin schema drift")
        _require(entry["path"] == name, "pin order/path drift")
        path = HERE / name
        _require(path.stat().st_size == entry["bytes"], f"bytes drift: {name}")
        _require(_sha(path) == entry["sha256"], f"SHA drift: {name}")

    tree = ast.parse((HERE / Path(RUNNER_PATH).name).read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    for required in (
        "_write_shard",
        "_validate_shard",
        "_admit_frontier",
        "_merge",
        "_validate_terminal",
        "run_tiny",
        "run_production",
        "self_test",
    ):
        _require(required in functions, f"runner function absent: {required}")
    production = functions["run_production"]
    calls = [
        node.func.id
        for node in ast.walk(production)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    _require(calls == ["_validate_contract", "_fail"], "production guard drift")


def recompute(contract: dict[str, Any]) -> dict[str, Any]:
    expected_keys = {
        "schema_version",
        "contract_id",
        "analysis_class",
        "chronology",
        "implementation",
        "fixture",
        "protocol",
        "production_authority",
        "expected",
        "limitations",
    }
    _require(set(contract) == expected_keys, "contract key drift")
    RUNNER._validate_contract(contract)
    _verify_chronology(contract)
    _verify_implementation(contract)
    d21 = load_json(HERE / Path(D21_RESULT).name)
    _require(
        d21["status"]
        == "NO_GO_D21_FULL_53_RESOURCE_AUTHORIZATION_EXECUTABLE_IMPLEMENTATION_ABSENT",
        "D21 source status drift",
    )
    live = RUNNER.self_test(contract)
    expected = contract["expected"]
    _require(
        expected
        == {
            "status": "VERIFIED_D22_TINY_FIXTURE_SUCCESS_RESUME_AND_FAULT_MATRIX",
            "target_records": live["fixture"]["clean_target"]["bytes"]
            // RUNNER.SPILL.size,
            "target_bytes": live["fixture"]["clean_target"]["bytes"],
            "target_sha256": live["fixture"]["clean_target"]["sha256"],
            "terminal_receipt_sha256": live["fixture"][
                "clean_terminal_receipt_sha256"
            ],
            "fault_codes": live["fault_matrix"],
        },
        "expected live evidence drift",
    )
    _require(
        live["fixture"]["clean_target"] == live["fixture"]["resumed_target"],
        "clean/resumed target identity drift",
    )
    _require(
        live["fixture"]["clean_terminal_receipt_sha256"]
        == live["fixture"]["resumed_terminal_receipt_sha256"],
        "clean/resumed terminal identity drift",
    )
    _require(
        live["production_authority"]
        == {
            "production_checkpoint_reads": 0,
            "production_q3_rows_acted": 0,
            "production_scientific_kernel_calls": 0,
            "full_53_shard_execution_authorized": False,
            "full_q4_target_materialized": False,
        },
        "production authority drift",
    )
    limitations = contract["limitations"]
    _require(
        isinstance(limitations, list)
        and len(limitations) == 5
        and all(isinstance(item, str) and item for item in limitations),
        "limitations drift",
    )
    return {
        "schema_version": 1,
        "contract_id": contract["contract_id"],
        "status": live["status"],
        "verified": True,
        "live_tiny_fixture_replayed": True,
        "fixture": live["fixture"],
        "fault_matrix": live["fault_matrix"],
        "production_authority": live["production_authority"],
        "authority": {
            "tiny_fixture_executable_protocol_verified": True,
            "tiny_fixture_exact_frontier_resume_verified": True,
            "tiny_fixture_fault_matrix_verified": True,
            "production_scientific_kernel_bound": False,
            "production_worst_case_resource_bound": False,
            "full_53_shard_execution_authorized": False,
            "full_53_shard_executed": False,
            "full_q4_target_materialized": False,
            "q5_executed": False,
            "ready_gate_eligible": False,
        },
        "limitations": list(limitations),
        "next_gate": live["next_gate"],
    }


def verify(contract: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    evidence = recompute(contract)
    _require(result == evidence, "result differs from live deterministic evidence")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("contract", "result"), required=True)
    args = parser.parse_args()
    try:
        contract = load_json(HERE / Path(CONTRACT_PATH).name)
        if args.mode == "contract":
            evidence = recompute(contract)
            evidence["status"] = "D22_CONTRACT_AND_LIVE_TINY_FIXTURE_VERIFIED"
            evidence["verified"] = False
        else:
            evidence = verify(
                contract, load_json(HERE / Path(RESULT_PATH).name)
            )
    except (
        OSError,
        VerificationError,
        RUNNER.RunnerError,
        KeyError,
        TypeError,
    ) as exc:
        print(
            json.dumps(
                {
                    "status": "D22_VERIFICATION_FAILED",
                    "verified": False,
                    "error": str(exc),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(evidence, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
