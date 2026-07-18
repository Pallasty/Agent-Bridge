#!/usr/bin/env python3
"""Independent checker for the implementation-authority/resource decision pack."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Callable, Mapping


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MIN_JSON_INTEGER = -(2**63)
MAX_JSON_INTEGER = 2**63 - 1

SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "production_evidence_ingestion_implementation_authority_and_resource_binding_"
    "decision_v1.py"
)
DECISION_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_ingestion_implementation_authority_and_resource_"
    "binding_decision_v1_pack_owner_decision_v0.json"
)
EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_production_evidence_ingestion_implementation_authority_and_resource_"
    "binding_decision_v1_pack.expected.v0.tsv"
)

PREDECESSOR_REPORT_REL = (
    "docs/reports/goal-c-u/2026-07-17-biocortex-track-b-reference-provider-fault-"
    "injection-runner-runtime-prerequisite-evidence-packet-offline-integration-and-"
    "production-evidence-ingestion-boundary-review-v1-pack.md"
)
PREDECESSOR_GATE_REL = (
    "scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-"
    "runtime-prerequisite-evidence-packet-offline-integration-and-production-"
    "evidence-ingestion-boundary-review-v1-pack.sh"
)
PREDECESSOR_SOURCE_REL = (
    "scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1.py"
)
PREDECESSOR_CHECKER_REL = (
    "scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1_pack.py"
)
PREDECESSOR_EXPECTED_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1_pack.expected.v0.tsv"
)
PREDECESSOR_FIXTURE_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1_pack_synthetic_v0.json"
)
PREDECESSOR_MANIFEST_REL = (
    "scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_"
    "runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_"
    "evidence_ingestion_boundary_review_v1_pack_v0.json"
)

PREDECESSOR_RAW_SHA256 = {
    PREDECESSOR_REPORT_REL: "a91d98e79cc33d9752229fccdf818b9a8f8d9e0d0c427b431ac1dc00434544b3",
    PREDECESSOR_GATE_REL: "e2a3e5fd49ebd58697838bc3f7e1860ce511f225a4bdd11ac8f2772bd8087cf7",
    PREDECESSOR_SOURCE_REL: "a2fa9559b43413e1c729d58b89f1ec951c6722ab142f0a3be4f7c6cdd98d9530",
    PREDECESSOR_CHECKER_REL: "4fac8a588980811e12f4b324c31a9f42d70f683051555560924932c235eb1c45",
    PREDECESSOR_EXPECTED_REL: "70fbf15cc210fb365b5377642c49d91fa00a2a049affeeec595ef76dd1bf3234",
    PREDECESSOR_FIXTURE_REL: "3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6",
    PREDECESSOR_MANIFEST_REL: "59260f9d4d5e00924739f96de567695dfe326413a01fcb3600703d9efb945b54",
}

PREDECESSOR_EXPECTED_TSV = """schema\tagent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_offline_integration_and_production_evidence_ingestion_boundary_review_v1.receipt.v0
status\tREFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_OFFLINE_AGGREGATE_INTEGRATED_PRODUCTION_INGESTION_BOUNDARY_REVIEWED_RUNTIME_EVIDENCE_ZERO_NO_AUTHORITY
decision\tOFFLINE_AGGREGATE_CONFORMANT_PRODUCTION_EVIDENCE_INGESTION_BOUNDARY_FROZEN_RUNTIME_EVIDENCE_ZERO_FAIL_CLOSED
date\t2026-07-17
mode\tSYNTHETIC_FIXED_KAT_ONLY
next_unit\tREFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_PRODUCTION_EVIDENCE_INGESTION_IMPLEMENTATION_AUTHORITY_AND_RESOURCE_BINDING_DECISION
tracks_represented\t2
evidence_packet_count\t15
owner_packet_count\t1
aggregate_case_result_count\t16
offline_double_conformant_count\t16
freshness_arithmetic_conformant_count\t15
dependency_topology_conformant\ttrue
track_separation_conformant\ttrue
synthetic_packet_set_sha256\t56e9343e7e31e8a80d1a56f7ab34fc11e15412d97620c031a06f740ae29ea460
case_results_sha256\t8852dc9a04a828e7756f73e8f65c7c39ef72ed2c046f2a8c0b8cdd27e598df58
aggregate_request_id_sha256\t9a812f63f8b6fe4dd1b7a9e67e037b798e1da46e7be65377774e12d5ec6a2b45
predecessor_receipt_content_sha256\tc6ea1a4872acacf1faff3695598d66e1cb0096f6574239199128225dab80e3c4
boundary_fixture_sha256\t3aee2bc2f27290e9a57789d434f4373609b720f7ee1d963871fd99a613f55ff6
trust_domain_count\t5
production_ingestion_control_count\t14
production_ingestion_controls_implemented\t0
threat_case_count\t20
freshness_requirement_count\t8
owner_handoff_requirement_count\t10
valid_owner_state_reason_combination_count\t6
nonclaim_field_count\t52
nonclaims_sha256\t6123bcbfdba739acd61ea264c625b9f2545081701774a8c8b3b3a6f7b08f5b4a
all_nonclaims_explicit\ttrue
real_evidence_items_present\t0
production_validated_evidence_items\t0
runtime_evidence_accepted\t0
runtime_prerequisites_satisfied\t0
real_currentness_proved\tfalse
production_evidence_ingestion_implemented\tfalse
production_review_subject_set_sha256\tNONE
owner_handoff_set_sha256\tNONE
owner_handoff_eligible\tfalse
owner_identity_bound\tfalse
owner_decision_recorded\tfalse
positive_decision_representable\tfalse
runtime_admission_ready\tfalse
runtime_admission_granted\tfalse
runtime_authority\tfalse
downstream_separate_gate_count\t4
downstream_gates_authorized\t0
side_effects_unlocked\tNONE
content_sha256\t7d48eb96d1a87894698d396efba848f90da8076cc3271bd9ac8c5250b0c722fa
"""

RECORD_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "production_evidence_ingestion_implementation_authority_and_resource_binding_"
    "decision.v1"
)
RECEIPT_SCHEMA = (
    "agent_bridge.biocortex_ab_track_b_reference_provider_fault_injection_runner_"
    "production_evidence_ingestion_implementation_authority_and_resource_binding_"
    "decision_v1.receipt.v0"
)
DATE = "2026-07-17"
STATUS = (
    "REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_ISOLATED_LAB_FIRST_"
    "IMPLEMENTATION_AUTHORITY_AND_RESOURCE_SCOPE_RECORDED_ZERO_EXTERNAL_SPEND_"
    "NO_RUNTIME_OR_PROVIDER_AUTHORITY"
)
DECISION = (
    "AUTHORIZE_EXACT_BOUNDED_REVERSIBLE_ISOLATED_LAB_COMPONENT_"
    "IMPLEMENTATION_ONLY_FAIL_CLOSED"
)
NEXT_UNIT = (
    "REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_"
    "PRODUCTION_EVIDENCE_ENVELOPE_BOUNDED_FRAME_PARSER_AND_SYNTHETIC_MODE_"
    "SEPARATION_ISOLATED_LAB_IMPLEMENTATION"
)
MODE = "ISOLATED_LAB_FIRST"
CURRENT_STATE = "AUTHORIZED_ISOLATED_LAB_FIRST_EXACT_UNIT"
IMPLEMENTATION_SIDE_EFFECTS = (
    "REVERSIBLE_LOCAL_CODE_SCHEMA_TEST_DOCS_FOR_EXACT_NEXT_UNIT_ONLY"
)

DOMAIN_PREFIXES = {
    "boundary": "AB_TRACK_B_IMPLEMENTATION_AUTHORITY_BOUNDARY_V1",
    "decision_provenance": "AB_TRACK_B_IMPLEMENTATION_DECISION_PROVENANCE_V1",
    "decision_record": "AB_TRACK_B_IMPLEMENTATION_AUTHORITY_DECISION_RECORD_V1",
    "implementation_authority": "AB_TRACK_B_IMPLEMENTATION_AUTHORITY_SCOPE_V1",
    "nonclaims": "AB_TRACK_B_IMPLEMENTATION_AUTHORITY_NONCLAIMS_V1",
    "owner_implementation_actor": "AB_TRACK_B_OWNER_IMPLEMENTATION_ACTOR_V1",
    "receipt": "AB_TRACK_B_IMPLEMENTATION_AUTHORITY_DECISION_RECEIPT_V1",
    "resource_binding": "AB_TRACK_B_ISOLATED_LAB_RESOURCE_BINDING_V1",
    "rollback": "AB_TRACK_B_IMPLEMENTATION_AUTHORITY_ROLLBACK_V1",
    "state_machine": "AB_TRACK_B_IMPLEMENTATION_AUTHORITY_STATE_MACHINE_V1",
}

SECTION_TO_HASH_KEY = {
    "boundary": "boundary_sha256",
    "decision_provenance": "decision_provenance_sha256",
    "implementation_authority": "implementation_authority_sha256",
    "nonclaims": "nonclaims_sha256",
    "owner_implementation_actor": "owner_implementation_actor_sha256",
    "resource_binding": "resource_binding_sha256",
    "rollback": "rollback_sha256",
    "state_machine": "state_machine_sha256",
}
EXPECTED_SECTION_HASHES = {
    "boundary_sha256": "dbc94c68d8820197ca0df13e6f072d56c7ccffd2607d6a43d441f084989c556a",
    "decision_provenance_sha256": "58c132e4357ca31e618e88fd1bc28419e993e01e370bfeeac6a0572bd372b78e",
    "implementation_authority_sha256": "9add7e535c3a4370e9fb79597274f0cc565f9f6e6358f3c52a3329b0a57cfa3c",
    "nonclaims_sha256": "58164b47e696429385dc5db1fb16630f1499eba3bd214a762dd0865d532980ca",
    "owner_implementation_actor_sha256": "efae8f560404112f6f15f5000dc87b707701ea7732c999ef9c9efbbc6f49bf3e",
    "resource_binding_sha256": "e1f431d6ecbc3c4400b2832d28a0c734b5530c9dcd0d6f9cf64c3d55c8c22276",
    "rollback_sha256": "4f8b5dd436c6a3d3547dcd4c899b7870b7ecd87c16934a9e4bd72e1a32c8c47b",
    "state_machine_sha256": "7a8fed45182582088e68294407ff30b5b6ba37bb5393f0924b8ae06c936fac9e",
}
DECISION_RECORD_RAW_SHA256 = "69e2976c1298263240e384817df3a172686e80b8a7c57359829d9e50dda5e3c3"
DECISION_RECORD_CANONICAL_SHA256 = "f51d38d3fe795868b701602e92068e19cb22c43016b387cc49beaf959b080140"
DECISION_RECORD_DOMAIN_SHA256 = "eda3b8b6d1288d4b9ccaeeec1427be890bfcfecac0034788f451a1bfe4bed76a"
RECEIPT_CONTENT_SHA256 = "48f4eee93f565005ffa79a119529d58e5d61eb947754d4672c96541001268463"

TOP_LEVEL_KEYS = {
    "boundary", "date", "decision", "decision_provenance",
    "implementation_authority", "next_unit", "nonclaims",
    "owner_implementation_actor", "predecessor", "resource_binding", "rollback",
    "schema", "schema_version", "section_sha256", "state_machine", "status",
}
SECTION_KEYS = {
    "predecessor": {
        "gate_path", "gate_raw_sha256", "integration_commit", "integration_parents",
        "integration_tree", "manifest_path", "manifest_raw_sha256",
        "receipt_content_sha256", "source_commit", "source_parent",
    },
    "decision_provenance": {
        "budget_cap_source", "decision_time_utc", "directive_observed_in_owner_session",
        "directive_semantics", "explicit_credential_authority_observed",
        "explicit_endpoint_authority_observed",
        "explicit_production_runtime_authority_observed",
        "explicit_provider_authority_observed",
        "latest_directive_explicitly_named_budget_cap",
        "latest_directive_explicitly_named_owner_label",
        "no_runtime_or_provider_authority_inferred", "owner_label_source",
        "owner_supplied_numeric_budget_cap", "trusted_decision_timestamp_observed",
    },
    "owner_implementation_actor": {
        "binding_basis", "cryptographic_identity_verified", "delegated_runtime_authority",
        "runtime_owner_decision_recorded", "runtime_owner_identity_bound",
        "semantic_actor_binding_recorded", "semantic_actor_label", "semantic_actor_role",
        "signature_observed",
    },
    "implementation_authority": {
        "allowed_operations", "authority_class", "current_state", "default_off_required",
        "exact_next_unit_authorized", "forbidden_operations",
        "implementation_authority_recorded", "implementation_scope",
        "implementation_scope_decision_recorded", "mode", "non_transitive",
        "production_environment_implementation_authorized",
        "production_shaped_component_code_authorized", "runtime_import_authorized",
        "runtime_registration_authorized", "single_successor_intent",
        "single_use_enforced_by_external_ledger", "subdelegation_authorized",
    },
    "resource_binding": {
        "allowed_resource_classes", "component_limits", "component_runtime_network",
        "credential_handles", "credential_paths", "currency_scope", "custody_store_binding",
        "effective_external_paid_spend_cap", "implementation_resource_binding_recorded",
        "owner_supplied_numeric_budget_cap", "production_resource_authority_bound",
        "provider_endpoints", "real_evidence_input_authorized", "replay_ledger_binding",
        "resource_scope_id", "security_reviewer_binding", "test_data_scope",
        "trust_root_binding", "trusted_time_binding",
    },
    "state_machine": {
        "current_state", "global_single_use_proved", "initial_state",
        "positive_provider_authority_state_representable",
        "runtime_authority_state_representable", "states", "terminal_states",
        "transitions",
    },
    "rollback": {
        "local_worktree_delete_allowed", "production_kill_switch",
        "production_rollback_authority", "published_git_revert_plan_required",
        "remote_git_mutation_authority_derived", "reversible_only",
        "runtime_disable_action_required", "scope_invalidation_requires_new_decision",
        "unpublished_change_revert_allowed",
    },
    "boundary": {
        "downstream_gates_authorized", "exact_next_unit_authorized",
        "implementation_authority_recorded", "implementation_resource_binding_recorded",
        "implementation_scope_decision_recorded", "implementation_side_effects_unlocked",
        "owner_handoff_eligible", "production_environment_implementation_authorized",
        "production_ingestion_controls_implemented",
        "production_ingestion_controls_runtime_exercised", "production_ingestion_enabled",
        "production_ingestion_implemented", "production_shaped_component_code_authorized",
        "production_validated_evidence_items", "provider_authority",
        "real_evidence_items_present", "runtime_admission_granted",
        "runtime_admission_ready", "runtime_authority", "runtime_evidence_accepted",
        "runtime_owner_decision_recorded", "runtime_owner_identity_bound",
        "runtime_prerequisites_satisfied", "runtime_side_effects_unlocked",
    },
}

ALLOWED_OPERATIONS = (
    "ADD_CLOSED_WORLD_PRODUCTION_EVIDENCE_ENVELOPE_SCHEMA",
    "ADD_BOUNDED_DUPLICATE_SAFE_UTF8_JSON_FRAME_PARSER",
    "ADD_DETERMINISTIC_NONSECRET_ADVERSARIAL_KATS",
    "ADD_PURE_REVIEWER_INDEPENDENT_CHECKER_REPORT_AND_GATE",
    "ADD_SYNTHETIC_PRODUCTION_MODE_SEPARATION",
)
FORBIDDEN_OPERATIONS = (
    "ACCESS_CREDENTIAL_OR_SECRET_MATERIAL", "ACCEPT_OR_PERSIST_REAL_EVIDENCE",
    "AUTHORIZE_OR_INJECT_FAULT", "AUTHORIZE_OUTPUT_OR_CLAIM",
    "BIND_PRODUCTION_SIGNER_OR_TRUST_ROOT", "BIND_PROVIDER_OR_PRODUCTION_ENDPOINT",
    "CALL_PROVIDER_OR_ATTEMPT_WIRE", "CREATE_RUNTIME_OR_EXPERIMENT_ROW",
    "DEPLOY_OR_ENABLE_PRODUCTION_INGESTION",
    "ESTABLISH_DURABLE_CUSTODY_OR_REPLAY_LEDGER", "LAUNCH_RUNNER_OR_BACKGROUND_DAEMON",
    "PROVISION_PAID_OR_EXTERNAL_RESOURCE", "READ_AMBIENT_OR_DEFAULT_CREDENTIAL_CHAIN",
    "REPRESENT_RUNTIME_OWNER_DECISION", "SATISFY_RUNTIME_PREREQUISITE",
    "USE_AMBIENT_OR_PRODUCTION_TRUSTED_TIME",
)
NONCLAIM_KEYS = {
    "any_production_ingestion_control_implemented", "budget_cap_zero_is_budget_reservation",
    "condition_output_authorized", "credential_or_secret_material_accessed",
    "deployment_authorized", "durable_custody_proved", "durable_replay_cas_proved",
    "evidence_acceptance_authorized", "experiment_rows_created",
    "external_paid_spend_authorized", "fault_injected", "fault_injection_authorized",
    "git_publication_authority_derived", "global_single_use_proved",
    "independent_checker_is_security_approval", "output_permit_defined",
    "owner_signature_observed", "paid_resource_provisioned",
    "production_credentials_authorized", "production_endpoint_bound",
    "production_environment_implementation_authorized", "production_ingestion_enabled",
    "production_ingestion_implemented", "production_resource_authority_bound",
    "production_rollback_authority_bound", "production_security_approval",
    "production_signer_bound", "production_trust_root_bound", "provider_authority",
    "provider_called", "real_evidence_accepted", "real_evidence_authenticated",
    "real_evidence_collected", "real_evidence_ingested", "real_evidence_quarantined",
    "real_evidence_validated", "runner_launch_authorized", "runner_launched",
    "runtime_admission_granted", "runtime_admission_ready", "runtime_authority",
    "runtime_owner_decision_recorded", "runtime_owner_identity_bound",
    "runtime_rows_created", "scientific_claim_authorized",
    "semantic_owner_label_is_authenticated_identity", "trusted_production_time_bound",
    "wire_attempted",
}

STATES = (
    "UNRECORDED_NO_AUTHORITY", CURRENT_STATE, "REJECTED_FAIL_CLOSED",
    "CONSUMED_SCOPE_COMPLETE", "INVALIDATED_REQUIRES_NEW_DECISION",
)
TERMINAL_STATES = (
    "REJECTED_FAIL_CLOSED", "CONSUMED_SCOPE_COMPLETE",
    "INVALIDATED_REQUIRES_NEW_DECISION",
)
TRANSITIONS = (
    ("OWNER_CONTINUES_RECOMMENDED_PATH_WITH_FAIL_CLOSED_DEFAULTS",
     "UNRECORDED_NO_AUTHORITY", CURRENT_STATE),
    ("OWNER_HOLDS_OR_REJECTS", "UNRECORDED_NO_AUTHORITY", "REJECTED_FAIL_CLOSED"),
    ("EXACT_AUTHORIZED_SUCCESSOR_INTEGRATED", CURRENT_STATE, "CONSUMED_SCOPE_COMPLETE"),
    ("OWNER_REVOKES_OR_BASELINE_SCOPE_BUDGET_NETWORK_CREDENTIAL_ENDPOINT_DRIFTS",
     CURRENT_STATE, "INVALIDATED_REQUIRES_NEW_DECISION"),
)

TSV_FIELDS = (
    "schema", "status", "decision", "date", "mode", "next_unit", "current_state",
    "implementation_authority_recorded", "implementation_scope_decision_recorded",
    "implementation_resource_binding_recorded", "production_shaped_component_code_authorized",
    "production_environment_implementation_authorized", "owner_semantic_actor_label",
    "owner_semantic_actor_binding_recorded", "owner_cryptographic_identity_verified",
    "owner_signature_observed", "owner_supplied_numeric_budget_cap",
    "external_paid_spend_cap", "allowed_operation_count", "forbidden_operation_count",
    "provider_endpoint_count", "credential_handle_count", "credential_path_count",
    "component_runtime_network", "state_count", "transition_count",
    "global_single_use_proved", "production_ingestion_implemented",
    "production_ingestion_enabled", "production_ingestion_controls_implemented",
    "production_ingestion_controls_runtime_exercised", "real_evidence_items_present",
    "production_validated_evidence_items", "runtime_evidence_accepted",
    "runtime_prerequisites_satisfied", "runtime_owner_identity_bound",
    "runtime_owner_decision_recorded", "runtime_admission_ready",
    "runtime_admission_granted", "runtime_authority", "provider_authority",
    "downstream_gates_authorized", "runtime_side_effects_unlocked",
    "implementation_side_effects_unlocked", "nonclaim_field_count",
    "all_nonclaims_explicit", "owner_implementation_actor_sha256",
    "implementation_authority_sha256", "resource_binding_sha256",
    "state_machine_sha256", "rollback_sha256", "boundary_sha256", "nonclaims_sha256",
    "decision_record_sha256", "predecessor_receipt_content_sha256", "content_sha256",
)


class CheckError(ValueError):
    """Independent fail-closed checker error."""


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CheckError(f"{code}: {message}")


def exact_keys(value: Mapping[str, Any], expected: set[str], code: str) -> None:
    require(type(value) is dict and set(value) == expected, code, "closed-world key set drift")


def canonical_bytes(value: Any) -> bytes:
    validate_json_value(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def validate_json_value(value: Any, depth: int = 0) -> None:
    require(depth <= 64, "E_JSON_DEPTH", "value nesting exceeds 64")
    require(type(value) is not float, "E_JSON_FLOAT", "floats are forbidden")
    if type(value) is int:
        require(MIN_JSON_INTEGER <= value <= MAX_JSON_INTEGER,
                "E_JSON_INTEGER_OVERFLOW", "integer out of range")
        return
    if type(value) in (str, bool) or value is None:
        return
    if type(value) is list:
        for item in value:
            validate_json_value(item, depth + 1)
        return
    require(type(value) is dict, "E_JSON_TYPE", "unsupported JSON value type")
    for key, item in value.items():
        require(type(key) is str, "E_JSON_KEY", "object key is not a string")
        validate_json_value(item, depth + 1)


def domain_sha256(domain: str, value: Any) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical_bytes(value)).hexdigest()


def without_key(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    require(key in result, "E_HASH_FIELD", key)
    del result[key]
    return result


def is_sha256(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def safe_path(relative: str) -> Path:
    parsed = PurePosixPath(relative)
    require(not parsed.is_absolute() and ".." not in parsed.parts and str(parsed) == relative,
            "E_PATH", relative)
    cursor = ROOT
    for component in parsed.parts:
        cursor = cursor / component
        require(not cursor.is_symlink(), "E_PATH_SYMLINK", relative)
    require(cursor.is_file() and not cursor.is_symlink(), "E_FILE", relative)
    resolved = cursor.resolve()
    require(ROOT == resolved or ROOT in resolved.parents, "E_PATH_ESCAPE", relative)
    return cursor


def read_bytes(relative: str) -> bytes:
    raw = safe_path(relative).read_bytes()
    require(len(raw) <= MAX_DOCUMENT_BYTES, "E_SIZE", relative)
    return raw


def read_text(relative: str) -> str:
    try:
        return read_bytes(relative).decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {relative}") from error


def raw_sha256(relative: str) -> str:
    return hashlib.sha256(read_bytes(relative)).hexdigest()


def _duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "E_DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def _bounded_integer(token: str) -> int:
    value = int(token, 10)
    require(MIN_JSON_INTEGER <= value <= MAX_JSON_INTEGER,
            "E_JSON_INTEGER_OVERFLOW", token)
    return value


def _reject_float(token: str) -> float:
    raise CheckError(f"E_JSON_FLOAT: {token}")


def _reject_constant(token: str) -> None:
    raise CheckError(f"E_JSON_NONFINITE: {token}")


def parse_json_bytes(raw: bytes, label: str) -> dict[str, Any]:
    require(not raw.startswith(b"\xef\xbb\xbf"), "E_JSON_BOM", label)
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_safe_object,
            parse_int=_bounded_integer,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as error:
        raise CheckError(f"E_UTF8: {label}") from error
    require(type(value) is dict, "E_JSON_ROOT", label)
    return value


def read_json(relative: str) -> dict[str, Any]:
    return parse_json_bytes(read_bytes(relative), relative)


def check_decoder_guards() -> int:
    probes = (
        b'{"a":1,"a":2}',
        b'{"value":NaN}',
        b'{"value":Infinity}',
        b'{"value":-Infinity}',
        b'{"value":9223372036854775808}',
        b'{"value":-9223372036854775809}',
        b'{"value":1.25}',
    )
    for index, raw in enumerate(probes):
        try:
            parse_json_bytes(raw, f"guard-{index}")
        except CheckError:
            continue
        raise CheckError(f"E_JSON_GUARD_PROBE: {index}")
    return len(probes)


def load_module(relative: str, name: str) -> ModuleType:
    path = safe_path(relative).resolve()
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "E_MODULE_LOAD", name)
    require(spec.origin is not None and Path(spec.origin).resolve() == path,
            "E_MODULE_ORIGIN", name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == path, "E_MODULE_PATH", name)
    return module


def verify_predecessor_artifacts() -> None:
    for relative, expected in PREDECESSOR_RAW_SHA256.items():
        require(raw_sha256(relative) == expected, "E_PREDECESSOR_RAW_HASH", relative)
    require(read_text(PREDECESSOR_EXPECTED_REL) == PREDECESSOR_EXPECTED_TSV,
            "E_PREDECESSOR_RECEIPT", "exact frozen receipt bytes")


def exact_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            exact_equal(left[key], right[key]) for key in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            exact_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return bool(left == right)


def check_source_ast_text(text: str) -> None:
    tree = ast.parse(text, filename=SOURCE_REL)
    allowed_imports = {"__future__", "hashlib", "json", "typing"}
    forbidden_calls = {"__import__", "compile", "eval", "exec", "input", "open"}
    forbidden_attributes = {
        "chdir", "connect", "environ", "fork", "getenv", "import_module", "listdir",
        "makedirs", "mkdir", "now", "open", "Popen", "putenv", "randbytes",
        "read", "read_bytes", "read_text", "recv", "remove", "rename", "replace",
        "request", "rmdir", "run", "send", "sleep", "socket", "spawn", "system",
        "time", "today", "token_bytes", "token_hex", "unlink", "urandom", "urlopen",
        "utcnow", "walk", "write", "write_bytes", "write_text",
    }
    public_functions: set[str] = set()
    classes: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".", 1)[0] in allowed_imports,
                        "E_AST_IMPORT", alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            require(node.level == 0 and module_name.split(".", 1)[0] in allowed_imports,
                    "E_AST_IMPORT", module_name)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                require(node.func.id not in forbidden_calls, "E_AST_CALL", node.func.id)
            elif isinstance(node.func, ast.Attribute):
                require(node.func.attr not in forbidden_attributes,
                        "E_AST_CALL", node.func.attr)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise CheckError("E_AST_MUTABLE_SCOPE: global/nonlocal")
        elif isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)):
            raise CheckError("E_AST_ASYNC_OR_GENERATOR: asynchronous/generator surface")
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            public_functions.add(node.name)
            lowered = node.name.lower()
            for forbidden_word in (
                "accept", "activate", "credential", "deploy", "endpoint", "ingest",
                "provider", "runtime", "secret", "socket", "wire",
            ):
                require(forbidden_word not in lowered,
                        "E_AST_PUBLIC_AUTHORITY_API", node.name)
        elif isinstance(node, ast.ClassDef):
            bases = [base.id for base in node.bases if isinstance(base, ast.Name)]
            classes.append((node.name, bases))
    require(public_functions == {
        "canonical_bytes", "domain_sha256", "exact_equal", "exact_keys", "is_sha256",
        "render_tsv", "require", "review_decision",
    }, "E_AST_PUBLIC_FUNCTIONS", str(sorted(public_functions)))
    require(classes == [("ImplementationAuthorityDecisionReviewError", ["ValueError"])],
            "E_AST_CLASSES", str(classes))


def check_successor_source_purity() -> None:
    check_source_ast_text(read_text(SOURCE_REL))


def expected_section_hashes(record: Mapping[str, Any]) -> dict[str, str]:
    return {
        hash_key: domain_sha256(DOMAIN_PREFIXES[section], record[section])
        for section, hash_key in SECTION_TO_HASH_KEY.items()
    }


def validate_record(record: dict[str, Any], *, enforce_frozen_hashes: bool = True) -> None:
    validate_json_value(record)
    exact_keys(record, TOP_LEVEL_KEYS, "E_RECORD_KEYS")
    require(type(record["schema_version"]) is int and record["schema_version"] == 1,
            "E_RECORD_VERSION", "exact integer one")
    for field, expected in (
        ("schema", RECORD_SCHEMA), ("date", DATE), ("status", STATUS),
        ("decision", DECISION), ("next_unit", NEXT_UNIT),
    ):
        require(type(record[field]) is str and record[field] == expected,
                "E_RECORD_VALUE", field)
    for section, keys in SECTION_KEYS.items():
        exact_keys(record[section], keys, f"E_{section.upper()}_KEYS")
    exact_keys(record["nonclaims"], NONCLAIM_KEYS, "E_NONCLAIM_KEYS")
    exact_keys(record["section_sha256"], set(EXPECTED_SECTION_HASHES),
               "E_SECTION_HASH_KEYS")

    predecessor = record["predecessor"]
    require(exact_equal(predecessor, {
        "gate_path": PREDECESSOR_GATE_REL,
        "gate_raw_sha256": PREDECESSOR_RAW_SHA256[PREDECESSOR_GATE_REL],
        "integration_commit": "d5bbe55d5d95b1163e287415f437cf77c594135d",
        "integration_parents": [
            "3d03193b645ded944b10a310633be8d6a2c1ab1b",
            "0268990ee74a6a958269d1c07f7d575d0284e6bf",
        ],
        "integration_tree": "6fd22d3e8abba06ae5eab26c9c9ce2af5672ada9",
        "manifest_path": PREDECESSOR_MANIFEST_REL,
        "manifest_raw_sha256": PREDECESSOR_RAW_SHA256[PREDECESSOR_MANIFEST_REL],
        "receipt_content_sha256": "7d48eb96d1a87894698d396efba848f90da8076cc3271bd9ac8c5250b0c722fa",
        "source_commit": "0268990ee74a6a958269d1c07f7d575d0284e6bf",
        "source_parent": "3d03193b645ded944b10a310633be8d6a2c1ab1b",
    }), "E_PREDECESSOR_BINDING", "exact predecessor lineage and receipt")

    provenance = record["decision_provenance"]
    require(exact_equal(provenance, {
        "budget_cap_source": "FAIL_CLOSED_ZERO_DEFAULT_UNDER_REVERSIBLE_AUTONOMY",
        "decision_time_utc": "NONE",
        "directive_observed_in_owner_session": True,
        "directive_semantics": "CONTINUE_RECOMMENDED_ISOLATED_LAB_FIRST_PATH",
        "explicit_credential_authority_observed": False,
        "explicit_endpoint_authority_observed": False,
        "explicit_production_runtime_authority_observed": False,
        "explicit_provider_authority_observed": False,
        "latest_directive_explicitly_named_budget_cap": False,
        "latest_directive_explicitly_named_owner_label": False,
        "no_runtime_or_provider_authority_inferred": True,
        "owner_label_source": "ESTABLISHED_PROJECT_OWNER_PROFILE",
        "owner_supplied_numeric_budget_cap": False,
        "trusted_decision_timestamp_observed": False,
    }), "E_GROUNDING_PROVENANCE", "directive grounding matrix")

    owner = record["owner_implementation_actor"]
    require(exact_equal(owner, {
        "binding_basis": "ESTABLISHED_PROFILE_PLUS_CURRENT_SESSION_CONTINUITY",
        "cryptographic_identity_verified": False,
        "delegated_runtime_authority": False,
        "runtime_owner_decision_recorded": False,
        "runtime_owner_identity_bound": False,
        "semantic_actor_binding_recorded": True,
        "semantic_actor_label": "pallasting",
        "semantic_actor_role": "PROJECT_OWNER",
        "signature_observed": False,
    }), "E_GROUNDING_OWNER", "semantic actor is not authenticated runtime owner")

    authority = record["implementation_authority"]
    require(authority["allowed_operations"] == list(ALLOWED_OPERATIONS),
            "E_ALLOWED_OPERATIONS", "exact ordered operation allowlist")
    require(authority["forbidden_operations"] == list(FORBIDDEN_OPERATIONS),
            "E_FORBIDDEN_OPERATIONS", "exact ordered operation denylist")
    expected_authority_scalars = {
        "authority_class": "REVERSIBLE_CODE_SCHEMA_TEST_DOCUMENTATION_ONLY",
        "current_state": CURRENT_STATE,
        "default_off_required": True,
        "exact_next_unit_authorized": True,
        "implementation_authority_recorded": True,
        "implementation_scope": "ISOLATED_LAB_CODE_ONLY_EXACT_NEXT_UNIT_SINGLE_USE_NON_TRANSITIVE",
        "implementation_scope_decision_recorded": True,
        "mode": MODE,
        "non_transitive": True,
        "production_environment_implementation_authorized": False,
        "production_shaped_component_code_authorized": True,
        "runtime_import_authorized": False,
        "runtime_registration_authorized": False,
        "single_successor_intent": True,
        "single_use_enforced_by_external_ledger": False,
        "subdelegation_authorized": False,
    }
    for field, expected in expected_authority_scalars.items():
        require(exact_equal(authority[field], expected), "E_AUTHORITY_SCOPE", field)

    resources = record["resource_binding"]
    require(exact_equal(resources, {
        "allowed_resource_classes": [
            "EXISTING_LOCAL_CPU_AND_MEMORY", "ISOLATED_AGENT_BRIDGE_WORKTREE",
            "PRIVATE_LOCAL_TEST_SCRATCH",
        ],
        "component_limits": {
            "max_array_items": 64, "max_input_frame_bytes": 1048576,
            "max_json_depth": 32, "max_object_members": 256,
            "max_parallel_workers": 1, "max_private_scratch_bytes": 67108864,
        },
        "component_runtime_network": False,
        "credential_handles": [],
        "credential_paths": [],
        "currency_scope": "ALL_CURRENCIES_ZERO_ONLY",
        "custody_store_binding": "NONE",
        "effective_external_paid_spend_cap": 0,
        "implementation_resource_binding_recorded": True,
        "owner_supplied_numeric_budget_cap": False,
        "production_resource_authority_bound": False,
        "provider_endpoints": [],
        "real_evidence_input_authorized": False,
        "replay_ledger_binding": "NONE",
        "resource_scope_id": "EXISTING_LOCAL_WORKTREE_PRIVATE_SCRATCH_AND_LOCAL_COMPUTE_ONLY",
        "security_reviewer_binding": "NONE_INDEPENDENT_CHECKER_IS_NOT_SECURITY_REVIEW",
        "test_data_scope": "COMMITTED_NONSECRET_FIXTURES_ONLY",
        "trust_root_binding": "NONE",
        "trusted_time_binding": "FIXED_KAT_ONLY_NOT_TRUSTED_TIME",
    }), "E_GROUNDING_RESOURCES", "exact zero-spend offline resource closure")

    machine = record["state_machine"]
    require(machine["states"] == list(STATES)
            and machine["terminal_states"] == list(TERMINAL_STATES),
            "E_STATE_VOCABULARY", "exact closed-world state order")
    observed_transitions = [
        (row.get("event"), row.get("from_state"), row.get("to_state"))
        if type(row) is dict and set(row) == {"event", "from_state", "to_state"}
        else None
        for row in machine["transitions"]
    ]
    require(observed_transitions == list(TRANSITIONS),
            "E_STATE_TRANSITIONS", "exact transition graph")
    require(machine["initial_state"] == "UNRECORDED_NO_AUTHORITY"
            and machine["current_state"] == CURRENT_STATE
            and machine["global_single_use_proved"] is False
            and machine["runtime_authority_state_representable"] is False
            and machine["positive_provider_authority_state_representable"] is False,
            "E_STATE_CEILING", "no runtime/provider positive authority state")

    rollback = record["rollback"]
    require(exact_equal(rollback, {
        "local_worktree_delete_allowed": True,
        "production_kill_switch": "NOT_APPLICABLE_NOT_ENABLED",
        "production_rollback_authority": False,
        "published_git_revert_plan_required": True,
        "remote_git_mutation_authority_derived": False,
        "reversible_only": True,
        "runtime_disable_action_required": False,
        "scope_invalidation_requires_new_decision": True,
        "unpublished_change_revert_allowed": True,
    }), "E_ROLLBACK", "local Git-only rollback closure")

    boundary = record["boundary"]
    expected_positive_boundary = {
        "exact_next_unit_authorized", "implementation_authority_recorded",
        "implementation_resource_binding_recorded", "implementation_scope_decision_recorded",
        "production_shaped_component_code_authorized",
    }
    expected_zero_boundary = {
        "downstream_gates_authorized", "production_ingestion_controls_implemented",
        "production_ingestion_controls_runtime_exercised", "production_validated_evidence_items",
        "real_evidence_items_present", "runtime_evidence_accepted",
        "runtime_prerequisites_satisfied",
    }
    expected_false_boundary = set(SECTION_KEYS["boundary"]) - expected_positive_boundary \
        - expected_zero_boundary - {
            "implementation_side_effects_unlocked", "runtime_side_effects_unlocked",
        }
    for field in expected_positive_boundary:
        require(boundary[field] is True, "E_BOUNDARY_POSITIVE", field)
    for field in expected_zero_boundary:
        require(type(boundary[field]) is int and boundary[field] == 0,
                "E_BOUNDARY_ZERO", field)
    for field in expected_false_boundary:
        require(boundary[field] is False, "E_BOUNDARY_FALSE", field)
    require(boundary["implementation_side_effects_unlocked"] == IMPLEMENTATION_SIDE_EFFECTS
            and boundary["runtime_side_effects_unlocked"] == "NONE",
            "E_BOUNDARY_SIDE_EFFECTS", "implementation/runtime plane separation")

    require(len(record["nonclaims"]) == 48
            and all(value is False for value in record["nonclaims"].values()),
            "E_NONCLAIMS", "all exact nonclaims must remain false")

    derived_hashes = expected_section_hashes(record)
    require(exact_equal(record["section_sha256"], derived_hashes),
            "E_SECTION_HASH", "domain-separated section hash drift")
    require(all(is_sha256(value) for value in derived_hashes.values()),
            "E_SECTION_HASH_FORMAT", "lowercase SHA-256 required")
    if enforce_frozen_hashes:
        require(exact_equal(derived_hashes, EXPECTED_SECTION_HASHES),
                "E_SECTION_FROZEN_HASH", "frozen decision section drift")
        require(hashlib.sha256(canonical_bytes(record)).hexdigest()
                == DECISION_RECORD_CANONICAL_SHA256,
                "E_RECORD_CANONICAL_HASH", "canonical decision hash drift")
        require(domain_sha256(DOMAIN_PREFIXES["decision_record"], record)
                == DECISION_RECORD_DOMAIN_SHA256,
                "E_RECORD_DOMAIN_HASH", "decision domain hash drift")


def expected_receipt(record: Mapping[str, Any]) -> dict[str, Any]:
    hashes = expected_section_hashes(record)
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "status": STATUS,
        "decision": DECISION,
        "date": DATE,
        "mode": MODE,
        "next_unit": NEXT_UNIT,
        "current_state": CURRENT_STATE,
        "implementation_authority_recorded": True,
        "implementation_scope_decision_recorded": True,
        "implementation_resource_binding_recorded": True,
        "production_shaped_component_code_authorized": True,
        "production_environment_implementation_authorized": False,
        "owner_semantic_actor_label": "pallasting",
        "owner_semantic_actor_binding_recorded": True,
        "owner_cryptographic_identity_verified": False,
        "owner_signature_observed": False,
        "owner_supplied_numeric_budget_cap": False,
        "external_paid_spend_cap": 0,
        "allowed_operation_count": 5,
        "forbidden_operation_count": 16,
        "provider_endpoint_count": 0,
        "credential_handle_count": 0,
        "credential_path_count": 0,
        "component_runtime_network": False,
        "state_count": 5,
        "transition_count": 4,
        "global_single_use_proved": False,
        "production_ingestion_implemented": False,
        "production_ingestion_enabled": False,
        "production_ingestion_controls_implemented": 0,
        "production_ingestion_controls_runtime_exercised": 0,
        "real_evidence_items_present": 0,
        "production_validated_evidence_items": 0,
        "runtime_evidence_accepted": 0,
        "runtime_prerequisites_satisfied": 0,
        "runtime_owner_identity_bound": False,
        "runtime_owner_decision_recorded": False,
        "runtime_admission_ready": False,
        "runtime_admission_granted": False,
        "runtime_authority": False,
        "provider_authority": False,
        "downstream_gates_authorized": 0,
        "runtime_side_effects_unlocked": "NONE",
        "implementation_side_effects_unlocked": IMPLEMENTATION_SIDE_EFFECTS,
        "nonclaim_field_count": 48,
        "all_nonclaims_explicit": True,
        "owner_implementation_actor_sha256": hashes["owner_implementation_actor_sha256"],
        "implementation_authority_sha256": hashes["implementation_authority_sha256"],
        "resource_binding_sha256": hashes["resource_binding_sha256"],
        "state_machine_sha256": hashes["state_machine_sha256"],
        "rollback_sha256": hashes["rollback_sha256"],
        "boundary_sha256": hashes["boundary_sha256"],
        "nonclaims_sha256": hashes["nonclaims_sha256"],
        "decision_record_sha256": domain_sha256(DOMAIN_PREFIXES["decision_record"], record),
        "predecessor_receipt_content_sha256": (
            "7d48eb96d1a87894698d396efba848f90da8076cc3271bd9ac8c5250b0c722fa"
        ),
    }
    receipt["content_sha256"] = domain_sha256(DOMAIN_PREFIXES["receipt"], receipt)
    return receipt


def independent_render_tsv(receipt: Mapping[str, Any]) -> str:
    exact_keys(receipt, set(TSV_FIELDS), "E_RECEIPT_KEYS")
    lines: list[str] = []
    for field in TSV_FIELDS:
        value = receipt[field]
        require(type(value) in (str, int, bool), "E_TSV_SCALAR", field)
        rendered = "true" if value is True else "false" if value is False else str(value)
        require("\t" not in rendered and "\n" not in rendered,
                "E_TSV_INJECTION", field)
        lines.append(f"{field}\t{rendered}")
    return "\n".join(lines) + "\n"


def validate_receipt(receipt: dict[str, Any], record: Mapping[str, Any],
                     module: ModuleType) -> str:
    expected = expected_receipt(record)
    require(exact_equal(receipt, expected), "E_RECEIPT", "exact scalar receipt drift")
    require(receipt["decision_record_sha256"] == DECISION_RECORD_DOMAIN_SHA256,
            "E_RECEIPT_RECORD_HASH", "decision record binding")
    require(receipt["content_sha256"] == RECEIPT_CONTENT_SHA256,
            "E_RECEIPT_CONTENT_HASH", "frozen receipt content")
    require(tuple(module.TSV_FIELDS) == TSV_FIELDS, "E_TSV_FIELDS", "field order drift")
    rendered = independent_render_tsv(receipt)
    require(module.render_tsv(copy.deepcopy(receipt)) == rendered,
            "E_TSV_MODULE", "module render differs")
    require(rendered == read_text(EXPECTED_REL), "E_TSV_EXPECTED", "frozen TSV drift")
    return rendered


def expect_rejected(action: Callable[[], Any], label: str) -> None:
    try:
        action()
    except (CheckError, ValueError, TypeError, KeyError, SyntaxError):
        return
    raise CheckError(f"E_MUTATION_ACCEPTED: {label}")


def mutate_scalar(value: Any) -> Any:
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return "0" * 64 if is_sha256(value) else value + "_MUTATED"
    if value is None:
        return 0
    if type(value) is list:
        return list(reversed(value)) if len(value) > 1 else value + ["MUTATED"]
    if type(value) is dict:
        result = copy.deepcopy(value)
        result["extra"] = False
        return result
    raise CheckError("E_MUTATOR_TYPE: unsupported")


def mutate_path(record: Mapping[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(record))
    cursor: Any = candidate
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = mutate_scalar(cursor[path[-1]])
    return candidate


def rehash_record(record: dict[str, Any]) -> None:
    record["section_sha256"] = expected_section_hashes(record)


def expect_record_rejected_by_both(candidate: dict[str, Any], module: ModuleType,
                                   label: str) -> None:
    expect_rejected(lambda: validate_record(copy.deepcopy(candidate),
                                             enforce_frozen_hashes=False),
                    label + "-independent")
    expect_rejected(lambda: module.review_decision(copy.deepcopy(candidate)),
                    label + "-module")


def grounding_matrix_paths() -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for section in (
        "decision_provenance", "owner_implementation_actor",
        "implementation_authority", "resource_binding",
    ):
        paths.extend((section, key) for key in sorted(SECTION_KEYS[section]))
    return tuple(paths)


def run_self_test(module: ModuleType, record: dict[str, Any],
                  receipt: dict[str, Any]) -> dict[str, int]:
    counts = {
        "json_guard_negatives": check_decoder_guards(),
        "source_ast_negatives": 0,
        "closed_world_negatives": 0,
        "grounding_matrix_negatives": 0,
        "overclaim_negatives": 0,
        "section_hash_negatives": 0,
        "receipt_negatives": 0,
    }

    ast_snippets = (
        "\nimport os\n",
        "\nimport socket\n",
        "\nfrom pathlib import Path\n",
        "\ndef accept_real_evidence():\n    pass\n",
        "\ndef runtime_activation():\n    pass\n",
        "\ndef _probe_open():\n    return open('x')\n",
        "\ndef _probe_import():\n    return __import__('os')\n",
        "\ndef _probe_global():\n    global _MUTABLE\n",
        "\nasync def _probe_async():\n    pass\n",
        "\ndef _probe_read():\n    return candidate.read_text()\n",
    )
    source_text = read_text(SOURCE_REL)
    for index, snippet in enumerate(ast_snippets):
        expect_rejected(lambda snippet=snippet: check_source_ast_text(source_text + snippet),
                        f"source-ast-{index}")
        counts["source_ast_negatives"] += 1

    for key in sorted(TOP_LEVEL_KEYS):
        candidate = copy.deepcopy(record)
        del candidate[key]
        expect_record_rejected_by_both(candidate, module, f"record-drop-{key}")
        counts["closed_world_negatives"] += 1
    candidate = copy.deepcopy(record)
    candidate["extra"] = False
    expect_record_rejected_by_both(candidate, module, "record-extra")
    counts["closed_world_negatives"] += 1
    object_sections = (
        "predecessor", "decision_provenance", "owner_implementation_actor",
        "implementation_authority", "resource_binding", "state_machine", "rollback",
        "boundary", "nonclaims", "section_sha256",
    )
    for section in object_sections:
        candidate = copy.deepcopy(record)
        candidate[section]["extra"] = False
        expect_record_rejected_by_both(candidate, module, f"section-extra-{section}")
        counts["closed_world_negatives"] += 1
        candidate = copy.deepcopy(record)
        first_key = sorted(candidate[section])[0]
        del candidate[section][first_key]
        expect_record_rejected_by_both(candidate, module,
                                       f"section-drop-{section}-{first_key}")
        counts["closed_world_negatives"] += 1

    for path in grounding_matrix_paths():
        candidate = mutate_path(record, path)
        rehash_record(candidate)
        expect_record_rejected_by_both(candidate, module,
                                       "grounding-" + "-".join(path))
        counts["grounding_matrix_negatives"] += 1

    overclaim_paths: list[tuple[str, ...]] = [
        ("nonclaims", key) for key in sorted(NONCLAIM_KEYS)
    ]
    overclaim_paths.extend(
        ("boundary", key)
        for key, value in sorted(record["boundary"].items())
        if value is False or (type(value) is int and value == 0)
    )
    overclaim_paths.extend(
        ("decision_provenance", key)
        for key, value in sorted(record["decision_provenance"].items())
        if value is False
    )
    overclaim_paths.extend(
        ("owner_implementation_actor", key)
        for key, value in sorted(record["owner_implementation_actor"].items())
        if value is False
    )
    overclaim_paths.extend(("resource_binding", key) for key in (
        "component_runtime_network", "credential_handles", "credential_paths",
        "custody_store_binding", "effective_external_paid_spend_cap",
        "owner_supplied_numeric_budget_cap", "production_resource_authority_bound",
        "provider_endpoints", "real_evidence_input_authorized", "replay_ledger_binding",
        "security_reviewer_binding", "trust_root_binding",
    ))
    overclaim_paths.extend(("implementation_authority", key) for key in (
        "production_environment_implementation_authorized", "runtime_import_authorized",
        "runtime_registration_authorized", "single_use_enforced_by_external_ledger",
        "subdelegation_authorized",
    ))
    overclaim_paths.extend(("state_machine", key) for key in (
        "global_single_use_proved", "positive_provider_authority_state_representable",
        "runtime_authority_state_representable",
    ))
    overclaim_paths.extend(("rollback", key) for key in (
        "production_rollback_authority", "remote_git_mutation_authority_derived",
        "runtime_disable_action_required",
    ))
    require(len(overclaim_paths) == len(set(overclaim_paths)),
            "E_OVERCLAIM_PATHS", "duplicate directed path")
    for path in overclaim_paths:
        candidate = mutate_path(record, path)
        rehash_record(candidate)
        expect_record_rejected_by_both(candidate, module,
                                       "overclaim-" + "-".join(path))
        counts["overclaim_negatives"] += 1

    for hash_key in sorted(EXPECTED_SECTION_HASHES):
        candidate = copy.deepcopy(record)
        candidate["section_sha256"][hash_key] = "0" * 64
        expect_record_rejected_by_both(candidate, module,
                                       f"section-hash-{hash_key}")
        counts["section_hash_negatives"] += 1

    for field in TSV_FIELDS:
        candidate_receipt = copy.deepcopy(receipt)
        candidate_receipt[field] = mutate_scalar(candidate_receipt[field])
        if field != "content_sha256":
            unsigned = copy.deepcopy(candidate_receipt)
            del unsigned["content_sha256"]
            candidate_receipt["content_sha256"] = domain_sha256(
                DOMAIN_PREFIXES["receipt"], unsigned
            )
        expect_rejected(lambda candidate=candidate_receipt: validate_receipt(
            candidate, record, module), f"receipt-{field}")
        counts["receipt_negatives"] += 1

    counts["directed_negative_tests"] = sum(
        value for key, value in counts.items() if key.endswith("_negatives")
    )
    return counts


def evaluate(self_test: bool) -> str:
    check_decoder_guards()
    verify_predecessor_artifacts()
    check_successor_source_purity()
    require(raw_sha256(DECISION_REL) == DECISION_RECORD_RAW_SHA256,
            "E_RECORD_RAW_HASH", "decision record raw bytes")
    record = read_json(DECISION_REL)
    validate_record(record)
    module = load_module(SOURCE_REL, Path(SOURCE_REL).stem)
    require(hasattr(module, "ImplementationAuthorityDecisionReviewError")
            and issubclass(module.ImplementationAuthorityDecisionReviewError, ValueError),
            "E_MODULE_ERROR", "stable review error")
    receipt = module.review_decision(copy.deepcopy(record))
    require(type(receipt) is dict, "E_MODULE_RECEIPT", "not an object")
    rendered = validate_receipt(receipt, record, module)
    if not self_test:
        return rendered
    counts = run_self_test(module, record, receipt)
    expected_counts = {
        "json_guard_negatives": 7,
        "source_ast_negatives": 10,
        "closed_world_negatives": 37,
        "grounding_matrix_negatives": 60,
        "overclaim_negatives": 101,
        "section_hash_negatives": 8,
        "receipt_negatives": 56,
        "directed_negative_tests": 279,
    }
    require(counts == expected_counts, "E_SELF_TEST_COUNTS", str(counts))
    return (
        "self_test\tPASS\n"
        f"directed_negative_tests\t{counts['directed_negative_tests']}\n"
        f"json_guard_negative_tests\t{counts['json_guard_negatives']}\n"
        f"closed_world_negative_tests\t{counts['closed_world_negatives']}\n"
        f"grounding_matrix_negative_tests\t{counts['grounding_matrix_negatives']}\n"
        f"overclaim_negative_tests\t{counts['overclaim_negatives']}\n"
        f"section_hash_negative_tests\t{counts['section_hash_negatives']}\n"
        f"receipt_negative_tests\t{counts['receipt_negatives']}\n"
        f"source_ast_negative_tests\t{counts['source_ast_negatives']}\n"
        "predecessor_artifact_hashes_frozen\t7\n"
        "predecessor_exact_receipt\tPASS\n"
        "source_ast_purity\tPASS\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        print(evaluate(args.self_test), end="")
    except (CheckError, ValueError, TypeError, KeyError, OSError, SyntaxError) as error:
        print(f"implementation authority/resource decision pack check failed: {error}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
