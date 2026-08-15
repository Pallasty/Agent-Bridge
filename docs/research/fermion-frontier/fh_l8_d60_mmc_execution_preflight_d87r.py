#!/usr/bin/env python3
"""Read-only D87R preflight for the destructive MMC image transaction."""

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
CONTRACT = HERE / "fh_l8_d60_mmc_execution_preflight_d87r_contract.json"
RESULT = HERE / "fh_l8_d60_mmc_execution_preflight_d87r_result.json"


class D87RError(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D87RError(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-MMC-EXECUTION-PREFLIGHT-D87R-V1":
        raise D87RError("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D87RError("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / str(name)) != expected:
            raise D87RError(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("preflight_observation_only") is not True or any(
        value for key, value in authority.items() if key != "preflight_observation_only"
    ):
        raise D87RError("destructive authority opened by preflight")


def _free_bytes(path: str) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


def live_snapshot(contract: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target_identity"]
    raw = subprocess.run(
        ["lsblk", "-J", "-b", "-o", "NAME,SIZE,FSTYPE,UUID,SERIAL,TRAN,RO,MOUNTPOINTS"],
        check=True, capture_output=True, text=True,
    ).stdout
    devices = json.loads(raw)["blockdevices"]
    disk = next(item for item in devices if item["name"] == "mmcblk0")
    part = next(item for item in disk["children"] if item["name"] == "mmcblk0p1")
    stable = Path(str(target["stable_device"]))
    boot = subprocess.run(["efibootmgr"], check=True, capture_output=True, text=True).stdout
    current = next(line.split(":", 1)[1].strip() for line in boot.splitlines() if line.startswith("BootCurrent:"))
    return {
        "candidate_unmounted": not (part.get("mountpoints") or []),
        "candidate_read_only": bool(disk["ro"]),
        "stable_identity_matches": stable.exists() and stable.resolve() == Path("/dev/mmcblk0"),
        "backup_targets": {
            path: {"source": subprocess.run(
                ["findmnt", "-no", "SOURCE", path], check=True, capture_output=True, text=True
            ).stdout.strip(), "available_bytes": _free_bytes(path)}
            for path in ("/", "/Data", "/home")
        },
        "uefi_booted": Path("/sys/firmware/efi").is_dir(),
        "current_boot_entry": current,
        "fallback_boot_entry": "0002 Ubuntu on nvme0n1p1",
        "fallback_boot_entry_present": "Boot0002" in boot and "Ubuntu" in boot,
        "firmware_sd_bootability_proven": False,
        "existing_mmc_data_disposable": False,
        "boot_payload_manifest_complete": False,
        "backup_image_present": False,
        "backup_image_sha256_present": False,
        "backup_restore_sample_passed": False,
    }


def evaluate(contract: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    required = int(contract["safety_policy"]["backup_required_bytes"])
    eligible = sorted(
        path for path, value in snapshot["backup_targets"].items()
        if int(value["available_bytes"]) >= required
    )
    identity_gate = bool(snapshot["stable_identity_matches"] and snapshot["candidate_unmounted"])
    data_gate = bool(
        snapshot["existing_mmc_data_disposable"] or (
            eligible and snapshot["backup_image_present"]
            and snapshot["backup_image_sha256_present"]
            and snapshot["backup_restore_sample_passed"]
        )
    )
    boot_gate = bool(
        snapshot["uefi_booted"] and snapshot["fallback_boot_entry_present"]
        and snapshot["firmware_sd_bootability_proven"]
        and snapshot["boot_payload_manifest_complete"]
    )
    admitted = identity_gate and data_gate and boot_gate
    blockers = []
    if not eligible:
        blockers.append("NO_BACKUP_TARGET_MEETS_IMAGE_PLUS_20GB_RESERVE")
    if not snapshot["existing_mmc_data_disposable"] and not data_gate:
        blockers.append("EXISTING_F2FS_DATA_NOT_DISPOSED_OR_VERIFIABLY_BACKED_UP")
    if not snapshot["firmware_sd_bootability_proven"]:
        blockers.append("FIRMWARE_SD_BOOTABILITY_NOT_PROVEN")
    if not snapshot["boot_payload_manifest_complete"]:
        blockers.append("BOOT_PAYLOAD_MANIFEST_INCOMPLETE")
    return {
        "status": "VERIFIED_D87R_MMC_EXECUTION_PREFLIGHT_BLOCKED",
        "stable_identity_gate_pass": identity_gate,
        "eligible_backup_targets": eligible,
        "existing_data_gate_pass": data_gate,
        "independent_boot_gate_pass": boot_gate,
        "execution_admitted": admitted,
        "blockers": blockers,
        "backup_write_authorized": False,
        "partition_authorized": False,
        "format_authorized": False,
        "bootloader_change_authorized": False,
        "reboot_authorized": False,
        "d82r_transaction_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "NO_GO_D87R_MMC_EXECUTION_PREFLIGHT_UNSATISFIED",
        "next_gate": "OWNER_PROVIDE_DISPOSABLE_64GB_MEDIA_OR_SAFE_BACKUP_TARGET_AND_SD_BOOT_PROOF",
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
