#!/usr/bin/env python3
"""Git-only validator for the nonexecuting P11-E0 acquisition contract pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
DIRECT_PARENT = "a26d75d2943a4dd683eaa166656f99a5df39758e"
P11D = "00d74c729bbc9322e215d6beab603f28e79d9923"
CONTRACT_NAME = "majorana_certificate_p11e0_source_archive_acquisition_contract.json"
RECORD_NAME = "majorana_certificate_p11e0_source_archive_acquisition_record.json"
MODULE_NAME = "majorana_certificate_p11e0_source_archive_acquisition_validator.py"
TEST_NAME = "test_majorana_certificate_p11e0_source_archive_acquisition.py"
G4_CONTRACT = "docs/research/fermion-frontier/majorana_certificate_p11_g4_split_governance_contract.json"
G4_RECORD = "docs/research/fermion-frontier/majorana_certificate_p11_g4_split_governance_record.json"
P11D_CONTRACT = "docs/research/fermion-frontier/majorana_certificate_p11d_source_runtime_evidence_feasibility_contract.json"
P11D_REPORT = "docs/research/fermion-frontier/majorana_certificate_p11d_source_runtime_evidence_feasibility_report.json"
CONTRACT_CANONICAL_SHA256 = "8bec22d3bc8855f1c2ac0f2c214e1f68de49af2eec82e998f392d299d56ae7bc"
OUTCOME = "SOURCE_ARCHIVE_ACQUISITION_CONTRACT_PACK_ESTABLISHED_AWAITING_INDEPENDENT_AUTHORIZATION"
NEXT_GATE = "P11-G5-SOURCE-ARCHIVE-ACQUISITION-AUTHORIZATION-V1"
SNAPSHOT_ID = "20260719T064131Z"
IDENTITIES = [
    "gcc-15=15.2.0-16ubuntu1",
    "binutils=2.46-3ubuntu2",
    "linux=7.0.0-28.28",
    "linux-signed=7.0.0-28.28",
]
DEB822 = (
    "Types: deb-src\n"
    "URIs: https://archive.ubuntu.com/ubuntu/\n"
    "Suites: resolute resolute-updates\n"
    "Components: main restricted universe multiverse\n"
    "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n"
    f"Snapshot: {SNAPSHOT_ID}\n\n"
    "Types: deb-src\n"
    "URIs: https://security.ubuntu.com/ubuntu/\n"
    "Suites: resolute-security\n"
    "Components: main restricted universe multiverse\n"
    "Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n"
    f"Snapshot: {SNAPSHOT_ID}\n"
)
APT_LINES = [
    "Dir::Etc::SourceList \"${CUSTODY_ROOT}/apt/ubuntu.sources\";",
    "Dir::Etc::SourceParts \"-\";",
    "Dir::Etc::Parts \"-\";",
    "Dir::Etc::main \"-\";",
    "Dir::State::Lists \"${CUSTODY_ROOT}/apt/lists\";",
    "Dir::State::status \"${CUSTODY_ROOT}/apt/empty-status\";",
    "Dir::Cache::archives \"${CUSTODY_ROOT}/apt/archives\";",
    "Dir::Cache::pkgcache \"\";",
    "Dir::Cache::srcpkgcache \"\";",
    "APT::Get::List-Cleanup \"false\";",
    "APT::Get::Download-Only \"true\";",
    "APT::Get::Only-Source \"true\";",
    "Acquire::AllowInsecureRepositories \"false\";",
    "Acquire::AllowDowngradeToInsecureRepositories \"false\";",
    "Acquire::Check-Valid-Until \"true\";",
    "Acquire::Languages \"none\";",
    "Acquire::Retries \"0\";",
]
G4_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    G4_CONTRACT: "A",
    G4_RECORD: "A",
    "docs/research/fermion-frontier/majorana_certificate_p11_g4_split_governance_validator.py": "A",
    "docs/research/fermion-frontier/test_majorana_certificate_p11_g4_split_governance.py": "A",
}
CHANGED_PATHS = {
    "docs/research/fermion-frontier/ARTIFACTS.md": "M",
    "docs/research/fermion-frontier/PROGRESS.md": "M",
    f"docs/research/fermion-frontier/{CONTRACT_NAME}": "A",
    f"docs/research/fermion-frontier/{RECORD_NAME}": "A",
    f"docs/research/fermion-frontier/{MODULE_NAME}": "A",
    f"docs/research/fermion-frontier/{TEST_NAME}": "A",
}


class ContractError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ContractError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _constant(value: str) -> None:
    raise ContractError(f"non-finite JSON constant: {value}")


def loads_strict(raw: bytes, label: str, *, canonical: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError(f"malformed {label}") from error
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    if canonical and raw != canonical_bytes(value):
        raise ContractError(f"{label} is not canonical JSON")
    return value


def load_json(path: Path, label: str, *, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise ContractError(f"invalid {label} file")
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
        "package_or_environment_mutation_authority": False,
        "network_or_source_archive_acquisition_authority": False,
        "source_archive_unpack_or_materialization_authority": False,
        "kernel_accounting_bound_design_authority": False,
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }


def _planned_commands() -> list[dict[str, Any]]:
    rows = [
        ("APT_UPDATE_ISOLATED_SNAPSHOT", "${CUSTODY_ROOT}", ["apt-get", "--snapshot", SNAPSHOT_ID, "update"]),
        ("APT_SOURCE_GCC15", "${CUSTODY_ROOT}/incoming/gcc-15", ["apt-get", "--snapshot", SNAPSHOT_ID, "--download-only", "--only-source", "source", "gcc-15=15.2.0-16ubuntu1"]),
        ("APT_SOURCE_BINUTILS", "${CUSTODY_ROOT}/incoming/binutils", ["apt-get", "--snapshot", SNAPSHOT_ID, "--download-only", "--only-source", "source", "binutils=2.46-3ubuntu2"]),
        ("APT_SOURCE_LINUX", "${CUSTODY_ROOT}/incoming/linux", ["apt-get", "--snapshot", SNAPSHOT_ID, "--download-only", "--only-source", "source", "linux=7.0.0-28.28"]),
        ("APT_SOURCE_LINUX_SIGNED", "${CUSTODY_ROOT}/incoming/linux-signed", ["apt-get", "--snapshot", SNAPSHOT_ID, "--download-only", "--only-source", "source", "linux-signed=7.0.0-28.28"]),
    ]
    return [
        {
            "step_id": step_id,
            "cwd": cwd,
            "environment": {"APT_CONFIG": "${CUSTODY_ROOT}/apt/apt.conf"},
            "argv": argv,
            "allowed_in_P11_E0": False,
        }
        for step_id, cwd, argv in rows
    ]


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P11-E0-SOURCE-ARCHIVE-ACQUISITION-CONTRACT-PACK-V1":
        raise ContractError("contract identity drift")
    if contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise ContractError("direct parent drift")
    if contract.get("authority") != _authority():
        raise ContractError("authority drift")
    if sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise ContractError("contract semantic drift")

    snapshot = contract.get("snapshot_anchor", {})
    if snapshot.get("snapshot_id") != SNAPSHOT_ID or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", SNAPSHOT_ID):
        raise ContractError("snapshot identity drift")
    if snapshot.get("snapshot_service_availability_or_package_presence_checked_in_P11_E0") is not False:
        raise ContractError("snapshot availability overclaim")
    if snapshot.get("future_P11_E1_must_fail_closed_if_snapshot_or_any_exact_version_is_unavailable") is not True:
        raise ContractError("snapshot fail-closed drift")
    if snapshot.get("fallback_to_latest_or_different_snapshot_allowed") is not False:
        raise ContractError("snapshot fallback drift")

    identities = [f"{row.get('source_package')}={row.get('source_version')}" for row in contract.get("exact_source_identities", ())]
    if identities != IDENTITIES:
        raise ContractError("exact source identity drift")
    deb822 = contract.get("deb822_source_template", {})
    if deb822.get("exact_utf8_text") != DEB822 or deb822.get("only_deb_src_entries") is not True:
        raise ContractError("deb822 template drift")
    if deb822.get("trusted_yes_allow_insecure_or_signature_bypass_present") is not False:
        raise ContractError("deb822 authentication bypass drift")
    apt = contract.get("apt_config_template", {})
    if apt.get("exact_lines") != APT_LINES:
        raise ContractError("APT config template drift")
    if apt.get("host_etc_apt_host_lists_host_cache_or_host_dpkg_status_may_be_written") is not False:
        raise ContractError("host APT write boundary drift")
    if apt.get("unlisted_system_APT_configuration_may_be_loaded") is not False:
        raise ContractError("APT config isolation drift")
    if contract.get("future_P11_E1_command_plan") != _planned_commands():
        raise ContractError("future command plan drift")

    layout = contract.get("isolated_custody_layout", {})
    if len(layout.get("paths", ())) != 11 or layout.get("repository_archive_ingestion_allowed") is not False:
        raise ContractError("custody layout drift")
    if layout.get("root_must_be_absolute_non_symlink_new_or_empty_and_outside_git_worktrees") is not True:
        raise ContractError("custody root boundary drift")
    if len(contract.get("future_executor_preconditions", ())) != 10:
        raise ContractError("future precondition drift")

    auth = contract.get("authentication_and_completeness_rules", {})
    if len(auth.get("archive_trust_chain", ())) != 6 or len(auth.get("required_set_equalities", ())) != 3:
        raise ContractError("authentication chain drift")
    if auth.get("unsigned_or_unverifiable_repository_metadata_allowed") is not False:
        raise ContractError("unsigned metadata authority drift")
    if auth.get("archive_unpack_patch_or_source_tree_materialization_allowed") is not False:
        raise ContractError("archive materialization authority drift")
    selection = auth.get("Sources_stanza_selection", {})
    if selection.get("zero_matches") != "FAIL_CLOSED" or selection.get("multiple_conflicting_matches") != "FAIL_CLOSED":
        raise ContractError("Sources selection drift")
    parser = auth.get("dsc_parser", {})
    for key in ("duplicate_control_fields_forbidden", "duplicate_Checksums_Sha256_filenames_forbidden",
                "filename_must_equal_basename_and_have_no_path_component_equal_to_dot_or_dotdot"):
        if parser.get(key) is not True:
            raise ContractError("dsc parser drift")

    space = contract.get("space_and_transaction_rules", {})
    if space.get("minimum_free_bytes_formula") != "expected_download_bytes + max(67108864, ceil(expected_download_bytes / 10))":
        raise ContractError("space formula drift")
    if space.get("partial_package_acceptance_allowed") is not False:
        raise ContractError("partial acceptance drift")
    receipt = contract.get("canonical_receipt_contract", {})
    if len(receipt.get("required_fields", ())) != 16:
        raise ContractError("receipt field drift")
    if receipt.get("receipt_without_retained_verified_bytes_is_not_custody") is not True:
        raise ContractError("receipt custody boundary drift")
    failure = contract.get("failure_cleanup_and_retry", {})
    if failure.get("resume_or_reuse_of_partial_download_bytes_allowed") is not False:
        raise ContractError("partial retry drift")
    if failure.get("network_success_without_complete_authentication_and_set_equality_is_failure") is not True:
        raise ContractError("network success boundary drift")

    decision = contract.get("decision", {})
    if decision.get("outcome") != OUTCOME or decision.get("next_governance_gate") != NEXT_GATE:
        raise ContractError("decision identity drift")
    for key in ("P11_E1_source_archive_acquisition_authorized", "source_archive_custody_established",
                "source_tree_materialized", "static_kernel_cgroup_accounting_bound_established",
                "difference_is_proven_headroom", "semantic_equivalence_established", "resource_no_go_inference"):
        if decision.get(key) is not False:
            raise ContractError("decision authority or proof drift")
    if decision.get("exact_static_process_peak_bytes") is not None or decision.get("strict_integer_peak_less_than_fixed_cap") is not None:
        raise ContractError("decision exact peak overclaim")
    if decision.get("implementation_gate") != "CLOSED" or decision.get("execution_gate") != "CLOSED":
        raise ContractError("candidate gate drift")


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True).stdout


def _parent(commit: str) -> str:
    row = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(row) != 2 or row[0] != commit:
        raise ContractError("commit must have one parent")
    return row[1]


def _paths(commit: str) -> dict[str, str]:
    return {
        path: status
        for status, path in (
            line.split("\t", 1)
            for line in _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit).splitlines()
        )
    }


def _commit_snapshot_id(commit: str) -> str:
    stamp = _git("show", "-s", "--format=%cI", commit).strip()
    instant = datetime.fromisoformat(stamp).astimezone(timezone.utc)
    return instant.strftime("%Y%m%dT%H%M%SZ")


def validate_g4(contract: Mapping[str, Any]) -> dict[str, Any]:
    if _parent(DIRECT_PARENT) != P11D or _paths(DIRECT_PARENT) != G4_PATHS:
        raise ContractError("P11-G4 topology or path drift")
    if _commit_snapshot_id(P11D) != SNAPSHOT_ID:
        raise ContractError("snapshot does not match P11-D commit instant")
    blobs = {
        Path(G4_CONTRACT).name: _git_bytes("show", f"{DIRECT_PARENT}:{G4_CONTRACT}"),
        Path(G4_RECORD).name: _git_bytes("show", f"{DIRECT_PARENT}:{G4_RECORD}"),
        Path(P11D_CONTRACT).name: _git_bytes("show", f"{DIRECT_PARENT}:{P11D_CONTRACT}"),
        Path(P11D_REPORT).name: _git_bytes("show", f"{DIRECT_PARENT}:{P11D_REPORT}"),
    }
    inputs = {row.get("relative_path"): row.get("sha256") for row in contract.get("source_inputs", ())}
    if set(inputs) != set(blobs):
        raise ContractError("source input path drift")
    for name, raw in blobs.items():
        if sha256(raw) != inputs[name]:
            raise ContractError(f"source blob custody drift: {name}")
    g4_contract = loads_strict(blobs[Path(G4_CONTRACT).name], "P11-G4 contract")
    if sha256(canonical_bytes(g4_contract)) != "d02ccaf69d91704658e2216088d2131d8a3f5d14c52ae448d48a0ec8eced93e5":
        raise ContractError("P11-G4 contract semantic drift")
    g4_record = loads_strict(blobs[Path(G4_RECORD).name], "P11-G4 record", canonical=True)
    if g4_record.get("disposition") != "OPEN_NONIMPLEMENTING_P11_E0_SOURCE_ARCHIVE_ACQUISITION_CONTRACT_PACK_ONLY_DEFER_P11_E2_KERNEL_BOUND_DESIGN":
        raise ContractError("P11-G4 disposition drift")
    if g4_record.get("next_gate") != "P11-E0-SOURCE-ARCHIVE-ACQUISITION-CONTRACT-PACK-V1":
        raise ContractError("P11-G4 next gate drift")
    if g4_record.get("route_A_contract_pack_allowed") is not True:
        raise ContractError("P11-G4 contract authority drift")
    for key in ("package_source_configuration_mutation_allowed", "package_index_refresh_allowed",
                "source_archive_download_allowed", "source_archive_custody_established",
                "static_kernel_cgroup_accounting_bound_established", "difference_is_proven_headroom",
                "semantic_equivalence_established", "resource_no_go_inference"):
        if g4_record.get(key) is not False:
            raise ContractError("P11-G4 forbidden authority drift")
    if g4_record.get("implementation_gate") != "CLOSED" or g4_record.get("execution_gate") != "CLOSED":
        raise ContractError("P11-G4 candidate gate drift")
    return {
        "P11_G4_disposition": g4_record["disposition"],
        "P11_G4_next_gate": g4_record["next_gate"],
        "P11_D_snapshot_anchor": SNAPSHOT_ID,
        "route_A_contract_pack_allowed": True,
        "source_archive_download_allowed": False,
        "source_archive_custody_established": False,
        "kernel_accounting_bound_design_allowed": False,
        "implementation_gate": "CLOSED",
        "execution_gate": "CLOSED",
    }


def expected_record(contract: Mapping[str, Any], raw: bytes, projection: Mapping[str, Any]) -> dict[str, Any]:
    decision = contract["decision"]
    return {
        "schema_version": 1,
        "record_id": "MAJORANA-P11-E0-SOURCE-ARCHIVE-ACQUISITION-RECORD-V1",
        "parent_commit": DIRECT_PARENT,
        "contract_raw_sha256": sha256(raw),
        "contract_canonical_sha256": sha256(canonical_bytes(contract)),
        "validated_projection": dict(projection),
        "outcome": OUTCOME,
        "next_governance_gate": NEXT_GATE,
        "snapshot_id": SNAPSHOT_ID,
        "exact_source_identities": list(IDENTITIES),
        "deb822_stanza_count": DEB822.count("Types: deb-src\n"),
        "APT_config_line_count": len(APT_LINES),
        "planned_future_command_count": len(_planned_commands()),
        "isolated_custody_path_count": len(contract["isolated_custody_layout"]["paths"]),
        "future_executor_precondition_count": len(contract["future_executor_preconditions"]),
        "archive_trust_chain_step_count": len(contract["authentication_and_completeness_rules"]["archive_trust_chain"]),
        "required_set_equality_count": len(contract["authentication_and_completeness_rules"]["required_set_equalities"]),
        "canonical_receipt_required_field_count": len(contract["canonical_receipt_contract"]["required_fields"]),
        "official_primary_source_pointer_count": len(contract["official_primary_sources"]),
        "package_or_environment_mutation_authority": False,
        "network_or_source_archive_acquisition_authority": False,
        "P11_E1_source_archive_acquisition_authorized": False,
        "source_archive_custody_established": False,
        "archive_unpack_or_source_tree_materialization_allowed": False,
        "kernel_accounting_bound_design_authority": False,
        "static_kernel_cgroup_accounting_bound_established": False,
        "fixed_process_cap_bytes": decision["fixed_process_cap_bytes"],
        "exact_static_process_peak_bytes": None,
        "strict_integer_peak_less_than_fixed_cap": None,
        "difference_is_proven_headroom": False,
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
        "S0_authority": False,
        "certificate_eligible": False,
        "result_contract_eligible": False,
    }


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P11-E0 contract")
    validate_contract(contract)
    projection = validate_g4(contract)
    record, _ = load_json(BASE / RECORD_NAME, "P11-E0 record", canonical=True)
    if record != expected_record(contract, raw, projection):
        raise ContractError("record reconstruction drift")
    return {
        "status": "VERIFIED_P11_E0_SOURCE_ARCHIVE_ACQUISITION_CONTRACT_PACK",
        "outcome": OUTCOME,
        "next_governance_gate": NEXT_GATE,
        "source_archive_acquisition_authorized": False,
        "implementation_gate": "CLOSED",
        "execution_gate": "CLOSED",
    }


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise ContractError("staging must begin at P11-G4")
    staged = {
        path: status
        for status, path in (
            line.split("\t", 1)
            for line in _git("diff", "--cached", "--name-status", "--no-renames").splitlines()
        )
    }
    if staged != CHANGED_PATHS:
        raise ContractError("staged changed-path set drift")
    if _git("diff", "--name-only").strip() or _git("ls-files", "--others", "--exclude-standard").strip():
        raise ContractError("unstaged or untracked files are forbidden")
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
