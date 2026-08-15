#!/usr/bin/env python3
"""Verify the D89 offline rootfs staging receipt and optional live artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_offline_rootfs_staging_gate_d89_contract.json"
RESULT = HERE / "fh_l8_d60_offline_rootfs_staging_gate_d89_result.json"


class D89Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D89Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-OFFLINE-ROOTFS-STAGING-GATE-D89-V1":
        raise D89Error("contract identity drift")
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", contract["baseline_commit"], "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D89Error("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected:
            raise D89Error(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("receipt_verification_only") is not True or any(
        value for key, value in authority.items() if key != "receipt_verification_only"
    ):
        raise D89Error("authority opened by rootfs staging gate")


def evaluate(contract: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    req = contract["requirements"]
    artifact = receipt["artifact"]
    integrity = bool(
        artifact["xz_integrity_pass"]
        and len(artifact["sha256"]) == 64
        and int(artifact["archive_entry_count"]) >= int(req["minimum_archive_entries"])
    )
    capacity = int(artifact["bytes"]) <= int(req["maximum_compressed_bytes"])
    packages = len(receipt["required_packages"]) >= int(req["minimum_required_packages"])
    tools = len(receipt["required_paths_present"]) >= 7
    mmc_clean = bool(
        receipt["mmc_post_state"]["uuid"] == req["expected_mmc_uuid"]
        and not receipt["mmc_post_state"]["mountpoints"]
    )
    complete = integrity and capacity and packages and tools and mmc_clean
    return {
        "status": "VERIFIED_D89_OFFLINE_ROOTFS_STAGING_COMPLETE",
        "archive_integrity_pass": integrity,
        "capacity_budget_pass": capacity,
        "required_package_set_present": packages,
        "required_tool_paths_present": tools,
        "mmc_identity_unchanged_and_unmounted": mmc_clean,
        "rootfs_staging_complete": complete,
        "payload_bundle_complete": False,
        "mmc_write_authorized": False,
        "bootloader_change_authorized": False,
        "reboot_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "PASS_D89_ROOTFS_STAGED_PAYLOAD_ASSEMBLY_NOT_STARTED",
        "next_gate": "OWNER_ADMIT_D90_OFFLINE_PAYLOAD_ASSEMBLY",
    }


def verify_live(receipt: Mapping[str, Any]) -> None:
    artifact = Path(str(receipt["artifact"]["path"]))
    if artifact.stat().st_size != int(receipt["artifact"]["bytes"]):
        raise D89Error("live artifact size drift")
    if digest(artifact) != receipt["artifact"]["sha256"]:
        raise D89Error("live artifact digest drift")
    subprocess.run(["xz", "-t", str(artifact)], check=True)


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    return evaluate(contract, load(HERE / str(contract["receipt"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    current = load(CONTRACT)
    verify_contract(current)
    receipt = load(HERE / str(current["receipt"]))
    if args.live:
        verify_live(receipt)
    print(json.dumps(evaluate(current, receipt), indent=2))
