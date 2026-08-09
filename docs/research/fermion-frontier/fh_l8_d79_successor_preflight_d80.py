#!/usr/bin/env python3
"""Verify the current-master, fail-closed successor preflight after FH-L8 D79."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d79_successor_preflight_d80_contract.json"
RESULT = HERE / "fh_l8_d79_successor_preflight_d80_result.json"


class D80Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D80Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    process = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    result = load(RESULT)
    if contract.get("contract_id") != "FH-L8-D79-SUCCESSOR-PREFLIGHT-D80-V1":
        raise D80Error("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    head = git_head()
    if not head.startswith(baseline) and head != baseline:
        # Descendants are valid continuation commits; unrelated/older bases are not.
        ancestry = subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, head],
            check=False,
        )
        if ancestry.returncode != 0:
            raise D80Error("current HEAD is not descended from the frozen master baseline")

    for name, expected in contract.get("source_pins", {}).items():
        path = HERE / name
        if not path.is_file() or digest(path) != expected:
            raise D80Error(f"source pin drift: {name}")

    d79 = load(HERE / "fh_l8_runtime_scope_lock_d79_result.json")
    d60 = load(HERE / "fh_l8_runtime_numeric_proof_d60_result.json")
    d77 = load(HERE / "fh_l8_integrated_envelope_refresh_d77_result.json")
    d78 = load(HERE / "fh_l8_owner_allocator_proof_d78_result.json")
    if d79.get("decision") != "NO_GO_D79_RUNTIME_SCOPE_LOCK_INCOMPLETE":
        raise D80Error("D79 no-go boundary drift")
    if d60.get("missing_input_count") != 9 or d60.get("numeric_runtime_seconds_proven") is not False:
        raise D80Error("D60 missing-input boundary drift")
    if d77.get("unresolved_gate_count") != 4 or d78.get("missing_variable_count") != 8:
        raise D80Error("resource blocker boundary drift")

    blockers = contract.get("required_blockers")
    if result.get("blockers") != blockers or result.get("blocker_count") != len(blockers):
        raise D80Error("result blocker set drift")
    if result.get("allowed_next_unit") != contract.get("allowed_next_unit"):
        raise D80Error("next-unit drift")
    required_false = (
        "numeric_peak_memory_proven",
        "numeric_runtime_seconds_proven",
        "full53_execution_authorized",
    )
    if any(result.get(field) is not False for field in required_false):
        raise D80Error("result authority is not fail-closed")
    if any(result.get(field) != 0 for field in (
        "timing_measurements_executed",
        "external_requests_sent",
        "scientific_kernel_calls_executed",
    )):
        raise D80Error("preflight performed forbidden execution")
    return {
        "verification": "FH_L8_D79_SUCCESSOR_PREFLIGHT_D80",
        "status": result["status"],
        "baseline_commit": baseline,
        "blocker_count": result["blocker_count"],
        "blockers": blockers,
        "allowed_next_unit": result["allowed_next_unit"],
        "decision": result["decision"],
        "full53_execution_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
