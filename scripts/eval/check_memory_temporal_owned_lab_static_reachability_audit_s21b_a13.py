#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-static-reachability-audit-contract-s21b-a13-v0.json"


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: checker AUDIT")
    contract = json.loads(CONTRACT.read_text(encoding="ascii"))
    raw = pathlib.Path(sys.argv[1]).read_bytes()
    audit = json.loads(raw)
    assert raw == canonical_bytes(audit)
    claimed = audit.pop("static_reachability_audit_digest_sha256")
    body = json.dumps(audit, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    domain = contract["verification_digest_domain"].encode("ascii")
    actual = hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()
    assert claimed == actual
    assert audit["format_id"] == contract["format_id"]
    assert audit["audit_scope"] == contract["audit_scope"]
    assert audit["audited_artifact_sha256"] == contract["artifact_sha256"]
    assert audit["denied_targets"] == contract["denied_targets"]
    assert audit["execution_capability_reachable"] is False
    assert audit["live_execution_authority_reachable"] is False
    assert audit["owner_authority_reachable"] is False
    assert audit["real_experiment_input_admission_reachable"] is False
    assert audit["result"] == "NO_STRUCTURED_UPGRADE_EDGE_REACHABLE"
    assert audit["side_effects_unlocked"] == "NONE"
    assert audit["test_only"] is True
    print("S21B_A13_STATIC_REACHABILITY_AUDIT_GATE\tPASS")


if __name__ == "__main__":
    main()
