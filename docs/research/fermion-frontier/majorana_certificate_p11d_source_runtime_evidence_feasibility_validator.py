#!/usr/bin/env python3
"""Read-only validator for P11-D evidence-feasibility audit."""

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
DIRECT_PARENT = "0960ff5b1e7d1b1d2922e18eb7d5b71cd44a6a30"
P11C = "61f06e3d9eae013303edcd902bd1ef99bff8930f"
CONTRACT_NAME = "majorana_certificate_p11d_source_runtime_evidence_feasibility_contract.json"
REPORT_NAME = "majorana_certificate_p11d_source_runtime_evidence_feasibility_report.json"
MODULE_NAME = "majorana_certificate_p11d_source_runtime_evidence_feasibility_validator.py"
TEST_NAME = "test_majorana_certificate_p11d_source_runtime_evidence_feasibility.py"
CONTRACT_CANONICAL_SHA256 = "77e17775596b01b25099783d4e5690eeaf7e8e145e425011ce77b09832c171c9"
OUTCOME = "SOURCE_CUSTODY_ROUTE_IDENTIFIED_STATIC_KERNEL_ACCOUNTING_NOT_ESTABLISHED"
PREFIX = "docs/research/fermion-frontier/"
G3_PATHS = {
    PREFIX + "ARTIFACTS.md": "M",
    PREFIX + "PROGRESS.md": "M",
    PREFIX + "majorana_certificate_p11_g3_evidence_feasibility_governance_contract.json": "A",
    PREFIX + "majorana_certificate_p11_g3_evidence_feasibility_governance_record.json": "A",
    PREFIX + "majorana_certificate_p11_g3_evidence_feasibility_governance_validator.py": "A",
    PREFIX + "test_majorana_certificate_p11_g3_evidence_feasibility_governance.py": "A",
}
CHANGED_PATHS = {
    PREFIX + "ARTIFACTS.md": "M",
    PREFIX + "PROGRESS.md": "M",
    PREFIX + CONTRACT_NAME: "A",
    PREFIX + REPORT_NAME: "A",
    PREFIX + MODULE_NAME: "A",
    PREFIX + TEST_NAME: "A",
}
DPKG_FORMAT = "-f=${Package}\\t${Version}\\t${Source}\\t${Status}\\n"
ALLOWED_COMMANDS = {
    ("uname", "-srvmo"),
    ("dpkg-query", "-W", DPKG_FORMAT, "binutils", "gcc-15", "linux-image-7.0.0-28-generic"),
    ("apt-cache", "show", "gcc-15"),
    ("apt-cache", "show", "binutils"),
    ("apt-cache", "show", "linux-image-7.0.0-28-generic"),
    ("apt-cache", "show", "linux-image-unsigned-7.0.0-28-generic"),
    ("apt-cache", "showsrc", "gcc-15", "binutils"),
}


class AuditError(RuntimeError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise AuditError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _constant(value: str) -> None:
    raise AuditError(f"non-finite JSON constant: {value}")


def loads_strict(raw: bytes, label: str, *, canonical: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditError(f"malformed {label}") from error
    if not isinstance(value, dict):
        raise AuditError(f"{label} must be an object")
    if canonical and raw != canonical_bytes(value):
        raise AuditError(f"{label} is not canonical JSON")
    return value


def load_json(path: Path, label: str, *, canonical: bool = False) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise AuditError(f"invalid {label} file")
    raw = path.read_bytes()
    return loads_strict(raw, label, canonical=canonical), raw


def _authority() -> dict[str, Any]:
    return {"scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "prototype_or_compilation_authority": False, "candidate_selection_authority": False,
            "candidate_or_cap_change_authority": False, "resource_or_no_go_authority": False,
            "S0_authority": False, "certificate_eligible": False, "result_contract_eligible": False}


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != "MAJORANA-P11-D-SOURCE-CUSTODY-AND-STATIC-RUNTIME-EVIDENCE-FEASIBILITY-AUDIT-V1" or contract.get("required_direct_parent_commit") != DIRECT_PARENT:
        raise AuditError("contract identity drift")
    if contract.get("authority") != _authority() or sha256(canonical_bytes(contract)) != CONTRACT_CANONICAL_SHA256:
        raise AuditError("contract authority or semantic drift")
    scope = contract.get("scope", {})
    for key in ("candidate_source_allowed", "C_assembly_or_linker_script_source_allowed", "compilation_or_linking_allowed",
                "Julia_or_candidate_execution_allowed", "benchmark_or_dynamic_memory_measurement_allowed",
                "package_index_update_installation_or_environment_mutation_allowed", "binary_or_source_archive_download_allowed",
                "scientific_schedule_semantics_or_cap_change_allowed"):
        if scope.get(key) is not False:
            raise AuditError("scope authority drift")
    if contract.get("outcome") != OUTCOME or len(contract.get("evidence_class_disposition", ())) != 7:
        raise AuditError("outcome or evidence-class drift")
    if contract.get("source_custody_route", {}).get("source_archive_custody_established") is not False or contract.get("static_kernel_accounting_assessment", {}).get("static_kernel_cgroup_accounting_bound_established") is not False:
        raise AuditError("custody or kernel-bound overclaim")


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=REPO, check=True, capture_output=True).stdout


def _run_local(command: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    if tuple(command) not in ALLOWED_COMMANDS:
        raise AuditError("non-allowlisted local identity command")
    return subprocess.run(tuple(command), capture_output=True)


def _parent(commit: str) -> str:
    row = _git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if len(row) != 2 or row[0] != commit:
        raise AuditError("commit must have one parent")
    return row[1]


def _paths(commit: str) -> dict[str, str]:
    return {path: status for status, path in (line.split("\t", 1) for line in _git("diff-tree", "--no-commit-id", "--name-status", "-r", "--no-renames", commit).splitlines())}


def validate_sources(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    if _parent(DIRECT_PARENT) != P11C or _paths(DIRECT_PARENT) != G3_PATHS:
        raise AuditError("P11-G3 topology or path drift")
    inputs = contract.get("source_inputs")
    if not isinstance(inputs, list) or len(inputs) != 3:
        raise AuditError("source input list drift")
    values: dict[str, bytes] = {}
    for row in inputs:
        path = row.get("relative_path")
        if not isinstance(path, str) or path in values:
            raise AuditError("source path drift")
        raw = _git_bytes("show", f"{DIRECT_PARENT}:{PREFIX}{path}")
        if sha256(raw) != row.get("sha256"):
            raise AuditError("source digest drift")
        values[path] = raw
    g3 = loads_strict(values["majorana_certificate_p11_g3_evidence_feasibility_governance_record.json"], "P11-G3 record", canonical=True)
    if g3.get("next_gate") != "P11-D-SOURCE-CUSTODY-AND-STATIC-RUNTIME-EVIDENCE-FEASIBILITY-AUDIT-V1" or g3.get("source_archive_download_allowed") is not False or g3.get("candidate_source_allowed") is not False:
        raise AuditError("P11-G3 authority drift")
    return [dict(row) for row in inputs]


def _regular_file(path: Path, *, size: int | None, digest: str) -> None:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise AuditError(f"invalid local receipt file: {path}")
    raw = path.read_bytes()
    if (size is not None and len(raw) != size) or sha256(raw) != digest:
        raise AuditError(f"local receipt file drift: {path}")


def _parse_deb822_types(raw: bytes) -> list[str]:
    values = []
    for line in raw.decode("utf-8").splitlines():
        if line.startswith("Types:"):
            values.extend(line.split(":", 1)[1].strip().split())
    return values


def _visible_source_archives() -> list[str]:
    root = Path("/var/cache/apt/archives")
    out = []
    for path in root.iterdir():
        name = path.name.lower()
        if path.is_file() and (name.endswith(".dsc") or ".orig.tar." in name or ".debian.tar." in name or name.startswith("gcc-15_") or name.startswith("binutils_")):
            out.append(path.name)
    return sorted(out)


def _config_value(raw: str, key: str) -> str | None:
    if f"{key}=y" in raw.splitlines():
        return "y"
    if f"# {key} is not set" in raw.splitlines():
        return "not_set"
    return None


def validate_local_snapshot(contract: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = contract.get("local_read_only_snapshot", {})
    receipts = snapshot.get("command_receipts")
    if not isinstance(receipts, list) or len(receipts) != len(ALLOWED_COMMANDS):
        raise AuditError("command receipt count drift")
    for row in receipts:
        result = _run_local(row["argv"])
        if result.returncode != row.get("returncode") or sha256(result.stdout) != row.get("stdout_sha256") or sha256(result.stderr) != row.get("stderr_sha256"):
            raise AuditError(f"local command receipt drift: {row.get('receipt_id')}")
    for row in snapshot.get("file_receipts", ()):
        _regular_file(Path(row["path"]), size=row.get("size_bytes"), digest=row["sha256"])
    source_path = Path("/etc/apt/sources.list.d/ubuntu.sources")
    types = _parse_deb822_types(source_path.read_bytes())
    source_observation = snapshot.get("source_index_and_cache_observation", {})
    if types != source_observation.get("configured_Ubuntu_Types_values") or "deb-src" in types or source_observation.get("deb_src_enabled") is not False:
        raise AuditError("deb-src observation drift")
    source_indexes = [p for p in Path("/var/lib/apt/lists").iterdir() if "Sources" in p.name]
    visible = _visible_source_archives()
    if len(source_indexes) != source_observation.get("source_index_files_visible_under_var_lib_apt_lists") or visible != source_observation.get("matching_source_archive_files_visible_at_var_cache_apt_archives_top_level"):
        raise AuditError("source index or archive presence drift")
    config_path = Path("/boot/config-7.0.0-28-generic")
    config_text = config_path.read_text(encoding="utf-8")
    host = snapshot.get("host_kernel_and_cgroup_identity", {})
    actual_config = {key: _config_value(config_text, key) for key in host.get("required_kernel_config_rows", {})}
    if actual_config != host.get("required_kernel_config_rows"):
        raise AuditError("kernel config drift")
    membership_rows = Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines()
    if len(membership_rows) != 1 or not membership_rows[0].startswith("0::"):
        raise AuditError("cgroup v2 membership drift")
    membership = membership_rows[0][3:]
    mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    if " - cgroup2 cgroup2 " not in mountinfo or " /sys/fs/cgroup " not in mountinfo:
        raise AuditError("cgroup2 mount drift")
    if membership != host.get("observed_membership_path"):
        raise AuditError("cgroup membership drift")
    cgroup_dir = Path("/sys/fs/cgroup") / membership.lstrip("/")
    missing = [name for name in host.get("required_nonroot_interface_files_present", ()) if not (cgroup_dir / name).is_file()]
    if missing or host.get("dynamic_interface_values_read_or_used") is not False:
        raise AuditError("cgroup interface presence or measurement drift")
    identities = snapshot.get("package_identity_rows", ())
    if [(row.get("source_package"), row.get("source_version")) for row in identities] != [("gcc-15", "15.2.0-16ubuntu1"), ("binutils", "2.46-3ubuntu2"), ("linux-signed", "7.0.0-28.28")]:
        raise AuditError("package-to-source identity drift")
    return {"kernel_release": host["kernel_release"], "cgroup_filesystem": "cgroup2",
            "cgroup_interface_file_count": len(host["required_nonroot_interface_files_present"]),
            "deb_src_enabled": False, "source_index_file_count": 0,
            "visible_matching_source_archive_count": len(visible),
            "toolchain_source_packages": ["gcc-15=15.2.0-16ubuntu1", "binutils=2.46-3ubuntu2"],
            "source_archive_custody_established": False, "dynamic_measurement_performed": False}


def validate_evidence(contract: Mapping[str, Any]) -> dict[str, Any]:
    official = contract.get("official_primary_sources")
    if not isinstance(official, list) or len(official) != 6 or any(row.get("byte_pinned") is not False or not row.get("url", "").startswith("https://") for row in official):
        raise AuditError("official source inventory drift")
    rows = contract.get("evidence_class_disposition")
    statuses = tuple(row.get("status") for row in rows if isinstance(row, dict))
    if len(statuses) != 7 or statuses[0] != "IDENTITY_ESTABLISHED_FROM_LOCAL_BINARY_METADATA_AND_DEBIAN_POLICY" or statuses[-1] != "NOT_ESTABLISHED_REQUIRES_COMPLETE_KERNEL_BOUND_AND_FUTURE_CANDIDATE_POSTLINK_STACK_EVIDENCE":
        raise AuditError("evidence disposition drift")
    kernel = contract.get("static_kernel_accounting_assessment", {})
    if len(kernel.get("official_documentation_findings", ())) != 6 or len(kernel.get("missing_static_bounds", ())) != 7 or kernel.get("exact_static_process_peak_bytes") is not None:
        raise AuditError("kernel assessment drift")
    return {"evidence_class_count": 7, "source_custody_route_status": contract["source_custody_route"]["status"],
            "static_kernel_accounting_status": kernel["status"]}


def expected_report(contract: Mapping[str, Any], raw: bytes, sources: list[dict[str, Any]], local: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "report_type": "majorana_p11_d_source_runtime_evidence_feasibility_report_v1",
            "gate_id": "P11-D-SOURCE-CUSTODY-AND-STATIC-RUNTIME-EVIDENCE-FEASIBILITY-AUDIT-V1",
            "parent_commit": DIRECT_PARENT, "contract_raw_sha256": sha256(raw),
            "contract_canonical_sha256": sha256(canonical_bytes(contract)), "source_inputs": sources,
            "validated_local_projection": dict(local), "validated_evidence_projection": dict(evidence),
            "official_primary_sources": contract["official_primary_sources"],
            "source_custody_route": contract["source_custody_route"],
            "static_kernel_accounting_assessment": contract["static_kernel_accounting_assessment"],
            "evidence_class_disposition": contract["evidence_class_disposition"], "outcome": OUTCOME,
            "source_archive_custody_established": False, "static_kernel_cgroup_accounting_bound_established": False,
            "dynamic_memory_measurement_performed": False, "candidate_implementation_present": False,
            "fixed_process_cap_bytes": 2147483648, "contract_target_component_sum_bytes": 1028653056,
            "difference_to_fixed_cap_bytes": 1118830592, "difference_is_proven_headroom": False,
            "exact_static_process_peak_bytes": None, "strict_integer_peak_less_than_fixed_cap": None,
            "semantic_equivalence_established": False, "implementation_gate": "CLOSED", "execution_gate": "CLOSED",
            "scientific_authority": "NONE", "execution_authority": False, "implementation_authority": False,
            "candidate_selection_authority": False, "candidate_or_cap_change_authority": False,
            "resource_or_no_go_authority": False, "resource_no_go_inference": False, "S0_authority": False,
            "certificate_eligible": False, "result_contract_eligible": False,
            "unresolved_after_audit": contract["unresolved_after_audit"],
            "next_governance_requirement": "NEW_SPLIT_GOVERNANCE_REQUIRED_FOR_SOURCE_ARCHIVE_ACQUISITION_OR_KERNEL_BOUND_RESEARCH"}


def validate_content() -> dict[str, Any]:
    contract, raw = load_json(BASE / CONTRACT_NAME, "P11-D contract")
    validate_contract(contract)
    sources = validate_sources(contract)
    local = validate_local_snapshot(contract)
    evidence = validate_evidence(contract)
    report, _ = load_json(BASE / REPORT_NAME, "P11-D report", canonical=True)
    if report != expected_report(contract, raw, sources, local, evidence):
        raise AuditError("report reconstruction drift")
    return {"status": "VERIFIED_P11_D_SOURCE_RUNTIME_EVIDENCE_FEASIBILITY_AUDIT", "outcome": OUTCOME,
            "source_archive_custody_established": False, "static_kernel_bound_established": False,
            "implementation_gate": "CLOSED", "execution_gate": "CLOSED"}


def validate_lifecycle() -> str:
    if _git("rev-parse", "HEAD").strip() != DIRECT_PARENT:
        raise AuditError("staging must begin at P11-G3")
    staged = {path: status for status, path in (line.split("\t", 1) for line in _git("diff", "--cached", "--name-status", "--no-renames").splitlines())}
    if staged != CHANGED_PATHS:
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
        parser.error("choose a verification mode")
    if args.verify_content:
        print(json.dumps(validate_content(), sort_keys=True))
    if args.verify_lifecycle:
        print(validate_lifecycle())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
