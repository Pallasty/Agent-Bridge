#!/usr/bin/env python3
"""Validate the source-only Track B strict-review packet.

This standard-library-only checker audits the review-receipt schema, composes
two synthetic command/request/raw-response/review/receipt chains, and executes
the strict-case algorithm at case x opaque-answer grain.  Synthetic schema
acceptance is not execution or custody proof, and the strict result is not a
score claim or authority to unblind.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import types
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable


PACK_SCHEMA = "agent_bridge.biocortex_ab_track_b_strict_review_pack.v0"
FIXTURE_SCHEMA = "agent_bridge.biocortex_ab_track_b_strict_review_pack_synthetic.v0"
BASELINE_COMMIT = "ddebacba20146a90546db9e4ea4bd2795b9ecc1a"
GRAPH_SOURCE_COMMIT = "ba4dbae629398ec16e4f22f4b0ac7f2ce372541f"
PREDECESSOR_IDENTITY_SOURCE_COMMIT = "d20b2b856c461f6cf1fc8ce8fa88b6c5e11f5161"
CANONICAL_SERIALIZATION = (
    "UTF8_SORTED_KEYS_INDENT_2_LF_FINAL_NEWLINE_NO_NAN_DUPLICATE_KEYS_REJECTED"
)
DECISION = "SOURCE_STRICT_REVIEW_IMPLEMENTED_NOT_LIVE_BOUND"
DIALECT = "https://json-schema.org/draft/2020-12/schema"

MANIFEST_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_strict_review_pack_v0.json"
FIXTURE_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_strict_review_pack_synthetic_v0.json"
)
IDENTITY_FIXTURE_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_synthetic_v0.json"
)
IDENTITY_MANIFEST_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_v0.json"
)
GRAPH_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
LEDGER_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
ADMISSION_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
RECEIPT_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-review-receipt-schema-v0.json"
)
COMMAND_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-review-command-schema-v0.json"
)
REVIEW_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-review-schema-v0.json"
TRUTH_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-truth-manifest-schema-v0.json"
)
REFERENT_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-truth-referent-schema-v0.json"
)
STRICT_ALGORITHM_PATH = "scripts/eval/biocortex_ab_track_b_strict_case_v0.py"

GRAPH_SHA256 = "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af"
LEDGER_SHA256 = "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a"
ADMISSION_SHA256 = "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e"
IDENTITY_MANIFEST_SHA256 = (
    "c1a6c5a6c83d61f92d35948432b139749d19d5828f68a7fc2473859bba21a7e9"
)
IDENTITY_FIXTURE_SHA256 = (
    "094a7343543be2a9b32fc996dc3e7006bc9d02f87f8cc9bdd269ef9fb61a341a"
)
RECEIPT_SCHEMA_SHA256 = (
    "f8af1331ae134be0f09a5e546b2d67e0db8ebfabb2177dc14a376bac773f463c"
)
COMMAND_SCHEMA_SHA256 = (
    "40df0e39f36df01d414487c496cf09b5ffbed89cafc540dc89e6e57bea4466f5"
)
REVIEW_SCHEMA_SHA256 = (
    "2745cd373d4f99cdd4bb3d0bc9d9087966adb3a9d0594749cb1150b90d1e9422"
)
TRUTH_SCHEMA_SHA256 = (
    "520070d1eb4852fd2a005d63b3d087769b3240902289ff5c44f11c109bd1cde6"
)
REFERENT_SCHEMA_SHA256 = (
    "5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8"
)
STRICT_ALGORITHM_SHA256 = (
    "816c00eaff6c7e9df6ecca849e8c01ab8dbfe8a80834b37612d89f0a4ffa68b2"
)
FIXTURE_SHA256 = "3a5754d5ed718fb627ba95184650b3bddfae34ae202a2d1fbc52d978ab368583"

RESOURCE_CAPS = {
    "max_answers": 262144,
    "max_cases": 4096,
    "max_claim_scores_per_answer": 64,
    "max_forbidden_handles_per_answer": 64,
    "max_output_bytes": 33554432,
    "max_receipt_bytes": 1048576,
    "max_reviewer_evaluations": 524288,
    "max_schema_bytes": 1048576,
    "max_single_artifact_bytes": 33554432,
    "max_total_claim_scores": 1048576,
    "max_total_input_bytes": 67108864,
    "max_unmatched_unsupported_assertions_per_answer": 4096,
}

ARTIFACT_BINDINGS = (
    {
        "artifact_kind": "review_receipt_schema",
        "binding_path": "review_and_blinding.review_receipt_schema_sha256",
        "local_dependencies": [
            "review_and_blinding.review_command_schema_sha256",
            "review_and_blinding.review_schema_sha256",
        ],
        "provider_neutral": True,
        "repo_path": RECEIPT_SCHEMA_PATH,
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:review-receipt:v0",
        "sha256": RECEIPT_SCHEMA_SHA256,
        "source_status": "SOURCE_ARTIFACT_IMPLEMENTED_NOT_LIVE_BOUND",
        "unlocks_side_effect": False,
    },
    {
        "artifact_kind": "strict_case_pass_algorithm",
        "binding_path": "truth_inputs.strict_case_algorithm_sha256",
        "local_dependencies": [
            "review_and_blinding.review_schema_sha256",
            "truth_inputs.truth_manifest_schema_sha256",
        ],
        "provider_neutral": True,
        "repo_path": STRICT_ALGORITHM_PATH,
        "schema_id": None,
        "sha256": STRICT_ALGORITHM_SHA256,
        "source_status": "SOURCE_ARTIFACT_IMPLEMENTED_NOT_LIVE_BOUND",
        "unlocks_side_effect": False,
    },
)

COMPLETED_PUBLIC_BINDINGS = (
    "review_and_blinding.map_bijection_checker_sha256",
    "review_and_blinding.map_schema_sha256",
    "review_and_blinding.review_command_schema_sha256",
    "review_and_blinding.review_receipt_schema_sha256",
    "review_and_blinding.review_schema_sha256",
    "sampling.sampling_receipt_schema_sha256",
    "truth_inputs.referent_schema_sha256",
    "truth_inputs.strict_case_algorithm_sha256",
    "truth_inputs.truth_manifest_schema_sha256",
)

NEXT_PUBLIC_FRONTIER = (
    "reference_condition.context_builder_sha256",
    "sampling.sampling_seed_derivation_sha256",
    "sampling.sampling_selection_algorithm_sha256",
)

BOUNDARY = {
    "authority_basis_bytes_verified": False,
    "authority_true_count": 0,
    "blind_packet_bytes_verified": False,
    "currentness_basis_bytes_verified": False,
    "deterministic_truth_gate_provenance_verified": False,
    "gold_evidence_bytes_verified": False,
    "graph_packet_mutated": False,
    "live_binding_satisfied_count": 0,
    "o_excl_score_claim_created": False,
    "private_runtime_artifact_emitted": False,
    "real_review_receipt_created": False,
    "real_run_admitted": False,
    "review_instruction_bytes_verified": False,
    "reviewer_roster_verified": False,
    "runtime_instance_validated": False,
    "scoring_authorized": False,
    "side_effects_unlocked": "NONE",
    "source_artifact_count": 2,
    "unblinding_authorized": False,
}

SEMANTICS = {
    "abstention_gate": (
        "EXPECTED_ABSTAIN_REQUIRES_OBSERVED_ABSTAIN_AND_ABSTENTION_PASS_AND_"
        "EMPTY_CLAIM_SCORES_AND_CURRENTNESS_PASS_AND_ZERO_FORBIDDEN_AND_ZERO_"
        "UNSUPPORTED_AND_USEFULNESS_GTE_4"
    ),
    "agreement_role": "DIAGNOSTIC_ONLY_NOT_A_GATE_OR_RESCUE",
    "answer_gate": (
        "EXPECTED_ANSWER_REQUIRES_OBSERVED_ANSWER_AND_NOT_REQUIRED_ABSTENTION_"
        "AND_ALL_SCORE_RUBRICS_EQ_2_AND_CURRENTNESS_PASS_AND_ZERO_FORBIDDEN_"
        "AND_ZERO_UNSUPPORTED_AND_USEFULNESS_GTE_4"
    ),
    "case_weight_application": "NOT_APPLIED_HERE_APPLY_EXACTLY_ONCE_DOWNSTREAM",
    "deterministic_answer_gate": (
        "AUTHORITY_EXISTS_AND_ALL_GOLD_RECALLED_AND_CURRENT_REFERENT_CORRECT"
    ),
    "deterministic_gate_input_grain": "ONE_CASE_X_OPAQUE_ANSWER",
    "deterministic_gate_provenance": "EXPLICIT_INPUT_NOT_VERIFIED_BY_THIS_ALGORITHM",
    "invalid_or_incomplete_input": "TERMINAL_PROTOCOL_ERROR_NO_PARTIAL_RESULT",
    "preference_field_present": False,
    "raw_response_definition": (
        "EXACT_RESPONSE_SINK_BYTES_EQUAL_CANONICAL_POPULATED_REVIEW_BYTES_NOT_"
        "CLI_STDOUT_OR_LOG_STREAM"
    ),
    "receipt_grain": "ONE_TRIAL_X_REVIEWER_SLOT_X_SINGLE_INVOCATION",
    "receipt_validation_authority": "SCHEMA_VALIDATION_ONLY_NOT_CUSTODY_RECEIPT",
    "reviewer_combination": (
        "LOGICAL_AND_EXACTLY_TWO_DISTINCT_SLOTS_NO_AVERAGING_NO_RESCUE"
    ),
    "sampling_weight_present": False,
    "strict_case_grain": "ONE_CASE_X_OPAQUE_ANSWER_BEFORE_UNBLIND",
    "strict_result_authority": "VALIDATION_ONLY_NOT_SCORE_CLAIM",
    "valid_failing_judgment": "ACCEPTED_INPUT_WITH_STRICT_FALSE",
}

STRUCTURAL_BLOCKERS = (
    "DETERMINISTIC_TRUTH_GATE_PRODUCER_AND_PROVENANCE_UNBOUND",
    "REVIEW_PROVENANCE_CHECKER_UNBOUND",
    "REVIEW_RAW_RESPONSE_SCHEMA_UNBOUND",
    "REVIEWER_ROSTER_INSTRUCTION_AND_CONFLICT_MANIFEST_UNBOUND",
    "SOURCE_ARTIFACTS_ARE_NOT_RUNTIME_INSTANCES",
)

RETAINED_STAGE_OBLIGATIONS = (
    {
        "binding_field_present": False,
        "obligation": "both_command_request_raw_response_and_receipt_chains",
        "owner_class": "custodian_private",
        "required_stage": "PRE_UNBLIND",
        "status": "DECLARED_SYMBOL_NOT_BINDING_FIELD_BLOCKS",
    },
    {
        "binding_field_present": False,
        "obligation": "both_complete_review_objects",
        "owner_class": "custodian_private",
        "required_stage": "PRE_UNBLIND",
        "status": "DECLARED_SYMBOL_NOT_BINDING_FIELD_BLOCKS",
    },
    {
        "binding_field_present": False,
        "obligation": "contract_scoped_o_excl_score_claim",
        "owner_class": "custodian_private",
        "required_stage": "PRE_UNBLIND",
        "status": "DECLARED_SYMBOL_NOT_BINDING_FIELD_BLOCKS",
    },
    {
        "binding_field_present": False,
        "obligation": "map_bijection_receipt_sha256",
        "owner_class": "custodian_private",
        "required_stage": "POST_GENERATION_PRE_REVIEW",
        "status": "DECLARED_REQUIRED_ARTIFACT_NOT_BINDING_FIELD_BLOCKS",
    },
)

EXPECTED_EVIDENCE = {
    COMMAND_SCHEMA_PATH: COMMAND_SCHEMA_SHA256,
    REVIEW_SCHEMA_PATH: REVIEW_SCHEMA_SHA256,
    TRUTH_SCHEMA_PATH: TRUTH_SCHEMA_SHA256,
    REFERENT_SCHEMA_PATH: REFERENT_SCHEMA_SHA256,
    GRAPH_PATH: GRAPH_SHA256,
    IDENTITY_FIXTURE_PATH: IDENTITY_FIXTURE_SHA256,
    IDENTITY_MANIFEST_PATH: IDENTITY_MANIFEST_SHA256,
    LEDGER_PATH: LEDGER_SHA256,
    ADMISSION_PATH: ADMISSION_SHA256,
}

SCHEMA_CATALOG = (
    {
        "key": "receipt",
        "path": RECEIPT_SCHEMA_PATH,
        "sha256": RECEIPT_SCHEMA_SHA256,
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:review-receipt:v0",
    },
    {
        "key": "command",
        "path": COMMAND_SCHEMA_PATH,
        "sha256": COMMAND_SCHEMA_SHA256,
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:review-command:v0",
    },
    {
        "key": "review",
        "path": REVIEW_SCHEMA_PATH,
        "sha256": REVIEW_SCHEMA_SHA256,
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:review:v0",
    },
    {
        "key": "truth",
        "path": TRUTH_SCHEMA_PATH,
        "sha256": TRUTH_SCHEMA_SHA256,
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:truth-manifest:v0",
    },
)

COMMAND_BOUNDARY = {
    "authorizes_execution": False,
    "automatic_retry": False,
    "condition_mapping_present": False,
    "contains_credentials": False,
    "external_fact_access": False,
    "mcp_access": False,
    "parent_environment_inherited": False,
    "postprocessing_applied": False,
    "project_access": False,
    "provider_neutral_record": True,
    "raw_private_input_present": False,
    "repository_access": False,
    "tool_access": False,
    "unblinding_allowed": False,
    "workspace_mode": "EMPTY_EPHEMERAL",
}

RECEIPT_BOUNDARY = {
    "authorizes_scoring": False,
    "authorizes_unblinding": False,
    "condition_mapping_present": False,
    "custody_proof_required": True,
    "filesystem_o_excl_proof_required": True,
    "private_record": True,
    "provider_neutral_record": True,
    "raw_response_private": True,
    "receipt_schema_acceptance_proves_execution": False,
    "score_claim_created": False,
    "self_attestation_sufficient": False,
    "unblinding_performed": False,
}

ALLOWED_SCHEMA_KEYWORDS = {
    "$defs",
    "$id",
    "$ref",
    "$schema",
    "additionalProperties",
    "const",
    "description",
    "items",
    "maxItems",
    "maxLength",
    "maximum",
    "minItems",
    "minLength",
    "minimum",
    "pattern",
    "properties",
    "required",
    "title",
    "type",
    "unevaluatedProperties",
    "uniqueItems",
}

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class CheckError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise CheckError(code, message)


def reject_constant(value: str) -> Any:
    fail("JSON_CONSTANT", f"non-finite JSON constant {value!r}")


def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("JSON_DUPLICATE_KEY", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def canonical_pretty_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("JSON_CANONICAL", f"value cannot be canonical JSON: {exc}")


def canonical_compact_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("JSON_CANONICAL", f"value cannot be compact canonical JSON: {exc}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_object(value: Any) -> str:
    return sha256_bytes(canonical_pretty_bytes(value))


def resolve_path(root: Path, relative: str) -> Path:
    if type(relative) is not str or not relative or "\\" in relative:
        fail("PATH", f"non-canonical path {relative!r}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        fail("PATH", f"non-canonical path {relative!r}")
    path = root.joinpath(*pure.parts)
    try:
        path.relative_to(root)
    except ValueError:
        fail("PATH", f"path escapes root: {relative!r}")
    return path


def read_bytes(root: Path, relative: str, maximum: int | None = None) -> bytes:
    path = resolve_path(root, relative)
    cap = maximum if maximum is not None else RESOURCE_CAPS["max_single_artifact_bytes"]
    try:
        size = path.stat().st_size
        if size < 0 or size > cap:
            fail("FILE_SIZE", f"{relative} exceeds its byte cap")
        raw = path.read_bytes()
    except OSError as exc:
        fail("FILE_READ", f"cannot read {relative}: {exc}")
    if len(raw) != size:
        fail("FILE_RACE", f"{relative} changed while being read")
    return raw


def parse_json(raw: bytes, label: str) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        fail("JSON_BOM", f"{label} has a UTF-8 BOM")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("JSON_UTF8", f"{label} is not UTF-8: {exc}")
    try:
        return json.loads(
            text,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_pairs,
        )
    except json.JSONDecodeError as exc:
        fail("JSON_PARSE", f"{label} is malformed: {exc}")


def parse_canonical_json(raw: bytes, label: str) -> Any:
    value = parse_json(raw, label)
    if raw != canonical_pretty_bytes(value):
        fail("JSON_CANONICAL", f"{label} is not canonical pretty JSON")
    return value


def load_canonical(
    root: Path, relative: str, maximum: int | None = None
) -> tuple[Any, bytes]:
    raw = read_bytes(root, relative, maximum)
    return parse_canonical_json(raw, relative), raw


def require_object(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        fail("TYPE_OBJECT", f"{label} must be an object")
    return value


def require_array(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        fail("TYPE_ARRAY", f"{label} must be an array")
    return value


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        fail(
            "EXACT_KEYS",
            f"{label} fields drift: missing={sorted(expected-set(value))} "
            f"extra={sorted(set(value)-expected)}",
        )


def require_sha(value: Any, label: str) -> str:
    if type(value) is not str or SHA_RE.fullmatch(value) is None:
        fail("SHA256", f"{label} must be lowercase SHA-256")
    return value


def require_utc(value: Any, label: str) -> datetime:
    if type(value) is not str or UTC_RE.fullmatch(value) is None:
        fail("UTC", f"{label} must be canonical UTC seconds")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        fail("UTC", f"{label} is not a real UTC instant: {exc}")


def collect_refs(value: Any) -> list[str]:
    result: list[str] = []
    if type(value) is dict:
        if "$ref" in value:
            result.append(value["$ref"])
        for child in value.values():
            result.extend(collect_refs(child))
    elif type(value) is list:
        for child in value:
            result.extend(collect_refs(child))
    return result


def validate_schema_document(schema: Any, entry: dict[str, str]) -> dict[str, int]:
    schema = require_object(schema, f"{entry['key']} schema")
    if schema.get("$schema") != DIALECT:
        fail("SCHEMA_DIALECT", f"{entry['key']} schema dialect drift")
    if schema.get("$id") != entry["schema_id"]:
        fail("SCHEMA_ID", f"{entry['key']} schema id drift")
    definitions = require_object(schema.get("$defs"), f"{entry['key']}.$defs")
    if not definitions:
        fail("DEFS_EMPTY", f"{entry['key']} definitions are empty")

    object_count = 0
    node_count = 0
    seen_refs: list[str] = []

    def walk(node: Any, path: str, *, root_node: bool = False) -> None:
        nonlocal object_count, node_count
        node_count += 1
        node = require_object(node, path)
        unknown = set(node) - ALLOWED_SCHEMA_KEYWORDS
        if unknown:
            fail("SCHEMA_KEYWORD", f"{path} has forbidden keywords {sorted(unknown)}")
        forms = int("$ref" in node) + int("const" in node) + int("type" in node)
        if forms != 1:
            fail("SCHEMA_FORM", f"{path} must be exactly one ref, const, or type")
        if "$ref" in node:
            if set(node) != {"$ref"}:
                fail("REF_SIBLING", f"{path} has a ref sibling")
            ref = node["$ref"]
            if type(ref) is not str or re.fullmatch(
                r"#/\$defs/[A-Za-z][A-Za-z0-9]*", ref
            ) is None:
                fail("REF_POLICY", f"{path} uses a non-local or encoded ref")
            name = ref.rsplit("/", 1)[1]
            if name not in definitions:
                fail("REF_UNRESOLVED", f"{path} references missing {name!r}")
            seen_refs.append(name)
            return
        if "const" in node:
            if set(node) != {"const"}:
                fail("CONST_SIBLING", f"{path} has a const sibling")
            if type(node["const"]) not in {str, bool, int}:
                fail("SCHEMA_CONST", f"{path} has unsupported const")
            return

        kind = node["type"]
        if type(kind) is not str or kind not in {"object", "array", "string", "integer"}:
            fail("SCHEMA_TYPE", f"{path} has unsupported type {kind!r}")
        allowed = {
            "object": {
                "additionalProperties",
                "properties",
                "required",
                "type",
                "unevaluatedProperties",
            },
            "array": {"items", "maxItems", "minItems", "type", "uniqueItems"},
            "string": {"maxLength", "minLength", "pattern", "type"},
            "integer": {"maximum", "minimum", "type"},
        }[kind]
        if root_node:
            allowed |= {"$defs", "$id", "$schema", "description", "title"}
        irrelevant = set(node) - allowed
        if irrelevant:
            fail("SCHEMA_GRAMMAR", f"{path} has irrelevant {sorted(irrelevant)}")
        if kind == "object":
            object_count += 1
            if node.get("additionalProperties") is not False:
                fail("OBJECT_OPEN", f"{path} must set additionalProperties=false")
            if node.get("unevaluatedProperties") is not False:
                fail("OBJECT_OPEN", f"{path} must set unevaluatedProperties=false")
            properties = require_object(node.get("properties"), f"{path}.properties")
            required = node.get("required")
            if (
                type(required) is not list
                or any(type(item) is not str for item in required)
                or required != sorted(required)
                or len(required) != len(set(required))
                or set(required) != set(properties)
            ):
                fail("OBJECT_REQUIRED", f"{path} must require every property, sorted")
            for key, child in properties.items():
                walk(child, f"{path}.properties.{key}")
        elif kind == "array":
            minimum = node.get("minItems", 0)
            maximum = node.get("maxItems")
            if (
                type(minimum) is not int
                or type(maximum) is not int
                or type(minimum) is bool
                or type(maximum) is bool
                or minimum < 0
                or maximum < minimum
            ):
                fail("ARRAY_BOUND", f"{path} lacks finite valid item bounds")
            if "uniqueItems" in node and node["uniqueItems"] is not True:
                fail("ARRAY_UNIQUE", f"{path}.uniqueItems may only be true")
            walk(node.get("items"), f"{path}.items")
        elif kind == "string":
            minimum = node.get("minLength")
            maximum = node.get("maxLength")
            pattern = node.get("pattern")
            if (
                type(minimum) is not int
                or type(maximum) is not int
                or type(pattern) is not str
                or type(minimum) is bool
                or type(maximum) is bool
                or minimum < 0
                or maximum < minimum
            ):
                fail("STRING_BOUND", f"{path} lacks finite valid string bounds")
            try:
                re.compile(pattern, re.ASCII)
            except re.error as exc:
                fail("STRING_PATTERN", f"{path} has invalid pattern: {exc}")
        else:
            minimum = node.get("minimum")
            maximum = node.get("maximum")
            if (
                type(minimum) is not int
                or type(maximum) is not int
                or type(minimum) is bool
                or type(maximum) is bool
                or maximum < minimum
            ):
                fail("INTEGER_BOUND", f"{path} lacks finite valid integer bounds")

    walk(schema, f"{entry['key']}.root", root_node=True)
    for name, definition in definitions.items():
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) is None:
            fail("DEF_NAME", f"{entry['key']} has invalid definition name {name!r}")
        walk(definition, f"{entry['key']}.$defs.{name}")
    defined = set(definitions)
    referenced = set(seen_refs)
    if referenced != defined:
        fail(
            "DEF_COVERAGE",
            f"{entry['key']} unreferenced={sorted(defined-referenced)} "
            f"missing={sorted(referenced-defined)}",
        )
    for ref in collect_refs(schema):
        if not ref.startswith("#/$defs/"):
            fail("REF_POLICY", f"{entry['key']} has remote ref {ref!r}")
    dependency_graph = {
        name: {ref.rsplit("/", 1)[1] for ref in collect_refs(definition)}
        for name, definition in definitions.items()
    }
    active: set[str] = set()
    complete: set[str] = set()

    def visit(name: str) -> None:
        if name in active:
            fail("REF_CYCLE", f"{entry['key']} definition cycle at {name}")
        if name in complete:
            return
        active.add(name)
        for target in sorted(dependency_graph[name]):
            visit(target)
        active.remove(name)
        complete.add(name)

    for name in sorted(definitions):
        visit(name)
    return {
        "local_ref_count": len(seen_refs),
        "node_count": node_count,
        "object_count": object_count,
    }


def validate_instance(schema: dict[str, Any], value: Any, path: str) -> None:
    definitions = require_object(schema.get("$defs"), "schema.$defs")

    def check(node: dict[str, Any], item: Any, item_path: str) -> None:
        if "$ref" in node:
            ref = node["$ref"]
            if type(ref) is not str or not ref.startswith("#/$defs/"):
                fail("INSTANCE_REF", f"{item_path} uses an unsupported ref")
            name = ref.rsplit("/", 1)[1]
            if name not in definitions:
                fail("INSTANCE_REF", f"{item_path} references a missing definition")
            check(require_object(definitions[name], f"schema.$defs.{name}"), item, item_path)
            return
        if "const" in node:
            expected = node["const"]
            if type(item) is not type(expected) or item != expected:
                fail("INSTANCE_CONST", f"{item_path} must equal {expected!r}")
            return
        kind = node.get("type")
        if kind == "object":
            if type(item) is not dict:
                fail("INSTANCE_TYPE", f"{item_path} must be an object")
            properties = require_object(node.get("properties"), f"{item_path}.properties")
            required = node.get("required")
            if type(required) is not list:
                fail("INSTANCE_SCHEMA", f"{item_path} required list is absent")
            missing = set(required) - set(item)
            extra = set(item) - set(properties)
            if missing:
                fail("INSTANCE_REQUIRED", f"{item_path} missing {sorted(missing)}")
            if extra:
                fail("INSTANCE_EXTRA", f"{item_path} has extra {sorted(extra)}")
            for key in required:
                check(
                    require_object(properties[key], f"schema property {key}"),
                    item[key],
                    f"{item_path}.{key}",
                )
        elif kind == "array":
            if type(item) is not list:
                fail("INSTANCE_TYPE", f"{item_path} must be an array")
            minimum = node.get("minItems", 0)
            maximum = node.get("maxItems")
            if type(minimum) is not int or type(maximum) is not int:
                fail("INSTANCE_SCHEMA", f"{item_path} array bounds are absent")
            if not minimum <= len(item) <= maximum:
                fail("INSTANCE_ARRAY_BOUND", f"{item_path} length is outside bounds")
            if node.get("uniqueItems"):
                identities = [canonical_compact_bytes(row) for row in item]
                if len(identities) != len(set(identities)):
                    fail("INSTANCE_UNIQUE", f"{item_path} has duplicates")
            child = require_object(node.get("items"), f"{item_path}.items")
            for index, row in enumerate(item):
                check(child, row, f"{item_path}[{index}]")
        elif kind == "string":
            if type(item) is not str:
                fail("INSTANCE_TYPE", f"{item_path} must be a string")
            minimum = node.get("minLength")
            maximum = node.get("maxLength")
            pattern = node.get("pattern")
            if type(minimum) is not int or type(maximum) is not int or type(pattern) is not str:
                fail("INSTANCE_SCHEMA", f"{item_path} string bounds are absent")
            if not minimum <= len(item) <= maximum:
                fail("INSTANCE_STRING_BOUND", f"{item_path} length is outside bounds")
            if re.fullmatch(pattern, item, re.ASCII) is None:
                fail("INSTANCE_PATTERN", f"{item_path} does not match its pattern")
        elif kind == "integer":
            if type(item) is not int:
                fail("INSTANCE_TYPE", f"{item_path} must be an integer, not bool/float")
            minimum = node.get("minimum")
            maximum = node.get("maximum")
            if type(minimum) is not int or type(maximum) is not int:
                fail("INSTANCE_SCHEMA", f"{item_path} integer bounds are absent")
            if not minimum <= item <= maximum:
                fail("INSTANCE_INTEGER_BOUND", f"{item_path} is outside bounds")
        else:
            fail("INSTANCE_SCHEMA", f"{item_path} uses unsupported type {kind!r}")

    check(schema, value, path)


def load_strict_module(root: Path) -> types.ModuleType:
    path = resolve_path(root, STRICT_ALGORITHM_PATH)
    raw = read_bytes(root, STRICT_ALGORITHM_PATH, 2 * 1024 * 1024)
    if sha256_bytes(raw) != STRICT_ALGORITHM_SHA256:
        fail("STRICT_ALGORITHM_HASH", "strict-case algorithm byte hash drift")
    spec = importlib.util.spec_from_file_location("track_b_strict_case_v0", path)
    if spec is None or spec.loader is None:
        fail("STRICT_IMPORT", "cannot create strict-case module spec")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        fail("STRICT_IMPORT", f"cannot load strict-case algorithm: {exc}")
    return module


def derive_frontier(graph: dict[str, Any], completed: set[str]) -> tuple[str, ...]:
    result: list[str] = []
    for node in graph["nodes"]:
        path = node["artifact_binding_path"]
        if path in completed or node["primary_readiness_class"] != "INDEPENDENT_PUBLIC":
            continue
        if set(node["local_dependencies"]).issubset(completed):
            result.append(path)
    return tuple(sorted(result))


def validate_manifest_value(
    root: Path,
    manifest: Any,
    fixture_raw: bytes,
    graph: dict[str, Any],
) -> None:
    manifest = require_object(manifest, "pack manifest")
    require_exact_keys(
        manifest,
        {
            "artifact_bindings",
            "baseline_commit",
            "boundary",
            "canonical_serialization",
            "completed_public_bindings",
            "date",
            "decision",
            "evidence_sha256",
            "graph_sha256",
            "graph_source_commit",
            "next_public_frontier",
            "predecessor_identity_pack_sha256",
            "predecessor_identity_source_commit",
            "resource_caps",
            "retained_stage_obligations",
            "schema",
            "semantics",
            "structural_blockers",
            "synthetic_fixture_path",
            "synthetic_fixture_sha256",
        },
        "pack manifest",
    )
    scalar_expected = {
        "baseline_commit": BASELINE_COMMIT,
        "canonical_serialization": CANONICAL_SERIALIZATION,
        "date": "2026-07-14",
        "decision": DECISION,
        "graph_sha256": GRAPH_SHA256,
        "graph_source_commit": GRAPH_SOURCE_COMMIT,
        "predecessor_identity_pack_sha256": IDENTITY_MANIFEST_SHA256,
        "predecessor_identity_source_commit": PREDECESSOR_IDENTITY_SOURCE_COMMIT,
        "schema": PACK_SCHEMA,
        "synthetic_fixture_path": FIXTURE_PATH,
        "synthetic_fixture_sha256": FIXTURE_SHA256,
    }
    for key, expected in scalar_expected.items():
        if manifest[key] != expected:
            fail("MANIFEST_SCALAR", f"manifest {key} drift")
    if manifest["synthetic_fixture_sha256"] != sha256_bytes(fixture_raw):
        fail("MANIFEST_FIXTURE_HASH", "manifest does not bind exact fixture bytes")
    structures = {
        "artifact_bindings": list(ARTIFACT_BINDINGS),
        "boundary": BOUNDARY,
        "completed_public_bindings": list(COMPLETED_PUBLIC_BINDINGS),
        "evidence_sha256": EXPECTED_EVIDENCE,
        "next_public_frontier": list(NEXT_PUBLIC_FRONTIER),
        "resource_caps": RESOURCE_CAPS,
        "retained_stage_obligations": list(RETAINED_STAGE_OBLIGATIONS),
        "semantics": SEMANTICS,
        "structural_blockers": list(STRUCTURAL_BLOCKERS),
    }
    for key, expected in structures.items():
        if manifest[key] != expected:
            fail(f"MANIFEST_{key.upper()}", f"manifest {key} drift")
    for path, expected in EXPECTED_EVIDENCE.items():
        if sha256_bytes(read_bytes(root, path)) != expected:
            fail("EVIDENCE_HASH", f"evidence bytes drift: {path}")
    ledger = require_object(
        parse_canonical_json(read_bytes(root, LEDGER_PATH), LEDGER_PATH), "live ledger"
    )
    if ledger.get("stage_obligations") != list(RETAINED_STAGE_OBLIGATIONS):
        fail("LEDGER_STAGE_OBLIGATIONS", "retained stage obligations differ from ledger")
    for binding in ARTIFACT_BINDINGS:
        if sha256_bytes(read_bytes(root, binding["repo_path"])) != binding["sha256"]:
            fail("ARTIFACT_HASH", f"artifact bytes drift: {binding['repo_path']}")

    nodes = require_array(graph.get("nodes"), "graph.nodes")
    graph_nodes = {node["artifact_binding_path"]: node for node in nodes}
    if len(graph_nodes) != len(nodes):
        fail("GRAPH_DUPLICATE", "graph repeats an artifact binding path")
    for binding in ARTIFACT_BINDINGS:
        node = graph_nodes.get(binding["binding_path"])
        if node is None:
            fail("GRAPH_COVERAGE", f"graph lacks {binding['binding_path']}")
        if (
            node["artifact_kind"] != binding["artifact_kind"]
            or node["local_dependencies"] != binding["local_dependencies"]
            or node["primary_readiness_class"] != "INDEPENDENT_PUBLIC"
            or node["public_authoring_eligible"] is not True
            or node["required_stage"] != "PRE_OUTPUT_ADMISSION"
            or node["binding_satisfied"] is not False
            or node["binding_evidence"] is not None
            or node["external_dependencies"] != []
            or node["blocked_upstream_dependencies"] != []
            or node["unrepresented_upstream_dependencies"] != []
            or node["unlocks_side_effect"] is not False
        ):
            fail("GRAPH_TARGET", f"graph target drift: {binding['binding_path']}")
    if derive_frontier(graph, set(COMPLETED_PUBLIC_BINDINGS)) != NEXT_PUBLIC_FRONTIER:
        fail("GRAPH_FRONTIER", "derived three-node frontier drift")


def validate_resource_alignment(
    schemas: dict[str, dict[str, Any]], strict_module: types.ModuleType
) -> None:
    expected_module_caps = {
        "MAX_ANSWERS": RESOURCE_CAPS["max_answers"],
        "MAX_CASES": RESOURCE_CAPS["max_cases"],
        "MAX_OUTPUT_BYTES": RESOURCE_CAPS["max_output_bytes"],
        "MAX_REVIEWER_EVALUATIONS": RESOURCE_CAPS["max_reviewer_evaluations"],
        "MAX_SINGLE_INPUT_BYTES": RESOURCE_CAPS["max_single_artifact_bytes"],
        "MAX_TOTAL_CLAIM_SCORES": RESOURCE_CAPS["max_total_claim_scores"],
        "MAX_TOTAL_INPUT_BYTES": RESOURCE_CAPS["max_total_input_bytes"],
    }
    for name, expected in expected_module_caps.items():
        if getattr(strict_module, name, None) != expected:
            fail("RESOURCE_ALIGNMENT", f"strict algorithm {name} differs from manifest")
    answer_review = schemas["review"]["$defs"]["answerReview"]["properties"]
    checks = {
        "claim_scores": (
            answer_review["claim_scores"].get("maxItems"),
            RESOURCE_CAPS["max_claim_scores_per_answer"],
        ),
        "forbidden_handles": (
            answer_review["matched_forbidden_assertion_handles"].get("maxItems"),
            RESOURCE_CAPS["max_forbidden_handles_per_answer"],
        ),
        "unsupported_assertions": (
            answer_review["unmatched_unsupported_assertion_count"].get("maximum"),
            RESOURCE_CAPS["max_unmatched_unsupported_assertions_per_answer"],
        ),
        "review_cases": (
            schemas["review"]["properties"]["cases"].get("maxItems"),
            RESOURCE_CAPS["max_cases"],
        ),
        "truth_cases": (
            schemas["truth"]["properties"]["cases"].get("maxItems"),
            RESOURCE_CAPS["max_cases"],
        ),
    }
    for label, (observed, expected) in checks.items():
        if observed != expected:
            fail("RESOURCE_ALIGNMENT", f"{label} cap differs from manifest")


def apply_second_review_overrides(
    first_review: dict[str, Any], fixture: dict[str, Any]
) -> dict[str, Any]:
    second = copy.deepcopy(first_review)
    second["reviewer_slot"] = fixture["receipt_runs"][1]["reviewer_slot"]
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for case in second["cases"]:
        for answer in case["answers"]:
            index[(case["case_id"], answer["answer_id"])] = answer
    seen: set[tuple[str, str]] = set()
    for row in fixture["second_review_overrides"]:
        require_exact_keys(row, {"answer_id", "case_id", "fields"}, "review override")
        key = (row["case_id"], row["answer_id"])
        if key in seen or key not in index:
            fail("FIXTURE_OVERRIDE", f"invalid or duplicate override {key}")
        seen.add(key)
        fields = require_object(row["fields"], "review override fields")
        if not fields or not set(fields).issubset(index[key]):
            fail("FIXTURE_OVERRIDE", f"override fields drift for {key}")
        index[key].update(copy.deepcopy(fields))
    if seen != set(index):
        fail("FIXTURE_OVERRIDE", "second-review overrides must cover every answer once")
    return second


def build_reviewer_roster(fixture: dict[str, Any]) -> dict[str, Any]:
    rows = []
    conflict_rows = {
        row["reviewer_slot"]: row["conflict_disclosed"]
        for row in fixture["reviewer_conflict_and_overlap_manifest"]["rows"]
    }
    for run in fixture["receipt_runs"]:
        rows.append(
            {
                "conflict_disclosed": conflict_rows.get(run["reviewer_slot"]),
                "executor_profile_sha256": sha256_object(run["executor_profile"]),
                "reviewer_slot": run["reviewer_slot"],
            }
        )
    return {
        "rows": rows,
        "schema": "agent_bridge.synthetic_reviewer_roster.v0",
        "trial_id": fixture["deterministic_truth_gates"]["trial_id"],
    }


def build_command(run: dict[str, Any], review: dict[str, Any], blind_sha: str) -> dict[str, Any]:
    request_raw = run["stdin_request_utf8"].encode("utf-8")
    return {
        "argv": [
            "synthetic-reviewer",
            "--stdin",
            "--response-sink",
            run["response_sink_id"],
        ],
        "argv_execution": "DIRECT_EXECVE_NO_SHELL",
        "blind_packet_sha256": blind_sha,
        "boundary": COMMAND_BOUNDARY,
        "context_environment_keys": [],
        "contract_sha256": review["contract_sha256"],
        "created_at_utc": run["command_created_at_utc"],
        "executor_profile_sha256": sha256_object(run["executor_profile"]),
        "response_sink_id": run["response_sink_id"],
        "response_sink_must_not_exist": True,
        "response_write_mode": "O_EXCL_SINGLE_FILE",
        "retry_policy": "ZERO_RETRY",
        "review_instruction_sha256": review["review_instruction_sha256"],
        "reviewer_slot": review["reviewer_slot"],
        "schema": "agent_bridge.biocortex_ab_track_b_review_command.v0",
        "stdin_delivery": "EXACT_BYTES_BY_STDIN",
        "stdin_request_sha256": sha256_bytes(request_raw),
        "trial_id": review["trial_id"],
        "working_directory_manifest_sha256": sha256_object(
            run["working_directory_manifest"]
        ),
    }


def build_receipt(
    run: dict[str, Any],
    review: dict[str, Any],
    command_raw: bytes,
    raw_response: bytes,
    reviewer_roster_sha256: str,
    conflict_manifest_sha256: str,
) -> dict[str, Any]:
    request_raw = run["stdin_request_utf8"].encode("utf-8")
    workspace_sha = sha256_object(run["working_directory_manifest"])
    review_sha = sha256_bytes(raw_response)
    return {
        "blind_packet_sha256": review["blind_packet_sha256"],
        "boundary": RECEIPT_BOUNDARY,
        "completed_at_utc": run["completed_at_utc"],
        "contract_sha256": review["contract_sha256"],
        "created_at_utc": run["created_at_utc"],
        "custodian_identity_sha256": sha256_object(run["custodian_identity"]),
        "execution_environment_sha256": sha256_object(run["execution_environment"]),
        "execution_trace_sha256": sha256_object(run["execution_trace"]),
        "executor_profile_sha256": sha256_object(run["executor_profile"]),
        "exit_code": 0,
        "external_fact_access_count": 0,
        "invocation_index": 1,
        "invocation_nonce_sha256": sha256_bytes(run["invocation_nonce"].encode("utf-8")),
        "mcp_server_count": 0,
        "project_context_loaded": False,
        "raw_response_byte_length": len(raw_response),
        "raw_response_equals_review_exact_bytes": True,
        "raw_response_sha256": review_sha,
        "receipt_writer_sha256": sha256_object(run["receipt_writer"]),
        "response_sink_created_exclusively": True,
        "response_sink_file_fsync_completed": True,
        "response_sink_file_mode": "0600",
        "response_sink_id": run["response_sink_id"],
        "response_sink_must_not_have_existed": True,
        "response_sink_nlink": 1,
        "response_sink_parent_directory_fsync_completed": True,
        "response_sink_parent_directory_mode": "0700",
        "response_sink_path_sha256": sha256_bytes(run["response_sink_path"].encode("utf-8")),
        "response_write_mode": "O_EXCL_SINGLE_FILE",
        "retry_count": 0,
        "review_byte_length": len(raw_response),
        "review_command_byte_length": len(command_raw),
        "review_command_schema_sha256": COMMAND_SCHEMA_SHA256,
        "review_command_sha256": sha256_bytes(command_raw),
        "review_instruction_sha256": review["review_instruction_sha256"],
        "review_receipt_schema_sha256": RECEIPT_SCHEMA_SHA256,
        "review_schema_sha256": REVIEW_SCHEMA_SHA256,
        "review_sha256": review_sha,
        "reviewer_conflict_and_overlap_manifest_sha256": conflict_manifest_sha256,
        "reviewer_roster_sha256": reviewer_roster_sha256,
        "reviewer_slot": review["reviewer_slot"],
        "schema": "agent_bridge.biocortex_ab_track_b_review_receipt.v0",
        "session_identity_sha256": sha256_object(run["session_identity"]),
        "started_at_utc": run["started_at_utc"],
        "stderr_byte_length": 0,
        "stderr_sha256": sha256_bytes(b""),
        "stdin_request_byte_length": len(request_raw),
        "stdin_request_sha256": sha256_bytes(request_raw),
        "tool_event_count": 0,
        "trial_id": review["trial_id"],
        "usage_record_sha256": sha256_object(run["usage_record"]),
        "working_directory_after_file_count": 0,
        "working_directory_after_manifest_sha256": workspace_sha,
        "working_directory_before_file_count": 0,
        "working_directory_before_manifest_sha256": workspace_sha,
        "working_directory_path_sha256": sha256_bytes(
            run["working_directory_path"].encode("utf-8")
        ),
        "writer_open_flags": "O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC",
    }


def validate_fixture_structure(
    fixture: Any,
    fixture_raw: bytes,
    identity: dict[str, Any],
    *,
    _expected_fixture_sha256: str = FIXTURE_SHA256,
) -> None:
    fixture = require_object(fixture, "synthetic fixture")
    require_exact_keys(
        fixture,
        {
            "boundary",
            "deterministic_truth_gates",
            "expected",
            "predecessor_identity_fixture",
            "receipt_runs",
            "reviewer_conflict_and_overlap_manifest",
            "schema",
            "second_review_overrides",
            "synthetic_only",
        },
        "synthetic fixture",
    )
    if sha256_bytes(fixture_raw) != _expected_fixture_sha256:
        fail("FIXTURE_HASH", "synthetic fixture byte hash drift")
    if fixture["schema"] != FIXTURE_SCHEMA or fixture["synthetic_only"] is not True:
        fail("FIXTURE_SCALAR", "synthetic fixture identity drift")
    if fixture["predecessor_identity_fixture"] != {
        "path": IDENTITY_FIXTURE_PATH,
        "sha256": IDENTITY_FIXTURE_SHA256,
    }:
        fail("FIXTURE_PREDECESSOR", "predecessor identity fixture binding drift")
    if fixture["boundary"] != {
        "authorizes_review_execution": False,
        "authorizes_scoring": False,
        "authorizes_unblinding": False,
        "live_binding_satisfied": False,
        "private_runtime_artifact_emitted": False,
        "real_run_admitted": False,
        "side_effects_unlocked": "NONE",
        "synthetic_only": True,
    }:
        fail("FIXTURE_BOUNDARY", "synthetic fixture boundary drift")
    if fixture["expected"] != {
        "blind_answer_case_count": 4,
        "case_count": 2,
        "receipt_count": 2,
        "reviewer_count": 2,
        "reviewer_evaluation_count": 8,
        "strict_fail_count": 2,
        "strict_pass_count": 2,
    }:
        fail("FIXTURE_EXPECTED", "synthetic expected metrics drift")
    runs = require_array(fixture["receipt_runs"], "fixture.receipt_runs")
    if len(runs) != 2:
        fail("FIXTURE_RUN_COUNT", "exactly two synthetic receipt runs are required")
    run_keys = {
        "command_created_at_utc",
        "completed_at_utc",
        "created_at_utc",
        "custodian_identity",
        "execution_environment",
        "execution_trace",
        "executor_profile",
        "invocation_nonce",
        "receipt_writer",
        "response_sink_id",
        "response_sink_path",
        "reviewer_slot",
        "session_identity",
        "started_at_utc",
        "stdin_request_utf8",
        "usage_record",
        "working_directory_manifest",
        "working_directory_path",
    }
    slots: list[str] = []
    sinks: list[str] = []
    for index, run in enumerate(runs):
        run = require_object(run, f"receipt run {index}")
        require_exact_keys(run, run_keys, f"receipt run {index}")
        slots.append(run["reviewer_slot"])
        sinks.append(run["response_sink_id"])
        command_created = require_utc(run["command_created_at_utc"], "command created")
        started = require_utc(run["started_at_utc"], "run started")
        completed = require_utc(run["completed_at_utc"], "run completed")
        receipt_created = require_utc(run["created_at_utc"], "receipt created")
        if not command_created < started <= completed < receipt_created:
            fail("FIXTURE_TIME_ORDER", "command < start <= complete < receipt is required")
        if run["working_directory_manifest"] != {
            "files": [],
            "schema": "agent_bridge.synthetic_empty_working_directory.v0",
        }:
            fail("FIXTURE_WORKSPACE", "synthetic workspace must remain empty")
        if run["execution_trace"].get("exit_code") != 0 or run["execution_trace"].get(
            "tool_events"
        ) != []:
            fail("FIXTURE_TRACE", "synthetic trace must have exit zero and no tool events")
        if run["receipt_writer"].get("open_flags") != (
            "O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC"
        ):
            fail("FIXTURE_WRITER", "synthetic writer flags drift")
        request_raw = run["stdin_request_utf8"].encode("utf-8")
        if not request_raw or len(request_raw) > 16 * 1024 * 1024:
            fail("FIXTURE_REQUEST", "synthetic request byte length is outside bounds")
    if len(set(slots)) != 2 or len(set(sinks)) != 2:
        fail("FIXTURE_RUN_IDENTITY", "reviewer slots and sinks must be distinct")
    truth_created = require_utc(identity["truth_manifest"]["created_at_utc"], "truth created")
    blind_created = require_utc(
        identity["map_bijection_request"]["blind_map"]["created_at_utc"], "blind map created"
    )
    if not truth_created < blind_created < require_utc(
        runs[0]["command_created_at_utc"], "first command created"
    ):
        fail("FIXTURE_TIME_ORDER", "truth < blind map < first command is required")
    conflict = require_object(
        fixture["reviewer_conflict_and_overlap_manifest"], "conflict manifest"
    )
    require_exact_keys(conflict, {"rows", "schema"}, "conflict manifest")
    if conflict["schema"] != "agent_bridge.synthetic_reviewer_conflict_manifest.v0":
        fail("FIXTURE_CONFLICT", "conflict manifest schema drift")
    conflict_rows = conflict["rows"]
    if [row.get("reviewer_slot") for row in conflict_rows] != slots or any(
        row != {"conflict_disclosed": True, "reviewer_slot": slot}
        for row, slot in zip(conflict_rows, slots)
    ):
        fail("FIXTURE_CONFLICT", "conflict manifest slot coverage drift")
    if type(identity.get("reviews")) is not list or len(identity["reviews"]) != 1:
        fail("FIXTURE_PREDECESSOR", "identity fixture must contain one predecessor review")
    apply_second_review_overrides(identity["reviews"][0], fixture)


def validate_chain(
    chain: dict[str, Any],
    schemas: dict[str, dict[str, Any]],
    blind_sha: str,
    reviewer_roster_sha256: str,
    conflict_manifest_sha256: str,
) -> None:
    run = chain["run"]
    review = chain["review"]
    command = chain["command"]
    receipt = chain["receipt"]
    command_raw = chain["command_raw"]
    review_raw = chain["review_raw"]
    raw_response = chain["raw_response"]
    receipt_raw = chain["receipt_raw"]
    if command_raw != canonical_pretty_bytes(command):
        fail("CHAIN_COMMAND_BYTES", "command bytes are not exact canonical command bytes")
    if review_raw != canonical_pretty_bytes(review):
        fail("CHAIN_REVIEW_BYTES", "review bytes are not exact canonical review bytes")
    if raw_response != review_raw:
        fail("CHAIN_RAW_RESPONSE", "response-sink bytes must exactly equal review bytes")
    if receipt_raw != canonical_pretty_bytes(receipt):
        fail("CHAIN_RECEIPT_BYTES", "receipt bytes are not exact canonical receipt bytes")
    if len(receipt_raw) > RESOURCE_CAPS["max_receipt_bytes"]:
        fail("CHAIN_RECEIPT_SIZE", "synthetic receipt exceeds byte cap")
    validate_instance(schemas["command"], command, "review command")
    validate_instance(schemas["review"], review, "review")
    validate_instance(schemas["receipt"], receipt, "review receipt")
    expected_command = build_command(run, review, blind_sha)
    if command != expected_command:
        fail("CHAIN_COMMAND_JOIN", "review command does not match run/review identity")
    expected_receipt = build_receipt(
        run,
        review,
        command_raw,
        raw_response,
        reviewer_roster_sha256,
        conflict_manifest_sha256,
    )
    if receipt != expected_receipt:
        fail("CHAIN_RECEIPT_JOIN", "receipt byte/hash/identity joins drift")
    command_created = require_utc(command["created_at_utc"], "command.created_at_utc")
    started = require_utc(receipt["started_at_utc"], "receipt.started_at_utc")
    completed = require_utc(receipt["completed_at_utc"], "receipt.completed_at_utc")
    receipt_created = require_utc(receipt["created_at_utc"], "receipt.created_at_utc")
    if not command_created < started <= completed < receipt_created:
        fail("CHAIN_TIME_ORDER", "command < start <= complete < receipt is required")


def build_and_validate_fixture(
    root: Path,
    fixture: dict[str, Any],
    fixture_raw: bytes,
    identity: dict[str, Any],
    schemas: dict[str, dict[str, Any]],
    strict_module: types.ModuleType,
) -> dict[str, Any]:
    validate_fixture_structure(fixture, fixture_raw, identity)
    truth = identity["truth_manifest"]
    first_review = copy.deepcopy(identity["reviews"][0])
    second_review = apply_second_review_overrides(first_review, fixture)
    first_review["reviewer_slot"] = fixture["receipt_runs"][0]["reviewer_slot"]
    reviews = [first_review, second_review]
    blind_packet = identity["map_bijection_request"]["blind_packet"]
    blind_sha = sha256_object(blind_packet)
    contract_sha = sha256_object(identity["map_bijection_request"]["contract"])
    truth_sha = sha256_object(truth)
    if blind_sha != reviews[0]["blind_packet_sha256"]:
        fail("FIXTURE_BLIND_HASH", "reviews do not bind exact blind packet object")
    if contract_sha != truth["contract_sha256"]:
        fail("FIXTURE_CONTRACT_HASH", "truth does not bind exact contract object")
    if truth_sha != reviews[0]["truth_manifest_sha256"]:
        fail("FIXTURE_TRUTH_HASH", "reviews do not bind exact truth object")
    for review in reviews:
        if review["blind_packet_sha256"] != blind_sha:
            fail("FIXTURE_REVIEW_IDENTITY", "review blind-packet hash divergence")
        if review["review_instruction_sha256"] != reviews[0]["review_instruction_sha256"]:
            fail("FIXTURE_REVIEW_IDENTITY", "review instruction hash divergence")

    roster = build_reviewer_roster(fixture)
    roster_sha = sha256_object(roster)
    conflict_sha = sha256_object(fixture["reviewer_conflict_and_overlap_manifest"])
    chains: list[dict[str, Any]] = []
    for run, review in zip(fixture["receipt_runs"], reviews):
        command = build_command(run, review, blind_sha)
        command_raw = canonical_pretty_bytes(command)
        review_raw = canonical_pretty_bytes(review)
        raw_response = review_raw
        receipt = build_receipt(
            run, review, command_raw, raw_response, roster_sha, conflict_sha
        )
        chain = {
            "command": command,
            "command_raw": command_raw,
            "raw_response": raw_response,
            "receipt": receipt,
            "receipt_raw": canonical_pretty_bytes(receipt),
            "review": review,
            "review_raw": review_raw,
            "run": run,
        }
        if any(
            len(raw) > RESOURCE_CAPS["max_single_artifact_bytes"]
            for raw in (command_raw, review_raw, raw_response)
        ):
            fail("FIXTURE_RESOURCE", "one synthetic chain artifact exceeds byte cap")
        validate_chain(chain, schemas, blind_sha, roster_sha, conflict_sha)
        chains.append(chain)

    strict_result = strict_module.evaluate_synthetic_objects(
        root,
        truth_manifest=truth,
        reviews=reviews,
        truth_gates=fixture["deterministic_truth_gates"],
    )
    rendered = strict_module.render_result(strict_result)
    swapped_result = strict_module.evaluate_synthetic_objects(
        root,
        truth_manifest=truth,
        reviews=list(reversed(reviews)),
        truth_gates=fixture["deterministic_truth_gates"],
    )
    swapped_rendered = strict_module.render_result(swapped_result)
    if swapped_rendered != rendered:
        fail("STRICT_REVIEW_ORDER", "strict renderer changes when review inputs are swapped")
    expected = fixture["expected"]
    actual = {
        "blind_answer_case_count": strict_result["answer_count"],
        "case_count": strict_result["case_count"],
        "receipt_count": len(chains),
        "reviewer_count": strict_result["reviewer_count"],
        "reviewer_evaluation_count": strict_result["reviewer_evaluation_count"],
        "strict_fail_count": strict_result["strict_fail_count"],
        "strict_pass_count": strict_result["strict_pass_count"],
    }
    if actual != expected:
        fail("FIXTURE_RESULT", f"strict synthetic metrics drift: {actual}")
    if strict_result["status"] != "VALIDATION_ONLY_NOT_SCORE_CLAIM":
        fail("STRICT_STATUS", "strict result authority boundary drift")
    if strict_result["input_mode"] != "synthetic_object" or strict_result[
        "synthetic_input"
    ] is not True:
        fail("STRICT_MODE", "strict result must identify synthetic object mode")
    if strict_result["algorithm_sha256"] != STRICT_ALGORITHM_SHA256:
        fail("STRICT_ALGORITHM_HASH", "strict result algorithm hash drift")
    reviewer_result_count = sum(len(row["reviewer_results"]) for row in strict_result["rows"])
    if reviewer_result_count != strict_result["reviewer_evaluation_count"] or reviewer_result_count != 8:
        fail("STRICT_REVIEWER_RESULT", "strict result must expose eight hashed-slot reviewer rows")
    if sum(line.startswith(b"reviewer_result\t") for line in rendered.splitlines()) != 8:
        fail("STRICT_REVIEWER_RESULT", "strict TSV must render eight reviewer_result rows")
    expected_slot_hashes = [
        strict_module.sha256_object(review["reviewer_slot"])
        for review in sorted(reviews, key=lambda value: value["reviewer_slot"])
    ]
    for row in strict_result["rows"]:
        observed = [reviewer["reviewer_slot_sha256"] for reviewer in row["reviewer_results"]]
        if observed != expected_slot_hashes or any(
            set(reviewer) != {
                "failure_rules",
                "reviewer_rule_pass",
                "reviewer_slot_sha256",
            }
            for reviewer in row["reviewer_results"]
        ):
            fail("STRICT_REVIEWER_RESULT", "hashed reviewer result identity/order drift")
    prohibited_keys = {
        "condition_id",
        "condition_key",
        "condition_map",
        "sampling_weight",
        "preferred_answer_id",
        "preference",
    }

    def keys(value: Any) -> set[str]:
        result: set[str] = set()
        if type(value) is dict:
            result.update(value)
            for child in value.values():
                result.update(keys(child))
        elif type(value) is list:
            for child in value:
                result.update(keys(child))
        return result

    if keys(strict_result) & prohibited_keys:
        fail("STRICT_PRIVATE_OUTPUT", "strict result exposes a prohibited mapping field")
    private_tokens = []
    for condition in identity["map_bijection_request"]["condition_roster"]["conditions"]:
        private_tokens.extend([condition["condition_id"], condition["condition_key"]])
    private_tokens.append(identity["map_bijection_request"]["answer_blinding_seed_hex"])
    private_tokens.extend(review["reviewer_slot"] for review in reviews)
    for token in private_tokens:
        if token.encode("utf-8") in rendered:
            fail("STRICT_PRIVATE_OUTPUT", "strict result exposes private condition/seed material")
    total_input_bytes = (
        len(fixture_raw)
        + sum(len(chain["command_raw"]) for chain in chains)
        + sum(len(chain["raw_response"]) for chain in chains)
        + sum(len(chain["receipt_raw"]) for chain in chains)
        + len(canonical_pretty_bytes(truth))
        + len(canonical_pretty_bytes(fixture["deterministic_truth_gates"]))
    )
    if total_input_bytes > RESOURCE_CAPS["max_total_input_bytes"]:
        fail("FIXTURE_RESOURCE", "synthetic total input exceeds byte cap")
    return {
        "chains": chains,
        "conflict_manifest_sha256": conflict_sha,
        "rendered_strict": rendered,
        "reviewer_roster": roster,
        "reviewer_roster_sha256": roster_sha,
        "reviews": reviews,
        "strict_result": strict_result,
        "review_order_invariant": True,
        "reviewer_result_count": reviewer_result_count,
        "total_input_bytes": total_input_bytes,
        "truth": truth,
    }


def load_inputs(root: Path) -> dict[str, Any]:
    manifest, manifest_raw = load_canonical(root, MANIFEST_PATH)
    fixture, fixture_raw = load_canonical(root, FIXTURE_PATH)
    identity, identity_raw = load_canonical(root, IDENTITY_FIXTURE_PATH)
    if sha256_bytes(identity_raw) != IDENTITY_FIXTURE_SHA256:
        fail("IDENTITY_FIXTURE_HASH", "predecessor identity fixture byte hash drift")
    graph, graph_raw = load_canonical(root, GRAPH_PATH)
    if sha256_bytes(graph_raw) != GRAPH_SHA256:
        fail("GRAPH_HASH", "dependency graph byte hash drift")
    schemas: dict[str, dict[str, Any]] = {}
    schema_raw: dict[str, bytes] = {}
    schema_metrics: dict[str, dict[str, int]] = {}
    for entry in SCHEMA_CATALOG:
        schema, raw = load_canonical(root, entry["path"], RESOURCE_CAPS["max_schema_bytes"])
        if sha256_bytes(raw) != entry["sha256"]:
            fail("SCHEMA_HASH", f"{entry['key']} schema byte hash drift")
        schema_metrics[entry["key"]] = validate_schema_document(schema, entry)
        schemas[entry["key"]] = schema
        schema_raw[entry["key"]] = raw
    strict_module = load_strict_module(root)
    validate_resource_alignment(schemas, strict_module)
    metrics = build_and_validate_fixture(
        root, fixture, fixture_raw, identity, schemas, strict_module
    )
    validate_manifest_value(root, manifest, fixture_raw, graph)
    return {
        "fixture": fixture,
        "fixture_raw": fixture_raw,
        "graph": graph,
        "identity": identity,
        "manifest": manifest,
        "manifest_raw": manifest_raw,
        "metrics": metrics,
        "schema_metrics": schema_metrics,
        "schema_raw": schema_raw,
        "schemas": schemas,
        "strict_module": strict_module,
    }


def receipt_rows(inputs: dict[str, Any]) -> list[tuple[str, Any]]:
    metrics = inputs["metrics"]
    strict = metrics["strict_result"]
    schema_metrics = inputs["schema_metrics"]
    rows: list[tuple[str, Any]] = [
        ("schema", PACK_SCHEMA),
        ("decision", DECISION),
        ("baseline_commit", BASELINE_COMMIT),
        ("manifest_sha256", sha256_bytes(inputs["manifest_raw"])),
        ("synthetic_fixture_sha256", sha256_bytes(inputs["fixture_raw"])),
        ("graph_sha256", GRAPH_SHA256),
        ("predecessor_identity_pack_sha256", IDENTITY_MANIFEST_SHA256),
        ("review_receipt_schema_sha256", RECEIPT_SCHEMA_SHA256),
        ("strict_case_algorithm_sha256", STRICT_ALGORITHM_SHA256),
        ("schema_count", len(SCHEMA_CATALOG)),
        ("schema_total_bytes", sum(len(raw) for raw in inputs["schema_raw"].values())),
        (
            "schema_node_count",
            sum(row["node_count"] for row in schema_metrics.values()),
        ),
        (
            "schema_object_count",
            sum(row["object_count"] for row in schema_metrics.values()),
        ),
        (
            "schema_local_ref_count",
            sum(row["local_ref_count"] for row in schema_metrics.values()),
        ),
        ("open_object_schema_count", 0),
        ("unbounded_schema_node_count", 0),
        ("synthetic_receipt_validation_status", "SCHEMA_VALIDATION_ONLY_NOT_CUSTODY_RECEIPT"),
        ("synthetic_receipt_count", len(metrics["chains"])),
        ("synthetic_command_count", len(metrics["chains"])),
        ("synthetic_raw_response_exact_review_count", len(metrics["chains"])),
        ("synthetic_reviewer_roster_sha256", metrics["reviewer_roster_sha256"]),
        ("synthetic_conflict_manifest_sha256", metrics["conflict_manifest_sha256"]),
        ("synthetic_total_input_bytes", metrics["total_input_bytes"]),
        ("strict_validation_status", strict["status"]),
        ("strict_input_mode", strict["input_mode"]),
        ("synthetic_case_count", strict["case_count"]),
        ("synthetic_blind_answer_case_count", strict["answer_count"]),
        ("synthetic_reviewer_count", strict["reviewer_count"]),
        ("synthetic_reviewer_evaluation_count", strict["reviewer_evaluation_count"]),
        ("synthetic_strict_pass_count", strict["strict_pass_count"]),
        ("synthetic_strict_fail_count", strict["strict_fail_count"]),
        ("synthetic_reviewer_result_count", metrics["reviewer_result_count"]),
        ("strict_review_input_order_invariant", metrics["review_order_invariant"]),
        ("strict_input_commitment_sha256", strict["input_commitment_sha256"]),
        ("strict_truth_gate_sha256", strict["truth_gate_sha256"]),
    ]
    for metric in sorted(strict["agreement"]):
        value = strict["agreement"][metric]
        rows.append((f"agreement_{metric}", f"{value['numerator']}/{value['denominator']}"))
    rows.extend(
        [
            ("agreement_used_for_gate", False),
            ("completed_public_binding_count", len(COMPLETED_PUBLIC_BINDINGS)),
            ("next_public_frontier_count", len(NEXT_PUBLIC_FRONTIER)),
            ("retained_stage_obligation_count", len(RETAINED_STAGE_OBLIGATIONS)),
            ("structural_blocker_count", len(STRUCTURAL_BLOCKERS)),
            ("source_artifact_count", 2),
            ("synthetic_receipt_is_custody_proof", False),
            ("review_instruction_bytes_verified", False),
            ("reviewer_roster_runtime_verified", False),
            ("deterministic_truth_gate_provenance_verified", False),
            ("o_excl_score_claim_created", False),
            ("runtime_instance_validated", False),
            ("live_binding_satisfied_count", 0),
            ("authority_true_count", 0),
            ("real_run_admitted", False),
            ("scoring_authorized", False),
            ("unblinding_authorized", False),
            ("side_effects_unlocked", "NONE"),
        ]
    )
    return rows


def render_receipt(inputs: dict[str, Any]) -> str:
    def scalar(value: Any) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)

    raw = "".join(f"{key}\t{scalar(value)}\n" for key, value in receipt_rows(inputs))
    if len(raw.encode("utf-8")) > RESOURCE_CAPS["max_output_bytes"]:
        fail("OUTPUT_SIZE", "checker output exceeds byte cap")
    return raw


def expect_rejection(
    name: str,
    callback: Callable[[], None],
    strict_error_type: type[BaseException] | None = None,
    *,
    expected_code: str | None = None,
) -> None:
    try:
        callback()
    except CheckError as exc:
        observed_code = exc.code
    except BaseException as exc:
        if strict_error_type is not None and isinstance(exc, strict_error_type):
            observed_code = getattr(exc, "code", None)
        else:
            raise
    else:
        fail("SELF_TEST_ACCEPTED", f"mutation {name} was accepted")
    if expected_code is not None and observed_code != expected_code:
        fail(
            "SELF_TEST_WRONG_CODE",
            f"mutation {name} expected {expected_code}, observed {observed_code}",
        )


def run_self_test(root: Path, inputs: dict[str, Any]) -> dict[str, int]:
    schemas = inputs["schemas"]
    metrics = inputs["metrics"]
    fixture = inputs["fixture"]
    identity = inputs["identity"]
    strict_module = inputs["strict_module"]
    strict_error = strict_module.StrictCaseError
    counts = {
        "command": 0,
        "exact_file_api": 0,
        "fixture": 0,
        "invariance": 0,
        "json": 0,
        "manifest": 0,
        "positive": 0,
        "receipt": 0,
        "schema": 0,
        "strict": 0,
    }

    json_mutations = (
        ("duplicate-key", b'{"a": 1, "a": 2}\n'),
        ("non-finite", b'{"a": NaN}\n'),
        ("bom", b'\xef\xbb\xbf{\n}\n'),
        ("compact", b'{"a":1}\n'),
        ("invalid-utf8", b'{"a":"\xff"}\n'),
    )
    for name, raw in json_mutations:
        expect_rejection(
            f"json-{name}", lambda raw=raw: parse_canonical_json(raw, f"json-{name}")
        )
        counts["json"] += 1

    receipt_schema_entry = SCHEMA_CATALOG[0]
    receipt_schema = schemas["receipt"]
    for field in sorted(receipt_schema["properties"]):
        trial = copy.deepcopy(receipt_schema)
        trial["required"].remove(field)
        expect_rejection(
            f"receipt-schema-unrequired-{field}",
            lambda trial=trial: validate_schema_document(trial, receipt_schema_entry),
        )
        counts["schema"] += 1

    base_chain = metrics["chains"][0]
    for field in sorted(base_chain["receipt"]):
        trial = copy.deepcopy(base_chain)
        trial["receipt"].pop(field)
        trial["receipt_raw"] = canonical_pretty_bytes(trial["receipt"])
        expect_rejection(
            f"receipt-missing-{field}",
            lambda trial=trial: validate_chain(
                trial,
                schemas,
                base_chain["review"]["blind_packet_sha256"],
                metrics["reviewer_roster_sha256"],
                metrics["conflict_manifest_sha256"],
            ),
        )
        counts["receipt"] += 1

    for field in sorted(base_chain["command"]):
        trial = copy.deepcopy(base_chain)
        trial["command"].pop(field)
        trial["command_raw"] = canonical_pretty_bytes(trial["command"])
        expect_rejection(
            f"command-missing-{field}",
            lambda trial=trial: validate_chain(
                trial,
                schemas,
                base_chain["review"]["blind_packet_sha256"],
                metrics["reviewer_roster_sha256"],
                metrics["conflict_manifest_sha256"],
            ),
        )
        counts["command"] += 1

    receipt_cross_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("review-command-hash", lambda x: x["receipt"].__setitem__("review_command_sha256", "0" * 64)),
        ("review-command-length", lambda x: x["receipt"].__setitem__("review_command_byte_length", 1)),
        ("request-hash", lambda x: x["receipt"].__setitem__("stdin_request_sha256", "0" * 64)),
        ("request-length", lambda x: x["receipt"].__setitem__("stdin_request_byte_length", 1)),
        ("raw-hash", lambda x: x["receipt"].__setitem__("raw_response_sha256", "0" * 64)),
        ("raw-length", lambda x: x["receipt"].__setitem__("raw_response_byte_length", 1)),
        ("review-hash", lambda x: x["receipt"].__setitem__("review_sha256", "0" * 64)),
        ("review-length", lambda x: x["receipt"].__setitem__("review_byte_length", 1)),
        ("instruction", lambda x: x["receipt"].__setitem__("review_instruction_sha256", "0" * 64)),
        ("review-receipt-schema", lambda x: x["receipt"].__setitem__("review_receipt_schema_sha256", "0" * 64)),
        ("roster", lambda x: x["receipt"].__setitem__("reviewer_roster_sha256", "0" * 64)),
        ("conflict", lambda x: x["receipt"].__setitem__("reviewer_conflict_and_overlap_manifest_sha256", "0" * 64)),
        ("slot", lambda x: x["receipt"].__setitem__("reviewer_slot", "reviewer_slot_drift")),
        ("contract", lambda x: x["receipt"].__setitem__("contract_sha256", "0" * 64)),
        ("blind", lambda x: x["receipt"].__setitem__("blind_packet_sha256", "0" * 64)),
        ("profile", lambda x: x["receipt"].__setitem__("executor_profile_sha256", "0" * 64)),
        ("workspace", lambda x: x["receipt"].__setitem__("working_directory_before_manifest_sha256", "0" * 64)),
        ("sink-path", lambda x: x["receipt"].__setitem__("response_sink_path_sha256", "0" * 64)),
        ("session", lambda x: x["receipt"].__setitem__("session_identity_sha256", "0" * 64)),
        ("usage", lambda x: x["receipt"].__setitem__("usage_record_sha256", "0" * 64)),
        ("nonce", lambda x: x["receipt"].__setitem__("invocation_nonce_sha256", "0" * 64)),
        ("completed-time", lambda x: x["receipt"].__setitem__("completed_at_utc", "2026-07-14T12:03:09Z")),
        ("created-time", lambda x: x["receipt"].__setitem__("created_at_utc", "2026-07-14T12:03:12Z")),
    ]
    for name, mutate in receipt_cross_mutations:
        trial = copy.deepcopy(base_chain)
        mutate(trial)
        trial["receipt_raw"] = canonical_pretty_bytes(trial["receipt"])
        expect_rejection(
            f"receipt-cross-{name}",
            lambda trial=trial: validate_chain(
                trial,
                schemas,
                base_chain["review"]["blind_packet_sha256"],
                metrics["reviewer_roster_sha256"],
                metrics["conflict_manifest_sha256"],
            ),
        )
        counts["receipt"] += 1

    raw_chain_mutations: list[tuple[str, str, bytes]] = [
        ("raw-response", "raw_response", b"{}\n"),
        ("review-bytes", "review_raw", b"{}\n"),
        ("receipt-bytes", "receipt_raw", b"{}\n"),
        ("command-bytes", "command_raw", b"{}\n"),
    ]
    for name, field, replacement in raw_chain_mutations:
        trial = copy.deepcopy(base_chain)
        trial[field] = replacement
        expect_rejection(
            f"chain-{name}",
            lambda trial=trial: validate_chain(
                trial,
                schemas,
                base_chain["review"]["blind_packet_sha256"],
                metrics["reviewer_roster_sha256"],
                metrics["conflict_manifest_sha256"],
            ),
        )
        counts["receipt" if field != "command_raw" else "command"] += 1

    swapped = strict_module.evaluate_synthetic_objects(
        root,
        truth_manifest=metrics["truth"],
        reviews=list(reversed(copy.deepcopy(metrics["reviews"]))),
        truth_gates=copy.deepcopy(fixture["deterministic_truth_gates"]),
    )
    if strict_module.render_result(swapped) != metrics["rendered_strict"]:
        fail("SELF_TEST_INVARIANCE", "review input order changed strict TSV bytes")
    counts["invariance"] += 1

    exact_truth_raw = canonical_pretty_bytes(metrics["truth"])
    exact_review_raws = [canonical_pretty_bytes(review) for review in metrics["reviews"]]
    exact_gate_raw = canonical_pretty_bytes(fixture["deterministic_truth_gates"])
    exact_result = strict_module.evaluate_artifact_bytes(
        root,
        truth_manifest_raw=exact_truth_raw,
        review_raws=exact_review_raws,
        truth_gate_raw=exact_gate_raw,
    )
    exact_swapped_result = strict_module.evaluate_artifact_bytes(
        root,
        truth_manifest_raw=exact_truth_raw,
        review_raws=list(reversed(exact_review_raws)),
        truth_gate_raw=exact_gate_raw,
    )
    exact_rendered = strict_module.render_result(exact_result)
    if (
        exact_result["input_mode"] != "exact_files"
        or exact_result["synthetic_input"] is not False
        or strict_module.render_result(exact_swapped_result) != exact_rendered
        or sum(
            line.startswith(b"reviewer_result\t")
            for line in exact_rendered.splitlines()
        )
        != 8
    ):
        fail("SELF_TEST_EXACT_FILE_API", "exact-files API boundary/order invariant drift")
    counts["exact_file_api"] += 1

    def strict_eval(
        reviews: list[dict[str, Any]], gates: dict[str, Any]
    ) -> dict[str, Any]:
        return strict_module.evaluate_synthetic_objects(
            root,
            truth_manifest=metrics["truth"],
            reviews=reviews,
            truth_gates=gates,
        )

    private_condition_id = identity["map_bijection_request"]["condition_roster"][
        "conditions"
    ][0]["condition_id"]

    def add_third_reviewer(
        reviews: list[dict[str, Any]], gates: dict[str, Any]
    ) -> None:
        del gates
        third = copy.deepcopy(reviews[1])
        third["reviewer_slot"] = "reviewer_slot_synthetic_3"
        reviews.append(third)

    def duplicate_truth_gate(
        reviews: list[dict[str, Any]], gates: dict[str, Any]
    ) -> None:
        del reviews
        gates["rows"][1]["case_id"] = gates["rows"][0]["case_id"]
        gates["rows"][1]["answer_id"] = gates["rows"][0]["answer_id"]

    invalid_strict: list[
        tuple[
            str,
            str,
            Callable[[list[dict[str, Any]], dict[str, Any]], None],
        ]
    ] = [
        ("reviewer-count-one", "REVIEWER_COUNT", lambda r, g: r.pop()),
        ("reviewer-count-three", "REVIEWER_COUNT", add_third_reviewer),
        (
            "duplicate-slot",
            "REVIEWER_DUPLICATE",
            lambda r, g: r[1].__setitem__("reviewer_slot", r[0]["reviewer_slot"]),
        ),
        (
            "review-trial",
            "REVIEW_IDENTITY",
            lambda r, g: r[1].__setitem__("trial_id", "trial_drift"),
        ),
        (
            "review-contract",
            "REVIEW_IDENTITY",
            lambda r, g: r[1].__setitem__("contract_sha256", "0" * 64),
        ),
        (
            "review-instruction",
            "REVIEW_IDENTITY_DIVERGENCE",
            lambda r, g: r[1].__setitem__("review_instruction_sha256", "0" * 64),
        ),
        ("review-case-order", "REVIEW_CASE_ORDER", lambda r, g: r[1]["cases"].reverse()),
        (
            "review-answer-order",
            "REVIEW_ANSWER_ORDER",
            lambda r, g: r[1]["cases"][0]["answers"].reverse(),
        ),
        (
            "review-claim-coverage",
            "REVIEW_CLAIM_COVERAGE",
            lambda r, g: r[1]["cases"][0]["answers"][0].__setitem__(
                "claim_scores", []
            ),
        ),
        (
            "review-abstention-table",
            "REVIEW_ABSTENTION_TRUTH_TABLE",
            lambda r, g: r[1]["cases"][1]["answers"][0].__setitem__(
                "abstention_assessment", "fail"
            ),
        ),
        (
            "forbidden-count-mismatch",
            "REVIEW_FORBIDDEN_COUNT",
            lambda r, g: r[1]["cases"][0]["answers"][0].__setitem__(
                "matched_forbidden_assertion_count", 1
            ),
        ),
        (
            "forbidden-unknown-handle",
            "REVIEW_FORBIDDEN_COVERAGE",
            lambda r, g: r[1]["cases"][0]["answers"][0].update(
                {
                    "matched_forbidden_assertion_count": 1,
                    "matched_forbidden_assertion_handles": [
                        "ast_33333333333333333333333333333333"
                    ],
                }
            ),
        ),
        ("truth-gate-order", "TRUTH_GATE_ORDER", lambda r, g: g["rows"].reverse()),
        ("truth-gate-coverage", "TRUTH_GATE_COVERAGE", lambda r, g: g["rows"].pop()),
        ("truth-gate-duplicate", "TRUTH_GATE_DUPLICATE", duplicate_truth_gate),
        (
            "truth-gate-identity",
            "TRUTH_GATE_IDENTITY",
            lambda r, g: g.__setitem__("contract_sha256", "0" * 64),
        ),
        (
            "truth-gate-boundary",
            "TRUTH_GATE_BOUNDARY",
            lambda r, g: g["boundary"].__setitem__(
                "source_provenance_verified_by_this_algorithm", True
            ),
        ),
        (
            "truth-gate-condition-map-boundary",
            "TRUTH_GATE_BOUNDARY",
            lambda r, g: g["boundary"].__setitem__("condition_mapping_present", True),
        ),
        (
            "truth-gate-extra",
            "EXACT_KEYS",
            lambda r, g: g["rows"][0].__setitem__("extra", True),
        ),
        (
            "truth-gate-map-leak",
            "EXACT_KEYS",
            lambda r, g: g.__setitem__(
                "condition_map", {"condition_id": private_condition_id}
            ),
        ),
        (
            "review-condition-id-leak",
            "INSTANCE_EXTRA",
            lambda r, g: r[1]["cases"][0]["answers"][0].__setitem__(
                "condition_id", private_condition_id
            ),
        ),
        (
            "review-weight-leak",
            "INSTANCE_EXTRA",
            lambda r, g: r[1]["cases"][0]["answers"][0]["claim_scores"][
                0
            ].__setitem__("weight", 1),
        ),
        (
            "review-preference-leak",
            "INSTANCE_EXTRA",
            lambda r, g: r[1]["cases"][0].__setitem__(
                "preferred_answer_id", private_condition_id
            ),
        ),
        (
            "observed-abstain-nonzero-score",
            "REVIEW_ABSTENTION_CLAIM_SCORE",
            lambda r, g: r[1]["cases"][0]["answers"][0].update(
                {"abstention_assessment": "fail", "response_mode": "abstain"}
            ),
        ),
        (
            "observed-abstain-unsupported-fact",
            "REVIEW_ABSTENTION_ASSERTIONS",
            lambda r, g: r[1]["cases"][0]["answers"][0].update(
                {
                    "abstention_assessment": "fail",
                    "claim_scores": [
                        {
                            "referent": copy.deepcopy(
                                r[1]["cases"][0]["answers"][0]["claim_scores"][0]["referent"]
                            ),
                            "score": 0,
                        }
                    ],
                    "response_mode": "abstain",
                    "unmatched_unsupported_assertion_count": 1,
                }
            ),
        ),
    ]
    for name, expected_code, mutate in invalid_strict:
        reviews = copy.deepcopy(metrics["reviews"])
        gates = copy.deepcopy(fixture["deterministic_truth_gates"])
        mutate(reviews, gates)
        expect_rejection(
            f"strict-{name}",
            lambda reviews=reviews, gates=gates: strict_eval(reviews, gates),
            strict_error,
            expected_code=expected_code,
        )
        counts["strict"] += 1

    original_total_input_cap = strict_module.MAX_TOTAL_INPUT_BYTES
    strict_module.MAX_TOTAL_INPUT_BYTES = 1
    try:
        expect_rejection(
            "strict-total-input-size-cap",
            lambda: strict_eval(
                copy.deepcopy(metrics["reviews"]),
                copy.deepcopy(fixture["deterministic_truth_gates"]),
            ),
            strict_error,
            expected_code="INPUT_SIZE",
        )
    finally:
        strict_module.MAX_TOTAL_INPUT_BYTES = original_total_input_cap
    counts["strict"] += 1

    def positive_control(
        name: str,
        mutate: Callable[[list[dict[str, Any]], dict[str, Any]], tuple[str, str]],
    ) -> None:
        reviews = copy.deepcopy(metrics["reviews"])
        gates = copy.deepcopy(fixture["deterministic_truth_gates"])
        target = mutate(reviews, gates)
        result = strict_eval(reviews, gates)
        row = next(
            row
            for row in result["rows"]
            if (row["case_id"], row["answer_id"]) == target
        )
        if row["strict_rule_pass"] is not False:
            fail("SELF_TEST_POSITIVE", f"valid failing control {name} did not fail strict")
        counts["positive"] += 1

    answer_key = (
        metrics["reviews"][0]["cases"][0]["case_id"],
        metrics["reviews"][0]["cases"][0]["answers"][0]["answer_id"],
    )
    abstain_key = (
        metrics["reviews"][0]["cases"][1]["case_id"],
        metrics["reviews"][0]["cases"][1]["answers"][0]["answer_id"],
    )

    def mutate_answer_field(field: str, value: Any) -> Callable[[list[dict[str, Any]], dict[str, Any]], tuple[str, str]]:
        def mutate(reviews: list[dict[str, Any]], gates: dict[str, Any]) -> tuple[str, str]:
            reviews[1]["cases"][0]["answers"][0][field] = copy.deepcopy(value)
            return answer_key
        return mutate

    positive_control(
        "claim-score-one",
        lambda r, g: (
            r[1]["cases"][0]["answers"][0]["claim_scores"][0].__setitem__("score", 1)
            or answer_key
        ),
    )
    positive_control("currentness-fail", mutate_answer_field("currentness", "fail"))
    positive_control("unsupported-one", mutate_answer_field("unmatched_unsupported_assertion_count", 1))
    positive_control("usefulness-three", mutate_answer_field("usefulness", 3))

    def forbidden_control(reviews: list[dict[str, Any]], gates: dict[str, Any]) -> tuple[str, str]:
        answer = reviews[1]["cases"][0]["answers"][0]
        answer["matched_forbidden_assertion_count"] = 1
        answer["matched_forbidden_assertion_handles"] = [
            metrics["truth"]["cases"][0]["claim_rubrics"][0]["forbidden_assertions"][0][
                "assertion_handle"
            ]
        ]
        return answer_key

    positive_control("forbidden-one", forbidden_control)

    def response_control(reviews: list[dict[str, Any]], gates: dict[str, Any]) -> tuple[str, str]:
        answer = reviews[1]["cases"][0]["answers"][0]
        answer["response_mode"] = "abstain"
        answer["abstention_assessment"] = "fail"
        for claim_score in answer["claim_scores"]:
            claim_score["score"] = 0
        return answer_key

    positive_control("answer-observed-abstain", response_control)

    for field, name in (
        ("authority_exists", "authority-false"),
        ("all_gold_recalled", "gold-false"),
        ("current_referent_correct", "current-referent-false"),
    ):
        def truth_control(
            reviews: list[dict[str, Any]],
            gates: dict[str, Any],
            field: str = field,
        ) -> tuple[str, str]:
            gates["rows"][0][field] = False
            return answer_key

        positive_control(name, truth_control)

    def abstention_response_control(
        reviews: list[dict[str, Any]], gates: dict[str, Any]
    ) -> tuple[str, str]:
        answer = reviews[1]["cases"][1]["answers"][0]
        answer["response_mode"] = "answer"
        answer["abstention_assessment"] = "fail"
        return abstain_key

    positive_control("abstention-observed-answer", abstention_response_control)

    fixture_mutations: list[
        tuple[str, str, Callable[[dict[str, Any]], None]]
    ] = [
        ("schema", "FIXTURE_SCALAR", lambda x: x.__setitem__("schema", "x")),
        (
            "synthetic",
            "FIXTURE_SCALAR",
            lambda x: x.__setitem__("synthetic_only", False),
        ),
        (
            "boundary",
            "FIXTURE_BOUNDARY",
            lambda x: x["boundary"].__setitem__("authorizes_scoring", True),
        ),
        (
            "expected",
            "FIXTURE_EXPECTED",
            lambda x: x["expected"].__setitem__("strict_pass_count", 3),
        ),
        (
            "predecessor",
            "FIXTURE_PREDECESSOR",
            lambda x: x["predecessor_identity_fixture"].__setitem__(
                "sha256", "0" * 64
            ),
        ),
        ("run-count", "FIXTURE_RUN_COUNT", lambda x: x["receipt_runs"].pop()),
        (
            "run-slot",
            "FIXTURE_RUN_IDENTITY",
            lambda x: x["receipt_runs"][1].__setitem__(
                "reviewer_slot", x["receipt_runs"][0]["reviewer_slot"]
            ),
        ),
        (
            "run-time",
            "FIXTURE_TIME_ORDER",
            lambda x: x["receipt_runs"][0].__setitem__(
                "created_at_utc", x["receipt_runs"][0]["started_at_utc"]
            ),
        ),
        (
            "workspace",
            "FIXTURE_WORKSPACE",
            lambda x: x["receipt_runs"][0]["working_directory_manifest"][
                "files"
            ].append("x"),
        ),
        (
            "trace",
            "FIXTURE_TRACE",
            lambda x: x["receipt_runs"][0]["execution_trace"][
                "tool_events"
            ].append("x"),
        ),
        (
            "conflict",
            "FIXTURE_CONFLICT",
            lambda x: x["reviewer_conflict_and_overlap_manifest"]["rows"][
                0
            ].__setitem__("conflict_disclosed", False),
        ),
        ("override", "FIXTURE_OVERRIDE", lambda x: x["second_review_overrides"].pop()),
    ]
    for name, expected_code, mutate in fixture_mutations:
        trial = copy.deepcopy(fixture)
        mutate(trial)
        raw = canonical_pretty_bytes(trial)
        expect_rejection(
            f"fixture-{name}",
            lambda trial=trial, raw=raw: validate_fixture_structure(
                trial,
                raw,
                identity,
                _expected_fixture_sha256=sha256_bytes(raw),
            ),
            expected_code=expected_code,
        )
        counts["fixture"] += 1

    manifest_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("baseline", lambda x: x.__setitem__("baseline_commit", "0" * 40)),
        ("schema", lambda x: x.__setitem__("schema", "x")),
        ("fixture", lambda x: x.__setitem__("synthetic_fixture_sha256", "0" * 64)),
        ("binding", lambda x: x["artifact_bindings"].reverse()),
        ("boundary", lambda x: x["boundary"].__setitem__("authority_true_count", 1)),
        ("completed", lambda x: x["completed_public_bindings"].pop()),
        ("evidence", lambda x: x["evidence_sha256"].__setitem__(GRAPH_PATH, "0" * 64)),
        ("frontier", lambda x: x["next_public_frontier"].pop()),
        ("resource", lambda x: x["resource_caps"].__setitem__("max_cases", 1)),
        ("obligation", lambda x: x["retained_stage_obligations"].pop()),
        ("semantics", lambda x: x["semantics"].__setitem__("preference_field_present", True)),
        ("blocker", lambda x: x["structural_blockers"].pop()),
    ]
    for name, mutate in manifest_mutations:
        trial = copy.deepcopy(inputs["manifest"])
        mutate(trial)
        expect_rejection(
            f"manifest-{name}",
            lambda trial=trial: validate_manifest_value(
                root, trial, inputs["fixture_raw"], inputs["graph"]
            ),
        )
        counts["manifest"] += 1

    total = sum(
        value
        for key, value in counts.items()
        if key not in {"exact_file_api", "invariance", "positive"}
    )
    if total < 100:
        fail("SELF_TEST_COUNT", f"only {total} rejected mutations were exercised")
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    inputs = load_inputs(root)
    if args.self_test:
        counts = run_self_test(root, inputs)
        total = sum(
            value
            for key, value in counts.items()
            if key not in {"exact_file_api", "invariance", "positive"}
        )
        print(
            "SELF_TEST_OK"
            f"\tjson_mutations_rejected={counts['json']}"
            f"\tschema_mutations_rejected={counts['schema']}"
            f"\treceipt_mutations_rejected={counts['receipt']}"
            f"\tcommand_mutations_rejected={counts['command']}"
            f"\tstrict_protocol_mutations_rejected={counts['strict']}"
            f"\tfixture_mutations_rejected={counts['fixture']}"
            f"\tmanifest_mutations_rejected={counts['manifest']}"
            f"\tvalid_failing_judgment_controls_accepted={counts['positive']}"
            f"\treview_order_invariance_controls_accepted={counts['invariance']}"
            f"\texact_file_api_controls_accepted={counts['exact_file_api']}"
            f"\ttotal_mutations_rejected={total}"
        )
        return 0
    print(render_receipt(inputs), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as exc:
        raise SystemExit(str(exc)) from None
