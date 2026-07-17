#!/usr/bin/env python3
"""Independent checker for the runtime-prerequisite preregistration pack."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
MODULE_REL = "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1.py"
CHECKER_REL = "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack.py"
FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack_synthetic_v0.json"
EXPECTED_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack.expected.v0.tsv"
MANIFEST_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack_v0.json"
REPORT_REL = "docs/reports/goal-c-u/2026-07-16-biocortex-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-plan-and-owner-decision-preregistration-v1-pack.md"
GATE_REL = "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-plan-and-owner-decision-preregistration-v1-pack.sh"

PREDECESSOR_MODULE_REL = "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_integration_and_runtime_admission_boundary_review_v1.py"
PREDECESSOR_CHECKER_REL = "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_integration_and_runtime_admission_boundary_review_v1_pack.py"
PREDECESSOR_FIXTURE_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_integration_and_runtime_admission_boundary_review_v1_pack_synthetic_v0.json"
PREDECESSOR_EXPECTED_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_integration_and_runtime_admission_boundary_review_v1_pack.expected.v0.tsv"
PREDECESSOR_MANIFEST_REL = "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_integration_and_runtime_admission_boundary_review_v1_pack_v0.json"
PREDECESSOR_REPORT_REL = "docs/reports/goal-c-u/2026-07-16-biocortex-track-b-reference-provider-fault-injection-runner-offline-integration-and-runtime-admission-boundary-review-v1-pack.md"
PREDECESSOR_GATE_REL = "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-offline-integration-and-runtime-admission-boundary-review-v1-pack.sh"

CURRENT_PATHS = (
    MODULE_REL,
    CHECKER_REL,
    FIXTURE_REL,
    EXPECTED_REL,
    MANIFEST_REL,
    REPORT_REL,
    GATE_REL,
)
PREDECESSOR_PATHS = (
    PREDECESSOR_MODULE_REL,
    PREDECESSOR_CHECKER_REL,
    PREDECESSOR_FIXTURE_REL,
    PREDECESSOR_EXPECTED_REL,
    PREDECESSOR_MANIFEST_REL,
    PREDECESSOR_REPORT_REL,
    PREDECESSOR_GATE_REL,
)

EXPECTED_SCHEMA = "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack_manifest.v0"
EXPECTED_STATUS = "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTERED_PENDING_NO_AUTHORITY"
EXPECTED_DECISION = "RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTERED_FAIL_CLOSED"
EXPECTED_NEXT_UNIT = "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES"
BASE_COMMIT = "c9c50917687c7715b031a6bfe8dd7801bfd737ee"
PREDECESSOR_SOURCE_COMMIT = "9a0f50ec378385be9ff0eda62a46666d04e04a97"
PREDECESSOR_MANIFEST_SHA256 = "8a107f72023fb419ebabd771a33172fa09c9eca5d4b1e574df494d8ce3f6fdb1"


class CheckError(ValueError):
    pass


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {message}")


def exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    require(set(value) == expected, code, "closed-world key set drift")


def read_text(relative: str) -> str:
    path = ROOT / relative
    require(path.is_file(), "E_FILE_MISSING", relative)
    return path.read_text(encoding="utf-8")


def read_json(relative: str) -> dict[str, Any]:
    value = json.loads(read_text(relative))
    require(type(value) is dict, "E_JSON_ROOT", relative)
    return value


def file_sha256(relative: str) -> str:
    path = ROOT / relative
    require(path.is_file(), "E_FILE_MISSING", relative)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module() -> ModuleType:
    path = ROOT / MODULE_REL
    require(path.is_file(), "E_PLAN_MODULE_MISSING", MODULE_REL)
    spec = importlib.util.spec_from_file_location("runtime_prerequisite_preregistration_v1", path)
    require(spec is not None and spec.loader is not None, "E_PLAN_MODULE_LOAD", "spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check_source_purity() -> None:
    tree = ast.parse(read_text(MODULE_REL), filename=MODULE_REL)
    allowed_import_roots = {"__future__", "copy", "dataclasses", "hashlib", "json", "typing"}
    forbidden_calls = {
        "__import__",
        "compile",
        "eval",
        "exec",
        "open",
        "system",
        "popen",
        "spawn",
        "fork",
        "getenv",
        "urandom",
        "token_bytes",
        "token_hex",
        "randbytes",
    }
    forbidden_attrs = {
        "read",
        "read_bytes",
        "read_text",
        "write",
        "write_bytes",
        "write_text",
        "unlink",
        "mkdir",
        "makedirs",
        "getenv",
        "environ",
        "now",
        "utcnow",
        "time",
        "sleep",
        "run",
        "Popen",
        "connect",
        "request",
        "urlopen",
        "import_module",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] in allowed_import_roots, "E_AST_IMPORT", alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            require(root in allowed_import_roots, "E_AST_IMPORT", node.module or "")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls, "E_AST_CALL", node.func.id)
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attrs, "E_AST_CALL", node.func.attr)


def expected_boundary() -> dict[str, Any]:
    return {
        "all_nonclaims_explicit": True,
        "condition_output_authorized": False,
        "credentials_accessed": False,
        "deployment_authorized": False,
        "evidence_items_present": 0,
        "evidence_plan_preregistered": True,
        "owner_decision_preregistered": True,
        "owner_decision_recorded": False,
        "output_permit_defined": False,
        "positive_decision_representable": False,
        "prerequisites_satisfied": 0,
        "production_components_bound": 0,
        "provider_called": False,
        "receipt_is_evidence_receipt": False,
        "receipt_is_execution_authority": False,
        "receipt_is_output_permit": False,
        "receipt_is_runtime_admission": False,
        "runtime_admission_granted": False,
        "runtime_admission_ready": False,
        "runtime_authority": False,
        "scientific_claim_authorized": False,
        "side_effects_unlocked": "NONE",
    }


def expected_results(receipt: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "allowed_current_decision_count",
        "content_sha256",
        "distinct_evidence_class_count",
        "distinct_owner_class_count",
        "downstream_separate_gate_count",
        "downstream_separate_gates_sha256",
        "evidence_items_present",
        "evidence_prerequisite_count",
        "fail_closed_transition_count",
        "nonclaim_field_count",
        "nonclaims_sha256",
        "owner_decision_preregistration_sha256",
        "owner_decision_prerequisite_count",
        "owner_decision_recorded",
        "positive_decision_representable",
        "prerequisite_evidence_plan_sha256",
        "prerequisite_plan_count",
        "prerequisites_satisfied",
    )
    return {key: receipt[key] for key in keys}


def validate_manifest(manifest: dict[str, Any], receipt: dict[str, Any]) -> None:
    exact_keys(
        manifest,
        {
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
        },
        "E_MANIFEST_KEYS",
    )
    require(manifest["schema"] == EXPECTED_SCHEMA, "E_MANIFEST_SCHEMA", "schema")
    require(manifest["status"] == EXPECTED_STATUS, "E_MANIFEST_STATUS", "status")
    require(manifest["decision"] == EXPECTED_DECISION, "E_MANIFEST_DECISION", "decision")
    require(manifest["next_unit"] == EXPECTED_NEXT_UNIT, "E_MANIFEST_NEXT", "next unit")
    require(manifest["date"] == "2026-07-16", "E_MANIFEST_DATE", "date")
    require(manifest["logical_baseline_commit"] == BASE_COMMIT, "E_MANIFEST_BASE", "commit")
    require(manifest["boundary"] == expected_boundary(), "E_MANIFEST_BOUNDARY", "boundary")
    require(manifest["results"] == expected_results(receipt), "E_MANIFEST_RESULTS", "results")
    require(
        manifest["tracks"]
        == {
            "MANAGED_SPANNER_CLOUD_KMS": "EVIDENCE_PLAN_PREREGISTERED_RUNTIME_UNBOUND",
            "SELF_HOSTED_ETCD_OPENBAO": "EVIDENCE_PLAN_PREREGISTERED_RUNTIME_UNBOUND",
        },
        "E_MANIFEST_TRACKS",
        "tracks",
    )
    require(
        manifest["predecessor"]
        == {
            "integration_commit": BASE_COMMIT,
            "manifest_path": PREDECESSOR_MANIFEST_REL,
            "manifest_sha256": PREDECESSOR_MANIFEST_SHA256,
            "source_commit": PREDECESSOR_SOURCE_COMMIT,
        },
        "E_MANIFEST_PREDECESSOR",
        "predecessor",
    )
    packet = manifest["packet"]
    require(type(packet) is dict, "E_MANIFEST_PACKET", "not object")
    exact_keys(packet, {"modes", "paths"}, "E_MANIFEST_PACKET_KEYS")
    require(packet["paths"] == list(CURRENT_PATHS), "E_MANIFEST_PATHS", "paths")
    expected_modes = {path: "100644" for path in CURRENT_PATHS}
    expected_modes[GATE_REL] = "100755"
    require(packet["modes"] == expected_modes, "E_MANIFEST_MODES", "modes")
    evidence = manifest["evidence_sha256"]
    require(type(evidence) is dict, "E_MANIFEST_EVIDENCE", "not object")
    expected_evidence_paths = set(CURRENT_PATHS) - {MANIFEST_REL, GATE_REL}
    expected_evidence_paths.update(PREDECESSOR_PATHS)
    require(set(evidence) == expected_evidence_paths, "E_MANIFEST_EVIDENCE_KEYS", "paths")
    for relative, digest in evidence.items():
        require(digest == file_sha256(relative), "E_MANIFEST_EVIDENCE_HASH", relative)
    oracle = manifest["test_oracle"]
    require(type(oracle) is dict, "E_MANIFEST_ORACLE", "not object")
    exact_keys(
        oracle,
        {
            "directed_negative_tests",
            "downstream_separate_gates",
            "fail_closed_transitions",
            "nonclaim_fields",
            "prerequisite_plan_rows",
            "source_ast_purity",
        },
        "E_MANIFEST_ORACLE_KEYS",
    )
    require(type(oracle["directed_negative_tests"]) is int and oracle["directed_negative_tests"] > 0, "E_MANIFEST_ORACLE", "negative count")
    require(oracle["prerequisite_plan_rows"] == 16, "E_MANIFEST_ORACLE", "plan rows")
    require(oracle["fail_closed_transitions"] == 6, "E_MANIFEST_ORACLE", "transitions")
    require(oracle["downstream_separate_gates"] == 4, "E_MANIFEST_ORACLE", "gates")
    require(oracle["nonclaim_fields"] == 31, "E_MANIFEST_ORACLE", "nonclaims")
    require(oracle["source_ast_purity"] == "PASS", "E_MANIFEST_ORACLE", "purity")


def validate_pack() -> tuple[ModuleType, dict[str, Any], dict[str, Any], dict[str, Any]]:
    module = load_module()
    fixture = read_json(FIXTURE_REL)
    predecessor = read_json(PREDECESSOR_MANIFEST_REL)
    receipt = module.RuntimePrerequisiteEvidencePlanReviewer().review(predecessor, fixture)
    require(receipt["schema"] == module.RECEIPT_SCHEMA, "E_RECEIPT_SCHEMA", "schema")
    require(receipt["status"] == EXPECTED_STATUS, "E_RECEIPT_STATUS", "status")
    require(receipt["decision"] == EXPECTED_DECISION, "E_RECEIPT_DECISION", "decision")
    require(receipt["next_unit"] == EXPECTED_NEXT_UNIT, "E_RECEIPT_NEXT", "next unit")
    require(receipt["prerequisite_plan_count"] == 16, "E_RECEIPT_PLAN_COUNT", "count")
    require(receipt["evidence_items_present"] == 0, "E_RECEIPT_EVIDENCE", "present")
    require(receipt["prerequisites_satisfied"] == 0, "E_RECEIPT_SATISFIED", "count")
    require(receipt["owner_decision_recorded"] is False, "E_RECEIPT_OWNER", "recorded")
    require(receipt["positive_decision_representable"] is False, "E_RECEIPT_POSITIVE", "representable")
    require(receipt["runtime_admission_granted"] is False, "E_RECEIPT_RUNTIME", "admission")
    require(receipt["runtime_authority"] is False, "E_RECEIPT_RUNTIME", "authority")
    require(receipt["side_effects_unlocked"] == "NONE", "E_RECEIPT_SIDE_EFFECTS", "side effects")
    rendered = module.render_tsv(receipt)
    require(rendered == read_text(EXPECTED_REL), "E_EXPECTED_TSV", "byte mismatch")
    manifest = read_json(MANIFEST_REL)
    validate_manifest(manifest, receipt)
    check_source_purity()
    return module, fixture, predecessor, manifest


def expect_review_reject(
    module: ModuleType,
    predecessor: dict[str, Any],
    fixture: dict[str, Any],
    label: str,
    mutate_fixture: Callable[[dict[str, Any]], None] | None = None,
    mutate_predecessor: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    candidate_fixture = copy.deepcopy(fixture)
    candidate_predecessor = copy.deepcopy(predecessor)
    if mutate_fixture is not None:
        mutate_fixture(candidate_fixture)
    if mutate_predecessor is not None:
        mutate_predecessor(candidate_predecessor)
    try:
        module.RuntimePrerequisiteEvidencePlanReviewer().review(candidate_predecessor, candidate_fixture)
    except module.PreregistrationReviewError:
        return
    raise CheckError(f"E_NEGATIVE_ACCEPTED: {label}")


def run_self_test(module: ModuleType, fixture: dict[str, Any], predecessor: dict[str, Any], manifest: dict[str, Any]) -> int:
    count = 0

    def reject_fixture(label: str, mutator: Callable[[dict[str, Any]], None]) -> None:
        nonlocal count
        expect_review_reject(module, predecessor, fixture, label, mutate_fixture=mutator)
        count += 1

    def reject_predecessor(label: str, mutator: Callable[[dict[str, Any]], None]) -> None:
        nonlocal count
        expect_review_reject(module, predecessor, fixture, label, mutate_predecessor=mutator)
        count += 1

    reject_fixture("fixture-extra", lambda value: value.__setitem__("extra", False))
    for key in tuple(fixture):
        reject_fixture(f"fixture-drop-{key}", lambda value, key=key: value.pop(key))
    reject_fixture("fixture-schema", lambda value: value.__setitem__("schema", "drift"))
    reject_fixture("fixture-date", lambda value: value.__setitem__("date", "2026-07-17"))
    reject_fixture("fixture-synthetic", lambda value: value.__setitem__("synthetic_only", False))
    reject_fixture("fixture-track", lambda value: value["tracks"].__setitem__(0, "DRIFT"))

    for index in range(16):
        row_mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            ("id", lambda row: row.__setitem__("prerequisite_id", "DRIFT")),
            ("owner", lambda row: row.__setitem__("owner_class", "DRIFT")),
            ("required", lambda row: row.__setitem__("evidence_required", "DRIFT")),
            ("class", lambda row: row.__setitem__("evidence_class", "DRIFT")),
            ("collection", lambda row: row.__setitem__("collection_method", "NOW")),
            ("freshness", lambda row: row.__setitem__("freshness_rule", "")),
            ("validation", lambda row: row.__setitem__("validation_rule", "ALLOW")),
            ("status", lambda row: row.__setitem__("plan_status", "COLLECTED")),
            ("present", lambda row: row.__setitem__("evidence_present", True)),
            ("satisfied", lambda row: row.__setitem__("satisfied", True)),
            ("rejection-drop", lambda row: row["rejection_reasons"].pop()),
            ("rejection-duplicate", lambda row: row["rejection_reasons"].__setitem__(1, row["rejection_reasons"][0])),
            ("dependency", lambda row: row["depends_on"].append("UNKNOWN_PREREQUISITE")),
            ("extra", lambda row: row.__setitem__("extra", False)),
        )
        for suffix, mutate_row in row_mutations:
            reject_fixture(
                f"plan-{index}-{suffix}",
                lambda value, index=index, mutate_row=mutate_row: mutate_row(value["prerequisite_evidence_plan"][index]),
            )

    nonclaims = fixture["nonclaims"]
    for key, original in nonclaims.items():
        replacement: Any = "SOME" if key == "side_effects_unlocked" else True
        reject_fixture(
            f"nonclaim-escalate-{key}",
            lambda value, key=key, replacement=replacement: value["nonclaims"].__setitem__(key, replacement),
        )
        reject_fixture(
            f"nonclaim-drop-{key}",
            lambda value, key=key: value["nonclaims"].pop(key),
        )

    owner = fixture["owner_decision_preregistration"]
    for key in tuple(owner):
        reject_fixture(
            f"owner-drop-{key}",
            lambda value, key=key: value["owner_decision_preregistration"].pop(key),
        )
    owner_mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
        ("positive", lambda value: value.__setitem__("positive_decision_representable", True)),
        ("recorded", lambda value: value.__setitem__("current_decision_recorded", True)),
        ("state", lambda value: value.__setitem__("current_state", "ADMITTED")),
        ("hash", lambda value: value.__setitem__("current_evidence_set_hash", "a" * 64)),
        ("identity", lambda value: value.__setitem__("owner_identity_bound", True)),
        ("delegate", lambda value: value.__setitem__("delegated_agent_authority", True)),
        ("decisions", lambda value: value["allowed_current_decisions"].append("ADMITTED")),
        ("quorum", lambda value: value.__setitem__("quorum_rule", "AGENT_MAY_SUBSTITUTE")),
        ("count-before", lambda value: value.__setitem__("required_validated_evidence_count_before_decision", 14)),
        ("count-after", lambda value: value.__setitem__("required_total_prerequisite_count_after_decision", 15)),
        ("transition", lambda value: value["fail_closed_transitions"][5].__setitem__("result", "PENDING_PREREQUISITE_EVIDENCE")),
        ("extra", lambda value: value.__setitem__("extra", False)),
    )
    for suffix, mutator in owner_mutations:
        reject_fixture(
            f"owner-{suffix}",
            lambda value, mutator=mutator: mutator(value["owner_decision_preregistration"]),
        )

    for index in range(4):
        reject_fixture(
            f"gate-authorize-{index}",
            lambda value, index=index: value["downstream_separate_gates"][index].__setitem__("authorized", True),
        )
        reject_fixture(
            f"gate-id-{index}",
            lambda value, index=index: value["downstream_separate_gates"][index].__setitem__("gate_id", "DRIFT"),
        )
    for key, original in fixture["expected"].items():
        replacement = not original if type(original) is bool else original + 1
        reject_fixture(
            f"expected-{key}",
            lambda value, key=key, replacement=replacement: value["expected"].__setitem__(key, replacement),
        )
    for key in tuple(fixture["predecessor"]):
        reject_fixture(
            f"binding-{key}",
            lambda value, key=key: value["predecessor"].__setitem__(key, "DRIFT"),
        )
    for key in tuple(predecessor):
        reject_predecessor(
            f"predecessor-{key}",
            lambda value, key=key: value.__setitem__(key, "DRIFT"),
        )

    receipt = module.RuntimePrerequisiteEvidencePlanReviewer().review(predecessor, fixture)
    manifest_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("extra", lambda value: value.__setitem__("extra", False)),
        ("schema", lambda value: value.__setitem__("schema", "drift")),
        ("status", lambda value: value.__setitem__("status", "drift")),
        ("decision", lambda value: value.__setitem__("decision", "drift")),
        ("next", lambda value: value.__setitem__("next_unit", "drift")),
        ("base", lambda value: value.__setitem__("logical_baseline_commit", "0" * 40)),
        ("path", lambda value: value["packet"]["paths"].pop()),
        ("mode", lambda value: value["packet"]["modes"].__setitem__(GATE_REL, "100644")),
        ("evidence", lambda value: value["evidence_sha256"].__setitem__(MODULE_REL, "0" * 64)),
        ("predecessor", lambda value: value["predecessor"].__setitem__("integration_commit", "0" * 40)),
        ("track", lambda value: value["tracks"].__setitem__("MANAGED_SPANNER_CLOUD_KMS", "ADMITTED")),
        ("oracle", lambda value: value["test_oracle"].__setitem__("nonclaim_fields", 30)),
    ]
    for key in expected_boundary():
        manifest_mutations.append(
            (
                f"boundary-{key}",
                lambda value, key=key: value["boundary"].__setitem__(
                    key,
                    "DRIFT" if type(value["boundary"][key]) is str else not value["boundary"][key] if type(value["boundary"][key]) is bool else value["boundary"][key] + 1,
                ),
            )
        )
    for key in expected_results(receipt):
        manifest_mutations.append(
            (
                f"result-{key}",
                lambda value, key=key: value["results"].__setitem__(
                    key,
                    "DRIFT" if type(value["results"][key]) is str else not value["results"][key] if type(value["results"][key]) is bool else value["results"][key] + 1,
                ),
            )
        )
    for label, mutator in manifest_mutations:
        candidate = copy.deepcopy(manifest)
        mutator(candidate)
        try:
            validate_manifest(candidate, receipt)
        except CheckError:
            count += 1
            continue
        raise CheckError(f"E_MANIFEST_NEGATIVE_ACCEPTED: {label}")

    require(count == manifest["test_oracle"]["directed_negative_tests"], "E_NEGATIVE_COUNT", f"observed={count}")
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    try:
        module, fixture, predecessor, manifest = validate_pack()
        print("VALID_RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTRATION_V1_PACK")
        if args.self_test:
            count = run_self_test(module, fixture, predecessor, manifest)
            print(f"directed_negative_tests\t{count}")
            print("source_ast_purity\tPASS")
    except (CheckError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
