#!/usr/bin/env python3
"""Read-only Git validator for the P11-G7 authorization review."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT = HERE / "majorana_certificate_p11_g7_remedial_authorization_review_contract.json"
RECORD = HERE / "majorana_certificate_p11_g7_remedial_authorization_review_record.json"
PARENT = "c6ebd524a008e069281d57873bdb52affacca092"
E1R_RECORD = "docs/research/fermion-frontier/majorana_certificate_p11e1r_remedial_acquisition_governance_design_record.json"


class ValidationError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def load(path: Path, require_canonical: bool = False) -> Any:
    raw = path.read_bytes()
    value = json.loads(raw)
    if require_canonical and raw != canonical(value):
        raise ValidationError(f"noncanonical JSON: {path.name}")
    return value


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True).stdout


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    record = load(RECORD, require_canonical=True)
    if git("rev-parse", "HEAD").decode().strip() != PARENT:
        raise ValidationError("G7 must be validated before its result commit")
    if contract["required_direct_parent_commit"] != PARENT or record["parent_commit"] != PARENT:
        raise ValidationError("direct-parent pin drift")
    e1r_raw = git("show", f"{PARENT}:{E1R_RECORD}")
    custody = contract["P11_E1R_custody"]
    if sha256(e1r_raw) != custody["record_raw_sha256"]:
        raise ValidationError("P11-E1R custody mismatch")
    e1r = json.loads(e1r_raw)
    if e1r["disposition"] != custody["expected_disposition"] or e1r["precondition_count"] != 5:
        raise ValidationError("P11-E1R design semantics drift")
    checks = contract["readiness_review"]
    if len(checks) != 6 or any(row["status"] != "PASS" for row in checks):
        raise ValidationError("readiness review did not pass exactly six checks")
    decision = contract["decision"]
    closed = (
        "network_or_archive_acquisition_authorized",
        "external_evidence_mutation_authorized",
        "source_unpack_or_reading_authorized",
        "candidate_implementation_or_execution_authorized",
        "kernel_accounting_bound_design_authorized",
    )
    if any(decision[key] for key in closed) or decision["scientific_authority"] != "NONE":
        raise ValidationError("operational or scientific authority reopened")
    if record["contract_raw_sha256"] != sha256(CONTRACT.read_bytes()):
        raise ValidationError("raw contract digest mismatch")
    if record["contract_canonical_sha256"] != sha256(canonical(contract)):
        raise ValidationError("canonical contract digest mismatch")
    return {"next_gate": decision["only_allowed_next_gate"], "readiness_pass_count": 6, "status": "PASS"}


if __name__ == "__main__":
    try:
        print(canonical(verify()).decode("ascii"))
    except (OSError, ValueError, subprocess.CalledProcessError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
