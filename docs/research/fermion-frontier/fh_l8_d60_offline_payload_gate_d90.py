#!/usr/bin/env python3
"""Verify the D90 self-contained offline payload assembly."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = HERE / "fh_l8_d60_offline_payload_gate_d90_contract.json"
RESULT = HERE / "fh_l8_d60_offline_payload_gate_d90_result.json"


class D90Error(RuntimeError):
    pass


def load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise D90Error(f"object required: {path.name}")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "FH-L8-D60-OFFLINE-PAYLOAD-GATE-D90-V1":
        raise D90Error("contract identity drift")
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", contract["baseline_commit"], "HEAD"],
        check=False, capture_output=True,
    ).returncode:
        raise D90Error("HEAD is not descended from baseline")
    for name, expected in contract["source_pins"].items():
        if digest(HERE / name) != expected:
            raise D90Error(f"source pin mismatch: {name}")
    authority = contract["authority"]
    if authority.get("receipt_verification_only") is not True or any(
        value for key, value in authority.items() if key != "receipt_verification_only"
    ):
        raise D90Error("authority opened by payload gate")


def evaluate(contract: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    req = contract["requirements"]
    payload = receipt["payload"]
    checks = receipt["static_checks"]
    manifest = bool(
        payload["manifest_all_entries_verified"]
        and int(payload["manifest_entries"]) >= int(req["minimum_manifest_entries"])
    )
    capacity = int(payload["total_bytes"]) <= int(req["maximum_payload_bytes"])
    source = bool(
        receipt["source_bundle"]["bundle_verify_pass"]
        and receipt["source_bundle"]["complete_history"]
        and receipt["source_bundle"]["head"] == req["expected_source_head"]
    )
    boot = bool(
        checks["module_tree_matches_kernel"] and checks["sdhci_pci_module_present"]
        and checks["modules_dep_present"] and checks["grub_template_has_isolation_pair"]
    )
    config = bool(checks["config_nvme_device_or_uuid_dependency_absent"])
    mmc = bool(
        receipt["mmc_post_state"]["uuid"] == req["expected_mmc_uuid"]
        and not receipt["mmc_post_state"]["mountpoints"]
    )
    assembled = manifest and capacity and source and boot and config and mmc
    materialized = assembled and not checks["root_and_esp_uuid_placeholders_unresolved"]
    return {
        "status": "VERIFIED_D90_OFFLINE_PAYLOAD_ASSEMBLY_COMPLETE",
        "manifest_integrity_pass": manifest,
        "capacity_budget_pass": capacity,
        "source_bundle_complete": source,
        "boot_artifact_set_complete": boot,
        "static_nvme_dependency_absent": config,
        "mmc_identity_unchanged_and_unmounted": mmc,
        "payload_assembly_complete": assembled,
        "boot_configuration_materialized": materialized,
        "physical_media_execution_ready": False,
        "mmc_write_authorized": False,
        "bootloader_change_authorized": False,
        "reboot_authorized": False,
        "measurement_authorized": False,
        "full53_execution_authorized": False,
        "decision": "PASS_D90_PAYLOAD_ASSEMBLED_PHYSICAL_MEDIA_AND_BOOT_PROOF_STILL_BLOCKED",
        "next_gate": "OWNER_ADMIT_D91_OFFLINE_PAYLOAD_BOOT_REHEARSAL",
    }


def verify_live(receipt: Mapping[str, Any]) -> None:
    root = Path(str(receipt["payload"]["path"]))
    if digest(root / "MANIFEST.sha256") != receipt["payload"]["manifest_sha256"]:
        raise D90Error("live manifest digest drift")
    subprocess.run(["sha256sum", "-c", "MANIFEST.sha256"], cwd=root, check=True, capture_output=True)
    bundle = root / "source/agent-bridge.bundle"
    subprocess.run(["git", "bundle", "verify", str(bundle)], check=True, capture_output=True)


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
