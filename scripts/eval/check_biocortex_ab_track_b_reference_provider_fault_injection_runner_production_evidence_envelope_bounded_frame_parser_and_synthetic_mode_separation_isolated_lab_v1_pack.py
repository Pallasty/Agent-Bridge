#!/usr/bin/env python3
"""Independent checker for the isolated-lab bounded-frame/mode pack.

The checker deliberately does not reuse the implementation's decoder,
canonicalizer, envelope validator, or hashing helpers.  It independently
replays the two positive KATs and the committed adversarial catalog, verifies
that every public frame ingress rejects non-KAT modes before observing the
frame, and keeps all production-control counters at zero.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Callable, Mapping, NoReturn


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MIN_INT64 = -(2**63)
MAX_INT64 = 2**63 - 1

SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1.py"
)
SCHEMA_REL = (
    "docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-"
    "runner-production-evidence-envelope-v1.schema.json"
)
FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1_pack_synthetic_v0.json"
)
EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1_pack.expected.v0.tsv"
)
MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1_pack_v0.json"
)
REPORT_REL = (
    "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-"
    "injection-runner-production-evidence-envelope-bounded-frame-parser-and-"
    "synthetic-mode-separation-isolated-lab-v1-pack.md"
)
GATE_REL = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-"
    "production-evidence-envelope-bounded-frame-parser-and-synthetic-mode-"
    "separation-isolated-lab-v1-pack.sh"
)

PRED_REPORT_REL = (
    "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-"
    "injection-runner-production-evidence-ingestion-implementation-authority-and-"
    "resource-binding-decision-v1-pack.md"
)
PRED_GATE_REL = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-"
    "production-evidence-ingestion-implementation-authority-and-resource-binding-"
    "decision-v1-pack.sh"
)
PRED_SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "production_evidence_ingestion_implementation_authority_and_resource_binding_"
    "decision_v1.py"
)
PRED_CHECKER_REL = (
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_ingestion_implementation_authority_and_resource_"
    "binding_decision_v1_pack.py"
)
PRED_EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_ingestion_implementation_authority_and_resource_"
    "binding_decision_v1_pack.expected.v0.tsv"
)
PRED_DECISION_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_ingestion_implementation_authority_and_resource_"
    "binding_decision_v1_pack_owner_decision_v0.json"
)
PRED_MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_ingestion_implementation_authority_and_resource_"
    "binding_decision_v1_pack_v0.json"
)
PRED_RAW_SHA256 = {
    PRED_REPORT_REL: "27e7a5662fcc1861f6dfef7026389bb185854171fe81767f4c6b1c0292d3e6ea",
    PRED_GATE_REL: "743fb03730df6e2717b95da8dfcbb8d94a2b83ba2b7442b6b2cf3d95f39a73cd",
    PRED_SOURCE_REL: "8d3357d85513d4715553b363ebeca8ae825f92776f674ebd35acb8437c4684fa",
    PRED_CHECKER_REL: "e7194d800ec811612ca7f003f1a1c29cde07ee3e9788ec8d3632c0eb4853ade0",
    PRED_EXPECTED_REL: "cb9aca5ec6bf5fe9889d37adffb509b6249752de913356ebf4eece51993f815e",
    PRED_DECISION_REL: "69e2976c1298263240e384817df3a172686e80b8a7c57359829d9e50dda5e3c3",
    PRED_MANIFEST_REL: "86a03cc5c97729a1b7b8ca35885e98840cb72fda44eff8a789fa9b7520de3150",
}
PRED_RECEIPT_CONTENT_SHA256 = (
    "48f4eee93f565005ffa79a119529d58e5d61eb947754d4672c96541001268463"
)

SOURCE_RAW_SHA256 = "bfa3badbe2b467fbed610d5acb42ef21f1aec2ceb2d5ccf2c218fecfe438eed1"
SCHEMA_RAW_SHA256 = "e8cb4964f86de39b16d553537467006454c720dc8bfa8d36e370189627328f55"
SCHEMA_CANONICAL_SHA256 = "c063d91c43ee4d73e5b01f396cd4da9aea2adafc78b17198a54d995b43c31f33"

DATE = "2026-07-17"
FIXTURE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1_pack.synthetic.v0"
)
PACK_RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1_pack.receipt.v0"
)
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_PRODUCTION_EVIDENCE_ENVELOPE_"
    "BOUNDED_FRAME_AND_SYNTHETIC_MODE_SEPARATION_ISOLATED_LAB_COMPONENTS_"
    "IMPLEMENTED_LOCAL_KAT_CONFORMANT_PRODUCTION_CONTROLS_ZERO_RUNTIME_UNBOUND"
)
DECISION = "ISOLATED_LAB_FRAME_AND_MODE_COMPONENTS_CONFORMANT_PRODUCTION_PATH_FAIL_CLOSED"
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "BOOTSTRAP_TRUST_AUTHENTICATION_ISOLATED_LAB_IMPLEMENTATION_AUTHORITY_AND_"
    "RESOURCE_BINDING_DECISION"
)
COMPONENT_STATE = "PARSED_ISOLATED_LAB_KAT_COMPONENT_ONLY"
SYNTHETIC_MODE = "SYNTHETIC_KAT"
PRODUCTION_MODE = "PRODUCTION"
ENVELOPE_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_kat.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner."
    "production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_"
    "separation_isolated_lab_v1.receipt.v0"
)
PACKET_KIND = "SYNTHETIC_PRODUCTION_EVIDENCE_ENVELOPE_KAT"
HASH_DOMAIN = "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_KAT_V1"
RECEIPT_DOMAIN = "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_KAT_RECEIPT_V1"
RECEIPT_SET_DOMAIN = "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_RECEIPT_SET_V1"
RAW_SET_DOMAIN = "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_RAW_FRAME_SET_V1"
CANONICAL_SET_DOMAIN = (
    "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_CANONICAL_FRAME_SET_V1"
)
PACK_RECEIPT_DOMAIN = "AB_TRACK_B_PRODUCTION_EVIDENCE_ENVELOPE_ISOLATED_LAB_PACK_RECEIPT_V1"
CANONICALIZATION = "AGENT_BRIDGE_CANONICAL_JSON_V1_SORTED_KEYS_COMPACT_UTF8"
TRACK_IDS = ("MANAGED_SPANNER_CLOUD_KMS", "SELF_HOSTED_ETCD_OPENBAO")
PREREQUISITE_ID = "FRAME_AND_PARSE"
FIXTURE_CASE_ID = "VALID_MINIMAL_FRAME_V1"
FIXTURE_PAYLOAD = "NONSECRET_DETERMINISTIC_UTF8_JSON_FRAME_KAT_V1"

LIMITS = {
    "max_array_items": 64,
    "max_input_frame_bytes": 1_048_576,
    "max_json_depth": 32,
    "max_json_nodes": 4_096,
    "max_object_members": 256,
    "max_parallel_workers": 1,
    "max_signed_int64": MAX_INT64,
    "min_signed_int64": MIN_INT64,
}
ENVELOPE_KEYS = {
    "canonicalization", "fixture_case_id", "fixture_payload", "hash_domain",
    "packet_kind", "prerequisite_id", "production_admissible", "schema",
    "schema_version", "synthetic_fixture", "track_id",
}
RECEIPT_FIELDS = (
    "array_count", "array_item_count", "canonical_bytes_match_raw",
    "canonical_frame_sha256", "canonicalization", "component_state",
    "content_sha256", "custody_committed", "domain_separated_frame_sha256",
    "downstream_gates_authorized", "envelope_schema",
    "evidence_acceptance_authorized", "execution_mode", "frame_bytes",
    "hash_domain", "isolated_lab_candidate_surface_component_implemented",
    "isolated_lab_candidate_surface_component_total", "json_depth", "node_count",
    "object_count", "object_member_count", "packet_kind", "production_admissible",
    "production_ingestion_control_count", "production_ingestion_controls_implemented",
    "production_ingestion_controls_runtime_exercised",
    "production_validated_evidence_items", "provider_authority", "raw_frame_sha256",
    "real_evidence_items_present", "runtime_authority", "schema",
    "side_effects_unlocked", "status", "synthetic_fixture", "track_id",
)
FIXTURE_KEYS = {
    "schema", "date", "execution_mode", "limits", "valid_frames",
    "expected_receipts", "negative_cases", "threat_contract", "boundary",
    "nonclaims", "predecessor",
}
THREAT_CONTRACT = {
    "locally_kat_covered": ["T01", "T02", "T03", "T04"],
    "deferred": [f"T{index:02d}" for index in range(5, 21)],
    "production_runtime_exercised": [],
}
BOUNDARY = {
    "boundary_threat_specifications_locally_kat_covered": 4,
    "downstream_gates_authorized": 0,
    "isolated_lab_candidate_surface_component_implemented": 2,
    "isolated_lab_candidate_surface_component_locally_kat_exercised": 2,
    "isolated_lab_candidate_surface_component_total": 2,
    "production_ingestion_control_count": 14,
    "production_ingestion_controls_implemented": 0,
    "production_ingestion_controls_runtime_exercised": 0,
    "production_threat_cases_runtime_exercised": 0,
    "production_validated_evidence_items": 0,
    "provider_authority": False,
    "real_evidence_items_present": 0,
    "runtime_authority": False,
    "runtime_evidence_accepted": 0,
    "runtime_prerequisites_satisfied": 0,
    "runtime_side_effects_unlocked": "NONE",
    "threat_case_count": 20,
}
NONCLAIM_KEYS = {
    "any_production_ingestion_control_implemented", "application_claim_authorized",
    "bootstrap_trust_authentication_implemented", "bootstrap_trust_implementation_authorized",
    "condition_output_authorized", "credential_or_secret_material_accessed",
    "deployment_authorized", "downstream_gate_authority_derived", "durable_custody_proved",
    "durable_replay_cas_proved", "evidence_acceptance_authorized",
    "evidence_authenticated", "evidence_quarantined", "evidence_semantically_validated",
    "experiment_rows_created", "external_paid_spend_authorized", "fault_injected",
    "fault_injection_authorized", "global_single_use_proved",
    "independent_checker_is_security_approval", "local_kat_is_production_mitigation",
    "operational_production_evidence_schema_defined", "output_permit_defined",
    "owner_decision_recorded", "owner_handoff_set_defined", "owner_identity_bound",
    "paid_resource_provisioned", "parser_production_fitness_proved",
    "production_credentials_authorized", "production_denial_of_service_resistance_proved",
    "production_endpoint_bound", "production_environment_implementation_authorized",
    "production_frame_and_parse_control_implemented", "production_ingestion_enabled",
    "production_ingestion_implemented", "production_resource_authority_bound",
    "production_rollback_authority_bound", "production_security_approval",
    "production_signer_bound", "production_synthetic_mode_separation_control_implemented",
    "production_threat_exercised", "production_trust_root_bound", "provider_authority",
    "provider_called", "real_evidence_accepted", "real_evidence_collected",
    "real_evidence_ingested", "real_evidence_parsed", "real_evidence_present",
    "real_evidence_validated", "remote_reference_dereferenced", "runner_launch_authorized",
    "runner_launched", "runtime_admission_granted", "runtime_admission_ready",
    "runtime_authority", "runtime_owner_decision_recorded", "runtime_owner_identity_bound",
    "runtime_rows_created", "scientific_claim_authorized", "trusted_production_time_bound",
    "validation_receipt_is_production_evidence_receipt", "wire_attempted",
}
PREDECESSOR = {
    "artifact_raw_sha256": PRED_RAW_SHA256,
    "expected_receipt_line_count": 56,
    "integration_commit": "58ab80243bc1e9484a4c4ac65dba978f35307abf",
    "receipt_content_sha256": PRED_RECEIPT_CONTENT_SHA256,
    "source_commit": "5d46f0ac978548c4373c5db89ae8c8557048df44",
    "source_parent": "d5bbe55d5d95b1163e287415f437cf77c594135d",
}

PACK_TSV_FIELDS = (
    "schema", "status", "decision", "date", "mode", "next_unit",
    "component_state", "valid_frame_count", "fixture_negative_case_count",
    "public_mode_pre_observation_test_count", "source_direct_adversarial_reference_count",
    "track_count", "receipt_set_sha256", "raw_frame_set_sha256",
    "canonical_frame_set_sha256", "isolated_lab_candidate_surface_component_total",
    "isolated_lab_candidate_surface_component_implemented",
    "isolated_lab_candidate_surface_component_locally_kat_exercised",
    "boundary_threat_specifications_locally_kat_covered", "threat_case_count",
    "production_threat_cases_runtime_exercised", "production_ingestion_control_count",
    "production_ingestion_controls_implemented",
    "production_ingestion_controls_runtime_exercised", "real_evidence_items_present",
    "production_validated_evidence_items", "runtime_evidence_accepted",
    "runtime_prerequisites_satisfied", "downstream_gates_authorized",
    "runtime_authority", "provider_authority", "runtime_side_effects_unlocked",
    "schema_raw_sha256", "schema_canonical_sha256", "source_raw_sha256",
    "fixture_raw_sha256", "predecessor_artifact_count",
    "predecessor_receipt_line_count", "predecessor_receipt_content_sha256",
    "content_sha256",
)

TEST_COUNTS = {
    "envelope_identity_negative_tests": 13,
    "frame_decode_negative_tests": 48,
    "manifest_negative_tests": 25,
    "mode_separation_negative_tests": 9,
    "receipt_negative_tests": 72,
    "schema_negative_tests": 22,
    "source_ast_negative_tests": 10,
    "total_directed_negative_tests": 199,
}


class CheckError(ValueError):
    """Independent checker failure."""


class OracleError(ValueError):
    """Independent frame oracle rejection."""

    def __init__(self, code: str, detail: str = "", detail_code: str | None = None) -> None:
        self.code = code
        self.detail = detail
        self.detail_code = detail_code
        super().__init__(f"{code}: {detail}")


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {detail}")


def reject(code: str, detail: str = "") -> NoReturn:
    raise OracleError(code, detail)


def exact_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(exact_equal(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(exact_equal(a, b) for a, b in zip(left, right))
    return bool(left == right)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def domain_sha256(domain: str, value_or_bytes: Any) -> str:
    raw = value_or_bytes if type(value_or_bytes) is bytes else canonical_bytes(value_or_bytes)
    return sha256(domain.encode("ascii") + b"\0" + raw)


def safe_path(relative: str) -> Path:
    parsed = PurePosixPath(relative)
    require(not parsed.is_absolute() and ".." not in parsed.parts and str(parsed) == relative,
            "E_PATH", relative)
    cursor = ROOT
    for part in parsed.parts:
        cursor /= part
        require(not cursor.is_symlink(), "E_SYMLINK", relative)
    require(cursor.is_file(), "E_FILE", relative)
    resolved = cursor.resolve()
    require(ROOT == resolved or ROOT in resolved.parents, "E_ESCAPE", relative)
    return cursor


def read_bytes(relative: str) -> bytes:
    raw = safe_path(relative).read_bytes()
    require(len(raw) <= MAX_DOCUMENT_BYTES, "E_DOCUMENT_SIZE", relative)
    return raw


def raw_sha256(relative: str) -> str:
    return sha256(read_bytes(relative))


def duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "E_DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def bounded_int(token: str) -> int:
    require(len(token) <= 20, "E_JSON_INTEGER_OVERFLOW", token)
    value = int(token, 10)
    require(MIN_INT64 <= value <= MAX_INT64, "E_JSON_INTEGER_OVERFLOW", token)
    return value


def reject_float(token: str) -> NoReturn:
    raise CheckError(f"E_JSON_FLOAT: {token}")


def reject_constant(token: str) -> NoReturn:
    raise CheckError(f"E_JSON_NONFINITE: {token}")


def parse_artifact_json(raw: bytes, label: str) -> dict[str, Any]:
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_JSON_BOM", label)
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(text, object_pairs_hook=duplicate_object, parse_int=bounded_int,
                           parse_float=reject_float, parse_constant=reject_constant)
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {label}") from error
    require(type(value) is dict, "E_JSON_ROOT", label)
    return value


def read_json(relative: str) -> dict[str, Any]:
    return parse_artifact_json(read_bytes(relative), relative)


def load_module() -> ModuleType:
    path = safe_path(SOURCE_REL).resolve()
    spec = importlib.util.spec_from_file_location("isolated_lab_frame_subject", path)
    require(spec is not None and spec.loader is not None, "E_IMPORT", SOURCE_REL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == path, "E_IMPORT_ORIGIN", SOURCE_REL)
    return module


def expected_envelope(track_id: str) -> dict[str, Any]:
    require(track_id in TRACK_IDS, "E_TRACK", track_id)
    return {
        "canonicalization": CANONICALIZATION,
        "fixture_case_id": FIXTURE_CASE_ID,
        "fixture_payload": FIXTURE_PAYLOAD,
        "hash_domain": HASH_DOMAIN,
        "packet_kind": PACKET_KIND,
        "prerequisite_id": PREREQUISITE_ID,
        "production_admissible": False,
        "schema": ENVELOPE_SCHEMA,
        "schema_version": 1,
        "synthetic_fixture": True,
        "track_id": track_id,
    }


def inspect_shape(value: Any, depth: int = 1) -> dict[str, int]:
    if depth > LIMITS["max_json_depth"]:
        reject("E_JSON_DEPTH", "depth")
    stats = {"array_count": 0, "array_item_count": 0, "json_depth": depth,
             "node_count": 1, "object_count": 0, "object_member_count": 0}
    if value is None or type(value) in (bool, int, str):
        if type(value) is int and not MIN_INT64 <= value <= MAX_INT64:
            reject("E_JSON_INTEGER_RANGE", "range")
        if type(value) is str:
            if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
                reject("E_JSON_UNICODE_SCALAR", "surrogate")
            stripped = value.strip()
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", stripped) or stripped.startswith(("//", "\\\\")):
                reject("E_REMOTE_REFERENCE_FORBIDDEN", "value")
            if stripped.casefold() in {"gzip", "zip", "zlib", "zstd", "deflate", "br", "bzip2", "xz",
                                      "7z", "lz4", "snappy",
                                      "application/gzip", "application/zip", "application/x-bzip2",
                                      "application/x-xz"}:
                reject("E_COMPRESSION_FORBIDDEN", "value")
        return stats
    if type(value) is float:
        reject("E_JSON_FLOAT_FORBIDDEN", "float")
    if type(value) is list:
        if len(value) > LIMITS["max_array_items"]:
            reject("E_JSON_ARRAY_ITEMS", "items")
        stats["array_count"] = 1
        stats["array_item_count"] = len(value)
        children = enumerate(value)
    elif type(value) is dict:
        if len(value) > LIMITS["max_object_members"]:
            reject("E_JSON_OBJECT_MEMBERS", "members")
        stats["object_count"] = 1
        stats["object_member_count"] = len(value)
        remote_names = {"$id", "$ref", "endpoint", "href", "provider_endpoint",
                        "remote_ref", "remote_reference", "uri", "url"}
        compression_names = {"codec", "compressed", "compression", "compression_algorithm",
                             "compression_codec", "content_encoding"}
        for key in value:
            if any(0xD800 <= ord(character) <= 0xDFFF for character in key):
                reject("E_JSON_UNICODE_SCALAR", "surrogate key")
            lower = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).replace("-", "_").replace(".", "_").casefold()
            if lower in remote_names or lower.endswith(("_endpoint", "_href", "_remote_ref",
                                                         "_remote_reference", "_uri", "_url")):
                reject("E_REMOTE_REFERENCE_FORBIDDEN", key)
            if lower in compression_names or lower.endswith("_compression"):
                reject("E_COMPRESSION_FORBIDDEN", key)
        children = value.items()
    else:
        reject("E_JSON_TYPE", type(value).__name__)
    for _, child_value in children:
        child_depth = depth + 1 if type(child_value) in (dict, list) else depth
        child = inspect_shape(child_value, child_depth)
        for key in stats:
            stats[key] = max(stats[key], child[key]) if key == "json_depth" else stats[key] + child[key]
        if stats["node_count"] > LIMITS["max_json_nodes"]:
            reject("E_JSON_NODE_COUNT", "nodes")
    return stats


def internal_decode(frame: bytes) -> tuple[dict[str, Any], dict[str, int]]:
    if type(frame) is not bytes:
        reject("E_FRAME_TYPE", "bytes")
    if not frame:
        reject("E_FRAME_EMPTY", "empty")
    if len(frame) > LIMITS["max_input_frame_bytes"]:
        reject("E_FRAME_TOO_LARGE", "size")
    boms = (b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00", b"\xef\xbb\xbf", b"\xfe\xff", b"\xff\xfe")
    if any(frame.startswith(prefix) for prefix in boms):
        reject("E_BOM_FORBIDDEN", "bom")
    magics = (b"\x1f\x8b", b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08", b"BZh",
              b"\xfd7zXZ\x00", b"7z\xbc\xaf\x27\x1c", b"\x28\xb5\x2f\xfd",
              b"\x04\x22\x4d\x18", b"\xff\x06\x00\x00sNaPpY", b"\x78\x01", b"\x78\x9c", b"\x78\xda")
    if any(frame.startswith(prefix) for prefix in magics):
        reject("E_COMPRESSION_FORBIDDEN", "magic")
    if frame[:1] in b" \t\r\n" or frame[-1:] in b" \t\r\n":
        reject("E_FRAME_OUTER_WHITESPACE", "outer")
    try:
        text = frame.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        reject("E_UTF8_INVALID", "utf8")
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
            if depth > LIMITS["max_json_depth"]:
                reject("E_JSON_DEPTH", "raw depth")
        elif char in "}]":
            depth = max(0, depth - 1)
    try:
        decoder = json.JSONDecoder(object_pairs_hook=lambda pairs: oracle_pairs(pairs),
                                   parse_int=oracle_int, parse_float=oracle_float,
                                   parse_constant=oracle_constant, strict=True)
        value, end = decoder.raw_decode(text)
    except OracleError:
        raise
    except (json.JSONDecodeError, RecursionError):
        reject("E_JSON_SYNTAX", "syntax")
    if end != len(text):
        reject("E_JSON_TRAILING_DATA", "trailing")
    if type(value) is not dict:
        reject("E_JSON_ROOT_NOT_OBJECT", "root")
    return value, inspect_shape(value)


def oracle_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            reject("E_JSON_DUPLICATE_KEY", key)
        result[key] = value
    return result


def oracle_int(token: str) -> int:
    if len(token) > 20:
        reject("E_JSON_INTEGER_RANGE", token)
    value = int(token, 10)
    if not MIN_INT64 <= value <= MAX_INT64:
        reject("E_JSON_INTEGER_RANGE", token)
    return value


def oracle_float(token: str) -> NoReturn:
    reject("E_JSON_FLOAT_FORBIDDEN", token)


def oracle_constant(token: str) -> NoReturn:
    reject("E_JSON_NONFINITE", token)


def oracle_review(frame: bytes, mode: Any) -> dict[str, Any]:
    if type(mode) is str and mode == PRODUCTION_MODE:
        raise OracleError("E_PRODUCTION_MODE_NOT_AUTHORIZED")
    if type(mode) is not str or mode != SYNTHETIC_MODE:
        raise OracleError("E_MODE_UNKNOWN")
    try:
        envelope, stats = internal_decode(frame)
        canonical = canonical_bytes(envelope)
        if canonical != frame:
            reject("E_FRAME_NONCANONICAL", "canonical")
    except OracleError as error:
        raise OracleError("E_PRODUCTION_FRAME_REJECTED", detail_code=error.code) from error
    try:
        if set(envelope) != ENVELOPE_KEYS:
            reject("E_ENVELOPE_KEYS", "keys")
        track = envelope.get("track_id")
        if type(track) is not str or track not in TRACK_IDS:
            reject("E_ENVELOPE_TRACK", "track")
        expected = expected_envelope(track)
        codes = {
            "schema": "E_ENVELOPE_SCHEMA", "schema_version": "E_ENVELOPE_SCHEMA_VERSION",
            "packet_kind": "E_ENVELOPE_PACKET_KIND", "hash_domain": "E_ENVELOPE_HASH_DOMAIN",
            "canonicalization": "E_ENVELOPE_CANONICALIZATION",
            "synthetic_fixture": "E_ENVELOPE_SYNTHETIC_FLAG",
            "production_admissible": "E_ENVELOPE_PRODUCTION_FLAG",
            "track_id": "E_ENVELOPE_TRACK", "prerequisite_id": "E_ENVELOPE_PREREQUISITE",
            "fixture_case_id": "E_ENVELOPE_FIXTURE_CASE",
            "fixture_payload": "E_ENVELOPE_FIXTURE_PAYLOAD",
        }
        for key, code in codes.items():
            if type(envelope[key]) is not type(expected[key]) or envelope[key] != expected[key]:
                reject(code, key)
    except OracleError as error:
        raise OracleError("E_SYNTHETIC_PRODUCTION_DOMAIN_REJECTED",
                          detail_code=error.code) from error
    receipt: dict[str, Any] = {
        "array_count": stats["array_count"], "array_item_count": stats["array_item_count"],
        "canonical_bytes_match_raw": True, "canonical_frame_sha256": sha256(canonical),
        "canonicalization": CANONICALIZATION, "component_state": COMPONENT_STATE,
        "content_sha256": "0" * 64, "custody_committed": False,
        "domain_separated_frame_sha256": domain_sha256(HASH_DOMAIN, canonical),
        "downstream_gates_authorized": 0, "envelope_schema": ENVELOPE_SCHEMA,
        "evidence_acceptance_authorized": False, "execution_mode": SYNTHETIC_MODE,
        "frame_bytes": len(frame), "hash_domain": HASH_DOMAIN,
        "isolated_lab_candidate_surface_component_implemented": 2,
        "isolated_lab_candidate_surface_component_total": 2,
        "json_depth": stats["json_depth"], "node_count": stats["node_count"],
        "object_count": stats["object_count"], "object_member_count": stats["object_member_count"],
        "packet_kind": PACKET_KIND, "production_admissible": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_validated_evidence_items": 0, "provider_authority": False,
        "raw_frame_sha256": sha256(frame), "real_evidence_items_present": 0,
        "runtime_authority": False, "schema": RECEIPT_SCHEMA, "side_effects_unlocked": "NONE",
        "status": "PRODUCTION_SHAPED_EVIDENCE_ENVELOPE_ISOLATED_LAB_SYNTHETIC_KAT_FRAME_REVIEWED_NO_PRODUCTION_AUTHORITY",
        "synthetic_fixture": True, "track_id": track,
    }
    unsigned = dict(receipt)
    del unsigned["content_sha256"]
    receipt["content_sha256"] = domain_sha256(RECEIPT_DOMAIN, unsigned)
    return receipt


def oracle_decode_public(frame: bytes, mode: Any) -> dict[str, Any]:
    """Independent public decode ingress with the same pre-observation mode ceiling."""

    if type(mode) is str and mode == PRODUCTION_MODE:
        raise OracleError("E_PRODUCTION_MODE_NOT_AUTHORIZED")
    if type(mode) is not str or mode != SYNTHETIC_MODE:
        raise OracleError("E_MODE_UNKNOWN")
    value, _ = internal_decode(frame)
    return value


def check_schema(schema: dict[str, Any]) -> None:
    expected_top = {"$schema", "title", "description", "$comment", "type", "required",
                    "properties", "additionalProperties", "unevaluatedProperties",
                    "minProperties", "maxProperties"}
    require(set(schema) == expected_top, "E_SCHEMA_KEYS", "top")
    require(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema",
            "E_SCHEMA_DRAFT", "draft")
    require(schema["type"] == "object" and schema["additionalProperties"] is False
            and schema["unevaluatedProperties"] is False, "E_SCHEMA_CLOSED", "object")
    require(schema["required"] == sorted(ENVELOPE_KEYS), "E_SCHEMA_REQUIRED", "order")
    require(schema["minProperties"] == 11 and schema["maxProperties"] == 11,
            "E_SCHEMA_CARDINALITY", "11")
    require(set(schema["properties"]) == ENVELOPE_KEYS, "E_SCHEMA_PROPERTIES", "keys")
    expected = expected_envelope(TRACK_IDS[0])
    for key in sorted(ENVELOPE_KEYS - {"track_id"}):
        prop = schema["properties"][key]
        require(set(prop) == {"type", "const"} and exact_equal(prop["const"], expected[key]),
                "E_SCHEMA_CONST", key)
        expected_type = "boolean" if type(expected[key]) is bool else "integer" if type(expected[key]) is int else "string"
        require(prop["type"] == expected_type, "E_SCHEMA_TYPE", key)
    require(exact_equal(schema["properties"]["track_id"],
                        {"type": "string", "enum": list(TRACK_IDS)}),
            "E_SCHEMA_TRACKS", "two tracks")
    require("not an operational production evidence schema" in schema["description"],
            "E_SCHEMA_NONCLAIM", "description")


def expected_packet() -> dict[str, Any]:
    paths = [SCHEMA_REL, SOURCE_REL, str(Path(SOURCE_REL).with_name(Path(__file__).name)),
             FIXTURE_REL, EXPECTED_REL, MANIFEST_REL, REPORT_REL, GATE_REL]
    modes = {path: ("100755" if path == GATE_REL else "100644") for path in paths}
    return {"all_add_required": True, "modes": modes, "path_count": 8, "paths": paths}


def expected_manifest_boundary() -> dict[str, Any]:
    return {
        "authorization_scope_consumed_only_by_integrated_release": True,
        "bootstrap_trust_authentication_authorized": False,
        "component_implementation_scope": "ISOLATED_LAB_CODE_SCHEMA_TEST_DOCUMENTATION_ONLY",
        "custody_committed": False, "downstream_gate_count": 4,
        "downstream_gates_authorized": 0, "evidence_acceptance_authorized": False,
        "isolated_lab_candidate_surface_components_implemented": 2,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 2,
        "local_threat_specifications_covered": 4, "owner_handoff_eligible": False,
        "production_admissible": False,
        "production_environment_implementation_authorized": False,
        "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_ingestion_enabled": False, "production_ingestion_implemented": False,
        "production_mode_success_representable": False,
        "production_threat_specification_count": 20,
        "production_validated_evidence_items": 0, "provider_authority": False,
        "real_evidence_input_authorized": False, "real_evidence_items_present": 0,
        "runtime_admission_granted": False, "runtime_admission_ready": False,
        "runtime_authority": False, "runtime_evidence_accepted": 0,
        "runtime_owner_decision_recorded": False, "runtime_owner_identity_bound": False,
        "runtime_prerequisite_count": 16, "runtime_prerequisites_satisfied": 0,
        "runtime_side_effects_unlocked": "NONE", "source_commit_is_release_evidence": False,
    }


def expected_manifest_results() -> dict[str, Any]:
    return {
        "all_nonclaims_explicit": True, "downstream_gate_count": 4,
        "downstream_gates_authorized": 0, "isolated_lab_candidate_surface_component_count": 2,
        "isolated_lab_candidate_surface_components_implemented": 2,
        "isolated_lab_candidate_surface_components_locally_kat_exercised": 2,
        "local_threat_specification_count": 4, "production_ingestion_control_count": 14,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "production_mode_success_state_count": 0, "production_threat_specification_count": 20,
        "production_threat_specifications_runtime_exercised": 0,
        "production_validated_evidence_items": 0, "real_evidence_items_present": 0,
        "runtime_evidence_accepted": 0, "runtime_prerequisite_count": 16,
        "runtime_prerequisites_satisfied": 0, "synthetic_kat_receipt_count": 2,
        "tracks_locally_kat_validated": 2,
    }


def expected_resource_binding() -> dict[str, Any]:
    return {
        "allowed_resource_classes": ["EXISTING_LOCAL_CPU_AND_MEMORY",
                                     "ISOLATED_AGENT_BRIDGE_WORKTREE",
                                     "PRIVATE_LOCAL_TEST_SCRATCH"],
        "component_limits": {
            "floating_point_allowed": False, "max_array_items": 64,
            "max_input_frame_bytes": 1_048_576, "max_json_depth": 32,
            "max_json_nodes": 4_096, "max_object_members": 256,
            "max_parallel_workers": 1, "max_private_scratch_bytes": 67_108_864,
            "max_signed_integer": MAX_INT64, "min_signed_integer": MIN_INT64,
        },
        "component_runtime_network": False, "credential_handle_count": 0,
        "credential_path_count": 0, "currency_scope": "ALL_CURRENCIES_ZERO_ONLY",
        "effective_external_paid_spend_cap": 0, "owner_supplied_numeric_budget_cap": False,
        "production_resource_authority_bound": False, "provider_endpoint_count": 0,
        "real_evidence_input_authorized": False,
        "test_data_scope": "COMMITTED_NONSECRET_SYNTHETIC_KAT_FIXTURES_ONLY",
    }


def expected_manifest_predecessor() -> dict[str, Any]:
    return {
        "artifact_raw_sha256": PRED_RAW_SHA256, "gate_path": PRED_GATE_REL,
        "gate_sha256": PRED_RAW_SHA256[PRED_GATE_REL],
        "integration_commit": "58ab80243bc1e9484a4c4ac65dba978f35307abf",
        "integration_parents": ["d5bbe55d5d95b1163e287415f437cf77c594135d",
                                "5d46f0ac978548c4373c5db89ae8c8557048df44"],
        "integration_tree": "24c932f02e112a6f1b3b5261577ee12c0410c9b6",
        "manifest_path": PRED_MANIFEST_REL,
        "manifest_sha256": PRED_RAW_SHA256[PRED_MANIFEST_REL],
        "receipt_content_sha256": PRED_RECEIPT_CONTENT_SHA256,
        "source_commit": "5d46f0ac978548c4373c5db89ae8c8557048df44",
        "source_parent": "d5bbe55d5d95b1163e287415f437cf77c594135d",
    }


def expected_test_oracle() -> dict[str, Any]:
    return {
        **TEST_COUNTS, "positive_track_kats": 2, "predecessor_artifact_hashes_frozen": 7,
        "predecessor_exact_receipt": "PASS", "schema_draft_2020_12": "PASS",
        "schema_parser_independence": "PASS", "source_ast_purity": "PASS",
    }


def normalize_manifest_placeholders(manifest: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(manifest)
    hashes = {
        SCHEMA_REL: raw_sha256(SCHEMA_REL), SOURCE_REL: raw_sha256(SOURCE_REL),
        str(Path(SOURCE_REL).with_name(Path(__file__).name)):
            raw_sha256(str(Path(SOURCE_REL).with_name(Path(__file__).name))),
        FIXTURE_REL: raw_sha256(FIXTURE_REL), EXPECTED_REL: raw_sha256(EXPECTED_REL),
    }
    placeholders = {
        SCHEMA_REL: "__SCHEMA_SHA256__", SOURCE_REL: "__SOURCE_SHA256__",
        str(Path(SOURCE_REL).with_name(Path(__file__).name)): "__CHECKER_SHA256__",
        FIXTURE_REL: "__FIXTURE_SHA256__", EXPECTED_REL: "__EXPECTED_SHA256__",
    }
    for path, expected in hashes.items():
        observed = result["evidence_sha256"].get(path)
        require(observed in (expected, placeholders[path]), "E_MANIFEST_HASH", path)
        result["evidence_sha256"][path] = expected
    count_placeholders = {
        "envelope_identity_negative_tests": "__ENVELOPE_IDENTITY_NEGATIVE_TEST_COUNT__",
        "frame_decode_negative_tests": "__FRAME_DECODE_NEGATIVE_TEST_COUNT__",
        "manifest_negative_tests": "__MANIFEST_NEGATIVE_TEST_COUNT__",
        "mode_separation_negative_tests": "__MODE_SEPARATION_NEGATIVE_TEST_COUNT__",
        "receipt_negative_tests": "__RECEIPT_NEGATIVE_TEST_COUNT__",
        "schema_negative_tests": "__SCHEMA_NEGATIVE_TEST_COUNT__",
        "source_ast_negative_tests": "__SOURCE_AST_NEGATIVE_TEST_COUNT__",
        "total_directed_negative_tests": "__TOTAL_DIRECTED_NEGATIVE_TEST_COUNT__",
    }
    for field, placeholder in count_placeholders.items():
        observed = result["test_oracle"].get(field)
        require(observed in (TEST_COUNTS[field], placeholder), "E_MANIFEST_COUNT", field)
        result["test_oracle"][field] = TEST_COUNTS[field]
    return result


def validate_manifest(manifest: dict[str, Any]) -> None:
    top = {"boundary", "date", "decision", "evidence_sha256", "logical_baseline_commit",
           "logical_baseline_parent", "logical_baseline_tree", "next_unit", "nonclaims",
           "packet", "predecessor", "resource_binding", "results", "schema", "status",
           "test_oracle"}
    require(set(manifest) == top, "E_MANIFEST_KEYS", "top")
    scalars = {
        "schema": "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_production_evidence_envelope_bounded_frame_parser_and_synthetic_mode_separation_isolated_lab_v1_pack_manifest.v0",
        "status": STATUS, "decision": DECISION, "date": DATE, "next_unit": NEXT_UNIT,
        "logical_baseline_commit": "fa0cb9f088e0da2c55c92efde860d9521d4b7493",
        "logical_baseline_parent": "58ab80243bc1e9484a4c4ac65dba978f35307abf",
        "logical_baseline_tree": "7bafdda577cd79e364bac6af1b779374a3a7a52b",
    }
    for field, expected in scalars.items():
        require(manifest[field] == expected, "E_MANIFEST_SCALAR", field)
    expected_hashes = {path: raw_sha256(path) for path in
                       (SCHEMA_REL, SOURCE_REL, str(Path(SOURCE_REL).with_name(Path(__file__).name)),
                        FIXTURE_REL, EXPECTED_REL)}
    require(exact_equal(manifest["evidence_sha256"], expected_hashes),
            "E_MANIFEST_EVIDENCE", "raw hashes")
    require(exact_equal(manifest["packet"], expected_packet()), "E_MANIFEST_PACKET", "eight paths")
    require(exact_equal(manifest["predecessor"], expected_manifest_predecessor()),
            "E_MANIFEST_PREDECESSOR", "binding")
    require(exact_equal(manifest["resource_binding"], expected_resource_binding()),
            "E_MANIFEST_RESOURCE", "limits")
    require(exact_equal(manifest["results"], expected_manifest_results()),
            "E_MANIFEST_RESULTS", "counts")
    require(exact_equal(manifest["boundary"], expected_manifest_boundary()),
            "E_MANIFEST_BOUNDARY", "authority")
    require(set(manifest["nonclaims"]) == NONCLAIM_KEYS and
            all(value is False for value in manifest["nonclaims"].values()),
            "E_MANIFEST_NONCLAIMS", "63 false")
    require(exact_equal(manifest["test_oracle"], expected_test_oracle()),
            "E_MANIFEST_ORACLE", "counts")


def check_source_ast(text: str) -> None:
    tree = ast.parse(text, filename=SOURCE_REL)
    allowed = {"__future__", "hashlib", "json", "re", "typing"}
    forbidden_calls = {"__import__", "compile", "eval", "exec", "input", "open"}
    forbidden_attrs = {"connect", "environ", "fork", "getenv", "import_module", "now",
                       "Popen", "randbytes", "read", "read_bytes", "read_text", "recv",
                       "request", "run", "send", "sleep", "socket", "spawn", "system",
                       "time", "today", "token_bytes", "token_hex", "urandom", "urlopen",
                       "utcnow", "write", "write_bytes", "write_text"}
    public: set[str] = set()
    classes: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".", 1)[0] in allowed, "E_AST_IMPORT", alias.name)
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            require(node.level == 0 and name.split(".", 1)[0] in allowed, "E_AST_IMPORT", name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls, "E_AST_CALL", node.func.id)
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attrs, "E_AST_CALL", node.func.attr)
        elif isinstance(node, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await,
                               ast.Yield, ast.YieldFrom)):
            raise CheckError("E_AST_EFFECT: mutable/async/generator")
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            public.add(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append((node.name, [base.id for base in node.bases if isinstance(base, ast.Name)]))
    require(public == {"decode_frame", "known_answer_envelope", "known_answer_frame",
                       "review_frame", "review_known_answer"}, "E_AST_PUBLIC", str(public))
    require(classes == [("FrameReviewError", ["ValueError"])], "E_AST_CLASSES", str(classes))


def validate_predecessor() -> None:
    for relative, expected in PRED_RAW_SHA256.items():
        require(raw_sha256(relative) == expected, "E_PREDECESSOR_HASH", relative)
    lines = read_bytes(PRED_EXPECTED_REL).decode("utf-8").splitlines()
    require(len(lines) == 56, "E_PREDECESSOR_LINES", str(len(lines)))
    require(lines[-1] == f"content_sha256\t{PRED_RECEIPT_CONTENT_SHA256}",
            "E_PREDECESSOR_RECEIPT", "content")


def validate_fixture(fixture: dict[str, Any]) -> None:
    require(set(fixture) == FIXTURE_KEYS, "E_FIXTURE_KEYS", "top")
    require(fixture["schema"] == FIXTURE_SCHEMA and fixture["date"] == DATE
            and fixture["execution_mode"] == SYNTHETIC_MODE, "E_FIXTURE_ID", "identity")
    require(exact_equal(fixture["limits"], LIMITS), "E_FIXTURE_LIMITS", "limits")
    require(type(fixture["valid_frames"]) is list and len(fixture["valid_frames"]) == 2,
            "E_FIXTURE_VALID", "two")
    require(type(fixture["expected_receipts"]) is list and len(fixture["expected_receipts"]) == 2,
            "E_FIXTURE_RECEIPTS", "two")
    for index, row in enumerate(fixture["valid_frames"]):
        require(type(row) is dict and set(row) == {"track_id", "frame_utf8"},
                "E_VALID_FRAME_KEYS", str(index))
        require(row["track_id"] == TRACK_IDS[index] and type(row["frame_utf8"]) is str,
                "E_VALID_FRAME_ORDER", str(index))
    cases = fixture["negative_cases"]
    require(type(cases) is list and len(cases) == 64, "E_NEGATIVE_COUNT", str(len(cases)))
    require([row.get("case_id") for row in cases] == [f"N{i:03d}" for i in range(1, 65)],
            "E_NEGATIVE_IDS", "N001..N064")
    for row in cases:
        common = {"case_id", "execution_mode", "expected_code", "expected_detail_code",
                  "ingress",
                  "threat_case_id"}
        variants = set(row) - common
        require(set(row) >= common and variants in ({"frame_utf8"}, {"frame_hex"}, {"frame_recipe"}),
                "E_NEGATIVE_KEYS", row.get("case_id", "?"))
        require(row["threat_case_id"] in {"T01", "T02", "T03", "T04", "RESOURCE", "MODE", "DOMAIN"},
                "E_NEGATIVE_THREAT", row["case_id"])
        require(row["ingress"] in {"DECODE_FRAME", "REVIEW_FRAME"},
                "E_NEGATIVE_INGRESS", row["case_id"])
        if row["ingress"] == "DECODE_FRAME" and row["threat_case_id"] != "MODE":
            require(row["execution_mode"] == SYNTHETIC_MODE,
                    "E_DECODE_CASE_MODE", row["case_id"])
        require(type(row["expected_code"]) is str and
                (row["expected_detail_code"] is None or type(row["expected_detail_code"]) is str),
                "E_NEGATIVE_EXPECTED", row["case_id"])
    require({row["threat_case_id"] for row in cases} >= {"T01", "T02", "T03", "T04"},
            "E_NEGATIVE_COVERAGE", "T01-T04")
    require({row["ingress"] for row in cases} == {"DECODE_FRAME", "REVIEW_FRAME"},
            "E_NEGATIVE_INGRESS_COVERAGE", "both public ingress functions")
    require(exact_equal(fixture["threat_contract"], THREAT_CONTRACT), "E_THREATS", "contract")
    require(exact_equal(fixture["boundary"], BOUNDARY), "E_BOUNDARY", "contract")
    require(set(fixture["nonclaims"]) == NONCLAIM_KEYS and
            all(value is False for value in fixture["nonclaims"].values()),
            "E_NONCLAIMS", "all false")
    require(exact_equal(fixture["predecessor"], PREDECESSOR), "E_PREDECESSOR", "fixture")


def frame_from_case(row: Mapping[str, Any]) -> Any:
    if "frame_utf8" in row:
        return row["frame_utf8"].encode("utf-8")
    if "frame_hex" in row:
        value = row["frame_hex"]
        require(type(value) is str and len(value) % 2 == 0 and value == value.lower()
                and all(c in "0123456789abcdef" for c in value), "E_CASE_HEX", row["case_id"])
        return bytes.fromhex(value)
    recipe = row["frame_recipe"]
    require(type(recipe) is dict and type(recipe.get("kind")) is str,
            "E_RECIPE", row["case_id"])
    kind = recipe["kind"]
    if kind == "OVERSIZED_FRAME":
        require(set(recipe) == {"kind", "frame_bytes"} and
                recipe["frame_bytes"] == LIMITS["max_input_frame_bytes"] + 1,
                "E_RECIPE_OVERSIZE", row["case_id"])
        return b"{" + b"x" * (recipe["frame_bytes"] - 2) + b"}"
    if kind == "DEPTH_OVERFLOW":
        require(set(recipe) == {"kind", "depth"} and recipe["depth"] == 33,
                "E_RECIPE_DEPTH", row["case_id"])
        return ("[" * 33 + "0" + "]" * 33).encode()
    if kind == "OBJECT_MEMBER_OVERFLOW":
        require(set(recipe) == {"kind", "members"} and recipe["members"] == 257,
                "E_RECIPE_OBJECT", row["case_id"])
        return canonical_bytes({f"k{i:03d}": 0 for i in range(257)})
    if kind == "ARRAY_ITEM_OVERFLOW":
        require(set(recipe) == {"kind", "items"} and recipe["items"] == 65,
                "E_RECIPE_ARRAY", row["case_id"])
        return canonical_bytes({"x": [0] * 65})
    if kind == "NODE_OVERFLOW":
        require(set(recipe) == {"kind", "minimum_nodes"} and recipe["minimum_nodes"] == 4097,
                "E_RECIPE_NODES", row["case_id"])
        return canonical_bytes({"x": [[0] * 64 for _ in range(64)]})
    raise CheckError(f"E_RECIPE_KIND: {kind}")


def exception_codes(action: Callable[[], Any]) -> tuple[str, str | None]:
    try:
        action()
    except Exception as error:  # subject and oracle expose stable fields
        code = getattr(error, "code", None)
        require(type(code) is str, "E_EXCEPTION_CODE", type(error).__name__)
        detail = getattr(error, "detail_code", None)
        require(detail is None or type(detail) is str, "E_EXCEPTION_DETAIL", str(detail))
        return code, detail
    raise CheckError("E_NEGATIVE_ACCEPTED: action returned")


class ObservationBomb:
    """Frame sentinel whose observation is a checker failure."""

    observations = 0

    def _boom(self) -> NoReturn:
        type(self).observations += 1
        raise CheckError("E_FRAME_OBSERVED: mode guard ran too late")

    def __len__(self) -> int:
        self._boom()

    def __iter__(self):
        self._boom()

    def __getitem__(self, key: Any) -> Any:
        self._boom()

    def __bytes__(self) -> bytes:
        self._boom()


def check_mode_guards(module: ModuleType) -> int:
    count = 0
    for function_name in ("decode_frame", "review_frame"):
        function = getattr(module, function_name)
        for mode, expected in ((PRODUCTION_MODE, "E_PRODUCTION_MODE_NOT_AUTHORIZED"),
                               ("UNKNOWN", "E_MODE_UNKNOWN"), (7, "E_MODE_UNKNOWN")):
            ObservationBomb.observations = 0
            code, detail = exception_codes(lambda function=function, mode=mode:
                                           function(ObservationBomb(), mode))
            require((code, detail) == (expected, None), "E_MODE_GUARD_CODE", function_name)
            require(ObservationBomb.observations == 0, "E_MODE_GUARD_OBSERVED", function_name)
            count += 1
    return count


def check_module_contract(module: ModuleType) -> None:
    constants = {
        "CANONICALIZATION": CANONICALIZATION, "COMPONENT_STATE": COMPONENT_STATE,
        "ENVELOPE_SCHEMA": ENVELOPE_SCHEMA, "HASH_DOMAIN": HASH_DOMAIN,
        "PACKET_KIND": PACKET_KIND, "PREREQUISITE_ID": PREREQUISITE_ID,
        "PRODUCTION_MODE": PRODUCTION_MODE, "RECEIPT_HASH_DOMAIN": RECEIPT_DOMAIN,
        "RECEIPT_SCHEMA": RECEIPT_SCHEMA, "SYNTHETIC_KAT_MODE": SYNTHETIC_MODE,
        "TRACK_IDS": TRACK_IDS,
    }
    for name, expected in constants.items():
        require(exact_equal(getattr(module, name), expected), "E_MODULE_CONSTANT", name)
    require(tuple(module.ENVELOPE_KEYS) == tuple(sorted(ENVELOPE_KEYS)),
            "E_MODULE_ENVELOPE_KEYS", "order")
    require(issubclass(module.FrameReviewError, ValueError), "E_MODULE_ERROR", "class")


def receipt_set_hash(receipts: list[dict[str, Any]]) -> str:
    return domain_sha256(RECEIPT_SET_DOMAIN, [row["content_sha256"] for row in receipts])


def pack_receipt(fixture: dict[str, Any], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    raw_hashes = [row["raw_frame_sha256"] for row in receipts]
    canonical_hashes = [row["canonical_frame_sha256"] for row in receipts]
    result: dict[str, Any] = {
        "schema": PACK_RECEIPT_SCHEMA, "status": STATUS, "decision": DECISION,
        "date": DATE, "mode": SYNTHETIC_MODE, "next_unit": NEXT_UNIT,
        "component_state": COMPONENT_STATE, "valid_frame_count": 2,
        "fixture_negative_case_count": 64, "public_mode_pre_observation_test_count": 6,
        "source_direct_adversarial_reference_count": 64, "track_count": 2,
        "receipt_set_sha256": receipt_set_hash(receipts),
        "raw_frame_set_sha256": domain_sha256(RAW_SET_DOMAIN, raw_hashes),
        "canonical_frame_set_sha256": domain_sha256(CANONICAL_SET_DOMAIN, canonical_hashes),
        **BOUNDARY,
        "schema_raw_sha256": SCHEMA_RAW_SHA256,
        "schema_canonical_sha256": SCHEMA_CANONICAL_SHA256,
        "source_raw_sha256": SOURCE_RAW_SHA256,
        "fixture_raw_sha256": raw_sha256(FIXTURE_REL),
        "predecessor_artifact_count": 7, "predecessor_receipt_line_count": 56,
        "predecessor_receipt_content_sha256": PRED_RECEIPT_CONTENT_SHA256,
        "content_sha256": "0" * 64,
    }
    # Pack TSV omits redundant threat-list/evidence-plane fields from BOUNDARY.
    result = {field: result[field] for field in PACK_TSV_FIELDS}
    unsigned = dict(result)
    del unsigned["content_sha256"]
    result["content_sha256"] = domain_sha256(PACK_RECEIPT_DOMAIN, unsigned)
    return result


def render_tsv(receipt: Mapping[str, Any]) -> str:
    require(set(receipt) == set(PACK_TSV_FIELDS), "E_TSV_KEYS", "pack receipt")
    lines: list[str] = []
    for field in PACK_TSV_FIELDS:
        value = receipt[field]
        require(type(value) in (str, int, bool), "E_TSV_TYPE", field)
        text = "true" if value is True else "false" if value is False else str(value)
        require("\t" not in text and "\n" not in text, "E_TSV_INJECTION", field)
        lines.append(f"{field}\t{text}")
    return "\n".join(lines) + "\n"


def artifact_json_guard_tests() -> int:
    probes = (b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}',
              b'{"x":-Infinity}', b'{"x":1.5}', b'{"x":9223372036854775808}',
              b'{"x":-9223372036854775809}')
    for index, raw in enumerate(probes):
        try:
            parse_artifact_json(raw, f"probe-{index}")
        except CheckError:
            continue
        raise CheckError(f"E_JSON_GUARD_ACCEPTED: {index}")
    return len(probes)


def expect_checker_rejected(action: Callable[[], Any], label: str) -> None:
    try:
        action()
    except (CheckError, OracleError, ValueError, TypeError, KeyError, SyntaxError):
        return
    raise CheckError(f"E_MUTATION_ACCEPTED: {label}")


def schema_mutation_tests(schema: dict[str, Any]) -> int:
    candidates: list[dict[str, Any]] = []
    candidate = copy.deepcopy(schema); candidate["extra"] = False; candidates.append(candidate)
    candidate = copy.deepcopy(schema); del candidate["$comment"]; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["$schema"] += "x"; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["type"] = "array"; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["additionalProperties"] = True; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["unevaluatedProperties"] = True; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["minProperties"] = 10; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["maxProperties"] = 12; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["required"] = list(reversed(candidate["required"])); candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["properties"]["extra"] = {"const": 0}; candidates.append(candidate)
    candidate = copy.deepcopy(schema); del candidate["properties"]["schema"]; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["properties"]["schema"]["const"] += "x"; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["properties"]["track_id"]["enum"].reverse(); candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["properties"]["track_id"]["type"] = "integer"; candidates.append(candidate)
    candidate = copy.deepcopy(schema); candidate["description"] = "production schema"; candidates.append(candidate)
    require(len(candidates) == 15,
            "E_SCHEMA_TEST_COUNT", str(len(candidates)))
    for index, candidate in enumerate(candidates):
        expect_checker_rejected(lambda candidate=candidate: check_schema(candidate),
                                f"schema-{index}")
    return len(candidates)


def mutate_manifest_path(manifest: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    candidate = copy.deepcopy(manifest)
    cursor: Any = candidate
    for part in path[:-1]:
        cursor = cursor[part]
    value = cursor[path[-1]]
    cursor[path[-1]] = (not value if type(value) is bool else value + 1 if type(value) is int
                        else list(reversed(value)) if type(value) is list
                        else value + "_MUTATED")
    return candidate


def manifest_mutation_tests(manifest: dict[str, Any]) -> int:
    paths = (
        ("schema",), ("status",), ("decision",), ("date",), ("next_unit",),
        ("logical_baseline_commit",), ("logical_baseline_parent",),
        ("logical_baseline_tree",),
        ("boundary", "production_ingestion_controls_implemented"),
        ("boundary", "production_ingestion_controls_runtime_exercised"),
        ("boundary", "runtime_authority"), ("boundary", "provider_authority"),
        ("boundary", "bootstrap_trust_authentication_authorized"),
        ("results", "synthetic_kat_receipt_count"),
        ("results", "local_threat_specification_count"),
        ("results", "runtime_prerequisites_satisfied"),
        ("resource_binding", "component_runtime_network"),
        ("resource_binding", "effective_external_paid_spend_cap"),
        ("predecessor", "integration_commit"), ("predecessor", "source_commit"),
        ("packet", "path_count"), ("packet", "paths"),
        ("nonclaims", "runtime_authority"),
        ("test_oracle", "total_directed_negative_tests"),
        ("evidence_sha256", SOURCE_REL),
    )
    require(len(paths) == TEST_COUNTS["manifest_negative_tests"],
            "E_MANIFEST_TEST_COUNT", str(len(paths)))
    for path in paths:
        candidate = mutate_manifest_path(manifest, path)
        expect_checker_rejected(lambda candidate=candidate: validate_manifest(candidate),
                                "manifest-" + "-".join(path))
    return len(paths)


def run_fixture_cases(module: ModuleType, fixture: dict[str, Any]) -> int:
    for row in fixture["negative_cases"]:
        frame = frame_from_case(row)
        mode = row["execution_mode"]
        expected = (row["expected_code"], row["expected_detail_code"])
        try:
            if row["ingress"] == "DECODE_FRAME":
                subject = exception_codes(
                    lambda frame=frame, mode=mode: module.decode_frame(frame, mode)
                )
                oracle = exception_codes(
                    lambda frame=frame, mode=mode: oracle_decode_public(frame, mode)
                )
            else:
                subject = exception_codes(
                    lambda frame=frame, mode=mode: module.review_frame(frame, mode)
                )
                oracle = exception_codes(
                    lambda frame=frame, mode=mode: oracle_review(frame, mode)
                )
        except CheckError as error:
            raise CheckError(f"{row['case_id']}: {error}") from error
        require(subject == expected and oracle == expected, "E_CASE_RESULT", row["case_id"])
    return len(fixture["negative_cases"])


def source_ast_mutation_tests() -> int:
    source = read_bytes(SOURCE_REL).decode("utf-8")
    snippets = ("\nimport os\n", "\nimport socket\n", "\nfrom pathlib import Path\n",
                "\ndef public_extra():\n    pass\n", "\ndef _x():\n    return open('x')\n",
                "\ndef _x():\n    return __import__('os')\n", "\ndef _x():\n    global X\n",
                "\nasync def _x():\n    pass\n", "\ndef _x():\n    return x.read_text()\n",
                "\ndef _x():\n    return x.socket()\n")
    for index, snippet in enumerate(snippets):
        try:
            check_source_ast(source + snippet)
        except CheckError:
            continue
        raise CheckError(f"E_AST_MUTATION_ACCEPTED: {index}")
    return len(snippets)


def receipt_mutation_tests(module: ModuleType, receipts: list[dict[str, Any]], frames: list[bytes]) -> int:
    count = 0
    for index, receipt in enumerate(receipts):
        for field in RECEIPT_FIELDS:
            candidate = copy.deepcopy(receipt)
            value = candidate[field]
            candidate[field] = (not value if type(value) is bool else value + 1 if type(value) is int
                                else ("0" * 64 if type(value) is str and len(value) == 64 else str(value) + "_X"))
            require(not exact_equal(candidate, oracle_review(frames[index], SYNTHETIC_MODE)),
                    "E_RECEIPT_MUTATION", field)
            count += 1
    return count


def evaluate(self_test: bool, candidate: bool) -> tuple[str, dict[str, int]]:
    require(raw_sha256(SOURCE_REL) == SOURCE_RAW_SHA256, "E_SOURCE_HASH", SOURCE_REL)
    require(raw_sha256(SCHEMA_REL) == SCHEMA_RAW_SHA256, "E_SCHEMA_HASH", SCHEMA_REL)
    schema = read_json(SCHEMA_REL)
    require(sha256(canonical_bytes(schema)) == SCHEMA_CANONICAL_SHA256,
            "E_SCHEMA_CANONICAL", SCHEMA_REL)
    check_schema(schema)
    check_source_ast(read_bytes(SOURCE_REL).decode("utf-8"))
    validate_predecessor()
    fixture = read_json(FIXTURE_REL)
    validate_fixture(fixture)
    manifest_observed = read_json(MANIFEST_REL)
    manifest = normalize_manifest_placeholders(manifest_observed)
    validate_manifest(manifest)
    if not candidate:
        require(exact_equal(manifest_observed, manifest),
                "E_MANIFEST_PLACEHOLDER", "release manifest is not fully frozen")
    module = load_module()
    check_module_contract(module)
    mode_count = check_mode_guards(module)

    frames: list[bytes] = []
    receipts: list[dict[str, Any]] = []
    for index, row in enumerate(fixture["valid_frames"]):
        frame = row["frame_utf8"].encode("utf-8")
        expected_frame = canonical_bytes(expected_envelope(TRACK_IDS[index]))
        require(frame == expected_frame, "E_VALID_FRAME", TRACK_IDS[index])
        oracle = oracle_review(frame, SYNTHETIC_MODE)
        subject = module.review_frame(frame, SYNTHETIC_MODE)
        decoded = module.decode_frame(frame, SYNTHETIC_MODE)
        require(exact_equal(decoded, expected_envelope(TRACK_IDS[index])),
                "E_PUBLIC_DECODE", TRACK_IDS[index])
        require(exact_equal(subject, oracle)
                and exact_equal(fixture["expected_receipts"][index], oracle),
                "E_RECEIPT", TRACK_IDS[index])
        require(set(oracle) == set(RECEIPT_FIELDS), "E_RECEIPT_KEYS", TRACK_IDS[index])
        frames.append(frame)
        receipts.append(oracle)

    fixture_negative_count = run_fixture_cases(module, fixture)
    rendered = render_tsv(pack_receipt(fixture, receipts))
    if not candidate:
        require(rendered == read_bytes(EXPECTED_REL).decode("utf-8"),
                "E_EXPECTED_TSV", EXPECTED_REL)
    fixture_mode = sum(row["threat_case_id"] == "MODE" for row in fixture["negative_cases"])
    fixture_identity = sum(row["expected_code"] == "E_SYNTHETIC_PRODUCTION_DOMAIN_REJECTED"
                           for row in fixture["negative_cases"])
    fixture_frame = fixture_negative_count - fixture_mode - fixture_identity
    counts = {
        "fixture_negative_tests": fixture_negative_count,
        "public_mode_pre_observation_tests": mode_count,
        "artifact_json_guard_tests": 0,
        "envelope_identity_negative_tests": fixture_identity,
        "frame_decode_negative_tests": fixture_frame,
        "manifest_negative_tests": 0,
        "mode_separation_negative_tests": fixture_mode + mode_count,
        "receipt_negative_tests": 0,
        "schema_negative_tests": 0,
        "source_ast_negative_tests": 0,
        "total_directed_negative_tests": 0,
    }
    if self_test:
        counts["artifact_json_guard_tests"] = artifact_json_guard_tests()
        counts["schema_negative_tests"] = (
            counts["artifact_json_guard_tests"] + schema_mutation_tests(schema)
        )
        counts["manifest_negative_tests"] = manifest_mutation_tests(manifest)
        counts["source_ast_negative_tests"] = source_ast_mutation_tests()
        counts["receipt_negative_tests"] = receipt_mutation_tests(module, receipts, frames)
        directed_fields = tuple(TEST_COUNTS)
        counts["total_directed_negative_tests"] = sum(
            counts[field] for field in directed_fields
            if field != "total_directed_negative_tests"
        )
        require(all(counts[field] == expected for field, expected in TEST_COUNTS.items()),
                "E_SELF_TEST_COUNTS", str(counts))
    return rendered, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--candidate", action="store_true",
                        help="emit candidate TSV before the frozen expected file exists")
    args = parser.parse_args()
    try:
        rendered, counts = evaluate(args.self_test, args.candidate)
        if args.self_test:
            print("self_test\tPASS")
            for key in ("fixture_negative_tests", "public_mode_pre_observation_tests",
                        "artifact_json_guard_tests", "envelope_identity_negative_tests",
                        "frame_decode_negative_tests", "manifest_negative_tests",
                        "mode_separation_negative_tests", "receipt_negative_tests",
                        "schema_negative_tests", "source_ast_negative_tests",
                        "total_directed_negative_tests"):
                print(f"{key}\t{counts[key]}")
            print("predecessor_artifact_hashes_frozen\t7")
            print("predecessor_exact_receipt_lines\t56")
            print("source_ast_purity\tPASS")
        else:
            print(rendered, end="")
    except (CheckError, OracleError, ValueError, TypeError, KeyError, OSError,
            SyntaxError, UnicodeError) as error:
        print(f"isolated-lab frame/mode pack check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
