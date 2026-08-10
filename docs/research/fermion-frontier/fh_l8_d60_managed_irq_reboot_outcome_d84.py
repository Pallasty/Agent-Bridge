#!/usr/bin/env python3
"""Validate the D84 post-reboot managed-IRQ outcome without changing the host."""

from __future__ import annotations

import hashlib
import json
import argparse
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_managed_irq_reboot_outcome_d84_contract.json"
RESULT = HERE / "fh_l8_d60_managed_irq_reboot_outcome_d84_result.json"


class D84Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D84Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_cpu_list(spec: str) -> set[int]:
    cpus: set[int] = set()
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            lo, hi = (int(value) for value in item.split("-", 1))
            if lo > hi:
                raise D84Error("descending CPU range")
            cpus.update(range(lo, hi + 1))
        else:
            cpus.add(int(item))
    return cpus


def live_snapshot() -> dict[str, Any]:
    cmdline = Path("/proc/cmdline").read_text(encoding="utf-8").strip().split()
    cgroup_target = Path("/sys/fs/cgroup/fh-l8-d60-isolated.slice")
    irq_line = next(
        line for line in Path("/proc/interrupts").read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("175:")
    )
    return {
        "kernel_release": os.uname().release,
        "cmdline_token_present": "isolcpus=managed_irq,15" in cmdline,
        "target_irq_action": irq_line.split()[-1],
        "nvme_queue_count": int(Path("/sys/class/nvme/nvme0/queue_count").read_text().strip()),
        "configured_affinity_list": Path("/proc/irq/175/smp_affinity_list").read_text().strip(),
        "effective_affinity_list": Path("/proc/irq/175/effective_affinity_list").read_text().strip(),
        "target_cpu_thread_siblings_list": Path(
            "/sys/devices/system/cpu/cpu15/topology/thread_siblings_list"
        ).read_text().strip(),
        "target_cpu_online": 15 in parse_cpu_list(Path("/sys/devices/system/cpu/online").read_text().strip()),
        "transaction_state_absent": not Path("/run/fh-l8-d82-isolation-transaction.json").exists(),
        "target_cgroup_absent": not cgroup_target.exists(),
        "noninteractive_host_admin_available": subprocess.run(
            ["sudo", "-n", "true"], check=False, capture_output=True
        ).returncode == 0,
    }


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-MANAGED-IRQ-REBOOT-OUTCOME-D84-V1":
        raise D84Error("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
                      check=False, capture_output=True).returncode:
        raise D84Error("HEAD is not descended from baseline")
    pins = contract.get("source_pins")
    if not isinstance(pins, Mapping) or len(pins) != 5:
        raise D84Error("exact source pins required")
    for name, expected in pins.items():
        if digest(HERE / str(name)) != expected:
            raise D84Error(f"source pin mismatch: {name}")
    authority = contract["authority"]
    forbidden = ("runtime_lock_precommitted", "measurement_authorized",
                 "numeric_runtime_seconds_proven", "full53_execution_authorized")
    if any(authority[name] for name in forbidden):
        raise D84Error("authority opened by observation packet")


def evaluate(contract: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    rule = contract["reboot_acceptance_rule"]
    target = int(rule["target_cpu"])
    configured_excludes = target not in parse_cpu_list(str(snapshot["configured_affinity_list"]))
    effective_excludes = target not in parse_cpu_list(str(snapshot["effective_affinity_list"]))
    cmdline_ok = snapshot.get("cmdline_token_present") is True
    action_ok = snapshot.get("target_irq_action") == rule["target_irq_action"]
    acceptance = bool(cmdline_ok and action_ok and configured_excludes and effective_excludes)
    clean = snapshot.get("transaction_state_absent") is True and snapshot.get("target_cgroup_absent") is True
    return {
        "status": "VERIFIED_D84_REBOOT_PARAMETER_PRESENT_MANAGED_IRQ_NOT_ISOLATED",
        "source_pin_count": len(contract["source_pins"]),
        "boot_parameter_admitted": cmdline_ok,
        "target_irq_identity_admitted": action_ok,
        "configured_affinity_excludes_target": configured_excludes,
        "effective_affinity_excludes_target": effective_excludes,
        "reboot_acceptance_admitted": acceptance,
        "transaction_residue_absent": clean,
        "fresh_d82r_receipt_authorized": acceptance and clean,
        "runtime_lock_precommitted": False,
        "measurement_authorized": False,
        "timing_measurements_executed": 0,
        "scientific_kernel_calls_executed": 0,
        "numeric_runtime_seconds_proven": False,
        "full53_execution_authorized": False,
        "decision": ("READY_D84_FOR_FRESH_D82R_TRANSACTION"
                     if acceptance and clean else
                     "NO_GO_D84_MANAGED_IRQ_BOOT_PARAMETER_INEFFECTIVE_FOR_NVME0Q15"),
        "next_gate": ("HOST_ADMIN_D82R_APPLY_VERIFY_RECEIPT_ROLLBACK"
                      if acceptance and clean else
                      "APPLY_IRQAFFINITY_HOUSEKEEPING_PLUS_MANAGED_IRQ_BOOT_PLAN_THEN_RESTART")
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(contract, contract["observed_snapshot"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="evaluate a fresh read-only host snapshot")
    args = parser.parse_args()
    if args.live:
        current_contract = load(CONTRACT)
        verify_contract(current_contract)
        print(json.dumps(evaluate(current_contract, live_snapshot()), indent=2))
    else:
        print(json.dumps(verify(), indent=2))
