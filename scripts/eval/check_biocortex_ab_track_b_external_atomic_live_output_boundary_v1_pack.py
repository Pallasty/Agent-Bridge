#!/usr/bin/env python3
"""Validate the Track B external atomic live-output boundary v1 design pack.

The checker validates closed design bytes, qualified all-unverified evidence,
schema constraints, manifest joins, source purity, deterministic receipts, and
414 directed structural mutations.  It performs no provider, credential,
generator, physical-sink, or live-output operation.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable


BASELINE_COMMIT = "1de35708f92beaae35bfb4b16ab25292f343cfd1"
GUARD_SOURCE_COMMIT = "9763e987abbd0091b45abaf8db3af871eea482b8"
GUARD_INTEGRATION_COMMIT = "dee25a3832aef0ab6e18af0b0082162006a5e593"
S12_SOURCE_COMMIT = "611a10fb4133e6aa58ef76b6d02744b3a90fe09c"
S12_INTEGRATION_COMMIT = "f4ff82721caa3537e1e0ba2d7682017e09427858"
PACK_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_external_atomic_live_output_boundary_v1_"
    "pack_manifest.v0"
)
RESULT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_external_atomic_live_output_boundary_v1_"
    "pack_validation_result.v0"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_EXPERIMENT_V1_"
    "PREREGISTRATION"
)
SIGNATURE_DOMAIN_TAG = (
    b"agent-bridge/biocortex-ab/track-b/external-atomic-live-output/"
    b"authority-decision-signature/v1"
)
EXPECTED_AUTHORITY_DECISION_FIELDS = (
    "OPERATION_ID",
    "REQUEST_ENVELOPE_SHA256",
    "PROVIDER_INCARNATION",
    "ACTUAL_AUTHORITY_EPOCH",
    "ACTUAL_LEADER_TERM",
    "ACTUAL_COMMITTED_REVISION",
    "RECORD_SEQUENCE",
    "AUTHORITY_STATE",
    "CURRENTNESS_DECISION_SHA256",
    "ANTI_ROLLBACK_WITNESS_SHA256",
    "LOGICAL_SINK_RESERVATION_RECEIPT_SHA256",
    "LOGICAL_SINK_FENCE",
    "ACTUAL_SINK_IDENTITY_SHA256",
    "ACTUAL_SIGNER_KEY_VERSION",
)
EXPECTED_TERMINAL_VECTORS = (
    ("SEALED_OBSERVED", "EMPTY", "PERMANENTLY_FORBIDDEN", True, "TERMINAL_SINK_INCONSISTENCY"),
    ("SEALED_OBSERVED", "FIRST_BYTE_COMMITTED", "PERMANENTLY_FORBIDDEN", True, "TERMINAL_SINK_INCONSISTENCY"),
    ("SEALED_OBSERVED", "STREAMING", "PERMANENTLY_FORBIDDEN", True, "TERMINAL_SINK_INCONSISTENCY"),
    ("SEALED_OBSERVED", "SEALED", "POST_GENERATION_MAP_GATE_ONLY", False, "SUCCESS_SEALED_CANDIDATE"),
    ("BURNED_EMPTY", "EMPTY", "PERMANENTLY_FORBIDDEN", False, "BURNED_EMPTY_FINAL"),
    ("BURNED_EMPTY", "FIRST_BYTE_COMMITTED", "PERMANENTLY_FORBIDDEN", True, "UNEXPECTED_LATE_SINK_BYTES"),
    ("BURNED_EMPTY", "STREAMING", "PERMANENTLY_FORBIDDEN", True, "UNEXPECTED_LATE_SINK_BYTES"),
    ("BURNED_EMPTY", "SEALED", "PERMANENTLY_FORBIDDEN", True, "UNEXPECTED_LATE_SINK_BYTES"),
    ("PARTIAL_QUARANTINED", "EMPTY", "PERMANENTLY_FORBIDDEN", True, "TERMINAL_SINK_INCONSISTENCY"),
    ("PARTIAL_QUARANTINED", "FIRST_BYTE_COMMITTED", "PERMANENTLY_FORBIDDEN", False, "PARTIAL_TERMINAL_DOMINATES_LATE_SINK_PROGRESS"),
    ("PARTIAL_QUARANTINED", "STREAMING", "PERMANENTLY_FORBIDDEN", False, "PARTIAL_TERMINAL_DOMINATES_LATE_SINK_PROGRESS"),
    ("PARTIAL_QUARANTINED", "SEALED", "PERMANENTLY_FORBIDDEN", False, "PARTIAL_TERMINAL_DOMINATES_LATE_SINK_PROGRESS"),
    ("AMBIGUOUS_QUARANTINED", "EMPTY", "PERMANENTLY_FORBIDDEN", False, "AMBIGUOUS_TERMINAL_DOMINATES_PRESENT_OR_LATE_SINK_PROGRESS"),
    ("AMBIGUOUS_QUARANTINED", "FIRST_BYTE_COMMITTED", "PERMANENTLY_FORBIDDEN", False, "AMBIGUOUS_TERMINAL_DOMINATES_PRESENT_OR_LATE_SINK_PROGRESS"),
    ("AMBIGUOUS_QUARANTINED", "STREAMING", "PERMANENTLY_FORBIDDEN", False, "AMBIGUOUS_TERMINAL_DOMINATES_PRESENT_OR_LATE_SINK_PROGRESS"),
    ("AMBIGUOUS_QUARANTINED", "SEALED", "PERMANENTLY_FORBIDDEN", False, "AMBIGUOUS_TERMINAL_DOMINATES_PRESENT_OR_LATE_SINK_PROGRESS"),
)

SOURCE_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_external_atomic_live_output_boundary_v1.py"
)
CHECKER_PATH = Path(
    "scripts/eval/check_biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack.py"
)
CONTRACT_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-"
    "execution-boundary-contract-v1.json"
)
OBSERVATION_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-production-provider-prerequisite-"
    "observation-source-profile-schema-v1.json"
)
RECEIPT_SCHEMA_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-"
    "boundary-design-receipt-schema-v1.json"
)
OBSERVATION_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_"
    "boundary_v1_pack_synthetic_v0.json"
)
EXPECTED_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_"
    "boundary_v1_pack.expected.v0.tsv"
)
MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_"
    "boundary_v1_pack_v0.json"
)
REPORT_PATH = Path(
    "docs/reports/goal-c-u/2026-07-15-biocortex-track-b-external-atomic-live-"
    "output-boundary-v1-pack.md"
)
GATE_PATH = Path(
    "scripts/check-biocortex-ab-track-b-external-atomic-live-output-boundary-v1-pack.sh"
)
GUARD_MANIFEST_PATH = Path(
    "scripts/eval/fixtures/biocortex_ab_track_b_first_condition_output_guard_v1_pack_v0.json"
)
GUARD_GATE_PATH = Path(
    "scripts/check-biocortex-ab-track-b-first-condition-output-guard-v1-pack.sh"
)
GUARD_SOURCE_PATH = Path(
    "scripts/eval/biocortex_ab_track_b_first_condition_output_guard_v1.py"
)
S12_CONTRACT_PATH = Path(
    "docs/design/fixtures/biocortex-ab-track-b-recovered-s9-decision-"
    "reverification-s12-v0.json"
)
S12_GATE_PATH = Path(
    "scripts/check-memory-temporal-recovered-s9-decision-reverification-s12.sh"
)
S12_CHECKER_PATH = Path(
    "scripts/eval/check_memory_temporal_recovered_s9_decision_reverification_s12.py"
)
S12_SOURCE_PATH = Path(
    "crates/store/src/temporal_replay_transport/recovered_s9_decision_"
    "reverification.rs"
)

PACKET_PATHS = (
    str(RECEIPT_SCHEMA_PATH),
    str(CONTRACT_PATH),
    str(OBSERVATION_SCHEMA_PATH),
    str(SOURCE_PATH),
    str(CHECKER_PATH),
    str(OBSERVATION_PATH),
    str(EXPECTED_PATH),
    str(MANIFEST_PATH),
    str(REPORT_PATH),
    str(GATE_PATH),
)
EVIDENCE_PATHS = (
    str(RECEIPT_SCHEMA_PATH),
    str(CONTRACT_PATH),
    str(OBSERVATION_SCHEMA_PATH),
    str(SOURCE_PATH),
    str(CHECKER_PATH),
    str(OBSERVATION_PATH),
    str(GUARD_MANIFEST_PATH),
    str(GUARD_GATE_PATH),
    str(GUARD_SOURCE_PATH),
    str(S12_CONTRACT_PATH),
    str(S12_GATE_PATH),
    str(S12_CHECKER_PATH),
    str(S12_SOURCE_PATH),
)


class PackError(RuntimeError):
    """Pack-level validation failure."""


def fail(message: str) -> None:
    raise PackError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


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
        fail(f"cannot render canonical JSON: {exc}")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reference_signature_message(authority_decision_sha256: str) -> bytes:
    require(
        type(authority_decision_sha256) is str
        and len(authority_decision_sha256) == 64
        and all(character in "0123456789abcdef" for character in authority_decision_sha256),
        "reference signature digest is not canonical lower-hex SHA-256",
    )
    payload = bytes.fromhex(authority_decision_sha256)
    require(len(SIGNATURE_DOMAIN_TAG) == 93, "signature domain byte count drift")
    require(len(payload) == 32, "signature payload byte count drift")
    return (
        len(SIGNATURE_DOMAIN_TAG).to_bytes(4, "big")
        + SIGNATURE_DOMAIN_TAG
        + len(payload).to_bytes(8, "big")
        + payload
    )


def _reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_canonical(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda token: fail(f"{label} has non-finite {token}"),
            object_pairs_hook=_reject_pairs,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"cannot load {label}: {exc}")
    require(type(value) is dict, f"{label} root must be an object")
    require(canonical_bytes(value) == raw, f"{label} is not canonical JSON")
    return value, raw


def exact_keys(value: Any, expected: tuple[str, ...], label: str) -> None:
    require(type(value) is dict, f"{label} must be an object")
    require(tuple(sorted(value)) == tuple(sorted(expected)), f"{label} key drift")


def load_source_module(path: Path) -> tuple[Any, str]:
    name = "_ab_external_atomic_live_output_boundary_v1_owned"
    require(name not in sys.modules, "owned module name already occupied")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "cannot load boundary source")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(name, None)
        fail(f"cannot execute boundary source: {exc}")
    return module, name


def validate_source_ast(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    allowed_imports = {"__future__", "datetime", "hashlib", "json", "re", "typing"}
    forbidden_calls = {"__import__", "compile", "eval", "exec", "open"}
    forbidden_attributes = {
        "Popen",
        "call",
        "connect",
        "open",
        "popen",
        "request",
        "run",
        "system",
        "unlink",
        "write_bytes",
        "write_text",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            require(
                all(alias.name in allowed_imports for alias in node.names),
                "source import allowlist violation",
            )
        if isinstance(node, ast.ImportFrom):
            require(
                node.module in allowed_imports,
                "source from-import allowlist violation",
            )
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(
                    node.func.id not in forbidden_calls,
                    f"source forbidden call: {node.func.id}",
                )
            if isinstance(node.func, ast.Attribute):
                require(
                    node.func.attr not in forbidden_attributes,
                    f"source forbidden attribute call: {node.func.attr}",
                )


def validate_signature_and_terminal_closure(
    boundary: Any, contract: dict[str, Any]
) -> None:
    grain = contract["authority_grain"]
    decision_contract = grain["authority_decision_payload_contract"]
    require(
        tuple(decision_contract["field_names"])
        == EXPECTED_AUTHORITY_DECISION_FIELDS
        and tuple(
            profile["name"] for profile in decision_contract["field_profiles"]
        )
        == EXPECTED_AUTHORITY_DECISION_FIELDS,
        "authority decision payload field closure drift",
    )
    require(
        decision_contract["excluded_result_fields"]
        == ["AUTHORITY_DECISION_SHA256", "SIGNATURE_RECEIPT_SHA256"],
        "authority decision digest/signature cycle exclusion drift",
    )
    require(
        decision_contract["request_envelope_resolution_rule"]
        == "RESOLVE_EXACT_CLOSED_REQUEST_ENVELOPE_BY_REQUEST_ENVELOPE_SHA256_RECOMPUTE_DIGEST_AND_VALIDATE_ALL_48_FIELDS",
        "authority decision request-envelope resolution drift",
    )
    require(
        decision_contract["result_projection_rule"]
        == "FINAL_RESULT_ENVELOPE_EXCLUDING_AUTHORITY_DECISION_SHA256_AND_SIGNATURE_RECEIPT_SHA256_HAS_EXACTLY_THE_14_PAYLOAD_FIELDS_AND_EVERY_VALUE_IS_BYTE_EQUAL_TO_THE_SIGNED_PAYLOAD_VALUE",
        "authority decision final-result byte-equal projection rule drift",
    )
    decision_kat = decision_contract["known_answer_test"]
    reference_decision = canonical_bytes(decision_kat["payload"])
    require(
        len(reference_decision) == 890
        and len(reference_decision)
        == decision_kat["payload_canonical_bytes"]
        and sha256_bytes(reference_decision)
        == "1a615a23b60b56c63acfc3fcccec8841b70fa5989b609e5fa1a18fd014387db3"
        == decision_kat["payload_sha256"],
        "authority decision transcript KAT drift",
    )
    require(
        boundary.canonical_authority_decision_payload_bytes(
            decision_kat["payload"]
        )
        == reference_decision,
        "owned and independent authority decision canonicalizers disagree",
    )
    result_names = tuple(
        profile["name"] for profile in grain["result_envelope"]["fields"]
    )
    require(
        tuple(
            name
            for name in result_names
            if name not in decision_contract["excluded_result_fields"]
        )
        == EXPECTED_AUTHORITY_DECISION_FIELDS,
        "final result is not the exact signed authority-decision projection",
    )
    receipt_contract = grain["signature_receipt_contract"]
    require(
        receipt_contract["canonicalization"]
        == "RFC8785_COMPATIBLE_RESTRICTED_CANONICAL_JSON_PROFILE_V1"
        and receipt_contract["duplicate_key_policy"]
        == "REJECT_BEFORE_CANONICALIZATION"
        and receipt_contract["max_canonical_bytes"] == 65536
        and receipt_contract["receipt_hash_rule"]
        == "SIGNATURE_RECEIPT_SHA256_EQUALS_LOWER_HEX_SHA256_OF_EXACT_CANONICAL_RECEIPT_BYTES",
        "signature receipt canonical content-hash profile drift",
    )
    require(
        "RESOLVE_EXACT_CLOSED_AUTHORITY_DECISION_PAYLOAD_BY_RESULT_AUTHORITY_DECISION_SHA256_AND_VALIDATE_ALL_FIELDS"
        in receipt_contract["verification_rules"],
        "signature does not require resolved closed authority decision payload",
    )
    key_binding = receipt_contract["key_binding"]
    require(
        key_binding["kms_resource_id_semantics"]
        == "EXACT_VERSIONED_SIGNER_RESOURCE_ID"
        and key_binding["kms_resource_rule"]
        == "KMS_RESOURCE_ID_BYTE_EQUALS_REQUEST_SIGNER_KMS_RESOURCE_ID"
        and key_binding["kms_response_name_rule"]
        == "KMS_RESPONSE_NAME_BYTE_EQUALS_KMS_RESOURCE_ID"
        and key_binding["public_key_material_encoding"]
        == "RAW_32_BYTE_RFC8032_ED25519_VERIFICATION_KEY",
        "exact signer resource or public-key encoding binding drift",
    )
    require(
        key_binding["public_key_provider_decode_rule"]
        == "STRICT_PEM_TO_DER_SUBJECTPUBLICKEYINFO_ED25519_OID_1_3_101_112_ABSENT_PARAMETERS_EXTRACT_EXACT_32_BYTE_SUBJECTPUBLICKEY",
        "provider public-key decoding rule drift",
    )
    message_contract = receipt_contract[
        "message_derivation"
    ]
    known_answer = message_contract["known_answer_test"]
    reference = reference_signature_message(
        known_answer["authority_decision_sha256"]
    )
    require(len(reference) == 137, "signature message byte count drift")
    require(
        reference.hex() == known_answer["message_hex"],
        "signature message KAT bytes drift",
    )
    require(
        sha256_bytes(reference) == known_answer["message_sha256"],
        "signature message KAT digest drift",
    )
    require(
        boundary.reconstruct_signature_message(
            known_answer["authority_decision_sha256"]
        )
        == reference,
        "owned and independent signature reconstructors disagree",
    )
    require(
        reference[-32:] == bytes(range(32))
        and reference[-64:] != known_answer["authority_decision_sha256"].encode(
            "ascii"
        ),
        "signature message must contain raw digest bytes, not ASCII hex",
    )
    state_machine = contract["state_machine"]
    vectors = state_machine["terminal_authority_sink_vectors"]
    expected_pairs = [
        (authority, sink)
        for authority in boundary.AUTHORITY_TERMINAL_STATES
        for sink in boundary.PHYSICAL_SINK_PERSISTENT_STATES
    ]
    actual_pairs = [
        (row["authority_state"], row["physical_sink_state"]) for row in vectors
    ]
    require(
        actual_pairs == expected_pairs and len(set(actual_pairs)) == 16,
        "terminal authority by sink vector coverage drift",
    )
    actual_vector_semantics = tuple(
        (
            row["authority_state"],
            row["physical_sink_state"],
            row["reviewer_visibility"],
            row["incident_overlay_required"],
            row["classification"],
        )
        for row in vectors
    )
    require(
        actual_vector_semantics == EXPECTED_TERMINAL_VECTORS,
        "terminal vector classification or incident semantics drift",
    )
    for row in vectors:
        require(
            row["required_fence_state"] == "TERMINAL_AUTHORITY_FENCED"
            and row["authority_action"] == "PRESERVE_ABSORBING_TERMINAL"
            and row["sink_action"] == "READ_ONLY_AFTER_FENCE",
            "terminal vector action drift",
        )
        if row["authority_state"] != "SEALED_OBSERVED" or row[
            "physical_sink_state"
        ] != "SEALED":
            require(
                row["reviewer_visibility"] == "PERMANENTLY_FORBIDDEN",
                "non-success terminal vector becomes visible",
            )
    success_vectors = [
        row
        for row in vectors
        if row["reviewer_visibility"] == "POST_GENERATION_MAP_GATE_ONLY"
    ]
    require(
        len(success_vectors) == 1
        and success_vectors[0]["authority_state"] == "SEALED_OBSERVED"
        and success_vectors[0]["physical_sink_state"] == "SEALED",
        "sealed success vector is not unique",
    )
    fence = state_machine["physical_sink_terminal_fence"]
    require(
        fence["global_cas_claimed"] is False
        and fence["authority_and_sink_fence_share_transaction"] is False
        and fence["unfence_allowed"] is False,
        "terminal fence overclaims cross-domain atomicity or reversibility",
    )
    require(
        fence["terminal_fence_absent_record_operation"]
        == "CREATE_TERMINAL_AUTHORITY_FENCED_EMPTY_RECORD_FOR_EXACT_ABSENT_OPERATION_AND_SLOT"
        and fence["terminal_fence_existing_record_operation"]
        == "INSTALL_TERMINAL_AUTHORITY_FENCE_FOR_EXACT_EXISTING_OPERATION_AND_SLOT",
        "terminal fence operation binding drift",
    )
    require(
        fence["binding_fields"]
        == [
            "OPERATION_ID",
            "SINK_SLOT_ID",
            "LOGICAL_SINK_FENCE",
            "AUTHORITY_STATE",
            "AUTHORITY_DECISION_SHA256",
            "RECORD_SEQUENCE",
        ],
        "terminal fence authority-decision binding drift",
    )
    required_mutations = {
        "ACCEPT_FIRST_BYTE_WITH_EXACT_FENCE_EXECUTOR_AND_CHUNK_INDEX",
        "APPEND_NEXT_CHUNK_WITH_EXACT_FENCE_AND_INDEX",
        "SEAL_EXACT_OUTPUT_ONCE",
    }
    require(
        set(
            fence[
                "mutating_operations_requiring_open_fence_in_same_sink_linearization"
            ]
        )
        == required_mutations,
        "sink mutation fence coverage drift",
    )
    transitions = state_machine["transitions"]
    for row in transitions:
        if row["operation"] in required_mutations:
            require(
                row["domain"] == "PHYSICAL_SINK"
                and row["atomic_precondition_scope"]
                == "PHYSICAL_SINK_RECORD_ONLY"
                and "OPEN" in row["atomic_precondition"],
                f"sink mutation is not atomically fence guarded: {row['operation']}",
            )
    absent_fence_transition = next(
        row
        for row in transitions
        if row["operation"]
        == "CREATE_TERMINAL_AUTHORITY_FENCED_EMPTY_RECORD_FOR_EXACT_ABSENT_OPERATION_AND_SLOT"
    )
    require(
        absent_fence_transition["domain"] == "PHYSICAL_SINK"
        and absent_fence_transition["atomic_precondition_scope"]
        == "PHYSICAL_SINK_RECORD_ONLY"
        and absent_fence_transition["atomic_precondition"]
        == "SINK_RECORD_IS_ABSENT_FOR_EXACT_OPERATION_AND_SLOT"
        and absent_fence_transition["next_authority_state"] == "UNCHANGED"
        and absent_fence_transition["next_sink_state"] == "EMPTY"
        and absent_fence_transition["next_sink_fence_state"]
        == "TERMINAL_AUTHORITY_FENCED",
        "absent terminal sink fence transition drift",
    )
    require(
        absent_fence_transition["cross_domain_observation_nonatomic"]
        == "VERIFIED_SIGNED_AUTHORITY_DECISION_PAYLOAD_HAS_TERMINAL_STATE_AND_EXACT_BINDINGS_NONATOMIC"
        and absent_fence_transition["linearization"]
        == "EXACT_ABSENT_PHYSICAL_SINK_RECORD_CAS_CREATE",
        "absent terminal sink fence linearization drift",
    )
    existing_fence_transition = next(
        row
        for row in transitions
        if row["operation"]
        == "INSTALL_TERMINAL_AUTHORITY_FENCE_FOR_EXACT_EXISTING_OPERATION_AND_SLOT"
    )
    require(
        existing_fence_transition["domain"] == "PHYSICAL_SINK"
        and existing_fence_transition["atomic_precondition_scope"]
        == "PHYSICAL_SINK_RECORD_ONLY"
        and existing_fence_transition["atomic_precondition"]
        == "SINK_RECORD_MATCHES_OPERATION_LOGICAL_FENCE_OPEN_AND_ANY_OUTPUT_STATE"
        and existing_fence_transition["next_authority_state"] == "UNCHANGED"
        and existing_fence_transition["next_sink_state"] == "UNCHANGED"
        and existing_fence_transition["next_sink_fence_state"]
        == "TERMINAL_AUTHORITY_FENCED",
        "existing terminal sink fence transition drift",
    )
    require(
        existing_fence_transition["cross_domain_observation_nonatomic"]
        == "VERIFIED_SIGNED_AUTHORITY_DECISION_PAYLOAD_HAS_TERMINAL_STATE_AND_EXACT_BINDINGS_NONATOMIC"
        and existing_fence_transition["linearization"]
        == "EXACT_PRE_STATE_PHYSICAL_SINK_RECORD_CAS",
        "existing terminal sink fence linearization drift",
    )
    initialization_transition = next(
        row
        for row in transitions
        if row["operation"]
        == "INITIALIZE_PHYSICAL_SINK_RECORD_FOR_EXACT_RESERVED_OPERATION_AND_SLOT"
    )
    require(
        initialization_transition["domain"] == "PHYSICAL_SINK"
        and initialization_transition["atomic_precondition"]
        == "SINK_RECORD_IS_ABSENT_FOR_EXACT_OPERATION_AND_SLOT"
        and initialization_transition["next_sink_state"] == "EMPTY"
        and initialization_transition["next_sink_fence_state"] == "OPEN"
        and initialization_transition["linearization"]
        == "EXACT_ABSENT_PHYSICAL_SINK_RECORD_CAS_CREATE",
        "physical sink initialization transition drift",
    )
    authorize_transition = next(
        row
        for row in transitions
        if row["operation"] == "AUTHORIZE_CONSUME_AND_RESERVE_LOGICAL_SINK"
    )
    require(
        authorize_transition["next_sink_state"] == "UNCHANGED"
        and authorize_transition["next_sink_fence_state"] == "UNCHANGED",
        "authority transaction appears to mutate physical sink state",
    )


def validate_json_schema(schema: dict[str, Any], label: str) -> None:
    require(
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        f"{label} draft drift",
    )
    require(schema.get("type") == "object", f"{label} root type drift")
    require(schema.get("additionalProperties") is False, f"{label} root open")
    require(
        schema.get("unevaluatedProperties") is False,
        f"{label} unevaluated properties open",
    )
    require(
        schema.get("required") == sorted(schema.get("properties", {})),
        f"{label} required/properties drift",
    )


def validate_matrix_schema(
    matrix: dict[str, Any],
    prerequisites: tuple[tuple[str, str], ...],
    label: str,
) -> None:
    require(matrix["type"] == "array", f"{label} type drift")
    require(matrix["items"] is False, f"{label} trailing items open")
    require(matrix["minItems"] == len(prerequisites), f"{label} min count drift")
    require(matrix["maxItems"] == len(prerequisites), f"{label} max count drift")
    rows = matrix["prefixItems"]
    require(len(rows) == len(prerequisites), f"{label} row count drift")
    for row, (code, _) in zip(rows, prerequisites):
        require(row["type"] == "object", f"{label} row type drift")
        require(row["additionalProperties"] is False, f"{label} row open")
        require(row["unevaluatedProperties"] is False, f"{label} row unevaluated open")
        require(
            row["required"]
            == ["evidence_receipt_sha256", "prerequisite_code", "verified"],
            f"{label} row required drift",
        )
        require(
            row["properties"]["prerequisite_code"]["const"] == code,
            f"{label} prerequisite code drift",
        )
        require(
            row["properties"]["verified"]["const"] is False,
            f"{label} raises verification",
        )
        require(
            row["properties"]["evidence_receipt_sha256"]["const"] is None,
            f"{label} invents evidence",
        )


def validate_schemas(root: Path, boundary: Any, receipt: dict[str, Any]) -> None:
    observation_schema, _ = load_canonical(
        root / OBSERVATION_SCHEMA_PATH, "observation schema"
    )
    receipt_schema, _ = load_canonical(root / RECEIPT_SCHEMA_PATH, "receipt schema")
    validate_json_schema(observation_schema, "observation schema")
    validate_json_schema(receipt_schema, "receipt schema")
    require(
        observation_schema["properties"]["schema"]["const"]
        == boundary.OBSERVATION_SCHEMA,
        "observation instance schema drift",
    )
    require(
        observation_schema["properties"]["predecessor_integration_commit"]["const"]
        == BASELINE_COMMIT,
        "observation baseline schema drift",
    )
    require(
        observation_schema["properties"]["external_organization_state_observed"][
            "const"
        ]
        is False,
        "observation schema claims external visibility",
    )
    require(
        observation_schema["properties"]["host_visibility_complete"]["const"] is False,
        "observation schema claims complete host visibility",
    )
    validate_matrix_schema(
        observation_schema["properties"]["prerequisite_evidence"],
        boundary.PREREQUISITES,
        "observation matrix",
    )
    require(
        receipt_schema["properties"]["schema"]["const"] == boundary.RECEIPT_SCHEMA,
        "receipt instance schema drift",
    )
    require(
        receipt_schema["properties"]["decision"]["const"] == boundary.DECISION,
        "receipt decision drift",
    )
    require(
        receipt_schema["properties"]["status"]["const"] == boundary.STATUS,
        "receipt status drift",
    )
    validate_matrix_schema(
        receipt_schema["properties"]["prerequisite_verification"],
        boundary.PREREQUISITES,
        "receipt matrix",
    )
    for key, value in receipt.items():
        if type(value) is bool:
            require(
                receipt_schema["properties"][key]["const"] is value,
                f"receipt schema boolean drift: {key}",
            )
    require(
        receipt_schema["properties"]["on_disk_artifact_identity_verified"]["const"]
        is False,
        "source receipt overclaims on-disk identity",
    )
    require(
        receipt_schema["properties"]["side_effects_unlocked"]["const"] == "NONE",
        "receipt schema unlocks side effects",
    )


def validate_manifest(root: Path, boundary: Any) -> dict[str, Any]:
    manifest, _ = load_canonical(root / MANIFEST_PATH, "pack manifest")
    exact_keys(
        manifest,
        (
            "baseline_commit",
            "boundary",
            "date",
            "decision",
            "evidence_sha256",
            "known_limitations",
            "next_unit",
            "packet",
            "predecessors",
            "provider_observation",
            "schema",
            "status",
            "test_oracle",
        ),
        "manifest",
    )
    require(manifest["schema"] == PACK_SCHEMA, "manifest schema drift")
    require(manifest["date"] == "2026-07-15", "manifest date drift")
    require(manifest["baseline_commit"] == BASELINE_COMMIT, "manifest baseline drift")
    require(manifest["decision"] == boundary.DECISION, "manifest decision drift")
    require(manifest["status"] == boundary.STATUS, "manifest status drift")
    require(manifest["next_unit"] == NEXT_UNIT, "manifest next unit drift")
    require(
        manifest["predecessors"]
        == {
            "current_baseline_commit": BASELINE_COMMIT,
            "first_condition_output_guard_integration_commit": GUARD_INTEGRATION_COMMIT,
            "first_condition_output_guard_source_commit": GUARD_SOURCE_COMMIT,
            "recovered_s9_reverification_integration_commit": S12_INTEGRATION_COMMIT,
            "recovered_s9_reverification_source_commit": S12_SOURCE_COMMIT,
        },
        "manifest predecessor drift",
    )
    packet = manifest["packet"]
    require(packet["paths"] == list(PACKET_PATHS), "manifest packet path/order drift")
    require(
        packet["modes"]
        == {
            path: ("100755" if path == str(GATE_PATH) else "100644")
            for path in PACKET_PATHS
        },
        "manifest packet mode drift",
    )
    evidence = manifest["evidence_sha256"]
    require(
        tuple(sorted(evidence)) == tuple(sorted(EVIDENCE_PATHS)),
        "manifest evidence path drift",
    )
    for relative in EVIDENCE_PATHS:
        require(
            evidence[relative] == sha256_bytes((root / relative).read_bytes()),
            f"manifest evidence hash drift: {relative}",
        )
    require(
        manifest["test_oracle"]
        == {
            "authority_decision_kat_bytes": 890,
            "authority_decision_payload_fields": 14,
            "authority_persistent_states": 7,
            "crash_cuts": 11,
            "directed_structural_negative_tests": 414,
            "invariants": 20,
            "physical_sink_terminal_fence_states": 2,
            "physical_sink_persistent_states": 4,
            "production_prerequisites": 18,
            "request_identity_bindings": 48,
            "result_bindings": 16,
            "signature_domain_bytes": 93,
            "signature_message_bytes": 137,
            "signature_receipt_fields": 10,
            "state_transitions": 13,
            "terminal_authority_sink_vectors": 16,
        },
        "manifest test oracle drift",
    )
    require(
        manifest["boundary"]
        == {
            "condition_output_authorized": False,
            "contract_schema_and_internal_consistency_verified": True,
            "live_output_capability_emitted": False,
            "live_output_permit_defined": False,
            "production_execution_runtime_verified": False,
            "receipt_is_output_permit": False,
            "side_effects_unlocked": "NONE",
        },
        "manifest boundary drift",
    )
    require(
        manifest["provider_observation"]
        == {
            "external_organization_state_observed": False,
            "future_host_or_external_state_automatically_rechecked": False,
            "host_visibility_complete": False,
            "observed_at_utc": "2026-07-15T15:00:00Z",
            "prerequisites_unbound_or_unverified": 18,
            "prerequisites_verified": 0,
            "scope": (
                "REPOSITORY_AND_CURRENT_PROCESS_HOST_VISIBILITY_NON_SECRET_AUDIT"
            ),
        },
        "manifest provider observation drift",
    )
    require(
        type(manifest["known_limitations"]) is list
        and len(manifest["known_limitations"]) >= 10,
        "manifest limitations incomplete",
    )
    return manifest


def build_receipt(
    root: Path,
    boundary: Any,
    contract_raw: bytes,
    observation_raw: bytes,
) -> dict[str, Any]:
    return boundary.build_design_receipt(
        contract_raw,
        observation_raw,
        evaluated_at_utc="2026-07-15T15:00:01Z",
        boundary_source_sha256=sha256_bytes((root / SOURCE_PATH).read_bytes()),
        observation_schema_sha256=sha256_bytes(
            (root / OBSERVATION_SCHEMA_PATH).read_bytes()
        ),
        receipt_schema_sha256=sha256_bytes((root / RECEIPT_SCHEMA_PATH).read_bytes()),
        predecessor_guard_manifest_sha256=sha256_bytes(
            (root / GUARD_MANIFEST_PATH).read_bytes()
        ),
        predecessor_s12_contract_sha256=sha256_bytes(
            (root / S12_CONTRACT_PATH).read_bytes()
        ),
    )


def directed_negatives(
    boundary: Any,
    contract: dict[str, Any],
    observation: dict[str, Any],
    receipt: dict[str, Any],
) -> int:
    count = 0

    def reject(label: str, action: Callable[[], Any]) -> None:
        nonlocal count
        try:
            action()
        except boundary.BoundaryError:
            count += 1
            return
        except Exception as exc:
            fail(
                f"negative {label} raised wrong exception: "
                f"{type(exc).__name__}: {exc}"
            )
        fail(f"negative {label} was accepted")

    for envelope, profiles in (
        ("request_envelope", boundary.REQUEST_FIELD_PROFILES),
        ("result_envelope", boundary.RESULT_FIELD_PROFILES),
    ):
        for index in range(len(profiles)):
            mutated = copy.deepcopy(contract)
            mutated["authority_grain"][envelope]["fields"][index][
                "source"
            ] = "UNTRUSTED"
            reject(
                f"{envelope}-mutate-{index}",
                lambda value=mutated: boundary.validate_contract(value),
            )
            removed = copy.deepcopy(contract)
            del removed["authority_grain"][envelope]["fields"][index]
            reject(
                f"{envelope}-remove-{index}",
                lambda value=removed: boundary.validate_contract(value),
            )
    mutated = copy.deepcopy(contract)
    mutated["authority_grain"]["operation_id_derivation"]["input_bindings"].append(
        "OPERATION_ID"
    )
    reject(
        "operation-id-self-reference",
        lambda: boundary.validate_contract(mutated),
    )
    mutated = copy.deepcopy(contract)
    mutated["authority_grain"]["operation_id_derivation"]["framing"] = (
        "AMBIGUOUS_CONCATENATION"
    )
    reject("operation-id-framing", lambda: boundary.validate_contract(mutated))
    for index in range(len(boundary.RESULT_REQUEST_CONSTRAINTS)):
        mutated = copy.deepcopy(contract)
        mutated["authority_grain"]["result_request_constraints"][index][
            "rule"
        ] = "ACCEPT_WITHOUT_JOIN"
        reject(
            f"result-request-constraint-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    mutated = copy.deepcopy(contract)
    mutated["authority_grain"]["signature_receipt_contract"]["closed"] = False
    reject("signature-receipt-open", lambda: boundary.validate_contract(mutated))
    for field, replacement in (
        ("canonicalization", "AMBIGUOUS_JSON"),
        ("duplicate_key_policy", "ACCEPT_LAST_VALUE"),
        ("max_canonical_bytes", 65535),
        ("receipt_hash_rule", "OPAQUE_RECEIPT_HASH"),
    ):
        mutated = copy.deepcopy(contract)
        mutated["authority_grain"]["signature_receipt_contract"][field] = replacement
        reject(
            f"signature-receipt-{field}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    signature_message_mutations: tuple[tuple[str, Any], ...] = (
        ("domain_tag", "agent-bridge/incorrect-domain/v1"),
        ("domain_tag_encoding", "UTF8_NFC"),
        ("framing", "AMBIGUOUS_CONCATENATION"),
        ("payload_field", "SIGNED_MESSAGE_SHA256"),
        ("payload_field_encoding", "UPPER_HEX_64"),
        ("payload_decoding", "ASCII_HEX_BYTES"),
        ("signature_scheme", "ED25519PH"),
        ("signer_input_mode", "PROVIDER_DIGEST"),
    )
    for field, replacement in signature_message_mutations:
        mutated = copy.deepcopy(contract)
        mutated["authority_grain"]["signature_receipt_contract"][
            "message_derivation"
        ][field] = replacement
        reject(
            f"signature-message-{field}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    for field, replacement in (
        ("domain_tag_bytes", 92),
        ("expected_message_bytes", 136),
    ):
        mutated = copy.deepcopy(contract)
        mutated["authority_grain"]["signature_receipt_contract"][
            "message_derivation"
        ][field] = replacement
        reject(
            f"signature-message-{field}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    for field in (
        "authority_decision_sha256",
        "message_hex",
        "message_sha256",
    ):
        mutated = copy.deepcopy(contract)
        mutated["authority_grain"]["signature_receipt_contract"][
            "message_derivation"
        ]["known_answer_test"][field] = "0" * 64
        reject(
            f"signature-message-kat-{field}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    known_digest = contract["authority_grain"]["signature_receipt_contract"][
        "message_derivation"
    ]["known_answer_test"]["authority_decision_sha256"]
    for label, value in (
        ("uppercase", known_digest.upper()),
        ("short", known_digest[:-1]),
        ("nonhex", "g" * 64),
    ):
        reject(
            f"signature-message-input-{label}",
            lambda candidate=value: boundary.reconstruct_signature_message(candidate),
        )
    decision_contract = contract["authority_grain"][
        "authority_decision_payload_contract"
    ]
    for index in range(len(decision_contract["field_profiles"])):
        mutated = copy.deepcopy(contract)
        mutated["authority_grain"]["authority_decision_payload_contract"][
            "field_profiles"
        ][index]["source"] = "UNTRUSTED"
        reject(
            f"authority-decision-profile-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    decision_contract_mutations: tuple[
        tuple[str, Callable[[dict[str, Any]], None]], ...
    ] = (
        (
            "digest-rule",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ].__setitem__("digest_rule", "OPAQUE_DIGEST"),
        ),
        (
            "excluded-fields",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ]["excluded_result_fields"].__setitem__(0, "REQUEST_ENVELOPE_SHA256"),
        ),
        (
            "field-names",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ]["field_names"].pop(),
        ),
        (
            "kat-payload",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ]["known_answer_test"]["payload"].__setitem__(
                "AUTHORITY_STATE", "SEALED_OBSERVED"
            ),
        ),
        (
            "kat-bytes",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ]["known_answer_test"].__setitem__("payload_canonical_bytes", 889),
        ),
        (
            "kat-sha",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ]["known_answer_test"].__setitem__("payload_sha256", "0" * 64),
        ),
        (
            "max-bytes",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ].__setitem__("max_canonical_bytes", 889),
        ),
        (
            "request-envelope-resolution",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ].__setitem__("request_envelope_resolution_rule", "OPAQUE_REQUEST_HASH"),
        ),
        (
            "result-projection",
            lambda value: value["authority_grain"][
                "authority_decision_payload_contract"
            ].__setitem__("result_projection_rule", "PARTIAL_OR_REENCODED_RESULT"),
        ),
    )
    for label, mutate in decision_contract_mutations:
        mutated = copy.deepcopy(contract)
        mutate(mutated)
        reject(
            f"authority-decision-{label}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    decision_payload = copy.deepcopy(
        decision_contract["known_answer_test"]["payload"]
    )
    missing_payload = copy.deepcopy(decision_payload)
    missing_payload.pop("AUTHORITY_STATE")
    extra_payload = copy.deepcopy(decision_payload)
    extra_payload["UNEXPECTED"] = "x"
    invalid_state_payload = copy.deepcopy(decision_payload)
    invalid_state_payload["AUTHORITY_STATE"] = "NOT_A_STATE"
    leading_zero_payload = copy.deepcopy(decision_payload)
    leading_zero_payload["RECORD_SEQUENCE"] = "04"
    invalid_decision_payloads = (
        ("missing", missing_payload),
        ("extra", extra_payload),
        ("invalid-state", invalid_state_payload),
        ("leading-zero", leading_zero_payload),
    )
    for label, payload in invalid_decision_payloads:
        reject(
            f"authority-decision-input-{label}",
            lambda candidate=payload: boundary.canonical_authority_decision_payload_bytes(
                candidate
            ),
        )
    for field in (
        "key_version_rule",
        "kms_resource_id_semantics",
        "kms_resource_rule",
        "kms_response_name_rule",
        "public_key_material_encoding",
        "public_key_provider_decode_rule",
        "public_key_sha256_rule",
    ):
        mutated = copy.deepcopy(contract)
        mutated["authority_grain"]["signature_receipt_contract"]["key_binding"][
            field
        ] = "AMBIGUOUS"
        reject(
            f"signature-key-binding-{field}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    vectors = contract["state_machine"]["terminal_authority_sink_vectors"]
    for index in range(len(vectors)):
        mutated = copy.deepcopy(contract)
        row = mutated["state_machine"]["terminal_authority_sink_vectors"][index]
        row["reviewer_visibility"] = (
            "PERMANENTLY_FORBIDDEN"
            if row["reviewer_visibility"] == "POST_GENERATION_MAP_GATE_ONLY"
            else "POST_GENERATION_MAP_GATE_ONLY"
        )
        reject(
            f"terminal-vector-visibility-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
        mutated = copy.deepcopy(contract)
        mutated["state_machine"]["terminal_authority_sink_vectors"][index][
            "incident_overlay_required"
        ] = not vectors[index]["incident_overlay_required"]
        reject(
            f"terminal-vector-incident-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
        mutated = copy.deepcopy(contract)
        mutated["state_machine"]["terminal_authority_sink_vectors"][index][
            "classification"
        ] = "WRONG_CLASSIFICATION"
        reject(
            f"terminal-vector-classification-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    state_mutations: tuple[
        tuple[str, Callable[[dict[str, Any]], None]], ...
    ] = (
        (
            "terminal-authority-rewrite",
            lambda value: value["state_machine"]["terminal_authority_dominance"].__setitem__(
                "authority_rewrite_after_terminal_allowed", True
            ),
        ),
        (
            "terminal-new-sink-authorization",
            lambda value: value["state_machine"]["terminal_authority_dominance"].__setitem__(
                "new_sink_mutation_authorization_after_terminal_allowed", True
            ),
        ),
        (
            "fence-global-cas",
            lambda value: value["state_machine"]["physical_sink_terminal_fence"].__setitem__(
                "global_cas_claimed", True
            ),
        ),
        (
            "fence-shared-transaction",
            lambda value: value["state_machine"]["physical_sink_terminal_fence"].__setitem__(
                "authority_and_sink_fence_share_transaction", True
            ),
        ),
        (
            "fence-unfence",
            lambda value: value["state_machine"]["physical_sink_terminal_fence"].__setitem__(
                "unfence_allowed", True
            ),
        ),
        (
            "fence-record-atomicity",
            lambda value: value["state_machine"]["physical_sink_terminal_fence"].__setitem__(
                "record_atomicity", "SEPARATE_RECORDS"
            ),
        ),
        (
            "fence-post-read",
            lambda value: value["state_machine"]["physical_sink_terminal_fence"].__setitem__(
                "post_fence_confirmation", "NO_REREAD"
            ),
        ),
        (
            "fence-binding",
            lambda value: value["state_machine"]["physical_sink_terminal_fence"][
                "binding_fields"
            ].__setitem__(0, "WRONG_OPERATION"),
        ),
        (
            "fence-state-remove",
            lambda value: value["state_machine"][
                "physical_sink_terminal_fence_states"
            ].pop(),
        ),
        (
            "fence-absent-operation-binding",
            lambda value: value["state_machine"]["physical_sink_terminal_fence"].__setitem__(
                "terminal_fence_absent_record_operation", "WRONG_ABSENT_OPERATION"
            ),
        ),
        (
            "fence-existing-operation-binding",
            lambda value: value["state_machine"]["physical_sink_terminal_fence"].__setitem__(
                "terminal_fence_existing_record_operation", "WRONG_EXISTING_OPERATION"
            ),
        ),
        (
            "fence-absent-transition-atomic-precondition",
            lambda value: next(
                row
                for row in value["state_machine"]["transitions"]
                if row["operation"]
                == "CREATE_TERMINAL_AUTHORITY_FENCED_EMPTY_RECORD_FOR_EXACT_ABSENT_OPERATION_AND_SLOT"
            ).__setitem__("atomic_precondition", "NOT_SAME_RECORD"),
        ),
        (
            "fence-existing-transition-atomic-precondition",
            lambda value: next(
                row
                for row in value["state_machine"]["transitions"]
                if row["operation"]
                == "INSTALL_TERMINAL_AUTHORITY_FENCE_FOR_EXACT_EXISTING_OPERATION_AND_SLOT"
            ).__setitem__("atomic_precondition", "NOT_SAME_RECORD"),
        ),
        (
            "late-first-byte-authority-rewrite",
            lambda value: next(
                row
                for row in value["state_machine"]["terminal_authority_sink_vectors"]
                if row["authority_state"] == "AMBIGUOUS_QUARANTINED"
                and row["physical_sink_state"] == "FIRST_BYTE_COMMITTED"
            ).__setitem__("authority_action", "PROMOTE_TO_SEALED"),
        ),
        (
            "terminal-vector-remove",
            lambda value: value["state_machine"][
                "terminal_authority_sink_vectors"
            ].pop(),
        ),
        (
            "sink-initialization-precondition",
            lambda value: next(
                row
                for row in value["state_machine"]["transitions"]
                if row["operation"]
                == "INITIALIZE_PHYSICAL_SINK_RECORD_FOR_EXACT_RESERVED_OPERATION_AND_SLOT"
            ).__setitem__("atomic_precondition", "NOT_ABSENT"),
        ),
        (
            "authority-initializes-sink",
            lambda value: next(
                row
                for row in value["state_machine"]["transitions"]
                if row["operation"]
                == "AUTHORIZE_CONSUME_AND_RESERVE_LOGICAL_SINK"
            ).__setitem__("next_sink_state", "EMPTY"),
        ),
    )
    for label, mutate in state_mutations:
        mutated = copy.deepcopy(contract)
        mutate(mutated)
        reject(label, lambda value=mutated: boundary.validate_contract(value))
    for index in range(len(boundary.PREREQUISITES)):
        mutated = copy.deepcopy(contract)
        mutated["production_prerequisites"][index][
            "evidence_class"
        ] = "FAKE_EVIDENCE"
        reject(
            f"prerequisite-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    for index in range(len(boundary.INVARIANTS)):
        mutated = copy.deepcopy(contract)
        mutated["invariants"][index] = "WEAKENED_INVARIANT"
        reject(
            f"invariant-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    for index in range(len(boundary.TRANSITIONS)):
        mutated = copy.deepcopy(contract)
        mutated["state_machine"]["transitions"][index]["operation"] = "BYPASS"
        reject(
            f"transition-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    for index in range(len(boundary.CRASH_CUTS)):
        mutated = copy.deepcopy(contract)
        mutated["crash_protocol"][index][
            "generator_reinvoke_allowed"
        ] = True
        reject(
            f"crash-cut-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    for field in contract["design_boundary"]:
        mutated = copy.deepcopy(contract)
        mutated["design_boundary"][field] = (
            "UNLOCKED" if field == "side_effects_unlocked" else True
        )
        reject(
            f"design-boundary-{field}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    for index in range(len(boundary.PROVIDER_REFERENCE_RESEARCH)):
        mutated = copy.deepcopy(contract)
        mutated["provider_reference_research"][index]["sources"][0] = (
            "https://example.invalid/substitution"
        )
        reject(
            f"research-source-{index}",
            lambda value=mutated: boundary.validate_contract(value),
        )
    mutated = copy.deepcopy(contract)
    mutated["predecessors"]["current_baseline_commit"] = "0" * 40
    reject("contract-baseline", lambda: boundary.validate_contract(mutated))
    for index in range(len(boundary.PREREQUISITES)):
        mutated = copy.deepcopy(observation)
        mutated["prerequisite_evidence"][index][
            "evidence_receipt_sha256"
        ] = "a" * 64
        reject(
            f"observation-evidence-{index}",
            lambda value=mutated: boundary.validate_observation(value),
        )
    observation_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("schema", lambda value: value.__setitem__("schema", "wrong")),
        ("scope", lambda value: value.__setitem__("audit_scope", "GLOBAL_ABSENCE")),
        (
            "external-org",
            lambda value: value.__setitem__(
                "external_organization_state_observed", True
            ),
        ),
        (
            "host-complete",
            lambda value: value.__setitem__("host_visibility_complete", True),
        ),
        (
            "time",
            lambda value: value.__setitem__(
                "observed_at_utc", "2026-99-99T00:00:00Z"
            ),
        ),
        (
            "baseline",
            lambda value: value.__setitem__(
                "predecessor_integration_commit", "0" * 40
            ),
        ),
        (
            "qualifier",
            lambda value: value.__setitem__(
                "absence_claim_scope_qualified", False
            ),
        ),
        (
            "secrets",
            lambda value: value.__setitem__(
                "secret_values_inspected_or_recorded", True
            ),
        ),
        (
            "side-effects",
            lambda value: value.__setitem__("side_effects_unlocked", "OUTPUT"),
        ),
        (
            "profile",
            lambda value: value.__setitem__("source_profile", "PRODUCTION"),
        ),
        (
            "inventory",
            lambda value: value["inventory"].__setitem__(
                "production_credential_binding_receipts_observed", 1
            ),
        ),
        ("extra", lambda value: value.__setitem__("unexpected", False)),
    ]
    for label, mutate in observation_mutations:
        mutated = copy.deepcopy(observation)
        mutate(mutated)
        reject(
            f"observation-{label}",
            lambda value=mutated: boundary.validate_observation(value),
        )
    true_receipt_fields = (
        "authority_envelopes_frozen",
        "caller_supplied_identity_digest_shapes_validated",
        "crash_protocol_frozen",
        "prerequisite_schema_frozen",
        "schema_and_internal_consistency_verified",
        "state_machine_frozen",
    )
    false_receipt_fields = (
        "all_generator_paths_guarded_verified",
        "anti_rollback_witness_verified",
        "condition_output_authorized",
        "crash_cut_operational_evidence_verified",
        "custodian_trust_pin_verified",
        "external_global_single_use_verified",
        "external_linearizable_authorize_consume_logical_sink_reservation_verified",
        "first_byte_cas_and_durability_verified",
        "guard_owned_sink_verified",
        "independent_fault_evidence_verified",
        "live_output_capability_emitted",
        "live_output_permit_defined",
        "loaded_runtime_attestation_verified",
        "non_bypassable_generator_runtime_verified",
        "on_disk_artifact_identity_verified",
        "owner_trust_pin_verified",
        "private_single_use_capability_verified",
        "production_provider_bound_and_verified",
        "receipt_is_output_permit",
        "trusted_currentness_at_use_verified",
    )
    for field in true_receipt_fields:
        mutated = copy.deepcopy(receipt)
        mutated[field] = False
        reject(
            f"receipt-lower-{field}",
            lambda value=mutated: boundary.validate_receipt(value),
        )
    for field in false_receipt_fields:
        mutated = copy.deepcopy(receipt)
        mutated[field] = True
        reject(
            f"receipt-raise-{field}",
            lambda value=mutated: boundary.validate_receipt(value),
        )
    for index in range(len(boundary.PREREQUISITES)):
        mutated = copy.deepcopy(receipt)
        mutated["prerequisite_verification"][index]["verified"] = True
        reject(
            f"receipt-prerequisite-{index}",
            lambda value=mutated: boundary.validate_receipt(value),
        )
    mutated = copy.deepcopy(receipt)
    mutated["blockers"] = mutated["blockers"][:-1]
    reject("receipt-blockers", lambda: boundary.validate_receipt(mutated))
    mutated = copy.deepcopy(receipt)
    mutated["side_effects_unlocked"] = "OUTPUT"
    reject("receipt-side-effects", lambda: boundary.validate_receipt(mutated))
    reject(
        "canonical-missing-newline",
        lambda: boundary.parse_canonical_object(b"{}", "negative"),
    )
    reject(
        "canonical-duplicate",
        lambda: boundary.parse_canonical_object(
            b'{"a": 1, "a": 2}\n', "negative"
        ),
    )
    reject(
        "canonical-nonfinite",
        lambda: boundary.parse_canonical_object(b'{"a": NaN}\n', "negative"),
    )
    reject(
        "canonical-oversize",
        lambda: boundary.parse_canonical_object(
            b"{" + b" " * boundary.MAX_CANONICAL_BYTES + b"}",
            "negative",
        ),
    )
    nested: dict[str, Any] = {}
    cursor = nested
    for _ in range(boundary.MAX_JSON_DEPTH + 2):
        child: dict[str, Any] = {}
        cursor["a"] = child
        cursor = child
    reject(
        "canonical-depth",
        lambda: boundary.parse_canonical_object(
            boundary.canonical_bytes(nested), "negative"
        ),
    )
    require(count == 414, f"directed negative count drift: {count}")
    return count


def render_tsv(fields: list[tuple[str, Any]]) -> str:
    lines = []
    for key, value in fields:
        if value is True:
            rendered = "true"
        elif value is False:
            rendered = "false"
        else:
            rendered = str(value)
        require("\t" not in key and "\n" not in key, "invalid TSV key")
        require(
            "\t" not in rendered and "\n" not in rendered,
            f"invalid TSV value: {key}",
        )
        lines.append(f"{key}\t{rendered}")
    return "\n".join(lines) + "\n"


def evaluate(root: Path) -> str:
    root = root.resolve()
    validate_source_ast(root / SOURCE_PATH)
    boundary, owned_name = load_source_module(root / SOURCE_PATH)
    try:
        contract, contract_raw = load_canonical(root / CONTRACT_PATH, "boundary contract")
        observation, observation_raw = load_canonical(
            root / OBSERVATION_PATH, "provider observation"
        )
        boundary.validate_contract(contract)
        validate_signature_and_terminal_closure(boundary, contract)
        boundary.validate_observation(observation)
        receipt = build_receipt(root, boundary, contract_raw, observation_raw)
        validate_schemas(root, boundary, receipt)
        manifest = validate_manifest(root, boundary)
        repeat = build_receipt(root, boundary, contract_raw, observation_raw)
        require(
            boundary.canonical_bytes(receipt) == boundary.canonical_bytes(repeat),
            "receipt is not deterministic",
        )
        forged = boundary.build_design_receipt(
            contract_raw,
            observation_raw,
            evaluated_at_utc="2026-07-15T15:00:01Z",
            boundary_source_sha256="1" * 64,
            observation_schema_sha256="2" * 64,
            receipt_schema_sha256="3" * 64,
            predecessor_guard_manifest_sha256="4" * 64,
            predecessor_s12_contract_sha256="5" * 64,
        )
        require(
            forged["on_disk_artifact_identity_verified"] is False,
            "caller digests overclaim on-disk identity",
        )
        negative_count = directed_negatives(
            boundary, contract, observation, receipt
        )
        require(
            manifest["decision"] == receipt["decision"],
            "manifest/receipt decision drift",
        )
        return render_tsv(
            [
                ("schema", RESULT_SCHEMA),
                ("status", receipt["status"]),
                ("decision", receipt["decision"]),
                ("baseline_commit", BASELINE_COMMIT),
                ("s12_integration_commit", S12_INTEGRATION_COMMIT),
                ("contract_sha256", receipt["contract_sha256"]),
                (
                    "boundary_source_sha256",
                    sha256_bytes((root / SOURCE_PATH).read_bytes()),
                ),
                (
                    "observation_schema_sha256",
                    sha256_bytes((root / OBSERVATION_SCHEMA_PATH).read_bytes()),
                ),
                (
                    "receipt_schema_sha256",
                    sha256_bytes((root / RECEIPT_SCHEMA_PATH).read_bytes()),
                ),
                (
                    "observation_sha256",
                    receipt["readiness_observation_sha256"],
                ),
                (
                    "predecessor_guard_manifest_sha256",
                    receipt["predecessor_guard_manifest_sha256"],
                ),
                (
                    "predecessor_s12_contract_sha256",
                    receipt["predecessor_s12_contract_sha256"],
                ),
                (
                    "authority_decision_payload_field_count",
                    len(boundary.AUTHORITY_DECISION_PAYLOAD_FIELDS),
                ),
                (
                    "authority_decision_kat_byte_count",
                    contract["authority_grain"][
                        "authority_decision_payload_contract"
                    ]["known_answer_test"]["payload_canonical_bytes"],
                ),
                (
                    "authority_decision_kat_sha256",
                    contract["authority_grain"][
                        "authority_decision_payload_contract"
                    ]["known_answer_test"]["payload_sha256"],
                ),
                (
                    "request_identity_binding_count",
                    len(boundary.REQUEST_IDENTITY_BINDINGS),
                ),
                ("result_binding_count", len(boundary.RESULT_BINDINGS)),
                (
                    "signature_receipt_field_count",
                    len(boundary.SIGNATURE_RECEIPT_FIELDS),
                ),
                (
                    "signature_domain_byte_count",
                    len(SIGNATURE_DOMAIN_TAG),
                ),
                (
                    "signature_message_byte_count",
                    len(
                        reference_signature_message(
                            contract["authority_grain"][
                                "signature_receipt_contract"
                            ]["message_derivation"]["known_answer_test"][
                                "authority_decision_sha256"
                            ]
                        )
                    ),
                ),
                (
                    "production_prerequisite_count",
                    len(boundary.PREREQUISITES),
                ),
                ("state_transition_count", len(boundary.TRANSITIONS)),
                (
                    "authority_persistent_state_count",
                    len(boundary.AUTHORITY_PERSISTENT_STATES),
                ),
                (
                    "physical_sink_persistent_state_count",
                    len(boundary.PHYSICAL_SINK_PERSISTENT_STATES),
                ),
                (
                    "physical_sink_terminal_fence_state_count",
                    len(boundary.PHYSICAL_SINK_FENCE_STATES),
                ),
                (
                    "terminal_authority_sink_vector_count",
                    len(boundary.TERMINAL_AUTHORITY_SINK_VECTORS),
                ),
                ("crash_cut_count", len(boundary.CRASH_CUTS)),
                ("invariant_count", len(boundary.INVARIANTS)),
                ("observed_at_utc", observation["observed_at_utc"]),
                ("prerequisites_verified", 0),
                (
                    "schema_and_internal_consistency_verified",
                    receipt["schema_and_internal_consistency_verified"],
                ),
                ("manifest_evidence_hashes_bound", True),
                ("production_execution_runtime_verified", False),
                (
                    "production_provider_bound_and_verified",
                    receipt["production_provider_bound_and_verified"],
                ),
                (
                    "owner_trust_pin_verified",
                    receipt["owner_trust_pin_verified"],
                ),
                (
                    "custodian_trust_pin_verified",
                    receipt["custodian_trust_pin_verified"],
                ),
                (
                    "external_linearizable_authorize_consume_logical_sink_reservation_verified",
                    receipt[
                        "external_linearizable_authorize_consume_logical_sink_reservation_verified"
                    ],
                ),
                (
                    "trusted_currentness_at_use_verified",
                    receipt["trusted_currentness_at_use_verified"],
                ),
                (
                    "anti_rollback_witness_verified",
                    receipt["anti_rollback_witness_verified"],
                ),
                (
                    "external_global_single_use_verified",
                    receipt["external_global_single_use_verified"],
                ),
                (
                    "private_single_use_capability_verified",
                    receipt["private_single_use_capability_verified"],
                ),
                (
                    "all_generator_paths_guarded_verified",
                    receipt["all_generator_paths_guarded_verified"],
                ),
                (
                    "guard_owned_sink_verified",
                    receipt["guard_owned_sink_verified"],
                ),
                (
                    "first_byte_cas_and_durability_verified",
                    receipt["first_byte_cas_and_durability_verified"],
                ),
                (
                    "loaded_runtime_attestation_verified",
                    receipt["loaded_runtime_attestation_verified"],
                ),
                (
                    "independent_fault_evidence_verified",
                    receipt["independent_fault_evidence_verified"],
                ),
                (
                    "crash_cut_operational_evidence_verified",
                    receipt["crash_cut_operational_evidence_verified"],
                ),
                (
                    "live_output_permit_defined",
                    receipt["live_output_permit_defined"],
                ),
                (
                    "live_output_capability_emitted",
                    receipt["live_output_capability_emitted"],
                ),
                (
                    "condition_output_authorized",
                    receipt["condition_output_authorized"],
                ),
                (
                    "receipt_is_output_permit",
                    receipt["receipt_is_output_permit"],
                ),
                ("external_organization_state_observed", False),
                ("host_visibility_complete", False),
                ("directed_structural_negative_tests", negative_count),
                ("source_profile", boundary.SOURCE_PROFILE),
                ("side_effects_unlocked", receipt["side_effects_unlocked"]),
                ("next_unit", NEXT_UNIT),
                ("test_oracle_scope", "STRUCTURAL_ONLY"),
                ("test_oracle", "STRUCTURAL_ORACLE_PASS"),
            ]
        )
    finally:
        sys.modules.pop(owned_name, None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="repeat the complete evaluation and require byte-identical output",
    )
    args = parser.parse_args()
    try:
        output = evaluate(args.root)
        if args.self_test:
            repeated = evaluate(args.root)
            require(output == repeated, "self-test repeat output drift")
    except (PackError, OSError) as exc:
        print(
            f"external atomic live-output boundary v1 pack: FAIL: {exc}",
            file=sys.stderr,
        )
        return 1
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
