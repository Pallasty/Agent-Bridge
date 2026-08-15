#!/usr/bin/env python3
"""Verify D91 virtual boot rehearsal, preserving its UEFI negative result."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_offline_boot_rehearsal_gate_d91_contract.json"
RESULT = HERE / "fh_l8_d60_offline_boot_rehearsal_gate_d91_result.json"


class D91Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D91Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-OFFLINE-BOOT-REHEARSAL-GATE-D91-V1":
        raise D91Error("contract identity drift")
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", contract["baseline_commit"], "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D91Error("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected:
            raise D91Error(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("receipt_verification_only") is not True or any(
        value for key, value in authority.items() if key != "receipt_verification_only"
    ):
        raise D91Error("authority opened by rehearsal gate")


def evaluate(contract: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    req = contract["requirements"]
    obs = receipt["observations"]
    direct = bool(obs["direct_kernel_boot_pass"] and obs["direct_kernel_reached_systemd_basic"])
    loader = bool(receipt["tools"]["grub_file_efi_check"])
    uefi = bool(obs["uefi_grub_kernel_chain_pass"])
    untouched = bool(obs["mmc_touched"] is False and obs["host_rebooted"] is False)
    rehearsal_complete = direct and loader and uefi and untouched
    return {
        "status": "VERIFIED_D91_DIRECT_KERNEL_PASS_UEFI_CHAIN_BLOCKED",
        "direct_kernel_boot_pass": direct,
        "uefi_loader_format_pass": loader,
        "uefi_grub_kernel_chain_pass": uefi,
        "mmc_and_host_untouched": untouched,
        "boot_rehearsal_complete": rehearsal_complete,
        "physical_sd_boot_proven": False,
        "mmc_write_authorized": False,
        "bootloader_change_authorized": False,
        "reboot_authorized": False,
        "d82r_transaction_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "PARTIAL_D91_DIRECT_BOOT_PROVEN_UEFI_GRUB_MAPPING_REQUIRES_FIX",
        "next_gate": "OWNER_ADMIT_D91R_GRUB_UEFI_REHEARSAL_FIX_OR_ACCEPT_DIRECT_KERNEL_ONLY",
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(contract, load(HERE / str(contract["receipt"])))


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
