#!/usr/bin/env python3
"""Provider-neutral Track B strict-case rule over exact blind artifacts.

This module computes a deterministic rule result at ``case_id × opaque
answer_id`` grain.  It never reads a condition map, applies sampling weights,
validates review provenance, creates a score claim, or authorizes unblinding.
The three deterministic answer gates are explicit input rows because the
current truth-manifest schema binds their evidence digests but does not contain
runtime gate outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DIALECT = "https://json-schema.org/draft/2020-12/schema"
REVIEW_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-review-schema-v0.json"
REVIEW_SCHEMA_SHA256 = "2745cd373d4f99cdd4bb3d0bc9d9087966adb3a9d0594749cb1150b90d1e9422"
TRUTH_SCHEMA_PATH = "docs/design/fixtures/biocortex-ab-track-b-truth-manifest-schema-v0.json"
TRUTH_SCHEMA_SHA256 = "520070d1eb4852fd2a005d63b3d087769b3240902289ff5c44f11c109bd1cde6"
REFERENT_SCHEMA_SHA256 = "5da057e70675cbd259e0d1beb98039d2eee8589c73aa910f92f90cb0374545a8"
RESULT_SCHEMA = "agent_bridge.biocortex_ab_track_b_strict_case_validation_result.v0"
TRUTH_GATE_SCHEMA = "agent_bridge.biocortex_ab_track_b_strict_case_truth_gate_input.v0"

MAX_SINGLE_INPUT_BYTES = 32 * 1024 * 1024
MAX_TOTAL_INPUT_BYTES = 64 * 1024 * 1024
MAX_CASES = 4096
MAX_ANSWERS = 262144
MAX_REVIEWER_EVALUATIONS = 524288
MAX_TOTAL_CLAIM_SCORES = 1048576
MAX_OUTPUT_BYTES = 32 * 1024 * 1024

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")

FAILURE_RULE_ORDER = (
    "AUTHORITY_MISSING",
    "GOLD_RECALL_INCOMPLETE",
    "CURRENT_REFERENT_INCORRECT",
    "REVIEW_RESPONSE_MODE",
    "REVIEW_ABSTENTION_ASSESSMENT",
    "REVIEW_CLAIM_SCORE",
    "REVIEW_CURRENTNESS",
    "REVIEW_FORBIDDEN_ASSERTION",
    "REVIEW_UNSUPPORTED_ASSERTION",
    "REVIEW_USEFULNESS",
)


class StrictCaseError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise StrictCaseError(code, message)


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


def parse_json(raw: bytes, label: str) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        fail("JSON_BOM", f"{label} has a UTF-8 BOM")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("JSON_UTF8", f"{label} is not UTF-8: {exc}")
    try:
        value = json.loads(
            text,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_pairs,
        )
    except json.JSONDecodeError as exc:
        fail("JSON_PARSE", f"{label} is malformed: {exc}")
    if raw != canonical_pretty_bytes(value):
        fail("JSON_CANONICAL", f"{label} is not canonical pretty JSON")
    return value


def read_limited(path: Path, label: str, maximum: int = MAX_SINGLE_INPUT_BYTES) -> bytes:
    try:
        size = path.stat().st_size
        if size < 0 or size > maximum:
            fail("INPUT_SIZE", f"{label} exceeds {maximum} bytes")
        raw = path.read_bytes()
    except OSError as exc:
        fail("INPUT_READ", f"cannot read {label}: {exc}")
    if len(raw) != size:
        fail("INPUT_RACE", f"{label} changed while being read")
    return raw


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


def require_label(value: Any, label: str) -> str:
    if type(value) is not str or LABEL_RE.fullmatch(value) is None:
        fail("LABEL", f"{label} must be a canonical label")
    return value


def require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        fail("TYPE_BOOL", f"{label} must be Boolean")
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


def validate_instance(schema: dict[str, Any], value: Any, path: str) -> None:
    definitions = require_object(schema.get("$defs"), "schema.$defs")

    def check(node: dict[str, Any], item: Any, item_path: str) -> None:
        if "$ref" in node:
            ref = node["$ref"]
            if type(ref) is not str or not ref.startswith("#/$defs/"):
                fail("SCHEMA_REF", f"{item_path} uses an unsupported schema ref")
            name = ref.rsplit("/", 1)[1]
            if name not in definitions:
                fail("SCHEMA_REF", f"{item_path} references missing definition")
            check(require_object(definitions[name], f"schema.$defs.{name}"), item, item_path)
            return
        if "const" in node:
            expected = node["const"]
            if type(item) is not type(expected) or item != expected:
                fail("INSTANCE_CONST", f"{item_path} must equal {expected!r}")
            return
        schema_type = node.get("type")
        if schema_type == "object":
            if type(item) is not dict:
                fail("INSTANCE_TYPE", f"{item_path} must be an object")
            properties = require_object(node.get("properties"), f"{item_path}.properties")
            required = node.get("required")
            if type(required) is not list:
                fail("SCHEMA_REQUIRED", f"{item_path} schema required list is absent")
            missing = set(required) - set(item)
            extra = set(item) - set(properties)
            if missing:
                fail("INSTANCE_REQUIRED", f"{item_path} missing {sorted(missing)}")
            if extra:
                fail("INSTANCE_EXTRA", f"{item_path} has extra {sorted(extra)}")
            for key in required:
                check(require_object(properties[key], f"schema property {key}"), item[key], f"{item_path}.{key}")
        elif schema_type == "array":
            if type(item) is not list:
                fail("INSTANCE_TYPE", f"{item_path} must be an array")
            minimum = node.get("minItems", 0)
            maximum = node.get("maxItems")
            if type(minimum) is not int or type(maximum) is not int:
                fail("SCHEMA_ARRAY", f"{item_path} schema array bounds are absent")
            if not minimum <= len(item) <= maximum:
                fail("INSTANCE_ARRAY_BOUND", f"{item_path} length is outside bounds")
            if node.get("uniqueItems"):
                identities = [canonical_compact_bytes(row) for row in item]
                if len(identities) != len(set(identities)):
                    fail("INSTANCE_UNIQUE", f"{item_path} has duplicate rows")
            child = require_object(node.get("items"), f"{item_path}.items")
            for index, row in enumerate(item):
                check(child, row, f"{item_path}[{index}]")
        elif schema_type == "string":
            if type(item) is not str:
                fail("INSTANCE_TYPE", f"{item_path} must be a string")
            minimum = node.get("minLength")
            maximum = node.get("maxLength")
            pattern = node.get("pattern")
            if type(minimum) is not int or type(maximum) is not int or type(pattern) is not str:
                fail("SCHEMA_STRING", f"{item_path} schema string bounds are absent")
            if not minimum <= len(item) <= maximum:
                fail("INSTANCE_STRING_BOUND", f"{item_path} length is outside bounds")
            if re.fullmatch(pattern, item, re.ASCII) is None:
                fail("INSTANCE_PATTERN", f"{item_path} does not match its pattern")
        elif schema_type == "integer":
            if type(item) is not int:
                fail("INSTANCE_TYPE", f"{item_path} must be an integer, not bool/float")
            minimum = node.get("minimum")
            maximum = node.get("maximum")
            if type(minimum) is not int or type(maximum) is not int:
                fail("SCHEMA_INTEGER", f"{item_path} schema integer bounds are absent")
            if not minimum <= item <= maximum:
                fail("INSTANCE_INTEGER_BOUND", f"{item_path} is outside bounds")
        else:
            fail("SCHEMA_TYPE", f"{item_path} uses unsupported schema type {schema_type!r}")

    check(schema, value, path)


def load_frozen_schema(root: Path, relative: str, expected_sha256: str) -> dict[str, Any]:
    path = root.joinpath(*Path(relative).parts)
    raw = read_limited(path, relative, maximum=1024 * 1024)
    if sha256_bytes(raw) != expected_sha256:
        fail("SCHEMA_HASH", f"{relative} hash drift")
    schema = require_object(parse_json(raw, relative), relative)
    if schema.get("$schema") != DIALECT:
        fail("SCHEMA_DIALECT", f"{relative} dialect drift")
    return schema


def referent_tuple(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        value["claim_handle"],
        value["referent_handle"],
        value["predicate_handle"],
    )


def validate_truth_manifest(schema: dict[str, Any], value: Any) -> dict[str, Any]:
    validate_instance(schema, value, "truth_manifest")
    value = require_object(value, "truth_manifest")
    if value["referent_schema_sha256"] != REFERENT_SCHEMA_SHA256:
        fail("TRUTH_REFERENT_SCHEMA", "truth manifest referent schema hash drift")
    as_of = require_utc(value["truth_as_of_utc"], "truth.truth_as_of_utc")
    cutoff = require_utc(value["knowledge_cutoff_utc"], "truth.knowledge_cutoff_utc")
    created = require_utc(value["created_at_utc"], "truth.created_at_utc")
    if not as_of <= cutoff <= created:
        fail("TRUTH_TIME_ORDER", "truth_as_of <= cutoff <= created is required")
    cases = require_array(value["cases"], "truth.cases")
    if len(cases) > MAX_CASES:
        fail("TRUTH_RESOURCE", "truth case count exceeds the cap")

    case_order: list[str] = []
    case_map: dict[str, dict[str, Any]] = {}
    claim_to_pair: dict[str, tuple[str, str]] = {}
    pair_to_claim: dict[tuple[str, str], str] = {}
    all_required: set[str] = set()
    all_forbidden: set[str] = set()
    packet_handles: set[str] = set()

    for case in cases:
        case_id = case["case_id"]
        if case_id in case_map:
            fail("TRUTH_CASE_DUPLICATE", f"truth repeats {case_id}")
        case_order.append(case_id)
        packet_handles.add(case_id)
        score_referents: list[tuple[str, str, str]] = []
        case_forbidden: set[str] = set()
        for rubric in case["claim_rubrics"]:
            identity = referent_tuple(rubric["referent"])
            claim, referent, predicate = identity
            pair = (referent, predicate)
            if claim in claim_to_pair:
                fail("TRUTH_CLAIM_DUPLICATE", f"truth repeats claim {claim}")
            if pair in pair_to_claim:
                fail("TRUTH_PAIR_DUPLICATE", f"truth repeats referent/predicate {pair}")
            claim_to_pair[claim] = pair
            pair_to_claim[pair] = claim
            packet_handles.update(identity)
            required = [row["assertion_handle"] for row in rubric["required_assertions"]]
            forbidden = [row["assertion_handle"] for row in rubric["forbidden_assertions"]]
            if len(required) != len(set(required)) or len(forbidden) != len(set(forbidden)):
                fail("TRUTH_ASSERTION_DUPLICATE", "truth repeats an assertion in one rubric")
            if set(required) & set(forbidden):
                fail("TRUTH_ASSERTION_OVERLAP", "required and forbidden assertions overlap")
            if all_required & set(required) or all_forbidden & set(forbidden):
                fail("TRUTH_ASSERTION_DUPLICATE", "truth assertion handle is globally repeated")
            all_required.update(required)
            all_forbidden.update(forbidden)
            packet_handles.update(required)
            packet_handles.update(forbidden)
            case_forbidden.update(forbidden)
            if rubric["review_requirement"] == "score":
                if not required:
                    fail("TRUTH_SCORE_RUBRIC", "score rubric requires an assertion")
                score_referents.append(identity)
            else:
                if required or not forbidden:
                    fail("TRUTH_CONTEXT_RUBRIC", "context-only rubric requires only forbidden assertions")
        expected_mode = case["expected_response_mode"]
        if expected_mode == "answer" and not score_referents:
            fail("TRUTH_ANSWER_CASE", "answer case has no score rubric")
        if expected_mode == "abstain" and score_referents:
            fail("TRUTH_ABSTAIN_CASE", "abstention case has a score rubric")
        case_map[case_id] = {
            "expected_response_mode": expected_mode,
            "score_referents": score_referents,
            "forbidden_assertions": case_forbidden,
        }
    if all_required & all_forbidden:
        fail("TRUTH_ASSERTION_GLOBAL_OVERLAP", "required/forbidden handles overlap globally")
    packet_handles.add(value["trial_id"])
    return {
        "case_order": case_order,
        "case_map": case_map,
        "packet_handles": packet_handles,
    }


def expected_abstention_assessment(expected_mode: str, observed_mode: str) -> str:
    if expected_mode == "answer" and observed_mode == "answer":
        return "not_required"
    if expected_mode == "abstain" and observed_mode == "abstain":
        return "pass"
    return "fail"


def validate_review(
    schema: dict[str, Any],
    value: Any,
    truth: dict[str, Any],
    truth_raw: bytes,
    truth_info: dict[str, Any],
) -> dict[str, Any]:
    validate_instance(schema, value, "review")
    value = require_object(value, "review")
    for field in ("trial_id", "contract_sha256"):
        if value[field] != truth[field]:
            fail("REVIEW_IDENTITY", f"review {field} differs from truth manifest")
    if value["truth_manifest_sha256"] != sha256_bytes(truth_raw):
        fail("REVIEW_TRUTH_HASH", "review does not bind exact truth-manifest bytes")
    if value["referent_schema_sha256"] != REFERENT_SCHEMA_SHA256:
        fail("REVIEW_REFERENT_SCHEMA", "review referent schema hash drift")
    cases = value["cases"]
    observed_case_order = [case["case_id"] for case in cases]
    if observed_case_order != truth_info["case_order"]:
        fail("REVIEW_CASE_ORDER", "review case order/set differs from truth")
    if len(observed_case_order) != len(set(observed_case_order)):
        fail("REVIEW_CASE_DUPLICATE", "review repeats a case")

    seen_answers: set[str] = set()
    answer_order: list[tuple[str, str]] = []
    answer_map: dict[tuple[str, str], dict[str, Any]] = {}
    claim_score_count = 0
    for review_case in cases:
        case_id = review_case["case_id"]
        truth_case = truth_info["case_map"][case_id]
        local_answers: set[str] = set()
        for answer in review_case["answers"]:
            answer_id = answer["answer_id"]
            if answer_id in local_answers or answer_id in seen_answers:
                fail("REVIEW_ANSWER_DUPLICATE", "review repeats an answer id")
            local_answers.add(answer_id)
            seen_answers.add(answer_id)
            answer_order.append((case_id, answer_id))
            answer_map[(case_id, answer_id)] = answer
            observed_referents = [referent_tuple(row["referent"]) for row in answer["claim_scores"]]
            if len(observed_referents) != len(set(observed_referents)):
                fail("REVIEW_CLAIM_DUPLICATE", "review repeats a claim score")
            if observed_referents != truth_case["score_referents"]:
                fail("REVIEW_CLAIM_COVERAGE", "review claim score order/set differs from truth")
            claim_score_count += len(observed_referents)
            forbidden = answer["matched_forbidden_assertion_handles"]
            if len(forbidden) != len(set(forbidden)):
                fail("REVIEW_FORBIDDEN_DUPLICATE", "review repeats a forbidden handle")
            if answer["matched_forbidden_assertion_count"] != len(forbidden):
                fail("REVIEW_FORBIDDEN_COUNT", "forbidden count differs from handles")
            if not set(forbidden).issubset(truth_case["forbidden_assertions"]):
                fail("REVIEW_FORBIDDEN_COVERAGE", "review names an unknown forbidden handle")
            expected_assessment = expected_abstention_assessment(
                truth_case["expected_response_mode"], answer["response_mode"]
            )
            if answer["abstention_assessment"] != expected_assessment:
                fail("REVIEW_ABSTENTION_TRUTH_TABLE", "review violates the frozen four-quadrant table")
            if answer["response_mode"] == "abstain":
                if any(row["score"] != 0 for row in answer["claim_scores"]):
                    fail(
                        "REVIEW_ABSTENTION_CLAIM_SCORE",
                        "observed abstention must score every required claim zero",
                    )
                if forbidden or answer["unmatched_unsupported_assertion_count"]:
                    fail(
                        "REVIEW_ABSTENTION_ASSERTIONS",
                        "observed abstention cannot contain factual assertion violations",
                    )
    if len(answer_order) > MAX_ANSWERS:
        fail("REVIEW_RESOURCE", "review answer count exceeds the cap")
    if claim_score_count > MAX_TOTAL_CLAIM_SCORES:
        fail("REVIEW_RESOURCE", "one review claim-score count exceeds the global cap")
    reviewer_slot = value["reviewer_slot"]
    packet_ids = set(truth_info["packet_handles"]) | seen_answers
    if reviewer_slot in packet_ids:
        fail("REVIEWER_COLLISION", "reviewer slot collides with a packet identifier")
    return {
        "reviewer_slot": reviewer_slot,
        "answer_order": answer_order,
        "answer_map": answer_map,
        "claim_score_count": claim_score_count,
    }


def validate_truth_gates(
    value: Any,
    truth: dict[str, Any],
    truth_raw: bytes,
    truth_info: dict[str, Any],
    answer_order: list[tuple[str, str]],
    review: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    value = require_object(value, "deterministic_truth_gates")
    require_exact_keys(
        value,
        {
            "blind_packet_sha256",
            "boundary",
            "contract_sha256",
            "rows",
            "schema",
            "trial_id",
            "truth_manifest_sha256",
        },
        "deterministic_truth_gates",
    )
    if value["schema"] != TRUTH_GATE_SCHEMA:
        fail("TRUTH_GATE_SCHEMA", "deterministic truth-gate schema drift")
    for field in ("trial_id", "contract_sha256"):
        require_label(value[field], f"truth_gates.{field}") if field == "trial_id" else require_sha(value[field], f"truth_gates.{field}")
        if value[field] != truth[field]:
            fail("TRUTH_GATE_IDENTITY", f"truth gate {field} differs")
    require_sha(value["blind_packet_sha256"], "truth_gates.blind_packet_sha256")
    if value["blind_packet_sha256"] != review["blind_packet_sha256"]:
        fail("TRUTH_GATE_IDENTITY", "truth gate blind packet differs")
    if require_sha(value["truth_manifest_sha256"], "truth_gates.truth_manifest_sha256") != sha256_bytes(truth_raw):
        fail("TRUTH_GATE_IDENTITY", "truth gate does not bind exact truth bytes")
    boundary = require_object(value["boundary"], "truth_gates.boundary")
    expected_boundary = {
        "authorizes_scoring": False,
        "authorizes_unblinding": False,
        "condition_mapping_present": False,
        "provider_neutral_record": True,
        "source_provenance_verified_by_this_algorithm": False,
    }
    if boundary != expected_boundary:
        fail("TRUTH_GATE_BOUNDARY", "truth gate boundary drift")
    rows = require_array(value["rows"], "truth_gates.rows")
    if len(rows) != len(answer_order) or len(rows) > MAX_ANSWERS:
        fail("TRUTH_GATE_COVERAGE", "truth gate row count differs from blind answers")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    observed_order: list[tuple[str, str]] = []
    for row in rows:
        row = require_object(row, "truth gate row")
        case_id = row.get("case_id")
        answer_id = row.get("answer_id")
        key = (case_id, answer_id)
        if key in result:
            fail("TRUTH_GATE_DUPLICATE", "truth gate repeats a case/answer row")
        if case_id not in truth_info["case_map"]:
            fail("TRUTH_GATE_ORPHAN", "truth gate names an unknown case")
        expected_mode = truth_info["case_map"][case_id]["expected_response_mode"]
        if expected_mode == "answer":
            require_exact_keys(
                row,
                {
                    "all_gold_recalled",
                    "answer_id",
                    "applicability",
                    "authority_exists",
                    "case_id",
                    "current_referent_correct",
                },
                "answer truth gate row",
            )
            if row["applicability"] != "ANSWER_REQUIRED":
                fail("TRUTH_GATE_APPLICABILITY", "answer case gate must be applicable")
            require_bool(row["authority_exists"], "truth gate authority_exists")
            require_bool(row["all_gold_recalled"], "truth gate all_gold_recalled")
            require_bool(row["current_referent_correct"], "truth gate current_referent_correct")
        else:
            require_exact_keys(
                row,
                {"answer_id", "applicability", "case_id"},
                "abstention truth gate row",
            )
            if row["applicability"] != "NOT_APPLICABLE_ABSTENTION":
                fail("TRUTH_GATE_APPLICABILITY", "abstention case gate must be not applicable")
        observed_order.append(key)
        result[key] = row
    if observed_order != answer_order:
        fail("TRUTH_GATE_ORDER", "truth gate row order/set differs from reviews")
    return result


def reviewer_failure_rules(expected_mode: str, answer: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if answer["response_mode"] != expected_mode:
        failures.append("REVIEW_RESPONSE_MODE")
    expected_assessment = expected_abstention_assessment(expected_mode, answer["response_mode"])
    if answer["abstention_assessment"] != expected_assessment:
        failures.append("REVIEW_ABSTENTION_ASSESSMENT")
    if expected_mode == "answer" and any(row["score"] != 2 for row in answer["claim_scores"]):
        failures.append("REVIEW_CLAIM_SCORE")
    if expected_mode == "abstain" and answer["claim_scores"]:
        failures.append("REVIEW_CLAIM_SCORE")
    if answer["currentness"] != "pass":
        failures.append("REVIEW_CURRENTNESS")
    if answer["matched_forbidden_assertion_count"] != 0 or answer["matched_forbidden_assertion_handles"]:
        failures.append("REVIEW_FORBIDDEN_ASSERTION")
    if answer["unmatched_unsupported_assertion_count"] != 0:
        failures.append("REVIEW_UNSUPPORTED_ASSERTION")
    if answer["usefulness"] < 4:
        failures.append("REVIEW_USEFULNESS")
    return failures


def evaluate_values(
    root: Path,
    truth: dict[str, Any],
    truth_raw: bytes,
    reviews: list[dict[str, Any]],
    review_raws: list[bytes],
    truth_gates: dict[str, Any],
    truth_gate_raw: bytes,
    *,
    input_mode: str,
) -> dict[str, Any]:
    if input_mode not in {"exact_files", "synthetic_object"}:
        fail("INPUT_MODE", "unsupported strict-case input mode")
    if len(reviews) != 2 or len(review_raws) != 2:
        fail("REVIEWER_COUNT", "exactly two review objects are required")
    total_input = len(truth_raw) + len(truth_gate_raw) + sum(len(raw) for raw in review_raws)
    if total_input > MAX_TOTAL_INPUT_BYTES:
        fail("INPUT_SIZE", "strict-case total input exceeds the cap")

    review_schema = load_frozen_schema(root, REVIEW_SCHEMA_PATH, REVIEW_SCHEMA_SHA256)
    truth_schema = load_frozen_schema(root, TRUTH_SCHEMA_PATH, TRUTH_SCHEMA_SHA256)
    truth_info = validate_truth_manifest(truth_schema, truth)
    review_infos = [
        validate_review(review_schema, review, truth, truth_raw, truth_info)
        for review in reviews
    ]
    slots = [info["reviewer_slot"] for info in review_infos]
    if len(set(slots)) != 2:
        fail("REVIEWER_DUPLICATE", "reviewer slots must be distinct")
    common_fields = (
        "trial_id",
        "contract_sha256",
        "blind_packet_sha256",
        "truth_manifest_sha256",
        "referent_schema_sha256",
        "review_instruction_sha256",
    )
    for field in common_fields:
        if reviews[0][field] != reviews[1][field]:
            fail("REVIEW_IDENTITY_DIVERGENCE", f"review objects disagree on {field}")
    if review_infos[0]["answer_order"] != review_infos[1]["answer_order"]:
        fail("REVIEW_ANSWER_ORDER", "review case/answer order or coverage differs")
    ordered_review_infos = sorted(review_infos, key=lambda info: info["reviewer_slot"])
    reviewer_evaluations = sum(len(info["answer_order"]) for info in review_infos)
    if reviewer_evaluations > MAX_REVIEWER_EVALUATIONS:
        fail("REVIEW_RESOURCE", "reviewer evaluation count exceeds the cap")
    total_claim_scores = sum(info["claim_score_count"] for info in review_infos)
    if total_claim_scores > MAX_TOTAL_CLAIM_SCORES:
        fail("REVIEW_RESOURCE", "two-review claim-score count exceeds the cap")

    answer_order = review_infos[0]["answer_order"]
    gate_map = validate_truth_gates(
        truth_gates, truth, truth_raw, truth_info, answer_order, reviews[0]
    )
    order_index = {code: index for index, code in enumerate(FAILURE_RULE_ORDER)}
    rows: list[dict[str, Any]] = []
    failure_counts = {code: 0 for code in FAILURE_RULE_ORDER}
    reviewer_rule_passes: dict[tuple[str, str], list[bool]] = {}
    for case_id, answer_id in answer_order:
        expected_mode = truth_info["case_map"][case_id]["expected_response_mode"]
        gate = gate_map[(case_id, answer_id)]
        failures: set[str] = set()
        if expected_mode == "answer":
            if not gate["authority_exists"]:
                failures.add("AUTHORITY_MISSING")
            if not gate["all_gold_recalled"]:
                failures.add("GOLD_RECALL_INCOMPLETE")
            if not gate["current_referent_correct"]:
                failures.add("CURRENT_REFERENT_INCORRECT")
            deterministic_gate_pass: bool | str = not failures
        else:
            deterministic_gate_pass = "not_applicable"
        reviewer_fail_count = 0
        per_reviewer_pass: list[bool] = []
        reviewer_results: list[dict[str, Any]] = []
        for info in ordered_review_infos:
            reviewer_failures = reviewer_failure_rules(
                expected_mode, info["answer_map"][(case_id, answer_id)]
            )
            passed = not reviewer_failures
            per_reviewer_pass.append(passed)
            reviewer_results.append(
                {
                    "failure_rules": reviewer_failures,
                    "reviewer_rule_pass": passed,
                    "reviewer_slot_sha256": sha256_object(info["reviewer_slot"]),
                }
            )
            if not passed:
                reviewer_fail_count += 1
                failures.update(reviewer_failures)
        reviewer_rule_passes[(case_id, answer_id)] = per_reviewer_pass
        ordered_failures = sorted(failures, key=order_index.__getitem__)
        for code in ordered_failures:
            failure_counts[code] += 1
        rows.append(
            {
                "answer_id": answer_id,
                "case_id": case_id,
                "deterministic_gate_pass": deterministic_gate_pass,
                "failure_rules": ordered_failures,
                "reviewer_fail_count": reviewer_fail_count,
                "reviewer_pass_count": 2 - reviewer_fail_count,
                "reviewer_results": reviewer_results,
                "strict_rule_pass": not ordered_failures,
            }
        )

    agreement_fields = {
        "abstention_assessment": lambda row: row["abstention_assessment"],
        "claim_scores": lambda row: canonical_compact_bytes(row["claim_scores"]),
        "currentness": lambda row: row["currentness"],
        "forbidden_assertions": lambda row: (
            row["matched_forbidden_assertion_count"],
            tuple(row["matched_forbidden_assertion_handles"]),
        ),
        "response_mode": lambda row: row["response_mode"],
        "reviewer_rule_pass": None,
        "unmatched_unsupported_assertion_count": lambda row: row["unmatched_unsupported_assertion_count"],
        "usefulness": lambda row: row["usefulness"],
    }
    agreements: dict[str, dict[str, int]] = {}
    for metric, projection in agreement_fields.items():
        numerator = 0
        for key in answer_order:
            if metric == "reviewer_rule_pass":
                equal = reviewer_rule_passes[key][0] == reviewer_rule_passes[key][1]
            else:
                assert projection is not None
                equal = projection(ordered_review_infos[0]["answer_map"][key]) == projection(
                    ordered_review_infos[1]["answer_map"][key]
                )
            numerator += int(equal)
        agreements[metric] = {"denominator": len(answer_order), "numerator": numerator}

    algorithm_path = Path(__file__)
    algorithm_sha = sha256_bytes(read_limited(algorithm_path, "strict-case algorithm", maximum=2 * 1024 * 1024))
    input_commitment = sha256_object(
        {
            "review_sha256": sorted(sha256_bytes(raw) for raw in review_raws),
            "schema": "agent_bridge.biocortex_ab_track_b_strict_case_input_commitment.v0",
            "truth_gate_sha256": sha256_bytes(truth_gate_raw),
            "truth_manifest_sha256": sha256_bytes(truth_raw),
        }
    )
    return {
        "agreement": agreements,
        "algorithm_sha256": algorithm_sha,
        "answer_count": len(answer_order),
        "case_count": len(truth_info["case_order"]),
        "contract_sha256": truth["contract_sha256"],
        "failure_rule_counts": failure_counts,
        "input_commitment_sha256": input_commitment,
        "input_mode": input_mode,
        "reviewer_count": 2,
        "reviewer_evaluation_count": reviewer_evaluations,
        "reviewer_slots_sha256": sha256_object(sorted(slots)),
        "rows": rows,
        "schema": RESULT_SCHEMA,
        "status": "VALIDATION_ONLY_NOT_SCORE_CLAIM",
        "strict_fail_count": sum(not row["strict_rule_pass"] for row in rows),
        "strict_pass_count": sum(row["strict_rule_pass"] for row in rows),
        "synthetic_input": input_mode == "synthetic_object",
        "truth_gate_sha256": sha256_bytes(truth_gate_raw),
        "truth_manifest_sha256": sha256_bytes(truth_raw),
    }


def evaluate_artifact_bytes(
    root: Path,
    *,
    truth_manifest_raw: bytes,
    review_raws: list[bytes],
    truth_gate_raw: bytes,
) -> dict[str, Any]:
    if any(len(raw) > MAX_SINGLE_INPUT_BYTES for raw in [truth_manifest_raw, truth_gate_raw, *review_raws]):
        fail("INPUT_SIZE", "one strict-case input exceeds the cap")
    truth = require_object(parse_json(truth_manifest_raw, "truth manifest"), "truth manifest")
    reviews = [
        require_object(parse_json(raw, f"review {index}"), f"review {index}")
        for index, raw in enumerate(review_raws, start=1)
    ]
    truth_gates = require_object(parse_json(truth_gate_raw, "deterministic truth gates"), "deterministic truth gates")
    return evaluate_values(
        root,
        truth,
        truth_manifest_raw,
        reviews,
        review_raws,
        truth_gates,
        truth_gate_raw,
        input_mode="exact_files",
    )


def evaluate_synthetic_objects(
    root: Path,
    *,
    truth_manifest: dict[str, Any],
    reviews: list[dict[str, Any]],
    truth_gates: dict[str, Any],
) -> dict[str, Any]:
    truth_raw = canonical_pretty_bytes(truth_manifest)
    review_raws = [canonical_pretty_bytes(review) for review in reviews]
    truth_gate_raw = canonical_pretty_bytes(truth_gates)
    return evaluate_values(
        root,
        truth_manifest,
        truth_raw,
        reviews,
        review_raws,
        truth_gates,
        truth_gate_raw,
        input_mode="synthetic_object",
    )


def render_result(result: dict[str, Any]) -> bytes:
    lines = [
        f"schema\t{result['schema']}",
        f"status\t{result['status']}",
        f"algorithm_sha256\t{result['algorithm_sha256']}",
        f"input_commitment_sha256\t{result['input_commitment_sha256']}",
        f"input_mode\t{result['input_mode']}",
        f"synthetic_input\t{str(result['synthetic_input']).lower()}",
        f"contract_sha256\t{result['contract_sha256']}",
        f"truth_manifest_sha256\t{result['truth_manifest_sha256']}",
        f"truth_gate_sha256\t{result['truth_gate_sha256']}",
        f"reviewer_slots_sha256\t{result['reviewer_slots_sha256']}",
        f"review_schema_sha256\t{REVIEW_SCHEMA_SHA256}",
        f"truth_manifest_schema_sha256\t{TRUTH_SCHEMA_SHA256}",
        f"case_count\t{result['case_count']}",
        f"blind_answer_case_count\t{result['answer_count']}",
        f"reviewer_count\t{result['reviewer_count']}",
        f"reviewer_evaluation_count\t{result['reviewer_evaluation_count']}",
        f"strict_pass_count\t{result['strict_pass_count']}",
        f"strict_fail_count\t{result['strict_fail_count']}",
        "strict_case_grain\tCASE_X_OPAQUE_ANSWER",
        "reviewer_combination\tLOGICAL_AND_EXACTLY_TWO_DISTINCT_SLOTS",
        "agreement_used_for_gate\tfalse",
        "case_weight_application\tNOT_APPLIED",
        "condition_mapping_present\tfalse",
        "authority_basis_bytes_verified\tfalse",
        "gold_evidence_bytes_verified\tfalse",
        "currentness_basis_bytes_verified\tfalse",
        "truth_gate_source_provenance_verified\tfalse",
        "blind_packet_bytes_verified\tfalse",
        "review_instruction_bytes_verified\tfalse",
        "review_receipts_verified\tfalse",
        "reviewer_roster_verified\tfalse",
        "o_excl_score_claim_created\tfalse",
        "authorizes_scoring\tfalse",
        "authorizes_unblinding\tfalse",
        "side_effects_unlocked\tNONE",
    ]
    for metric in sorted(result["agreement"]):
        row = result["agreement"][metric]
        lines.append(f"agreement\t{metric}\t{row['numerator']}\t{row['denominator']}")
    for code in FAILURE_RULE_ORDER:
        lines.append(f"failure_rule_count\t{code}\t{result['failure_rule_counts'][code]}")
    for row in result["rows"]:
        deterministic = row["deterministic_gate_pass"]
        if type(deterministic) is bool:
            deterministic_text = str(deterministic).lower()
        else:
            deterministic_text = deterministic
        failure_text = ",".join(row["failure_rules"]) if row["failure_rules"] else "NONE"
        lines.append(
            "result\t"
            f"{row['case_id']}\t{row['answer_id']}\t"
            f"{deterministic_text}\t{row['reviewer_pass_count']}\t"
            f"{str(row['strict_rule_pass']).lower()}\t{failure_text}"
        )
        for reviewer in row["reviewer_results"]:
            reviewer_failure_text = (
                ",".join(reviewer["failure_rules"])
                if reviewer["failure_rules"]
                else "NONE"
            )
            lines.append(
                "reviewer_result\t"
                f"{row['case_id']}\t{row['answer_id']}\t"
                f"{reviewer['reviewer_slot_sha256']}\t"
                f"{str(reviewer['reviewer_rule_pass']).lower()}\t"
                f"{reviewer_failure_text}"
            )
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    if len(raw) > MAX_OUTPUT_BYTES:
        fail("OUTPUT_SIZE", "strict-case result exceeds the output cap")
    return raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--truth-manifest", type=Path, required=True)
    parser.add_argument("--review", type=Path, action="append", required=True)
    parser.add_argument("--deterministic-truth-gates", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if len(args.review) != 2:
            fail("REVIEWER_COUNT", "pass exactly two --review paths")
        raws = [
            read_limited(args.truth_manifest, "truth manifest"),
            *[
                read_limited(path, f"review {index}")
                for index, path in enumerate(args.review, start=1)
            ],
            read_limited(args.deterministic_truth_gates, "deterministic truth gates"),
        ]
        if sum(len(raw) for raw in raws) > MAX_TOTAL_INPUT_BYTES:
            fail("INPUT_SIZE", "strict-case total input exceeds the cap")
        result = evaluate_artifact_bytes(
            args.root.resolve(),
            truth_manifest_raw=raws[0],
            review_raws=raws[1:3],
            truth_gate_raw=raws[3],
        )
        sys.stdout.buffer.write(render_result(result))
        return 0
    except StrictCaseError as exc:
        print(f"Track B strict-case check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
