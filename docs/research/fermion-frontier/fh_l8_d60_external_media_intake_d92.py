#!/usr/bin/env python3
"""D92 read-only intake gate for owner-supplied media and boot evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_external_media_intake_d92_contract.json"
RESULT = HERE / "fh_l8_d60_external_media_intake_d92_result.json"


class D92Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D92Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-EXTERNAL-MEDIA-INTAKE-D92-V1":
        raise D92Error("contract identity drift")
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", contract["baseline_commit"], "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D92Error("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected:
            raise D92Error(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("observation_only") is not True or any(
        value for key, value in authority.items() if key != "observation_only"
    ):
        raise D92Error("authority opened by intake gate")


def evaluate(contract: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    req = contract["requirements"]
    disposable = bool(snapshot["eligible_disposable_media"])
    backup = bool(snapshot["eligible_backup_targets"])
    evidence = all(bool(snapshot[key]) for key in (
        "stable_device_identity_evidence", "disposable_or_data_disposition_receipt",
        "backup_capacity_and_sha256", "firmware_sd_boot_proof", "rollback_boot_entry_proof"
    ))
    mounted = bool(snapshot["candidate_mmc"]["mounted_at"])
    admitted = disposable and backup and evidence and not mounted
    blockers = []
    if mounted:
        blockers.append("CURRENT_MMC_DESKTOP_MOUNT_PRESENT_OWNER_MUST_UNMOUNT")
    if not disposable:
        blockers.append("NO_OWNER_SUPPLIED_DISPOSABLE_64GB_MEDIA")
    if not backup:
        blockers.append("NO_SAFE_BACKUP_TARGET_WITH_IMAGE_PLUS_20GB_RESERVE")
    if not snapshot["firmware_sd_boot_proof"]:
        blockers.append("FIRMWARE_SD_BOOT_PROOF_MISSING")
    return {
        "status": "VERIFIED_D92_EXTERNAL_MEDIA_INTAKE_BLOCKED",
        "disposable_media_intake_pass": disposable,
        "backup_target_intake_pass": backup,
        "required_evidence_complete": evidence,
        "current_mmc_unmounted": not mounted,
        "external_execution_admitted": admitted,
        "blockers": blockers,
        "unmount_authorized": False,
        "backup_write_authorized": False,
        "partition_authorized": False,
        "format_authorized": False,
        "firmware_change_authorized": False,
        "reboot_authorized": False,
        "d82r_transaction_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "NO_GO_D92_OWNER_MEDIA_AND_BOOT_EVIDENCE_REQUIRED",
        "next_gate": "OWNER_SUPPLY_DISPOSABLE_MEDIA_OR_SAFE_BACKUP_AND_UNMOUNT_CURRENT_MMC",
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(contract, contract["observed_snapshot"])


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
