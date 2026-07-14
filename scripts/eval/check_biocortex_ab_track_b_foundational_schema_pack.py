#!/usr/bin/env python3
"""Validate the public Track B foundational schema pack without side effects."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable


PACK_SCHEMA = "agent_bridge.biocortex_ab_track_b_foundational_schema_pack.v0"
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_foundational_schema_pack_synthetic.v0"
)
DIALECT = "https://json-schema.org/draft/2020-12/schema"
BASELINE_COMMIT = "a989cf6e09d60cb4d3d9b6d5f6a60e55ecd65259"
GRAPH_SOURCE_COMMIT = "ba4dbae629398ec16e4f22f4b0ac7f2ce372541f"
GRAPH_SHA256 = "8f618659cb90cc311ef79aafa3fc536bacc3f428f82291998174a0e374d993af"
S2_SCHEMA_SHA256 = "6d321d45aafe65ef06efb49c46ccf9f1931624aada9e8873d7e29765826e3aa0"
CANONICAL_SERIALIZATION = (
    "UTF8_SORTED_KEYS_INDENT_2_LF_FINAL_NEWLINE_NO_NAN_DUPLICATE_KEYS_REJECTED"
)
DECISION = "SOURCE_ARTIFACTS_IMPLEMENTED_NOT_LIVE_BOUND"

MANIFEST_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_foundational_schema_pack_v0.json"
)
FIXTURE_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_foundational_schema_pack_synthetic_v0.json"
)
GRAPH_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_artifact_dependency_graph_v0.json"
)
LEDGER_PATH = "scripts/eval/fixtures/biocortex_ab_track_b_live_binding_ledger_v0.json"
ADMISSION_PATH = (
    "scripts/eval/fixtures/biocortex_ab_track_b_real_run_admission_v0.json"
)
S2_CONTRACT_PATH = (
    "scripts/eval/fixtures/memory_temporal_evidence_substrate_s2_contract_v0.json"
)

SCHEMA_CATALOG = (
    {
        "binding_path": "review_and_blinding.map_schema_sha256",
        "key": "blind_map",
        "path": "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json",
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:blind-map:v0",
        "instance_schema": "agent_bridge.biocortex_ab_track_b_blind_map.v0",
        "sha256": "ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783",
    },
    {
        "binding_path": "review_and_blinding.review_command_schema_sha256",
        "key": "review_command",
        "path": "docs/design/fixtures/biocortex-ab-track-b-review-command-schema-v0.json",
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:review-command:v0",
        "instance_schema": "agent_bridge.biocortex_ab_track_b_review_command.v0",
        "sha256": "40df0e39f36df01d414487c496cf09b5ffbed89cafc540dc89e6e57bea4466f5",
    },
    {
        "binding_path": "sampling.sampling_receipt_schema_sha256",
        "key": "sampling_receipt",
        "path": "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json",
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:sampling-receipt:v0",
        "instance_schema": "agent_bridge.biocortex_ab_track_b_sampling_receipt.v0",
        "sha256": "9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd",
    },
    {
        "binding_path": "truth_inputs.referent_schema_sha256",
        "key": "truth_referents",
        "path": "docs/design/fixtures/biocortex-ab-track-b-truth-referent-schema-v0.json",
        "schema_id": "urn:agent-bridge:biocortex-ab:track-b:truth-referent:v0",
        "instance_schema": None,
        "sha256": "5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8",
    },
)

EXPECTED_EVIDENCE = {
    "crates/bridge/src/memory_truth.rs": "2e46a521332820b07171b425c95004f35a98887c7c49a2d78baf7740f07195a4",
    "docs/design/MEMORY_TEMPORAL_EVIDENCE_SUBSTRATE_S2_2026_07_14.md": "dd837929fdd1acf29be4c17ce06f3dacd4ae25f2bb13cf6ed190b84f65098f5b",
    "docs/reports/goal-c-u/2026-07-14-biocortex-ab-track-b-evidence-substrate-s2.md": "974d45a40b66517ce2c4445731c76f8dc0af66f976fa634cbf024ab7b020a337",
    "scripts/eval/check_biocortex_ab_track_b_admission.py": "b09b10243f195299dc226b5d8d2b484ec74f5eecd49bb487296c391f6f193b13",
    GRAPH_PATH: GRAPH_SHA256,
    LEDGER_PATH: "764f063fefe0e516547f9bd1e71417242daf292d57e480ae39b73df8bcda341a",
    ADMISSION_PATH: "1508c0c990ccf9ce26fa0eb524194bb587816cc78d4546236c8d9c00dd3b306e",
    S2_CONTRACT_PATH: "4dc7f459baa6de49755b79578c1ffdd6818c56d7f15916af72b024ef04c793da",
    "scripts/eval/portfolio_continuity_successor_v3_trial.py": "0b92b1153a77257a49fc847eb37be3e20d687c41067559c22b2ebed72649e003",
}

SAMPLING_BINDINGS = (
    "case_inclusion_probabilities",
    "case_sampling_weights",
    "contract_sha256",
    "created_at_utc",
    "eligible_frame_manifest_sha256",
    "frame_o_excl_receipt_sha256",
    "receipt_precedes_first_condition_output",
    "receipt_schema_sha256",
    "receipt_writer_sha256",
    "reserve_manifest_sha256",
    "sampling_selection_algorithm_sha256",
    "sampling_selection_domain",
    "sampling_selection_message",
    "seed_derivation_sha256",
    "seed_entropy_receipt_sha256",
    "selected_case_manifest_sha256",
    "strata_allocation_manifest_sha256",
    "trial_id",
)

NEXT_FRONTIER = (
    "reference_condition.context_builder_sha256",
    "review_and_blinding.map_bijection_checker_sha256",
    "review_and_blinding.review_schema_sha256",
    "sampling.sampling_seed_derivation_sha256",
    "sampling.sampling_selection_algorithm_sha256",
    "truth_inputs.truth_manifest_schema_sha256",
)

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

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
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
        fail("JSON_CANONICAL", f"value is not canonical JSON: {exc}")


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
        fail("JSON_CANONICAL", f"value is not compact canonical JSON: {exc}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def resolve_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        fail("PATH", f"non-canonical relative path {relative!r}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        fail("PATH", f"non-canonical relative path {relative!r}")
    path = root.joinpath(*pure.parts)
    try:
        path.relative_to(root)
    except ValueError:
        fail("PATH", f"path escapes root: {relative!r}")
    return path


def read_bytes(root: Path, relative: str) -> bytes:
    path = resolve_path(root, relative)
    try:
        return path.read_bytes()
    except OSError as exc:
        fail("FILE_READ", f"cannot read {relative}: {exc}")


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


def load_canonical(root: Path, relative: str) -> tuple[Any, bytes]:
    raw = read_bytes(root, relative)
    value = parse_json(raw, relative)
    if raw != canonical_pretty_bytes(value):
        fail("JSON_CANONICAL", f"{relative} is not canonical pretty JSON")
    return value, raw


def require_object(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        fail("TYPE_OBJECT", f"{label} must be an object")
    return value


def require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        fail(
            "EXACT_KEYS",
            f"{label} fields drift: missing={sorted(expected - actual)} extra={sorted(actual - expected)}",
        )


def require_sha256(value: Any, label: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        fail("SHA256", f"{label} must be lowercase SHA-256")
    return value


def require_label(value: Any, label: str) -> str:
    if type(value) is not str or LABEL_RE.fullmatch(value) is None:
        fail("LABEL", f"{label} must be a bounded ASCII machine label")
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


def require_sorted_unique_strings(value: Any, label: str) -> list[str]:
    if type(value) is not list or any(type(item) is not str for item in value):
        fail("STRING_LIST", f"{label} must be a string list")
    if value != sorted(set(value)):
        fail("STRING_LIST", f"{label} must be sorted and unique")
    return value


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
        fail("SCHEMA_DIALECT", f"{entry['key']} schema dialect drift")
    if schema.get("$id") != entry["schema_id"]:
        fail("SCHEMA_ID", f"{entry['key']} schema id drift")

    definitions = require_object(schema.get("$defs"), f"{entry['key']}.$defs")
    if not definitions:
        fail("DEFS_EMPTY", f"{entry['key']} must be self-contained")
    for name in definitions:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) is None:
            fail("DEF_NAME", f"invalid definition name {name!r}")

    seen_refs: list[str] = []
    object_count = 0

    def walk(node: Any, path: str) -> None:
        nonlocal object_count
        node = require_object(node, path)
        unknown = set(node) - ALLOWED_SCHEMA_KEYWORDS
        if unknown:
            fail("SCHEMA_KEYWORD", f"{path} has forbidden keywords {sorted(unknown)}")
        if "$ref" in node:
            if set(node) != {"$ref"}:
                fail("REF_SIBLING", f"{path} has a $ref sibling")
            ref = node["$ref"]
            if type(ref) is not str or re.fullmatch(r"#/\$defs/[A-Za-z][A-Za-z0-9]*", ref) is None:
                fail("REF_POLICY", f"{path} uses a non-local or encoded $ref")
            name = ref.rsplit("/", 1)[1]
            if name not in definitions:
                fail("REF_UNRESOLVED", f"{path} references missing definition {name!r}")
            seen_refs.append(name)
            return

        schema_type = node.get("type")
        if schema_type is not None and schema_type not in {"object", "array", "string", "integer"}:
            fail("SCHEMA_TYPE", f"{path} has unsupported type {schema_type!r}")
        if "const" in node and type(node["const"]) not in {str, bool, int}:
            fail("SCHEMA_CONST", f"{path} has an unsupported const")

        if schema_type == "object":
            object_count += 1
            if node.get("additionalProperties") is not False:
                fail("OBJECT_OPEN", f"{path} must set additionalProperties=false")
            if node.get("unevaluatedProperties") is not False:
                fail("OBJECT_OPEN", f"{path} must set unevaluatedProperties=false")
            properties = require_object(node.get("properties"), f"{path}.properties")
            required = node.get("required")
            if type(required) is not list or required != sorted(set(required)):
                fail("OBJECT_REQUIRED", f"{path}.required must be sorted and unique")
            if set(required) != set(properties):
                fail("OBJECT_REQUIRED", f"{path} must require every declared property")
            for key, child in properties.items():
                walk(child, f"{path}.properties.{key}")
        elif schema_type == "array":
            if type(node.get("maxItems")) is not int or type(node.get("maxItems")) is bool:
                fail("ARRAY_BOUND", f"{path} requires a finite maxItems")
            if node["maxItems"] < 0:
                fail("ARRAY_BOUND", f"{path}.maxItems cannot be negative")
            if "minItems" in node and (
                type(node["minItems"]) is not int or node["minItems"] < 0
            ):
                fail("ARRAY_BOUND", f"{path}.minItems is invalid")
            walk(node.get("items"), f"{path}.items")
        elif schema_type == "string":
            if "pattern" not in node:
                fail("STRING_PATTERN", f"{path} requires an ASCII pattern")
            try:
                re.compile(node["pattern"], re.ASCII)
            except (TypeError, re.error) as exc:
                fail("STRING_PATTERN", f"{path} pattern is invalid: {exc}")
            if type(node.get("minLength")) is not int or type(node.get("maxLength")) is not int:
                fail("STRING_BOUND", f"{path} requires minLength and maxLength")
            if node["minLength"] < 0 or node["maxLength"] < node["minLength"]:
                fail("STRING_BOUND", f"{path} string bounds are invalid")
        elif schema_type == "integer":
            minimum = node.get("minimum")
            maximum = node.get("maximum")
            if type(minimum) is not int or type(maximum) is not int:
                fail("INTEGER_BOUND", f"{path} requires integer bounds")
            if type(minimum) is bool or type(maximum) is bool or maximum < minimum:
                fail("INTEGER_BOUND", f"{path} integer bounds are invalid")

    walk(schema, entry["key"])
    for name, definition in definitions.items():
        walk(definition, f"{entry['key']}.$defs.{name}")

    used = set(seen_refs)
    unused = set(definitions) - used
    if unused:
        fail("DEF_UNUSED", f"{entry['key']} has unused definitions {sorted(unused)}")

    dependency_graph: dict[str, set[str]] = {}
    for name, definition in definitions.items():
        dependency_graph[name] = {
            ref.rsplit("/", 1)[1] for ref in collect_refs(definition)
        }
    active: set[str] = set()
    complete: set[str] = set()

    def visit(name: str) -> None:
        if name in active:
            fail("REF_CYCLE", f"definition reference cycle at {name}")
        if name in complete:
            return
        active.add(name)
        for target in sorted(dependency_graph[name]):
            visit(target)
        active.remove(name)
        complete.add(name)

    for name in sorted(definitions):
        visit(name)

    properties = require_object(schema.get("properties"), f"{entry['key']}.properties")
    instance_schema = entry["instance_schema"]
    if instance_schema is None:
        if "schema" in properties:
            fail("INSTANCE_DISCRIMINATOR", "truth referent leaf must not carry a schema field")
    elif properties.get("schema") != {"const": instance_schema}:
        fail("INSTANCE_DISCRIMINATOR", f"{entry['key']} schema discriminator drift")

    return {
        "object_count": object_count,
        "ref_count": len(seen_refs),
        "remote_ref_count": 0,
        "unresolved_ref_count": 0,
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
        schema_type = node.get("type")
        if schema_type == "object":
            if type(item) is not dict:
                fail("INSTANCE_TYPE", f"{item_path} must be an object")
            required = set(node["required"])
            missing = required - set(item)
            if missing:
                fail("INSTANCE_REQUIRED", f"{item_path} missing {sorted(missing)}")
            extra = set(item) - set(node["properties"])
            if extra:
                fail("INSTANCE_EXTRA", f"{item_path} has unknown fields {sorted(extra)}")
            for key in node["required"]:
                check(node["properties"][key], item[key], f"{item_path}.{key}")
        elif schema_type == "array":
            if type(item) is not list:
                fail("INSTANCE_TYPE", f"{item_path} must be an array")
            if len(item) < node.get("minItems", 0):
                fail("INSTANCE_MIN_ITEMS", f"{item_path} is too short")
            if len(item) > node["maxItems"]:
                fail("INSTANCE_MAX_ITEMS", f"{item_path} is too long")
            if node.get("uniqueItems"):
                identities = [canonical_compact_bytes(row) for row in item]
                if len(identities) != len(set(identities)):
                    fail("INSTANCE_UNIQUE", f"{item_path} has duplicate items")
            for index, row in enumerate(item):
                check(node["items"], row, f"{item_path}[{index}]")
        elif schema_type == "string":
            if type(item) is not str:
                fail("INSTANCE_TYPE", f"{item_path} must be a string")
            if len(item) < node["minLength"] or len(item) > node["maxLength"]:
                fail("INSTANCE_STRING_BOUND", f"{item_path} length is outside bounds")
            if re.fullmatch(node["pattern"], item, re.ASCII) is None:
                fail("INSTANCE_PATTERN", f"{item_path} does not match its pattern")
        elif schema_type == "integer":
            if type(item) is not int:
                fail("INSTANCE_TYPE", f"{item_path} must be an integer, not bool/float")
            if item < node["minimum"]:
                fail("INSTANCE_MINIMUM", f"{item_path} is below minimum")
            if item > node["maximum"]:
                fail("INSTANCE_MAXIMUM", f"{item_path} is above maximum")

    check(schema, value, path)


def validate_blind_map(schema: dict[str, Any], value: Any) -> dict[str, Any]:
    validate_instance(schema, value, "blind_map")
    require_utc(value["created_at_utc"], "blind_map.created_at_utc")
    cases = value["cases"]
    case_ids: list[str] = []
    answer_ids: list[str] = []
    condition_sets: list[set[str]] = []
    for case in cases:
        case_id = case["case_id"]
        if case_id in case_ids:
            fail("BLIND_CASE_DUPLICATE", f"duplicate blind case {case_id}")
        case_ids.append(case_id)
        conditions: list[str] = []
        for assignment in case["assignments"]:
            answer_id = assignment["answer_id"]
            condition_id = assignment["condition_id"]
            if answer_id in answer_ids:
                fail("BLIND_ANSWER_DUPLICATE", f"duplicate answer id {answer_id}")
            answer_ids.append(answer_id)
            if condition_id in conditions:
                fail("BLIND_CONDITION_BIJECTION", f"duplicate condition {condition_id}")
            conditions.append(condition_id)
        condition_sets.append(set(conditions))
    if any(current != condition_sets[0] for current in condition_sets[1:]):
        fail("BLIND_CONDITION_ROSTER", "condition roster differs across cases")
    return {
        "answer_ids": answer_ids,
        "case_ids": case_ids,
        "condition_ids": sorted(condition_sets[0]),
        "created_at": require_utc(value["created_at_utc"], "blind_map.created_at_utc"),
    }


def validate_review_command(schema: dict[str, Any], value: Any) -> dict[str, Any]:
    validate_instance(schema, value, "review_command")
    if value["context_environment_keys"] != []:
        fail("REVIEW_ENVIRONMENT", "review command context environment must be empty")
    argv = value["argv"]
    if argv[0] == "":
        fail("REVIEW_EXECUTABLE_EMPTY", "review executable cannot be empty")
    if any(any(ord(char) < 32 or ord(char) == 127 for char in token) for token in argv):
        fail("REVIEW_CONTROL", "review argv contains a control character")
    if any("\\" in token for token in argv):
        fail("REVIEW_BACKSLASH", "review argv contains a backslash path or escape")
    executable = argv[0].rsplit("/", 1)[-1].lower()
    if executable in {"sh", "bash", "dash", "zsh", "fish", "cmd", "cmd.exe", "powershell", "pwsh"}:
        fail("REVIEW_SHELL", "review command cannot invoke a shell")
    return {
        "created_at": require_utc(value["created_at_utc"], "review_command.created_at_utc"),
        "reviewer_slot": value["reviewer_slot"],
    }


def validate_sampling_receipt(
    schema: dict[str, Any], value: Any, schema_sha256: str
) -> dict[str, Any]:
    validate_instance(schema, value, "sampling_receipt")
    if value["receipt_schema_sha256"] != schema_sha256:
        fail("SAMPLING_SCHEMA_HASH", "sampling receipt schema hash does not bind bytes")
    created_at = require_utc(value["created_at_utc"], "sampling_receipt.created_at_utc")
    probabilities = value["case_inclusion_probabilities"]
    weights = value["case_sampling_weights"]
    probability_ids = [row["case_id"] for row in probabilities]
    weight_ids = [row["case_id"] for row in weights]
    if len(probability_ids) != len(set(probability_ids)):
        fail("SAMPLING_PROBABILITY_CASE_DUPLICATE", "duplicate probability case")
    if len(weight_ids) != len(set(weight_ids)):
        fail("SAMPLING_WEIGHT_CASE_DUPLICATE", "duplicate weight case")
    if set(probability_ids) != set(weight_ids):
        fail("SAMPLING_CASE_SET", "probability and weight case sets differ")
    if probability_ids != weight_ids:
        fail("SAMPLING_CASE_ORDER", "probability and weight case order differs")
    weight_by_case = {row["case_id"]: row for row in weights}
    for probability in probabilities:
        case_id = probability["case_id"]
        if not case_id.startswith("case_"):
            fail("SAMPLING_CASE_NAMESPACE", f"sampling id is not case-grain: {case_id}")
        numerator = probability["numerator"]
        denominator = probability["denominator"]
        if numerator > denominator:
            fail("SAMPLING_PROBABILITY_RANGE", f"probability exceeds one for {case_id}")
        if math.gcd(numerator, denominator) != 1:
            fail("SAMPLING_FRACTION_REDUCED", f"probability is not reduced for {case_id}")
        weight = weight_by_case[case_id]
        weight_numerator = weight["numerator"]
        weight_denominator = weight["denominator"]
        if weight_numerator < weight_denominator:
            fail("SAMPLING_WEIGHT_RANGE", f"weight is below one for {case_id}")
        if math.gcd(weight_numerator, weight_denominator) != 1:
            fail("SAMPLING_FRACTION_REDUCED", f"weight is not reduced for {case_id}")
        if numerator * weight_numerator != denominator * weight_denominator:
            fail("SAMPLING_RECIPROCAL", f"probability and weight are not reciprocal for {case_id}")
    return {"case_ids": probability_ids, "created_at": created_at}


def validate_truth_referents(schema: dict[str, Any], value: Any) -> dict[str, Any]:
    if type(value) is not list or not value or len(value) > 10000:
        fail("TRUTH_REFERENT_LIST", "truth referents must be a bounded non-empty list")
    claim_to_pair: dict[str, tuple[str, str]] = {}
    pair_to_claim: dict[tuple[str, str], str] = {}
    for index, row in enumerate(value):
        validate_instance(schema, row, f"truth_referents[{index}]")
        claim = row["claim_handle"]
        pair = (row["referent_handle"], row["predicate_handle"])
        if claim in claim_to_pair and claim_to_pair[claim] != pair:
            fail("TRUTH_CLAIM_COLLISION", f"claim handle {claim} maps to multiple pairs")
        if pair in pair_to_claim and pair_to_claim[pair] != claim:
            fail("TRUTH_PAIR_COLLISION", f"claim pair {pair} maps to multiple handles")
        if claim in claim_to_pair or pair in pair_to_claim:
            fail("TRUTH_DUPLICATE", f"duplicate truth referent row at {index}")
        claim_to_pair[claim] = pair
        pair_to_claim[pair] = claim
    return {
        "claim_handles": sorted(claim_to_pair),
        "predicate_handles": sorted({pair[1] for pair in pair_to_claim}),
        "referent_handles": sorted({pair[0] for pair in pair_to_claim}),
    }


def validate_fixture_value(
    fixture: Any,
    schemas: dict[str, dict[str, Any]],
    schema_hashes: dict[str, str],
) -> dict[str, int]:
    fixture = require_object(fixture, "synthetic fixture")
    require_exact_keys(
        fixture,
        {"boundary", "expected", "instances", "schema", "synthetic_only"},
        "synthetic fixture",
    )
    if fixture["schema"] != FIXTURE_SCHEMA or fixture["synthetic_only"] is not True:
        fail("FIXTURE_IDENTITY", "synthetic fixture identity drift")
    if fixture["boundary"] != {
        "authority_asserted": False,
        "condition_mapping_public": False,
        "credentials_present": False,
        "private_source_data_present": False,
        "real_run_authorized": False,
        "side_effects_unlocked": False,
    }:
        fail("FIXTURE_BOUNDARY", "synthetic fixture boundary drift")
    instances = require_object(fixture["instances"], "synthetic fixture.instances")
    require_exact_keys(
        instances,
        {"blind_map", "review_command", "sampling_receipt", "truth_referents"},
        "synthetic fixture.instances",
    )

    blind = instances["blind_map"]
    review = instances["review_command"]
    sampling = instances["sampling_receipt"]
    blind_result = validate_blind_map(schemas["blind_map"], blind)
    review_result = validate_review_command(schemas["review_command"], review)
    sampling_result = validate_sampling_receipt(
        schemas["sampling_receipt"], sampling, schema_hashes["sampling_receipt"]
    )
    truth_result = validate_truth_referents(
        schemas["truth_referents"], instances["truth_referents"]
    )

    if blind["trial_id"] != review["trial_id"] or blind["trial_id"] != sampling["trial_id"]:
        fail("CROSS_TRIAL", "trial identity differs across schema instances")
    if blind["contract_sha256"] != review["contract_sha256"] or blind["contract_sha256"] != sampling["contract_sha256"]:
        fail("CROSS_CONTRACT", "contract identity differs across schema instances")
    if blind["blind_packet_sha256"] != review["blind_packet_sha256"]:
        fail("CROSS_BLIND_PACKET", "review does not bind the blind packet")
    if blind["eligible_frame_manifest_sha256"] != sampling["eligible_frame_manifest_sha256"]:
        fail("CROSS_ELIGIBLE", "eligible frame identity differs")
    if blind["selected_case_manifest_sha256"] != sampling["selected_case_manifest_sha256"]:
        fail("CROSS_SELECTED", "selected case manifest identity differs")
    receipt_sha256 = sha256_bytes(canonical_pretty_bytes(sampling))
    if blind["sampling_receipt_sha256"] != receipt_sha256:
        fail("CROSS_RECEIPT_HASH", "blind map does not bind canonical sampling receipt bytes")
    if blind_result["case_ids"] != sampling_result["case_ids"]:
        fail("CROSS_CASE_ORDER", "blind map and sampling case order differ")
    if not (sampling_result["created_at"] < blind_result["created_at"] <= review_result["created_at"]):
        fail("CROSS_TIME_ORDER", "receipt/map/review creation order is invalid")

    prohibited_tokens = set(blind_result["answer_ids"]) | set(blind_result["condition_ids"])
    review_bytes = canonical_compact_bytes(review)
    sampling_bytes = canonical_compact_bytes(sampling)
    if any(token.encode("ascii") in review_bytes for token in prohibited_tokens):
        fail("CROSS_IDENTITY_LEAK", "review command leaks answer or condition identity")
    if any(token.encode("ascii") in sampling_bytes for token in prohibited_tokens):
        fail("CROSS_IDENTITY_LEAK", "sampling receipt leaks answer or condition identity")

    packet_ids = (
        set(blind_result["case_ids"])
        | set(blind_result["answer_ids"])
        | set(blind_result["condition_ids"])
    )
    if review_result["reviewer_slot"] in packet_ids:
        fail("CROSS_REVIEWER_COLLISION", "reviewer slot collides with a packet identifier")
    public_ids = packet_ids | {review_result["reviewer_slot"]}
    truth_ids = (
        set(truth_result["claim_handles"])
        | set(truth_result["predicate_handles"])
        | set(truth_result["referent_handles"])
    )
    if public_ids & truth_ids:
        fail("CROSS_NAMESPACE", "truth handles overlap another packet namespace")

    expected = {
        "answer_count": len(blind_result["answer_ids"]),
        "case_count": len(blind_result["case_ids"]),
        "condition_count_per_case": len(blind_result["condition_ids"]),
        "instance_schema_class_count": 4,
        "sampling_probability_row_count": len(sampling["case_inclusion_probabilities"]),
        "sampling_weight_row_count": len(sampling["case_sampling_weights"]),
        "truth_referent_count": len(instances["truth_referents"]),
    }
    if fixture["expected"] != expected:
        fail("FIXTURE_EXPECTED", "synthetic fixture expected metrics drift")
    return expected


def derive_next_frontier(graph: dict[str, Any], completed: set[str]) -> tuple[str, ...]:
    frontier: list[str] = []
    for node in graph["nodes"]:
        path = node["artifact_binding_path"]
        if path in completed or node["primary_readiness_class"] != "INDEPENDENT_PUBLIC":
            continue
        if set(node["local_dependencies"]).issubset(completed):
            frontier.append(path)
    return tuple(sorted(frontier))


def validate_manifest_value(
    root: Path,
    manifest: Any,
    fixture_raw: bytes,
    schemas: dict[str, dict[str, Any]],
    schema_raw: dict[str, bytes],
) -> dict[str, Any]:
    manifest = require_object(manifest, "pack manifest")
    require_exact_keys(
        manifest,
        {
            "admission_field_projection",
            "artifact_bindings",
            "baseline_commit",
            "boundary",
            "canonical_serialization",
            "date",
            "decision",
            "evidence_sha256",
            "graph_sha256",
            "graph_source_commit",
            "json_schema_dialect",
            "next_public_frontier",
            "s2_contract_schema_sha256",
            "sampling_receipt_required_bindings",
            "schema",
            "synthetic_fixture_path",
            "synthetic_fixture_sha256",
        },
        "pack manifest",
    )
    if manifest["schema"] != PACK_SCHEMA:
        fail("MANIFEST_SCHEMA", "pack schema drift")
    if manifest["baseline_commit"] != BASELINE_COMMIT:
        fail("MANIFEST_BASELINE", "pack baseline drift")
    if manifest["graph_source_commit"] != GRAPH_SOURCE_COMMIT or manifest["graph_sha256"] != GRAPH_SHA256:
        fail("MANIFEST_GRAPH", "graph identity drift")
    if manifest["s2_contract_schema_sha256"] != S2_SCHEMA_SHA256:
        fail("MANIFEST_S2", "S2 schema identity drift")
    if manifest["canonical_serialization"] != CANONICAL_SERIALIZATION:
        fail("MANIFEST_CANONICAL", "canonical serialization drift")
    if manifest["json_schema_dialect"] != DIALECT or manifest["decision"] != DECISION:
        fail("MANIFEST_DECISION", "dialect or decision drift")
    if manifest["synthetic_fixture_path"] != FIXTURE_PATH:
        fail("MANIFEST_FIXTURE", "synthetic fixture path drift")
    if manifest["synthetic_fixture_sha256"] != sha256_bytes(fixture_raw):
        fail("MANIFEST_FIXTURE_HASH", "synthetic fixture hash drift")
    if manifest["admission_field_projection"] != {
        "frame_o_excl_receipt_sha256": "SAMPLING_RECEIPT_INTERNAL_PRE_ENTROPY_FRAME_COMMITMENT",
        "seed_entropy_receipt_sha256": "sampling.sampling_seed_entropy_receipt_sha256",
    }:
        fail("MANIFEST_PROJECTION", "sampling field projection drift")

    bindings = manifest["artifact_bindings"]
    if type(bindings) is not list or len(bindings) != len(SCHEMA_CATALOG):
        fail("MANIFEST_BINDINGS", "artifact binding count drift")
    for record, entry in zip(bindings, SCHEMA_CATALOG, strict=True):
        require_exact_keys(
            require_object(record, "artifact binding"),
            {
                "binding_path",
                "provider_neutral",
                "repo_path",
                "schema_id",
                "sha256",
                "source_status",
                "unlocks_side_effect",
            },
            f"artifact binding {entry['binding_path']}",
        )
        expected = {
            "binding_path": entry["binding_path"],
            "provider_neutral": True,
            "repo_path": entry["path"],
            "schema_id": entry["schema_id"],
            "sha256": entry["sha256"],
            "source_status": "SOURCE_SCHEMA_IMPLEMENTED_NOT_LIVE_BOUND",
            "unlocks_side_effect": False,
        }
        if record != expected:
            fail("MANIFEST_BINDINGS", f"artifact binding drift for {entry['binding_path']}")
        if sha256_bytes(schema_raw[entry["key"]]) != entry["sha256"]:
            fail("SCHEMA_HASH", f"schema byte hash drift for {entry['key']}")

    if manifest["evidence_sha256"] != EXPECTED_EVIDENCE:
        fail("MANIFEST_EVIDENCE", "evidence hash catalog drift")
    for path, expected_sha in EXPECTED_EVIDENCE.items():
        if sha256_bytes(read_bytes(root, path)) != expected_sha:
            fail("EVIDENCE_HASH", f"evidence bytes drift: {path}")

    graph, _ = load_canonical(root, GRAPH_PATH)
    ledger, _ = load_canonical(root, LEDGER_PATH)
    admission, _ = load_canonical(root, ADMISSION_PATH)
    s2_contract = require_object(
        parse_json(read_bytes(root, S2_CONTRACT_PATH), S2_CONTRACT_PATH),
        "S2 contract",
    )
    del ledger
    completed = {entry["binding_path"] for entry in SCHEMA_CATALOG}
    if (
        set(graph["summary"]["recommended_first_pack"]) != completed
        or graph["summary"]["recommended_first_pack_count"] != len(completed)
    ):
        fail("GRAPH_RECOMMENDED_PACK", "foundational bindings differ from recommended first pack")
    graph_nodes = {node["artifact_binding_path"]: node for node in graph["nodes"]}
    if not completed.issubset(graph_nodes):
        fail("GRAPH_COVERAGE", "foundational binding is absent from graph")
    for path in completed:
        node = graph_nodes[path]
        if (
            node["primary_readiness_class"] != "INDEPENDENT_PUBLIC"
            or node["public_authoring_eligible"] is not True
            or node["local_dependencies"] != []
            or node["external_dependencies"] != []
            or node["blocked_upstream_dependencies"] != []
            or node["unrepresented_upstream_dependencies"] != []
            or node["binding_satisfied"] is not False
            or node["binding_evidence"] is not None
        ):
            fail("GRAPH_ROOT", f"graph root boundary drift: {path}")
    frontier = derive_next_frontier(graph, completed)
    if frontier != NEXT_FRONTIER or tuple(manifest["next_public_frontier"]) != frontier:
        fail("NEXT_FRONTIER", "derived next public frontier drift")

    contract_bindings = admission["sampling"]["sampling_receipt_required_bindings"]
    if set(contract_bindings) != set(SAMPLING_BINDINGS) or len(contract_bindings) != 18:
        fail("SAMPLING_BINDING_CONTRACT", "admission sampling binding contract drift")
    if tuple(manifest["sampling_receipt_required_bindings"]) != SAMPLING_BINDINGS:
        fail("SAMPLING_BINDING_MANIFEST", "manifest sampling binding list drift")
    sampling_required = set(schemas["sampling_receipt"]["required"])
    if sampling_required != set(SAMPLING_BINDINGS) | {"schema"}:
        fail("SAMPLING_SCHEMA_REQUIRED", "sampling schema must contain schema plus exact 18 bindings")

    if s2_contract["implementation_boundary"]["store_adapter"] is not False:
        fail("S2_BOUNDARY", "S2 unexpectedly claims a store adapter")
    if (
        s2_contract["implementation_boundary"]["real_capture_authorized"] is not False
        or s2_contract["implementation_boundary"]["biocortex_runtime_influence"] is not False
        or s2_contract["decision"] != "BLOCKED_FAIL_CLOSED"
    ):
        fail("S2_BOUNDARY", "S2 admission boundary drift")

    if manifest["boundary"] != {
        "admission_packet_mutated": False,
        "authority_true_count": 0,
        "graph_packet_mutated": False,
        "live_binding_satisfied_count": 0,
        "real_run_admitted": False,
        "s2_adapter_claimed": False,
        "schema_validated_count": 4,
        "side_effects_unlocked": "NONE",
        "source_artifact_count": 4,
    }:
        fail("MANIFEST_BOUNDARY", "non-authority boundary drift")
    return {"frontier": frontier, "graph": graph}


def load_inputs(root: Path) -> dict[str, Any]:
    manifest, manifest_raw = load_canonical(root, MANIFEST_PATH)
    fixture, fixture_raw = load_canonical(root, FIXTURE_PATH)
    schemas: dict[str, dict[str, Any]] = {}
    schema_raw: dict[str, bytes] = {}
    schema_metrics: dict[str, dict[str, int]] = {}
    for entry in SCHEMA_CATALOG:
        schema, raw = load_canonical(root, entry["path"])
        schema_metrics[entry["key"]] = validate_schema_document(schema, entry)
        if sha256_bytes(raw) != entry["sha256"]:
            fail("SCHEMA_HASH", f"schema byte hash drift for {entry['key']}")
        schemas[entry["key"]] = schema
        schema_raw[entry["key"]] = raw
    repeated_primitives = (
        ("label", ("blind_map", "review_command", "sampling_receipt")),
        ("sha256", ("blind_map", "review_command", "sampling_receipt")),
        ("utc", ("blind_map", "review_command", "sampling_receipt")),
        ("caseId", ("blind_map", "sampling_receipt")),
    )
    for definition_name, schema_keys in repeated_primitives:
        definitions = [
            schemas[key]["$defs"][definition_name]
            for key in schema_keys
        ]
        if any(definition != definitions[0] for definition in definitions[1:]):
            fail(
                "COMMON_PRIMITIVE_DRIFT",
                f"repeated primitive definition {definition_name} differs across schemas",
            )
    schema_hashes = {key: sha256_bytes(raw) for key, raw in schema_raw.items()}
    fixture_metrics = validate_fixture_value(fixture, schemas, schema_hashes)
    manifest_metrics = validate_manifest_value(
        root, manifest, fixture_raw, schemas, schema_raw
    )
    return {
        "fixture": fixture,
        "fixture_metrics": fixture_metrics,
        "fixture_raw": fixture_raw,
        "manifest": manifest,
        "manifest_metrics": manifest_metrics,
        "manifest_raw": manifest_raw,
        "schema_hashes": schema_hashes,
        "schema_metrics": schema_metrics,
        "schema_raw": schema_raw,
        "schemas": schemas,
    }


def receipt_rows(inputs: dict[str, Any]) -> list[tuple[str, Any]]:
    schema_hashes = inputs["schema_hashes"]
    schema_metrics = inputs["schema_metrics"]
    fixture_metrics = inputs["fixture_metrics"]
    schema_bytes = sum(len(raw) for raw in inputs["schema_raw"].values())
    ref_count = sum(row["ref_count"] for row in schema_metrics.values())
    object_count = sum(row["object_count"] for row in schema_metrics.values())
    artifact_catalog_sha256 = sha256_bytes(
        canonical_compact_bytes(inputs["manifest"]["artifact_bindings"])
    )
    return [
        ("schema", PACK_SCHEMA),
        ("baseline_commit", BASELINE_COMMIT),
        ("manifest_sha256", sha256_bytes(inputs["manifest_raw"])),
        ("synthetic_fixture_sha256", sha256_bytes(inputs["fixture_raw"])),
        ("artifact_catalog_sha256", artifact_catalog_sha256),
        ("graph_sha256", GRAPH_SHA256),
        ("s2_contract_schema_sha256", S2_SCHEMA_SHA256),
        ("schema_count", 4),
        ("schema_total_bytes", schema_bytes),
        ("schema_object_count", object_count),
        ("local_ref_count", ref_count),
        ("remote_ref_count", 0),
        ("unresolved_ref_count", 0),
        ("open_object_schema_count", 0),
        ("unknown_schema_keyword_count", 0),
        ("common_primitive_drift_count", 0),
        ("blind_map_schema_sha256", schema_hashes["blind_map"]),
        ("review_command_schema_sha256", schema_hashes["review_command"]),
        ("sampling_receipt_schema_sha256", schema_hashes["sampling_receipt"]),
        ("truth_referent_schema_sha256", schema_hashes["truth_referents"]),
        ("evidence_input_count", len(EXPECTED_EVIDENCE)),
        ("positive_schema_class_count", 4),
        ("positive_instance_count", 5),
        ("cross_schema_positive_control_passed", True),
        ("sampling_required_binding_count", len(SAMPLING_BINDINGS)),
        ("synthetic_case_count", fixture_metrics["case_count"]),
        ("synthetic_answer_count", fixture_metrics["answer_count"]),
        ("synthetic_truth_referent_count", fixture_metrics["truth_referent_count"]),
        ("next_public_frontier_count", len(NEXT_FRONTIER)),
        ("source_artifact_count", 4),
        ("schema_validated_count", 4),
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
    name: str, expected_code: str, callback: Callable[[], None]
) -> None:
    try:
        callback()
    except CheckError as exc:
        if exc.code != expected_code:
            fail(
                "SELF_TEST_WRONG_CODE",
                f"{name} expected {expected_code}, observed {exc.code}: {exc}",
            )
        return
    fail("SELF_TEST_ACCEPTED", f"mutation {name} was accepted")


def run_self_test(root: Path, inputs: dict[str, Any]) -> tuple[int, int, int]:
    schemas = inputs["schemas"]
    schema_hashes = inputs["schema_hashes"]
    fixture = inputs["fixture"]
    manifest = inputs["manifest"]
    fixture_raw = inputs["fixture_raw"]
    schema_raw = inputs["schema_raw"]
    schema_mutations = 0
    fixture_mutations = 0
    source_mutations = 0

    def schema_case(
        name: str,
        key: str,
        expected: str,
        mutate: Callable[[dict[str, Any]], None],
    ) -> None:
        nonlocal schema_mutations
        trial = copy.deepcopy(schemas[key])
        mutate(trial)
        entry = next(row for row in SCHEMA_CATALOG if row["key"] == key)
        expect_rejection(name, expected, lambda: validate_schema_document(trial, entry))
        schema_mutations += 1

    schema_case(
        "remote-ref",
        "blind_map",
        "REF_POLICY",
        lambda x: x["properties"].__setitem__("trial_id", {"$ref": "https://example.invalid/schema"}),
    )
    schema_case(
        "relative-ref",
        "blind_map",
        "REF_POLICY",
        lambda x: x["properties"].__setitem__("trial_id", {"$ref": "other.json#/$defs/label"}),
    )
    schema_case(
        "unresolved-ref",
        "blind_map",
        "REF_UNRESOLVED",
        lambda x: x["properties"].__setitem__("trial_id", {"$ref": "#/$defs/missing"}),
    )
    schema_case(
        "dynamic-ref",
        "blind_map",
        "SCHEMA_KEYWORD",
        lambda x: x["properties"].__setitem__("trial_id", {"$dynamicRef": "#label"}),
    )
    schema_case(
        "open-object-additional",
        "blind_map",
        "OBJECT_OPEN",
        lambda x: x.__setitem__("additionalProperties", True),
    )
    schema_case(
        "open-object-unevaluated",
        "blind_map",
        "OBJECT_OPEN",
        lambda x: x.pop("unevaluatedProperties"),
    )
    schema_case(
        "unknown-keyword",
        "blind_map",
        "SCHEMA_KEYWORD",
        lambda x: x.__setitem__("default", {}),
    )
    schema_case(
        "missing-required",
        "blind_map",
        "OBJECT_REQUIRED",
        lambda x: x["required"].remove("trial_id"),
    )
    schema_case(
        "unused-definition",
        "blind_map",
        "DEF_UNUSED",
        lambda x: x["$defs"].__setitem__(
            "unused", {"maxLength": 1, "minLength": 1, "pattern": "^x$", "type": "string"}
        ),
    )
    schema_case(
        "ref-sibling",
        "blind_map",
        "REF_SIBLING",
        lambda x: x["properties"]["trial_id"].__setitem__("description", "drift"),
    )
    schema_case(
        "dialect-drift",
        "blind_map",
        "SCHEMA_DIALECT",
        lambda x: x.__setitem__("$schema", "https://json-schema.org/draft/2019-09/schema"),
    )
    schema_case(
        "id-drift",
        "blind_map",
        "SCHEMA_ID",
        lambda x: x.__setitem__("$id", "urn:drift"),
    )
    schema_case(
        "combiner",
        "blind_map",
        "SCHEMA_KEYWORD",
        lambda x: x.__setitem__("allOf", []),
    )
    schema_case(
        "content-encoding",
        "review_command",
        "SCHEMA_KEYWORD",
        lambda x: x["properties"]["argv"]["items"].__setitem__("contentEncoding", "base64"),
    )

    def fixture_case(
        name: str, expected: str, mutate: Callable[[dict[str, Any]], None]
    ) -> None:
        nonlocal fixture_mutations
        trial = copy.deepcopy(fixture)
        mutate(trial)
        expect_rejection(
            name,
            expected,
            lambda: validate_fixture_value(trial, schemas, schema_hashes),
        )
        fixture_mutations += 1

    def reseal_receipt(value: dict[str, Any]) -> None:
        receipt = value["instances"]["sampling_receipt"]
        value["instances"]["blind_map"]["sampling_receipt_sha256"] = sha256_bytes(
            canonical_pretty_bytes(receipt)
        )

    fixture_case(
        "blind-duplicate-answer",
        "BLIND_ANSWER_DUPLICATE",
        lambda x: x["instances"]["blind_map"]["cases"][1]["assignments"][0].__setitem__(
            "answer_id", x["instances"]["blind_map"]["cases"][0]["assignments"][0]["answer_id"]
        ),
    )
    fixture_case(
        "blind-duplicate-condition",
        "BLIND_CONDITION_BIJECTION",
        lambda x: x["instances"]["blind_map"]["cases"][0]["assignments"][1].__setitem__(
            "condition_id", x["instances"]["blind_map"]["cases"][0]["assignments"][0]["condition_id"]
        ),
    )
    fixture_case(
        "blind-condition-roster",
        "BLIND_CONDITION_ROSTER",
        lambda x: x["instances"]["blind_map"]["cases"][1]["assignments"][1].__setitem__(
            "condition_id", "cond_cccccccccccccccccccccccccccccccc"
        ),
    )
    fixture_case(
        "blind-duplicate-case",
        "BLIND_CASE_DUPLICATE",
        lambda x: x["instances"]["blind_map"]["cases"][1].__setitem__(
            "case_id", x["instances"]["blind_map"]["cases"][0]["case_id"]
        ),
    )
    fixture_case(
        "blind-raw-seed",
        "INSTANCE_EXTRA",
        lambda x: x["instances"]["blind_map"].__setitem__("blind_seed", "secret"),
    )
    fixture_case(
        "blind-unblind",
        "INSTANCE_CONST",
        lambda x: x["instances"]["blind_map"]["boundary"].__setitem__("unblinding_allowed", True),
    )
    fixture_case(
        "blind-answer-leak",
        "INSTANCE_STRING_BOUND",
        lambda x: x["instances"]["blind_map"]["cases"][0]["assignments"][0].__setitem__(
            "answer_id", "ans_reference"
        ),
    )
    fixture_case(
        "cross-trial",
        "CROSS_TRIAL",
        lambda x: x["instances"]["review_command"].__setitem__("trial_id", "trial_drift"),
    )
    fixture_case(
        "cross-contract",
        "CROSS_CONTRACT",
        lambda x: x["instances"]["review_command"].__setitem__("contract_sha256", "1" * 64),
    )
    fixture_case(
        "cross-receipt-hash",
        "CROSS_RECEIPT_HASH",
        lambda x: x["instances"]["blind_map"].__setitem__("sampling_receipt_sha256", "1" * 64),
    )
    fixture_case(
        "cross-eligible",
        "CROSS_ELIGIBLE",
        lambda x: x["instances"]["blind_map"].__setitem__("eligible_frame_manifest_sha256", "1" * 64),
    )
    fixture_case(
        "cross-selected",
        "CROSS_SELECTED",
        lambda x: x["instances"]["blind_map"].__setitem__("selected_case_manifest_sha256", "1" * 64),
    )
    fixture_case(
        "cross-blind-packet",
        "CROSS_BLIND_PACKET",
        lambda x: x["instances"]["review_command"].__setitem__("blind_packet_sha256", "1" * 64),
    )
    fixture_case(
        "cross-case-order",
        "CROSS_CASE_ORDER",
        lambda x: x["instances"]["blind_map"]["cases"].reverse(),
    )

    fixture_case(
        "review-shell",
        "REVIEW_SHELL",
        lambda x: x["instances"]["review_command"]["argv"].__setitem__(0, "/bin/sh"),
    )
    fixture_case(
        "review-empty-executable",
        "REVIEW_EXECUTABLE_EMPTY",
        lambda x: x["instances"]["review_command"]["argv"].__setitem__(0, ""),
    )
    fixture_case(
        "review-control",
        "INSTANCE_PATTERN",
        lambda x: x["instances"]["review_command"]["argv"].__setitem__(1, "bad\nflag"),
    )
    fixture_case(
        "review-environment",
        "INSTANCE_MAX_ITEMS",
        lambda x: x["instances"]["review_command"]["context_environment_keys"].append("path"),
    )
    fixture_case(
        "reviewer-packet-id-collision",
        "CROSS_REVIEWER_COLLISION",
        lambda x: x["instances"]["review_command"].__setitem__(
            "reviewer_slot", x["instances"]["blind_map"]["cases"][0]["case_id"]
        ),
    )
    for field in (
        "authorizes_execution",
        "automatic_retry",
        "condition_mapping_present",
        "contains_credentials",
        "external_fact_access",
        "mcp_access",
        "parent_environment_inherited",
        "postprocessing_applied",
        "project_access",
        "raw_private_input_present",
        "repository_access",
        "tool_access",
        "unblinding_allowed",
    ):
        fixture_case(
            f"review-boundary-{field}",
            "INSTANCE_CONST",
            lambda x, field=field: x["instances"]["review_command"]["boundary"].__setitem__(field, True),
        )
    fixture_case(
        "review-response-exists",
        "INSTANCE_CONST",
        lambda x: x["instances"]["review_command"].__setitem__("response_sink_must_not_exist", False),
    )
    fixture_case(
        "review-retry",
        "INSTANCE_CONST",
        lambda x: x["instances"]["review_command"].__setitem__("retry_policy", "ONE_RETRY"),
    )
    fixture_case(
        "review-shell-mode",
        "INSTANCE_CONST",
        lambda x: x["instances"]["review_command"].__setitem__("argv_execution", "SHELL"),
    )
    fixture_case(
        "review-identity-leak",
        "CROSS_IDENTITY_LEAK",
        lambda x: x["instances"]["review_command"]["argv"].append(
            x["instances"]["blind_map"]["cases"][0]["assignments"][0]["condition_id"]
        ),
    )

    for field in SAMPLING_BINDINGS:
        fixture_case(
            f"sampling-missing-{field}",
            "INSTANCE_REQUIRED",
            lambda x, field=field: x["instances"]["sampling_receipt"].pop(field),
        )
    fixture_case(
        "sampling-bool",
        "INSTANCE_TYPE",
        lambda x: x["instances"]["sampling_receipt"]["case_inclusion_probabilities"][0].__setitem__("numerator", True),
    )
    fixture_case(
        "sampling-float",
        "INSTANCE_TYPE",
        lambda x: x["instances"]["sampling_receipt"]["case_inclusion_probabilities"][0].__setitem__("numerator", 0.25),
    )
    fixture_case(
        "sampling-zero",
        "INSTANCE_MINIMUM",
        lambda x: x["instances"]["sampling_receipt"]["case_inclusion_probabilities"][0].__setitem__("numerator", 0),
    )

    def mutate_and_reseal(
        value: dict[str, Any], callback: Callable[[dict[str, Any]], None]
    ) -> None:
        callback(value)
        reseal_receipt(value)

    fixture_case(
        "sampling-probability-range",
        "SAMPLING_PROBABILITY_RANGE",
        lambda x: mutate_and_reseal(
            x,
            lambda y: y["instances"]["sampling_receipt"]["case_inclusion_probabilities"][0].update(
                {"numerator": 5, "denominator": 4}
            ),
        ),
    )
    fixture_case(
        "sampling-weight-range",
        "SAMPLING_WEIGHT_RANGE",
        lambda x: mutate_and_reseal(
            x,
            lambda y: y["instances"]["sampling_receipt"]["case_sampling_weights"][0].update(
                {"numerator": 1, "denominator": 4}
            ),
        ),
    )
    fixture_case(
        "sampling-unreduced",
        "SAMPLING_FRACTION_REDUCED",
        lambda x: mutate_and_reseal(
            x,
            lambda y: y["instances"]["sampling_receipt"]["case_inclusion_probabilities"][0].update(
                {"numerator": 2, "denominator": 8}
            ),
        ),
    )
    fixture_case(
        "sampling-nonreciprocal",
        "SAMPLING_RECIPROCAL",
        lambda x: mutate_and_reseal(
            x,
            lambda y: y["instances"]["sampling_receipt"]["case_sampling_weights"][0].update(
                {"numerator": 3, "denominator": 1}
            ),
        ),
    )
    fixture_case(
        "sampling-duplicate-probability-case",
        "SAMPLING_PROBABILITY_CASE_DUPLICATE",
        lambda x: mutate_and_reseal(
            x,
            lambda y: y["instances"]["sampling_receipt"]["case_inclusion_probabilities"][1].update(
                {
                    "case_id": y["instances"]["sampling_receipt"]["case_inclusion_probabilities"][0]["case_id"],
                    "denominator": 3,
                }
            ),
        ),
    )
    fixture_case(
        "sampling-case-order",
        "SAMPLING_CASE_ORDER",
        lambda x: mutate_and_reseal(
            x, lambda y: y["instances"]["sampling_receipt"]["case_sampling_weights"].reverse()
        ),
    )
    fixture_case(
        "sampling-case-set",
        "SAMPLING_CASE_SET",
        lambda x: mutate_and_reseal(
            x,
            lambda y: y["instances"]["sampling_receipt"]["case_sampling_weights"][1].__setitem__(
                "case_id", "case_00000000000000000000000000000003"
            ),
        ),
    )
    fixture_case(
        "sampling-schema-hash",
        "SAMPLING_SCHEMA_HASH",
        lambda x: x["instances"]["sampling_receipt"].__setitem__("receipt_schema_sha256", "1" * 64),
    )
    fixture_case(
        "sampling-domain",
        "INSTANCE_CONST",
        lambda x: x["instances"]["sampling_receipt"].__setitem__("sampling_selection_domain", "drift"),
    )
    fixture_case(
        "sampling-message",
        "INSTANCE_CONST",
        lambda x: x["instances"]["sampling_receipt"].__setitem__("sampling_selection_message", "drift"),
    )
    fixture_case(
        "sampling-late-receipt",
        "INSTANCE_CONST",
        lambda x: x["instances"]["sampling_receipt"].__setitem__("receipt_precedes_first_condition_output", False),
    )
    fixture_case(
        "sampling-answer-grain",
        "INSTANCE_PATTERN",
        lambda x: mutate_and_reseal(
            x,
            lambda y: (
                y["instances"]["sampling_receipt"]["case_inclusion_probabilities"][0].__setitem__(
                    "case_id", "ans__aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                ),
                y["instances"]["sampling_receipt"]["case_sampling_weights"][0].__setitem__(
                    "case_id", "ans__aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                ),
            ),
        ),
    )

    fixture_case(
        "truth-value-field",
        "INSTANCE_EXTRA",
        lambda x: x["instances"]["truth_referents"][0].__setitem__("value", "raw"),
    )
    fixture_case(
        "truth-memory-key-field",
        "INSTANCE_EXTRA",
        lambda x: x["instances"]["truth_referents"][0].__setitem__("memory_key", "secret"),
    )
    fixture_case(
        "truth-authority-field",
        "INSTANCE_EXTRA",
        lambda x: x["instances"]["truth_referents"][0].__setitem__("truth_tier", "authoritative"),
    )
    fixture_case(
        "truth-bad-referent-namespace",
        "INSTANCE_STRING_BOUND",
        lambda x: x["instances"]["truth_referents"][0].__setitem__("referent_handle", "memory_key"),
    )
    fixture_case(
        "truth-unicode",
        "INSTANCE_STRING_BOUND",
        lambda x: x["instances"]["truth_referents"][0].__setitem__("predicate_handle", "prd_é"),
    )
    fixture_case(
        "truth-missing-predicate",
        "INSTANCE_REQUIRED",
        lambda x: x["instances"]["truth_referents"][0].pop("predicate_handle"),
    )
    fixture_case(
        "truth-claim-collision",
        "TRUTH_CLAIM_COLLISION",
        lambda x: x["instances"]["truth_referents"][1].__setitem__(
            "claim_handle", x["instances"]["truth_referents"][0]["claim_handle"]
        ),
    )
    fixture_case(
        "truth-pair-collision",
        "TRUTH_PAIR_COLLISION",
        lambda x: x["instances"]["truth_referents"][1].update(
            {
                "referent_handle": x["instances"]["truth_referents"][0]["referent_handle"],
                "predicate_handle": x["instances"]["truth_referents"][0]["predicate_handle"],
            }
        ),
    )

    def source_case(
        name: str, expected: str, mutate: Callable[[dict[str, Any]], None]
    ) -> None:
        nonlocal source_mutations
        trial = copy.deepcopy(manifest)
        mutate(trial)
        expect_rejection(
            name,
            expected,
            lambda: validate_manifest_value(
                root, trial, fixture_raw, schemas, schema_raw
            ),
        )
        source_mutations += 1

    source_case(
        "manifest-baseline",
        "MANIFEST_BASELINE",
        lambda x: x.__setitem__("baseline_commit", "0" * 40),
    )
    source_case(
        "manifest-artifact-hash",
        "MANIFEST_BINDINGS",
        lambda x: x["artifact_bindings"][0].__setitem__("sha256", "0" * 64),
    )
    source_case(
        "manifest-fixture-hash",
        "MANIFEST_FIXTURE_HASH",
        lambda x: x.__setitem__("synthetic_fixture_sha256", "0" * 64),
    )
    source_case(
        "manifest-evidence-hash",
        "MANIFEST_EVIDENCE",
        lambda x: x["evidence_sha256"].__setitem__(GRAPH_PATH, "0" * 64),
    )
    source_case(
        "manifest-live-binding",
        "MANIFEST_BOUNDARY",
        lambda x: x["boundary"].__setitem__("live_binding_satisfied_count", 1),
    )
    source_case(
        "manifest-authority",
        "MANIFEST_BOUNDARY",
        lambda x: x["boundary"].__setitem__("authority_true_count", 1),
    )
    source_case(
        "manifest-real-run",
        "MANIFEST_BOUNDARY",
        lambda x: x["boundary"].__setitem__("real_run_admitted", True),
    )
    source_case(
        "manifest-next-frontier",
        "NEXT_FRONTIER",
        lambda x: x["next_public_frontier"].pop(),
    )
    source_case(
        "manifest-sampling-binding",
        "SAMPLING_BINDING_MANIFEST",
        lambda x: x["sampling_receipt_required_bindings"].pop(),
    )
    source_case(
        "manifest-s2-adapter",
        "MANIFEST_BOUNDARY",
        lambda x: x["boundary"].__setitem__("s2_adapter_claimed", True),
    )

    return schema_mutations, fixture_mutations, source_mutations


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
        schema_count, fixture_count, source_count = run_self_test(root, inputs)
        total = schema_count + fixture_count + source_count
        print(
            "SELF_TEST_OK"
            f"\tschema_mutations_rejected={schema_count}"
            f"\tfixture_mutations_rejected={fixture_count}"
            f"\tsource_mutations_rejected={source_count}"
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
