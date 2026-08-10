#!/usr/bin/env python3
"""D88 integrity gate for the offline MMC boot payload."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_offline_boot_payload_gate_d88_contract.json"
RESULT = HERE / "fh_l8_d60_offline_boot_payload_gate_d88_result.json"


class D88Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D88Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-OFFLINE-BOOT-PAYLOAD-GATE-D88-V1":
        raise D88Error("contract identity drift")
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", contract["baseline_commit"], "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D88Error("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected:
            raise D88Error(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("observation_only") is not True or any(
        value for key, value in authority.items() if key != "observation_only"
    ):
        raise D88Error("authority opened by payload gate")


def evaluate(contract: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    req = contract["requirements"]
    readable = len(manifest["readable_artifacts"]) >= int(req["readable_artifacts_minimum"])
    sources = len(manifest["d82r_source_artifacts"]) >= int(req["d82r_source_artifacts_minimum"])
    boot_hashes = all(value.get("sha256") for value in manifest["protected_boot_artifacts"].values())
    builder = bool(manifest["root_image_builder"]["complete"])
    complete = readable and sources and boot_hashes and builder
    blockers = []
    if not boot_hashes:
        blockers.append("PRIVILEGED_KERNEL_AND_INITRAMFS_SHA256_ABSENT")
    if not builder:
        blockers.append("ROOT_IMAGE_BUILDER_ABSENT")
    return {
        "status": "VERIFIED_D88_OFFLINE_BOOT_PAYLOAD_PARTIAL",
        "efi_python_artifacts_pinned": readable,
        "d82r_source_bundle_pinned": sources,
        "kernel_initramfs_digests_complete": boot_hashes,
        "root_image_builder_present": builder,
        "boot_payload_manifest_complete": complete,
        "blockers": blockers,
        "package_install_authorized": False,
        "privileged_boot_read_authorized": False,
        "root_image_build_authorized": False,
        "mmc_write_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "PARTIAL_D88_SOURCE_AND_EFI_PINNED_PRIVILEGED_STAGING_REQUIRED",
        "next_gate": "OWNER_ADMIT_D88R_PRIVILEGED_BOOT_PAYLOAD_STAGING",
    }


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    verify_contract(contract)
    manifest = load(HERE / str(contract["manifest"]))
    for path, expected in manifest["readable_artifacts"].items():
        if digest(Path(path)) != expected:
            raise D88Error(f"readable artifact drift: {path}")
    for name, expected in manifest["d82r_source_artifacts"].items():
        if digest(HERE / name) != expected:
            raise D88Error(f"D82R artifact drift: {name}")
    return evaluate(contract, manifest)


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
