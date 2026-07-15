#!/usr/bin/env python3
"""Validate the Track B reference-provider fault-injection v1 preregistration.

This checker validates canonical closed artifacts, predecessor bindings, a
zero-execution observation, deterministic receipt construction, source purity,
and directed structural mutations.  It never calls a provider or unlocks a
credential, generator, sink, experiment, cost, or output permit.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable


BASELINE_COMMIT = "3ca858bd6f0097dd0f7f928e7acb4aef030a47a2"
PREDECESSOR_SOURCE_COMMIT = "3054ffe692e2e8f4edf22bda86fcbe4c9e1077d2"
PACK_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "preregistration_v1_pack_manifest.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_EXPERIMENT_V1_PREREGISTERED_"
    "NO_PROVIDER_INVOCATION_NO_PERMIT"
)
DECISION = "PREREGISTRATION_PASS_EXECUTION_BLOCKED_NO_AUTHORITY_OR_RUN_EVIDENCE"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_HARNESS_V1_"
    "OFFLINE_DOUBLE_IMPLEMENTATION"
)
MANAGED_TRACK = "MANAGED_SPANNER_CLOUD_KMS"
SELF_HOSTED_TRACK = "SELF_HOSTED_ETCD_OPENBAO"

RECEIPT_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-"
    "injection-preregistration-receipt-schema-v1.json"
)
OBSERVATION_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-"
    "injection-pre-execution-observation-schema-v1.json"
)
CONTRACT_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-"
    "injection-experiment-contract-v1.json"
)
SOURCE_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_"
    "preregistration_v1.py"
)
CHECKER_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_"
    "injection_preregistration_v1_pack.py"
)
OBSERVATION_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_preregistration_v1_pack_synthetic_v0.json"
)
EXPECTED_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_preregistration_v1_pack.expected.v0.tsv"
)
MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_"
    "injection_preregistration_v1_pack_v0.json"
)
REPORT_PATH = Path(
    "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-"
    "fault-injection-preregistration-v1-pack.md"
)
GATE_PATH = Path(
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-"
    "preregistration-v1-pack.sh"
)
PREDECESSOR_MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_"
    "boundary_v1_pack_v0.json"
)
PREDECESSOR_CONTRACT_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-"
    "execution-boundary-contract-v1.json"
)
PREDECESSOR_PACKET_PATHS = (
    "docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-"
    "boundary-design-receipt-schema-v1.json",
    "docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-"
    "execution-boundary-contract-v1.json",
    "docs/design/fixtures/biocortex-ab-track-b-production-provider-prerequisite-"
    "observation-source-profile-schema-v1.json",
    "scripts/eval/biocortex_ab_track_b_external_atomic_live_output_boundary_v1.py",
    "scripts/eval/check_biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack.py",
    "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_"
    "boundary_v1_pack_synthetic_v0.json",
    "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_"
    "boundary_v1_pack.expected.v0.tsv",
    "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_"
    "boundary_v1_pack_v0.json",
    "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-external-atomic-live-"
    "output-boundary-v1-pack.md",
    "scripts/check-biocortex-ab-track-b-external-atomic-live-output-boundary-v1-pack.sh",
)
PACKET_PATHS = (
    str(RECEIPT_SCHEMA_PATH),
    str(OBSERVATION_SCHEMA_PATH),
    str(CONTRACT_PATH),
    str(SOURCE_PATH),
    str(CHECKER_PATH),
    str(OBSERVATION_PATH),
    str(EXPECTED_PATH),
    str(MANIFEST_PATH),
    str(REPORT_PATH),
    str(GATE_PATH),
)
EVIDENCE_PATHS = (
    str(RECEIPT_SCHEMA_PATH),
    str(OBSERVATION_SCHEMA_PATH),
    str(CONTRACT_PATH),
    str(SOURCE_PATH),
    str(CHECKER_PATH),
    str(OBSERVATION_PATH),
    str(EXPECTED_PATH),
    str(REPORT_PATH),
) + PREDECESSOR_PACKET_PATHS


class PackError(RuntimeError):
    """Raised for any pack-level validation failure."""


def fail(message: str) -> None:
    raise PackError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail(f"cannot canonicalize JSON: {exc}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: fail(f"{label} has non-finite {token}"),
            object_pairs_hook=_reject_pairs,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"cannot load {label}: {exc}")
    require(type(value) is dict, f"{label} root must be an object")
    require(canonical_bytes(value) == raw, f"{label} is not canonical JSON")
    return value, raw


def exact_keys(value: Any, expected: tuple[str, ...], label: str) -> None:
    require(type(value) is dict, f"{label} must be an object")
    require(tuple(sorted(value)) == tuple(sorted(expected)), f"{label} key drift")


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return type(value) is dict
    if expected == "array":
        return type(value) is list
    if expected == "string":
        return type(value) is str
    if expected == "integer":
        return type(value) is int
    if expected == "number":
        return type(value) in (int, float)
    if expected == "boolean":
        return type(value) is bool
    if expected == "null":
        return value is None
    fail(f"unsupported JSON Schema type: {expected}")


def validate_json_schema(instance: Any, schema: Any, path: str = "$") -> None:
    require(type(schema) is dict, f"{path} schema must be an object")
    if "oneOf" in schema:
        branches = schema["oneOf"]
        require(type(branches) is list and branches, f"{path} oneOf shape drift")
        matches = 0
        for branch in branches:
            try:
                validate_json_schema(instance, branch, path)
            except PackError:
                continue
            matches += 1
        require(matches == 1, f"{path} must match exactly one oneOf branch")
        return
    if "const" in schema:
        require(instance == schema["const"] and type(instance) is type(schema["const"]), f"{path} const mismatch")
    if "enum" in schema:
        require(instance in schema["enum"], f"{path} enum mismatch")
    if "type" in schema:
        expected_type = schema["type"]
        require(type(expected_type) is str, f"{path} schema type must be a string")
        require(_type_matches(instance, expected_type), f"{path} type mismatch")
    if type(instance) is dict:
        properties = schema.get("properties", {})
        require(type(properties) is dict, f"{path} properties shape drift")
        required = schema.get("required", [])
        require(type(required) is list, f"{path} required shape drift")
        for key in required:
            require(key in instance, f"{path}.{key} is required")
        if schema.get("additionalProperties") is False:
            require(set(instance) <= set(properties), f"{path} has additional properties")
        for key, item in instance.items():
            if key in properties:
                validate_json_schema(item, properties[key], f"{path}.{key}")
    if type(instance) is list:
        if "maxItems" in schema:
            require(len(instance) <= schema["maxItems"], f"{path} exceeds maxItems")
        if "minItems" in schema:
            require(len(instance) >= schema["minItems"], f"{path} below minItems")
        if "items" in schema:
            for index, item in enumerate(instance):
                validate_json_schema(item, schema["items"], f"{path}[{index}]")
    if type(instance) is str:
        if "pattern" in schema:
            require(re.fullmatch(schema["pattern"], instance) is not None, f"{path} pattern mismatch")
        if schema.get("format") == "date-time":
            require(
                re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", instance)
                is not None,
                f"{path} date-time mismatch",
            )
    if type(instance) is int:
        if "minimum" in schema:
            require(instance >= schema["minimum"], f"{path} below minimum")
        if "maximum" in schema:
            require(instance <= schema["maximum"], f"{path} above maximum")


def validate_schema_document(schema: dict[str, Any], expected_id: str, label: str) -> None:
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{label} draft drift")
    require(schema.get("$id") == expected_id, f"{label} id drift")
    require(schema.get("type") == "object", f"{label} root type drift")
    require(schema.get("additionalProperties") is False, f"{label} root is not closed")
    require(type(schema.get("properties")) is dict, f"{label} properties missing")
    require(type(schema.get("required")) is list, f"{label} required missing")
    require(set(schema["properties"]) == set(schema["required"]), f"{label} property closure drift")


def load_source_module(path: Path) -> tuple[Any, str]:
    module_name = "_ab_reference_provider_fault_injection_preregistration_v1_owned"
    require(module_name not in sys.modules, "owned module name already occupied")
    spec = importlib.util.spec_from_file_location(module_name, path)
    require(spec is not None and spec.loader is not None, "cannot construct source module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        fail(f"cannot execute pure source: {exc}")
    return module, module_name


def validate_source_ast(path: Path) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        fail(f"cannot parse pure source: {exc}")
    allowed_imports = {"__future__", "hashlib", "json", "re", "typing"}
    forbidden_calls = {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "open",
    }
    forbidden_attributes = {
        "Popen",
        "call",
        "connect",
        "open",
        "popen",
        "request",
        "run",
        "system",
        "unlink",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".", 1)[0] in allowed_imports, f"forbidden source import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            require((node.module or "").split(".", 1)[0] in allowed_imports, f"forbidden source import-from: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls, f"forbidden source call: {node.func.id}")
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attributes, f"forbidden source attribute call: {node.func.attr}")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            fail("pure source may not mutate global or nonlocal state")


def _expect_reject(call: Callable[[], None], label: str) -> None:
    try:
        call()
    except Exception:
        return
    fail(f"directed mutation was accepted: {label}")


def run_directed_negative_tests(module: Any, contract: dict[str, Any], observation: dict[str, Any]) -> int:
    count = 0

    def reject_contract(mutated: dict[str, Any], label: str) -> None:
        nonlocal count
        _expect_reject(lambda: module.validate_contract(mutated), label)
        count += 1

    def reject_observation(mutated: dict[str, Any], label: str) -> None:
        nonlocal count
        _expect_reject(lambda: module.validate_observation(mutated), label)
        count += 1

    for key in tuple(contract):
        mutated = copy.deepcopy(contract)
        del mutated[key]
        reject_contract(mutated, f"contract missing {key}")

    for key in tuple(contract["boundary"]):
        mutated = copy.deepcopy(contract)
        mutated["boundary"][key] = True if key != "side_effects_unlocked" else "PROVIDER"
        reject_contract(mutated, f"boundary drift {key}")

    acceptance_mutations = {
        "all_planned_rows_required": False,
        "per_case_required_repetitions": 29,
        "post_outcome_exclusions_allowed": True,
        "statistical_claim_mode": "INFERENTIAL",
        "track_comparison_allowed": True,
    }
    for key, replacement in acceptance_mutations.items():
        mutated = copy.deepcopy(contract)
        mutated["acceptance_policy"][key] = replacement
        reject_contract(mutated, f"acceptance drift {key}")
    mutated = copy.deepcopy(contract)
    mutated["acceptance_policy"]["hard_fail_conditions"].pop()
    reject_contract(mutated, "hard-fail condition removed")
    mutated = copy.deepcopy(contract)
    mutated["acceptance_policy"]["hard_fail_conditions"][-1] = "ANY_RESOURCE_USE_OUTSIDE_LAB_ONLY"
    reject_contract(mutated, "hard-fail resource scope semantic drift")

    assignment_boolean_keys = (
        "configuration_frozen_before_assignment",
        "fresh_namespace_per_run",
        "injection_armed_after_assignment_before_candidate_start",
        "zero_post_assignment_case_substitution",
    )
    for key in assignment_boolean_keys:
        mutated = copy.deepcopy(contract)
        mutated["assignment_protocol"][key] = False
        reject_contract(mutated, f"assignment drift {key}")
    mutated = copy.deepcopy(contract)
    mutated["assignment_protocol"]["planned_balanced_blocks_per_track"] = 29
    reject_contract(mutated, "assignment block imbalance")
    mutated = copy.deepcopy(contract)
    mutated["assignment_protocol"]["track_interleaving"] = "ALLOWED"
    reject_contract(mutated, "track interleaving allowed")

    claims = contract["official_source_claims"]
    for index, claim in enumerate(claims):
        next_id = claims[(index + 1) % len(claims)]["claim_id"]
        for field, replacement in (
            ("claim_id", next_id),
            ("content_hash_attested", True),
            ("evidence_class", "EXECUTION_OBSERVED"),
            ("retrieved_on", "2026-07-14"),
            ("url", "https://example.invalid/not-official"),
        ):
            mutated = copy.deepcopy(contract)
            mutated["official_source_claims"][index][field] = replacement
            reject_contract(mutated, f"source {claim['claim_id']} drift {field}")
        if claim["claim_id"] in {"GSP03", "ETC04"}:
            mutated = copy.deepcopy(contract)
            mutated["official_source_claims"][index]["claim"] = (
                "OFFICIAL SOURCE TEXT REPLACED BY A DIFFERENT BUT SUFFICIENTLY LONG CLAIM"
            )
            reject_contract(mutated, f"source {claim['claim_id']} direct-fact semantic drift")

    for index, invariant in enumerate(contract["global_invariants"]):
        next_id = contract["global_invariants"][(index + 1) % 8]["invariant_id"]
        mutated = copy.deepcopy(contract)
        mutated["global_invariants"][index]["invariant_id"] = next_id
        reject_contract(mutated, f"global invariant duplicate {invariant['invariant_id']}")
        mutated = copy.deepcopy(contract)
        mutated["global_invariants"][index]["statement"] = "lowercase drift"
        reject_contract(mutated, f"global invariant statement drift {invariant['invariant_id']}")

    for track_index, track in enumerate(contract["tracks"]):
        other_locus = (
            "SELF_HOSTED_ADVERSARIAL_LAB"
            if track["track_id"] == MANAGED_TRACK
            else "MANAGED_SERVICE_WITH_CLIENT_FAULT_PROXY"
        )
        for case_index, case in enumerate(track["cases"]):
            mutations: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
                ("permit", lambda item: item.__setitem__("permit_allowed", True)),
                ("missing requirement", lambda item: item.pop("candidate_requirement")),
                ("unknown source", lambda item: item.__setitem__("source_ids", ["UNKNOWN"])),
                ("unknown invariant", lambda item: item.__setitem__("invariant_ids", ["UNKNOWN"])),
                (
                    "duplicate classification",
                    lambda item: item["allowed_classifications"].append(item["allowed_classifications"][0]),
                ),
                ("cross-track locus", lambda item: item.__setitem__("evidence_locus", other_locus)),
                ("empty forbidden claims", lambda item: item.__setitem__("forbidden_claims", [])),
            )
            for mutation_label, mutate in mutations:
                mutated = copy.deepcopy(contract)
                mutate(mutated["tracks"][track_index]["cases"][case_index])
                reject_contract(mutated, f"case {case['case_id']} {mutation_label}")
            if case["case_id"] in module.EXPECTED_CRITICAL_CASE_FIELDS:
                for field in module.EXPECTED_CRITICAL_CASE_FIELDS[case["case_id"]]:
                    mutated = copy.deepcopy(contract)
                    value = mutated["tracks"][track_index]["cases"][case_index][field]
                    if type(value) is str:
                        mutated["tracks"][track_index]["cases"][case_index][field] = "VALID_CAPS_SEMANTIC_DRIFT"
                    elif type(value) is list:
                        mutated["tracks"][track_index]["cases"][case_index][field] = (
                            list(reversed(value)) if len(value) > 1 else value + value
                        )
                    else:
                        fail(f"unsupported critical case mutation type: {field}")
                    reject_contract(mutated, f"case {case['case_id']} critical {field} drift")
            if case["case_id"] in module.EXPECTED_CASE_VARIANTS:
                mutated = copy.deepcopy(contract)
                mutated["tracks"][track_index]["cases"][case_index]["injection_variants"].pop()
                reject_contract(mutated, f"case {case['case_id']} variant closure drift")
        for invariant_index, invariant in enumerate(track["invariants"]):
            next_id = track["invariants"][(invariant_index + 1) % len(track["invariants"])]["invariant_id"]
            mutated = copy.deepcopy(contract)
            mutated["tracks"][track_index]["invariants"][invariant_index]["invariant_id"] = next_id
            reject_contract(mutated, f"track invariant duplicate {invariant['invariant_id']}")
            mutated = copy.deepcopy(contract)
            mutated["tracks"][track_index]["invariants"][invariant_index]["evidence_needed"] = "bad evidence"
            reject_contract(mutated, f"track invariant evidence drift {invariant['invariant_id']}")
            if invariant["invariant_id"] in module.EXPECTED_CRITICAL_INVARIANTS:
                for field in ("evidence_needed", "statement"):
                    mutated = copy.deepcopy(contract)
                    mutated["tracks"][track_index]["invariants"][invariant_index][field] = (
                        "VALID_CAPS_SEMANTIC_DRIFT"
                    )
                    reject_contract(
                        mutated,
                        f"track invariant {invariant['invariant_id']} critical {field} drift",
                    )
        mutated = copy.deepcopy(contract)
        mutated["tracks"][track_index]["preflight_requirements"].pop()
        reject_contract(mutated, f"track preflight removed {track['track_id']}")
        mutated = copy.deepcopy(contract)
        mutated["tracks"][track_index]["preflight_requirements"][0] = "VALID_CAPS_SEMANTIC_DRIFT"
        reject_contract(mutated, f"track preflight semantic drift {track['track_id']}")
        mutated = copy.deepcopy(contract)
        mutated["tracks"][track_index]["signing_attempt_state_machine"]["restart_rule"] = (
            "VALID_CAPS_SEMANTIC_DRIFT"
        )
        reject_contract(mutated, f"track signing state semantic drift {track['track_id']}")
        if track["track_id"] == MANAGED_TRACK:
            mutated = copy.deepcopy(contract)
            mutated["tracks"][track_index]["message_frame_reference"]["message_sha256"] = "0" * 64
            reject_contract(mutated, "managed message-frame reference drift")
        else:
            mutated = copy.deepcopy(contract)
            mutated["tracks"][track_index]["restore_witness_protocol"]["read_rule"] = (
                "SERIALIZABLE_STALE_READ_ALLOWED"
            )
            reject_contract(mutated, "self-hosted restore witness semantic drift")

    mutated = copy.deepcopy(contract)
    mutated["non_claims"].pop()
    reject_contract(mutated, "non-claim removed")
    mutated = copy.deepcopy(contract)
    mutated["cross_track_non_equivalence"].pop()
    reject_contract(mutated, "cross-track non-equivalence removed")
    mutated = copy.deepcopy(contract)
    mutated["experimental_unit"]["planned_run_rows"] = 1019
    reject_contract(mutated, "planned run rows drift")
    mutated = copy.deepcopy(contract)
    mutated["experimental_unit"]["run_key"] = ["TRACK_ID", "CASE_ID"]
    reject_contract(mutated, "run key drift")

    for key in tuple(observation):
        mutated = copy.deepcopy(observation)
        del mutated[key]
        reject_observation(mutated, f"observation missing {key}")
    for key in (
        "credentials_accessed",
        "experiment_executed",
        "external_organization_state_observed",
        "future_state_automatically_reaudited",
        "official_sources_refetched_before_execution",
        "paid_resources_provisioned",
        "provider_resources_bound",
    ):
        mutated = copy.deepcopy(observation)
        mutated[key] = True
        reject_observation(mutated, f"observation overclaim {key}")
    for key, replacement in (
        ("execution_evidence_sha256", "0" * 64),
        ("observed_at_utc", "2026-07-15T18:00:01Z"),
        ("run_rows", [{}]),
        ("side_effects_unlocked", "LAB"),
    ):
        mutated = copy.deepcopy(observation)
        mutated[key] = replacement
        reject_observation(mutated, f"observation drift {key}")
    for track_id in (MANAGED_TRACK, SELF_HOSTED_TRACK):
        mutated = copy.deepcopy(observation)
        mutated["track_case_counts"][track_id] += 1
        reject_observation(mutated, f"observation count drift {track_id}")
    return count


def validate_manifest(
    manifest: dict[str, Any],
    root: Path,
    negative_count: int,
) -> None:
    exact_keys(
        manifest,
        (
            "baseline_commit",
            "boundary",
            "data_quality",
            "date",
            "decision",
            "evidence_sha256",
            "known_limitations",
            "next_unit",
            "packet",
            "predecessor",
            "schema",
            "status",
            "test_oracle",
            "tracks",
        ),
        "manifest",
    )
    require(manifest["schema"] == PACK_SCHEMA, "manifest schema drift")
    require(manifest["baseline_commit"] == BASELINE_COMMIT, "manifest baseline drift")
    require(manifest["date"] == "2026-07-15", "manifest date drift")
    require(manifest["status"] == STATUS, "manifest status drift")
    require(manifest["decision"] == DECISION, "manifest decision drift")
    require(manifest["next_unit"] == NEXT_UNIT, "manifest next unit drift")
    require(
        manifest["predecessor"]
        == {
            "integration_commit": BASELINE_COMMIT,
            "manifest_path": str(PREDECESSOR_MANIFEST_PATH),
            "source_commit": PREDECESSOR_SOURCE_COMMIT,
        },
        "manifest predecessor drift",
    )
    boundary = manifest["boundary"]
    exact_keys(
        boundary,
        (
            "condition_output_authorized",
            "cost_authority_bound",
            "credentials_accessed",
            "experiment_executed",
            "live_generator_in_scope",
            "live_output_permit_defined",
            "paid_resources_provisioned",
            "production_adapter_in_scope",
            "provider_called",
            "receipt_is_output_permit",
            "side_effects_unlocked",
        ),
        "manifest boundary",
    )
    require(boundary.get("side_effects_unlocked") == "NONE", "manifest side effects drift")
    for key, value in boundary.items():
        if key != "side_effects_unlocked":
            require(value is False, f"manifest boundary overclaim: {key}")
    packet = manifest["packet"]
    exact_keys(packet, ("modes", "paths"), "manifest packet")
    require(packet["paths"] == list(PACKET_PATHS), "manifest packet path order drift")
    expected_modes = {path: ("100755" if path == str(GATE_PATH) else "100644") for path in PACKET_PATHS}
    require(packet["modes"] == expected_modes, "manifest packet modes drift")
    evidence = manifest["evidence_sha256"]
    require(type(evidence) is dict and set(evidence) == set(EVIDENCE_PATHS), "manifest evidence path closure drift")
    for path, expected_hash in evidence.items():
        try:
            raw = (root / path).read_bytes()
        except OSError as exc:
            fail(f"cannot read evidence path {path}: {exc}")
        require(sha256_bytes(raw) == expected_hash, f"manifest evidence hash drift: {path}")
    oracle = manifest["test_oracle"]
    require(
        oracle
        == {
            "directed_structural_and_frozen_semantic_negative_tests": negative_count,
            "invariants": 34,
            "managed_cases": 16,
            "official_source_claims": 16,
            "planned_run_rows": 1020,
            "repetitions_per_case": 30,
            "schema_documents": 2,
            "self_hosted_cases": 18,
            "tracks": 2,
        },
        "manifest test oracle drift",
    )
    require(
        manifest["tracks"]
        == {
            MANAGED_TRACK: {
                "case_count": 16,
                "claim_ceiling": "CLIENT_CONFORMANCE_AND_MANAGED_SERVICE_SEMANTICS_ONLY",
                "execution_status": "NOT_EXECUTED",
            },
            SELF_HOSTED_TRACK: {
                "case_count": 18,
                "claim_ceiling": "OWNED_LAB_ADVERSARIAL_BEHAVIOR_ONLY",
                "execution_status": "NOT_EXECUTED",
            },
        },
        "manifest track summary drift",
    )
    quality = manifest["data_quality"]
    require(type(quality) is dict and quality.get("execution_rows") == 0, "manifest quality execution row drift")
    require(
        quality.get("timeliness") == "REFETCH_REQUIRED_BEFORE_EXECUTION",
        "manifest quality timeliness drift",
    )
    limitations = manifest["known_limitations"]
    require(type(limitations) is list and len(limitations) >= 14, "manifest limitations too weak")
    require(len(limitations) == len(set(limitations)), "manifest duplicate limitation")


def validate_predecessor(manifest: dict[str, Any]) -> None:
    require(manifest.get("schema") == "agent_bridge.biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack_manifest.v0", "predecessor schema drift")
    require(manifest.get("status") == "EXTERNAL_ATOMIC_LIVE_OUTPUT_EXECUTION_BOUNDARY_V1_PREREGISTERED_NO_LIVE_OUTPUT_PERMIT", "predecessor status drift")
    require(manifest.get("next_unit") == "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_EXPERIMENT_V1_PREREGISTRATION", "predecessor next marker drift")
    predecessor_packet = manifest.get("packet", {}).get("paths")
    require(predecessor_packet == list(PREDECESSOR_PACKET_PATHS), "predecessor packet path closure drift")


def validate_message_frame_reference(
    contract: dict[str, Any],
    predecessor_contract: dict[str, Any],
    predecessor_raw: bytes,
) -> None:
    reference = contract["tracks"][0]["message_frame_reference"]
    require(reference["predecessor_contract_path"] == str(PREDECESSOR_CONTRACT_PATH), "message reference path drift")
    require(
        reference["predecessor_contract_sha256"] == sha256_bytes(predecessor_raw),
        "message reference predecessor hash drift",
    )
    require(
        reference["json_pointer"]
        == "/authority_grain/signature_receipt_contract/message_derivation",
        "message reference pointer drift",
    )
    derivation = predecessor_contract["authority_grain"]["signature_receipt_contract"][
        "message_derivation"
    ]
    require(derivation["closed"] is True, "predecessor message derivation is not closed")
    require(
        derivation["expected_message_bytes"] == reference["expected_message_bytes"] == 137,
        "message reference length drift",
    )
    require(
        derivation["known_answer_test"]["message_sha256"]
        == reference["message_sha256"]
        == "f5dcb16eec00a302bf56c9cc681b5c09d598589c4c3e9ab2413b68c21f16982d",
        "message reference known-answer hash drift",
    )


def evaluate(root: Path) -> tuple[str, int]:
    receipt_schema, _ = load_canonical(root / RECEIPT_SCHEMA_PATH, "receipt schema")
    observation_schema, _ = load_canonical(root / OBSERVATION_SCHEMA_PATH, "observation schema")
    contract, _ = load_canonical(root / CONTRACT_PATH, "contract")
    observation, _ = load_canonical(root / OBSERVATION_PATH, "observation")
    manifest, _ = load_canonical(root / MANIFEST_PATH, "manifest")
    predecessor_manifest, _ = load_canonical(root / PREDECESSOR_MANIFEST_PATH, "predecessor manifest")
    predecessor_contract, predecessor_contract_raw = load_canonical(
        root / PREDECESSOR_CONTRACT_PATH, "predecessor contract"
    )
    validate_schema_document(
        receipt_schema,
        "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_preregistration_receipt.v1",
        "receipt schema",
    )
    validate_schema_document(
        observation_schema,
        "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_pre_execution_observation.v0",
        "observation schema",
    )
    validate_json_schema(observation, observation_schema)
    validate_predecessor(predecessor_manifest)
    validate_message_frame_reference(contract, predecessor_contract, predecessor_contract_raw)
    validate_source_ast(root / SOURCE_PATH)
    module, module_name = load_source_module(root / SOURCE_PATH)
    try:
        require(module.BASELINE_COMMIT == BASELINE_COMMIT, "source baseline constant drift")
        require(module.STATUS == STATUS, "source status constant drift")
        require(module.DECISION == DECISION, "source decision constant drift")
        require(module.NEXT_UNIT == NEXT_UNIT, "source next unit constant drift")
        first = module.build_preregistration_receipt(contract, observation)
        second = module.self_test(contract, observation)
        require(canonical_bytes(first) == canonical_bytes(second), "source receipt nondeterminism")
        validate_json_schema(first, receipt_schema)
        rendered = module.render_receipt_tsv(first)
        negative_count = run_directed_negative_tests(module, contract, observation)
    finally:
        sys.modules.pop(module_name, None)
    validate_manifest(manifest, root, negative_count)
    try:
        expected = (root / EXPECTED_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail(f"cannot read expected TSV: {exc}")
    full_output = (
        rendered
        + f"directed_structural_and_frozen_semantic_negative_tests\t{negative_count}\n"
        + "schema_documents_validated\t2\n"
    )
    require(full_output == expected, "expected TSV drift")
    return full_output, negative_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        first, first_count = evaluate(root)
        if args.self_test:
            second, second_count = evaluate(root)
            require(first == second and first_count == second_count, "outer checker self-test drift")
        sys.stdout.write(first)
    except (PackError, OSError, ValueError) as exc:
        print(f"INVALID_BIOCORTEX_REFERENCE_PROVIDER_FAULT_INJECTION_PREREGISTRATION_V1: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
