#!/usr/bin/env python3
"""Read-only validator for P11-G4 split governance."""

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
DIRECT_PARENT = "00d74c729bbc9322e215d6beab603f28e79d9923"
G3 = "0960ff5b1e7d1b1d2922e18eb7d5b71cd44a6a30"
CONTRACT_NAME = "majorana_certificate_p11_g4_split_governance_contract.json"
RECORD_NAME = "majorana_certificate_p11_g4_split_governance_record.json"
MODULE_NAME = "majorana_certificate_p11_g4_split_governance_validator.py"
TEST_NAME = "test_majorana_certificate_p11_g4_split_governance.py"
P11D_CONTRACT = "docs/research/fermion-frontier/majorana_certificate_p11d_source_runtime_evidence_feasibility_contract.json"
P11D_REPORT = "docs/research/fermion-frontier/majorana_certificate_p11d_source_runtime_evidence_feasibility_report.json"
CONTRACT_CANONICAL_SHA256 = "d02ccaf69d91704658e2216088d2131d8a3f5d14c52ae448d48a0ec8eced93e5"
DISPOSITION = "OPEN_NONIMPLEMENTING_P11_E0_SOURCE_ARCHIVE_ACQUISITION_CONTRACT_PACK_ONLY_DEFER_P11_E2_KERNEL_BOUND_DESIGN"
NEXT_GATE = "P11-E0-SOURCE-ARCHIVE-ACQUISITION-CONTRACT-PACK-V1"
DEFERRED_GATE = "P11-E2-KERNEL-ACCOUNTING-BOUND-FEASIBILITY-DESIGN-V1"
ROUTE_A_STATUS = "OPEN_CONTRACT_PACK_ONLY_ACQUISITION_NOT_AUTHORIZED"
ROUTE_B_STATUS = "DEFERRED_PENDING_VERIFIED_EXACT_SOURCE_ARCHIVE_CUSTODY_AND_NEW_GOVERNANCE"
SEQUENCE = [
    "P11-E0_SOURCE_ARCHIVE_ACQUISITION_CONTRACT_PACK",
    "NEW_INDEPENDENT_GOVERNANCE_FOR_P11_E1_SOURCE_ARCHIVE_ACQUISITION",
    "P11-E1_EXACT_SOURCE_ARCHIVE_ACQUISITION_AND_BYTE_CUSTODY",
    "NEW_INDEPENDENT_GOVERNANCE_FOR_P11_E2_KERNEL_ACCOUNTING_BOUND_DESIGN",
    "P11-E2_NONEXECUTING_VERSION_BOUND_KERNEL_ACCOUNTING_DESIGN",
]
P11D_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    P11D_CONTRACT: "A",
    P11D_REPORT: "A",
    "docs/research/fermion-frontier/majorana_certificate_p11d_source_runtime_evidence_feasibility_validator.py": "A",
    "docs/research/fermion-frontier/test_majorana_certificate_p11d_source_runtime_evidence_feasibility.py": "A",
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
    return {
        "scientific_authority": "NONE",
        "execution_authority": False,
        "implementation_authority": False,
        "prototype_or_compilation_authority": False,
        "candidate_selection_authority": False,
        "candidate_or_cap_change_authority": False,
        "resource_or_no_go_authority": False,
        "source_archive_acquisition_authority": False,
        "kernel_accounting_bound_design_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P11-G4-SPLIT-GOVERNANCE-CLOSURE-V1":
        raise GovernanceError("contract identity drift")
    if contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise GovernanceError("direct parent drift")
    if contract.get("authority") != _authority():
        raise GovernanceError("authority drift")
    if sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise GovernanceError("contract semantic drift")

    decision = contract.get("decision", {})
    if decision.get("disposition") != DISPOSITION:
        raise GovernanceError("disposition drift")
    if decision.get("implementation_gate") != "CLOSED" or decision.get("execution_gate") != "CLOSED":
        raise GovernanceError("candidate gate drift")
    if decision.get("exact_static_process_peak_bytes") is not None:
        raise GovernanceError("peak overclaim drift")
    if decision.get("strict_integer_peak_less_than_fixed_cap") is not None:
        raise GovernanceError("cap overclaim drift")
    for key in ("difference_is_proven_headroom", "semantic_equivalence_established", "resource_no_go_inference"):
        if decision.get(key) is not False:
            raise GovernanceError("decision overclaim drift")

    route_a = contract.get("route_A_source_archive_custody", {})
    if route_a.get("status") != ROUTE_A_STATUS or route_a.get("only_allowed_next_gate") != NEXT_GATE:
        raise GovernanceError("route A identity drift")
    if len(route_a.get("required_exact_source_identities", ())) != 4:
        raise GovernanceError("route A source identity drift")
    if len(route_a.get("required_contract_pack_sections", ())) != 10:
        raise GovernanceError("route A contract pack drift")
    if route_a.get("contract_pack_may_define_commands_but_must_not_run_them") is not True:
        raise GovernanceError("route A command boundary drift")
    if route_a.get("all_outcomes_keep_acquisition_implementation_and_execution_closed") is not True:
        raise GovernanceError("route A outcome boundary drift")
    for key in (
        "package_source_configuration_mutation_allowed",
        "package_index_refresh_allowed",
        "binary_or_source_archive_download_allowed",
        "archive_unpack_or_patch_application_allowed",
        "source_tree_materialization_allowed",
        "candidate_source_allowed",
        "compilation_linking_disassembly_or_execution_allowed",
    ):
        if route_a.get(key) is not False:
            raise GovernanceError("route A acquisition authority drift")

    route_b = contract.get("route_B_static_kernel_accounting_bound", {})
    if route_b.get("status") != ROUTE_B_STATUS or route_b.get("future_gate") != DEFERRED_GATE:
        raise GovernanceError("route B identity drift")
    if len(route_b.get("prerequisites", ())) != 6:
        raise GovernanceError("route B prerequisite drift")
    for key in ("kernel_source_reading_or_bound_derivation_allowed", "dynamic_kernel_or_candidate_measurement_allowed",
                "static_kernel_cgroup_accounting_bound_established"):
        if route_b.get(key) is not False:
            raise GovernanceError("route B authority or proof drift")
    if route_b.get("exact_static_process_peak_bytes") is not None:
        raise GovernanceError("route B peak overclaim drift")

    if contract.get("ordered_successor_sequence") != SEQUENCE:
        raise GovernanceError("successor sequence drift")
    if contract.get("sequence_is_dependency_order_not_authority_to_skip_any_gate") is not True:
        raise GovernanceError("successor gate boundary drift")


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
    return {
        path: status
        for status, path in (
            line.split("\t", 1)
            for line in _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit).splitlines()
        )
    }


def validate_p11d(contract: Mapping[str, Any]) -> dict[str, Any]:
    if _parent(DIRECT_PARENT) != G3 or _paths(DIRECT_PARENT) != P11D_PATHS:
        raise GovernanceError("P11-D topology or path drift")
    custody = contract.get("P11_D_custody", {})
    contract_raw = _git_bytes("show", f"{DIRECT_PARENT}:{P11D_CONTRACT}")
    report_raw = _git_bytes("show", f"{DIRECT_PARENT}:{P11D_REPORT}")
    if sha256(contract_raw) != custody.get("contract_raw_sha256"):
        raise GovernanceError("P11-D contract custody drift")
    if sha256(report_raw) != custody.get("report_raw_sha256"):
        raise GovernanceError("P11-D report custody drift")
    p11d_contract = loads_strict(contract_raw, "P11-D contract")
    if sha256(canonical_bytes(p11d_contract)) != custody.get("contract_canonical_sha256"):
        raise GovernanceError("P11-D canonical contract custody drift")
    report = loads_strict(report_raw, "P11-D report", canonical=True)
    source_route = report.get("source_custody_route", {})
    kernel = report.get("static_kernel_accounting_assessment", {})
    if report.get("outcome") != custody.get("expected_outcome"):
        raise GovernanceError("P11-D outcome drift")
    if source_route.get("status") != custody.get("expected_source_custody_route_status"):
        raise GovernanceError("P11-D source route drift")
    if kernel.get("status") != custody.get("expected_static_kernel_accounting_status"):
        raise GovernanceError("P11-D kernel route drift")
    if report.get("source_archive_custody_established") is not False:
        raise GovernanceError("P11-D custody overclaim drift")
    if report.get("static_kernel_cgroup_accounting_bound_established") is not False:
        raise GovernanceError("P11-D bound overclaim drift")
    if report.get("implementation_gate") != "CLOSED" or report.get("execution_gate") != "CLOSED":
        raise GovernanceError("P11-D gate drift")
    if report.get("exact_static_process_peak_bytes") is not None:
        raise GovernanceError("P11-D exact peak overclaim drift")
    if report.get("difference_is_proven_headroom") is not False:
        raise GovernanceError("P11-D headroom overclaim drift")
    if report.get("resource_no_go_inference") is not False:
        raise GovernanceError("P11-D resource no-go drift")
    evidence = report.get("evidence_class_disposition", ())
    if len(evidence) != 7:
        raise GovernanceError("P11-D evidence projection drift")
    return {
        "P11_D_outcome": report["outcome"],
        "source_custody_route_status": source_route["status"],
        "static_kernel_accounting_status": kernel["status"],
        "source_archive_custody_established": False,
        "static_kernel_cgroup_accounting_bound_established": False,
        "evidence_class_count": len(evidence),
        "implementation_gate": "CLOSED",
        "execution_gate": "CLOSED",
    }


def expected_record(contract: Mapping[str, Any], raw: bytes, projection: Mapping[str, Any]) -> dict[str, Any]:
    route_a = contract["route_A_source_archive_custody"]
    return {
        "schema_version": 1,
        "record_id": "MAJORANA-P11-G4-SPLIT-GOVERNANCE-RECORD-V1",
        "parent_commit": DIRECT_PARENT,
        "contract_raw_sha256": sha256(raw),
        "contract_canonical_sha256": sha256(canonical_bytes(contract)),
        "validated_projection": dict(projection),
        "disposition": DISPOSITION,
        "route_A_status": ROUTE_A_STATUS,
        "next_gate": NEXT_GATE,
        "route_A_contract_pack_allowed": True,
        "required_exact_source_identities": [
            f"{row['source_package']}={row['source_version']}" for row in route_a["required_exact_source_identities"]
        ],
        "required_contract_pack_section_count": len(route_a["required_contract_pack_sections"]),
        "package_source_configuration_mutation_allowed": False,
        "package_index_refresh_allowed": False,
        "source_archive_download_allowed": False,
        "archive_unpack_or_source_tree_materialization_allowed": False,
        "route_B_status": ROUTE_B_STATUS,
        "route_B_future_gate": DEFERRED_GATE,
        "route_B_kernel_source_reading_or_bound_derivation_allowed": False,
        "ordered_successor_sequence": list(SEQUENCE),
        "sequence_is_dependency_order_not_authority": True,
        "source_archive_custody_established": False,
        "static_kernel_cgroup_accounting_bound_established": False,
        "fixed_process_cap_bytes": 2147483648,
        "contract_target_component_sum_bytes": 1028653056,
        "difference_to_fixed_cap_bytes": 1118830592,
        "difference_is_proven_headroom": False,
        "exact_static_process_peak_bytes": None,
        "strict_integer_peak_less_than_fixed_cap": None,
        "semantic_equivalence_established": False,
        "implementation_gate": "CLOSED",
        "execution_gate": "CLOSED",
        "resource_no_go_inference": False,
        "scientific_authority": "NONE",
        "execution_authority": False,
        "implementation_authority": False,
        "candidate_selection_authority": False,
        "candidate_or_cap_change_authority": False,
        "resource_or_no_go_authority": False,
        "source_archive_acquisition_authority": False,
        "kernel_accounting_bound_design_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P11-G4 contract")
    validate_contract(contract)
    projection = validate_p11d(contract)
    record, _ = load_json(BASE / RECORD_NAME, "P11-G4 record", canonical=True)
    if record != expected_record(contract, raw, projection):
        raise GovernanceError("record reconstruction drift")
    return {
        "status": "VERIFIED_P11_G4_SPLIT_GOVERNANCE",
        "disposition": DISPOSITION,
        "next_gate": NEXT_GATE,
        "deferred_gate": DEFERRED_GATE,
        "implementation_gate": "CLOSED",
        "execution_gate": "CLOSED",
    }


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise GovernanceError("staging must begin at P11-D")
    staged = {
        path: status
        for status, path in (
            line.split("\t", 1)
            for line in _git("diff", "--cached", "--name-status", "--no-renames").splitlines()
        )
    }
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
