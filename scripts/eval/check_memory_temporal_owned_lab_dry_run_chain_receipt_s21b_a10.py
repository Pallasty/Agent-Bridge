#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-chain-receipt-contract-s21b-a10-v0.json"
ROLES = ("controller", "observer", "runner", "validator")


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: checker TRANSCRIPT_DIRECTORY RECEIPT")
    transcript_dir, receipt_path = map(pathlib.Path, sys.argv[1:])
    contract = json.loads(CONTRACT.read_text(encoding="ascii"))
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    assert raw == canonical_bytes(receipt)
    claimed = receipt.pop("chain_digest_sha256")
    body = json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    domain = contract["receipt_digest_domain"].encode("ascii")
    actual = hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()
    assert claimed == actual
    assert receipt["format_id"] == contract["format_id"]
    assert receipt["input_mode"] == contract["input_mode"]
    assert receipt["chain_length"] == len(ROLES)
    assert receipt["receipt_state"] == "NON_LIVE_TRANSCRIPT_CHAIN_VERIFIED"
    assert receipt["side_effects_unlocked"] == "NONE"
    assert receipt["test_only"] is True
    assert [item["role"] for item in receipt["role_transcript_sha256"]] == list(ROLES)
    for item in receipt["role_transcript_sha256"]:
        assert item["sha256"] == hashlib.sha256((transcript_dir / f"{item['role']}.json").read_bytes()).hexdigest()
    print("S21B_A10_DRY_RUN_CHAIN_RECEIPT_GATE\tPASS")


if __name__ == "__main__":
    main()
