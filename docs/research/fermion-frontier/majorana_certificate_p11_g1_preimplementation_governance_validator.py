#!/usr/bin/env python3
"""Read-only validator for P11-G1 preimplementation governance."""

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
DIRECT_PARENT = "71967df1b328cc40ad28c555f0c6ff9152f87774"
G2 = "3b6f2515e6f66ab72cb4b612f9cb106a8a02b0e0"
CONTRACT_NAME = "majorana_certificate_p11_g1_preimplementation_governance_contract.json"
RECORD_NAME = "majorana_certificate_p11_g1_preimplementation_governance_record.json"
MODULE_NAME = "majorana_certificate_p11_g1_preimplementation_governance_validator.py"
TEST_NAME = "test_majorana_certificate_p11_g1_preimplementation_governance.py"
P11A_CONTRACT = "docs/research/fermion-frontier/majorana_certificate_p11a_explicit_memory_kernel_design_contract.json"
P11A_REPORT = "docs/research/fermion-frontier/majorana_certificate_p11a_explicit_memory_kernel_design_report.json"
CONTRACT_CANONICAL_SHA256 = "f13c5f65486a329cfbc2361c2888c9302dba5e30b047d8e5182ed2430cd3f52a"
DISPOSITION = "OPEN_NONEXECUTING_P11_B_PREIMPLEMENTATION_CONTRACT_PACK_ONLY"
NEXT_GATE = "P11-B-PREIMPLEMENTATION-CONTRACT-PACK-V1"
P11A_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    P11A_CONTRACT: "A", P11A_REPORT: "A",
    "docs/research/fermion-frontier/majorana_certificate_p11a_explicit_memory_kernel_design_validator.py": "A",
    "docs/research/fermion-frontier/test_majorana_certificate_p11a_explicit_memory_kernel_design.py": "A",
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
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise GovernanceError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


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
    return {"scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "prototype_or_compilation_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False}


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P11-G1-PREIMPLEMENTATION-GOVERNANCE-CLOSURE-V1" or contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise GovernanceError("contract identity drift")
    if contract.get("authority") != _authority() or sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise GovernanceError("contract authority or semantic drift")
    decision = contract.get("decision", {})
    if decision.get("disposition") != DISPOSITION or decision.get("implementation_gate") != "CLOSED" or decision.get("execution_gate") != "CLOSED" or decision.get("resource_no_go_inference") is not False:
        raise GovernanceError("decision drift")
    p11b = contract.get("P11_B_authorization", {})
    if p11b.get("only_allowed_next_gate") != NEXT_GATE or len(p11b.get("required_contract_sections", ())) != 7:
        raise GovernanceError("P11-B scope drift")
    for key in ("implementation_source_allowed", "prototype_allowed", "compilation_or_linking_allowed", "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed", "package_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed", "scientific_schedule_semantics_or_cap_change_allowed"):
        if p11b.get(key) is not False:
            raise GovernanceError("P11-B authority drift")


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True).stdout


def _parent(commit: str) -> str:
    row = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(row) != 2 or row[0] != commit:
        raise GovernanceError("commit must have one parent")
    return row[1]


def _paths(commit: str) -> dict[str, str]:
    return {path: status for status, path in (line.split("\t", 1) for line in _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit).splitlines())}


def validate_p11a(contract: Mapping[str, Any]) -> dict[str, Any]:
    if _parent(DIRECT_PARENT) != G2 or _paths(DIRECT_PARENT) != P11A_PATHS:
        raise GovernanceError("P11-A topology or path drift")
    custody = contract.get("P11_A_custody", {})
    contract_raw = _git_bytes("show", f"{DIRECT_PARENT}:{P11A_CONTRACT}")
    report_raw = _git_bytes("show", f"{DIRECT_PARENT}:{P11A_REPORT}")
    if sha256(contract_raw) != custody.get("contract_raw_sha256") or sha256(report_raw) != custody.get("report_raw_sha256"):
        raise GovernanceError("P11-A blob custody drift")
    report = loads_strict(report_raw, "P11-A report", canonical=True)
    if report.get("outcome") != custody.get("expected_outcome") or report.get("derived_explicit_region_subtotal_bytes") != 872415232:
        raise GovernanceError("P11-A result drift")
    if report.get("implementation_gate") != "CLOSED" or report.get("execution_gate") != "CLOSED" or report.get("exact_static_process_peak_bytes") is not None or report.get("strict_integer_peak_less_than_fixed_cap") is not None or report.get("resource_no_go_inference") is not False:
        raise GovernanceError("P11-A authority or nonclaim drift")
    return {"P11_A_outcome": report["outcome"], "explicit_region_subtotal_bytes": 872415232, "implementation_gate": "CLOSED", "execution_gate": "CLOSED"}


def expected_record(contract: Mapping[str, Any], raw: bytes, projection: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "record_id": "MAJORANA-P11-G1-PREIMPLEMENTATION-GOVERNANCE-RECORD-V1",
            "parent_commit": DIRECT_PARENT, "contract_raw_sha256": sha256(raw), "contract_canonical_sha256": sha256(canonical_bytes(contract)),
            "validated_projection": dict(projection), "disposition": DISPOSITION, "next_gate": NEXT_GATE,
            "local_toolchain_identity_inspection_allowed": True, "official_primary_metadata_retrieval_allowed": True,
            "binary_or_source_archive_download_allowed": False, "implementation_source_allowed": False,
            "compilation_or_linking_allowed": False, "Julia_or_candidate_execution_allowed": False,
            "fixed_process_cap_bytes": 2147483648, "exact_static_process_peak_bytes": None,
            "implementation_gate": "CLOSED", "execution_gate": "CLOSED", "resource_no_go_inference": False,
            "scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "candidate_selection_authority": False, "candidate_or_cap_change_authority": False,
            "resource_or_no_go_authority": False, "S0_authority": False, "certificate_eligible": False, "result_contract_eligible": False}


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P11-G1 contract")
    validate_contract(contract)
    projection = validate_p11a(contract)
    record, _ = load_json(BASE / RECORD_NAME, "P11-G1 record", canonical=True)
    if record != expected_record(contract, raw, projection):
        raise GovernanceError("record reconstruction drift")
    return {"status": "VERIFIED_P11_G1_PREIMPLEMENTATION_GOVERNANCE_CONTENT", "disposition": DISPOSITION, "next_gate": NEXT_GATE}


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise GovernanceError("staging must begin at P11-A")
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
