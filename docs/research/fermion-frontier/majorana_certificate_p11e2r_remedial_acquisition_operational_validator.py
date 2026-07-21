#!/usr/bin/env python3
"""Read-only Git validator for the nonexecuting P11-E2R contract pack."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTRACT = HERE / "majorana_certificate_p11e2r_remedial_acquisition_operational_contract.json"
RECORD = HERE / "majorana_certificate_p11e2r_remedial_acquisition_operational_record.json"
PARENT = "2568c1226b849a610dc4a7d1e2caf7fe0e390220"
G7_RECORD = "docs/research/fermion-frontier/majorana_certificate_p11_g7_remedial_authorization_review_record.json"


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
        raise ValidationError("E2R must be validated before its result commit")
    if contract["required_direct_parent_commit"] != PARENT or record["parent_commit"] != PARENT:
        raise ValidationError("direct-parent pin drift")
    g7_raw = git("show", f"{PARENT}:{G7_RECORD}")
    custody = contract["P11_G7_custody"]
    if sha256(g7_raw) != custody["record_raw_sha256"]:
        raise ValidationError("P11-G7 custody mismatch")
    g7 = json.loads(g7_raw)
    if g7["disposition"] != custody["expected_disposition"] or g7["next_gate"] != custody["expected_next_gate"]:
        raise ValidationError("P11-G7 authority semantics drift")
    authority = contract["current_authority"]
    boolean_keys = [key for key in authority if key.endswith("authorized")]
    if any(authority[key] for key in boolean_keys) or authority["scientific_authority"] != "NONE":
        raise ValidationError("current operational authority reopened")
    identity = contract["future_operation_identity"]
    if len(identity["exact_source_identities"]) != 4 or not identity["all_four_packages_must_be_acquired_fresh_into_the_new_root"]:
        raise ValidationError("fresh four-package identity contract drift")
    isolation = contract["future_APT_isolation_contract"]
    if not isolation["preflight_stdout_and_stderr_must_contain_no_host_etc_apt_path"]:
        raise ValidationError("host APT warning is not fail-closed")
    transaction = contract["future_final_path_receipt_transaction"]
    required = (
        "receipt_rows_must_name_the_declared_final_accepted_relative_paths_before_rename",
        "after_rename_independent_rehash_must_match_every_final_path_receipt_row",
        "receipt_incoming_path_or_missing_final_path_is_a_transaction_failure",
    )
    if not all(transaction[key] for key in required):
        raise ValidationError("final-path receipt repair drift")
    if not contract["future_operation_requires_new_independent_authorization"]:
        raise ValidationError("future operational gate bypass")
    if record["contract_raw_sha256"] != sha256(CONTRACT.read_bytes()) or record["contract_canonical_sha256"] != sha256(canonical(contract)):
        raise ValidationError("contract digest mismatch")
    return {"next_gate": contract["only_allowed_next_gate"], "status": "PASS"}


if __name__ == "__main__":
    try:
        print(canonical(verify()).decode("ascii"))
    except (OSError, ValueError, subprocess.CalledProcessError, ValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
