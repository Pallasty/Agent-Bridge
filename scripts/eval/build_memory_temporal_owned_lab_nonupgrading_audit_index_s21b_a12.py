#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
A11_CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-replay-verifier-contract-s21b-a11-v0.json"
A12_CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-nonupgrading-audit-index-contract-s21b-a12-v0.json"


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


def build(statement_path):
    a12, _ = load_canonical(A12_CONTRACT)
    a11, a11_raw = load_canonical(A11_CONTRACT)
    if hashlib.sha256(a11_raw).hexdigest() != a12["a11_contract_sha256"]:
        raise ValueError("A11 contract version mismatch")
    statement, statement_raw = load_canonical(statement_path)
    required_statement_keys = {
        "chain_digest_sha256", "format_id", "input_mode", "plan_sha256", "receipt_sha256",
        "replay_digest_sha256", "replay_outcome", "side_effects_unlocked", "test_only", "validity_boundary",
    }
    if set(statement) != required_statement_keys:
        raise ValueError("statement field set mismatch")
    claimed = statement.pop("replay_digest_sha256")
    if claimed != domain_digest(a11["replay_digest_domain"], statement):
        raise ValueError("statement self digest mismatch")
    if statement["format_id"] != a11["format_id"] or statement["input_mode"] != a11["input_mode"]:
        raise ValueError("statement contract mismatch")
    if statement["plan_sha256"] != a11["plan_sha256"]:
        raise ValueError("statement plan mismatch")
    if statement["replay_outcome"] != "STATIC_REPLAY_VERIFIED_NON_LIVE":
        raise ValueError("statement replay outcome mismatch")
    if statement["side_effects_unlocked"] != "NONE" or statement["test_only"] is not True:
        raise ValueError("statement non-live boundary mismatch")
    if statement["validity_boundary"] != a11["validity_boundary"]:
        raise ValueError("statement validity boundary mismatch")

    payload = {
        "execution_capability_present": False,
        "format_id": a12["format_id"],
        "input_mode": a12["input_mode"],
        "input_replay_digest_sha256": claimed,
        "input_replay_statement_sha256": hashlib.sha256(statement_raw).hexdigest(),
        "index_state": "STATIC_REPLAY_EVIDENCE_INDEXED_NON_UPGRADING",
        "owner_authority_present": False,
        "plan_sha256": statement["plan_sha256"],
        "real_experiment_input_admitted": False,
        "side_effects_unlocked": "NONE",
        "test_only": True,
        "validity_boundary": a12["validity_boundary"],
    }
    return {"audit_index_digest_sha256": domain_digest(a12["verification_digest_domain"], payload), **payload}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: builder A11_STATEMENT")
    try:
        index = build(pathlib.Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        sys.stderr.write("S21B_A12_NONUPGRADING_AUDIT_INDEX_REJECTED\n")
        return 65
    sys.stdout.buffer.write(canonical_bytes(index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
