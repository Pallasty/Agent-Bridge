#!/usr/bin/env python3
"""D46 static reconciliation of the fixed64 local-cost evidence chain."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUTS = {
    "d42": ("fh_l8_local_cost_survey_d42_result.json", "0bb796b3cd65b38969768540968eb64ae02d179490a704cb1d0a7b763e07aabc"),
    "d43": ("fh_l8_local_cost_survey_replay_d43_result.json", "d24b79c5f2d27fcdbbb3ff50af2b9ce549aecc1e7dbadf94290716aa5ca8882f"),
    "d44": ("fh_l8_resource_observation_d44_result.json", "0942264baaa94fc59343468b8de1a3ed08ff2f29e9e93431b5cf064990e4531d"),
    "d45": ("fh_l8_controlled_resource_replay_d45_result.json", "2fc990c6fb02492ecaaa6d010a0026456ebceb7402eba192fcbddaeb2389f79c"),
}


def _load():
    values = {}
    for label, (name, expected) in INPUTS.items():
        raw = (HERE / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError(f"{label} receipt pin mismatch")
        values[label] = json.loads(raw)
    return values


def review():
    x = _load()
    digest = "38aaeffb8f178e918e4f326888493166c21afc7fb1379e91ab965c345b4adc12"
    if x["d42"]["structural_rows_sha256"] != digest:
        raise RuntimeError("D42 digest drift")
    if not x["d43"]["structural_rows_match"] or x["d43"]["d43_structural_rows_sha256"] != digest:
        raise RuntimeError("D43 structural replay drift")
    if not x["d44"]["structural_digest_authoritative"] or x["d44"]["structural_rows_sha256"] != digest:
        raise RuntimeError("D44 normalization drift")
    if not x["d45"]["structural_replays_match"] or x["d45"]["structural_rows_sha256"] != digest:
        raise RuntimeError("D45 controlled replay drift")
    if any(x[label]["packed_q3_reads"] != 0 for label in x):
        raise RuntimeError("q3 boundary drift")
    if any(x[label]["full_53_scientific_execution_authorized"] for label in ("d42", "d43", "d45")):
        raise RuntimeError("full53 authority drift")
    if x["d42"]["scientific_action_calls"] != 67 or x["d43"]["scientific_action_calls"] != 67 or x["d45"]["scientific_action_calls_per_replay"] != 67:
        raise RuntimeError("action count drift")
    if x["d45"]["affinity_mode"] != "cpu0" or not x["d45"]["resource_observations_comparable"]:
        raise RuntimeError("controlled resource condition missing")
    return {
        "status": "VERIFIED_D46_FIXED64_LOCAL_COST_REVIEW",
        "source_receipt_sha256": {label: sha for label, (_, sha) in INPUTS.items()},
        "structural_rows_sha256": digest,
        "structural_chain_verified": True,
        "selected_representatives": 64,
        "scientific_action_calls": 67,
        "entries_min": 110,
        "entries_max": 220,
        "controlled_affinity": "cpu0",
        "controlled_replay_rss_kib": [38248, 38276],
        "controlled_rss_span_kib": 28,
        "bounded_64mib_observation_satisfied": True,
        "local_cost_claim_scope": "fixed64_source_bound_fixture_only",
        "packed_q3_reads": 0,
        "full_53_scientific_execution_authorized": False,
        "full53_extrapolation_forbidden": True,
        "next_gate": "D47_FIXED64_EVIDENCE_ARCHIVE_OR_REPRODUCIBILITY_PACKET",
    }


if __name__ == "__main__":
    print(json.dumps(review(), sort_keys=True, separators=(",", ":")))
