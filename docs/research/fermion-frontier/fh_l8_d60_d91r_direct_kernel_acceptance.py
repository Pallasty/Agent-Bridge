#!/usr/bin/env python3
"""Close D91R by accepting only the bounded direct-kernel evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_d91r_direct_kernel_acceptance_contract.json"
RESULT = HERE / "fh_l8_d60_d91r_direct_kernel_acceptance_result.json"


class D91RError(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D91RError(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-D91R-DIRECT-KERNEL-ACCEPTANCE-V1":
        raise D91RError("contract identity drift")
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", contract["baseline_commit"], "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D91RError("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected:
            raise D91RError(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("decision_record_only") is not True or any(
        value for key, value in authority.items() if key != "decision_record_only"
    ):
        raise D91RError("authority opened by D91R acceptance")


def evaluate(receipt: Mapping[str, Any]) -> dict[str, Any]:
    accepted = receipt["accepted_evidence"]
    rejected = receipt["rejected_or_open"]
    scope = receipt["scope"]
    bounded = all(bool(value) for value in accepted.values()) and all(
        value is False for value in (scope["mmc_touched"], scope["host_rebooted"], scope["efi_variables_changed"], scope["d82r_executed"], scope["measurement_executed"])
    )
    return {
        "status": "VERIFIED_D91R_DIRECT_KERNEL_ONLY_ACCEPTED",
        "direct_kernel_evidence_accepted": bounded,
        "uefi_chain_open": not rejected["uefi_grub_kernel_chain_pass"],
        "physical_sd_boot_proven": rejected["physical_sd_boot_proven"],
        "physical_media_execution_ready": False,
        "mmc_write_authorized": False,
        "efi_variable_change_authorized": False,
        "reboot_authorized": False,
        "d82r_transaction_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "ACCEPTED_LIMITED_DIRECT_KERNEL_REHEARSAL_ONLY",
        "next_gate": "OWNER_PROVIDE_DISPOSABLE_64GB_MEDIA_OR_SAFE_BACKUP_TARGET_AND_SD_BOOT_PROOF",
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(load(HERE / str(contract["receipt"])))


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
