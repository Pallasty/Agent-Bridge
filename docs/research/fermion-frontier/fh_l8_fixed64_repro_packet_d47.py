#!/usr/bin/env python3
"""D47 static verifier for the fixed64 reproducibility/archive packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "fh_l8_fixed64_repro_packet_d47_manifest.json"


def verify():
    manifest = json.loads(MANIFEST.read_text())
    receipts = {}
    for label, filename in manifest["receipt_files"].items():
        raw = (HERE / filename).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != manifest["receipt_sha256"][label]:
            raise RuntimeError(f"receipt hash mismatch: {label}")
        receipts[label] = json.loads(raw)
    expected = manifest["expected"]
    if receipts["d46"]["structural_rows_sha256"] != expected["structural_rows_sha256"]:
        raise RuntimeError("structural digest mismatch")
    for label in ("d42", "d43", "d44", "d45", "d46"):
        if receipts[label].get("packed_q3_reads") != 0:
            raise RuntimeError(f"q3 boundary mismatch: {label}")
    if receipts["d46"]["full_53_scientific_execution_authorized"]:
        raise RuntimeError("full53 boundary mismatch")
    for field in ("selected_representatives", "scientific_action_calls", "entries_min", "entries_max"):
        if receipts["d46"][field] != expected[field]:
            raise RuntimeError(f"expected field mismatch: {field}")
    if receipts["d45"]["affinity_mode"] != expected["controlled_affinity"]:
        raise RuntimeError("affinity mismatch")
    if receipts["d45"]["replay_peak_rss_kib"] != expected["controlled_replay_rss_kib"]:
        raise RuntimeError("controlled RSS receipt mismatch")
    return {
        "status": "VERIFIED_D47_FIXED64_REPRO_PACKET",
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "receipts_verified": sorted(receipts),
        "structural_rows_sha256": expected["structural_rows_sha256"],
        "selected_representatives": expected["selected_representatives"],
        "scientific_action_calls": expected["scientific_action_calls"],
        "packed_q3_reads": 0,
        "full_53_scientific_execution_authorized": False,
        "full53_extrapolation_forbidden": True,
        "scientific_actions_performed_by_verifier": 0,
        "next_gate": "D48_REPRO_PACKET_CONSUMER_CHECK_OR_ARCHIVE",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True, separators=(",", ":")))
