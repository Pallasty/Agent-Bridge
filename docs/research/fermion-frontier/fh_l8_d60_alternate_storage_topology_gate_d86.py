#!/usr/bin/env python3
"""Read-only D86 admission gate for an alternate storage controller."""

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
CONTRACT = HERE / "fh_l8_d60_alternate_storage_topology_gate_d86_contract.json"
RESULT = HERE / "fh_l8_d60_alternate_storage_topology_gate_d86_result.json"


class D86Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D86Error(f"object required: {path.name}")
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


def _block_inventory() -> dict[str, Mapping[str, Any]]:
    raw = subprocess.run(
        ["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,FSTYPE,UUID,LABEL,MOUNTPOINTS"],
        check=True, capture_output=True, text=True,
    ).stdout
    found: dict[str, Mapping[str, Any]] = {}

    def visit(item: Mapping[str, Any]) -> None:
        found[str(item["name"])] = item
        for child in item.get("children") or []:
            visit(child)

    for device in json.loads(raw)["blockdevices"]:
        visit(device)
    return found


def _pci_address(device: str) -> str:
    path = Path(device).resolve()
    for part in reversed(path.parts):
        if part.count(":") == 2 and "." in part:
            return part
    raise D86Error(f"PCI address absent from {path}")


def _used_bytes(path: str) -> int:
    stats = os.statvfs(path)
    return (stats.f_blocks - stats.f_bfree) * stats.f_frsize


def live_snapshot(contract: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    blocks = _block_inventory()
    disk = blocks[str(target["candidate_disk"])]
    part = blocks[str(target["candidate_partition"])]
    pci = str(target["candidate_pci_device"])
    pci_path = Path("/sys/bus/pci/devices") / pci
    irq_ids = sorted(int(path.name) for path in (pci_path / "msi_irqs").iterdir())
    mounts: dict[str, str] = {}
    output = subprocess.run(
        ["findmnt", "-rn", "-o", "TARGET,SOURCE"], check=True,
        capture_output=True, text=True,
    ).stdout
    prefix = str(target["forbidden_device_prefix"])
    for line in output.splitlines():
        mount, source = line.split(maxsplit=1)
        if source.startswith(prefix):
            mounts[mount] = source
    return {
        "candidate_disk_bytes": int(disk["size"]),
        "candidate_partition_bytes": int(part["size"]),
        "candidate_fstype": part.get("fstype"),
        "candidate_uuid": part.get("uuid"),
        "candidate_label": part.get("label"),
        "candidate_mountpoints": part.get("mountpoints") or [],
        "candidate_controller_pci": _pci_address(f"/sys/class/block/{target['candidate_disk']}/device"),
        "candidate_driver": (pci_path / "driver").resolve().name,
        "forbidden_controller_pci": _pci_address("/sys/class/nvme/nvme0/device"),
        "candidate_irqs": irq_ids,
        "candidate_irq_affinity": {
            str(irq): {
                "configured": Path(f"/proc/irq/{irq}/smp_affinity_list").read_text().strip(),
                "effective": Path(f"/proc/irq/{irq}/effective_affinity_list").read_text().strip(),
            } for irq in irq_ids
        },
        "nvme_mounts": mounts,
        "used_bytes": {path: _used_bytes(path) for path in ("/", "/Data", "/home")},
        "independent_efi_partition_present": False,
        "minimal_measurement_bundle_present": False,
    }


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-ALTERNATE-STORAGE-TOPOLOGY-GATE-D86-V1":
        raise D86Error("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D86Error("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / str(name)) != expected:
            raise D86Error(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("observation_only") is not True or any(
        value for key, value in authority.items() if key != "observation_only"
    ):
        raise D86Error("authority opened by topology gate")


def evaluate(contract: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    cpu = int(target["cpu"])
    independent = snapshot["candidate_controller_pci"] != snapshot["forbidden_controller_pci"]
    irq_excludes = bool(snapshot["candidate_irqs"]) and all(
        cpu not in parse_cpu_list(str(value["effective"]))
        for value in snapshot["candidate_irq_affinity"].values()
    )
    unmounted = not snapshot["candidate_mountpoints"]
    minimal_capacity = int(snapshot["candidate_partition_bytes"]) >= int(
        target["minimum_image_capacity_bytes"]
    )
    full_clone_bytes = sum(int(value) for value in snapshot["used_bytes"].values())
    full_clone_capacity = int(snapshot["candidate_partition_bytes"]) >= full_clone_bytes
    boot_proven = bool(snapshot["independent_efi_partition_present"])
    nvme_absent = not snapshot["nvme_mounts"]
    bundle_proven = bool(snapshot["minimal_measurement_bundle_present"])
    structural = independent and irq_excludes and unmounted and minimal_capacity
    admitted = structural and boot_proven and nvme_absent and bundle_proven
    return {
        "status": "VERIFIED_D86_ALTERNATE_STORAGE_STRUCTURAL_CANDIDATE_ONLY",
        "candidate_disk": target["candidate_disk"],
        "candidate_controller_independent": independent,
        "candidate_irq_excludes_target_cpu": irq_excludes,
        "candidate_unmounted": unmounted,
        "minimal_image_capacity_pass": minimal_capacity,
        "full_workspace_clone_required_bytes": full_clone_bytes,
        "full_workspace_clone_capacity_pass": full_clone_capacity,
        "independent_boot_path_proven": boot_proven,
        "nvme_dependency_absent": nvme_absent,
        "minimal_measurement_bundle_proven": bundle_proven,
        "structural_candidate": structural,
        "alternate_topology_admitted": admitted,
        "d82r_transaction_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "STRUCTURAL_CANDIDATE_ONLY_D86_MMC_REQUIRES_MINIMAL_BOOT_IMAGE",
        "next_gate": "OWNER_ADMIT_D87_MINIMAL_MMC_BOOT_IMAGE_PLAN",
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
