#!/usr/bin/env python3
"""Fail-closed Track B successor blind-map bijection v1 verifier.

The checker accepts exact canonical artifact bytes and a private 32-byte seed.
Its deterministic validation result contains hashes and counts only; it never emits the
seed, condition roster, blind map, answer identifiers, or condition identifiers.
It validates only the map layer; a successor admission checker owns version
routing and the outer authorization boundary.  The v1 surface accepts only the
sampling-receipt v1 and its selected-manifest source profile.  It never falls
back to v0 or treats validation as condition-output authority.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import math
import os
import re
import stat
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAP_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-blind-map-schema-v1.json"
)
SAMPLING_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-sampling-receipt-schema-v1.json"
)
CONTRACT_DIGEST_PROFILE_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-sampling-contract-digest-profile-v0.json"
)
SAMPLING_WRITER_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_sampling_receipt_writer_v0.py"
)
MAP_SCHEMA_SHA256 = "475f5c518df83049808e0a118f50ef83026b8c8202bebfd4439dfb9c416fd724"
SAMPLING_SCHEMA_SHA256 = "e418b58246eaf183b5624c7eb12299caeea933c83a07584faa915651b3cd48d4"
CONTRACT_DIGEST_PROFILE_SHA256 = (
    "a8972ad5e75b30634931fee84f08226e2660413b45cf9dfea948089d61160243"
)
SAMPLING_WRITER_SHA256 = (
    "a8642d2b524183e060eb2f2c16d3a4bba4bca43c8e18b8524bc14738d4f6d975"
)
SAMPLING_SEED_DERIVATION_SHA256 = (
    "4f51781ff707e89b4c09adffeafbdaacd75c7e1571d1a86e45d336aace888a3f"
)
SAMPLING_SELECTION_ALGORITHM_SHA256 = (
    "e327faf2ad73718dc33f68fdb66a89abf0ac84fbbf8d828ff79fa0e8b75772ec"
)
SAMPLING_ATTEMPT_NAMESPACE_DOMAIN = (
    "agent-bridge/track-b/sampling-attempt-namespace/v1"
)
SAMPLING_ATTEMPT_NAMESPACE_MESSAGE = (
    "domain_utf8_NUL_trial_id_utf8"
)
SAMPLING_EVENT_DOMAIN = "agent-bridge/track-b/sampling-event/v1"
SAMPLING_EVENT_MESSAGE = (
    "domain_utf8_NUL_contract_core_sha256_ascii_NUL_trial_id_utf8_NUL_"
    "eligible_frame_sha256_ascii_NUL_strata_allocation_sha256_ascii"
)

REQUEST_SCHEMA = "agent_bridge.biocortex_ab_track_b_map_bijection_request.v1"
RESULT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_map_bijection_validation_result.v1"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_successor_admission_map_pack_synthetic.v0"
)
MAP_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_blind_map.v1"
SAMPLING_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_sampling_receipt.v1"
SELECTED_INSTANCE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_selected_case_manifest_source_profile.v0"
)
ROSTER_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_condition_roster.v0"
GENERATION_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_generation_manifest.v0"
BLIND_INSTANCE_SCHEMA = "agent_bridge.biocortex_ab_track_b_blind_packet.v0"

IDENTITY_DERIVATION_DOMAIN = "agent-bridge/track-b/blind-map/v2"
HMAC_DOMAIN = IDENTITY_DERIVATION_DOMAIN.encode("ascii")
MAX_CASES = 4096
MAX_CONDITIONS = 64
MAX_TOTAL_ANSWERS = 262144
MAX_ANSWER_CHARS = 12000
MAX_TOTAL_ANSWER_BYTES = 16777216
MAX_ARTIFACT_BYTES = 33554432
MAX_TOTAL_INPUT_BYTES = 67108864

SHA_RE = re.compile(r"^[0-9a-f]{64}$")
LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
STRATUM_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
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


def read_bytes(
    path: Path,
    label: str,
    maximum: int = MAX_ARTIFACT_BYTES,
    oversize_code: str = "FILE_SIZE",
) -> bytes:
    if maximum < 0:
        fail("INPUT_RESOURCE", f"no input-byte budget remains for {label}")
    descriptor: int | None = None
    try:
        path_before = os.lstat(path)
        if not stat.S_ISREG(path_before.st_mode):
            fail("FILE_TYPE", f"{label} must be a regular non-symlink file")
        if path_before.st_nlink != 1:
            fail("FILE_LINK", f"{label} must have exactly one hard link")
        flags = os.O_RDONLY | os.O_NONBLOCK
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            fail("FILE_TYPE", f"{label} opened as a non-regular file")
        if opened.st_nlink != 1:
            fail("FILE_LINK", f"{label} opened with multiple hard links")
        if (opened.st_dev, opened.st_ino) != (
            path_before.st_dev,
            path_before.st_ino,
        ):
            fail("FILE_RACE", f"{label} identity changed before open")
        if opened.st_size < 0 or opened.st_size > maximum:
            fail(
                oversize_code,
                f"{label} exceeds the {maximum}-byte input cap",
            )
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(1048576, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
    except OSError as exc:
        fail("FILE_READ", f"cannot read {label}: {exc}")
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if len(raw) > maximum:
        fail(oversize_code, f"{label} exceeds the {maximum}-byte input cap")
    try:
        path_after = os.lstat(path)
    except OSError as exc:
        fail("FILE_RACE", f"cannot restat {label}: {exc}")
    identity_before = (
        path_before.st_dev,
        path_before.st_ino,
        path_before.st_mode,
        path_before.st_nlink,
        path_before.st_size,
    )
    identity_opened = (
        opened.st_dev,
        opened.st_ino,
        opened.st_mode,
        opened.st_nlink,
        opened.st_size,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
    )
    identity_path_after = (
        path_after.st_dev,
        path_after.st_ino,
        path_after.st_mode,
        path_after.st_nlink,
        path_after.st_size,
    )
    if not (
        identity_before
        == identity_opened
        == identity_after
        == identity_path_after
    ) or len(raw) != opened.st_size:
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
        (
            CONTRACT_DIGEST_PROFILE_PATH,
            CONTRACT_DIGEST_PROFILE_SHA256,
            "contract-digest profile",
        ),
        (SAMPLING_WRITER_PATH, SAMPLING_WRITER_SHA256, "sampling writer"),
    ):
        raw = read_bytes(root / path, label)
        if path.suffix == ".json":
            parse_canonical_bytes(raw, label)
        if sha256_bytes(raw) != expected:
            fail("SCHEMA_SOURCE_HASH", f"{label} byte hash drift")


def rebuild_sampling_receipt(
    root: Path, request_raw: bytes
) -> tuple[dict[str, Any], bytes, str]:
    request = parse_canonical_bytes(request_raw, "sampling-receipt write request")
    writer_path = (root / SAMPLING_WRITER_PATH).resolve()
    writer_raw = read_bytes(writer_path, "sampling writer")
    if sha256_bytes(writer_raw) != SAMPLING_WRITER_SHA256:
        fail("SAMPLING_WRITER_HASH", "sampling writer byte identity drift")
    module_name = "_biocortex_ab_track_b_bound_sampling_writer_v1_map"
    if module_name in sys.modules:
        fail("SAMPLING_WRITER_STATE", "bound sampling-writer module name is occupied")
    module = types.ModuleType(module_name)
    module.__file__ = str(writer_path)
    module.__package__ = None
    sys.modules[module_name] = module
    try:
        exec(compile(writer_raw, str(writer_path), "exec"), module.__dict__)
        builder = module.__dict__.get("build_sampling_receipt")
        if not callable(builder):
            fail("SAMPLING_WRITER_API", "sampling writer builder is unavailable")
        try:
            built = builder(request_raw)
        except Exception as exc:
            fail("SAMPLING_REBUILD", f"sampling writer rejected request: {exc}")
    finally:
        sys.modules.pop(module_name, None)
    canonical = getattr(built, "canonical_bytes", None)
    receipt_sha256 = getattr(built, "receipt_sha256", None)
    if type(canonical) is not bytes or type(receipt_sha256) is not str:
        fail("SAMPLING_WRITER_RESULT", "sampling writer result shape drift")
    require_sha(receipt_sha256, "rebuilt sampling receipt sha256")
    return request, canonical, receipt_sha256


def validate_contract_core(root: Path, value: dict[str, Any]) -> dict[str, Any]:
    profile, _ = load_canonical(
        root / CONTRACT_DIGEST_PROFILE_PATH, "contract-digest profile"
    )
    required = profile.get("required_fields")
    sha_fields = profile.get("sha256_fields")
    if type(required) is not list or type(sha_fields) is not list:
        fail("CONTRACT_PROFILE", "contract-digest profile field catalogs are malformed")
    exact_keys(value, set(required), "sampling contract core")
    if value.get("schema") != profile.get("contract_core_schema"):
        fail("CONTRACT_CORE_SCHEMA", "sampling contract-core schema drift")
    trial_id = require_label(value.get("trial_id"), "contract_core.trial_id")
    for field in sha_fields:
        require_sha(value.get(field), f"contract_core.{field}")
    exact_sources = {
        "contract_digest_profile_sha256": CONTRACT_DIGEST_PROFILE_SHA256,
        "sampling_receipt_schema_sha256": SAMPLING_SCHEMA_SHA256,
        "sampling_receipt_writer_sha256": SAMPLING_WRITER_SHA256,
        "sampling_seed_derivation_sha256": SAMPLING_SEED_DERIVATION_SHA256,
        "sampling_selection_algorithm_sha256": SAMPLING_SELECTION_ALGORITHM_SHA256,
    }
    for field, expected in exact_sources.items():
        if value.get(field) != expected:
            fail("CONTRACT_CORE_SOURCE", f"contract core {field} drift")
    return {"trial_id": trial_id}


def validate_eligible_frame(value: dict[str, Any]) -> dict[str, Any]:
    exact_keys(
        value,
        {
            "cases",
            "frame_builder_sha256",
            "inclusion_exclusion_rules_sha256",
            "schema",
            "target_population_definition_sha256",
            "trial_id",
        },
        "eligible-frame manifest",
    )
    if value["schema"] != "agent_bridge.biocortex_ab_track_b_eligible_frame_source_profile.v0":
        fail("FRAME_SCHEMA", "eligible-frame source-profile schema drift")
    trial_id = require_label(value["trial_id"], "eligible_frame.trial_id")
    for field in (
        "frame_builder_sha256",
        "inclusion_exclusion_rules_sha256",
        "target_population_definition_sha256",
    ):
        require_sha(value[field], f"eligible_frame.{field}")
    case_ids: list[str] = []
    strata: dict[str, str] = {}
    for index, raw_case in enumerate(
        require_list(value["cases"], "eligible_frame.cases", 1, MAX_CASES)
    ):
        case = require_object(raw_case, f"eligible_frame.cases[{index}]")
        exact_keys(case, {"case_id", "stratum"}, "eligible-frame case")
        case_id = require_match(case["case_id"], CASE_RE, "eligible-frame case_id")
        stratum = require_match(case["stratum"], STRATUM_RE, "eligible-frame stratum")
        if case_id in strata:
            fail("FRAME_CASE_DUPLICATE", "eligible frame repeats a case")
        case_ids.append(case_id)
        strata[case_id] = stratum
    if case_ids != sorted(case_ids, key=lambda item: item.encode("utf-8")):
        fail("FRAME_CASE_ORDER", "eligible frame is not in UTF-8 case-id order")
    return {"case_ids": case_ids, "strata": strata, "trial_id": trial_id}


def derive_sampling_event_sha256(
    contract_core_sha256: str,
    trial_id: str,
    eligible_frame_sha256: str,
    strata_allocation_sha256: str,
) -> str:
    message = b"\0".join(
        (
            SAMPLING_EVENT_DOMAIN.encode("utf-8"),
            contract_core_sha256.encode("ascii"),
            trial_id.encode("utf-8"),
            eligible_frame_sha256.encode("ascii"),
            strata_allocation_sha256.encode("ascii"),
        )
    )
    return sha256_bytes(message)


def derive_sampling_attempt_namespace_sha256(
    trial_id: str,
) -> str:
    message = b"\0".join(
        (
            SAMPLING_ATTEMPT_NAMESPACE_DOMAIN.encode("utf-8"),
            trial_id.encode("utf-8"),
        )
    )
    return sha256_bytes(message)


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
            "contract_digest_profile_sha256",
            "contract_sha256",
            "created_at_utc",
            "eligible_frame_manifest_sha256",
            "generation_sha256",
            "identity_derivation_domain",
            "sampling_receipt_schema_sha256",
            "sampling_receipt_sha256",
            "sampling_receipt_writer_sha256",
            "sampling_receipt_write_request_sha256",
            "sampling_attempt_namespace_sha256",
            "sampling_event_sha256",
            "sampling_seed_sha256",
            "schema",
            "selected_case_manifest_sha256",
            "selection_commitment_sha256",
            "trial_id",
        },
        "blind map",
    )
    if value["schema"] != MAP_INSTANCE_SCHEMA:
        fail("MAP_SCHEMA", "blind map instance schema drift")
    if value["identity_derivation_domain"] != IDENTITY_DERIVATION_DOMAIN:
        fail("MAP_IDENTITY_DOMAIN", "blind map identity domain drift")
    trial_id = require_label(value["trial_id"], "blind_map.trial_id")
    hashes = {
        key: require_sha(value[key], f"blind_map.{key}")
        for key in (
            "answer_blinding_seed_sha256",
            "blind_packet_sha256",
            "capture_sha256",
            "condition_roster_sha256",
            "contract_digest_profile_sha256",
            "contract_sha256",
            "eligible_frame_manifest_sha256",
            "generation_sha256",
            "sampling_receipt_schema_sha256",
            "sampling_receipt_sha256",
            "sampling_receipt_writer_sha256",
            "sampling_receipt_write_request_sha256",
            "sampling_attempt_namespace_sha256",
            "sampling_event_sha256",
            "sampling_seed_sha256",
            "selected_case_manifest_sha256",
            "selection_commitment_sha256",
        )
    }
    created_at = require_utc(value["created_at_utc"], "blind_map.created_at_utc")
    boundary = require_object(value["boundary"], "blind_map.boundary")
    expected_boundary = {
        "condition_output_authorized": False,
        "cross_version_identity_reuse_allowed": False,
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
            "anti_shopping_order_verified",
            "case_inclusion_probabilities",
            "case_sampling_weights",
            "condition_output_authorized",
            "contract_digest_profile_sha256",
            "contract_sha256",
            "created_at_utc",
            "eligible_frame_manifest_sha256",
            "external_entropy_sha256",
            "frame_o_excl_receipt_sha256",
            "pre_output_timing_verified",
            "receipt_precedes_first_condition_output",
            "receipt_schema_sha256",
            "receipt_writer_sha256",
            "reserve_manifest_sha256",
            "sampling_seed_sha256",
            "sampling_selection_algorithm_sha256",
            "sampling_selection_domain",
            "sampling_selection_message",
            "schema",
            "seed_derivation_domain",
            "seed_derivation_message_profile",
            "seed_derivation_sha256",
            "seed_entropy_receipt_sha256",
            "selected_case_manifest_sha256",
            "selection_commitment_sha256",
            "strata_allocation_manifest_sha256",
            "trial_id",
        },
        "sampling receipt",
    )
    if value["schema"] != SAMPLING_INSTANCE_SCHEMA:
        fail("SAMPLING_SCHEMA", "sampling receipt instance schema drift")
    if value["receipt_schema_sha256"] != SAMPLING_SCHEMA_SHA256:
        fail("SAMPLING_SCHEMA_HASH", "sampling receipt does not bind exact schema bytes")
    if value["receipt_writer_sha256"] != SAMPLING_WRITER_SHA256:
        fail("SAMPLING_WRITER_HASH", "sampling receipt writer identity drift")
    if value["contract_digest_profile_sha256"] != CONTRACT_DIGEST_PROFILE_SHA256:
        fail("SAMPLING_PROFILE_HASH", "contract-digest profile identity drift")
    if value["seed_derivation_sha256"] != SAMPLING_SEED_DERIVATION_SHA256:
        fail("SAMPLING_SEED_SOURCE", "seed-derivation source identity drift")
    if (
        value["sampling_selection_algorithm_sha256"]
        != SAMPLING_SELECTION_ALGORITHM_SHA256
    ):
        fail("SAMPLING_SELECTION_SOURCE", "selection source identity drift")
    for field in (
        "anti_shopping_order_verified",
        "condition_output_authorized",
        "pre_output_timing_verified",
    ):
        if value[field] is not False:
            fail("SAMPLING_BOUNDARY", f"sampling receipt {field} must remain false")
    if value["receipt_precedes_first_condition_output"] is not True:
        fail("SAMPLING_BOUNDARY", "sampling receipt lacks the pre-output protocol assertion")
    if value["sampling_selection_domain"] != "agent-bridge/track-b/sample/v1":
        fail("SAMPLING_DOMAIN", "sampling domain drift")
    if (
        value["sampling_selection_message"]
        != "domain_utf8_NUL_frame_sha256_ascii_NUL_stratum_utf8_NUL_case_id_utf8"
    ):
        fail("SAMPLING_MESSAGE", "sampling message drift")
    if value["seed_derivation_domain"] != "agent-bridge/track-b/sample/v1":
        fail("SAMPLING_SEED_DOMAIN", "seed-derivation domain drift")
    if (
        value["seed_derivation_message_profile"]
        != "domain_utf8_NUL_contract_sha256_ascii_NUL_trial_id_utf8_NUL_eligible_frame_sha256_ascii_NUL_external_entropy_sha256_ascii"
    ):
        fail("SAMPLING_SEED_MESSAGE", "seed-derivation message profile drift")
    trial_id = require_label(value["trial_id"], "sampling.trial_id")
    contract_sha = require_sha(value["contract_sha256"], "sampling.contract_sha256")
    eligible_sha = require_sha(
        value["eligible_frame_manifest_sha256"], "sampling.eligible_frame_manifest_sha256"
    )
    selected_sha = require_sha(
        value["selected_case_manifest_sha256"], "sampling.selected_case_manifest_sha256"
    )
    for key in (
        "contract_digest_profile_sha256",
        "external_entropy_sha256",
        "frame_o_excl_receipt_sha256",
        "receipt_writer_sha256",
        "reserve_manifest_sha256",
        "sampling_seed_sha256",
        "sampling_selection_algorithm_sha256",
        "seed_derivation_sha256",
        "seed_entropy_receipt_sha256",
        "selection_commitment_sha256",
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
        "contract_digest_profile_sha256": value["contract_digest_profile_sha256"],
        "eligible_frame_manifest_sha256": eligible_sha,
        "selected_case_manifest_sha256": selected_sha,
        "sampling_seed_sha256": value["sampling_seed_sha256"],
        "selection_commitment_sha256": value["selection_commitment_sha256"],
        "receipt_schema_sha256": value["receipt_schema_sha256"],
        "receipt_writer_sha256": value["receipt_writer_sha256"],
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
            "sampling_seed_sha256",
            "schema",
            "selection_commitment_sha256",
            "trial_id",
        },
        "selected-case manifest",
    )
    if value["schema"] != SELECTED_INSTANCE_SCHEMA:
        fail("SELECTED_SCHEMA", "selected-case manifest schema drift")
    cases: list[str] = []
    strata: dict[str, str] = {}
    for index, raw_case in enumerate(
        require_list(value["cases"], "selected.cases", 1, MAX_CASES)
    ):
        case = require_object(raw_case, f"selected.cases[{index}]")
        exact_keys(case, {"case_id", "stratum"}, "selected case")
        case_id = require_match(case["case_id"], CASE_RE, "selected case_id")
        stratum = require_match(case["stratum"], STRATUM_RE, "selected stratum")
        if case_id in cases:
            fail("SELECTED_CASE_DUPLICATE", "selected manifest repeats a case")
        cases.append(case_id)
        strata[case_id] = stratum
    if cases != sorted(cases, key=lambda item: item.encode("utf-8")):
        fail("SELECTED_CASE_ORDER", "selected manifest is not in UTF-8 case-id order")
    return {
        "trial_id": require_label(value["trial_id"], "selected.trial_id"),
        "contract_sha256": require_sha(
            value["contract_sha256"], "selected.contract_sha256"
        ),
        "eligible_frame_manifest_sha256": require_sha(
            value["eligible_frame_manifest_sha256"],
            "selected.eligible_frame_manifest_sha256",
        ),
        "sampling_seed_sha256": require_sha(
            value["sampling_seed_sha256"], "selected.sampling_seed_sha256"
        ),
        "selection_commitment_sha256": require_sha(
            value["selection_commitment_sha256"],
            "selected.selection_commitment_sha256",
        ),
        "case_ids": cases,
        "strata": strata,
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
    contract_core_raw: bytes,
    eligible_frame_manifest_raw: bytes,
    blind_map_raw: bytes,
    sampling_receipt_write_request_raw: bytes,
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
            contract_core_raw,
            eligible_frame_manifest_raw,
            blind_map_raw,
            sampling_receipt_write_request_raw,
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
    writer_request, rebuilt_receipt_raw, rebuilt_receipt_sha256 = (
        rebuild_sampling_receipt(root, sampling_receipt_write_request_raw)
    )
    if rebuilt_receipt_raw != sampling_receipt_raw:
        fail("SAMPLING_REBUILD", "sampling receipt differs from exact writer recomputation")
    if rebuilt_receipt_sha256 != sha256_bytes(sampling_receipt_raw):
        fail("SAMPLING_REBUILD", "sampling writer result digest differs from exact bytes")
    contract_core = parse_canonical_bytes(contract_core_raw, "sampling contract core")
    eligible_frame = parse_canonical_bytes(
        eligible_frame_manifest_raw, "eligible-frame manifest"
    )
    blind_map = parse_canonical_bytes(blind_map_raw, "blind map")
    sampling = parse_canonical_bytes(sampling_receipt_raw, "sampling receipt")
    selected = parse_canonical_bytes(selected_case_manifest_raw, "selected-case manifest")
    roster = parse_canonical_bytes(condition_roster_raw, "condition roster")
    generation = parse_canonical_bytes(generation_manifest_raw, "generation manifest")
    blind_packet = parse_canonical_bytes(blind_packet_raw, "blind packet")

    writer_join = {
        "contract_core": contract_core,
        "eligible_frame_manifest": eligible_frame,
        "selected_case_manifest": selected,
    }
    for field, expected in writer_join.items():
        if writer_request.get(field) != expected:
            fail("SAMPLING_REQUEST_JOIN", f"writer request {field} differs from map input")

    contract_result = validate_contract_core(root, contract_core)
    frame_result = validate_eligible_frame(eligible_frame)
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
        contract_result["trial_id"],
        frame_result["trial_id"],
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
    exact_contract_sha256 = sha256_bytes(contract_core_raw)
    if next(iter(contracts)) != exact_contract_sha256:
        fail("CONTRACT_BINDING", "contract-core hash differs from exact bytes")
    case_orders = (
        sampling_result["case_ids"],
        selected_result["case_ids"],
        map_result["case_ids"],
        list(generation_result["answers"]),
        list(blind_result["answers"]),
    )
    if any(order != case_orders[0] for order in case_orders[1:]):
        fail("CASE_ORDER_BINDING", "case order differs across artifacts")
    if not set(selected_result["case_ids"]).issubset(frame_result["case_ids"]):
        fail("FRAME_SELECTED_JOIN", "selected cases are not a subset of the eligible frame")
    for case_id in selected_result["case_ids"]:
        if selected_result["strata"][case_id] != frame_result["strata"][case_id]:
            fail("FRAME_SELECTED_JOIN", "selected-case stratum differs from the frame")
    if set(row[1] for row in roster_result["conditions"]) != map_result["condition_ids"]:
        fail("CONDITION_SET_BINDING", "blind map condition set differs from roster")
    for case_id in map_result["case_ids"]:
        if map_result["assignments"][case_id] != blind_result["answers"][case_id]:
            fail("BIJECTION_BINDING", "blind map is not the exact packet bijection")

    expected_bindings = {
        "contract_sha256": exact_contract_sha256,
        "sampling_receipt_sha256": sha256_bytes(sampling_receipt_raw),
        "sampling_receipt_write_request_sha256": sha256_bytes(
            sampling_receipt_write_request_raw
        ),
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
    successor_binding_pairs = {
        "contract_digest_profile_sha256": sampling_result[
            "contract_digest_profile_sha256"
        ],
        "sampling_receipt_schema_sha256": sampling_result[
            "receipt_schema_sha256"
        ],
        "sampling_receipt_writer_sha256": sampling_result[
            "receipt_writer_sha256"
        ],
        "sampling_seed_sha256": sampling_result["sampling_seed_sha256"],
        "selection_commitment_sha256": sampling_result[
            "selection_commitment_sha256"
        ],
    }
    for key, expected in successor_binding_pairs.items():
        if map_result["hashes"][key] != expected:
            fail("MAP_SUCCESSOR_BINDING", f"blind map {key} differs from receipt v1")
    sampling_attempt_namespace_sha256 = derive_sampling_attempt_namespace_sha256(
        map_result["trial_id"],
    )
    if (
        map_result["hashes"]["sampling_attempt_namespace_sha256"]
        != sampling_attempt_namespace_sha256
    ):
        fail(
            "MAP_SAMPLING_ATTEMPT_NAMESPACE",
            "blind map sampling-attempt namespace identity drift",
        )
    sampling_event_sha256 = derive_sampling_event_sha256(
        exact_contract_sha256,
        map_result["trial_id"],
        expected_bindings["eligible_frame_manifest_sha256"],
        sampling["strata_allocation_manifest_sha256"],
    )
    if map_result["hashes"]["sampling_event_sha256"] != sampling_event_sha256:
        fail("MAP_SAMPLING_EVENT", "blind map sampling-event identity drift")
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
    selected_successor_pairs = {
        "contract_sha256": sampling_result["contract_sha256"],
        "eligible_frame_manifest_sha256": sampling_result[
            "eligible_frame_manifest_sha256"
        ],
        "sampling_seed_sha256": sampling_result["sampling_seed_sha256"],
        "selection_commitment_sha256": sampling_result[
            "selection_commitment_sha256"
        ],
    }
    for key, expected in selected_successor_pairs.items():
        if selected_result[key] != expected:
            fail("SELECTED_SUCCESSOR_BINDING", f"selected manifest {key} differs")
    if hmac.compare_digest(
        expected_bindings["answer_blinding_seed_sha256"],
        sampling_result["sampling_seed_sha256"],
    ):
        fail("SEED_SEPARATION", "answer-blinding and sampling seed commitments collide")
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
    if map_result["answer_count"] != (
        len(map_result["case_ids"]) * len(map_result["condition_ids"])
    ):
        fail("BIJECTION_CARDINALITY", "answer cardinality is not case x condition")

    checker_sha = sha256_bytes(Path(__file__).resolve().read_bytes())
    return {
        "anti_shopping_order_verified": False,
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
        "condition_output_authorized": False,
        "condition_mapping_disclosed": False,
        "condition_roster_sha256": expected_bindings["condition_roster_sha256"],
        "contract_core_sha256": next(iter(contracts)),
        "contract_digest_profile_sha256": CONTRACT_DIGEST_PROFILE_SHA256,
        "cross_version_fallback_used": False,
        "generation_sha256": expected_bindings["generation_sha256"],
        "eligible_frame_manifest_sha256": expected_bindings[
            "eligible_frame_manifest_sha256"
        ],
        "identity_binding_count": 18,
        "identity_derivation_domain": IDENTITY_DERIVATION_DOMAIN,
        "input_mode": input_mode,
        "map_schema_sha256": MAP_SCHEMA_SHA256,
        "o_excl_receipt_verified": False,
        "pre_output_timing_verified": False,
        "protocol_time_order_consistent": True,
        "raw_seed_disclosed": False,
        "replay_consumption_verified": False,
        "request_sha256": require_sha(request_sha256, "request_sha256"),
        "sampling_receipt_sha256": expected_bindings["sampling_receipt_sha256"],
        "sampling_receipt_write_request_sha256": expected_bindings[
            "sampling_receipt_write_request_sha256"
        ],
        "sampling_receipt_writer_sha256": SAMPLING_WRITER_SHA256,
        "sampling_attempt_namespace_sha256": sampling_attempt_namespace_sha256,
        "sampling_event_sha256": sampling_event_sha256,
        "sampling_schema_sha256": SAMPLING_SCHEMA_SHA256,
        "sampling_seed_sha256": sampling_result["sampling_seed_sha256"],
        "schema": RESULT_SCHEMA,
        "seed_commitment_sha256": expected_bindings["answer_blinding_seed_sha256"],
        "selected_case_manifest_sha256": expected_bindings[
            "selected_case_manifest_sha256"
        ],
        "selected_manifest_schema": SELECTED_INSTANCE_SCHEMA,
        "selection_commitment_sha256": sampling_result[
            "selection_commitment_sha256"
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
            "contract_core",
            "eligible_frame_manifest",
            "generation_manifest",
            "sampling_receipt",
            "sampling_receipt_write_request",
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
        contract_core_raw=canonical_pretty_bytes(request["contract_core"]),
        eligible_frame_manifest_raw=canonical_pretty_bytes(
            request["eligible_frame_manifest"]
        ),
        blind_map_raw=canonical_pretty_bytes(request["blind_map"]),
        sampling_receipt_write_request_raw=canonical_pretty_bytes(
            request["sampling_receipt_write_request"]
        ),
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
    "contract_core_sha256",
    "contract_digest_profile_sha256",
    "map_schema_sha256",
    "sampling_schema_sha256",
    "sampling_receipt_writer_sha256",
    "selected_manifest_schema",
    "identity_derivation_domain",
    "blind_map_sha256",
    "sampling_receipt_sha256",
    "sampling_receipt_write_request_sha256",
    "sampling_attempt_namespace_sha256",
    "sampling_event_sha256",
    "sampling_seed_sha256",
    "selection_commitment_sha256",
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
    "cross_version_fallback_used",
    "raw_seed_disclosed",
    "condition_mapping_disclosed",
    "protocol_time_order_consistent",
    "anti_shopping_order_verified",
    "pre_output_timing_verified",
    "condition_output_authorized",
    "o_excl_receipt_verified",
    "replay_consumption_verified",
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
    parser.add_argument("--contract-core", dest="contract_core", type=Path)
    parser.add_argument("--eligible-frame-manifest", type=Path)
    parser.add_argument("--blind-map", type=Path)
    parser.add_argument("--sampling-receipt-write-request", type=Path)
    parser.add_argument("--sampling-receipt", type=Path)
    parser.add_argument("--selected-case-manifest", type=Path)
    parser.add_argument("--condition-roster", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--generation-manifest", type=Path)
    parser.add_argument("--blind-packet", type=Path)
    parser.add_argument("--seed-file", type=Path)
    return parser.parse_args()


RAW_ARGUMENTS = (
    "contract_core",
    "eligible_frame_manifest",
    "blind_map",
    "sampling_receipt_write_request",
    "sampling_receipt",
    "selected_case_manifest",
    "condition_roster",
    "capture",
    "generation_manifest",
    "blind_packet",
    "seed_file",
)


def read_raw_file_set(
    raw_paths: dict[str, Path],
    *,
    total_limit: int = MAX_TOTAL_INPUT_BYTES,
    artifact_limit: int = MAX_ARTIFACT_BYTES,
) -> tuple[dict[str, bytes], bytes]:
    if set(raw_paths) != set(RAW_ARGUMENTS):
        fail("ARGUMENT_MODE", "raw-file path set differs from the frozen interface")
    seed = read_bytes(raw_paths["seed_file"], "seed file", maximum=32)
    if len(seed) != 32:
        fail("SEED_LENGTH", "answer blinding seed must be exactly 32 bytes")
    if total_limit < len(seed):
        fail("INPUT_RESOURCE", "seed exhausts the global input-byte cap")
    raw: dict[str, bytes] = {}
    total = len(seed)
    for key in RAW_ARGUMENTS:
        if key == "seed_file":
            continue
        remaining = total_limit - total
        if remaining <= 0:
            fail("INPUT_RESOURCE", "artifact set exceeds the global input-byte cap")
        maximum = min(artifact_limit, remaining)
        oversize_code = "INPUT_RESOURCE" if remaining < artifact_limit else "FILE_SIZE"
        value = read_bytes(
            raw_paths[key],
            key.replace("_", " "),
            maximum=maximum,
            oversize_code=oversize_code,
        )
        raw[key] = value
        total += len(value)
    return raw, seed


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
                "choose one fixture/request or provide the complete eleven-file raw mode",
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
            raw, seed = read_raw_file_set(raw_paths)
            commitment_inputs = {**raw, "seed": seed}
            result = validate_artifact_bytes(
                root,
                contract_core_raw=raw["contract_core"],
                eligible_frame_manifest_raw=raw["eligible_frame_manifest"],
                blind_map_raw=raw["blind_map"],
                sampling_receipt_write_request_raw=raw[
                    "sampling_receipt_write_request"
                ],
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
