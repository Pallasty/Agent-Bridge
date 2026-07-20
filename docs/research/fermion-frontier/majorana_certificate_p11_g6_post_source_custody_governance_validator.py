#!/usr/bin/env python3
"""Read-only Git-custody validator for P11-G6 post-source governance."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "majorana_certificate_p11_g6_post_source_custody_governance_contract.json"
RECORD = HERE / "majorana_certificate_p11_g6_post_source_custody_governance_record.json"
PARENT = "aac2138c4b02d9e5218f92ddb575d5c17cd38dd3"
E1_MANIFEST = "docs/research/fermion-frontier/majorana_certificate_p11e1_source_archive_custody_manifest.json"
E1_REPORT = "docs/research/fermion-frontier/majorana_certificate_p11e1_source_archive_custody_report.json"


class ValidationError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def load(path: Path, canonical_required: bool = False) -> Any:
    raw = path.read_bytes()
    value = json.loads(raw)
    if canonical_required and raw != canonical(value):
        raise ValidationError(f"noncanonical JSON: {path.name}")
    return value


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=HERE.parents[2], check=True, capture_output=True).stdout


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify() -> dict[str, Any]:
    contract = load(CONTRACT)
    record = load(RECORD, canonical_required=True)
    if git("rev-parse", "HEAD").decode().strip() != PARENT:
        raise ValidationError("G6 must be evaluated before its result commit")
    if contract["required_direct_parent_commit"] != PARENT or record["parent_commit"] != PARENT:
        raise ValidationError("direct-parent pin drift")
    parent = git("show", "-s", "--format=%P", PARENT).decode().strip()
    if parent != "d549694726653f85e3f58c34e5bb98b82aa42d95":
        raise ValidationError("P11-E1 is not the expected direct child of G5")
    manifest_raw = git("show", f"{PARENT}:{E1_MANIFEST}")
    report_raw = git("show", f"{PARENT}:{E1_REPORT}")
    custody = contract["P11_E1_custody"]
    if digest(manifest_raw) != custody["manifest_raw_sha256"] or digest(report_raw) != custody["report_raw_sha256"]:
        raise ValidationError("P11-E1 artifact custody mismatch")
    manifest, report = json.loads(manifest_raw), json.loads(report_raw)
    outcome = "PARTIAL_VERIFIED_SOURCE_ARCHIVES_RETAINED_COMPLETE_SET_CUSTODY_NOT_ESTABLISHED"
    if manifest["outcome"] != outcome or report["outcome"] != outcome or report["source_archive_custody_established"]:
        raise ValidationError("P11-E1 partial result semantics drift")
    decision = contract["decision"]
    if not record["P11_E1_network_authority_consumed"] or decision["retry_or_network_acquisition_authorized"]:
        raise ValidationError("consumed network authority incorrectly reopened")
    if any(decision[key] for key in ("archive_unpack_or_source_reading_authorized", "candidate_implementation_or_execution_authorized", "kernel_accounting_bound_design_authorized")):
        raise ValidationError("closed downstream authority reopened")
    if record["contract_raw_sha256"] != digest(CONTRACT.read_bytes()) or record["contract_canonical_sha256"] != digest(canonical(contract)):
        raise ValidationError("G6 contract digest mismatch")
    if [item["status"] for item in contract["findings"]] != ["PASS"] * 4:
        raise ValidationError("governance finding failure")
    return {"finding_count": 4, "next_gate": decision["only_allowed_next_gate"], "status": "PASS"}


if __name__ == "__main__":
    try:
        print(canonical(verify()).decode("ascii"))
    except (OSError, ValueError, subprocess.CalledProcessError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
