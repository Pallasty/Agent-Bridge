#!/usr/bin/env python3
"""Read-only validator for P10-B's frozen source/runtime contract inventory."""

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
DIRECT_PARENT = "a0cc8766081712955acf2a45b356d47242d12459"
CONTRACT_NAME = "majorana_certificate_p10_b_source_runtime_contract_feasibility_contract.json"
RECORD_NAME = "majorana_certificate_p10_b_source_runtime_contract_feasibility_record.json"
MODULE_NAME = "majorana_certificate_p10_b_source_runtime_contract_feasibility_validator.py"
TEST_NAME = "test_majorana_certificate_p10_b_source_runtime_contract_feasibility.py"
CONTRACT_ID = "MAJORANA-P10-B-SOURCE-RUNTIME-CONTRACT-FEASIBILITY-AUDIT-V1"
RECORD_ID = "MAJORANA-P10-B-SOURCE-RUNTIME-CONTRACT-FEASIBILITY-RECORD-V1"
CONTRACT_CANONICAL_SHA256 = "09841d9505a9959864c85c19171dfe28501eb3a3344e4d2df203a520fa7939f1"
OUTCOME = "CLOSED_NO_INDEPENDENT_STATIC_BYTE_CONTRACT_ROUTE"
EVIDENCE_STATUS = "NO_INDEPENDENT_STATIC_CONTRACT_IN_FROZEN_INVENTORY"
OBLIGATION_IDS = (
    "LSB-01-SOURCE-TYPE-ALLOCATION-CLOSURE",
    "LSB-02-ALIAS-OWNERSHIP-LIFETIME-GRAPH",
    "LSB-03-EXACT-PAYLOAD-AND-CAPACITY-BYTES",
    "LSB-04-RUNTIME-OVERHEAD-ENVELOPE",
    "LSB-05-PEAK-COMPOSITION-AND-FIXED-CAP-COMPARISON",
    "LSB-06-INDEPENDENT-CHECKER-AND-ADVERSARIAL-MUTATIONS",
    "RSE-07-OPERATION-COST-CLOSURE",
)
CHANGED_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    f"docs/research/fermion-frontier/{CONTRACT_NAME}": "A",
    f"docs/research/fermion-frontier/{RECORD_NAME}": "A",
    f"docs/research/fermion-frontier/{MODULE_NAME}": "A",
    f"docs/research/fermion-frontier/{TEST_NAME}": "A",
}


class AuditError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _reject_constant(value: str) -> None:
    raise AuditError(f"non-finite JSON constant: {value}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path, label: str, *, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise AuditError(f"invalid {label} file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditError(f"malformed {label} JSON") from error
    if not isinstance(value, dict):
        raise AuditError(f"{label} must be an object")
    if canonical and raw != canonical_bytes(value):
        raise AuditError(f"{label} is not canonical JSON")
    return value, raw


def _authority() -> dict[str, Any]:
    return {"scientific_authority": "NONE", "execution_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False}


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != CONTRACT_ID or contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise AuditError("contract identity drift")
    if contract.get("authority") != _authority() or sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise AuditError("contract authority or semantic drift")
    scope = contract.get("scope")
    if not isinstance(scope, dict) or any(scope.get(key) is not False for key in ("Julia_execution_allowed", "candidate_execution_allowed", "host_observation_allowed", "D3_or_D4_observation_allowed", "candidate_or_cap_change_allowed")):
        raise AuditError("execution boundary drift")
    if tuple(contract.get("required_evidence_classes", ())) != (
        "source_pinned_transitive_allocation_and_container_type_closure", "stable_Julia_and_package_object_layout_header_alignment_and_capacity_contracts", "alias_ownership_copy_and_lifetime_boundary_contracts", "BigInt_GMP_string_hash_and_container_resize_byte_contracts", "allocator_GC_JIT_sysimage_library_thread_stack_and_transport_upper_bound_contracts", "independent_checker_implementation_separation_and_adversarial_mutation_plan", "sort_package_primitive_and_machine_cost_contracts"):
        raise AuditError("evidence-class drift")
    if tuple(contract.get("permitted_outcomes", ())) != ("EVIDENCE_ROUTE_IDENTIFIED_NOT_A_BYTE_PROOF", OUTCOME):
        raise AuditError("outcome boundary drift")


def source_facts(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    inputs = contract.get("source_inputs")
    if not isinstance(inputs, list) or len(inputs) != 4:
        raise AuditError("source-input shape drift")
    loaded: dict[str, dict[str, Any]] = {}
    for row in inputs:
        if not isinstance(row, dict) or set(row) != {"relative_path", "sha256", "role"}:
            raise AuditError("source-input row drift")
        path = BASE / row["relative_path"]
        value, raw = load_json(path, row["relative_path"])
        if sha256(raw) != row["sha256"]:
            raise AuditError("frozen source input digest drift")
        loaded[row["relative_path"]] = value
    lock = loaded["majorana_certificate_p0_runtime_lock.json"]
    fixture = loaded["majorana_certificate_p9_bit_order_resource_probe_fixture.json"]
    report = loaded["majorana_certificate_p10a_static_resource_envelope_report.json"]
    g1 = loaded["majorana_certificate_p10_g1_post_assessment_governance_contract.json"]
    if lock.get("runtime_lock_id") != "MAJORANA-P0-JULIA-1.11.9-LINUX-X86_64-V1" or lock.get("julia_runtime", {}).get("sysimage", {}).get("sha256") != "4e6f6765863713b3088d1a8f3b3eb68913503253ac5aa3a7a13c5b21f64d23bb":
        raise AuditError("runtime identity lock drift")
    if fixture.get("runtime_custody", {}).get("MajoranaPropagation_source_tree_closure", {}).get("file_count") != 42 or fixture.get("runtime_custody", {}).get("PauliPropagation_source_tree_closure", {}).get("file_count") != 119:
        raise AuditError("package source closure identity drift")
    anchors = report.get("assessment", {}).get("selected_source_anchor_custody", {})
    if anchors.get("closure_status") != "SELECTED_CORE_ANCHORS_ONLY_NOT_TRANSITIVE_ALLOCATION_CLOSURE":
        raise AuditError("allocation closure finding drift")
    rows = report.get("assessment", {}).get("proof_obligations", {}).get("rows")
    if not isinstance(rows, list) or tuple(row.get("obligation_id") for row in rows if isinstance(row, dict)) != OBLIGATION_IDS:
        raise AuditError("P10-A obligation ledger drift")
    if any(row.get("current_status") != "NOT_ESTABLISHED" for row in rows):
        raise AuditError("P10-A negative assessment drift")
    p10b = g1.get("P10_B_feasibility_audit_contract", {})
    if p10b.get("only_allowed_next_gate") != "P10-B-SOURCE-RUNTIME-CONTRACT-FEASIBILITY-AUDIT-V1" or p10b.get("Julia_execution_allowed") is not False:
        raise AuditError("P10-G1 authority drift")
    return [{"relative_path": row["relative_path"], "sha256": row["sha256"], "role": row["role"]} for row in inputs]


def expected_record(contract: Mapping[str, Any], contract_raw: bytes, facts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": 1, "record_id": RECORD_ID, "gate_id": "P10-B-SOURCE-RUNTIME-CONTRACT-FEASIBILITY-AUDIT-V1",
            "parent_commit": DIRECT_PARENT, "contract_raw_sha256": sha256(contract_raw), "contract_canonical_sha256": sha256(canonical_bytes(contract)),
            "audit_mode": "READ_ONLY_FROZEN_REPOSITORY_SOURCE_AND_LOCK_INVENTORY", "source_inputs": facts,
            "evidence_ledger": [{"obligation_id": item, "status": EVIDENCE_STATUS} for item in OBLIGATION_IDS],
            "outcome": OUTCOME, "exact_static_peak_bytes": None, "strict_integer_peak_less_than_fixed_cap": None,
            "fixed_process_cap_bytes": 2147483648, "execution_gate": "CLOSED", "resource_no_go_inference": False,
            "scientific_authority": "NONE", "execution_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False,
            "nonclaims": ["no_exact_static_peak_byte_bound", "no_resource_no_go_or_OOM_attribution", "no_Julia_or_candidate_execution", "no_machine_cost_bound", "no_S0_or_scientific_result"]}


def validate_record(record: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    if dict(record) != dict(expected):
        raise AuditError("record reconstruction drift")


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def validate_content() -> dict[str, Any]:
    contract, contract_raw = load_json(BASE / CONTRACT_NAME, "contract")
    validate_contract(contract)
    facts = source_facts(contract)
    record, _ = load_json(BASE / RECORD_NAME, "record", canonical=True)
    expected = expected_record(contract, contract_raw, facts)
    validate_record(record, expected)
    return {"outcome": OUTCOME, "execution_gate": "CLOSED", "status": "VERIFIED_P10_B_SOURCE_RUNTIME_CONTRACT_FEASIBILITY_CONTENT"}


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise AuditError("staging must begin at the P10-G1 direct parent")
    output = _git("diff", "--cached", "--name-status", "--no-renames")
    rows = {path: status for status, path in (line.split("\t", 1) for line in output.splitlines())}
    if rows != CHANGED_PATHS:
        raise AuditError("staged changed-path set drift")
    if _git("diff", "--name-only").strip() or _git("ls-files", "--others", "--exclude-standard").strip():
        raise AuditError("unstaged or untracked files are forbidden")
    return "STAGED_DIRECT_CHILD"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-content", action="store_true")
    parser.add_argument("--verify-lifecycle", action="store_true")
    args = parser.parse_args()
    if not args.verify_content and not args.verify_lifecycle:
        parser.error("choose --verify-content and/or --verify-lifecycle")
    if args.verify_content:
        print(json.dumps(validate_content(), sort_keys=True))
    if args.verify_lifecycle:
        print(validate_lifecycle())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
