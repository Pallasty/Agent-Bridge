#!/usr/bin/env python3
"""Verify the D82R reversible transaction tool and current live preflight."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "fh_l8_d60_isolation_transaction_d82r_contract.json"
RESULT = HERE / "fh_l8_d60_isolation_transaction_d82r_result.json"
TOOL = HERE / "fh_l8_d60_isolation_transaction_d82r.py"
CAPTURE = HERE / "fh_l8_d60_isolation_receipt_capture_d82r.py"


class D82RCheckError(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D82RCheckError("object required")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_tool():
    spec = importlib.util.spec_from_file_location("fh_l8_d82r_checked_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    result = load(RESULT)
    tool = load_tool()
    tool.verify_contract(contract)
    if result.get("contract_sha256") != sha256(CONTRACT):
        raise D82RCheckError("contract digest drift")
    if result.get("transaction_tool_sha256") != sha256(TOOL):
        raise D82RCheckError("transaction tool digest drift")
    if result.get("receipt_capture_sha256") != sha256(CAPTURE):
        raise D82RCheckError("receipt capture digest drift")
    backend = tool.RealBackend(Path(contract["target"]["state_file"]))
    live_plan = tool.plan(backend, contract)
    expected = {
        "status": "VERIFIED_D82R_LIVE_MANAGED_IRQ_BLOCKED_AND_ROLLED_BACK",
        "contract_sha256": sha256(CONTRACT),
        "transaction_tool_sha256": sha256(TOOL),
        "receipt_capture_sha256": sha256(CAPTURE),
        "transaction_mode_count": 5,
        "simulation_transaction_test_count": 8,
        "simulation_receipt_test_count": 3,
        "live_plan_status": live_plan["status"],
        "live_plan_blockers": live_plan["blockers"],
        "exclusive_active_irq_paths": live_plan["exclusive_active_irq_paths"],
        "root_cpuset_available": live_plan["root_cpuset_available"],
        "root_cpuset_already_enabled": live_plan["root_cpuset_already_enabled"],
        "target_cpu_online": live_plan["target_cpu_online"],
        "target_cpu_no_smt_sibling": live_plan["target_cpu_thread_siblings"] == "15",
        "irq_conflicts_present": live_plan["irq_conflict_count"] > 0,
        "live_apply_invocation_attempted": True,
        "live_apply_passed_preflight": True,
        "live_host_mutations_rolled_back": True,
        "live_irq_mutations_rolled_back": True,
        "receipt_captured": False,
        "transaction_state_absent_after_attempt": not backend.state_exists(),
        "target_cgroup_absent_after_attempt": not backend.exists(
            tool.CGROUP_ROOT / contract["target"]["parent_cgroup"]
        ),
        "residual_host_cgroup_mutations": 0,
        "residual_irq_mutations": 0,
        "timing_measurements_executed": 0,
        "scientific_kernel_calls_executed": 0,
        "numeric_runtime_seconds_proven": False,
        "full53_execution_authorized": False,
        "decision": "BLOCKED_D82R_BOOT_TIME_MANAGED_IRQ_ISOLATION_REQUIRED",
        "next_gate": "OWNER_ADMIT_D82R_BOOT_TIME_MANAGED_IRQ_RESTART_PLAN",
    }
    if result != expected:
        raise D82RCheckError("result drift")
    return expected


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
