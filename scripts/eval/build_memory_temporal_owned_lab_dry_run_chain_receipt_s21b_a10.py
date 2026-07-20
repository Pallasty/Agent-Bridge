#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-s21b-a9-v0.json"
A9_CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-transcript-contract-s21b-a9-v0.json"
A10_CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-chain-receipt-contract-s21b-a10-v0.json"
ROLES = ("controller", "observer", "runner", "validator")


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def load_canonical(path):
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != canonical_bytes(value):
        raise ValueError(f"noncanonical JSON: {path.name}")
    return value, raw


def receipt_digest(contract, payload):
    body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    domain = contract["receipt_digest_domain"].encode("ascii")
    return hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()


def build(transcript_dir):
    a9_contract, _ = load_canonical(A9_CONTRACT)
    a10_contract, _ = load_canonical(A10_CONTRACT)
    plan, plan_bytes = load_canonical(PLAN)
    plan_digest = hashlib.sha256(plan_bytes).hexdigest()
    if plan_digest != a9_contract["canonical_plan_sha256"]:
        raise ValueError("canonical plan digest mismatch")
    if [entry["role"] for entry in a9_contract["role_chain"]] != list(ROLES):
        raise ValueError("A9 contract role order mismatch")

    transcript_digests = []
    for role, expected in zip(ROLES, a9_contract["role_chain"], strict=True):
        packet, raw = load_canonical(transcript_dir / f"{role}.json")
        if packet["format_id"] != a9_contract["transcript_format_id"]:
            raise ValueError(f"{role}: wrong transcript format")
        for field in ("role", "next_role", "operation", "state"):
            if packet[field] != expected[field]:
                raise ValueError(f"{role}: wrong {field}")
        if packet["plan_sha256"] != plan_digest:
            raise ValueError(f"{role}: wrong plan digest")
        if packet["plan_metadata_read"] is not True or packet["real_experiment_input_read"] is not False:
            raise ValueError(f"{role}: wrong input boundary")
        if packet["execution_capability_present"] is not False or packet["live_execution_permitted"] is not False:
            raise ValueError(f"{role}: live capability asserted")
        if packet["side_effects_unlocked"] != "NONE" or packet["test_only"] is not True:
            raise ValueError(f"{role}: wrong non-live boundary")
        transcript_digests.append({"role": role, "sha256": hashlib.sha256(raw).hexdigest()})

    payload = {
        "chain_length": len(ROLES),
        "format_id": a10_contract["format_id"],
        "input_mode": a10_contract["input_mode"],
        "plan_sha256": plan_digest,
        "receipt_state": "NON_LIVE_TRANSCRIPT_CHAIN_VERIFIED",
        "role_transcript_sha256": transcript_digests,
        "side_effects_unlocked": "NONE",
        "test_only": True,
    }
    return {"chain_digest_sha256": receipt_digest(a10_contract, payload), **payload}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: builder TRANSCRIPT_DIRECTORY")
    try:
        receipt = build(pathlib.Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        sys.stderr.write("S21B_A10_DRY_RUN_CHAIN_RECEIPT_REJECTED\n")
        return 65
    sys.stdout.buffer.write(canonical_bytes(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
