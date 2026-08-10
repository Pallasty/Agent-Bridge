#!/usr/bin/env python3
"""Verify the bounded privileged D88R payload-staging receipt."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_privileged_boot_payload_gate_d88r_contract.json"
RESULT = HERE / "fh_l8_d60_privileged_boot_payload_gate_d88r_result.json"


class D88RError(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D88RError(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-PRIVILEGED-BOOT-PAYLOAD-GATE-D88R-V1":
        raise D88RError("contract identity drift")
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", contract["baseline_commit"], "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D88RError("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected:
            raise D88RError(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("receipt_verification_only") is not True or any(
        value for key, value in authority.items() if key != "receipt_verification_only"
    ):
        raise D88RError("authority opened after privileged staging")


def evaluate(contract: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    expected = contract["expected"]
    artifacts = receipt["boot_artifacts"]
    digests = len(artifacts) == 2 and all(
        len(str(value.get("sha256", ""))) == 64 for value in artifacts.values()
    )
    builder = receipt["installed_builder"]
    builder_ok = bool(
        builder["package"] == expected["builder_package"]
        and builder["version"] == expected["builder_version"]
        and Path(str(builder["path"])).is_file()
    )
    mmc_unchanged = bool(
        receipt["post_state"]["mmc_uuid"] == expected["mmc_uuid"]
        and not receipt["post_state"]["mmc_mountpoints"]
    )
    scope_clean = not bool(receipt["out_of_scope_actions_observed"])
    complete = digests and builder_ok and mmc_unchanged and scope_clean
    return {
        "status": "VERIFIED_D88R_PRIVILEGED_BOOT_PAYLOAD_PREREQUISITES_COMPLETE",
        "kernel_initramfs_digests_complete": digests,
        "root_image_builder_present": builder_ok,
        "mmc_identity_unchanged_and_unmounted": mmc_unchanged,
        "privileged_scope_clean": scope_clean,
        "boot_payload_prerequisites_complete": complete,
        "rootfs_build_authorized": False,
        "mmc_write_authorized": False,
        "bootloader_change_authorized": False,
        "reboot_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "PASS_D88R_PRIVILEGED_PREREQUISITES_STAGED_NO_IMAGE_BUILT",
        "next_gate": "OWNER_ADMIT_D89_OFFLINE_ROOTFS_STAGING_BUILD",
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(contract, load(HERE / str(contract["receipt"])))


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
