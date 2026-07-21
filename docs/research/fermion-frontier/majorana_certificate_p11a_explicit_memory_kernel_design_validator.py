#!/usr/bin/env python3
"""Read-only validator for the P11-A explicit-memory feasibility design."""

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
DIRECT_PARENT = "3b6f2515e6f66ab72cb4b612f9cb106a8a02b0e0"
P10B = "299f3027c49865403e527d76503d5bb88c3f0af0"
CONTRACT_NAME = "majorana_certificate_p11a_explicit_memory_kernel_design_contract.json"
REPORT_NAME = "majorana_certificate_p11a_explicit_memory_kernel_design_report.json"
MODULE_NAME = "majorana_certificate_p11a_explicit_memory_kernel_design_validator.py"
TEST_NAME = "test_majorana_certificate_p11a_explicit_memory_kernel_design.py"
CONTRACT_CANONICAL_SHA256 = "4ee5052fa0a79b8753f546f70871bf47cf65352225d02af3402ba20cd4831a11"
OUTCOME = "FEASIBLE_EXPLICIT_MEMORY_ROUTE_IDENTIFIED_NOT_IMPLEMENTATION_AUTHORITY"
QUESTION_IDS = (
    "Q1-FIXED-CAPACITY-COLLECTIONS", "Q2-FIXED-WIDTH-ARITHMETIC",
    "Q3-LIFETIME-NO-HIDDEN-ALLOCATION", "Q4-DETERMINISTIC-WORKSPACES",
    "Q5-RUNTIME-STACK-CODE-TRANSPORT", "Q6-INDEPENDENT-CHECKER",
    "Q7-FROZEN-SEMANTICS",
)
REGION_IDS = (
    "TERM_TABLE_MAIN", "TERM_TABLE_AUX", "BOUNDARY_SNAPSHOT",
    "RANKING_ROWS_WITH_TICK2048", "CONSTITUENT_ACTIONS", "MERGE_COLLISIONS",
    "DROPPED_ROWS", "INDEX_AND_MEMBERSHIP_WORKSPACE",
)
CHANGED_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    f"docs/research/fermion-frontier/{CONTRACT_NAME}": "A",
    f"docs/research/fermion-frontier/{REPORT_NAME}": "A",
    f"docs/research/fermion-frontier/{MODULE_NAME}": "A",
    f"docs/research/fermion-frontier/{TEST_NAME}": "A",
}
G2_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    "docs/research/fermion-frontier/majorana_certificate_p10_g2_post_audit_governance_contract.json": "A",
    "docs/research/fermion-frontier/majorana_certificate_p10_g2_post_audit_governance_record.json": "A",
    "docs/research/fermion-frontier/majorana_certificate_p10_g2_post_audit_governance_validator.py": "A",
    "docs/research/fermion-frontier/test_majorana_certificate_p10_g2_post_audit_governance.py": "A",
}


class DesignError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DesignError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _constant(value: str) -> None:
    raise DesignError(f"non-finite JSON constant: {value}")


def loads_strict(raw: bytes, label: str, *, canonical: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DesignError(f"malformed {label}") from error
    if not isinstance(value, dict):
        raise DesignError(f"{label} must be an object")
    if canonical and raw != canonical_bytes(value):
        raise DesignError(f"{label} is not canonical JSON")
    return value


def load_json(path: Path, label: str, *, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise DesignError(f"invalid {label} file")
    raw = path.read_bytes()
    return loads_strict(raw, label, canonical=canonical), raw


def _authority() -> dict[str, Any]:
    return {"scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "prototype_or_compilation_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False}


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P11-A-EXPLICIT-MEMORY-KERNEL-FEASIBILITY-DESIGN-V1" or contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise DesignError("contract identity drift")
    if contract.get("authority") != _authority() or sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise DesignError("contract authority or semantic drift")
    facts = contract.get("frozen_problem_facts", {})
    if facts.get("Majorana_generator_count") != 256 or facts.get("mask_storage_target_bytes") != 32 or facts.get("logical_term_cap_M") != 1048576 or facts.get("maximum_stored_tick_bits") != 2048 or facts.get("fixed_process_cap_bytes") != 2147483648:
        raise DesignError("frozen problem facts drift")
    questions = contract.get("design_question_disposition")
    if not isinstance(questions, list) or tuple(row.get("question_id") for row in questions if isinstance(row, dict)) != QUESTION_IDS or any(row.get("status") != "ROUTE_IDENTIFIED_CONTRACT_REQUIRED" for row in questions):
        raise DesignError("design question disposition drift")
    if contract.get("allowed_outcome") != OUTCOME:
        raise DesignError("outcome drift")


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _parent(commit: str) -> str:
    fields = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(fields) != 2 or fields[0] != commit:
        raise DesignError("commit must have one parent")
    return fields[1]


def _paths(commit: str) -> dict[str, str]:
    return {path: status for status, path in (line.split("\t", 1) for line in _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit).splitlines())}


def validate_sources(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    if _parent(DIRECT_PARENT) != P10B or _paths(DIRECT_PARENT) != G2_PATHS:
        raise DesignError("P10-G2 topology or path drift")
    inputs = contract.get("source_inputs")
    if not isinstance(inputs, list) or len(inputs) != 6:
        raise DesignError("source input drift")
    values: dict[str, bytes] = {}
    for row in inputs:
        path = BASE / row["relative_path"]
        if path.is_symlink() or not path.is_file():
            raise DesignError("invalid source input")
        raw = path.read_bytes()
        if sha256(raw) != row.get("sha256"):
            raise DesignError("source input digest drift")
        values[row["relative_path"]] = raw
    p6 = values["majorana_certificate_p6/majorana_p6_runner.jl"]
    p9 = values["majorana_certificate_p9_bit_order_resource_probe/majorana_p9_bit_order_step3_resource_probe.jl"]
    for needle in (b"L == 8 && NSITES == 64 && NMODES == 128", b"struct P6SnapshotRow", b"point_cost::BigInt", b"snapshot_coefficient_bits::Dict{Any,UInt64}"):
        if p6.count(needle) != 1:
            raise DesignError("P6 semantic anchor drift")
    for needle in (b"maximum_BigInt_bit_length=2048", b"maximum_step3_current_terms_before_constituent=1048576", b"transition_records = Any[]", b"boundary_records = Any[]", b"stage_records = Any[]"):
        if p9.count(needle) != 1:
            raise DesignError("P9 capacity anchor drift")
    p10 = loads_strict(values["majorana_certificate_p10a_static_resource_envelope_report.json"], "P10-A report", canonical=True)
    facts = p10.get("assessment", {}).get("known_static_facts", {}).get("cardinality_and_arithmetic_caps", {})
    if facts.get("logical_term_cap_M") != 1048576 or facts.get("maximum_BigInt_bit_length_L") != 2048:
        raise DesignError("P10-A fact drift")
    g2 = loads_strict(values["majorana_certificate_p10_g2_post_audit_governance_record.json"], "P10-G2 record", canonical=True)
    if g2.get("next_gate") != "P11-A-EXPLICIT-MEMORY-KERNEL-FEASIBILITY-DESIGN-V1" or g2.get("P11_A_implementation_allowed") is not False or g2.get("execution_gate") != "CLOSED":
        raise DesignError("P10-G2 authority drift")
    return [{"relative_path": row["relative_path"], "sha256": row["sha256"], "role": row["role"]} for row in inputs]


def derive_regions(contract: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int]:
    M = contract["frozen_problem_facts"]["logical_term_cap_M"]
    regions = contract.get("provisional_explicit_region_ledger")
    if not isinstance(regions, list) or tuple(row.get("region_id") for row in regions if isinstance(row, dict)) != REGION_IDS:
        raise DesignError("region ledger drift")
    derived: list[dict[str, Any]] = []
    for row in regions:
        expected = row["capacity_multiplier_M"] * M * row["bytes_per_slot"]
        if expected != row["derived_bytes"]:
            raise DesignError("region byte derivation drift")
        derived.append(dict(row))
    subtotal = sum(row["derived_bytes"] for row in derived)
    rules = contract.get("provisional_ledger_rules", {})
    if subtotal != 872415232 or rules.get("derived_explicit_region_subtotal_bytes") != subtotal or rules.get("unassigned_difference_to_fixed_cap_bytes") != 2147483648 - subtotal or rules.get("subtotal_is_a_design_budget_not_an_implemented_layout_or_process_peak_bound") is not True or rules.get("unassigned_difference_is_not_runtime_headroom_proof") is not True:
        raise DesignError("provisional subtotal boundary drift")
    return derived, subtotal


def expected_report(contract: Mapping[str, Any], raw: bytes, sources: list[dict[str, Any]], regions: list[dict[str, Any]], subtotal: int) -> dict[str, Any]:
    return {"schema_version": 1, "report_type": "majorana_p11_a_explicit_memory_kernel_feasibility_design_report_v1",
            "gate_id": "P11-A-EXPLICIT-MEMORY-KERNEL-FEASIBILITY-DESIGN-V1", "parent_commit": DIRECT_PARENT,
            "contract_raw_sha256": sha256(raw), "contract_canonical_sha256": sha256(canonical_bytes(contract)), "source_inputs": sources,
            "outcome": OUTCOME, "route_status": "IDENTIFIED_DESIGN_ONLY", "route_architecture": contract["route_architecture"],
            "derived_region_ledger": regions, "derived_explicit_region_subtotal_bytes": subtotal,
            "fixed_process_cap_bytes": 2147483648, "unassigned_difference_to_fixed_cap_bytes": 2147483648 - subtotal,
            "subtotal_interpretation": "PROVISIONAL_DESIGN_BUDGET_NOT_AN_IMPLEMENTED_LAYOUT_OR_PROCESS_PEAK_BOUND",
            "design_question_disposition": contract["design_question_disposition"], "unresolved_before_implementation": contract["unresolved_before_implementation"],
            "implementation_gate": "CLOSED", "execution_gate": "CLOSED", "exact_static_process_peak_bytes": None,
            "strict_integer_peak_less_than_fixed_cap": None, "semantic_equivalence_established": False, "resource_no_go_inference": False,
            "scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "candidate_selection_authority": False, "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False,
            "S0_authority": False, "certificate_eligible": False, "result_contract_eligible": False,
            "next_governance_requirement": "NEW_INDEPENDENT_IMPLEMENTATION_GOVERNANCE_REQUIRED"}


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P11-A contract")
    validate_contract(contract)
    sources = validate_sources(contract)
    regions, subtotal = derive_regions(contract)
    report, _ = load_json(BASE / REPORT_NAME, "P11-A report", canonical=True)
    if report != expected_report(contract, raw, sources, regions, subtotal):
        raise DesignError("report reconstruction drift")
    return {"status": "VERIFIED_P11_A_EXPLICIT_MEMORY_FEASIBILITY_DESIGN", "outcome": OUTCOME, "explicit_region_subtotal_bytes": subtotal, "implementation_gate": "CLOSED", "execution_gate": "CLOSED"}


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise DesignError("staging must begin at P10-G2")
    staged = {path: status for status, path in (line.split("\t", 1) for line in _git("diff", "--cached", "--name-status", "--no-renames").splitlines())}
    if staged != CHANGED_PATHS:
        raise DesignError("staged changed-path set drift")
    if _git("diff", "--name-only").strip() or _git("ls-files", "--others", "--exclude-standard").strip():
        raise DesignError("unstaged or untracked files are forbidden")
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
