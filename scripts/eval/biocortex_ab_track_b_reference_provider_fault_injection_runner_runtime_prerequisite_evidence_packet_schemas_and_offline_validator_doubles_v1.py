#!/usr/bin/env python3
"""Pure offline evidence-packet schema and validator-double reviewer.

The reviewer consumes caller-supplied immutable mappings.  It performs no file,
environment, ambient-clock, process, network, provider, credential, dynamic
import, random, or entropy I/O.  A conformant synthetic packet remains test
data: this module has no state that can represent accepted production evidence,
prerequisite satisfaction, a positive owner decision, or runtime authority.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
from dataclasses import asdict, dataclass, fields
from typing import Any, Iterable, Mapping, Sequence


RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1."
    "receipt.v0"
)
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1."
    "synthetic.v0"
)
OWNER_PACKET_INSTANCE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "owner_decision_packet.v1"
)
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_"
    "EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES_IMPLEMENTED_"
    "RUNTIME_EVIDENCE_ZERO_NO_AUTHORITY"
)
DECISION = (
    "RUNTIME_PREREQUISITE_EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES_"
    "CONFORMANT_RUNTIME_EVIDENCE_REMAINS_ZERO_FAIL_CLOSED"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "RUNTIME_PREREQUISITE_EVIDENCE_PACKET_OFFLINE_INTEGRATION_AND_"
    "PRODUCTION_EVIDENCE_INGESTION_BOUNDARY_REVIEW"
)
PREDECESSOR_MANIFEST_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1_"
    "pack_manifest.v0"
)
PREDECESSOR_FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_plan_and_owner_decision_preregistration_v1."
    "synthetic.v0"
)
PREDECESSOR_STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_"
    "PLAN_AND_OWNER_DECISION_PREREGISTERED_PENDING_NO_AUTHORITY"
)
PREDECESSOR_DECISION = (
    "RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTERED_"
    "FAIL_CLOSED"
)
PREDECESSOR_NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "RUNTIME_PREREQUISITE_EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES"
)
PREDECESSOR_SOURCE_COMMIT = "ca939cd3e097ebadb6adbea6d2778e2eff71da73"
PREDECESSOR_INTEGRATION_COMMIT = "8af4af0e5ceea8062b65ac06870cabf789567053"
PREDECESSOR_MANIFEST_FILE_SHA256 = (
    "caf420dd4f4d2b310d80bd56ab287f6ef527256c0126a48106438f6a344e6498"
)
PREDECESSOR_FIXTURE_FILE_SHA256 = (
    "156b9a0357f1d5773fdd39be25d832e1d9e2e1df0d766b1947bbcc9cee118db3"
)
PREDECESSOR_MANIFEST_CANONICAL_SHA256 = (
    "59092d560b7df77bcb51d56a4d8974e345f28dfcafeaa7b765f24f27875818c4"
)
PREDECESSOR_FIXTURE_CANONICAL_SHA256 = (
    "279be92874e22e236d6c3db29e72c4602b33bd7fbef6f19c5c4b3608cfbf4d90"
)
PREDECESSOR_PLAN_SHA256 = (
    "260036232778e6d22f2050333b0daeab7d70153a15cb7f36526f47d1514a239b"
)

# Filled only after the two schema artifacts and synthetic fixture are frozen.
EVIDENCE_SCHEMA_SHA256 = "a8b66deefe134afdb17e624bc821aba90c9d5a2490433f6a65276a6bfa63eaac"
OWNER_SCHEMA_SHA256 = "99f2737282f2df568792ced2f2e16820f74eb2820bcbe240eaa97c03cc197086"
PROFILE_CATALOG_SHA256 = "3dd1546ff94469a05e0c22f5184b8c6aada03f9dcd1bc863ad38403c9028a3ed"
NONCLAIMS_SHA256 = "a1bffa33c447d8dce3eb8db9fa709729b483e681f211065661efc58a37714596"
EXPECTED_SHA256 = "70220e9d0b6a149036865ed41008318784cf4af617357bb4173f847c59313a59"
FIXTURE_SHA256 = "236839e4a8e831a84ef11c089cbd624152ddb456e583c2c414ece6c5ebb09f97"

TRACKS = (
    "MANAGED_SPANNER_CLOUD_KMS",
    "SELF_HOSTED_ETCD_OPENBAO",
)
ALLOWED_OWNER_DECISIONS = (
    "PENDING_PREREQUISITE_EVIDENCE",
    "REJECTED_FAIL_CLOSED",
)
DOWNSTREAM_GATE_IDS = (
    "CONDITION_OUTPUT_GATE",
    "OUTPUT_PERMIT_GATE",
    "SCIENTIFIC_CLAIM_GATE",
    "APPLICATION_CLAIM_GATE",
)
NO_MAX_AGE_KAT_HORIZON_SECONDS = 31_536_000
PACKET_SET_HASH_DOMAIN = "AB_TRACK_B_RUNTIME_PREREQUISITE_SYNTHETIC_PACKET_SET_V1"
PACKET_SET_CANONICALIZATION = "AGENT_BRIDGE_CANONICAL_JSON_V1_SORTED_KEYS_INDENT_2_LF"


class EvidencePacketReviewError(ValueError):
    """Fail-closed validation error with a stable reason code."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise EvidencePacketReviewError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: Iterable[str], code: str) -> None:
    require(set(value) == set(expected), code, "closed-world key set drift")


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


def is_sha256(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def without_key(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    del result[key]
    return result


def _synthetic_digest(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class BoundaryNonClaims:
    provider_endpoint_bound: bool
    provider_called: bool
    wire_attempted: bool
    credentials_accessed: bool
    secret_material_present: bool
    paid_resource_provisioned: bool
    production_authority_verifier_implemented: bool
    production_managed_adapter_implemented: bool
    production_self_hosted_adapter_implemented: bool
    production_stop_control_implemented: bool
    production_validator_implemented: bool
    real_evidence_collected: bool
    production_validated_evidence_present: bool
    evidence_receipt_accepted: bool
    runtime_evidence_accepted: bool
    runtime_prerequisite_satisfied: bool
    owner_identity_bound: bool
    owner_decision_recorded: bool
    positive_owner_decision_representable: bool
    positive_runtime_decision_recorded: bool
    owner_decision_authority_exercised: bool
    real_runner_launched: bool
    runtime_row_created: bool
    experiment_row_created: bool
    condition_output_authorized: bool
    output_permit_defined: bool
    runtime_admission_ready: bool
    runtime_admission_granted: bool
    runtime_authority: bool
    deployment_authorized: bool
    scientific_claim_authorized: bool
    application_claim_authorized: bool
    schema_receipt_is_evidence_receipt: bool
    validator_double_receipt_is_execution_authority: bool
    validator_double_receipt_is_output_permit: bool
    validator_double_is_runtime_admission: bool
    synthetic_fixture_is_production_evidence: bool
    side_effects_unlocked: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BoundaryNonClaims":
        names = tuple(field.name for field in fields(cls))
        exact_keys(value, names, "E_NONCLAIM_KEYS")
        for name in names:
            item = value[name]
            if name == "side_effects_unlocked":
                require(type(item) is str, "E_NONCLAIM_TYPE", name)
            else:
                require(type(item) is bool, "E_NONCLAIM_TYPE", name)
        return cls(**dict(value))

    def all_explicit(self) -> bool:
        values = asdict(self)
        for name, value in values.items():
            if name == "side_effects_unlocked":
                if value != "NONE":
                    return False
            elif type(value) is not bool or value:
                return False
        return True

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _validate_predecessor_manifest(manifest: Mapping[str, Any]) -> None:
    require(
        sha256_value(manifest) == PREDECESSOR_MANIFEST_CANONICAL_SHA256,
        "E_PREDECESSOR_MANIFEST_HASH",
        "manifest drift",
    )
    require(
        manifest.get("schema") == PREDECESSOR_MANIFEST_SCHEMA,
        "E_PREDECESSOR_MANIFEST_SCHEMA",
        "schema",
    )
    require(
        manifest.get("status") == PREDECESSOR_STATUS,
        "E_PREDECESSOR_STATUS",
        "status",
    )
    require(
        manifest.get("decision") == PREDECESSOR_DECISION,
        "E_PREDECESSOR_DECISION",
        "decision",
    )
    require(
        manifest.get("next_unit") == PREDECESSOR_NEXT_UNIT,
        "E_PREDECESSOR_NEXT",
        "next unit",
    )
    predecessor = manifest.get("predecessor")
    require(type(predecessor) is dict, "E_PREDECESSOR_BINDING", "not object")
    require(
        manifest.get("logical_baseline_commit")
        == "c9c50917687c7715b031a6bfe8dd7801bfd737ee",
        "E_PREDECESSOR_BASELINE",
        "logical baseline",
    )
    results = manifest.get("results")
    require(type(results) is dict, "E_PREDECESSOR_RESULTS", "not object")
    require(results.get("prerequisite_plan_count") == 16, "E_PREDECESSOR_RESULTS", "plan")
    require(results.get("evidence_items_present") == 0, "E_PREDECESSOR_RESULTS", "evidence")
    require(results.get("prerequisites_satisfied") == 0, "E_PREDECESSOR_RESULTS", "satisfied")
    require(
        results.get("positive_decision_representable") is False,
        "E_PREDECESSOR_RESULTS",
        "positive decision",
    )


def _validate_predecessor_fixture(fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    require(
        sha256_value(fixture) == PREDECESSOR_FIXTURE_CANONICAL_SHA256,
        "E_PREDECESSOR_FIXTURE_HASH",
        "fixture drift",
    )
    require(
        fixture.get("schema") == PREDECESSOR_FIXTURE_SCHEMA,
        "E_PREDECESSOR_FIXTURE_SCHEMA",
        "schema",
    )
    require(fixture.get("synthetic_only") is True, "E_PREDECESSOR_SYNTHETIC", "flag")
    require(fixture.get("tracks") == list(TRACKS), "E_PREDECESSOR_TRACKS", "tracks")
    plan = fixture.get("prerequisite_evidence_plan")
    require(type(plan) is list and len(plan) == 16, "E_PREDECESSOR_PLAN", "count")
    require(
        sha256_value(plan) == PREDECESSOR_PLAN_SHA256,
        "E_PREDECESSOR_PLAN_HASH",
        "plan drift",
    )
    for row in plan:
        require(type(row) is dict, "E_PREDECESSOR_PLAN_ROW", "not object")
        require(row.get("plan_status") == "PREREGISTERED_NOT_COLLECTED", "E_PREDECESSOR_PLAN_STATUS", "status")
        require(row.get("evidence_present") is False, "E_PREDECESSOR_PLAN_EVIDENCE", "present")
        require(row.get("satisfied") is False, "E_PREDECESSOR_PLAN_SATISFIED", "satisfied")
    owner = fixture.get("owner_decision_preregistration")
    require(type(owner) is dict, "E_PREDECESSOR_OWNER", "not object")
    require(
        owner.get("allowed_current_decisions") == list(ALLOWED_OWNER_DECISIONS),
        "E_PREDECESSOR_OWNER",
        "decision vocabulary",
    )
    require(owner.get("positive_decision_representable") is False, "E_PREDECESSOR_OWNER", "positive")
    require(owner.get("current_decision_recorded") is False, "E_PREDECESSOR_OWNER", "recorded")
    return copy.deepcopy(plan)


def _validate_schema_documents(
    evidence_schema: Mapping[str, Any],
    owner_schema: Mapping[str, Any],
) -> None:
    require(
        sha256_value(evidence_schema) == EVIDENCE_SCHEMA_SHA256,
        "E_EVIDENCE_SCHEMA_HASH",
        "schema artifact drift",
    )
    require(
        sha256_value(owner_schema) == OWNER_SCHEMA_SHA256,
        "E_OWNER_SCHEMA_HASH",
        "schema artifact drift",
    )
    for document, code in ((evidence_schema, "E_EVIDENCE_SCHEMA"), (owner_schema, "E_OWNER_SCHEMA")):
        require(
            document.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
            code,
            "draft",
        )
        require(
            type(document.get("$id")) is str
            and document["$id"].startswith("agent_bridge.biocortex_ab_track_b_"),
            code,
            "id",
        )
    require(type(evidence_schema.get("$defs")) is dict, "E_EVIDENCE_SCHEMA", "defs")
    require(
        type(evidence_schema.get("oneOf")) is list
        and len(evidence_schema["oneOf"]) == 15,
        "E_EVIDENCE_SCHEMA",
        "oneOf",
    )
    expected_refs = [f"#/$defs/packet{index:02d}" for index in range(1, 16)]
    require(
        evidence_schema["oneOf"] == [{"$ref": ref} for ref in expected_refs],
        "E_EVIDENCE_SCHEMA",
        "ordered packet refs",
    )
    common = evidence_schema["$defs"].get("commonPacket")
    require(type(common) is dict, "E_EVIDENCE_SCHEMA", "common packet")
    evidence_properties = common.get("properties")
    owner_properties = owner_schema.get("properties")
    require(type(evidence_properties) is dict, "E_EVIDENCE_SCHEMA", "properties")
    require(type(owner_properties) is dict, "E_OWNER_SCHEMA", "properties")
    require(
        evidence_properties.get("packet_kind", {}).get("const")
        == "SYNTHETIC_VALIDATOR_DOUBLE",
        "E_EVIDENCE_SCHEMA_BOUNDARY",
        "packet kind",
    )
    require(
        owner_properties.get("packet_kind", {}).get("const")
        == "SYNTHETIC_OWNER_DECISION_VALIDATOR_DOUBLE",
        "E_OWNER_SCHEMA_BOUNDARY",
        "packet kind",
    )
    decision_enum = owner_properties.get("decision_state", {}).get("enum")
    require(decision_enum == list(ALLOWED_OWNER_DECISIONS), "E_OWNER_SCHEMA_DECISIONS", "enum")
    require(
        owner_properties.get("positive_decision_representable", {}).get("const") is False,
        "E_OWNER_SCHEMA_POSITIVE",
        "positive representation",
    )
    require(
        owner_properties.get("decision_recorded", {}).get("const") is False,
        "E_OWNER_SCHEMA_RECORDED",
        "decision recorded",
    )
    require(owner_schema.get("type") == "object", "E_OWNER_SCHEMA", "root type")
    require(owner_schema.get("additionalProperties") is False, "E_OWNER_SCHEMA", "closed world")
    evidence_defs = evidence_schema["$defs"]
    discriminators: list[str] = []
    for index in range(1, 16):
        packet_def = evidence_defs.get(f"packet{index:02d}")
        payload_def = evidence_defs.get(f"payload{index:02d}")
        require(type(packet_def) is dict and type(payload_def) is dict, "E_EVIDENCE_SCHEMA", str(index))
        require(packet_def.get("unevaluatedProperties") is False, "E_EVIDENCE_SCHEMA", f"packet {index}")
        branch = packet_def.get("allOf")
        require(type(branch) is list and len(branch) == 2, "E_EVIDENCE_SCHEMA", f"packet {index}")
        properties = branch[1].get("properties")
        require(type(properties) is dict, "E_EVIDENCE_SCHEMA", f"packet {index}")
        prerequisite_id = properties.get("prerequisite_id", {}).get("const")
        require(type(prerequisite_id) is str and prerequisite_id, "E_EVIDENCE_SCHEMA", f"id {index}")
        discriminators.append(prerequisite_id)
        require(
            properties.get("payload", {}).get("$ref") == f"#/$defs/payload{index:02d}",
            "E_EVIDENCE_SCHEMA",
            f"payload {index}",
        )
        require(payload_def.get("additionalProperties") is False, "E_EVIDENCE_SCHEMA", f"payload {index}")
    require(len(discriminators) == len(set(discriminators)) == 15, "E_EVIDENCE_SCHEMA", "discriminators")


def _resolve_schema_ref(root: Mapping[str, Any], ref: str) -> Mapping[str, Any]:
    require(ref.startswith("#/"), "E_SCHEMA_REF", ref)
    value: Any = root
    for raw_component in ref[2:].split("/"):
        component = raw_component.replace("~1", "/").replace("~0", "~")
        require(type(value) is dict and component in value, "E_SCHEMA_REF", ref)
        value = value[component]
    require(type(value) is dict, "E_SCHEMA_REF", ref)
    return value


def _merge_examples(left: Any, right: Any) -> Any:
    if type(left) is dict and type(right) is dict:
        result = copy.deepcopy(left)
        for key, value in right.items():
            if key in result:
                result[key] = _merge_examples(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result
    # Later allOf branches specialize earlier type-only examples with consts.
    return copy.deepcopy(right)


def _example_from_schema(
    node: Mapping[str, Any],
    root: Mapping[str, Any],
    label: str,
) -> Any:
    if "$ref" in node:
        return _example_from_schema(_resolve_schema_ref(root, node["$ref"]), root, label)
    if "const" in node:
        return copy.deepcopy(node["const"])
    if node.get("type") == "object" or "properties" in node:
        properties = node.get("properties", {})
        required = node.get("required", [])
        require(type(properties) is dict and type(required) is list, "E_SCHEMA_EXAMPLE", label)
        result: dict[str, Any] = {}
        names = required if required else list(properties)
        for name in names:
            if name in properties:
                result[name] = _example_from_schema(
                    properties[name],
                    root,
                    f"{label}:{name}",
                )
        return result
    if "allOf" in node:
        result: Any = {}
        for index, branch in enumerate(node["allOf"]):
            require(type(branch) is dict, "E_SCHEMA_EXAMPLE", f"{label}:allOf")
            result = _merge_examples(
                result,
                _example_from_schema(branch, root, f"{label}:allOf:{index}"),
            )
        return result
    if "oneOf" in node:
        branches = node["oneOf"]
        require(type(branches) is list and branches, "E_SCHEMA_EXAMPLE", f"{label}:oneOf")
        return _example_from_schema(branches[0], root, f"{label}:oneOf:0")
    if "enum" in node:
        values = node["enum"]
        require(type(values) is list and values, "E_SCHEMA_EXAMPLE", f"{label}:enum")
        return copy.deepcopy(values[0])
    node_type = node.get("type")
    if node_type == "array":
        if "prefixItems" in node:
            return [
                _example_from_schema(item, root, f"{label}:{index}")
                for index, item in enumerate(node["prefixItems"])
            ]
        count = node.get("minItems", 0)
        item_schema = node.get("items")
        require(type(count) is int and count >= 0, "E_SCHEMA_EXAMPLE", label)
        if count == 0:
            return []
        require(type(item_schema) is dict, "E_SCHEMA_EXAMPLE", label)
        return [
            _example_from_schema(item_schema, root, f"{label}:{index}")
            for index in range(count)
        ]
    if node_type == "string":
        pattern = node.get("pattern", "")
        if pattern == "^[0-9a-f]{64}$":
            return _synthetic_digest("SCHEMA_EXAMPLE", label)
        if pattern.startswith("^[0-9]{4}-"):
            return "2026-07-17T12:00:00Z"
        return f"SYNTHETIC_{_synthetic_digest(label)[:16].upper()}"
    if node_type == "integer":
        return int(node.get("minimum", 0))
    if node_type == "boolean":
        return False
    raise EvidencePacketReviewError(f"E_SCHEMA_EXAMPLE: unsupported node at {label}")


def _schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return type(value) is dict
    if expected == "array":
        return type(value) is list
    if expected == "string":
        return type(value) is str
    if expected == "integer":
        return type(value) is int
    if expected == "boolean":
        return type(value) is bool
    if expected == "null":
        return value is None
    return False


def _validate_schema_instance(
    value: Any,
    node: Mapping[str, Any],
    root: Mapping[str, Any],
    path: str,
) -> None:
    if "$ref" in node:
        _validate_schema_instance(value, _resolve_schema_ref(root, node["$ref"]), root, path)
        return
    if "const" in node:
        require(value == node["const"] and type(value) is type(node["const"]), "E_SCHEMA_CONST", path)
    if "enum" in node:
        require(value in node["enum"], "E_SCHEMA_ENUM", path)
    if "type" in node:
        require(_schema_type_matches(value, node["type"]), "E_SCHEMA_TYPE", path)
    if "allOf" in node:
        for index, branch in enumerate(node["allOf"]):
            _validate_schema_instance(value, branch, root, f"{path}:allOf:{index}")
    if "oneOf" in node:
        matches = 0
        for index, branch in enumerate(node["oneOf"]):
            try:
                _validate_schema_instance(value, branch, root, f"{path}:oneOf:{index}")
            except EvidencePacketReviewError:
                continue
            matches += 1
        require(matches == 1, "E_SCHEMA_ONE_OF", f"{path}:{matches}")
    if "if" in node:
        try:
            _validate_schema_instance(value, node["if"], root, f"{path}:if")
        except EvidencePacketReviewError:
            pass
        else:
            if "then" in node:
                _validate_schema_instance(value, node["then"], root, f"{path}:then")
    if type(value) is dict:
        properties = node.get("properties", {})
        required = node.get("required", [])
        require(type(properties) is dict and type(required) is list, "E_SCHEMA_OBJECT", path)
        require(all(name in value for name in required), "E_SCHEMA_REQUIRED", path)
        if node.get("additionalProperties") is False:
            require(set(value) <= set(properties), "E_SCHEMA_ADDITIONAL", path)
        for name, item in value.items():
            if name in properties:
                _validate_schema_instance(item, properties[name], root, f"{path}:{name}")
    if type(value) is list:
        if "minItems" in node:
            require(len(value) >= node["minItems"], "E_SCHEMA_MIN_ITEMS", path)
        if "maxItems" in node:
            require(len(value) <= node["maxItems"], "E_SCHEMA_MAX_ITEMS", path)
        if node.get("uniqueItems") is True:
            encodings = [canonical_bytes(item) for item in value]
            require(len(encodings) == len(set(encodings)), "E_SCHEMA_UNIQUE_ITEMS", path)
        prefix = node.get("prefixItems", [])
        require(type(prefix) is list, "E_SCHEMA_PREFIX_ITEMS", path)
        for index, item_schema in enumerate(prefix):
            require(index < len(value), "E_SCHEMA_PREFIX_ITEMS", path)
            _validate_schema_instance(value[index], item_schema, root, f"{path}:{index}")
        items = node.get("items")
        if items is False:
            require(len(value) <= len(prefix), "E_SCHEMA_ITEMS", path)
        elif type(items) is dict:
            for index in range(len(prefix), len(value)):
                _validate_schema_instance(value[index], items, root, f"{path}:{index}")
    if type(value) is str:
        if "minLength" in node:
            require(len(value) >= node["minLength"], "E_SCHEMA_MIN_LENGTH", path)
        if "maxLength" in node:
            require(len(value) <= node["maxLength"], "E_SCHEMA_MAX_LENGTH", path)
        if "pattern" in node:
            require(re.fullmatch(node["pattern"], value) is not None, "E_SCHEMA_PATTERN", path)
    if type(value) is int and type(value) is not bool:
        if "minimum" in node:
            require(value >= node["minimum"], "E_SCHEMA_MINIMUM", path)
        if "maximum" in node:
            require(value <= node["maximum"], "E_SCHEMA_MAXIMUM", path)


def _parse_utc_second(value: str) -> dt.datetime:
    require(type(value) is str and value.endswith("Z"), "E_FRESHNESS_FORMAT", "UTC")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise EvidencePacketReviewError("E_FRESHNESS_FORMAT: invalid UTC second") from error
    return parsed.replace(tzinfo=dt.timezone.utc)


def _render_utc_second(value: dt.datetime) -> str:
    require(value.tzinfo == dt.timezone.utc, "E_FRESHNESS_FORMAT", "timezone")
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _derive_packet_profiles(
    specs: Any,
    plan: Sequence[Mapping[str, Any]],
    evidence_schema: Mapping[str, Any],
) -> list[dict[str, Any]]:
    require(type(specs) is list and len(specs) == 16, "E_PROFILE_COUNT", "spec count")
    require(sha256_value(specs) == PROFILE_CATALOG_SHA256, "E_PROFILE_HASH", "spec drift")
    defs = evidence_schema["$defs"]
    expected_keys = {
        "max_age_seconds",
        "offline_validator_id",
        "packet_def",
        "payload_def",
        "prerequisite_id",
    }
    profiles: list[dict[str, Any]] = []
    for index, (spec, row) in enumerate(zip(specs, plan, strict=True), start=1):
        require(type(spec) is dict, "E_PROFILE_SPEC", str(index))
        exact_keys(spec, expected_keys, "E_PROFILE_SPEC_KEYS")
        require(spec["prerequisite_id"] == row["prerequisite_id"], "E_PROFILE_SPEC_ID", str(index))
        require(spec["packet_def"] == f"packet{index:02d}", "E_PROFILE_SPEC_PACKET", str(index))
        require(spec["payload_def"] == f"payload{index:02d}", "E_PROFILE_SPEC_PAYLOAD", str(index))
        require(
            type(spec["offline_validator_id"]) is str
            and spec["offline_validator_id"].startswith("OFFLINE_")
            and spec["offline_validator_id"].endswith("_V1"),
            "E_PROFILE_SPEC_VALIDATOR",
            str(index),
        )
        max_age = spec["max_age_seconds"]
        require(max_age is None or (type(max_age) is int and max_age > 0), "E_PROFILE_SPEC_MAX_AGE", str(index))
        if index <= 15:
            packet_node = defs[spec["packet_def"]]
            branch_properties = packet_node["allOf"][1]["properties"]
            require(branch_properties["prerequisite_id"]["const"] == row["prerequisite_id"], "E_PROFILE_SCHEMA_ID", str(index))
            require(branch_properties["evidence_class"]["const"] == row["evidence_class"], "E_PROFILE_SCHEMA_CLASS", str(index))
            require(branch_properties["owner_class"]["const"] == row["owner_class"], "E_PROFILE_SCHEMA_OWNER", str(index))
            payload = defs[spec["payload_def"]]
            fields_catalog = list(payload["required"])
            track_partition = branch_properties["track_partition"]["const"]
            packet_schema_id = f"{evidence_schema['$id']}#/$defs/{spec['packet_def']}"
        else:
            require(spec["packet_def"] == "packet16", "E_OWNER_PROFILE_DEF", "packet")
            require(spec["payload_def"] == "payload16", "E_OWNER_PROFILE_DEF", "payload")
            fields_catalog = [
                "evidence_set_binding",
                "decision_state",
                "decision_reason",
                "owner_identity_bound",
                "decision_recorded",
            ]
            track_partition = "GLOBAL"
            packet_schema_id = OWNER_PACKET_INSTANCE_SCHEMA
        profiles.append(
            {
                "depends_on": copy.deepcopy(row["depends_on"]),
                "evidence_class": row["evidence_class"],
                "evidence_required": row["evidence_required"],
                "freshness_rule": row["freshness_rule"],
                "max_age_seconds": max_age,
                "offline_validator_id": spec["offline_validator_id"],
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
    require(profiles[-1]["depends_on"] == [row["prerequisite_id"] for row in plan[:-1]], "E_OWNER_PROFILE", "dependencies")
    return profiles


def _validate_dependency_topology(profiles: Sequence[Mapping[str, Any]]) -> None:
    """Bind the frozen predecessor DAG to the ordered packet suite."""

    require(len(profiles) == 16, "E_DEPENDENCY_TOPOLOGY", "profile count")
    ordered_ids = [profile["prerequisite_id"] for profile in profiles]
    require(len(ordered_ids) == len(set(ordered_ids)), "E_DEPENDENCY_TOPOLOGY", "duplicate id")
    for index, profile in enumerate(profiles):
        dependencies = profile["depends_on"]
        require(type(dependencies) is list, "E_DEPENDENCY_TOPOLOGY", f"{index}:type")
        require(
            len(dependencies) == len(set(dependencies)),
            "E_DEPENDENCY_TOPOLOGY",
            f"{index}:duplicate dependency",
        )
        require(
            all(dependency in ordered_ids[:index] for dependency in dependencies),
            "E_DEPENDENCY_TOPOLOGY",
            f"{index}:not a prior prerequisite",
        )
    require(profiles[0]["depends_on"] == [], "E_DEPENDENCY_TOPOLOGY", "root")
    require(
        profiles[-2]["depends_on"] == ordered_ids[:14],
        "E_DEPENDENCY_TOPOLOGY",
        "independent review aggregate",
    )
    require(
        profiles[-1]["depends_on"] == ordered_ids[:15],
        "E_DEPENDENCY_TOPOLOGY",
        "owner aggregate",
    )


def _assert_schema_boundary(boundary: Any, code: str) -> None:
    require(type(boundary) is dict and boundary, code, "not object")
    for name, value in boundary.items():
        if name == "side_effects_unlocked":
            require(value == "NONE", code, name)
        elif name == "paid_resources_provisioned" or name.endswith("_created"):
            require(type(value) is int and value == 0, code, name)
        else:
            require(type(value) is bool and value is False, code, name)


def _assert_track_separation(packet: Mapping[str, Any], code: str) -> None:
    partition = packet["track_partition"]
    payload = packet["payload"]
    if "track_evidence" not in payload:
        require(partition == "GLOBAL", code, "global payload")
        return
    track_evidence = payload["track_evidence"]
    if partition == "MANAGED_ONLY":
        require(track_evidence["track_id"] == TRACKS[0], code, "managed")
    elif partition == "SELF_HOSTED_ONLY":
        require(track_evidence["track_id"] == TRACKS[1], code, "self hosted")
    elif partition == "DUAL_TRACK_SEPARATE":
        require(type(track_evidence) is dict and set(track_evidence) == set(TRACKS), code, "dual keys")
        managed = track_evidence[TRACKS[0]]
        self_hosted = track_evidence[TRACKS[1]]
        require(managed["track_id"] == TRACKS[0], code, "managed id")
        require(self_hosted["track_id"] == TRACKS[1], code, "self hosted id")
        managed_hashes = {value for value in managed["binding"].values() if is_sha256(value)}
        self_hashes = {value for value in self_hosted["binding"].values() if is_sha256(value)}
        require(managed_hashes.isdisjoint(self_hashes), code, "cross-track binding reuse")
        require(
            managed["synthetic_evidence_artifact_sha256"]
            != self_hosted["synthetic_evidence_artifact_sha256"],
            code,
            "cross-track evidence reuse",
        )
    else:
        raise EvidencePacketReviewError(f"{code}: invalid partition")


def _assert_exact_track_binding(
    packet: Mapping[str, Any],
    expected_packet: Mapping[str, Any],
) -> None:
    require(
        packet["track_partition"] == expected_packet["track_partition"],
        "E_PACKET_TRACK_BINDING",
        "partition drift",
    )
    actual_track = packet["payload"].get("track_evidence")
    expected_track = expected_packet["payload"].get("track_evidence")
    require(
        actual_track == expected_track,
        "E_PACKET_TRACK_BINDING",
        "frozen per-track KAT binding drift",
    )


def _derive_packet_set_sha256(packet_ids: Sequence[str]) -> str:
    require(
        type(packet_ids) in (list, tuple)
        and len(packet_ids) == 15
        and len(packet_ids) == len(set(packet_ids))
        and all(is_sha256(packet_id) for packet_id in packet_ids),
        "E_PACKET_SET_DERIVATION",
        "ordered packet ids",
    )
    return sha256_value(
        {
            "canonicalization": PACKET_SET_CANONICALIZATION,
            "domain": PACKET_SET_HASH_DOMAIN,
            "ordered_packet_id_sha256": list(packet_ids),
        }
    )


def _derive_review_evidence_set_sha256(packet_ids: Sequence[str]) -> str:
    require(
        type(packet_ids) in (list, tuple)
        and len(packet_ids) == 14
        and len(packet_ids) == len(set(packet_ids))
        and all(is_sha256(packet_id) for packet_id in packet_ids),
        "E_PACKET_SET_DERIVATION",
        "ordered prerequisite packet ids",
    )
    return sha256_value(
        {
            "canonicalization": PACKET_SET_CANONICALIZATION,
            "domain": PACKET_SET_HASH_DOMAIN,
            "ordered_packet_id_sha256": list(packet_ids),
        }
    )


def _derive_packet_id(packet: Mapping[str, Any]) -> str:
    return sha256_value(without_key(packet, "packet_id_sha256"))


def _make_evidence_packet(
    profile: Mapping[str, Any],
    evidence_schema: Mapping[str, Any],
    context: Mapping[str, Any],
    index: int,
    prerequisite_packet_ids: Sequence[str] = (),
) -> dict[str, Any]:
    node = evidence_schema["$defs"][profile["packet_def"]]
    packet = _example_from_schema(node, evidence_schema, f"packet:{index}")
    observed = _parse_utc_second(context["observed_at_utc"])
    checked = _parse_utc_second(context["checked_at_utc"])
    max_age = profile["max_age_seconds"]
    expires = observed + dt.timedelta(
        seconds=max_age if max_age is not None else NO_MAX_AGE_KAT_HORIZON_SECONDS
    )
    packet["freshness"]["observed_at_utc"] = _render_utc_second(observed)
    packet["freshness"]["checked_at_utc"] = _render_utc_second(checked)
    packet["freshness"]["expires_at_utc"] = _render_utc_second(expires)
    packet["synthetic_provenance"]["fixture_sha256"] = context["fixture_identity_sha256"]
    packet["synthetic_provenance"]["generator_build_sha256"] = context["generator_build_sha256"]
    packet["synthetic_provenance"]["validator_build_sha256"] = context["validator_build_sha256"]
    packet["synthetic_provenance"]["fixed_checked_at_utc"] = context["checked_at_utc"]
    if index == 15:
        require(
            len(prerequisite_packet_ids) == 14,
            "E_PACKET_SET_DERIVATION",
            "packet 15 prerequisite count",
        )
        payload = packet["payload"]
        payload["packet_id_hash_algorithm"] = "SHA-256"
        payload["packet_set_hash_domain"] = PACKET_SET_HASH_DOMAIN
        payload["packet_set_canonicalization"] = PACKET_SET_CANONICALIZATION
        payload["ordered_prerequisite_packet_id_sha256"] = list(
            prerequisite_packet_ids
        )
        payload["evidence_set_sha256"] = _derive_review_evidence_set_sha256(
            prerequisite_packet_ids
        )
    else:
        require(
            len(prerequisite_packet_ids) == 0,
            "E_PACKET_SET_DERIVATION",
            f"packet {index} unexpected prerequisites",
        )
    packet["packet_id_sha256"] = _derive_packet_id(packet)
    return packet


def _make_evidence_packet_suite(
    profiles: Sequence[Mapping[str, Any]],
    evidence_schema: Mapping[str, Any],
    context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    require(len(profiles) == 16, "E_PACKET_SET_DERIVATION", "profile count")
    packets = [
        _make_evidence_packet(profile, evidence_schema, context, index)
        for index, profile in enumerate(profiles[:14], start=1)
    ]
    prerequisite_packet_ids = [packet["packet_id_sha256"] for packet in packets]
    packets.append(
        _make_evidence_packet(
            profiles[14],
            evidence_schema,
            context,
            15,
            prerequisite_packet_ids,
        )
    )
    require(
        len({packet["packet_id_sha256"] for packet in packets}) == 15,
        "E_PACKET_SET_DERIVATION",
        "packet id collision",
    )
    return packets


def _validate_generated_evidence_packet(
    packet: Mapping[str, Any],
    profile: Mapping[str, Any],
    evidence_schema: Mapping[str, Any],
    context: Mapping[str, Any],
    expected_packet: Mapping[str, Any],
    prerequisite_packet_ids: Sequence[str],
) -> dict[str, Any]:
    require(type(packet) is dict, "E_PACKET", "not object")
    common_required = evidence_schema["$defs"]["commonPacket"]["required"]
    require(set(packet) == set(common_required), "E_PACKET_KEYS", profile["prerequisite_id"])
    _validate_schema_instance(
        packet,
        evidence_schema["$defs"][profile["packet_def"]],
        evidence_schema,
        profile["prerequisite_id"],
    )
    _validate_schema_instance(
        packet,
        evidence_schema,
        evidence_schema,
        f"{profile['prerequisite_id']}:root",
    )
    freshness = packet["freshness"]
    observed = _parse_utc_second(freshness["observed_at_utc"])
    checked = _parse_utc_second(freshness["checked_at_utc"])
    expires = _parse_utc_second(freshness["expires_at_utc"])
    expected_observed = _parse_utc_second(context["observed_at_utc"])
    expected_checked = _parse_utc_second(context["checked_at_utc"])
    require(
        observed == expected_observed
        and checked == expected_checked
        and freshness["observed_at_utc"] == context["observed_at_utc"]
        and freshness["checked_at_utc"] == context["checked_at_utc"],
        "E_PACKET_CONTEXT_BINDING",
        profile["prerequisite_id"],
    )
    require(observed <= checked < expires, "E_PACKET_FRESHNESS", profile["prerequisite_id"])
    max_age = profile["max_age_seconds"]
    expected_horizon = (
        max_age if max_age is not None else NO_MAX_AGE_KAT_HORIZON_SECONDS
    )
    require(
        (expires - observed).total_seconds() == expected_horizon
        and freshness["expires_at_utc"]
        == _render_utc_second(expected_observed + dt.timedelta(seconds=expected_horizon)),
        "E_PACKET_FRESHNESS",
        "derived expiry",
    )
    require(freshness["real_currentness_proved"] is False, "E_PACKET_CURRENTNESS", "real currentness")
    require(freshness["decision_recheck_required"] is True, "E_PACKET_CURRENTNESS", "recheck")
    _assert_schema_boundary(packet["boundary"], "E_PACKET_BOUNDARY")
    _assert_track_separation(packet, "E_PACKET_TRACK_SEPARATION")
    provenance = packet["synthetic_provenance"]
    fixed_checked = _parse_utc_second(provenance["fixed_checked_at_utc"])
    require(provenance["origin"] == "SYNTHETIC_VALIDATOR_DOUBLE", "E_PACKET_PROVENANCE", "origin")
    require(provenance["real_collection_performed"] is False, "E_PACKET_PROVENANCE", "collection")
    require(provenance["provider_sdk_present"] is False, "E_PACKET_PROVENANCE", "provider SDK")
    require(provenance["secret_material_present"] is False, "E_PACKET_PROVENANCE", "secret")
    require(
        provenance["fixture_sha256"] == context["fixture_identity_sha256"]
        and provenance["generator_build_sha256"] == context["generator_build_sha256"]
        and provenance["validator_build_sha256"] == context["validator_build_sha256"]
        and provenance["fixed_checked_at_utc"] == context["checked_at_utc"]
        and fixed_checked == expected_checked,
        "E_PACKET_PROVENANCE_BINDING",
        profile["prerequisite_id"],
    )
    require(
        packet["predecessor_bindings"] == expected_packet["predecessor_bindings"],
        "E_PACKET_PREDECESSOR_BINDING",
        profile["prerequisite_id"],
    )
    _assert_exact_track_binding(packet, expected_packet)
    if profile["prerequisite_id"] == (
        "INDEPENDENT_SECURITY_FAILURE_MODE_AND_ROLLBACK_REVIEW_APPROVED"
    ):
        payload = packet["payload"]
        require(
            payload["ordered_prerequisite_packet_id_sha256"]
            == list(prerequisite_packet_ids),
            "E_PACKET_DEPENDENCY_ORDER",
            "packet 15 ordered prerequisite ids",
        )
        require(
            payload["evidence_set_sha256"]
            == _derive_review_evidence_set_sha256(prerequisite_packet_ids),
            "E_PACKET_EVIDENCE_SET",
            "packet 15 derived evidence set",
        )
    require(
        packet["packet_id_sha256"] == _derive_packet_id(packet),
        "E_PACKET_ID_HASH",
        profile["prerequisite_id"],
    )
    require(
        packet["payload"] == expected_packet["payload"],
        "E_PACKET_KAT_BINDING",
        profile["prerequisite_id"],
    )
    require(
        packet == expected_packet,
        "E_PACKET_KAT_BINDING",
        f"{profile['prerequisite_id']}: exact frozen packet",
    )
    return {
        "offline_double_conformant": True,
        "packet_id_sha256": packet["packet_id_sha256"],
        "packet_schema_id": profile["packet_schema_id"],
        "prerequisite_disposition": "PENDING_NOT_COLLECTED",
        "prerequisite_id": profile["prerequisite_id"],
        "primary_reason": "SYNTHETIC_INPUT_NOT_RUNTIME_EVIDENCE",
        "real_evidence_items": 0,
        "runtime_evidence_disposition": "NOT_EVALUATED_OUT_OF_SCOPE",
        "schema_conformant": True,
        "schema_disposition": "CONFORMANT_SYNTHETIC_VALIDATOR_DOUBLE",
    }


def _make_owner_packet(
    owner_schema: Mapping[str, Any],
    context: Mapping[str, Any],
    evidence_packet_ids: Sequence[str],
    decision_state: str = "PENDING_PREREQUISITE_EVIDENCE",
    decision_reason: str = "WAITING_FOR_ALL_EVIDENCE",
) -> dict[str, Any]:
    packet = _example_from_schema(owner_schema, owner_schema, "owner-packet")
    packet["decision_state"] = decision_state
    packet["decision_reason"] = decision_reason
    packet["synthetic_provenance"]["fixture_sha256"] = context["fixture_identity_sha256"]
    packet["synthetic_provenance"]["generator_build_sha256"] = context["generator_build_sha256"]
    packet["synthetic_provenance"]["validator_build_sha256"] = context["validator_build_sha256"]
    packet["synthetic_provenance"]["fixed_checked_at_utc"] = context["checked_at_utc"]
    packet["evidence_set_binding"]["evidence_set_sha256"] = "NONE"
    packet["evidence_set_binding"]["synthetic_schema_conformant_packet_count"] = 15
    packet["evidence_set_binding"]["runtime_validated_evidence_count"] = 0
    if decision_state == "PENDING_PREREQUISITE_EVIDENCE":
        packet["evidence_set_binding"]["final_validation_state"] = "NOT_PERFORMED"
        packet["evidence_set_binding"]["final_validation_at_utc"] = "NONE"
    elif decision_state == "REJECTED_FAIL_CLOSED":
        packet["evidence_set_binding"]["final_validation_state"] = (
            "REJECTED_FAIL_CLOSED"
        )
        packet["evidence_set_binding"]["final_validation_at_utc"] = context[
            "checked_at_utc"
        ]
    else:
        raise EvidencePacketReviewError("E_OWNER_PACKET_STATE_MATRIX: invalid state")
    packet["evidence_set_binding"]["same_evidence_hash_owner_window_proved"] = False
    require(
        len(evidence_packet_ids) == 15 and all(is_sha256(item) for item in evidence_packet_ids),
        "E_PACKET_SET_DERIVATION",
        "owner packet ids",
    )
    packet["packet_id_sha256"] = _derive_packet_id(packet)
    return packet


def _validate_generated_owner_packet(
    packet: Mapping[str, Any],
    profile: Mapping[str, Any],
    owner_schema: Mapping[str, Any],
    context: Mapping[str, Any],
    evidence_packet_ids: Sequence[str],
) -> dict[str, Any]:
    require(type(packet) is dict, "E_OWNER_PACKET", "not object")
    require(set(packet) == set(owner_schema["required"]), "E_OWNER_PACKET_KEYS", "closed world")
    state = packet["decision_state"]
    reason = packet["decision_reason"]
    reason_matrix = {
        "PENDING_PREREQUISITE_EVIDENCE": {
            "WAITING_FOR_ALL_EVIDENCE",
            "OWNER_DECISION_PENDING",
        },
        "REJECTED_FAIL_CLOSED": {
            "EVIDENCE_VALIDATION_FAILED",
            "EVIDENCE_FRESHNESS_FAILED",
            "EVIDENCE_BINDING_FAILED",
            "POSITIVE_DECISION_NOT_REPRESENTABLE",
        },
    }
    require(
        state in reason_matrix and reason in reason_matrix[state],
        "E_OWNER_PACKET_STATE_MATRIX",
        "state/reason",
    )
    binding = packet["evidence_set_binding"]
    require(type(binding) is dict, "E_OWNER_PACKET_STATE_MATRIX", "binding")
    exact_keys(
        binding,
        owner_schema["$defs"]["evidenceSetBinding"]["required"],
        "E_OWNER_PACKET_STATE_MATRIX",
    )
    if state == "PENDING_PREREQUISITE_EVIDENCE":
        require(
            binding["evidence_set_sha256"] == "NONE"
            and binding["synthetic_schema_conformant_packet_count"] == 15
            and binding["runtime_validated_evidence_count"] == 0
            and binding["final_validation_state"] == "NOT_PERFORMED"
            and binding["final_validation_at_utc"] == "NONE"
            and binding["same_evidence_hash_owner_window_proved"] is False,
            "E_OWNER_PACKET_STATE_MATRIX",
            "pending evidence/final-validation binding",
        )
    else:
        rejected_at = _parse_utc_second(binding["final_validation_at_utc"])
        require(
            binding["evidence_set_sha256"] == "NONE"
            and binding["synthetic_schema_conformant_packet_count"] == 15
            and binding["runtime_validated_evidence_count"] == 0
            and binding["final_validation_state"] == "REJECTED_FAIL_CLOSED"
            and binding["final_validation_at_utc"] == context["checked_at_utc"]
            and rejected_at == _parse_utc_second(context["checked_at_utc"])
            and binding["same_evidence_hash_owner_window_proved"] is False,
            "E_OWNER_PACKET_STATE_MATRIX",
            "rejected evidence/final-validation binding",
        )
    require(packet["positive_decision_representable"] is False, "E_OWNER_PACKET_POSITIVE", "positive")
    require(packet["delegated_agent_authority"] is False, "E_OWNER_PACKET_POSITIVE", "delegated")
    require(packet["owner_identity_bound"] is False, "E_OWNER_PACKET_IDENTITY", "identity")
    require(packet["decision_recorded"] is False, "E_OWNER_PACKET_RECORDED", "recorded")
    _assert_schema_boundary(packet["boundary"], "E_OWNER_PACKET_BOUNDARY")
    provenance = packet["synthetic_provenance"]
    require(
        type(provenance) is dict,
        "E_OWNER_PACKET_PROVENANCE_BINDING",
        "not object",
    )
    exact_keys(
        provenance,
        owner_schema["$defs"]["syntheticProvenance"]["required"],
        "E_OWNER_PACKET_PROVENANCE_BINDING",
    )
    fixed_checked = _parse_utc_second(provenance["fixed_checked_at_utc"])
    require(
        provenance["fixture_sha256"] == context["fixture_identity_sha256"]
        and provenance["generator_build_sha256"] == context["generator_build_sha256"]
        and provenance["validator_build_sha256"] == context["validator_build_sha256"]
        and provenance["fixed_checked_at_utc"] == context["checked_at_utc"]
        and fixed_checked == _parse_utc_second(context["checked_at_utc"]),
        "E_OWNER_PACKET_PROVENANCE_BINDING",
        "frozen context",
    )
    require(
        packet["packet_id_sha256"] == _derive_packet_id(packet),
        "E_OWNER_PACKET_ID_HASH",
        "content-derived id",
    )
    _validate_schema_instance(packet, owner_schema, owner_schema, "owner")
    expected_packet = _make_owner_packet(
        owner_schema,
        context,
        evidence_packet_ids,
        state,
        reason,
    )
    require(
        packet == expected_packet,
        "E_OWNER_PACKET_KAT_BINDING",
        "exact frozen owner packet",
    )
    return {
        "offline_double_conformant": True,
        "packet_id_sha256": packet["packet_id_sha256"],
        "packet_schema_id": profile["packet_schema_id"],
        "prerequisite_disposition": (
            "PENDING_NOT_COLLECTED"
            if state == "PENDING_PREREQUISITE_EVIDENCE"
            else "REJECTED_FAIL_CLOSED"
        ),
        "prerequisite_id": profile["prerequisite_id"],
        "primary_reason": reason,
        "real_evidence_items": 0,
        "runtime_evidence_disposition": "NOT_EVALUATED_OUT_OF_SCOPE",
        "schema_conformant": True,
        "schema_disposition": "CONFORMANT_SYNTHETIC_VALIDATOR_DOUBLE",
    }


def _validate_fixture_root(
    fixture: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], BoundaryNonClaims, dict[str, Any]]:
    require(
        sha256_value(fixture) == FIXTURE_SHA256,
        "E_FIXTURE_HASH",
        "successor synthetic KAT fixture drift",
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
    require(fixture["schema"] == FIXTURE_SCHEMA, "E_FIXTURE_SCHEMA", "schema")
    require(fixture["date"] == "2026-07-17", "E_FIXTURE_DATE", "date")
    require(fixture["synthetic_only"] is True, "E_FIXTURE_SYNTHETIC", "flag")
    require(fixture["tracks"] == list(TRACKS), "E_FIXTURE_TRACKS", "tracks")
    predecessor = fixture["predecessor"]
    require(type(predecessor) is dict, "E_FIXTURE_PREDECESSOR", "not object")
    exact_keys(
        predecessor,
        {
            "fixture_sha256",
            "integration_commit",
            "manifest_sha256",
            "plan_sha256",
            "source_commit",
        },
        "E_FIXTURE_PREDECESSOR_KEYS",
    )
    require(predecessor["source_commit"] == PREDECESSOR_SOURCE_COMMIT, "E_FIXTURE_PREDECESSOR", "source")
    require(predecessor["integration_commit"] == PREDECESSOR_INTEGRATION_COMMIT, "E_FIXTURE_PREDECESSOR", "integration")
    require(predecessor["manifest_sha256"] == PREDECESSOR_MANIFEST_FILE_SHA256, "E_FIXTURE_PREDECESSOR", "manifest")
    require(predecessor["fixture_sha256"] == PREDECESSOR_FIXTURE_FILE_SHA256, "E_FIXTURE_PREDECESSOR", "fixture")
    require(predecessor["plan_sha256"] == PREDECESSOR_PLAN_SHA256, "E_FIXTURE_PREDECESSOR", "plan")
    downstream = fixture["downstream_separate_gates"]
    require(type(downstream) is list and len(downstream) == 4, "E_DOWNSTREAM_GATES", "count")
    for row, gate_id in zip(downstream, DOWNSTREAM_GATE_IDS, strict=True):
        require(
            row == {
                "authorized": False,
                "gate_id": gate_id,
                "status": "SEPARATE_NOT_AUTHORIZED",
            },
            "E_DOWNSTREAM_GATE",
            gate_id,
        )
    nonclaims_raw = fixture["nonclaims"]
    require(type(nonclaims_raw) is dict, "E_NONCLAIMS", "not object")
    require(sha256_value(nonclaims_raw) == NONCLAIMS_SHA256, "E_NONCLAIMS_HASH", "drift")
    nonclaims = BoundaryNonClaims.from_mapping(nonclaims_raw)
    require(nonclaims.all_explicit(), "E_NONCLAIMS", "escalation")
    expected = fixture["expected"]
    require(type(expected) is dict, "E_EXPECTED", "not object")
    require(sha256_value(expected) == EXPECTED_SHA256, "E_EXPECTED_HASH", "drift")
    specs = fixture["packet_profile_specs"]
    require(type(specs) is list and len(specs) == 16, "E_PROFILE_COUNT", "not list")
    context = fixture["synthetic_context"]
    require(type(context) is dict, "E_SYNTHETIC_CONTEXT", "not object")
    exact_keys(
        context,
        {
            "checked_at_utc",
            "fixture_identity_sha256",
            "generator_build_sha256",
            "observed_at_utc",
            "validator_build_sha256",
        },
        "E_SYNTHETIC_CONTEXT_KEYS",
    )
    observed = _parse_utc_second(context["observed_at_utc"])
    checked = _parse_utc_second(context["checked_at_utc"])
    require(observed <= checked, "E_SYNTHETIC_CONTEXT_TIME", "order")
    for name in (
        "fixture_identity_sha256",
        "generator_build_sha256",
        "validator_build_sha256",
    ):
        require(is_sha256(context[name]), "E_SYNTHETIC_CONTEXT_HASH", name)
    return copy.deepcopy(specs), copy.deepcopy(context), nonclaims, copy.deepcopy(expected)


class RuntimePrerequisiteEvidencePacketSchemaReviewer:
    """Review the frozen schemas and all offline validator-double known answers."""

    def _prepare(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_fixture: Mapping[str, Any],
        evidence_schema: Mapping[str, Any],
        owner_schema: Mapping[str, Any],
        fixture: Mapping[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], BoundaryNonClaims, dict[str, Any]]:
        _validate_predecessor_manifest(predecessor_manifest)
        plan = _validate_predecessor_fixture(predecessor_fixture)
        _validate_schema_documents(evidence_schema, owner_schema)
        profile_specs, context, nonclaims, expected = _validate_fixture_root(fixture)
        profiles = _derive_packet_profiles(profile_specs, plan, evidence_schema)
        _validate_dependency_topology(profiles)
        return profiles, context, nonclaims, expected

    def known_answer_packet_suite(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_fixture: Mapping[str, Any],
        evidence_schema: Mapping[str, Any],
        owner_schema: Mapping[str, Any],
        fixture: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return deterministic synthetic KAT inputs; none is real evidence."""

        profiles, context, _nonclaims, _expected = self._prepare(
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            fixture,
        )
        evidence_packets = _make_evidence_packet_suite(
            profiles,
            evidence_schema,
            context,
        )
        evidence_packet_ids = [
            packet["packet_id_sha256"] for packet in evidence_packets
        ]
        return {
            "evidence_packets": evidence_packets,
            "owner_packet": _make_owner_packet(
                owner_schema,
                context,
                evidence_packet_ids,
            ),
        }

    def validate_evidence_packet_double(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_fixture: Mapping[str, Any],
        evidence_schema: Mapping[str, Any],
        owner_schema: Mapping[str, Any],
        fixture: Mapping[str, Any],
        packet_index: int,
        packet: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate one synthetic evidence packet without accepting evidence."""

        require(type(packet_index) is int and 0 <= packet_index < 15, "E_PACKET_INDEX", "range")
        profiles, context, _nonclaims, _expected = self._prepare(
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            fixture,
        )
        expected_packets = _make_evidence_packet_suite(
            profiles,
            evidence_schema,
            context,
        )
        prerequisite_packet_ids = [
            item["packet_id_sha256"] for item in expected_packets[:14]
        ]
        return _validate_generated_evidence_packet(
            packet,
            profiles[packet_index],
            evidence_schema,
            context,
            expected_packets[packet_index],
            prerequisite_packet_ids,
        )

    def validate_owner_packet_double(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_fixture: Mapping[str, Any],
        evidence_schema: Mapping[str, Any],
        owner_schema: Mapping[str, Any],
        fixture: Mapping[str, Any],
        packet: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate the pending/rejected-only synthetic owner envelope."""

        profiles, context, _nonclaims, _expected = self._prepare(
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            fixture,
        )
        evidence_packets = _make_evidence_packet_suite(
            profiles,
            evidence_schema,
            context,
        )
        evidence_packet_ids = [
            item["packet_id_sha256"] for item in evidence_packets
        ]
        return _validate_generated_owner_packet(
            packet,
            profiles[-1],
            owner_schema,
            context,
            evidence_packet_ids,
        )

    def review(
        self,
        predecessor_manifest: Mapping[str, Any],
        predecessor_fixture: Mapping[str, Any],
        evidence_schema: Mapping[str, Any],
        owner_schema: Mapping[str, Any],
        fixture: Mapping[str, Any],
    ) -> dict[str, Any]:
        profiles, context, nonclaims, expected = self._prepare(
            predecessor_manifest,
            predecessor_fixture,
            evidence_schema,
            owner_schema,
            fixture,
        )
        plan = predecessor_fixture["prerequisite_evidence_plan"]
        packets = _make_evidence_packet_suite(profiles, evidence_schema, context)
        packet_ids = [packet["packet_id_sha256"] for packet in packets]
        prerequisite_packet_ids = packet_ids[:14]
        case_results = [
            _validate_generated_evidence_packet(
                packet,
                profile,
                evidence_schema,
                context,
                packet,
                prerequisite_packet_ids,
            )
            for packet, profile in zip(packets, profiles[:-1], strict=True)
        ]
        owner_packet = _make_owner_packet(owner_schema, context, packet_ids)
        case_results.append(
            _validate_generated_owner_packet(
                owner_packet,
                profiles[-1],
                owner_schema,
                context,
                packet_ids,
            )
        )

        require(len(case_results) == expected["offline_validator_double_count"] == 16, "E_EXPECTED_COUNT", "validators")
        require(len(profiles) == expected["packet_schema_count"] == 16, "E_EXPECTED_COUNT", "schemas")
        require(len(packets) == expected["evidence_packet_schema_count"] == 15, "E_EXPECTED_COUNT", "evidence schemas")
        require(expected["owner_packet_schema_count"] == 1, "E_EXPECTED_COUNT", "owner schema")
        require(expected["real_evidence_items_present"] == 0, "E_EXPECTED_BOUNDARY", "evidence")
        require(expected["production_validated_evidence_items"] == 0, "E_EXPECTED_BOUNDARY", "validated")
        require(expected["runtime_prerequisites_satisfied"] == 0, "E_EXPECTED_BOUNDARY", "satisfied")
        require(expected["positive_decision_representable"] is False, "E_EXPECTED_BOUNDARY", "positive")
        require(expected["downstream_gates_authorized"] == 0, "E_EXPECTED_BOUNDARY", "downstream")

        receipt: dict[str, Any] = {
            "all_nonclaims_explicit": nonclaims.all_explicit(),
            "case_results": case_results,
            "case_results_sha256": sha256_value(case_results),
            "condition_outputs": 0,
            "content_sha256": "0" * 64,
            "credentials_accessed": 0,
            "date": "2026-07-17",
            "decision": DECISION,
            "downstream_gates_authorized": 0,
            "downstream_separate_gate_count": len(DOWNSTREAM_GATE_IDS),
            "evidence_packet_schema_count": 15,
            "evidence_schema_sha256": sha256_value(evidence_schema),
            "experiment_rows": 0,
            "freshness_arithmetic_conformant_count": len(packets),
            "next_unit": NEXT_UNIT,
            "nonclaim_field_count": len(nonclaims.as_dict()),
            "nonclaims_sha256": sha256_value(nonclaims.as_dict()),
            "offline_double_conformant_count": len(case_results),
            "offline_validator_double_count": len(case_results),
            "output_permits": 0,
            "owner_decision_recorded": False,
            "owner_identity_bound": False,
            "owner_packet_schema_count": 1,
            "owner_schema_sha256": sha256_value(owner_schema),
            "packet_profile_catalog_sha256": sha256_value(profiles),
            "packet_schema_count": len(profiles),
            "positive_decision_representable": False,
            "predecessor_fixture_sha256": sha256_value(predecessor_fixture),
            "predecessor_manifest_sha256": sha256_value(predecessor_manifest),
            "predecessor_plan_sha256": sha256_value(plan),
            "production_validated_evidence_items": 0,
            "provider_calls": 0,
            "real_currentness_proved": False,
            "real_evidence_items_present": 0,
            "runtime_admission_granted": False,
            "runtime_admission_ready": False,
            "runtime_authority": False,
            "runtime_evidence_accepted": 0,
            "runtime_prerequisites_satisfied": 0,
            "runtime_rows": 0,
            "schema": RECEIPT_SCHEMA,
            "schema_conformant_count": len(case_results),
            "side_effects_unlocked": "NONE",
            "status": STATUS,
            "synthetic_packet_count": len(case_results),
            "synthetic_packet_set_sha256": _derive_packet_set_sha256(packet_ids),
            "tracks_represented": len(TRACKS),
            "wire_attempts": 0,
        }
        content = copy.deepcopy(receipt)
        del content["content_sha256"]
        receipt["content_sha256"] = sha256_value(content)
        return receipt


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


def render_tsv(receipt: Mapping[str, Any]) -> str:
    rows: list[str] = []
    for field in TSV_FIELDS:
        require(field in receipt, "E_TSV_FIELD", field)
        value = receipt[field]
        rendered = "true" if value is True else "false" if value is False else str(value)
        require("\t" not in rendered and "\n" not in rendered, "E_TSV_VALUE", field)
        rows.append(f"{field}\t{rendered}")
    return "\n".join(rows) + "\n"
