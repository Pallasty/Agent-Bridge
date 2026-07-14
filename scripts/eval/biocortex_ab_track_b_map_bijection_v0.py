#!/usr/bin/env python3
"""Fail-closed Track B blind-map bijection verifier.

The checker accepts exact canonical artifact bytes and a private 32-byte seed.
Its deterministic validation result contains hashes and counts only; it never emits the
seed, condition roster, blind map, answer identifiers, or condition identifiers.
It validates only the map layer; the identity-composition pack checker owns the
outer truth/review joins and their synthetic-fixture fence.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAP_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v0.json"
)
SAMPLING_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v0.json"
)
MAP_SCHEMA_SHA256 = "ad40df50eec68fa192c79e6699a8d2da2a9c3925a387eaa7427f7e19f996d783"
SAMPLING_SCHEMA_SHA256 = "9e73afee2f6366a241b155680b4f77341adeb7c4e341ab91b8d4b1499b5aacbd"

REQUEST_SCHEMA = "agent_bridge.biocortex_ab_track_b_map_bijection_request.v0"
RESULT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_map_bijection_validation_result.v0"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_identity_composition_pack_synthetic.v0"
)
MAP_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_blind_map.v0"
SAMPLING_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_receipt.v0"
SELECTED_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_selected_case_manifest.v0"
ROSTER_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_condition_roster.v0"
GENERATION_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_generation_manifest.v0"
BLIND_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_blind_packet.v0"

HMAC_DOMAIN = b"agent-bridge/track-b/blind-map/v1"
MAX_CASES = 4096
MAX_CONDITIONS = 64
MAX_TOTAL_ANSWERS = 262144
MAX_ANSWER_CHARS = 12000
MAX_TOTAL_ANSWER_BYTES = 16777216
MAX_ARTIFACT_BYTES = 33554432
MAX_TOTAL_INPUT_BYTES = 67108864

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
CASE_RE = re.compile(r"^case_[0-9a-f]{32}$")
ANSWER_RE = re.compile(r"^ans_[0-9a-f]{32}$")
CONDITION_RE = re.compile(r"^cond_[0-9a-f]{32}$")
UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class BijectionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise BijectionError(code, message)


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
                sort_keys=True,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        fail("JSON_CANONICAL", f"value cannot be serialized canonically: {exc}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_object(value: Any) -> str:
    return sha256_bytes(canonical_pretty_bytes(value))


def parse_canonical_bytes(raw: bytes, label: str) -> dict[str, Any]:
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
        fail("JSON_PARSE", f"{label} is malformed JSON: {exc}")
    if type(value) is not dict:
        fail("OBJECT_TYPE", f"{label} must be an object")
    if canonical_pretty_bytes(value) != raw:
        fail("JSON_CANONICAL", f"{label} bytes are not canonical pretty JSON")
    return value


def read_bytes(path: Path, label: str, maximum: int = MAX_ARTIFACT_BYTES) -> bytes:
    try:
        size = path.stat().st_size
        if size < 0 or size > maximum:
            fail("FILE_SIZE", f"{label} exceeds the {maximum}-byte input cap")
        raw = path.read_bytes()
    except OSError as exc:
        fail("FILE_READ", f"cannot read {label}: {exc}")
    if len(raw) != size:
        fail("FILE_RACE", f"{label} changed while it was read")
    return raw


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = read_bytes(path, label)
    return parse_canonical_bytes(raw, label), raw


def exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        fail("OBJECT_KEYS", f"{label} field set differs from the frozen contract")


def require_object(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        fail("OBJECT_TYPE", f"{label} must be an object")
    return value


def require_list(value: Any, label: str, minimum: int, maximum: int) -> list[Any]:
    if type(value) is not list:
        fail("ARRAY_TYPE", f"{label} must be an array")
    if not minimum <= len(value) <= maximum:
        fail("ARRAY_BOUND", f"{label} length is outside {minimum}..{maximum}")
    return value


def require_string(value: Any, label: str, minimum: int, maximum: int) -> str:
    if type(value) is not str or not minimum <= len(value) <= maximum:
        fail("STRING_VALUE", f"{label} must be a bounded string")
    return value


def require_match(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        fail("STRING_PATTERN", f"{label} is malformed")
    return value


def require_sha(value: Any, label: str) -> str:
    return require_match(value, SHA_RE, label)


def require_label(value: Any, label: str) -> str:
    return require_match(value, LABEL_RE, label)


def require_integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        fail("INTEGER_VALUE", f"{label} must be an integer in {minimum}..{maximum}")
    return value


def require_utc(value: Any, label: str) -> datetime:
    text = require_match(value, UTC_RE, label)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        fail("UTC_VALUE", f"{label} is not a real UTC second: {exc}")
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        fail("UTC_VALUE", f"{label} is not canonical UTC")
    return parsed


def hmac_hex(seed: bytes, *parts: str) -> str:
    message = HMAC_DOMAIN + b"\0" + b"\0".join(
        part.encode("utf-8") for part in parts
    )
    return hmac.new(seed, message, hashlib.sha256).hexdigest()


def derive_condition_id(seed: bytes, trial_id: str, condition_key: str) -> str:
    return "cond_" + hmac_hex(seed, "condition-id", trial_id, condition_key)[:32]


def derive_answer_id(
    seed: bytes, trial_id: str, case_id: str, condition_id: str
) -> str:
    return "ans_" + hmac_hex(
        seed, "answer-id", trial_id, case_id, condition_id
    )[:32]


def blind_rank(seed: bytes, trial_id: str, case_id: str, condition_id: str) -> str:
    return hmac_hex(seed, "blind-order", trial_id, case_id, condition_id)


def generation_rank(
    seed: bytes, trial_id: str, case_id: str, condition_id: str
) -> str:
    return hmac_hex(seed, "generation-order", trial_id, case_id, condition_id)


def validate_schema_sources(root: Path) -> None:
    for path, expected, label in (
        (MAP_SCHEMA_PATH, MAP_SCHEMA_SHA256, "blind-map schema"),
        (SAMPLING_SCHEMA_PATH, SAMPLING_SCHEMA_SHA256, "sampling schema"),
    ):
        _, raw = load_canonical(root / path, label)
        if sha256_bytes(raw) != expected:
            fail("SCHEMA_SOURCE_HASH", f"{label} byte hash drift")


def validate_blind_map(value: dict[str, Any]) -> dict[str, Any]:
    exact_keys(
        value,
        {
            "answer_blinding_seed_sha256",
            "blind_packet_sha256",
            "boundary",
            "capture_sha256",
            "cases",
            "condition_roster_sha256",
            "contract_sha256",
            "created_at_utc",
            "eligible_frame_manifest_sha256",
            "generation_sha256",
            "sampling_receipt_sha256",
            "schema",
            "selected_case_manifest_sha256",
            "trial_id",
        },
        "blind map",
    )
    if value["schema"] != MAP_INSTANCE_SCHEMA:
        fail("MAP_SCHEMA", "blind map instance schema drift")
    trial_id = require_label(value["trial_id"], "blind_map.trial_id")
    hashes = {
        key: require_sha(value[key], f"blind_map.{key}")
        for key in (
            "answer_blinding_seed_sha256",
            "blind_packet_sha256",
            "capture_sha256",
            "condition_roster_sha256",
            "contract_sha256",
            "eligible_frame_manifest_sha256",
            "generation_sha256",
            "sampling_receipt_sha256",
            "selected_case_manifest_sha256",
        )
    }
    created_at = require_utc(value["created_at_utc"], "blind_map.created_at_utc")
    boundary = require_object(value["boundary"], "blind_map.boundary")
    expected_boundary = {
        "mapping_private": True,
        "reviewer_must_not_read_before_review": True,
        "single_use_trial_specific": True,
        "unblinding_allowed": False,
    }
    if boundary != expected_boundary:
        fail("MAP_BOUNDARY", "blind map boundary is not fail closed")
    raw_cases = require_list(value["cases"], "blind_map.cases", 1, MAX_CASES)
    case_ids: list[str] = []
    assignments: dict[str, list[tuple[str, str]]] = {}
    answer_ids: set[str] = set()
    condition_set: set[str] | None = None
    for case_index, raw_case in enumerate(raw_cases):
        case = require_object(raw_case, f"blind_map.cases[{case_index}]")
        exact_keys(case, {"assignments", "case_id"}, "blind map case")
        case_id = require_match(case["case_id"], CASE_RE, "blind map case_id")
        if case_id in assignments:
            fail("MAP_CASE_DUPLICATE", "blind map repeats a case")
        rows: list[tuple[str, str]] = []
        seen_conditions: set[str] = set()
        for row_index, raw_row in enumerate(
            require_list(
                case["assignments"],
                f"blind_map.cases[{case_index}].assignments",
                1,
                MAX_CONDITIONS,
            )
        ):
            row = require_object(raw_row, "blind map assignment")
            exact_keys(row, {"answer_id", "condition_id"}, "blind map assignment")
            answer_id = require_match(row["answer_id"], ANSWER_RE, "map answer_id")
            condition_id = require_match(
                row["condition_id"], CONDITION_RE, "map condition_id"
            )
            if answer_id in answer_ids:
                fail("MAP_ANSWER_DUPLICATE", "blind map repeats an answer globally")
            if condition_id in seen_conditions:
                fail("MAP_CONDITION_DUPLICATE", "blind map repeats a condition in one case")
            answer_ids.add(answer_id)
            seen_conditions.add(condition_id)
            rows.append((answer_id, condition_id))
        if condition_set is None:
            condition_set = seen_conditions
        elif seen_conditions != condition_set:
            fail("MAP_CONDITION_SET", "blind map cases do not share one condition set")
        case_ids.append(case_id)
        assignments[case_id] = rows
    if len(answer_ids) > MAX_TOTAL_ANSWERS:
        fail("MAP_RESOURCE", "blind map answer product exceeds the global cap")
    return {
        "trial_id": trial_id,
        "hashes": hashes,
        "created_at": created_at,
        "case_ids": case_ids,
        "assignments": assignments,
        "answer_count": len(answer_ids),
        "condition_ids": condition_set or set(),
    }


def validate_sampling(value: dict[str, Any]) -> dict[str, Any]:
    exact_keys(
        value,
        {
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
            "schema",
            "seed_derivation_sha256",
            "seed_entropy_receipt_sha256",
            "selected_case_manifest_sha256",
            "strata_allocation_manifest_sha256",
            "trial_id",
        },
        "sampling receipt",
    )
    if value["schema"] != SAMPLING_INSTANCE_SCHEMA:
        fail("SAMPLING_SCHEMA", "sampling receipt instance schema drift")
    if value["receipt_schema_sha256"] != SAMPLING_SCHEMA_SHA256:
        fail("SAMPLING_SCHEMA_HASH", "sampling receipt does not bind exact schema bytes")
    if value["receipt_precedes_first_condition_output"] is not True:
        fail("SAMPLING_BOUNDARY", "sampling receipt does not assert pre-output creation")
    if value["sampling_selection_domain"] != "agent-bridge/track-b/sample/v1":
        fail("SAMPLING_DOMAIN", "sampling domain drift")
    if (
        value["sampling_selection_message"]
        != "domain_utf8_NUL_frame_sha256_ascii_NUL_stratum_utf8_NUL_case_id_utf8"
    ):
        fail("SAMPLING_MESSAGE", "sampling message drift")
    trial_id = require_label(value["trial_id"], "sampling.trial_id")
    contract_sha = require_sha(value["contract_sha256"], "sampling.contract_sha256")
    eligible_sha = require_sha(
        value["eligible_frame_manifest_sha256"], "sampling.eligible_frame_manifest_sha256"
    )
    selected_sha = require_sha(
        value["selected_case_manifest_sha256"], "sampling.selected_case_manifest_sha256"
    )
    for key in (
        "frame_o_excl_receipt_sha256",
        "receipt_writer_sha256",
        "reserve_manifest_sha256",
        "sampling_selection_algorithm_sha256",
        "seed_derivation_sha256",
        "seed_entropy_receipt_sha256",
        "strata_allocation_manifest_sha256",
    ):
        require_sha(value[key], f"sampling.{key}")
    created_at = require_utc(value["created_at_utc"], "sampling.created_at_utc")

    def rational_rows(field: str) -> list[tuple[str, int, int]]:
        result: list[tuple[str, int, int]] = []
        seen: set[str] = set()
        for index, raw_row in enumerate(
            require_list(value[field], f"sampling.{field}", 1, MAX_CASES)
        ):
            row = require_object(raw_row, f"sampling.{field}[{index}]")
            exact_keys(row, {"case_id", "denominator", "numerator"}, field)
            case_id = require_match(row["case_id"], CASE_RE, f"{field}.case_id")
            numerator = require_integer(
                row["numerator"], f"{field}.numerator", 1, 9007199254740991
            )
            denominator = require_integer(
                row["denominator"], f"{field}.denominator", 1, 9007199254740991
            )
            if math.gcd(numerator, denominator) != 1:
                fail("SAMPLING_REDUCED", f"{field} fraction is not reduced")
            if case_id in seen:
                fail("SAMPLING_CASE_DUPLICATE", f"{field} repeats a case")
            seen.add(case_id)
            result.append((case_id, numerator, denominator))
        return result

    probabilities = rational_rows("case_inclusion_probabilities")
    weights = rational_rows("case_sampling_weights")
    if [row[0] for row in probabilities] != [row[0] for row in weights]:
        fail("SAMPLING_CASE_ORDER", "probability and weight case order differs")
    for probability, weight in zip(probabilities, weights, strict=True):
        if probability[1] > probability[2]:
            fail("SAMPLING_PROBABILITY", "inclusion probability exceeds one")
        if weight[1] < weight[2]:
            fail("SAMPLING_WEIGHT", "sampling weight is below one")
        if probability[1] * weight[1] != probability[2] * weight[2]:
            fail("SAMPLING_RECIPROCAL", "probability and weight are not reciprocal")
    return {
        "trial_id": trial_id,
        "contract_sha256": contract_sha,
        "eligible_frame_manifest_sha256": eligible_sha,
        "selected_case_manifest_sha256": selected_sha,
        "created_at": created_at,
        "case_ids": [row[0] for row in probabilities],
    }


def validate_selected(value: dict[str, Any]) -> dict[str, Any]:
    exact_keys(
        value,
        {
            "cases",
            "contract_sha256",
            "eligible_frame_manifest_sha256",
            "schema",
            "trial_id",
        },
        "selected-case manifest",
    )
    if value["schema"] != SELECTED_INSTANCE_SCHEMA:
        fail("SELECTED_SCHEMA", "selected-case manifest schema drift")
    cases: list[str] = []
    for index, raw_case in enumerate(
        require_list(value["cases"], "selected.cases", 1, MAX_CASES)
    ):
        case = require_object(raw_case, f"selected.cases[{index}]")
        exact_keys(case, {"case_id"}, "selected case")
        case_id = require_match(case["case_id"], CASE_RE, "selected case_id")
        if case_id in cases:
            fail("SELECTED_CASE_DUPLICATE", "selected manifest repeats a case")
        cases.append(case_id)
    return {
        "trial_id": require_label(value["trial_id"], "selected.trial_id"),
        "contract_sha256": require_sha(
            value["contract_sha256"], "selected.contract_sha256"
        ),
        "eligible_frame_manifest_sha256": require_sha(
            value["eligible_frame_manifest_sha256"],
            "selected.eligible_frame_manifest_sha256",
        ),
        "case_ids": cases,
    }


def validate_roster(
    value: dict[str, Any], seed: bytes, expected_trial: str
) -> dict[str, Any]:
    exact_keys(
        value,
        {"conditions", "contract_sha256", "schema", "trial_id"},
        "condition roster",
    )
    if value["schema"] != ROSTER_INSTANCE_SCHEMA:
        fail("ROSTER_SCHEMA", "condition roster schema drift")
    trial_id = require_label(value["trial_id"], "roster.trial_id")
    if trial_id != expected_trial:
        fail("TRIAL_BINDING", "condition roster trial differs")
    conditions: list[tuple[str, str]] = []
    ids: set[str] = set()
    keys: set[str] = set()
    for index, raw_condition in enumerate(
        require_list(value["conditions"], "roster.conditions", 1, MAX_CONDITIONS)
    ):
        condition = require_object(raw_condition, f"roster.conditions[{index}]")
        exact_keys(condition, {"condition_id", "condition_key"}, "roster condition")
        condition_key = require_label(condition["condition_key"], "condition_key")
        condition_id = require_match(
            condition["condition_id"], CONDITION_RE, "condition_id"
        )
        if condition_key in keys or condition_id in ids:
            fail("ROSTER_DUPLICATE", "condition roster repeats key or opaque id")
        expected_id = derive_condition_id(seed, trial_id, condition_key)
        if not hmac.compare_digest(condition_id, expected_id):
            fail("ROSTER_DERIVATION", "condition id is not seed-derived")
        keys.add(condition_key)
        ids.add(condition_id)
        conditions.append((condition_key, condition_id))
    if [row[0] for row in conditions] != sorted(row[0] for row in conditions):
        fail("ROSTER_ORDER", "condition roster is not sorted by private condition key")
    return {
        "trial_id": trial_id,
        "contract_sha256": require_sha(
            value["contract_sha256"], "roster.contract_sha256"
        ),
        "conditions": conditions,
    }


def validate_generation(
    value: dict[str, Any],
    selected_cases: list[str],
    roster: list[tuple[str, str]],
    seed: bytes,
    trial_id: str,
) -> dict[str, Any]:
    exact_keys(
        value,
        {
            "capture_sha256",
            "cases",
            "contract_sha256",
            "first_condition_output_at_utc",
            "schema",
            "trial_id",
        },
        "generation manifest",
    )
    if value["schema"] != GENERATION_INSTANCE_SCHEMA:
        fail("GENERATION_SCHEMA", "generation manifest schema drift")
    if require_label(value["trial_id"], "generation.trial_id") != trial_id:
        fail("TRIAL_BINDING", "generation trial differs")
    first_output_at = require_utc(
        value["first_condition_output_at_utc"],
        "generation.first_condition_output_at_utc",
    )
    ranked_pairs = [
        (
            generation_rank(seed, trial_id, case_id, condition_id),
            case_id,
            condition_key,
            condition_id,
        )
        for case_id in selected_cases
        for condition_key, condition_id in roster
    ]
    ranks = [row[0] for row in ranked_pairs]
    if len(ranks) != len(set(ranks)):
        fail("GENERATION_RANK_COLLISION", "generation HMAC ranks collide")
    expected_pairs = [
        (case_id, condition_key, condition_id)
        for _, case_id, condition_key, condition_id in sorted(
            ranked_pairs, key=lambda row: row[0]
        )
    ]
    expected_index = {
        (case_id, condition_key): index
        for index, (case_id, condition_key, _) in enumerate(expected_pairs, start=1)
    }
    answers: dict[str, dict[str, dict[str, Any]]] = {}
    total_bytes = 0
    raw_cases = require_list(value["cases"], "generation.cases", 1, MAX_CASES)
    if len(raw_cases) != len(selected_cases):
        fail("GENERATION_CASE_COVERAGE", "generation case count differs")
    for case_index, (raw_case, expected_case_id) in enumerate(
        zip(raw_cases, selected_cases, strict=True)
    ):
        case = require_object(raw_case, f"generation.cases[{case_index}]")
        exact_keys(case, {"answers", "case_id"}, "generation case")
        case_id = require_match(case["case_id"], CASE_RE, "generation case_id")
        if case_id != expected_case_id:
            fail("GENERATION_CASE_ORDER", "generation case order differs")
        expected_keys = sorted(
            [condition_key for condition_key, _ in roster],
            key=lambda key: expected_index[(case_id, key)],
        )
        raw_answers = require_list(
            case["answers"], "generation answers", len(roster), len(roster)
        )
        if [row.get("condition_key") for row in raw_answers if type(row) is dict] != expected_keys:
            fail("GENERATION_ORDER", "generation answer order differs")
        rows: dict[str, dict[str, Any]] = {}
        for answer_index, raw_answer in enumerate(raw_answers):
            answer = require_object(raw_answer, "generation answer")
            exact_keys(
                answer,
                {
                    "answer_markdown",
                    "answer_sha256",
                    "condition_key",
                    "invocation_index",
                },
                "generation answer",
            )
            condition_key = require_label(answer["condition_key"], "condition_key")
            text = require_string(
                answer["answer_markdown"], "generation answer text", 1, MAX_ANSWER_CHARS
            )
            text_bytes = text.encode("utf-8")
            total_bytes += len(text_bytes)
            if total_bytes > MAX_TOTAL_ANSWER_BYTES:
                fail("GENERATION_RESOURCE", "generation answer bytes exceed global cap")
            answer_sha = require_sha(answer["answer_sha256"], "generation answer_sha256")
            if answer_sha != sha256_bytes(text_bytes):
                fail("GENERATION_ANSWER_HASH", "generation answer hash differs from bytes")
            invocation_index = require_integer(
                answer["invocation_index"],
                "generation invocation_index",
                1,
                MAX_TOTAL_ANSWERS,
            )
            if invocation_index != expected_index[(case_id, condition_key)]:
                fail("GENERATION_INVOCATION", "generation invocation order is not reproducible")
            rows[condition_key] = {
                "answer_markdown": text,
                "answer_sha256": answer_sha,
                "invocation_index": invocation_index,
            }
        answers[case_id] = rows
    return {
        "trial_id": trial_id,
        "contract_sha256": require_sha(
            value["contract_sha256"], "generation.contract_sha256"
        ),
        "capture_sha256": require_sha(
            value["capture_sha256"], "generation.capture_sha256"
        ),
        "first_output_at": first_output_at,
        "answers": answers,
        "answer_bytes": total_bytes,
    }


def validate_blind_packet(
    value: dict[str, Any],
    selected_cases: list[str],
    roster: list[tuple[str, str]],
    generation: dict[str, Any],
    seed: bytes,
    trial_id: str,
) -> dict[str, Any]:
    exact_keys(
        value,
        {
            "capture_sha256",
            "cases",
            "contract_sha256",
            "generation_sha256",
            "schema",
            "trial_id",
        },
        "blind packet",
    )
    if value["schema"] != BLIND_INSTANCE_SCHEMA:
        fail("BLIND_SCHEMA", "blind packet schema drift")
    if require_label(value["trial_id"], "blind.trial_id") != trial_id:
        fail("TRIAL_BINDING", "blind packet trial differs")
    raw_cases = require_list(value["cases"], "blind.cases", 1, MAX_CASES)
    if len(raw_cases) != len(selected_cases):
        fail("BLIND_CASE_COVERAGE", "blind packet case count differs")
    answers: dict[str, list[tuple[str, str]]] = {}
    global_answer_ids: set[str] = set()
    for case_index, (raw_case, expected_case_id) in enumerate(
        zip(raw_cases, selected_cases, strict=True)
    ):
        case = require_object(raw_case, f"blind.cases[{case_index}]")
        exact_keys(case, {"answers", "case_id"}, "blind case")
        case_id = require_match(case["case_id"], CASE_RE, "blind case_id")
        if case_id != expected_case_id:
            fail("BLIND_CASE_ORDER", "blind packet case order differs")
        ranked_conditions = [
            (blind_rank(seed, trial_id, case_id, condition_id), condition_key, condition_id)
            for condition_key, condition_id in roster
        ]
        ranks = [row[0] for row in ranked_conditions]
        if len(ranks) != len(set(ranks)):
            fail("BLIND_RANK_COLLISION", "blind-order HMAC ranks collide")
        expected_conditions = [
            (condition_key, condition_id)
            for _, condition_key, condition_id in sorted(
                ranked_conditions, key=lambda row: row[0]
            )
        ]
        raw_answers = require_list(
            case["answers"], "blind answers", len(roster), len(roster)
        )
        rows: list[tuple[str, str]] = []
        for raw_answer, (condition_key, condition_id) in zip(
            raw_answers, expected_conditions, strict=True
        ):
            answer = require_object(raw_answer, "blind answer")
            exact_keys(
                answer,
                {"answer_id", "answer_markdown", "answer_sha256"},
                "blind answer",
            )
            answer_id = require_match(answer["answer_id"], ANSWER_RE, "blind answer_id")
            expected_id = derive_answer_id(seed, trial_id, case_id, condition_id)
            if not hmac.compare_digest(answer_id, expected_id):
                fail("BLIND_ANSWER_DERIVATION", "blind answer id is not seed-derived")
            if answer_id in global_answer_ids:
                fail("BLIND_ANSWER_DUPLICATE", "blind packet repeats an answer id")
            global_answer_ids.add(answer_id)
            text = require_string(
                answer["answer_markdown"], "blind answer text", 1, MAX_ANSWER_CHARS
            )
            answer_sha = require_sha(answer["answer_sha256"], "blind answer_sha256")
            generated = generation["answers"][case_id][condition_key]
            if (
                answer_sha != sha256_bytes(text.encode("utf-8"))
                or answer_sha != generated["answer_sha256"]
                or text != generated["answer_markdown"]
            ):
                fail("BLIND_ANSWER_BYTES", "blind answer differs from generation")
            rows.append((answer_id, condition_id))
        answers[case_id] = rows
    return {
        "trial_id": trial_id,
        "contract_sha256": require_sha(value["contract_sha256"], "blind.contract_sha256"),
        "capture_sha256": require_sha(value["capture_sha256"], "blind.capture_sha256"),
        "generation_sha256": require_sha(
            value["generation_sha256"], "blind.generation_sha256"
        ),
        "answers": answers,
    }


def private_token_text_encodings(raw: bytes) -> tuple[set[str], set[str]]:
    """Return case-folded and case-sensitive common lossless encodings."""
    base32 = base64.b32encode(raw).decode("ascii")
    standard = base64.b64encode(raw).decode("ascii")
    urlsafe = base64.urlsafe_b64encode(raw).decode("ascii")
    folded = {
        raw.hex(),
        ":".join(f"{byte:02x}" for byte in raw),
        "-".join(f"{byte:02x}" for byte in raw),
        " ".join(f"{byte:02x}" for byte in raw),
        base32.casefold(),
        base32.rstrip("=").casefold(),
    }
    try:
        folded.add(raw.decode("ascii").casefold())
    except UnicodeDecodeError:
        pass
    exact = {
        encoded
        for encoded in (
            standard,
            standard.rstrip("="),
            urlsafe,
            urlsafe.rstrip("="),
        )
        if encoded
    }
    return folded, exact


def iter_json_strings(value: Any):
    if type(value) is str:
        yield value
    elif type(value) is list:
        for item in value:
            yield from iter_json_strings(item)
    elif type(value) is dict:
        for item in value.values():
            yield from iter_json_strings(item)


def reject_blind_private_token_disclosure(
    blind_packet: dict[str, Any],
    roster: list[tuple[str, str]],
    seed: bytes,
) -> None:
    """Reject direct private-token disclosures anywhere in the blind packet."""
    folded_condition_keys: set[str] = set()
    exact_condition_keys: set[str] = set()
    folded_condition_ids: set[str] = set()
    exact_condition_ids: set[str] = set()
    for condition_key, condition_id in roster:
        folded, exact = private_token_text_encodings(condition_key.encode("utf-8"))
        folded_condition_keys |= folded
        exact_condition_keys |= exact
        folded, exact = private_token_text_encodings(condition_id.encode("utf-8"))
        folded_condition_ids |= folded
        exact_condition_ids |= exact
    folded_seed_encodings, exact_seed_encodings = private_token_text_encodings(seed)
    packet_bytes = canonical_pretty_bytes(blind_packet)
    exact_corpus = packet_bytes.decode("utf-8")
    folded_corpus = exact_corpus.casefold()
    if any(token in folded_corpus for token in folded_condition_keys) or any(
        token in exact_corpus for token in exact_condition_keys
    ):
        fail(
            "BLIND_CONDITION_KEY_LEAK",
            "reviewer-visible blind packet contains a private condition key",
        )
    if any(token in folded_corpus for token in folded_condition_ids) or any(
        token in exact_corpus for token in exact_condition_ids
    ):
        fail(
            "BLIND_CONDITION_ID_LEAK",
            "reviewer-visible blind packet contains a private condition id",
        )
    if (
        seed in packet_bytes
        or any(
            seed in text.encode("utf-8")
            for text in iter_json_strings(blind_packet)
        )
        or any(token in folded_corpus for token in folded_seed_encodings)
        or any(token in exact_corpus for token in exact_seed_encodings)
    ):
        fail(
            "BLIND_RAW_SEED_LEAK",
            "reviewer-visible blind packet discloses the raw blinding seed",
        )


def validate_artifact_bytes(
    root: Path,
    *,
    contract_raw: bytes,
    eligible_frame_manifest_raw: bytes,
    blind_map_raw: bytes,
    sampling_receipt_raw: bytes,
    selected_case_manifest_raw: bytes,
    condition_roster_raw: bytes,
    capture_raw: bytes,
    generation_manifest_raw: bytes,
    blind_packet_raw: bytes,
    seed: bytes,
    request_sha256: str,
    input_mode: str,
) -> dict[str, Any]:
    if input_mode not in {"raw_files", "synthetic_fixture", "synthetic_request"}:
        fail("INPUT_MODE", "map checker input mode is not frozen")
    if len(seed) != 32:
        fail("SEED_LENGTH", "answer blinding seed must be exactly 32 bytes")
    total_input_bytes = sum(
        len(raw)
        for raw in (
            contract_raw,
            eligible_frame_manifest_raw,
            blind_map_raw,
            sampling_receipt_raw,
            selected_case_manifest_raw,
            condition_roster_raw,
            capture_raw,
            generation_manifest_raw,
            blind_packet_raw,
            seed,
        )
    )
    if total_input_bytes > MAX_TOTAL_INPUT_BYTES:
        fail("INPUT_RESOURCE", "artifact set exceeds the global input-byte cap")
    validate_schema_sources(root)
    blind_map = parse_canonical_bytes(blind_map_raw, "blind map")
    sampling = parse_canonical_bytes(sampling_receipt_raw, "sampling receipt")
    selected = parse_canonical_bytes(selected_case_manifest_raw, "selected-case manifest")
    roster = parse_canonical_bytes(condition_roster_raw, "condition roster")
    generation = parse_canonical_bytes(generation_manifest_raw, "generation manifest")
    blind_packet = parse_canonical_bytes(blind_packet_raw, "blind packet")

    map_result = validate_blind_map(blind_map)
    sampling_result = validate_sampling(sampling)
    selected_result = validate_selected(selected)
    roster_result = validate_roster(roster, seed, map_result["trial_id"])
    generation_result = validate_generation(
        generation,
        selected_result["case_ids"],
        roster_result["conditions"],
        seed,
        map_result["trial_id"],
    )
    blind_result = validate_blind_packet(
        blind_packet,
        selected_result["case_ids"],
        roster_result["conditions"],
        generation_result,
        seed,
        map_result["trial_id"],
    )
    reject_blind_private_token_disclosure(
        blind_packet,
        roster_result["conditions"],
        seed,
    )

    trial_ids = {
        map_result["trial_id"],
        sampling_result["trial_id"],
        selected_result["trial_id"],
        roster_result["trial_id"],
        generation_result["trial_id"],
        blind_result["trial_id"],
    }
    if len(trial_ids) != 1:
        fail("TRIAL_BINDING", "artifact trial identities differ")
    contracts = {
        map_result["hashes"]["contract_sha256"],
        sampling_result["contract_sha256"],
        selected_result["contract_sha256"],
        roster_result["contract_sha256"],
        generation_result["contract_sha256"],
        blind_result["contract_sha256"],
    }
    if len(contracts) != 1:
        fail("CONTRACT_BINDING", "artifact contract identities differ")
    case_orders = (
        sampling_result["case_ids"],
        selected_result["case_ids"],
        map_result["case_ids"],
        list(generation_result["answers"]),
        list(blind_result["answers"]),
    )
    if any(order != case_orders[0] for order in case_orders[1:]):
        fail("CASE_ORDER_BINDING", "case order differs across artifacts")
    if set(row[1] for row in roster_result["conditions"]) != map_result["condition_ids"]:
        fail("CONDITION_SET_BINDING", "blind map condition set differs from roster")
    for case_id in map_result["case_ids"]:
        if map_result["assignments"][case_id] != blind_result["answers"][case_id]:
            fail("BIJECTION_BINDING", "blind map is not the exact packet bijection")

    expected_bindings = {
        "contract_sha256": sha256_bytes(contract_raw),
        "sampling_receipt_sha256": sha256_bytes(sampling_receipt_raw),
        "eligible_frame_manifest_sha256": sha256_bytes(
            eligible_frame_manifest_raw
        ),
        "selected_case_manifest_sha256": sha256_bytes(selected_case_manifest_raw),
        "condition_roster_sha256": sha256_bytes(condition_roster_raw),
        "capture_sha256": sha256_bytes(capture_raw),
        "generation_sha256": sha256_bytes(generation_manifest_raw),
        "blind_packet_sha256": sha256_bytes(blind_packet_raw),
        "answer_blinding_seed_sha256": sha256_bytes(seed),
    }
    for key, expected in expected_bindings.items():
        if map_result["hashes"][key] != expected:
            fail("MAP_IDENTITY_BINDING", f"blind map {key} differs from exact bytes")
    if sampling_result["contract_sha256"] != expected_bindings["contract_sha256"]:
        fail("CONTRACT_BINDING", "artifact contract hash differs from exact bytes")
    if (
        sampling_result["eligible_frame_manifest_sha256"]
        != expected_bindings["eligible_frame_manifest_sha256"]
        or selected_result["eligible_frame_manifest_sha256"]
        != expected_bindings["eligible_frame_manifest_sha256"]
    ):
        fail("ELIGIBLE_BINDING", "eligible-frame binding differs")
    if (
        sampling_result["selected_case_manifest_sha256"]
        != expected_bindings["selected_case_manifest_sha256"]
    ):
        fail("SELECTED_BINDING", "sampling receipt does not bind selected-case bytes")
    if generation_result["capture_sha256"] != expected_bindings["capture_sha256"]:
        fail("CAPTURE_BINDING", "generation capture binding differs from map")
    if blind_result["capture_sha256"] != expected_bindings["capture_sha256"]:
        fail("CAPTURE_BINDING", "blind packet capture binding differs from map")
    if blind_result["generation_sha256"] != expected_bindings["generation_sha256"]:
        fail("GENERATION_BINDING", "blind packet does not bind generation bytes")
    if not (
        sampling_result["created_at"]
        < generation_result["first_output_at"]
        <= map_result["created_at"]
    ):
        fail(
            "TIME_ORDER",
            "sampling receipt must precede first output, which must not follow the map",
        )

    checker_sha = sha256_bytes(Path(__file__).resolve().read_bytes())
    return {
        "answer_count": map_result["answer_count"],
        "authorizes_review_execution": False,
        "authorizes_scoring": False,
        "authorizes_unblinding": False,
        "blind_map_sha256": sha256_bytes(blind_map_raw),
        "blind_packet_sha256": expected_bindings["blind_packet_sha256"],
        "capture_sha256": expected_bindings["capture_sha256"],
        "case_count": len(map_result["case_ids"]),
        "checker_sha256": checker_sha,
        "condition_count": len(map_result["condition_ids"]),
        "condition_mapping_disclosed": False,
        "condition_roster_sha256": expected_bindings["condition_roster_sha256"],
        "contract_sha256": next(iter(contracts)),
        "generation_sha256": expected_bindings["generation_sha256"],
        "eligible_frame_manifest_sha256": expected_bindings[
            "eligible_frame_manifest_sha256"
        ],
        "identity_binding_count": 10,
        "input_mode": input_mode,
        "map_schema_sha256": MAP_SCHEMA_SHA256,
        "o_excl_receipt_verified": False,
        "raw_seed_disclosed": False,
        "request_sha256": require_sha(request_sha256, "request_sha256"),
        "sampling_receipt_sha256": expected_bindings["sampling_receipt_sha256"],
        "sampling_schema_sha256": SAMPLING_SCHEMA_SHA256,
        "schema": RESULT_SCHEMA,
        "seed_commitment_sha256": expected_bindings["answer_blinding_seed_sha256"],
        "selected_case_manifest_sha256": expected_bindings[
            "selected_case_manifest_sha256"
        ],
        "stage_custody_verified": False,
        "status": "VALIDATION_ONLY_NOT_STAGE_RECEIPT",
        "satisfies_post_generation_gate": False,
        "synthetic_input": input_mode != "raw_files",
        "trial_id_sha256": sha256_bytes(map_result["trial_id"].encode("utf-8")),
    }


def validate_request_object(
    root: Path, request: Any, input_mode: str = "synthetic_request"
) -> dict[str, Any]:
    if input_mode not in {"synthetic_fixture", "synthetic_request"}:
        fail(
            "INPUT_MODE",
            "object requests are synthetic-only; raw_files requires exact file bytes",
        )
    request = require_object(request, "map bijection request")
    exact_keys(
        request,
        {
            "answer_blinding_seed_hex",
            "blind_map",
            "blind_packet",
            "capture",
            "condition_roster",
            "contract",
            "eligible_frame_manifest",
            "generation_manifest",
            "sampling_receipt",
            "schema",
            "selected_case_manifest",
        },
        "map bijection request",
    )
    if request["schema"] != REQUEST_SCHEMA:
        fail("REQUEST_SCHEMA", "map bijection request schema drift")
    seed_hex = require_match(
        request["answer_blinding_seed_hex"], SHA_RE, "answer_blinding_seed_hex"
    )
    request_raw = canonical_pretty_bytes(request)
    return validate_artifact_bytes(
        root,
        contract_raw=canonical_pretty_bytes(request["contract"]),
        eligible_frame_manifest_raw=canonical_pretty_bytes(
            request["eligible_frame_manifest"]
        ),
        blind_map_raw=canonical_pretty_bytes(request["blind_map"]),
        sampling_receipt_raw=canonical_pretty_bytes(request["sampling_receipt"]),
        selected_case_manifest_raw=canonical_pretty_bytes(
            request["selected_case_manifest"]
        ),
        condition_roster_raw=canonical_pretty_bytes(request["condition_roster"]),
        capture_raw=canonical_pretty_bytes(request["capture"]),
        generation_manifest_raw=canonical_pretty_bytes(request["generation_manifest"]),
        blind_packet_raw=canonical_pretty_bytes(request["blind_packet"]),
        seed=bytes.fromhex(seed_hex),
        request_sha256=sha256_bytes(request_raw),
        input_mode=input_mode,
    )


def extract_synthetic_map_request(fixture: Any) -> dict[str, Any]:
    fixture = require_object(fixture, "synthetic fixture")
    exact_keys(
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
        fail("FIXTURE_IDENTITY", "synthetic fixture identity or fence drift")
    if fixture["boundary"] != {
        "authority_asserted": False,
        "condition_mapping_real": False,
        "private_source_data_present": False,
        "real_run_authorized": False,
        "side_effects_unlocked": False,
        "synthetic_seed_only": True,
    }:
        fail("FIXTURE_BOUNDARY", "synthetic fixture boundary drift")
    return require_object(
        fixture["map_bijection_request"], "synthetic map-bijection request"
    )


RESULT_ORDER = (
    "schema",
    "status",
    "checker_sha256",
    "request_sha256",
    "input_mode",
    "trial_id_sha256",
    "contract_sha256",
    "map_schema_sha256",
    "sampling_schema_sha256",
    "blind_map_sha256",
    "sampling_receipt_sha256",
    "selected_case_manifest_sha256",
    "condition_roster_sha256",
    "generation_sha256",
    "blind_packet_sha256",
    "capture_sha256",
    "eligible_frame_manifest_sha256",
    "seed_commitment_sha256",
    "identity_binding_count",
    "case_count",
    "condition_count",
    "answer_count",
    "synthetic_input",
    "raw_seed_disclosed",
    "condition_mapping_disclosed",
    "o_excl_receipt_verified",
    "stage_custody_verified",
    "satisfies_post_generation_gate",
    "authorizes_review_execution",
    "authorizes_unblinding",
    "authorizes_scoring",
)


def render_result(result: dict[str, Any]) -> bytes:
    if set(result) != set(RESULT_ORDER):
        fail("RESULT_FIELDS", "map validation-result field set drift")
    return "".join(
        f"{key}\t{str(result[key]).lower() if type(result[key]) is bool else result[key]}\n"
        for key in RESULT_ORDER
    ).encode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--synthetic-map-fixture",
        dest="synthetic_map_fixture",
        type=Path,
        help="synthetic outer fixture; validates only its fenced map request",
    )
    source.add_argument("--synthetic-request", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--eligible-frame-manifest", type=Path)
    parser.add_argument("--blind-map", type=Path)
    parser.add_argument("--sampling-receipt", type=Path)
    parser.add_argument("--selected-case-manifest", type=Path)
    parser.add_argument("--condition-roster", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--generation-manifest", type=Path)
    parser.add_argument("--blind-packet", type=Path)
    parser.add_argument("--seed-file", type=Path)
    return parser.parse_args()


RAW_ARGUMENTS = (
    "contract",
    "eligible_frame_manifest",
    "blind_map",
    "sampling_receipt",
    "selected_case_manifest",
    "condition_roster",
    "capture",
    "generation_manifest",
    "blind_packet",
    "seed_file",
)


def raw_request_commitment(raw: dict[str, bytes]) -> str:
    return sha256_object(
        {
            "artifact_sha256": {
                key: sha256_bytes(value)
                for key, value in sorted(raw.items())
            },
            "schema": "agent_bridge.biocortex_ab_track_b_artifact_set_commitment.v0",
        }
    )


def main() -> int:
    args = parse_args()
    root = (args.root or Path(__file__).resolve().parents[2]).resolve()
    try:
        raw_paths = {name: getattr(args, name) for name in RAW_ARGUMENTS}
        any_raw = any(path is not None for path in raw_paths.values())
        all_raw = all(path is not None for path in raw_paths.values())
        if (
            args.synthetic_map_fixture is None
            and args.synthetic_request is None
            and not all_raw
        ) or (
            (
                args.synthetic_map_fixture is not None
                or args.synthetic_request is not None
            )
            and any_raw
        ) or (any_raw and not all_raw):
            fail(
                "ARGUMENT_MODE",
                "choose one fixture/request or provide the complete ten-file raw mode",
            )
        if args.synthetic_map_fixture is not None:
            fixture, _ = load_canonical(
                args.synthetic_map_fixture, "synthetic fixture"
            )
            request = extract_synthetic_map_request(fixture)
            result = validate_request_object(
                root, request, input_mode="synthetic_fixture"
            )
        elif args.synthetic_request is not None:
            request, _ = load_canonical(
                args.synthetic_request, "synthetic map bijection request"
            )
            result = validate_request_object(
                root, request, input_mode="synthetic_request"
            )
        else:
            raw = {
                key: read_bytes(path, key.replace("_", " "))
                for key, path in raw_paths.items()
                if key != "seed_file"
            }
            seed = read_bytes(raw_paths["seed_file"], "seed file", maximum=32)
            commitment_inputs = {**raw, "seed": seed}
            result = validate_artifact_bytes(
                root,
                contract_raw=raw["contract"],
                eligible_frame_manifest_raw=raw["eligible_frame_manifest"],
                blind_map_raw=raw["blind_map"],
                sampling_receipt_raw=raw["sampling_receipt"],
                selected_case_manifest_raw=raw["selected_case_manifest"],
                condition_roster_raw=raw["condition_roster"],
                capture_raw=raw["capture"],
                generation_manifest_raw=raw["generation_manifest"],
                blind_packet_raw=raw["blind_packet"],
                seed=seed,
                request_sha256=raw_request_commitment(commitment_inputs),
                input_mode="raw_files",
            )
        sys.stdout.buffer.write(render_result(result))
        return 0
    except BijectionError as exc:
        print(f"Track B map bijection check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
