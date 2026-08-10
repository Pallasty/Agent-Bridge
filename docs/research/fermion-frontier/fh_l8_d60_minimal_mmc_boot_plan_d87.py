#!/usr/bin/env python3
"""D87 closed-authority checker for the minimal MMC boot-image plan."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_minimal_mmc_boot_plan_d87_contract.json"
RESULT = HERE / "fh_l8_d60_minimal_mmc_boot_plan_d87_result.json"


class D87Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D87Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-MINIMAL-MMC-BOOT-PLAN-D87-V1":
        raise D87Error("contract identity drift")
    baseline = str(contract.get("baseline_commit", ""))
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", baseline, "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D87Error("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / str(name)) != expected:
            raise D87Error(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("plan_only") is not True or any(
        value for key, value in authority.items() if key != "plan_only"
    ):
        raise D87Error("execution authority opened by plan gate")
    if len(contract["required_payload"]) < 6 or len(contract["measurement_acceptance"]) < 6:
        raise D87Error("plan closure incomplete")


def evaluate(contract: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["target"]
    layout = contract["planned_layout"]
    preflight = contract["required_preflight"]
    usable = int(target["disk_bytes"]) - int(layout["esp_bytes"])
    layout_fits = usable >= int(layout["root_minimum_bytes"])
    preflight_complete = all(bool(value) for value in preflight.values())
    backup_gate_complete = all(bool(preflight[key]) for key in (
        "data_disposition_recorded", "backup_target_capacity_proven", "backup_image_digest_proven"
    ))
    boot_gate_complete = all(bool(preflight[key]) for key in (
        "firmware_sd_bootability_proven", "payload_manifest_digest_proven",
        "rollback_boot_entry_proven"
    ))
    plan_complete = bool(
        layout_fits and layout["partition_table"] == "gpt"
        and layout["esp_fstype"] == "vfat"
        and layout["root_fstype"] == "ext4"
        and len(contract["required_payload"]) >= 6
        and len(contract["measurement_acceptance"]) >= 6
    )
    execution_ready = plan_complete and preflight_complete
    return {
        "status": "VERIFIED_D87_MINIMAL_MMC_BOOT_PLAN_CLOSED",
        "plan_complete": plan_complete,
        "layout_fits_candidate": layout_fits,
        "planned_root_capacity_bytes": usable,
        "existing_media_backup_gate_complete": backup_gate_complete,
        "independent_boot_gate_complete": boot_gate_complete,
        "all_preflight_evidence_complete": preflight_complete,
        "execution_ready": execution_ready,
        "partition_authorized": False,
        "format_authorized": False,
        "bootloader_change_authorized": False,
        "reboot_authorized": False,
        "d82r_transaction_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "PLAN_READY_EXECUTION_BLOCKED_PENDING_D87R_PREFLIGHT_AND_OWNER_ADMISSION",
        "next_gate": "OWNER_ADMIT_D87R_MMC_BOOT_IMAGE_EXECUTION",
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(contract)


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
