#!/usr/bin/env python3
"""Independently validate the Track B offline fault-injection harness v1 pack."""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


LOGICAL_BASELINE_COMMIT = "0be03cfdbee77f0bc29559e0795fa3ec77f07357"
PREDECESSOR_SOURCE_COMMIT = "8640a7ef39319befbbb265376c26dec03910db25"
CONTRACT_SHA256 = "632dbf1d8202d94d6aef70d8b20c04050e647679da973d81afbe13d68344ad22"
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_OFFLINE_HARNESS_V1_IMPLEMENTED_"
    "SYNTHETIC_ONLY_NO_PROVIDER_INVOCATION"
)
DECISION = "OFFLINE_HARNESS_PASS_PROVIDER_EXPERIMENT_REMAINS_BLOCKED"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "AUTHORITY_AND_ADAPTER_CONTRACT"
)
PACK_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "offline_harness_v1_pack_manifest.v0"
)
SYNTHETIC_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "offline_harness_configuration.v1"
)
RESULT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "offline_harness_v1_pack_validation_result.v0"
)
RUN_ROW_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "offline_harness_run_row.v1"
)
SUITE_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_"
    "offline_harness_suite_receipt.v1"
)
MANAGED_TRACK = "MANAGED_SPANNER_CLOUD_KMS"
SELF_HOSTED_TRACK = "SELF_HOSTED_ETCD_OPENBAO"
SCHEDULE_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/schedule"
)
RUN_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/run"
)
NAMESPACE_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/namespace"
)

SOURCE_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_harness_v1.py"
)
CHECKER_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.py"
)
CONTRACT_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-experiment-contract-v1.json"
)
SCHEDULE_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-schedule-entry-schema-v1.json"
)
RUN_ROW_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-run-row-schema-v1.json"
)
SUITE_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-suite-receipt-schema-v1.json"
)
SYNTHETIC_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_synthetic_v0.json"
)
EXPECTED_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.expected.v0.tsv"
)
MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_v0.json"
)
REPORT_PATH = Path(
    "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-offline-harness-v1-pack.md"
)
GATE_PATH = Path(
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-v1-pack.sh"
)
PREDECESSOR_MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_v0.json"
)

EXPECTED_PREDECESSOR_HASHES = {
    str(CONTRACT_PATH): CONTRACT_SHA256,
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1.py": "1644a95f21144b28335ca107638245fcc605add4b0ba438dafb50fab6e65a1e0",
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.py": "874f5f5ac44e4a481f99fd7c23755067c2dba9d848df5ad5a43cb5f26ba422f8",
    str(PREDECESSOR_MANIFEST_PATH): "4f15f205539796213ee6f7d0694b7c6bcaf69dae6014b1d084d66228b96486df",
    "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-preregistration-v1-pack.md": "6f6bbdf6c71ccb1a4eba916be90aa4f35a72548c9e3faf08980727625ba147c1",
}
PREDECESSOR_PACKET_PATHS = [
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-preregistration-receipt-schema-v1.json",
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-pre-execution-observation-schema-v1.json",
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-experiment-contract-v1.json",
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1.py",
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.py",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_synthetic_v0.json",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.expected.v0.tsv",
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_v0.json",
    "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-preregistration-v1-pack.md",
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-preregistration-v1-pack.sh",
]
REPORT_BOUND_PATHS = [
    str(SCHEDULE_SCHEMA_PATH),
    str(RUN_ROW_SCHEMA_PATH),
    str(SUITE_SCHEMA_PATH),
    str(SOURCE_PATH),
    str(CHECKER_PATH),
    str(SYNTHETIC_PATH),
    str(EXPECTED_PATH),
    *PREDECESSOR_PACKET_PATHS,
]

MESSAGE_HEX = (
    "0000005d6167656e742d6272696467652f62696f636f727465782d61622f747261636b2d62"
    "2f65787465726e616c2d61746f6d69632d6c6976652d6f75747075742f617574686f726974"
    "792d6465636973696f6e2d7369676e61747572652f76310000000000000020000102030405"
    "060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
)
MESSAGE_SHA256 = "f5dcb16eec00a302bf56c9cc681b5c09d598589c4c3e9ab2413b68c21f16982d"
PUBLIC_KEY_HEX = "03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8"
SIGNATURE_HEX = (
    "a93bd4857e41a015737960804da71913927d63754ee11ad79b604a48f4a1eaee"
    "f3f193ee7224c755b7792d62662f938000cc0ddad7531af9582f3047e51fa601"
)
MANAGED_EXACT_KEY_VERSION_RESOURCE = (
    "projects/offline-double/locations/global/keyRings/track-b/cryptoKeys/"
    "reference/cryptoKeyVersions/7"
)
MANAGED_KEY_VERSION = 7
MANAGED_ISOLATION = "SERIALIZABLE"
MANAGED_PROTECTION_LEVEL = "HSM"
SELF_HOSTED_KEY_VERSION = 2
NOT_APPLICABLE = "NOT_APPLICABLE"


class PackError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def fail(code: str, message: str) -> None:
    raise PackError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


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
        fail("E_CANONICAL", f"cannot canonicalize JSON: {exc}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def crc32c_reference(raw: bytes) -> int:
    """Independent reflected Castagnoli CRC32C implementation."""

    crc = 0xFFFFFFFF
    for octet in raw:
        crc ^= octet
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "E_DUPLICATE_JSON_KEY", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: fail("E_NONFINITE_JSON", f"{label} has {token}"),
            object_pairs_hook=_reject_pairs,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("E_LOAD", f"cannot load {label}: {exc}")
    require(type(value) is dict, "E_ROOT_TYPE", f"{label} root must be an object")
    require(canonical_bytes(value) == raw, "E_NOT_CANONICAL", f"{label} is not canonical JSON")
    return value, raw


def _type_matches(value: Any, expected: str) -> bool:
    return {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "integer": type(value) is int,
        "number": type(value) in (int, float) and type(value) is not bool,
        "boolean": type(value) is bool,
        "null": value is None,
    }.get(expected, False)


def _resolve_ref(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    require(reference.startswith("#/$defs/"), "E_SCHEMA_REF", f"unsupported ref {reference}")
    name = reference.removeprefix("#/$defs/")
    result = root_schema.get("$defs", {}).get(name)
    require(type(result) is dict, "E_SCHEMA_REF", f"unresolved ref {reference}")
    return result


def validate_json_schema(
    instance: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> None:
    root = root_schema or schema
    if "$ref" in schema:
        validate_json_schema(instance, _resolve_ref(root, schema["$ref"]), root_schema=root, path=path)
        return
    if "const" in schema:
        require(instance == schema["const"] and type(instance) is type(schema["const"]), "E_SCHEMA_CONST", f"{path} const mismatch")
    if "enum" in schema:
        require(instance in schema["enum"], "E_SCHEMA_ENUM", f"{path} enum mismatch")
    if "type" in schema:
        expected = schema["type"]
        if type(expected) is list:
            matches = any(_type_matches(instance, item) for item in expected)
        else:
            matches = type(expected) is str and _type_matches(instance, expected)
        require(matches, "E_SCHEMA_TYPE", f"{path} type mismatch")
    if type(instance) is dict:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        require(type(properties) is dict and type(required) is list, "E_SCHEMA_SHAPE", f"{path} object schema drift")
        for key in required:
            require(key in instance, "E_SCHEMA_REQUIRED", f"{path}.{key} missing")
        additional = schema.get("additionalProperties", True)
        if additional is False:
            require(set(instance) <= set(properties), "E_SCHEMA_ADDITIONAL", f"{path} has additional properties")
        for key, value in instance.items():
            if key in properties:
                validate_json_schema(value, properties[key], root_schema=root, path=f"{path}.{key}")
            elif type(additional) is dict:
                validate_json_schema(value, additional, root_schema=root, path=f"{path}.{key}")
    if type(instance) is list:
        if "minItems" in schema:
            require(len(instance) >= schema["minItems"], "E_SCHEMA_MIN_ITEMS", f"{path} too short")
        if "maxItems" in schema:
            require(len(instance) <= schema["maxItems"], "E_SCHEMA_MAX_ITEMS", f"{path} too long")
        if schema.get("uniqueItems") is True:
            serialized = [canonical_bytes(item) for item in instance]
            require(len(serialized) == len(set(serialized)), "E_SCHEMA_UNIQUE", f"{path} is not unique")
        if "items" in schema:
            for index, item in enumerate(instance):
                validate_json_schema(item, schema["items"], root_schema=root, path=f"{path}[{index}]")
    if type(instance) is str:
        if "pattern" in schema:
            require(re.fullmatch(schema["pattern"], instance) is not None, "E_SCHEMA_PATTERN", f"{path} pattern mismatch")
        if "minLength" in schema:
            require(len(instance) >= schema["minLength"], "E_SCHEMA_MIN_LENGTH", f"{path} too short")
    if type(instance) is int:
        if "minimum" in schema:
            require(instance >= schema["minimum"], "E_SCHEMA_MINIMUM", f"{path} below minimum")
        if "maximum" in schema:
            require(instance <= schema["maximum"], "E_SCHEMA_MAXIMUM", f"{path} above maximum")


def validate_schema_document(schema: dict[str, Any], expected_id: str, label: str) -> None:
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "E_SCHEMA_DRAFT", f"{label} draft drift")
    require(schema.get("$id") == expected_id, "E_SCHEMA_ID", f"{label} id drift")
    require(schema.get("type") == "object", "E_SCHEMA_ROOT", f"{label} root type drift")
    require(schema.get("additionalProperties") is False, "E_SCHEMA_OPEN", f"{label} root is open")
    require(set(schema.get("properties", {})) == set(schema.get("required", [])), "E_SCHEMA_CLOSURE", f"{label} root closure drift")


def _framed_hash_bytes(domain: str, *parts: bytes) -> str:
    framed = bytearray()
    domain_raw = domain.encode("utf-8")
    framed.extend(len(domain_raw).to_bytes(4, "big"))
    framed.extend(domain_raw)
    for part in parts:
        framed.extend(len(part).to_bytes(4, "big"))
        framed.extend(part)
    return sha256_bytes(bytes(framed))


def _framed_hash(domain: str, *parts: str) -> str:
    return _framed_hash_bytes(
        domain,
        *(part.encode("utf-8") for part in parts),
    )


ZERO_SHA256 = "0" * 64
EXACT_KEY_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/"
    "exact-operation-key"
)
WITNESS_DOMAIN = (
    "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/"
    "external-restore-witness"
)
WITNESS_ACTOR_DOMAIN = "OUTSIDE_ETCD_SNAPSHOT_AND_RESTORE_DOUBLE"
EVIDENCE_CLASS = "OFFLINE_DOUBLE_SIMULATION_ONLY_NOT_PROVIDER_OR_LAB_EVIDENCE"
STATE_FIELDS = {
    "attempt", "attempt_consumed", "authority", "cache", "call_binding_sha256",
    "challenge_consumptions", "database_attempts", "emitted_outputs",
    "durable_operation_record_sha256", "durable_operation_revision",
    "logical_sink_reservations", "outbox", "prepared_attempt_sequence",
    "prepared_key_version", "prepared_message_sha256", "prepared_operation_id",
    "prepared_public_key_sha256", "prepared_record_sha256", "prepared_request_sha256",
    "processed_response_sha256", "receipt", "receipt_binding_sha256", "restarts",
    "restore", "restore_cluster_id", "restore_incarnation_id", "restore_revision_floor",
    "simulated_application_calls", "simulated_processing_events", "terminal_fence",
    "validated_response_sha256", "validation_binding_sha256", "watch",
    "witness_generation", "witness_record_sha256",
}
INITIAL_STATE = {
    "attempt": "NONE", "attempt_consumed": False, "authority": "EMPTY",
    "cache": "NOT_APPLICABLE", "call_binding_sha256": ZERO_SHA256,
    "challenge_consumptions": 0, "database_attempts": 0, "emitted_outputs": 0,
    "durable_operation_record_sha256": ZERO_SHA256,
    "durable_operation_revision": 0,
    "logical_sink_reservations": 0, "outbox": "NONE",
    "prepared_attempt_sequence": 0, "prepared_key_version": 0,
    "prepared_message_sha256": ZERO_SHA256, "prepared_operation_id": ZERO_SHA256,
    "prepared_public_key_sha256": ZERO_SHA256, "prepared_record_sha256": ZERO_SHA256,
    "prepared_request_sha256": ZERO_SHA256, "processed_response_sha256": ZERO_SHA256,
    "receipt": "NONE", "receipt_binding_sha256": ZERO_SHA256, "restarts": 0,
    "restore": "NOT_APPLICABLE", "restore_cluster_id": "NOT_APPLICABLE",
    "restore_incarnation_id": "NOT_APPLICABLE", "restore_revision_floor": 0,
    "simulated_application_calls": 0, "simulated_processing_events": 0,
    "terminal_fence": "NONE", "validated_response_sha256": ZERO_SHA256,
    "validation_binding_sha256": ZERO_SHA256, "watch": "NOT_APPLICABLE",
    "witness_generation": 0, "witness_record_sha256": ZERO_SHA256,
}
PREPARED_FIELDS = {
    "operation_id", "canonical_request_sha256", "exact_key_version",
    "public_key_pin_sha256", "message_sha256", "attempt_sequence",
}
OPERATION_RECORD_FIELDS = {
    "record_kind", "operation_id", "authority", "outbox", "attempt",
    "attempt_consumed", "receipt", "challenge_consumptions",
    "logical_sink_reservations", "message_sha256", "exact_key_version",
    "public_key_pin_sha256", "prepared_record_sha256", "call_binding_sha256",
    "processed_response_sha256", "validated_response_sha256",
    "validation_binding_sha256", "receipt_binding_sha256", "terminal",
}
TRANSITION_ENVELOPE_FIELDS = {
    "phase", "store_kind", "operation_id", "operation_key", "consistency",
    "nested", "leased", "compare_record_sha256", "observed_record_sha256",
    "expected_mod_revision", "committed_record_sha256", "committed_revision",
    "top_level_revision", "mutation_count", "cas_result",
    "response_revision_source",
}
WITNESS_FIELDS = {
    "domain", "authority_id", "prior_cluster_id", "prior_incarnation_id",
    "prior_revision_floor", "snapshot_sha256", "snapshot_revision", "new_cluster_id",
    "new_incarnation_id", "new_revision_floor", "bump_revision", "mark_compacted",
    "rebase_authorization_sha256", "previous_record_sha256", "generation",
}
EVENT_DETAIL_KEYS: dict[str, set[str]] = {
    "ALL_PRE_RESTORE_WATCHES_INVALIDATED": {"new_cluster_id", "new_incarnation_id"},
    "ASSIGNMENT_HASH_SEALED": {"assignment_sha256", "simulation_run_id"},
    "CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM": {"assignment_sha256", "case_id"},
    "CONTROL_NO_FAULT_TRIGGERED": {"case_id", "trigger_count"},
    "DURABLE_IMAGE_SERIALIZED": {"durable_image", "image_sha256"},
    "EPHEMERAL_WORKER_DESTROYED": set(),
    "ETCD_BARE_ABSENT_LINEARIZABLE_READ": {"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"},
    "ETCD_CONFIRMING_LINEARIZABLE_READ": {"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"},
    "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION": {"cas_result", "operation_key", "record_sha256", "revision"},
    "ETCD_DELAYED_COMMIT_FENCE_CONFLICT": {"cas_result", "compare_record_sha256", "delayed_record_sha256", "observed_record_sha256", "operation_key", "revision"},
    "ETCD_EXACT_LINEARIZABLE_LOOKUP": {"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"},
    "ETCD_FOLLOWER_ISOLATED": {"follower_state_accepted"},
    "ETCD_LEADER_LOST_POSTCOMMIT": set(),
    "ETCD_LEADER_REMOVED_AFTER_REQUEST_ADMISSION": {"operation_key"},
    "ETCD_LINEARIZABLE_EXACT_RECEIPT_LOOKUP": {"operation_id", "receipt_binding_sha256", "result"},
    "ETCD_LINEARIZABLE_READ_REACHED_QUORUM": set(),
    "ETCD_LINEARIZABLE_READ_UNAVAILABLE_FAIL_CLOSED": set(),
    "ETCD_LINEARIZABLE_REVISION_ADVANCED": set(),
    "ETCD_NESTED_TRANSACTION_REJECTED": {"nested"},
    "ETCD_OUTBOX_COMMITTED": {"outbox"},
    "ETCD_QUORUM_LOST": {"result"},
    "ETCD_RECEIPT_PERSIST_OUTCOME_UNKNOWN": set(),
    "ETCD_REQUEST_ADMITTED_WITH_PENDING_COMMIT": {"delayed_record_sha256", "operation_key"},
    "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS": {"cas_result", "committed_record_sha256", "compare_record_sha256", "consistency", "operation_key", "revision"},
    "ETCD_SERIALIZABLE_READ_MODE_REJECTED": {"serializable"},
    "ETCD_TOP_LEVEL_CAS": {"leased", "nested", "response_revision_source", "serializable"},
    "ETCD_TRANSACTION_ACK_DROPPED": set(),
    "ETCD_WATCH_DELAYED": {"authority_use"},
    "EXTERNAL_WITNESS_LEDGER_OPENED": {
        "actor_domain", "current_record_sha256", "generation",
        "isolated_from_restore_snapshot", "logical_cluster_lineage_id",
        "observed_generation", "observed_record_sha256", "read_consistency",
        "read_revision", "witness_key",
    },
    "FULL_LINEARIZABLE_CACHE_REBUILD_COMPLETED": {"new_cluster_id", "revision_floor"},
    "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT": {"reason"},
    "KMS_RESOURCE_REJECTED_BEFORE_ATTEMPT": {"variant"},
    "LOSING_WORKER_ATTEMPT_CAS_CONFLICT": {"simulated_calls"},
    "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE": {"prior_worker_ephemeral_state_reused", "state_object_reused"},
    "ONE_SHOT_FAULT_CONTROLLER_ARMED": {"assignment_sha256", "case_id", "injection_cut", "injection_variant", "trigger_limit"},
    "ONE_SHOT_FAULT_TRIGGERED": {"case_id", "causal_binding_sha256", "injection_cut", "injection_variant", "trigger_count"},
    "OPENBAO_DIRECT_TARGET_SEAL_STATUS": {"cluster_id", "sealed", "service_wide_unavailable_inferred", "target_ha_role", "target_node"},
    "OPENBAO_KEY_ROTATED": {"frozen_version", "latest_version"},
    "OPENBAO_PINNED_VERSION_UNAVAILABLE_REJECTED": {"latest_substitution"},
    "OPENBAO_ROUTE_EXECUTION_EVIDENCE": {"audit_record_sha256", "cluster_id", "executing_ha_role", "executing_node", "forwarded_by_node", "redirect_forward_audit_bound", "redirect_node", "request_id", "route_node", "target_node", "wire_attempt_sha256"},
    "OPENBAO_STANDBY_TAKEOVER_UNAVAILABLE_FAIL_CLOSED": {"accepted_receipts", "cluster_id", "emitted_outputs", "request_id"},
    "RESTART_NO_RESIGN_CONFIRMED": {"calls_after_restart"},
    "RESTORED_CLUSTER_INCIDENT_QUARANTINED": {"variant", "witness_generation", "witness_record_sha256"},
    "RESTORE_REVISION_BUMPED_AND_MARKED_COMPACTED": {"bump_revision", "mark_compacted", "new_revision_floor", "prior_revision_floor", "snapshot_revision"},
    "RESTORE_WITNESS_CANDIDATE_STAGED": {"snapshot_sha256", "witness_record_sha256"},
    "SNAPSHOT_HASH_VERIFIED": {"skip_hash_check", "snapshot_revision", "snapshot_sha256"},
    "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION": {"cas_result", "committed_record_sha256", "compare_record_sha256", "consistency", "operation_key", "revision"},
    "SPANNER_BARE_ABSENT_STRONG_READ": {"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"},
    "SPANNER_CLOSURE_SIDE_EFFECT_SENTINEL_REJECTED": {"attempted"},
    "SPANNER_COMMIT_ADMITTED_OUTCOME_UNRESOLVED": {"delayed_record_sha256", "operation_key"},
    "SPANNER_COMMIT_RESPONSE_LOST": {"operation_key", "record_sha256", "server_commit"},
    "SPANNER_CONFIRMING_STRONG_READ": {"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"},
    "SPANNER_DEFINITE_ABORT": {"attempt"},
    "SPANNER_DELAYED_COMMIT_FENCE_CONFLICT": {"cas_result", "compare_record_sha256", "delayed_record_sha256", "observed_record_sha256", "operation_key", "revision"},
    "SPANNER_EXACT_STRONG_LOOKUP": {"consistency", "operation_key", "record_sha256", "result", "revision", "terminal"},
    "SPANNER_ISOLATION_PROFILE_REJECTED": {"requested", "required"},
    "SPANNER_OUTBOX_COMMITTED": {"outbox"},
    "SPANNER_RECEIPT_PERSIST_OUTCOME_UNKNOWN": set(),
    "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT": {"attempt", "closure_scope"},
    "SPANNER_SERVER_COMMIT_APPLIED": {"operation_key", "record_sha256", "revision"},
    "SPANNER_STRONG_EXACT_RECEIPT_LOOKUP": {"operation_id", "receipt_binding_sha256", "result"},
    "TRANSIT_ZERO_VERSION_REJECTED_BEFORE_ATTEMPT": set(),
    "TWO_WORKERS_RELEASED": {"workers"},
    "WORKER_CRASHED_BEFORE_ATTEMPT_CAS": set(),
    "WORKER_RESTARTED": {"calls_before_restart", "durable_attempt_state"},
}
_WITNESS_EVENT_KEYS = {
    "actor_domain", "caller_actor_domain", "cas_result", "expected_generation",
    "expected_previous_record_sha256", "observed_generation",
    "logical_cluster_lineage_id", "observed_previous_record_sha256",
    "observed_witness_key", "rejection_reason",
    "witness_key", "witness_record", "witness_record_sha256",
}
_CALL_EVENT_KEYS = {
    "attempt_sequence", "audit_record_sha256", "call_binding_sha256", "evidence_class",
    "executing_node", "execution_cluster_id", "execution_request_id", "hidden_retries",
    "key_version", "message_sha256", "operation_id", "prepared_record_sha256",
    "public_key_sha256", "request_sha256", "wire_attempt_sha256",
}
_VALIDATION_EVENT_KEYS = {
    "audit_record_sha256", "call_binding_sha256", "executing_node", "execution_cluster_id",
    "execution_request_id", "key_version", "message_bytes", "message_sha256",
    "operation_id", "public_key_sha256", "request_sha256", "response_sha256",
    "validation_binding_sha256", "wire_attempt_sha256",
}
_RECEIPT_EVENT_KEYS = {
    "audit_record_sha256", "call_binding_sha256", "executing_node", "execution_cluster_id",
    "execution_request_id", "key_version", "message_sha256", "operation_id",
    "prepared_record_sha256", "public_key_sha256", "receipt_binding_sha256",
    "request_sha256", "response_sha256", "validation_binding_sha256",
    "wire_attempt_sha256",
}
for _event_name in (
    "EXTERNAL_WITNESS_EXACT_CAS_COMMITTED", "EXTERNAL_WITNESS_VALIDATION_FAILED",
    "RESTORE_IDENTITY_OR_WITNESS_BINDING_REJECTED",
):
    EVENT_DETAIL_KEYS[_event_name] = _WITNESS_EVENT_KEYS
for _kind in ("KMS", "TRANSIT"):
    EVENT_DETAIL_KEYS.update({
        f"{_kind}_AMBIGUOUS_QUARANTINED": {"call_binding_sha256", "operation_id", "prepared_record_sha256", "validation_binding_sha256"},
        f"{_kind}_DOUBLE_CALL": _CALL_EVENT_KEYS,
        f"{_kind}_DOUBLE_PROCESSING_COMPLETED": {"call_binding_sha256", "response_sha256"},
        f"{_kind}_DOUBLE_RESPONSE_DROPPED": {"call_binding_sha256", "response_sha256"},
        f"{_kind}_DOUBLE_RESPONSE_OBSERVED": {"call_binding_sha256", "response_sha256"},
        f"{_kind}_RESPONSE_FULLY_VALIDATED": _VALIDATION_EVENT_KEYS,
        f"{_kind}_RESPONSE_REJECTED": {"call_binding_sha256", "operation_id", "prepared_record_sha256", "reason"},
        f"{_kind}_SIGNATURE_RECEIPT_COMMITTED": _RECEIPT_EVENT_KEYS,
        f"{_kind}_SIGN_ATTEMPT_PREPARED": {"durable", "prepared_record", "prepared_record_sha256"},
    })
_TRANSITION_COMMIT_EVENT_KEYS = {
    "transition_envelope", "transition_record", "transition_record_sha256",
}
EVENT_DETAIL_KEYS["SPANNER_OUTBOX_COMMITTED"] = {
    "outbox", *_TRANSITION_COMMIT_EVENT_KEYS,
}
EVENT_DETAIL_KEYS["ETCD_TOP_LEVEL_CAS"] = {
    "leased", "nested", "response_revision_source", "serializable",
    *_TRANSITION_COMMIT_EVENT_KEYS,
}
EVENT_DETAIL_KEYS["ETCD_NESTED_TRANSACTION_REJECTED"] = {
    "nested", "transition_envelope",
}
for _event_name in (
    "SPANNER_SERVER_COMMIT_APPLIED",
    "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION",
    "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION",
    "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS",
):
    EVENT_DETAIL_KEYS[_event_name] |= _TRANSITION_COMMIT_EVENT_KEYS
for _kind in ("KMS", "TRANSIT"):
    EVENT_DETAIL_KEYS[f"{_kind}_SIGN_ATTEMPT_PREPARED"] = {
        "durable", "prepared_record", "prepared_record_sha256",
        *_TRANSITION_COMMIT_EVENT_KEYS,
    }
    EVENT_DETAIL_KEYS[f"{_kind}_SIGN_ATTEMPT_CALL_CONSUMED"] = set(
        _TRANSITION_COMMIT_EVENT_KEYS
    )
    EVENT_DETAIL_KEYS[f"{_kind}_SIGNATURE_RECEIPT_COMMITTED"] = {
        *_RECEIPT_EVENT_KEYS, *_TRANSITION_COMMIT_EVENT_KEYS,
    }
    EVENT_DETAIL_KEYS[f"{_kind}_AMBIGUOUS_QUARANTINED"] = {
        "call_binding_sha256", "operation_id", "prepared_record_sha256",
        "validation_binding_sha256", *_TRANSITION_COMMIT_EVENT_KEYS,
    }
    EVENT_DETAIL_KEYS[f"{_kind}_RESPONSE_REJECTED"] = {
        "call_binding_sha256", "operation_id", "prepared_record_sha256", "reason",
        *_TRANSITION_COMMIT_EVENT_KEYS,
    }
for _event_name in (
    "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT",
    "KMS_RESOURCE_REJECTED_BEFORE_ATTEMPT",
    "OPENBAO_PINNED_VERSION_UNAVAILABLE_REJECTED",
    "TRANSIT_ZERO_VERSION_REJECTED_BEFORE_ATTEMPT",
):
    EVENT_DETAIL_KEYS[_event_name] |= _TRANSITION_COMMIT_EVENT_KEYS


def independent_schedule(contract: dict[str, Any], config_sha: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track in contract["tracks"]:
        track_id = track["track_id"]
        case_ids = [case["case_id"] for case in track["cases"]]
        for repetition in range(1, 31):
            ordered = sorted(
                case_ids,
                key=lambda case_id: _framed_hash_bytes(
                    SCHEDULE_DOMAIN,
                    track_id.encode(),
                    repetition.to_bytes(4, "big"),
                    case_id.encode(),
                ),
            )
            assignment = {
                "domain": SCHEDULE_DOMAIN,
                "track_id": track_id,
                "repetition_index": repetition,
                "ordered_case_ids": ordered,
                "configuration_sha256": config_sha,
                "contract_sha256": CONTRACT_SHA256,
            }
            assignment_sha = sha256_value(assignment)
            for position, case_id in enumerate(ordered, start=1):
                simulation_run_id = _framed_hash_bytes(
                    RUN_DOMAIN,
                    track_id.encode(),
                    case_id.encode(),
                    repetition.to_bytes(4, "big"),
                    bytes.fromhex(config_sha),
                    bytes.fromhex(assignment_sha),
                )
                rows.append(
                    {
                        "track_id": track_id,
                        "case_id": case_id,
                        "repetition_index": repetition,
                        "block_position": position,
                        "assignment_sha256": assignment_sha,
                        "configuration_sha256": config_sha,
                        "simulation_run_id": simulation_run_id,
                        "namespace_id": _framed_hash_bytes(
                            NAMESPACE_DOMAIN, bytes.fromhex(simulation_run_id)
                        ),
                        "assignment_before_candidate_start": True,
                        "injection_armed_before_candidate_start": True,
                    }
                )
    return rows


STATIC_CLASSIFICATIONS = {
    "M00": "CONFORMING_OBSERVED",
    "M01": "RECOVERED_BY_DATABASE_ONLY_RETRY",
    "M02": "FAIL_CLOSED_REJECTED",
    "M03": "FAIL_CLOSED_REJECTED",
    "M04": "RECOVERED_BY_STRONG_LOOKUP",
    "M05": "FAIL_CLOSED_REJECTED",
    "M06": "FAIL_CLOSED_REJECTED",
    "M07": "FAIL_CLOSED_REJECTED",
    "M08": "FAIL_CLOSED_REJECTED",
    "M09": "FAIL_CLOSED_REJECTED",
    "M10": "FAIL_CLOSED_REJECTED",
    "M11": "FAIL_CLOSED_REJECTED",
    "M12": "AMBIGUOUS_QUARANTINED",
    "M14": "CONFORMING_OBSERVED",
    "M15": "RECOVERED_BY_STRONG_LOOKUP",
    "S00": "CONFORMING_OBSERVED",
    "S02": "FAIL_CLOSED_REJECTED",
    "S03": "FAIL_CLOSED_REJECTED",
    "S04": "RECOVERED_BY_STRONG_LOOKUP",
    "S05": "RECOVERED_BY_STRONG_LOOKUP",
    "S06": "RECOVERED_BY_STRONG_LOOKUP",
    "S07": "FAIL_CLOSED_REJECTED",
    "S08": "FAIL_CLOSED_REJECTED",
    "S09": "INCIDENT_QUARANTINED",
    "S10": "INCIDENT_QUARANTINED",
    "S11": "REBASED_NEW_INCARNATION",
    "S13": "AMBIGUOUS_QUARANTINED",
    "S16": "FAIL_CLOSED_REJECTED",
    "S17": "FAIL_CLOSED_REJECTED",
}

VARIANTS = {
    "M04": [
        "DROP_COMMIT_RESPONSE_AFTER_SERVER_COMMIT",
        "DROP_COMMIT_RESPONSE_WHILE_COMMIT_OUTCOME_IS_UNRESOLVED",
    ],
    "M07": [
        "COMPUTE_DATA_CRC32C_OVER_BASE64_TEXT",
        "RETURN_VERIFIED_DATA_CRC32C_FALSE",
    ],
    "M08": [
        "OMIT_CRYPTOKEYVERSION_SEGMENT",
        "SET_CRYPTOKEYVERSION_SEGMENT_TO_ZERO",
        "USE_PARENT_CRYPTOKEY_RESOURCE",
        "USE_NONCANONICAL_LEADING_ZERO_VERSION",
        "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME",
    ],
    "S09": [
        "RESTORE_OLDER_SNAPSHOT_WITHOUT_BUMP",
        "RETURN_STALE_REPLAYED_OR_FORKED_WITNESS_RECORD",
        "MAKE_INDEPENDENT_WITNESS_UNAVAILABLE_OR_CAS_CONFLICT",
    ],
    "S12": [
        "SEALED_ACTIVE_WITH_VALIDATED_STANDBY_TAKEOVER",
        "SEALED_ACTIVE_WITH_NO_VALIDATED_SUCCESSOR_RESPONSE",
    ],
    "S15": [
        "ROTATE_KEY_PINNED_VERSION_REMAINS_AVAILABLE",
        "ROTATE_KEY_PINNED_VERSION_UNAVAILABLE",
    ],
    "S17": [
        "MUTATE_SIGNATURE_VERSION_PREFIX",
        "MUTATE_PUBLIC_KEY_PIN",
        "MUTATE_MESSAGE",
    ],
}

REQUIRED_EVENTS = {
    "M00": ("SPANNER_OUTBOX_COMMITTED", "KMS_SIGN_ATTEMPT_PREPARED", "KMS_RESPONSE_FULLY_VALIDATED", "KMS_SIGNATURE_RECEIPT_COMMITTED"),
    "M01": ("SPANNER_DEFINITE_ABORT", "SPANNER_OUTBOX_COMMITTED", "KMS_SIGNATURE_RECEIPT_COMMITTED"),
    "M02": ("SPANNER_CLOSURE_SIDE_EFFECT_SENTINEL_REJECTED",),
    "M03": ("SPANNER_ISOLATION_PROFILE_REJECTED",),
    "M04": ("SPANNER_COMMIT_RESPONSE_LOST",),
    "M05": ("KMS_REQUEST_REJECTED_BEFORE_ATTEMPT",),
    "M06": ("KMS_REQUEST_REJECTED_BEFORE_ATTEMPT",),
    "M07": ("KMS_DOUBLE_CALL", "KMS_RESPONSE_REJECTED"),
    "M08": (),
    "M09": ("KMS_DOUBLE_CALL", "KMS_RESPONSE_REJECTED"),
    "M10": ("KMS_DOUBLE_CALL", "KMS_RESPONSE_REJECTED"),
    "M11": ("KMS_DOUBLE_CALL", "KMS_RESPONSE_REJECTED"),
    "M12": ("KMS_DOUBLE_RESPONSE_DROPPED", "KMS_AMBIGUOUS_QUARANTINED", "DURABLE_IMAGE_SERIALIZED", "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE"),
    "M13": ("SPANNER_RECEIPT_PERSIST_OUTCOME_UNKNOWN", "SPANNER_STRONG_EXACT_RECEIPT_LOOKUP", "DURABLE_IMAGE_SERIALIZED"),
    "M14": ("TWO_WORKERS_RELEASED", "LOSING_WORKER_ATTEMPT_CAS_CONFLICT", "KMS_SIGNATURE_RECEIPT_COMMITTED"),
    "M15": ("WORKER_CRASHED_BEFORE_ATTEMPT_CAS", "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE", "KMS_SIGNATURE_RECEIPT_COMMITTED"),
    "S00": ("ETCD_TOP_LEVEL_CAS", "TRANSIT_SIGN_ATTEMPT_PREPARED", "TRANSIT_RESPONSE_FULLY_VALIDATED", "TRANSIT_SIGNATURE_RECEIPT_COMMITTED"),
    "S01": ("ETCD_FOLLOWER_ISOLATED",),
    "S02": ("ETCD_SERIALIZABLE_READ_MODE_REJECTED",),
    "S03": ("ETCD_NESTED_TRANSACTION_REJECTED",),
    "S04": ("ETCD_LEADER_REMOVED_AFTER_REQUEST_ADMISSION",),
    "S05": ("ETCD_LEADER_LOST_POSTCOMMIT", "ETCD_EXACT_LINEARIZABLE_LOOKUP"),
    "S06": ("ETCD_TRANSACTION_ACK_DROPPED", "ETCD_EXACT_LINEARIZABLE_LOOKUP"),
    "S07": ("ETCD_QUORUM_LOST",),
    "S08": ("ETCD_WATCH_DELAYED", "ETCD_LINEARIZABLE_REVISION_ADVANCED"),
    "S09": ("EXTERNAL_WITNESS_VALIDATION_FAILED", "RESTORED_CLUSTER_INCIDENT_QUARANTINED"),
    "S10": ("SNAPSHOT_HASH_VERIFIED", "RESTORE_IDENTITY_OR_WITNESS_BINDING_REJECTED"),
    "S11": ("SNAPSHOT_HASH_VERIFIED", "EXTERNAL_WITNESS_EXACT_CAS_COMMITTED", "ALL_PRE_RESTORE_WATCHES_INVALIDATED", "FULL_LINEARIZABLE_CACHE_REBUILD_COMPLETED"),
    "S12": ("OPENBAO_DIRECT_TARGET_SEAL_STATUS", "OPENBAO_ROUTE_EXECUTION_EVIDENCE"),
    "S13": ("TRANSIT_DOUBLE_RESPONSE_DROPPED", "TRANSIT_AMBIGUOUS_QUARANTINED", "DURABLE_IMAGE_SERIALIZED"),
    "S14": ("ETCD_RECEIPT_PERSIST_OUTCOME_UNKNOWN", "ETCD_LINEARIZABLE_EXACT_RECEIPT_LOOKUP", "DURABLE_IMAGE_SERIALIZED"),
    "S15": ("OPENBAO_KEY_ROTATED",),
    "S16": ("TRANSIT_ZERO_VERSION_REJECTED_BEFORE_ATTEMPT",),
    "S17": ("TRANSIT_DOUBLE_CALL", "TRANSIT_RESPONSE_REJECTED"),
}

REQUIRED_TOKENS = {
    "M00": ("SERIALIZABLE_OUTBOX", "FULL_KMS_VALIDATION"),
    "M01": ("DATABASE_ONLY_RETRY", "NO_EXTERNAL_SIDE_EFFECT_REPLAY"),
    "M02": ("STATIC_CALL_GRAPH_REJECTED", "RUNTIME_SIDE_EFFECT_SENTINEL"),
    "M03": ("REQUESTED_ISOLATION_REJECTED",),
    "M04": ("UNKNOWN_NOT_BLINDLY_REISSUED",),
    "M05": ("DATA_ARM_REQUIRED", "DIGEST_ARM_ABSENT"),
    "M06": ("EXACT_137_BYTE_FRAME_REQUIRED",),
    "M07": ("CRC32C_OVER_RAW_BYTES",),
    "M08": ("EXACT_VERSION_RESOURCE_REQUIRED",),
    "M09": ("LOCAL_SIGNATURE_CRC32C",),
    "M10": ("EXACT_PROTECTION_ENUM",),
    "M11": ("OFFLINE_ED25519_VERIFY",),
    "M12": ("TERMINAL_QUARANTINE", "RESTART_NO_RESIGN"),
    "M13": ("IN_MEMORY_SIGNATURE_NOT_DURABLE", "RESTART_NO_RESIGN"),
    "M14": ("ONE_PREPARED_OWNER", "LOSER_ZERO_CALLS", "RECEIPT_NOT_PROVIDER_EVENT_PROOF"),
    "M15": ("DURABLE_OUTBOX_RECOVERY", "NO_REAUTHORIZE", "NO_RECONSUME_CHALLENGE"),
    "S00": ("LINEARIZABLE_AUTHORITY", "NON_NESTED_NONLEASED_CAS"),
    "S01": ("ISOLATED_FOLLOWER_STATE_REJECTED",),
    "S02": ("CANDIDATE_SERIALIZABLE_MODE_REJECTED_PREEXECUTION",),
    "S03": ("DECODED_NESTED_TXN_REJECTED_PREEXECUTION",),
    "S04": ("LEADER_ELECTION_NOT_ABORT_PROOF",),
    "S05": ("EXACT_COMMITTED_OPERATION_RECOVERED", "NO_BLIND_REISSUE"),
    "S06": ("EXACT_COMMITTED_OPERATION_RECOVERED", "NO_BLIND_REISSUE"),
    "S07": ("NO_SERIALIZABLE_FALLBACK",),
    "S08": ("WATCH_TELEMETRY_ONLY", "WATCH_CANNOT_AUTHORIZE"),
    "S09": ("INDEPENDENT_WITNESS_DOMAIN", "INVALID_WITNESS_FAILS_CLOSED"),
    "S10": ("BUMP_NOT_SELF_AUTHORIZING", "NEW_IDENTITY_REQUIRED"),
    "S11": ("VERIFIED_SNAPSHOT", "INDEPENDENT_WITNESS_EXACT_CAS", "FULL_LINEARIZABLE_REBUILD"),
    "S12": ("TARGET_AND_EXECUTING_NODE_SEPARATE", "NO_SERVICE_WIDE_FAILURE_INFERENCE"),
    "S13": ("TERMINAL_QUARANTINE", "RESTART_NO_RESIGN"),
    "S14": ("IN_MEMORY_SIGNATURE_NOT_DURABLE", "RESTART_NO_RESIGN"),
    "S15": ("EXPLICIT_FROZEN_VERSION", "LATEST_NOT_SUBSTITUTED"),
    "S16": ("ZERO_OR_OMITTED_VERSION_REJECTED", "LATEST_NOT_SELECTED"),
    "S17": ("SINGLE_NONBATCH_CONTEXT_FREE_REQUEST", "INVALID_BINDING_REJECTED"),
}

SEMANTIC_TOKEN_VECTORS = {
    "M00": (
        "SERIALIZABLE_OUTBOX", "PREPARED_BEFORE_DOUBLE_CALL",
        "FULL_KMS_VALIDATION", "DURABLE_RECEIPT",
    ),
    "M01": (
        "DATABASE_ONLY_RETRY", "STABLE_OPERATION_ID",
        "NO_EXTERNAL_SIDE_EFFECT_REPLAY", "FULL_KMS_VALIDATION",
    ),
    "M02": (
        "STATIC_CALL_GRAPH_REJECTED", "RUNTIME_SIDE_EFFECT_SENTINEL",
        "ZERO_DOUBLE_CALLS",
    ),
    "M03": (
        "REQUESTED_ISOLATION_REJECTED", "EFFECTIVE_ISOLATION_NOT_STARTED",
        "ZERO_DOUBLE_CALLS",
    ),
    "M04:odd": (
        "UNKNOWN_NOT_BLINDLY_REISSUED", "EXACT_RECORD_STRONG_LOOKUP",
        "OUTBOX_RECOVERED",
    ),
    "M04:even": (
        "UNKNOWN_NOT_BLINDLY_REISSUED", "BARE_ABSENCE_NONTERMINAL",
        "SAME_OPERATION_TERMINAL_FENCE", "CONFIRMING_STRONG_READ",
    ),
    "M05": ("DATA_ARM_REQUIRED", "DIGEST_ARM_ABSENT", "ZERO_DOUBLE_CALLS"),
    "M06": (
        "EXACT_137_BYTE_FRAME_REQUIRED", "MESSAGE_SHA256_MISMATCH_REJECTED",
        "ZERO_DOUBLE_CALLS",
    ),
    "M07:bad_crc": (
        "CRC32C_OVER_RAW_BYTES", "BASE64_TEXT_CRC_REJECTED",
        "EXPLICIT_DOUBLE_ERROR",
    ),
    "M07:false_flag": (
        "CRC32C_OVER_RAW_BYTES", "VERIFIED_DATA_CRC32C_REQUIRED",
        "FALSE_VERIFICATION_REJECTED",
    ),
    "M08:precall": (
        "EXACT_VERSION_RESOURCE_REQUIRED", "INVALID_RESOURCE_REJECTED_PRECALL",
        "ZERO_DOUBLE_CALLS",
    ),
    "M08:response_name": (
        "EXACT_VERSION_RESOURCE_REQUIRED", "RESPONSE_NAME_BYTE_EQUALITY",
        "MISMATCHED_RESPONSE_NAME_REJECTED",
    ),
    "M09": ("LOCAL_SIGNATURE_CRC32C", "CORRUPT_SIGNATURE_REJECTED"),
    "M10": ("EXACT_PROTECTION_ENUM", "HSM_ENUM_DISTINCTION"),
    "M11": (
        "PINNED_PUBLIC_KEY", "OFFLINE_ED25519_VERIFY",
        "INVALID_SIGNATURE_REJECTED",
    ),
    "M12": (
        "DURABLE_PREPARED_MARKER", "LOST_RESPONSE_NOT_NO_SIGN_PROOF",
        "TERMINAL_QUARANTINE", "RESTART_NO_RESIGN",
    ),
    "M13:recovered": (
        "IN_MEMORY_SIGNATURE_NOT_DURABLE", "EXACT_RECEIPT_RECOVERED",
        "RESTART_NO_RESIGN",
    ),
    "M13:quarantined": (
        "IN_MEMORY_SIGNATURE_NOT_DURABLE", "ABSENT_RECEIPT_QUARANTINED",
        "RESTART_NO_RESIGN",
    ),
    "M14": (
        "ONE_PREPARED_OWNER", "LOSER_ZERO_CALLS",
        "ONE_SIMULATED_APPLICATION_CALL", "RECEIPT_NOT_PROVIDER_EVENT_PROOF",
    ),
    "M15": (
        "DURABLE_OUTBOX_RECOVERY", "NO_REAUTHORIZE",
        "NO_RECONSUME_CHALLENGE", "ONE_SIMULATED_APPLICATION_CALL",
    ),
    "S00": (
        "LINEARIZABLE_AUTHORITY", "NON_NESTED_NONLEASED_CAS",
        "PREPARED_BEFORE_DOUBLE_CALL", "FULL_TRANSIT_VALIDATION",
    ),
    "S01:success": ("ISOLATED_FOLLOWER_STATE_REJECTED", "CURRENT_QUORUM_READ"),
    "S01:fail": ("ISOLATED_FOLLOWER_STATE_REJECTED", "NO_STALE_FALLBACK"),
    "S02": ("CANDIDATE_SERIALIZABLE_MODE_REJECTED_PREEXECUTION", "ZERO_DOUBLE_CALLS"),
    "S03": ("DECODED_NESTED_TXN_REJECTED_PREEXECUTION", "ZERO_DOUBLE_CALLS"),
    "S04:odd": (
        "LEADER_ELECTION_NOT_ABORT_PROOF", "EXACT_RECORD_LINEARIZABLE_LOOKUP",
        "NO_BLIND_REISSUE",
    ),
    "S04:even": (
        "LEADER_ELECTION_NOT_ABORT_PROOF", "BARE_ABSENCE_NONTERMINAL",
        "SAME_KEY_TERMINAL_FENCE", "CONFIRMING_LINEARIZABLE_READ",
    ),
    "S05": (
        "EXACT_COMMITTED_OPERATION_RECOVERED", "NO_BLIND_REISSUE",
        "TOP_LEVEL_REVISION_ONLY",
    ),
    "S06": (
        "EXACT_COMMITTED_OPERATION_RECOVERED", "NO_BLIND_REISSUE",
        "TOP_LEVEL_REVISION_ONLY",
    ),
    "S07": ("QUORUM_UNAVAILABLE", "NO_SERIALIZABLE_FALLBACK", "ZERO_DOUBLE_CALLS"),
    "S08": (
        "WATCH_TELEMETRY_ONLY", "WATCH_CANNOT_AUTHORIZE",
        "WATCH_CANNOT_RESOLVE_AMBIGUITY",
    ),
    "S09": (
        "INDEPENDENT_WITNESS_DOMAIN", "INVALID_WITNESS_FAILS_CLOSED",
        "NO_INCUMBENT_EPOCH_REJOIN",
    ),
    "S10": (
        "BUMP_NOT_SELF_AUTHORIZING", "NEW_IDENTITY_REQUIRED",
        "EXACT_WITNESS_BINDING_REQUIRED",
    ),
    "S11": (
        "VERIFIED_SNAPSHOT", "REVISION_BUMP_MARK_COMPACTED",
        "INDEPENDENT_WITNESS_EXACT_CAS", "NEW_CLUSTER_AND_INCARNATION",
        "WATCH_INVALIDATED", "FULL_LINEARIZABLE_REBUILD",
    ),
    "S12:success": (
        "TARGET_AND_EXECUTING_NODE_SEPARATE", "SUCCESS_BRANCH_EXPLICIT_VERSION",
        "SUCCESS_BRANCH_EXACT_MESSAGE_AND_PIN", "SUCCESS_BRANCH_OFFLINE_VERIFY",
        "SUCCESS_BRANCH_DURABLE_RECEIPT", "NO_SERVICE_WIDE_FAILURE_INFERENCE",
    ),
    "S12:fail": (
        "TARGET_AND_EXECUTING_NODE_SEPARATE", "FAIL_BRANCH_ZERO_ACCEPTED_RECEIPT",
        "FAIL_BRANCH_ZERO_OUTPUT", "NO_SERVICE_WIDE_FAILURE_INFERENCE",
    ),
    "S13": (
        "DURABLE_PREPARED_MARKER", "LOST_RESPONSE_NOT_NO_SIGN_PROOF",
        "TERMINAL_QUARANTINE", "RESTART_NO_RESIGN",
    ),
    "S14:recovered": (
        "IN_MEMORY_SIGNATURE_NOT_DURABLE", "EXACT_RECEIPT_RECOVERED",
        "RESTART_NO_RESIGN",
    ),
    "S14:quarantined": (
        "IN_MEMORY_SIGNATURE_NOT_DURABLE", "ABSENT_RECEIPT_QUARANTINED",
        "RESTART_NO_RESIGN",
    ),
    "S15:available": (
        "EXPLICIT_FROZEN_VERSION", "LATEST_NOT_SUBSTITUTED",
        "FULL_TRANSIT_VALIDATION",
    ),
    "S15:unavailable": (
        "EXPLICIT_FROZEN_VERSION", "LATEST_NOT_SUBSTITUTED",
        "ZERO_DOUBLE_CALLS",
    ),
    "S16": (
        "ZERO_OR_OMITTED_VERSION_REJECTED", "LATEST_NOT_SELECTED",
        "ZERO_DOUBLE_CALLS",
    ),
    "S17": (
        "SINGLE_NONBATCH_CONTEXT_FREE_REQUEST", "EXACT_VERSION_PREFIX",
        "PINNED_KEY_AND_MESSAGE", "INVALID_BINDING_REJECTED",
    ),
}

GLOBAL_SEMANTIC_TOKEN_DENY = {
    "PROVIDER_PROCESSING_OBSERVED",
    "PROVIDER_EVIDENCE_PRESENT",
    "PRODUCTION_READY",
    "OUTPUT_PERMIT_GRANTED",
    "EXACTLY_ONCE_PROVEN",
    "REAL_PROVIDER_CALL",
}


@dataclass(frozen=True)
class EvidenceExpectation:
    request_sha256: str
    response_sha256: str
    requested_key_version: int
    validated_key_version: int
    requested_isolation: str
    effective_isolation: str
    message_sha256: str
    message_bytes: int
    public_key_sha256: str
    test_signature_sha256: str
    semantic_tokens: tuple[str, ...]


def _independent_kms_request() -> dict[str, Any]:
    message = bytes.fromhex(MESSAGE_HEX)
    return {
        "name": MANAGED_EXACT_KEY_VERSION_RESOURCE,
        "data": base64.b64encode(message).decode("ascii"),
        "data_crc32c": crc32c_reference(message),
    }


def _independent_kms_response(request: dict[str, Any]) -> dict[str, Any]:
    signature = bytes.fromhex(SIGNATURE_HEX)
    return {
        "name": request["name"],
        "signature": base64.b64encode(signature).decode("ascii"),
        "signature_crc32c": crc32c_reference(signature),
        "verified_data_crc32c": True,
        "protection_level": MANAGED_PROTECTION_LEVEL,
    }


def _independent_transit_request() -> dict[str, Any]:
    return {
        "input": base64.b64encode(bytes.fromhex(MESSAGE_HEX)).decode("ascii"),
        "key_version": SELF_HOSTED_KEY_VERSION,
        "prehashed": False,
    }


def _independent_transit_response() -> dict[str, Any]:
    signature = base64.b64encode(bytes.fromhex(SIGNATURE_HEX)).decode("ascii")
    return {"signature": f"vault:v{SELF_HOSTED_KEY_VERSION}:{signature}"}


def _semantic_token_key(
    case_id: str,
    repetition: int,
    variant: str,
    classification: str,
) -> str:
    if case_id in {"M04", "S04"}:
        return f"{case_id}:{'odd' if repetition % 2 else 'even'}"
    if case_id == "M07":
        return (
            "M07:bad_crc"
            if variant == "COMPUTE_DATA_CRC32C_OVER_BASE64_TEXT"
            else "M07:false_flag"
        )
    if case_id == "M08":
        return (
            "M08:response_name"
            if variant == "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME"
            else "M08:precall"
        )
    if case_id in {"M13", "S14"}:
        suffix = "recovered" if classification == "RECOVERED_BY_STRONG_LOOKUP" else "quarantined"
        return f"{case_id}:{suffix}"
    if case_id == "S01":
        suffix = "success" if classification == "CONFORMING_OBSERVED" else "fail"
        return f"S01:{suffix}"
    if case_id == "S12":
        suffix = "success" if classification == "CONFORMING_OBSERVED" else "fail"
        return f"S12:{suffix}"
    if case_id == "S15":
        suffix = "available" if classification == "CONFORMING_OBSERVED" else "unavailable"
        return f"S15:{suffix}"
    return case_id


def compile_evidence_expectation(
    case_id: str,
    repetition: int,
    variant: str,
    classification: str,
) -> EvidenceExpectation:
    request_sha = ZERO_SHA256
    response_sha = ZERO_SHA256
    requested_key_version = 0
    validated_key_version = 0
    requested_isolation = NOT_APPLICABLE
    effective_isolation = NOT_APPLICABLE
    message = bytes.fromhex(MESSAGE_HEX)
    public_key = bytes.fromhex(PUBLIC_KEY_HEX)
    signature = bytes.fromhex(SIGNATURE_HEX)

    if case_id.startswith("M"):
        requested_isolation = MANAGED_ISOLATION
        effective_isolation = MANAGED_ISOLATION
        request = _independent_kms_request()
        response = _independent_kms_response(request)
        if case_id in {"M00", "M01", "M14", "M15"}:
            request_sha = sha256_value(request)
            response_sha = sha256_value(response)
            requested_key_version = validated_key_version = MANAGED_KEY_VERSION
        elif case_id in {"M02", "M04"}:
            pass
        elif case_id == "M03":
            requested_isolation = "REPEATABLE_READ"
            effective_isolation = "NOT_STARTED"
        elif case_id == "M05":
            requested_key_version = MANAGED_KEY_VERSION
            request = {
                "name": request["name"],
                "digest": {
                    "sha256": base64.b64encode(
                        bytes.fromhex(MESSAGE_SHA256)
                    ).decode("ascii")
                },
            }
            request_sha = sha256_value(request)
        elif case_id == "M06":
            requested_key_version = MANAGED_KEY_VERSION
            mutated_message = message[:-1] + bytes([message[-1] ^ 1])
            request = {
                "name": request["name"],
                "data": base64.b64encode(mutated_message).decode("ascii"),
                "data_crc32c": crc32c_reference(mutated_message),
            }
            request_sha = sha256_value(request)
        elif case_id == "M07":
            requested_key_version = MANAGED_KEY_VERSION
            if variant == "COMPUTE_DATA_CRC32C_OVER_BASE64_TEXT":
                request["data_crc32c"] = crc32c_reference(request["data"].encode("ascii"))
                response = {"provider_error": "CRC32C_MISMATCH"}
            elif variant == "RETURN_VERIFIED_DATA_CRC32C_FALSE":
                response["verified_data_crc32c"] = False
            else:
                fail("E_EVIDENCE_BRANCH", f"unsupported M07 variant {variant}")
            request_sha = sha256_value(request)
            response_sha = sha256_value(response)
        elif case_id == "M08":
            requested_key_version = MANAGED_KEY_VERSION
            if variant == "OMIT_CRYPTOKEYVERSION_SEGMENT":
                request["name"] = request["name"].replace(
                    "/cryptoKeyVersions/", "/", 1
                )
                requested_key_version = 0
                request_sha = sha256_value(request)
            elif variant == "SET_CRYPTOKEYVERSION_SEGMENT_TO_ZERO":
                request["name"] = request["name"].rsplit("/", 1)[0] + "/0"
                requested_key_version = 0
                request_sha = sha256_value(request)
            elif variant == "USE_PARENT_CRYPTOKEY_RESOURCE":
                request["name"] = request["name"].split("/cryptoKeyVersions/", 1)[0]
                requested_key_version = 0
                request_sha = sha256_value(request)
            elif variant == "USE_NONCANONICAL_LEADING_ZERO_VERSION":
                request["name"] = request["name"].rsplit("/", 1)[0] + f"/0{MANAGED_KEY_VERSION}"
                request_sha = sha256_value(request)
            elif variant == "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME":
                response["name"] = response["name"].rsplit("/", 1)[0] + f"/{MANAGED_KEY_VERSION + 1}"
                request_sha = sha256_value(request)
                response_sha = sha256_value(response)
            else:
                fail("E_EVIDENCE_BRANCH", f"unsupported M08 variant {variant}")
        elif case_id in {"M09", "M10", "M11"}:
            requested_key_version = MANAGED_KEY_VERSION
            if case_id == "M09":
                response["signature_crc32c"] ^= 1
            elif case_id == "M10":
                response["protection_level"] = "HSM_SINGLE_TENANT"
            else:
                corrupted = bytearray(base64.b64decode(response["signature"]))
                corrupted[0] ^= 1
                response["signature"] = base64.b64encode(corrupted).decode("ascii")
                response["signature_crc32c"] = crc32c_reference(bytes(corrupted))
            request_sha = sha256_value(request)
            response_sha = sha256_value(response)
        elif case_id == "M12":
            request_sha = sha256_value(request)
            requested_key_version = MANAGED_KEY_VERSION
        elif case_id == "M13":
            request_sha = sha256_value(request)
            response_sha = sha256_value(response)
            requested_key_version = MANAGED_KEY_VERSION
            validated_key_version = MANAGED_KEY_VERSION
        else:
            fail("E_EVIDENCE_CASE", f"unsupported managed case {case_id}")
    elif case_id.startswith("S"):
        request = _independent_transit_request()
        response = _independent_transit_response()
        if case_id == "S00":
            request_sha = sha256_value(request)
            response_sha = sha256_value(response)
            requested_key_version = validated_key_version = SELF_HOSTED_KEY_VERSION
        elif case_id in {
            "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08",
            "S09", "S10", "S11",
        }:
            pass
        elif case_id == "S12":
            if classification == "CONFORMING_OBSERVED":
                request_sha = sha256_value(request)
                response_sha = sha256_value(response)
                requested_key_version = validated_key_version = SELF_HOSTED_KEY_VERSION
        elif case_id == "S13":
            request_sha = sha256_value(request)
            requested_key_version = SELF_HOSTED_KEY_VERSION
        elif case_id == "S14":
            request_sha = sha256_value(request)
            response_sha = sha256_value(response)
            requested_key_version = SELF_HOSTED_KEY_VERSION
            validated_key_version = SELF_HOSTED_KEY_VERSION
        elif case_id == "S15":
            request_sha = sha256_value(request)
            requested_key_version = SELF_HOSTED_KEY_VERSION
            if classification == "CONFORMING_OBSERVED":
                response_sha = sha256_value(response)
                validated_key_version = SELF_HOSTED_KEY_VERSION
        elif case_id == "S16":
            request["key_version"] = 0
            request_sha = sha256_value(request)
        elif case_id == "S17":
            requested_key_version = SELF_HOSTED_KEY_VERSION
            if variant == "MUTATE_SIGNATURE_VERSION_PREFIX":
                response["signature"] = response["signature"].replace(
                    f"vault:v{SELF_HOSTED_KEY_VERSION}:",
                    f"vault:v{SELF_HOSTED_KEY_VERSION + 1}:",
                    1,
                )
            elif variant == "MUTATE_PUBLIC_KEY_PIN":
                mutated_public_key = bytearray(public_key)
                mutated_public_key[-1] ^= 1
                public_key = bytes(mutated_public_key)
            elif variant == "MUTATE_MESSAGE":
                mutated_message = message[:-1] + bytes([message[-1] ^ 1])
                request["input"] = base64.b64encode(mutated_message).decode("ascii")
            else:
                fail("E_EVIDENCE_BRANCH", f"unsupported S17 variant {variant}")
            request_sha = sha256_value(request)
            response_sha = sha256_value(response)
        else:
            fail("E_EVIDENCE_CASE", f"unsupported self-hosted case {case_id}")
    else:
        fail("E_EVIDENCE_CASE", f"unsupported case {case_id}")

    token_key = _semantic_token_key(case_id, repetition, variant, classification)
    require(
        token_key in SEMANTIC_TOKEN_VECTORS,
        "E_EVIDENCE_BRANCH",
        f"missing semantic-token vector {token_key}",
    )
    return EvidenceExpectation(
        request_sha256=request_sha,
        response_sha256=response_sha,
        requested_key_version=requested_key_version,
        validated_key_version=validated_key_version,
        requested_isolation=requested_isolation,
        effective_isolation=effective_isolation,
        message_sha256=MESSAGE_SHA256,
        message_bytes=len(message),
        public_key_sha256=sha256_bytes(public_key),
        test_signature_sha256=sha256_bytes(signature),
        semantic_tokens=SEMANTIC_TOKEN_VECTORS[token_key],
    )


def validate_evidence_expectation(
    row: dict[str, Any],
    case: dict[str, Any],
    expectation: EvidenceExpectation,
) -> None:
    evidence = row["evidence"]
    for field_name in (
        "request_sha256", "response_sha256", "requested_key_version",
        "validated_key_version", "requested_isolation", "effective_isolation",
        "message_sha256", "message_bytes", "public_key_sha256",
        "test_signature_sha256",
    ):
        require(
            evidence[field_name] == getattr(expectation, field_name),
            f"E_EVIDENCE_{field_name.upper()}",
            f"{case['case_id']} {field_name} drift",
        )
    actual_tokens = evidence["semantic_tokens"]
    require(type(actual_tokens) is list, "E_SEMANTIC_TOKEN_SHAPE", "semantic tokens must be a list")
    require(
        all(
            type(token) is str
            and re.fullmatch(r"[A-Z0-9]+(?:_[A-Z0-9]+)*", token) is not None
            for token in actual_tokens
        ),
        "E_SEMANTIC_TOKEN_SHAPE",
        "noncanonical semantic token",
    )
    require(
        len(actual_tokens) == len(set(actual_tokens)),
        "E_SEMANTIC_TOKEN_DUPLICATE",
        "duplicate semantic token",
    )
    forbidden = GLOBAL_SEMANTIC_TOKEN_DENY | set(case["forbidden_claims"])
    overlap = set(actual_tokens) & forbidden
    require(
        not overlap,
        "E_SEMANTIC_TOKEN_FORBIDDEN",
        f"forbidden semantic claims: {sorted(overlap)}",
    )
    require(
        actual_tokens == list(expectation.semantic_tokens),
        "E_SEMANTIC_TOKEN_VECTOR",
        f"{case['case_id']} semantic-token vector drift",
    )


def expected_variant(case: dict[str, Any], repetition: int) -> str:
    values = VARIANTS.get(case["case_id"])
    return values[(repetition - 1) % len(values)] if values else case["injection_cut"]


def expected_classification(case_id: str, repetition: int) -> str:
    if case_id == "M13" or case_id == "S14":
        return "RECOVERED_BY_STRONG_LOOKUP" if repetition % 2 else "AMBIGUOUS_QUARANTINED"
    if case_id in {"S01", "S12", "S15"}:
        return "CONFORMING_OBSERVED" if repetition % 2 else "FAIL_CLOSED_REJECTED"
    require(case_id in STATIC_CLASSIFICATIONS, "E_ORACLE_CASE", f"no independent classification for {case_id}")
    return STATIC_CLASSIFICATIONS[case_id]


def expected_simulated_calls(case_id: str, repetition: int, variant: str) -> int:
    always_one = {
        "M00", "M01", "M07", "M09", "M10", "M11", "M12", "M13", "M14", "M15",
        "S00", "S13", "S14", "S17",
    }
    if case_id in always_one:
        return 1
    if case_id == "M08":
        return int(variant == "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME")
    if case_id in {"S12", "S15"}:
        return int(repetition % 2 == 1)
    return 0


def _event_names(row: dict[str, Any]) -> list[str]:
    return [event["name"] for event in row["event_trace"]]


def expected_core_state(case_id: str, repetition: int) -> dict[str, Any]:
    if case_id.startswith("M"):
        if case_id in {"M02", "M03"}:
            return {
                "authority": "REJECTED_FAIL_CLOSED", "outbox": "NONE",
                "challenge_consumptions": 0, "logical_sink_reservations": 0,
                "database_attempts": 0,
            }
        if case_id == "M04" and repetition % 2 == 0:
            return {
                "authority": "FENCED_ABSENT", "outbox": "NONE",
                "challenge_consumptions": 0, "logical_sink_reservations": 0,
                "database_attempts": 1,
            }
        return {
            "authority": "AUTHORIZED_COMMITTED", "outbox": "SIGN_PENDING",
            "challenge_consumptions": 1, "logical_sink_reservations": 1,
            "database_attempts": 2 if case_id == "M01" else 1,
        }
    if case_id == "S01":
        return {
            "authority": "QUORUM_READ_OBSERVED" if repetition % 2 else "REJECTED_FAIL_CLOSED",
            "outbox": "NONE", "challenge_consumptions": 0,
            "logical_sink_reservations": 0, "database_attempts": 0,
        }
    if case_id in {"S02", "S03", "S07", "S08"}:
        return {
            "authority": "REJECTED_FAIL_CLOSED", "outbox": "NONE",
            "challenge_consumptions": 0, "logical_sink_reservations": 0,
            "database_attempts": 0,
        }
    if case_id in {"S09", "S10", "S11"}:
        return {
            "authority": "EMPTY", "outbox": "NONE", "challenge_consumptions": 0,
            "logical_sink_reservations": 0, "database_attempts": 0,
        }
    if case_id == "S04" and repetition % 2 == 0:
        return {
            "authority": "FENCED_ABSENT", "outbox": "NONE",
            "challenge_consumptions": 0, "logical_sink_reservations": 0,
            "database_attempts": 1,
        }
    if case_id == "S12" and repetition % 2 == 0:
        return {
            "authority": "REJECTED_FAIL_CLOSED", "outbox": "NONE",
            "challenge_consumptions": 0, "logical_sink_reservations": 0,
            "database_attempts": 0,
        }
    return {
        "authority": "AUTHORIZED_COMMITTED", "outbox": "SIGN_PENDING",
        "challenge_consumptions": 1, "logical_sink_reservations": 1,
        "database_attempts": 1,
    }


def _one_event(row: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [event for event in row["event_trace"] if event["name"] == name]
    require(len(matches) == 1, "E_EVENT_CARDINALITY", f"{name} cardinality drift")
    return matches[0]


def _validate_event_closure(row: dict[str, Any]) -> None:
    trace = row["event_trace"]
    require(
        [event.get("sequence") for event in trace] == list(range(1, len(trace) + 1)),
        "E_EVENT_SEQUENCE",
        "event sequence drift",
    )
    forbidden = (
        "PROVIDER_PROCESSING_OBSERVED", "PROVIDER_EVIDENCE_PRESENT", "PRODUCTION_READY",
        "OUTPUT_PERMIT_GRANTED", "EXACTLY_ONCE_PROVEN", "REAL_PROVIDER_CALL",
    )
    for event in trace:
        require(set(event) == {"sequence", "name", "details"}, "E_EVENT_FIELDS", "event fields are open")
        name = event["name"]
        require(name in EVENT_DETAIL_KEYS, "E_EVENT_NAME", f"unrecognized event {name}")
        require(set(event["details"]) == EVENT_DETAIL_KEYS[name], "E_EVENT_DETAILS", f"{name} detail fields drift")
        rendered = json.dumps(event["details"], sort_keys=True).upper()
        require(not any(token in rendered for token in forbidden), "E_EVENT_PROVENANCE", f"{name} contains a forbidden claim")
    spanner_attempts = [
        event for event in trace
        if event["name"] == "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT"
    ]
    require(
        [event["details"]["attempt"] for event in spanner_attempts]
        == list(range(1, len(spanner_attempts) + 1))
        and all(event["details"]["closure_scope"] == "DATABASE_ONLY" for event in spanner_attempts),
        "E_EVENT_VALUE",
        "Spanner transaction-attempt evidence drift",
    )
    for event in [event for event in trace if event["name"] == "SPANNER_OUTBOX_COMMITTED"]:
        require(event["details"]["outbox"] == "SIGN_PENDING", "E_EVENT_VALUE", "Spanner outbox event drift")
    for event in [event for event in trace if event["name"] == "ETCD_TOP_LEVEL_CAS"]:
        require(
            all(
                event["details"][field] == expected
                for field, expected in {
                    "serializable": False, "nested": False, "leased": False,
                    "response_revision_source": "TOP_LEVEL_HEADER",
                }.items()
            ),
            "E_EVENT_VALUE",
            "etcd top-level CAS event drift",
        )
    for event in [event for event in trace if event["name"] == "ETCD_OUTBOX_COMMITTED"]:
        require(event["details"] == {"outbox": "SIGN_PENDING"}, "E_EVENT_VALUE", "etcd outbox event drift")


def _assert_cut_adjacency(
    row: dict[str, Any], trigger: dict[str, Any], before: str, after: str
) -> None:
    earlier = _one_event(row, before)
    later = _one_event(row, after)
    require(
        earlier["sequence"] + 1 == trigger["sequence"]
        and trigger["sequence"] + 1 == later["sequence"],
        "E_FAULT_CUT",
        f"fault trigger is not between {before} and {after}",
    )


def _expected_signing_call_binding(
    run_id: str, request_sha256: str, key_version: int
) -> str:
    prepared_record = {
        "operation_id": run_id,
        "canonical_request_sha256": request_sha256,
        "exact_key_version": key_version,
        "public_key_pin_sha256": sha256_bytes(bytes.fromhex(PUBLIC_KEY_HEX)),
        "message_sha256": MESSAGE_SHA256,
        "attempt_sequence": 1,
    }
    return _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/double-call",
        sha256_value(prepared_record),
        request_sha256,
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
    )


def _expected_response_validation_binding(
    run_id: str,
    request_sha256: str,
    response_sha256: str,
    key_version: int,
) -> str:
    call_binding = _expected_signing_call_binding(
        run_id, request_sha256, key_version
    )
    return _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/response-validation",
        call_binding,
        response_sha256,
        request_sha256,
        str(key_version),
        sha256_bytes(bytes.fromhex(PUBLIC_KEY_HEX)),
        MESSAGE_SHA256,
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
    )


def _expected_fault_causal_binding(
    row: dict[str, Any], trigger: dict[str, Any]
) -> str:
    """Compile the one-shot cut witness from independent frozen inputs."""

    case_id = row["schedule"]["case_id"]
    repetition = row["schedule"]["repetition_index"]
    variant = row["case"]["injection_variant"]
    run_id = row["schedule"]["simulation_run_id"]
    labelled_cuts = {
        "M01": "SPANNER_ATTEMPT_1_BEFORE_ABORT",
        "M02": "RETRYABLE_CLOSURE_SIDE_EFFECT_SENTINEL",
        "M03": "REQUESTED_ISOLATION_PROFILE",
        "M15": "OUTBOX_READY_BEFORE_ATTEMPT_CAS",
        "S01": "FOLLOWER_PARTITION_BOUNDARY",
        "S02": "SERIALIZABLE_READ_PROFILE",
        "S03": "DECODED_NESTED_TXN",
        "S07": "ETCD_QUORUM_PARTITION",
        "S08": "WATCH_DELIVERY_DELAY",
        "S12": "ACTIVE_NODE_BEFORE_SEAL",
    }
    if case_id in labelled_cuts:
        expected_sequence = {
            "M01": 5,
            "M02": 4,
            "M03": 4,
            "M15": 6,
            "S01": 4,
            "S02": 4,
            "S03": 4,
            "S07": 4,
            "S08": 4,
            "S12": 4,
        }[case_id]
        require(
            trigger["sequence"] == expected_sequence,
            "E_TRIGGER_CAUSAL_BINDING",
            f"{case_id} trigger sequence drift",
        )
        return _framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/causal-cut",
            run_id,
            labelled_cuts[case_id],
            str(expected_sequence),
        )
    if case_id in {"M04", "S04", "S05", "S06"}:
        key_version = (
            MANAGED_KEY_VERSION if case_id.startswith("M")
            else SELF_HOSTED_KEY_VERSION
        )
        return sha256_value(_operation_record(run_id, key_version))
    if case_id in {"M05", "M06"}:
        classification = (
            row["case_classification"] or row["simulated_classification"]
        )
        return compile_evidence_expectation(
            case_id, repetition, variant, classification
        ).request_sha256
    if case_id in {"M07", "M08"}:
        if (
            case_id == "M07"
            and variant == "RETURN_VERIFIED_DATA_CRC32C_FALSE"
        ) or (
            case_id == "M08"
            and variant == "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME"
        ):
            return sha256_value(
                _independent_kms_response(_independent_kms_request())
            )
        return sha256_value(_independent_kms_request())
    if case_id in {"M09", "M10", "M11"}:
        return sha256_value(
            _independent_kms_response(_independent_kms_request())
        )
    if case_id in {"M12", "S13"}:
        if case_id == "M12":
            request_sha256 = sha256_value(_independent_kms_request())
            key_version = MANAGED_KEY_VERSION
        else:
            request_sha256 = sha256_value(_independent_transit_request())
            key_version = SELF_HOSTED_KEY_VERSION
        return _expected_signing_call_binding(
            run_id, request_sha256, key_version
        )
    if case_id in {"M13", "S14"}:
        if case_id == "M13":
            request_sha256 = sha256_value(_independent_kms_request())
            response_sha256 = sha256_value(
                _independent_kms_response(_independent_kms_request())
            )
            key_version = MANAGED_KEY_VERSION
        else:
            request_sha256 = sha256_value(_independent_transit_request())
            response_sha256 = sha256_value(_independent_transit_response())
            key_version = SELF_HOSTED_KEY_VERSION
        return _expected_response_validation_binding(
            run_id, request_sha256, response_sha256, key_version
        )
    if case_id == "M14":
        return run_id
    if case_id == "S09":
        expected = _expected_witness_record(run_id, 0, None)
        if variant == "RESTORE_OLDER_SNAPSHOT_WITHOUT_BUMP":
            expected.update(
                bump_revision=0,
                new_revision_floor=expected["snapshot_revision"],
                mark_compacted=False,
            )
        elif variant == "RETURN_STALE_REPLAYED_OR_FORKED_WITNESS_RECORD":
            prior = expected
            expected = _expected_witness_record(run_id, 1, prior)
            expected.update(
                previous_record_sha256=ZERO_SHA256,
                generation=1,
            )
        return sha256_value(expected)
    if case_id in {"S10", "S11"}:
        return _framed_hash(WITNESS_DOMAIN, run_id, "snapshot", "0")
    if case_id in {"S15", "S16"}:
        return sha256_value(_independent_transit_request())
    if case_id == "S17":
        if variant == "MUTATE_MESSAGE":
            return sha256_value(_independent_transit_request())
        return sha256_value(_independent_transit_response())
    fail(
        "E_TRIGGER_CAUSAL_BINDING",
        f"missing causal-binding oracle for {case_id}",
    )


def _validate_fault_cut(
    row: dict[str, Any], case: dict[str, Any], variant: str
) -> None:
    case_id = case["case_id"]
    trace = row["event_trace"]
    assignment = _one_event(row, "ASSIGNMENT_HASH_SEALED")
    arm = _one_event(row, "ONE_SHOT_FAULT_CONTROLLER_ARMED")
    start = _one_event(row, "CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM")
    require(
        assignment["sequence"] == 1 and arm["sequence"] == 2 and start["sequence"] == 3,
        "E_EVENT_PREFIX",
        f"{case_id} assignment/arm/start order drift",
    )
    require(
        assignment["details"] == {
            "assignment_sha256": row["schedule"]["assignment_sha256"],
            "simulation_run_id": row["schedule"]["simulation_run_id"],
        },
        "E_ASSIGNMENT_BINDING",
        f"{case_id} assignment binding drift",
    )
    require(
        arm["details"] == {
            "assignment_sha256": row["schedule"]["assignment_sha256"],
            "case_id": case_id,
            "injection_cut": case["injection_cut"],
            "injection_variant": variant,
            "trigger_limit": 0 if case["injection_cut"] == "NONE" else 1,
        },
        "E_ARM_BINDING",
        f"{case_id} fault arm drift",
    )
    triggers = [event for event in trace if event["name"] == "ONE_SHOT_FAULT_TRIGGERED"]
    if case["injection_cut"] == "NONE":
        require(not triggers, "E_FAULT_CARDINALITY", f"{case_id} control triggered")
        require(
            _one_event(row, "CONTROL_NO_FAULT_TRIGGERED")["details"]
            == {"case_id": case_id, "trigger_count": 0},
            "E_FAULT_CARDINALITY",
            f"{case_id} control record drift",
        )
        return
    require(len(triggers) == 1, "E_FAULT_CARDINALITY", f"{case_id} fault cardinality drift")
    trigger = triggers[0]
    require(
        trigger["details"]["case_id"] == case_id
        and trigger["details"]["injection_cut"] == case["injection_cut"]
        and trigger["details"]["injection_variant"] == variant
        and trigger["details"]["trigger_count"] == 1,
        "E_TRIGGER_BINDING",
        f"{case_id} trigger binding drift",
    )
    require(
        trigger["details"]["causal_binding_sha256"]
        == _expected_fault_causal_binding(row, trigger),
        "E_TRIGGER_CAUSAL_BINDING",
        f"{case_id} causal cut binding drift",
    )
    if case_id == "M01":
        before = [event for event in trace if event["name"] == "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT" and event["details"]["attempt"] == 1]
        after = [event for event in trace if event["name"] == "SPANNER_DEFINITE_ABORT" and event["details"]["attempt"] == 1]
        require(
            len(before) == len(after) == 1
            and before[0]["sequence"] + 1 == trigger["sequence"]
            and trigger["sequence"] + 1 == after[0]["sequence"],
            "E_FAULT_CUT",
            "M01 abort trigger cut drift",
        )
        return
    bounds = {
        "M02": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "SPANNER_CLOSURE_SIDE_EFFECT_SENTINEL_REJECTED"),
        "M03": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "SPANNER_ISOLATION_PROFILE_REJECTED"),
        "M05": ("SPANNER_OUTBOX_COMMITTED", "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT"),
        "M06": ("SPANNER_OUTBOX_COMMITTED", "KMS_REQUEST_REJECTED_BEFORE_ATTEMPT"),
        "M12": ("KMS_DOUBLE_PROCESSING_COMPLETED", "KMS_DOUBLE_RESPONSE_DROPPED"),
        "M13": ("KMS_RESPONSE_FULLY_VALIDATED", "SPANNER_RECEIPT_PERSIST_OUTCOME_UNKNOWN"),
        "M14": ("SPANNER_OUTBOX_COMMITTED", "TWO_WORKERS_RELEASED"),
        "M15": ("SPANNER_OUTBOX_COMMITTED", "WORKER_CRASHED_BEFORE_ATTEMPT_CAS"),
        "S01": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_FOLLOWER_ISOLATED"),
        "S02": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_SERIALIZABLE_READ_MODE_REJECTED"),
        "S03": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_NESTED_TRANSACTION_REJECTED"),
        "S04": ("ETCD_REQUEST_ADMITTED_WITH_PENDING_COMMIT", "ETCD_LEADER_REMOVED_AFTER_REQUEST_ADMISSION"),
        "S05": ("ETCD_OUTBOX_COMMITTED", "ETCD_LEADER_LOST_POSTCOMMIT"),
        "S06": ("ETCD_OUTBOX_COMMITTED", "ETCD_TRANSACTION_ACK_DROPPED"),
        "S07": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_QUORUM_LOST"),
        "S08": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "ETCD_WATCH_DELAYED"),
        "S09": ("RESTORE_WITNESS_CANDIDATE_STAGED", "EXTERNAL_WITNESS_VALIDATION_FAILED"),
        "S10": ("SNAPSHOT_HASH_VERIFIED", "RESTORE_IDENTITY_OR_WITNESS_BINDING_REJECTED"),
        "S11": ("SNAPSHOT_HASH_VERIFIED", "RESTORE_REVISION_BUMPED_AND_MARKED_COMPACTED"),
        "S12": ("CANDIDATE_STARTED_AFTER_ASSIGNMENT_AND_ARM", "OPENBAO_DIRECT_TARGET_SEAL_STATUS"),
        "S13": ("TRANSIT_DOUBLE_PROCESSING_COMPLETED", "TRANSIT_DOUBLE_RESPONSE_DROPPED"),
        "S14": ("TRANSIT_RESPONSE_FULLY_VALIDATED", "ETCD_RECEIPT_PERSIST_OUTCOME_UNKNOWN"),
        "S15": ("ETCD_OUTBOX_COMMITTED", "OPENBAO_KEY_ROTATED"),
        "S16": ("ETCD_OUTBOX_COMMITTED", "TRANSIT_ZERO_VERSION_REJECTED_BEFORE_ATTEMPT"),
    }
    if case_id in bounds:
        _assert_cut_adjacency(row, trigger, *bounds[case_id])
    elif case_id == "M04":
        _assert_cut_adjacency(
            row,
            trigger,
            "SPANNER_SERVER_COMMIT_APPLIED" if variant == "DROP_COMMIT_RESPONSE_AFTER_SERVER_COMMIT" else "SPANNER_COMMIT_ADMITTED_OUTCOME_UNRESOLVED",
            "SPANNER_COMMIT_RESPONSE_LOST",
        )
    elif case_id in {"M07", "M08", "M09", "M10", "M11"}:
        precall = (case_id == "M07" and variant == "COMPUTE_DATA_CRC32C_OVER_BASE64_TEXT") or (case_id == "M08" and variant != "RETURN_DIFFERENT_CRYPTOKEYVERSION_NAME")
        if precall:
            _assert_cut_adjacency(
                row,
                trigger,
                "SPANNER_OUTBOX_COMMITTED",
                "KMS_SIGN_ATTEMPT_PREPARED"
                if case_id == "M07"
                else "KMS_RESOURCE_REJECTED_BEFORE_ATTEMPT",
            )
        else:
            prepared = _one_event(row, "KMS_SIGN_ATTEMPT_PREPARED")
            consumed = _one_event(row, "KMS_SIGN_ATTEMPT_CALL_CONSUMED")
            call = _one_event(row, "KMS_DOUBLE_CALL")
            require(
                prepared["sequence"] + 1 == trigger["sequence"]
                and trigger["sequence"] + 1 == consumed["sequence"]
                and consumed["sequence"] + 1 == call["sequence"],
                "E_FAULT_CUT",
                "managed response-mutation cut drift",
            )
    elif case_id == "S17":
        if variant == "MUTATE_MESSAGE":
            _assert_cut_adjacency(
                row, trigger, "ETCD_OUTBOX_COMMITTED", "TRANSIT_SIGN_ATTEMPT_PREPARED"
            )
        else:
            prepared = _one_event(row, "TRANSIT_SIGN_ATTEMPT_PREPARED")
            consumed = _one_event(row, "TRANSIT_SIGN_ATTEMPT_CALL_CONSUMED")
            call = _one_event(row, "TRANSIT_DOUBLE_CALL")
            require(
                prepared["sequence"] + 1 == trigger["sequence"]
                and trigger["sequence"] + 1 == consumed["sequence"]
                and consumed["sequence"] + 1 == call["sequence"],
                "E_FAULT_CUT",
                "self-hosted response-mutation cut drift",
            )
    else:
        fail("E_FAULT_CUT", f"missing fault cut oracle for {case_id}")


def _expected_operation_record(
    run_id: str,
    key_version: int,
    *,
    authority: str,
    outbox: str,
    attempt: str = "NONE",
    attempt_consumed: bool = False,
    receipt: str = "NONE",
    challenge_consumptions: int,
    logical_sink_reservations: int,
    prepared_record_sha256: str = ZERO_SHA256,
    call_binding_sha256: str = ZERO_SHA256,
    processed_response_sha256: str = ZERO_SHA256,
    validated_response_sha256: str = ZERO_SHA256,
    validation_binding_sha256: str = ZERO_SHA256,
    receipt_binding_sha256: str = ZERO_SHA256,
    terminal: bool = False,
    record_kind: str = "EXACT_OPERATION_RECORD",
) -> dict[str, Any]:
    """Independent canonical durable operation record constructor."""

    return {
        "record_kind": record_kind,
        "operation_id": run_id,
        "authority": authority,
        "outbox": outbox,
        "attempt": attempt,
        "attempt_consumed": attempt_consumed,
        "receipt": receipt,
        "challenge_consumptions": challenge_consumptions,
        "logical_sink_reservations": logical_sink_reservations,
        "message_sha256": MESSAGE_SHA256,
        "exact_key_version": key_version,
        "public_key_pin_sha256": sha256_bytes(bytes.fromhex(PUBLIC_KEY_HEX)),
        "prepared_record_sha256": prepared_record_sha256,
        "call_binding_sha256": call_binding_sha256,
        "processed_response_sha256": processed_response_sha256,
        "validated_response_sha256": validated_response_sha256,
        "validation_binding_sha256": validation_binding_sha256,
        "receipt_binding_sha256": receipt_binding_sha256,
        "terminal": terminal,
    }


def _validate_durable_transition_replay(row: dict[str, Any]) -> None:
    trace = row["event_trace"]
    state = row["state"]
    schedule = row["schedule"]
    run_id = schedule["simulation_run_id"]
    operation_key = _framed_hash(EXACT_KEY_DOMAIN, run_id)
    transitions = [
        event for event in trace if "transition_record" in event["details"]
    ]
    rejected = [
        event for event in trace
        if "transition_envelope" in event["details"]
        and "transition_record" not in event["details"]
    ]

    if rejected:
        require(
            schedule["case_id"] == "S03"
            and len(rejected) == 1
            and not transitions,
            "E_S03_TRANSITION",
            "preexecution rejection envelope escaped S03",
        )
        event = rejected[0]
        envelope = event["details"]["transition_envelope"]
        require(
            event["name"] == "ETCD_NESTED_TRANSACTION_REJECTED"
            and set(envelope) == TRANSITION_ENVELOPE_FIELDS,
            "E_S03_TRANSITION",
            "S03 rejection envelope shape drift",
        )
        require(
            envelope
            == {
                "phase": "NESTED_TRANSACTION_REJECTED_PREEXECUTION",
                "store_kind": "ETCD_LINEARIZABLE_TOP_LEVEL_EXACT_KEY_CAS",
                "operation_id": run_id,
                "operation_key": operation_key,
                "consistency": "LINEARIZABLE",
                "nested": True,
                "leased": False,
                "compare_record_sha256": ZERO_SHA256,
                "observed_record_sha256": ZERO_SHA256,
                "expected_mod_revision": 0,
                "committed_record_sha256": ZERO_SHA256,
                "committed_revision": 0,
                "top_level_revision": 0,
                "mutation_count": 0,
                "cas_result": "REJECTED_PREEXECUTION",
                "response_revision_source": "NONE_PREEXECUTION_REJECTED",
            },
            "E_S03_TRANSITION",
            "S03 nested request did not fail before mutation",
        )
        require(
            state["durable_operation_record_sha256"] == ZERO_SHA256
            and state["durable_operation_revision"] == 0,
            "E_S03_TRANSITION",
            "S03 rejection mutated durable operation state",
        )

    if not transitions:
        require(
            state["durable_operation_record_sha256"] == ZERO_SHA256
            and state["durable_operation_revision"] == 0,
            "E_TRANSITION_STATE",
            "row without applied transition retained a durable tip",
        )
        return

    require(not rejected, "E_TRANSITION_PHASE", "applied/rejected transitions mixed")
    if schedule["case_id"] in {"M04", "S04"}:
        expected_exact_phase = (
            "AUTHORITY_OUTBOX_COMMITTED"
            if schedule["repetition_index"] % 2
            else "TERMINAL_FENCE_COMMITTED"
        )
        require(
            len(transitions) == 1
            and transitions[0]["details"]["transition_envelope"]["phase"]
            == expected_exact_phase,
            "E_TRANSITION_PHASE",
            "unknown-outcome exact commit phase/parity drift",
        )
    managed = schedule["track_id"] == MANAGED_TRACK
    allowed = {
        None: {"AUTHORITY_OUTBOX_COMMITTED", "TERMINAL_FENCE_COMMITTED"},
        "AUTHORITY_OUTBOX_COMMITTED": {
            "SIGN_ATTEMPT_PREPARED", "PRE_ATTEMPT_REJECTED_FAIL_CLOSED",
        },
        "SIGN_ATTEMPT_PREPARED": {"SIGN_ATTEMPT_CALL_CONSUMED"},
        "SIGN_ATTEMPT_CALL_CONSUMED": {
            "SIGNATURE_RECEIPT_COMMITTED", "AMBIGUOUS_QUARANTINED",
            "RESPONSE_REJECTED_FAIL_CLOSED",
        },
    }
    previous_phase: str | None = None
    previous_record: dict[str, Any] | None = None
    previous_sha = ZERO_SHA256
    previous_revision = 0

    for event in transitions:
        details = event["details"]
        record = details["transition_record"]
        envelope = details["transition_envelope"]
        record_sha = details["transition_record_sha256"]
        require(
            set(record) == OPERATION_RECORD_FIELDS
            and set(envelope) == TRANSITION_ENVELOPE_FIELDS,
            "E_TRANSITION_FIELDS",
            "durable transition fields drift",
        )
        require(
            sha256_value(record) == record_sha
            and envelope["committed_record_sha256"] == record_sha,
            "E_TRANSITION_HASH",
            "durable transition record hash drift",
        )
        phase = envelope["phase"]
        require(
            phase in allowed.get(previous_phase, set()),
            "E_TRANSITION_PHASE",
            f"illegal transition {previous_phase!r} -> {phase!r}",
        )
        require(
            envelope["operation_id"] == record["operation_id"] == run_id
            and envelope["operation_key"] == operation_key,
            "E_TRANSITION_BINDING",
            "operation id/key binding drift",
        )
        require(
            envelope["compare_record_sha256"] == previous_sha
            and envelope["observed_record_sha256"] == previous_sha,
            "E_TRANSITION_COMPARE",
            "CAS compare/observed hash drift",
        )
        require(
            envelope["expected_mod_revision"] == previous_revision
            and envelope["committed_revision"] == previous_revision + 1
            and envelope["top_level_revision"] == previous_revision + 1,
            "E_TRANSITION_REVISION",
            "CAS revision/top-level revision drift",
        )
        require(
            envelope["mutation_count"] == 1
            and envelope["cas_result"] == "APPLIED"
            and envelope["nested"] is False
            and envelope["leased"] is False,
            "E_TRANSITION_CAS",
            "transition is not one nonnested nonleased mutation",
        )
        expected_store = (
            (
                "SPANNER_SERIALIZABLE_EXACT_KEY_CAS",
                "SERIALIZABLE",
                "SERIALIZABLE_COMMIT_MODEL",
            )
            if managed
            else (
                "ETCD_LINEARIZABLE_TOP_LEVEL_EXACT_KEY_CAS",
                "LINEARIZABLE",
                "TOP_LEVEL_TXN_HEADER",
            )
        )
        require(
            (
                envelope["store_kind"], envelope["consistency"],
                envelope["response_revision_source"],
            )
            == expected_store,
            "E_TRANSITION_STORE",
            "transition backend/consistency/revision-source drift",
        )
        key_version = MANAGED_KEY_VERSION if managed else SELF_HOSTED_KEY_VERSION
        require(
            record["record_kind"]
            in {"EXACT_OPERATION_RECORD", "TERMINAL_FENCE"}
            and record["message_sha256"] == MESSAGE_SHA256
            and record["public_key_pin_sha256"]
            == sha256_bytes(bytes.fromhex(PUBLIC_KEY_HEX))
            and record["exact_key_version"] == key_version,
            "E_TRANSITION_BINDING",
            "frozen message/key binding drift",
        )
        if phase == "TERMINAL_FENCE_COMMITTED":
            require(
                record["record_kind"] == "TERMINAL_FENCE"
                and record["authority"] == "FENCED_ABSENT"
                and record["outbox"] == "NONE"
                and record["challenge_consumptions"] == 0
                and record["logical_sink_reservations"] == 0,
                "E_TRANSITION_ATOMIC",
                "terminal fence atomic binding drift",
            )
        else:
            require(
                record["record_kind"] == "EXACT_OPERATION_RECORD"
                and record["authority"] == "AUTHORIZED_COMMITTED"
                and record["outbox"] == "SIGN_PENDING"
                and record["challenge_consumptions"] == 1
                and record["logical_sink_reservations"] == 1,
                "E_TRANSITION_ATOMIC",
                "authority/challenge/sink/outbox binding drift",
            )
        if previous_record is not None:
            immutable = {
                "operation_id", "authority", "outbox", "challenge_consumptions",
                "logical_sink_reservations", "message_sha256",
                "exact_key_version", "public_key_pin_sha256",
            }
            require(
                all(record[field] == previous_record[field] for field in immutable),
                "E_TRANSITION_IMMUTABLE",
                "immutable transition binding changed",
            )

        if phase == "AUTHORITY_OUTBOX_COMMITTED":
            expected = _expected_operation_record(
                run_id,
                key_version,
                authority="AUTHORIZED_COMMITTED",
                outbox="SIGN_PENDING",
                challenge_consumptions=1,
                logical_sink_reservations=1,
            )
            expected_event_name = (
                "SPANNER_SERVER_COMMIT_APPLIED"
                if schedule["case_id"] == "M04"
                else "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION"
                if schedule["case_id"] == "S04"
                else "SPANNER_OUTBOX_COMMITTED"
                if managed
                else "ETCD_TOP_LEVEL_CAS"
            )
            require(
                record == expected
                and event["name"] == expected_event_name,
                "E_TRANSITION_SHAPE",
                "authority/outbox record drift",
            )
            if event["name"] == "SPANNER_SERVER_COMMIT_APPLIED":
                require(
                    details["operation_key"] == envelope["operation_key"]
                    and details["record_sha256"] == record_sha
                    and details["revision"] == envelope["committed_revision"],
                    "E_TRANSITION_OUTER_BINDING",
                    "managed exact commit outer/transition binding drift",
                )
            elif event["name"] == "ETCD_DELAYED_COMMIT_APPLIED_AFTER_ELECTION":
                require(
                    details["operation_key"] == envelope["operation_key"]
                    and details["record_sha256"] == record_sha
                    and details["cas_result"] == envelope["cas_result"]
                    and details["revision"] == envelope["committed_revision"],
                    "E_TRANSITION_OUTER_BINDING",
                    "self-hosted exact commit outer/transition binding drift",
                )
        elif phase == "TERMINAL_FENCE_COMMITTED":
            expected = _expected_operation_record(
                run_id,
                key_version,
                authority="FENCED_ABSENT",
                outbox="NONE",
                challenge_consumptions=0,
                logical_sink_reservations=0,
                terminal=True,
                record_kind="TERMINAL_FENCE",
            )
            require(
                schedule["case_id"] in {"M04", "S04"}
                and schedule["repetition_index"] % 2 == 0
                and record == expected
                and event["name"]
                == (
                    "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION"
                    if managed
                    else "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS"
                ),
                "E_TRANSITION_SHAPE",
                "terminal fence transition record drift",
            )
            require(
                details["operation_key"] == envelope["operation_key"]
                and details["consistency"]
                == ("SERIALIZABLE" if managed else "LINEARIZABLE_TOP_LEVEL_CAS")
                and details["compare_record_sha256"]
                == envelope["compare_record_sha256"]
                and details["committed_record_sha256"] == record_sha
                and details["cas_result"] == envelope["cas_result"]
                and details["revision"] == envelope["committed_revision"],
                "E_TRANSITION_OUTER_BINDING",
                "terminal fence outer/transition binding drift",
            )
        elif phase == "SIGN_ATTEMPT_PREPARED":
            require(
                event["name"].endswith("_SIGN_ATTEMPT_PREPARED")
                and record["attempt"] == "SIGN_ATTEMPT_PREPARED"
                and record["attempt_consumed"] is False
                and record["prepared_record_sha256"] != ZERO_SHA256
                and record["call_binding_sha256"] == ZERO_SHA256
                and record["processed_response_sha256"] == ZERO_SHA256
                and record["validated_response_sha256"] == ZERO_SHA256
                and record["validation_binding_sha256"] == ZERO_SHA256
                and record["receipt"] == "NONE"
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is False,
                "E_TRANSITION_SHAPE",
                "prepared transition record drift",
            )
        elif phase == "SIGN_ATTEMPT_CALL_CONSUMED":
            require(
                event["name"].endswith("_SIGN_ATTEMPT_CALL_CONSUMED")
                and record["attempt"] == "SIGN_ATTEMPT_PREPARED"
                and record["attempt_consumed"] is True
                and record["prepared_record_sha256"] != ZERO_SHA256
                and record["call_binding_sha256"] != ZERO_SHA256
                and record["processed_response_sha256"] == ZERO_SHA256
                and record["validated_response_sha256"] == ZERO_SHA256
                and record["validation_binding_sha256"] == ZERO_SHA256
                and record["receipt"] == "NONE"
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is False,
                "E_TRANSITION_SHAPE",
                "call-consumption transition record drift",
            )
        elif phase == "SIGNATURE_RECEIPT_COMMITTED":
            require(
                event["name"].endswith("_SIGNATURE_RECEIPT_COMMITTED")
                and record["attempt"] == "CONSUMED"
                and record["attempt_consumed"] is True
                and record["processed_response_sha256"]
                == record["validated_response_sha256"] != ZERO_SHA256
                and record["validation_binding_sha256"] != ZERO_SHA256
                and record["receipt"] == "SIGNATURE_RECEIPT_COMMITTED"
                and record["receipt_binding_sha256"] != ZERO_SHA256
                and record["terminal"] is True,
                "E_TRANSITION_SHAPE",
                "receipt transition record drift",
            )
        elif phase == "AMBIGUOUS_QUARANTINED":
            require(
                event["name"].endswith("_AMBIGUOUS_QUARANTINED")
                and record["attempt"] == "AMBIGUOUS_QUARANTINED"
                and record["attempt_consumed"] is True
                and record["processed_response_sha256"] != ZERO_SHA256
                and record["receipt"] == "NONE"
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is True,
                "E_TRANSITION_SHAPE",
                "quarantine transition record drift",
            )
            require(
                (
                    record["validation_binding_sha256"] == ZERO_SHA256
                    and record["validated_response_sha256"] == ZERO_SHA256
                )
                or (
                    record["validation_binding_sha256"] != ZERO_SHA256
                    and record["validated_response_sha256"]
                    == record["processed_response_sha256"]
                ),
                "E_TRANSITION_SHAPE",
                "quarantine validation binding drift",
            )
        elif phase == "RESPONSE_REJECTED_FAIL_CLOSED":
            require(
                event["name"].endswith("_RESPONSE_REJECTED")
                and record["attempt"] == "REJECTED_FAIL_CLOSED"
                and record["attempt_consumed"] is True
                and record["processed_response_sha256"] != ZERO_SHA256
                and record["validated_response_sha256"] == ZERO_SHA256
                and record["validation_binding_sha256"] == ZERO_SHA256
                and record["receipt"] == "NONE"
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is True,
                "E_TRANSITION_SHAPE",
                "response rejection transition drift",
            )
        elif phase == "PRE_ATTEMPT_REJECTED_FAIL_CLOSED":
            require(
                record["attempt"] == "REJECTED_FAIL_CLOSED"
                and record["attempt_consumed"] is False
                and record["prepared_record_sha256"] == ZERO_SHA256
                and record["call_binding_sha256"] == ZERO_SHA256
                and record["processed_response_sha256"] == ZERO_SHA256
                and record["validated_response_sha256"] == ZERO_SHA256
                and record["validation_binding_sha256"] == ZERO_SHA256
                and record["receipt"] == "NONE"
                and record["receipt_binding_sha256"] == ZERO_SHA256
                and record["terminal"] is True,
                "E_TRANSITION_SHAPE",
                "pre-attempt rejection transition drift",
            )

        previous_phase = phase
        previous_record = record
        previous_sha = record_sha
        previous_revision += 1

    require(previous_record is not None, "E_TRANSITION_STATE", "missing transition winner")
    require(
        state["durable_operation_record_sha256"] == previous_sha
        and state["durable_operation_revision"] == previous_revision,
        "E_TRANSITION_STATE",
        "final durable tip differs from replay winner",
    )
    projection = {
        "authority", "outbox", "attempt", "attempt_consumed", "receipt",
        "challenge_consumptions", "logical_sink_reservations",
        "prepared_record_sha256", "call_binding_sha256",
        "processed_response_sha256", "validated_response_sha256",
        "validation_binding_sha256", "receipt_binding_sha256",
    }
    require(
        all(state[field] == previous_record[field] for field in projection),
        "E_TRANSITION_STATE",
        "final durable record/state projection drift",
    )
    if schedule["case_id"] == "M05":
        attempts = [
            event for event in trace
            if event["name"] == "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT"
        ]
        require(
            len(attempts) == 1
            and attempts[0]["sequence"] + 1 == transitions[0]["sequence"]
            and transitions[0]["name"] == "SPANNER_OUTBOX_COMMITTED",
            "E_M05_ATOMIC",
            "M05 r1 binding was not one modeled serializable transaction",
        )


def _replay_call_chain(row: dict[str, Any]) -> None:
    state = row["state"]
    require(set(state) == STATE_FIELDS, "E_STATE_FIELDS", "state fields drift")
    require(row["evidence"]["pre_state_sha256"] == sha256_value(INITIAL_STATE), "E_PRE_STATE_HASH", "pre-state hash drift")
    require(row["evidence"]["post_state_sha256"] == sha256_value(state), "E_POST_STATE_HASH", "post-state hash drift")
    prepared = [event for event in row["event_trace"] if event["name"].endswith("_SIGN_ATTEMPT_PREPARED")]
    consumptions = [
        event for event in row["event_trace"]
        if event["name"].endswith("_SIGN_ATTEMPT_CALL_CONSUMED")
    ]
    calls = [event for event in row["event_trace"] if event["name"].endswith("_DOUBLE_CALL")]
    processing = [event for event in row["event_trace"] if event["name"].endswith("_DOUBLE_PROCESSING_COMPLETED")]
    deliveries = [
        event for event in row["event_trace"]
        if event["name"].endswith("_DOUBLE_RESPONSE_OBSERVED")
        or event["name"].endswith("_DOUBLE_RESPONSE_DROPPED")
    ]
    validations = [event for event in row["event_trace"] if event["name"].endswith("_RESPONSE_FULLY_VALIDATED")]
    receipts = [event for event in row["event_trace"] if event["name"].endswith("_SIGNATURE_RECEIPT_COMMITTED")]
    rejections = [event for event in row["event_trace"] if event["name"].endswith("_RESPONSE_REJECTED")]
    require(len(prepared) <= 1 and len(calls) <= 1, "E_CALL_CARDINALITY", "prepared/call cardinality drift")
    require(
        len(consumptions) == len(calls),
        "E_CALL_CONSUMPTION",
        "call-consumption CAS cardinality drift",
    )
    require(len(calls) == len(processing), "E_PROCESS_COUNT", "call/processing cardinality drift")
    require(len(calls) == len(deliveries), "E_RESPONSE_CARDINALITY", "call/response delivery cardinality drift")
    require(state["simulated_application_calls"] == len(calls), "E_CALL_STATE", "state call count drift")
    require(state["simulated_processing_events"] == len(processing), "E_PROCESS_COUNT", "state processing count drift")
    require(row["evidence"]["simulated_application_calls"] == len(calls), "E_CALL_COUNT", "evidence call count drift")
    require(row["evidence"]["simulated_processing_events"] == len(processing), "E_PROCESS_COUNT", "evidence processing count drift")
    require(state["attempt_consumed"] is bool(calls), "E_ATTEMPT_CONSUMPTION", "attempt consumption drift")
    if prepared:
        details = prepared[0]["details"]
        record = details["prepared_record"]
        require(set(record) == PREPARED_FIELDS, "E_PREPARED_FIELDS", "prepared record fields drift")
        require(details["durable"] is True, "E_PREPARED_DURABLE", "prepared record is not durable")
        require(record["operation_id"] == row["schedule"]["simulation_run_id"], "E_PREPARED_BINDING", "prepared operation drift")
        require(record["message_sha256"] == MESSAGE_SHA256 and record["public_key_pin_sha256"] == sha256_bytes(bytes.fromhex(PUBLIC_KEY_HEX)), "E_PREPARED_BINDING", "prepared message/key drift")
        require(record["attempt_sequence"] == 1 and record["exact_key_version"] > 0, "E_PREPARED_BINDING", "prepared sequence/version drift")
        require(details["prepared_record_sha256"] == sha256_value(record), "E_PREPARED_HASH", "prepared hash drift")
        state_bindings = {
            "prepared_operation_id": record["operation_id"],
            "prepared_request_sha256": record["canonical_request_sha256"],
            "prepared_key_version": record["exact_key_version"],
            "prepared_public_key_sha256": record["public_key_pin_sha256"],
            "prepared_message_sha256": record["message_sha256"],
            "prepared_attempt_sequence": record["attempt_sequence"],
            "prepared_record_sha256": details["prepared_record_sha256"],
        }
        require(all(state[key] == value for key, value in state_bindings.items()), "E_PREPARED_STATE", "prepared state drift")
    if calls:
        require(prepared and prepared[0]["sequence"] < calls[0]["sequence"], "E_PREPARED_ORDER", "call preceded prepared record")
        consumption = consumptions[0]
        details = calls[0]["details"]
        require(
            prepared[0]["sequence"] < consumption["sequence"]
            and consumption["sequence"] + 1 == calls[0]["sequence"],
            "E_CALL_CONSUMPTION",
            "call was not immediately preceded by consumption CAS",
        )
        require(
            consumption["details"]["transition_record"]["attempt_consumed"] is True
            and consumption["details"]["transition_record"]["call_binding_sha256"]
            == details["call_binding_sha256"],
            "E_CALL_CONSUMPTION",
            "call/consumption record binding drift",
        )
        require(details["hidden_retries"] is False and details["evidence_class"] == EVIDENCE_CLASS, "E_CALL_PROVENANCE", "call provenance drift")
        require(
            details["operation_id"] == row["schedule"]["simulation_run_id"]
            == state["prepared_operation_id"]
            and details["prepared_record_sha256"] == state["prepared_record_sha256"]
            and details["key_version"] == state["prepared_key_version"]
            and details["public_key_sha256"] == state["prepared_public_key_sha256"]
            and details["message_sha256"] == state["prepared_message_sha256"]
            and details["attempt_sequence"] == state["prepared_attempt_sequence"] == 1,
            "E_CALL_PREPARED_BINDING",
            "call/prepared binding drift",
        )
        expected_call = _framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/double-call",
            details["prepared_record_sha256"], details["request_sha256"],
            details["execution_request_id"] or "NOT_APPLICABLE",
            details["executing_node"] or "NOT_APPLICABLE",
            details["execution_cluster_id"] or "NOT_APPLICABLE",
            details["audit_record_sha256"] or "NOT_APPLICABLE",
            details["wire_attempt_sha256"] or "NOT_APPLICABLE",
        )
        require(details["call_binding_sha256"] == expected_call == state["call_binding_sha256"], "E_CALL_BINDING", "call binding drift")
        require(details["request_sha256"] == state["prepared_request_sha256"], "E_CALL_REQUEST", "prepared/call request mismatch")
        require(processing[0]["details"]["call_binding_sha256"] == expected_call, "E_PROCESS_BINDING", "processing call binding drift")
        require(processing[0]["details"]["response_sha256"] == state["processed_response_sha256"], "E_PROCESS_RESPONSE", "processed response drift")
        require(
            calls[0]["sequence"] < processing[0]["sequence"] < deliveries[0]["sequence"],
            "E_RESPONSE_ORDER",
            "call/processing/delivery order drift",
        )
        require(
            deliveries[0]["details"]["call_binding_sha256"] == expected_call
            and deliveries[0]["details"]["response_sha256"]
            == processing[0]["details"]["response_sha256"],
            "E_RESPONSE_BINDING",
            "response delivery binding drift",
        )
    else:
        require(state["call_binding_sha256"] == state["processed_response_sha256"] == ZERO_SHA256, "E_ZERO_CALL_STATE", "zero-call row has call state")
    if validations:
        require(calls and len(validations) == 1, "E_VALIDATION_CARDINALITY", "validation without one call")
        details = validations[0]["details"]
        call_details = calls[0]["details"]
        require(
            details["operation_id"] == state["prepared_operation_id"]
            and details["call_binding_sha256"] == call_details["call_binding_sha256"]
            and details["request_sha256"] == state["prepared_request_sha256"]
            and details["key_version"] == state["prepared_key_version"]
            and details["public_key_sha256"] == state["prepared_public_key_sha256"]
            and details["message_sha256"] == state["prepared_message_sha256"]
            and all(
                details[field] == call_details[field]
                for field in (
                    "execution_request_id",
                    "executing_node",
                    "execution_cluster_id",
                    "audit_record_sha256",
                    "wire_attempt_sha256",
                )
            ),
            "E_VALIDATION_UPSTREAM",
            "validation/prepared call binding drift",
        )
        expected_validation = _framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/response-validation",
            details["call_binding_sha256"], details["response_sha256"], details["request_sha256"],
            str(details["key_version"]), details["public_key_sha256"], details["message_sha256"],
            details["execution_request_id"] or "NOT_APPLICABLE",
            details["executing_node"] or "NOT_APPLICABLE",
            details["execution_cluster_id"] or "NOT_APPLICABLE",
            details["audit_record_sha256"] or "NOT_APPLICABLE",
            details["wire_attempt_sha256"] or "NOT_APPLICABLE",
        )
        require(details["message_bytes"] == 137, "E_VALIDATION_MESSAGE", "validated message length drift")
        require(
            deliveries[0]["name"].endswith("_DOUBLE_RESPONSE_OBSERVED")
            and deliveries[0]["sequence"] < validations[0]["sequence"],
            "E_VALIDATION_ORDER",
            "validation preceded observed response",
        )
        require(details["response_sha256"] == state["processed_response_sha256"], "E_VALIDATION_RESPONSE", "validation response mismatch")
        require(details["validation_binding_sha256"] == expected_validation == state["validation_binding_sha256"], "E_VALIDATION_BINDING", "validation binding drift")
        require(state["validated_response_sha256"] == details["response_sha256"], "E_VALIDATION_STATE", "validated response state drift")
    else:
        require(state["validation_binding_sha256"] == state["validated_response_sha256"] == ZERO_SHA256, "E_ZERO_VALIDATION_STATE", "unvalidated row has validation state")
    for rejection in rejections:
        require(
            len(deliveries) == 1
            and deliveries[0]["name"].endswith("_DOUBLE_RESPONSE_OBSERVED")
            and deliveries[0]["sequence"] < rejection["sequence"],
            "E_REJECTION_ORDER",
            "response rejection preceded observed response",
        )
    if receipts:
        require(calls and validations and len(receipts) == 1, "E_RECEIPT_CAUSAL", "receipt lacks call/validation")
        details = receipts[0]["details"]
        call_details = calls[0]["details"]
        validation_details = validations[0]["details"]
        require(
            details["operation_id"] == state["prepared_operation_id"]
            and details["prepared_record_sha256"] == state["prepared_record_sha256"]
            and details["request_sha256"] == state["prepared_request_sha256"]
            and details["response_sha256"] == state["validated_response_sha256"]
            and details["key_version"] == state["prepared_key_version"]
            and details["public_key_sha256"] == state["prepared_public_key_sha256"]
            and details["message_sha256"] == state["prepared_message_sha256"]
            and details["call_binding_sha256"] == call_details["call_binding_sha256"]
            and details["validation_binding_sha256"]
            == validation_details["validation_binding_sha256"]
            and all(
                details[field] == call_details[field] == validation_details[field]
                for field in (
                    "execution_request_id",
                    "executing_node",
                    "execution_cluster_id",
                    "audit_record_sha256",
                    "wire_attempt_sha256",
                )
            ),
            "E_RECEIPT_UPSTREAM",
            "receipt upstream binding drift",
        )
        expected_receipt = _framed_hash(
            "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/durable-receipt",
            details["prepared_record_sha256"], details["call_binding_sha256"],
            details["validation_binding_sha256"], details["response_sha256"],
            details["execution_request_id"] or "NOT_APPLICABLE",
            details["executing_node"] or "NOT_APPLICABLE",
            details["execution_cluster_id"] or "NOT_APPLICABLE",
            details["audit_record_sha256"] or "NOT_APPLICABLE",
            details["wire_attempt_sha256"] or "NOT_APPLICABLE",
        )
        require(details["receipt_binding_sha256"] == expected_receipt == state["receipt_binding_sha256"], "E_RECEIPT_BINDING", "receipt binding drift")
        require(receipts[0]["sequence"] > validations[0]["sequence"], "E_RECEIPT_CAUSAL", "receipt preceded validation")
    else:
        require(state["receipt_binding_sha256"] == ZERO_SHA256, "E_RECEIPT_TRACE", "untraced receipt binding")
    require((state["receipt"] == "SIGNATURE_RECEIPT_COMMITTED") == bool(receipts), "E_RECEIPT_STATE", "receipt state/event drift")
    for event in [event for event in row["event_trace"] if event["name"] == "DURABLE_IMAGE_SERIALIZED"]:
        image = event["details"]["durable_image"]
        require(set(image) == STATE_FIELDS, "E_DURABLE_FIELDS", "durable image fields drift")
        require(event["details"]["image_sha256"] == sha256_value(image), "E_DURABLE_HASH", "durable image hash drift")
        destroyed = _one_event(row, "EPHEMERAL_WORKER_DESTROYED")
        restarted = _one_event(row, "WORKER_RESTARTED")
        constructed = _one_event(row, "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE")
        no_resign = _one_event(row, "RESTART_NO_RESIGN_CONFIRMED")
        require(
            event["sequence"] < destroyed["sequence"] < restarted["sequence"]
            < constructed["sequence"] < no_resign["sequence"],
            "E_RESTART_ORDER",
            "restart transition order drift",
        )
        require(restarted["details"] == {
            "calls_before_restart": image["simulated_application_calls"],
            "durable_attempt_state": image["attempt"],
        }, "E_RESTART_IMAGE", "restart metadata does not bind durable image")
        require(no_resign["details"]["calls_after_restart"] == image["simulated_application_calls"], "E_RESTART_IMAGE", "restart call count drift")
        if row["schedule"]["case_id"] != "M15":
            expected_state = dict(image)
            expected_state["restarts"] += 1
            require(expected_state == state, "E_RESTART_IMAGE", "post-restart state differs from durable image")
        else:
            expected_durable_image = dict(INITIAL_STATE)
            expected_authority_record = _expected_operation_record(
                row["schedule"]["simulation_run_id"],
                MANAGED_KEY_VERSION,
                authority="AUTHORIZED_COMMITTED",
                outbox="SIGN_PENDING",
                challenge_consumptions=1,
                logical_sink_reservations=1,
            )
            expected_durable_image.update(
                authority="AUTHORIZED_COMMITTED",
                outbox="SIGN_PENDING",
                database_attempts=1,
                challenge_consumptions=1,
                logical_sink_reservations=1,
                durable_operation_record_sha256=sha256_value(
                    expected_authority_record
                ),
                durable_operation_revision=1,
            )
            require(
                image == expected_durable_image,
                "E_RESTART_IMAGE",
                "M15 crash-before-attempt durable image drift",
            )
            post_restart_signing_fields = {
                "attempt",
                "attempt_consumed",
                "call_binding_sha256",
                "durable_operation_record_sha256",
                "durable_operation_revision",
                "prepared_attempt_sequence",
                "prepared_key_version",
                "prepared_message_sha256",
                "prepared_operation_id",
                "prepared_public_key_sha256",
                "prepared_record_sha256",
                "prepared_request_sha256",
                "processed_response_sha256",
                "receipt",
                "receipt_binding_sha256",
                "simulated_application_calls",
                "simulated_processing_events",
                "validated_response_sha256",
                "validation_binding_sha256",
            }
            require(
                state["restarts"] == image["restarts"] + 1
                and all(
                    state[field] == image[field]
                    for field in STATE_FIELDS
                    - post_restart_signing_fields
                    - {"restarts"}
                ),
                "E_RESTART_IMAGE",
                "M15 durable image changed outside post-restart signing fields",
            )
    for event in [event for event in row["event_trace"] if event["name"] == "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE"]:
        require(event["details"] == {"prior_worker_ephemeral_state_reused": False, "state_object_reused": False}, "E_RESTART_REUSE", "restart reused state")


def _operation_record(run_id: str, key_version: int) -> dict[str, Any]:
    return _expected_operation_record(
        run_id,
        key_version,
        authority="AUTHORIZED_COMMITTED",
        outbox="SIGN_PENDING",
        challenge_consumptions=1,
        logical_sink_reservations=1,
    )


def _validate_exact_key_model(row: dict[str, Any], case_id: str, repetition: int) -> None:
    if case_id not in {"M04", "S04", "S05", "S06"}:
        return
    run_id = row["schedule"]["simulation_run_id"]
    key_version = MANAGED_KEY_VERSION if case_id == "M04" else SELF_HOSTED_KEY_VERSION
    operation_key = _framed_hash(EXACT_KEY_DOMAIN, run_id)
    operation_sha = sha256_value(_operation_record(run_id, key_version))
    if case_id in {"S05", "S06"} or repetition % 2:
        lookup_name = "SPANNER_EXACT_STRONG_LOOKUP" if case_id == "M04" else "ETCD_EXACT_LINEARIZABLE_LOOKUP"
        lookup = _one_event(row, lookup_name)["details"]
        require(lookup["operation_key"] == operation_key and lookup["record_sha256"] == operation_sha, "E_EXACT_KEY_LOOKUP", "exact operation lookup drift")
        require(lookup["result"] == "EXACT_OPERATION_RECORD" and lookup["terminal"] is False, "E_EXACT_KEY_LOOKUP", "exact lookup result drift")
        expected_consistency = "STRONG" if case_id == "M04" else "LINEARIZABLE"
        require(
            lookup["consistency"] == expected_consistency and lookup["revision"] == 1,
            "E_CAS_CONSISTENCY",
            "exact lookup consistency/revision drift",
        )
        require(
            row["state"]["durable_operation_record_sha256"] == operation_sha
            and row["state"]["durable_operation_revision"] == 1,
            "E_EXACT_KEY_STATE",
            "exact operation durable tip drift",
        )
        return
    bare_name = "SPANNER_BARE_ABSENT_STRONG_READ" if case_id == "M04" else "ETCD_BARE_ABSENT_LINEARIZABLE_READ"
    fence_name = "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION" if case_id == "M04" else "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS"
    confirm_name = "SPANNER_CONFIRMING_STRONG_READ" if case_id == "M04" else "ETCD_CONFIRMING_LINEARIZABLE_READ"
    conflict_name = "SPANNER_DELAYED_COMMIT_FENCE_CONFLICT" if case_id == "M04" else "ETCD_DELAYED_COMMIT_FENCE_CONFLICT"
    bare = _one_event(row, bare_name)
    fence = _one_event(row, fence_name)
    confirm = _one_event(row, confirm_name)
    conflict = _one_event(row, conflict_name)
    require(bare["sequence"] < fence["sequence"] < confirm["sequence"] < conflict["sequence"], "E_UNKNOWN_FENCE", "fence order drift")
    require({event["details"]["operation_key"] for event in (bare, fence, confirm, conflict)} == {operation_key}, "E_FENCE_KEY", "fence key drift")
    expected_read_consistency = "STRONG" if case_id == "M04" else "LINEARIZABLE"
    expected_fence_consistency = "SERIALIZABLE" if case_id == "M04" else "LINEARIZABLE_TOP_LEVEL_CAS"
    require(
        bare["details"]["consistency"] == expected_read_consistency
        and bare["details"]["revision"] == 0
        and fence["details"]["consistency"] == expected_fence_consistency
        and fence["details"]["revision"] == 1
        and confirm["details"]["consistency"] == expected_read_consistency
        and confirm["details"]["revision"] == 1
        and conflict["details"]["revision"] == 1,
        "E_CAS_CONSISTENCY",
        "fence consistency/revision drift",
    )
    fence_record = _expected_operation_record(
        run_id,
        key_version,
        authority="FENCED_ABSENT",
        outbox="NONE",
        challenge_consumptions=0,
        logical_sink_reservations=0,
        terminal=True,
        record_kind="TERMINAL_FENCE",
    )
    fence_sha = sha256_value(fence_record)
    require(bare["details"]["result"] == "ABSENT" and bare["details"]["record_sha256"] == ZERO_SHA256 and bare["details"]["terminal"] is False, "E_UNKNOWN_FENCE", "bare absence was terminal")
    require(fence["details"]["compare_record_sha256"] == ZERO_SHA256 and fence["details"]["committed_record_sha256"] == fence_sha and fence["details"]["cas_result"] == "APPLIED", "E_UNKNOWN_FENCE", "fence CAS drift")
    require(confirm["details"]["record_sha256"] == fence_sha and confirm["details"]["result"] == "TERMINAL_FENCE" and confirm["details"]["terminal"] is True, "E_UNKNOWN_FENCE", "confirming read drift")
    require(
        conflict["details"]["compare_record_sha256"] == ZERO_SHA256
        and conflict["details"]["delayed_record_sha256"] == operation_sha
        and conflict["details"]["observed_record_sha256"] == fence_sha
        and conflict["details"]["cas_result"] == "CONFLICT_NO_MUTATION",
        "E_FENCE_RACE",
        "delayed commit bypassed fence",
    )
    require(
        row["state"]["durable_operation_record_sha256"] == fence_sha
        and row["state"]["durable_operation_revision"] == 1,
        "E_EXACT_KEY_STATE",
        "terminal fence durable tip drift",
    )


def _expected_witness_record(
    run_id: str,
    ledger_generation: int,
    previous_record: dict[str, Any] | None,
) -> dict[str, Any]:
    prior_cluster = "cluster-incumbent" if previous_record is None else previous_record["new_cluster_id"]
    prior_incarnation = "incarnation-incumbent" if previous_record is None else previous_record["new_incarnation_id"]
    prior_floor = 100 if previous_record is None else previous_record["new_revision_floor"]
    snapshot_revision = prior_floor - 10
    bump = 1000 + ledger_generation
    return {
        "domain": WITNESS_DOMAIN,
        "authority_id": _framed_hash(WITNESS_DOMAIN, run_id, "authority"),
        "prior_cluster_id": prior_cluster,
        "prior_incarnation_id": prior_incarnation,
        "prior_revision_floor": prior_floor,
        "snapshot_sha256": _framed_hash(WITNESS_DOMAIN, run_id, "snapshot", str(ledger_generation)),
        "snapshot_revision": snapshot_revision,
        "new_cluster_id": f"cluster-rebased-{run_id[:16]}-g{ledger_generation + 1}",
        "new_incarnation_id": f"incarnation-rebased-{run_id[16:32]}-g{ledger_generation + 1}",
        "new_revision_floor": snapshot_revision + bump,
        "bump_revision": bump,
        "mark_compacted": True,
        "rebase_authorization_sha256": _framed_hash(WITNESS_DOMAIN, run_id, "rebase-authorization", str(ledger_generation + 1)),
        "previous_record_sha256": ZERO_SHA256 if previous_record is None else sha256_value(previous_record),
        "generation": ledger_generation + 1,
    }


def _validate_witness_model(row: dict[str, Any], case_id: str, variant: str) -> None:
    if case_id not in {"S09", "S10", "S11"}:
        return
    event_name = {
        "S09": "EXTERNAL_WITNESS_VALIDATION_FAILED",
        "S10": "RESTORE_IDENTITY_OR_WITNESS_BINDING_REJECTED",
        "S11": "EXTERNAL_WITNESS_EXACT_CAS_COMMITTED",
    }[case_id]
    details = _one_event(row, event_name)["details"]
    record = details["witness_record"]
    require(set(record) == WITNESS_FIELDS, "E_WITNESS_FIELDS", "witness record fields drift")
    require(details["witness_record_sha256"] == sha256_value(record), "E_WITNESS_HASH", "witness record hash drift")
    require(details["actor_domain"] == details["caller_actor_domain"] == WITNESS_ACTOR_DOMAIN, "E_WITNESS_DOMAIN", "witness actor domain drift")
    run_id = row["schedule"]["simulation_run_id"]
    lineage_id = f"logical-lineage-{run_id[:24]}"
    require(
        details["logical_cluster_lineage_id"] == lineage_id
        and details["witness_key"]
        == _framed_hash(
            f"{WITNESS_DOMAIN}/exact-key",
            record["authority_id"],
            lineage_id,
        ),
        "E_WITNESS_KEY",
        "witness key/lineage drift",
    )
    expected = _expected_witness_record(run_id, 0, None)
    expected_open_sha = ZERO_SHA256
    expected_open_generation = 0
    expected_reason = "NONE"
    if case_id == "S09" and variant == "RESTORE_OLDER_SNAPSHOT_WITHOUT_BUMP":
        expected.update(bump_revision=0, new_revision_floor=expected["snapshot_revision"], mark_compacted=False)
        expected_reason = "MARK_COMPACTED_REQUIRED"
    elif case_id == "S09" and variant == "RETURN_STALE_REPLAYED_OR_FORKED_WITNESS_RECORD":
        prior = expected
        expected_open_sha = sha256_value(prior)
        expected_open_generation = 1
        expected = _expected_witness_record(run_id, 1, prior)
        expected.update(previous_record_sha256=ZERO_SHA256, generation=1)
        expected_reason = "PREVIOUS_RECORD_SHA256_MISMATCH"
    elif case_id == "S09":
        expected_reason = "UNAVAILABLE"
    elif case_id == "S10" and row["schedule"]["repetition_index"] % 2:
        expected["new_incarnation_id"] = expected["prior_incarnation_id"]
        expected_reason = "INCARNATION_ID_REUSED"
    elif case_id == "S10":
        expected["previous_record_sha256"] = "f" * 64
        expected_reason = "PREVIOUS_RECORD_SHA256_MISMATCH"
    require(record == expected, "E_WITNESS_BINDINGS", f"{case_id} witness binding drift")
    if case_id == "S09":
        require(
            _one_event(row, "RESTORE_WITNESS_CANDIDATE_STAGED")["details"]
            == {
                "snapshot_sha256": expected["snapshot_sha256"],
                "witness_record_sha256": sha256_value(expected),
            },
            "E_WITNESS_BINDINGS",
            "S09 staged witness candidate drift",
        )
    else:
        require(
            _one_event(row, "SNAPSHOT_HASH_VERIFIED")["details"]
            == {
                "skip_hash_check": False,
                "snapshot_revision": expected["snapshot_revision"],
                "snapshot_sha256": expected["snapshot_sha256"],
            },
            "E_WITNESS_BINDINGS",
            f"{case_id} snapshot verification drift",
        )
    opened = _one_event(row, "EXTERNAL_WITNESS_LEDGER_OPENED")["details"]
    expected_witness_key = _framed_hash(
        f"{WITNESS_DOMAIN}/exact-key",
        record["authority_id"],
        lineage_id,
    )
    require(opened == {
        "actor_domain": WITNESS_ACTOR_DOMAIN,
        "current_record_sha256": expected_open_sha,
        "generation": expected_open_generation,
        "isolated_from_restore_snapshot": True,
        "logical_cluster_lineage_id": lineage_id,
        "observed_generation": expected_open_generation,
        "observed_record_sha256": expected_open_sha,
        "read_consistency": "LINEARIZABLE",
        "read_revision": expected_open_generation,
        "witness_key": expected_witness_key,
    }, "E_WITNESS_LEDGER", "witness ledger initial state drift")
    require(
        details["expected_previous_record_sha256"] == record["previous_record_sha256"]
        and details["expected_generation"] == max(record["generation"] - 1, 0)
        and details["observed_previous_record_sha256"] == opened["current_record_sha256"]
        and details["observed_generation"] == opened["generation"]
        and details["observed_witness_key"] == details["witness_key"],
        "E_WITNESS_CAS_ENVELOPE",
        "witness CAS compare envelope drift",
    )
    if case_id == "S11":
        require(details["cas_result"] == "APPLIED" and details["rejection_reason"] == "NONE", "E_WITNESS_CAS", "valid witness CAS failed")
        require(details["observed_previous_record_sha256"] == ZERO_SHA256 and details["observed_generation"] == 0, "E_WITNESS_CAS", "witness CAS compare drift")
        require(row["state"]["witness_record_sha256"] == sha256_value(record) and row["state"]["witness_generation"] == 1, "E_WITNESS_STATE", "witness state drift")
        require(row["state"]["restore_cluster_id"] == record["new_cluster_id"] and row["state"]["restore_incarnation_id"] == record["new_incarnation_id"] and row["state"]["restore_revision_floor"] == record["new_revision_floor"], "E_RESTORE_BINDING", "restore/witness state drift")
        require(row["state"]["watch"] == "INVALIDATED" and row["state"]["cache"] == "FULL_LINEARIZABLE_REBUILD", "E_RESTORE_REBUILD", "restore rebuild drift")
    else:
        require(details["cas_result"] == "REJECTED_NO_MUTATION" and details["rejection_reason"] == expected_reason, "E_WITNESS_REJECTION", "invalid witness rejection drift")
        require(row["state"]["witness_record_sha256"] == expected_open_sha and row["state"]["witness_generation"] == expected_open_generation, "E_WITNESS_NO_MUTATION", "failed witness CAS mutated state")


def _validate_s12_model(row: dict[str, Any], classification: str) -> None:
    if row["schedule"]["case_id"] != "S12":
        return
    run_id = row["schedule"]["simulation_run_id"]
    cluster_id = f"cluster-double-{run_id[:16]}"
    request_id = f"request-double-{run_id[16:40]}"
    seal = _one_event(row, "OPENBAO_DIRECT_TARGET_SEAL_STATUS")["details"]
    route = _one_event(row, "OPENBAO_ROUTE_EXECUTION_EVIDENCE")["details"]
    require(seal == {
        "target_node": "node-active-a", "cluster_id": cluster_id, "target_ha_role": "ACTIVE",
        "sealed": True, "service_wide_unavailable_inferred": False,
    }, "E_S12_SEAL", "S12 seal record drift")
    success = classification == "CONFORMING_OBSERVED"
    expected_audit = _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/s12-audit",
        run_id, cluster_id, request_id, "node-active-a", "node-standby-b",
    ) if success else None
    expected_wire = _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/s12-wire-attempt",
        run_id, cluster_id, request_id, "node-standby-b",
    ) if success else None
    require(route == {
        "target_node": "node-active-a", "route_node": "node-active-a",
        "executing_node": "node-standby-b" if success else None,
        "executing_ha_role": "PERFORMANCE_STANDBY_ACTIVE" if success else None,
        "cluster_id": cluster_id, "request_id": request_id,
        "redirect_node": "node-standby-b" if success else None,
        "forwarded_by_node": "node-active-a" if success else None,
        "audit_record_sha256": expected_audit, "wire_attempt_sha256": expected_wire,
        "redirect_forward_audit_bound": success,
    }, "E_S12_CORRELATION", "S12 execution correlation drift")
    calls = [event for event in row["event_trace"] if event["name"] == "TRANSIT_DOUBLE_CALL"]
    receipts = [event for event in row["event_trace"] if event["name"] == "TRANSIT_SIGNATURE_RECEIPT_COMMITTED"]
    if success:
        require(len(calls) == len(receipts) == 1, "E_S12_RECEIPT", "S12 success call/receipt drift")
        for event in (calls[0], _one_event(row, "TRANSIT_RESPONSE_FULLY_VALIDATED"), receipts[0]):
            details = event["details"]
            require(
                details["execution_request_id"] == request_id
                and details["executing_node"] == "node-standby-b"
                and details["execution_cluster_id"] == cluster_id
                and details["audit_record_sha256"] == expected_audit
                and details["wire_attempt_sha256"] == expected_wire,
                "E_S12_CALL_BINDING",
                "S12 call/receipt does not bind execution evidence",
            )
    else:
        require(not calls and not receipts and row["state"]["receipt"] == "NONE" and row["state"]["emitted_outputs"] == 0, "E_S12_FAIL", "S12 fail branch accepted work")
        require(
            _one_event(
                row,
                "OPENBAO_STANDBY_TAKEOVER_UNAVAILABLE_FAIL_CLOSED",
            )["details"]
            == {
                "cluster_id": cluster_id,
                "request_id": request_id,
                "accepted_receipts": 0,
                "emitted_outputs": 0,
            },
            "E_S12_FAIL",
            "S12 fail-closed result drift",
        )


def independent_oracle_row(
    row: dict[str, Any],
    expected_schedule: dict[str, Any],
    track: dict[str, Any],
    case: dict[str, Any],
) -> None:
    require(row["schedule"] == expected_schedule, "E_SCHEDULE_DRIFT", "candidate schedule differs from independent schedule")
    case_id = case["case_id"]
    repetition = expected_schedule["repetition_index"]
    variant = expected_variant(case, repetition)
    classification = expected_classification(case_id, repetition)
    require(row["case"]["injection_variant"] == variant, "E_VARIANT", f"{case_id} variant drift")
    actual_classification = row["case_classification"] or row["simulated_classification"]
    require(actual_classification == classification, "E_CLASSIFICATION", f"{case_id} oracle classification drift")
    require(classification in case["allowed_classifications"], "E_CLASSIFICATION_SET", f"{case_id} result outside contract")

    _validate_event_closure(row)
    _validate_fault_cut(row, case, variant)
    _validate_durable_transition_replay(row)
    _replay_call_chain(row)
    expected_core = expected_core_state(case_id, repetition)
    require(
        all(row["state"][field] == value for field, value in expected_core.items()),
        "E_CORE_STATE",
        "core authority/outbox state drift",
    )
    _validate_exact_key_model(row, case_id, repetition)
    _validate_witness_model(row, case_id, variant)
    _validate_s12_model(row, classification)

    names = _event_names(row)
    for name in REQUIRED_EVENTS[case_id]:
        require(name in names, "E_REQUIRED_EVENT", f"{case_id} missing event {name}")
    tokens = set(row["evidence"]["semantic_tokens"])
    for token in REQUIRED_TOKENS[case_id]:
        require(token in tokens, "E_REQUIRED_TOKEN", f"{case_id} missing token {token}")
    evidence_expectation = compile_evidence_expectation(
        case_id,
        repetition,
        variant,
        classification,
    )
    validate_evidence_expectation(row, case, evidence_expectation)

    expected_calls = expected_simulated_calls(case_id, repetition, variant)
    require(row["evidence"]["simulated_application_calls"] == expected_calls, "E_CALL_COUNT", f"{case_id} application call count drift")
    require(row["state"]["simulated_application_calls"] == expected_calls, "E_CALL_STATE", f"{case_id} state call count drift")
    require(row["evidence"]["simulated_processing_events"] == expected_calls, "E_PROCESS_COUNT", f"{case_id} double process count drift")
    require(row["evidence"]["real_provider_calls"] == 0, "E_REAL_PROVIDER", f"{case_id} real provider evidence claimed")
    require(row["evidence"]["provider_evidence_sha256"] is None, "E_PROVIDER_PROVENANCE", f"{case_id} simulator trace used as provider evidence")
    require(row["counts_toward_experiment"] is False and row["experimental_run_row"] is False, "E_EXPERIMENT_DENOMINATOR", f"{case_id} offline row counted as experiment")
    require(row["evidence"]["simulator_trace_sha256"] == sha256_value(row["event_trace"]), "E_TRACE_HASH", f"{case_id} trace hash drift")
    require(row["evidence"]["emitted_outputs"] == 0 and row["state"]["emitted_outputs"] == 0, "E_OUTPUT", f"{case_id} emitted output")
    global_ids = {f"X{index:02d}" for index in range(1, 9)}
    require(global_ids.issubset(row["effective_invariant_ids"]), "E_GLOBAL_UNION", f"{case_id} lacks global invariant union")
    require(row["explicit_invariant_ids"] == case["invariant_ids"], "E_CASE_INVARIANT", f"{case_id} explicit invariant drift")
    expected_branch = ["S10", "S11", "S12"] if case_id == "S12" and classification == "CONFORMING_OBSERVED" else []
    if expected_branch:
        require(set(expected_branch).issubset(row["effective_invariant_ids"]), "E_S12_INVARIANTS", "S12 success lacks full signing invariants")
    require(row["branch_invariant_ids"] == expected_branch, "E_BRANCH_INVARIANT", f"{case_id} branch invariant drift")
    expected_effective = sorted(global_ids | set(case["invariant_ids"]) | set(expected_branch))
    require(row["effective_invariant_ids"] == expected_effective, "E_INVARIANT_CLOSURE", f"{case_id} invariant closure drift")

    if case["evidence_locus"] == "CLIENT_CONFORMANCE_DOUBLE":
        require(row["row_kind"] == "CLIENT_CONFORMANCE_OBSERVATION", "E_LEDGER_KIND", f"{case_id} client row kind drift")
        require(row["case"]["actual_evidence_origin"] == "OFFLINE_CLIENT_CONFORMANCE_DOUBLE", "E_LEDGER_ORIGIN", f"{case_id} client origin drift")
        require(row["case_classification"] == classification and row["simulated_classification"] is None, "E_LEDGER_CLASS", f"{case_id} client classification ledger drift")
    else:
        require(row["row_kind"] == "MODEL_SCENARIO", "E_LEDGER_KIND", f"{case_id} model row kind drift")
        require(row["case"]["actual_evidence_origin"] == "OFFLINE_MODEL_SCENARIO", "E_LEDGER_ORIGIN", f"{case_id} model origin drift")
        require(row["case_classification"] is None and row["simulated_classification"] == classification, "E_LEDGER_CLASS", f"{case_id} model classification ledger drift")

    if case_id == "M04":
        if repetition % 2:
            require("SPANNER_EXACT_STRONG_LOOKUP" in names, "E_UNKNOWN_RESOLUTION", "M04 exact-record branch missing")
        else:
            require(all(name in names for name in ("SPANNER_BARE_ABSENT_STRONG_READ", "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION", "SPANNER_CONFIRMING_STRONG_READ")), "E_UNKNOWN_FENCE", "M04 fence branch incomplete")
    if case_id == "S04":
        if repetition % 2:
            require("ETCD_EXACT_LINEARIZABLE_LOOKUP" in names, "E_UNKNOWN_RESOLUTION", "S04 exact-record branch missing")
        else:
            require(all(name in names for name in ("ETCD_BARE_ABSENT_LINEARIZABLE_READ", "ETCD_SAME_KEY_ABSENT_TO_TERMINAL_FENCE_CAS", "ETCD_CONFIRMING_LINEARIZABLE_READ")), "E_UNKNOWN_FENCE", "S04 fence branch incomplete")
    if case_id in {"M12", "M13", "S13", "S14"}:
        require(all(name in names for name in ("EPHEMERAL_WORKER_DESTROYED", "NEW_WORKER_CONSTRUCTED_FROM_DURABLE_IMAGE", "RESTART_NO_RESIGN_CONFIRMED")), "E_RESTART", f"{case_id} did not rebuild worker from durable image")
        restart_index = names.index("WORKER_RESTARTED")
        require(not any(name.endswith("_DOUBLE_CALL") for name in names[restart_index + 1 :]), "E_RESTART_RESIGN", f"{case_id} re-signed after restart")
    if case_id == "M14":
        require(names.count("KMS_DOUBLE_CALL") == 1 and row["state"]["receipt"] == "SIGNATURE_RECEIPT_COMMITTED", "E_WORKER_CAS", "M14 winner/loser semantics drift")
    if case_id == "M15":
        require(row["state"]["challenge_consumptions"] == 1, "E_RECONSUME", "M15 re-consumed challenge")
    if case_id == "S12":
        if repetition % 2:
            require(all(token in tokens for token in ("SUCCESS_BRANCH_EXACT_MESSAGE_AND_PIN", "SUCCESS_BRANCH_OFFLINE_VERIFY", "SUCCESS_BRANCH_DURABLE_RECEIPT")), "E_S12_SUCCESS", "S12 success evidence incomplete")
            require(row["state"]["receipt"] == "SIGNATURE_RECEIPT_COMMITTED", "E_S12_RECEIPT", "S12 success lacks receipt")
        else:
            require(all(token in tokens for token in ("FAIL_BRANCH_ZERO_ACCEPTED_RECEIPT", "FAIL_BRANCH_ZERO_OUTPUT")), "E_S12_FAIL", "S12 fail evidence incomplete")
            require(row["state"]["receipt"] == "NONE", "E_S12_RECEIPT", "S12 fail branch accepted receipt")


def independent_oracle_bundle(
    rows: list[dict[str, Any]], contract: dict[str, Any], config_sha: str
) -> None:
    schedule = independent_schedule(contract, config_sha)
    require(len(rows) == len(schedule) == 1020, "E_ROW_COUNT", "offline row count drift")
    index = {
        (track["track_id"], case["case_id"]): (track, case)
        for track in contract["tracks"]
        for case in track["cases"]
    }
    run_keys: set[tuple[str, str, int]] = set()
    run_ids: set[str] = set()
    namespaces: set[str] = set()
    case_counts: dict[tuple[str, str], int] = {}
    for row, expected in zip(rows, schedule, strict=True):
        key = (expected["track_id"], expected["case_id"], expected["repetition_index"])
        require(key not in run_keys, "E_DUPLICATE_RUN_KEY", f"duplicate run key {key}")
        run_keys.add(key)
        require(expected["simulation_run_id"] not in run_ids, "E_DUPLICATE_RUN_ID", "duplicate simulation run id")
        run_ids.add(expected["simulation_run_id"])
        require(expected["namespace_id"] not in namespaces, "E_NAMESPACE_REUSE", "namespace reused")
        namespaces.add(expected["namespace_id"])
        case_key = (expected["track_id"], expected["case_id"])
        case_counts[case_key] = case_counts.get(case_key, 0) + 1
        track, case = index[case_key]
        independent_oracle_row(row, expected, track, case)
    require(all(count == 30 for count in case_counts.values()) and len(case_counts) == 34, "E_CASE_BALANCE", "case repetition balance drift")
    require(all(row["schedule"]["track_id"] == MANAGED_TRACK for row in rows[:480]), "E_TRACK_INTERLEAVE", "managed block interleaved")
    require(all(row["schedule"]["track_id"] == SELF_HOSTED_TRACK for row in rows[480:]), "E_TRACK_INTERLEAVE", "self-hosted block interleaved")
    require(sum(row["row_kind"] == "CLIENT_CONFORMANCE_OBSERVATION" for row in rows) == 420, "E_CLIENT_LEDGER_COUNT", "client ledger count drift")
    require(sum(row["row_kind"] == "MODEL_SCENARIO" for row in rows) == 600, "E_MODEL_LEDGER_COUNT", "model ledger count drift")


def load_source_module(path: Path) -> tuple[Any, str]:
    name = "_ab_reference_provider_fault_injection_offline_harness_v1_owned"
    require(name not in sys.modules, "E_MODULE_OCCUPIED", "owned module name occupied")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "E_MODULE_SPEC", "cannot create source module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(name, None)
        fail("E_MODULE_EXEC", f"cannot execute pure harness source: {exc}")
    return module, name


def validate_source_ast(path: Path) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        fail("E_SOURCE_PARSE", f"cannot parse harness source: {exc}")
    allowed_imports = {
        "__future__", "base64", "dataclasses", "functools", "hashlib", "json", "typing"
    }
    forbidden_calls = {
        "__import__", "breakpoint", "compile", "eval", "exec", "input", "open", "print"
    }
    forbidden_attributes = {
        "Popen", "call", "connect", "getenv", "open", "popen", "read_bytes", "read_text",
        "request", "run", "sleep", "system", "time", "unlink", "urandom", "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".", 1)[0] in allowed_imports, "E_SOURCE_IMPORT", f"forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            require((node.module or "").split(".", 1)[0] in allowed_imports, "E_SOURCE_IMPORT", f"forbidden import-from {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls, "E_SOURCE_CALL", f"forbidden call {node.func.id}")
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attributes, "E_SOURCE_CALL", f"forbidden attribute call {node.func.attr}")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            fail("E_SOURCE_MUTATION", "harness source may not declare global/nonlocal mutation")
        elif isinstance(node, ast.Constant) and type(node.value) is str:
            lowered = node.value.lower()
            require("https://" not in lowered and "http://" not in lowered, "E_SOURCE_ENDPOINT", "harness embeds a network endpoint")


def validate_known_answer_tests(module: Any) -> None:
    message = bytes.fromhex(MESSAGE_HEX)
    public_key = bytes.fromhex(PUBLIC_KEY_HEX)
    signature = bytes.fromhex(SIGNATURE_HEX)
    require(len(message) == 137 and sha256_bytes(message) == MESSAGE_SHA256, "E_MESSAGE_KAT", "message KAT drift")
    require(module.MESSAGE == message and module.MESSAGE_SHA256 == MESSAGE_SHA256, "E_MESSAGE_KAT", "source message KAT drift")
    require(module.PUBLIC_KEY == public_key and module.PUBLIC_KEY_HEX == PUBLIC_KEY_HEX, "E_PUBLIC_KEY_KAT", "public-key KAT drift")
    require(module.TEST_SIGNATURE == signature, "E_SIGNATURE_KAT", "signature KAT drift")
    require(module.ed25519_verify(signature, message, public_key) is True, "E_SIGNATURE_VERIFY", "valid signature rejected")
    mutated_signature = bytes([signature[0] ^ 1]) + signature[1:]
    require(module.ed25519_verify(mutated_signature, message, public_key) is False, "E_SIGNATURE_VERIFY", "invalid signature accepted")
    noncanonical_x_zero_sign_one = bytes.fromhex(
        "0100000000000000000000000000000000000000000000000000000000000080"
        "7c0cedf931aacc41330ef0c9585ffe722a49f8ba19f66277575acf5f9210c605"
    )
    require(
        module.ed25519_verify(noncanonical_x_zero_sign_one, message, public_key) is False,
        "E_SIGNATURE_CANONICAL",
        "noncanonical Ed25519 x=0/sign=1 point accepted",
    )
    require(module.crc32c(b"123456789") == 0xE3069283, "E_CRC32C_KAT", "CRC32C KAT drift")
    require(module.crc32c(message) != module.crc32c(__import__("base64").b64encode(message)), "E_CRC_DOMAIN", "raw/Base64 CRC domains collapsed")


def validate_evidence_compiler_known_answers(configuration: dict[str, Any]) -> None:
    managed = configuration["profiles"]["managed"]
    hosted = configuration["profiles"]["self_hosted"]
    require(
        managed["exact_key_version_resource"] == MANAGED_EXACT_KEY_VERSION_RESOURCE
        and managed["key_version"] == MANAGED_KEY_VERSION
        and managed["effective_isolation"] == MANAGED_ISOLATION
        and managed["protection_level"] == MANAGED_PROTECTION_LEVEL,
        "E_EVIDENCE_CONFIGURATION",
        "managed evidence configuration drift",
    )
    require(
        hosted["key_version"] == SELF_HOSTED_KEY_VERSION,
        "E_EVIDENCE_CONFIGURATION",
        "self-hosted evidence configuration drift",
    )
    message = bytes.fromhex(MESSAGE_HEX)
    require(
        crc32c_reference(b"123456789") == 0xE3069283,
        "E_EVIDENCE_CRC32C_KAT",
        "independent CRC32C KAT drift",
    )
    require(
        crc32c_reference(message) != crc32c_reference(base64.b64encode(message)),
        "E_EVIDENCE_CRC32C_DOMAIN",
        "independent raw/Base64 CRC domains collapsed",
    )
    require(
        sha256_bytes(bytes.fromhex(SIGNATURE_HEX))
        == "bd95d9e321630bb658ea95cd3112ddbd63337a0e6f597ce97d4c4f809ac3f02f",
        "E_EVIDENCE_SIGNATURE_KAT",
        "test-signature SHA-256 KAT drift",
    )

    def compiled(case_id: str, repetition: int) -> EvidenceExpectation:
        case = {"case_id": case_id, "injection_cut": "NONE"}
        variant = expected_variant(case, repetition)
        classification = expected_classification(case_id, repetition)
        return compile_evidence_expectation(case_id, repetition, variant, classification)

    kats = {
        "M00.request": compiled("M00", 1).request_sha256,
        "M00.response": compiled("M00", 1).response_sha256,
        "M00.message": compiled("M00", 1).message_sha256,
        "M00.message-bytes": compiled("M00", 1).message_bytes,
        "M00.public-key": compiled("M00", 1).public_key_sha256,
        "M05.digest-arm-request": compiled("M05", 1).request_sha256,
        "M06.mutated-frame-request": compiled("M06", 1).request_sha256,
        "M07.bad-crc-request": compiled("M07", 1).request_sha256,
        "M07.provider-error-response": compiled("M07", 1).response_sha256,
        "M07.false-flag-response": compiled("M07", 2).response_sha256,
        "M08.omit-request": compiled("M08", 1).request_sha256,
        "M08.zero-request": compiled("M08", 2).request_sha256,
        "M08.parent-request": compiled("M08", 3).request_sha256,
        "M08.leading-zero-request": compiled("M08", 4).request_sha256,
        "M08.response-name": compiled("M08", 5).response_sha256,
        "M09.response": compiled("M09", 1).response_sha256,
        "M10.response": compiled("M10", 1).response_sha256,
        "M11.response": compiled("M11", 1).response_sha256,
        "S00.request": compiled("S00", 1).request_sha256,
        "S00.response": compiled("S00", 1).response_sha256,
        "S16.request": compiled("S16", 1).request_sha256,
        "S17.prefix-response": compiled("S17", 1).response_sha256,
        "S17.pin-response": compiled("S17", 2).response_sha256,
        "S17.pin-public-key": compiled("S17", 2).public_key_sha256,
        "S17.message-request": compiled("S17", 3).request_sha256,
    }
    require(kats == {
        "M00.request": "3cb0ee063c70d01e02c5bafe361167346a5b1dbc6773a07f77223a480b5471db",
        "M00.response": "faf1a87d83b1bf40dc2d59f1954f32515fe3739819f4db6845edada4742213a1",
        "M00.message": MESSAGE_SHA256,
        "M00.message-bytes": 137,
        "M00.public-key": "56475aa75463474c0285df5dbf2bcab73da651358839e9b77481b2eab107708c",
        "M05.digest-arm-request": "89a8203450bcef9a1ac1c226e00d219694d337b14cb173fc6e53b9b2e66b4e4c",
        "M06.mutated-frame-request": "2c76881ff3be55611810f41c20221725ffbd986ce38ab8413cd58ead2ddc07c0",
        "M07.bad-crc-request": "9966ebed6752bf1dcad3ce6bd416b8b8553fd599fb7ad7069b593563fcbeff61",
        "M07.provider-error-response": "db85077eab05ecf19bad65644432efb0b404a8de17b6eb88e14423460b6ed161",
        "M07.false-flag-response": "9eee7f41b811fda68a31f3e546448dd9cedef0b4593b21faba9b16f44de4748c",
        "M08.omit-request": "a95bcfffbc08bf5cc7958e3b47fffde74a6c850f9623bb6981bb9eaf432a9fdd",
        "M08.zero-request": "09d5154474d0122c846bf672319455d3fd495a5f87a396fb885d0f8c5832dfe7",
        "M08.parent-request": "ed85b20c46c1994ecf5dabd5ae7aa92c3453afa25ef2f9336aa263278b853aea",
        "M08.leading-zero-request": "5a165c7e787f565a8ba8e49da5b6f8349a2d8e9d9d418023159d3bd7355ea875",
        "M08.response-name": "da03e2347fc92982170a29d7175eb5a22cef237f757bbc5d4423c5090a1543c1",
        "M09.response": "a18dfa557579bb6854a7098e9a4c4ca933999541453e0dddc63ea2220e2ab0e3",
        "M10.response": "380bedd5e09f93e238f43ce2a25348982e95e98b8732f7ca962a6b1786a54d2e",
        "M11.response": "9a67138b7c3f94dea30fc7516c3cd83cdcb84950dce3018f30e21366c2f1e04c",
        "S00.request": "d63f32e219067bdc59aefb9ad3e170beb296e7523858ab393c44e035c9bffe4c",
        "S00.response": "ca35537719c43b7e0c89cd4d9e4a3c3aee63488c12f5878b51e20b9567d84fce",
        "S16.request": "293fb344e821fb7859df247f8f1a60b602759cd59accc4a20d840f4d3732b29f",
        "S17.prefix-response": "a11517288cfa8cf5f2b5a49d1a65a253252b54f1d926ecd34a3944d1dd6ff7b0",
        "S17.pin-response": "ca35537719c43b7e0c89cd4d9e4a3c3aee63488c12f5878b51e20b9567d84fce",
        "S17.pin-public-key": "a4c744f25d818ab54a8dc583fa583d4d8d0161555b9bbf7a7c90bd1e47ced039",
        "S17.message-request": "5e6b07764c207e9a3a53ddfb7b1f20f4eff509f440047e30ac812ac682f5ab19",
    }, "E_EVIDENCE_PAYLOAD_KAT", "independent evidence payload KAT drift")


def validate_predecessor(root: Path, manifest: dict[str, Any]) -> None:
    require(manifest["status"] == "REFERENCE_PROVIDER_FAULT_INJECTION_EXPERIMENT_V1_PREREGISTERED_NO_PROVIDER_INVOCATION_NO_PERMIT", "E_PREDECESSOR_STATUS", "predecessor status drift")
    require(manifest["decision"] == "PREREGISTRATION_PASS_EXECUTION_BLOCKED_NO_AUTHORITY_OR_RUN_EVIDENCE", "E_PREDECESSOR_DECISION", "predecessor decision drift")
    require(manifest["next_unit"] == "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_HARNESS_V1_OFFLINE_DOUBLE_IMPLEMENTATION", "E_PREDECESSOR_NEXT", "predecessor next-unit drift")
    require(manifest["boundary"]["provider_called"] is False and manifest["boundary"]["experiment_executed"] is False, "E_PREDECESSOR_BOUNDARY", "predecessor boundary drift")
    for relative, expected in EXPECTED_PREDECESSOR_HASHES.items():
        require(sha256_bytes((root / relative).read_bytes()) == expected, "E_PREDECESSOR_HASH", f"predecessor hash drift: {relative}")


def validate_report_bindings(root: Path) -> None:
    try:
        report_text = (root / REPORT_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail("E_REPORT_LOAD", f"cannot load report: {exc}")
    lines = report_text.splitlines()
    require(lines.count("## Artifact binding") == 1, "E_REPORT_BINDING", "Artifact binding heading drift")
    start = lines.index("## Artifact binding") + 1
    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line:
            section.append(line)
    require(len(section) == len(REPORT_BOUND_PATHS) == 17, "E_REPORT_BINDING", "Artifact binding section cardinality drift")
    expected_lines = []
    for relative in REPORT_BOUND_PATHS:
        try:
            digest = sha256_bytes((root / relative).read_bytes())
        except OSError as exc:
            fail("E_REPORT_BINDING", f"cannot hash report-bound artifact {relative}: {exc}")
        expected_lines.append(f"- `{relative}`: `{digest}`")
    require(section == expected_lines, "E_REPORT_BINDING", "Artifact binding catalog drift")


def _expect_code(code: str, call: Callable[[], None], label: str) -> None:
    try:
        call()
    except PackError as exc:
        require(exc.code == code, "E_NEGATIVE_WRONG_CODE", f"{label}: expected {code}, got {exc.code}")
        return
    fail("E_NEGATIVE_ACCEPTED", f"directed mutation accepted: {label}")


def run_directed_negative_tests(
    module: Any,
    rows: list[dict[str, Any]],
    contract: dict[str, Any],
    configuration: dict[str, Any],
    run_schema: dict[str, Any],
) -> int:
    count = 0
    config_sha = sha256_value(configuration)
    schedule = independent_schedule(contract, config_sha)
    index = {
        (track["track_id"], case["case_id"]): (track, case)
        for track in contract["tracks"]
        for case in track["cases"]
    }
    representatives: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]] = {}
    for row, expected in zip(rows, schedule, strict=True):
        case_id = expected["case_id"]
        if case_id not in representatives:
            track, case = index[(expected["track_id"], case_id)]
            representatives[case_id] = (row, expected, track, case)
    require(len(representatives) == 34, "E_NEGATIVE_COVERAGE", "negative representatives incomplete")

    def require_candidate_reject(mutated_row: dict[str, Any], label: str) -> None:
        try:
            module.validate_run_row(mutated_row, contract, configuration)
        except module.HarnessError:
            return
        fail("E_NEGATIVE_ACCEPTED", f"candidate accepted directed mutation: {label}")

    for case_id, (row, expected, track, case) in representatives.items():
        mutated = copy.deepcopy(row)
        mutated["schedule"]["namespace_id"] = "f" * 64
        _expect_code("E_SCHEDULE_DRIFT", lambda m=mutated, e=expected, t=track, c=case: independent_oracle_row(m, e, t, c), f"{case_id} schedule")
        count += 1

        mutated = copy.deepcopy(row)
        field = "case_classification" if row["case_classification"] is not None else "simulated_classification"
        mutated[field] = "FAIL_CLOSED_REJECTED" if (row[field] != "FAIL_CLOSED_REJECTED") else "CONFORMING_OBSERVED"
        _expect_code("E_CLASSIFICATION", lambda m=mutated, e=expected, t=track, c=case: independent_oracle_row(m, e, t, c), f"{case_id} classification")
        count += 1

        mutated = copy.deepcopy(row)
        mutated["evidence"]["provider_evidence_sha256"] = mutated["evidence"]["simulator_trace_sha256"]
        _expect_code("E_PROVIDER_PROVENANCE", lambda m=mutated, e=expected, t=track, c=case: independent_oracle_row(m, e, t, c), f"{case_id} provenance")
        count += 1

        mutated = copy.deepcopy(row)
        mutated["counts_toward_experiment"] = True
        _expect_code("E_EXPERIMENT_DENOMINATOR", lambda m=mutated, e=expected, t=track, c=case: independent_oracle_row(m, e, t, c), f"{case_id} denominator")
        count += 1

        mutated = copy.deepcopy(row)
        mutated["effective_invariant_ids"].remove("X02")
        _expect_code("E_GLOBAL_UNION", lambda m=mutated, e=expected, t=track, c=case: independent_oracle_row(m, e, t, c), f"{case_id} global union")
        count += 1

        mutated = copy.deepcopy(row)
        mutated["event_trace"].pop(0)
        _expect_code("E_EVENT_SEQUENCE", lambda m=mutated, e=expected, t=track, c=case: independent_oracle_row(m, e, t, c), f"{case_id} event prefix")
        count += 1

        mutated = copy.deepcopy(row)
        mutated["evidence"]["semantic_tokens"].remove(REQUIRED_TOKENS[case_id][0])
        _expect_code("E_REQUIRED_TOKEN", lambda m=mutated, e=expected, t=track, c=case: independent_oracle_row(m, e, t, c), f"{case_id} semantic token")
        count += 1

        mutated = copy.deepcopy(row)
        mutated["evidence"]["real_provider_calls"] = 1
        _expect_code("E_REAL_PROVIDER", lambda m=mutated, e=expected, t=track, c=case: independent_oracle_row(m, e, t, c), f"{case_id} real provider")
        count += 1

    # The row schema retains infrastructure/boundary rows but refuses to classify them.
    client_row = next(copy.deepcopy(row) for row in rows if row["row_kind"] == "CLIENT_CONFORMANCE_OBSERVATION")
    client_row["row_outcome"] = "OFFLINE_INFRASTRUCTURE_FAILURE_RETAINED"
    client_row["case_classification"] = None
    client_row["simulated_classification"] = None
    client_row["classification_scope"] = "NOT_EVALUABLE_RETAINED"
    client_row["oracle_classification_allowed"] = False
    client_row["counts_toward_harness_conformance"] = False
    module.validate_run_row(client_row, contract, configuration)
    validate_json_schema(client_row, run_schema)
    representative = representatives[client_row["schedule"]["case_id"]]
    _expect_code(
        "E_CLASSIFICATION",
        lambda: independent_oracle_row(client_row, representative[1], representative[2], representative[3]),
        "retained infrastructure row cannot pass case oracle",
    )
    count += 1

    boundary_row = copy.deepcopy(client_row)
    boundary_row["row_outcome"] = "OFFLINE_BOUNDARY_BREACH_ABORT_RETAINED"
    module.validate_run_row(boundary_row, contract, configuration)
    validate_json_schema(boundary_row, run_schema)

    missing = rows[:-1]
    _expect_code("E_ROW_COUNT", lambda: independent_oracle_bundle(missing, contract, config_sha), "missing row")
    count += 1
    duplicate = copy.deepcopy(rows)
    duplicate[-1] = copy.deepcopy(duplicate[0])
    _expect_code("E_SCHEDULE_DRIFT", lambda: independent_oracle_bundle(duplicate, contract, config_sha), "duplicate/substituted row")
    count += 1
    interleaved = copy.deepcopy(rows)
    interleaved[0], interleaved[480] = interleaved[480], interleaved[0]
    _expect_code("E_SCHEDULE_DRIFT", lambda: independent_oracle_bundle(interleaved, contract, config_sha), "track interleave")
    count += 1

    # S12 branch-specific evidence and restart/fence P0s.
    s12_success = next(
        (row, expected, track, case)
        for row, expected, track, case in representatives.values()
        if case["case_id"] == "S12"
    )
    mutated = copy.deepcopy(s12_success[0])
    mutated["effective_invariant_ids"].remove("S10")
    _expect_code("E_S12_INVARIANTS", lambda: independent_oracle_row(mutated, *s12_success[1:]), "S12 full validation invariants")
    count += 1

    m12 = representatives["M12"]
    mutated = copy.deepcopy(m12[0])
    restart_index = next(index for index, event in enumerate(mutated["event_trace"]) if event["name"] == "WORKER_RESTARTED")
    repeated_call = copy.deepcopy(next(event for event in mutated["event_trace"] if event["name"] == "KMS_DOUBLE_CALL"))
    mutated["event_trace"].insert(restart_index + 1, repeated_call)
    for sequence, event in enumerate(mutated["event_trace"], start=1):
        event["sequence"] = sequence
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_CALL_CARDINALITY", lambda: independent_oracle_row(mutated, *m12[1:]), "restart re-sign")
    count += 1

    m04 = next(value for value in (
        (row, expected, *index[(expected["track_id"], expected["case_id"])])
        for row, expected in zip(rows, schedule, strict=True)
    ) if value[1]["case_id"] == "M04" and value[1]["repetition_index"] % 2 == 0)
    mutated = copy.deepcopy(m04[0])
    fence_index = next(index for index, event in enumerate(mutated["event_trace"]) if event["name"] == "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION")
    confirm_index = next(index for index, event in enumerate(mutated["event_trace"]) if event["name"] == "SPANNER_CONFIRMING_STRONG_READ")
    mutated["event_trace"][fence_index], mutated["event_trace"][confirm_index] = mutated["event_trace"][confirm_index], mutated["event_trace"][fence_index]
    for sequence, event in enumerate(mutated["event_trace"], start=1):
        event["sequence"] = sequence
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_UNKNOWN_FENCE", lambda: independent_oracle_row(mutated, *m04[1:]), "terminal fence read/CAS order")
    count += 1

    # Prepared-attempt and receipt transitions must reject misuse before processing.
    run_id = "1" * 64
    assignment_sha = "2" * 64

    def prepared_kms_state() -> tuple[Any, dict[str, Any], dict[str, Any]]:
        state = module.SimulationState(outbox="SIGN_PENDING")
        state.event(
            "ASSIGNMENT_HASH_SEALED",
            assignment_sha256=assignment_sha,
            simulation_run_id=run_id,
        )
        request = module._kms_request(configuration)
        module._prepare_attempt(
            state,
            "KMS",
            module.sha256_value(request),
            configuration["profiles"]["managed"]["key_version"],
        )
        return state, request, module._kms_response(configuration, request)

    state, request, response = prepared_kms_state()
    mismatched = copy.deepcopy(request)
    mismatched["data_crc32c"] ^= 1
    try:
        module._double_call(state, "KMS", mismatched, response)
    except module.HarnessError:
        require(state.simulated_processing_events == 0, "E_NEGATIVE_STATE", "mismatched request processed before rejection")
        count += 1
    else:
        fail("E_NEGATIVE_ACCEPTED", "prepared request A allowed call B")

    state, request, response = prepared_kms_state()
    module._double_call(state, "KMS", request, response)
    try:
        module._double_call(state, "KMS", request, response)
    except module.HarnessError:
        require(state.simulated_application_calls == state.simulated_processing_events == 1, "E_NEGATIVE_STATE", "second call mutated counters")
        count += 1
    else:
        fail("E_NEGATIVE_ACCEPTED", "prepared marker allowed a second call")

    state, request, response = prepared_kms_state()
    response["verified_data_crc32c"] = False
    observed = module._double_call(state, "KMS", request, response)
    try:
        module._mark_response_validated(
            state,
            "KMS",
            configuration,
            request,
            observed,
        )
    except module.HarnessError:
        require(
            state.validated_response_sha256 == ZERO_SHA256
            and state.validation_binding_sha256 == ZERO_SHA256,
            "E_NEGATIVE_STATE",
            "invalid response left validation state",
        )
        count += 1
    else:
        fail("E_NEGATIVE_ACCEPTED", "invalid KMS response marked fully validated")

    state, _, _ = prepared_kms_state()
    try:
        module._commit_receipt(state, "KMS")
    except module.HarnessError:
        count += 1
    else:
        fail("E_NEGATIVE_ACCEPTED", "zero-call receipt commit accepted")

    state, request, response = prepared_kms_state()
    state.prepared_key_version += 1
    try:
        module._double_call(state, "KMS", request, response)
    except module.HarnessError:
        require(state.simulated_processing_events == 0, "E_NEGATIVE_STATE", "tampered prepared record reached processing")
        count += 1
    else:
        fail("E_NEGATIVE_ACCEPTED", "tampered prepared record accepted")

    transit_request = module._transit_request(configuration)
    transit_response = module._transit_response(configuration)
    version = configuration["profiles"]["self_hosted"]["key_version"]
    for label, bad_response in (
        ("missing-v", {"signature": transit_response["signature"].replace(f"vault:v{version}:", f"vault:{version}:", 1)}),
        ("leading-zero", {"signature": transit_response["signature"].replace(f"vault:v{version}:", f"vault:v0{version}:", 1)}),
    ):
        require(
            module._validate_transit(configuration, transit_request, bad_response) is False,
            "E_TRANSIT_CANONICAL",
            f"Transit accepted noncanonical version prefix: {label}",
        )
        count += 1
    for label, mutate in (
        ("omitted-version", lambda value: value.pop("key_version")),
        ("batch", lambda value: value.__setitem__("batch", True)),
        ("context", lambda value: value.__setitem__("context", "unexpected")),
        ("prehashed", lambda value: value.__setitem__("prehashed", True)),
    ):
        bad_request = copy.deepcopy(transit_request)
        mutate(bad_request)
        require(
            module._validate_transit(configuration, bad_request, transit_response) is False,
            "E_TRANSIT_REQUEST_SHAPE",
            f"Transit accepted invalid request shape: {label}",
        )
        count += 1

    cas_state = module.SimulationState()
    cas_state.event(
        "ASSIGNMENT_HASH_SEALED",
        assignment_sha256=assignment_sha,
        simulation_run_id=run_id,
    )
    cas_double = module.ExactKeyCASDouble.for_run(run_id)
    operation_record = cas_double.operation_record(run_id, MANAGED_KEY_VERSION)
    cas_double.stage_delayed_commit(operation_record)
    try:
        cas_double.cas_absent_to_terminal_fence(
            cas_state,
            "TEST_TERMINAL_FENCE",
            kind="KMS",
            consistency="LINEARIZABLE",
            operation_id=run_id,
            exact_key_version=MANAGED_KEY_VERSION,
        )
    except module.HarnessError:
        count += 1
    else:
        fail("E_NEGATIVE_ACCEPTED", "terminal fence CAS accepted without a bare-absent read")

    cas_double.exact_read(
        cas_state,
        "TEST_BARE_ABSENT_READ",
        consistency="LINEARIZABLE",
    )
    cas_double.cas_absent_to_terminal_fence(
        cas_state,
        "TEST_TERMINAL_FENCE",
        kind="KMS",
        consistency="LINEARIZABLE",
        operation_id=run_id,
        exact_key_version=MANAGED_KEY_VERSION,
    )
    try:
        cas_double.commit_now(operation_record)
    except module.HarnessError:
        count += 1
    else:
        fail("E_NEGATIVE_ACCEPTED", "delayed exact operation overwrote terminal fence")

    witness_state = module.SimulationState()
    witness_state.event(
        "ASSIGNMENT_HASH_SEALED",
        assignment_sha256=assignment_sha,
        simulation_run_id=run_id,
    )
    witness_ledger = module.ExternalWitnessLedger(
        f"logical-lineage-{run_id[:24]}"
    )
    witness_candidate = module._witness_candidate(witness_state, witness_ledger)
    applied = witness_ledger.compare_and_swap(
        witness_state,
        witness_candidate,
        caller_actor_domain="ETCD_RESTORE_ACTOR_FORBIDDEN",
        expected_previous_record_sha256=ZERO_SHA256,
        expected_generation=0,
        event_name="TEST_WITNESS_ACTOR_REJECTED",
    )
    require(
        applied is False and witness_ledger.current_record is None,
        "E_WITNESS_CAPABILITY",
        "restore actor mutated external witness ledger",
    )
    count += 1

    invalid_correlation = module.S12ExecutionCorrelation(
        target_node="node-active-a",
        route_node="node-active-a",
        executing_node="node-active-a",
        executing_ha_role="PERFORMANCE_STANDBY_ACTIVE",
        cluster_id="cluster-test",
        request_id="request-test",
        redirect_node="node-active-a",
        forwarded_by_node="node-active-a",
        audit_record_sha256="a" * 64,
        wire_attempt_sha256="b" * 64,
        redirect_forward_audit_bound=True,
    )
    try:
        invalid_correlation.validate(success=True)
    except module.HarnessError:
        count += 1
    else:
        fail("E_NEGATIVE_ACCEPTED", "S12 target/route/executor alias accepted")

    # Nested event provenance and invariant overclaim must be independently rejected.
    m00 = representatives["M00"]
    mutated = copy.deepcopy(m00[0])
    call_event = next(event for event in mutated["event_trace"] if event["name"] == "KMS_DOUBLE_CALL")
    call_event["details"]["provider_evidence_sha256"] = "f" * 64
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_EVENT_DETAILS", lambda: independent_oracle_row(mutated, *m00[1:]), "nested provider evidence")
    count += 1

    mutated = copy.deepcopy(m00[0])
    mutated["effective_invariant_ids"].append("X99")
    mutated["effective_invariant_ids"].sort()
    _expect_code("E_INVARIANT_CLOSURE", lambda: independent_oracle_row(mutated, *m00[1:]), "unknown invariant overclaim")
    count += 1

    # Removing the raw call event cannot be hidden by retained counters.
    mutated = copy.deepcopy(m00[0])
    mutated["event_trace"] = [event for event in mutated["event_trace"] if event["name"] != "KMS_DOUBLE_CALL"]
    for sequence, event in enumerate(mutated["event_trace"], start=1):
        event["sequence"] = sequence
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_CALL_CONSUMPTION", lambda: independent_oracle_row(mutated, *m00[1:]), "removed call event")
    count += 1

    s11 = representatives["S11"]
    for field_name in sorted(WITNESS_FIELDS):
        mutated = copy.deepcopy(s11[0])
        witness_event = next(
            event for event in mutated["event_trace"]
            if event["name"] == "EXTERNAL_WITNESS_EXACT_CAS_COMMITTED"
        )
        record = witness_event["details"]["witness_record"]
        original = record[field_name]
        if type(original) is bool:
            record[field_name] = not original
        elif type(original) is int:
            record[field_name] = original + 17
        elif field_name.endswith("sha256"):
            record[field_name] = "e" * 64
        else:
            record[field_name] = original + "-mutated"
        witness_event["details"]["witness_record_sha256"] = sha256_value(record)
        if field_name == "authority_id":
            witness_event["details"]["witness_key"] = _framed_hash(
                f"{WITNESS_DOMAIN}/exact-key",
                record["authority_id"],
                witness_event["details"]["logical_cluster_lineage_id"],
            )
        mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
        _expect_code(
            "E_WITNESS_BINDINGS",
            lambda m=mutated: independent_oracle_row(m, *s11[1:]),
            f"S11 witness field {field_name}",
        )
        count += 1

    s12_success_row = s12_success
    mutated = copy.deepcopy(s12_success_row[0])
    route = next(event for event in mutated["event_trace"] if event["name"] == "OPENBAO_ROUTE_EXECUTION_EVIDENCE")
    route["details"]["executing_node"] = route["details"]["route_node"]
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_S12_CORRELATION", lambda: independent_oracle_row(mutated, *s12_success_row[1:]), "S12 route equals executor")
    count += 1

    mutated = copy.deepcopy(s12_success_row[0])
    route = next(event for event in mutated["event_trace"] if event["name"] == "OPENBAO_ROUTE_EXECUTION_EVIDENCE")
    route["details"].pop("request_id")
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_EVENT_DETAILS", lambda: independent_oracle_row(mutated, *s12_success_row[1:]), "S12 missing request id")
    count += 1

    mutated = copy.deepcopy(s12_success_row[0])
    route = next(event for event in mutated["event_trace"] if event["name"] == "OPENBAO_ROUTE_EXECUTION_EVIDENCE")
    route["details"]["redirect_forward_audit_bound"] = False
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_S12_CORRELATION", lambda: independent_oracle_row(mutated, *s12_success_row[1:]), "S12 false audit binding")
    count += 1

    s12_failure = next(
        (row, expected, *index[(expected["track_id"], expected["case_id"])])
        for row, expected in zip(rows, schedule, strict=True)
        if expected["case_id"] == "S12" and expected["repetition_index"] % 2 == 0
    )
    mutated = copy.deepcopy(s12_failure[0])
    route = next(event for event in mutated["event_trace"] if event["name"] == "OPENBAO_ROUTE_EXECUTION_EVIDENCE")
    route["details"]["executing_node"] = "node-standby-b"
    route["details"]["executing_ha_role"] = "PERFORMANCE_STANDBY_ACTIVE"
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_S12_CORRELATION", lambda: independent_oracle_row(mutated, *s12_failure[1:]), "S12 failure preclaims executor")
    count += 1

    mutated = copy.deepcopy(m12[0])
    processing_index = next(index for index, event in enumerate(mutated["event_trace"]) if event["name"] == "KMS_DOUBLE_PROCESSING_COMPLETED")
    trigger_index = next(index for index, event in enumerate(mutated["event_trace"]) if event["name"] == "ONE_SHOT_FAULT_TRIGGERED")
    mutated["event_trace"][processing_index], mutated["event_trace"][trigger_index] = mutated["event_trace"][trigger_index], mutated["event_trace"][processing_index]
    for sequence, event in enumerate(mutated["event_trace"], start=1):
        event["sequence"] = sequence
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_FAULT_CUT", lambda: independent_oracle_row(mutated, *m12[1:]), "M12 early response-drop trigger")
    count += 1

    mutated = copy.deepcopy(m12[0])
    trigger_index = next(index for index, event in enumerate(mutated["event_trace"]) if event["name"] == "ONE_SHOT_FAULT_TRIGGERED")
    mutated["event_trace"].insert(trigger_index + 1, copy.deepcopy(mutated["event_trace"][trigger_index]))
    for sequence, event in enumerate(mutated["event_trace"], start=1):
        event["sequence"] = sequence
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_FAULT_CARDINALITY", lambda: independent_oracle_row(mutated, *m12[1:]), "M12 double trigger")
    count += 1

    mutated = copy.deepcopy(m12[0])
    durable = next(event for event in mutated["event_trace"] if event["name"] == "DURABLE_IMAGE_SERIALIZED")
    durable["details"]["durable_image"]["attempt"] = "CONSUMED"
    durable["details"]["image_sha256"] = sha256_value(durable["details"]["durable_image"])
    restarted = next(event for event in mutated["event_trace"] if event["name"] == "WORKER_RESTARTED")
    restarted["details"]["durable_attempt_state"] = "CONSUMED"
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_RESTART_IMAGE", lambda: independent_oracle_row(mutated, *m12[1:]), "corrupt durable restart image")
    count += 1

    mutated = copy.deepcopy(m00[0])
    mutated["evidence"]["post_state_sha256"] = ZERO_SHA256
    _expect_code("E_POST_STATE_HASH", lambda: independent_oracle_row(mutated, *m00[1:]), "false post-state hash")
    count += 1

    mutated = copy.deepcopy(m00[0])
    call_event = next(event for event in mutated["event_trace"] if event["name"] == "KMS_DOUBLE_CALL")
    call_event["details"]["call_binding_sha256"] = "f" * 64
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_CALL_CONSUMPTION", lambda: independent_oracle_row(mutated, *m00[1:]), "false call binding")
    count += 1

    mutated = copy.deepcopy(m00[0])
    receipt_event = next(event for event in mutated["event_trace"] if event["name"] == "KMS_SIGNATURE_RECEIPT_COMMITTED")
    receipt_event["details"]["receipt_binding_sha256"] = "f" * 64
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    _expect_code("E_RECEIPT_BINDING", lambda: independent_oracle_row(mutated, *m00[1:]), "false receipt binding")
    count += 1

    # Every integrity-review bypass is pinned as one mutation rejected by both implementations.
    mutated = copy.deepcopy(m00[0])
    call_event = next(event for event in mutated["event_trace"] if event["name"] == "KMS_DOUBLE_CALL")
    call_event["details"]["operation_id"] = "f" * 64
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    require_candidate_reject(mutated, "call operation/prepared binding")
    _expect_code(
        "E_CALL_PREPARED_BINDING",
        lambda: independent_oracle_row(mutated, *m00[1:]),
        "call operation/prepared binding",
    )
    count += 1

    mutated = copy.deepcopy(m00[0])
    validation_index = next(
        index for index, event in enumerate(mutated["event_trace"])
        if event["name"] == "KMS_RESPONSE_FULLY_VALIDATED"
    )
    processing_index = next(
        index for index, event in enumerate(mutated["event_trace"])
        if event["name"] == "KMS_DOUBLE_PROCESSING_COMPLETED"
    )
    mutated["event_trace"][validation_index], mutated["event_trace"][processing_index] = (
        mutated["event_trace"][processing_index],
        mutated["event_trace"][validation_index],
    )
    for sequence, event in enumerate(mutated["event_trace"], start=1):
        event["sequence"] = sequence
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    require_candidate_reject(mutated, "validation before processing/delivery")
    _expect_code(
        "E_RESPONSE_ORDER",
        lambda: independent_oracle_row(mutated, *m00[1:]),
        "validation before processing/delivery",
    )
    count += 1

    mutated = copy.deepcopy(m00[0])
    mutated["event_trace"] = [
        event for event in mutated["event_trace"]
        if event["name"] != "KMS_DOUBLE_RESPONSE_OBSERVED"
    ]
    for sequence, event in enumerate(mutated["event_trace"], start=1):
        event["sequence"] = sequence
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    require_candidate_reject(mutated, "missing observed response")
    _expect_code(
        "E_RESPONSE_CARDINALITY",
        lambda: independent_oracle_row(mutated, *m00[1:]),
        "missing observed response",
    )
    count += 1

    mutated = copy.deepcopy(s12_failure[0])
    unavailable = next(
        event for event in mutated["event_trace"]
        if event["name"] == "OPENBAO_STANDBY_TAKEOVER_UNAVAILABLE_FAIL_CLOSED"
    )
    unavailable["details"]["accepted_receipts"] = 1
    unavailable["details"]["emitted_outputs"] = 1
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    require_candidate_reject(mutated, "S12 failure accepted work counters")
    _expect_code(
        "E_S12_FAIL",
        lambda: independent_oracle_row(mutated, *s12_failure[1:]),
        "S12 failure accepted work counters",
    )
    count += 1

    mutated = copy.deepcopy(m04[0])
    bare = next(
        event for event in mutated["event_trace"]
        if event["name"] == "SPANNER_BARE_ABSENT_STRONG_READ"
    )
    bare["details"]["consistency"] = "EVENTUAL"
    bare["details"]["revision"] = 999
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    require_candidate_reject(mutated, "M04 bare-read consistency/revision")
    _expect_code(
        "E_CAS_CONSISTENCY",
        lambda: independent_oracle_row(mutated, *m04[1:]),
        "M04 bare-read consistency/revision",
    )
    count += 1

    m15 = representatives["M15"]
    mutated = copy.deepcopy(m15[0])
    durable = next(
        event for event in mutated["event_trace"]
        if event["name"] == "DURABLE_IMAGE_SERIALIZED"
    )
    durable["details"]["durable_image"]["witness_generation"] = 99
    durable["details"]["image_sha256"] = sha256_value(durable["details"]["durable_image"])
    mutated["evidence"]["simulator_trace_sha256"] = sha256_value(mutated["event_trace"])
    require_candidate_reject(mutated, "M15 durable image hidden-field drift")
    _expect_code(
        "E_RESTART_IMAGE",
        lambda: independent_oracle_row(mutated, *m15[1:]),
        "M15 durable image hidden-field drift",
    )
    count += 1

    # Durable state-machine and causal-cut mutations must be rejected by both
    # the candidate replay and this independently compiled transition oracle.
    def rehash_trace(value: dict[str, Any], *, resequence: bool = False) -> None:
        if resequence:
            for sequence, event in enumerate(value["event_trace"], start=1):
                event["sequence"] = sequence
        value["evidence"]["simulator_trace_sha256"] = sha256_value(
            value["event_trace"]
        )

    def rehash_state(value: dict[str, Any]) -> None:
        value["evidence"]["post_state_sha256"] = sha256_value(value["state"])

    dual_rejection_labels: list[str] = [
        "call operation/prepared binding",
        "validation before processing/delivery",
        "missing observed response",
        "S12 failure accepted work counters",
        "M04 bare-read consistency/revision",
        "M15 durable image hidden-field drift",
    ]

    def reject_by_both(
        value: dict[str, Any],
        record: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
        error_code: str,
        label: str,
    ) -> None:
        require_candidate_reject(value, label)
        _expect_code(
            error_code,
            lambda: independent_oracle_row(value, *record[1:]),
            label,
        )
        dual_rejection_labels.append(label)

    def first_transition(value: dict[str, Any]) -> dict[str, Any]:
        return next(
            event for event in value["event_trace"]
            if "transition_record" in event["details"]
        )

    def transition_phase(
        value: dict[str, Any], phase: str
    ) -> dict[str, Any]:
        return next(
            event for event in value["event_trace"]
            if event["details"].get("transition_envelope", {}).get("phase")
            == phase
        )

    transition_negatives = 0

    mutated = copy.deepcopy(m00[0])
    first_transition(mutated)["details"]["transition_record"]["extra"] = True
    rehash_trace(mutated)
    reject_by_both(mutated, m00, "E_TRANSITION_FIELDS", "transition record field closure")
    transition_negatives += 1

    mutated = copy.deepcopy(m00[0])
    first_transition(mutated)["details"]["transition_record_sha256"] = "f" * 64
    rehash_trace(mutated)
    reject_by_both(mutated, m00, "E_TRANSITION_HASH", "transition record hash")
    transition_negatives += 1

    for field_name in ("compare_record_sha256", "observed_record_sha256"):
        mutated = copy.deepcopy(m00[0])
        transition_phase(mutated, "SIGN_ATTEMPT_PREPARED")["details"][
            "transition_envelope"
        ][field_name] = ZERO_SHA256
        rehash_trace(mutated)
        reject_by_both(
            mutated,
            m00,
            "E_TRANSITION_COMPARE",
            f"transition {field_name}",
        )
        transition_negatives += 1

    for field_name in (
        "expected_mod_revision", "committed_revision", "top_level_revision",
    ):
        mutated = copy.deepcopy(m00[0])
        transition_phase(mutated, "SIGN_ATTEMPT_PREPARED")["details"][
            "transition_envelope"
        ][field_name] += 9
        rehash_trace(mutated)
        reject_by_both(
            mutated,
            m00,
            "E_TRANSITION_REVISION",
            f"transition {field_name}",
        )
        transition_negatives += 1

    for record, field_name in ((m00, "nested"), (representatives["S00"], "leased")):
        mutated = copy.deepcopy(record[0])
        first_transition(mutated)["details"]["transition_envelope"][field_name] = True
        rehash_trace(mutated)
        reject_by_both(
            mutated,
            record,
            "E_TRANSITION_CAS",
            f"transition {field_name} mutation",
        )
        transition_negatives += 1

    transition_store_mutations = (
        (m00, "store_kind", "ETCD_LINEARIZABLE_TOP_LEVEL_EXACT_KEY_CAS"),
        (representatives["S00"], "consistency", "SERIALIZABLE"),
        (representatives["S00"], "response_revision_source", "LOCAL_CACHE"),
    )
    for record, field_name, replacement in transition_store_mutations:
        mutated = copy.deepcopy(record[0])
        first_transition(mutated)["details"]["transition_envelope"][
            field_name
        ] = replacement
        rehash_trace(mutated)
        reject_by_both(
            mutated,
            record,
            "E_TRANSITION_STORE",
            f"transition {field_name}",
        )
        transition_negatives += 1

    mutated = copy.deepcopy(m00[0])
    mutated["event_trace"] = [
        event for event in mutated["event_trace"]
        if event["details"].get("transition_envelope", {}).get("phase")
        != "SIGN_ATTEMPT_PREPARED"
    ]
    rehash_trace(mutated, resequence=True)
    reject_by_both(mutated, m00, "E_TRANSITION_PHASE", "prepared phase skipped")
    transition_negatives += 1

    mutated = copy.deepcopy(m00[0])
    consume_index = next(
        index for index, event in enumerate(mutated["event_trace"])
        if event["name"] == "KMS_SIGN_ATTEMPT_CALL_CONSUMED"
    )
    call_index = next(
        index for index, event in enumerate(mutated["event_trace"])
        if event["name"] == "KMS_DOUBLE_CALL"
    )
    mutated["event_trace"][consume_index], mutated["event_trace"][call_index] = (
        mutated["event_trace"][call_index], mutated["event_trace"][consume_index]
    )
    rehash_trace(mutated, resequence=True)
    reject_by_both(
        mutated, m00, "E_CALL_CONSUMPTION", "call before consumption CAS"
    )
    transition_negatives += 1

    m05_transition = representatives["M05"]
    mutated = copy.deepcopy(m05_transition[0])
    first_attempt_index = next(
        index for index, event in enumerate(mutated["event_trace"])
        if event["name"] == "SPANNER_SERIALIZABLE_TRANSACTION_ATTEMPT"
    )
    second_attempt = copy.deepcopy(mutated["event_trace"][first_attempt_index])
    second_attempt["details"]["attempt"] = 2
    mutated["event_trace"].insert(first_attempt_index + 1, second_attempt)
    rehash_trace(mutated, resequence=True)
    reject_by_both(
        mutated, m05_transition, "E_M05_ATOMIC", "M05 split transaction binding"
    )
    transition_negatives += 1

    mutated = copy.deepcopy(m15[0])
    durable = next(
        event for event in mutated["event_trace"]
        if event["name"] == "DURABLE_IMAGE_SERIALIZED"
    )
    durable["details"]["durable_image"][
        "durable_operation_record_sha256"
    ] = ZERO_SHA256
    durable["details"]["durable_image"]["durable_operation_revision"] = 0
    durable["details"]["image_sha256"] = sha256_value(
        durable["details"]["durable_image"]
    )
    rehash_trace(mutated)
    reject_by_both(mutated, m15, "E_RESTART_IMAGE", "M15 restart durable tip")
    transition_negatives += 1

    s03 = representatives["S03"]
    mutated = copy.deepcopy(s03[0])
    mutated["state"]["durable_operation_record_sha256"] = "f" * 64
    mutated["state"]["durable_operation_revision"] = 1
    rehash_state(mutated)
    reject_by_both(
        mutated, s03, "E_S03_TRANSITION", "S03 zero-mutation guarantee"
    )
    transition_negatives += 1

    def replace_hash_binding(value: Any, old: str, new: str) -> None:
        if type(value) is dict:
            for key, nested in value.items():
                if nested == old:
                    value[key] = new
                else:
                    replace_hash_binding(nested, old, new)
        elif type(value) is list:
            for index, nested in enumerate(value):
                if nested == old:
                    value[index] = new
                else:
                    replace_hash_binding(nested, old, new)

    for record, replacement_key, label in (
        (representatives["M04"], "f" * 64, "M04 applied commit joint rewrite"),
        (representatives["S04"], "e" * 64, "S04 applied commit joint rewrite"),
    ):
        mutated = copy.deepcopy(record[0])
        applied = first_transition(mutated)
        old_key = applied["details"]["transition_envelope"]["operation_key"]
        replace_hash_binding(mutated["event_trace"], old_key, replacement_key)
        rehash_trace(mutated)
        reject_by_both(
            mutated,
            record,
            "E_TRANSITION_BINDING",
            label,
        )
        transition_negatives += 1

    m04_odd_transition = representatives["M04"]
    mutated = copy.deepcopy(m04_odd_transition[0])
    first_transition(mutated)["details"]["operation_key"] = "f" * 64
    rehash_trace(mutated)
    reject_by_both(
        mutated,
        m04_odd_transition,
        "E_TRANSITION_OUTER_BINDING",
        "M04 applied outer operation key",
    )
    transition_negatives += 1

    s04_odd_transition = representatives["S04"]
    mutated = copy.deepcopy(s04_odd_transition[0])
    first_transition(mutated)["details"]["cas_result"] = "CONFLICT_NO_MUTATION"
    rehash_trace(mutated)
    reject_by_both(
        mutated,
        s04_odd_transition,
        "E_TRANSITION_OUTER_BINDING",
        "S04 applied outer CAS result",
    )
    transition_negatives += 1

    mutated = copy.deepcopy(m04[0])
    fence = next(
        event for event in mutated["event_trace"]
        if event["name"] == "SPANNER_ABSENT_TO_TERMINAL_FENCE_TRANSACTION"
    )
    fence["details"]["committed_record_sha256"] = "f" * 64
    rehash_trace(mutated)
    reject_by_both(
        mutated,
        m04,
        "E_TRANSITION_OUTER_BINDING",
        "M04 rich fence hash",
    )
    transition_negatives += 1

    s04_even_transition = next(
        (row, expected, *index[(expected["track_id"], expected["case_id"])])
        for row, expected in zip(rows, schedule, strict=True)
        if expected["case_id"] == "S04"
        and expected["repetition_index"] % 2 == 0
    )
    mutated = copy.deepcopy(s04_even_transition[0])
    mutated["state"]["durable_operation_record_sha256"] = ZERO_SHA256
    mutated["state"]["durable_operation_revision"] = 0
    rehash_state(mutated)
    reject_by_both(
        mutated,
        s04_even_transition,
        "E_TRANSITION_STATE",
        "S04 terminal-fence durable tip",
    )
    transition_negatives += 1

    mutated = copy.deepcopy(s04_even_transition[0])
    first_transition(mutated)["details"]["revision"] = 9
    rehash_trace(mutated)
    reject_by_both(
        mutated,
        s04_even_transition,
        "E_TRANSITION_OUTER_BINDING",
        "S04 fence outer revision",
    )
    transition_negatives += 1

    mutated = copy.deepcopy(m05_transition[0])
    trigger = next(
        event for event in mutated["event_trace"]
        if event["name"] == "ONE_SHOT_FAULT_TRIGGERED"
    )
    trigger["details"]["causal_binding_sha256"] = "f" * 64
    rehash_trace(mutated)
    reject_by_both(
        mutated,
        m05_transition,
        "E_TRIGGER_CAUSAL_BINDING",
        "one-shot fault causal binding",
    )
    transition_negatives += 1

    mutated = copy.deepcopy(m15[0])
    outbox_index = next(
        index for index, event in enumerate(mutated["event_trace"])
        if event["name"] == "SPANNER_OUTBOX_COMMITTED"
    )
    mutated["event_trace"].insert(
        outbox_index,
        {
            "sequence": 0,
            "name": "SPANNER_DEFINITE_ABORT",
            "details": {"attempt": 1},
        },
    )
    rehash_trace(mutated, resequence=True)
    trigger = next(
        event for event in mutated["event_trace"]
        if event["name"] == "ONE_SHOT_FAULT_TRIGGERED"
    )
    trigger["details"]["causal_binding_sha256"] = _framed_hash(
        "agent-bridge/biocortex-ab/track-b/reference-provider-fault-injection/v1/causal-cut",
        mutated["schedule"]["simulation_run_id"],
        "OUTBOX_READY_BEFORE_ATTEMPT_CAS",
        str(trigger["sequence"]),
    )
    rehash_trace(mutated)
    reject_by_both(
        mutated,
        m15,
        "E_TRIGGER_CAUSAL_BINDING",
        "M15 shifted trigger sequence self-proof",
    )
    transition_negatives += 1

    s09_transition = representatives["S09"]
    mutated = copy.deepcopy(s09_transition[0])
    next(
        event for event in mutated["event_trace"]
        if event["name"] == "RESTORE_WITNESS_CANDIDATE_STAGED"
    )["details"]["witness_record_sha256"] = "f" * 64
    next(
        event for event in mutated["event_trace"]
        if event["name"] == "ONE_SHOT_FAULT_TRIGGERED"
    )["details"]["causal_binding_sha256"] = "f" * 64
    rehash_trace(mutated)
    reject_by_both(
        mutated,
        s09_transition,
        "E_TRIGGER_CAUSAL_BINDING",
        "S09 staged witness causal self-proof",
    )
    transition_negatives += 1

    s10_transition = representatives["S10"]
    mutated = copy.deepcopy(s10_transition[0])
    next(
        event for event in mutated["event_trace"]
        if event["name"] == "SNAPSHOT_HASH_VERIFIED"
    )["details"]["snapshot_sha256"] = "f" * 64
    next(
        event for event in mutated["event_trace"]
        if event["name"] == "ONE_SHOT_FAULT_TRIGGERED"
    )["details"]["causal_binding_sha256"] = "f" * 64
    rehash_trace(mutated)
    reject_by_both(
        mutated,
        s10_transition,
        "E_TRIGGER_CAUSAL_BINDING",
        "S10 snapshot causal self-proof",
    )
    transition_negatives += 1

    require(
        transition_negatives == 28,
        "E_NEGATIVE_COVERAGE",
        "transition negative catalog drift",
    )
    count += transition_negatives

    # Evidence fields are compiled independently from the frozen KAT payloads.
    # These mutations stay after REQUIRED_TOKENS checks so legacy missing-token
    # negatives retain their original error codes.
    def row_at(
        case_id: str,
        repetition: int,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        return next(
            (row, expected, *index[(expected["track_id"], expected["case_id"])])
            for row, expected in zip(rows, schedule, strict=True)
            if expected["case_id"] == case_id
            and expected["repetition_index"] == repetition
        )

    m00 = row_at("M00", 1)
    m03 = row_at("M03", 1)
    m04_even = row_at("M04", 2)
    m05 = row_at("M05", 1)
    m06 = row_at("M06", 1)
    m07_bad_crc = row_at("M07", 1)
    m08_omit = row_at("M08", 1)
    m08_zero = row_at("M08", 2)
    m08_parent = row_at("M08", 3)
    m12_evidence = row_at("M12", 1)
    m13_quarantined = row_at("M13", 2)
    s00 = row_at("S00", 1)
    s04_even = row_at("S04", 2)
    s16 = row_at("S16", 1)
    s17_prefix = row_at("S17", 1)
    s17_key_pin = row_at("S17", 2)
    base_kms_request_sha = sha256_value(_independent_kms_request())
    base_kms_response_sha = sha256_value(
        _independent_kms_response(_independent_kms_request())
    )
    base_transit_response_sha = sha256_value(_independent_transit_response())

    evidence_negatives: list[
        tuple[
            tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
            str,
            str,
            Callable[[dict[str, Any]], None],
        ]
    ] = [
        (
            m00, "E_EVIDENCE_REQUEST_SHA256", "M00 request SHA",
            lambda value: value["evidence"].__setitem__("request_sha256", ZERO_SHA256),
        ),
        (
            m07_bad_crc, "E_EVIDENCE_REQUEST_SHA256", "M07 bad-CRC request SHA",
            lambda value: value["evidence"].__setitem__("request_sha256", base_kms_request_sha),
        ),
        (
            m05, "E_EVIDENCE_REQUEST_SHA256", "M05 digest-arm request SHA",
            lambda value: value["evidence"].__setitem__("request_sha256", ZERO_SHA256),
        ),
        (
            m06, "E_EVIDENCE_REQUEST_SHA256", "M06 mutated-frame request SHA",
            lambda value: value["evidence"].__setitem__("request_sha256", ZERO_SHA256),
        ),
        (
            m08_omit, "E_EVIDENCE_REQUEST_SHA256", "M08 omitted-segment request SHA",
            lambda value, source=m08_parent[0]["evidence"]["request_sha256"]: value["evidence"].__setitem__("request_sha256", source),
        ),
        (
            m08_zero, "E_EVIDENCE_REQUESTED_KEY_VERSION", "M08 zero requested key version",
            lambda value: value["evidence"].__setitem__("requested_key_version", MANAGED_KEY_VERSION),
        ),
        (
            s16, "E_EVIDENCE_REQUESTED_KEY_VERSION", "S16 zero requested key version",
            lambda value: value["evidence"].__setitem__("requested_key_version", SELF_HOSTED_KEY_VERSION),
        ),
        (
            m00, "E_EVIDENCE_RESPONSE_SHA256", "M00 response SHA",
            lambda value: value["evidence"].__setitem__("response_sha256", ZERO_SHA256),
        ),
        (
            m12_evidence, "E_EVIDENCE_RESPONSE_SHA256", "M12 dropped response SHA",
            lambda value: value["evidence"].__setitem__("response_sha256", base_kms_response_sha),
        ),
        (
            s17_prefix, "E_EVIDENCE_RESPONSE_SHA256", "S17 mutated-prefix response SHA",
            lambda value: value["evidence"].__setitem__("response_sha256", base_transit_response_sha),
        ),
        (
            m13_quarantined, "E_EVIDENCE_VALIDATED_KEY_VERSION", "M13 quarantined validated key version",
            lambda value: value["evidence"].__setitem__("validated_key_version", 0),
        ),
        (
            m03, "E_EVIDENCE_REQUESTED_ISOLATION", "M03 requested isolation",
            lambda value: value["evidence"].__setitem__("requested_isolation", MANAGED_ISOLATION),
        ),
        (
            m03, "E_EVIDENCE_EFFECTIVE_ISOLATION", "M03 effective isolation",
            lambda value: value["evidence"].__setitem__("effective_isolation", MANAGED_ISOLATION),
        ),
        (
            s00, "E_EVIDENCE_REQUESTED_ISOLATION", "S00 self-hosted isolation",
            lambda value: value["evidence"].__setitem__("requested_isolation", "LINEARIZABLE"),
        ),
        (
            m00, "E_EVIDENCE_TEST_SIGNATURE_SHA256", "test-signature SHA",
            lambda value: value["evidence"].__setitem__("test_signature_sha256", ZERO_SHA256),
        ),
        (
            m00, "E_EVIDENCE_MESSAGE_SHA256", "message SHA KAT",
            lambda value: value["evidence"].__setitem__("message_sha256", ZERO_SHA256),
        ),
        (
            m00, "E_EVIDENCE_MESSAGE_BYTES", "message length KAT",
            lambda value: value["evidence"].__setitem__("message_bytes", 136),
        ),
        (
            s17_key_pin, "E_EVIDENCE_PUBLIC_KEY_SHA256", "S17 mutated public-key pin",
            lambda value: value["evidence"].__setitem__(
                "public_key_sha256", sha256_bytes(bytes.fromhex(PUBLIC_KEY_HEX))
            ),
        ),
        (
            m04_even, "E_SEMANTIC_TOKEN_VECTOR", "M04 parity token vector",
            lambda value: value["evidence"].__setitem__(
                "semantic_tokens", list(SEMANTIC_TOKEN_VECTORS["M04:odd"])
            ),
        ),
        (
            s04_even, "E_SEMANTIC_TOKEN_VECTOR", "S04 parity token vector",
            lambda value: value["evidence"].__setitem__(
                "semantic_tokens", list(SEMANTIC_TOKEN_VECTORS["S04:odd"])
            ),
        ),
        (
            m00, "E_SEMANTIC_TOKEN_FORBIDDEN", "global forbidden semantic token",
            lambda value: value["evidence"]["semantic_tokens"].append("PRODUCTION_READY"),
        ),
        (
            m00, "E_SEMANTIC_TOKEN_FORBIDDEN", "case forbidden semantic token",
            lambda value, token=m00[3]["forbidden_claims"][0]: value["evidence"]["semantic_tokens"].append(token),
        ),
    ]
    require(
        len(evidence_negatives) == 22,
        "E_NEGATIVE_COVERAGE",
        "evidence negative catalog drift",
    )
    for record, error_code, label, mutate in evidence_negatives:
        mutated = copy.deepcopy(record[0])
        mutate(mutated)
        require_candidate_reject(mutated, label)
        _expect_code(
            error_code,
            lambda value=mutated, arguments=record[1:]: independent_oracle_row(
                value, *arguments
            ),
            label,
        )
        dual_rejection_labels.append(label)
        count += 1

    # Boundary/config mutations must fail in the candidate before any model work.
    for field in (
        "provider_called", "credentials_accessed", "paid_resources_provisioned",
        "live_output_permit_defined", "production_adapter_in_scope", "experiment_executed",
    ):
        mutated_config = copy.deepcopy(configuration)
        mutated_config["boundary"][field] = True
        try:
            module.validate_configuration(mutated_config)
        except module.HarnessError:
            count += 1
        else:
            fail("E_NEGATIVE_ACCEPTED", f"configuration boundary mutation accepted: {field}")

    require(
        len(dual_rejection_labels) == 56,
        "E_NEGATIVE_COVERAGE",
        "dual candidate/oracle rejection catalog drift",
    )
    return count


PACKET_PATHS = [
    str(SCHEDULE_SCHEMA_PATH),
    str(RUN_ROW_SCHEMA_PATH),
    str(SUITE_SCHEMA_PATH),
    str(SOURCE_PATH),
    str(CHECKER_PATH),
    str(SYNTHETIC_PATH),
    str(EXPECTED_PATH),
    str(MANIFEST_PATH),
    str(REPORT_PATH),
    str(GATE_PATH),
]


def validate_manifest(
    manifest: dict[str, Any],
    root: Path,
    receipt: dict[str, Any],
    negative_count: int,
) -> None:
    expected_fields = {
        "schema", "date", "logical_baseline_commit", "predecessor", "status", "decision",
        "boundary", "packet", "evidence_sha256", "test_oracle", "results",
        "data_quality", "tracks", "known_limitations", "next_unit",
    }
    require(set(manifest) == expected_fields, "E_MANIFEST_FIELDS", "manifest field drift")
    require(manifest["schema"] == PACK_SCHEMA, "E_MANIFEST_SCHEMA", "manifest schema drift")
    require(manifest["date"] == "2026-07-15", "E_MANIFEST_DATE", "manifest date drift")
    require(manifest["logical_baseline_commit"] == LOGICAL_BASELINE_COMMIT, "E_MANIFEST_BASELINE", "manifest baseline drift")
    require(manifest["predecessor"] == {
        "integration_commit": LOGICAL_BASELINE_COMMIT,
        "manifest_path": str(PREDECESSOR_MANIFEST_PATH),
        "source_commit": PREDECESSOR_SOURCE_COMMIT,
    }, "E_MANIFEST_PREDECESSOR", "manifest predecessor drift")
    require(manifest["status"] == STATUS, "E_MANIFEST_STATUS", "manifest status drift")
    require(manifest["decision"] == DECISION, "E_MANIFEST_DECISION", "manifest decision drift")
    require(manifest["boundary"] == receipt["boundary"], "E_MANIFEST_BOUNDARY", "manifest boundary drift")
    packet = manifest["packet"]
    require(packet["paths"] == PACKET_PATHS, "E_MANIFEST_PATHS", "packet path order drift")
    require(set(packet["modes"]) == set(PACKET_PATHS), "E_MANIFEST_MODES", "packet mode catalog drift")
    require(
        [packet["modes"][path] for path in PACKET_PATHS]
        == ["100644"] * 9 + ["100755"],
        "E_MANIFEST_MODES",
        "packet mode drift",
    )
    evidence = manifest["evidence_sha256"]
    require(type(evidence) is dict and evidence, "E_MANIFEST_EVIDENCE", "manifest evidence missing")
    require(str(MANIFEST_PATH) not in evidence and str(GATE_PATH) not in evidence, "E_MANIFEST_CYCLE", "manifest/gate circular evidence binding")
    for relative, expected in evidence.items():
        require(type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected) is not None, "E_MANIFEST_HASH", f"invalid evidence hash {relative}")
        require(sha256_bytes((root / relative).read_bytes()) == expected, "E_MANIFEST_HASH", f"evidence hash drift {relative}")
    required_evidence = set(PACKET_PATHS) - {str(MANIFEST_PATH), str(GATE_PATH)}
    required_evidence |= set(EXPECTED_PREDECESSOR_HASHES)
    require(set(evidence) == required_evidence, "E_MANIFEST_EVIDENCE", "manifest evidence path set drift")
    require(manifest["test_oracle"] == {
        "cases": 34,
        "client_conformance_observation_rows": 420,
        "directed_negative_tests": negative_count,
        "model_scenario_rows": 600,
        "offline_synthetic_rows": 1020,
        "repetitions_per_case": 30,
        "schema_documents": 3,
        "tracks": 2,
    }, "E_MANIFEST_ORACLE", "manifest oracle drift")
    require(manifest["results"] == {
        "configuration_sha256": receipt["configuration_sha256"],
        "experimental_run_rows": 0,
        "managed_service_observation_rows": 0,
        "offline_rows_sha256": receipt["offline_rows_sha256"],
        "owned_lab_observation_rows": 0,
        "planned_experiment_rows_satisfied": 0,
        "provider_evidence_rows": 0,
        "schedule_sha256": receipt["schedule_sha256"],
    }, "E_MANIFEST_RESULTS", "manifest results drift")
    require(manifest["data_quality"] == receipt["data_quality"], "E_MANIFEST_QUALITY", "manifest data quality drift")
    require(manifest["tracks"] == receipt["track_results"], "E_MANIFEST_TRACKS", "manifest track results drift")
    require(manifest["next_unit"] == NEXT_UNIT, "E_MANIFEST_NEXT", "manifest next unit drift")
    require(type(manifest["known_limitations"]) is list and len(manifest["known_limitations"]) >= 10, "E_MANIFEST_LIMITATIONS", "manifest limitations incomplete")


def render_result_tsv(receipt: dict[str, Any], negative_count: int) -> str:
    counts = receipt["counts"]
    fields: list[tuple[str, Any]] = [
        ("schema", RESULT_SCHEMA),
        ("status", receipt["status"]),
        ("decision", receipt["decision"]),
        ("contract_sha256", receipt["contract_sha256"]),
        ("configuration_sha256", receipt["configuration_sha256"]),
        ("schedule_sha256", receipt["schedule_sha256"]),
        ("offline_rows_sha256", receipt["offline_rows_sha256"]),
        ("tracks", counts["tracks"]),
        ("cases", counts["cases"]),
        ("repetitions_per_case", counts["repetitions_per_case"]),
        ("offline_synthetic_rows", counts["offline_synthetic_rows"]),
        ("client_conformance_observation_rows", counts["client_conformance_observation_rows"]),
        ("model_scenario_rows", counts["model_scenario_rows"]),
        ("managed_service_observation_rows", counts["managed_service_observation_rows"]),
        ("owned_lab_observation_rows", counts["owned_lab_observation_rows"]),
        ("provider_evidence_rows", counts["provider_evidence_rows"]),
        ("experimental_run_rows", counts["experimental_run_rows"]),
        ("planned_experiment_rows_satisfied", counts["planned_experiment_rows_satisfied"]),
        ("directed_negative_tests", negative_count),
        ("schema_documents_validated", 3),
    ]
    return "".join(f"{key}\t{str(value).lower() if type(value) is bool else value}\n" for key, value in fields)


def evaluate(root: Path) -> tuple[str, int]:
    schedule_schema, _ = load_canonical(root / SCHEDULE_SCHEMA_PATH, "schedule schema")
    run_schema, _ = load_canonical(root / RUN_ROW_SCHEMA_PATH, "run-row schema")
    suite_schema, _ = load_canonical(root / SUITE_SCHEMA_PATH, "suite-receipt schema")
    contract, contract_raw = load_canonical(root / CONTRACT_PATH, "preregistration contract")
    configuration, _ = load_canonical(root / SYNTHETIC_PATH, "offline configuration")
    manifest, _ = load_canonical(root / MANIFEST_PATH, "pack manifest")
    predecessor_manifest, _ = load_canonical(root / PREDECESSOR_MANIFEST_PATH, "predecessor manifest")

    validate_schema_document(
        schedule_schema,
        "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_offline_schedule_entry.v1",
        "schedule schema",
    )
    validate_schema_document(run_schema, RUN_ROW_SCHEMA, "run-row schema")
    validate_schema_document(suite_schema, SUITE_RECEIPT_SCHEMA, "suite-receipt schema")
    require(sha256_bytes(contract_raw) == CONTRACT_SHA256, "E_CONTRACT_HASH", "contract hash drift")
    validate_predecessor(root, predecessor_manifest)
    validate_report_bindings(root)
    validate_source_ast(root / SOURCE_PATH)

    module, module_name = load_source_module(root / SOURCE_PATH)
    try:
        require(module.CONTRACT_SHA256 == CONTRACT_SHA256, "E_SOURCE_CONSTANT", "source contract pin drift")
        require(module.STATUS == STATUS and module.DECISION == DECISION, "E_SOURCE_CONSTANT", "source status/decision drift")
        require(module.NEXT_UNIT == NEXT_UNIT, "E_SOURCE_CONSTANT", "source next-unit drift")
        module.validate_contract(contract)
        module.validate_configuration(configuration)
        validate_known_answer_tests(module)
        validate_evidence_compiler_known_answers(configuration)
        first_receipt, first_rows = module.build_suite_receipt(contract, configuration)
        second_receipt, second_rows = module.build_suite_receipt(
            copy.deepcopy(contract), copy.deepcopy(configuration)
        )
        require(canonical_bytes(first_receipt) == canonical_bytes(second_receipt), "E_CANDIDATE_NONDETERMINISM", "suite receipt changed across deep-copy rerun")
        require(canonical_bytes(first_rows) == canonical_bytes(second_rows), "E_CANDIDATE_NONDETERMINISM", "offline rows changed across deep-copy rerun")
        config_sha = sha256_value(configuration)
        expected_schedule = independent_schedule(contract, config_sha)
        require([entry.as_dict() for entry in module.build_schedule(contract, configuration)] == expected_schedule, "E_SCHEDULE_INDEPENDENCE", "candidate schedule differs from independent implementation")
        for row, expected in zip(first_rows, expected_schedule, strict=True):
            validate_json_schema(expected, schedule_schema)
            validate_json_schema(row, run_schema)
        validate_json_schema(first_receipt, suite_schema)
        independent_oracle_bundle(first_rows, contract, config_sha)
        require(first_receipt["schedule_sha256"] == sha256_value(expected_schedule), "E_RECEIPT_SCHEDULE_HASH", "receipt schedule hash drift")
        require(first_receipt["offline_rows_sha256"] == sha256_value(first_rows), "E_RECEIPT_ROWS_HASH", "receipt rows hash drift")
        negative_count = run_directed_negative_tests(
            module, first_rows, contract, configuration, run_schema
        )
    finally:
        sys.modules.pop(module_name, None)

    validate_manifest(manifest, root, first_receipt, negative_count)
    output = render_result_tsv(first_receipt, negative_count)
    try:
        expected_output = (root / EXPECTED_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        fail("E_EXPECTED_LOAD", f"cannot load expected TSV: {exc}")
    require(output == expected_output, "E_EXPECTED_DRIFT", "expected TSV drift")
    return output, negative_count


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
            require(first == second and first_count == second_count, "E_OUTER_NONDETERMINISM", "outer self-test drift")
        sys.stdout.write(first)
    except (PackError, OSError, ValueError) as exc:
        print(
            f"INVALID_BIOCORTEX_REFERENCE_PROVIDER_FAULT_INJECTION_OFFLINE_HARNESS_V1: {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
