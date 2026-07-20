#!/usr/bin/env python3
import hashlib
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
A13_CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-static-reachability-audit-contract-s21b-a13-v0.json"
A14_CONTRACT = ROOT / "docs/design/fixtures/biocortex-ab-track-b-owned-lab-proof-boundary-contract-s21b-a14-v0.json"


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


def build(audit_path):
    a14, _ = load_canonical(A14_CONTRACT)
    a13, a13_raw = load_canonical(A13_CONTRACT)
    if hashlib.sha256(a13_raw).hexdigest() != a14["a13_contract_sha256"]:
        raise ValueError("A13 contract version mismatch")
    audit, audit_raw = load_canonical(audit_path)
    expected_keys = {"audited_artifact_sha256", "audit_scope", "denied_targets", "execution_capability_reachable", "format_id", "live_execution_authority_reachable", "owner_authority_reachable", "real_experiment_input_admission_reachable", "result", "side_effects_unlocked", "static_reachability_audit_digest_sha256", "test_only"}
    if set(audit) != expected_keys:
        raise ValueError("A13 audit field set mismatch")
    claimed = audit.pop("static_reachability_audit_digest_sha256")
    if claimed != domain_digest(a13["verification_digest_domain"], audit):
        raise ValueError("A13 audit self digest mismatch")
    if audit["format_id"] != a13["format_id"] or audit["audit_scope"] != a13["audit_scope"]:
        raise ValueError("A13 audit contract mismatch")
    if audit["audited_artifact_sha256"] != a13["artifact_sha256"]:
        raise ValueError("A13 artifact binding mismatch")
    if any(audit[field] is not False for field in ("execution_capability_reachable", "live_execution_authority_reachable", "owner_authority_reachable", "real_experiment_input_admission_reachable")):
        raise ValueError("A13 audit reaches forbidden target")
    if audit["result"] != "NO_STRUCTURED_UPGRADE_EDGE_REACHABLE" or audit["side_effects_unlocked"] != "NONE" or audit["test_only"] is not True:
        raise ValueError("A13 audit boundary mismatch")
    requirements = [{"requirement": item, "status": "UNPROVEN_REQUIRED_FOR_CAPABILITY_CHANGE"} for item in a14["required_uncovered_requirements"]]
    payload = {
        "a13_audit_digest_sha256": claimed,
        "a13_audit_sha256": hashlib.sha256(audit_raw).hexdigest(),
        "capability_change_requires_all_uncovered_requirements": True,
        "execution_capability_present": False,
        "format_id": a14["format_id"],
        "input_mode": a14["input_mode"],
        "owner_authority_present": False,
        "real_experiment_input_admitted": False,
        "side_effects_unlocked": "NONE",
        "test_only": True,
        "uncovered_requirements": requirements,
        "validity_boundary": a14["validity_boundary"],
    }
    return {"proof_boundary_register_digest_sha256": domain_digest(a14["verification_digest_domain"], payload), **payload}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: builder A13_AUDIT")
    try:
        register = build(pathlib.Path(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        sys.stderr.write("S21B_A14_PROOF_BOUNDARY_REGISTER_REJECTED\n")
        return 65
    sys.stdout.buffer.write(canonical_bytes(register))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
