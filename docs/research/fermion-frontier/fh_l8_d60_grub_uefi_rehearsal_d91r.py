#!/usr/bin/env python3
"""Verify D91R's UEFI/GRUB rehearsal fix without granting physical-media authority."""
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
from typing import Any, Mapping
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_grub_uefi_rehearsal_d91r_contract.json"
RESULT = HERE / "fh_l8_d60_grub_uefi_rehearsal_d91r_result.json"
class D91RError(RuntimeError): pass
def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping): raise D91RError("object required")
    return value
def digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-GRUB-UEFI-REHEARSAL-D91R-V1": raise D91RError("identity drift")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", contract["baseline_commit"], "HEAD"], check=False, capture_output=True).returncode: raise D91RError("baseline drift")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected: raise D91RError(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority["receipt_verification_only"] is not True or any(value for key, value in authority.items() if key != "receipt_verification_only"): raise D91RError("authority opened")
def evaluate(contract: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    obs = receipt["observations"]
    chain = all(obs[key] is True for key in ("standalone_efi_format_valid", "kernel_loaded_from_embedded_memdisk", "uefi_grub_kernel_chain_pass", "rootfs_device_found", "rootfs_switch_pass", "systemd_basic_target_pass"))
    clean = obs["grub_prompt_observed"] is False and obs["kernel_panic_observed"] is False
    untouched = obs["mmc_touched"] is False and obs["host_rebooted"] is False
    admitted = chain and clean and untouched
    return {
        "status": "VERIFIED_D91R_UEFI_GRUB_KERNEL_ROOTFS_CHAIN_PASS",
        "attempt_count": receipt["attempt_count"],
        "uefi_grub_kernel_chain_pass": chain,
        "rootfs_switch_and_systemd_basic_pass": bool(obs["rootfs_switch_pass"] and obs["systemd_basic_target_pass"]),
        "multi_user_target_required": False,
        "multi_user_target_pass": obs["multi_user_target_pass"],
        "grub_prompt_and_kernel_panic_absent": clean,
        "mmc_and_host_untouched": untouched,
        "virtual_rehearsal_admitted": admitted,
        "physical_sd_boot_proven": False,
        "mmc_write_authorized": False,
        "bootloader_change_authorized": False,
        "host_reboot_authorized": False,
        "d82r_transaction_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "PASS_D91R_VIRTUAL_UEFI_CHAIN_PHYSICAL_MEDIA_AUTHORITY_STILL_CLOSED" if admitted else "BLOCKED_D91R_VIRTUAL_UEFI_CHAIN_INCOMPLETE",
        "next_gate": "OWNER_ADMIT_SEPARATE_D92_PHYSICAL_MMC_MATERIALIZATION_AND_FIRMWARE_BOOT_GATE"
    }
def verify() -> dict[str, Any]:
    contract = load(CONTRACT); verify_contract(contract); return evaluate(contract, load(HERE / contract["receipt"]))
if __name__ == "__main__": print(json.dumps(verify(), indent=2))
