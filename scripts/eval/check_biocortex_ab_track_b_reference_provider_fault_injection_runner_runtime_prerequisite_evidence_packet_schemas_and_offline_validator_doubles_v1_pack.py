#!/usr/bin/env python3
"""Independent checker for runtime-prerequisite evidence packet validator doubles."""

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
from typing import Any, Callable, Mapping, Sequence


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
MODULE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1.py"
)
CHECKER_REL = (
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_pack.py"
)
EVIDENCE_SCHEMA_REL = (
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-"
    "runtime-prerequisite-evidence-packet-schema-v1.json"
)
OWNER_SCHEMA_REL = (
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-"
    "owner-decision-packet-schema-v1.json"
)
FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_"
    "pack_synthetic_v0.json"
)
EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_"
    "pack.expected.v0.tsv"
)
PREDECESSOR_MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_pack_v0.json"
)
PREDECESSOR_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_"
    "pack_synthetic_v0.json"
)

TRACKS = (
    "MANAGED_SPANNER_CLOUD_KMS",
    "SELF_HOSTED_ETCD_OPENBAO",
)
OWNER_DECISIONS = (
    "PENDING_PREREQUISITE_EVIDENCE",
    "REJECTED_FAIL_CLOSED",
)
OWNER_REASONS = (
    "WAITING_FOR_ALL_EVIDENCE",
    "EVIDENCE_VALIDATION_FAILED",
    "EVIDENCE_FRESHNESS_FAILED",
    "EVIDENCE_BINDING_FAILED",
    "OWNER_DECISION_PENDING",
    "POSITIVE_DECISION_NOT_REPRESENTABLE",
)
DOWNSTREAM_GATES = (
    "CONDITION_OUTPUT_GATE",
    "OUTPUT_PERMIT_GATE",
    "SCIENTIFIC_CLAIM_GATE",
    "APPLICATION_CLAIM_GATE",
)
EXPECTED_PARTITIONS = (
    "GLOBAL",
    "MANAGED_ONLY",
    "SELF_HOSTED_ONLY",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "DUAL_TRACK_SEPARATE",
    "GLOBAL",
)

TSV_FIELDS = (
    "schema",
    "status",
    "decision",
    "date",
    "tracks_represented",
    "packet_schema_count",
    "evidence_packet_schema_count",
    "owner_packet_schema_count",
    "offline_validator_double_count",
    "synthetic_packet_count",
    "schema_conformant_count",
    "offline_double_conformant_count",
    "freshness_arithmetic_conformant_count",
    "real_evidence_items_present",
    "production_validated_evidence_items",
    "runtime_evidence_accepted",
    "runtime_prerequisites_satisfied",
    "owner_identity_bound",
    "owner_decision_recorded",
    "positive_decision_representable",
    "downstream_gates_authorized",
    "downstream_separate_gate_count",
    "nonclaim_field_count",
    "all_nonclaims_explicit",
    "provider_calls",
    "wire_attempts",
    "credentials_accessed",
    "runtime_rows",
    "experiment_rows",
    "condition_outputs",
    "output_permits",
    "real_currentness_proved",
    "runtime_admission_ready",
    "runtime_admission_granted",
    "runtime_authority",
    "side_effects_unlocked",
    "predecessor_manifest_sha256",
    "predecessor_fixture_sha256",
    "predecessor_plan_sha256",
    "evidence_schema_sha256",
    "owner_schema_sha256",
    "packet_profile_catalog_sha256",
    "synthetic_packet_set_sha256",
    "case_results_sha256",
    "nonclaims_sha256",
    "content_sha256",
    "next_unit",
)


class CheckError(ValueError):
    """Independent pack validation failure."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: set[str], code: str) -> None:
    require(set(value) == expected, code, "closed-world key set drift")


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(relative: str) -> str:
    path = ROOT / relative
    require(path.is_file(), "E_FILE_MISSING", relative)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_key(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    require(key in result, "E_HASH_FIELD", key)
    del result[key]
    return result


def is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "E_DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def read_json(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    require(path.is_file(), "E_FILE_MISSING", relative)
    try:
        raw = path.read_bytes().decode("utf-8", errors="strict")
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CheckError(f"E_NONFINITE_JSON: {token}")
            ),
        )
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {relative}") from error
    require(type(value) is dict, "E_JSON_ROOT", relative)
    return value


def read_expected() -> str:
    path = ROOT / EXPECTED_REL
    require(path.is_file(), "E_EXPECTED_MISSING", EXPECTED_REL)
    try:
        return path.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise CheckError(f"E_EXPECTED_UTF8: {EXPECTED_REL}") from error


def check_json_decoder_guards() -> None:
    try:
        json.loads('{"a":1,"a":2}', object_pairs_hook=_reject_duplicate_pairs)
    except CheckError:
        pass
    else:
        raise CheckError("E_DUPLICATE_JSON_PROBE: duplicate key accepted")
    try:
        json.loads(
            '{"value":NaN}',
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CheckError(f"E_NONFINITE_JSON: {token}")
            ),
        )
    except CheckError:
        pass
    else:
        raise CheckError("E_NONFINITE_JSON_PROBE: nonfinite value accepted")


def load_module() -> ModuleType:
    path = (ROOT / MODULE_REL).resolve()
    require(path.is_file(), "E_MODULE_MISSING", MODULE_REL)
    spec = importlib.util.spec_from_file_location(
        "runtime_prerequisite_evidence_packet_validator_doubles_v1",
        path,
    )
    require(spec is not None and spec.loader is not None, "E_MODULE_LOAD", "spec")
    require(
        spec.origin is not None and Path(spec.origin).resolve() == path,
        "E_MODULE_PATH",
        "origin drift",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    require(
        Path(module.__file__).resolve() == path,
        "E_MODULE_PATH",
        "loaded path drift",
    )
    return module


def check_source_purity() -> None:
    path = ROOT / MODULE_REL
    require(path.is_file(), "E_MODULE_MISSING", MODULE_REL)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=MODULE_REL)
    allowed_import_roots = {
        "__future__",
        "copy",
        "dataclasses",
        "datetime",
        "hashlib",
        "json",
        "re",
        "typing",
    }
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
        "today",
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
                require(
                    alias.name.split(".")[0] in allowed_import_roots,
                    "E_AST_IMPORT",
                    alias.name,
                )
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            require(root in allowed_import_roots, "E_AST_IMPORT", node.module or "")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(
                    node.func.id not in forbidden_calls,
                    "E_AST_CALL",
                    node.func.id,
                )
            elif isinstance(node.func, ast.Attribute):
                require(
                    node.func.attr not in forbidden_attrs,
                    "E_AST_CALL",
                    node.func.attr,
                )


def validate_predecessor(
    module: ModuleType,
    manifest: dict[str, Any],
    fixture: dict[str, Any],
) -> list[dict[str, Any]]:
    require(
        sha256_value(manifest) == module.PREDECESSOR_MANIFEST_CANONICAL_SHA256,
        "E_PREDECESSOR_MANIFEST_HASH",
        "manifest",
    )
    require(
        sha256_value(fixture) == module.PREDECESSOR_FIXTURE_CANONICAL_SHA256,
        "E_PREDECESSOR_FIXTURE_HASH",
        "fixture",
    )
    require(
        manifest.get("schema") == module.PREDECESSOR_MANIFEST_SCHEMA,
        "E_PREDECESSOR_MANIFEST_SCHEMA",
        "schema",
    )
    require(manifest.get("status") == module.PREDECESSOR_STATUS, "E_PREDECESSOR_STATUS", "status")
    require(
        manifest.get("decision") == module.PREDECESSOR_DECISION,
        "E_PREDECESSOR_DECISION",
        "decision",
    )
    require(
        manifest.get("next_unit") == module.PREDECESSOR_NEXT_UNIT,
        "E_PREDECESSOR_NEXT",
        "next unit",
    )
    results = manifest.get("results")
    require(type(results) is dict, "E_PREDECESSOR_RESULTS", "not object")
    require(results.get("prerequisite_plan_count") == 16, "E_PREDECESSOR_RESULTS", "plan count")
    require(results.get("evidence_items_present") == 0, "E_PREDECESSOR_RESULTS", "evidence")
    require(results.get("prerequisites_satisfied") == 0, "E_PREDECESSOR_RESULTS", "satisfied")
    require(results.get("positive_decision_representable") is False, "E_PREDECESSOR_RESULTS", "positive")

    require(fixture.get("schema") == module.PREDECESSOR_FIXTURE_SCHEMA, "E_PREDECESSOR_FIXTURE_SCHEMA", "schema")
    require(fixture.get("synthetic_only") is True, "E_PREDECESSOR_SYNTHETIC", "flag")
    require(fixture.get("tracks") == list(TRACKS), "E_PREDECESSOR_TRACKS", "tracks")
    plan = fixture.get("prerequisite_evidence_plan")
    require(type(plan) is list and len(plan) == 16, "E_PREDECESSOR_PLAN", "count")
    require(sha256_value(plan) == module.PREDECESSOR_PLAN_SHA256, "E_PREDECESSOR_PLAN_HASH", "plan")
    prerequisite_ids: list[str] = []
    for index, row in enumerate(plan):
        require(type(row) is dict, "E_PREDECESSOR_PLAN_ROW", str(index))
        prerequisite_id = row.get("prerequisite_id")
        require(type(prerequisite_id) is str and prerequisite_id, "E_PREDECESSOR_PLAN_ID", str(index))
        prerequisite_ids.append(prerequisite_id)
        reasons = row.get("rejection_reasons")
        require(
            type(reasons) is list
            and len(reasons) == 4
            and len(set(reasons)) == 4
            and all(type(reason) is str and reason for reason in reasons),
            "E_PREDECESSOR_REJECTIONS",
            prerequisite_id,
        )
        require(row.get("plan_status") == "PREREGISTERED_NOT_COLLECTED", "E_PREDECESSOR_PLAN_STATUS", prerequisite_id)
        require(row.get("evidence_present") is False, "E_PREDECESSOR_PLAN_EVIDENCE", prerequisite_id)
        require(row.get("satisfied") is False, "E_PREDECESSOR_PLAN_SATISFIED", prerequisite_id)
    require(len(prerequisite_ids) == len(set(prerequisite_ids)) == 16, "E_PREDECESSOR_PLAN_ID", "duplicates")
    owner = fixture.get("owner_decision_preregistration")
    require(type(owner) is dict, "E_PREDECESSOR_OWNER", "not object")
    require(owner.get("allowed_current_decisions") == list(OWNER_DECISIONS), "E_PREDECESSOR_OWNER", "decisions")
    require(owner.get("current_decision_recorded") is False, "E_PREDECESSOR_OWNER", "recorded")
    require(owner.get("positive_decision_representable") is False, "E_PREDECESSOR_OWNER", "positive")
    return copy.deepcopy(plan)


def validate_boundary_schema(definition: Any, code: str) -> None:
    require(type(definition) is dict, code, "not object")
    require(definition.get("type") == "object", code, "type")
    require(definition.get("additionalProperties") is False, code, "closed world")
    properties = definition.get("properties")
    required = definition.get("required")
    require(type(properties) is dict and type(required) is list, code, "shape")
    require(set(required) == set(properties), code, "required closure")
    for name, node in properties.items():
        require(type(node) is dict and "const" in node, code, name)
        value = node["const"]
        if name == "side_effects_unlocked":
            require(value == "NONE", code, name)
        elif name == "paid_resources_provisioned" or name.endswith("_created"):
            require(type(value) is int and value == 0, code, name)
        else:
            require(value is False, code, name)


def validate_schemas(
    module: ModuleType,
    evidence_schema: dict[str, Any],
    owner_schema: dict[str, Any],
    plan: Sequence[Mapping[str, Any]],
) -> None:
    require(
        sha256_value(evidence_schema) == module.EVIDENCE_SCHEMA_SHA256,
        "E_EVIDENCE_SCHEMA_CANONICAL_HASH",
        "reviewer constant",
    )
    require(
        sha256_value(owner_schema) == module.OWNER_SCHEMA_SHA256,
        "E_OWNER_SCHEMA_CANONICAL_HASH",
        "reviewer constant",
    )
    require(
        evidence_schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        "E_EVIDENCE_SCHEMA",
        "draft",
    )
    require(
        owner_schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        "E_OWNER_SCHEMA",
        "draft",
    )
    exact_keys(
        evidence_schema,
        {"$defs", "$id", "$schema", "description", "oneOf", "title"},
        "E_EVIDENCE_SCHEMA_ROOT",
    )
    require(
        evidence_schema["oneOf"]
        == [{"$ref": f"#/$defs/packet{index:02d}"} for index in range(1, 16)],
        "E_EVIDENCE_SCHEMA_ONE_OF",
        "ordered branches",
    )
    defs = evidence_schema.get("$defs")
    require(type(defs) is dict, "E_EVIDENCE_SCHEMA_DEFS", "not object")
    common = defs.get("commonPacket")
    require(type(common) is dict, "E_EVIDENCE_SCHEMA_COMMON", "missing")
    common_properties = common.get("properties")
    common_required = common.get("required")
    require(type(common_properties) is dict and type(common_required) is list, "E_EVIDENCE_SCHEMA_COMMON", "shape")
    require(
        common_properties.get("packet_kind", {}).get("const")
        == "SYNTHETIC_VALIDATOR_DOUBLE",
        "E_EVIDENCE_SCHEMA_PACKET_KIND",
        "kind",
    )
    discriminators: list[str] = []
    schema_ids: list[str] = []
    for index, (row, partition) in enumerate(
        zip(plan[:15], EXPECTED_PARTITIONS, strict=True),
        start=1,
    ):
        packet = defs.get(f"packet{index:02d}")
        payload = defs.get(f"payload{index:02d}")
        require(type(packet) is dict and type(payload) is dict, "E_EVIDENCE_SCHEMA_BRANCH", str(index))
        require(packet.get("unevaluatedProperties") is False, "E_EVIDENCE_SCHEMA_BRANCH", f"{index}:closed")
        all_of = packet.get("allOf")
        require(type(all_of) is list and len(all_of) == 2, "E_EVIDENCE_SCHEMA_BRANCH", f"{index}:allOf")
        require(all_of[0] == {"$ref": "#/$defs/commonPacket"}, "E_EVIDENCE_SCHEMA_BRANCH", f"{index}:common")
        branch = all_of[1]
        properties = branch.get("properties")
        require(type(properties) is dict, "E_EVIDENCE_SCHEMA_BRANCH", f"{index}:properties")
        require(
            properties.get("prerequisite_id", {}).get("const") == row["prerequisite_id"],
            "E_EVIDENCE_SCHEMA_DISCRIMINATOR",
            str(index),
        )
        require(
            properties.get("evidence_class", {}).get("const") == row["evidence_class"],
            "E_EVIDENCE_SCHEMA_CLASS",
            str(index),
        )
        require(
            properties.get("owner_class", {}).get("const") == row["owner_class"],
            "E_EVIDENCE_SCHEMA_OWNER",
            str(index),
        )
        require(
            properties.get("track_partition", {}).get("const") == partition,
            "E_EVIDENCE_SCHEMA_TRACK",
            str(index),
        )
        require(
            properties.get("payload", {}).get("$ref") == f"#/$defs/payload{index:02d}",
            "E_EVIDENCE_SCHEMA_PAYLOAD",
            str(index),
        )
        require(payload.get("type") == "object", "E_EVIDENCE_SCHEMA_PAYLOAD", f"{index}:type")
        require(payload.get("additionalProperties") is False, "E_EVIDENCE_SCHEMA_PAYLOAD", f"{index}:closed")
        payload_required = payload.get("required")
        payload_properties = payload.get("properties")
        require(
            type(payload_required) is list
            and type(payload_properties) is dict
            and set(payload_required) == set(payload_properties),
            "E_EVIDENCE_SCHEMA_PAYLOAD",
            f"{index}:required",
        )
        discriminators.append(row["prerequisite_id"])
        schema_ids.append(f"{evidence_schema['$id']}#/$defs/packet{index:02d}")
    require(len(discriminators) == len(set(discriminators)) == 15, "E_EVIDENCE_SCHEMA_DISCRIMINATOR", "duplicates")
    require(len(schema_ids) == len(set(schema_ids)) == 15, "E_EVIDENCE_SCHEMA_ID", "duplicates")
    validate_boundary_schema(defs.get("boundary"), "E_EVIDENCE_SCHEMA_BOUNDARY")

    exact_keys(
        owner_schema,
        {
            "$defs",
            "$id",
            "$schema",
            "additionalProperties",
            "allOf",
            "description",
            "properties",
            "required",
            "title",
            "type",
        },
        "E_OWNER_SCHEMA_ROOT",
    )
    require(owner_schema.get("type") == "object", "E_OWNER_SCHEMA", "type")
    require(owner_schema.get("additionalProperties") is False, "E_OWNER_SCHEMA", "closed world")
    owner_properties = owner_schema.get("properties")
    owner_required = owner_schema.get("required")
    require(type(owner_properties) is dict and type(owner_required) is list, "E_OWNER_SCHEMA", "shape")
    require(set(owner_required) == set(owner_properties), "E_OWNER_SCHEMA", "required closure")
    owner_row = plan[-1]
    require(
        owner_properties.get("packet_kind", {}).get("const")
        == "SYNTHETIC_OWNER_DECISION_VALIDATOR_DOUBLE",
        "E_OWNER_SCHEMA_PACKET_KIND",
        "kind",
    )
    require(
        owner_properties.get("prerequisite_id", {}).get("const")
        == owner_row["prerequisite_id"],
        "E_OWNER_SCHEMA_DISCRIMINATOR",
        "id",
    )
    require(
        owner_properties.get("evidence_class", {}).get("const")
        == owner_row["evidence_class"],
        "E_OWNER_SCHEMA_CLASS",
        "class",
    )
    require(
        owner_properties.get("owner_class", {}).get("const") == owner_row["owner_class"],
        "E_OWNER_SCHEMA_OWNER",
        "owner",
    )
    require(
        owner_properties.get("decision_state", {}).get("enum") == list(OWNER_DECISIONS),
        "E_OWNER_SCHEMA_DECISIONS",
        "vocabulary",
    )
    require(
        owner_properties.get("decision_reason", {}).get("enum") == list(OWNER_REASONS),
        "E_OWNER_SCHEMA_REASONS",
        "vocabulary",
    )
    for name in (
        "owner_identity_bound",
        "decision_recorded",
        "delegated_agent_authority",
        "positive_decision_representable",
    ):
        require(owner_properties.get(name, {}).get("const") is False, "E_OWNER_SCHEMA_FAIL_CLOSED", name)
    all_of = owner_schema.get("allOf")
    require(type(all_of) is list and len(all_of) == 2, "E_OWNER_SCHEMA_TRANSITIONS", "count")
    validate_boundary_schema(owner_schema.get("$defs", {}).get("boundary"), "E_OWNER_SCHEMA_BOUNDARY")


def derive_profiles(
    module: ModuleType,
    specs: Any,
    plan: Sequence[Mapping[str, Any]],
    evidence_schema: Mapping[str, Any],
) -> list[dict[str, Any]]:
    require(type(specs) is list and len(specs) == 16, "E_PROFILE_COUNT", "count")
    require(
        sha256_value(specs) == module.PROFILE_CATALOG_SHA256,
        "E_PROFILE_CATALOG_HASH",
        "reviewer constant",
    )
    expected_keys = {
        "max_age_seconds",
        "offline_validator_id",
        "packet_def",
        "payload_def",
        "prerequisite_id",
    }
    defs = evidence_schema["$defs"]
    profiles: list[dict[str, Any]] = []
    validator_ids: list[str] = []
    for index, (spec, row) in enumerate(zip(specs, plan, strict=True), start=1):
        require(type(spec) is dict, "E_PROFILE", str(index))
        exact_keys(spec, expected_keys, "E_PROFILE_KEYS")
        require(spec["prerequisite_id"] == row["prerequisite_id"], "E_PROFILE_ID", str(index))
        require(spec["packet_def"] == f"packet{index:02d}", "E_PROFILE_PACKET_DEF", str(index))
        require(spec["payload_def"] == f"payload{index:02d}", "E_PROFILE_PAYLOAD_DEF", str(index))
        validator_id = spec["offline_validator_id"]
        require(
            type(validator_id) is str
            and validator_id.startswith("OFFLINE_")
            and validator_id.endswith("_V1"),
            "E_PROFILE_VALIDATOR",
            str(index),
        )
        validator_ids.append(validator_id)
        max_age = spec["max_age_seconds"]
        require(
            max_age is None or (type(max_age) is int and max_age > 0),
            "E_PROFILE_MAX_AGE",
            str(index),
        )
        if index <= 15:
            packet_node = defs[spec["packet_def"]]
            branch_properties = packet_node["allOf"][1]["properties"]
            payload = defs[spec["payload_def"]]
            fields_catalog = list(payload["required"])
            track_partition = branch_properties["track_partition"]["const"]
            packet_schema_id = (
                f"{evidence_schema['$id']}#/$defs/{spec['packet_def']}"
            )
        else:
            fields_catalog = [
                "evidence_set_binding",
                "decision_state",
                "decision_reason",
                "owner_identity_bound",
                "decision_recorded",
            ]
            track_partition = "GLOBAL"
            packet_schema_id = module.OWNER_PACKET_INSTANCE_SCHEMA
        profiles.append(
            {
                "depends_on": copy.deepcopy(row["depends_on"]),
                "evidence_class": row["evidence_class"],
                "evidence_required": row["evidence_required"],
                "freshness_rule": row["freshness_rule"],
                "max_age_seconds": max_age,
                "offline_validator_id": validator_id,
                "owner_class": row["owner_class"],
                "packet_def": spec["packet_def"],
                "packet_schema_id": packet_schema_id,
                "payload_def": spec["payload_def"],
                "plan_row_sha256": sha256_value(row),
                "prerequisite_id": row["prerequisite_id"],
                "real_validator_implemented": False,
                "rejection_reasons": copy.deepcopy(row["rejection_reasons"]),
                "required_evidence_fields": fields_catalog,
                "track_partition": track_partition,
                "validation_rule": row["validation_rule"],
            }
        )
    require(len(validator_ids) == len(set(validator_ids)) == 16, "E_PROFILE_VALIDATOR", "duplicates")
    require(
        profiles[-1]["depends_on"]
        == [row["prerequisite_id"] for row in plan[:-1]],
        "E_OWNER_PROFILE_DEPENDENCY",
        "dependencies",
    )
    return profiles


def validate_fixture(
    module: ModuleType,
    fixture: dict[str, Any],
    plan: Sequence[Mapping[str, Any]],
    evidence_schema: Mapping[str, Any],
) -> list[dict[str, Any]]:
    require(
        sha256_value(fixture) == module.FIXTURE_SHA256,
        "E_FIXTURE_CANONICAL_HASH",
        "reviewer constant",
    )
    exact_keys(
        fixture,
        {
            "date",
            "downstream_separate_gates",
            "expected",
            "nonclaims",
            "packet_profile_specs",
            "predecessor",
            "schema",
            "synthetic_context",
            "synthetic_only",
            "tracks",
        },
        "E_FIXTURE_KEYS",
    )
    require(fixture["schema"] == module.FIXTURE_SCHEMA, "E_FIXTURE_SCHEMA", "schema")
    require(fixture["date"] == "2026-07-17", "E_FIXTURE_DATE", "date")
    require(fixture["synthetic_only"] is True, "E_FIXTURE_SYNTHETIC", "flag")
    require(fixture["tracks"] == list(TRACKS), "E_FIXTURE_TRACKS", "tracks")
    predecessor = fixture["predecessor"]
    require(type(predecessor) is dict, "E_FIXTURE_PREDECESSOR", "not object")
    require(predecessor.get("source_commit") == module.PREDECESSOR_SOURCE_COMMIT, "E_FIXTURE_PREDECESSOR", "source")
    require(
        predecessor.get("integration_commit") == module.PREDECESSOR_INTEGRATION_COMMIT,
        "E_FIXTURE_PREDECESSOR",
        "integration",
    )
    require(
        predecessor.get("manifest_sha256")
        == module.PREDECESSOR_MANIFEST_FILE_SHA256
        == file_sha256(PREDECESSOR_MANIFEST_REL),
        "E_FIXTURE_PREDECESSOR",
        "manifest",
    )
    require(
        predecessor.get("fixture_sha256")
        == module.PREDECESSOR_FIXTURE_FILE_SHA256
        == file_sha256(PREDECESSOR_FIXTURE_REL),
        "E_FIXTURE_PREDECESSOR",
        "fixture",
    )
    require(predecessor.get("plan_sha256") == module.PREDECESSOR_PLAN_SHA256, "E_FIXTURE_PREDECESSOR", "plan")

    downstream = fixture["downstream_separate_gates"]
    require(type(downstream) is list and len(downstream) == 4, "E_DOWNSTREAM_COUNT", "count")
    for row, gate_id in zip(downstream, DOWNSTREAM_GATES, strict=True):
        require(
            row
            == {
                "authorized": False,
                "gate_id": gate_id,
                "status": "SEPARATE_NOT_AUTHORIZED",
            },
            "E_DOWNSTREAM_GATE",
            gate_id,
        )

    nonclaims = fixture["nonclaims"]
    require(type(nonclaims) is dict and nonclaims, "E_NONCLAIMS", "not object")
    require(sha256_value(nonclaims) == module.NONCLAIMS_SHA256, "E_NONCLAIMS_HASH", "reviewer constant")
    for name, value in nonclaims.items():
        if name == "side_effects_unlocked":
            require(value == "NONE", "E_NONCLAIMS", name)
        else:
            require(type(value) is bool and value is False, "E_NONCLAIMS", name)

    expected = fixture["expected"]
    require(type(expected) is dict and expected, "E_EXPECTED", "not object")
    require(sha256_value(expected) == module.EXPECTED_SHA256, "E_EXPECTED_HASH", "reviewer constant")
    require(expected.get("packet_schema_count") == 16, "E_EXPECTED", "packet schemas")
    require(expected.get("evidence_packet_schema_count") == 15, "E_EXPECTED", "evidence schemas")
    require(expected.get("owner_packet_schema_count") == 1, "E_EXPECTED", "owner schema")
    require(expected.get("offline_validator_double_count") == 16, "E_EXPECTED", "validators")
    require(expected.get("real_evidence_items_present") == 0, "E_EXPECTED", "evidence")
    require(expected.get("production_validated_evidence_items") == 0, "E_EXPECTED", "validated")
    require(expected.get("runtime_prerequisites_satisfied") == 0, "E_EXPECTED", "satisfied")
    require(expected.get("positive_decision_representable") is False, "E_EXPECTED", "positive")
    require(expected.get("downstream_gates_authorized") == 0, "E_EXPECTED", "downstream")

    context = fixture["synthetic_context"]
    require(type(context) is dict, "E_CONTEXT", "not object")
    exact_keys(
        context,
        {
            "checked_at_utc",
            "fixture_identity_sha256",
            "generator_build_sha256",
            "observed_at_utc",
            "validator_build_sha256",
        },
        "E_CONTEXT_KEYS",
    )
    require(
        type(context["observed_at_utc"]) is str
        and type(context["checked_at_utc"]) is str
        and context["observed_at_utc"] <= context["checked_at_utc"],
        "E_CONTEXT_TIME",
        "order",
    )
    for name in (
        "fixture_identity_sha256",
        "generator_build_sha256",
        "validator_build_sha256",
    ):
        require(is_sha256(context[name]), "E_CONTEXT_HASH", name)
    return derive_profiles(
        module,
        fixture["packet_profile_specs"],
        plan,
        evidence_schema,
    )


def validate_receipt(
    module: ModuleType,
    receipt: dict[str, Any],
    manifest: Mapping[str, Any],
    predecessor_fixture: Mapping[str, Any],
    plan: Sequence[Mapping[str, Any]],
    evidence_schema: Mapping[str, Any],
    owner_schema: Mapping[str, Any],
    fixture: Mapping[str, Any],
    profiles: Sequence[Mapping[str, Any]],
) -> None:
    exact_keys(receipt, set(TSV_FIELDS) | {"case_results"}, "E_RECEIPT_KEYS")
    require(receipt["schema"] == module.RECEIPT_SCHEMA, "E_RECEIPT_SCHEMA", "schema")
    require(receipt["status"] == module.STATUS, "E_RECEIPT_STATUS", "status")
    require(receipt["decision"] == module.DECISION, "E_RECEIPT_DECISION", "decision")
    require(receipt["next_unit"] == module.NEXT_UNIT, "E_RECEIPT_NEXT", "next unit")
    exact_counts = {
        "tracks_represented": 2,
        "packet_schema_count": 16,
        "evidence_packet_schema_count": 15,
        "owner_packet_schema_count": 1,
        "offline_validator_double_count": 16,
        "synthetic_packet_count": 16,
        "schema_conformant_count": 16,
        "offline_double_conformant_count": 16,
        "freshness_arithmetic_conformant_count": 15,
        "real_evidence_items_present": 0,
        "production_validated_evidence_items": 0,
        "runtime_evidence_accepted": 0,
        "runtime_prerequisites_satisfied": 0,
        "downstream_gates_authorized": 0,
        "downstream_separate_gate_count": 4,
        "provider_calls": 0,
        "wire_attempts": 0,
        "credentials_accessed": 0,
        "runtime_rows": 0,
        "experiment_rows": 0,
        "condition_outputs": 0,
        "output_permits": 0,
    }
    for name, expected in exact_counts.items():
        require(receipt[name] == expected and type(receipt[name]) is int, "E_RECEIPT_COUNT", name)
    for name in (
        "owner_identity_bound",
        "owner_decision_recorded",
        "positive_decision_representable",
        "real_currentness_proved",
        "runtime_admission_ready",
        "runtime_admission_granted",
        "runtime_authority",
    ):
        require(receipt[name] is False, "E_RECEIPT_BOUNDARY", name)
    require(receipt["all_nonclaims_explicit"] is True, "E_RECEIPT_NONCLAIMS", "explicit")
    require(receipt["nonclaim_field_count"] == len(fixture["nonclaims"]), "E_RECEIPT_NONCLAIMS", "count")
    require(receipt["side_effects_unlocked"] == "NONE", "E_RECEIPT_SIDE_EFFECTS", "side effects")

    case_results = receipt["case_results"]
    require(type(case_results) is list and len(case_results) == 16, "E_CASE_RESULTS", "count")
    expected_case_keys = {
        "offline_double_conformant",
        "packet_id_sha256",
        "packet_schema_id",
        "prerequisite_disposition",
        "prerequisite_id",
        "primary_reason",
        "real_evidence_items",
        "runtime_evidence_disposition",
        "schema_conformant",
        "schema_disposition",
    }
    for index, (case, profile) in enumerate(zip(case_results, profiles, strict=True)):
        require(type(case) is dict, "E_CASE_RESULT", str(index))
        exact_keys(case, expected_case_keys, "E_CASE_RESULT_KEYS")
        require(case["prerequisite_id"] == profile["prerequisite_id"], "E_CASE_RESULT_ID", str(index))
        require(case["packet_schema_id"] == profile["packet_schema_id"], "E_CASE_RESULT_SCHEMA", str(index))
        require(is_sha256(case["packet_id_sha256"]), "E_CASE_RESULT_PACKET", str(index))
        require(case["offline_double_conformant"] is True, "E_CASE_RESULT_CONFORMANCE", str(index))
        require(case["schema_conformant"] is True, "E_CASE_RESULT_CONFORMANCE", str(index))
        require(case["prerequisite_disposition"] == "PENDING_NOT_COLLECTED", "E_CASE_RESULT_DISPOSITION", str(index))
        require(case["runtime_evidence_disposition"] == "NOT_EVALUATED_OUT_OF_SCOPE", "E_CASE_RESULT_DISPOSITION", str(index))
        require(case["schema_disposition"] == "CONFORMANT_SYNTHETIC_VALIDATOR_DOUBLE", "E_CASE_RESULT_DISPOSITION", str(index))
        require(case["real_evidence_items"] == 0, "E_CASE_RESULT_EVIDENCE", str(index))
        expected_reason = (
            "WAITING_FOR_ALL_EVIDENCE"
            if index == 15
            else "SYNTHETIC_INPUT_NOT_RUNTIME_EVIDENCE"
        )
        require(case["primary_reason"] == expected_reason, "E_CASE_RESULT_REASON", str(index))

    require(receipt["case_results_sha256"] == sha256_value(case_results), "E_RECEIPT_HASH", "cases")
    require(receipt["predecessor_manifest_sha256"] == sha256_value(manifest), "E_RECEIPT_HASH", "predecessor manifest")
    require(
        receipt["predecessor_fixture_sha256"] == sha256_value(predecessor_fixture),
        "E_RECEIPT_HASH",
        "predecessor fixture",
    )
    require(receipt["predecessor_plan_sha256"] == sha256_value(plan), "E_RECEIPT_HASH", "predecessor plan")
    require(receipt["evidence_schema_sha256"] == sha256_value(evidence_schema), "E_RECEIPT_HASH", "evidence schema")
    require(receipt["owner_schema_sha256"] == sha256_value(owner_schema), "E_RECEIPT_HASH", "owner schema")
    require(
        receipt["packet_profile_catalog_sha256"] == sha256_value(profiles),
        "E_RECEIPT_HASH",
        "profiles",
    )
    require(
        receipt["synthetic_packet_set_sha256"]
        == sha256_value(
            {
                "canonicalization": module.PACKET_SET_CANONICALIZATION,
                "domain": module.PACKET_SET_HASH_DOMAIN,
                "ordered_packet_id_sha256": [
                    case["packet_id_sha256"] for case in case_results[:15]
                ],
            }
        ),
        "E_RECEIPT_HASH",
        "synthetic packet set",
    )
    require(receipt["nonclaims_sha256"] == sha256_value(fixture["nonclaims"]), "E_RECEIPT_HASH", "nonclaims")
    require(
        receipt["content_sha256"] == sha256_value(without_key(receipt, "content_sha256")),
        "E_RECEIPT_HASH",
        "content",
    )


def render_tsv(receipt: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for field in TSV_FIELDS:
        require(field in receipt, "E_TSV_FIELD", field)
        value = receipt[field]
        rendered = "true" if value is True else "false" if value is False else str(value)
        require("\t" not in rendered and "\n" not in rendered, "E_TSV_VALUE", field)
        rows.append(f"{field}\t{rendered}")
    return "\n".join(rows) + "\n"


def validate_pack() -> tuple[
    ModuleType,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    str,
]:
    check_source_purity()
    check_json_decoder_guards()
    module = load_module()
    predecessor_manifest = read_json(PREDECESSOR_MANIFEST_REL)
    predecessor_fixture = read_json(PREDECESSOR_FIXTURE_REL)
    evidence_schema = read_json(EVIDENCE_SCHEMA_REL)
    owner_schema = read_json(OWNER_SCHEMA_REL)
    fixture = read_json(FIXTURE_REL)
    plan = validate_predecessor(module, predecessor_manifest, predecessor_fixture)
    validate_schemas(module, evidence_schema, owner_schema, plan)
    profiles = validate_fixture(module, fixture, plan, evidence_schema)
    receipt = module.RuntimePrerequisiteEvidencePacketSchemaReviewer().review(
        copy.deepcopy(predecessor_manifest),
        copy.deepcopy(predecessor_fixture),
        copy.deepcopy(evidence_schema),
        copy.deepcopy(owner_schema),
        copy.deepcopy(fixture),
    )
    require(type(receipt) is dict, "E_RECEIPT", "not object")
    validate_receipt(
        module,
        receipt,
        predecessor_manifest,
        predecessor_fixture,
        plan,
        evidence_schema,
        owner_schema,
        fixture,
        profiles,
    )
    rendered = render_tsv(receipt)
    require(module.render_tsv(receipt) == rendered, "E_TSV_RENDERER", "reviewer drift")
    expected = read_expected()
    require(rendered == expected, "E_EXPECTED_TSV", "byte mismatch")
    return (
        module,
        predecessor_manifest,
        predecessor_fixture,
        evidence_schema,
        owner_schema,
        fixture,
        plan,
        receipt,
        rendered,
    )


ReviewMutator = Callable[
    [
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
    ],
    None,
]

PacketMutator = Callable[[dict[str, Any]], None]


def expect_review_reject(
    module: ModuleType,
    predecessor_manifest: dict[str, Any],
    predecessor_fixture: dict[str, Any],
    evidence_schema: dict[str, Any],
    owner_schema: dict[str, Any],
    fixture: dict[str, Any],
    label: str,
    mutator: ReviewMutator,
) -> None:
    manifest_candidate = copy.deepcopy(predecessor_manifest)
    predecessor_candidate = copy.deepcopy(predecessor_fixture)
    evidence_candidate = copy.deepcopy(evidence_schema)
    owner_candidate = copy.deepcopy(owner_schema)
    fixture_candidate = copy.deepcopy(fixture)
    mutator(
        manifest_candidate,
        predecessor_candidate,
        evidence_candidate,
        owner_candidate,
        fixture_candidate,
    )
    try:
        module.RuntimePrerequisiteEvidencePacketSchemaReviewer().review(
            manifest_candidate,
            predecessor_candidate,
            evidence_candidate,
            owner_candidate,
            fixture_candidate,
        )
    except module.EvidencePacketReviewError:
        return
    raise CheckError(f"E_NEGATIVE_ACCEPTED: {label}")


def artifact_digests(
    predecessor_manifest: Mapping[str, Any],
    predecessor_fixture: Mapping[str, Any],
    evidence_schema: Mapping[str, Any],
    owner_schema: Mapping[str, Any],
    fixture: Mapping[str, Any],
) -> tuple[str, str, str, str, str]:
    return (
        sha256_value(predecessor_manifest),
        sha256_value(predecessor_fixture),
        sha256_value(evidence_schema),
        sha256_value(owner_schema),
        sha256_value(fixture),
    )


def with_content_packet_id(mutator: PacketMutator) -> PacketMutator:
    def wrapped(packet: dict[str, Any]) -> None:
        mutator(packet)
        packet["packet_id_sha256"] = sha256_value(
            without_key(packet, "packet_id_sha256")
        )

    return wrapped


def expect_public_packet_reject(
    module: ModuleType,
    predecessor_manifest: dict[str, Any],
    predecessor_fixture: dict[str, Any],
    evidence_schema: dict[str, Any],
    owner_schema: dict[str, Any],
    fixture: dict[str, Any],
    packet: dict[str, Any],
    label: str,
    expected_reason_prefix: str,
    mutator: PacketMutator,
    *,
    packet_index: int | None,
) -> None:
    call_artifacts = (
        copy.deepcopy(predecessor_manifest),
        copy.deepcopy(predecessor_fixture),
        copy.deepcopy(evidence_schema),
        copy.deepcopy(owner_schema),
        copy.deepcopy(fixture),
    )
    artifacts_before = artifact_digests(*call_artifacts)
    packet_before = sha256_value(packet)
    candidate = copy.deepcopy(packet)
    mutator(candidate)
    reviewer = module.RuntimePrerequisiteEvidencePacketSchemaReviewer()
    rejection: Exception | None = None
    try:
        if packet_index is None:
            reviewer.validate_owner_packet_double(*call_artifacts, candidate)
        else:
            reviewer.validate_evidence_packet_double(
                *call_artifacts,
                packet_index,
                candidate,
            )
    except module.EvidencePacketReviewError as error:
        rejection = error
    require(rejection is not None, "E_SEMANTIC_NEGATIVE_ACCEPTED", label)
    actual_prefix = str(rejection).partition(":")[0]
    require(
        actual_prefix == expected_reason_prefix,
        "E_SEMANTIC_REASON_CODE",
        f"{label}: expected {expected_reason_prefix}, got {actual_prefix}",
    )
    require(
        artifact_digests(*call_artifacts) == artifacts_before,
        "E_SEMANTIC_ARTIFACT_MUTATION",
        label,
    )
    require(sha256_value(packet) == packet_before, "E_SEMANTIC_KAT_MUTATION", label)


def expect_public_owner_accept(
    module: ModuleType,
    predecessor_manifest: dict[str, Any],
    predecessor_fixture: dict[str, Any],
    evidence_schema: dict[str, Any],
    owner_schema: dict[str, Any],
    fixture: dict[str, Any],
    packet: dict[str, Any],
    label: str,
    expected_primary_reason: str,
    mutator: PacketMutator,
) -> None:
    call_artifacts = (
        copy.deepcopy(predecessor_manifest),
        copy.deepcopy(predecessor_fixture),
        copy.deepcopy(evidence_schema),
        copy.deepcopy(owner_schema),
        copy.deepcopy(fixture),
    )
    artifacts_before = artifact_digests(*call_artifacts)
    packet_before = sha256_value(packet)
    candidate = copy.deepcopy(packet)
    mutator(candidate)
    result = module.RuntimePrerequisiteEvidencePacketSchemaReviewer().validate_owner_packet_double(
        *call_artifacts,
        candidate,
    )
    require(type(result) is dict, "E_SEMANTIC_POSITIVE_RESULT", label)
    require(
        result.get("primary_reason") == expected_primary_reason,
        "E_SEMANTIC_POSITIVE_REASON",
        f"{label}: {result.get('primary_reason')}",
    )
    require(
        result.get("packet_id_sha256") == candidate["packet_id_sha256"],
        "E_SEMANTIC_POSITIVE_PACKET_ID",
        label,
    )
    require(
        artifact_digests(*call_artifacts) == artifacts_before,
        "E_SEMANTIC_ARTIFACT_MUTATION",
        label,
    )
    require(sha256_value(packet) == packet_before, "E_SEMANTIC_KAT_MUTATION", label)


def run_self_test(
    module: ModuleType,
    predecessor_manifest: dict[str, Any],
    predecessor_fixture: dict[str, Any],
    evidence_schema: dict[str, Any],
    owner_schema: dict[str, Any],
    fixture: dict[str, Any],
    plan: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    frozen_artifact_paths = (
        PREDECESSOR_MANIFEST_REL,
        PREDECESSOR_FIXTURE_REL,
        EVIDENCE_SCHEMA_REL,
        OWNER_SCHEMA_REL,
        FIXTURE_REL,
    )
    frozen_file_digests_before = tuple(
        file_sha256(path) for path in frozen_artifact_paths
    )
    counts = {
        "artifact_integrity_mutations": 0,
        "rejection_reason_mutations": 0,
        "root_mutations": 0,
        "schema_mutations": 0,
        "track_mutations": 0,
        "freshness_mutations": 0,
        "boundary_mutations": 0,
        "owner_positive_mutations": 0,
        "downstream_mutations": 0,
        "semantic_evidence_mutations": 0,
        "semantic_owner_mutations": 0,
        "valid_rejected_owner_packets": 0,
    }

    def reject(category: str, label: str, mutator: ReviewMutator) -> None:
        expect_review_reject(
            module,
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            fixture,
            label,
            mutator,
        )
        counts[category] += 1

    for profile_index, row in enumerate(plan):
        reasons = row["rejection_reasons"]
        require(len(reasons) == 4, "E_SELF_TEST_REJECTIONS", str(profile_index))
        for reason_index, reason in enumerate(reasons):
            reject(
                "rejection_reason_mutations",
                f"profile-{profile_index + 1:02d}-reason-{reason}",
                lambda _manifest, predecessor, _evidence, _owner, _fixture,
                profile_index=profile_index, reason_index=reason_index, reason=reason: predecessor[
                    "prerequisite_evidence_plan"
                ][profile_index]["rejection_reasons"].__setitem__(
                    reason_index,
                    f"{reason}_DRIFT",
                ),
            )

    reject(
        "root_mutations",
        "fixture-extra",
        lambda _manifest, _predecessor, _evidence, _owner, current: current.__setitem__(
            "extra",
            False,
        ),
    )
    for key in tuple(fixture):
        reject(
            "root_mutations",
            f"fixture-drop-{key}",
            lambda _manifest, _predecessor, _evidence, _owner, current, key=key: current.pop(key),
        )

    def co_mutate_frozen_context(
        _manifest: dict[str, Any],
        _predecessor: dict[str, Any],
        _evidence: dict[str, Any],
        _owner: dict[str, Any],
        current: dict[str, Any],
    ) -> None:
        current["synthetic_context"].update(
            {
                "checked_at_utc": "2035-07-17T12:01:00Z",
                "fixture_identity_sha256": "f" * 64,
                "generator_build_sha256": "e" * 64,
                "observed_at_utc": "2035-07-17T12:00:00Z",
                "validator_build_sha256": "d" * 64,
            }
        )

    reject(
        "root_mutations",
        "fixture-co-mutated-context-and-provenance",
        co_mutate_frozen_context,
    )

    reject(
        "schema_mutations",
        "evidence-schema-extra",
        lambda _manifest, _predecessor, evidence, _owner, _fixture: evidence.__setitem__(
            "extra",
            False,
        ),
    )
    reject(
        "schema_mutations",
        "owner-schema-extra",
        lambda _manifest, _predecessor, _evidence, owner, _fixture: owner.__setitem__(
            "extra",
            False,
        ),
    )
    for index in range(1, 16):
        reject(
            "schema_mutations",
            f"schema-discriminator-{index:02d}",
            lambda _manifest, _predecessor, evidence, _owner, _fixture, index=index: evidence[
                "$defs"
            ][f"packet{index:02d}"]["allOf"][1]["properties"]["prerequisite_id"].__setitem__(
                "const",
                "DRIFT",
            ),
        )

    reject(
        "track_mutations",
        "fixture-track",
        lambda _manifest, _predecessor, _evidence, _owner, current: current["tracks"].__setitem__(
            0,
            "DRIFT",
        ),
    )
    reject(
        "track_mutations",
        "managed-partition",
        lambda _manifest, _predecessor, evidence, _owner, _fixture: evidence["$defs"][
            "packet02"
        ]["allOf"][1]["properties"]["track_partition"].__setitem__("const", "GLOBAL"),
    )

    reject(
        "freshness_mutations",
        "context-time-order",
        lambda _manifest, _predecessor, _evidence, _owner, current: current[
            "synthetic_context"
        ].__setitem__("checked_at_utc", "2026-07-17T00:00:00Z"),
    )
    reject(
        "freshness_mutations",
        "profile-max-age-zero",
        lambda _manifest, _predecessor, _evidence, _owner, current: current[
            "packet_profile_specs"
        ][0].__setitem__("max_age_seconds", 0),
    )
    reject(
        "freshness_mutations",
        "schema-real-currentness",
        lambda _manifest, _predecessor, evidence, _owner, _fixture: evidence["$defs"][
            "freshness"
        ]["properties"]["real_currentness_proved"].__setitem__("const", True),
    )

    nonclaim_keys = tuple(fixture["nonclaims"])
    for key in nonclaim_keys[:4]:
        replacement: Any = "SOME" if key == "side_effects_unlocked" else True
        reject(
            "boundary_mutations",
            f"nonclaim-{key}",
            lambda _manifest, _predecessor, _evidence, _owner, current,
            key=key, replacement=replacement: current["nonclaims"].__setitem__(
                key,
                replacement,
            ),
        )
    reject(
        "boundary_mutations",
        "evidence-boundary-runtime-authority",
        lambda _manifest, _predecessor, evidence, _owner, _fixture: evidence["$defs"][
            "boundary"
        ]["properties"]["runtime_authority"].__setitem__("const", True),
    )
    reject(
        "boundary_mutations",
        "owner-boundary-runtime-authority",
        lambda _manifest, _predecessor, _evidence, owner, _fixture: owner["$defs"][
            "boundary"
        ]["properties"]["runtime_authority"].__setitem__("const", True),
    )

    reject(
        "owner_positive_mutations",
        "owner-positive-representable",
        lambda _manifest, _predecessor, _evidence, owner, _fixture: owner[
            "properties"
        ]["positive_decision_representable"].__setitem__("const", True),
    )
    reject(
        "owner_positive_mutations",
        "owner-admitted-enum",
        lambda _manifest, _predecessor, _evidence, owner, _fixture: owner[
            "properties"
        ]["decision_state"]["enum"].append("ADMITTED"),
    )
    reject(
        "owner_positive_mutations",
        "owner-decision-recorded",
        lambda _manifest, _predecessor, _evidence, owner, _fixture: owner[
            "properties"
        ]["decision_recorded"].__setitem__("const", True),
    )

    for index in range(4):
        reject(
            "downstream_mutations",
            f"downstream-authorize-{index}",
            lambda _manifest, _predecessor, _evidence, _owner, current, index=index: current[
                "downstream_separate_gates"
            ][index].__setitem__("authorized", True),
        )

    require(
        counts["rejection_reason_mutations"] == 64,
        "E_SELF_TEST_REJECTION_COUNT",
        str(counts["rejection_reason_mutations"]),
    )
    artifact_categories = (
        "rejection_reason_mutations",
        "root_mutations",
        "schema_mutations",
        "track_mutations",
        "freshness_mutations",
        "boundary_mutations",
        "owner_positive_mutations",
        "downstream_mutations",
    )
    counts["artifact_integrity_mutations"] = sum(
        counts[name] for name in artifact_categories
    )
    require(
        counts["artifact_integrity_mutations"] == 111,
        "E_SELF_TEST_ARTIFACT_COUNT",
        str(counts["artifact_integrity_mutations"]),
    )

    suite_artifacts = (
        copy.deepcopy(predecessor_manifest),
        copy.deepcopy(predecessor_fixture),
        copy.deepcopy(evidence_schema),
        copy.deepcopy(owner_schema),
        copy.deepcopy(fixture),
    )
    suite_artifacts_before = artifact_digests(*suite_artifacts)
    suite = module.RuntimePrerequisiteEvidencePacketSchemaReviewer().known_answer_packet_suite(
        *suite_artifacts
    )
    require(
        artifact_digests(*suite_artifacts) == suite_artifacts_before,
        "E_SEMANTIC_ARTIFACT_MUTATION",
        "known-answer-suite",
    )
    exact_keys(suite, {"evidence_packets", "owner_packet"}, "E_SEMANTIC_SUITE_KEYS")
    evidence_packets = suite["evidence_packets"]
    owner_packet = suite["owner_packet"]
    require(
        type(evidence_packets) is list and len(evidence_packets) == 15,
        "E_SEMANTIC_SUITE_COUNT",
        "evidence packets",
    )
    require(type(owner_packet) is dict, "E_SEMANTIC_OWNER_PACKET", "not object")

    def evidence_reject(
        label: str,
        packet_index: int,
        expected_reason_prefix: str,
        mutator: PacketMutator,
    ) -> None:
        expect_public_packet_reject(
            module,
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            fixture,
            evidence_packets[packet_index],
            label,
            expected_reason_prefix,
            mutator,
            packet_index=packet_index,
        )
        counts["semantic_evidence_mutations"] += 1

    def owner_reject(
        label: str,
        expected_reason_prefix: str,
        mutator: PacketMutator,
    ) -> None:
        expect_public_packet_reject(
            module,
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            fixture,
            owner_packet,
            label,
            expected_reason_prefix,
            mutator,
            packet_index=None,
        )
        counts["semantic_owner_mutations"] += 1

    evidence_reject(
        "evidence-future-context-drift",
        0,
        "E_PACKET_CONTEXT_BINDING",
        with_content_packet_id(
            lambda packet: packet["freshness"].__setitem__(
                "checked_at_utc",
                "2026-07-17T12:02:00Z",
            )
        ),
    )
    evidence_reject(
        "evidence-invalid-calendar",
        0,
        "E_FRESHNESS_FORMAT",
        with_content_packet_id(
            lambda packet: packet["freshness"].__setitem__(
                "observed_at_utc",
                "2026-02-30T12:00:00Z",
            )
        ),
    )
    for provenance_field in (
        "fixture_sha256",
        "generator_build_sha256",
        "validator_build_sha256",
    ):
        evidence_reject(
            f"evidence-provenance-{provenance_field}-drift",
            0,
            "E_PACKET_PROVENANCE_BINDING",
            with_content_packet_id(
                lambda packet, provenance_field=provenance_field: packet[
                    "synthetic_provenance"
                ].__setitem__(provenance_field, "f" * 64)
            ),
        )
    evidence_reject(
        "evidence-payload-subject-digest-drift",
        0,
        "E_PACKET_KAT_BINDING",
        with_content_packet_id(
            lambda packet: packet["payload"].__setitem__(
                "source_commit_sha256",
                "f" * 64,
            )
        ),
    )
    evidence_reject(
        "evidence-packet-id-drift",
        0,
        "E_PACKET_ID_HASH",
        lambda packet: packet.__setitem__("packet_id_sha256", "0" * 64),
    )
    evidence_reject(
        "packet15-ordered-prerequisite-reverse",
        14,
        "E_PACKET_DEPENDENCY_ORDER",
        with_content_packet_id(
            lambda packet: packet["payload"][
                "ordered_prerequisite_packet_id_sha256"
            ].reverse()
        ),
    )
    evidence_reject(
        "packet15-evidence-set-drift",
        14,
        "E_PACKET_EVIDENCE_SET",
        with_content_packet_id(
            lambda packet: packet["payload"].__setitem__(
                "evidence_set_sha256",
                "f" * 64,
            )
        ),
    )

    def swap_dual_track_binding_and_artifact(packet: dict[str, Any]) -> None:
        track_evidence = packet["payload"]["track_evidence"]
        managed = track_evidence[TRACKS[0]]
        self_hosted = track_evidence[TRACKS[1]]
        managed["binding"], self_hosted["binding"] = (
            self_hosted["binding"],
            managed["binding"],
        )
        managed["synthetic_evidence_artifact_sha256"], self_hosted[
            "synthetic_evidence_artifact_sha256"
        ] = (
            self_hosted["synthetic_evidence_artifact_sha256"],
            managed["synthetic_evidence_artifact_sha256"],
        )

    evidence_reject(
        "dual-track-binding-and-artifact-swap",
        3,
        "E_PACKET_TRACK_BINDING",
        with_content_packet_id(swap_dual_track_binding_and_artifact),
    )

    owner_reject(
        "owner-pending-non-none-evidence-set",
        "E_OWNER_PACKET_STATE_MATRIX",
        with_content_packet_id(
            lambda packet: packet["evidence_set_binding"].__setitem__(
                "evidence_set_sha256",
                "f" * 64,
            )
        ),
    )
    owner_reject(
        "owner-pending-rejected-final-state",
        "E_OWNER_PACKET_STATE_MATRIX",
        with_content_packet_id(
            lambda packet: packet["evidence_set_binding"].__setitem__(
                "final_validation_state",
                "REJECTED_FAIL_CLOSED",
            )
        ),
    )

    def rejected_owner(candidate: dict[str, Any]) -> None:
        candidate["decision_state"] = "REJECTED_FAIL_CLOSED"
        candidate["decision_reason"] = "EVIDENCE_VALIDATION_FAILED"
        binding = candidate["evidence_set_binding"]
        binding["evidence_set_sha256"] = "NONE"
        binding["final_validation_state"] = "REJECTED_FAIL_CLOSED"
        binding["final_validation_at_utc"] = fixture["synthetic_context"][
            "checked_at_utc"
        ]

    def valid_rejected_owner(candidate: dict[str, Any]) -> None:
        rejected_owner(candidate)
        candidate["packet_id_sha256"] = sha256_value(
            without_key(candidate, "packet_id_sha256")
        )

    expect_public_owner_accept(
        module,
        predecessor_manifest,
        predecessor_fixture,
        evidence_schema,
        owner_schema,
        fixture,
        owner_packet,
        "owner-valid-rejected-fail-closed",
        "EVIDENCE_VALIDATION_FAILED",
        valid_rejected_owner,
    )
    counts["valid_rejected_owner_packets"] += 1

    def rejected_owner_invalid_calendar(candidate: dict[str, Any]) -> None:
        rejected_owner(candidate)
        candidate["evidence_set_binding"]["final_validation_at_utc"] = (
            "2026-02-30T12:00:00Z"
        )

    owner_reject(
        "owner-invalid-calendar",
        "E_FRESHNESS_FORMAT",
        with_content_packet_id(rejected_owner_invalid_calendar),
    )
    owner_reject(
        "owner-provenance-invalid-calendar",
        "E_FRESHNESS_FORMAT",
        with_content_packet_id(
            lambda packet: packet["synthetic_provenance"].__setitem__(
                "fixed_checked_at_utc",
                "2026-02-30T12:00:00Z",
            )
        ),
    )
    owner_reject(
        "owner-positive-escalation",
        "E_OWNER_PACKET_POSITIVE",
        with_content_packet_id(
            lambda packet: packet.__setitem__("positive_decision_representable", True)
        ),
    )
    owner_reject(
        "owner-boundary-escalation",
        "E_OWNER_PACKET_BOUNDARY",
        with_content_packet_id(
            lambda packet: packet["boundary"].__setitem__("runtime_authority", True)
        ),
    )

    require(
        counts["semantic_evidence_mutations"] == 10,
        "E_SELF_TEST_SEMANTIC_EVIDENCE_COUNT",
        str(counts["semantic_evidence_mutations"]),
    )
    require(
        counts["semantic_owner_mutations"] == 6,
        "E_SELF_TEST_SEMANTIC_OWNER_COUNT",
        str(counts["semantic_owner_mutations"]),
    )
    require(
        counts["valid_rejected_owner_packets"] == 1,
        "E_SELF_TEST_REJECTED_OWNER_COUNT",
        str(counts["valid_rejected_owner_packets"]),
    )
    require(
        tuple(file_sha256(path) for path in frozen_artifact_paths)
        == frozen_file_digests_before,
        "E_SELF_TEST_FROZEN_ARTIFACT_MUTATION",
        "self-test changed a frozen input",
    )
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    try:
        (
            module,
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            fixture,
            plan,
            _receipt,
            rendered,
        ) = validate_pack()
        print(rendered, end="")
        if args.self_test:
            counts = run_self_test(
                module,
                predecessor_manifest,
                predecessor_fixture,
                evidence_schema,
                owner_schema,
                fixture,
                plan,
            )
            for name in (
                "artifact_integrity_mutations",
                "rejection_reason_mutations",
                "root_mutations",
                "schema_mutations",
                "track_mutations",
                "freshness_mutations",
                "boundary_mutations",
                "owner_positive_mutations",
                "downstream_mutations",
                "semantic_evidence_mutations",
                "semantic_owner_mutations",
                "valid_rejected_owner_packets",
            ):
                print(f"{name}\t{counts[name]}")
            directed_negative_tests = (
                counts["artifact_integrity_mutations"]
                + counts["semantic_evidence_mutations"]
                + counts["semantic_owner_mutations"]
            )
            print(f"directed_negative_tests\t{directed_negative_tests}")
            print("source_ast_purity\tPASS")
    except (
        CheckError,
        json.JSONDecodeError,
        OSError,
        AttributeError,
        KeyError,
        TypeError,
    ) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
