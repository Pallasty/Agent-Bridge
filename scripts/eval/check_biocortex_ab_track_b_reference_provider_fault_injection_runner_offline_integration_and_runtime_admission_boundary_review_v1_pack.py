#!/usr/bin/env python3
"""Independently validate the offline integration boundary-review pack."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Callable, Mapping


MODULE_PATH = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_integration_and_runtime_admission_boundary_review_v1.py"
)
CHECKER_PATH = (
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_offline_integration_and_runtime_admission_boundary_review_v1_pack.py"
)
FIXTURE_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_offline_integration_and_runtime_admission_boundary_review_v1_pack_"
    "synthetic_v0.json"
)
EXPECTED_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_offline_integration_and_runtime_admission_boundary_review_v1_pack."
    "expected.v0.tsv"
)
MANIFEST_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_offline_integration_and_runtime_admission_boundary_review_v1_pack_v0.json"
)
REPORT_PATH = (
    "docs/reports/goal-c-u/2026-07-16-biocortex-track-b-reference-provider-fault-"
    "injection-runner-offline-integration-and-runtime-admission-boundary-review-v1-"
    "pack.md"
)
GATE_PATH = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-"
    "offline-integration-and-runtime-admission-boundary-review-v1-pack.sh"
)
PREDECESSOR_MANIFEST_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_offline_authority_and_adapter_doubles_v1_pack_v0.json"
)
PREDECESSOR_EXPECTED_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_offline_authority_and_adapter_doubles_v1_pack.expected.v0.tsv"
)

PACK_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "offline_integration_and_runtime_admission_boundary_review_v1_pack_manifest.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_OFFLINE_INTEGRATION_REVIEWED_"
    "RUNTIME_ADMISSION_BLOCKED_NO_AUTHORITY"
)
DECISION = (
    "OFFLINE_INTEGRATION_COMPLETE_FOR_SYNTHETIC_CONFORMANCE_"
    "RUNTIME_ADMISSION_BLOCKED_FAIL_CLOSED"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTRATION"
)
BASELINE_COMMIT = "a1c9469e9a14cd73159d34974f0e99714ce5a1f0"
SOURCE_PREDECESSOR_COMMIT = "425ce42fa4f2bc1bbf2ce072c7a8b3407cd8bbb1"
MAX_JSON_BYTES = 8 * 1024 * 1024
EXPECTED_DIRECTED_NEGATIVES = 186

PACK_PATHS = (
    MODULE_PATH,
    CHECKER_PATH,
    FIXTURE_PATH,
    EXPECTED_PATH,
    MANIFEST_PATH,
    REPORT_PATH,
    GATE_PATH,
)
PACK_MODES = {
    MODULE_PATH: "100644",
    CHECKER_PATH: "100644",
    FIXTURE_PATH: "100644",
    EXPECTED_PATH: "100644",
    MANIFEST_PATH: "100644",
    REPORT_PATH: "100644",
    GATE_PATH: "100755",
}
NEW_EVIDENCE_PATHS = (MODULE_PATH, CHECKER_PATH, FIXTURE_PATH, EXPECTED_PATH, REPORT_PATH)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PackError(ValueError):
    pass


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise PackError(f"{code}: {message}")


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PackError(f"E_DUPLICATE_JSON_KEY: {key}")
        result[key] = value
    return result


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def safe_repo_path(path: str) -> PurePosixPath:
    require(type(path) is str and path != "", "E_PATH", "path must be text")
    parsed = PurePosixPath(path)
    require(not parsed.is_absolute(), "E_PATH", f"absolute path: {path}")
    require(".." not in parsed.parts and "." not in parsed.parts, "E_PATH", path)
    require(str(parsed) == path, "E_PATH", f"noncanonical path: {path}")
    return parsed


def read_bytes(root: Path, repo_path: str, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    safe_repo_path(repo_path)
    path = root / repo_path
    require(path.is_file() and not path.is_symlink(), "E_FILE", repo_path)
    size = path.stat().st_size
    require(size <= max_bytes, "E_FILE_SIZE", repo_path)
    data = path.read_bytes()
    require(len(data) == size, "E_FILE_RACE", repo_path)
    return data


def read_json(root: Path, repo_path: str) -> dict[str, Any]:
    raw = read_bytes(root, repo_path)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackError(f"E_JSON: {repo_path}: {error}") from error
    require(type(value) is dict, "E_JSON_ROOT", repo_path)
    require(canonical_bytes(value) == raw, "E_CANONICAL_JSON", repo_path)
    return value


def read_tsv(root: Path, repo_path: str) -> tuple[dict[str, Any], bytes]:
    raw = read_bytes(root, repo_path, 1024 * 1024)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PackError(f"E_TSV_UTF8: {repo_path}") from error
    require(text.endswith("\n"), "E_TSV_FINAL_NEWLINE", repo_path)
    result: dict[str, Any] = {}
    for line in text.splitlines():
        require(line.count("\t") == 1, "E_TSV_ROW", line)
        key, rendered = line.split("\t", 1)
        require(key not in result, "E_TSV_DUPLICATE", key)
        if rendered == "true":
            value: Any = True
        elif rendered == "false":
            value = False
        elif rendered.isdigit():
            value = int(rendered)
        else:
            value = rendered
        result[key] = value
    return result, raw


def load_review_module(root: Path) -> ModuleType:
    path = root / MODULE_PATH
    require(path.is_file() and not path.is_symlink(), "E_REVIEW_MODULE", MODULE_PATH)
    spec = importlib.util.spec_from_file_location("offline_boundary_review_v1", path)
    require(spec is not None and spec.loader is not None, "E_REVIEW_MODULE", "spec")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_source_purity(root: Path) -> None:
    source = read_bytes(root, MODULE_PATH).decode("utf-8")
    tree = ast.parse(source, filename=MODULE_PATH)
    allowed_imports = {"__future__", "copy", "dataclasses", "hashlib", "json", "typing"}
    denied_calls = {"__import__", "compile", "eval", "exec", "input", "open"}
    denied_attributes = {
        "connect",
        "getenv",
        "now",
        "open",
        "read_bytes",
        "read_text",
        "sleep",
        "system",
        "time",
        "token_bytes",
        "urandom",
        "utcnow",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".", 1)[0] in allowed_imports, "E_AST_IMPORT", alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            require(module.split(".", 1)[0] in allowed_imports, "E_AST_IMPORT", module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in denied_calls, "E_AST_CALL", node.func.id)
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in denied_attributes, "E_AST_CALL", node.func.attr)


def verify_predecessor_hashes(root: Path, fixture: Mapping[str, Any]) -> None:
    predecessor = fixture["predecessor"]
    pairs = (
        ("manifest_path", "manifest_sha256"),
        ("expected_path", "expected_sha256"),
        ("module_path", "module_sha256"),
        ("checker_path", "checker_sha256"),
        ("report_path", "report_sha256"),
        ("gate_path", "gate_sha256"),
    )
    expected_paths = {
        PREDECESSOR_MANIFEST_PATH,
        PREDECESSOR_EXPECTED_PATH,
        "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1.py",
        "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack.py",
        "docs/reports/goal-c-u/2026-07-16-biocortex-track-b-reference-provider-fault-injection-runner-offline-authority-and-adapter-doubles-v1-pack.md",
        "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-offline-authority-and-adapter-doubles-v1-pack.sh",
    }
    actual_paths = {predecessor[path_field] for path_field, _ in pairs}
    require(actual_paths == expected_paths, "E_PREDECESSOR_PATHS", "path catalog")
    for path_field, hash_field in pairs:
        path = predecessor[path_field]
        expected = predecessor[hash_field]
        require(type(expected) is str and SHA256_RE.fullmatch(expected), "E_HASH", hash_field)
        require(sha256_bytes(read_bytes(root, path)) == expected, "E_HASH_DRIFT", path)
    require(predecessor["integration_commit"] == BASELINE_COMMIT, "E_BASELINE", "integration")
    require(
        predecessor["source_commit"] == SOURCE_PREDECESSOR_COMMIT,
        "E_BASELINE",
        "source",
    )


def validate_receipt(receipt: Mapping[str, Any], fixture: Mapping[str, Any]) -> None:
    required_keys = {
        "adapter_doubles_reviewed",
        "all_nonclaims_explicit",
        "condition_outputs",
        "content_sha256",
        "credentials_accessed",
        "date",
        "decision",
        "downstream_separate_gate_count",
        "downstream_separate_gates",
        "downstream_separate_gates_sha256",
        "experiment_rows",
        "integration_component_count",
        "integration_matrix",
        "integration_matrix_sha256",
        "next_unit",
        "nonclaim_field_count",
        "nonclaims",
        "nonclaims_sha256",
        "offline_integration_reviewed",
        "offline_synthetic_conformance_complete",
        "output_permits",
        "paid_resources_provisioned",
        "predecessor_manifest_sha256",
        "predecessor_receipt_sha256",
        "production_components_bound",
        "provider_calls",
        "receipt_is_execution_authority",
        "receipt_is_output_permit",
        "receipt_is_runtime_admission",
        "runtime_admission_granted",
        "runtime_admission_ready",
        "runtime_authority",
        "runtime_prerequisite_count",
        "runtime_prerequisites",
        "runtime_prerequisites_missing",
        "runtime_prerequisites_satisfied",
        "runtime_prerequisites_sha256",
        "runtime_rows",
        "schema",
        "side_effects_unlocked",
        "status",
        "stop_control_doubles_reviewed",
        "synthetic_components_complete",
        "tracks_reviewed",
        "wire_attempts",
    }
    require(set(receipt) == required_keys, "E_RECEIPT_KEYS", "closed-world receipt")
    expected = fixture["expected"]
    scalar_expected = {
        "adapter_doubles_reviewed": expected["adapter_doubles_reviewed"],
        "all_nonclaims_explicit": True,
        "condition_outputs": 0,
        "credentials_accessed": 0,
        "date": "2026-07-16",
        "decision": DECISION,
        "downstream_separate_gate_count": expected["downstream_separate_gate_count"],
        "experiment_rows": 0,
        "integration_component_count": expected["integration_component_count"],
        "next_unit": NEXT_UNIT,
        "nonclaim_field_count": expected["nonclaim_field_count"],
        "offline_integration_reviewed": True,
        "offline_synthetic_conformance_complete": True,
        "output_permits": 0,
        "paid_resources_provisioned": 0,
        "production_components_bound": 0,
        "provider_calls": 0,
        "receipt_is_execution_authority": False,
        "receipt_is_output_permit": False,
        "receipt_is_runtime_admission": False,
        "runtime_admission_granted": False,
        "runtime_admission_ready": False,
        "runtime_authority": False,
        "runtime_prerequisite_count": expected["runtime_prerequisite_count"],
        "runtime_prerequisites_missing": expected["runtime_prerequisite_count"],
        "runtime_prerequisites_satisfied": 0,
        "runtime_rows": 0,
        "schema": (
            "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
            "offline_integration_and_runtime_admission_boundary_review_v1.receipt.v0"
        ),
        "side_effects_unlocked": "NONE",
        "status": STATUS,
        "stop_control_doubles_reviewed": expected["stop_control_doubles_reviewed"],
        "synthetic_components_complete": expected["synthetic_components_complete"],
        "tracks_reviewed": expected["track_count"],
        "wire_attempts": 0,
    }
    for key, value in scalar_expected.items():
        require(receipt[key] == value, "E_RECEIPT_VALUE", key)
    matrix = receipt["integration_matrix"]
    prerequisites = receipt["runtime_prerequisites"]
    downstream = receipt["downstream_separate_gates"]
    nonclaims = receipt["nonclaims"]
    require(type(matrix) is list and len(matrix) == 15, "E_MATRIX", "count")
    require(type(prerequisites) is list and len(prerequisites) == 16, "E_PREREQ", "count")
    require(type(downstream) is list and len(downstream) == 4, "E_DOWNSTREAM", "count")
    require(nonclaims == fixture["nonclaims"], "E_NONCLAIMS", "receipt")
    require(all(row["synthetic_implemented"] is True for row in matrix), "E_MATRIX", "synthetic")
    require(all(row["production_bound"] is False for row in matrix), "E_MATRIX", "production")
    require(
        all(row["runtime_authority_contribution"] is False for row in matrix),
        "E_MATRIX",
        "runtime authority",
    )
    require(all(row["satisfied"] is False for row in prerequisites), "E_PREREQ", "satisfied")
    require(all(row["authorized"] is False for row in downstream), "E_DOWNSTREAM", "authorized")
    require(receipt["integration_matrix_sha256"] == sha256_value(matrix), "E_HASH", "matrix")
    require(
        receipt["runtime_prerequisites_sha256"] == sha256_value(prerequisites),
        "E_HASH",
        "prerequisites",
    )
    require(
        receipt["downstream_separate_gates_sha256"] == sha256_value(downstream),
        "E_HASH",
        "downstream",
    )
    require(receipt["nonclaims_sha256"] == sha256_value(nonclaims), "E_HASH", "nonclaims")
    content = copy.deepcopy(dict(receipt))
    claimed_content = content.pop("content_sha256")
    require(claimed_content == sha256_value(content), "E_HASH", "content")


def validate_manifest(
    root: Path,
    manifest: Mapping[str, Any],
    fixture: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    required_keys = {
        "boundary",
        "date",
        "decision",
        "evidence_sha256",
        "logical_baseline_commit",
        "next_unit",
        "packet",
        "predecessor",
        "results",
        "schema",
        "status",
        "test_oracle",
        "tracks",
    }
    require(set(manifest) == required_keys, "E_MANIFEST_KEYS", "closed-world manifest")
    require(manifest["schema"] == PACK_SCHEMA, "E_MANIFEST", "schema")
    require(manifest["status"] == STATUS, "E_MANIFEST", "status")
    require(manifest["decision"] == DECISION, "E_MANIFEST", "decision")
    require(manifest["date"] == "2026-07-16", "E_MANIFEST", "date")
    require(manifest["logical_baseline_commit"] == BASELINE_COMMIT, "E_MANIFEST", "baseline")
    require(manifest["next_unit"] == NEXT_UNIT, "E_MANIFEST", "next unit")
    packet = manifest["packet"]
    require(packet == {"modes": PACK_MODES, "paths": list(PACK_PATHS)}, "E_PACKET", "catalog")
    predecessor = manifest["predecessor"]
    fixture_predecessor = fixture["predecessor"]
    require(
        predecessor
        == {
            "integration_commit": BASELINE_COMMIT,
            "manifest_path": PREDECESSOR_MANIFEST_PATH,
            "manifest_sha256": fixture_predecessor["manifest_sha256"],
            "source_commit": SOURCE_PREDECESSOR_COMMIT,
        },
        "E_MANIFEST_PREDECESSOR",
        "predecessor",
    )
    boundary = manifest["boundary"]
    require(
        boundary
        == {
            "all_nonclaims_explicit": True,
            "condition_output_authorized": False,
            "deployment_authorized": False,
            "offline_integration_reviewed": True,
            "offline_synthetic_conformance_complete": True,
            "output_permit_defined": False,
            "production_components_bound": 0,
            "provider_called": False,
            "receipt_is_execution_authority": False,
            "receipt_is_output_permit": False,
            "receipt_is_runtime_admission": False,
            "runtime_admission_granted": False,
            "runtime_admission_ready": False,
            "runtime_authority": False,
            "scientific_claim_authorized": False,
            "side_effects_unlocked": "NONE",
        },
        "E_MANIFEST_BOUNDARY",
        "boundary",
    )
    results = manifest["results"]
    expected_results = {
        "adapter_doubles_reviewed": 9,
        "content_sha256": receipt["content_sha256"],
        "downstream_separate_gate_count": 4,
        "downstream_separate_gates_sha256": receipt["downstream_separate_gates_sha256"],
        "integration_component_count": 15,
        "integration_matrix_sha256": receipt["integration_matrix_sha256"],
        "nonclaim_field_count": 23,
        "nonclaims_sha256": receipt["nonclaims_sha256"],
        "production_components_bound": 0,
        "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0,
        "runtime_prerequisites_sha256": receipt["runtime_prerequisites_sha256"],
        "stop_control_doubles_reviewed": 5,
        "synthetic_components_complete": 15,
    }
    require(results == expected_results, "E_MANIFEST_RESULTS", "results")
    require(
        manifest["test_oracle"]
        == {
            "directed_negative_tests": EXPECTED_DIRECTED_NEGATIVES,
            "downstream_separate_gates": 4,
            "integration_components": 15,
            "nonclaim_fields": 23,
            "runtime_prerequisites": 16,
            "source_ast_purity": "PASS",
        },
        "E_MANIFEST_ORACLE",
        "test oracle",
    )
    require(
        manifest["tracks"]
        == {
            "MANAGED_SPANNER_CLOUD_KMS": "OFFLINE_INTEGRATION_REVIEWED_RUNTIME_UNBOUND",
            "SELF_HOSTED_ETCD_OPENBAO": "OFFLINE_INTEGRATION_REVIEWED_RUNTIME_UNBOUND",
        },
        "E_MANIFEST_TRACKS",
        "tracks",
    )
    evidence = manifest["evidence_sha256"]
    require(type(evidence) is dict, "E_EVIDENCE", "not object")
    expected_evidence_paths = set(NEW_EVIDENCE_PATHS) | {
        fixture_predecessor["manifest_path"],
        fixture_predecessor["expected_path"],
        fixture_predecessor["module_path"],
        fixture_predecessor["checker_path"],
        fixture_predecessor["report_path"],
        fixture_predecessor["gate_path"],
    }
    require(set(evidence) == expected_evidence_paths, "E_EVIDENCE", "path catalog")
    for path, expected_hash in evidence.items():
        require(type(expected_hash) is str and SHA256_RE.fullmatch(expected_hash), "E_HASH", path)
        require(sha256_bytes(read_bytes(root, path)) == expected_hash, "E_HASH_DRIFT", path)


def mutate_scalar(value: Any) -> Any:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return value + "__MUTATED"
    raise AssertionError(f"unsupported mutation type: {type(value).__name__}")


def expect_rejected(module: ModuleType, action: Callable[[], Any], label: str) -> None:
    try:
        action()
    except module.BoundaryReviewError:
        return
    raise PackError(f"E_NEGATIVE_ACCEPTED: {label}")


def run_directed_negative_tests(
    module: ModuleType,
    predecessor_manifest: Mapping[str, Any],
    predecessor_receipt: Mapping[str, Any],
    fixture: Mapping[str, Any],
) -> int:
    reviewer = module.OfflineIntegrationRuntimeAdmissionBoundaryReviewer()
    count = 0

    root_mutations = {
        "schema": "wrong.schema",
        "date": "2026-07-17",
        "synthetic_only": False,
    }
    for field, value in root_mutations.items():
        mutated = copy.deepcopy(fixture)
        mutated[field] = value
        expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"fixture {field}")
        count += 1
    mutated = copy.deepcopy(fixture)
    mutated["extra"] = False
    expect_rejected(module, lambda: reviewer.review(predecessor_manifest, predecessor_receipt, mutated), "fixture extra")
    count += 1

    for field in fixture["nonclaims"]:
        mutated = copy.deepcopy(fixture)
        mutated["nonclaims"][field] = mutate_scalar(mutated["nonclaims"][field])
        expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"nonclaim {field}")
        count += 1
        mutated = copy.deepcopy(fixture)
        del mutated["nonclaims"][field]
        expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"missing nonclaim {field}")
        count += 1

    for index in range(len(fixture["review_scope"]["adapter_ids"])):
        mutated = copy.deepcopy(fixture)
        mutated["review_scope"]["adapter_ids"][index] += "__MUTATED"
        expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"adapter {index}")
        count += 1
    for index in range(len(fixture["review_scope"]["stop_control_ids"])):
        mutated = copy.deepcopy(fixture)
        mutated["review_scope"]["stop_control_ids"][index] += "__MUTATED"
        expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"stop {index}")
        count += 1
    for index in range(len(fixture["review_scope"]["tracks"])):
        mutated = copy.deepcopy(fixture)
        mutated["review_scope"]["tracks"][index] += "__MUTATED"
        expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"track {index}")
        count += 1

    for index in range(len(fixture["runtime_prerequisites"])):
        for field in ("satisfied", "prerequisite_id", "status"):
            mutated = copy.deepcopy(fixture)
            row = mutated["runtime_prerequisites"][index]
            row[field] = mutate_scalar(row[field])
            expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"prerequisite {index} {field}")
            count += 1

    for index in range(len(fixture["downstream_separate_gates"])):
        for field in ("authorized", "gate_id", "status"):
            mutated = copy.deepcopy(fixture)
            row = mutated["downstream_separate_gates"][index]
            row[field] = mutate_scalar(row[field])
            expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"downstream {index} {field}")
            count += 1

    for field in fixture["expected"]:
        mutated = copy.deepcopy(fixture)
        mutated["expected"][field] = mutate_scalar(mutated["expected"][field])
        expect_rejected(module, lambda m=mutated: reviewer.review(predecessor_manifest, predecessor_receipt, m), f"expected {field}")
        count += 1

    receipt_fields = (
        "authority_bundles_verified",
        "scope_signature_receipts_verified",
        "control_evidence_receipts_verified",
        "private_capability_commitments_verified",
        "control_ledger_start_cas",
        "adapter_calls",
        "adapter_forbidden_rejections",
        "adapter_cross_scope_rejections",
        "adapter_duplicate_rejections",
        "stop_sequences_absorbing_complete",
        "stop_sequences_failed_quarantined",
        "provider_calls",
        "runtime_authority",
        "content_sha256",
    )
    for field in receipt_fields:
        mutated_receipt = copy.deepcopy(predecessor_receipt)
        mutated_receipt[field] = mutate_scalar(mutated_receipt[field])
        expect_rejected(module, lambda r=mutated_receipt: reviewer.review(predecessor_manifest, r, fixture), f"predecessor receipt {field}")
        count += 1

    for field in predecessor_manifest["boundary"]:
        mutated_manifest = copy.deepcopy(predecessor_manifest)
        mutated_manifest["boundary"][field] = mutate_scalar(mutated_manifest["boundary"][field])
        expect_rejected(module, lambda m=mutated_manifest: reviewer.review(m, predecessor_receipt, fixture), f"predecessor boundary {field}")
        count += 1

    result_fields = (
        "adapter_calls",
        "authority_bundles_verified",
        "control_evidence_receipts_verified",
        "experiment_rows",
        "private_capability_commitments_verified",
        "provider_calls",
        "runtime_rows",
        "scope_signature_receipts_verified",
        "stop_sequences_absorbing_complete",
        "stop_sequences_failed_quarantined",
        "wire_attempts",
        "conformance_content_sha256",
    )
    for field in result_fields:
        mutated_manifest = copy.deepcopy(predecessor_manifest)
        mutated_manifest["results"][field] = mutate_scalar(mutated_manifest["results"][field])
        expect_rejected(module, lambda m=mutated_manifest: reviewer.review(m, predecessor_receipt, fixture), f"predecessor result {field}")
        count += 1

    for field in ("schema", "status", "decision", "next_unit"):
        mutated_manifest = copy.deepcopy(predecessor_manifest)
        mutated_manifest[field] = mutate_scalar(mutated_manifest[field])
        expect_rejected(module, lambda m=mutated_manifest: reviewer.review(m, predecessor_receipt, fixture), f"predecessor {field}")
        count += 1
    for track in predecessor_manifest["tracks"]:
        mutated_manifest = copy.deepcopy(predecessor_manifest)
        mutated_manifest["tracks"][track] += "__MUTATED"
        expect_rejected(module, lambda m=mutated_manifest: reviewer.review(m, predecessor_receipt, fixture), f"predecessor track {track}")
        count += 1

    require(count == EXPECTED_DIRECTED_NEGATIVES, "E_NEGATIVE_COUNT", str(count))
    return count


def evaluate(root: Path, self_test: bool) -> str:
    module = load_review_module(root)
    require(module.STATUS == STATUS, "E_MODULE_CONSTANT", "status")
    require(module.DECISION == DECISION, "E_MODULE_CONSTANT", "decision")
    require(module.NEXT_UNIT == NEXT_UNIT, "E_MODULE_CONSTANT", "next unit")
    fixture = read_json(root, FIXTURE_PATH)
    predecessor_manifest = read_json(root, PREDECESSOR_MANIFEST_PATH)
    predecessor_receipt, _ = read_tsv(root, PREDECESSOR_EXPECTED_PATH)
    expected_receipt, expected_raw = read_tsv(root, EXPECTED_PATH)
    manifest = read_json(root, MANIFEST_PATH)
    verify_source_purity(root)
    verify_predecessor_hashes(root, fixture)
    reviewer = module.OfflineIntegrationRuntimeAdmissionBoundaryReviewer()
    receipt = reviewer.review(predecessor_manifest, predecessor_receipt, fixture)
    validate_receipt(receipt, fixture)
    rendered = module.render_tsv(receipt).encode("utf-8")
    require(rendered == expected_raw, "E_EXPECTED_RECEIPT", "byte drift")
    require(expected_receipt == {key: receipt[key] for key in module.TSV_FIELDS}, "E_EXPECTED_RECEIPT", "field drift")
    validate_manifest(root, manifest, fixture, receipt)
    negative_count = run_directed_negative_tests(module, predecessor_manifest, predecessor_receipt, fixture)
    if self_test:
        return (
            "self_test\tPASS\n"
            f"directed_negative_tests\t{negative_count}\n"
            "source_ast_purity\tPASS\n"
        )
    return (
        rendered.decode("utf-8")
        + f"directed_negative_tests\t{negative_count}\n"
        + "source_ast_purity\tPASS\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        print(evaluate(args.root.resolve(), args.self_test), end="")
    except (OSError, PackError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
