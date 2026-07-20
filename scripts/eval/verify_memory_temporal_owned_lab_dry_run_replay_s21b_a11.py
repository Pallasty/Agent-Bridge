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
A11_CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-replay-verifier-contract-s21b-a11-v0.json"
ROLES = ("controller", "observer", "runner", "validator")


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def load_canonical(path):
    raw = path.read_bytes()
    value = json.loads(raw)
    if raw != canonical_bytes(value):
        raise ValueError(f"noncanonical JSON: {path.name}")
    return value, raw


def domain_digest(domain_text, payload):
    body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    domain = domain_text.encode("ascii")
    return hashlib.sha256(struct.pack(">I", len(domain)) + domain + struct.pack(">Q", len(body)) + body).hexdigest()


def verify(transcript_dir, receipt_path):
    a11, _ = load_canonical(A11_CONTRACT)
    a9, a9_raw = load_canonical(A9_CONTRACT)
    a10, a10_raw = load_canonical(A10_CONTRACT)
    plan, plan_raw = load_canonical(PLAN)
    if hashlib.sha256(a9_raw).hexdigest() != a11["a9_contract_sha256"]:
        raise ValueError("A9 contract version mismatch")
    if hashlib.sha256(a10_raw).hexdigest() != a11["a10_contract_sha256"]:
        raise ValueError("A10 contract version mismatch")
    plan_digest = hashlib.sha256(plan_raw).hexdigest()
    if plan_digest != a11["plan_sha256"] or plan_digest != a9["canonical_plan_sha256"]:
        raise ValueError("plan version mismatch")
    if plan["allow_live_execution"] is not False or plan["allow_external_input"] is not False:
        raise ValueError("plan crosses non-live boundary")
    if tuple(a11["required_roles"]) != ROLES or tuple(a10["required_roles"]) != ROLES:
        raise ValueError("role set mismatch")

    receipt, receipt_raw = load_canonical(receipt_path)
    required_receipt_keys = {
        "chain_digest_sha256", "chain_length", "format_id", "input_mode", "plan_sha256",
        "receipt_state", "role_transcript_sha256", "side_effects_unlocked", "test_only",
    }
    if set(receipt) != required_receipt_keys:
        raise ValueError("receipt field set mismatch")
    claimed_chain = receipt.pop("chain_digest_sha256")
    if claimed_chain != domain_digest(a10["receipt_digest_domain"], receipt):
        raise ValueError("receipt self digest mismatch")
    if receipt["format_id"] != a10["format_id"] or receipt["input_mode"] != a10["input_mode"]:
        raise ValueError("receipt contract mismatch")
    if receipt["chain_length"] != len(ROLES) or receipt["plan_sha256"] != plan_digest:
        raise ValueError("receipt plan or length mismatch")
    if receipt["receipt_state"] != "NON_LIVE_TRANSCRIPT_CHAIN_VERIFIED":
        raise ValueError("receipt state mismatch")
    if receipt["side_effects_unlocked"] != "NONE" or receipt["test_only"] is not True:
        raise ValueError("receipt non-live boundary mismatch")
    if [item.get("role") for item in receipt["role_transcript_sha256"]] != list(ROLES):
        raise ValueError("receipt transcript order mismatch")

    for role, expected, committed in zip(ROLES, a9["role_chain"], receipt["role_transcript_sha256"], strict=True):
        packet, raw = load_canonical(transcript_dir / f"{role}.json")
        if committed != {"role": role, "sha256": hashlib.sha256(raw).hexdigest()}:
            raise ValueError(f"{role}: receipt transcript digest mismatch")
        if packet["format_id"] != a9["transcript_format_id"] or packet["plan_sha256"] != plan_digest:
            raise ValueError(f"{role}: binding mismatch")
        if any(packet[field] != expected[field] for field in ("role", "next_role", "operation", "state")):
            raise ValueError(f"{role}: chain mismatch")
        if packet["plan_metadata_read"] is not True or packet["real_experiment_input_read"] is not False:
            raise ValueError(f"{role}: input boundary mismatch")
        if packet["execution_capability_present"] is not False or packet["live_execution_permitted"] is not False:
            raise ValueError(f"{role}: execution boundary mismatch")
        if packet["side_effects_unlocked"] != "NONE" or packet["test_only"] is not True:
            raise ValueError(f"{role}: non-live boundary mismatch")

    payload = {
        "chain_digest_sha256": claimed_chain,
        "format_id": a11["format_id"],
        "input_mode": a11["input_mode"],
        "plan_sha256": plan_digest,
        "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "replay_outcome": "STATIC_REPLAY_VERIFIED_NON_LIVE",
        "side_effects_unlocked": "NONE",
        "test_only": True,
        "validity_boundary": a11["validity_boundary"],
    }
    return {"replay_digest_sha256": domain_digest(a11["replay_digest_domain"], payload), **payload}


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: verifier TRANSCRIPT_DIRECTORY RECEIPT")
    try:
        statement = verify(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        sys.stderr.write("S21B_A11_STATIC_REPLAY_REJECTED\n")
        return 65
    sys.stdout.buffer.write(canonical_bytes(statement))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
