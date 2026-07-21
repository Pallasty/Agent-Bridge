#!/usr/bin/env python3
"""Read-only validator for the P10-G2 post-audit governance closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
DIRECT_PARENT = "299f3027c49865403e527d76503d5bb88c3f0af0"
P10B_PARENT = "a0cc8766081712955acf2a45b356d47242d12459"
CONTRACT_NAME = "majorana_certificate_p10_g2_post_audit_governance_contract.json"
RECORD_NAME = "majorana_certificate_p10_g2_post_audit_governance_record.json"
MODULE_NAME = "majorana_certificate_p10_g2_post_audit_governance_validator.py"
TEST_NAME = "test_majorana_certificate_p10_g2_post_audit_governance.py"
P10B_CONTRACT = "docs/research/fermion-frontier/majorana_certificate_p10_b_source_runtime_contract_feasibility_contract.json"
P10B_RECORD = "docs/research/fermion-frontier/majorana_certificate_p10_b_source_runtime_contract_feasibility_record.json"
CONTRACT_CANONICAL_SHA256 = "449cbd58d53ff3fd35b1e05c6a418d339bdd9ac55cc0054c292cbe4f41c81cd8"
DISPOSITION = "CLOSE_CURRENT_JULIA_STATIC_BYTE_ROUTE_OPEN_NONEXECUTING_P11_A_DESIGN_ONLY"
NEXT_GATE = "P11-A-EXPLICIT-MEMORY-KERNEL-FEASIBILITY-DESIGN-V1"
P10B_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    P10B_CONTRACT: "A",
    P10B_RECORD: "A",
    "docs/research/fermion-frontier/majorana_certificate_p10_b_source_runtime_contract_feasibility_validator.py": "A",
    "docs/research/fermion-frontier/test_majorana_certificate_p10_b_source_runtime_contract_feasibility.py": "A",
}
CHANGED_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    f"docs/research/fermion-frontier/{CONTRACT_NAME}": "A",
    f"docs/research/fermion-frontier/{RECORD_NAME}": "A",
    f"docs/research/fermion-frontier/{MODULE_NAME}": "A",
    f"docs/research/fermion-frontier/{TEST_NAME}": "A",
}


class GovernanceError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise GovernanceError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _constant(value: str) -> None:
    raise GovernanceError(f"non-finite JSON constant: {value}")


def loads_strict(raw: bytes, label: str, *, canonical: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GovernanceError(f"malformed {label}") from error
    if not isinstance(value, dict):
        raise GovernanceError(f"{label} must be an object")
    if canonical and raw != canonical_bytes(value):
        raise GovernanceError(f"{label} is not canonical JSON")
    return value


def load_json(path: Path, label: str, *, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise GovernanceError(f"invalid {label} file")
    raw = path.read_bytes()
    return loads_strict(raw, label, canonical=canonical), raw


def _authority() -> dict[str, Any]:
    return {"scientific_authority": "NONE", "execution_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False}


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P10-G2-POST-AUDIT-GOVERNANCE-CLOSURE-V1" or contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise GovernanceError("contract identity drift")
    if contract.get("authority") != _authority() or sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise GovernanceError("contract authority or semantic drift")
    decision = contract.get("decision", {})
    if decision.get("disposition") != DISPOSITION or decision.get("execution_gate") != "CLOSED" or decision.get("resource_no_go_inference") is not False:
        raise GovernanceError("governance decision drift")
    p11a = contract.get("P11_A_design_authorization", {})
    if p11a.get("only_allowed_next_gate") != NEXT_GATE:
        raise GovernanceError("next-gate drift")
    for key in ("implementation_allowed", "prototype_allowed", "compilation_allowed", "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed", "network_or_external_source_acquisition_allowed", "scientific_schedule_or_semantics_change_allowed"):
        if p11a.get(key) is not False:
            raise GovernanceError("P11-A authority drift")
    if p11a.get("fixed_process_cap_bytes") != 2147483648 or len(p11a.get("required_design_questions", ())) != 7:
        raise GovernanceError("P11-A design boundary drift")


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True).stdout


def _parent(commit: str) -> str:
    fields = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(fields) != 2 or fields[0] != commit:
        raise GovernanceError("commit must have one parent")
    return fields[1]


def _paths(commit: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit).splitlines():
        status, path = line.split("\t", 1)
        if path in rows:
            raise GovernanceError("duplicate changed path")
        rows[path] = status
    return rows


def validate_p10b(contract: Mapping[str, Any]) -> dict[str, Any]:
    if _parent(DIRECT_PARENT) != P10B_PARENT or _paths(DIRECT_PARENT) != P10B_PATHS:
        raise GovernanceError("P10-B topology or path drift")
    custody = contract.get("P10_B_custody", {})
    contract_raw = _git_bytes("show", f"{DIRECT_PARENT}:{P10B_CONTRACT}")
    record_raw = _git_bytes("show", f"{DIRECT_PARENT}:{P10B_RECORD}")
    if sha256(contract_raw) != custody.get("contract_raw_sha256") or sha256(record_raw) != custody.get("record_raw_sha256"):
        raise GovernanceError("P10-B blob custody drift")
    record = loads_strict(record_raw, "P10-B record", canonical=True)
    if record.get("outcome") != custody.get("expected_outcome") or record.get("execution_gate") != "CLOSED":
        raise GovernanceError("P10-B outcome drift")
    ledger = record.get("evidence_ledger")
    if not isinstance(ledger, list) or len(ledger) != 7 or any(row.get("status") != custody.get("expected_evidence_status") for row in ledger if isinstance(row, dict)):
        raise GovernanceError("P10-B evidence ledger drift")
    if record.get("exact_static_peak_bytes") is not None or record.get("strict_integer_peak_less_than_fixed_cap") is not None or record.get("resource_no_go_inference") is not False:
        raise GovernanceError("P10-B nonclaim drift")
    return {"P10_B_outcome": record["outcome"], "P10_B_evidence_row_count": len(ledger), "P10_B_execution_gate": "CLOSED"}


def expected_record(contract: Mapping[str, Any], raw: bytes, projection: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "record_id": "MAJORANA-P10-G2-POST-AUDIT-GOVERNANCE-RECORD-V1",
            "parent_commit": DIRECT_PARENT, "contract_raw_sha256": sha256(raw), "contract_canonical_sha256": sha256(canonical_bytes(contract)),
            "validated_projection": dict(projection), "disposition": DISPOSITION, "closed_route": "CURRENT_FROZEN_JULIA_STATIC_BYTE_ROUTE",
            "next_gate": NEXT_GATE, "P11_A_implementation_allowed": False, "P11_A_compilation_allowed": False,
            "P11_A_Julia_or_candidate_execution_allowed": False, "P11_A_external_source_acquisition_allowed": False,
            "fixed_process_cap_bytes": 2147483648, "exact_static_peak_bytes": None, "execution_gate": "CLOSED",
            "scientific_authority": "NONE", "execution_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False, "resource_no_go_inference": False}


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P10-G2 contract")
    validate_contract(contract)
    projection = validate_p10b(contract)
    record, _ = load_json(BASE / RECORD_NAME, "P10-G2 record", canonical=True)
    if record != expected_record(contract, raw, projection):
        raise GovernanceError("record reconstruction drift")
    return {"status": "VERIFIED_P10_G2_POST_AUDIT_GOVERNANCE_CONTENT", "disposition": DISPOSITION, "next_gate": NEXT_GATE}


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise GovernanceError("staging must begin at P10-B")
    staged = {path: status for status, path in (line.split("\t", 1) for line in _git("diff", "--cached", "--name-status", "--no-renames").splitlines())}
    if staged != CHANGED_PATHS:
        raise GovernanceError("staged changed-path set drift")
    if _git("diff", "--name-only").strip() or _git("ls-files", "--others", "--exclude-standard").strip():
        raise GovernanceError("unstaged or untracked files are forbidden")
    return "STAGED_DIRECT_CHILD"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-content", action="store_true")
    parser.add_argument("--verify-lifecycle", action="store_true")
    args = parser.parse_args()
    if not args.verify_content and not args.verify_lifecycle:
        parser.error("choose a verification mode")
    if args.verify_content:
        print(json.dumps(validate_content(), sort_keys=True))
    if args.verify_lifecycle:
        print(validate_lifecycle())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
