#!/usr/bin/env python3
"""Read-only validator for the nonexecuting P10-G1 governance closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
DIRECT_PARENT = "7ee0aca97233d2fd83d5e150f13c87e6e7379032"
P10_B0 = "63ae7e485724ff7a208e3e369c43a8b1933c5e2e"
G0 = "7650fc4beb042571477bca43eb7f62c7beab0368"
CONTRACT_NAME = "majorana_certificate_p10_g1_post_assessment_governance_contract.json"
RECORD_NAME = "majorana_certificate_p10_g1_post_assessment_governance_record.json"
MODULE_NAME = "majorana_certificate_p10_g1_post_assessment_governance_validator.py"
TEST_NAME = "test_majorana_certificate_p10_g1_post_assessment_governance.py"
P10_REPORT_PATH = "docs/research/fermion-frontier/majorana_certificate_p10a_static_resource_envelope_report.json"
CONTRACT_ID = "MAJORANA-P10-G1-POST-ASSESSMENT-GOVERNANCE-CLOSURE-V1"
RECORD_ID = "MAJORANA-P10-G1-POST-ASSESSMENT-GOVERNANCE-CLOSURE-RECORD-V1"
DISPOSITION = "OPEN_NONEXECUTING_P10_B_CONTRACT_FEASIBILITY_AUDIT_ONLY"
NEXT_GATE = "P10-B-SOURCE-RUNTIME-CONTRACT-FEASIBILITY-AUDIT-V1"
CONTRACT_CANONICAL_SHA256 = "ec3cd856eb30613644fb1a8b478f05195f22b3e195c122521e61d674ab5c7847"
G1_CHANGED_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    f"docs/research/fermion-frontier/{CONTRACT_NAME}": "A",
    f"docs/research/fermion-frontier/{RECORD_NAME}": "A",
    f"docs/research/fermion-frontier/{MODULE_NAME}": "A",
    f"docs/research/fermion-frontier/{TEST_NAME}": "A",
}
P10_B0_PATHS = {
    "docs/research/fermion-frontier/majorana_certificate_p10a_static_resource_envelope_fixture.json",
    "docs/research/fermion-frontier/majorana_certificate_p10a_static_resource_envelope_policy.json",
    "docs/research/fermion-frontier/majorana_certificate_p10a_static_resource_envelope.py",
    "docs/research/fermion-frontier/test_majorana_certificate_p10a_static_resource_envelope.py",
}
OBLIGATION_IDS = (
    "LSB-01-SOURCE-TYPE-ALLOCATION-CLOSURE",
    "LSB-02-ALIAS-OWNERSHIP-LIFETIME-GRAPH",
    "LSB-03-EXACT-PAYLOAD-AND-CAPACITY-BYTES",
    "LSB-04-RUNTIME-OVERHEAD-ENVELOPE",
    "LSB-05-PEAK-COMPOSITION-AND-FIXED-CAP-COMPARISON",
    "LSB-06-INDEPENDENT-CHECKER-AND-ADVERSARIAL-MUTATIONS",
    "RSE-07-OPERATION-COST-CLOSURE",
)


class GovernanceError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")
    except (TypeError, ValueError) as error:
        raise GovernanceError("value is not canonical JSON encodable") from error


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _reject_constant(value: str) -> None:
    raise GovernanceError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GovernanceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def loads_strict(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise GovernanceError(f"{label} is not UTF-8") from error
    if text.startswith("\ufeff"):
        raise GovernanceError(f"{label} has a forbidden BOM")
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_pairs, parse_constant=_reject_constant)
    except GovernanceError:
        raise
    except json.JSONDecodeError as error:
        raise GovernanceError(f"{label} is malformed JSON") from error


def _read_regular(path: Path, label: str) -> bytes:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise GovernanceError(f"missing {label}") from error
    if path.is_symlink() or not stat.S_ISREG(mode):
        raise GovernanceError(f"{label} must be a regular non-symlink file")
    return path.read_bytes()


def load_json(path: Path, label: str, *, require_canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    raw = _read_regular(path, label)
    value = loads_strict(raw, label)
    if not isinstance(value, dict):
        raise GovernanceError(f"{label} must be an object")
    if require_canonical and raw != canonical_bytes(value):
        raise GovernanceError(f"{label} is not canonical JSON")
    return value, raw


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True).stdout


def _commit_parent(commit: str) -> str:
    fields = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(fields) != 2 or fields[0] != commit:
        raise GovernanceError("commit must have exactly one parent")
    return fields[1]


def _changed_paths(commit: str) -> dict[str, str]:
    output = _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit)
    rows: dict[str, str] = {}
    for line in output.splitlines():
        status, path = line.split("\t", 1)
        if status not in {"A", "M", "D", "T"} or path in rows:
            raise GovernanceError("malformed committed changed-path set")
        rows[path] = status
    return rows


def _git_blob(commit: str, path: str) -> bytes:
    return _git_bytes("show", f"{commit}:{path}")


def _require_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise GovernanceError(f"{label} key set drift")


def _authority() -> dict[str, Any]:
    return {
        "scientific_authority": "NONE",
        "execution_authority": False,
        "candidate_selection_authority": False,
        "candidate_or_cap_change_authority": False,
        "resource_or_no_go_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }


def _p10_authority() -> dict[str, Any]:
    return {
        "scientific_authority": "NONE",
        "execution_authority": False,
        "candidate_selection_authority": False,
        "candidate_or_cap_change_authority": False,
        "resource_no_go_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version", "contract_id", "contract_role", "self_relative_path",
        "required_direct_parent_commit", "authority", "p10_a_result_custody",
        "allowed_P10_A_governance_projection", "decision_rules",
        "proof_obligation_disposition", "P10_B_feasibility_audit_contract",
        "forbidden_actions", "closure_lifecycle",
    }
    _require_keys(contract, expected, "P10-G1 contract")
    if canonical_sha256(contract) != CONTRACT_CANONICAL_SHA256:
        raise GovernanceError("P10-G1 contract semantic drift")
    if (
        contract["schema_version"] != 1
        or contract["contract_id"] != CONTRACT_ID
        or contract["self_relative_path"] != CONTRACT_NAME
        or contract["required_direct_parent_commit"] != DIRECT_PARENT
        or contract["authority"] != _authority()
    ):
        raise GovernanceError("P10-G1 contract identity or authority drift")
    custody = contract["p10_a_result_custody"]
    if not isinstance(custody, dict) or custody.get("result_commit_sha") != DIRECT_PARENT or custody.get("preprobe_commit_sha") != P10_B0:
        raise GovernanceError("P10-A result custody drift")
    if set(custody.get("preprobe_changed_paths", ())) != P10_B0_PATHS:
        raise GovernanceError("P10-A preprobe paths drift")
    disposition = contract["proof_obligation_disposition"]
    if tuple(disposition.get("ordered_obligation_ids", ())) != OBLIGATION_IDS or disposition.get("P10_A_verified_obligation_count") != 0:
        raise GovernanceError("proof-obligation disposition drift")
    p10b = contract["P10_B_feasibility_audit_contract"]
    if not isinstance(p10b, dict) or p10b.get("only_allowed_next_gate") != NEXT_GATE:
        raise GovernanceError("P10-B next-gate drift")
    for key in ("candidate_execution_allowed", "Julia_execution_allowed", "candidate_or_cap_change_allowed", "resource_no_go_allowed", "scientific_or_S0_result_allowed"):
        if p10b.get(key) is not False:
            raise GovernanceError("P10-B authority drift")
    lifecycle = contract["closure_lifecycle"]
    if lifecycle.get("P10_G1_exact_changed_paths") != list(G1_CHANGED_PATHS):
        raise GovernanceError("P10-G1 lifecycle path drift")
    return dict(contract)


def _validate_p10_topology(contract: Mapping[str, Any]) -> bytes:
    if _commit_parent(P10_B0) != G0 or _commit_parent(DIRECT_PARENT) != P10_B0:
        raise GovernanceError("P10-A B0/B1 parent topology drift")
    if set(_changed_paths(P10_B0)) != P10_B0_PATHS or set(_changed_paths(DIRECT_PARENT)) != {P10_REPORT_PATH}:
        raise GovernanceError("P10-A B0/B1 changed-path set drift")
    if _changed_paths(DIRECT_PARENT).get(P10_REPORT_PATH) != "A":
        raise GovernanceError("P10-A B1 must add only its report")
    for path in P10_B0_PATHS:
        if _git_blob(P10_B0, path) != _git_blob(DIRECT_PARENT, path):
            raise GovernanceError("P10-A B0 source blob differs at B1")
    report = _git_blob(DIRECT_PARENT, P10_REPORT_PATH)
    custody = contract["p10_a_result_custody"]
    if _sha256(report) != custody["report_sha256"]:
        raise GovernanceError("P10-A report digest drift")
    return report


def _project_p10_report(raw: bytes, contract: Mapping[str, Any]) -> dict[str, Any]:
    report = loads_strict(raw, "P10-A result report")
    if not isinstance(report, dict) or raw != canonical_bytes(report):
        raise GovernanceError("P10-A report is malformed or noncanonical")
    assessment = report.get("assessment")
    authority = report.get("authority")
    if not isinstance(assessment, dict) or authority != _p10_authority():
        raise GovernanceError("P10-A report authority drift")
    identity = {
        "schema_version": report.get("schema_version"),
        "gate_id": report.get("gate_id"),
        "report_type": report.get("report_type"),
        "status": report.get("status"),
        "preprobe_commit": report.get("preprobe_commit"),
    }
    byte = assessment.get("byte_envelope")
    proof = assessment.get("proof_obligations")
    admission = assessment.get("admission")
    if not all(isinstance(value, dict) for value in (byte, proof, admission)):
        raise GovernanceError("P10-A report assessment shape drift")
    projection = {
        "identity": identity,
        "authority": authority,
        "assessment_lifecycle_status": assessment.get("assessment_lifecycle_status"),
        "outcome_classification": assessment.get("outcome_classification"),
        "fixed_process_cap_bytes": byte.get("fixed_process_cap_bytes"),
        "exact_static_peak_bytes": byte.get("exact_static_peak_bytes"),
        "strict_integer_peak_less_than_cap": byte.get("strict_integer_peak_less_than_cap"),
        "comparison_status": byte.get("comparison_status"),
        "resource_no_go_inference": byte.get("resource_no_go_inference"),
        "obligation_count": proof.get("obligation_count"),
        "verified_obligation_count": proof.get("verified_obligation_count"),
        "all_seven_obligations_positive": proof.get("all_seven_obligations_positive"),
        "admission_status": admission.get("status"),
        "execution_gate": admission.get("execution_gate"),
        "future_execution_prerequisite_satisfied": admission.get("future_execution_prerequisite_satisfied"),
    }
    expected = contract["allowed_P10_A_governance_projection"]
    if projection["identity"] != expected["identity"] or projection["authority"] != expected["authority"] or {key: projection[key] for key in projection if key not in {"identity", "authority"}} != expected["assessment"]:
        raise GovernanceError("P10-A minimal governance projection drift")
    return projection


def expected_record(contract: Mapping[str, Any], contract_raw: bytes, projection: Mapping[str, Any]) -> dict[str, Any]:
    obligations = [{"obligation_id": item, "status": "NOT_ESTABLISHED"} for item in OBLIGATION_IDS]
    return {
        "P10_A_minimal_governance_projection": dict(projection),
        "S0_authority": False,
        "candidate_or_cap_change_authority": False,
        "candidate_selection_authority": False,
        "certificate_eligible": False,
        "closure_assertions": {
            "P10_A_result_will_not_be_amended": True,
            "P10_G1_does_not_authorize_execution_or_candidate_change": True,
            "P10_G1_does_not_claim_contract_availability_or_a_resource_no_go": True,
            "P10_B_if_started_is_nonexecuting_and_needs_a_new_independent_governance_decision_before_any_byte_proof_or_execution": True,
            "host_or_D4_inputs_do_not_enter_the_governance_record": True,
        },
        "contract_id": CONTRACT_ID,
        "contract_receipt": {
            "canonical_sha256": canonical_sha256(contract),
            "raw_and_canonical_hashes_have_distinct_byte_domains": True,
            "raw_sha256": _sha256(contract_raw),
            "relative_path": CONTRACT_NAME,
            "size_bytes": len(contract_raw),
        },
        "disposition": DISPOSITION,
        "disposition_reason": "P10_A_is_a_closed_valid_negative_assessment_with_zero_of_seven_obligations_verified_and_no_exact_peak_byte_bound;_the_only_authorized_followup_is_to_inventory_whether_independent_static_contract_evidence_can_be_obtained",
        "execution_authority": False,
        "next_gate": {
            "D5_authorized": False,
            "P10_B_allowed_outcomes": ["EVIDENCE_ROUTE_IDENTIFIED_NOT_A_BYTE_PROOF", "CLOSED_NO_INDEPENDENT_STATIC_BYTE_CONTRACT_ROUTE"],
            "P10_B_candidate_execution_allowed": False,
            "P10_B_candidate_or_cap_change_allowed": False,
            "P10_B_gate": NEXT_GATE,
            "P10_B_is_not_a_byte_proof_or_execution": True,
            "P10_B_Julia_execution_allowed": False,
            "P10_B_resource_no_go_allowed": False,
            "a_later_byte_proof_requires_new_independent_governance": True,
            "execution_authorized": False,
            "status": "NONEXECUTING_STATIC_EVIDENCE_FEASIBILITY_AUDIT_REQUIRED",
        },
        "proof_obligation_ledger": {
            "admission_status": "NOT_ESTABLISHED",
            "assessment_status": "CLOSED_NEGATIVE_ASSESSMENT",
            "execution_gate": "CLOSED",
            "obligations": obligations,
            "overall_status": "ASSESSED_NOT_ESTABLISHED",
            "static_resource_envelope_established": False,
        },
        "record_id": RECORD_ID,
        "record_type": "majorana_p10_g1_post_assessment_governance_closure_record_v1",
        "required_direct_parent_commit": DIRECT_PARENT,
        "resource_or_no_go_authority": False,
        "result_contract_eligible": False,
        "schema_version": 1,
        "scientific_authority": "NONE",
    }


def validate_record(record: Mapping[str, Any], contract: Mapping[str, Any], contract_raw: bytes, projection: Mapping[str, Any]) -> dict[str, Any]:
    if dict(record) != expected_record(contract, contract_raw, projection):
        raise GovernanceError("P10-G1 record reconstruction drift")
    return dict(record)


def validate_content() -> dict[str, Any]:
    contract, contract_raw = load_json(BASE / CONTRACT_NAME, "P10-G1 contract")
    validate_contract(contract)
    p10_report = _validate_p10_topology(contract)
    projection = _project_p10_report(p10_report, contract)
    record, record_raw = load_json(BASE / RECORD_NAME, "P10-G1 record", require_canonical=True)
    validate_record(record, contract, contract_raw, projection)
    if record_raw != canonical_bytes(record):
        raise GovernanceError("P10-G1 record canonical-byte drift")
    return {
        "disposition": record["disposition"],
        "next_gate": record["next_gate"]["P10_B_gate"],
        "status": "VERIFIED_P10_G1_POST_ASSESSMENT_GOVERNANCE_CONTENT",
    }


def _staged_paths() -> dict[str, str]:
    output = _git("diff", "--cached", "--name-status", "--no-renames")
    rows: dict[str, str] = {}
    for line in output.splitlines():
        status, path = line.split("\t", 1)
        if status not in {"A", "M"} or path in rows:
            raise GovernanceError("invalid staged changed-path record")
        rows[path] = status
    return rows


def validate_lifecycle() -> str:
    head = _git("rev-parse", "HEAD").strip()
    if head == DIRECT_PARENT:
        if _staged_paths() != G1_CHANGED_PATHS:
            raise GovernanceError("P10-G1 staged changed-path set drift")
        if _git("diff", "--name-only") or _git("ls-files", "--others", "--exclude-standard"):
            raise GovernanceError("P10-G1 staged lifecycle requires no unstaged or untracked paths")
        return "STAGED_DIRECT_CHILD"
    if _commit_parent(head) != DIRECT_PARENT or _changed_paths(head) != G1_CHANGED_PATHS:
        raise GovernanceError("P10-G1 committed parent or changed-path set drift")
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise GovernanceError("P10-G1 committed lifecycle requires a clean worktree")
    return "COMMITTED_DIRECT_CHILD"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-content", action="store_true")
    parser.add_argument("--verify-lifecycle", action="store_true")
    args = parser.parse_args(argv)
    if args.verify_content == args.verify_lifecycle:
        parser.error("choose exactly one verification mode")
    try:
        output = validate_content() if args.verify_content else {"lifecycle": validate_lifecycle(), "status": "VERIFIED_P10_G1_POST_ASSESSMENT_GOVERNANCE_LIFECYCLE"}
    except (GovernanceError, subprocess.CalledProcessError) as error:
        print(f"P10_G1_GOVERNANCE_ERROR: {error}", file=sys.stderr)
        return 2
    print(canonical_bytes(output).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
