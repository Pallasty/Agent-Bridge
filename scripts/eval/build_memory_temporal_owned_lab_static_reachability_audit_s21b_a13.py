#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-static-reachability-audit-contract-s21b-a13-v0.json"
ARTIFACTS = {
    "a9_plan": ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-s21b-a9-v0.json",
    "a9_contract": ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-plan-transcript-contract-s21b-a9-v0.json",
    "a10_contract": ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-chain-receipt-contract-s21b-a10-v0.json",
    "a11_contract": ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-dry-run-replay-verifier-contract-s21b-a11-v0.json",
    "a12_contract": ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-nonupgrading-audit-index-contract-s21b-a12-v0.json",
}


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


def build():
    contract, _ = load_canonical(CONTRACT)
    loaded = {}
    for name, path in ARTIFACTS.items():
        value, raw = load_canonical(path)
        if hashlib.sha256(raw).hexdigest() != contract["artifact_sha256"][name]:
            raise ValueError(f"{name}: raw-byte binding mismatch")
        loaded[name] = value
    plan = loaded["a9_plan"]
    if any(plan[field] is not False for field in ("allow_device_access", "allow_external_input", "allow_live_execution", "allow_network", "allow_paid_resources")):
        raise ValueError("A9 plan crosses non-live boundary")
    required = {
        "a9_contract": {"contract_authorizes_live_execution": False, "execution_capability_present": False, "real_experiment_input_admitted": False, "side_effects_unlocked": "NONE"},
        "a10_contract": {"contract_authorizes_live_execution": False, "execution_capability_present": False, "real_experiment_input_admitted": False, "side_effects_unlocked": "NONE"},
        "a11_contract": {"execution_capability_present": False, "owner_authority_present": False, "real_experiment_input_admitted": False, "side_effects_unlocked": "NONE", "verification_authorizes_live_execution": False},
        "a12_contract": {"audit_index_authorizes_live_execution": False, "execution_capability_present": False, "owner_authority_present": False, "real_experiment_input_admitted": False, "side_effects_unlocked": "NONE"},
    }
    for name, expected in required.items():
        if loaded[name].get("nonclaims") != expected:
            raise ValueError(f"{name}: nonclaim boundary mismatch")
    payload = {
        "audited_artifact_sha256": contract["artifact_sha256"],
        "audit_scope": contract["audit_scope"],
        "denied_targets": contract["denied_targets"],
        "execution_capability_reachable": False,
        "format_id": contract["format_id"],
        "live_execution_authority_reachable": False,
        "owner_authority_reachable": False,
        "real_experiment_input_admission_reachable": False,
        "result": "NO_STRUCTURED_UPGRADE_EDGE_REACHABLE",
        "side_effects_unlocked": "NONE",
        "test_only": True,
    }
    return {"static_reachability_audit_digest_sha256": domain_digest(contract["verification_digest_domain"], payload), **payload}


def main():
    if len(sys.argv) != 1:
        raise SystemExit("usage: auditor")
    try:
        audit = build()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        sys.stderr.write("S21B_A13_STATIC_REACHABILITY_AUDIT_REJECTED\n")
        return 65
    sys.stdout.buffer.write(canonical_bytes(audit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
