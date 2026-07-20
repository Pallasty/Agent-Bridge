#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-nonupgrading-audit-index-contract-s21b-a12-v0.json"


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: checker A11_STATEMENT AUDIT_INDEX")
    statement_path, index_path = map(pathlib.Path, sys.argv[1:])
    contract = json.loads(CONTRACT.read_text(encoding="ascii"))
    raw = index_path.read_bytes()
    index = json.loads(raw)
    assert raw == canonical_bytes(index)
    claimed = index.pop("audit_index_digest_sha256")
    body = json.dumps(index, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    domain = contract["verification_digest_domain"].encode("ascii")
    actual = hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()
    assert claimed == actual
    assert index["format_id"] == contract["format_id"]
    assert index["input_mode"] == contract["input_mode"]
    assert index["input_replay_statement_sha256"] == hashlib.sha256(statement_path.read_bytes()).hexdigest()
    assert index["index_state"] == "STATIC_REPLAY_EVIDENCE_INDEXED_NON_UPGRADING"
    assert index["execution_capability_present"] is False
    assert index["owner_authority_present"] is False
    assert index["real_experiment_input_admitted"] is False
    assert index["side_effects_unlocked"] == "NONE"
    assert index["test_only"] is True
    assert index["validity_boundary"] == contract["validity_boundary"]
    print("S21B_A12_NONUPGRADING_AUDIT_INDEX_GATE\tPASS")


if __name__ == "__main__":
    main()
