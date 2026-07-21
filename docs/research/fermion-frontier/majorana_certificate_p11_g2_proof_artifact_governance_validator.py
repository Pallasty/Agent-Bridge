#!/usr/bin/env python3
"""Read-only validator for P11-G2 proof-artifact governance."""

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
DIRECT_PARENT = "9659d7cdf4a75768b358f0085e50dbf9f76bbc02"
G1 = "fb9bcd3bcbedcde774f0c9e0e5b730efb350a7f5"
CONTRACT_NAME = "majorana_certificate_p11_g2_proof_artifact_governance_contract.json"
RECORD_NAME = "majorana_certificate_p11_g2_proof_artifact_governance_record.json"
MODULE_NAME = "majorana_certificate_p11_g2_proof_artifact_governance_validator.py"
TEST_NAME = "test_majorana_certificate_p11_g2_proof_artifact_governance.py"
P11B_CONTRACT = "docs/research/fermion-frontier/majorana_certificate_p11b_preimplementation_contract_pack_contract.json"
P11B_REPORT = "docs/research/fermion-frontier/majorana_certificate_p11b_preimplementation_contract_pack_report.json"
CONTRACT_CANONICAL_SHA256 = "d68d246926cd444ef8f081f6765e3e0ad40a31c84df13d907117431a31af943e"
DISPOSITION = "OPEN_NONIMPLEMENTING_P11_C_STATIC_PROOF_ARTIFACT_PACK_ONLY"
NEXT_GATE = "P11-C-STATIC-PROOF-ARTIFACT-PACK-V1"
P11B_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    P11B_CONTRACT: "A",
    P11B_REPORT: "A",
    "docs/research/fermion-frontier/majorana_certificate_p11b_preimplementation_contract_pack_validator.py": "A",
    "docs/research/fermion-frontier/test_majorana_certificate_p11b_preimplementation_contract_pack.py": "A",
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
    if contract.get("contract_id") != "MAJORANA-P11-G2-PROOF-ARTIFACT-GOVERNANCE-CLOSURE-V1" or contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise GovernanceError("contract identity drift")
    if contract.get("authority") != _authority() or sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise GovernanceError("contract authority or semantic drift")
    decision = contract.get("decision", {})
    if decision.get("disposition") != DISPOSITION or decision.get("implementation_gate") != "CLOSED" or decision.get("execution_gate") != "CLOSED":
        raise GovernanceError("decision drift")
    if decision.get("exact_static_process_peak_bytes") is not None or decision.get("strict_integer_peak_less_than_fixed_cap") is not None or decision.get("difference_is_proven_headroom") is not False or decision.get("resource_no_go_inference") is not False:
        raise GovernanceError("decision overclaim drift")
    p11c = contract.get("P11_C_authorization", {})
    if p11c.get("only_allowed_next_gate") != NEXT_GATE or len(p11c.get("allowed_artifacts", ())) != 7:
        raise GovernanceError("P11-C scope drift")
    for key in ("implementation_source_allowed", "C_assembly_or_linker_script_source_allowed", "prototype_allowed", "compilation_or_linking_allowed", "Julia_or_candidate_execution_allowed", "benchmark_or_host_measurement_allowed", "package_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed", "network_retrieval_allowed", "scientific_schedule_semantics_or_cap_change_allowed"):
        if p11c.get(key) is not False:
            raise GovernanceError("P11-C authority drift")
    if p11c.get("checker_must_not_import_P11_B_validator") is not True or p11c.get("both_outcomes_keep_implementation_and_execution_closed") is not True:
        raise GovernanceError("P11-C independence or gate drift")


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


def validate_p11b(contract: Mapping[str, Any]) -> dict[str, Any]:
    if _parent(DIRECT_PARENT) != G1 or _paths(DIRECT_PARENT) != P11B_PATHS:
        raise GovernanceError("P11-B topology or path drift")
    custody = contract.get("P11_B_custody", {})
    contract_raw = _git_bytes("show", f"{DIRECT_PARENT}:{P11B_CONTRACT}")
    report_raw = _git_bytes("show", f"{DIRECT_PARENT}:{P11B_REPORT}")
    if sha256(contract_raw) != custody.get("contract_raw_sha256") or sha256(report_raw) != custody.get("report_raw_sha256"):
        raise GovernanceError("P11-B blob custody drift")
    report = loads_strict(report_raw, "P11-B report", canonical=True)
    derived = report.get("derived_contract_digests_and_totals", {})
    if report.get("outcome") != custody.get("expected_outcome") or derived.get("target_component_sum_bytes") != 1028653056 or derived.get("explicit_arena_bytes") != 872415232 or derived.get("wide_scratch_bits") != 2112:
        raise GovernanceError("P11-B result drift")
    if report.get("implementation_gate") != "CLOSED" or report.get("execution_gate") != "CLOSED" or report.get("exact_static_process_peak_bytes") is not None or report.get("strict_integer_peak_less_than_fixed_cap") is not None or report.get("difference_is_proven_headroom") is not False or report.get("semantic_equivalence_established") is not False or report.get("resource_no_go_inference") is not False:
        raise GovernanceError("P11-B authority or nonclaim drift")
    return {"P11_B_outcome": report["outcome"], "target_component_sum_bytes": 1028653056,
            "explicit_arena_bytes": 872415232, "wide_scratch_bits": 2112,
            "implementation_gate": "CLOSED", "execution_gate": "CLOSED"}


def expected_record(contract: Mapping[str, Any], raw: bytes, projection: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "record_id": "MAJORANA-P11-G2-PROOF-ARTIFACT-GOVERNANCE-RECORD-V1",
            "parent_commit": DIRECT_PARENT, "contract_raw_sha256": sha256(raw),
            "contract_canonical_sha256": sha256(canonical_bytes(contract)), "validated_projection": dict(projection),
            "disposition": DISPOSITION, "next_gate": NEXT_GATE,
            "authorized_artifact_count": 7, "independent_contract_checker_required": True,
            "candidate_source_allowed": False, "compilation_or_linking_allowed": False,
            "Julia_or_candidate_execution_allowed": False, "network_retrieval_allowed": False,
            "fixed_process_cap_bytes": 2147483648, "preimplementation_target_component_sum_bytes": 1028653056,
            "difference_to_fixed_cap_bytes": 1118830592, "difference_is_proven_headroom": False,
            "exact_static_process_peak_bytes": None, "strict_integer_peak_less_than_fixed_cap": None,
            "semantic_equivalence_established": False, "implementation_gate": "CLOSED", "execution_gate": "CLOSED",
            "resource_no_go_inference": False, "scientific_authority": "NONE", "execution_authority": False,
            "implementation_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False,
            "S0_authority": False, "certificate_eligible": False, "result_contract_eligible": False}


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P11-G2 contract")
    validate_contract(contract)
    projection = validate_p11b(contract)
    record, _ = load_json(BASE / RECORD_NAME, "P11-G2 record", canonical=True)
    if record != expected_record(contract, raw, projection):
        raise GovernanceError("record reconstruction drift")
    return {"status": "VERIFIED_P11_G2_PROOF_ARTIFACT_GOVERNANCE_CONTENT", "disposition": DISPOSITION,
            "next_gate": NEXT_GATE, "implementation_gate": "CLOSED", "execution_gate": "CLOSED"}


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise GovernanceError("staging must begin at P11-B")
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
