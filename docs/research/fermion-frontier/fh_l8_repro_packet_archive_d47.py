#!/usr/bin/env python3
"""D48 final archive step for the fixed64 reproducibility packet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

D47_RESULT_PATH = HERE / "fh_l8_fixed64_repro_packet_d47_result.json"
D47_MANIFEST_PATH = HERE / "fh_l8_fixed64_repro_packet_d47_manifest.json"
D48_CHECK_PATH = HERE / "fh_l8_repro_packet_consumer_check_d48_result.json"
ARCHIVE_FILES = [
    "fh_l8_local_cost_survey_d42_result.json",
    "fh_l8_local_cost_survey_replay_d43_result.json",
    "fh_l8_resource_observation_d44_result.json",
    "fh_l8_controlled_resource_replay_d45_result.json",
    "fh_l8_fixed64_cost_review_d46_result.json",
    "fh_l8_fixed64_repro_packet_d47_manifest.json",
    "fh_l8_fixed64_repro_packet_d47_result.json",
    "fh_l8_repro_packet_consumer_check_d48_result.json",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path.name}")


def archive():
    for name in (D47_RESULT_PATH, D47_MANIFEST_PATH, D48_CHECK_PATH):
        _require_file(name)

    d47 = json.loads(D47_RESULT_PATH.read_text())
    d48 = json.loads(D48_CHECK_PATH.read_text())
    if d47.get("status") != "VERIFIED_D47_FIXED64_REPRO_PACKET":
        raise ValueError("D47 result status invalid")
    if d47.get("next_gate") != "D48_REPRO_PACKET_CONSUMER_CHECK_OR_ARCHIVE":
        raise ValueError("D47 next_gate invalid")
    if d48.get("status") != "VERIFIED_D48_REPRO_PACKET_CONSUMER_CHECK_OR_ARCHIVE":
        raise ValueError("D48 check status invalid")
    if d48.get("next_gate") != "ARCHIVE_REPRO_PACKET_D47_RESULT":
        raise ValueError("D48 next_gate invalid")
    if d47.get("selected_representatives") != 64 or d47.get("scientific_action_calls") != 67:
        raise ValueError("D47 action scope invalid")
    if d48.get("scientific_actions_performed_by_verifier") != 0:
        raise ValueError("D48 verifier should perform no scientific actions")
    if d47.get("scientific_actions_performed_by_verifier") != 0:
        raise ValueError("D47 verifier should perform no scientific actions")
    if d47.get("full_53_scientific_execution_authorized"):
        raise ValueError("full-53 should remain unauthorized")
    if d47.get("packed_q3_reads") != 0:
        raise ValueError("packed-q3 reads should stay zero")

    if d47.get("manifest_sha256") != _sha256(D47_MANIFEST_PATH):
        raise ValueError("D47 manifest hash mismatch")
    if d48.get("d47_result_sha256") != _sha256(D47_RESULT_PATH):
        raise ValueError("D48 lock hash mismatch")
    if d48.get("d47_manifest_sha256") != _sha256(D47_MANIFEST_PATH):
        raise ValueError("D48 manifest lock mismatch")
    if d47.get("structural_rows_sha256") != "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12":
        raise ValueError("structural digest mismatch")
    if d47.get("structural_rows_sha256") != d48.get("structural_rows_sha256"):
        raise ValueError("structural digest mismatch across gates")

    return {
        "status": "ARCHIVED_D48_REPRO_PACKET_D47_RESULT",
        "next_gate": "FH_L8_REPRO_PACKET_D47_ARCHIVE_CLOSED",
        "archive_bundle": {
            "bundle_id": "FH-L8-D47-REPRO-PACKET-ARCHIVE-V1",
            "records": len(ARCHIVE_FILES),
            "artifact_root": "docs/research/fermion-frontier",
            "sha256": {name: _sha256(HERE / name) for name in ARCHIVE_FILES},
            "result_path": "docs/research/fermion-frontier/fh_l8_repro_packet_consumer_check_d48_result.json",
            "manifest_path": "docs/research/fermion-frontier/fh_l8_fixed64_repro_packet_d47_manifest.json",
            "source_bound_scope": "fixed64_source_bound_fixture_only",
            "selected_representatives": 64,
            "resource_gate_readiness": "stabilized",
            "scientific_action_checks": 0,
            "packed_q3_reads": 0,
            "full_53_scientific_execution_authorized": False,
            "full53_extrapolation_forbidden": True,
            "archival_decision": "no_full_53_authority_only_static_reproducibility_lock",
        },
    }


if __name__ == "__main__":
    print(json.dumps(archive(), sort_keys=True, separators=(",", ":")))
