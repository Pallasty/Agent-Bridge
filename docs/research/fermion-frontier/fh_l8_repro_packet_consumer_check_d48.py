#!/usr/bin/env python3
"""D48 static consumer check of the fixed64 reproducibility packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

D47_RESULT_PATH = HERE / "fh_l8_fixed64_repro_packet_d47_result.json"
MANIFEST_PATH = HERE / "fh_l8_fixed64_repro_packet_d47_manifest.json"

REQUIRED_RECEIPTS = {
    "d42": ("fh_l8_local_cost_survey_d42_result.json", "0bb796b3cd65b38969768540968eb64ae02d179490a704cb1d0a7b763e07aabc"),
    "d43": ("fh_l8_local_cost_survey_replay_d43_result.json", "d24b79c5f2d27fcdbbb3ff50af2b9ce549aecc1e7dbadf94290716aa5ca8882f"),
    "d44": ("fh_l8_resource_observation_d44_result.json", "0942264baaa94fc59343468b8de1a3ed08ff2f29e9e93431b5cf064990e4531d"),
    "d45": ("fh_l8_controlled_resource_replay_d45_result.json", "2fc990c6fb02492ecaaa6d010a0026456ebceb7402eba192fcbddaeb2389f79c"),
    "d46": ("fh_l8_fixed64_cost_review_d46_result.json", "48c6d1c860c200ff618535de278a3135b1ce23d2dd4fcc24c5bce0efe79cb2e9"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def consumer_check():
    if not D47_RESULT_PATH.exists():
        raise FileNotFoundError(f"missing {D47_RESULT_PATH.name}")
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"missing {MANIFEST_PATH.name}")

    result = _load(D47_RESULT_PATH)
    manifest = _load(MANIFEST_PATH)

    d47_sha = _sha256(D47_RESULT_PATH)
    manifest_sha = _sha256(MANIFEST_PATH)
    if result.get("manifest_sha256") != manifest_sha:
        raise ValueError("manifest hash mismatch in D47 result")

    expected_receipts = ["d42", "d43", "d44", "d45", "d46"]
    if result.get("receipts_verified") != expected_receipts:
        raise ValueError("D47 receipt set mismatch")
    if result.get("status") != "VERIFIED_D47_FIXED64_REPRO_PACKET":
        raise ValueError("unexpected D47 status")
    if result.get("selected_representatives") != 64 or result.get("scientific_action_calls") != 67:
        raise ValueError("D47 action scope drift")
    if result.get("packed_q3_reads") != 0:
        raise ValueError("D47 has packed-q3 reads")
    if result.get("full_53_scientific_execution_authorized"):
        raise ValueError("D47 authorizes forbidden scientific execution")
    if not result.get("full53_extrapolation_forbidden", False):
        raise ValueError("D47 full-53 extrapolation must be forbidden")
    if result.get("scientific_actions_performed_by_verifier") != 0:
        raise ValueError("D47 verifier must perform no scientific actions")
    if result.get("next_gate") != "D48_REPRO_PACKET_CONSUMER_CHECK_OR_ARCHIVE":
        raise ValueError("unexpected D47 next_gate")

    if manifest.get("receipt_files", {}).keys() != set(REQUIRED_RECEIPTS.keys()):
        raise ValueError("manifest receipt key mismatch")
    if manifest.get("schema") != "agent_bridge.fh_l8.fixed64.repro_packet.d47.v1":
        raise ValueError("manifest schema mismatch")
    if manifest.get("scope") != "D42-D46 fixed64 source-bound local-cost evidence":
        raise ValueError("manifest scope mismatch")
    if manifest.get("status", None) is not None:
        pass

    manifest_receipt_hashes = {}
    for label, (name, expected) in REQUIRED_RECEIPTS.items():
        if manifest["receipt_files"].get(label) != name:
            raise ValueError(f"manifest receipt file mismatch: {label}")
        path = HERE / manifest["receipt_files"][label]
        if not path.exists():
            raise FileNotFoundError(f"missing manifest receipt: {name}")
        actual = _sha256(path)
        manifest_receipt_hashes[label] = actual
        if actual != expected:
            raise ValueError(f"manifest pinned hash mismatch for {label}")
        if manifest["receipt_sha256"].get(label) != expected:
            raise ValueError(f"receipt sha256 field mismatch for {label}")
        if actual != manifest["receipt_sha256"][label]:
            raise ValueError(f"manifest hash verification failed for {label}")

    expected_rows_sha = "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12"
    if manifest["expected"]["structural_rows_sha256"] != expected_rows_sha:
        raise ValueError("manifest structural digest changed")
    if result["structural_rows_sha256"] != expected_rows_sha:
        raise ValueError("D47 structural digest changed")

    if manifest["expected"]["selected_representatives"] != 64:
        raise ValueError("manifest representative bound changed")
    if manifest["expected"]["scientific_action_calls"] != 67:
        raise ValueError("manifest action bound changed")

    return {
        "status": "VERIFIED_D48_REPRO_PACKET_CONSUMER_CHECK_OR_ARCHIVE",
        "next_gate": "ARCHIVE_REPRO_PACKET_D47_RESULT",
        "d47_manifest_sha256": manifest_sha,
        "d47_result_sha256": d47_sha,
        "verified_receipts": expected_receipts,
        "receipt_hashes": manifest_receipt_hashes,
        "structural_rows_sha256": expected_rows_sha,
        "selected_representatives": 64,
        "scientific_action_checks_performed": 0,
        "scientific_actions_performed_by_verifier": 0,
        "packed_q3_reads": 0,
        "full_53_scientific_execution_authorized": False,
        "full53_extrapolation_forbidden": True,
        "consumer_check_mode": "static_manifest_and_result_lock",
        "decision": "repro_packet_is_static_read_only_consistent_and_ready_for_archive",
        "archive_ready": True,
    }


if __name__ == "__main__":
    print(json.dumps(consumer_check(), sort_keys=True, separators=(",", ":")))
