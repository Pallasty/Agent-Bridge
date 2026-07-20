#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-proof-boundary-contract-s21b-a14-v0.json"


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: checker A13_AUDIT REGISTER")
    audit_path, register_path = map(pathlib.Path, sys.argv[1:])
    contract = json.loads(CONTRACT.read_text(encoding="ascii"))
    raw = register_path.read_bytes()
    register = json.loads(raw)
    assert raw == canonical_bytes(register)
    claimed = register.pop("proof_boundary_register_digest_sha256")
    body = json.dumps(register, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    domain = contract["verification_digest_domain"].encode("ascii")
    actual = hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()
    assert claimed == actual
    assert register["format_id"] == contract["format_id"]
    assert register["input_mode"] == contract["input_mode"]
    assert register["a13_audit_sha256"] == hashlib.sha256(audit_path.read_bytes()).hexdigest()
    assert register["capability_change_requires_all_uncovered_requirements"] is True
    assert register["execution_capability_present"] is False
    assert register["owner_authority_present"] is False
    assert register["real_experiment_input_admitted"] is False
    assert register["side_effects_unlocked"] == "NONE"
    assert register["test_only"] is True
    assert register["validity_boundary"] == contract["validity_boundary"]
    assert [entry["requirement"] for entry in register["uncovered_requirements"]] == contract["required_uncovered_requirements"]
    assert all(entry["status"] == "UNPROVEN_REQUIRED_FOR_CAPABILITY_CHANGE" for entry in register["uncovered_requirements"])
    print("S21B_A14_PROOF_BOUNDARY_REGISTER_GATE\tPASS")


if __name__ == "__main__":
    main()
