#!/usr/bin/env python3
"""Fail-closed offline oracle for the S17 owned-lab L1 preregistration.

This checker validates only a zero-observation, zero-authority contract packet.
It never creates a lab root, starts a runner, sends a signal, opens a provider,
or treats a schema/plan as runtime evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


sys.dont_write_bytecode = True

STATUS = (
    "RECOVERED_ENVELOPE_OWNED_LAB_PROCESS_CRASH_RESTART_S17_FIRST_BATCH_"
    "OL00_OL04_OL05_PREREGISTERED_EXECUTION_BLOCKED_ZERO_OBSERVATIONS_NO_AUTHORITY"
)
DECISION = "BLOCKED_PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING"
CLAIM_LEVEL = "L1_PROCESS_CRASH_FRESH_PROCESS_RESTART_ONLY"
CLAIM_CEILING = (
    "OWNED_LAB_LOCAL_PROCESS_DEATH_RECOVERY_L1_ONLY_NOT_HOST_POWER_LOSS_"
    "NOT_STORAGE_DEVICE_DURABILITY_NOT_PROVIDER_DURABILITY_NOT_ROLLBACK_RESISTANCE"
)
EXPECTED_OBSERVATION_SCHEMA_CANONICAL_SHA256 = "f9cabcfcebefee153f7651bdfe426936932de1623f642431341469f0762f5a47"
EXPECTED_OWNER_SCHEMA_CANONICAL_SHA256 = "3dfd4e530906dde744b95f550ee06df69774042bcb754defd90afbeb5b968a6c"

PLAN_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-"
    "process-crash-restart-plan-s17-v0.json"
)
OBSERVATION_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-"
    "process-crash-restart-observation-schema-s17-v0.json"
)
OWNER_SCHEMA_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-owned-lab-"
    "owner-resource-decision-schema-s17-v0.json"
)
SUCCESSOR_PATH = (
    "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s17-v0.json"
)
SYNTHETIC_PATH = (
    "scripts/eval/fixtures/memory_temporal_recovered_envelope_owned_lab_"
    "process_crash_restart_s17.synthetic.v0.json"
)
DESIGN_PATH = (
    "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_OWNED_LAB_PROCESS_"
    "CRASH_RESTART_PREREGISTRATION_S17_2026_07_17.md"
)
REPORT_PATH = (
    "docs/reports/goal-c-u/2026-07-17-biocortex-ab-track-b-recovered-envelope-"
    "owned-lab-process-crash-restart-preregistration-s17.md"
)
CHECKER_PATH = (
    "scripts/eval/check_memory_temporal_recovered_envelope_owned_lab_"
    "process_crash_restart_s17.py"
)
GATE_PATH = (
    "scripts/check-memory-temporal-recovered-envelope-owned-lab-process-"
    "crash-restart-s17.sh"
)

BASELINE = {
    "source_parent_commit": "d5bbe55d5d95b1163e287415f437cf77c594135d",
    "s16_source_commit": "dca7436a9d9df990355d67e374184202332f0354",
    "s16_integration_commit": "d7f3e206169227905dbd320f1876de46e3facfea",
    "s16_source_baseline_commit": "a152b26ed839d4b96f669552f090ec55bc066ca9",
    "s15_integration_commit": "80fdb9b5d5f4be5f9663f30cd686cd5fb6bdfd35",
}

S16_BINDINGS = {
    "s15_contract_sha256": "07d7ae5e7345bb5052aa130349af2e90bae853e5c74560346a4178b2b0397cc7",
    "s16_contract_sha256": "2500ae0651025434392b87d5a151487faa4b6e60a6523e083c1987446c3bdb66",
    "s16_successor_gate_sha256": "175b58589dbdb0c22310c41451271c822532945d85c25c8f268f5a9b2ac7f7c3",
    "s16_model_source_sha256": "b10984e6336c436a0b84548d0f8c9f7ad4537df7b491d4863e1b6545f517f2d1",
    "s16_design_sha256": "5333c844fdc24d6f63e5dc1c575765912168dc7b8f9ffafff8b0a7cd9d6c7275",
    "s16_gate_sha256": "207f4d3d98f7152efe37645a78e66cd8afc3ed6983f412d15c206129b60b5007",
    "s16_checker_sha256": "0f4c5d9fb2a63f3a65d56a462a6299819e539a4b5f205610ac1c0daffc8dc0e8",
    "s16_expected_receipt_sha256": "875ef3ce65ac06228f4a76de069a34eb79ffa04e805a296369c634fd9a666015",
    "catalog_row_count": 5639,
    "catalog_message_len": 225852,
    "catalog_sha256": "c09cdc640957594cc7acc2eeea39cb4e59993631ef04a1fa1e26a69c285af853",
    "base_record_len": 5494,
    "base_record_sha256": "a788ec43fefa76e393d77c86bbfabeef7d2ae8c5499bb834c1945af5cbb1b3cd",
    "lookup_commitment_sha256": "866e016ce631433e3e272d0858906f3c76c67204cd74b73ab11b7353e57eae00",
    "receipt_sha256": "12c80f1b610d48438ec69457a6f553bf48fd6a15a9c3ffebd7b20c67895b76a2",
    "witness_sha256": "c336caea644548f287ddc285ee3b9433f853f9b1f562cee9f055df913458bf99",
    "selected_view_sha256": "9a8f959a01d3aead14b527d51bb1c744999e8e1ee33a564cea72bb15b2b00d6a",
    "clean_d00_row_sha256": "b9e4f9ab470de985c97b50292deae898181c96e21894b43de23ec98ec3fced1a",
}

FROZEN_PREDECESSOR_ARTIFACTS = {
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-bounded-runtime-adapter-s15-v0.json": S16_BINDINGS["s15_contract_sha256"],
    "docs/design/fixtures/biocortex-ab-track-b-recovered-envelope-durability-fault-model-s16-v0.json": S16_BINDINGS["s16_contract_sha256"],
    "docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s16-v0.json": S16_BINDINGS["s16_successor_gate_sha256"],
    "docs/design/MEMORY_TEMPORAL_RECOVERED_ENVELOPE_DURABILITY_FAULT_MODEL_S16_2026_07_17.md": S16_BINDINGS["s16_design_sha256"],
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_reverification/recovered_envelope_delivery/recovered_envelope_source/bounded_runtime_adapter/durability_fault_model.rs": S16_BINDINGS["s16_model_source_sha256"],
    "scripts/check-memory-temporal-recovered-envelope-durability-fault-model-s16.sh": S16_BINDINGS["s16_gate_sha256"],
    "scripts/eval/check_memory_temporal_recovered_envelope_durability_fault_model_s16.py": S16_BINDINGS["s16_checker_sha256"],
    "scripts/eval/fixtures/memory_temporal_recovered_envelope_durability_fault_model_s16.expected.v0.tsv": S16_BINDINGS["s16_expected_receipt_sha256"],
}

EXPECTED_FAMILIES = [
    {
        "owned_lab_family_id": "OL00",
        "s16_case_id": "D00_CLEAN_COMMITTED_HEAD",
        "scenario_count": 1,
        "variants": ["CLEAN_CONTROL_NO_CRASH"],
    },
    {
        "owned_lab_family_id": "OL04",
        "s16_case_id": "D04_PUBLISH_CRASH_RESTART_CUTS",
        "scenario_count": 6,
        "variants": [
            "CRASH_AT_EMPTY_RESTART",
            "CRASH_AFTER_OBJECT_PREFIX_RESTART",
            "CRASH_AFTER_OBJECT_COMMIT_RESTART",
            "CRASH_AFTER_RECEIPT_COMMIT_RESTART",
            "CRASH_AFTER_WITNESS_COMMIT_RESTART",
            "CRASH_AFTER_ACK_RESTART",
        ],
    },
    {
        "owned_lab_family_id": "OL05",
        "s16_case_id": "D05_S15_READ_CRASH_RESTART_CUTS",
        "scenario_count": 53,
        "variants": (
            ["BEFORE_OPEN", "AFTER_OPEN"]
            + [f"AFTER_DATA_{index:04d}" for index in range(1, 50)]
            + ["AFTER_COMPLETE_BEFORE_S14", "AFTER_HISTORICAL"]
        ),
    },
]

GLOBAL_PREREQUISITES = [
    "PRODUCTION_AUTHORITY_VERIFIER_IMPLEMENTED",
    "PRODUCTION_MANAGED_ADAPTER_SET_IMPLEMENTED",
    "PRODUCTION_SELF_HOSTED_ADAPTER_SET_IMPLEMENTED",
    "PRODUCTION_STOP_CONTROL_SET_IMPLEMENTED",
    "TRUST_ROOT_AND_KEY_VERSION_POLICY_BOUND",
    "PROVIDER_ENDPOINT_AND_PROFILE_IDENTITY_BOUND",
    "CREDENTIAL_BROKER_LEASE_AND_REVOCATION_BOUND",
    "RESOURCE_SCOPE_AND_COST_BUDGET_AUTHORITY_BOUND",
    "DURABLE_CONTROL_LEDGER_AND_ATOMIC_CAS_PROVEN",
    "TRUSTED_TIME_AND_CURRENTNESS_EVIDENCE_BOUND",
    "RUNNER_BUILD_PROCESS_SESSION_AND_CHANNEL_PROVENANCE_BOUND",
    "FAULT_DISARM_EGRESS_ISOLATION_AND_EMERGENCY_STOP_PROVEN",
    "DURABLE_EVIDENCE_RETENTION_AND_SCOPED_CLEANUP_PROVEN",
    "REAL_PREREGISTERED_SCHEDULE_ASSIGNMENT_AND_ROW_CUSTODY_BOUND",
    "INDEPENDENT_SECURITY_FAILURE_MODE_AND_ROLLBACK_REVIEW_APPROVED",
    "OWNER_RUNTIME_ADMISSION_DECISION_RECORDED",
]

EXPECTED_CROSS_FIELD_RULES = [
    "PIDFD_TARGET_PID_AND_START_EQUAL_INITIAL_CHILD",
    "SIGNAL_SENDER_PID_AND_START_EQUAL_CONTROLLER",
    "FRESH_PID_START_AND_NONCE_DISTINCT_FROM_INITIAL_CHILD",
    "INITIAL_AND_FRESH_EXEC_IMAGE_HASH_EQUAL_FROZEN_RUNNER_BINARY",
    "BOOT_IDS_EQUAL_WHEN_SAME_BOOT_VERIFIED",
    "ROOT_STAT_IDENTITIES_EQUAL_WHEN_ROOT_STABLE",
    "MOUNT_IDENTITIES_AND_MOUNTINFO_EQUAL_WHEN_MOUNT_STABLE",
    "DATABASE_PATH_IS_DIRECT_DESCENDANT_OF_EXACT_RUN_ROOT",
    "DATABASE_IDENTITIES_EQUAL_WHEN_DATABASE_STABLE",
    "SQLITE_PROFILE_AND_SCHEMA_HASH_EQUAL_FROZEN_BINDINGS",
    "CUSTODY_RAW_AND_CANONICAL_HASHES_EQUAL_IDENTITY_HASHES",
    "RAW_EVENT_FRAME_BYTE_RANGE_HASH_RECOMPUTED_FROM_RETAINED_RAW_PACKET",
    "PHASE_RAW_MEASUREMENT_DECODED_FROM_BOUND_RAW_EVENT_FRAME",
    "ACK_OBSERVED_PAYLOAD_BINDS_RECEIPT_AND_WITNESS_AND_NOT_OBSERVED_HAS_NO_PAYLOAD",
    "S16_VIRTUAL_PROJECTION_EXACTLY_DERIVED_FROM_RAW_PHASE_MEASUREMENT_WITH_DOMAIN_SEPARATED_ABSENT_SENTINELS",
    "S16_VIRTUAL_PROJECTION_COUNTERS_ZERO_SIDE_EFFECTS_NONE_AND_DISTINCT_FROM_S17_LEDGER",
    "CLASSIFICATION_INPUT_SHA256_RECOMPUTED_FROM_DOMAIN_AND_EXACT_FRAME",
    "PHASE_RECORD_SHA256_RECOMPUTED_WITH_SELF_HASH_OMITTED",
    "CLASSIFIER_BUILD_EQUALS_FROZEN_CLASSIFIER_BINARY_AND_OWNER_RECEIPT",
    "CLASSIFICATION_RECOMPUTED_BY_PHASE_LIFECYCLE_EVALUATOR_AND_FULL_FROZEN_S16_CATALOG",
    "ASSIGNMENT_FAMILY_CASE_AND_VARIANT_NOT_USED_TO_PREFILTER_CLASSIFICATION",
    "ASSIGNMENT_LABELS_COMPARED_WITH_RECOMPUTED_CLASSIFICATION_ONLY_AFTER_FULL_CATALOG_LOOKUP",
    "UNIQUE_MAPPING_CASE_VARIANT_ROW_REASON_AND_FAILURE_EQUAL_RECOMPUTED_FROZEN_S16_ROW",
    "S16_ABSENT_SENTINELS_USED_ONLY_IN_VIRTUAL_MODEL_PROJECTION_NOT_RAW_PACKET_FACTS",
    "D05_CUT_INDEX_OBSERVED_DATA_STEPS_LENGTH_AND_ADAPTER_STATE_RELATION_VALID",
    "D05_FIRST_AND_RESTART_PHASES_BIND_SAME_ATTEMPT_CUT",
    "EVERY_PHASE_DURABLE_IMAGE_FACTS_EQUAL_TOP_LEVEL_RAW_RECOVERED_STATE",
    "D05_FIRST_PHASE_PROCESS_EQUALS_INITIAL_CHILD",
    "D05_RESTART_PHASE_PROCESS_EQUALS_FRESH_CHILD",
    "SINGLE_PHASE_PROCESS_EQUALS_ELIGIBLE_RESULT_PROCESS",
    "CUSTODY_SEQUENCE_AND_PREVIOUS_HASH_RELATION_VALID",
    "OWNER_RECEIPT_ASSIGNMENT_RESOURCE_SAFETY_AND_DECISION_BINDINGS_VALID",
]

OBSERVABLE_S16_ROW_FIELDS = (
    "publisher_phase", "object_persistence", "object_len", "observed_object_sha256",
    "receipt_state", "computed_receipt_sha256", "stored_receipt_sha256",
    "witness_state", "computed_witness_sha256", "stored_witness_sha256",
    "selected_view_sha256", "competing_view_sha256", "ack_state", "crash_cut",
    "crash_cut_index", "adapter_pre_state", "adapter_post_state",
)


class CheckFailure(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def exact_keys(value: Any, expected: Iterable[str], label: str) -> None:
    require(type(value) is dict, f"{label} must be an object")
    actual = set(value)
    wanted = set(expected)
    require(
        actual == wanted,
        f"{label} keys drift: missing={sorted(wanted - actual)} extra={sorted(actual - wanted)}",
    )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def domain_separated_jcs_sha256(domain: str, frame: Any) -> str:
    return hashlib.sha256(domain.encode("utf-8") + b"\x00" + canonical_json_bytes(frame)).hexdigest()


def read_bytes(repo: Path, relative: str) -> bytes:
    path = repo / relative
    require(path.is_file() and not path.is_symlink(), f"missing/non-regular artifact: {relative}")
    return path.read_bytes()


def read_text(repo: Path, relative: str) -> str:
    raw = read_bytes(repo, relative)
    require(not raw.startswith(b"\xef\xbb\xbf"), f"UTF-8 BOM forbidden: {relative}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"non-UTF-8 artifact: {relative}") from exc


def artifact_sha256(repo: Path, relative: str) -> str:
    return hashlib.sha256(read_bytes(repo, relative)).hexdigest()


def import_frozen_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load frozen module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lifecycle_extra(row: dict[str, Any]) -> tuple[bool, int, int]:
    case_id = row["case_id"]
    variant_id = row["variant_id"]
    if case_id != "D05_S15_READ_CRASH_RESTART_CUTS":
        return (case_id == "D04_PUBLISH_CRASH_RESTART_CUTS", 0, 0)
    if variant_id.endswith("_RESTART"):
        return (True, 49, S16_BINDINGS["base_record_len"])
    cut = row["crash_cut"]
    if cut in {"READ_BEFORE_OPEN", "READ_AFTER_OPEN"}:
        steps = 0
    elif cut == "READ_AFTER_DATA":
        steps = row["crash_cut_index"]
        require(type(steps) is int and 1 <= steps <= 49, "D05 data cut index outside lifecycle KAT")
    elif cut in {"READ_AFTER_COMPLETE_BEFORE_S14", "READ_AFTER_HISTORICAL"}:
        steps = 49
    else:
        raise CheckFailure(f"D05 lifecycle KAT unknown cut: {cut}")
    return (False, steps, min(steps * 113, S16_BINDINGS["base_record_len"]))


def ack_payload_extra(row: dict[str, Any]) -> tuple[str | None, str | None]:
    if row["ack_state"] == "OBSERVED":
        return (S16_BINDINGS["receipt_sha256"], S16_BINDINGS["witness_sha256"])
    return (None, None)


def validate_full_catalog_uniqueness(repo: Path) -> dict[str, dict[str, Any]]:
    checker_path = repo / "scripts/eval/check_memory_temporal_recovered_envelope_durability_fault_model_s16.py"
    module = import_frozen_module(checker_path, "s16_frozen_catalog_for_s17_uniqueness")
    record = module.independent_record(repo)
    rows = module.generate_rows(record)
    require(len(rows) == S16_BINDINGS["catalog_row_count"], "S16 full-catalog KAT row count drift")
    observed_ack_rows = [row for row in rows if row["ack_state"] == "OBSERVED"]
    require(len(observed_ack_rows) == 5, "S16 observed-ack KAT count drift")
    require(all(ack_payload_extra(row) == (S16_BINDINGS["receipt_sha256"], S16_BINDINGS["witness_sha256"]) for row in observed_ack_rows), "S16 observed-ack payload KAT drift")
    require(all(ack_payload_extra(row) == (None, None) for row in rows if row["ack_state"] != "OBSERVED"), "S16 unobserved-ack payload KAT drift")

    def observed_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(row[field] for field in OBSERVABLE_S16_ROW_FIELDS)

    full_counts = Counter(observed_key(row) + lifecycle_extra(row) for row in rows)
    require(len(full_counts) == 5639 and max(full_counts.values()) == 1, "augmented 20-field S16 catalog fingerprints are not globally unique")
    target_cases = {
        "D00_CLEAN_COMMITTED_HEAD",
        "D04_PUBLISH_CRASH_RESTART_CUTS",
        "D05_S15_READ_CRASH_RESTART_CUTS",
    }
    targets = [row for row in rows if row["case_id"] in target_cases]
    require(len(targets) == 113, "S17 full-catalog KAT target count drift")
    target_keys = [observed_key(row) + lifecycle_extra(row) for row in targets]
    require(len(set(target_keys)) == 113, "S17 target lifecycle fingerprints collide")
    require(all(full_counts[key] == 1 for key in target_keys), "S17 target lifecycle fingerprint is missing or non-unique in full catalog")

    pre_lifecycle_counts = Counter(observed_key(row) for row in rows)
    ambiguous_targets = [row for row in targets if pre_lifecycle_counts[observed_key(row)] != 1]
    require(
        [(row["case_id"], row["variant_id"], pre_lifecycle_counts[observed_key(row)]) for row in ambiguous_targets]
        == [("D04_PUBLISH_CRASH_RESTART_CUTS", "CRASH_AFTER_OBJECT_PREFIX_RESTART", 2)],
        "pre-lifecycle ambiguity KAT drift",
    )
    representatives = {
        "OL00": ("D00_CLEAN_COMMITTED_HEAD", "CLEAN"),
        "OL04": ("D04_PUBLISH_CRASH_RESTART_CUTS", "CRASH_AT_EMPTY_RESTART"),
        "OL05_FIRST": ("D05_S15_READ_CRASH_RESTART_CUTS", "BEFORE_OPEN_FIRST_ATTEMPT"),
        "OL05_RESTART": ("D05_S15_READ_CRASH_RESTART_CUTS", "BEFORE_OPEN_RESTART"),
    }
    output: dict[str, dict[str, Any]] = {}
    for label, identity in representatives.items():
        matches = [row for row in rows if (row["case_id"], row["variant_id"]) == identity]
        require(len(matches) == 1, f"representative S16 row missing/non-unique: {label}")
        row = matches[0]
        output[label] = {
            "row": row,
            "row_sha256": hashlib.sha256(module.row_message(row)).hexdigest(),
        }
    output["_sentinels"] = {
        "OBJECT": module.absent_digest("OBJECT").hex(),
        "RECEIPT": module.absent_digest("RECEIPT").hex(),
        "WITNESS": module.absent_digest("WITNESS").hex(),
        "REPLICA_VIEW": module.absent_digest("REPLICA_VIEW").hex(),
    }
    require(output["OL00"]["row_sha256"] == S16_BINDINGS["clean_d00_row_sha256"], "D00 representative row digest drift")
    return output


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in output, f"duplicate JSON key: {key}")
        output[key] = value
    return output


def reject_float(value: str) -> None:
    raise CheckFailure(f"floating-point JSON number forbidden: {value}")


def reject_constant(value: str) -> None:
    raise CheckFailure(f"non-finite JSON constant forbidden: {value}")


def parse_json_text(text: str, label: str) -> dict[str, Any]:
    require(not text.startswith("\ufeff"), f"UTF-8 BOM forbidden: {label}")
    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"invalid JSON {label}: {exc}") from exc
    require(type(value) is dict, f"top-level JSON object required: {label}")
    return value


def load_json(repo: Path, relative: str) -> dict[str, Any]:
    return parse_json_text(read_text(repo, relative), relative)


def all_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    if type(value) is dict:
        for key, child in value.items():
            tokens.add(key)
            tokens.update(all_tokens(child))
    elif type(value) is list:
        for child in value:
            tokens.update(all_tokens(child))
    elif type(value) is str:
        tokens.add(value)
    return tokens


def walk_json(value: Any) -> Iterable[Any]:
    yield value
    if type(value) is dict:
        for child in value.values():
            yield from walk_json(child)
    elif type(value) is list:
        for child in value:
            yield from walk_json(child)


def validate_local_refs(schema: dict[str, Any], label: str) -> None:
    defs = schema.get("$defs", {})
    for node in walk_json(schema):
        if type(node) is dict and "$ref" in node:
            ref = node["$ref"]
            require(type(ref) is str and ref.startswith("#/$defs/"), f"{label} external or malformed ref: {ref}")
            name = ref.removeprefix("#/$defs/")
            require(name and "/" not in name and name in defs, f"{label} unresolved local ref: {ref}")


def strict_json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(strict_json_equal(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(strict_json_equal(a, b) for a, b in zip(left, right))
    return left == right


def resolve_local_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    require(ref.startswith("#/$defs/") and "/" not in ref.removeprefix("#/$defs/"), f"unsupported schema ref: {ref}")
    name = ref.removeprefix("#/$defs/")
    require(name in root["$defs"], f"unresolved schema ref: {ref}")
    return root["$defs"][name]


def schema_type_matches(expected: str, value: Any) -> bool:
    return {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "integer": type(value) is int,
        "boolean": type(value) is bool,
        "null": value is None,
    }.get(expected, False)


def schema_instance_errors(
    schema: dict[str, Any], value: Any, root: dict[str, Any], path: str = "$"
) -> list[str]:
    errors: list[str] = []
    if "$ref" in schema:
        errors.extend(schema_instance_errors(resolve_local_ref(root, schema["$ref"]), value, root, path))
    if "const" in schema and not strict_json_equal(value, schema["const"]):
        errors.append(f"{path}: const mismatch")
    if "enum" in schema and not any(strict_json_equal(value, option) for option in schema["enum"]):
        errors.append(f"{path}: enum mismatch")
    expected_type = schema.get("type")
    if expected_type is not None and not schema_type_matches(expected_type, value):
        errors.append(f"{path}: type mismatch ({expected_type})")
        return errors
    if "oneOf" in schema:
        matches = sum(not schema_instance_errors(option, value, root, path) for option in schema["oneOf"])
        if matches != 1:
            errors.append(f"{path}: oneOf matched {matches}")
    for item in schema.get("allOf", []):
        errors.extend(schema_instance_errors(item, value, root, path))
    if "if" in schema:
        branch = "then" if not schema_instance_errors(schema["if"], value, root, path) else "else"
        if branch in schema:
            errors.extend(schema_instance_errors(schema[branch], value, root, path))
    if type(value) is dict:
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required {key}")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                errors.extend(schema_instance_errors(properties[key], child, root, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: additional property {key}")
    if type(value) is list:
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: too many items")
        prefix = schema.get("prefixItems", [])
        for index, item_schema in enumerate(prefix[: len(value)]):
            errors.extend(schema_instance_errors(item_schema, value[index], root, f"{path}[{index}]"))
        if len(value) > len(prefix):
            items = schema.get("items")
            if items is False:
                errors.append(f"{path}: trailing items forbidden")
            elif type(items) is dict:
                for index in range(len(prefix), len(value)):
                    errors.extend(schema_instance_errors(items, value[index], root, f"{path}[{index}]"))
    if type(value) is str:
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: string too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: string too long")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: pattern mismatch")
    if type(value) is int:
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    return errors


def validate_schema_keywords(root: dict[str, Any], label: str) -> None:
    allowed_types = {"object", "array", "string", "integer", "boolean", "null"}
    for node in walk_json(root):
        if type(node) is not dict:
            continue
        if "type" in node:
            require(node["type"] in allowed_types, f"{label} unsupported type keyword: {node['type']}")
        for keyword in ("properties", "$defs"):
            if keyword in node:
                require(type(node[keyword]) is dict, f"{label} {keyword} must be object")
        if "required" in node:
            required = node["required"]
            require(type(required) is list and all(type(item) is str for item in required) and len(required) == len(set(required)), f"{label} malformed required")
        for keyword in ("oneOf", "allOf", "prefixItems"):
            if keyword in node:
                require(type(node[keyword]) is list and len(node[keyword]) > 0 and all(type(item) is dict for item in node[keyword]), f"{label} malformed {keyword}")
        if "pattern" in node:
            try:
                re.compile(node["pattern"])
            except (TypeError, re.error) as exc:
                raise CheckFailure(f"{label} malformed pattern") from exc
        if "additionalProperties" in node:
            require(type(node["additionalProperties"]) in {bool, dict}, f"{label} malformed additionalProperties")
        if "items" in node:
            require(node["items"] is False or type(node["items"]) is dict, f"{label} malformed items")


def validate_closed_object_required_graph(root: dict[str, Any], label: str) -> None:
    closed_objects = [("$", root)]
    closed_objects.extend((f"$defs.{name}", definition) for name, definition in root.get("$defs", {}).items())
    for path, definition in closed_objects:
        if definition.get("type") != "object" or definition.get("additionalProperties") is not False:
            continue
        properties = definition.get("properties")
        required = definition.get("required")
        require(type(properties) is dict, f"{label} closed object lacks properties: {path}")
        require(type(required) is list, f"{label} closed object lacks required: {path}")
        require(
            len(required) == len(set(required)) and set(required) == set(properties),
            f"{label} closed object required/property graph drift: {path}",
        )


def schema_sample(schema: dict[str, Any], root: dict[str, Any], field: str = "") -> Any:
    if "$ref" in schema:
        return schema_sample(resolve_local_ref(root, schema["$ref"]), root, field)
    if "const" in schema:
        return copy.deepcopy(schema["const"])
    if "enum" in schema:
        return copy.deepcopy(schema["enum"][0])
    if "oneOf" in schema:
        return schema_sample(schema["oneOf"][0], root, field)
    expected_type = schema.get("type")
    if expected_type == "object":
        return {key: schema_sample(schema["properties"][key], root, key) for key in schema.get("required", [])}
    if expected_type == "array":
        prefix = schema.get("prefixItems", [])
        count = max(schema.get("minItems", 0), len(prefix))
        return [schema_sample(prefix[index], root, field) for index in range(min(count, len(prefix)))]
    if expected_type == "boolean":
        return False
    if expected_type == "integer":
        return schema.get("minimum", 0)
    if expected_type == "null":
        return None
    if expected_type == "string":
        if field == "canonical_root":
            return "/Data/CascadeProjects/.ab-owned-lab/s17-" + "1" * 40 + "-1-1-" + "2" * 64
        if field == "database_canonical_path":
            return "/Data/CascadeProjects/.ab-owned-lab/s17-" + "1" * 40 + "-1-1-" + "2" * 64 + "/state.sqlite3"
        if field == "database_relative_path" or field == "sqlite_database_relative_path":
            return "state.sqlite3"
        if field == "root_device_major_minor":
            return "1:1"
        if field == "mapped_s16_case_id":
            return "D00_CLEAN_COMMITTED_HEAD"
        if field == "mapped_s16_variant_id":
            return "CLEAN_COMMITTED_HEAD"
        pattern = schema.get("pattern", "")
        if pattern == "^[1-9][0-9]*$":
            return "1"
        if "{64}" in pattern:
            return "1" * 64
        if "{40}" in pattern:
            return "1" * 40
        if field in {"decision_issued_at_utc", "decision_expires_at_utc"}:
            return "2026-07-17T00:00:00Z"
        return "x"
    raise CheckFailure(f"cannot synthesize schema field: {field}")


def overlay_schema_constraints(value: Any, schema: dict[str, Any], root: dict[str, Any]) -> Any:
    if "$ref" in schema:
        value = overlay_schema_constraints(value, resolve_local_ref(root, schema["$ref"]), root)
    if "const" in schema:
        return copy.deepcopy(schema["const"])
    if schema.get("type") == "null":
        return None
    if type(value) is dict:
        for key, child_schema in schema.get("properties", {}).items():
            if key in value:
                value[key] = overlay_schema_constraints(value[key], child_schema, root)
    for item in schema.get("allOf", []):
        value = overlay_schema_constraints(value, item, root)
    return value


def require_all_false_or_zero(value: dict[str, Any], label: str) -> None:
    require(type(value) is dict, f"{label} must be an object")
    for key, item in value.items():
        if key == "side_effects_unlocked":
            require(item == "NONE", f"{label}.{key} must be NONE")
        elif type(item) is bool:
            require(item is False, f"{label}.{key} must be false")
        elif type(item) is int:
            require(item == 0, f"{label}.{key} must be zero")
        elif item is None:
            continue
        else:
            raise CheckFailure(f"unexpected nonzero/nonfalse field {label}.{key}")


def validate_schedule(schedule: dict[str, Any]) -> None:
    exact_keys(
        schedule,
        (
            "family_id_namespace",
            "family_count",
            "scenario_count_per_repetition",
            "repetition_start_inclusive",
            "repetition_end_inclusive",
            "repetition_count",
            "canary_repetition",
            "post_canary_repetitions_preregistered",
            "assigned_attempt_count",
            "planned_pidfd_sigkill_attempt_count",
            "planned_distinct_fresh_exec_read_count",
            "planned_d05_first_and_restart_phase_record_count",
            "planned_total_s16_mapping_phase_record_count",
            "actual_assigned_attempt_count",
            "actual_sigkill_attempt_count",
            "actual_fresh_process_read_count",
            "actual_s16_mapping_phase_record_count",
            "every_assigned_attempt_counts_toward_denominator",
            "retry_or_implicit_rerun_allowed",
            "rerun_requires_new_run_assignment_and_owner_decision",
            "families_outside_ol00_ol04_ol05_are_preregistered",
            "d05_read_quantum_bytes",
            "d05_data_step_count",
            "families",
        ),
        "plan.schedule",
    )
    expected_scalars = {
        "family_id_namespace": "OL00_OL04_OL05_FIRST_BATCH",
        "family_count": 3,
        "scenario_count_per_repetition": 60,
        "repetition_start_inclusive": 1,
        "repetition_end_inclusive": 1,
        "repetition_count": 1,
        "canary_repetition": 1,
        "post_canary_repetitions_preregistered": False,
        "assigned_attempt_count": 60,
        "planned_pidfd_sigkill_attempt_count": 59,
        "planned_distinct_fresh_exec_read_count": 59,
        "planned_d05_first_and_restart_phase_record_count": 106,
        "planned_total_s16_mapping_phase_record_count": 113,
        "actual_assigned_attempt_count": 0,
        "actual_sigkill_attempt_count": 0,
        "actual_fresh_process_read_count": 0,
        "actual_s16_mapping_phase_record_count": 0,
        "every_assigned_attempt_counts_toward_denominator": True,
        "retry_or_implicit_rerun_allowed": False,
        "rerun_requires_new_run_assignment_and_owner_decision": True,
        "families_outside_ol00_ol04_ol05_are_preregistered": False,
        "d05_read_quantum_bytes": 113,
        "d05_data_step_count": 49,
    }
    for key, expected in expected_scalars.items():
        require(type(schedule[key]) is type(expected) and schedule[key] == expected, f"schedule.{key} drift")
    require(schedule["families"] == EXPECTED_FAMILIES, "closed OL00/OL04/OL05 family order or variants drift")
    require(sum(item["scenario_count"] for item in schedule["families"]) == 60, "scenario sum drift")
    require(1 + 6 + 53 == schedule["assigned_attempt_count"], "attempt denominator arithmetic drift")
    require(6 + 53 == schedule["planned_pidfd_sigkill_attempt_count"], "SIGKILL arithmetic drift")
    require(53 * 2 == schedule["planned_d05_first_and_restart_phase_record_count"], "D05 phase arithmetic drift")
    require(1 + 6 + 53 * 2 == schedule["planned_total_s16_mapping_phase_record_count"], "mapping row arithmetic drift")


def validate_plan(plan: dict[str, Any]) -> None:
    exact_keys(
        plan,
        (
            "schema", "status", "decision", "purpose", "baseline", "s16_bindings",
            "authorization_boundary", "claim_ceiling", "candidate_lab_profile", "schedule",
            "classification_contract", "current_accounting", "global_runtime_prerequisites", "nonclaims",
        ),
        "plan",
    )
    require(plan["schema"] == "agent_bridge.memory_temporal_recovered_envelope_owned_lab_process_crash_restart_plan_s17.v0", "plan schema drift")
    require(plan["status"] == STATUS and plan["decision"] == DECISION, "plan state drift")
    require(plan["purpose"] == "PREREGISTER_ONE_60_ATTEMPT_L1_OWNED_LAB_OL00_OL04_OL05_CANARY_BATCH_WITHOUT_EXECUTION_OR_AUTHORITY", "plan purpose drift")
    baseline = dict(BASELINE)
    baseline["source_parent_role"] = "EXACT_LOCAL_MASTER_BASELINE_AT_PREREGISTRATION"
    require(plan["baseline"] == baseline, "plan baseline drift")
    require(plan["s16_bindings"] == S16_BINDINGS, "frozen S16 bindings drift")

    auth = plan["authorization_boundary"]
    require(auth["owner_resource_decision_schema"] == "agent_bridge.memory_temporal_recovered_envelope_owned_lab_owner_resource_decision_s17.v0", "owner schema identity drift")
    require(auth["owner_resource_decision_sha256"] is None, "owner decision digest must be absent")
    for key in (
        "authenticated_owner_identity_bound", "owner_resource_decision_recorded",
        "owned_lab_execution_authorized", "production_execution_authorized",
        "provider_execution_authorized", "feature_flag_is_authorization",
        "preregistration_is_execution_authority", "positive_decision_in_this_plan",
    ):
        require(auth[key] is False, f"plan authorization unexpectedly enabled: {key}")
    require(auth["positive_owner_decision_admissible_in_v0_schema"] is False, "plan v0 admits positive owner decision")
    require(auth["cross_field_semantic_and_signature_validator_implemented"] is False, "plan claims semantic/signature validator")
    require(auth["side_effects_unlocked"] == "NONE", "plan side effect drift")

    ceiling = plan["claim_ceiling"]
    require(ceiling["level"] == CLAIM_LEVEL, "plan claim level drift")
    require(ceiling["current_claim"] == "PREREGISTRATION_ONLY_NO_RUNTIME_EVIDENCE", "current claim drift")
    for key, value in ceiling.items():
        if type(value) is bool and (key.endswith("_observed") or key.endswith("_proved")):
            require(value is False, f"plan claim unexpectedly proved: {key}")

    profile = plan["candidate_lab_profile"]
    require(profile["candidate_root"] == "/Data/CascadeProjects/.ab-owned-lab", "candidate root drift")
    require(profile["candidate_filesystem"] == "f2fs", "candidate filesystem drift")
    require(profile["candidate_values_are_authority"] is False and profile["must_recheck_and_bind_at_decision"] is True, "candidate facts became authority")
    for key in (
        "network_allowed", "provider_endpoint_allowed", "credential_access_allowed",
        "paid_resource_allowed", "root_privilege_allowed", "mount_or_unmount_allowed",
        "drop_caches_allowed", "reboot_allowed", "block_device_mutation_allowed",
    ):
        require(profile[key] is False, f"forbidden lab capability enabled: {key}")

    process = profile["process_control"]
    require(process["controller_is_distinct_process"] is True, "controller separation drift")
    require(process["cut_channel"] == "INHERITED_ANONYMOUS_PIPE_RUN_BOUND_FRAMES_ONLY", "cut channel drift")
    require(process["cut_ready_marker_persistence_allowed"] is False, "persisted cut marker enabled")
    require(process["pidfd_open_required_before_cut"] is True, "pidfd open no longer required")
    require(process["pidfd_identity_recheck_required_before_signal"] is True, "pidfd identity recheck no longer required")
    require(process["kill_api"] == "PIDFD_SEND_SIGNAL_SIGKILL", "kill API drift")
    require(process["numeric_pid_signal_fallback_allowed"] is False, "numeric PID fallback enabled")
    require(process["pidfd_unavailable_policy"] == "FAIL_CLOSED_NO_OBSERVATION", "pidfd unavailable policy drift")
    require(process["child_descendants_allowed"] is False, "child descendants enabled")
    require(process["death_confirmed_before_fresh_exec"] is True, "death-before-restart ordering drift")
    require(process["fresh_exec_distinct_pid_start_token_and_nonce_required"] is True, "fresh exec identity weakened")
    require(process["inherited_target_fd_shared_memory_adapter_sink_cursor_or_cache_allowed"] is False, "state inheritance enabled")

    isolation = profile["path_isolation"]
    require(isolation["root_creation"] == "CREATE_NEW_MODE_0700", "root creation drift")
    require(isolation["per_run_root_template"] == "/Data/CascadeProjects/.ab-owned-lab/s17-<source-commit>-<controller-pid>-<monotonic-counter>-<random-nonce-sha256>", "per-run root template drift")
    require(isolation["preexisting_run_root_allowed"] is False, "preexisting root enabled")
    require(isolation["nofollow_required_for_every_component_and_leaf"] is True, "nofollow weakened")
    require(isolation["symlink_hardlink_or_path_alias_allowed"] is False, "path alias enabled")
    require(isolation["cleanup_outside_exact_run_root_allowed"] is False, "cleanup scope widened")

    backend = profile["durable_backend"]
    require(backend["engine"] == "SQLITE", "backend drift")
    require(backend["journal_mode"] == "DELETE" and backend["synchronous"] == "EXTRA", "SQLite durability profile drift")
    require(backend["restart_reopen_mode"] == "READ_WRITE_WITHOUT_CREATE", "restart may create database")
    for key in (
        "sqlite_profile_sha256_binding", "sqlite_schema_sha256_binding",
        "sqlite_application_id_binding", "sqlite_user_version_binding",
        "classifier_and_expected_oracle_binding",
    ):
        require(backend[key] == "REQUIRED_IN_SEPARATE_OWNER_RESOURCE_DECISION", f"future exact binding weakened: {key}")
    require(backend["database_file_fsync_required"] is True, "database fsync weakened")
    require(backend["parent_directory_fsync_required_after_create_commit_and_cleanup"] is True, "directory fsync weakened")
    require(backend["wal_mode_allowed"] is False and backend["memory_or_tmpfs_database_allowed"] is False, "ineligible backend enabled")
    require(backend["implicit_recovery_repairs_or_recreates_missing_database"] is False, "implicit repair enabled")

    limits = profile["resource_limits"]
    expected_limits = {
        "maximum_active_assigned_attempts": 1,
        "maximum_controller_processes": 1,
        "maximum_child_processes": 1,
        "maximum_tasks": 16,
        "maximum_open_files": 256,
        "memory_max_bytes": 805306368,
        "swap_max_bytes": 268435456,
        "disk_max_bytes": 268435456,
        "build_jobs": 1,
        "cut_ready_timeout_seconds": 10,
        "pidfd_signal_timeout_seconds": 10,
        "death_confirmation_timeout_seconds": 10,
        "fresh_exec_timeout_seconds": 20,
        "attempt_timeout_seconds": 60,
        "batch_timeout_seconds": 900,
        "proposed_cost_ceiling_usd": 0,
    }
    for key, expected in expected_limits.items():
        require(type(limits[key]) is int and limits[key] == expected, f"resource limit drift: {key}")
    require(limits["oom_event_invalidates_attempt"] is True, "OOM attempt invalidation weakened")
    require(limits["any_oom_event_invalidates_entire_batch"] is True, "OOM batch invalidation weakened")
    require(limits["nested_cargo_allowed"] is False, "nested Cargo enabled")
    require(limits["timeout_or_leaked_child_invalidates_entire_batch"] is True, "timeout/leak batch invalidation weakened")

    validate_schedule(plan["schedule"])
    classification = plan["classification_contract"]
    require(classification["planned_family_or_variant_is_outcome_oracle"] is False, "planned label became oracle")
    require(classification["classification_is_derived_from_raw_observed_state"] is True, "raw-state classification weakened")
    require(classification["phase_raw_measurement_binds_retained_raw_event_frame"] is True, "phase raw-frame binding weakened")
    require(classification["phase_raw_measurement_uses_null_for_absent_hashes"] is True, "raw absent hash semantics weakened")
    require(classification["ack_payload_present_if_and_only_if_ack_observed"] is True, "ack payload presence semantics weakened")
    require(classification["s16_absent_sentinels_and_zero_evidence_counters_exist_only_in_virtual_projection"] is True, "S16 virtual projection boundary weakened")
    require(classification["s16_virtual_projection_must_be_recomputed_from_raw_phase_measurement"] is True, "S16 projection derivation weakened")
    require(classification["phase_lifecycle_inputs_include_restart_cut_data_steps_length_and_adapter_state"] is True, "phase lifecycle inputs weakened")
    require(classification["classification_searches_full_5639_row_s16_catalog"] is True, "classification catalog scope narrowed")
    require(classification["assignment_family_case_or_variant_prefilter_allowed"] is False, "assignment label prefilter enabled")
    require(classification["offline_full_catalog_uniqueness_kat"] == {
        "catalog_row_count": 5639,
        "full_catalog_unique_fingerprint_count": 5639,
        "full_catalog_duplicate_fingerprint_count": 0,
        "full_catalog_maximum_fingerprint_multiplicity": 1,
        "target_phase_count": 113,
        "unique_match_count": 113,
        "zero_match_count": 0,
        "multiple_match_count": 0,
        "observable_s16_row_field_count": 17,
        "lifecycle_evaluator_field_count": 3,
        "augmented_catalog_fingerprint_field_count": 20,
        "ack_payload_binding_is_separate_from_uniqueness_fingerprint": True,
        "lifecycle_evaluator_fields": ["restarted_after_crash", "observed_data_steps", "observed_len"],
        "planned_family_case_or_variant_used_as_prefilter": False,
        "known_pre_lifecycle_ambiguity": "D04_CRASH_AFTER_OBJECT_PREFIX_RESTART_VS_D01_PREFIX_CUT_2747",
        "ambiguity_resolution": "OBSERVED_RESTARTED_AFTER_CRASH",
    }, "offline full-catalog uniqueness KAT drift")
    require(classification["classification_input_and_phase_record_hash_frames_are_domain_separated"] is True, "phase hash domain separation weakened")
    require(classification["schema_conformance_alone_proves_cross_field_identity"] is False, "schema conformance became cross-field proof")
    require(classification["cross_field_semantic_validator_required_before_eligibility"] is True, "cross-field validator no longer required")
    require(classification["cross_field_semantic_validator_implemented"] is False, "cross-field validator falsely implemented")
    require(classification["unknown_or_nonunique_mapping"] == "OBSERVED_OUT_OF_MODEL_INDETERMINATE", "unknown mapping drift")
    require(classification["unknown_mapping_unlocks_execution_or_side_effect"] is False, "unknown mapping unlocks effect")
    require(classification["s16_nonzero_evidence_count_rejection_is_preserved"] is True, "S16 evidence boundary weakened")
    require(classification["latest_list_range_retry_cache_repair_or_replica_switch_allowed"] is False, "hidden fallback enabled")

    require_all_false_or_zero(plan["current_accounting"], "plan.current_accounting")
    global_boundary = plan["global_runtime_prerequisites"]
    require(global_boundary == {
        "total": 16, "satisfied": 0, "missing": 16,
        "owned_lab_scoped_decision_can_mark_global_prerequisite_satisfied": False,
        "global_runtime_admission_ready": False,
        "global_runtime_admission_granted": False,
    }, "global runtime boundary drift")
    require_all_false_or_zero(plan["nonclaims"], "plan.nonclaims")


def validate_schema_envelope(schema: dict[str, Any], expected_id: str, label: str) -> None:
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{label} draft drift")
    require(schema.get("$id") == expected_id, f"{label} id drift")
    require(schema.get("type") == "object", f"{label} root type drift")
    require(schema.get("additionalProperties") is False, f"{label} root is not closed")
    require(type(schema.get("required")) is list and type(schema.get("properties")) is dict, f"{label} root shape drift")
    require(set(schema["required"]) == set(schema["properties"]), f"{label} optional root field drift")
    require(type(schema.get("$defs")) is dict, f"{label} definitions missing")
    validate_local_refs(schema, label)


def require_tokens(value: dict[str, Any], required: Iterable[str], label: str) -> None:
    tokens = all_tokens(value)
    missing = sorted(set(required) - tokens)
    require(not missing, f"{label} required closed-world tokens missing: {missing}")


def classification_input_frame(observation: dict[str, Any], phase: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_packet_sha256": observation["identity"]["raw_packet_sha256"],
        "assignment_id": observation["identity"]["assignment_id"],
        "phase_ordinal": phase["phase_ordinal"],
        "phase_kind": phase["phase_kind"],
        "process_identity_sha256": phase["process_identity_sha256"],
        "raw_phase_measurement": phase["raw_phase_measurement"],
        "s16_virtual_projection": phase["s16_virtual_projection"],
    }


def recompute_classification_input_sha256(observation: dict[str, Any], phase: dict[str, Any]) -> str:
    return domain_separated_jcs_sha256(
        "agent_bridge.s17.owned_lab.classification_input.v0",
        classification_input_frame(observation, phase),
    )


def recompute_phase_record_sha256(phase: dict[str, Any]) -> str:
    frame = copy.deepcopy(phase)
    frame.pop("phase_record_sha256", None)
    return domain_separated_jcs_sha256(
        "agent_bridge.s17.owned_lab.mapping_phase_record.v0",
        frame,
    )


def phase_hashes_valid(observation: dict[str, Any]) -> bool:
    for phase in observation["mapping_phase_records"]:
        if phase["classification_input_sha256"] != recompute_classification_input_sha256(observation, phase):
            return False
        if phase["phase_record_sha256"] != recompute_phase_record_sha256(phase):
            return False
    return True


def json_row_value(value: Any) -> Any:
    return value.hex() if type(value) is bytes else value


def virtual_projection_from_row(schema: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    projection = schema_sample(schema["$defs"]["s16_virtual_projection"], schema)
    for field in OBSERVABLE_S16_ROW_FIELDS:
        projection[field] = json_row_value(row[field])
    restarted, steps, observed_len = lifecycle_extra(row)
    projection.update({
        "restarted_after_crash": restarted,
        "observed_data_steps": steps,
        "observed_len": observed_len,
    })
    projection["ack_receipt_sha256"], projection["ack_witness_sha256"] = ack_payload_extra(row)
    return projection


def raw_measurement_from_row(schema: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    raw = schema_sample(schema["$defs"]["phase_raw_measurement"], schema)
    raw.update({
        "publisher_phase": row["publisher_phase"],
        "object_state": row["object_persistence"],
        "object_len": row["object_len"],
        "object_sha256": None if row["object_persistence"] == "ABSENT" else json_row_value(row["observed_object_sha256"]),
        "receipt_state": row["receipt_state"],
        "computed_receipt_sha256": None if row["receipt_state"] == "ABSENT" else json_row_value(row["computed_receipt_sha256"]),
        "stored_receipt_sha256": None if row["receipt_state"] == "ABSENT" else json_row_value(row["stored_receipt_sha256"]),
        "witness_state": row["witness_state"],
        "computed_witness_sha256": None if row["witness_state"] == "ABSENT" else json_row_value(row["computed_witness_sha256"]),
        "stored_witness_sha256": None if row["witness_state"] == "ABSENT" else json_row_value(row["stored_witness_sha256"]),
        "selected_view_state": "PRESENT" if row["witness_state"] == "PRESENT" else "ABSENT",
        "selected_view_sha256": json_row_value(row["selected_view_sha256"]) if row["witness_state"] == "PRESENT" else None,
        "competing_view_state": "ABSENT",
        "competing_view_sha256": None,
        "ack_state": row["ack_state"],
        "crash_cut": row["crash_cut"],
        "crash_cut_index": row["crash_cut_index"],
        "adapter_pre_state": row["adapter_pre_state"],
        "adapter_post_state": row["adapter_post_state"],
    })
    raw["restarted_after_crash"], raw["observed_data_steps"], raw["observed_len"] = lifecycle_extra(row)
    raw["ack_receipt_sha256"], raw["ack_witness_sha256"] = ack_payload_extra(row)
    return raw


def projection_matches_raw(
    raw: dict[str, Any], projection: dict[str, Any], sentinels: dict[str, str],
) -> bool:
    expected = {
        "publisher_phase": raw["publisher_phase"],
        "object_persistence": raw["object_state"],
        "object_len": raw["object_len"],
        "observed_object_sha256": raw["object_sha256"] or sentinels["OBJECT"],
        "receipt_state": raw["receipt_state"],
        "computed_receipt_sha256": raw["computed_receipt_sha256"] or sentinels["RECEIPT"],
        "stored_receipt_sha256": raw["stored_receipt_sha256"] or sentinels["RECEIPT"],
        "witness_state": raw["witness_state"],
        "computed_witness_sha256": raw["computed_witness_sha256"] or sentinels["WITNESS"],
        "stored_witness_sha256": raw["stored_witness_sha256"] or sentinels["WITNESS"],
        "selected_view_sha256": raw["selected_view_sha256"] or sentinels["REPLICA_VIEW"],
        "competing_view_sha256": raw["competing_view_sha256"] or sentinels["REPLICA_VIEW"],
        "ack_state": raw["ack_state"],
        "crash_cut": raw["crash_cut"],
        "crash_cut_index": raw["crash_cut_index"],
        "adapter_pre_state": raw["adapter_pre_state"],
        "adapter_post_state": raw["adapter_post_state"],
        "restarted_after_crash": raw["restarted_after_crash"],
        "observed_data_steps": raw["observed_data_steps"],
        "observed_len": raw["observed_len"],
        "ack_receipt_sha256": raw["ack_receipt_sha256"],
        "ack_witness_sha256": raw["ack_witness_sha256"],
    }
    if any(projection.get(field) != value for field, value in expected.items()):
        return False
    return (
        projection["projection_kind"] == "FROZEN_S16_EVALUATOR_INPUT_V0"
        and projection["external_durability_observation_count"] == 0
        and projection["provider_durability_observation_count"] == 0
        and projection["owned_lab_durability_observation_count"] == 0
        and projection["side_effects_unlocked"] == "NONE"
    )


def assignment_matches_recomputed_classification(observation: dict[str, Any]) -> bool:
    assignment = observation["assignment"]
    family_id = assignment["owned_lab_family_id"]
    mapped = [
        (phase["classification"]["mapped_s16_case_id"], phase["classification"]["mapped_s16_variant_id"])
        for phase in observation["mapping_phase_records"]
    ]
    if family_id == "OL00":
        expected = [("D00_CLEAN_COMMITTED_HEAD", "CLEAN")]
    elif family_id == "OL04":
        expected = [("D04_PUBLISH_CRASH_RESTART_CUTS", assignment["planned_variant_id"])]
    elif family_id == "OL05":
        planned = assignment["planned_variant_id"]
        expected = [
            ("D05_S15_READ_CRASH_RESTART_CUTS", f"{planned}_FIRST_ATTEMPT"),
            ("D05_S15_READ_CRASH_RESTART_CUTS", f"{planned}_RESTART"),
        ]
    else:
        return False
    return assignment["planned_s16_case_id"] == expected[0][0] and mapped == expected


def every_phase_durable_image_matches_top_level(observation: dict[str, Any]) -> bool:
    top = observation["raw_recovered_state"]
    for phase in observation["mapping_phase_records"]:
        raw = phase["raw_phase_measurement"]
        expected = {
            "object_state": raw["object_state"],
            "object_len": raw["object_len"],
            "object_sha256": raw["object_sha256"],
            "receipt_state": raw["receipt_state"],
            "receipt_sha256": raw["stored_receipt_sha256"],
            "witness_state": raw["witness_state"],
            "witness_sha256": raw["stored_witness_sha256"],
            "selected_view_state": raw["selected_view_state"],
            "selected_view_sha256": raw["selected_view_sha256"],
            "competing_view_state": raw["competing_view_state"],
            "competing_view_sha256": raw["competing_view_sha256"],
        }
        if any(top[field] != value for field, value in expected.items()):
            return False
    return True


def build_classification_sample(schema: dict[str, Any], row: dict[str, Any], row_sha256: str) -> dict[str, Any]:
    value = schema_sample(schema["$defs"]["classification"], schema)
    value["mapping_cardinality"] = 1
    value["mapped_s16_case_id"] = row["case_id"]
    value["mapped_s16_variant_id"] = row["variant_id"]
    value["mapped_s16_row_sha256"] = row_sha256
    value["mapped_reason"] = row["reason"]
    value["mapped_failure"] = row["mapped_s15_failure"]
    value["mapping_status"] = "UNIQUE_FROZEN_S16_REFERENCE"
    return value


def build_phase_sample(
    schema: dict[str, Any], ordinal: int, kind: str, process_identity: str,
    kat_row: dict[str, Any],
) -> dict[str, Any]:
    value = schema_sample(schema["$defs"]["mapping_phase_record"], schema)
    value["phase_ordinal"] = ordinal
    value["phase_kind"] = kind
    value["process_identity_sha256"] = process_identity
    row = kat_row["row"]
    raw = raw_measurement_from_row(schema, row)
    raw["raw_event_frame_index"] = ordinal - 1
    raw["raw_event_frame_offset_bytes"] = (ordinal - 1) * 4096
    raw["raw_event_frame_length_bytes"] = 4096
    value["raw_phase_measurement"] = raw
    value["s16_virtual_projection"] = virtual_projection_from_row(schema, row)
    value["classification"] = build_classification_sample(schema, row, kat_row["row_sha256"])
    return value


def build_observation_sample(schema: dict[str, Any], family_id: str, kat_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    families = {item["owned_lab_family_id"]: item for item in EXPECTED_FAMILIES}
    family = families[family_id]
    variant = family["variants"][0]
    value = schema_sample(schema, schema)
    value["assignment"].update({
        "owned_lab_family_id": family_id,
        "planned_s16_case_id": family["s16_case_id"],
        "planned_variant_id": variant,
        "read_quantum_bytes": 113 if family_id == "OL05" else None,
    })
    sqlite = value["storage_environment"]["sqlite_runtime_profile"]
    sqlite["database_fsync_attempted_before_kill"] = True
    sqlite["database_fsync_return_code"] = 0
    sqlite["parent_directory_fsync_attempted_before_kill"] = True
    sqlite["parent_directory_fsync_return_code"] = 0
    raw = value["raw_recovered_state"]
    raw.update({
        "write_sync_receipt_state": "ABSENT",
        "write_sync_receipt_sha256": None,
        "object_state": "ABSENT",
        "object_len": 0,
        "object_sha256": None,
        "receipt_state": "ABSENT",
        "receipt_sha256": None,
        "witness_state": "ABSENT",
        "witness_sha256": None,
        "selected_view_state": "ABSENT",
        "selected_view_sha256": None,
        "competing_view_state": "ABSENT",
        "competing_view_sha256": None,
    })
    value["custody"]["custody_sequence"] = 1
    value["custody"]["previous_custody_entry_sha256"] = None
    raw_packet_sha256 = value["identity"]["raw_packet_sha256"]
    initial_process = value["crash_observation"]["child_process_identity_sha256"]
    if family_id == "OL00":
        value["crash_observation"] = overlay_schema_constraints(
            value["crash_observation"], schema["$defs"]["control_process_observation_constraints"], schema
        )
        value["restart_observation"] = None
        value["mapping_phase_records"] = [
            build_phase_sample(schema, 1, "ATTEMPT_RESULT", initial_process, kat_rows["OL00"])
        ]
        value["accounting"]["owned_lab_process_sigkill_observation_count"] = 0
        value["accounting"]["owned_lab_fresh_process_restart_observation_count"] = 0
        value["accounting"]["s16_mapping_phase_record_count"] = 1
    else:
        value["crash_observation"] = overlay_schema_constraints(
            value["crash_observation"], schema["$defs"]["pidfd_sigkill_observation_constraints"], schema
        )
        restart = schema_sample(schema["$defs"]["restart_observation"], schema)
        restart["observed_record_len"] = 1
        restart["observed_record_sha256"] = "c" * 64
        value["restart_observation"] = restart
        fresh_process = restart["fresh_child_process_identity_sha256"]
        if family_id == "OL04":
            value["mapping_phase_records"] = [
                build_phase_sample(schema, 1, "ATTEMPT_RESULT", fresh_process, kat_rows["OL04"])
            ]
            value["accounting"]["s16_mapping_phase_record_count"] = 1
        else:
            value["mapping_phase_records"] = [
                build_phase_sample(schema, 1, "FIRST_ATTEMPT", initial_process, kat_rows["OL05_FIRST"]),
                build_phase_sample(schema, 2, "RESTART", fresh_process, kat_rows["OL05_RESTART"]),
            ]
            value["accounting"]["s16_mapping_phase_record_count"] = 2
        value["accounting"]["owned_lab_process_sigkill_observation_count"] = 1
        value["accounting"]["owned_lab_fresh_process_restart_observation_count"] = 1
    for phase in value["mapping_phase_records"]:
        phase["raw_phase_measurement"]["retained_raw_event_stream_sha256"] = raw_packet_sha256
        phase["classification"]["classifier_build_sha256"] = value["frozen_bindings"]["classifier_binary_sha256"]
        phase["classification_input_sha256"] = recompute_classification_input_sha256(value, phase)
        phase["phase_record_sha256"] = recompute_phase_record_sha256(phase)
    recovered = value["mapping_phase_records"][-1]["raw_phase_measurement"]
    value["raw_recovered_state"].update({
        "object_state": recovered["object_state"],
        "object_len": recovered["object_len"],
        "object_sha256": recovered["object_sha256"],
        "receipt_state": recovered["receipt_state"],
        "receipt_sha256": recovered["stored_receipt_sha256"],
        "witness_state": recovered["witness_state"],
        "witness_sha256": recovered["stored_witness_sha256"],
        "selected_view_state": recovered["selected_view_state"],
        "selected_view_sha256": recovered["selected_view_sha256"],
        "competing_view_state": recovered["competing_view_state"],
        "competing_view_sha256": recovered["competing_view_sha256"],
    })
    return value


def build_owner_sample(schema: dict[str, Any], state: str) -> dict[str, Any]:
    value = schema_sample(schema, schema)
    value["decision_state"] = state
    value["decision_reason"] = (
        "WAITING_FOR_AUTHENTICATED_OWNER_RESOURCE_BINDING"
        if state == "PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING"
        else "OWNER_AUTHENTICATION_FAILED"
    )
    value["owner"].update({
        "identity_authenticated": False,
        "decision_recorded": False,
        "owner_identity_sha256": None,
        "owner_key_id": None,
        "owner_signature_sha256": None,
        "decision_issued_at_utc": None,
        "decision_expires_at_utc": None,
    })
    value["execution_scope"]["owned_lab_execution_authorized"] = False
    value["execution_scope"]["single_use_execution_capability_issued"] = False
    safety = value["safety_and_custody"]
    for field in ("trusted_time_bound", "single_use_replay_cas_ready", "stop_controls_ready", "custody_and_retention_ready", "independent_review_approved"):
        safety[field] = False
    for field in ("trusted_time_receipt_sha256", "single_use_replay_cas_receipt_sha256", "stop_control_sha256", "stop_receipt_sha256", "retention_policy_sha256", "cleanup_policy_sha256", "cleanup_receipt_sha256", "reviewer_receipt_sha256"):
        safety[field] = None
    value["authorization_receipt"] = None
    return value


def validate_observation_schema(schema: dict[str, Any], kat_rows: dict[str, dict[str, Any]]) -> None:
    validate_schema_envelope(
        schema,
        "agent_bridge.memory_temporal_recovered_envelope_owned_lab_process_crash_restart_observation_s17.v0",
        "observation schema",
    )
    validate_schema_keywords(schema, "observation schema")
    require(
        canonical_json_sha256(schema) == EXPECTED_OBSERVATION_SCHEMA_CANONICAL_SHA256,
        "observation schema canonical JSON structure commitment drift",
    )
    validate_closed_object_required_graph(schema, "observation schema")
    require_tokens(
        schema,
        (
            "AUTHENTICATED_OWNED_LAB_RUNTIME_OBSERVATION",
            "OWNED_LAB_OBSERVED_RUNTIME",
            CLAIM_LEVEL,
            CLAIM_CEILING,
            "OL00", "OL04", "OL05",
            "NONE_CONTROL",
            "CONTROLLER_PIDFD_SEND_SIGNAL_SIGKILL",
            "SIGKILL", "SIGNALED", "NEW_EXEC",
            "ANONYMOUS_PIPE", "OBSERVED_OUT_OF_MODEL_INDETERMINATE",
            "pidfd_open_succeeded", "pidfd_target_pid", "pidfd_target_start_identity",
            "pidfd_target_matches_child", "pidfd_send_signal_return_code",
            "pidfd_send_signal_errno", "signal_sender_pid", "signal_sender_start_identity",
            "signal_sender_matches_controller", "child_descendant_count_before_kill",
            "pidfd_became_readable", "child_reaped", "observed_exit_signal_number",
            "post_reap_original_proc_identity_present",
            "fresh_exec_image_sha256", "fresh_pid_and_start_identity_distinct_from_initial_child",
            "target_fds_closed_before_exec", "fresh_process_reaped", "fresh_process_exit_status",
            "root_created_exclusively", "root_mode_octal", "database_mode_octal",
            "root_symlink_observed", "database_symlink_observed",
            "database_hardlink_count", "root_device_major_minor", "root_mount_id",
            "mountinfo_entry_before_sha256", "mountinfo_entry_after_sha256",
            "filesystem_verified_from_mountinfo", "persistent_filesystem_verified",
            "tmpfs_overlay_or_fuse_detected",
            "boot_id_before_sha256", "boot_id_after_sha256", "same_boot_verified",
            "DELETE", "EXTRA", "normal_reopen_may_create", "quick_check_result",
            "database_fsync_return_code", "parent_directory_fsync_return_code",
            "cut_ready_channel", "cut_ready_persisted_before_kill",
            "independent_failure_domain_proved",
            "process_restart_is_host_or_power_loss_proof", "storage_device_durability_proved",
            "provider_linearizability_or_quorum_proved", "rollback_resistance_proved",
            "equivocation_or_split_brain_resistance_proved", "production_readiness_proved",
            "trusted_time_obtained", "canonical_payload_excludes_identity_and_custody",
            "retained_raw_event_frame_hash_scope", "classification_input_domain_separator",
            "classification_input_hash_scope", "classification_input_frame_fields",
            "classification_input_frame_encoding",
            "phase_record_domain_separator", "phase_record_hash_scope",
            "phase_record_self_hash_excluded", "raw_phase_measurement",
            "restarted_after_crash", "observed_data_steps", "observed_len",
            "adapter_pre_state", "adapter_post_state",
            "RAW_EVENT_FRAME_BYTE_RANGE_HASH_RECOMPUTED_FROM_RETAINED_RAW_PACKET",
            "CLASSIFICATION_INPUT_SHA256_RECOMPUTED_FROM_DOMAIN_AND_EXACT_FRAME",
            "PHASE_RECORD_SHA256_RECOMPUTED_WITH_SELF_HASH_OMITTED",
            "CLASSIFIER_BUILD_EQUALS_FROZEN_CLASSIFIER_BINARY_AND_OWNER_RECEIPT",
        ),
        "observation schema",
    )
    defs = schema["$defs"]
    for name in (
        "hashing_contract", "semantic_validation_contract", "identity", "frozen_bindings",
        "authorization", "assignment", "storage_environment", "sqlite_runtime_profile",
        "crash_observation", "restart_observation", "raw_recovered_state",
        "phase_raw_measurement", "s16_virtual_projection", "mapping_phase_record", "classification",
        "accounting", "custody", "nonclaims",
    ):
        require(name in defs, f"observation schema definition missing: {name}")
        definition = defs[name]
        require(definition.get("type") == "object", f"observation definition type drift: {name}")
        require(definition.get("additionalProperties") is False, f"observation definition is open: {name}")
    require(type(schema.get("allOf")) is list and len(schema["allOf"]) == 3, "observation family conditionals missing")
    root_rules: dict[str, dict[str, Any]] = {}
    for rule in schema["allOf"]:
        try:
            family = rule["if"]["properties"]["assignment"]["properties"]["owned_lab_family_id"]["const"]
            require(rule["if"]["properties"]["assignment"]["required"] == ["owned_lab_family_id"], "root family nested required drift")
            require(rule["if"]["required"] == ["assignment"], "root family required drift")
            require(family not in root_rules, "duplicate root family condition")
            root_rules[family] = rule["then"]["properties"]
        except (KeyError, TypeError) as exc:
            raise CheckFailure("malformed root family conditional") from exc
    require(set(root_rules) == {"OL00", "OL04", "OL05"}, "root family conditional set drift")
    expected_root_semantics = {
        "OL00": ("#/$defs/control_process_observation_constraints", "null", "#/$defs/single_mapping_phase_record", 1, 0, 0),
        "OL04": ("#/$defs/pidfd_sigkill_observation_constraints", "ref", "#/$defs/single_mapping_phase_record", 1, 1, 1),
        "OL05": ("#/$defs/pidfd_sigkill_observation_constraints", "ref", "#/$defs/first_attempt_mapping_phase_record", 2, 1, 1),
    }
    for family, (crash_ref, restart_kind, first_phase_ref, phase_count, kill_count, restart_count) in expected_root_semantics.items():
        then = root_rules[family]
        require(then["crash_observation"].get("$ref") == crash_ref, f"{family} crash constraint drift")
        if restart_kind == "null":
            require(then["restart_observation"] == {"type": "null"}, f"{family} restart must be null")
        else:
            require(then["restart_observation"].get("$ref") == "#/$defs/restart_observation", f"{family} fresh restart constraint drift")
        phases = then["mapping_phase_records"]
        require(phases.get("minItems") == phase_count and phases.get("maxItems") == phase_count and phases.get("items") is False, f"{family} phase cardinality drift")
        require(phases.get("prefixItems", [])[0].get("$ref") == first_phase_ref, f"{family} first phase drift")
        if family == "OL05":
            require(len(phases["prefixItems"]) == 2 and phases["prefixItems"][1].get("$ref") == "#/$defs/restart_mapping_phase_record", "OL05 restart phase drift")
        else:
            require(len(phases["prefixItems"]) == 1, f"{family} extra phase")
        accounting = then["accounting"]["properties"]
        require(accounting["owned_lab_process_sigkill_observation_count"].get("const") == kill_count, f"{family} kill accounting drift")
        require(accounting["owned_lab_fresh_process_restart_observation_count"].get("const") == restart_count, f"{family} restart accounting drift")
        require(accounting["s16_mapping_phase_record_count"].get("const") == phase_count, f"{family} phase accounting drift")
    assignment = defs["assignment"]
    require(len(assignment.get("allOf", [])) == 3, "observation assignment family conditionals drift")
    assignment_rules: dict[str, dict[str, Any]] = {}
    for rule in assignment["allOf"]:
        try:
            family = rule["if"]["properties"]["owned_lab_family_id"]["const"]
            require(rule["if"]["required"] == ["owned_lab_family_id"], "assignment family required drift")
            assignment_rules[family] = rule["then"]["properties"]
        except (KeyError, TypeError) as exc:
            raise CheckFailure("malformed assignment family conditional") from exc
    require(set(assignment_rules) == {"OL00", "OL04", "OL05"}, "assignment family conditional set drift")
    for family in EXPECTED_FAMILIES:
        family_id = family["owned_lab_family_id"]
        rule = assignment_rules[family_id]
        require(rule["planned_s16_case_id"].get("const") == family["s16_case_id"], f"{family_id} case binding drift")
        variant_schema = rule["planned_variant_id"]
        actual_variants = [variant_schema["const"]] if "const" in variant_schema else variant_schema.get("enum")
        require(actual_variants == family["variants"], f"{family_id} variant set/order drift")
        if family_id == "OL05":
            require(rule["read_quantum_bytes"].get("const") == 113, "OL05 read quantum drift")
        else:
            require(rule["read_quantum_bytes"].get("type") == "null", f"{family_id} read quantum must be null")
    pidfd = defs["pidfd_sigkill_observation_constraints"]["properties"]
    expected_pidfd_constants = {
        "kill_method": "CONTROLLER_PIDFD_SEND_SIGNAL_SIGKILL",
        "pidfd_open_succeeded": True,
        "pidfd_target_matches_child": True,
        "kill_target_identity_rechecked": True,
        "pidfd_send_signal_return_code": 0,
        "signal_sender_matches_controller": True,
        "child_descendant_count_before_kill": 0,
        "pidfd_became_readable": True,
        "wait_status_kind": "SIGNALED",
        "terminating_signal": "SIGKILL",
        "observed_exit_signal_number": 9,
        "child_reaped": True,
        "post_reap_original_proc_identity_present": False,
        "graceful_exit_observed": False,
        "process_crash_observed": True,
    }
    for field, expected in expected_pidfd_constants.items():
        require(pidfd.get(field, {}).get("const") == expected, f"pidfd crash constraint drift: {field}")
    control = defs["control_process_observation_constraints"]["properties"]
    require(control["kill_method"].get("const") == "NONE_CONTROL", "control kill method drift")
    require(control["process_crash_observed"].get("const") is False, "control became crash")
    require(control["graceful_exit_observed"].get("const") is True, "control graceful exit drift")
    restart = defs["restart_observation"]["properties"]
    for field, expected in {
        "fresh_process_started": True,
        "spawn_method": "NEW_EXEC",
        "fresh_exec_image_matches_frozen_runner": True,
        "fresh_pid_and_start_identity_distinct_from_initial_child": True,
        "fresh_process_nonce_distinct_from_initial_child": True,
        "same_process_reused": False,
        "same_boot_verified": True,
        "target_fds_closed_before_exec": True,
        "inherited_target_file_descriptor_used": False,
        "inherited_adapter_sink_or_cache_used": False,
        "exact_path_reopened": True,
        "fresh_process_reaped": True,
        "fresh_process_exit_status": "CLEAN_EXIT_ZERO",
    }.items():
        require(restart.get(field, {}).get("const") == expected, f"fresh-exec constraint drift: {field}")
    require("child_process_nonce_sha256" in defs["crash_observation"]["required"], "initial child nonce missing")
    require("fresh_process_nonce_sha256" in defs["restart_observation"]["required"], "fresh process nonce missing")
    for field in ("classifier_source_sha256", "classifier_binary_sha256", "expected_oracle_sha256"):
        require(field in defs["frozen_bindings"]["required"], f"frozen classifier/oracle binding missing: {field}")
    storage = defs["storage_environment"]["properties"]
    for field, expected in {
        "root_is_unique_per_run": True,
        "root_created_exclusively": True,
        "root_mode_octal": "0700",
        "root_symlink_observed": False,
        "filesystem": "f2fs",
        "filesystem_verified_from_mountinfo": True,
        "persistent_filesystem_verified": True,
        "tmpfs_overlay_or_fuse_detected": False,
        "same_boot_verified": True,
        "database_regular_file": True,
        "database_mode_octal": "0600",
        "database_symlink_observed": False,
        "database_hardlink_count": 1,
    }.items():
        require(storage.get(field, {}).get("const") == expected, f"storage constraint drift: {field}")
    sqlite = defs["sqlite_runtime_profile"]["properties"]
    for field, expected in {
        "journal_mode": "DELETE",
        "synchronous": "EXTRA",
        "database_created_exclusively": True,
        "normal_reopen_may_create": False,
        "normal_open_opened_existing_regular_file": True,
        "declared_durable_stage_requires_database_fsync": True,
        "declared_durable_stage_requires_parent_directory_fsync": True,
        "quick_check_result": "ok",
        "unexpected_sidecar_count": 0,
    }.items():
        require(sqlite.get(field, {}).get("const") == expected, f"SQLite constraint drift: {field}")
    sqlite_rules = defs["sqlite_runtime_profile"].get("allOf", [])
    require(len(sqlite_rules) == 2, "SQLite fsync conditionals drift")
    require({next(iter(rule["if"]["properties"])) for rule in sqlite_rules} == {"database_fsync_attempted_before_kill", "parent_directory_fsync_attempted_before_kill"}, "SQLite fsync conditional fields drift")
    for rule in sqlite_rules:
        field = next(iter(rule["if"]["properties"]))
        receipt_field = field.replace("_attempted_before_kill", "_return_code")
        require(rule["if"]["properties"][field].get("const") is True and rule["if"]["required"] == [field], f"SQLite {field} condition drift")
        require(rule["then"]["properties"][receipt_field].get("const") == 0, f"SQLite {field} success receipt drift")
        require(rule["else"]["properties"][receipt_field].get("type") == "null", f"SQLite {field} absent receipt drift")
    raw_rules = defs["raw_recovered_state"].get("allOf", [])
    require(len(raw_rules) == 8, "ABSENT/present hash conditionals drift")
    raw_condition_fields = [next(iter(rule["if"]["properties"])) for rule in raw_rules]
    require(raw_condition_fields == ["write_sync_receipt_state", "object_state", "object_state", "object_state", "receipt_state", "witness_state", "selected_view_state", "competing_view_state"], "raw-state conditional graph/order drift")
    classification_rules = defs["classification"].get("allOf", [])
    require(len(classification_rules) == 2, "classification mutual exclusion drift")
    classification_states = [rule["if"]["properties"]["mapping_status"].get("const") for rule in classification_rules]
    require(classification_states == ["UNIQUE_FROZEN_S16_REFERENCE", "OBSERVED_OUT_OF_MODEL_INDETERMINATE"], "classification conditional states drift")
    require(classification_rules[0]["then"]["properties"]["mapping_cardinality"].get("const") == 1, "unique mapping cardinality drift")
    require(classification_rules[1]["then"]["properties"]["mapping_cardinality"].get("const") == 0, "indeterminate mapping cardinality drift")
    for name, ordinal, kind in (
        ("single_mapping_phase_record", 1, "ATTEMPT_RESULT"),
        ("first_attempt_mapping_phase_record", 1, "FIRST_ATTEMPT"),
        ("restart_mapping_phase_record", 2, "RESTART"),
    ):
        phase = defs[name]
        require(phase.get("allOf", [])[0].get("$ref") == "#/$defs/mapping_phase_record", f"{name} base ref drift")
        props = phase["allOf"][1]["properties"]
        require(props["phase_ordinal"].get("const") == ordinal and props["phase_kind"].get("const") == kind, f"{name} order/kind drift")
    phase_raw = defs["phase_raw_measurement"]
    require(
        set(phase_raw["properties"]) == {
            "retained_raw_event_stream_sha256", "raw_event_frame_index",
            "raw_event_frame_offset_bytes", "raw_event_frame_length_bytes",
            "raw_event_frame_sha256", "measurement_decode_status", "publisher_phase",
            "object_state", "object_len", "object_sha256", "receipt_state",
            "computed_receipt_sha256", "stored_receipt_sha256", "witness_state",
            "computed_witness_sha256", "stored_witness_sha256", "selected_view_state",
            "selected_view_sha256", "competing_view_state", "competing_view_sha256",
            "ack_state", "ack_receipt_sha256", "ack_witness_sha256",
            "crash_cut", "crash_cut_index",
            "restarted_after_crash", "observed_data_steps", "observed_len",
            "adapter_pre_state", "adapter_post_state",
        },
        "phase raw measurement field graph drift",
    )
    for forbidden in ("case_id", "variant_id", "disposition", "reason", "mapped_s15_failure", "planned_variant_id"):
        require(forbidden not in phase_raw["properties"], f"phase raw measurement admits outcome/oracle field: {forbidden}")
    require(phase_raw["properties"]["measurement_decode_status"] == {"const": "EXACT_BOUND_FRAME_DECODED"}, "phase raw decode status drift")
    require(len(phase_raw.get("allOf", [])) == 6, "phase raw-state conditional graph drift")
    require([next(iter(rule["if"]["properties"])) for rule in phase_raw["allOf"]] == ["object_state", "receipt_state", "witness_state", "selected_view_state", "competing_view_state", "ack_state"], "phase raw-state conditional order drift")
    ack_rule = phase_raw["allOf"][-1]
    require(ack_rule["if"]["properties"]["ack_state"] == {"const": "OBSERVED"} and ack_rule["if"]["required"] == ["ack_state"], "phase ack observed condition drift")
    for field in ("ack_receipt_sha256", "ack_witness_sha256"):
        require(ack_rule["then"]["properties"][field].get("$ref") == "#/$defs/sha256", f"observed ack payload binding weakened: {field}")
        require(ack_rule["else"]["properties"][field] == {"type": "null"}, f"unobserved ack payload admitted: {field}")
    require(phase_raw["properties"]["restarted_after_crash"] == {"type": "boolean"}, "phase restart lifecycle input drift")
    require(phase_raw["properties"]["observed_data_steps"].get("maximum") == 49, "phase observed-data-step ceiling drift")
    require(phase_raw["properties"]["observed_len"].get("maximum") == 5494, "phase observed-length ceiling drift")
    require(defs["mapping_phase_record"]["properties"]["raw_phase_measurement"].get("$ref") == "#/$defs/phase_raw_measurement", "mapping phase raw measurement binding drift")
    require(defs["mapping_phase_record"]["properties"]["s16_virtual_projection"].get("$ref") == "#/$defs/s16_virtual_projection", "mapping phase virtual S16 projection binding drift")
    projection = defs["s16_virtual_projection"]
    require(set(projection["properties"]) == {
        "projection_kind", *OBSERVABLE_S16_ROW_FIELDS, "restarted_after_crash",
        "observed_data_steps", "observed_len", "ack_receipt_sha256", "ack_witness_sha256",
        "external_durability_observation_count", "provider_durability_observation_count",
        "owned_lab_durability_observation_count", "side_effects_unlocked",
    }, "virtual S16 projection field graph drift")
    for field, expected in {
        "projection_kind": "FROZEN_S16_EVALUATOR_INPUT_V0",
        "external_durability_observation_count": 0,
        "provider_durability_observation_count": 0,
        "owned_lab_durability_observation_count": 0,
        "side_effects_unlocked": "NONE",
    }.items():
        require(projection["properties"][field] == {"const": expected}, f"virtual S16 projection const drift: {field}")
    require(len(projection.get("allOf", [])) == 1, "virtual S16 projection ack conditional drift")
    custody = defs["custody"]
    require(custody["properties"]["independent_failure_domain_proved"] == {"const": False}, "custody independence not fixed false")
    require(custody["properties"]["trusted_time_obtained"] == {"const": False}, "trusted time may be forged")
    require(custody["properties"]["trusted_time_receipt_sha256"] == {"type": "null"}, "trusted time receipt may be forged")
    require(len(custody.get("allOf", [])) == 1, "custody sequence conditional drift")
    custody_rule = custody["allOf"][0]
    require(custody_rule["if"]["properties"]["custody_sequence"].get("const") == 1, "custody first sequence drift")
    require(custody_rule["then"]["properties"]["previous_custody_entry_sha256"].get("type") == "null", "custody first predecessor drift")
    require(custody_rule["else"]["properties"]["previous_custody_entry_sha256"].get("$ref") == "#/$defs/sha256", "custody chained predecessor drift")
    hashing = defs["hashing_contract"]["properties"]
    require(hashing["canonical_payload_excludes_identity_and_custody"] == {"const": True}, "canonical payload exclusion drift")
    require(hashing["self_referential_fields_excluded"] == {"const": True}, "self-reference exclusion drift")
    require(hashing["retained_raw_event_frame_hash_scope"] == {"const": "SHA256_OF_EXACT_BYTE_RANGE_AT_OFFSET_AND_LENGTH_IN_EXTERNAL_RAW_EVENT_STREAM"}, "raw frame hash scope drift")
    require(hashing["classification_input_domain_separator"] == {"const": "agent_bridge.s17.owned_lab.classification_input.v0"}, "classification input domain drift")
    require(hashing["classification_input_hash_scope"] == {"const": "SHA256_UTF8_DOMAIN_NUL_RFC8785_JCS_OF_EXACT_CLASSIFICATION_INPUT_FRAME"}, "classification input scope drift")
    require(hashing["classification_input_frame_fields"].get("const") == [
        "identity.raw_packet_sha256", "identity.assignment_id", "mapping_phase_record.phase_ordinal",
        "mapping_phase_record.phase_kind", "mapping_phase_record.process_identity_sha256",
        "mapping_phase_record.raw_phase_measurement", "mapping_phase_record.s16_virtual_projection",
    ], "classification input frame drift")
    require(hashing["classification_input_frame_encoding"] == {"const": "RFC8785_OBJECT_WITH_TERMINAL_SOURCE_PATH_COMPONENTS_AS_KEYS"}, "classification input frame encoding drift")
    require(hashing["phase_record_domain_separator"] == {"const": "agent_bridge.s17.owned_lab.mapping_phase_record.v0"}, "phase record domain drift")
    require(hashing["phase_record_hash_scope"] == {"const": "SHA256_UTF8_DOMAIN_NUL_RFC8785_JCS_OF_MAPPING_PHASE_RECORD_WITH_PHASE_RECORD_SHA256_OMITTED"}, "phase record scope drift")
    require(hashing["phase_record_self_hash_excluded"] == {"const": True}, "phase record self-exclusion drift")
    semantic = defs["semantic_validation_contract"]["properties"]
    require(semantic["schema_conformance_alone_proves_cross_field_identity"] == {"const": False}, "schema claims cross-field proof")
    require(semantic["independent_semantic_validator_required"] == {"const": True}, "semantic validator no longer required")
    require(semantic["required_cross_field_rules"].get("const") == EXPECTED_CROSS_FIELD_RULES, "cross-field semantic rule set/order drift")
    for family_id in ("OL00", "OL04", "OL05"):
        sample = build_observation_sample(schema, family_id, kat_rows)
        errors = schema_instance_errors(schema, sample, schema)
        require(not errors, f"observation {family_id} composition KAT failed: {errors[:3]}")
        require(phase_hashes_valid(sample), f"observation {family_id} phase digest KAT failed")
        require(assignment_matches_recomputed_classification(sample), f"observation {family_id} post-lookup assignment consistency KAT failed")
        require(every_phase_durable_image_matches_top_level(sample), f"observation {family_id} phase/top durable image KAT failed")
        expected_kat_labels = {"OL00": ["OL00"], "OL04": ["OL04"], "OL05": ["OL05_FIRST", "OL05_RESTART"]}[family_id]
        for phase, kat_label in zip(sample["mapping_phase_records"], expected_kat_labels):
            kat_row = kat_rows[kat_label]
            classification = phase["classification"]
            require(projection_matches_raw(phase["raw_phase_measurement"], phase["s16_virtual_projection"], kat_rows["_sentinels"]), f"{family_id} raw-to-S16 projection KAT drift")
            require((classification["mapped_s16_case_id"], classification["mapped_s16_variant_id"]) == (kat_row["row"]["case_id"], kat_row["row"]["variant_id"]), f"{family_id} mapped row identity KAT drift")
            require(classification["mapped_s16_row_sha256"] == kat_row["row_sha256"], f"{family_id} mapped row digest KAT drift")
            require((classification["mapped_reason"], classification["mapped_failure"]) == (kat_row["row"]["reason"], kat_row["row"]["mapped_s15_failure"]), f"{family_id} mapped outcome KAT drift")
        for phase in sample["mapping_phase_records"]:
            require(phase["raw_phase_measurement"]["retained_raw_event_stream_sha256"] == sample["identity"]["raw_packet_sha256"], f"{family_id} phase/raw packet KAT drift")
            require(phase["classification"]["classifier_build_sha256"] == sample["frozen_bindings"]["classifier_binary_sha256"], f"{family_id} classifier binding KAT drift")
        if family_id == "OL00":
            require(sample["mapping_phase_records"][0]["raw_phase_measurement"]["restarted_after_crash"] is False, "OL00 lifecycle KAT became restart")
        elif family_id == "OL04":
            require(sample["mapping_phase_records"][0]["raw_phase_measurement"]["restarted_after_crash"] is True, "OL04 lifecycle KAT lost restart")
        else:
            first_raw = sample["mapping_phase_records"][0]["raw_phase_measurement"]
            restart_raw = sample["mapping_phase_records"][1]["raw_phase_measurement"]
            require(first_raw["restarted_after_crash"] is False and restart_raw["restarted_after_crash"] is True, "OL05 lifecycle phase KAT drift")
            require((first_raw["crash_cut"], first_raw["crash_cut_index"]) == (restart_raw["crash_cut"], restart_raw["crash_cut_index"]), "OL05 phase cut binding KAT drift")


def validate_owner_schema(schema: dict[str, Any]) -> None:
    validate_schema_envelope(
        schema,
        "agent_bridge.memory_temporal_recovered_envelope_owned_lab_owner_resource_decision_s17.v0",
        "owner schema",
    )
    validate_schema_keywords(schema, "owner schema")
    require(
        canonical_json_sha256(schema) == EXPECTED_OWNER_SCHEMA_CANONICAL_SHA256,
        "owner schema canonical JSON structure commitment drift",
    )
    validate_closed_object_required_graph(schema, "owner schema")
    require(type(schema.get("allOf")) is list and len(schema["allOf"]) == 2, "owner pending/rejected conditions drift")
    require(schema["properties"]["positive_decision_admissible_in_this_schema"].get("const") is False, "owner v0 admits positive decision")
    require(schema["properties"]["decision_state"].get("enum") == ["PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING", "REJECTED_FAIL_CLOSED"], "owner decision states drift")
    require(schema["properties"]["decision_reason"].get("enum") == ["WAITING_FOR_AUTHENTICATED_OWNER_RESOURCE_BINDING", "OWNER_AUTHENTICATION_FAILED", "RESOURCE_OR_SCOPE_BINDING_FAILED", "PREREQUISITE_OR_REVIEW_FAILED"], "owner decision reasons drift")
    require_tokens(
        schema,
        (
            "AUTHORIZED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY_EXECUTION",
            "OL00_OL04_OL05_FIRST_BATCH", "OL00", "OL04", "OL05",
            "PIDFD_SIGKILL_AND_REAP_EXACT_BOUND_CHILD_ONLY", "FAIL_CLOSED_NO_OBSERVATION",
            "ANONYMOUS_PIPE",
            "DELETE", "EXTRA", "READWRITE_EXISTING_NO_CREATE",
            "assigned_attempt_count", "planned_pidfd_sigkill_attempt_count",
            "planned_distinct_fresh_exec_read_count",
            "single_use_execution_capability_issued", "single_use_replay_cas_receipt_sha256",
            "stop_receipt_sha256", "cleanup_policy_sha256", "reviewer_receipt_sha256",
            "memory_limit_bytes", "swap_limit_bytes", "tasks_max", "nofile_limit",
            "suite_timeout_seconds", "build_jobs", "nested_cargo_allowed",
            "oom_timeout_or_leak_invalidates_batch",
            "network_allowed", "PROVIDER_ACCESS", "credential_access_allowed",
            "paid_resource_allowed", "ROOT_OR_PRIVILEGE_ESCALATION", "MOUNT_OR_UNMOUNT",
            "DROP_CACHES", "REBOOT_KERNEL_CRASH_OR_POWER_FAULT",
            "DIRECT_BLOCK_DEVICE_WRITE_OR_MUTATION",
        ),
        "owner schema",
    )
    defs = schema["$defs"]
    for name in ("owner", "frozen_subject", "resource_scope", "execution_scope", "safety_and_custody", "global_runtime_boundary", "nonclaims"):
        require(name in defs, f"owner schema definition missing: {name}")
        require(defs[name].get("type") == "object", f"owner definition type drift: {name}")
        require(defs[name].get("additionalProperties") is False, f"owner definition is open: {name}")
    frozen_subject_fields = set(defs["frozen_subject"]["required"])
    for field in (
        "observation_schema_sha256", "control_protocol_sha256", "sqlite_profile_sha256",
        "sqlite_schema_sha256", "classifier_source_sha256", "classifier_binary_sha256",
        "expected_oracle_sha256",
    ):
        require(field in frozen_subject_fields, f"owner frozen subject omits exact binding: {field}")
    execution = defs["execution_scope"]["properties"]
    for field, expected in {
        "family_id_namespace": "OL00_OL04_OL05_FIRST_BATCH",
        "family_count": 3,
        "scenario_count_per_canary_batch": 60,
        "canary_batch_count": 1,
        "assigned_attempt_count": 60,
        "planned_pidfd_sigkill_attempt_count": 59,
        "planned_distinct_fresh_exec_read_count": 59,
        "planned_d05_first_and_restart_phase_record_count": 106,
        "planned_total_s16_mapping_phase_record_count": 113,
        "full_102_scenario_schedule_authorized": False,
        "post_canary_execution_authorized": False,
        "pidfd_required": True,
        "pidfd_identity_recheck_required": True,
        "pidfd_unavailable_policy": "FAIL_CLOSED_NO_OBSERVATION",
        "pidfd_unavailable_counts_as_observation": False,
        "fresh_process_required": True,
        "control_channel": "ANONYMOUS_PIPE",
        "persisted_control_marker_allowed": False,
        "production_execution_authorized": False,
        "provider_execution_authorized": False,
        "network_allowed": False,
        "credential_access_allowed": False,
        "paid_resource_allowed": False,
    }.items():
        require(execution.get(field, {}).get("const") == expected, f"owner execution constraint drift: {field}")
    resources = defs["resource_scope"]["properties"]
    for field, expected in {
        "filesystem": "f2fs",
        "root_must_not_preexist": True,
        "root_mode_octal": "0700",
        "symlink_follow_allowed": False,
        "direct_block_device_writes_allowed": False,
        "sqlite_journal_mode": "DELETE",
        "sqlite_synchronous": "EXTRA",
        "sqlite_reopen_create_allowed": False,
        "sqlite_unexpected_sidecars_allowed": False,
        "sqlite_database_file_fsync_required": True,
        "sqlite_parent_directory_fsync_required": True,
        "maximum_active_assigned_attempts": 1,
        "maximum_controller_processes": 1,
        "maximum_child_processes": 1,
        "memory_limit_bytes": 805306368,
        "swap_limit_bytes": 268435456,
        "tasks_max": 16,
        "nofile_limit": 256,
        "disk_limit_bytes": 268435456,
        "kill_and_reap_timeout_seconds": 10,
        "recover_timeout_seconds": 20,
        "suite_timeout_seconds": 900,
        "build_jobs": 1,
        "nested_cargo_allowed": False,
        "cost_ceiling_usd": 0,
    }.items():
        require(resources.get(field, {}).get("const") == expected, f"owner resource constraint drift: {field}")
    require(resources["canonical_root"].get("pattern") == r"^/Data/CascadeProjects/\.ab-owned-lab/s17-[0-9a-f]{40}-[1-9][0-9]*-[1-9][0-9]*-[0-9a-f]{64}$", "owner/observation root pattern drift")
    for rule in schema["allOf"]:
        state = rule["if"]["properties"]["decision_state"]["const"]
        require(state in {"PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING", "REJECTED_FAIL_CLOSED"}, "owner condition admits unknown state")
        then = rule["then"]["properties"]
        require(then["authorization_receipt"].get("type") == "null", f"owner {state} permits receipt")
        require(then["execution_scope"]["properties"]["owned_lab_execution_authorized"].get("const") is False, f"owner {state} permits execution")
        require(then["execution_scope"]["properties"]["single_use_execution_capability_issued"].get("const") is False, f"owner {state} permits capability")
        owner_fields = then["owner"]["properties"]
        require(owner_fields["identity_authenticated"].get("const") is False and owner_fields["decision_recorded"].get("const") is False, f"owner {state} claims authentication")
        for field in ("owner_identity_sha256", "owner_key_id", "owner_signature_sha256", "decision_issued_at_utc", "decision_expires_at_utc"):
            require(owner_fields[field].get("type") == "null", f"owner {state} carries identity/decision field: {field}")
        safety = then["safety_and_custody"]["properties"]
        for field in ("trusted_time_bound", "single_use_replay_cas_ready", "stop_controls_ready", "custody_and_retention_ready", "independent_review_approved"):
            require(safety[field].get("const") is False, f"owner {state} claims safety readiness: {field}")
        for field in ("trusted_time_receipt_sha256", "single_use_replay_cas_receipt_sha256", "stop_control_sha256", "stop_receipt_sha256", "retention_policy_sha256", "cleanup_policy_sha256", "cleanup_receipt_sha256", "reviewer_receipt_sha256"):
            require(safety[field].get("type") == "null", f"owner {state} carries safety receipt: {field}")
        reason_schema = then["decision_reason"]
        if state == "PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING":
            require(reason_schema.get("const") == "WAITING_FOR_AUTHENTICATED_OWNER_RESOURCE_BINDING", "pending owner reason drift")
        else:
            require(reason_schema.get("enum") == ["OWNER_AUTHENTICATION_FAILED", "RESOURCE_OR_SCOPE_BINDING_FAILED", "PREREQUISITE_OR_REVIEW_FAILED"], "rejected owner reasons drift")
    receipt = defs["authorization_receipt"]
    receipt_fields = set(receipt["required"])
    for field in (
        "owner_identity_sha256", "owner_key_id", "owner_signature_sha256",
        "decision_issued_at_utc", "decision_expires_at_utc", "plan_sha256",
        "schedule_sha256", "assignment_set_sha256", "runner_source_commit",
        "runner_source_sha256", "runner_binary_sha256", "toolchain_sha256",
        "observation_schema_sha256", "control_protocol_sha256", "sqlite_profile_sha256",
        "sqlite_schema_sha256", "classifier_source_sha256", "classifier_binary_sha256",
        "expected_oracle_sha256", "resource_scope_sha256", "safety_and_custody_sha256",
        "single_use_replay_cas_receipt_sha256", "stop_control_sha256",
        "stop_receipt_sha256", "retention_policy_sha256", "cleanup_policy_sha256",
        "cleanup_receipt_sha256", "reviewer_receipt_sha256", "semantic_binding_rules",
    ):
        require(field in receipt_fields, f"authorization receipt omits exact binding: {field}")
    require(receipt["properties"]["trusted_time_receipt_sha256"].get("type") == "null", "authorization receipt fabricates trusted time")
    require(len(receipt["properties"]["semantic_binding_rules"].get("const", [])) >= 8, "authorization receipt semantic target weakened")
    owner_nonclaims = defs["nonclaims"]["properties"]
    for field in ("positive_decision_admissible_in_this_schema", "schema_conformance_alone_authorizes_execution", "cross_field_semantic_validation_implemented", "cryptographic_owner_signature_verification_implemented"):
        require(owner_nonclaims[field] == {"const": False}, f"owner nonclaim drift: {field}")
    for state in ("PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING", "REJECTED_FAIL_CLOSED"):
        errors = schema_instance_errors(schema, build_owner_sample(schema, state), schema)
        require(not errors, f"owner {state} composition KAT failed: {errors[:3]}")
    forbidden_positive = build_owner_sample(schema, "PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING")
    forbidden_positive["decision_state"] = "AUTHORIZED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY_EXECUTION"
    require(schema_instance_errors(schema, forbidden_positive, schema), "owner v0 accepted forbidden positive state")


def validate_successor(successor: dict[str, Any]) -> None:
    require(successor["schema"] == "agent_bridge.memory_temporal_successor_admission_gate_s17.v0", "successor schema drift")
    require(successor["status"] == STATUS and successor["decision"] == DECISION, "successor state drift")
    require(successor["baseline"] == BASELINE, "successor baseline drift")
    prereg = successor["preregistration"]
    require(prereg["family_ids"] == ["OL00", "OL04", "OL05"], "successor family order drift")
    expected_counts = {
        "family_count": 3,
        "scenario_count_per_repetition": 60,
        "repetition_count": 1,
        "assigned_attempt_count": 60,
        "planned_pidfd_sigkill_attempt_count": 59,
        "planned_distinct_fresh_exec_read_count": 59,
        "planned_d05_first_and_restart_phase_record_count": 106,
        "planned_s16_mapping_phase_record_count": 113,
    }
    for key, expected in expected_counts.items():
        require(prereg[key] == expected, f"successor preregistration drift: {key}")
    harness = successor["harness_fail_closed_profile"]
    for key, expected in {
        "control_channel": "INHERITED_ANONYMOUS_PIPE_RUN_BOUND_FRAMES_ONLY",
        "persisted_control_marker_allowed": False,
        "pidfd_required": True,
        "kill_api": "PIDFD_SEND_SIGNAL_SIGKILL",
        "numeric_pid_fallback_allowed": False,
        "pidfd_unavailable_policy": "FAIL_CLOSED_NO_OBSERVATION",
        "child_descendants_allowed": False,
        "fresh_exec_distinct_pid_start_token_and_nonce_required": True,
        "nofollow_required": True,
        "preexisting_or_aliased_root_allowed": False,
        "sqlite_journal_mode": "DELETE",
        "sqlite_synchronous": "EXTRA",
        "sqlite_restart_reopen": "READ_WRITE_WITHOUT_CREATE",
        "database_file_fsync_required": True,
        "parent_directory_fsync_required": True,
        "memory_max_bytes": 805306368,
        "swap_max_bytes": 268435456,
        "maximum_tasks": 16,
        "maximum_open_files": 256,
        "build_jobs": 1,
        "nested_cargo_allowed": False,
        "cut_ready_timeout_seconds": 10,
        "pidfd_signal_timeout_seconds": 10,
        "death_confirmation_timeout_seconds": 10,
        "fresh_exec_timeout_seconds": 20,
        "attempt_timeout_seconds": 60,
        "batch_timeout_seconds": 900,
        "any_oom_event_invalidates_entire_batch": True,
        "timeout_or_leaked_child_invalidates_entire_batch": True,
    }.items():
        require(harness.get(key) == expected, f"successor harness boundary drift: {key}")
    authorization = successor["authorization"]
    for key, value in authorization.items():
        if key == "owner_resource_decision_sha256":
            require(value is None, "successor owner decision digest must be absent")
        else:
            require(value is False, f"successor authorization unexpectedly enabled: {key}")
    require_all_false_or_zero(successor["current_execution_and_evidence"], "successor.current_execution_and_evidence")
    global_boundary = successor["global_runtime_prerequisites"]
    require(global_boundary["total"] == 16 and global_boundary["satisfied"] == 0 and global_boundary["missing"] == 16, "successor global prerequisite count drift")
    for key in ("lab_scoped_decision_can_satisfy_global_prerequisite", "global_runtime_admission_ready", "global_runtime_admission_granted"):
        require(global_boundary[key] is False, f"successor global boundary enabled: {key}")
    require_all_false_or_zero(successor["admission"], "successor.admission")
    require(successor["next_evidence_stage"]["may_authorize_provider_or_production"] is False, "successor widened to provider/production")
    require(successor["next_evidence_stage"]["may_issue_currentness_admission_output_or_claim"] is False, "successor widened to output/claim")
    require(successor["next_evidence_stage"]["requires_exact_observation_control_sqlite_classifier_and_oracle_binding"] is True, "successor exact future bindings weakened")
    require(successor["next_evidence_stage"]["requires_phase_raw_frame_and_lifecycle_semantic_validation"] is True, "successor phase raw semantic validation weakened")
    require(successor["next_evidence_stage"]["requires_ack_payload_and_virtual_s16_projection_semantic_validation"] is True, "successor ack/projection semantic validation weakened")
    require(successor["next_evidence_stage"]["requires_virtual_s16_projection_zero_counters_distinct_from_s17_ledger"] is True, "successor S16/S17 ledger separation weakened")
    require(successor["next_evidence_stage"]["requires_full_5639_row_catalog_classification_without_assignment_label_prefilter"] is True, "successor label-prefilter boundary weakened")
    require(successor["next_evidence_stage"]["requires_classification_input_and_phase_record_digest_recomputation"] is True, "successor phase digest recomputation weakened")
    require(successor["next_evidence_stage"]["requires_new_positive_owner_schema_and_semantic_signature_validator"] is True, "successor positive owner/validator boundary weakened")
    require(successor["next_evidence_stage"]["requires_stop_custody_retention_cleanup_and_review"] is True, "successor safety binding weakened")
    require(successor["next_evidence_stage"]["trusted_external_time_required_for_this_offline_lab_batch"] is False, "successor requires unavailable trusted external time")
    require(successor["next_evidence_stage"]["trusted_external_time_receipt_present"] is False, "successor fabricates trusted external time receipt")
    require_all_false_or_zero(successor["nonclaims"], "successor.nonclaims")


def validate_synthetic(fixture: dict[str, Any], plan: dict[str, Any], successor: dict[str, Any]) -> None:
    require(fixture["schema"] == "agent_bridge.memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17_synthetic_fixture.v0", "synthetic schema drift")
    require(fixture["fixture_kind"] == "OFFLINE_SHAPE_KAT_ONLY", "synthetic kind drift")
    require(fixture["status"] == STATUS and fixture["decision"] == DECISION, "synthetic state drift")
    require_all_false_or_zero(fixture["synthetic_semantics"], "synthetic.synthetic_semantics")
    require(fixture["baseline"] == BASELINE, "synthetic baseline drift")
    synthetic_s16_expected = {
        key: value for key, value in S16_BINDINGS.items() if key != "s16_design_sha256"
    }
    require(fixture["s16_known_answer_kat"] == synthetic_s16_expected, "synthetic S16 KAT drift")

    expected_catalog = [
        {"role": "PLAN", "path": PLAN_PATH},
        {"role": "OBSERVATION_SCHEMA", "path": OBSERVATION_SCHEMA_PATH},
        {"role": "OWNER_RESOURCE_DECISION_SCHEMA", "path": OWNER_SCHEMA_PATH},
        {"role": "SUCCESSOR_GATE", "path": SUCCESSOR_PATH},
        {"role": "SYNTHETIC_FIXTURE", "path": SYNTHETIC_PATH},
    ]
    require(fixture["artifact_catalog"] == expected_catalog, "synthetic artifact catalog drift")

    schedule = fixture["schedule_kat"]
    require(schedule["family_ids"] == ["OL00", "OL04", "OL05"], "synthetic family order drift")
    require(schedule["family_scenario_counts"] == [1, 6, 53], "synthetic family counts drift")
    for key in (
        "family_id_namespace", "family_count", "scenario_count_per_repetition",
        "repetition_start_inclusive", "repetition_end_inclusive", "repetition_count",
        "canary_repetition", "assigned_attempt_count", "planned_pidfd_sigkill_attempt_count",
        "planned_distinct_fresh_exec_read_count",
        "planned_d05_first_and_restart_phase_record_count",
        "planned_total_s16_mapping_phase_record_count",
        "families_outside_ol00_ol04_ol05_are_preregistered",
        "d05_read_quantum_bytes", "d05_data_step_count",
    ):
        require(schedule[key] == plan["schedule"][key], f"synthetic schedule KAT drift: {key}")
    require(schedule["d05_cut_position_count"] == 53, "synthetic D05 cut count drift")
    require(schedule["d05_after_data_start_inclusive"] == 1 and schedule["d05_after_data_end_inclusive"] == 49, "synthetic D05 data range drift")
    require(fixture["harness_profile_kat"] == successor["harness_fail_closed_profile"], "synthetic/successor harness profile drift")

    owner = fixture["owner_shape_kat"]
    require(owner["packet_present"] is False and owner["packet"] is None, "synthetic contains owner packet")
    require(owner["positive_decision_admissible_in_current_schema"] is False, "synthetic v0 admits positive owner decision")
    require(owner["cross_field_semantic_and_signature_validator_implemented"] is False, "synthetic claims semantic/signature validator")
    for key in ("owner_identity_authenticated", "decision_recorded", "owned_lab_execution_authorized", "production_execution_authorized", "provider_execution_authorized", "single_use_execution_capability_issued"):
        require(owner[key] is False, f"synthetic owner authority enabled: {key}")
    require(owner["owner_identity_sha256"] is None and owner["owner_signature_sha256"] is None, "synthetic owner identity present")

    observation = fixture["observation_shape_kat"]
    require(observation["packet_count"] == 0 and observation["packets"] == [], "synthetic contains observation")
    require(observation["claim_level_if_future_authorized"] == CLAIM_LEVEL, "synthetic claim level drift")
    require(observation["synthetic_fixture_can_satisfy_observation_schema_as_runtime_evidence"] is False, "synthetic became runtime evidence")
    require(observation["planned_label_is_outcome_oracle"] is False, "synthetic planned label became oracle")
    require(observation["phase_raw_measurement_and_hash_frames_preregistered"] is True, "synthetic phase raw/hash contract weakened")
    require(observation["ack_payload_and_virtual_s16_projection_preregistered"] is True, "synthetic ack/projection contract weakened")
    require(observation["virtual_s16_projection_counters_are_not_s17_observed_evidence"] is True, "synthetic S16/S17 counter boundary weakened")
    require(observation["classification_searches_full_5639_row_catalog_without_assignment_label_prefilter"] is True, "synthetic classification prefilter boundary weakened")
    require(observation["phase_semantic_validator_implemented"] is False, "synthetic claims phase semantic validator")
    require(observation["unknown_mapping"] == "OBSERVED_OUT_OF_MODEL_INDETERMINATE", "synthetic unknown mapping drift")

    require_all_false_or_zero(fixture["execution_and_evidence_ledger"], "synthetic.execution_and_evidence_ledger")
    global_kat = fixture["global_runtime_prerequisite_kat"]
    require(global_kat["total"] == 16 and global_kat["satisfied"] == 0 and global_kat["missing"] == 16, "synthetic global count drift")
    require([row["prerequisite_id"] for row in global_kat["rows"]] == GLOBAL_PREREQUISITES, "synthetic global prerequisite order drift")
    require([row["ordinal"] for row in global_kat["rows"]] == list(range(1, 17)), "synthetic global prerequisite ordinals drift")
    require(all(row["satisfied"] is False for row in global_kat["rows"]), "synthetic global prerequisite enabled")
    for key in ("global_runtime_admission_ready", "global_runtime_admission_granted", "lab_scoped_decision_can_satisfy_global_prerequisite"):
        require(global_kat[key] is False, f"synthetic global boundary enabled: {key}")
    claim_kat = fixture["claim_ceiling_kat"]
    require(claim_kat["level"] == CLAIM_LEVEL, "synthetic claim KAT level drift")
    require(claim_kat["current_claim"] == "PREREGISTRATION_ONLY_NO_RUNTIME_EVIDENCE", "synthetic claim KAT current claim drift")
    for key, value in claim_kat.items():
        if type(value) is bool:
            require(value is False, f"synthetic claim unexpectedly proved: {key}")

    expected = fixture["expected_offline_validation"]
    require(expected["family_count"] == 3 and expected["scenario_count_per_repetition"] == 60 and expected["assigned_attempt_count"] == 60, "synthetic expected schedule drift")
    require(expected["planned_pidfd_sigkill_attempt_count"] == 59 and expected["planned_distinct_fresh_exec_read_count"] == 59, "synthetic expected crash accounting drift")
    require(expected["planned_s16_mapping_phase_record_count"] == 113, "synthetic expected mapping count drift")
    require(expected["runtime_observation_count"] == 0 and expected["owner_packet_count"] == 0, "synthetic expected evidence drift")
    require(expected["positive_owner_decision_admissible_in_current_schema"] is False, "synthetic expected positive owner decision")
    require(expected["cross_field_semantic_and_signature_validator_implemented"] is False, "synthetic expected semantic/signature validator")
    require(expected["decision"] == DECISION and expected["side_effects_unlocked"] == "NONE", "synthetic expected state drift")


def validate_docs(design: str, report: str) -> None:
    combined = design + "\n" + report
    for phrase in (
        "60 assigned attempts", "59", "113", "pidfd_send_signal", "fresh-exec",
        "ANONYMOUS", "DELETE", "EXTRA", "F2FS", "0/16", "side_effects_unlocked=NONE",
        "not institutional recognition", "BLOCKED_PENDING_AUTHENTICATED_OWNER_RESOURCE_BINDING",
    ):
        require(phrase.lower() in combined.lower(), f"documentation omits boundary phrase: {phrase}")
    for forbidden in ("3,060 assigned attempts", "4,650", "OL00–OL15"):
        require(forbidden not in combined, f"superseded full-taxonomy schedule remains in documentation: {forbidden}")
    require("TODO_ARTIFACT_SHA256" not in report, "report contains unresolved artifact digest")


def validate_bundle(bundle: dict[str, dict[str, Any]], design: str, report: str, kat_rows: dict[str, dict[str, Any]]) -> None:
    validate_plan(bundle["plan"])
    validate_observation_schema(bundle["observation"], kat_rows)
    validate_owner_schema(bundle["owner"])
    validate_successor(bundle["successor"])
    validate_synthetic(bundle["synthetic"], bundle["plan"], bundle["successor"])
    validate_docs(design, report)


def expect_rejected(label: str, mutate: Any, bundle: dict[str, dict[str, Any]], design: str, report: str, kat_rows: dict[str, dict[str, Any]]) -> None:
    candidate = copy.deepcopy(bundle)
    mutate(candidate)
    try:
        validate_bundle(candidate, design, report, kat_rows)
    except CheckFailure:
        return
    raise CheckFailure(f"directed mutation was accepted: {label}")


def expect_instance_rejected(label: str, schema: dict[str, Any], instance: dict[str, Any]) -> None:
    require(schema_instance_errors(schema, instance, schema), f"invalid schema instance was accepted: {label}")


def expect_phase_hash_rejected(label: str, observation: dict[str, Any], mutate: Any) -> None:
    candidate = copy.deepcopy(observation)
    mutate(candidate)
    require(not phase_hashes_valid(candidate), f"phase digest mutation was accepted: {label}")


def expect_projection_rejected(
    label: str, observation: dict[str, Any], mutate: Any, sentinels: dict[str, str],
) -> None:
    candidate = copy.deepcopy(observation)
    mutate(candidate)
    for phase in candidate["mapping_phase_records"]:
        phase["classification_input_sha256"] = recompute_classification_input_sha256(candidate, phase)
        phase["phase_record_sha256"] = recompute_phase_record_sha256(phase)
    require(phase_hashes_valid(candidate), f"projection mutation did not recompute phase digests: {label}")
    require(
        any(not projection_matches_raw(phase["raw_phase_measurement"], phase["s16_virtual_projection"], sentinels) for phase in candidate["mapping_phase_records"]),
        f"raw-to-S16 projection mutation was accepted: {label}",
    )


def self_test(bundle: dict[str, dict[str, Any]], design: str, report: str, kat_rows: dict[str, dict[str, Any]]) -> None:
    mutations = [
        ("nonzero observation", lambda b: b["plan"]["current_accounting"].__setitem__("owned_lab_durability_observation_count", 1)),
        ("authority enabled", lambda b: b["plan"]["authorization_boundary"].__setitem__("owned_lab_execution_authorized", True)),
        ("denominator drift", lambda b: b["plan"]["schedule"].__setitem__("assigned_attempt_count", 61)),
        ("family reorder", lambda b: b["plan"]["schedule"]["families"].reverse()),
        ("L2 claim", lambda b: b["plan"]["claim_ceiling"].__setitem__("level", "L2_HOST_RESTART")),
        ("global prerequisite", lambda b: b["plan"]["global_runtime_prerequisites"].__setitem__("satisfied", 1)),
        ("open observation root", lambda b: b["observation"].__setitem__("additionalProperties", True)),
        ("pidfd proof weakened", lambda b: b["observation"]["$defs"]["pidfd_sigkill_observation_constraints"]["properties"].pop("pidfd_open_succeeded")),
        ("root family conditions emptied", lambda b: b["observation"].__setitem__("allOf", [{}, {}, {}])),
        ("assignment conditions emptied", lambda b: b["observation"]["$defs"]["assignment"].__setitem__("allOf", [{}, {}, {}])),
        ("killed branch uses control", lambda b: b["observation"]["allOf"][1]["then"]["properties"].__setitem__("crash_observation", {"$ref": "#/$defs/control_process_observation_constraints"})),
        ("killed branch restart null", lambda b: b["observation"]["allOf"][1]["then"]["properties"].__setitem__("restart_observation", {"type": "null"})),
        ("pidfd identity no longer required", lambda b: b["observation"]["$defs"]["crash_observation"]["required"].remove("pidfd_target_start_identity")),
        ("SQLite fsync conditions removed", lambda b: b["observation"]["$defs"]["sqlite_runtime_profile"].__setitem__("allOf", [])),
        ("raw hash conditions removed", lambda b: b["observation"]["$defs"]["raw_recovered_state"].__setitem__("allOf", [])),
        ("classification conditions removed", lambda b: b["observation"]["$defs"]["classification"].__setitem__("allOf", [])),
        ("custody independence widened", lambda b: b["observation"]["$defs"]["custody"]["properties"].__setitem__("independent_failure_domain_proved", {"type": "boolean", "default": False})),
        ("trusted time widened", lambda b: b["observation"]["$defs"]["custody"]["properties"].__setitem__("trusted_time_obtained", {"type": "boolean"})),
        ("canonical hash exclusion disabled", lambda b: b["observation"]["$defs"]["hashing_contract"]["properties"].__setitem__("canonical_payload_excludes_identity_and_custody", {"const": False})),
        ("classification frame admits planned case", lambda b: b["observation"]["$defs"]["hashing_contract"]["properties"]["classification_input_frame_fields"]["const"].insert(2, "assignment.planned_s16_case_id")),
        ("phase record self hash admitted", lambda b: b["observation"]["$defs"]["hashing_contract"]["properties"].__setitem__("phase_record_self_hash_excluded", {"const": False})),
        ("semantic classifier catalog scope weakened", lambda b: b["observation"]["$defs"]["semantic_validation_contract"]["properties"]["required_cross_field_rules"]["const"].__setitem__(17, "CLASSIFICATION_PREFILTERED_BY_PLANNED_CASE")),
        ("unresolved schema ref", lambda b: b["observation"]["properties"].__setitem__("hashing_contract", {"$ref": "#/$defs/does_not_exist"})),
        ("D05 double phase removed", lambda b: b["observation"]["allOf"][2]["then"]["properties"]["mapping_phase_records"].update({"minItems": 1, "maxItems": 1})),
        ("initial nonce no longer required", lambda b: b["observation"]["$defs"]["crash_observation"]["required"].remove("child_process_nonce_sha256")),
        ("custody chain condition removed", lambda b: b["observation"]["$defs"]["custody"].__setitem__("allOf", [])),
        ("owner conditions removed", lambda b: b["owner"].__setitem__("allOf", [])),
        ("owner positive state admitted", lambda b: b["owner"]["properties"]["decision_state"]["enum"].append("AUTHORIZED_OWNED_LAB_L1_OL00_OL04_OL05_CANARY_EXECUTION")),
        ("pending owner authentication enabled", lambda b: b["owner"]["allOf"][0]["then"]["properties"]["owner"]["properties"].__setitem__("identity_authenticated", {"const": True})),
        ("pending owner receipt admitted", lambda b: b["owner"]["allOf"][0]["then"]["properties"].__setitem__("authorization_receipt", {"$ref": "#/$defs/authorization_receipt"})),
        ("target receipt owner signature optional", lambda b: b["owner"]["$defs"]["authorization_receipt"]["required"].remove("owner_signature_sha256")),
        ("target receipt semantic rules emptied", lambda b: b["owner"]["$defs"]["authorization_receipt"]["properties"]["semantic_binding_rules"].__setitem__("const", [])),
        ("owner packet injected", lambda b: b["synthetic"]["owner_shape_kat"].update({"packet_present": True, "packet": {}})),
        ("observation injected", lambda b: b["synthetic"]["observation_shape_kat"].update({"packet_count": 1, "packets": [{}]})),
        ("runner claimed", lambda b: b["successor"]["current_execution_and_evidence"].__setitem__("runner_implemented", True)),
        ("full catalog search disabled", lambda b: b["plan"]["classification_contract"].__setitem__("classification_searches_full_5639_row_s16_catalog", False)),
        ("full catalog uniqueness count drift", lambda b: b["plan"]["classification_contract"]["offline_full_catalog_uniqueness_kat"].__setitem__("multiple_match_count", 1)),
        ("successor label prefilter allowed", lambda b: b["successor"]["next_evidence_stage"].__setitem__("requires_full_5639_row_catalog_classification_without_assignment_label_prefilter", False)),
        ("unknown plan field", lambda b: b["plan"].__setitem__("unexpected", False)),
    ]
    for definition_name, required_field in (
        ("storage_environment", "mountinfo_entry_before_sha256"),
        ("sqlite_runtime_profile", "profile_sha256"),
        ("raw_recovered_state", "object_state"),
        ("classification", "mapping_status"),
        ("custody", "custody_sequence"),
        ("hashing_contract", "canonical_payload_top_level_fields"),
        ("semantic_validation_contract", "required_cross_field_rules"),
        ("accounting", "owned_lab_process_sigkill_observation_count"),
        ("frozen_bindings", "runner_binary_sha256"),
        ("identity", "raw_packet_sha256"),
        ("mapping_phase_record", "classification"),
        ("phase_raw_measurement", "restarted_after_crash"),
        ("authorization", "owner_resource_decision_sha256"),
    ):
        mutations.append((
            f"closed object required field removed: {definition_name}.{required_field}",
            lambda b, name=definition_name, field=required_field: b["observation"]["$defs"][name]["required"].remove(field),
        ))
    for label, mutation in mutations:
        expect_rejected(label, mutation, bundle, design, report, kat_rows)

    observation_schema = bundle["observation"]
    ol00 = build_observation_sample(observation_schema, "OL00", kat_rows)
    ol00["restart_observation"] = schema_sample(observation_schema["$defs"]["restart_observation"], observation_schema)
    expect_instance_rejected("OL00 fake restart", observation_schema, ol00)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["crash_observation"]["kill_method"] = "NONE_CONTROL"
    expect_instance_rejected("OL04 non-pidfd kill", observation_schema, ol04)
    ol05 = build_observation_sample(observation_schema, "OL05", kat_rows)
    ol05["mapping_phase_records"] = ol05["mapping_phase_records"][:1]
    expect_instance_rejected("OL05 missing restart phase", observation_schema, ol05)
    ol05 = build_observation_sample(observation_schema, "OL05", kat_rows)
    ol05["mapping_phase_records"].reverse()
    expect_instance_rejected("OL05 reversed phases", observation_schema, ol05)
    digest_kat = build_observation_sample(observation_schema, "OL05", kat_rows)
    require(phase_hashes_valid(digest_kat), "positive phase digest self-test KAT failed")
    expect_phase_hash_rejected("raw measurement tamper", digest_kat, lambda value: value["mapping_phase_records"][0]["raw_phase_measurement"].__setitem__("observed_len", 1))
    expect_phase_hash_rejected("phase ordinal tamper", digest_kat, lambda value: value["mapping_phase_records"][0].__setitem__("phase_ordinal", 2))
    expect_phase_hash_rejected("classification tamper", digest_kat, lambda value: value["mapping_phase_records"][0]["classification"].__setitem__("mapped_reason", "TAMPERED_REASON"))
    expect_phase_hash_rejected("classification input digest tamper", digest_kat, lambda value: value["mapping_phase_records"][0].__setitem__("classification_input_sha256", "0" * 64))
    expect_phase_hash_rejected("phase record digest tamper", digest_kat, lambda value: value["mapping_phase_records"][0].__setitem__("phase_record_sha256", "0" * 64))
    expect_phase_hash_rejected("raw packet digest tamper", digest_kat, lambda value: value["identity"].__setitem__("raw_packet_sha256", "0" * 64))
    projection_kat = build_observation_sample(observation_schema, "OL04", kat_rows)
    expect_projection_rejected(
        "virtual object length differs from raw object length",
        projection_kat,
        lambda value: value["mapping_phase_records"][0]["s16_virtual_projection"].__setitem__("object_len", 1),
        kat_rows["_sentinels"],
    )
    post_lookup_kat = build_observation_sample(observation_schema, "OL05", kat_rows)
    post_lookup_kat["assignment"]["planned_variant_id"] = "AFTER_OPEN"
    require(not schema_instance_errors(observation_schema, post_lookup_kat, observation_schema), "post-lookup assignment mutation unexpectedly violates schema")
    require(phase_hashes_valid(post_lookup_kat), "planned label unexpectedly participates in classification-input digest")
    require(not assignment_matches_recomputed_classification(post_lookup_kat), "post-lookup assignment mismatch was accepted")
    phase_top_kat = build_observation_sample(observation_schema, "OL05", kat_rows)
    phase_top_kat["raw_recovered_state"]["object_sha256"] = "0" * 64
    require(not schema_instance_errors(observation_schema, phase_top_kat, observation_schema), "phase/top mutation unexpectedly violates schema")
    require(phase_hashes_valid(phase_top_kat), "top-level recovered state unexpectedly participates in phase digest")
    require(not every_phase_durable_image_matches_top_level(phase_top_kat), "phase/top durable image mismatch was accepted")
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    del ol04["restart_observation"]["fresh_process_nonce_sha256"]
    expect_instance_rejected("fresh nonce absent", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["custody"]["custody_sequence"] = 2
    ol04["custody"]["previous_custody_entry_sha256"] = None
    expect_instance_rejected("broken custody predecessor", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["raw_recovered_state"]["object_sha256"] = "d" * 64
    expect_instance_rejected("ABSENT object with hash", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["mapping_phase_records"][0]["classification"]["mapping_cardinality"] = 0
    expect_instance_rejected("unique mapping cardinality zero", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    del ol04["mapping_phase_records"][0]["raw_phase_measurement"]
    expect_instance_rejected("phase raw measurement absent", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["mapping_phase_records"][0]["raw_phase_measurement"]["planned_variant_id"] = "CRASH_AT_EMPTY_RESTART"
    expect_instance_rejected("planned label injected into phase raw measurement", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["mapping_phase_records"][0]["raw_phase_measurement"]["restarted_after_crash"] = "true"
    expect_instance_rejected("phase lifecycle restart is not boolean", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["mapping_phase_records"][0]["raw_phase_measurement"]["ack_receipt_sha256"] = "d" * 64
    expect_instance_rejected("unobserved ack carries payload", observation_schema, ol04)
    ol00 = build_observation_sample(observation_schema, "OL00", kat_rows)
    ol00["mapping_phase_records"][0]["raw_phase_measurement"]["ack_witness_sha256"] = None
    expect_instance_rejected("observed ack omits payload", observation_schema, ol00)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["mapping_phase_records"][0]["raw_phase_measurement"]["object_sha256"] = "d" * 64
    expect_instance_rejected("raw absent object carries S16 sentinel", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["mapping_phase_records"][0]["s16_virtual_projection"]["owned_lab_durability_observation_count"] = 1
    expect_instance_rejected("virtual S16 projection imports S17 evidence count", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["custody"]["trusted_time_obtained"] = True
    expect_instance_rejected("fabricated trusted time", observation_schema, ol04)
    ol04 = build_observation_sample(observation_schema, "OL04", kat_rows)
    ol04["custody"]["independent_failure_domain_proved"] = True
    expect_instance_rejected("same-host independence", observation_schema, ol04)
    try:
        parse_json_text('{"schema":"a","schema":"b"}', "duplicate-self-test")
    except CheckFailure:
        pass
    else:
        raise CheckFailure("duplicate JSON key mutation was accepted")
    try:
        parse_json_text('{"value":1.5}', "float-self-test")
    except CheckFailure:
        pass
    else:
        raise CheckFailure("floating-point JSON mutation was accepted")


def receipt_rows(repo: Path, bundle: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    plan = bundle["plan"]
    rows = [
        ("schema", "agent_bridge.memory_temporal_recovered_envelope_owned_lab_process_crash_restart_s17_validation_receipt.v0"),
        ("status", STATUS),
        ("decision", DECISION),
        ("family_namespace", "OL00_OL04_OL05_FIRST_BATCH"),
        ("family_count", "3"),
        ("scenario_count", "60"),
        ("repetition_count", "1"),
        ("assigned_attempt_count", "60"),
        ("planned_pidfd_sigkill_attempt_count", "59"),
        ("planned_distinct_fresh_exec_read_count", "59"),
        ("clean_control_attempt_count", "1"),
        ("planned_d05_first_and_restart_phase_record_count", "106"),
        ("planned_total_s16_mapping_phase_record_count", "113"),
        ("full_catalog_augmented_fingerprint_count", "5639"),
        ("full_catalog_duplicate_fingerprint_count", "0"),
        ("full_catalog_maximum_fingerprint_multiplicity", "1"),
        ("full_catalog_observed_ack_payload_binding_count", "5"),
        ("target_phase_unique_match_count", "113"),
        ("target_phase_zero_match_count", "0"),
        ("target_phase_multiple_match_count", "0"),
        ("actual_assigned_attempt_count", str(plan["schedule"]["actual_assigned_attempt_count"])),
        ("actual_sigkill_attempt_count", str(plan["schedule"]["actual_sigkill_attempt_count"])),
        ("actual_fresh_process_read_count", str(plan["schedule"]["actual_fresh_process_read_count"])),
        ("actual_s16_mapping_phase_record_count", str(plan["schedule"]["actual_s16_mapping_phase_record_count"])),
        ("owned_lab_durability_observation_count", str(plan["current_accounting"]["owned_lab_durability_observation_count"])),
        ("provider_durability_observation_count", str(plan["current_accounting"]["provider_durability_observation_count"])),
        ("production_validated_evidence_items", str(plan["current_accounting"]["production_validated_evidence_items"])),
        ("global_runtime_prerequisites_satisfied", "0"),
        ("global_runtime_prerequisites_total", "16"),
        ("claim_level", CLAIM_LEVEL),
        ("candidate_filesystem", "f2fs"),
        ("owner_resource_decision_recorded", "false"),
        ("positive_owner_decision_admissible_in_v0_schema", "false"),
        ("cross_field_semantic_and_signature_validator_implemented", "false"),
        ("runner_implemented", "false"),
        ("side_effects_unlocked", "NONE"),
    ]
    for label, path in (
        ("plan_sha256", PLAN_PATH),
        ("observation_schema_sha256", OBSERVATION_SCHEMA_PATH),
        ("owner_resource_decision_schema_sha256", OWNER_SCHEMA_PATH),
        ("successor_gate_sha256", SUCCESSOR_PATH),
        ("synthetic_fixture_sha256", SYNTHETIC_PATH),
        ("checker_sha256", CHECKER_PATH),
        ("source_gate_sha256", GATE_PATH),
    ):
        rows.append((label, artifact_sha256(repo, path)))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]

    for path, expected in FROZEN_PREDECESSOR_ARTIFACTS.items():
        require(artifact_sha256(repo, path) == expected, f"frozen predecessor artifact drift: {path}")
    kat_rows = validate_full_catalog_uniqueness(repo)

    bundle = {
        "plan": load_json(repo, PLAN_PATH),
        "observation": load_json(repo, OBSERVATION_SCHEMA_PATH),
        "owner": load_json(repo, OWNER_SCHEMA_PATH),
        "successor": load_json(repo, SUCCESSOR_PATH),
        "synthetic": load_json(repo, SYNTHETIC_PATH),
    }
    design = read_text(repo, DESIGN_PATH)
    report = read_text(repo, REPORT_PATH)
    validate_bundle(bundle, design, report, kat_rows)
    if args.self_test:
        self_test(bundle, design, report, kat_rows)
    for key, value in receipt_rows(repo, bundle):
        print(f"{key}\t{value}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(f"S17 preregistration check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
