#!/usr/bin/env python3
"""Validate the source-only Track B identity-composition packet.

This checker is deliberately standard-library-only.  It validates two strict
JSON schemas, one deterministic map-bijection implementation, their synthetic
cross-artifact positive control, the immutable dependency graph, and a
detached source manifest.  A successful receipt never admits a real run or a
runtime instance.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import re
import types
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable


PACK_SCHEMA = "agent_bridge.biocortex_ab_track_b_identity_composition_pack.v0"
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_identity_composition_pack_synthetic.v0"
)
BASELINE_COMMIT = "c8e070de0de2abca764c5060b5fba91a64b6f189"
GRAPH_SOURCE_COMMIT = "ba4dbae629398ec16e4f22f4b0ac7f2ce372541f"
GRAPH_SHA256 = "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af"
FOUNDATIONAL_SOURCE_COMMIT = "d07180200345293f7d603d192eb55b3f7222379d"
FOUNDATIONAL_RECEIPT_SHA256 = (
    "f5470213cd8b1fe4d63455de12b6591675a88452203c4f01cff1fd89486d35fb"
)
CANONICAL_SERIALIZATION = (
    "UTF8_SORTED_KEYS_INDENT_2_LF_FINAL_NEWLINE_NO_NAN_DUPLICATE_KEYS_REJECTED"
)
DECISION = "SOURCE_IDENTITY_COMPOSITION_IMPLEMENTED_NOT_LIVE_BOUND"
DIALECT = "https://json-schema.org/draft/2020-12/schema"
MAP_VALIDATION_RESULT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_map_bijection_validation_result.v0"
)
MAP_VALIDATION_STATUS = "VALIDATION_ONLY_NOT_STAGE_RECEIPT"
MAP_VALIDATION_RESULT_FIELDS = (
    "answer_count",
    "authorizes_review_execution",
    "authorizes_scoring",
    "authorizes_unblinding",
    "blind_map_sha256",
    "blind_packet_sha256",
    "capture_sha256",
    "case_count",
    "checker_sha256",
    "condition_count",
    "condition_mapping_disclosed",
    "condition_roster_sha256",
    "contract_sha256",
    "eligible_frame_manifest_sha256",
    "generation_sha256",
    "identity_binding_count",
    "input_mode",
    "map_schema_sha256",
    "o_excl_receipt_verified",
    "raw_seed_disclosed",
    "request_sha256",
    "sampling_receipt_sha256",
    "sampling_schema_sha256",
    "schema",
    "seed_commitment_sha256",
    "selected_case_manifest_sha256",
    "stage_custody_verified",
    "status",
    "satisfies_post_generation_gate",
    "synthetic_input",
    "trial_id_sha256",
)

MANIFEST_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_identity_composition_pack_v0.json"
)
FIXTURE_PATH = (
    "scripts/eval/fixtures/"
    "biocortex_ab_track_b_identity_composition_pack_synthetic_v0.json"
)
GRAPH_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
)
MAP_CHECKER_PATH = "scripts/eval/biocortex_ab_track_b_map_bijection_v0.py"
REVIEW_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-review-schema-v0.json"
)
TRUTH_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-truth-manifest-schema-v0.json"
)
REFERENT_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-truth-referent-schema-v0.json"
)

MAP_CHECKER_SHA256 = "45f55cea933ee12df402fbb55d27ea7c6cd08ba8eef9d9868e4e491dd62a2cd2"
REVIEW_SCHEMA_SHA256 = "2745cd373d4f99cdd4bb3d0bc9d9087966adb3a9d0594749cb1150b90d1e9422"
TRUTH_SCHEMA_SHA256 = "520070d1eb4852fd2a005d63b3d087769b3240902289ff5c44f11c109bd1cde6"
REFERENT_SCHEMA_SHA256 = "5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8"
SYNTHETIC_SHA256 = "094a7343543be2a9b32fc996dc3e7006bc9d02f87f8cc9bdd269ef9fb61a341a"

SCHEMA_CATALOG = (
    {
        "artifact_kind": "review_object_schema",
        "binding_path": "review_and_blinding.review_schema_sha256",
        "key": "review",
        "local_dependencies": ["truth_inputs.referent_schema_sha256"],
        "path": REVIEW_SCHEMA_PATH,
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:review:v0",
        "instance_schema": "agent_bridge.biocortex_ab_track_b_review.v0",
        "sha256": REVIEW_SCHEMA_SHA256,
    },
    {
        "artifact_kind": "truth_authority_manifest_schema",
        "binding_path": "truth_inputs.truth_manifest_schema_sha256",
        "key": "truth",
        "local_dependencies": ["truth_inputs.referent_schema_sha256"],
        "path": TRUTH_SCHEMA_PATH,
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:truth-manifest:v0",
        "instance_schema": "agent_bridge.biocortex_ab_track_b_truth_manifest.v0",
        "sha256": TRUTH_SCHEMA_SHA256,
    },
)

ARTIFACT_BINDINGS = (
    {
        "artifact_kind": "blind_map_bijection_checker",
        "binding_path": "review_and_blinding.map_bijection_checker_sha256",
        "local_dependencies": [
            "review_and_blinding.map_schema_sha256",
            "sampling.sampling_receipt_schema_sha256",
        ],
        "provider_neutral": True,
        "repo_path": MAP_CHECKER_PATH,
        "schema_id": None,
        "sha256": MAP_CHECKER_SHA256,
        "source_status": "SOURCE_ARTIFACT_IMPLEMENTED_NOT_LIVE_BOUND",
        "unlocks_side_effect": False,
    },
    *(
        {
            "artifact_kind": entry["artifact_kind"],
            "binding_path": entry["binding_path"],
            "local_dependencies": entry["local_dependencies"],
            "provider_neutral": True,
            "repo_path": entry["path"],
            "schema_id": entry["schema_id"],
            "sha256": entry["sha256"],
            "source_status": "SOURCE_ARTIFACT_IMPLEMENTED_NOT_LIVE_BOUND",
            "unlocks_side_effect": False,
        }
        for entry in SCHEMA_CATALOG
    ),
)

COMPLETED_PUBLIC_BINDINGS = (
    "review_and_blinding.map_bijection_checker_sha256",
    "review_and_blinding.map_schema_sha256",
    "review_and_blinding.review_command_schema_sha256",
    "review_and_blinding.review_schema_sha256",
    "sampling.sampling_receipt_schema_sha256",
    "truth_inputs.referent_schema_sha256",
    "truth_inputs.truth_manifest_schema_sha256",
)
NEXT_PUBLIC_FRONTIER = (
    "reference_condition.context_builder_sha256",
    "review_and_blinding.review_receipt_schema_sha256",
    "sampling.sampling_seed_derivation_sha256",
    "sampling.sampling_selection_algorithm_sha256",
    "truth_inputs.strict_case_algorithm_sha256",
)
IDENTITY_BINDING_REQUIRED_FIELDS = (
    "trial_id",
    "contract_sha256",
    "sampling_receipt_sha256",
    "eligible_frame_manifest_sha256",
    "selected_case_manifest_sha256",
    "condition_roster_sha256",
    "capture_sha256",
    "generation_sha256",
    "blind_packet_sha256",
    "answer_blinding_seed_sha256",
)
STRUCTURAL_BLOCKERS = (
    "LIVE_LEDGER_HAS_NO_MAP_BIJECTION_RECEIPT_BINDING",
    "LIVE_LEDGER_HAS_NO_TRUTH_KNOWLEDGE_CUTOFF_SCALAR",
    "LIVE_LEDGER_HAS_NO_TRUTH_MANIFEST_CHECKER_BINDING",
    "S3_ADAPTER_REMAINS_FAIL_CLOSED",
    "SOURCE_ARTIFACTS_ARE_NOT_RUNTIME_INSTANCES",
)

RESOURCE_CAPS = {
    "max_answer_characters": 12000,
    "max_cases": 4096,
    "max_conditions": 64,
    "max_forbidden_assertions_per_case": 64,
    "max_forbidden_handles_per_answer": 64,
    "max_schema_bytes": 1048576,
    "max_single_artifact_bytes": 33554432,
    "max_total_answer_bytes": 16777216,
    "max_total_answers": 262144,
    "max_total_claim_scores": 1048576,
    "max_total_input_bytes": 67108864,
    "max_total_truth_assertions": 1048576,
}
SEMANTICS = {
    "abstention_assessment_truth_table": (
        "ANSWER_ANSWER_NOT_REQUIRED_ABSTAIN_ABSTAIN_PASS_MISMATCH_FAIL"
    ),
    "abstention_currentness": "PASS_FOR_CORRECT_NO_ASSERTION_ABSTENTION",
    "case_weight_application": "EXACTLY_ONCE_DOWNSTREAM",
    "claim_gate": "ALL_SCORE_RUBRICS_MUST_SCORE_2",
    "claim_weight_present": False,
    "forbidden_count_semantics": "MATCHED_UNIQUE_REGISTERED_ASSERTIONS",
    "map_checker_grain": "ONE_TRIAL_PRIVATE_MAP",
    "map_object_api_mode": "SYNTHETIC_ONLY_RAW_FILES_REQUIRE_TEN_EXACT_FILES",
    "map_validation_authority": "VALIDATION_ONLY_NOT_STAGE_RECEIPT",
    "preference_field_present": False,
    "review_grain": "ONE_TRIAL_X_REVIEWER_SLOT",
    "review_instruction_binding": "CROSS_REVIEW_EQUALITY_ONLY_NO_INSTRUCTION_BYTES",
    "structural_blocker_scope": "THIS_TRANCHE_LOCAL_NON_EXHAUSTIVE",
    "truth_manifest_grain": "ONE_TRIAL_PRIVATE_TRUTH_MANIFEST",
    "truth_root_digest_binding": "3_EXACTLY_RESOLVED_11_FORMAT_ONLY",
    "truth_time_order": "AS_OF_LE_CUTOFF_LE_CREATED_LT_FIRST_OUTPUT",
    "unsupported_count_semantics": "UNMATCHED_UNREGISTERED_ASSERTIONS_ONLY",
}
BOUNDARY = {
    "authority_true_count": 0,
    "graph_packet_mutated": False,
    "live_binding_satisfied_count": 0,
    "map_receipt_created": False,
    "private_runtime_artifact_emitted": False,
    "real_run_admitted": False,
    "runtime_instance_validated": False,
    "side_effects_unlocked": "NONE",
    "source_artifact_count": 3,
}

EXPECTED_EVIDENCE = {
    "crates/bridge/src/memory_truth.rs": (
        "2e46a521332820b07171b425c95004f35a98887c7c49a2d78baf7740f07195a4"
    ),
    "crates/bridge/src/memory_truth_adapter.rs": (
        "c459e96919778c24b0bc699653d8c12b83332e6318b7298deee071a01e90e023"
    ),
    "docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S2_2026_07_14.md": (
        "dd837929fdd1acf29be4c17ce06f3dacd4ae25f2bb13cf6ed190b84f65098f5b"
    ),
    REFERENT_SCHEMA_PATH: REFERENT_SCHEMA_SHA256,
    "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json": (
        "ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783"
    ),
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json": (
        "9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd"
    ),
    "docs/design/fixtures/biocortex-ab-track-b-review-command-schema-v0.json": (
        "40df0e39f36df01d414487c496cf09b5ffbed89cafc540dc89e6e57bea4466f5"
    ),
    GRAPH_PATH: GRAPH_SHA256,
    "scripts/eval/check_biocortex_ab_track_b_foundational_schema_pack.py": (
        "63f6192bfdc20083ce1770f67a4d053ace7d7ac253a8d538bbea38cabcc7bec9"
    ),
    "scripts/eval/fixtures/biocortex_ab_track_b_foundational_schema_pack_v0.json": (
        "fbfbf5738dd81e0afe8dbc45b1e91a35e92382a1913006a9b2e5ded67c077f36"
    ),
    "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json": (
        "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a"
    ),
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json": (
        "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e"
    ),
    "scripts/eval/portfolio_continuity_successor_v3_trial.py": (
        "0b92b1153a77257a49fc847eb37be3e20d687c41067559c22b2ebed72649e003"
    ),
    "scripts/eval/fixtures/portfolio_continuity_successor_v3_answer_contract.json": (
        "da9e190492d74824159bbff18eaeff02a4848921989f4077072f126e1d4e4bcc"
    ),
    "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_contract_v0.json": (
        "4dc7f459baa6de49755b79578c1ffdd6818c56d7f15916af72b024ef04c793da"
    ),
    "scripts/eval/fixtures/memory_temporal_evidence_adapter_s3_contract_v0.json": (
        "0efefdc38111bac5f344335be425dc6cf931fa509284833b959e326f7d2e8c2a"
    ),
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


def private_token_variants(raw: bytes) -> set[bytes]:
    """Return raw and frozen common lossless text encodings for a secret token."""

    standard = base64.b64encode(raw)
    urlsafe = base64.urlsafe_b64encode(raw)
    base32 = base64.b32encode(raw)
    hexadecimal = raw.hex().encode("ascii")
    hex_pairs = [f"{byte:02x}" for byte in raw]
    variants = {
        raw,
        raw.lower(),
        raw.upper(),
        hexadecimal,
        hexadecimal.upper(),
        ":".join(hex_pairs).encode("ascii"),
        ":".join(hex_pairs).upper().encode("ascii"),
        "-".join(hex_pairs).encode("ascii"),
        "-".join(hex_pairs).upper().encode("ascii"),
        " ".join(hex_pairs).encode("ascii"),
        " ".join(hex_pairs).upper().encode("ascii"),
        base32,
        base32.lower(),
        base32.rstrip(b"="),
        base32.rstrip(b"=").lower(),
        standard,
        standard.rstrip(b"="),
        urlsafe,
        urlsafe.rstrip(b"="),
    }
    return {variant for variant in variants if variant}


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
    try:
        size = path.stat().st_size
        cap = maximum if maximum is not None else RESOURCE_CAPS["max_single_artifact_bytes"]
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


def load_canonical(root: Path, relative: str, maximum: int | None = None) -> tuple[Any, bytes]:
    raw = read_bytes(root, relative, maximum)
    value = parse_canonical_json(raw, relative)
    return value, raw


def require_canonical_bytes(raw: bytes, value: Any, label: str) -> None:
    if raw != canonical_pretty_bytes(value):
        fail("JSON_CANONICAL", f"{label} is not canonical pretty JSON")


def parse_canonical_json(raw: bytes, label: str) -> Any:
    value = parse_json(raw, label)
    require_canonical_bytes(raw, value, label)
    return value


def require_object(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        fail("TYPE_OBJECT", f"{label} must be an object")
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
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        fail("UTC", f"{label} is not a real UTC instant: {exc}")
    return parsed


def collect_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if type(value) is dict:
        if "$ref" in value:
            refs.append(value["$ref"])
        for child in value.values():
            refs.extend(collect_refs(child))
    elif type(value) is list:
        for child in value:
            refs.extend(collect_refs(child))
    return refs


def validate_schema_document(schema: Any, entry: dict[str, Any]) -> dict[str, int]:
    schema = require_object(schema, f"{entry['key']} schema")
    if schema.get("$schema") != DIALECT:
        fail("SCHEMA_DIALECT", f"{entry['key']} dialect drift")
    if schema.get("$id") != entry["schema_id"]:
        fail("SCHEMA_ID", f"{entry['key']} id drift")
    definitions = require_object(schema.get("$defs"), f"{entry['key']}.$defs")
    if not definitions:
        fail("DEFS_EMPTY", f"{entry['key']} definitions are empty")
    for name in definitions:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) is None:
            fail("DEF_NAME", f"invalid definition name {name!r}")

    seen_refs: list[str] = []
    object_count = 0
    node_count = 0

    def walk(node: Any, path: str, *, root_node: bool = False) -> None:
        nonlocal object_count, node_count
        node_count += 1
        node = require_object(node, path)
        unknown = set(node) - ALLOWED_SCHEMA_KEYWORDS
        if unknown:
            fail("SCHEMA_KEYWORD", f"{path} has forbidden keywords {sorted(unknown)}")
        forms = int("$ref" in node) + int("const" in node) + int("type" in node)
        if forms != 1:
            fail("SCHEMA_FORM", f"{path} must be exactly one ref, const, or typed form")
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

        schema_type = node["type"]
        if type(schema_type) is not str or schema_type not in {
            "object",
            "array",
            "string",
            "integer",
        }:
            fail("SCHEMA_TYPE", f"{path} has unsupported type {schema_type!r}")
        allowed_for_type = {
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
        }[schema_type]
        if root_node:
            allowed_for_type |= {"$defs", "$id", "$schema", "description", "title"}
        irrelevant = set(node) - allowed_for_type
        if irrelevant:
            fail(
                "SCHEMA_GRAMMAR",
                f"{path} has keywords outside its {schema_type} grammar: "
                f"{sorted(irrelevant)}",
            )
        if schema_type == "object":
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
                or len(required) != len(set(required))
                or required != sorted(required)
            ):
                fail("OBJECT_REQUIRED", f"{path}.required must be sorted unique")
            if set(required) != set(properties):
                fail("OBJECT_REQUIRED", f"{path} must require every property")
            for key, child in properties.items():
                walk(child, f"{path}.properties.{key}")
        elif schema_type == "array":
            maximum = node.get("maxItems")
            minimum = node.get("minItems", 0)
            if (
                type(maximum) is not int
                or type(minimum) is not int
                or type(maximum) is bool
                or type(minimum) is bool
                or minimum < 0
                or maximum < minimum
            ):
                fail("ARRAY_BOUND", f"{path} has invalid finite array bounds")
            if type(node.get("uniqueItems")) is not bool:
                fail("ARRAY_UNIQUE", f"{path}.uniqueItems must be explicit Boolean")
            walk(node.get("items"), f"{path}.items")
        elif schema_type == "string":
            pattern = node.get("pattern")
            if type(pattern) is not str or not pattern.startswith("^") or not pattern.endswith("$"):
                fail("STRING_PATTERN", f"{path} requires an anchored ASCII pattern")
            try:
                re.compile(pattern, re.ASCII)
            except re.error as exc:
                fail("STRING_PATTERN", f"{path} pattern is invalid: {exc}")
            minimum = node.get("minLength")
            maximum = node.get("maxLength")
            if (
                type(minimum) is not int
                or type(maximum) is not int
                or type(minimum) is bool
                or type(maximum) is bool
                or minimum < 0
                or maximum < minimum
            ):
                fail("STRING_BOUND", f"{path} has invalid string bounds")
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
                fail("INTEGER_BOUND", f"{path} has invalid integer bounds")

    walk(schema, entry["key"], root_node=True)
    for name, definition in definitions.items():
        walk(definition, f"{entry['key']}.$defs.{name}")
    unused = set(definitions) - set(seen_refs)
    if unused:
        fail("DEF_UNUSED", f"{entry['key']} has unused definitions {sorted(unused)}")
    dependency_graph = {
        name: {ref.rsplit("/", 1)[1] for ref in collect_refs(definition)}
        for name, definition in definitions.items()
    }
    active: set[str] = set()
    complete: set[str] = set()

    def visit(name: str) -> None:
        if name in active:
            fail("REF_CYCLE", f"definition cycle at {name}")
        if name in complete:
            return
        active.add(name)
        for target in sorted(dependency_graph[name]):
            visit(target)
        active.remove(name)
        complete.add(name)

    for name in sorted(definitions):
        visit(name)
    if schema["properties"].get("schema") != {"const": entry["instance_schema"]}:
        fail("INSTANCE_DISCRIMINATOR", f"{entry['key']} discriminator drift")
    return {
        "node_count": node_count,
        "object_count": object_count,
        "ref_count": len(seen_refs),
    }


def validate_instance(schema: dict[str, Any], value: Any, path: str) -> None:
    definitions = schema["$defs"]

    def check(node: dict[str, Any], item: Any, item_path: str) -> None:
        if "$ref" in node:
            check(definitions[node["$ref"].rsplit("/", 1)[1]], item, item_path)
            return
        if "const" in node:
            expected = node["const"]
            if type(item) is not type(expected) or item != expected:
                fail("INSTANCE_CONST", f"{item_path} must equal {expected!r}")
            return
        schema_type = node["type"]
        if schema_type == "object":
            if type(item) is not dict:
                fail("INSTANCE_TYPE", f"{item_path} must be an object")
            missing = set(node["required"]) - set(item)
            if missing:
                fail("INSTANCE_REQUIRED", f"{item_path} missing {sorted(missing)}")
            extra = set(item) - set(node["properties"])
            if extra:
                fail("INSTANCE_EXTRA", f"{item_path} has extra {sorted(extra)}")
            for key in node["required"]:
                check(node["properties"][key], item[key], f"{item_path}.{key}")
        elif schema_type == "array":
            if type(item) is not list:
                fail("INSTANCE_TYPE", f"{item_path} must be an array")
            if not node.get("minItems", 0) <= len(item) <= node["maxItems"]:
                fail("INSTANCE_ARRAY_BOUND", f"{item_path} length is outside bounds")
            if node.get("uniqueItems"):
                identities = [canonical_compact_bytes(row) for row in item]
                if len(identities) != len(set(identities)):
                    fail("INSTANCE_UNIQUE", f"{item_path} has duplicate rows")
            for index, row in enumerate(item):
                check(node["items"], row, f"{item_path}[{index}]")
        elif schema_type == "string":
            if type(item) is not str:
                fail("INSTANCE_TYPE", f"{item_path} must be a string")
            if not node["minLength"] <= len(item) <= node["maxLength"]:
                fail("INSTANCE_STRING_BOUND", f"{item_path} length is outside bounds")
            if re.fullmatch(node["pattern"], item, re.ASCII) is None:
                fail("INSTANCE_PATTERN", f"{item_path} does not match its pattern")
        else:
            if type(item) is not int:
                fail("INSTANCE_TYPE", f"{item_path} must be an integer, not bool/float")
            if not node["minimum"] <= item <= node["maximum"]:
                fail("INSTANCE_INTEGER_BOUND", f"{item_path} is outside bounds")

    check(schema, value, path)


def load_map_module(root: Path) -> types.ModuleType:
    raw = read_bytes(root, MAP_CHECKER_PATH)
    if sha256_bytes(raw) != MAP_CHECKER_SHA256:
        fail("ARTIFACT_HASH", "map checker byte hash drift")
    module = types.ModuleType("biocortex_ab_track_b_map_bijection_v0_frozen")
    module.__file__ = str(resolve_path(root, MAP_CHECKER_PATH))
    try:
        code = compile(raw, module.__file__, "exec")
        exec(code, module.__dict__)
    except Exception as exc:
        fail("MAP_IMPORT", f"cannot load frozen map checker: {exc}")
    return module


def referent_tuple(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        row["claim_handle"],
        row["referent_handle"],
        row["predicate_handle"],
    )


def validate_truth_manifest(schema: dict[str, Any], value: Any) -> dict[str, Any]:
    validate_instance(schema, value, "truth_manifest")
    if value["referent_schema_sha256"] != REFERENT_SCHEMA_SHA256:
        fail("TRUTH_REFERENT_SCHEMA", "truth manifest referent schema hash drift")
    as_of = require_utc(value["truth_as_of_utc"], "truth_manifest.truth_as_of_utc")
    cutoff = require_utc(
        value["knowledge_cutoff_utc"], "truth_manifest.knowledge_cutoff_utc"
    )
    created = require_utc(value["created_at_utc"], "truth_manifest.created_at_utc")
    if not as_of <= cutoff <= created:
        fail("TRUTH_TIME_ORDER", "truth_as_of <= cutoff <= created is required")
    if len(value["cases"]) > RESOURCE_CAPS["max_cases"]:
        fail("TRUTH_RESOURCE", "truth case count exceeds the global cap")

    cases: list[str] = []
    case_results: dict[str, dict[str, Any]] = {}
    claim_to_pair: dict[str, tuple[str, str]] = {}
    pair_to_claim: dict[tuple[str, str], str] = {}
    required_assertions: set[str] = set()
    forbidden_assertions: set[str] = set()
    rubric_count = 0
    assertion_count = 0
    score_claim_count = 0
    for case_index, case in enumerate(value["cases"]):
        case_id = case["case_id"]
        if case_id in case_results:
            fail("TRUTH_CASE_DUPLICATE", f"duplicate truth case {case_id}")
        cases.append(case_id)
        score_referents: list[tuple[str, str, str]] = []
        case_forbidden: set[str] = set()
        case_required: set[str] = set()
        for rubric_index, rubric in enumerate(case["claim_rubrics"]):
            rubric_count += 1
            identity = referent_tuple(rubric["referent"])
            claim = identity[0]
            pair = (identity[1], identity[2])
            if claim in claim_to_pair:
                if claim_to_pair[claim] != pair:
                    fail("TRUTH_CLAIM_COLLISION", f"claim {claim} maps to two pairs")
                fail("TRUTH_CLAIM_DUPLICATE", f"claim {claim} is repeated")
            if pair in pair_to_claim:
                fail("TRUTH_PAIR_COLLISION", f"pair {pair} maps to two claims")
            claim_to_pair[claim] = pair
            pair_to_claim[pair] = claim
            local_required: set[str] = set()
            for assertion in rubric["required_assertions"]:
                handle = assertion["assertion_handle"]
                if handle in forbidden_assertions:
                    fail(
                        "TRUTH_ASSERTION_DISJOINT",
                        f"required assertion {handle} is already forbidden",
                    )
                if handle in required_assertions or handle in local_required:
                    fail("TRUTH_ASSERTION_DUPLICATE", f"required assertion {handle} repeats")
                local_required.add(handle)
            local_forbidden: set[str] = set()
            for assertion in rubric["forbidden_assertions"]:
                handle = assertion["assertion_handle"]
                if handle in required_assertions or handle in local_required:
                    fail(
                        "TRUTH_ASSERTION_DISJOINT",
                        f"forbidden assertion {handle} is already required",
                    )
                if handle in forbidden_assertions or handle in local_forbidden:
                    fail("TRUTH_ASSERTION_DUPLICATE", f"forbidden assertion {handle} repeats")
                local_forbidden.add(handle)
            required_assertions |= local_required
            forbidden_assertions |= local_forbidden
            case_required |= local_required
            case_forbidden |= local_forbidden
            assertion_count += len(local_required) + len(local_forbidden)
            if rubric["review_requirement"] == "score":
                score_claim_count += 1
                score_referents.append(identity)
                if not local_required:
                    fail("TRUTH_SCORE_ASSERTIONS", "score rubric needs a required assertion")
            elif local_required or not local_forbidden:
                fail(
                    "TRUTH_CONTEXT_ASSERTIONS",
                    "context_only rubric needs no required and at least one forbidden assertion",
                )
        if (
            len(case_forbidden)
            > RESOURCE_CAPS["max_forbidden_assertions_per_case"]
        ):
            fail("TRUTH_RESOURCE", "case forbidden-assertion count exceeds the cap")
        if case["expected_response_mode"] == "answer" and not score_referents:
            fail("TRUTH_RESPONSE_SEMANTICS", "answer case needs a score rubric")
        if case["expected_response_mode"] == "abstain" and score_referents:
            fail("TRUTH_RESPONSE_SEMANTICS", "abstain case cannot require scores")
        case_results[case_id] = {
            "expected_response_mode": case["expected_response_mode"],
            "score_referents": score_referents,
            "forbidden_assertions": case_forbidden,
            "required_assertions": case_required,
        }
    if assertion_count > RESOURCE_CAPS["max_total_truth_assertions"]:
        fail("TRUTH_RESOURCE", "truth assertion product exceeds global cap")
    if score_claim_count > RESOURCE_CAPS["max_total_claim_scores"]:
        fail("TRUTH_RESOURCE", "truth score-rubric product exceeds global cap")
    return {
        "trial_id": value["trial_id"],
        "created_at": created,
        "knowledge_cutoff": cutoff,
        "truth_as_of": as_of,
        "contract_sha256": value["contract_sha256"],
        "selected_case_manifest_sha256": value["selected_case_manifest_sha256"],
        "case_ids": cases,
        "cases": case_results,
        "claim_handles": set(claim_to_pair),
        "referent_handles": {pair[0] for pair in pair_to_claim},
        "predicate_handles": {pair[1] for pair in pair_to_claim},
        "assertion_handles": required_assertions | forbidden_assertions,
        "rubric_count": rubric_count,
        "assertion_count": assertion_count,
        "score_claim_count": score_claim_count,
    }


def validate_review_object(
    schema: dict[str, Any],
    value: Any,
    *,
    truth: dict[str, Any],
    truth_raw: bytes,
    map_request: dict[str, Any],
) -> dict[str, Any]:
    validate_instance(schema, value, "review")
    blind = map_request["blind_packet"]
    roster = map_request["condition_roster"]
    if value["trial_id"] != truth["trial_id"] or value["trial_id"] != blind["trial_id"]:
        fail("CROSS_TRIAL", "review trial identity differs")
    if (
        value["contract_sha256"] != truth["contract_sha256"]
        or value["contract_sha256"] != blind["contract_sha256"]
    ):
        fail("CROSS_CONTRACT", "review contract identity differs")
    if value["blind_packet_sha256"] != sha256_bytes(canonical_pretty_bytes(blind)):
        fail("CROSS_BLIND_PACKET", "review does not bind exact blind bytes")
    if value["truth_manifest_sha256"] != sha256_bytes(truth_raw):
        fail("CROSS_TRUTH_MANIFEST", "review does not bind exact truth manifest")
    if value["referent_schema_sha256"] != REFERENT_SCHEMA_SHA256:
        fail("CROSS_REFERENT_SCHEMA", "review referent schema binding drift")
    truth_cases = truth["cases"]
    blind_cases = blind["cases"]
    if len(value["cases"]) != len(truth_cases) or len(value["cases"]) != len(blind_cases):
        fail("REVIEW_CASE_COVERAGE", "review case count differs")
    review_case_ids = [case["case_id"] for case in value["cases"]]
    if len(review_case_ids) != len(set(review_case_ids)):
        fail("REVIEW_CASE_DUPLICATE", "review repeats a case identifier")

    packet_ids = {truth["trial_id"], *truth["case_ids"]}
    packet_ids |= truth["claim_handles"] | truth["referent_handles"]
    packet_ids |= truth["predicate_handles"] | truth["assertion_handles"]
    condition_ids = {row["condition_id"] for row in roster["conditions"]}
    condition_keys = {row["condition_key"] for row in roster["conditions"]}
    packet_ids |= condition_ids
    for case in blind_cases:
        packet_ids.update(answer["answer_id"] for answer in case["answers"])
    if value["reviewer_slot"] in packet_ids:
        fail("REVIEWER_COLLISION", "reviewer slot collides with a packet identifier")
    reviewer_slot_bytes = value["reviewer_slot"].encode("utf-8")
    private_tokens = condition_ids | condition_keys
    if any(
        variant in reviewer_slot_bytes
        for token in private_tokens
        for variant in private_token_variants(token.encode("utf-8"))
    ):
        fail("REVIEW_CONDITION_LEAK", "review material contains a private condition token")
    seed = bytes.fromhex(map_request["answer_blinding_seed_hex"])
    if any(
        variant in reviewer_slot_bytes for variant in private_token_variants(seed)
    ):
        fail("REVIEW_RAW_SEED_LEAK", "review material discloses the raw blinding seed")

    answer_count = 0
    claim_score_count = 0
    seen_answer_ids: set[str] = set()
    for index, (case, truth_case_id, blind_case) in enumerate(
        zip(value["cases"], truth["case_ids"], blind_cases, strict=True)
    ):
        if case["case_id"] != truth_case_id or case["case_id"] != blind_case["case_id"]:
            fail("REVIEW_CASE_ORDER", f"review case order differs at {index}")
        expected_answers = [row["answer_id"] for row in blind_case["answers"]]
        observed_answers = [row["answer_id"] for row in case["answers"]]
        if len(observed_answers) != len(set(observed_answers)) or any(
            answer_id in seen_answer_ids for answer_id in observed_answers
        ):
            fail("REVIEW_ANSWER_DUPLICATE", "review repeats an answer identifier")
        seen_answer_ids.update(observed_answers)
        if len(observed_answers) != len(expected_answers) or set(observed_answers) != set(expected_answers):
            fail("REVIEW_ANSWER_COVERAGE", "review answer set differs")
        if observed_answers != expected_answers:
            fail("REVIEW_ANSWER_ORDER", "review answer order differs")
        truth_case = truth["cases"][truth_case_id]
        expected_referents = truth_case["score_referents"]
        for answer in case["answers"]:
            answer_count += 1
            observed_referents = [referent_tuple(row["referent"]) for row in answer["claim_scores"]]
            if len(observed_referents) != len(set(observed_referents)):
                fail("REVIEW_CLAIM_DUPLICATE", "one answer scores a claim twice")
            if observed_referents != expected_referents:
                fail("REVIEW_CLAIM_COVERAGE", "review claim order/set differs")
            claim_score_count += len(observed_referents)
            forbidden_handles = answer["matched_forbidden_assertion_handles"]
            if len(forbidden_handles) != len(set(forbidden_handles)):
                fail("REVIEW_FORBIDDEN_DUPLICATE", "review repeats forbidden assertion")
            if (
                len(forbidden_handles)
                > RESOURCE_CAPS["max_forbidden_handles_per_answer"]
            ):
                fail("REVIEW_RESOURCE", "answer forbidden-handle count exceeds the cap")
            if not set(forbidden_handles).issubset(truth_case["forbidden_assertions"]):
                fail("REVIEW_FORBIDDEN_COVERAGE", "review names unknown forbidden assertion")
            if answer["matched_forbidden_assertion_count"] != len(forbidden_handles):
                fail("REVIEW_FORBIDDEN_COUNT", "review forbidden count differs from handles")
            expected_mode = truth_case["expected_response_mode"]
            observed_mode = answer["response_mode"]
            if observed_mode == "abstain":
                if any(row["score"] != 0 for row in answer["claim_scores"]):
                    fail(
                        "REVIEW_ABSTENTION_CLAIM_SCORE",
                        "observed abstention must score every required claim zero",
                    )
                if forbidden_handles or answer["unmatched_unsupported_assertion_count"]:
                    fail(
                        "REVIEW_ABSTENTION_ASSERTIONS",
                        "observed abstention cannot contain factual assertion violations",
                    )
            if expected_mode != observed_mode:
                expected_assessment = "fail"
            elif observed_mode == "answer":
                expected_assessment = "not_required"
            else:
                expected_assessment = "pass"
            if answer["abstention_assessment"] != expected_assessment:
                fail(
                    "REVIEW_ABSTENTION",
                    "assessment conflicts with expected x observed response truth table",
                )
            if (
                expected_mode == observed_mode == "abstain"
                and answer["currentness"] != "pass"
            ):
                fail(
                    "REVIEW_ABSTENTION_CURRENTNESS",
                    "correct no-assertion abstention has vacuous currentness pass",
                )
    expected_product = len(truth["case_ids"]) * len(roster["conditions"])
    if answer_count != expected_product:
        fail("REVIEW_CARTESIAN", "review does not cover the case-condition product")
    if answer_count > RESOURCE_CAPS["max_total_answers"]:
        fail("REVIEW_RESOURCE", "review answer product exceeds global cap")
    if claim_score_count > RESOURCE_CAPS["max_total_claim_scores"]:
        fail("REVIEW_RESOURCE", "review claim-score product exceeds global cap")
    return {
        "reviewer_slot": value["reviewer_slot"],
        "review_instruction_sha256": value["review_instruction_sha256"],
        "answer_count": answer_count,
        "claim_score_count": claim_score_count,
    }


def validate_map_validation_result(value: Any) -> None:
    result = require_object(value, "map validation result")
    require_exact_keys(
        result, set(MAP_VALIDATION_RESULT_FIELDS), "map validation result"
    )
    expected_boundary = {
        "authorizes_review_execution": False,
        "authorizes_scoring": False,
        "authorizes_unblinding": False,
        "condition_mapping_disclosed": False,
        "input_mode": "synthetic_fixture",
        "o_excl_receipt_verified": False,
        "raw_seed_disclosed": False,
        "satisfies_post_generation_gate": False,
        "schema": MAP_VALIDATION_RESULT_SCHEMA,
        "stage_custody_verified": False,
        "status": MAP_VALIDATION_STATUS,
        "synthetic_input": True,
    }
    for key, expected in expected_boundary.items():
        if result[key] != expected:
            fail("MAP_VALIDATION_BOUNDARY", f"map validation result {key} drift")
    if result["checker_sha256"] != MAP_CHECKER_SHA256:
        fail("MAP_VALIDATION_IDENTITY", "map result checker hash drift")
    if result["identity_binding_count"] != len(IDENTITY_BINDING_REQUIRED_FIELDS):
        fail("MAP_VALIDATION_IDENTITY", "map identity-binding count drift")


def validate_fixture_value(
    root: Path,
    fixture: Any,
    schemas: dict[str, dict[str, Any]],
    map_module: types.ModuleType,
) -> dict[str, Any]:
    fixture = require_object(fixture, "synthetic fixture")
    require_exact_keys(
        fixture,
        {
            "boundary",
            "expected",
            "map_bijection_request",
            "reviews",
            "schema",
            "synthetic_only",
            "truth_manifest",
        },
        "synthetic fixture",
    )
    if fixture["schema"] != FIXTURE_SCHEMA or fixture["synthetic_only"] is not True:
        fail("FIXTURE_IDENTITY", "synthetic fixture identity drift")
    if fixture["boundary"] != {
        "authority_asserted": False,
        "condition_mapping_real": False,
        "private_source_data_present": False,
        "real_run_authorized": False,
        "side_effects_unlocked": False,
        "synthetic_seed_only": True,
    }:
        fail("FIXTURE_BOUNDARY", "synthetic fixture boundary drift")
    if len(canonical_pretty_bytes(fixture)) > RESOURCE_CAPS["max_total_input_bytes"]:
        fail("FIXTURE_RESOURCE", "synthetic composition input exceeds its byte cap")
    request = require_object(fixture["map_bijection_request"], "map request")
    try:
        map_result = map_module.validate_request_object(
            root, request, input_mode="synthetic_fixture"
        )
    except map_module.BijectionError as exc:
        fail(f"MAP_{exc.code}", str(exc))
    validate_map_validation_result(map_result)

    case_count = map_result["case_count"]
    condition_count = map_result["condition_count"]
    answer_count = map_result["answer_count"]
    if case_count > RESOURCE_CAPS["max_cases"]:
        fail("FIXTURE_RESOURCE", "case count exceeds the composition cap")
    if condition_count > RESOURCE_CAPS["max_conditions"]:
        fail("FIXTURE_RESOURCE", "condition count exceeds the composition cap")
    if answer_count != case_count * condition_count:
        fail("MAP_CARTESIAN", "map answer count is not cases x conditions")
    if answer_count > RESOURCE_CAPS["max_total_answers"]:
        fail("FIXTURE_RESOURCE", "answer product exceeds the composition cap")

    generated_answers = [
        answer
        for case in request["generation_manifest"]["cases"]
        for answer in case["answers"]
    ]
    if len(generated_answers) != answer_count:
        fail("MAP_CARTESIAN", "generation answer count differs from the map product")
    total_answer_bytes = 0
    for answer in generated_answers:
        text = answer["answer_markdown"]
        if len(text) > RESOURCE_CAPS["max_answer_characters"]:
            fail("FIXTURE_RESOURCE", "one answer exceeds the character cap")
        total_answer_bytes += len(text.encode("utf-8"))
    if total_answer_bytes > RESOURCE_CAPS["max_total_answer_bytes"]:
        fail("FIXTURE_RESOURCE", "answer corpus exceeds the UTF-8 byte cap")

    private_condition_rows = request["condition_roster"]["conditions"]
    blind_packet_bytes = canonical_pretty_bytes(request["blind_packet"])
    for field, code in (
        ("condition_key", "BLIND_CONDITION_KEY_LEAK"),
        ("condition_id", "BLIND_CONDITION_ID_LEAK"),
    ):
        for row in private_condition_rows:
            token = row[field].encode("utf-8")
            if any(
                variant in blind_packet_bytes
                for variant in private_token_variants(token)
            ):
                fail(code, f"blind packet contains an exact private {field} token")
    seed = bytes.fromhex(request["answer_blinding_seed_hex"])
    if any(
        variant in blind_packet_bytes for variant in private_token_variants(seed)
    ):
        fail("BLIND_RAW_SEED_LEAK", "blind packet discloses the raw blinding seed")

    truth_value = fixture["truth_manifest"]
    truth_raw = canonical_pretty_bytes(truth_value)
    truth = validate_truth_manifest(schemas["truth"], truth_value)
    selected = request["selected_case_manifest"]
    blind = request["blind_packet"]
    if truth["trial_id"] != selected["trial_id"] or truth["trial_id"] != blind["trial_id"]:
        fail("CROSS_TRIAL", "truth and map artifacts have different trial identities")
    if (
        truth["contract_sha256"] != selected["contract_sha256"]
        or truth["contract_sha256"] != blind["contract_sha256"]
    ):
        fail("CROSS_CONTRACT", "truth and map artifacts bind different contracts")
    if truth["selected_case_manifest_sha256"] != sha256_bytes(
        canonical_pretty_bytes(selected)
    ):
        fail("CROSS_SELECTED", "truth manifest does not bind selected-case bytes")
    if truth["case_ids"] != [row["case_id"] for row in selected["cases"]]:
        fail("CROSS_CASE_ORDER", "truth and selected-case order differ")
    if truth["case_ids"] != [row["case_id"] for row in blind["cases"]]:
        fail("CROSS_CASE_ORDER", "truth and blind-packet case order differ")
    first_output = require_utc(
        request["generation_manifest"]["first_condition_output_at_utc"],
        "generation.first_condition_output_at_utc",
    )
    if not truth["created_at"] < first_output:
        fail(
            "TRUTH_OUTPUT_TIME_ORDER",
            "truth creation must strictly precede first condition output",
        )

    reviews = fixture["reviews"]
    if type(reviews) is not list or not 1 <= len(reviews) <= 64:
        fail("REVIEW_LIST", "synthetic reviews must be a bounded non-empty list")
    review_results: list[dict[str, Any]] = []
    reviewer_slots: set[str] = set()
    review_instruction_hashes: set[str] = set()
    for review in reviews:
        result = validate_review_object(
            schemas["review"],
            review,
            truth=truth,
            truth_raw=truth_raw,
            map_request=request,
        )
        if result["reviewer_slot"] in reviewer_slots:
            fail("REVIEWER_DUPLICATE", "synthetic reviews repeat a reviewer slot")
        reviewer_slots.add(result["reviewer_slot"])
        review_instruction_hashes.add(result["review_instruction_sha256"])
        if len(review_instruction_hashes) != 1:
            fail(
                "REVIEW_INSTRUCTION_DIVERGENCE",
                "one trial cannot mix reviewer instruction identities",
            )
        review_results.append(result)
    total_review_answers = sum(row["answer_count"] for row in review_results)
    total_review_claim_scores = sum(
        row["claim_score_count"] for row in review_results
    )
    if total_review_answers > RESOURCE_CAPS["max_total_answers"]:
        fail("REVIEW_RESOURCE", "all review answer rows exceed the global cap")
    if total_review_claim_scores > RESOURCE_CAPS["max_total_claim_scores"]:
        fail("REVIEW_RESOURCE", "all review claim scores exceed the global cap")
    metrics = {
        "answer_count": answer_count,
        "case_count": case_count,
        "claim_rubric_count": truth["rubric_count"],
        "condition_count": condition_count,
        "identity_binding_count": map_result["identity_binding_count"],
        "review_answer_count": total_review_answers,
        "review_object_count": len(review_results),
        "score_claim_count": truth["score_claim_count"],
        "truth_assertion_count": truth["assertion_count"],
    }
    if fixture["expected"] != metrics:
        fail("FIXTURE_EXPECTED", "synthetic expected metrics drift")
    return {
        **metrics,
        "map_validation_result": map_result,
        "review_claim_score_count": total_review_claim_scores,
        "total_answer_bytes": total_answer_bytes,
    }


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
            "foundational_receipt_sha256",
            "foundational_source_commit",
            "graph_sha256",
            "graph_source_commit",
            "identity_binding_required_fields",
            "next_public_frontier",
            "resource_caps",
            "schema",
            "semantics",
            "structural_blockers",
            "synthetic_fixture_path",
            "synthetic_fixture_sha256",
        },
        "pack manifest",
    )
    if manifest["synthetic_fixture_sha256"] != sha256_bytes(fixture_raw):
        fail("MANIFEST_FIXTURE_HASH", "manifest fixture hash does not bind bytes")
    scalar_expected = {
        "baseline_commit": BASELINE_COMMIT,
        "canonical_serialization": CANONICAL_SERIALIZATION,
        "date": "2026-07-14",
        "decision": DECISION,
        "foundational_receipt_sha256": FOUNDATIONAL_RECEIPT_SHA256,
        "foundational_source_commit": FOUNDATIONAL_SOURCE_COMMIT,
        "graph_sha256": GRAPH_SHA256,
        "graph_source_commit": GRAPH_SOURCE_COMMIT,
        "schema": PACK_SCHEMA,
        "synthetic_fixture_path": FIXTURE_PATH,
        "synthetic_fixture_sha256": SYNTHETIC_SHA256,
    }
    for key, expected in scalar_expected.items():
        if manifest[key] != expected:
            fail("MANIFEST_SCALAR", f"manifest {key} drift")
    exact_structures = {
        "artifact_bindings": list(ARTIFACT_BINDINGS),
        "boundary": BOUNDARY,
        "completed_public_bindings": list(COMPLETED_PUBLIC_BINDINGS),
        "evidence_sha256": EXPECTED_EVIDENCE,
        "identity_binding_required_fields": list(IDENTITY_BINDING_REQUIRED_FIELDS),
        "next_public_frontier": list(NEXT_PUBLIC_FRONTIER),
        "resource_caps": RESOURCE_CAPS,
        "semantics": SEMANTICS,
        "structural_blockers": list(STRUCTURAL_BLOCKERS),
    }
    for key, expected in exact_structures.items():
        if manifest[key] != expected:
            fail(f"MANIFEST_{key.upper()}", f"manifest {key} drift")
    for path, expected in EXPECTED_EVIDENCE.items():
        if sha256_bytes(read_bytes(root, path)) != expected:
            fail("EVIDENCE_HASH", f"evidence bytes drift: {path}")
    graph_nodes = {node["artifact_binding_path"]: node for node in graph["nodes"]}
    for binding in ARTIFACT_BINDINGS:
        node = graph_nodes.get(binding["binding_path"])
        if node is None:
            fail("GRAPH_COVERAGE", f"graph lacks {binding['binding_path']}")
        if (
            node["artifact_kind"] != binding["artifact_kind"]
            or node["local_dependencies"] != binding["local_dependencies"]
            or node["primary_readiness_class"] != "INDEPENDENT_PUBLIC"
            or node["public_authoring_eligible"] is not True
            or node["binding_satisfied"] is not False
            or node["binding_evidence"] is not None
        ):
            fail("GRAPH_TARGET", f"graph target drift: {binding['binding_path']}")
    frontier = derive_frontier(graph, set(COMPLETED_PUBLIC_BINDINGS))
    if frontier != NEXT_PUBLIC_FRONTIER:
        fail("GRAPH_FRONTIER", "derived five-node frontier drift")


def load_inputs(root: Path) -> dict[str, Any]:
    manifest, manifest_raw = load_canonical(root, MANIFEST_PATH)
    fixture, fixture_raw = load_canonical(root, FIXTURE_PATH)
    if sha256_bytes(fixture_raw) != SYNTHETIC_SHA256:
        fail("FIXTURE_HASH", "synthetic fixture byte hash drift")
    map_module = load_map_module(root)
    schemas: dict[str, dict[str, Any]] = {}
    schema_raw: dict[str, bytes] = {}
    schema_metrics: dict[str, dict[str, int]] = {}
    for entry in SCHEMA_CATALOG:
        schema, raw = load_canonical(root, entry["path"], RESOURCE_CAPS["max_schema_bytes"])
        if sha256_bytes(raw) != entry["sha256"]:
            fail("ARTIFACT_HASH", f"{entry['key']} schema byte hash drift")
        schema_metrics[entry["key"]] = validate_schema_document(schema, entry)
        schemas[entry["key"]] = schema
        schema_raw[entry["key"]] = raw
    referent, referent_raw = load_canonical(root, REFERENT_SCHEMA_PATH)
    if sha256_bytes(referent_raw) != REFERENT_SCHEMA_SHA256:
        fail("EVIDENCE_HASH", "referent schema bytes drift")
    expected_referent = {
        "additionalProperties": False,
        "properties": referent["properties"],
        "required": referent["required"],
        "type": "object",
        "unevaluatedProperties": False,
    }
    for key in ("review", "truth"):
        if schemas[key]["$defs"]["referent"] != expected_referent:
            fail("REFERENT_PRIMITIVE_DRIFT", f"{key} referent definition drift")
        for primitive in ("claimHandle", "predicateHandle", "referentHandle"):
            if schemas[key]["$defs"][primitive] != referent["$defs"][primitive]:
                fail("REFERENT_PRIMITIVE_DRIFT", f"{key}.{primitive} drift")
    graph, graph_raw = load_canonical(root, GRAPH_PATH)
    if sha256_bytes(graph_raw) != GRAPH_SHA256:
        fail("GRAPH_HASH", "graph byte hash drift")
    fixture_metrics = validate_fixture_value(root, fixture, schemas, map_module)
    validate_manifest_value(root, manifest, fixture_raw, graph)
    return {
        "fixture": fixture,
        "fixture_raw": fixture_raw,
        "fixture_metrics": fixture_metrics,
        "graph": graph,
        "manifest": manifest,
        "manifest_raw": manifest_raw,
        "map_module": map_module,
        "schema_metrics": schema_metrics,
        "schema_raw": schema_raw,
        "schemas": schemas,
    }


def receipt_rows(inputs: dict[str, Any]) -> list[tuple[str, Any]]:
    metrics = inputs["fixture_metrics"]
    schema_metrics = inputs["schema_metrics"]
    map_result = metrics["map_validation_result"]
    return [
        ("schema", PACK_SCHEMA),
        ("baseline_commit", BASELINE_COMMIT),
        ("manifest_sha256", sha256_bytes(inputs["manifest_raw"])),
        ("synthetic_fixture_sha256", sha256_bytes(inputs["fixture_raw"])),
        (
            "artifact_catalog_sha256",
            sha256_bytes(canonical_compact_bytes(list(ARTIFACT_BINDINGS))),
        ),
        (
            "evidence_catalog_sha256",
            sha256_bytes(canonical_compact_bytes(EXPECTED_EVIDENCE)),
        ),
        ("graph_sha256", GRAPH_SHA256),
        ("foundational_receipt_sha256", FOUNDATIONAL_RECEIPT_SHA256),
        ("map_bijection_checker_sha256", MAP_CHECKER_SHA256),
        ("review_schema_sha256", REVIEW_SCHEMA_SHA256),
        ("truth_manifest_schema_sha256", TRUTH_SCHEMA_SHA256),
        ("schema_count", 2),
        (
            "schema_total_bytes",
            sum(len(raw) for raw in inputs["schema_raw"].values()),
        ),
        (
            "schema_node_count",
            sum(row["node_count"] for row in schema_metrics.values()),
        ),
        (
            "schema_object_count",
            sum(row["object_count"] for row in schema_metrics.values()),
        ),
        (
            "local_ref_count",
            sum(row["ref_count"] for row in schema_metrics.values()),
        ),
        ("no_op_schema_node_count", 0),
        ("open_object_schema_count", 0),
        ("positive_schema_class_count", 2),
        ("positive_map_validation_status", map_result["status"]),
        ("positive_map_input_mode", map_result["input_mode"]),
        ("positive_map_request_sha256", map_result["request_sha256"]),
        ("positive_map_authorizes_review_execution", False),
        ("positive_map_satisfies_post_generation_gate", False),
        ("synthetic_case_count", metrics["case_count"]),
        ("synthetic_condition_count", metrics["condition_count"]),
        ("synthetic_answer_count", metrics["answer_count"]),
        ("synthetic_claim_rubric_count", metrics["claim_rubric_count"]),
        ("synthetic_truth_assertion_count", metrics["truth_assertion_count"]),
        ("synthetic_review_object_count", metrics["review_object_count"]),
        ("synthetic_review_answer_count", metrics["review_answer_count"]),
        ("synthetic_review_claim_score_count", metrics["review_claim_score_count"]),
        ("synthetic_answer_utf8_bytes", metrics["total_answer_bytes"]),
        ("synthetic_condition_key_leak_count", 0),
        ("identity_binding_count", metrics["identity_binding_count"]),
        ("completed_public_binding_count", len(COMPLETED_PUBLIC_BINDINGS)),
        ("next_public_frontier_count", len(NEXT_PUBLIC_FRONTIER)),
        ("structural_blocker_count", len(STRUCTURAL_BLOCKERS)),
        ("source_artifact_count", 3),
        ("runtime_instance_validated", False),
        ("live_binding_satisfied_count", 0),
        ("authority_true_count", 0),
        ("real_run_admitted", False),
        ("side_effects_unlocked", "NONE"),
        ("decision", DECISION),
    ]


def render_receipt(inputs: dict[str, Any]) -> str:
    def scalar(value: Any) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        return str(value)

    return "".join(f"{key}\t{scalar(value)}\n" for key, value in receipt_rows(inputs))


def expect_rejection(
    name: str,
    expected_code: str,
    callback: Callable[[], None],
    map_error_type: type[BaseException] | None = None,
) -> None:
    try:
        callback()
    except CheckError as exc:
        code = exc.code
    except BaseException as exc:
        if map_error_type is not None and isinstance(exc, map_error_type):
            code = getattr(exc, "code", "")
        else:
            raise
    else:
        fail("SELF_TEST_ACCEPTED", f"mutation {name} was accepted")
    if code != expected_code:
        fail(
            "SELF_TEST_WRONG_CODE",
            f"{name} expected {expected_code}, observed {code}",
        )


def run_self_test(root: Path, inputs: dict[str, Any]) -> dict[str, int]:
    """Run exact-code adversarial mutations after the positive control passed."""

    counts = {
        "fixture": 0,
        "json": 0,
        "map": 0,
        "positive": 0,
        "schema": 0,
        "source": 0,
    }
    schemas = inputs["schemas"]
    fixture = inputs["fixture"]
    map_module = inputs["map_module"]

    def json_case(name: str, code: str, raw: bytes) -> None:
        expect_rejection(name, code, lambda: parse_json(raw, name))
        counts["json"] += 1

    json_case("duplicate-key", "JSON_DUPLICATE_KEY", b'{"a":1,"a":2}\n')
    json_case("nan", "JSON_CONSTANT", b'{"a":NaN}\n')
    json_case("infinity", "JSON_CONSTANT", b'{"a":Infinity}\n')
    json_case("negative-infinity", "JSON_CONSTANT", b'{"a":-Infinity}\n')
    json_case("bom", "JSON_BOM", b'\xef\xbb\xbf{}\n')
    json_case("invalid-utf8", "JSON_UTF8", b'{"a":"\xff"}\n')
    json_case("malformed", "JSON_PARSE", b'{]\n')
    expect_rejection(
        "noncanonical",
        "JSON_CANONICAL",
        lambda: parse_canonical_json(b'{"z":1, "a":2}\n', "noncanonical"),
    )
    counts["json"] += 1

    def schema_case(
        name: str,
        key: str,
        code: str,
        mutate: Callable[[dict[str, Any]], None],
    ) -> None:
        trial = copy.deepcopy(schemas[key])
        mutate(trial)
        entry = next(row for row in SCHEMA_CATALOG if row["key"] == key)
        expect_rejection(name, code, lambda: validate_schema_document(trial, entry))
        counts["schema"] += 1

    schema_case("schema-dialect", "review", "SCHEMA_DIALECT", lambda x: x.__setitem__("$schema", "x"))
    schema_case("schema-id", "review", "SCHEMA_ID", lambda x: x.__setitem__("$id", "urn:x"))
    schema_case("schema-noop", "review", "SCHEMA_FORM", lambda x: x["$defs"].__setitem__("claimHandle", {}))
    schema_case("schema-missing-type", "review", "SCHEMA_FORM", lambda x: x["$defs"]["boundary"].pop("type"))
    schema_case("schema-type-container", "review", "SCHEMA_TYPE", lambda x: x["$defs"]["boundary"].__setitem__("type", []))
    schema_case("schema-two-forms", "review", "SCHEMA_FORM", lambda x: x["properties"]["schema"].__setitem__("type", "string"))
    schema_case("schema-ref-sibling", "review", "REF_SIBLING", lambda x: x["properties"]["trial_id"].__setitem__("description", "x"))
    for suffix, ref in (
        ("remote", "https://example.invalid/x"),
        ("file", "file:///tmp/x"),
        ("relative", "../x#/$defs/label"),
        ("encoded", "#/%24defs/label"),
    ):
        schema_case(
            f"schema-ref-{suffix}",
            "review",
            "REF_POLICY",
            lambda x, ref=ref: x["properties"].__setitem__("trial_id", {"$ref": ref}),
        )
    schema_case("schema-unresolved", "review", "REF_UNRESOLVED", lambda x: x["properties"].__setitem__("trial_id", {"$ref": "#/$defs/Missing"}))
    schema_case("schema-keyword", "review", "SCHEMA_KEYWORD", lambda x: x.__setitem__("allOf", []))
    schema_case("schema-open-additional", "review", "OBJECT_OPEN", lambda x: x.__setitem__("additionalProperties", True))
    schema_case("schema-open-unevaluated", "review", "OBJECT_OPEN", lambda x: x.pop("unevaluatedProperties"))
    schema_case("schema-required-order", "review", "OBJECT_REQUIRED", lambda x: x["required"].reverse())
    schema_case("schema-required-missing", "review", "OBJECT_REQUIRED", lambda x: x["required"].pop())
    schema_case("schema-required-nonstring", "review", "OBJECT_REQUIRED", lambda x: x["required"].__setitem__(0, 1))
    schema_case("schema-required-unhashable", "review", "OBJECT_REQUIRED", lambda x: x["required"].__setitem__(0, {}))
    schema_case("schema-array-max", "review", "ARRAY_BOUND", lambda x: x["properties"]["cases"].pop("maxItems"))
    schema_case("schema-array-range", "review", "ARRAY_BOUND", lambda x: x["properties"]["cases"].update({"minItems": 2, "maxItems": 1}))
    schema_case("schema-array-unique", "review", "ARRAY_UNIQUE", lambda x: x["properties"]["cases"].__setitem__("uniqueItems", "true"))
    schema_case("schema-array-unique-missing", "review", "ARRAY_UNIQUE", lambda x: x["properties"]["cases"].pop("uniqueItems"))
    schema_case("schema-string-pattern", "review", "STRING_PATTERN", lambda x: x["$defs"]["label"].pop("pattern"))
    schema_case("schema-string-anchor", "review", "STRING_PATTERN", lambda x: x["$defs"]["label"].__setitem__("pattern", ".*"))
    schema_case("schema-string-bound", "review", "STRING_BOUND", lambda x: x["$defs"]["label"].update({"minLength": 2, "maxLength": 1}))
    schema_case("schema-int-bound", "review", "INTEGER_BOUND", lambda x: x["$defs"]["answerReview"]["properties"]["usefulness"].__setitem__("minimum", True))
    schema_case("schema-typed-keyword", "review", "SCHEMA_GRAMMAR", lambda x: x["$defs"]["label"].__setitem__("maxItems", 1))
    schema_case("schema-nested-defs", "review", "SCHEMA_GRAMMAR", lambda x: x["$defs"]["boundary"].__setitem__("$defs", {}))
    schema_case("schema-const-sibling", "review", "CONST_SIBLING", lambda x: x["properties"]["schema"].__setitem__("description", "x"))
    schema_case("schema-const-value", "review", "SCHEMA_CONST", lambda x: x["properties"]["schema"].__setitem__("const", None))
    schema_case("schema-unused", "review", "DEF_UNUSED", lambda x: x["$defs"].__setitem__("Unused", {"const": "x"}))
    schema_case("schema-cycle", "review", "REF_CYCLE", lambda x: x["$defs"].__setitem__("claimHandle", {"$ref": "#/$defs/claimHandle"}))

    request0 = fixture["map_bijection_request"]

    def rebind_sampling(value: dict[str, Any]) -> None:
        value["blind_map"]["sampling_receipt_sha256"] = sha256_bytes(
            canonical_pretty_bytes(value["sampling_receipt"])
        )

    def mutate_sampling_eligible(value: dict[str, Any]) -> None:
        value["sampling_receipt"]["eligible_frame_manifest_sha256"] = "0" * 64
        rebind_sampling(value)

    def mutate_sampling_selected(value: dict[str, Any]) -> None:
        value["sampling_receipt"]["selected_case_manifest_sha256"] = "0" * 64
        rebind_sampling(value)

    def rebind_blind_packet(value: dict[str, Any]) -> None:
        value["blind_map"]["blind_packet_sha256"] = sha256_bytes(
            canonical_pretty_bytes(value["blind_packet"])
        )

    def mutate_generation_capture(value: dict[str, Any]) -> None:
        value["generation_manifest"]["capture_sha256"] = "0" * 64
        generation_sha = sha256_bytes(
            canonical_pretty_bytes(value["generation_manifest"])
        )
        value["blind_map"]["generation_sha256"] = generation_sha
        value["blind_packet"]["generation_sha256"] = generation_sha
        rebind_blind_packet(value)

    def mutate_blind_capture(value: dict[str, Any]) -> None:
        value["blind_packet"]["capture_sha256"] = "0" * 64
        rebind_blind_packet(value)

    def mutate_blind_generation(value: dict[str, Any]) -> None:
        value["blind_packet"]["generation_sha256"] = "0" * 64
        rebind_blind_packet(value)

    def map_case(
        name: str,
        code: str,
        mutate: Callable[[dict[str, Any]], None],
    ) -> None:
        trial = copy.deepcopy(request0)
        mutate(trial)
        expect_rejection(
            name,
            code,
            lambda: map_module.validate_request_object(root, trial),
            map_module.BijectionError,
        )
        counts["map"] += 1

    map_case("map-request-schema", "REQUEST_SCHEMA", lambda x: x.__setitem__("schema", "x"))
    map_case("map-seed-format", "STRING_PATTERN", lambda x: x.__setitem__("answer_blinding_seed_hex", "00"))
    map_case("map-boundary", "MAP_BOUNDARY", lambda x: x["blind_map"]["boundary"].__setitem__("unblinding_allowed", True))
    map_case("map-case-duplicate", "MAP_CASE_DUPLICATE", lambda x: x["blind_map"]["cases"][1].__setitem__("case_id", x["blind_map"]["cases"][0]["case_id"]))
    map_case("map-answer-duplicate", "MAP_ANSWER_DUPLICATE", lambda x: x["blind_map"]["cases"][1]["assignments"][0].__setitem__("answer_id", x["blind_map"]["cases"][0]["assignments"][0]["answer_id"]))
    map_case("map-condition-duplicate", "MAP_CONDITION_DUPLICATE", lambda x: x["blind_map"]["cases"][0]["assignments"][1].__setitem__("condition_id", x["blind_map"]["cases"][0]["assignments"][0]["condition_id"]))
    map_case("map-condition-set", "MAP_CONDITION_SET", lambda x: x["blind_map"]["cases"][1]["assignments"][1].__setitem__("condition_id", "cond_33333333333333333333333333333333"))
    map_case("sampling-schema", "SAMPLING_SCHEMA", lambda x: x["sampling_receipt"].__setitem__("schema", "x"))
    map_case("sampling-schema-hash", "SAMPLING_SCHEMA_HASH", lambda x: x["sampling_receipt"].__setitem__("receipt_schema_sha256", "0" * 64))
    map_case("sampling-boundary", "SAMPLING_BOUNDARY", lambda x: x["sampling_receipt"].__setitem__("receipt_precedes_first_condition_output", False))
    map_case("sampling-domain", "SAMPLING_DOMAIN", lambda x: x["sampling_receipt"].__setitem__("sampling_selection_domain", "x"))
    map_case("sampling-message", "SAMPLING_MESSAGE", lambda x: x["sampling_receipt"].__setitem__("sampling_selection_message", "x"))
    map_case("sampling-prob-duplicate", "SAMPLING_CASE_DUPLICATE", lambda x: x["sampling_receipt"]["case_inclusion_probabilities"][1].__setitem__("case_id", x["sampling_receipt"]["case_inclusion_probabilities"][0]["case_id"]))
    map_case("sampling-weight-duplicate", "SAMPLING_CASE_DUPLICATE", lambda x: x["sampling_receipt"]["case_sampling_weights"][1].__setitem__("case_id", x["sampling_receipt"]["case_sampling_weights"][0]["case_id"]))
    map_case("sampling-order", "SAMPLING_CASE_ORDER", lambda x: x["sampling_receipt"]["case_sampling_weights"].reverse())
    map_case("sampling-probability", "SAMPLING_PROBABILITY", lambda x: x["sampling_receipt"]["case_inclusion_probabilities"][0].update({"numerator": 2, "denominator": 1}))
    map_case("sampling-weight", "SAMPLING_WEIGHT", lambda x: x["sampling_receipt"]["case_sampling_weights"][0].update({"numerator": 1, "denominator": 2}))
    map_case("sampling-reciprocal", "SAMPLING_RECIPROCAL", lambda x: x["sampling_receipt"]["case_sampling_weights"][0].update({"numerator": 2, "denominator": 1}))
    map_case("sampling-reduced-prob", "SAMPLING_REDUCED", lambda x: x["sampling_receipt"]["case_inclusion_probabilities"][0].update({"numerator": 2, "denominator": 2}))
    map_case("sampling-reduced-weight", "SAMPLING_REDUCED", lambda x: x["sampling_receipt"]["case_sampling_weights"][0].update({"numerator": 2, "denominator": 2}))
    map_case("selected-schema", "SELECTED_SCHEMA", lambda x: x["selected_case_manifest"].__setitem__("schema", "x"))
    map_case("selected-duplicate", "SELECTED_CASE_DUPLICATE", lambda x: x["selected_case_manifest"]["cases"][1].__setitem__("case_id", x["selected_case_manifest"]["cases"][0]["case_id"]))
    map_case("roster-schema", "ROSTER_SCHEMA", lambda x: x["condition_roster"].__setitem__("schema", "x"))
    map_case("roster-key-duplicate", "ROSTER_DUPLICATE", lambda x: x["condition_roster"]["conditions"][1].__setitem__("condition_key", x["condition_roster"]["conditions"][0]["condition_key"]))
    map_case("roster-id-duplicate", "ROSTER_DUPLICATE", lambda x: x["condition_roster"]["conditions"][1].__setitem__("condition_id", x["condition_roster"]["conditions"][0]["condition_id"]))
    map_case("roster-derivation", "ROSTER_DERIVATION", lambda x: x["condition_roster"]["conditions"][0].__setitem__("condition_id", "cond_33333333333333333333333333333333"))
    map_case("roster-order", "ROSTER_ORDER", lambda x: x["condition_roster"]["conditions"].reverse())
    map_case("generation-schema", "GENERATION_SCHEMA", lambda x: x["generation_manifest"].__setitem__("schema", "x"))
    map_case("generation-case-coverage", "GENERATION_CASE_COVERAGE", lambda x: x["generation_manifest"]["cases"].pop())
    map_case("generation-case-order", "GENERATION_CASE_ORDER", lambda x: x["generation_manifest"]["cases"].reverse())
    map_case("generation-order", "GENERATION_ORDER", lambda x: x["generation_manifest"]["cases"][0]["answers"].reverse())
    map_case("generation-answer-hash", "GENERATION_ANSWER_HASH", lambda x: x["generation_manifest"]["cases"][0]["answers"][0].__setitem__("answer_markdown", "drift"))
    map_case("generation-invocation", "GENERATION_INVOCATION", lambda x: x["generation_manifest"]["cases"][0]["answers"][0].__setitem__("invocation_index", 3))
    map_case("blind-schema", "BLIND_SCHEMA", lambda x: x["blind_packet"].__setitem__("schema", "x"))
    map_case("blind-case-coverage", "BLIND_CASE_COVERAGE", lambda x: x["blind_packet"]["cases"].pop())
    map_case("blind-case-order", "BLIND_CASE_ORDER", lambda x: x["blind_packet"]["cases"].reverse())
    map_case("blind-answer-derivation", "BLIND_ANSWER_DERIVATION", lambda x: x["blind_packet"]["cases"][0]["answers"][0].__setitem__("answer_id", "ans_33333333333333333333333333333333"))
    map_case("blind-answer-bytes", "BLIND_ANSWER_BYTES", lambda x: x["blind_packet"]["cases"][0]["answers"][0].__setitem__("answer_markdown", "drift"))
    map_case("cross-contract", "CONTRACT_BINDING", lambda x: x["selected_case_manifest"].__setitem__("contract_sha256", "0" * 64))
    map_case("cross-case-order", "CASE_ORDER_BINDING", lambda x: x["blind_map"]["cases"].reverse())
    map_case("cross-bijection", "BIJECTION_BINDING", lambda x: x["blind_map"]["cases"][0]["assignments"].reverse())
    map_case("map-contract-hash", "CONTRACT_BINDING", lambda x: x["blind_map"].__setitem__("contract_sha256", "0" * 64))
    map_case("map-sampling-hash", "MAP_IDENTITY_BINDING", lambda x: x["blind_map"].__setitem__("sampling_receipt_sha256", "0" * 64))
    map_case("map-eligible-hash", "MAP_IDENTITY_BINDING", lambda x: x["blind_map"].__setitem__("eligible_frame_manifest_sha256", "0" * 64))
    map_case("map-selected-hash", "MAP_IDENTITY_BINDING", lambda x: x["blind_map"].__setitem__("selected_case_manifest_sha256", "0" * 64))
    map_case("map-roster-hash", "MAP_IDENTITY_BINDING", lambda x: x["blind_map"].__setitem__("condition_roster_sha256", "0" * 64))
    map_case("map-capture-hash", "MAP_IDENTITY_BINDING", lambda x: x["blind_map"].__setitem__("capture_sha256", "0" * 64))
    map_case("map-generation-hash", "MAP_IDENTITY_BINDING", lambda x: x["blind_map"].__setitem__("generation_sha256", "0" * 64))
    map_case("map-blind-hash", "MAP_IDENTITY_BINDING", lambda x: x["blind_map"].__setitem__("blind_packet_sha256", "0" * 64))
    map_case("map-seed-hash", "MAP_IDENTITY_BINDING", lambda x: x["blind_map"].__setitem__("answer_blinding_seed_sha256", "0" * 64))
    map_case("sampling-eligible-binding", "ELIGIBLE_BINDING", mutate_sampling_eligible)
    map_case("sampling-selected-binding", "SELECTED_BINDING", mutate_sampling_selected)
    map_case("generation-capture-binding", "CAPTURE_BINDING", mutate_generation_capture)
    map_case("blind-capture-binding", "CAPTURE_BINDING", mutate_blind_capture)
    map_case("blind-generation-binding", "GENERATION_BINDING", mutate_blind_generation)
    map_case("map-time-order", "TIME_ORDER", lambda x: x["blind_map"].__setitem__("created_at_utc", x["sampling_receipt"]["created_at_utc"]))

    expect_rejection(
        "object-api-raw-mode",
        "INPUT_MODE",
        lambda: map_module.validate_request_object(
            root,
            request0,
            input_mode="raw_files",
        ),
        map_error_type=map_module.BijectionError,
    )
    counts["map"] += 1

    blind_packet_scope_probe = copy.deepcopy(request0["blind_packet"])
    blind_packet_scope_probe["trial_id"] = request0["answer_blinding_seed_hex"]
    expect_rejection(
        "blind-packet-trial-seed-leak",
        "BLIND_RAW_SEED_LEAK",
        lambda: map_module.reject_blind_private_token_disclosure(
            blind_packet_scope_probe,
            [
                (row["condition_key"], row["condition_id"])
                for row in request0["condition_roster"]["conditions"]
            ],
            bytes.fromhex(request0["answer_blinding_seed_hex"]),
        ),
        map_error_type=map_module.BijectionError,
    )
    counts["map"] += 1

    positive_map_result = map_module.validate_request_object(
        root, request0, input_mode="synthetic_fixture"
    )

    def map_result_case(
        name: str, code: str, mutate: Callable[[dict[str, Any]], None]
    ) -> None:
        trial = copy.deepcopy(positive_map_result)
        mutate(trial)
        expect_rejection(name, code, lambda: validate_map_validation_result(trial))
        counts["map"] += 1

    map_result_case("map-result-extra", "EXACT_KEYS", lambda x: x.__setitem__("receipt", True))
    map_result_case("map-result-status", "MAP_VALIDATION_BOUNDARY", lambda x: x.__setitem__("status", "VALID"))
    map_result_case("map-result-mode", "MAP_VALIDATION_BOUNDARY", lambda x: x.__setitem__("input_mode", "raw_files"))
    map_result_case("map-result-authority", "MAP_VALIDATION_BOUNDARY", lambda x: x.__setitem__("authorizes_review_execution", True))
    map_result_case("map-result-postgate", "MAP_VALIDATION_BOUNDARY", lambda x: x.__setitem__("satisfies_post_generation_gate", True))
    map_result_case("map-result-checker", "MAP_VALIDATION_IDENTITY", lambda x: x.__setitem__("checker_sha256", "0" * 64))
    map_result_case("map-result-binding-count", "MAP_VALIDATION_IDENTITY", lambda x: x.__setitem__("identity_binding_count", 9))

    def fixture_case(
        name: str,
        code: str,
        mutate: Callable[[dict[str, Any]], None],
    ) -> None:
        trial = copy.deepcopy(fixture)
        mutate(trial)
        expect_rejection(
            name,
            code,
            lambda: validate_fixture_value(root, trial, schemas, map_module),
        )
        counts["fixture"] += 1

    def fixture_acceptance(
        name: str, mutate: Callable[[dict[str, Any]], None]
    ) -> None:
        trial = copy.deepcopy(fixture)
        mutate(trial)
        try:
            validate_fixture_value(root, trial, schemas, map_module)
        except CheckError as exc:
            fail(
                "SELF_TEST_REJECTED_CONTROL",
                f"positive control {name} was rejected with {exc.code}",
            )
        counts["positive"] += 1

    def duplicate_forbidden_with_new_reason(value: dict[str, Any]) -> None:
        forbidden = value["truth_manifest"]["cases"][1]["claim_rubrics"][0][
            "forbidden_assertions"
        ]
        duplicate = copy.deepcopy(forbidden[0])
        duplicate["reason"] = "stale"
        forbidden.append(duplicate)

    def duplicate_claim_with_new_score(value: dict[str, Any]) -> None:
        scores = value["reviews"][0]["cases"][0]["answers"][0]["claim_scores"]
        duplicate = copy.deepcopy(scores[0])
        duplicate["score"] = (duplicate["score"] + 1) % 3
        scores.append(duplicate)

    def duplicate_reviewer(value: dict[str, Any]) -> None:
        value["reviews"].append(copy.deepcopy(value["reviews"][0]))

    def diverge_review_instruction(value: dict[str, Any]) -> None:
        duplicate = copy.deepcopy(value["reviews"][0])
        duplicate["reviewer_slot"] = "reviewer_slot_synthetic_2"
        duplicate["review_instruction_sha256"] = "0" * 64
        value["reviews"].append(duplicate)

    def record_answer_as_abstention(value: dict[str, Any]) -> None:
        answer = value["reviews"][0]["cases"][0]["answers"][0]
        answer["response_mode"] = "abstain"
        answer["abstention_assessment"] = "fail"
        for claim_score in answer["claim_scores"]:
            claim_score["score"] = 0

    def record_answer_as_abstention_wrong_assessment(
        value: dict[str, Any]
    ) -> None:
        answer = value["reviews"][0]["cases"][0]["answers"][0]
        answer["response_mode"] = "abstain"
        for claim_score in answer["claim_scores"]:
            claim_score["score"] = 0

    def record_abstention_as_answer(value: dict[str, Any]) -> None:
        answer = value["reviews"][0]["cases"][1]["answers"][0]
        answer["response_mode"] = "answer"
        answer["abstention_assessment"] = "fail"

    def set_reviewer_slot_to_seed_encoding(
        value: dict[str, Any], encoding: str
    ) -> None:
        seed = bytes.fromhex(
            value["map_bijection_request"]["answer_blinding_seed_hex"]
        )
        if encoding == "colon_hex":
            token = ":".join(f"{byte:02x}" for byte in seed)
        elif encoding == "hyphen_hex":
            token = "-".join(f"{byte:02x}" for byte in seed)
        elif encoding == "base32":
            token = base64.b32encode(seed).decode("ascii").rstrip("=").lower()
        else:
            fail("SELF_TEST_ENCODING", f"unknown seed encoding {encoding}")
        value["reviews"][0]["reviewer_slot"] = token

    def set_reviewer_slot_to_condition_encoding(
        value: dict[str, Any], field: str, encoding: str
    ) -> None:
        raw = value["map_bijection_request"]["condition_roster"]["conditions"][
            0
        ][field].encode("utf-8")
        if encoding == "hex":
            token = raw.hex()
        elif encoding == "base32":
            token = base64.b32encode(raw).decode("ascii").rstrip("=").lower()
        else:
            fail("SELF_TEST_ENCODING", f"unknown condition encoding {encoding}")
        value["reviews"][0]["reviewer_slot"] = token

    def inject_blind_private_token(value: dict[str, Any], token: str) -> None:
        request = value["map_bijection_request"]
        roster_row = request["condition_roster"]["conditions"][0]
        condition_key = roster_row["condition_key"]
        condition_id = roster_row["condition_id"]
        generation_case = request["generation_manifest"]["cases"][0]
        generated = next(
            row
            for row in generation_case["answers"]
            if row["condition_key"] == condition_key
        )
        generated["answer_markdown"] += f" {token}"
        generated["answer_sha256"] = sha256_bytes(
            generated["answer_markdown"].encode("utf-8")
        )
        map_case_row = request["blind_map"]["cases"][0]
        answer_id = next(
            row["answer_id"]
            for row in map_case_row["assignments"]
            if row["condition_id"] == condition_id
        )
        blind_answer = next(
            row
            for row in request["blind_packet"]["cases"][0]["answers"]
            if row["answer_id"] == answer_id
        )
        blind_answer["answer_markdown"] = generated["answer_markdown"]
        blind_answer["answer_sha256"] = generated["answer_sha256"]
        generation_sha = sha256_bytes(
            canonical_pretty_bytes(request["generation_manifest"])
        )
        request["blind_packet"]["generation_sha256"] = generation_sha
        request["blind_map"]["generation_sha256"] = generation_sha
        blind_sha = sha256_bytes(canonical_pretty_bytes(request["blind_packet"]))
        request["blind_map"]["blind_packet_sha256"] = blind_sha
        for review in value["reviews"]:
            review["blind_packet_sha256"] = blind_sha

    def inject_blind_condition_key(value: dict[str, Any]) -> None:
        token = value["map_bijection_request"]["condition_roster"]["conditions"][
            0
        ]["condition_key"]
        inject_blind_private_token(value, token)

    def inject_blind_condition_id(value: dict[str, Any]) -> None:
        token = value["map_bijection_request"]["condition_roster"]["conditions"][
            0
        ]["condition_id"]
        inject_blind_private_token(value, token)

    def inject_blind_raw_seed(value: dict[str, Any]) -> None:
        token = value["map_bijection_request"]["answer_blinding_seed_hex"].upper()
        inject_blind_private_token(value, token)

    def inject_blind_condition_encoding(
        value: dict[str, Any], field: str, encoding: str
    ) -> None:
        raw = value["map_bijection_request"]["condition_roster"]["conditions"][
            0
        ][field].encode("utf-8")
        if encoding == "hex":
            token = raw.hex()
        elif encoding == "base32":
            token = base64.b32encode(raw).decode("ascii").rstrip("=").lower()
        elif encoding == "base64url":
            token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        else:
            fail("SELF_TEST_ENCODING", f"unknown condition encoding {encoding}")
        inject_blind_private_token(value, token)

    def inject_blind_seed_encoding(
        value: dict[str, Any], encoding: str
    ) -> None:
        seed = bytes.fromhex(
            value["map_bijection_request"]["answer_blinding_seed_hex"]
        )
        if encoding == "base32":
            token = base64.b32encode(seed).decode("ascii").rstrip("=").lower()
        elif encoding == "base64":
            token = base64.b64encode(seed).decode("ascii")
        else:
            fail("SELF_TEST_ENCODING", f"unknown seed encoding {encoding}")
        inject_blind_private_token(value, token)

    fixture_case("fixture-boundary", "FIXTURE_BOUNDARY", lambda x: x["boundary"].__setitem__("real_run_authorized", True))
    fixture_case("fixture-extra", "EXACT_KEYS", lambda x: x.__setitem__("live", True))
    fixture_case("truth-referent-hash", "TRUTH_REFERENT_SCHEMA", lambda x: x["truth_manifest"].__setitem__("referent_schema_sha256", "0" * 64))
    fixture_case("truth-asof-late", "TRUTH_TIME_ORDER", lambda x: x["truth_manifest"].__setitem__("truth_as_of_utc", "2026-07-14T12:02:00Z"))
    fixture_case("truth-cutoff-late", "TRUTH_TIME_ORDER", lambda x: x["truth_manifest"].__setitem__("knowledge_cutoff_utc", "2026-07-14T12:06:00Z"))
    fixture_case("truth-output-time", "TRUTH_OUTPUT_TIME_ORDER", lambda x: x["truth_manifest"].__setitem__("created_at_utc", x["map_bijection_request"]["generation_manifest"]["first_condition_output_at_utc"]))
    fixture_case("truth-map-trial", "CROSS_TRIAL", lambda x: x["truth_manifest"].__setitem__("trial_id", "track_b_identity_synthetic_drift"))
    fixture_case("truth-map-contract", "CROSS_CONTRACT", lambda x: x["truth_manifest"].__setitem__("contract_sha256", "0" * 64))
    fixture_case("truth-selected-binding", "CROSS_SELECTED", lambda x: x["truth_manifest"].__setitem__("selected_case_manifest_sha256", "0" * 64))
    fixture_case("truth-case-duplicate", "TRUTH_CASE_DUPLICATE", lambda x: x["truth_manifest"]["cases"][1].__setitem__("case_id", x["truth_manifest"]["cases"][0]["case_id"]))
    fixture_case("truth-claim-collision", "TRUTH_CLAIM_COLLISION", lambda x: x["truth_manifest"]["cases"][1]["claim_rubrics"][0]["referent"].__setitem__("claim_handle", x["truth_manifest"]["cases"][0]["claim_rubrics"][0]["referent"]["claim_handle"]))
    fixture_case("truth-pair-collision", "TRUTH_PAIR_COLLISION", lambda x: x["truth_manifest"]["cases"][1]["claim_rubrics"][0]["referent"].update({"referent_handle": x["truth_manifest"]["cases"][0]["claim_rubrics"][0]["referent"]["referent_handle"], "predicate_handle": x["truth_manifest"]["cases"][0]["claim_rubrics"][0]["referent"]["predicate_handle"]}))
    fixture_case("truth-assertion-disjoint", "TRUTH_ASSERTION_DISJOINT", lambda x: x["truth_manifest"]["cases"][0]["claim_rubrics"][0]["forbidden_assertions"][0].__setitem__("assertion_handle", x["truth_manifest"]["cases"][0]["claim_rubrics"][0]["required_assertions"][0]["assertion_handle"]))
    fixture_case("truth-assertion-global-disjoint", "TRUTH_ASSERTION_DISJOINT", lambda x: x["truth_manifest"]["cases"][1]["claim_rubrics"][0]["forbidden_assertions"][0].__setitem__("assertion_handle", x["truth_manifest"]["cases"][0]["claim_rubrics"][0]["required_assertions"][0]["assertion_handle"]))
    fixture_case("truth-forbidden-reason-alias", "TRUTH_ASSERTION_DUPLICATE", duplicate_forbidden_with_new_reason)
    fixture_case("truth-score-empty", "TRUTH_SCORE_ASSERTIONS", lambda x: x["truth_manifest"]["cases"][0]["claim_rubrics"][0].__setitem__("required_assertions", []))
    fixture_case("truth-context-required", "TRUTH_CONTEXT_ASSERTIONS", lambda x: x["truth_manifest"]["cases"][1]["claim_rubrics"][0].__setitem__("required_assertions", [{"assertion_handle": "ast_33333333333333333333333333333333"}]))
    fixture_case("truth-context-no-forbidden", "TRUTH_CONTEXT_ASSERTIONS", lambda x: x["truth_manifest"]["cases"][1]["claim_rubrics"][0].__setitem__("forbidden_assertions", []))
    fixture_case("truth-answer-no-score", "TRUTH_RESPONSE_SEMANTICS", lambda x: x["truth_manifest"]["cases"][0]["claim_rubrics"][0].update({"review_requirement": "context_only", "required_assertions": []}))
    fixture_case("truth-abstain-score", "TRUTH_RESPONSE_SEMANTICS", lambda x: x["truth_manifest"]["cases"][1]["claim_rubrics"][0].update({"review_requirement": "score", "required_assertions": [{"assertion_handle": "ast_33333333333333333333333333333333"}]}))
    fixture_case("truth-weight", "INSTANCE_EXTRA", lambda x: x["truth_manifest"]["cases"][0]["claim_rubrics"][0].__setitem__("weight", 1))
    fixture_case("review-trial", "CROSS_TRIAL", lambda x: x["reviews"][0].__setitem__("trial_id", "trial_drift"))
    fixture_case("review-contract", "CROSS_CONTRACT", lambda x: x["reviews"][0].__setitem__("contract_sha256", "0" * 64))
    fixture_case("review-blind-hash", "CROSS_BLIND_PACKET", lambda x: x["reviews"][0].__setitem__("blind_packet_sha256", "0" * 64))
    fixture_case("review-truth-hash", "CROSS_TRUTH_MANIFEST", lambda x: x["reviews"][0].__setitem__("truth_manifest_sha256", "0" * 64))
    fixture_case("review-referent-hash", "CROSS_REFERENT_SCHEMA", lambda x: x["reviews"][0].__setitem__("referent_schema_sha256", "0" * 64))
    fixture_case("review-case-coverage", "REVIEW_CASE_COVERAGE", lambda x: x["reviews"][0]["cases"].pop())
    fixture_case("review-case-duplicate", "REVIEW_CASE_DUPLICATE", lambda x: x["reviews"][0]["cases"][1].__setitem__("case_id", x["reviews"][0]["cases"][0]["case_id"]))
    fixture_case("review-case-order", "REVIEW_CASE_ORDER", lambda x: x["reviews"][0]["cases"].reverse())
    fixture_case("review-answer-coverage", "REVIEW_ANSWER_COVERAGE", lambda x: x["reviews"][0]["cases"][0]["answers"].pop())
    fixture_case("review-answer-duplicate", "REVIEW_ANSWER_DUPLICATE", lambda x: x["reviews"][0]["cases"][0]["answers"][1].__setitem__("answer_id", x["reviews"][0]["cases"][0]["answers"][0]["answer_id"]))
    fixture_case("review-answer-order", "REVIEW_ANSWER_ORDER", lambda x: x["reviews"][0]["cases"][0]["answers"].reverse())
    fixture_case("review-claim-coverage", "REVIEW_CLAIM_COVERAGE", lambda x: x["reviews"][0]["cases"][0]["answers"][0].__setitem__("claim_scores", []))
    fixture_case("review-claim-duplicate", "REVIEW_CLAIM_DUPLICATE", duplicate_claim_with_new_score)
    fixture_case("review-forbidden-coverage", "REVIEW_FORBIDDEN_COVERAGE", lambda x: x["reviews"][0]["cases"][0]["answers"][0].__setitem__("matched_forbidden_assertion_handles", ["ast_33333333333333333333333333333333"]))
    fixture_case("review-forbidden-count", "REVIEW_FORBIDDEN_COUNT", lambda x: x["reviews"][0]["cases"][0]["answers"][1].__setitem__("matched_forbidden_assertion_count", 0))
    fixture_case("review-forbidden-duplicate", "INSTANCE_UNIQUE", lambda x: x["reviews"][0]["cases"][0]["answers"][1]["matched_forbidden_assertion_handles"].append(x["reviews"][0]["cases"][0]["answers"][1]["matched_forbidden_assertion_handles"][0]))
    fixture_case("review-abstention-answer", "REVIEW_ABSTENTION", lambda x: x["reviews"][0]["cases"][0]["answers"][0].__setitem__("abstention_assessment", "pass"))
    fixture_case("review-abstention-fail", "REVIEW_ABSTENTION", lambda x: x["reviews"][0]["cases"][1]["answers"][0].__setitem__("abstention_assessment", "fail"))
    fixture_case("review-answer-abstain-wrong-assessment", "REVIEW_ABSTENTION", record_answer_as_abstention_wrong_assessment)
    fixture_case("review-abstain-answer-wrong-assessment", "REVIEW_ABSTENTION", lambda x: x["reviews"][0]["cases"][1]["answers"][0].__setitem__("response_mode", "answer"))
    fixture_case("review-abstention-claim-score", "REVIEW_ABSTENTION_CLAIM_SCORE", lambda x: x["reviews"][0]["cases"][0]["answers"][0].update({"response_mode": "abstain", "abstention_assessment": "fail"}))
    fixture_case("review-abstention-currentness", "REVIEW_ABSTENTION_CURRENTNESS", lambda x: x["reviews"][0]["cases"][1]["answers"][0].__setitem__("currentness", "uncertain"))
    fixture_case("review-abstention-assertion", "REVIEW_ABSTENTION_ASSERTIONS", lambda x: x["reviews"][0]["cases"][1]["answers"][0].__setitem__("unmatched_unsupported_assertion_count", 1))
    fixture_acceptance("answer-observed-abstention", record_answer_as_abstention)
    fixture_acceptance("abstention-observed-answer", record_abstention_as_answer)
    fixture_case("reviewer-case-collision", "REVIEWER_COLLISION", lambda x: x["reviews"][0].__setitem__("reviewer_slot", x["truth_manifest"]["cases"][0]["case_id"]))
    fixture_case("reviewer-trial-collision", "REVIEWER_COLLISION", lambda x: x["reviews"][0].__setitem__("reviewer_slot", x["truth_manifest"]["trial_id"]))
    fixture_case("reviewer-answer-collision", "REVIEWER_COLLISION", lambda x: x["reviews"][0].__setitem__("reviewer_slot", x["reviews"][0]["cases"][0]["answers"][0]["answer_id"]))
    fixture_case("reviewer-claim-collision", "REVIEWER_COLLISION", lambda x: x["reviews"][0].__setitem__("reviewer_slot", x["truth_manifest"]["cases"][0]["claim_rubrics"][0]["referent"]["claim_handle"]))
    fixture_case("reviewer-condition-collision", "REVIEWER_COLLISION", lambda x: x["reviews"][0].__setitem__("reviewer_slot", x["map_bijection_request"]["condition_roster"]["conditions"][0]["condition_id"]))
    fixture_case("reviewer-condition-key-leak", "REVIEW_CONDITION_LEAK", lambda x: x["reviews"][0].__setitem__("reviewer_slot", x["map_bijection_request"]["condition_roster"]["conditions"][0]["condition_key"]))
    fixture_case("reviewer-condition-key-hex-leak", "REVIEW_CONDITION_LEAK", lambda x: set_reviewer_slot_to_condition_encoding(x, "condition_key", "hex"))
    fixture_case("reviewer-condition-id-base32-leak", "REVIEW_CONDITION_LEAK", lambda x: set_reviewer_slot_to_condition_encoding(x, "condition_id", "base32"))
    fixture_case("reviewer-raw-seed-leak", "REVIEW_RAW_SEED_LEAK", lambda x: x["reviews"][0].__setitem__("reviewer_slot", x["map_bijection_request"]["answer_blinding_seed_hex"]))
    fixture_case("reviewer-seed-colon-hex-leak", "REVIEW_RAW_SEED_LEAK", lambda x: set_reviewer_slot_to_seed_encoding(x, "colon_hex"))
    fixture_case("reviewer-seed-hyphen-hex-leak", "REVIEW_RAW_SEED_LEAK", lambda x: set_reviewer_slot_to_seed_encoding(x, "hyphen_hex"))
    fixture_case("reviewer-seed-base32-leak", "REVIEW_RAW_SEED_LEAK", lambda x: set_reviewer_slot_to_seed_encoding(x, "base32"))
    fixture_case("reviewer-duplicate", "REVIEWER_DUPLICATE", duplicate_reviewer)
    fixture_case("review-instruction-divergence", "REVIEW_INSTRUCTION_DIVERGENCE", diverge_review_instruction)
    fixture_case("review-preference", "INSTANCE_EXTRA", lambda x: x["reviews"][0]["cases"][0].__setitem__("preferred_answer_id", "tie"))
    fixture_case("review-weight", "INSTANCE_EXTRA", lambda x: x["reviews"][0]["cases"][0]["answers"][0]["claim_scores"][0].__setitem__("weight", 1))
    fixture_case("review-old-unsupported-field", "INSTANCE_EXTRA", lambda x: x["reviews"][0]["cases"][0]["answers"][0].__setitem__("unsupported_assertion_count", 1))
    fixture_case("review-authority", "INSTANCE_CONST", lambda x: x["reviews"][0]["boundary"].__setitem__("authorizes_scoring", True))
    fixture_case("blind-condition-key-leak", "MAP_BLIND_CONDITION_KEY_LEAK", inject_blind_condition_key)
    fixture_case("blind-condition-key-hex-leak", "MAP_BLIND_CONDITION_KEY_LEAK", lambda x: inject_blind_condition_encoding(x, "condition_key", "hex"))
    fixture_case("blind-condition-key-base32-leak", "MAP_BLIND_CONDITION_KEY_LEAK", lambda x: inject_blind_condition_encoding(x, "condition_key", "base32"))
    fixture_case("blind-condition-id-leak", "MAP_BLIND_CONDITION_ID_LEAK", inject_blind_condition_id)
    fixture_case("blind-condition-id-base64url-leak", "MAP_BLIND_CONDITION_ID_LEAK", lambda x: inject_blind_condition_encoding(x, "condition_id", "base64url"))
    fixture_case("blind-raw-seed-leak", "MAP_BLIND_RAW_SEED_LEAK", inject_blind_raw_seed)
    fixture_case("blind-seed-base32-leak", "MAP_BLIND_RAW_SEED_LEAK", lambda x: inject_blind_seed_encoding(x, "base32"))
    fixture_case("blind-seed-base64-leak", "MAP_BLIND_RAW_SEED_LEAK", lambda x: inject_blind_seed_encoding(x, "base64"))
    fixture_case("fixture-expected", "FIXTURE_EXPECTED", lambda x: x["expected"].__setitem__("answer_count", 5))

    def resource_case(
        name: str,
        cap_key: str,
        cap_value: int,
        code: str,
        mutate: Callable[[dict[str, Any]], None],
    ) -> None:
        original = RESOURCE_CAPS[cap_key]
        trial = copy.deepcopy(fixture)
        mutate(trial)
        RESOURCE_CAPS[cap_key] = cap_value
        try:
            expect_rejection(name, code, lambda: validate_fixture_value(root, trial, schemas, map_module))
        finally:
            RESOURCE_CAPS[cap_key] = original
        counts["fixture"] += 1

    resource_case("fixture-input-resource", "max_total_input_bytes", 0, "FIXTURE_RESOURCE", lambda x: None)
    resource_case("fixture-case-resource", "max_cases", 1, "FIXTURE_RESOURCE", lambda x: None)
    resource_case("fixture-condition-resource", "max_conditions", 1, "FIXTURE_RESOURCE", lambda x: None)
    resource_case("fixture-answer-product", "max_total_answers", 3, "FIXTURE_RESOURCE", lambda x: None)
    resource_case("fixture-answer-characters", "max_answer_characters", 1, "FIXTURE_RESOURCE", lambda x: None)
    resource_case("fixture-answer-bytes", "max_total_answer_bytes", 1, "FIXTURE_RESOURCE", lambda x: None)
    resource_case("truth-resource", "max_total_truth_assertions", 0, "TRUTH_RESOURCE", lambda x: None)
    resource_case("truth-forbidden-resource", "max_forbidden_assertions_per_case", 0, "TRUTH_RESOURCE", lambda x: None)
    resource_case("review-resource", "max_total_claim_scores", 1, "REVIEW_RESOURCE", lambda x: None)
    resource_case("review-forbidden-resource", "max_forbidden_handles_per_answer", 0, "REVIEW_RESOURCE", lambda x: None)

    manifest0 = inputs["manifest"]
    graph = inputs["graph"]

    def source_case(name: str, code: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        trial = copy.deepcopy(manifest0)
        mutate(trial)
        expect_rejection(
            name,
            code,
            lambda: validate_manifest_value(root, trial, inputs["fixture_raw"], graph),
        )
        counts["source"] += 1

    source_case("manifest-baseline", "MANIFEST_SCALAR", lambda x: x.__setitem__("baseline_commit", "0" * 40))
    source_case("manifest-schema", "MANIFEST_SCALAR", lambda x: x.__setitem__("schema", "x"))
    source_case("manifest-fixture", "MANIFEST_FIXTURE_HASH", lambda x: x.__setitem__("synthetic_fixture_sha256", "0" * 64))
    source_case("manifest-bindings", "MANIFEST_ARTIFACT_BINDINGS", lambda x: x["artifact_bindings"].reverse())
    source_case("manifest-boundary", "MANIFEST_BOUNDARY", lambda x: x["boundary"].__setitem__("authority_true_count", 1))
    source_case("manifest-completed", "MANIFEST_COMPLETED_PUBLIC_BINDINGS", lambda x: x["completed_public_bindings"].pop())
    source_case("manifest-evidence", "MANIFEST_EVIDENCE_SHA256", lambda x: x["evidence_sha256"].__setitem__(GRAPH_PATH, "0" * 64))
    source_case("manifest-identity", "MANIFEST_IDENTITY_BINDING_REQUIRED_FIELDS", lambda x: x["identity_binding_required_fields"].pop())
    source_case("manifest-frontier", "MANIFEST_NEXT_PUBLIC_FRONTIER", lambda x: x["next_public_frontier"].pop())
    source_case("manifest-resources", "MANIFEST_RESOURCE_CAPS", lambda x: x["resource_caps"].__setitem__("max_cases", 1))
    source_case("manifest-semantics", "MANIFEST_SEMANTICS", lambda x: x["semantics"].__setitem__("claim_weight_present", True))
    source_case("manifest-blockers", "MANIFEST_STRUCTURAL_BLOCKERS", lambda x: x["structural_blockers"].pop())

    total = sum(value for key, value in counts.items() if key != "positive")
    if total < 112:
        fail("SELF_TEST_COUNT", f"only {total} mutations were exercised")
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    inputs = load_inputs(args.root.resolve())
    if args.self_test:
        counts = run_self_test(args.root.resolve(), inputs)
        total = sum(value for key, value in counts.items() if key != "positive")
        print(
            "SELF_TEST_OK"
            f"\tjson_mutations_rejected={counts['json']}"
            f"\tschema_mutations_rejected={counts['schema']}"
            f"\tmap_mutations_rejected={counts['map']}"
            f"\tfixture_mutations_rejected={counts['fixture']}"
            f"\tsource_mutations_rejected={counts['source']}"
            f"\tpositive_mismatch_controls_accepted={counts['positive']}"
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
