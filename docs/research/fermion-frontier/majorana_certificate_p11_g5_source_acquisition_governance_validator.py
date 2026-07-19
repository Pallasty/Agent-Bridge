#!/usr/bin/env python3
"""Read-only validator for P11-G5 source-acquisition governance."""

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
DIRECT_PARENT = "aacab7a82d2687270f6c4eb5edb7efb9903db303"
G4 = "a26d75d2943a4dd683eaa166656f99a5df39758e"
CONTRACT_NAME = "majorana_certificate_p11_g5_source_acquisition_governance_contract.json"
RECORD_NAME = "majorana_certificate_p11_g5_source_acquisition_governance_record.json"
MODULE_NAME = "majorana_certificate_p11_g5_source_acquisition_governance_validator.py"
TEST_NAME = "test_majorana_certificate_p11_g5_source_acquisition_governance.py"
E0_CONTRACT = "docs/research/fermion-frontier/majorana_certificate_p11e0_source_archive_acquisition_contract.json"
E0_RECORD = "docs/research/fermion-frontier/majorana_certificate_p11e0_source_archive_acquisition_record.json"
CONTRACT_CANONICAL_SHA256 = "c167daf424ffa0d6ebd5ec3821d8697f8385262bdc8a3c50fdeda60b674959a9"
DISPOSITION = "AUTHORIZE_P11_E1_EXACT_ISOLATED_SOURCE_ARCHIVE_ACQUISITION_AND_BYTE_CUSTODY_ONLY"
NEXT_GATE = "P11-E1-EXACT-SOURCE-ARCHIVE-ACQUISITION-AND-BYTE-CUSTODY-V1"
POST_GATE = "P11-G6-POST-SOURCE-CUSTODY-GOVERNANCE-V1"
SNAPSHOT_ID = "20260719T064131Z"
CUSTODY_ROOT = "/Data/CascadeProjects/.ab-evidence/fermion-majorana/p11-e1-source-custody"
IDENTITIES = [
    "gcc-15=15.2.0-16ubuntu1",
    "binutils=2.46-3ubuntu2",
    "linux=7.0.0-28.28",
    "linux-signed=7.0.0-28.28",
]
ORIGINS = [
    "https://archive.ubuntu.com/ubuntu/",
    "https://security.ubuntu.com/ubuntu/",
    "https://snapshot.ubuntu.com/",
]
READINESS_IDS = [
    "direct_parent_topology_and_exact_six_path_custody",
    "four_exact_source_identities_and_P11_D_snapshot_anchor",
    "snapshot_unavailability_and_version_substitution_fail_closed",
    "absolute_new_or_empty_non_symlink_custody_root_outside_Git",
    "isolated_APT_source_lists_cache_status_and_no_host_state_writes",
    "five_exact_snapshot_commands_and_download_only_no_unpack_boundary",
    "keyring_InRelease_Sources_dsc_parts_local_SHA256_chain",
    "Sources_dsc_local_set_equality_and_strict_parser",
    "authenticated_size_budget_atomic_acceptance_receipts_and_bounded_cleanup",
    "candidate_build_execution_kernel_bound_and_scientific_gates_remain_closed",
]
ALLOWED_OUTCOMES = [
    "SOURCE_ARCHIVE_CUSTODY_ESTABLISHED_EXACT_FOUR_PACKAGE_SET",
    "PARTIAL_VERIFIED_SOURCE_ARCHIVES_RETAINED_COMPLETE_SET_CUSTODY_NOT_ESTABLISHED",
    "CLOSED_SNAPSHOT_OR_EXACT_SOURCE_VERSION_UNAVAILABLE",
    "CLOSED_AUTHENTICATION_COMPLETENESS_SPACE_OR_TRANSACTION_FAILURE",
]
E0_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    E0_CONTRACT: "A",
    E0_RECORD: "A",
    "docs/research/fermion-frontier/majorana_certificate_p11e0_source_archive_acquisition_validator.py": "A",
    "docs/research/fermion-frontier/test_majorana_certificate_p11e0_source_archive_acquisition.py": "A",
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
        "candidate_execution_authority": False,
        "candidate_implementation_authority": False,
        "prototype_or_compilation_authority": False,
        "candidate_selection_authority": False,
        "candidate_or_cap_change_authority": False,
        "resource_or_no_go_authority": False,
        "source_archive_acquisition_authority_consumed_in_P11_G5": False,
        "package_or_environment_mutation_authority_consumed_in_P11_G5": False,
        "kernel_accounting_bound_design_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P11-G5-SOURCE-ARCHIVE-ACQUISITION-GOVERNANCE-CLOSURE-V1":
        raise GovernanceError("contract identity drift")
    if contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise GovernanceError("direct parent drift")
    if contract.get("authority") != _authority():
        raise GovernanceError("governance-stage authority drift")
    if sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise GovernanceError("contract semantic drift")

    readiness = contract.get("readiness_review", ())
    if [row.get("check_id") for row in readiness] != READINESS_IDS:
        raise GovernanceError("readiness identity drift")
    if [row.get("status") for row in readiness] != ["PASS"] * len(READINESS_IDS):
        raise GovernanceError("readiness disposition drift")
    decision = contract.get("decision", {})
    if decision.get("disposition") != DISPOSITION or decision.get("only_allowed_next_gate") != NEXT_GATE:
        raise GovernanceError("decision identity drift")
    if decision.get("all_readiness_checks_pass") is not True:
        raise GovernanceError("readiness aggregate drift")
    if decision.get("authorization_is_single_stage_exact_contract_bound_and_fail_closed") is not True:
        raise GovernanceError("authorization scope drift")
    if decision.get("authorization_is_not_consumed_by_P11_G5") is not True:
        raise GovernanceError("authorization consumption drift")
    if decision.get("exact_static_process_peak_bytes") is not None or decision.get("strict_integer_peak_less_than_fixed_cap") is not None:
        raise GovernanceError("peak overclaim drift")
    for key in ("difference_is_proven_headroom", "semantic_equivalence_established", "resource_no_go_inference"):
        if decision.get(key) is not False:
            raise GovernanceError("decision overclaim drift")
    if decision.get("candidate_implementation_gate") != "CLOSED" or decision.get("candidate_execution_gate") != "CLOSED":
        raise GovernanceError("candidate gate drift")

    auth = contract.get("P11_E1_authorization", {})
    if auth.get("gate_id") != NEXT_GATE or auth.get("snapshot_id") != SNAPSHOT_ID:
        raise GovernanceError("P11-E1 identity drift")
    if auth.get("P11_E0_contract_must_match_raw_SHA256") != "43147dc554d1994dfd7d2d6c5400e68648a418c58d99833bccad72be91b8c4a3":
        raise GovernanceError("P11-E0 binding drift")
    if auth.get("exact_source_identities") != IDENTITIES or auth.get("exact_custody_root") != CUSTODY_ROOT:
        raise GovernanceError("P11-E1 source or root drift")
    if auth.get("allowed_network_origins") != ORIGINS:
        raise GovernanceError("network origin drift")
    for key in ("operational_acquisition_runner_source_allowed", "create_and_write_exact_custody_root_allowed",
                "read_apt_get_binary_ubuntu_keyring_and_declared_system_identity_inputs_allowed",
                "network_snapshot_index_and_source_archive_acquisition_allowed",
                "run_only_the_five_exact_P11_E0_apt_get_argv_allowed",
                "hash_parse_verify_receipt_and_atomic_acceptance_allowed"):
        if auth.get(key) is not True:
            raise GovernanceError("P11-E1 required authority drift")
    for key in ("host_etc_apt_var_lib_apt_var_cache_apt_or_dpkg_status_write_allowed",
                "sudo_root_or_privilege_escalation_allowed",
                "credentials_tokens_private_mirrors_proxies_or_third_party_keys_allowed",
                "latest_version_alternate_snapshot_suite_component_package_or_version_substitution_allowed",
                "archive_unpack_patch_or_source_tree_materialization_allowed",
                "kernel_source_reading_or_kernel_accounting_bound_derivation_allowed",
                "candidate_source_linker_script_object_or_executable_allowed",
                "compile_link_disassemble_execute_benchmark_or_dynamic_measurement_allowed",
                "Julia_or_P9_candidate_execution_allowed",
                "scientific_schedule_semantics_or_cap_change_allowed"):
        if auth.get(key) is not False:
            raise GovernanceError("P11-E1 forbidden authority drift")

    limits = contract.get("P11_E1_execution_order_and_limits", {})
    if len(limits.get("required_step_order", ())) != 12:
        raise GovernanceError("P11-E1 step order drift")
    if limits.get("APT_update_attempt_limit") != 1 or limits.get("source_download_attempt_limit_per_package") != 2:
        raise GovernanceError("attempt limit drift")
    if limits.get("Acquire_Retries_inside_each_apt_command") != 0:
        raise GovernanceError("internal retry drift")
    for key in ("runner_must_use_direct_argv_without_shell", "runner_must_not_read_proxy_or_credential_environment_variables",
                "runner_must_clear_environment_except_explicit_locale_PATH_HOME_and_APT_CONFIG_allowlist",
                "network_phase_ends_before_independent_validator",
                "independent_validator_must_be_offline_and_must_not_run_APT_GPG_unpack_build_or_candidate_commands"):
        if limits.get(key) is not True:
            raise GovernanceError("runner or validator boundary drift")

    outputs = contract.get("P11_E1_required_outputs", {})
    if len(outputs.get("external_outputs", ())) != 7 or len(outputs.get("repository_outputs", ())) != 5:
        raise GovernanceError("required output drift")
    if contract.get("P11_E1_allowed_outcomes") != ALLOWED_OUTCOMES:
        raise GovernanceError("allowed outcome drift")
    if contract.get("all_P11_E1_outcomes_keep_archive_unpack_kernel_bound_candidate_implementation_and_execution_closed") is not True:
        raise GovernanceError("outcome boundary drift")
    post = contract.get("post_P11_E1_requirement", {})
    if post.get("next_gate_if_complete_custody") != POST_GATE or post.get("next_gate_if_incomplete_or_failed") != POST_GATE:
        raise GovernanceError("post-P11-E1 gate drift")
    lifecycle = contract.get("P11_E1_lifecycle", {})
    if len(lifecycle.get("exact_changed_paths", ())) != 7:
        raise GovernanceError("P11-E1 lifecycle path drift")
    if lifecycle.get("external_archive_bytes_must_not_be_staged_or_committed") is not True:
        raise GovernanceError("external-byte Git boundary drift")


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


def validate_p11e0(contract: Mapping[str, Any]) -> dict[str, Any]:
    if _parent(DIRECT_PARENT) != G4 or _paths(DIRECT_PARENT) != E0_PATHS:
        raise GovernanceError("P11-E0 topology or path drift")
    custody = contract.get("P11_E0_custody", {})
    contract_raw = _git_bytes("show", f"{DIRECT_PARENT}:{E0_CONTRACT}")
    record_raw = _git_bytes("show", f"{DIRECT_PARENT}:{E0_RECORD}")
    if sha256(contract_raw) != custody.get("contract_raw_sha256") or sha256(record_raw) != custody.get("record_raw_sha256"):
        raise GovernanceError("P11-E0 blob custody drift")
    p11e0_contract = loads_strict(contract_raw, "P11-E0 contract")
    if sha256(canonical_bytes(p11e0_contract)) != custody.get("contract_canonical_sha256"):
        raise GovernanceError("P11-E0 canonical contract drift")
    record = loads_strict(record_raw, "P11-E0 record", canonical=True)
    if record.get("outcome") != custody.get("expected_outcome"):
        raise GovernanceError("P11-E0 outcome drift")
    if record.get("next_governance_gate") != custody.get("expected_next_governance_gate"):
        raise GovernanceError("P11-E0 next gate drift")
    if record.get("snapshot_id") != custody.get("expected_snapshot_id") or record.get("exact_source_identities") != IDENTITIES:
        raise GovernanceError("P11-E0 source identity drift")
    expected_counts = {
        "exact_source_identity_count": len(record.get("exact_source_identities", ())),
        "planned_future_command_count": record.get("planned_future_command_count"),
        "APT_config_line_count": record.get("APT_config_line_count"),
        "future_executor_precondition_count": record.get("future_executor_precondition_count"),
        "archive_trust_chain_step_count": record.get("archive_trust_chain_step_count"),
        "required_set_equality_count": record.get("required_set_equality_count"),
        "canonical_receipt_required_field_count": record.get("canonical_receipt_required_field_count"),
    }
    if expected_counts != {
        "exact_source_identity_count": 4,
        "planned_future_command_count": 5,
        "APT_config_line_count": 17,
        "future_executor_precondition_count": 10,
        "archive_trust_chain_step_count": 6,
        "required_set_equality_count": 3,
        "canonical_receipt_required_field_count": 16,
    }:
        raise GovernanceError("P11-E0 readiness count drift")
    for key in ("P11_E1_source_archive_acquisition_authorized", "source_archive_custody_established",
                "archive_unpack_or_source_tree_materialization_allowed", "static_kernel_cgroup_accounting_bound_established",
                "difference_is_proven_headroom", "semantic_equivalence_established", "resource_no_go_inference"):
        if record.get(key) is not False:
            raise GovernanceError("P11-E0 authority or proof drift")
    if record.get("implementation_gate") != "CLOSED" or record.get("execution_gate") != "CLOSED":
        raise GovernanceError("P11-E0 candidate gate drift")
    return {
        "P11_E0_outcome": record["outcome"],
        "snapshot_id": record["snapshot_id"],
        "exact_source_identity_count": 4,
        "planned_future_command_count": 5,
        "APT_config_line_count": 17,
        "future_executor_precondition_count": 10,
        "archive_trust_chain_step_count": 6,
        "required_set_equality_count": 3,
        "canonical_receipt_required_field_count": 16,
        "source_archive_acquisition_previously_authorized": False,
        "source_archive_custody_established": False,
        "implementation_gate": "CLOSED",
        "execution_gate": "CLOSED",
    }


def expected_record(contract: Mapping[str, Any], raw: bytes, projection: Mapping[str, Any]) -> dict[str, Any]:
    limits = contract["P11_E1_execution_order_and_limits"]
    return {
        "schema_version": 1,
        "record_id": "MAJORANA-P11-G5-SOURCE-ARCHIVE-ACQUISITION-GOVERNANCE-RECORD-V1",
        "parent_commit": DIRECT_PARENT,
        "contract_raw_sha256": sha256(raw),
        "contract_canonical_sha256": sha256(canonical_bytes(contract)),
        "validated_projection": dict(projection),
        "disposition": DISPOSITION,
        "next_gate": NEXT_GATE,
        "post_P11_E1_gate": POST_GATE,
        "readiness_check_count": len(READINESS_IDS),
        "readiness_pass_count": len(READINESS_IDS),
        "P11_E1_source_archive_acquisition_authorized": True,
        "P11_E1_authority_consumed": False,
        "snapshot_id": SNAPSHOT_ID,
        "exact_source_identities": list(IDENTITIES),
        "exact_custody_root": CUSTODY_ROOT,
        "allowed_network_origins": list(ORIGINS),
        "operational_acquisition_runner_source_allowed": True,
        "isolated_custody_root_write_allowed": True,
        "network_snapshot_index_and_source_archive_acquisition_allowed": True,
        "APT_update_attempt_limit": limits["APT_update_attempt_limit"],
        "source_download_attempt_limit_per_package": limits["source_download_attempt_limit_per_package"],
        "Acquire_Retries_inside_each_apt_command": limits["Acquire_Retries_inside_each_apt_command"],
        "P11_E1_exact_changed_path_count": len(contract["P11_E1_lifecycle"]["exact_changed_paths"]),
        "P11_E1_allowed_outcomes": list(ALLOWED_OUTCOMES),
        "host_APT_or_dpkg_state_write_allowed": False,
        "sudo_root_or_privilege_escalation_allowed": False,
        "credentials_private_mirrors_proxies_or_third_party_keys_allowed": False,
        "version_snapshot_or_source_substitution_allowed": False,
        "archive_unpack_or_source_tree_materialization_allowed": False,
        "kernel_source_reading_or_accounting_bound_design_allowed": False,
        "candidate_implementation_allowed": False,
        "candidate_execution_allowed": False,
        "source_archive_custody_established": False,
        "static_kernel_cgroup_accounting_bound_established": False,
        "fixed_process_cap_bytes": 2147483648,
        "exact_static_process_peak_bytes": None,
        "strict_integer_peak_less_than_fixed_cap": None,
        "difference_is_proven_headroom": False,
        "semantic_equivalence_established": False,
        "resource_no_go_inference": False,
        "scientific_authority": "NONE",
        "candidate_execution_authority_consumed_in_P11_G5": False,
        "candidate_implementation_authority_consumed_in_P11_G5": False,
        "source_archive_acquisition_authority_consumed_in_P11_G5": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P11-G5 contract")
    validate_contract(contract)
    projection = validate_p11e0(contract)
    record, _ = load_json(BASE / RECORD_NAME, "P11-G5 record", canonical=True)
    if record != expected_record(contract, raw, projection):
        raise GovernanceError("record reconstruction drift")
    return {
        "status": "VERIFIED_P11_G5_SOURCE_ARCHIVE_ACQUISITION_GOVERNANCE",
        "disposition": DISPOSITION,
        "next_gate": NEXT_GATE,
        "P11_E1_authority_consumed": False,
        "candidate_implementation_gate": "CLOSED",
        "candidate_execution_gate": "CLOSED",
    }


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise GovernanceError("staging must begin at P11-E0")
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
