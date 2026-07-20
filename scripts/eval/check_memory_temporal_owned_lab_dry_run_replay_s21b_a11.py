#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-replay-verifier-contract-s21b-a11-v0.json"


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: checker RECEIPT STATEMENT")
    receipt_path, statement_path = map(pathlib.Path, sys.argv[1:])
    contract = json.loads(CONTRACT.read_text(encoding="ascii"))
    raw = statement_path.read_bytes()
    statement = json.loads(raw)
    assert raw == canonical_bytes(statement)
    claimed = statement.pop("replay_digest_sha256")
    body = json.dumps(statement, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    domain = contract["replay_digest_domain"].encode("ascii")
    actual = hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()
    assert claimed == actual
    assert statement["format_id"] == contract["format_id"]
    assert statement["input_mode"] == contract["input_mode"]
    assert statement["receipt_sha256"] == hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    assert statement["replay_outcome"] == "STATIC_REPLAY_VERIFIED_NON_LIVE"
    assert statement["side_effects_unlocked"] == "NONE"
    assert statement["test_only"] is True
    assert statement["validity_boundary"] == contract["validity_boundary"]
    print("S21B_A11_STATIC_REPLAY_GATE\tPASS")


if __name__ == "__main__":
    main()
