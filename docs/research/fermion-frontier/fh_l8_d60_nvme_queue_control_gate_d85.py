#!/usr/bin/env python3
"""Read-only D85 gate for supported NVMe PCI queue-count control."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_nvme_queue_control_gate_d85_contract.json"
RESULT = HERE / "fh_l8_d60_nvme_queue_control_gate_d85_result.json"


class D85Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D85Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_cpu_list(spec: str) -> set[int]:
    cpus: set[int] = set()
    for item in spec.strip().split(","):
        if not item:
            continue
        if "-" in item:
            lo, hi = (int(value) for value in item.split("-", 1))
            cpus.update(range(lo, hi + 1))
        else:
            cpus.add(int(item))
    return cpus


def target_irq(action: str) -> tuple[int, str]:
    for line in Path("/proc/interrupts").read_text(encoding="utf-8").splitlines():
        if line.split() and line.split()[-1] == action:
            return int(line.split(":", 1)[0]), line
    raise D85Error(f"IRQ action absent: {action}")


def live_snapshot(contract: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    irq, _ = target_irq(str(target["irq_action"]))
    params = sorted(path.name for path in Path("/sys/module/nvme/parameters").iterdir())
    queue_count = Path("/sys/class/nvme/nvme0/queue_count")
    root_source = subprocess.run(
        ["findmnt", "-no", "SOURCE", "/"], check=True, capture_output=True, text=True
    ).stdout.strip()
    cmdline = Path("/proc/cmdline").read_text(encoding="utf-8").strip().split()
    return {
        "kernel_release": os.uname().release,
        "cmdline_tokens": [
            token for token in ("irqaffinity=0-14", "isolcpus=managed_irq,15")
            if token in cmdline
        ],
        "nvme_queue_count": int(queue_count.read_text().strip()),
        "nvme_module_parameters": params,
        "queue_count_mode": queue_count.stat().st_mode & 0o777,
        "root_source": root_source,
        "target_irq": irq,
        "target_irq_action": target["irq_action"],
        "configured_affinity_list": Path(f"/proc/irq/{irq}/smp_affinity_list").read_text().strip(),
        "effective_affinity_list": Path(f"/proc/irq/{irq}/effective_affinity_list").read_text().strip(),
        "transaction_state_absent": not Path("/run/fh-l8-d82-isolation-transaction.json").exists(),
        "target_cgroup_absent": not Path("/sys/fs/cgroup/fh-l8-d60-isolated.slice").exists(),
    }


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-NVME-QUEUE-CONTROL-GATE-D85-V1":
        raise D85Error("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
        check=False, capture_output=True
    ).returncode:
        raise D85Error("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / str(name)) != expected:
            raise D85Error(f"source pin mismatch: {name}")
    if any(value for key, value in contract["authority"].items() if key != "observation_only"):
        raise D85Error("authority opened by feasibility gate")


def evaluate(contract: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    supported = set(contract["supported_total_queue_parameter_names"])
    params = set(snapshot["nvme_module_parameters"])
    target_cpu = int(target["cpu"])
    total_queue_control = bool(supported & params)
    runtime_queue_control = bool(int(snapshot["queue_count_mode"]) & 0o222)
    root_on_controller = str(snapshot["root_source"]).startswith(
        str(target["root_block_device_prefix"])
    )
    irq_conflict = target_cpu in parse_cpu_list(str(snapshot["effective_affinity_list"]))
    clean = bool(snapshot["transaction_state_absent"] and snapshot["target_cgroup_absent"])
    admissible = bool(
        total_queue_control and runtime_queue_control and not root_on_controller
        and int(snapshot["nvme_queue_count"]) <= int(target["required_max_io_queue_count"])
        and not irq_conflict and clean
    )
    return {
        "status": "VERIFIED_D85_NO_SUPPORTED_NVME_PCI_TOTAL_QUEUE_CONTROL",
        "target_irq_action": snapshot["target_irq_action"],
        "target_irq_observed": snapshot["target_irq"],
        "target_irq_number_is_stable_identity": False,
        "nvme_queue_count": snapshot["nvme_queue_count"],
        "supported_total_queue_parameter_present": total_queue_control,
        "runtime_queue_count_writable": runtime_queue_control,
        "root_filesystem_on_target_controller": root_on_controller,
        "driver_unload_admissible": False,
        "target_irq_conflict_present": irq_conflict,
        "transaction_residue_absent": clean,
        "d82r_transaction_authorized": admissible,
        "custom_kernel_authorized": False,
        "hardware_change_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "NO_GO_D85_STOCK_NVME_PCI_DRIVER_HAS_NO_TOTAL_QUEUE_COUNT_CONTROL",
        "next_gate": "OWNER_CHOOSE_CUSTOM_KERNEL_OR_DIFFERENT_HARDWARE_OR_TARGET_CONTRACT",
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(contract, contract["observed_snapshot"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    current = load(CONTRACT)
    verify_contract(current)
    print(json.dumps(evaluate(current, live_snapshot(current)) if args.live else verify(), indent=2))
