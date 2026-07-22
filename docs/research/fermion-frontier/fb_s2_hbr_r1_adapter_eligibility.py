#!/usr/bin/env python3
"""Fail-closed FB-S2 qualification of a source-bound BioCortex HBR-R1 adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import resource
import stat
import subprocess
import sys
import time
from typing import Any, Dict, Mapping, Sequence, Tuple


HERE = pathlib.Path(__file__).resolve().parent
CONTRACT_PATH = HERE / "fb_s2_hbr_r1_adapter_eligibility_contract.json"
FROZEN_CONTRACT_SHA256 = "f4b64721b8a04c8a0e9225224b125bc452e0acbf58375b184b0b4b1d35214049"
EXPECTED_SCHEMA = "agent_bridge.fermion_biocortex.fb_s2_hbr_r1_adapter_eligibility_contract.v1"
FROZEN_STATUS = "PUBLIC_EVIDENCE_AUDIT_PROTOCOL_FROZEN_AFTER_RECONNAISSANCE_BEFORE_AUTOMATED_CHECK"
REQUIRES_V2 = "REQUIRES_NEW_HASH_BOUND_POSITIVE_QUALIFICATION_V2"
NO_GO = "NO_GO_ADAPTER_ELIGIBILITY"
INDETERMINATE = "INDETERMINATE_SOURCE_AUTHORITY"


class EligibilityError(RuntimeError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def reject_constant(token: str) -> None:
    raise EligibilityError(f"non-finite JSON constant is forbidden: {token}")


def load_json(path: pathlib.Path) -> Dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"), parse_constant=reject_constant
    )
    if not isinstance(value, dict):
        raise EligibilityError(f"JSON root must be an object: {path}")
    return value


def load_contract(path: pathlib.Path = CONTRACT_PATH) -> Dict[str, Any]:
    actual_hash = sha256_path(path)
    if actual_hash != FROZEN_CONTRACT_SHA256:
        raise EligibilityError(f"frozen contract hash mismatch: {actual_hash}")
    contract = load_json(path)
    if contract.get("schema") != EXPECTED_SCHEMA:
        raise EligibilityError("contract schema mismatch")
    if contract.get("status") != FROZEN_STATUS:
        raise EligibilityError("contract status mismatch")
    if contract.get("confirmation_authority") is not False:
        raise EligibilityError("post-reconnaissance audit cannot claim confirmation authority")
    if contract.get("positive_qualification_authority") is not False:
        raise EligibilityError("one-sided v1 cannot claim positive qualification authority")
    if contract.get("chronology", {}).get("outcome_blind_preregistration_claimed") is not False:
        raise EligibilityError("outcome-blind chronology claim is forbidden")
    if any(value is not False for value in contract.get("nonclaims", {}).values()):
        raise EligibilityError("every nonclaim must remain false")
    rules = contract.get("decision_rule", {})
    if rules != {
        "missing_commit_tree_binding_or_unrunnable_integrity_gate": INDETERMINATE,
        "any_bound_eligibility_gate_false_or_missing": NO_GO,
        "all_bound_eligibility_gates_true": REQUIRES_V2,
    }:
        raise EligibilityError("decision rule drift")
    if contract.get("stop_rules") != {
        "no_candidate_execution_when_not_eligible": True,
        "no_adapter_construction_under_design_only_authority": True,
        "no_new_proxy_or_reservoir_substitute": True,
        "no_fresh_holdout_materialization_or_reveal_when_not_eligible": True,
        "no_threshold_seed_split_or_source_rebinding_after_receipt": True,
    }:
        raise EligibilityError("stop rule drift")
    bindings = contract.get("source_bindings")
    if not isinstance(bindings, list) or not bindings:
        raise EligibilityError("source bindings must be a non-empty list")
    paths = [row.get("path") for row in bindings]
    if any(not isinstance(path_value, str) or not path_value for path_value in paths):
        raise EligibilityError("invalid source binding path")
    if len(paths) != len(set(paths)):
        raise EligibilityError("duplicate source binding path")
    return contract


def git_environment() -> Dict[str, str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": os.environ.get("HOME", "/nonexistent"),
        "LC_ALL": "C",
        "LANG": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
    }
    return env


def git(
    repository: pathlib.Path,
    arguments: Sequence[str],
    *,
    binary: bool = False,
    check: bool = True,
    timeout: int = 30,
) -> bytes | str:
    completed = subprocess.run(
        ["/usr/bin/git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        env=git_environment(),
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace")[:1000]
        raise EligibilityError(
            f"git {' '.join(arguments)} failed with {completed.returncode}: {stderr}"
        )
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", "strict").strip()


def parse_tree(raw: bytes) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, path_bytes = record.partition(b"\t")
        if not separator:
            raise EligibilityError("malformed git tree record")
        try:
            mode, object_type, blob = metadata.decode("ascii").split(" ")
            path_value = path_bytes.decode("utf-8", "strict")
        except (UnicodeDecodeError, ValueError) as error:
            raise EligibilityError("malformed git tree encoding") from error
        if object_type != "blob" or path_value in result:
            raise EligibilityError("unexpected or duplicate recursive tree entry")
        result[path_value] = {"mode": mode, "blob": blob}
    return result


def blob(repository: pathlib.Path, commit: str, path: str) -> bytes:
    value = git(repository, ["cat-file", "blob", f"{commit}:{path}"], binary=True)
    assert isinstance(value, bytes)
    return value


def parse_tsv_map(value: bytes, label: str) -> Dict[str, str]:
    try:
        text = value.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise EligibilityError(f"{label} is not UTF-8") from error
    result: Dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        cells = line.split("\t")
        if len(cells) != 2 or not re.fullmatch(r"[A-Za-z0-9_]+", cells[0]) or not cells[1]:
            raise EligibilityError(f"malformed {label} row {line_number}")
        if cells[0] in result:
            raise EligibilityError(f"duplicate {label} key: {cells[0]}")
        result[cells[0]] = cells[1]
    if not result:
        raise EligibilityError(f"empty {label}")
    return result


def parse_tsv_prefix_map(value: bytes, label: str) -> Dict[str, str]:
    """Parse a leading two-column map before a mixed TSV table begins."""
    try:
        text = value.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise EligibilityError(f"{label} is not UTF-8") from error
    result: Dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        cells = line.split("\t")
        if len(cells) != 2:
            break
        if not re.fullmatch(r"[A-Za-z0-9_]+", cells[0]) or not cells[1]:
            raise EligibilityError(f"malformed {label} row {line_number}")
        if cells[0] in result:
            raise EligibilityError(f"duplicate {label} key: {cells[0]}")
        result[cells[0]] = cells[1]
    if not result:
        raise EligibilityError(f"empty {label}")
    return result


def parse_gate_map(value: bytes, label: str) -> Dict[str, str]:
    """Parse the bound BioCortex gate's one-key-per-line key=value output."""
    try:
        text = value.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise EligibilityError(f"{label} is not UTF-8") from error
    result: Dict[str, str] = {}
    terminal_message = (
        "language P3-A2 HBR-R1 runtime-adapter entry contract passed"
    )
    lines = text.splitlines()
    for line_number, line in enumerate(lines, 1):
        if line == terminal_message:
            if "terminal_message" in result:
                raise EligibilityError(f"duplicate {label} terminal message")
            result["terminal_message"] = line
            continue
        key, separator, field_value = line.partition("=")
        if (
            separator != "="
            or re.fullmatch(r"[A-Za-z0-9_]+", key) is None
            or not field_value
            or key in result
        ):
            raise EligibilityError(f"malformed {label} row {line_number}")
        result[key] = field_value
    if not result:
        raise EligibilityError(f"empty {label}")
    if result.get("terminal_message") != terminal_message or lines[-1] != terminal_message:
        raise EligibilityError(f"{label} fixed terminal message is absent or misplaced")
    return result


def parse_bool(value: str | None) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def parse_nonnegative_integer(value: str | None) -> int | None:
    if value is None or re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        return None
    return int(value)


def verify_record_path_hashes(
    repository: pathlib.Path,
    commit: str,
    tree: Mapping[str, Mapping[str, str]],
    record: Mapping[str, str],
    label: str,
) -> Dict[str, Any]:
    pairs = []
    mismatches = []
    for key, path_value in sorted(record.items()):
        if (
            not key.endswith("_path")
            or key.startswith("member_")
            or path_value == "UNSET"
        ):
            continue
        sha_key = key[: -len("_path")] + "_sha256"
        expected_sha = record.get(sha_key)
        if expected_sha is None or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None:
            continue
        entry = tree.get(path_value)
        passed = False
        actual_sha = None
        if entry is not None:
            actual_sha = sha256_bytes(blob(repository, commit, path_value))
            passed = actual_sha == expected_sha
        if not passed:
            mismatches.append(key)
        pairs.append(
            {
                "path_key": key,
                "path": path_value,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "pass": passed,
            }
        )
    expected_pair_count = parse_nonnegative_integer(
        record.get("evidence_path_hash_pair_count")
    )
    if expected_pair_count is not None and len(pairs) != expected_pair_count:
        mismatches.append("evidence_path_hash_pair_count")
    member_count = parse_nonnegative_integer(record.get("member_count"))
    if member_count is not None:
        for index in range(1, member_count + 1):
            prefix = f"member_{index:02d}_"
            path_key = prefix + "path"
            path_value = record.get(path_key)
            expected_sha = record.get(prefix + "sha256")
            expected_mode = record.get(prefix + "mode")
            entry = tree.get(path_value or "")
            actual_sha = None
            passed = False
            if (
                path_value
                and entry is not None
                and expected_sha
                and re.fullmatch(r"[0-9a-f]{64}", expected_sha)
            ):
                actual_sha = sha256_bytes(blob(repository, commit, path_value))
                mode_pass = expected_mode is not None and entry["mode"].endswith(
                    expected_mode[-4:]
                )
                passed = actual_sha == expected_sha and mode_pass
            if not passed:
                mismatches.append(path_key)
            pairs.append(
                {
                    "path_key": path_key,
                    "path": path_value,
                    "expected_sha256": expected_sha,
                    "actual_sha256": actual_sha,
                    "pass": passed,
                }
            )
    return {
        "record": label,
        "pair_count": len(pairs),
        "pairs": pairs,
        "mismatches": sorted(set(mismatches)),
        "pass": bool(pairs) and not mismatches,
    }


def cross_record_authority_consistency(
    records: Mapping[str, Mapping[str, str]]
) -> Dict[str, Any]:
    runtime = records["runtime"]
    fields = (
        "informational_only",
        "route_closed_current_chain",
        "reopen_currently_authorized",
        "runtime_adapter_contract_authority",
        "runtime_adapter_implementation_authority",
        "materialized_adapter_anchor_authority",
        "candidate_artifact_construction_authority",
        "candidate_compilation_authority",
        "candidate_implementation_authority",
        "candidate_execution_authority",
        "source_execution_authority",
        "materialized_runtime_adapter_root_present",
        "materialized_entry_anchor_present",
        "runtime_adapter_impl_present",
        "registered_arm_executor_impl_head_count",
        "bound_runtime_subject_count",
        "accepted_registry_instance_count",
        "case_path_closure_complete",
        "candidate_constructed",
        "candidate_compiled",
        "candidate_linked",
        "candidate_executed",
        "source_parsed",
        "source_compiled",
        "source_linked",
        "source_executed",
        "runtime_authority",
        "agent_bridge_authority",
        "agent_bridge_influence",
        "ab_memory_access",
        "validation_receipt_scope",
    )
    comparisons = []
    mismatches = []
    for record_name, record in records.items():
        if record_name == "runtime":
            continue
        shared_count = 0
        for field in fields:
            if field not in runtime or field not in record:
                continue
            shared_count += 1
            passed = runtime[field] == record[field]
            comparisons.append(
                {
                    "record": record_name,
                    "field": field,
                    "runtime": runtime[field],
                    "other": record[field],
                    "pass": passed,
                }
            )
            if not passed:
                mismatches.append(f"{record_name}:{field}")
        if shared_count == 0:
            mismatches.append(f"{record_name}:NO_SHARED_AUTHORITY_FIELD")
    return {
        "comparisons": comparisons,
        "mismatches": mismatches,
        "pass": bool(comparisons) and not mismatches,
    }


def verify_snapshot(
    repository: pathlib.Path, contract: Mapping[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, bytes], Dict[str, Dict[str, str]]]:
    upstream = contract["upstream"]
    commit = upstream["commit"]
    observed: Dict[str, Any] = {
        "expected_commit": commit,
        "expected_tree": upstream["tree"],
        "binding_mismatches": [],
    }
    actual_commit = git(repository, ["rev-parse", "--verify", f"{commit}^{{commit}}"])
    actual_tree = git(repository, ["rev-parse", "--verify", f"{commit}^{{tree}}"])
    assert isinstance(actual_commit, str) and isinstance(actual_tree, str)
    observed["actual_commit"] = actual_commit
    observed["actual_tree"] = actual_tree
    if actual_commit != commit:
        observed["binding_mismatches"].append("commit")
    if actual_tree != upstream["tree"]:
        observed["binding_mismatches"].append("tree")
    raw_tree = git(repository, ["ls-tree", "-r", "-z", commit], binary=True)
    assert isinstance(raw_tree, bytes)
    tree = parse_tree(raw_tree)
    values: Dict[str, bytes] = {}
    evidence = []
    for expected in contract["source_bindings"]:
        path_value = expected["path"]
        entry = tree.get(path_value)
        row = {"path": path_value, "pass": False}
        if entry is None:
            observed["binding_mismatches"].append(f"missing:{path_value}")
            row["reason"] = "MISSING"
            evidence.append(row)
            continue
        data = blob(repository, commit, path_value)
        values[path_value] = data
        actual = {
            "mode": entry["mode"],
            "blob": entry["blob"],
            "bytes": len(data),
            "sha256": sha256_bytes(data),
        }
        row.update(actual)
        row["pass"] = all(actual[key] == expected[key] for key in actual)
        if not row["pass"]:
            observed["binding_mismatches"].append(f"identity:{path_value}")
        evidence.append(row)
    observed["files"] = evidence
    observed["exact_commit_tree_and_file_bindings"] = not observed["binding_mismatches"]
    return observed, values, tree


def verify_protocol_commit(
    protocol_commit: str | None, contract_path: pathlib.Path = CONTRACT_PATH
) -> Dict[str, Any]:
    if not protocol_commit:
        return {"verified": False, "reason": "PROTOCOL_COMMIT_NOT_SUPPLIED"}
    repository_text = git(HERE, ["rev-parse", "--show-toplevel"])
    assert isinstance(repository_text, str)
    repository = pathlib.Path(repository_text)
    actual_commit = git(
        repository, ["rev-parse", "--verify", f"{protocol_commit}^{{commit}}"]
    )
    head = git(repository, ["rev-parse", "--verify", "HEAD^{commit}"])
    ancestor = subprocess.run(
        [
            "/usr/bin/git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            protocol_commit,
            str(head),
        ],
        env=git_environment(),
        check=False,
        capture_output=True,
    ).returncode == 0
    paths = [contract_path.resolve(), pathlib.Path(__file__).resolve()]
    files = []
    passed = actual_commit == protocol_commit and ancestor
    for path in paths:
        relative = path.relative_to(repository).as_posix()
        data = blob(repository, protocol_commit, relative)
        current_sha = sha256_path(path)
        committed_sha = sha256_bytes(data)
        file_pass = current_sha == committed_sha
        files.append(
            {
                "path": relative,
                "current_sha256": current_sha,
                "committed_sha256": committed_sha,
                "pass": file_pass,
            }
        )
        passed = passed and file_pass
    tree = git(repository, ["rev-parse", f"{protocol_commit}^{{tree}}"])
    return {
        "verified": passed,
        "protocol_commit": protocol_commit,
        "protocol_tree": tree,
        "protocol_commit_is_ancestor_of_execution_head": ancestor,
        "files": files,
    }


def inspect_candidate_sources(
    repository: pathlib.Path,
    commit: str,
    tree: Mapping[str, Mapping[str, str]],
    manifest: Mapping[str, str],
) -> Dict[str, Any]:
    source_count = parse_nonnegative_integer(manifest.get("source_count"))
    result: Dict[str, Any] = {
        "manifest_schema": manifest.get("schema"),
        "manifest_source_media": manifest.get("source_media"),
        "declared_source_count": source_count,
        "source_bindings_pass": False,
        "candidate_sources_are_in_cargo_or_module_targets": False,
        "candidate_source_content_decoded_or_lexically_inspected": False,
    }
    if source_count is None or source_count <= 0:
        return result
    source_paths = []
    binding_pass = True
    for index in range(1, source_count + 1):
        prefix = f"source_{index:02d}_"
        path_value = manifest.get(prefix + "path")
        expected_sha = manifest.get(prefix + "sha256")
        expected_bytes = parse_nonnegative_integer(manifest.get(prefix + "bytes"))
        if not path_value or path_value not in tree or expected_sha is None or expected_bytes is None:
            binding_pass = False
            continue
        data = blob(repository, commit, path_value)
        if sha256_bytes(data) != expected_sha or len(data) != expected_bytes:
            binding_pass = False
        source_paths.append(path_value)
    result["source_bindings_pass"] = binding_pass and len(source_paths) == source_count
    result["candidate_sources_are_in_cargo_or_module_targets"] = (
        manifest.get("source_media") == "UTF8_RS_SOURCE_IN_CARGO_OR_MODULE_TARGETS"
    )
    return result


def inspect_fermion_mapping(
    mapping: Mapping[str, str] | None, requirements: Mapping[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    if mapping is None:
        evidence = {"manifest_present": False}
        return evidence, {f"fermion_mapping.{key}": False for key in requirements}
    evidence: Dict[str, Any] = {"manifest_present": True, "fields": dict(mapping)}
    checks: Dict[str, bool] = {}
    for key, expected in requirements.items():
        actual = mapping.get(key)
        if isinstance(expected, bool):
            checks[f"fermion_mapping.{key}"] = parse_bool(actual) is expected
        elif isinstance(expected, int):
            parsed = parse_nonnegative_integer(actual)
            checks[f"fermion_mapping.{key}"] = parsed is not None and parsed >= expected
        elif isinstance(expected, list):
            checks[f"fermion_mapping.{key}"] = actual == "|".join(expected)
        else:
            checks[f"fermion_mapping.{key}"] = actual == expected
    return evidence, checks


def json_object_bytes(value: bytes, label: str) -> Dict[str, Any]:
    try:
        result = json.loads(
            value.decode("utf-8", "strict"), parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EligibilityError(f"invalid {label} JSON") from error
    if not isinstance(result, dict):
        raise EligibilityError(f"{label} JSON root must be an object")
    return result


def inspect_mapping_artifacts(
    repository: pathlib.Path,
    commit: str,
    tree: Mapping[str, Mapping[str, str]],
    mapping: Mapping[str, str] | None,
    requirements: Mapping[str, Any],
    memory_cap: int,
) -> Tuple[Dict[str, Any], Dict[str, bool]]:
    roles = requirements["required_roles"]
    checks: Dict[str, bool] = {
        "fermion_mapping_artifacts.artifact_roles_declared": False,
        "fermion_mapping_artifacts.paths_distinct": False,
        "fermion_mapping_artifacts.equivalence_receipt_valid": False,
        "fermion_mapping_artifacts.independent_review_receipt_valid": False,
    }
    for role in roles:
        checks[f"fermion_mapping_artifacts.identity.{role}"] = False
    evidence: Dict[str, Any] = {
        "required_roles": roles,
        "artifacts": [],
        "equivalence_receipt": None,
        "independent_review_receipt": None,
    }
    if mapping is None:
        return evidence, checks
    checks["fermion_mapping_artifacts.artifact_roles_declared"] = (
        mapping.get("artifact_roles") == "|".join(roles)
    )
    paths = []
    artifact_bytes: Dict[str, bytes] = {}
    for role in roles:
        expected = {
            field: mapping.get(f"{role}_{field}")
            for field in requirements["required_identity_fields"]
        }
        path_value = expected["path"]
        entry = tree.get(path_value or "")
        actual: Dict[str, Any] = {}
        if path_value and entry is not None:
            data = blob(repository, commit, path_value)
            artifact_bytes[role] = data
            actual = {
                "path": path_value,
                "mode": entry["mode"],
                "blob": entry["blob"],
                "bytes": str(len(data)),
                "sha256": sha256_bytes(data),
            }
            paths.append(path_value)
        passed = bool(actual) and all(
            str(actual[field]) == expected[field]
            for field in requirements["required_identity_fields"]
        )
        checks[f"fermion_mapping_artifacts.identity.{role}"] = passed
        evidence["artifacts"].append(
            {"role": role, "expected": expected, "actual": actual, "pass": passed}
        )
    checks["fermion_mapping_artifacts.paths_distinct"] = (
        len(paths) == len(roles) and len(set(paths)) == len(paths)
    )

    equivalence = None
    try:
        equivalence = json_object_bytes(
            artifact_bytes["equivalence_receipt"], "equivalence receipt"
        )
    except (KeyError, EligibilityError):
        pass
    if equivalence is not None:
        receipt_fields = requirements["required_equivalence_receipt_fields"]
        count = equivalence.get("independent_test_count")
        error = equivalence.get("maximum_absolute_error")
        memory = equivalence.get("memory_max_bytes")
        equivalence_pass = (
            equivalence.get("schema") == requirements["equivalence_receipt_schema"]
            and equivalence.get("status") == requirements["equivalence_receipt_status"]
            and equivalence.get("upstream_commit") == commit
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count >= requirements["minimum_independent_test_count"]
            and isinstance(error, (int, float))
            and not isinstance(error, bool)
            and math.isfinite(float(error))
            and 0.0 <= float(error) <= requirements["maximum_absolute_error"]
            and isinstance(memory, int)
            and not isinstance(memory, bool)
            and 0 < memory <= min(
                memory_cap, requirements["maximum_execution_memory_bytes"]
            )
            and isinstance(equivalence.get("linked_binary_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", equivalence["linked_binary_sha256"])
            is not None
            and all(equivalence.get(key) is expected for key, expected in receipt_fields.items())
        )
        checks["fermion_mapping_artifacts.equivalence_receipt_valid"] = equivalence_pass
        evidence["equivalence_receipt"] = equivalence

    independent = None
    try:
        independent = json_object_bytes(
            artifact_bytes["independent_review_receipt"],
            "independent review receipt",
        )
    except (KeyError, EligibilityError):
        pass
    if independent is not None:
        review_fields = requirements["required_independent_review_fields"]
        review_pass = (
            independent.get("schema")
            == requirements["independent_review_receipt_schema"]
            and independent.get("status")
            == requirements["independent_review_receipt_status"]
            and independent.get("upstream_commit") == commit
            and all(independent.get(key) is expected for key, expected in review_fields.items())
        )
        checks["fermion_mapping_artifacts.independent_review_receipt_valid"] = review_pass
        evidence["independent_review_receipt"] = independent
    return evidence, checks


def cgroup_limits() -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "cgroup_v2_path": None,
        "memory_max_bytes": None,
        "memory_swap_max_bytes": None,
    }
    try:
        line = next(
            row for row in pathlib.Path("/proc/self/cgroup").read_text().splitlines()
            if row.startswith("0::")
        )
        relative = line.split("::", 1)[1].lstrip("/")
        root = pathlib.Path("/sys/fs/cgroup") / relative
        result["cgroup_v2_path"] = "/" + relative
        for filename, key in (
            ("memory.max", "memory_max_bytes"),
            ("memory.swap.max", "memory_swap_max_bytes"),
        ):
            raw = (root / filename).read_text(encoding="ascii").strip()
            result[key] = None if raw == "max" else int(raw)
    except (OSError, StopIteration, ValueError):
        pass
    return result


def run_integrity_gate(
    repository: pathlib.Path, contract: Mapping[str, Any]
) -> Dict[str, Any]:
    commit = contract["upstream"]["commit"]
    gate_relative = contract["records"]["artifact_integrity_gate"]
    gate = repository / gate_relative
    result: Dict[str, Any] = {
        "executed": False,
        "launch_error": None,
        "returncode": None,
        "stdout_bytes": 0,
        "stdout_sha256": None,
        "stderr_bytes": 0,
        "stderr_sha256": None,
        "fields": {},
        "resource_envelope": cgroup_limits(),
    }
    cap = int(contract["artifact_integrity_execution"]["outer_memory_max_bytes"])
    limits = result["resource_envelope"]
    if (
        limits.get("memory_max_bytes") is None
        or limits["memory_max_bytes"] > cap
        or limits.get("memory_swap_max_bytes") != 0
    ):
        result["launch_error"] = "required cgroup memory/swap envelope is not enforced"
        return result
    head = git(repository, ["rev-parse", "--verify", "HEAD^{commit}"])
    status = git(
        repository,
        ["status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"],
    )
    if head != commit or status:
        result["launch_error"] = "gate requires a clean worktree at the exact pinned HEAD"
        return result
    try:
        gate_stat = gate.lstat()
    except OSError:
        gate_stat = None
    expected_gate = next(
        row for row in contract["source_bindings"] if row["path"] == gate_relative
    )
    if (
        gate_stat is None
        or stat.S_ISLNK(gate_stat.st_mode)
        or not stat.S_ISREG(gate_stat.st_mode)
        or not os.access(gate, os.X_OK)
        or sha256_path(gate) != expected_gate["sha256"]
        or (gate_stat.st_mode & 0o777) != 0o755
    ):
        result["launch_error"] = "bound gate is not a directly executable regular file"
        return result
    timeout = int(contract["artifact_integrity_execution"]["maximum_seconds"])
    try:
        process = subprocess.Popen(
            [str(gate)],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, 9)
        process.communicate()
        result["launch_error"] = "TimeoutExpired"
        return result
    except OSError as error:
        result["launch_error"] = type(error).__name__
        return result
    result["executed"] = True
    result["returncode"] = process.returncode
    result["stdout_bytes"] = len(stdout)
    result["stdout_sha256"] = sha256_bytes(stdout)
    result["stderr_bytes"] = len(stderr)
    result["stderr_sha256"] = sha256_bytes(stderr)
    result["child_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    if len(stdout) <= 65536:
        try:
            result["fields"] = parse_gate_map(stdout, "integrity gate stdout")
        except EligibilityError:
            result["fields"] = {}
    return result


def classify(
    source_trustworthy: bool,
    integrity_observed: bool,
    checks: Mapping[str, bool],
) -> str:
    if not source_trustworthy or not integrity_observed:
        return INDETERMINATE
    if not checks or not all(value is True for value in checks.values()):
        return NO_GO
    return REQUIRES_V2


def evaluate(
    contract: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    runtime: Mapping[str, str],
    source_inspection: Mapping[str, Any],
    mapping: Mapping[str, str] | None,
    mapping_artifact_checks: Mapping[str, bool],
    mapping_artifact_evidence: Mapping[str, Any],
    record_evidence: Mapping[str, Any],
    integrity: Mapping[str, Any],
) -> Tuple[str, Dict[str, bool], Dict[str, Any]]:
    requirements = contract["eligibility_gates"]
    integrity_fields = integrity.get("fields", {})
    checks: Dict[str, bool] = {
        "source_and_provenance.exact_commit_tree_and_file_bindings": bool(
            snapshot.get("exact_commit_tree_and_file_bindings")
        ),
        "source_and_provenance.protocol_commit_verified_before_gate": bool(
            record_evidence.get("protocol_commit_verified_before_gate")
        ),
        "source_and_provenance.all_bound_record_path_hash_pairs": bool(
            record_evidence.get("all_path_hash_pairs_pass")
        ),
        "source_and_provenance.cross_record_authority_consistent": bool(
            record_evidence.get("cross_record", {}).get("pass")
        ),
        "source_and_provenance.candidate_source_manifest_bindings_pass": bool(
            source_inspection.get("source_bindings_pass")
        ),
        "source_and_provenance.outer_memory_limit_enforced": (
            integrity.get("resource_envelope", {}).get("memory_max_bytes")
            is not None
            and integrity["resource_envelope"]["memory_max_bytes"]
            <= requirements["source_and_provenance"].get(
                "outer_memory_max_bytes",
                1073741824,
            )
        ),
        "source_and_provenance.outer_swap_limit_enforced": (
            integrity.get("resource_envelope", {}).get("memory_swap_max_bytes") == 0
        ),
        "source_and_provenance.artifact_integrity_gate_returncode": (
            integrity.get("returncode")
            == requirements["source_and_provenance"]["artifact_integrity_gate_returncode"]
        ),
        "source_and_provenance.artifact_integrity_binding_status": (
            integrity_fields.get("binding_status")
            == requirements["source_and_provenance"]["artifact_integrity_binding_status"]
        ),
        "source_and_provenance.artifact_integrity_contract_gate_entered": (
            parse_bool(integrity_fields.get("contract_gate_entered"))
            is requirements["source_and_provenance"]["artifact_integrity_contract_gate_entered"]
        ),
    }
    for key, expected in requirements["authority"].items():
        checks[f"authority.{key}"] = parse_bool(runtime.get(key)) is expected
    for key, expected in requirements["implementation"].items():
        label = f"implementation.{key}"
        if key == "minimum_registered_arm_executor_impl_head_count":
            actual = parse_nonnegative_integer(
                runtime.get("registered_arm_executor_impl_head_count")
            )
            checks[label] = actual is not None and actual >= expected
        elif key == "candidate_sources_are_in_cargo_or_module_targets":
            checks[label] = source_inspection.get(key) is expected
        elif key.startswith("minimum_"):
            runtime_key = key[len("minimum_") :]
            actual = parse_nonnegative_integer(runtime.get(runtime_key))
            checks[label] = actual is not None and actual >= expected
        else:
            checks[label] = parse_bool(runtime.get(key)) is expected
    mapping_evidence, mapping_checks = inspect_fermion_mapping(
        mapping, requirements["fermion_mapping"]
    )
    checks.update(mapping_checks)
    checks.update(mapping_artifact_checks)
    source_trustworthy = bool(snapshot.get("exact_commit_tree_and_file_bindings"))
    integrity_observed = (
        integrity.get("executed") is True
        and integrity.get("launch_error") is None
    )
    status = classify(source_trustworthy, integrity_observed, checks)
    evidence = {
        "mapping": mapping_evidence,
        "mapping_artifacts": mapping_artifact_evidence,
        "source_trustworthy": source_trustworthy,
        "integrity_observed": integrity_observed,
        "passed_gate_count": sum(checks.values()),
        "required_gate_count": len(checks),
        "failed_gates": sorted(key for key, value in checks.items() if not value),
    }
    return status, checks, evidence


def scientific_result_sha256(receipt: Mapping[str, Any]) -> str:
    core = dict(receipt)
    core.pop("scientific_result_sha256", None)
    core.pop("resources", None)
    return sha256_bytes(
        json.dumps(
            core, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    )


def run(
    repository: pathlib.Path,
    *,
    contract_path: pathlib.Path = CONTRACT_PATH,
    execute_integrity_gate: bool = False,
    protocol_commit: str | None = None,
) -> Dict[str, Any]:
    started = time.monotonic()
    contract = load_contract(contract_path)
    protocol_binding = verify_protocol_commit(protocol_commit, contract_path)
    if execute_integrity_gate and protocol_binding.get("verified") is not True:
        raise EligibilityError(
            "official integrity execution requires the frozen contract and checker in a verified prior protocol commit"
        )
    snapshot, values, tree = verify_snapshot(repository, contract)
    commit = contract["upstream"]["commit"]
    records = contract["records"]
    runtime = parse_tsv_map(
        values[records["runtime_adapter_entry_contract"]], "runtime adapter record"
    )
    record_maps = {
        "runtime": runtime,
        "custody": parse_tsv_map(
            values["fixtures/language_p3a2_hbr_r1_runtime_adapter_entry_contract_custody.v1.tsv"],
            "runtime adapter custody",
        ),
        "root": parse_tsv_prefix_map(
            values["fixtures/language_p3a2_hbr_r1_runtime_adapter_root_contract.v1.tsv"],
            "runtime adapter root",
        ),
        "owner_hold": parse_tsv_map(
            values["fixtures/language_p3a2_owner_admission_hold.v10.tsv"],
            "owner hold",
        ),
        "route_closure": parse_tsv_map(
            values[
                "fixtures/language_p3a2_hbr_r1_explicit_registry_packet_contents_route_closure_summary.v1.tsv"
            ],
            "route closure",
        ),
    }
    record_path_evidence = {
        label: verify_record_path_hashes(
            repository, commit, tree, record, label
        )
        for label, record in record_maps.items()
    }
    record_evidence = {
        "path_hash_records": record_path_evidence,
        "all_path_hash_pairs_pass": all(
            value["pass"] for value in record_path_evidence.values()
        ),
        "cross_record": cross_record_authority_consistency(record_maps),
        "protocol_commit_verified_before_gate": protocol_binding.get("verified") is True,
    }
    manifest = parse_tsv_map(
        values[records["candidate_source_manifest"]], "candidate source manifest"
    )
    source_inspection = inspect_candidate_sources(
        repository, commit, tree, manifest
    )
    mapping_path = records["required_fermion_binding_manifest"]
    mapping = None
    if mapping_path in tree:
        mapping = parse_tsv_map(blob(repository, commit, mapping_path), "fermion mapping")
    mapping_artifact_evidence, mapping_artifact_checks = inspect_mapping_artifacts(
        repository,
        commit,
        tree,
        mapping,
        contract["eligibility_gates"]["fermion_mapping_artifacts"],
        int(contract["artifact_integrity_execution"]["outer_memory_max_bytes"]),
    )
    integrity = (
        run_integrity_gate(repository, contract)
        if execute_integrity_gate
        else {
            "executed": False,
            "launch_error": "integrity gate execution was not requested",
            "returncode": None,
            "fields": {},
        }
    )
    status, checks, decision_evidence = evaluate(
        contract,
        snapshot,
        runtime,
        source_inspection,
        mapping,
        mapping_artifact_checks,
        mapping_artifact_evidence,
        record_evidence,
        integrity,
    )
    receipt: Dict[str, Any] = {
        "schema": "agent_bridge.fermion_biocortex.fb_s2_hbr_r1_adapter_eligibility_receipt.v1",
        "protocol_id": contract["protocol_id"],
        "analysis_class": contract["analysis_class"],
        "confirmation_authority": False,
        "positive_qualification_authority": False,
        "contract_sha256": sha256_path(contract_path),
        "checker_sha256": sha256_path(pathlib.Path(__file__).resolve()),
        "protocol_commit_binding": protocol_binding,
        "upstream": contract["upstream"],
        "source_snapshot": snapshot,
        "artifact_integrity": integrity,
        "runtime_record": {
            key: runtime.get(key)
            for key in sorted(
                set(contract["eligibility_gates"]["authority"])
                | {
                    key
                    for key in contract["eligibility_gates"]["implementation"]
                    if not key.startswith("minimum_")
                }
                | {
                    key[len("minimum_") :]
                    for key in contract["eligibility_gates"]["implementation"]
                    if key.startswith("minimum_")
                }
                | {
                    "informational_only",
                    "validation_receipt_scope",
                    "source_media",
                    "authorized_next_step",
                    "next_required_gate",
                }
            )
        },
        "candidate_source_inspection": source_inspection,
        "record_chain_evidence": record_evidence,
        "gate_results": checks,
        "decision_evidence": decision_evidence,
        "status": status,
        "stop_rules_activated": True,
        "fb_s2b_design_authorized": False,
        "candidate_execution_requested_by_this_checker": False,
        "fresh_holdout_accessed_by_this_checker": False,
        "claims": contract["nonclaims"],
    }
    receipt["scientific_result_sha256"] = scientific_result_sha256(receipt)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    receipt["resources"] = {
        "elapsed_seconds": time.monotonic() - started,
        "process_peak_rss_kib": usage.ru_maxrss,
        "cgroup": cgroup_limits(),
    }
    json.dumps(receipt, allow_nan=False)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--biocortex-repo", required=True, type=pathlib.Path)
    parser.add_argument("--contract", type=pathlib.Path, default=CONTRACT_PATH)
    parser.add_argument("--run-artifact-integrity-gate", action="store_true")
    parser.add_argument("--protocol-commit")
    arguments = parser.parse_args(argv)
    try:
        receipt = run(
            arguments.biocortex_repo,
            contract_path=arguments.contract,
            execute_integrity_gate=arguments.run_artifact_integrity_gate,
            protocol_commit=arguments.protocol_commit,
        )
    except (EligibilityError, OSError, subprocess.SubprocessError) as error:
        print(f"FB-S2 eligibility error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
